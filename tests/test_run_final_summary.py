
import json
from pathlib import Path

import pytest

from src.deletion_audit.reporting import run_final_summary as runner


def test_load_json_reads_object(tmp_path):
    path = tmp_path / "report.json"
    path.write_text('{"resource_count": 1}', encoding="utf-8")

    assert runner.load_json(path) == {"resource_count": 1}


def test_load_json_rejects_missing_file(tmp_path):
    path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="Required report not found"):
        runner.load_json(path)


def test_load_json_rejects_non_object_json(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a JSON object"):
        runner.load_json(path)


def test_main_creates_final_summary(tmp_path, monkeypatch, capsys):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    (reports_dir / "unified_audit_report.json").write_text(
        '{"resources": []}', encoding="utf-8"
    )
    (reports_dir / "ai_investigation_rec101.json").write_text(
        '{"resource_id": "rec101"}', encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)

    expected_summary = {
        "report_type": "FINAL_GDPR_DELETION_AUDIT_SUMMARY",
        "resource_count": 0,
        "investigation_reports_available": 0,
    }

    monkeypatch.setattr(
        runner, "build_final_summary", lambda **kwargs: expected_summary
    )
    monkeypatch.setattr(
        runner, "validate_final_summary", lambda summary: []
    )

    def fake_write(summary, output_path):
        output_path.write_text(
            json.dumps(summary), encoding="utf-8"
        )
        return output_path

    monkeypatch.setattr(runner, "write_final_summary", fake_write)

    runner.main()

    output_path = (
        reports_dir / "final_gdpr_deletion_audit_summary.json"
    )
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf-8")) == (
        expected_summary
    )

    output = capsys.readouterr().out
    assert "Final report validation PASSED." in output
    assert "Final GDPR deletion audit summary created." in output


def test_main_exits_when_validation_fails(tmp_path, monkeypatch, capsys):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    (reports_dir / "unified_audit_report.json").write_text(
        '{"resources": []}', encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        runner, "build_final_summary", lambda **kwargs: {}
    )
    monkeypatch.setattr(
        runner,
        "validate_final_summary",
        lambda summary: [
            {
                "severity": "ERROR",
                "code": "INVALID_REPORT",
                "message": "Simulated validation failure",
            }
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        runner.main()

    assert exc_info.value.code == 1
    output = capsys.readouterr().out
    assert "Final report validation FAILED:" in output
    assert "INVALID_REPORT" in output
