"""Boundary tests for canonical dataset access and version metadata."""

import io
from types import SimpleNamespace
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from app.features import data_mvp
from fastapi import HTTPException


class Objects:
    def __init__(self, raw, declared=None):
        self.raw = raw
        self.declared = len(raw) if declared is None else declared

    def close(self):
        pass

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(self.raw), "ContentLength": self.declared}


def install_objects(monkeypatch, raw, declared=None):
    monkeypatch.setattr(data_mvp, "get_s3", lambda: Objects(raw, declared))
    monkeypatch.setattr(data_mvp, "get_settings", lambda: SimpleNamespace(s3_bucket="test"))


def parquet(table):
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


def test_full_canonical_rows_are_used_beyond_preview(monkeypatch):
    table = pa.table({"amount": list(range(125))})
    install_objects(monkeypatch, parquet(table))
    rows, columns = data_mvp.load_rows(
        {
            "parquet_object_key": "trusted-key",
            "row_count": 125,
            "column_count": 1,
        }
    )
    assert columns == ["amount"] and len(rows) == 125
    assert sum(row["amount"] for row in rows) == 7750


def test_canonical_size_and_metadata_fail_closed(monkeypatch):
    install_objects(monkeypatch, b"unread", data_mvp.MAX_PARQUET_BYTES + 1)
    version = {"parquet_object_key": "trusted-key", "row_count": 1, "column_count": 1}
    with pytest.raises(HTTPException) as error:
        data_mvp.load_rows(version)
    assert error.value.status_code == 413
    install_objects(monkeypatch, parquet(pa.table({"a": [1, 2]})))
    with pytest.raises(HTTPException) as error:
        data_mvp.load_rows(version)
    assert error.value.status_code == 409


def test_corrupt_canonical_errors_are_sanitized(monkeypatch):
    install_objects(monkeypatch, b"private-secret-storage-endpoint")
    with pytest.raises(HTTPException) as error:
        data_mvp.load_rows({"parquet_object_key": "trusted-key", "row_count": 1, "column_count": 1})
    assert error.value.status_code == 503
    assert "private-secret" not in error.value.detail


def test_cleaned_metadata_records_actual_counts_and_bounds_preview():
    table = pa.table({"name": ["x" * 300, "x" * 300, None], "amount": [5, 5, 8]})
    schema, findings = data_mvp.cleaned_metadata(table, "original", {"before_rows": 3})
    assert len(schema["preview"][0]["name"]) == 257
    assert schema["profile"]["duplicate_rows"] == 1
    assert schema["profile"]["parent_version_id"] == "original"
    assert {finding["rule_code"] for finding in findings} == {"missing_values", "duplicate_rows"}


def test_analysis_exports_serialize_version_and_analysis_identifiers():
    import json

    analysis_id, version_id = uuid4(), uuid4()
    response = data_mvp.export_response(
        "json",
        [{"amount": 7}],
        ["amount"],
        {"id": analysis_id, "version_id": version_id, "metrics": {"revenue": "7"}},
    )
    payload = json.loads(response.body)
    assert payload["analysis"]["id"] == str(analysis_id)
    assert payload["analysis"]["version_id"] == str(version_id)


def test_cleaned_quality_recomputes_mixed_and_formula_flags_from_current_rows():
    table = pa.table(
        {
            "mixed": ["1", "2", "3", "4", "text"],
            "formula": ["=1+1", "@external", "-7", "+8.5", None],
            "other": ["=another", "safe", "safe", "safe", "safe"],
        }
    )
    _, findings = data_mvp.cleaned_metadata(table, "original", {})
    by_rule = {finding["rule_code"]: finding for finding in findings}
    assert by_rule["mixed_types"]["column_name"] == "mixed"
    assert by_rule["mixed_types"]["affected_rows"] == 1
    assert by_rule["formula_like_values"]["affected_rows"] == 2
    # A second column on the first row does not double-count formula-like rows;
    # genuine signed numeric values are not flagged as formulas.
    safe = pa.table({"values": ["1", "2", "3", "4", "5"]})
    _, cleaned_findings = data_mvp.cleaned_metadata(safe, "original", {})
    assert not any(
        f["rule_code"] in {"mixed_types", "formula_like_values"} for f in cleaned_findings
    )
