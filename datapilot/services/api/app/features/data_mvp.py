"""Immutable cleaning, deterministic analytics, dashboards, and bounded exports.

Every computation uses canonical Parquet produced by ingestion, never a sampled preview.
No client supplied SQL, code, or object-store path is evaluated.
"""

import io
import json
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import Field, field_validator
from sqlalchemy import insert, select, update

from app.core.config import get_settings
from app.features.auth import require_origin
from app.features.contracts import StrictModel
from app.features.data_compute import analyze_rows, clean_rows, filter_rows, generate_export
from app.features.db import get_engine, get_s3
from app.features.routes import User, authorize_workspace
from app.features.tables import feature_import_files
from app.models import (
    analyses,
    audit_events,
    cleaning_plans,
    dashboards,
    dataset_versions,
    datasets,
    jobs,
    quality_findings,
)
from app.processing.parser import number as parsed_number

router = APIRouter(prefix="/api/v1")
MAX_PARQUET_BYTES = 200 * 1024 * 1024
ROLES = {"revenue", "cost", "quantity", "date", "category"}
ExportFormat = Literal["csv", "xlsx", "json", "pdf", "powerbi"]


class CleaningPreview(StrictModel):
    version_id: UUID | None = None
    operations: list[dict[str, Any]] = Field(min_length=1, max_length=20)


class CleaningApply(StrictModel):
    plan_id: UUID


class AnalysisCreate(StrictModel):
    dataset_id: UUID
    version_id: UUID | None = None
    name: str = Field(default="Analysis", min_length=1, max_length=120)
    mapping: dict[str, str] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Name cannot be blank or contain control characters")
        return value.strip()

    @field_validator("mapping")
    @classmethod
    def valid_mapping(cls, value):
        if set(value) - ROLES or any(not v or len(v) > 120 for v in value.values()):
            raise ValueError("Map supported semantic roles to existing column names")
        return value


class DashboardCreate(StrictModel):
    analysis_id: UUID
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Title cannot be blank or contain control characters")
        return value.strip()


def audit(connection, wid, uid, event, resource_type, resource_id, metadata=None):
    connection.execute(
        insert(audit_events).values(
            organization_id=wid,
            actor_user_id=uid,
            event_type=event,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata or {},
        )
    )


def completed_job(connection, wid, uid, vid, kind):
    now = datetime.now(UTC)
    connection.execute(
        insert(jobs).values(
            organization_id=wid,
            created_by=uid,
            dataset_version_id=vid,
            kind=kind,
            status="succeeded",
            progress=100,
            started_at=now,
            finished_at=now,
        )
    )


def version_record(connection, wid, did, vid=None, *, lock=False):
    statement = select(dataset_versions).where(
        dataset_versions.c.organization_id == wid,
        dataset_versions.c.dataset_id == did,
    )
    if vid is not None:
        statement = statement.where(dataset_versions.c.id == vid)
    else:
        statement = statement.order_by(dataset_versions.c.version_number.desc())
    if lock:
        statement = statement.with_for_update()
    record = connection.execute(statement.limit(1)).mappings().first()
    if record is None:
        raise HTTPException(404, "Dataset version not found")
    if record["status"] != "ready" or not record["parquet_object_key"]:
        raise HTTPException(409, "Wait for this dataset version to finish processing")
    return record


def load_rows(version):
    """Read a bounded canonical object; originals remain in the parser sandbox."""
    try:
        with closing(get_s3()) as client:
            result = client.get_object(
                Bucket=get_settings().s3_bucket, Key=version["parquet_object_key"]
            )
            with closing(result["Body"]) as body:
                if result.get("ContentLength", 0) > MAX_PARQUET_BYTES:
                    raise HTTPException(413, "Canonical dataset exceeds the processing limit")
                raw = body.read(MAX_PARQUET_BYTES + 1)
                if len(raw) > MAX_PARQUET_BYTES:
                    raise HTTPException(413, "Canonical dataset exceeds the processing limit")
        table = pq.read_table(pa.BufferReader(raw))
        if table.num_rows > 250_000 or table.num_columns > 50:
            raise HTTPException(413, "Canonical dataset exceeds the processing limit")
        if table.num_rows != version["row_count"] or table.num_columns != version["column_count"]:
            raise HTTPException(409, "Canonical dataset metadata does not match its version")
        return table.to_pylist(), table.column_names
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Canonical dataset is temporarily unavailable") from None


def json_safe(value):
    return jsonable_encoder(value)


