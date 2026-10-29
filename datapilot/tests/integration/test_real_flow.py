"""API security/lifecycle checks against an empty disposable PostgreSQL database.

Set DATAPILOT_FLOW_DATABASE_URL separately from the migration test's database.
Object storage is replaced with a byte-preserving fake; real storage/worker execution
is exercised by scripts/real-flow-smoke.py instead.
"""

import hashlib
import io
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

pytestmark = pytest.mark.integration
ORIGIN = "http://localhost:3000"
CSV = b"product,amount,note\nNotebook,120,\nNotebook,120,\nPencil,90,ready\n"


class MemoryObjects:
    def __init__(self):
        self.objects = {}

    def close(self):
        pass

    def head_bucket(self, **kwargs):
        return {}

    def create_bucket(self, **kwargs):
        return {}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        body = Body.read() if hasattr(Body, "read") else Body
        self.objects[Bucket, Key] = bytes(body)
        return {"ETag": hashlib.md5(body, usedforsecurity=False).hexdigest()}

    def delete_object(self, *, Bucket, Key, **kwargs):
        self.objects.pop((Bucket, Key), None)
        return {}


@pytest.fixture
def api(flow_app, monkeypatch):
    from app.features import routes

    storage = MemoryObjects()
    monkeypatch.setattr(routes, "get_s3", lambda: storage)
    monkeypatch.setattr(routes, "rate_limit", lambda *_: None)
    with TestClient(flow_app, headers={"Origin": ORIGIN}) as client:
        yield client, storage


def account(client):
    credentials = {
        "email": f"test-{uuid4().hex}@example.test",
        "password": secrets.token_urlsafe(24),
        "display_name": "Flow Test",
    }
    response = client.post("/api/v1/auth/register", json=credentials)
    assert response.status_code == 201
    assert "password" not in response.json()
    return credentials, response.json()


def workspace(client):
    response = client.post("/api/v1/workspaces", json={"name": "Flow validation workspace"})
    assert response.status_code == 201
    assert response.json()["role"] == "owner"
    return response.json()


def submit(client, workspace_id, files=None, paths=None):
    if files is None:
        files = [("sales.csv", CSV, "text/csv")]
    if paths is None:
        paths = [item[0] for item in files]
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/imports",
        data={"relative_paths": json.dumps(paths), "name": "Folder import"},
        files=[("files", (filename, io.BytesIO(body), mime)) for filename, body, mime in files],
    )


def test_authentication_session_revocation_and_password_storage(api):
    from app.features.db import get_engine
    from app.features.tables import feature_accounts, feature_sessions

    client, _ = api
    assert client.get("/api/v1/auth/me").status_code == 401
    credentials, identity = account(client)
    cookie = client.cookies.get("dp_session")
    assert cookie
    assert client.get("/api/v1/auth/me").json()["id"] == identity["id"]
    with get_engine().connect() as connection:
        record = connection.execute(select(feature_accounts)).mappings().all()
        assert all(row["password_hash"] != credentials["password"] for row in record)
        assert all(row["password_hash"].startswith("scrypt$") for row in record)
        sessions = connection.execute(select(feature_sessions.c.token_hash)).scalars().all()
        assert cookie not in sessions
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code in {200, 204}
    assert client.get("/api/v1/auth/me").status_code == 401
    with TestClient(client.app, cookies={"dp_session": cookie}) as replay:
        assert replay.get("/api/v1/auth/me").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": credentials["email"].upper(),
            "password": credentials["password"],
        },
    )
    assert login.status_code == 200
    assert login.json()["id"] == identity["id"]
    session_cookie = login.headers.get("set-cookie", "").lower()
    assert "httponly" in session_cookie and "samesite=strict" in session_cookie
    with get_engine().begin() as connection:
        connection.execute(
            update(feature_sessions).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_duplicate_email_and_origin_validation(api):
    client, _ = api
    credentials, _ = account(client)
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 409
    short = {**credentials, "email": f"short-{uuid4().hex}@example.test", "password": "short"}
    assert client.post("/api/v1/auth/register", json=short).status_code == 422
    invalid_email = {**credentials, "email": "not-an-email"}
    assert client.post("/api/v1/auth/register", json=invalid_email).status_code == 422
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": credentials["email"],
                "password": "wrong-password-12345",
            },
        ).status_code
        == 401
    )
    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Rejected origin"},
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403
    client.headers.pop("Origin")
    assert client.post("/api/v1/workspaces", json={"name": "Missing origin"}).status_code == 403
    client.headers["Origin"] = ORIGIN


