"""Exercise real local accounts, multi-file/folder imports, S3 and the Celery worker.

Run after the Compose stack is ready: python scripts/real-flow-smoke.py
Optional first argument: same-origin web base URL. Uses only the standard library.
Creates randomly named validation accounts/workspaces without logging credentials.
"""

import hashlib
import http.cookiejar
import io
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from uuid import uuid4
from xml.etree import ElementTree as ET

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000").rstrip("/")
ORIGIN = "http://localhost:3000"
CSV = b"product,amount,note\nNotebook,120,\nNotebook,120,\nPencil,90,ready\n"


def xlsx_fixture():
    content_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    relation_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    sheet_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    types = ET.Element(f"{{{content_ns}}}Types")
    for extension, content_type in [
        ("rels", "application/vnd.openxmlformats-package.relationships+xml"),
        ("xml", "application/xml"),
    ]:
        ET.SubElement(
            types,
            f"{{{content_ns}}}Default",
            {
                "Extension": extension,
                "ContentType": content_type,
            },
        )
    for part, content_type in [
        (
            "/xl/workbook.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        ),
        (
            "/xl/worksheets/sheet1.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        ),
    ]:
        ET.SubElement(
            types,
            f"{{{content_ns}}}Override",
            {
                "PartName": part,
                "ContentType": content_type,
            },
        )
    root_relations = ET.Element(f"{{{relation_ns}}}Relationships")
    ET.SubElement(
        root_relations,
        f"{{{relation_ns}}}Relationship",
        {
            "Id": "rId1",
            "Type": office_ns + "/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    workbook = ET.Element(f"{{{sheet_ns}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{sheet_ns}}}sheets")
    ET.SubElement(
        sheets,
        f"{{{sheet_ns}}}sheet",
        {
            "name": "Inventory",
            "sheetId": "1",
            f"{{{office_ns}}}id": "rId1",
        },
    )
    workbook_relations = ET.Element(f"{{{relation_ns}}}Relationships")
    ET.SubElement(
        workbook_relations,
        f"{{{relation_ns}}}Relationship",
        {
            "Id": "rId1",
            "Type": office_ns + "/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )
    sheet = ET.Element(f"{{{sheet_ns}}}worksheet")
    sheet_data = ET.SubElement(sheet, f"{{{sheet_ns}}}sheetData")
    for number, values in enumerate([("sku", "quantity"), ("A", 3), ("B", 8)], 1):
        row = ET.SubElement(sheet_data, f"{{{sheet_ns}}}row", {"r": str(number)})
        for column, value in zip("AB", values, strict=True):
            cell = ET.SubElement(row, f"{{{sheet_ns}}}c", {"r": f"{column}{number}"})
            if isinstance(value, str):
                cell.set("t", "inlineStr")
                inline = ET.SubElement(cell, f"{{{sheet_ns}}}is")
                ET.SubElement(inline, f"{{{sheet_ns}}}t").text = value
            else:
                ET.SubElement(cell, f"{{{sheet_ns}}}v").text = str(value)
    parts = {
        "[Content_Types].xml": types,
        "_rels/.rels": root_relations,
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": workbook_relations,
        "xl/worksheets/sheet1.xml": sheet,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, ET.tostring(content, encoding="utf-8", xml_declaration=True))
    return buffer.getvalue()


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method, path, payload=None, *, expected=200, body=None, content_type=None):
        headers = {"Origin": ORIGIN, "Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode()
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(
            BASE + "/api/v1" + path, data=body, headers=headers, method=method
        )
        try:
            with self.opener.open(request, timeout=40) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        if status != expected:
            # Do not dump request bodies, auth headers, cookies or password fields.
            raise AssertionError(f"{method} {path}: expected HTTP {expected}, got {status}")
        return json.loads(raw) if raw else None

    def register(self):
        email = f"validation-{uuid4().hex}@example.test"
        password = secrets.token_urlsafe(28)
        identity = self.request(
            "POST",
            "/auth/register",
            {
                "email": email,
                "password": password,
                "display_name": "Execution validation",
            },
            expected=201,
        )
        assert self.request("GET", "/auth/me")["id"] == identity["id"]
        self.request("POST", "/auth/logout", expected=204)
        self.request("GET", "/auth/me", expected=401)
        logged_in = self.request("POST", "/auth/login", {"email": email, "password": password})
        assert logged_in["id"] == identity["id"]

    def upload(self, workspace, files):
        boundary = "DataPilotSmoke" + secrets.token_hex(16)
        pieces = []

        def field(name, value):
            pieces.append(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n'
                    f"\r\n{value}\r\n"
                ).encode()
            )

        field("name", "Real execution validation")
        field("relative_paths", json.dumps([path for path, _, _ in files]))
        for path, content, mime in files:
            filename = path.rsplit("/", 1)[-1]
            pieces.append(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="files"; '
                    f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
                ).encode()
            )
            pieces.extend([content, b"\r\n"])
        pieces.append(f"--{boundary}--\r\n".encode())
        return self.request(
            "POST",
            f"/workspaces/{workspace}/imports",
            expected=202,
            body=b"".join(pieces),
            content_type=f"multipart/form-data; boundary={boundary}",
        )

    def completed(self, workspace, batch_id, expected_status):
        deadline = time.monotonic() + 90
        previous = None
        while time.monotonic() < deadline:
            batch = self.request("GET", f"/workspaces/{workspace}/imports/{batch_id}")
            statuses = tuple(sorted(file["status"] for file in batch["files"]))
            if statuses != previous:
                print("Import file states:", ", ".join(statuses), flush=True)
                previous = statuses
            if batch["status"] in {"succeeded", "partial", "failed"}:
                assert batch["status"] == expected_status, (
                    batch["status"],
                    [(f["path"], f["error_code"]) for f in batch["files"]],
                )
                return batch
            time.sleep(2)
        raise AssertionError("Background ingestion did not finish within 90 seconds")


def main():
    client = Client()
    client.register()
    print("Account registration, login and logout: PASS", flush=True)
    workspace = client.request(
        "POST",
        "/workspaces",
        {
            "name": "Execution validation " + datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        },
        expected=201,
    )["id"]
    assert any(w["id"] == workspace for w in client.request("GET", "/workspaces"))
    spreadsheet = xlsx_fixture()
    batch = client.upload(
        workspace,
        [
            ("sources/sales.csv", CSV, "text/csv"),
            (
                "sources/nested/inventory.xlsx",
                spreadsheet,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("sources/broken.xlsx", b"this is not an XLSX zip", "application/octet-stream"),
        ],
    )
    assert batch["total_files"] == 3
    completed = client.completed(workspace, batch["id"], "partial")
    files = {f["path"]: f for f in completed["files"]}
    assert files["sources/broken.xlsx"]["status"] == "failed"
    assert files["sources/broken.xlsx"]["error_code"]
    for path, rows, columns, original in [
        ("sources/sales.csv", 3, 3, CSV),
        ("sources/nested/inventory.xlsx", 2, 2, spreadsheet),
    ]:
        record = files[path]
        assert record["status"] == "succeeded" and record["progress"] == 100
        data = client.request("GET", f"/workspaces/{workspace}/datasets/{record['dataset_id']}")
        assert data["status"] == "ready"
        assert data["row_count"] == rows and data["column_count"] == columns
        assert len(data["preview"]) == rows and len(data["columns"]) == columns
        assert data["source_path"] == path
        assert data["sha256"] == hashlib.sha256(original).hexdigest()
        if path.endswith("sales.csv"):
            assert sum(float(row["amount"]) for row in data["preview"]) == 330
            findings = {q["rule_code"]: q for q in data["quality"]}
            assert findings["duplicate_rows"]["affected_rows"] == 1
            assert any(
                q["rule_code"] == "missing_values"
                and q["column_name"] == "note"
                and q["affected_rows"] == 2
                for q in data["quality"]
            )
    print(
        "Real CSV/XLSX ingestion, folder paths, immutable hashes, previews and quality: PASS",
        flush=True,
    )
    print("Malformed file isolated while other files succeed: PASS", flush=True)
    # A second batch demonstrates that previous persisted results remain available.
    second = client.upload(workspace, [("second/source.csv", b"key,value\nA,7\n", "text/csv")])
    client.completed(workspace, second["id"], "succeeded")
    assert len(client.request("GET", f"/workspaces/{workspace}/datasets")) == 4
    assert len(client.request("GET", f"/workspaces/{workspace}/imports")) == 2
    stranger = Client()
    stranger.register()
    assert all(w["id"] != workspace for w in stranger.request("GET", "/workspaces"))
    stranger.request("GET", f"/workspaces/{workspace}/datasets", expected=404)
    stranger.request("GET", f"/workspaces/{workspace}/imports/{batch['id']}", expected=404)
    stranger.request(
        "GET",
        f"/workspaces/{workspace}/datasets/{files['sources/sales.csv']['dataset_id']}",
        expected=404,
    )
    stranger.request("POST", f"/workspaces/{workspace}/imports/{batch['id']}/retry", expected=404)
    print("Cross-account workspace/import/dataset/retry access denied: PASS", flush=True)
    print("Real execution smoke check completed. Validation workspace:", workspace, flush=True)


if __name__ == "__main__":
    main()
