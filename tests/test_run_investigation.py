
import json
import sys
from types import SimpleNamespace

import pytest

from src.deletion_audit.investigation import run_investigation as runner


def test_load_json_report_reads_existing_report(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    report_file = reports_dir / "sample.json"
    report_file.write_text('{"status": "complete"}', encoding="utf-8")

    monkeypatch.setattr(runner, "REPORTS_DIR", reports_dir)

    result = runner.load_json_report("sample.json")

    assert result == {"status": "complete"}


def test_load_json_report_raises_for_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="Required report not found"):
        runner.load_json_report("missing.json")


def test_main_writes_investigation_report(tmp_path, monkeypatch, capsys):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    (reports_dir / "timeline_reconstruction_report.json").write_text(
        '{"events": []}', encoding="utf-8"
    )
    (reports_dir / "unified_audit_report.json").write_text(
        '{"findings": []}', encoding="utf-8"
    )

    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(runner, "build_evidence_context",
                        lambda **kwargs: {"resource_id": kwargs["resource_id"]})
    monkeypatch.setattr(
        runner,
        "investigate_resource",
        lambda context: SimpleNamespace(
            model_dump=lambda **kwargs: {
                "resource_id": context["resource_id"],
                "investigation_status": "completed",
            },
            investigation_status="completed",
        ),
    )
    monkeypatch.setattr(sys, "argv", ["run_investigation", "--resource", "rec101"])

    runner.main()

    output_file = reports_dir / "ai_investigation_rec101.json"
    assert output_file.exists()
    assert json.loads(output_file.read_text(encoding="utf-8")) == {
        "resource_id": "rec101",
        "investigation_status": "completed",
    }

    output = capsys.readouterr().out
    assert "AI investigation completed." in output
    assert "Resource: rec101" in output
    assert "Status: completed" in output

@pytest.mark.parametrize(
    ("status_code", "expected_message"),
    [
        (503, "Gemini is temporarily unavailable (503)"),
        (429, "Gemini API quota or rate limit reached (429)"),
        (500, "Gemini API request failed"),
    ],
)
def test_main_handles_gemini_api_errors(
    tmp_path, monkeypatch, capsys, status_code, expected_message
):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    (reports_dir / "timeline_reconstruction_report.json").write_text(
        '{"events": []}', encoding="utf-8"
    )
    (reports_dir / "unified_audit_report.json").write_text(
        '{"findings": []}', encoding="utf-8"
    )

    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(
        runner,
        "build_evidence_context",
        lambda **kwargs: {"resource_id": kwargs["resource_id"]},
    )

    def raise_api_error(context):
        raise runner.errors.APIError(
            code=status_code,
            response_json={"error": {"message": "simulated API failure"}},
        )

    monkeypatch.setattr(runner, "investigate_resource", raise_api_error)
    monkeypatch.setattr(
        sys, "argv", ["run_investigation", "--resource", "rec101"]
    )

    with pytest.raises(SystemExit) as exc_info:
        runner.main()

    assert exc_info.value.code == 1
    assert expected_message in capsys.readouterr().err
    assert not (reports_dir / "ai_investigation_rec101.json").exists()
