import zipfile

import openpyxl
import pyarrow.parquet as pq
import pytest
from app.processing.launch import IngestionFailure, read_regular, validate_result
from app.processing.parser import ParseError, parse


def run_csv(tmp_path, text):
    source = tmp_path / "source.csv"
    source.write_text(text)
    result = parse(source, "csv", tmp_path / "output.parquet")
    assert pq.read_table(tmp_path / "output.parquet").num_rows == result["row_count"]
    return result


def test_csv_nulls_duplicates_source_preserved(tmp_path):
    text = "region,revenue\nNorth,120\nSouth,\nNorth,120\n"
    result = run_csv(tmp_path, text)
    assert result["row_count"] == 3
    assert result["column_count"] == 2
    assert result["schema_json"]["preview"][1]["revenue"] is None
    assert result["schema_json"]["profile"]["statistics"]["revenue"]["sum"] == "240"
    findings = {f["rule_code"]: f for f in result["quality"]}
    assert findings["missing_values"]["affected_rows"] == 1
    assert findings["duplicate_rows"]["affected_rows"] == 1
    assert (tmp_path / "source.csv").read_text() == text


def test_semicolon_unicode_unique_headers_and_leading_zero_ids(tmp_path):
    result = run_csv(tmp_path, "id;name;name;\n001;Zahra;école;yes\n002;Mouna;مدرسة;no\n")
    assert [c["name"] for c in result["schema_json"]["columns"]] == [
        "id",
        "name",
        "name_2",
        "column_4",
    ]
    assert result["schema_json"]["preview"][0]["id"] == "001"
    assert result["schema_json"]["preview"][1]["name_2"] == "مدرسة"
    assert result["schema_json"]["profile"]["delimiter"] == ";"


def test_csv_literal_formula_and_mixed_types(tmp_path):
    result = run_csv(tmp_path, "value,label\n1,=SUM(A1:A3)\n2,ok\n3,ok\n4,ok\noops,ok\n")
    assert result["schema_json"]["columns"][0]["type"] == "string"
    assert result["schema_json"]["preview"][0]["label"] == "=SUM(A1:A3)"
    assert {f["rule_code"] for f in result["quality"]} == {"mixed_types", "formula_like_values"}


def test_header_only_and_preview_bound(tmp_path):
    assert run_csv(tmp_path, "a,b\n")["row_count"] == 0
    result = run_csv(tmp_path, "a,b\n" + "value," + "x" * 400 + "\n" + "value,short\n" * 110)
    assert len(result["schema_json"]["preview"]) == 100
    assert len(result["schema_json"]["preview"][0]["b"]) == 257


@pytest.mark.parametrize(
    ("text", "code"),
    [("", "file_size"), ("a\n\x00\n", "invalid_csv"), ('a,b\n"bad\n', "invalid_csv")],
)
def test_invalid_csv(tmp_path, text, code):
    with pytest.raises(ParseError) as error:
        run_csv(tmp_path, text)
    assert error.value.code == code


def test_xlsx_real_values_and_formula_rejection(tmp_path):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["region", "revenue"])
    sheet.append(["North", 12])
    # The worker stages uploads with a fixed extensionless name.
    file = tmp_path / "input"
    book.save(file)
    result = parse(file, "xlsx", tmp_path / "output.parquet")
    assert result["schema_json"]["preview"] == [{"region": "North", "revenue": 12}]
    assert result["schema_json"]["profile"]["worksheet"] == "Sheet"
    sheet.append(["South", "=1+2"])
    book.save(file)
    with pytest.raises(ParseError) as error:
        parse(file, "xlsx", tmp_path / "output.parquet")
    assert error.value.code == "formulas_unsupported"


def test_xlsx_zip_ratio_and_invalid_archive(tmp_path):
    file = tmp_path / "source.xlsx"
    file.write_bytes(b"this is not a workbook")
    with pytest.raises(ParseError) as error:
        parse(file, "xlsx", tmp_path / "output.parquet")
    assert error.value.code == "invalid_xlsx"
    with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "x")
        archive.writestr("xl/worksheets/sheet1.xml", "0" * (11 * 1024**2))
    with pytest.raises(ParseError) as error:
        parse(file, "xlsx", tmp_path / "output.parquet")
    assert error.value.code == "zip_bomb"


def test_parser_manifest_validation_and_symlink_output(tmp_path):
    target = tmp_path / "private"
    target.write_text("secret")
    link = tmp_path / "result.json"
    link.symlink_to(target)
    with pytest.raises(OSError):
        read_regular(link, 4096)
    with pytest.raises(IngestionFailure):
        validate_result({"row_count": 1, "column_count": 50000})


def test_iso_dates_are_typed_in_parquet(tmp_path):
    result = run_csv(tmp_path, "date\n2026-10-27\n2026-10-28\n")
    assert result["schema_json"]["columns"][0]["type"] == "date"
    assert result["schema_json"]["preview"][0]["date"] == "2026-10-27"
    assert (
        str(pq.read_table(tmp_path / "output.parquet").schema.field("date").type) == "date32[day]"
    )
