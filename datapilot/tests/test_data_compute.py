import csv
import io
import json
import zipfile
from datetime import date
from decimal import Decimal, localcontext

import openpyxl
import pytest
from app.features.data_compute import analyze_rows, clean_rows, filter_rows, generate_export


def test_golden_decimal_metrics_and_missing_pair_profit():
    rows = [
        {"sales": "0.1", "expenses": "0.03", "units": 2, "region": "Nord", "day": "2026-01-01"},
        {"sales": "0.2", "expenses": "0.07", "units": 3, "region": "Nord", "day": date(2026, 1, 2)},
        {"sales": "10", "expenses": None, "units": 1, "region": "Sud", "day": "not a date"},
        {"sales": None, "expenses": "5", "units": None, "region": "Sud", "day": None},
        {"sales": "n/a", "expenses": "2", "units": "bad", "region": None, "day": "2026-02-01"},
    ]
    mapping = {
        "revenue": "sales",
        "cost": "expenses",
        "quantity": "units",
        "category": "region",
        "date": "day",
    }
    result = analyze_rows(rows, mapping)
    assert result["metrics"]["rows"] == 5
    assert result["metrics"]["revenue"] == "10.3"
    assert result["metrics"]["cost"] == "7.1"
    assert result["metrics"]["quantity"] == "6"
    # An incomplete cost row must not invent a profit of 10 or deduct an unpaired cost of 7.
    assert result["metrics"]["profit"] == "0.2"
    assert Decimal(result["metrics"]["margin_percent"]) == pytest.approx(Decimal(200) / 3)
    assert Decimal(result["metrics"]["average_revenue_per_row"]) == pytest.approx(
        Decimal("10.3") / 3
    )
    assert result["evidence"]["profit_rows"] == 2
    assert result["evidence"]["missing_values"]["revenue"] == 1
    assert result["evidence"]["invalid_values"]["revenue"] == 1
    assert result["evidence"]["invalid_values"]["date"] == 1
    assert result["category_series"][0] == {
        "label": "Nord",
        "rows": 2,
        "revenue": "0.3",
        "cost": "0.1",
        "quantity": "5",
        "profit": "0.2",
    }
    assert [item["label"] for item in result["date_series"]] == [
        "2026-01-01",
        "2026-01-02",
        "2026-02-01",
    ]


def test_filters_have_inclusive_dates_and_export_uses_same_rows():
    rows = [
        {"d": "2026-01-01", "c": "A", "r": 10},
        {"d": "2026-01-31", "c": "A", "r": 20},
        {"d": "2026-02-01", "c": "A", "r": 30},
        {"d": "2026-01-15", "c": "B", "r": 40},
        {"d": "bad", "c": "A", "r": 50},
    ]
    mapping = {"date": "d", "category": "c", "revenue": "r"}
    filters = {"date_from": "2026-01-01", "date_to": "2026-01-31", "categories": ["A"]}
    result = analyze_rows(rows, mapping, filters)
    assert result["metrics"]["revenue"] == "30"
    assert result["metrics"]["rows"] == 2
    assert result["evidence"]["rows_total"] == 5
    assert filter_rows(rows, mapping, filters) == rows[:2]
    assert analyze_rows(rows, mapping, {"categories": []})["metrics"]["rows"] == 0


def test_no_guessing_and_zero_denominator():
    result = analyze_rows([{"r": "0", "c": "3"}], {"revenue": "r", "cost": "c"})
    assert result["metrics"]["profit"] == "-3"
    assert result["metrics"]["margin_percent"] is None
    result = analyze_rows([{"amount": 99}], {"quantity": "amount"})
    assert result["metrics"] == {"rows": 1, "quantity": "99"}
    assert "revenue" not in result["metrics"]


@pytest.mark.parametrize(
    "mapping,filters",
    [
        ({"currency": "amount"}, {}),
        ({"revenue": "missing"}, {}),
        ({"revenue": "amount", "cost": "amount"}, {}),
        ({"revenue": "amount"}, {"sql": "SELECT *"}),
        ({"revenue": "amount"}, {"date_from": "2026-01-01"}),
        ({"date": "amount"}, {"date_from": "2026-02-30"}),
        ({"date": "amount"}, {"date_from": "2026-02-01", "date_to": "2026-01-01"}),
        ({"category": "amount"}, {"categories": "A"}),
    ],
)
def test_invalid_semantics_rejected(mapping, filters):
    with pytest.raises(ValueError):
        analyze_rows([{"amount": "7"}], mapping, filters)


