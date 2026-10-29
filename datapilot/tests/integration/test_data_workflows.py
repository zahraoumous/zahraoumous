"""Immutable cleaning and deterministic analytics through authenticated API routes."""

import io
from unittest.mock import patch
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update
from test_real_flow import account, submit, workspace
from test_real_flow import api as source_api  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def data_api(source_api, monkeypatch):  # noqa: F811 - imported pytest fixture
    from app.features import data_mvp
    from app.features.db import get_engine
    from app.models import dataset_versions, datasets

    client, storage = source_api

    def get_object(*, Bucket, Key):
        content = storage.objects[Bucket, Key]
        return {"Body": io.BytesIO(content), "ContentLength": len(content)}

    storage.get_object = get_object
    monkeypatch.setattr(data_mvp, "get_s3", lambda: storage)
    credentials, identity = account(client)
    wid = workspace(client)["id"]
    batch = submit(client, wid).json()
    source = batch["files"][0]
    did, vid = source["dataset_id"], source["dataset_version_id"]
    table = pa.table(
        {
            "product": [" A ", " A ", "B"],
            "amount": [120, 120, 90],
            "cost": [40, 40, 30],
            "note": [None, None, "ready"],
        }
    )
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    parquet_key = f"{wid}/versions/{vid}/canonical.parquet"
    from app.core.config import get_settings

    storage.objects[get_settings().s3_bucket, parquet_key] = buffer.getvalue()
    with get_engine().begin() as connection:
        connection.execute(
            update(datasets).where(datasets.c.id == UUID(did)).values(status="ready")
        )
        connection.execute(
            update(dataset_versions)
            .where(dataset_versions.c.id == UUID(vid))
            .values(
                status="ready",
                parquet_object_key=parquet_key,
                row_count=3,
                column_count=4,
                schema_json={
                    "columns": [
                        {"name": name, "type": "string", "null_count": 0}
                        for name in table.column_names
                    ],
                    "preview": table.to_pylist(),
                },
            )
        )
    yield client, storage, wid, did, vid, credentials, identity


def test_preview_apply_is_immutable_idempotent_and_exact(data_api):
    client, storage, wid, did, original, *_ = data_api
    before = dict(storage.objects)
    base = f"/api/v1/workspaces/{wid}/datasets/{did}"
    plan = client.post(
        base + "/cleaning/preview",
        json={
            "version_id": original,
            "operations": [{"op": "trim"}, {"op": "drop_duplicates"}],
        },
    )
    assert plan.status_code == 200, plan.text
    assert plan.json()["before_rows"] == 3
    assert plan.json()["after_rows"] == 2
    assert storage.objects == before
    applied = client.post(base + "/cleaning/apply", json={"plan_id": plan.json()["id"]})
    assert applied.status_code == 200, applied.text
    cleaned = applied.json()
    assert cleaned["is_cleaned"] and cleaned["parent_version_id"] == original
    assert cleaned["version_number"] == 2 and cleaned["row_count"] == 2
    assert cleaned["preview"][0]["product"] == "A"
    assert cleaned["version_id"] != original
    replay = client.post(base + "/cleaning/apply", json={"plan_id": plan.json()["id"]})
    assert replay.status_code == 200
    assert replay.json()["version_id"] == cleaned["version_id"]
    assert all(storage.objects[key] == value for key, value in before.items())
    versions = client.get(base + "/versions").json()
    assert len(versions) == 2
    assert client.get(base + f"/versions/{original}").json()["row_count"] == 3
    assert client.get(base + f"/versions/{cleaned['version_id']}").json()["row_count"] == 2