def test_multi_file_folder_import_preserves_original_bytes_and_scopes(api):
    from app.features.db import get_engine
    from app.models import dataset_versions, jobs

    client, storage = api
    account(client)
    own_workspace = workspace(client)
    wid = own_workspace["id"]
    assert any(w["id"] == wid for w in client.get("/api/v1/workspaces").json())
    response = submit(
        client,
        wid,
        files=[
            ("sales.csv", CSV, "text/csv"),
            ("inventory.csv", b"sku,quantity\nA,3\nB,8\n", "text/csv"),
        ],
        paths=["source/sales.csv", "source/nested/inventory.csv"],
    )
    assert response.status_code == 202
    batch = response.json()
    assert batch["status"] == "queued" and batch["total_files"] == 2
    assert {f["path"] for f in batch["files"]} == {
        "source/sales.csv",
        "source/nested/inventory.csv",
    }
    assert all(f["status"] == "queued" for f in batch["files"])
    assert set(storage.objects.values()) == {CSV, b"sku,quantity\nA,3\nB,8\n"}
    assert all("source/" not in key for _, key in storage.objects)
    with get_engine().connect() as connection:
        file_ids = [f["job_id"] for f in batch["files"]]
        records = connection.execute(select(jobs).where(jobs.c.id.in_(file_ids))).mappings().all()
        assert len(records) == 2 and all(str(j["organization_id"]) == wid for j in records)
        versions = (
            connection.execute(
                select(dataset_versions).where(
                    dataset_versions.c.id.in_([f["dataset_version_id"] for f in batch["files"]]),
                )
            )
            .mappings()
            .all()
        )
        assert {v["source_sha256"] for v in versions} == {
            hashlib.sha256(body).hexdigest() for body in storage.objects.values()
        }
    assert client.get(f"/api/v1/workspaces/{wid}/imports/{batch['id']}").status_code == 200
    assert len(client.get(f"/api/v1/workspaces/{wid}/datasets").json()) == 2


@pytest.mark.parametrize(
    "paths",
    [
        ["../outside.csv"],
        ["/absolute.csv"],
        ["a\\b.csv"],
        ["folder/../outside.csv"],
        ["C:/outside.csv"],
    ],
)
def test_upload_rejects_unsafe_paths(api, paths):
    client, storage = api
    account(client)
    own_workspace = workspace(client)
    response = submit(client, own_workspace["id"], paths=paths)
    assert response.status_code == 422
    assert not storage.objects


def test_upload_rejects_duplicates_mismatched_paths_types_and_count(api):
    client, storage = api
    account(client)
    wid = workspace(client)["id"]
    duplicate = submit(
        client, wid, files=[("a.csv", CSV, "text/csv")] * 2, paths=["folder/a.csv"] * 2
    )
    assert duplicate.status_code == 422
    assert submit(client, wid, paths=[]).status_code == 422
    unsupported = submit(client, wid, files=[("program.py", b"print(1)", "text/plain")])
    assert unsupported.status_code in {415, 422}
    too_many = submit(client, wid, files=[(f"{i}.csv", b"a\n1\n", "text/csv") for i in range(101)])
    assert too_many.status_code in {400, 413, 422}
    assert not storage.objects


