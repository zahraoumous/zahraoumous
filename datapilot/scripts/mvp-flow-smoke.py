"""Verify the remaining MVP against real PostgreSQL, object storage and worker.

Run after scripts/dev.sh. Optional first argument: same-origin web base URL.
Creates only random validation accounts and workspaces; never prints credentials.
"""

import csv
import importlib.util
import io
import json
import secrets
import urllib.request
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "datapilot_real_flow", Path(__file__).with_name("real-flow-smoke.py")
)
assert spec and spec.loader
flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow)
Client = flow.Client
CSV = (
    b"product,amount,cost,quantity,date,note\n"
    b" Notebook ,120,60,2,2026-01-01,\n"
    b" Notebook ,120,60,2,2026-01-01,\n"
    b"Pencil,90,30,1,2026-01-02,ready\n"
)


def download(client, path):
    request = urllib.request.Request(flow.BASE + "/api/v1" + path)
    with client.opener.open(request, timeout=40) as response:
        assert response.status == 200
        assert "attachment" in response.headers.get("Content-Disposition", "")
        return response.read(), response.headers.get("Content-Type", "")


def main():
    client = Client()
    client.register()
    wid = client.request("POST", "/workspaces", {"name": "Remaining MVP validation"}, expected=201)[
        "id"
    ]
    base = f"/workspaces/{wid}"
    batch = client.upload(wid, [("validation/sales.csv", CSV, "text/csv")])
    batch = client.completed(wid, batch["id"], "succeeded")
    did = batch["files"][0]["dataset_id"]
    dataset_path = base + f"/datasets/{did}"
    original = client.request("GET", dataset_path)
    preview = client.request(
        "POST",
        dataset_path + "/cleaning/preview",
        {
            "version_id": original["version_id"],
            "operations": [{"op": "trim", "column": "product"}, {"op": "drop_duplicates"}],
        },
    )
    assert preview["before_rows"] == 3 and preview["after_rows"] == 2
    cleaned = client.request("POST", dataset_path + "/cleaning/apply", {"plan_id": preview["id"]})
    assert cleaned["version_id"] != original["version_id"] and cleaned["row_count"] == 2
    assert cleaned["sha256"] == original["sha256"]
    assert client.request("GET", dataset_path)["row_count"] == 3
    versions = client.request("GET", dataset_path + "/versions")
    assert len(versions) == 2
    assert (
        client.request("GET", dataset_path + "/versions/" + cleaned["version_id"])["row_count"] == 2
    )
    analysis = client.request(
        "POST",
        base + "/analyses",
        {
            "dataset_id": did,
            "version_id": cleaned["version_id"],
            "name": "Confirmed sales metrics",
            "mapping": {
                "revenue": "amount",
                "cost": "cost",
                "quantity": "quantity",
                "category": "product",
                "date": "date",
            },
        },
        expected=201,
    )
    assert analysis["metrics"]["revenue"] == "210"
    assert analysis["metrics"]["cost"] == "90"
    assert analysis["metrics"]["profit"] == "120"
    assert analysis["metrics"]["quantity"] == "3"
    assert analysis["evidence"]["rows_included"] == 2
    assert len(analysis["category_series"]) == len(analysis["date_series"]) == 2
    aid = analysis["id"]
    assert client.request("GET", base + "/analyses/" + aid)["metrics"] == analysis["metrics"]
    assert any(a["id"] == aid for a in client.request("GET", base + "/analyses"))
    dashboard = client.request(
        "POST",
        base + "/dashboards",
        {"analysis_id": aid, "title": "Confirmed dashboard"},
        expected=201,
    )
    assert any(d["id"] == dashboard["id"] for d in client.request("GET", base + "/dashboards"))
    assert client.request("GET", base + "/dashboards/" + dashboard["id"])["id"] == dashboard["id"]
    print("Immutable cleaning, full-version metrics, persisted analyses and dashboards: PASS")
    export_base = base + f"/analyses/{aid}/exports/"
    raw, mime = download(client, export_base + "csv")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert len(rows) == 2 and sum(int(r["amount"]) for r in rows) == 210
    raw, mime = download(client, export_base + "xlsx")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert "xl/worksheets/sheet1.xml" in archive.namelist()
    raw, mime = download(client, export_base + "json")
    assert len(json.loads(raw)["rows"]) == 2
    raw, mime = download(client, export_base + "pdf")
    assert raw.startswith(b"%PDF-") and b"%%EOF" in raw
    raw, mime = download(client, export_base + "powerbi")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert {"data.csv", "analysis.json", "mapping.json", "measures.dax", "PowerQuery.m"} <= set(
            archive.namelist()
        )
    print("CSV/XLSX/JSON/PDF and Power BI handoff downloads contain real data: PASS")
    settings = client.request("GET", "/ai/settings")
    assert settings["provider"] == "local" and not settings["has_api_key"]
    skills = client.request("GET", "/ai/skills")
    assert {s["id"] for s in skills} == {"data_quality", "business_analyst", "executive_summary"}
    ask = {
        "question": "Explain these confirmed metrics",
        "analysis_id": aid,
        "version_id": cleaned["version_id"],
        "skill_id": "business_analyst",
    }
    for language in ["en", "fr", "ar"]:
        answer = client.request("POST", dataset_path + "/ask", {**ask, "language": language})
        assert answer["provider"] == "local" and "210" in answer["answer"]
        assert answer["evidence"] and answer["conversation_id"]
    key = "validation-only-" + secrets.token_urlsafe(18)
    settings = client.request(
        "PUT", "/ai/settings", {"provider": "openai", "model": "gpt-4.1-mini", "api_key": key}
    )
    assert settings["has_api_key"] and key not in json.dumps(settings)
    retained = client.request(
        "PUT", "/ai/settings", {"provider": "openai", "model": "gpt-4.1-mini", "api_key": ""}
    )
    assert retained["has_api_key"]
    client.request("POST", dataset_path + "/ask", ask, expected=422)
    cleared = client.request(
        "PUT",
        "/ai/settings",
        {"provider": "openai", "model": "gpt-4.1-mini", "clear_api_key": True},
    )
    assert not cleared["has_api_key"]
    client.request("PUT", "/ai/settings", {"provider": "local", "model": "deterministic-v1"})
    stranger = Client()
    stranger.register()
    assert not stranger.request("GET", "/ai/settings")["has_api_key"]
    stranger.request("POST", dataset_path + "/ask", ask, expected=404)
    stranger.request("GET", base + "/analyses/" + aid, expected=404)
    stranger.request("GET", base + "/dashboards/" + dashboard["id"], expected=404)
    stranger.request("GET", dataset_path + "/versions", expected=404)
    print("Skill-guided local answers in EN/FR/AR; provider settings/key lifecycle/isolation: PASS")
    print("External provider calls use mocked unit tests; no live provider key was supplied.")


if __name__ == "__main__":
    main()