def test_analysis_dashboard_filters_and_downloads(data_api):
    client, _, wid, did, vid, *_ = data_api
    base = f"/api/v1/workspaces/{wid}"
    created = client.post(
        base + "/analyses",
        json={
            "dataset_id": did,
            "version_id": vid,
            "name": "Sales",
            "mapping": {"revenue": "amount", "cost": "cost", "category": "product"},
        },
    )
    assert created.status_code == 201, created.text
    analysis = created.json()
    assert analysis["metrics"]["revenue"] == "330"
    assert analysis["metrics"]["profit"] == "220"
    assert analysis["evidence"]["rows_total"] == 3
    assert analysis["evidence"]["dataset_version_id"] == vid
    assert len(analysis["category_series"]) == 2
    aid = analysis["id"]
    assert client.get(base + f"/analyses/{aid}").json()["metrics"] == analysis["metrics"]
    dashboard = client.post(base + "/dashboards", json={"analysis_id": aid, "title": "Sales KPI"})
    assert dashboard.status_code == 201
    dashboard_id = dashboard.json()["id"]
    assert client.get(base + f"/dashboards/{dashboard_id}").json()["analysis"]["id"] == aid
    assert client.get(base + "/dashboards").json()[0]["id"] == dashboard_id
    for kind, signature in [
        ("csv", b"product"),
        ("xlsx", b"PK"),
        ("json", b"{"),
        ("pdf", b"%PDF"),
        ("powerbi", b"PK"),
    ]:
        response = client.get(base + f"/analyses/{aid}/exports/{kind}")
        assert response.status_code == 200, response.text[:200]
        assert response.content.removeprefix(b"\xef\xbb\xbf").startswith(signature)
        assert "attachment" in response.headers["content-disposition"]
    invalid = client.post(
        base + "/analyses",
        json={
            "dataset_id": did,
            "mapping": {"revenue": "no-such-column"},
        },
    )
    assert invalid.status_code == 422


def test_mvp_cross_workspace_and_viewer_boundaries(data_api):
    from app.features.db import get_engine
    from app.models import memberships

    owner, _, wid, did, vid, *_ = data_api
    base = f"/api/v1/workspaces/{wid}"
    with TestClient(owner.app, headers={"Origin": "http://localhost:3000"}) as stranger:
        with patch("app.features.routes.rate_limit", lambda *_: None):
            _, identity = account(stranger)
        assert stranger.get(base + f"/datasets/{did}/versions").status_code == 404
        assert stranger.get(base + f"/datasets/{did}/exports/csv").status_code == 404
        assert stranger.get(base + "/analyses").status_code == 404
        assert stranger.get(base + "/dashboards").status_code == 404
        assert (
            stranger.post(
                base + f"/datasets/{did}/cleaning/preview",
                json={
                    "operations": [{"op": "trim"}],
                },
            ).status_code
            == 404
        )
        with get_engine().begin() as connection:
            connection.execute(
                insert(memberships).values(
                    organization_id=UUID(wid),
                    user_id=UUID(identity["id"]),
                    role="viewer",
                )
            )
        assert stranger.get(base + f"/datasets/{did}/versions").status_code == 200
        assert (
            stranger.post(
                base + "/analyses",
                json={
                    "dataset_id": did,
                    "version_id": vid,
                    "mapping": {"revenue": "amount"},
                },
            ).status_code
            == 403
        )
        assert (
            stranger.post(
                base + f"/datasets/{did}/cleaning/preview",
                json={
                    "operations": [{"op": "trim"}],
                },
            ).status_code
            == 403
        )


def test_apply_storage_failure_preserves_version_and_plan(data_api, monkeypatch):
    from app.features.db import get_engine
    from app.models import cleaning_plans, dataset_versions

    client, storage, wid, did, vid, *_ = data_api
    base = f"/api/v1/workspaces/{wid}/datasets/{did}"
    plan = client.post(
        base + "/cleaning/preview",
        json={
            "operations": [{"op": "drop_duplicates"}],
        },
    ).json()

    def fail(**kwargs):
        raise RuntimeError("private storage endpoint should stay private")

    monkeypatch.setattr(storage, "put_object", fail)
    response = client.post(base + "/cleaning/apply", json={"plan_id": plan["id"]})
    assert response.status_code == 503
    assert "private storage" not in response.text
    with get_engine().connect() as connection:
        versions = (
            connection.execute(
                select(dataset_versions.c.id).where(dataset_versions.c.dataset_id == UUID(did))
            )
            .scalars()
            .all()
        )
        assert versions == [UUID(vid)]
        status = connection.execute(
            select(cleaning_plans.c.status).where(cleaning_plans.c.id == UUID(plan["id"]))
        ).scalar_one()
        assert status == "proposed"