def test_cross_account_access_and_viewer_write_denial(api):
    from app.features.db import get_engine
    from app.models import memberships

    owner, _ = api
    account(owner)
    wid = workspace(owner)["id"]
    imported = submit(owner, wid)
    assert imported.status_code == 202
    batch = imported.json()
    dataset_id = batch["files"][0]["dataset_id"]
    with TestClient(owner.app, headers={"Origin": ORIGIN}) as stranger:
        _, other_user = account(stranger)
        assert all(w["id"] != wid for w in stranger.get("/api/v1/workspaces").json())
        for path in [
            f"/workspaces/{wid}/datasets",
            f"/workspaces/{wid}/imports",
            f"/workspaces/{wid}/imports/{batch['id']}",
            f"/workspaces/{wid}/datasets/{dataset_id}",
        ]:
            assert stranger.get("/api/v1" + path).status_code == 404
        assert submit(stranger, wid).status_code == 404
        assert (
            stranger.post(f"/api/v1/workspaces/{wid}/imports/{batch['id']}/retry").status_code
            == 404
        )
        with get_engine().begin() as connection:
            connection.execute(
                insert(memberships).values(
                    organization_id=wid,
                    user_id=other_user["id"],
                    role="viewer",
                )
            )
        assert stranger.get(f"/api/v1/workspaces/{wid}/datasets/{dataset_id}").status_code == 200
        assert submit(stranger, wid).status_code == 403
        assert (
            stranger.post(f"/api/v1/workspaces/{wid}/imports/{batch['id']}/retry").status_code
            == 403
        )


def test_retry_only_failed_files_without_changing_source(api):
    from app.features.db import get_engine
    from app.models import jobs

    client, storage = api
    account(client)
    wid = workspace(client)["id"]
    batch = submit(
        client, wid, files=[("a.csv", CSV, "text/csv"), ("b.csv", b"x\n2\n", "text/csv")]
    ).json()
    first, second = batch["files"]
    before = dict(storage.objects)
    with get_engine().begin() as connection:
        connection.execute(
            update(jobs)
            .where(jobs.c.id == first["job_id"])
            .values(
                status="failed",
                sanitized_error_code="test_failure",
                sanitized_error_message="Retryable validation fixture",
                progress=0,
            )
        )
        connection.execute(
            update(jobs)
            .where(jobs.c.id == second["job_id"])
            .values(
                status="succeeded",
                progress=100,
            )
        )
    response = client.post(f"/api/v1/workspaces/{wid}/imports/{batch['id']}/retry")
    assert response.status_code in {200, 202}
    statuses = {f["id"]: f["status"] for f in response.json()["files"]}
    assert statuses[first["id"]] == "queued"
    assert statuses[second["id"]] == "succeeded"
    assert before == storage.objects


def test_storage_failure_rolls_back_metadata_and_uploaded_objects(api, monkeypatch):
    client, storage = api
    account(client)
    wid = workspace(client)["id"]
    put = storage.put_object

    def fail_second_upload(**kwargs):
        if storage.objects:
            raise RuntimeError("internal-storage-endpoint-must-not-leak")
        return put(**kwargs)

    monkeypatch.setattr(storage, "put_object", fail_second_upload)
    response = submit(
        client, wid, files=[("a.csv", CSV, "text/csv"), ("b.csv", b"a\n1\n", "text/csv")]
    )
    assert response.status_code == 503
    assert "internal-storage-endpoint" not in response.text
    assert not storage.objects
    assert client.get(f"/api/v1/workspaces/{wid}/imports").json() == []
    assert client.get(f"/api/v1/workspaces/{wid}/datasets").json() == []


def test_actual_per_file_limit_is_enforced_before_storage(api):
    from app.features.routes import MAX_FILE_BYTES

    client, storage = api
    account(client)
    wid = workspace(client)["id"]
    response = submit(client, wid, files=[("large.csv", b"x" * (MAX_FILE_BYTES + 1), "text/csv")])
    assert response.status_code == 413
    assert not storage.objects
    assert client.get(f"/api/v1/workspaces/{wid}/imports").json() == []


def test_batch_byte_limit_is_separate_from_per_file_limit(api, monkeypatch):
    from app.features import routes

    client, storage = api
    account(client)
    wid = workspace(client)["id"]
    # Lower only the aggregate cap to exercise boundary handling without allocating 100 MiB.
    monkeypatch.setattr(routes, "MAX_BATCH_BYTES", len(CSV) * 2 - 1)
    response = submit(client, wid, files=[("a.csv", CSV, "text/csv"), ("b.csv", CSV, "text/csv")])
    assert response.status_code == 413
    assert not storage.objects
    assert client.get(f"/api/v1/workspaces/{wid}/imports").json() == []
