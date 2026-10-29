import hashlib
import json
import tempfile
import unicodedata
from contextlib import closing
from pathlib import Path, PurePosixPath
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from app.core.config import get_settings
from app.features.auth import (
    DUMMY_HASH,
    add_session,
    current_user,
    hash_password,
    rate_limit,
    remove_session,
    require_origin,
    verify_password,
)
from app.features.contracts import (
    Credentials,
    DatasetDetail,
    DatasetSummary,
    Identity,
    ImportBatch,
    Registration,
    Workspace,
    WorkspaceCreate,
)
from app.features.db import ensure_bucket, get_engine, get_s3
from app.features.tables import feature_accounts, feature_import_files, feature_imports
from app.models import (
    audit_events,
    dataset_versions,
    datasets,
    jobs,
    memberships,
    organizations,
    quality_findings,
    users,
)

router = APIRouter(prefix="/api/v1")
User = Annotated[dict[str, Any], Depends(current_user)]
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_BATCH_BYTES = 100 * 1024 * 1024
MAX_FILES = 100


def authorize_workspace(connection, workspace_id: UUID, user_id: UUID, write: bool = False):
    workspace = (
        connection.execute(
            select(organizations.c.id, organizations.c.name, memberships.c.role)
            .select_from(
                organizations.join(memberships, organizations.c.id == memberships.c.organization_id)
            )
            .where(
                organizations.c.id == workspace_id,
                memberships.c.user_id == user_id,
                organizations.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    if workspace is None:
        raise HTTPException(404, "Workspace not found")
    if write and workspace["role"] not in {"owner", "analyst"}:
        raise HTTPException(403, "Your workspace role does not allow imports")
    return workspace


def record_audit(connection, organization_id, user_id, event_type, resource_id):
    connection.execute(
        insert(audit_events).values(
            organization_id=organization_id,
            actor_user_id=user_id,
            event_type=event_type,
            resource_type="import",
            resource_id=resource_id,
        )
    )


@router.post("/auth/register", response_model=Identity, status_code=201)
def register(payload: Registration, request: Request, response: Response):
    require_origin(request)
    rate_limit(request, payload.email)
    user_id = uuid4()
    encoded = hash_password(payload.password)
    try:
        with get_engine().begin() as connection:
            connection.execute(
                insert(users).values(
                    id=user_id,
                    oidc_sub="local:" + str(user_id),
                    email=payload.email,
                    display_name=payload.display_name,
                )
            )
            connection.execute(
                insert(feature_accounts).values(
                    user_id=user_id,
                    email_normalized=payload.email,
                    password_hash=encoded,
                )
            )
            add_session(connection, user_id, response)
    except IntegrityError:
        raise HTTPException(409, "This email is already registered") from None
    return {"id": user_id, "email": payload.email, "display_name": payload.display_name}


@router.post("/auth/login", response_model=Identity)
def login(payload: Credentials, request: Request, response: Response):
    require_origin(request)
    rate_limit(request, payload.email)
    with get_engine().begin() as connection:
        record = (
            connection.execute(
                select(
                    users.c.id,
                    users.c.email,
                    users.c.display_name,
                    feature_accounts.c.password_hash,
                )
                .select_from(users.join(feature_accounts, users.c.id == feature_accounts.c.user_id))
                .where(feature_accounts.c.email_normalized == payload.email)
            )
            .mappings()
            .first()
        )
        valid = verify_password(payload.password, record["password_hash"] if record else DUMMY_HASH)
        if record is None or not valid:
            raise HTTPException(401, "Email or password is incorrect")
        add_session(connection, record["id"], response)
        return {key: record[key] for key in ("id", "email", "display_name")}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    require_origin(request)
    remove_session(request, response)


@router.get("/auth/me", response_model=Identity)
def me(user: User, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.get("/workspaces", response_model=list[Workspace])
def list_workspaces(user: User):
    with get_engine().connect() as connection:
        return list(
            connection.execute(
                select(organizations.c.id, organizations.c.name, memberships.c.role)
                .select_from(
                    organizations.join(
                        memberships, organizations.c.id == memberships.c.organization_id
                    )
                )
                .where(memberships.c.user_id == user["id"], organizations.c.status == "active")
                .order_by(organizations.c.created_at)
            ).mappings()
        )


@router.post("/workspaces", response_model=Workspace, status_code=201)
def create_workspace(payload: WorkspaceCreate, request: Request, user: User):
    require_origin(request)
    workspace_id = uuid4()
    with get_engine().begin() as connection:
        connection.execute(insert(organizations).values(id=workspace_id, name=payload.name))
        connection.execute(
            insert(memberships).values(
                organization_id=workspace_id,
                user_id=user["id"],
                role="owner",
            )
        )
        connection.execute(
            insert(audit_events).values(
                organization_id=workspace_id,
                actor_user_id=user["id"],
                event_type="workspace.created",
                resource_type="workspace",
                resource_id=workspace_id,
            )
        )
    return {"id": workspace_id, "name": payload.name, "role": "owner"}


def get_import_batch(connection, workspace_id: UUID, import_id: UUID) -> dict[str, Any]:
    batch = (
        connection.execute(
            select(feature_imports).where(
                feature_imports.c.id == import_id,
                feature_imports.c.organization_id == workspace_id,
            )
        )
        .mappings()
        .first()
    )
    if batch is None:
        raise HTTPException(404, "Import not found")
    files = list(
        connection.execute(
            select(
                feature_import_files.c.id,
                feature_import_files.c.path,
                feature_import_files.c.filename,
                feature_import_files.c.job_id,
                feature_import_files.c.dataset_id,
                feature_import_files.c.dataset_version_id,
                jobs.c.status,
                jobs.c.progress,
                jobs.c.sanitized_error_code.label("error_code"),
                jobs.c.sanitized_error_message.label("error_message"),
            )
            .select_from(
                feature_import_files.join(jobs, feature_import_files.c.job_id == jobs.c.id)
            )
            .where(
                feature_import_files.c.organization_id == workspace_id,
                feature_import_files.c.import_id == import_id,
                jobs.c.organization_id == workspace_id,
            )
            .order_by(feature_import_files.c.path)
        ).mappings()
    )
    statuses = {file["status"] for file in files}
    if statuses == {"succeeded"}:
        status = "succeeded"
    elif "running" in statuses:
        status = "running"
    elif "queued" in statuses:
        status = "queued"
    elif statuses == {"failed"} or statuses == {"cancelled"}:
        status = "failed"
    else:
        status = "partial"
    return {
        "id": batch["id"],
        "name": batch["name"],
        "created_at": batch["created_at"],
        "status": status,
        "total_files": len(files),
        "files": files,
    }


@router.get("/workspaces/{workspace_id}/imports", response_model=list[ImportBatch])
def list_imports(workspace_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        ids = connection.execute(
            select(feature_imports.c.id)
            .where(
                feature_imports.c.organization_id == workspace_id,
            )
            .order_by(feature_imports.c.created_at.desc())
            .limit(100)
        ).scalars()
        return [get_import_batch(connection, workspace_id, import_id) for import_id in ids]


@router.get("/workspaces/{workspace_id}/imports/{import_id}", response_model=ImportBatch)
def import_status(workspace_id: UUID, import_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        return get_import_batch(connection, workspace_id, import_id)


def validate_paths(paths: object, count: int) -> list[str]:
    if (
        not isinstance(paths, list)
        or len(paths) != count
        or not all(isinstance(p, str) for p in paths)
    ):
        raise HTTPException(422, "relative_paths must be a JSON array matching the uploaded files")
    clean: list[str] = []
    for raw in paths:
        path = unicodedata.normalize("NFC", raw)
        parts = path.split("/")
        if (
            not path
            or len(path) > 1024
            or path.startswith("/")
            or "\\" in path
            or ":" in path
            or any(part in {"", ".", ".."} for part in parts)
            or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or not parts[-1].strip()
        ):
            raise HTTPException(
                422, "File paths must be relative and cannot contain traversal segments"
            )
        if PurePosixPath(path).suffix.lower() not in {".csv", ".xlsx"}:
            raise HTTPException(422, "Only CSV and XLSX files can be imported")
        clean.append(path)
    if len(set(clean)) != len(clean):
        raise HTTPException(422, "Duplicate relative file paths are not allowed")
    return clean


IMPORT_REQUEST = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["files"],
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "maxItems": 100,
                        },
                        "relative_paths": {
                            "type": "string",
                            "description": "JSON array, one relative path per file",
                        },
                        "name": {"type": "string", "maxLength": 120},
                    },
                }
            }
        },
    }
}


