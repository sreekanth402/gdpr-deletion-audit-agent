
import json

from src.deletion_audit.ingestion.evidence_scanner import scan_evidence


def test_scan_valid_text_file(tmp_path):
    evidence_file = tmp_path / "audit.log"
    evidence_file.write_text("DELETE user u101", encoding="utf-8")

    results = scan_evidence(tmp_path)

    assert len(results) == 1
    assert results[0]["status"] == "OK"
    assert results[0]["content"] == "DELETE user u101"


def test_scan_empty_text_file(tmp_path):
    evidence_file = tmp_path / "audit.txt"
    evidence_file.write_text("   \n", encoding="utf-8")

    results = scan_evidence(tmp_path)

    assert results[0]["status"] == "ERROR"
    assert "empty" in results[0]["errors"][0].lower()


def test_scan_valid_json_file(tmp_path):
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text(
        json.dumps({"records": [{"event_id": "evt001"}]}),
        encoding="utf-8",
    )

    results = scan_evidence(tmp_path)

    assert results[0]["status"] == "OK"


def test_scan_unsupported_file(tmp_path):
    evidence_file = tmp_path / "image.png"
    evidence_file.write_bytes(b"example")

    results = scan_evidence(tmp_path)

    assert results[0]["status"] == "UNSUPPORTED"


def test_scan_missing_directory(tmp_path):
    missing_dir = tmp_path / "does_not_exist"

    results = scan_evidence(missing_dir)

    assert results[0]["status"] == "ERROR"


def test_scan_empty_directory(tmp_path):
    results = scan_evidence(tmp_path)

    assert len(results) == 1
    assert results[0]["status"] == "WARNING"


def test_scan_malformed_json_file(tmp_path):
    evidence_file = tmp_path / "broken.json"
    evidence_file.write_text('{"records": [}', encoding="utf-8")

    results = scan_evidence(tmp_path)

    assert len(results) == 1
    assert results[0]["status"] == "ERROR"
    assert results[0]["content"] is None
    assert any("Invalid JSON" in error for error in results[0]["errors"])


def test_scan_malformed_csv_file(tmp_path):
    evidence_file = tmp_path / "broken.csv"
    evidence_file.write_text(
        "event_id,user_id\n"
        "evt001,u101\n"
        "evt002,u102,extra\n",
        encoding="utf-8",
    )

    results = scan_evidence(tmp_path)

    assert len(results) == 1
    assert results[0]["status"] == "ERROR"
    assert any("expected 2 values" in error for error in results[0]["errors"])


def test_scan_path_that_is_a_file(tmp_path):
    evidence_file = tmp_path / "not_a_directory.txt"
    evidence_file.write_text("evidence", encoding="utf-8")

    results = scan_evidence(evidence_file)

    assert len(results) == 1
    assert results[0]["status"] == "ERROR"
    assert any("not a directory" in error.lower() for error in results[0]["errors"])


def test_scan_nested_evidence_file(tmp_path):
    nested_dir = tmp_path / "system_a" / "logs"
    nested_dir.mkdir(parents=True)

    evidence_file = nested_dir / "audit.log"
    evidence_file.write_text("DELETE user u101", encoding="utf-8")

    results = scan_evidence(tmp_path)

    assert len(results) == 1
    assert results[0]["status"] == "OK"
    assert results[0]["content"] == "DELETE user u101"
    assert results[0]["file"] == str(evidence_file)