def test_cleaning_is_ordered_immutable_and_explained():
    rows = [{"name": " A ", "v": "1.25"}, {"name": "A", "v": "1.25"}, {"name": " ", "v": None}]
    result, summary = clean_rows(
        rows,
        ["name", "v"],
        [
            {"op": "trim"},
            {"op": "empty_to_null"},
            {"op": "drop_duplicates"},
            {"op": "drop_missing", "column": "name"},
            {"op": "cast_number", "column": "v"},
            {"op": "rename", "column": "v", "value": "value"},
        ],
    )
    assert result == [{"name": "A", "value": 1.25}]
    assert rows[0] == {"name": " A ", "v": "1.25"}
    assert summary["before_rows"] == 3 and summary["after_rows"] == 1
    assert summary["removed_rows"] == 2
    assert summary["columns"] == ["name", "value"]
    assert summary["operations"][2]["removed_rows"] == 1


@pytest.mark.parametrize(
    "operations",
    [
        [{"op": "eval", "value": "1 + 1"}],
        [{"op": "trim", "column": "absent"}],
        [{"op": "rename", "column": "a", "value": "b"}],
        [{"op": "fill_missing", "column": "a", "value": {"x": 1}}],
        [{"op": "trim", "script": "ignored"}],
        [{"op": "cast_number", "column": "a"}],
    ],
)
def test_lossy_or_unsafe_cleaning_rejected(operations):
    with pytest.raises(ValueError):
        clean_rows([{"a": "not numeric", "b": None}], ["a", "b"], operations)


def test_numeric_cast_refuses_silent_precision_loss():
    with pytest.raises(ValueError, match="precision"):
        clean_rows([{"x": "0.1234567890123456789"}], ["x"], [{"op": "cast_number", "column": "x"}])


def test_exports_keep_unicode_and_never_evaluate_spreadsheet_formulas():
    rows = [{"label": '=HYPERLINK("https://example.test")', "école": "مدرسة", "n": -3}]
    columns = ["label", "école", "n"]
    content, mime, extension = generate_export("csv", rows, columns)
    parsed = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    assert extension == "csv" and mime.startswith("text/csv")
    assert parsed[1] == ['\'=HYPERLINK("https://example.test")', "مدرسة", "-3"]
    content, _, _ = generate_export("xlsx", rows, columns)
    book = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
    assert book.active["A2"].data_type == "s"
    assert book.active["A2"].value == rows[0]["label"]
    assert book.active["B2"].value == "مدرسة"
    assert book.active["C2"].value == -3
    content, _, _ = generate_export("json", rows, columns)
    assert json.loads(content)["rows"] == rows


def test_portable_powerbi_package_and_valid_pdf_provenance(tmp_path):
    rows = [{"r": 12, "c": 7}]
    analysis = {**analyze_rows(rows, {"revenue": "r", "cost": "c"}), "version_id": "immutable-v1"}
    content, mime, extension = generate_export("powerbi", rows, ["r", "c"], analysis)
    assert mime == "application/zip" and extension == "zip"
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert set(archive.namelist()) == {
            "data.csv",
            "analysis.json",
            "mapping.json",
            "measures.dax",
            "PowerQuery.m",
            "README.txt",
        }
        assert json.loads(archive.read("analysis.json"))["metrics"]["profit"] == "5"
        assert "ISNUMBER" in archive.read("measures.dax").decode()
        assert not any(name.endswith((".pbix", ".pbit")) for name in archive.namelist())
    content, mime, extension = generate_export("pdf", rows, ["r", "c"], analysis)
    assert content.startswith(b"%PDF-1.4") and content.endswith(b"%%EOF\n")
    assert b"immutable-v1" in content and b"Profit: 5" in content
    xref = int(content.split(b"startxref\n")[1].splitlines()[0])
    assert content[xref : xref + 4] == b"xref"


def test_exact_totals_cover_large_and_tiny_values():
    result = analyze_rows([{"r": "1e350"}, {"r": "1e-350"}], {"revenue": "r"})
    total = result["metrics"]["revenue"]
    assert total == "1" + "0" * 350 + "." + "0" * 349 + "1"


def test_spreadsheet_export_preserves_large_integers_and_reports_illegal_xml():
    content, _, _ = generate_export("xlsx", [{"id": 9223372036854775807}], ["id"])
    book = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
    assert book.active["A2"].value == "9223372036854775807"
    assert book.active["A2"].data_type == "s"
    with pytest.raises(ValueError, match="control character"):
        generate_export("xlsx", [{"a": "a\x01b"}], ["a"])


def test_powerbi_mapping_matches_formula_escaped_csv_header():
    content, _, _ = generate_export(
        "powerbi", [{"=amount": 5}], ["=amount"], {"mapping": {"revenue": "=amount"}}
    )
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert json.loads(archive.read("mapping.json")) == {"revenue": "'=amount"}
        assert "Data['=amount]" in archive.read("measures.dax").decode()


def test_total_preserves_long_mantissa_across_allowed_exponent_range():
    tiny = "1." + "0" * 380 + "1e-350"
    result = analyze_rows([{"value": "1e350"}, {"value": tiny}], {"revenue": "value"})
    with localcontext() as context:
        context.prec = 1200
        assert Decimal(result["metrics"]["revenue"]) - Decimal("1e350") == Decimal(tiny)
