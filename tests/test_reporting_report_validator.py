
import pytest

from src.deletion_audit.reporting.report_validator import (
    _parse_timestamp,
    validate_final_summary,
)


def valid_report():
    return {
        "report_type": "FINAL_GDPR_DELETION_AUDIT_SUMMARY",
        "resources": [
            {
                "resource_id": "rec101",
                "deterministic_audit": {
                    "audit_status": "REVIEW_REQUIRED",
                    "recommended_action": "Review the evidence",
                },
                "ai_investigation": {
                    "available": False,
                    "status": "NOT_RUN",
                },
            }
        ],
        "summary": {
            "resources_evaluated": 1,
            "review_required": 1,
            "policy_review": 0,
            "verification_required": 0,
            "verified_deleted": 0,
        },
        "resource_count": 1,
        "investigation_reports_available": 0,
        "decision_authority": "Deterministic audit results remain authoritative.",
    }


def test_valid_report_has_no_issues():
    assert validate_final_summary(valid_report()) == []


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        "",
        "not-a-timestamp",
    ],
)
def test_parse_timestamp_rejects_invalid_values(value):
    assert _parse_timestamp(value) is None


def test_parse_timestamp_accepts_utc_z():
    parsed = _parse_timestamp("2026-01-01T12:00:00Z")

    assert parsed is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_parse_timestamp_normalizes_naive_timestamp():
    parsed = _parse_timestamp("2026-01-01T12:00:00")

    assert parsed is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_non_dictionary_report_is_rejected():
    issues = validate_final_summary([])

    assert any(issue["code"] == "INVALID_REPORT" for issue in issues)


def test_invalid_resources_field_is_rejected():
    report = valid_report()
    report["resources"] = None

    issues = validate_final_summary(report)

    assert any(issue["code"] == "INVALID_RESOURCES" for issue in issues)


def test_duplicate_resource_ids_are_reported():
    report = valid_report()
    duplicate = valid_report()["resources"][0].copy()
    report["resources"].append(duplicate)

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "DUPLICATE_RESOURCE_ID"
        for issue in issues
    )


def test_missing_follow_up_action_is_warning():
    report = valid_report()
    report["resources"][0]["deterministic_audit"].pop(
        "recommended_action"
    )

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "MISSING_FOLLOW_UP_ACTION"
        and issue["severity"] == "WARNING"
        for issue in issues
    )


def test_invalid_ai_status_is_reported():
    report = valid_report()
    report["resources"][0]["ai_investigation"]["status"] = "UNKNOWN"

    issues = validate_final_summary(report)

    assert any(issue["code"] == "INVALID_AI_STATUS" for issue in issues)


def test_summary_count_mismatch_is_reported():
    report = valid_report()
    report["summary"]["review_required"] = 99

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "SUMMARY_COUNT_MISMATCH"
        for issue in issues
    )


def test_missing_decision_authority_is_warning():
    report = valid_report()
    report["decision_authority"] = ""

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "MISSING_DECISION_AUTHORITY"
        and issue["severity"] == "WARNING"
        for issue in issues
    )