@router.post(
    "/workspaces/{workspace_id}/imports",
    response_model=ImportBatch,
    status_code=202,
    openapi_extra=IMPORT_REQUEST,
)
async def create_import(workspace_id: UUID, request: Request, user: User):
    require_origin(request)
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"], write=True)
    try:
        form = await request.form(max_files=MAX_FILES, max_fields=4, max_part_size=128 * 1024)
    except (MultiPartException, ValueError):
        raise HTTPException(422, "Invalid multipart upload or too many files") from None
    try:
        if any(key not in {"files", "relative_paths", "name"} for key in form.keys()):
            raise HTTPException(422, "Unexpected import form fields")
        raw_files = form.getlist("files")
        files = [file for file in raw_files if isinstance(file, UploadFile)]
        if not 1 <= len(files) <= MAX_FILES or len(files) != len(raw_files):
            raise HTTPException(422, "Select between 1 and 100 files")
        supplied_paths = form.get("relative_paths")
        try:
            paths = (
                json.loads(supplied_paths)
                if isinstance(supplied_paths, str)
                else [file.filename for file in files]
            )
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(422, "relative_paths must be a valid JSON array") from None
        paths = validate_paths(paths, len(files))
        name = form.get("name", "File import")
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 120
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
        ):
            raise HTTPException(422, "Import name must contain 1 to 120 characters")
        import_id = uuid4()
        staged: list[dict[str, Any]] = []
        total_size = 0
        with tempfile.TemporaryDirectory(prefix="dp-upload-") as temporary:
            for upload, path in zip(files, paths, strict=True):
                dataset_id, version_id, job_id = uuid4(), uuid4(), uuid4()
                local = Path(temporary) / str(version_id)
                digest = hashlib.sha256()
                size = 0
                with local.open("wb") as output:
                    while chunk := await upload.read(1024 * 1024):
                        size += len(chunk)
                        total_size += len(chunk)
                        if size > MAX_FILE_BYTES or total_size > MAX_BATCH_BYTES:
                            raise HTTPException(
                                413, "Limit exceeded: 25 MiB per file and 100 MiB per import"
                            )
                        digest.update(chunk)
                        output.write(chunk)
                if not size:
                    raise HTTPException(422, "Empty files cannot be imported")
                staged.append(
                    {
                        "dataset_id": dataset_id,
                        "version_id": version_id,
                        "job_id": job_id,
                        "path": path,
                        "filename": PurePosixPath(path).name,
                        "size": size,
                        "local": local,
                        "sha256": digest.hexdigest(),
                        "object_key": f"{workspace_id}/versions/{version_id}/source",
                    }
                )
            await run_in_threadpool(
                commit_import, workspace_id, user["id"], import_id, name.strip(), staged
            )
        with get_engine().connect() as connection:
            return get_import_batch(connection, workspace_id, import_id)

    finally:
        await form.close()


