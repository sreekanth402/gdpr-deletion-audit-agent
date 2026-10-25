
from src.deletion_audit.ingestion.json_reader import read_json_file


def test_reads_valid_json(tmp_path):
    file_path = tmp_path / "valid.json"
    file_path.write_text(
        '{"system": "CRM", "records": [{"event_id": "evt101"}]}',
        encoding="utf-8",
    )

    result = read_json_file(file_path)

    assert result["valid"] is True
    assert result["data"]["system"] == "CRM"
    assert result["data"]["records"][0]["event_id"] == "evt101"


def test_rejects_invalid_json(tmp_path):
    file_path = tmp_path / "invalid.json"
    file_path.write_text(
        '{"system": "CRM",}',
        encoding="utf-8",
    )

    result = read_json_file(file_path)

    assert result["valid"] is False
    assert result["data"] is None
    assert any("Invalid JSON" in error for error in result["errors"])


def test_reports_missing_file(tmp_path):
    file_path = tmp_path / "missing.json"

    result = read_json_file(file_path)

    assert result["valid"] is False
    assert "File does not exist." in result["errors"]


def test_reads_json_array(tmp_path):
    file_path = tmp_path / "array.json"
    file_path.write_text(
        '[{"event_id": "evt101"}, {"event_id": "evt102"}]',
        encoding="utf-8",
    )

    result = read_json_file(file_path)

    assert result["valid"] is True
    assert len(result["data"]) == 2
