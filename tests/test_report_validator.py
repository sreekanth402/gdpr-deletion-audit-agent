
from copy import deepcopy

from src.deletion_audit.audit.report_validator import (
    validate_final_summary,
)


def make_valid_report():
    return {
        "report_type": "FINAL_GDPR_DELETION_AUDIT_SUMMARY",
        "summary": {
            "resources_evaluated": 1,
            "review_required": 0,
            "policy_review": 0,
            "verification_required": 0,
            "verified_deleted": 1,
        },
        "resource_count": 1,
        "investigation_reports_available": 1,
        "resources": [
            {
                "resource_id": "rec102",
                "deterministic_audit": {
                    "resource_id": "rec102",
                    "audit_status": "VERIFIED_DELETED",
                    "delete_event_id": "evt003",
                    "delete_evidence": {
                        "event_id": "evt003",
                        "event_type": "DELETE",
                        "timestamp": "2026-10-20T11:00:00+00:00",
                    },
                    "absence_verification_event_ids": ["evt004"],
                    "absence_verification_evidence": [
                        {
                            "event_id": "evt004",
                            "event_type": "VERIFY_ABSENT",
                            "timestamp": "2026-10-20T11:30:00+00:00",
                        }
                    ],
                    "recommended_action": "Retain the evidence.",
                },
                "ai_investigation": {
                    "available": True,
                    "status": "INVESTIGATION_COMPLETE",
                    "summary": "Evidence reviewed.",
                    "evidence_gaps": [],
                    "recommended_checks": [],
                    "limitations": [],
                },
            }
        ],
        "integrity_findings": [],
        "event_id_conflicts": [],
        "limitations": [],
        "decision_authority": (
            "Deterministic audit results remain authoritative."
        ),
    }


def test_valid_report_has_no_errors():
    report = make_valid_report()

    assert validate_final_summary(report) == []


def test_rejects_missing_absence_verification():
    report = make_valid_report()
    report["resources"][0]["deterministic_audit"][
        "absence_verification_evidence"
    ] = []

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "MISSING_ABSENCE_VERIFICATION"
        for issue in issues
    )


def test_rejects_verification_before_deletion():
    report = make_valid_report()
    report["resources"][0]["deterministic_audit"][
        "absence_verification_evidence"
    ][0]["timestamp"] = "2026-10-20T10:30:00+00:00"

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "INVALID_ABSENCE_VERIFICATION"
        for issue in issues
    )


def test_detects_summary_count_mismatch():
    report = make_valid_report()
    report["summary"]["verified_deleted"] = 0

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "SUMMARY_COUNT_MISMATCH"
        for issue in issues
    )


def test_detects_duplicate_resources():
    report = make_valid_report()
    report["resources"].append(
        deepcopy(report["resources"][0])
    )
    report["resource_count"] = 2
    report["summary"]["resources_evaluated"] = 2
    report["summary"]["verified_deleted"] = 2
    report["investigation_reports_available"] = 2

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "DUPLICATE_RESOURCE_ID"
        for issue in issues
    )


def test_detects_ai_status_mismatch():
    report = make_valid_report()
    report["resources"][0]["ai_investigation"]["available"] = False

    issues = validate_final_summary(report)

    assert any(
        issue["code"] == "AI_AVAILABILITY_MISMATCH"
        for issue in issues
    )