def commit_import(workspace_id, user_id, import_id, name, staged):
    stored: list[str] = []
    committed = False
    with closing(get_s3()) as client:
        bucket = get_settings().s3_bucket
        try:
            ensure_bucket(client)
            for file in staged:
                with file["local"].open("rb") as body:
                    client.put_object(
                        Bucket=bucket,
                        Key=file["object_key"],
                        Body=body,
                        ContentLength=file["size"],
                        ContentType="application/octet-stream",
                    )
                stored.append(file["object_key"])
            with get_engine().begin() as connection:
                authorize_workspace(connection, workspace_id, user_id, write=True)
                connection.execute(
                    insert(feature_imports).values(
                        id=import_id,
                        organization_id=workspace_id,
                        created_by=user_id,
                        name=name,
                    )
                )
                for file in staged:
                    connection.execute(
                        insert(datasets).values(
                            id=file["dataset_id"],
                            organization_id=workspace_id,
                            created_by=user_id,
                            name=file["filename"],
                            source_type=PurePosixPath(file["path"]).suffix[1:].lower(),
                            status="uploaded",
                        )
                    )
                    connection.execute(
                        insert(dataset_versions).values(
                            id=file["version_id"],
                            organization_id=workspace_id,
                            dataset_id=file["dataset_id"],
                            version_number=1,
                            raw_object_key=file["object_key"],
                            source_sha256=file["sha256"],
                            status="uploaded",
                        )
                    )
                    connection.execute(
                        insert(jobs).values(
                            id=file["job_id"],
                            organization_id=workspace_id,
                            created_by=user_id,
                            dataset_version_id=file["version_id"],
                            kind="ingest",
                            status="queued",
                        )
                    )
                    connection.execute(
                        insert(feature_import_files).values(
                            organization_id=workspace_id,
                            import_id=import_id,
                            path=file["path"],
                            filename=file["filename"],
                            dataset_id=file["dataset_id"],
                            dataset_version_id=file["version_id"],
                            job_id=file["job_id"],
                        )
                    )
                record_audit(connection, workspace_id, user_id, "import.created", import_id)
            committed = True
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "The import could not be saved. Please try again.") from None
        finally:
            if not committed:
                for key in stored:
                    try:
                        client.delete_object(Bucket=bucket, Key=key)
                    except Exception:
                        # Unreferenced random objects remain inaccessible through the API.
                        pass