def version_summary(version):
    return {
        "id": version["id"],
        "version_id": version["id"],
        "dataset_id": version["dataset_id"],
        "version_number": version["version_number"],
        "parent_version_id": version["parent_version_id"],
        "is_cleaned": version["is_cleaned"],
        "status": version["status"],
        "row_count": version["row_count"],
        "column_count": version["column_count"],
        "created_at": version["created_at"],
        "sha256": version["source_sha256"],
    }


def version_detail(connection, wid, did, version):
    dataset = connection.execute(
        select(datasets.c.name).where(datasets.c.organization_id == wid, datasets.c.id == did)
    ).scalar_one()
    path = connection.execute(
        select(feature_import_files.c.path).where(
            feature_import_files.c.organization_id == wid,
            feature_import_files.c.dataset_id == did,
        )
    ).scalar_one_or_none()
    findings = list(
        connection.execute(
            select(
                quality_findings.c.rule_code,
                quality_findings.c.severity,
                quality_findings.c.column_name,
                quality_findings.c.affected_rows,
                quality_findings.c.details_json.label("details"),
            ).where(
                quality_findings.c.organization_id == wid,
                quality_findings.c.dataset_version_id == version["id"],
            )
        ).mappings()
    )
    schema = version["schema_json"]
    return {
        **version_summary(version),
        "id": did,
        "name": dataset,
        "source_path": path or dataset,
        "columns": schema.get("columns", []),
        "preview": schema.get("preview", []),
        "profile": schema.get("profile", {}),
        "quality": findings,
    }


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/versions")
def list_versions(workspace_id: UUID, dataset_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        records = (
            connection.execute(
                select(dataset_versions)
                .where(
                    dataset_versions.c.organization_id == workspace_id,
                    dataset_versions.c.dataset_id == dataset_id,
                )
                .order_by(dataset_versions.c.version_number.desc())
            )
            .mappings()
            .all()
        )
        if not records:
            raise HTTPException(404, "Dataset not found")
        return [version_summary(record) for record in records]


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/versions/{version_id}")
def get_version(workspace_id: UUID, dataset_id: UUID, version_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        version = version_record(connection, workspace_id, dataset_id, version_id)
        return version_detail(connection, workspace_id, dataset_id, version)


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/cleaning/preview")
def preview_cleaning(
    workspace_id: UUID, dataset_id: UUID, payload: CleaningPreview, request: Request, user: User
):
    require_origin(request)
    with get_engine().begin() as connection:
        authorize_workspace(connection, workspace_id, user["id"], write=True)
        version = version_record(connection, workspace_id, dataset_id, payload.version_id)
        rows, columns = load_rows(version)
        try:
            cleaned, summary = clean_rows(rows, columns, payload.operations)
            # Validate that the entire proposed output is representable before approval.
            canonical_table(cleaned, summary["columns"])
        except (ValueError, TypeError, pa.ArrowException) as exc:
            raise HTTPException(422, str(exc)[:300]) from None
        preview = {
            **summary,
            "operations": payload.operations,
            "summary": summary,
            "version_id": str(version["id"]),
            "preview": json_safe(cleaned[:100]),
        }
        plan_id = uuid4()
        connection.execute(
            insert(cleaning_plans).values(
                id=plan_id,
                organization_id=workspace_id,
                dataset_version_id=version["id"],
                created_by=user["id"],
                operations_json=payload.operations,
                preview_json=preview,
            )
        )
        completed_job(connection, workspace_id, user["id"], version["id"], "clean_preview")
        audit(connection, workspace_id, user["id"], "cleaning.previewed", "cleaning_plan", plan_id)
        return {"id": plan_id, **preview}


def canonical_table(rows, columns):
    # Explicit column list also preserves an empty cleaned table's schema.
    return pa.table({name: [row.get(name) for row in rows] for name in columns})


def cleaned_metadata(table, parent_id, summary):
    columns = []
    findings = []
    rows = table.to_pylist()
    signatures = Counter(json.dumps(json_safe(row), sort_keys=True) for row in rows)
    duplicates = sum(count - 1 for count in signatures.values())
    formula_rows: set[int] = set()
    for field in table.schema:
        column = table.column(field.name)
        typ = (
            "boolean"
            if pa.types.is_boolean(field.type)
            else "integer"
            if pa.types.is_integer(field.type)
            else "number"
            if pa.types.is_floating(field.type) or pa.types.is_decimal(field.type)
            else "date"
            if pa.types.is_date(field.type) or pa.types.is_timestamp(field.type)
            else "string"
        )
        columns.append({"name": field.name, "type": typ, "null_count": column.null_count})
        if typ == "string":
            present = [value for value in column.to_pylist() if value is not None]
            numeric_like = sum(parsed_number(value) is not None for value in present)
            if present and 0.8 <= numeric_like / len(present) < 1:
                findings.append(
                    {
                        "rule_code": "mixed_types",
                        "severity": "warning",
                        "column_name": field.name,
                        "affected_rows": len(present) - numeric_like,
                        "details_json": {
                            "description": "Mostly numeric column includes text; preserved as text."
                        },
                    }
                )
            for row_index, row in enumerate(rows):
                value = row.get(field.name)
                if (
                    value
                    and value.lstrip().startswith(("=", "+", "-", "@"))
                    and parsed_number(value) is None
                ):
                    formula_rows.add(row_index)
        if column.null_count:
            findings.append(
                {
                    "rule_code": "missing_values",
                    "severity": "warning",
                    "column_name": field.name,
                    "affected_rows": column.null_count,
                    "details_json": {"fraction": column.null_count / max(table.num_rows, 1)},
                }
            )
    if duplicates:
        findings.append(
            {
                "rule_code": "duplicate_rows",
                "severity": "warning",
                "column_name": None,
                "affected_rows": duplicates,
                "details_json": {"description": "Exact duplicate occurrences beyond the first."},
            }
        )
    if formula_rows:
        findings.append(
            {
                "rule_code": "formula_like_values",
                "severity": "info",
                "column_name": None,
                "affected_rows": len(formula_rows),
                "details_json": {
                    "description": "Formula-like strings were kept as text, never evaluated."
                },
            }
        )
    preview = json_safe(rows[:100])
    for row in preview:
        for key, value in row.items():
            if isinstance(value, str) and len(value) > 256:
                row[key] = value[:256] + "…"
    return {
        "columns": columns,
        "preview": preview,
        "profile": {
            "duplicate_rows": duplicates,
            "parent_version_id": str(parent_id),
            "cleaning": summary,
            "preview_string_limit": 256,
        },
    }, findings


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/cleaning/apply")
def apply_cleaning(
    workspace_id: UUID, dataset_id: UUID, payload: CleaningApply, request: Request, user: User
):
    require_origin(request)
    stored_key = None
    committed = False
    try:
        with get_engine().begin() as connection:
            authorize_workspace(connection, workspace_id, user["id"], write=True)
            # Serialize version numbering per dataset and repeated approval per plan.
            dataset = connection.execute(
                select(datasets.c.id)
                .where(datasets.c.id == dataset_id, datasets.c.organization_id == workspace_id)
                .with_for_update()
            ).scalar_one_or_none()
            if dataset is None:
                raise HTTPException(404, "Dataset not found")
            plan = (
                connection.execute(
                    select(cleaning_plans)
                    .where(
                        cleaning_plans.c.id == payload.plan_id,
                        cleaning_plans.c.organization_id == workspace_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if plan is None:
                raise HTTPException(404, "Cleaning plan not found")
            parent = version_record(
                connection, workspace_id, dataset_id, plan["dataset_version_id"]
            )
            if plan["status"] == "applied":
                result = version_record(
                    connection, workspace_id, dataset_id, plan["new_version_id"]
                )
                return version_detail(connection, workspace_id, dataset_id, result)
            if plan["status"] != "proposed":
                raise HTTPException(409, "This cleaning plan cannot be applied")
            rows, columns = load_rows(parent)
            try:
                cleaned, summary = clean_rows(rows, columns, plan["operations_json"])
                table = canonical_table(cleaned, summary["columns"])
            except (ValueError, TypeError, pa.ArrowException) as exc:
                raise HTTPException(422, str(exc)[:300]) from None
            schema, findings = cleaned_metadata(table, parent["id"], summary)
            buffer = io.BytesIO()
            pq.write_table(table, buffer, compression="snappy")
            content = buffer.getvalue()
            if len(content) > MAX_PARQUET_BYTES:
                raise HTTPException(413, "Cleaned dataset exceeds the processing limit")
            version_id = uuid4()
            latest = version_record(connection, workspace_id, dataset_id)
            stored_key = f"{workspace_id}/versions/{version_id}/cleaned.parquet"
            with closing(get_s3()) as client:
                client.put_object(
                    Bucket=get_settings().s3_bucket,
                    Key=stored_key,
                    Body=content,
                    ContentLength=len(content),
                    ContentType="application/octet-stream",
                )
            connection.execute(
                insert(dataset_versions).values(
                    id=version_id,
                    organization_id=workspace_id,
                    dataset_id=dataset_id,
                    parent_version_id=parent["id"],
                    version_number=latest["version_number"] + 1,
                    is_cleaned=True,
                    raw_object_key=parent["raw_object_key"],
                    parquet_object_key=stored_key,
                    source_sha256=parent["source_sha256"],
                    schema_json=schema,
                    row_count=table.num_rows,
                    column_count=table.num_columns,
                    status="ready",
                )
            )
            if findings:
                connection.execute(
                    insert(quality_findings),
                    [
                        {
                            "organization_id": workspace_id,
                            "dataset_version_id": version_id,
                            **finding,
                        }
                        for finding in findings
                    ],
                )
            connection.execute(
                update(cleaning_plans)
                .where(cleaning_plans.c.id == payload.plan_id)
                .values(
                    status="applied",
                    approved_by=user["id"],
                    approved_at=datetime.now(UTC),
                    new_version_id=version_id,
                )
            )
            completed_job(connection, workspace_id, user["id"], version_id, "clean_apply")
            audit(
                connection,
                workspace_id,
                user["id"],
                "cleaning.applied",
                "dataset_version",
                version_id,
                {"plan_id": str(payload.plan_id), "parent_version_id": str(parent["id"])},
            )
            result = version_record(connection, workspace_id, dataset_id, version_id)
            response = version_detail(connection, workspace_id, dataset_id, result)
        committed = True
        return response
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            503, "The cleaned version could not be saved. Please try again."
        ) from None
    finally:
        if stored_key and not committed:
            try:
                with closing(get_s3()) as client:
                    client.delete_object(Bucket=get_settings().s3_bucket, Key=stored_key)
            except Exception:
                pass


def analysis_detail(record):
    plan, results = record["plan_json"] or {}, record["results_json"] or {}
    return {
        "id": record["id"],
        "dataset_id": results.get("dataset_id"),
        "version_id": record["dataset_version_id"],
        "source_sha256": (record["evidence_json"] or {}).get("source_sha256"),
        "name": plan.get("name", "Analysis"),
        "status": record["status"],
        "mapping": plan.get("mapping", {}),
        "filters": plan.get("filters", {}),
        "metrics": record["metrics_json"] or {},
        "category_series": results.get("category_series", []),
        "date_series": results.get("date_series", []),
        "series": {
            "category": results.get("category_series", []),
            "date": results.get("date_series", []),
        },
        "insights": (record["insight_json"] or {}).get("items", []),
        "evidence": record["evidence_json"] or {},
        "created_at": record["created_at"],
    }


def analysis_record(connection, wid, aid):
    record = (
        connection.execute(
            select(analyses).where(analyses.c.organization_id == wid, analyses.c.id == aid)
        )
        .mappings()
        .first()
    )
    if record is None:
        raise HTTPException(404, "Analysis not found")
    return record


@router.post("/workspaces/{workspace_id}/analyses", status_code=201)
def create_analysis(workspace_id: UUID, payload: AnalysisCreate, request: Request, user: User):
    require_origin(request)
    with get_engine().begin() as connection:
        authorize_workspace(connection, workspace_id, user["id"], write=True)
        version = version_record(connection, workspace_id, payload.dataset_id, payload.version_id)
        rows, columns = load_rows(version)
        if any(column not in columns for column in payload.mapping.values()):
            raise HTTPException(422, "Mapped columns must exist in this dataset version")
        try:
            result = analyze_rows(rows, payload.mapping, payload.filters)
        except ValueError as exc:
            raise HTTPException(422, str(exc)[:300]) from None
        aid = uuid4()
        evidence = {
            **result["evidence"],
            "dataset_version_id": str(version["id"]),
            "source_sha256": version["source_sha256"],
            "engine": "deterministic-v1",
        }
        connection.execute(
            insert(analyses).values(
                id=aid,
                organization_id=workspace_id,
                dataset_version_id=version["id"],
                created_by=user["id"],
                status="completed",
                completed_at=datetime.now(UTC),
                plan_json={
                    "name": payload.name,
                    "mapping": payload.mapping,
                    "filters": payload.filters,
                },
                metrics_json=result["metrics"],
                results_json={
                    "dataset_id": str(payload.dataset_id),
                    "name": payload.name,
                    "category_series": result["category_series"],
                    "date_series": result["date_series"],
                },
                evidence_json=evidence,
                insight_json={"items": result["insights"]},
                model_version="deterministic-v1",
            )
        )
        completed_job(connection, workspace_id, user["id"], version["id"], "analysis")
        audit(connection, workspace_id, user["id"], "analysis.created", "analysis", aid)
        return analysis_detail(analysis_record(connection, workspace_id, aid))


@router.get("/workspaces/{workspace_id}/analyses")
def list_analyses(workspace_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        records = connection.execute(
            select(analyses)
            .where(analyses.c.organization_id == workspace_id)
            .order_by(analyses.c.created_at.desc())
            .limit(200)
        ).mappings()
        return [analysis_detail(record) for record in records]


@router.get("/workspaces/{workspace_id}/analyses/{analysis_id}")
def get_analysis(workspace_id: UUID, analysis_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        return analysis_detail(analysis_record(connection, workspace_id, analysis_id))


def dashboard_detail(connection, wid, record):
    return {
        "id": record["id"],
        "title": record["title"],
        "analysis_id": record["analysis_id"],
        "created_at": record["created_at"],
        "spec": record["spec_json"],
        "analysis": analysis_detail(analysis_record(connection, wid, record["analysis_id"])),
    }


@router.post("/workspaces/{workspace_id}/dashboards", status_code=201)
def create_dashboard(workspace_id: UUID, payload: DashboardCreate, request: Request, user: User):
    require_origin(request)
    with get_engine().begin() as connection:
        authorize_workspace(connection, workspace_id, user["id"], write=True)
        analysis_record(connection, workspace_id, payload.analysis_id)
        did = uuid4()
        connection.execute(
            insert(dashboards).values(
                id=did,
                organization_id=workspace_id,
                analysis_id=payload.analysis_id,
                created_by=user["id"],
                title=payload.title,
                spec_json={"version": 1, "widgets": ["metrics", "category", "date", "insights"]},
            )
        )
        record = (
            connection.execute(select(dashboards).where(dashboards.c.id == did)).mappings().one()
        )
        audit(connection, workspace_id, user["id"], "dashboard.created", "dashboard", did)
        return dashboard_detail(connection, workspace_id, record)


@router.get("/workspaces/{workspace_id}/dashboards")
def list_dashboards(workspace_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        records = (
            connection.execute(
                select(dashboards)
                .where(dashboards.c.organization_id == workspace_id)
                .order_by(dashboards.c.created_at.desc())
                .limit(200)
            )
            .mappings()
            .all()
        )
        return [dashboard_detail(connection, workspace_id, record) for record in records]


@router.get("/workspaces/{workspace_id}/dashboards/{dashboard_id}")
def get_dashboard(workspace_id: UUID, dashboard_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        record = (
            connection.execute(
                select(dashboards).where(
                    dashboards.c.organization_id == workspace_id, dashboards.c.id == dashboard_id
                )
            )
            .mappings()
            .first()
        )
        if record is None:
            raise HTTPException(404, "Dashboard not found")
        return dashboard_detail(connection, workspace_id, record)


def export_response(format, rows, columns, analysis=None):
    try:
        content, media_type, extension = generate_export(format, rows, columns, json_safe(analysis))
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:300]) from None
    if len(content) > MAX_PARQUET_BYTES:
        raise HTTPException(413, "Export exceeds the supported size")
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="datapilot.{extension}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}/exports/{format}")
def export_dataset(
    workspace_id: UUID,
    dataset_id: UUID,
    format: ExportFormat,
    user: User,
    version_id: UUID | None = None,
):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        version = version_record(connection, workspace_id, dataset_id, version_id)
        rows, columns = load_rows(version)
    return export_response(
        format,
        rows,
        columns,
        {"version_id": str(version["id"]), "source_sha256": version["source_sha256"]},
    )


@router.get("/workspaces/{workspace_id}/analyses/{analysis_id}/exports/{format}")
def export_analysis(workspace_id: UUID, analysis_id: UUID, format: ExportFormat, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        record = analysis_record(connection, workspace_id, analysis_id)
        detail = analysis_detail(record)
        version = version_record(
            connection, workspace_id, UUID(detail["dataset_id"]), record["dataset_version_id"]
        )
        rows, columns = load_rows(version)
    rows = filter_rows(rows, detail["mapping"], detail["filters"])
    return export_response(format, rows, columns, detail)
