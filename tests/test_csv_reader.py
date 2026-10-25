
import csv

from src.deletion_audit.ingestion.csv_reader import read_csv_file


def write_csv(path, content):
    path.write_text(content, encoding="utf-8")


def test_reads_valid_csv(tmp_path):
    file_path = tmp_path / "valid.csv"
    write_csv(
        file_path,
        "user_id,email\nu101,john@example.com\n",
    )

    result = read_csv_file(file_path, {"user_id", "email"})

    assert result["valid"] is True
    assert result["records"] == [
        {"user_id": "u101", "email": "john@example.com"}
    ]


def test_normalizes_header_whitespace(tmp_path):
    file_path = tmp_path / "spaces.csv"
    write_csv(file_path, " user_id , email \nu101, john@example.com \n")

    result = read_csv_file(file_path, {"user_id", "email"})

    assert result["valid"] is True
    assert result["records"][0]["user_id"] == "u101"
    assert result["records"][0]["email"] == "john@example.com"


def test_rejects_duplicate_headers(tmp_path):
    file_path = tmp_path / "duplicate.csv"
    write_csv(file_path, "user_id,user_id\nu101,u102\n")

    result = read_csv_file(file_path)

    assert result["valid"] is False
    assert any("duplicate" in error.lower() for error in result["errors"])


def test_rejects_missing_required_column(tmp_path):
    file_path = tmp_path / "missing.csv"
    write_csv(file_path, "user_id\nu101\n")

    result = read_csv_file(file_path, {"user_id", "email"})

    assert result["valid"] is False
    assert any("missing required columns" in error.lower()
               for error in result["errors"])


def test_rejects_rows_with_wrong_field_count(tmp_path):
    file_path = tmp_path / "wrong_count.csv"
    write_csv(file_path, "user_id,email\nu101,john@example.com,extra\n")

    result = read_csv_file(file_path)

    assert result["valid"] is False
    assert result["records"] == []
    assert any("expected 2 values, found 3" in error
               for error in result["errors"])


def test_rejects_empty_header_name(tmp_path):
    file_path = tmp_path / "empty_header.csv"
    write_csv(file_path, "user_id,\nu101,john@example.com\n")

    result = read_csv_file(file_path)

    assert result["valid"] is False
    assert any("empty column name" in error.lower()
               for error in result["errors"])


def test_rejects_empty_file(tmp_path):
    file_path = tmp_path / "empty.csv"
    write_csv(file_path, "")

    result = read_csv_file(file_path)

    assert result["valid"] is False
    assert any("empty" in error.lower() for error in result["errors"])


def test_reports_missing_file(tmp_path):
    file_path = tmp_path / "does_not_exist.csv"

    result = read_csv_file(file_path)

    assert result["valid"] is False
    assert "File does not exist." in result["errors"]


def test_reads_csv_with_leading_blank_line(tmp_path):
    csv_file = tmp_path / "activity.csv"
    csv_file.write_text(
        "\nevent_id,user_id\n"
        "evt001,u101\n",
        encoding="utf-8",
    )

    result = read_csv_file(
        csv_file,
        required_columns={"event_id", "user_id"},
    )

    assert result["valid"] is True
    assert len(result["records"]) == 1
    assert result["records"][0]["event_id"] == "evt001"

def test_reports_actual_line_number_after_blank_lines(tmp_path):
    file_path = tmp_path / "blank_lines.csv"
    write_csv(
        file_path,
        "user_id,email\n"
        "u101,john@example.com\n"
        "\n"
        "u102,jane@example.com,unexpected\n",
    )

    result = read_csv_file(file_path)

    assert result["valid"] is False
    assert any(
        "Line 4:" in error
        and "expected 2 values, found 3" in error
        for error in result["errors"]
    )