@router.post("/workspaces/{workspace_id}/imports/{import_id}/retry", response_model=ImportBatch)
def retry_import(workspace_id: UUID, import_id: UUID, request: Request, user: User):
    require_origin(request)
    with get_engine().begin() as connection:
        authorize_workspace(connection, workspace_id, user["id"], write=True)
        batch = get_import_batch(connection, workspace_id, import_id)
        failed = [file for file in batch["files"] if file["status"] == "failed"]
        if not failed:
            raise HTTPException(409, "This import has no failed files to retry")
        for file in failed:
            # Conditional update keeps concurrent retry requests from resetting a running job.
            changed = connection.execute(
                update(jobs)
                .where(
                    jobs.c.id == file["job_id"],
                    jobs.c.organization_id == workspace_id,
                    jobs.c.status == "failed",
                )
                .values(
                    status="queued",
                    progress=0,
                    sanitized_error_code=None,
                    sanitized_error_message=None,
                    started_at=None,
                    finished_at=None,
                )
            )
            if changed.rowcount:
                connection.execute(
                    update(dataset_versions)
                    .where(
                        dataset_versions.c.id == file["dataset_version_id"],
                        dataset_versions.c.organization_id == workspace_id,
                    )
                    .values(status="uploaded")
                )
                connection.execute(
                    update(datasets)
                    .where(
                        datasets.c.id == file["dataset_id"],
                        datasets.c.organization_id == workspace_id,
                    )
                    .values(status="uploaded")
                )
                connection.execute(
                    delete(quality_findings).where(
                        quality_findings.c.dataset_version_id == file["dataset_version_id"],
                        quality_findings.c.organization_id == workspace_id,
                    )
                )
        record_audit(connection, workspace_id, user["id"], "import.retried", import_id)
        return get_import_batch(connection, workspace_id, import_id)


def dataset_query(workspace_id: UUID):
    return (
        select(
            datasets.c.id,
            datasets.c.name,
            datasets.c.status,
            datasets.c.created_at,
            dataset_versions.c.id.label("version_id"),
            dataset_versions.c.row_count,
            dataset_versions.c.column_count,
            feature_import_files.c.path.label("source_path"),
        )
        .select_from(
            datasets.join(dataset_versions, datasets.c.id == dataset_versions.c.dataset_id).join(
                feature_import_files,
                dataset_versions.c.id == feature_import_files.c.dataset_version_id,
            )
        )
        .where(
            datasets.c.organization_id == workspace_id,
            dataset_versions.c.organization_id == workspace_id,
            feature_import_files.c.organization_id == workspace_id,
        )
    )


@router.get("/workspaces/{workspace_id}/datasets", response_model=list[DatasetSummary])
def list_datasets(workspace_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        return list(
            connection.execute(
                dataset_query(workspace_id).order_by(datasets.c.created_at.desc()).limit(500)
            ).mappings()
        )


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}", response_model=DatasetDetail)
def get_dataset(workspace_id: UUID, dataset_id: UUID, user: User):
    with get_engine().connect() as connection:
        authorize_workspace(connection, workspace_id, user["id"])
        summary = (
            connection.execute(dataset_query(workspace_id).where(datasets.c.id == dataset_id))
            .mappings()
            .first()
        )
        if summary is None:
            raise HTTPException(404, "Dataset not found")
        version = (
            connection.execute(
                select(dataset_versions.c.schema_json, dataset_versions.c.source_sha256).where(
                    dataset_versions.c.id == summary["version_id"],
                    dataset_versions.c.organization_id == workspace_id,
                )
            )
            .mappings()
            .one()
        )
        findings = list(
            connection.execute(
                select(
                    quality_findings.c.rule_code,
                    quality_findings.c.severity,
                    quality_findings.c.column_name,
                    quality_findings.c.affected_rows,
                    quality_findings.c.details_json.label("details"),
                )
                .where(
                    quality_findings.c.organization_id == workspace_id,
                    quality_findings.c.dataset_version_id == summary["version_id"],
                )
                .order_by(quality_findings.c.severity, quality_findings.c.rule_code)
            ).mappings()
        )
        schema = version["schema_json"]
        return {
            **summary,
            "columns": schema.get("columns", []),
            "preview": schema.get("preview", []),
            "profile": schema.get("profile", {}),
            "quality": findings,
            "sha256": version["source_sha256"],
        }
