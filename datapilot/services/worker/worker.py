"""Celery orchestration: durable queued jobs, bounded dispatch and isolated parsing."""

import hashlib
import logging
import tempfile
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.features.db import get_engine, get_s3
from app.features.tables import feature_import_files
from app.models import dataset_versions, datasets, jobs, quality_findings
from app.processing.launch import IngestionFailure, run_restricted
from celery import Celery
from sqlalchemy import and_, delete, func, insert, select, update

settings = get_settings()
logger = logging.getLogger("datapilot.worker")
celery_app = Celery("datapilot", broker=settings.redis_url.get_secret_value())
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_connection_retry_on_startup=True,
    task_time_limit=180,
    task_soft_time_limit=170,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_transport_options={"visibility_timeout": 300},
    beat_schedule={"dispatch-imports": {"task": "datapilot.dispatch_pending", "schedule": 5.0}},
)


@celery_app.task(name="datapilot.ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}


def scoped(table, org, identifier):
    return and_(table.c.organization_id == org, table.c.id == identifier)


def fail_job(connection, row, code: str, message: str) -> None:
    connection.execute(
        update(jobs)
        .where(scoped(jobs, row["organization_id"], row["id"]))
        .values(
            status="failed",
            sanitized_error_code=code,
            sanitized_error_message=message,
            finished_at=datetime.now(UTC),
        )
    )
    connection.execute(
        update(dataset_versions)
        .where(scoped(dataset_versions, row["organization_id"], row["dataset_version_id"]))
        .values(status="failed")
    )
    connection.execute(
        update(datasets)
        .where(scoped(datasets, row["organization_id"], row["dataset_id"]))
        .values(status="failed")
    )


@celery_app.task(name="datapilot.dispatch_pending", time_limit=30, soft_time_limit=25)
def dispatch_pending() -> dict[str, int]:
    """Database queue is authoritative; lost broker publishes are recovered by polling."""
    now = datetime.now(UTC)
    job_files = jobs.join(
        feature_import_files,
        and_(
            feature_import_files.c.job_id == jobs.c.id,
            feature_import_files.c.organization_id == jobs.c.organization_id,
        ),
    )
    to_publish: list[str] = []
    with get_engine().begin() as connection:
        stale = (
            connection.execute(
                select(
                    jobs.c.id,
                    jobs.c.organization_id,
                    jobs.c.dataset_version_id,
                    feature_import_files.c.dataset_id,
                )
                .select_from(job_files)
                .where(
                    jobs.c.kind == "ingest",
                    jobs.c.status == "running",
                    jobs.c.started_at < now - timedelta(minutes=10),
                )
                .with_for_update(of=jobs, skip_locked=True)
            )
            .mappings()
            .all()
        )
        for row in stale:
            fail_job(
                connection,
                row,
                "worker_interrupted",
                "Processing was interrupted; retry this file.",
            )
        connection.execute(
            update(jobs)
            .where(
                jobs.c.kind == "ingest",
                jobs.c.status == "queued",
                jobs.c.progress == 1,
                jobs.c.started_at < now - timedelta(minutes=5),
            )
            .values(progress=0, started_at=None)
        )
        pending = connection.execute(
            select(func.count())
            .select_from(jobs)
            .where(
                jobs.c.kind == "ingest",
                (jobs.c.status == "running")
                | ((jobs.c.status == "queued") & (jobs.c.progress == 1)),
            )
        ).scalar_one()
        capacity = max(0, 4 - pending)
        if capacity:
            ids = (
                connection.execute(
                    select(jobs.c.id)
                    .select_from(job_files)
                    .where(
                        jobs.c.kind == "ingest",
                        jobs.c.status == "queued",
                        jobs.c.progress == 0,
                    )
                    .order_by(jobs.c.created_at)
                    .limit(capacity)
                    .with_for_update(of=jobs, skip_locked=True)
                )
                .scalars()
                .all()
            )
            for identifier in ids:
                connection.execute(
                    update(jobs)
                    .where(jobs.c.id == identifier)
                    .values(
                        progress=1,
                        started_at=now,
                    )
                )
                to_publish.append(str(identifier))
    published = 0
    for identifier in to_publish:
        try:
            ingest.apply_async(args=[identifier])
            published += 1
        except Exception:
            # Keep the reservation; the next poll recovers it after five minutes.
            logger.error("queue_publish_failed job_id=%s", identifier)
    return {"published": published, "recovered_failed": len(stale)}


@celery_app.task(name="datapilot.ingest", time_limit=180, soft_time_limit=170)
def ingest(job_id: str) -> dict[str, str]:
    identifier = UUID(job_id)
    with get_engine().begin() as connection:
        query = (
            select(
                jobs.c.id,
                jobs.c.organization_id,
                jobs.c.dataset_version_id,
                feature_import_files.c.dataset_id,
                dataset_versions.c.raw_object_key,
                dataset_versions.c.source_sha256,
                datasets.c.source_type,
            )
            .select_from(
                jobs.join(
                    feature_import_files,
                    and_(
                        feature_import_files.c.job_id == jobs.c.id,
                        feature_import_files.c.organization_id == jobs.c.organization_id,
                    ),
                )
                .join(
                    dataset_versions,
                    and_(
                        dataset_versions.c.id == jobs.c.dataset_version_id,
                        dataset_versions.c.organization_id == jobs.c.organization_id,
                    ),
                )
                .join(
                    datasets,
                    and_(
                        datasets.c.id == feature_import_files.c.dataset_id,
                        datasets.c.organization_id == jobs.c.organization_id,
                    ),
                )
            )
            .where(jobs.c.id == identifier, jobs.c.kind == "ingest", jobs.c.status == "queued")
        )
        claimed = (
            connection.execute(query.with_for_update(of=jobs, skip_locked=True)).mappings().first()
        )
        if claimed is None:
            return {"status": "already_claimed"}
        row = dict(claimed)
        connection.execute(
            update(jobs)
            .where(jobs.c.id == identifier)
            .values(
                status="running",
                progress=10,
                started_at=datetime.now(UTC),
                attempt_count=jobs.c.attempt_count + 1,
            )
        )
        connection.execute(
            update(dataset_versions)
            .where(scoped(dataset_versions, row["organization_id"], row["dataset_version_id"]))
            .values(status="validating")
        )
        connection.execute(
            update(datasets)
            .where(scoped(datasets, row["organization_id"], row["dataset_id"]))
            .values(status="validating")
        )
    try:
        with tempfile.TemporaryDirectory(prefix="datapilot-job-") as staging:
            directory = Path(staging)
            digest = hashlib.sha256()
            total = 0
            with closing(get_s3()) as s3:
                original = s3.get_object(Bucket=settings.s3_bucket, Key=row["raw_object_key"])
                with closing(original["Body"]) as body, (directory / "input").open("wb") as target:
                    while chunk := body.read(1024 * 1024):
                        total += len(chunk)
                        if total > 25 * 1024**2:
                            raise IngestionFailure("file_size", "The file exceeds 25 MiB.")
                        digest.update(chunk)
                        target.write(chunk)
            if digest.hexdigest() != row["source_sha256"]:
                raise IngestionFailure(
                    "checksum_mismatch", "Stored source checksum verification failed."
                )
            with get_engine().begin() as connection:
                connection.execute(update(jobs).where(jobs.c.id == identifier).values(progress=35))
                connection.execute(
                    update(dataset_versions)
                    .where(
                        scoped(dataset_versions, row["organization_id"], row["dataset_version_id"])
                    )
                    .values(status="profiling")
                )
                connection.execute(
                    update(datasets)
                    .where(scoped(datasets, row["organization_id"], row["dataset_id"]))
                    .values(status="profiling")
                )
            result = run_restricted(directory, row["source_type"])
            if result.get("sha256") != row["source_sha256"]:
                raise IngestionFailure(
                    "checksum_mismatch", "Parser source checksum verification failed."
                )
            parquet = directory / "output.parquet"
            if not parquet.is_file() or parquet.stat().st_size > 512 * 1024**2:
                raise IngestionFailure(
                    "invalid_result", "The parser output is missing or too large."
                )
            key = f"{row['organization_id']}/versions/{row['dataset_version_id']}/data.parquet"
            with closing(get_s3()) as s3, parquet.open("rb") as body:
                s3.put_object(
                    Bucket=settings.s3_bucket,
                    Key=key,
                    Body=body,
                    ContentType="application/vnd.apache.parquet",
                )
            with get_engine().begin() as connection:
                connection.execute(
                    delete(quality_findings).where(
                        quality_findings.c.organization_id == row["organization_id"],
                        quality_findings.c.dataset_version_id == row["dataset_version_id"],
                    )
                )
                for finding in result["quality"]:
                    connection.execute(
                        insert(quality_findings).values(
                            organization_id=row["organization_id"],
                            dataset_version_id=row["dataset_version_id"],
                            **finding,
                        )
                    )
                schema = result["schema_json"]
                schema["profile"]["isolation"] = result["isolation"]
                connection.execute(
                    update(dataset_versions)
                    .where(
                        scoped(dataset_versions, row["organization_id"], row["dataset_version_id"])
                    )
                    .values(
                        status="ready",
                        parquet_object_key=key,
                        row_count=result["row_count"],
                        column_count=result["column_count"],
                        schema_json=schema,
                    )
                )
                connection.execute(
                    update(datasets)
                    .where(scoped(datasets, row["organization_id"], row["dataset_id"]))
                    .values(status="ready")
                )
                connection.execute(
                    update(jobs)
                    .where(scoped(jobs, row["organization_id"], identifier))
                    .values(
                        status="succeeded",
                        progress=100,
                        finished_at=datetime.now(UTC),
                        sanitized_error_code=None,
                        sanitized_error_message=None,
                    )
                )
        logger.info("ingest_succeeded job_id=%s", identifier)
        return {"status": "succeeded"}
    except IngestionFailure as exc:
        code, message = exc.code, exc.message
    except Exception:
        code, message = (
            "processing_failed",
            "Processing failed; retry or inspect the source format.",
        )
    with get_engine().begin() as connection:
        fail_job(connection, row, code, message)
    logger.warning("ingest_failed job_id=%s error_code=%s", identifier, code)
    return {"status": "failed", "error_code": code}
