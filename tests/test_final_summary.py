
import pytest

from src.deletion_audit.reporting.final_summary import (
    build_final_summary,
    write_final_summary,
)


def test_combines_audit_and_investigation():
    audit = {
        "summary": {"resources_evaluated": 1, "review_required": 1},
        "results": [
            {
                "resource_id": "rec101",
                "audit_status": "REVIEW_REQUIRED",
                "policy_action": "DELETE",
            }
        ],
        "integrity_findings": [],
        "event_id_conflicts": [],
        "limitations": [],
    }

    investigations = [
        {
            "resource_id": "rec101",
            "investigation_status": "NEEDS_MORE_EVIDENCE",
            "summary": "Current deletion status is not established.",
            "evidence_gaps": ["Missing current-state verification."],
            "recommended_checks": ["Check the source system."],
            "limitations": ["Only recorded events were reviewed."],
        }
    ]

    result = build_final_summary(audit, investigations)

    assert result["resource_count"] == 1
    assert result["investigation_reports_available"] == 1

    resource = result["resources"][0]

    assert resource["deterministic_audit"]["audit_status"] == "REVIEW_REQUIRED"
    assert resource["ai_investigation"]["status"] == "NEEDS_MORE_EVIDENCE"
    assert resource["ai_investigation"]["available"] is True


def test_resource_without_investigation_is_not_run():
    audit = {
        "summary": {},
        "results": [{"resource_id": "rec102", "audit_status": "VERIFIED_DELETED"}],
    }

    result = build_final_summary(audit, [])

    ai = result["resources"][0]["ai_investigation"]

    assert ai["available"] is False
    assert ai["status"] == "NOT_RUN"


def test_duplicate_investigations_are_rejected():
    audit = {"results": [{"resource_id": "rec101"}]}
    investigations = [
        {"resource_id": "rec101"},
        {"resource_id": "rec101"},
    ]

    with pytest.raises(ValueError, match="Duplicate investigation"):
        build_final_summary(audit, investigations)


def test_missing_resource_id_is_rejected():
    audit = {"results": [{"audit_status": "REVIEW_REQUIRED"}]}

    with pytest.raises(ValueError, match="resource_id"):
        build_final_summary(audit, [])


def test_writes_valid_json(tmp_path):
    summary = {"report_type": "FINAL_GDPR_DELETION_AUDIT_SUMMARY"}

    output = write_final_summary(summary, tmp_path / "nested" / "summary.json")

    assert output.is_file()
    assert '"report_type"' in output.read_text(encoding="utf-8")

def test_preserves_integrity_findings_and_event_id_conflicts():
    audit = {
        "summary": {"resources_evaluated": 1},
        "results": [
            {
                "resource_id": "rec101",
                "audit_status": "REVIEW_REQUIRED",
            }
        ],
        "integrity_findings": [
            {
                "resource_id": "rec101",
                "event_id": "evt-restore",
                "finding_type": "POST_DELETION_RESTORE",
                "severity": "HIGH",
            }
        ],
        "event_id_conflicts": [
            {
                "event_id": "evt-conflict",
                "resource_id": "rec101",
            }
        ],
        "limitations": ["Current state was not independently verified."],
    }

    result = build_final_summary(audit, [])

    assert result["integrity_findings"] == audit["integrity_findings"]
    assert result["event_id_conflicts"] == audit["event_id_conflicts"]
    assert result["limitations"] == audit["limitations"]


def test_ai_investigation_does_not_override_deterministic_status():
    audit = {
        "summary": {"resources_evaluated": 1, "review_required": 1},
        "results": [
            {
                "resource_id": "rec101",
                "audit_status": "REVIEW_REQUIRED",
            }
        ],
        "integrity_findings": [],
        "event_id_conflicts": [],
        "limitations": [],
    }

    investigations = [
        {
            "resource_id": "rec101",
            "investigation_status": "INVESTIGATION_COMPLETE",
            "summary": "Investigation completed.",
            "evidence_gaps": [],
            "recommended_checks": [],
            "limitations": [],
        }
    ]

    result = build_final_summary(audit, investigations)
    resource = result["resources"][0]

    assert resource["deterministic_audit"]["audit_status"] == "REVIEW_REQUIRED"
    assert resource["ai_investigation"]["status"] == "INVESTIGATION_COMPLETE"
    assert result["summary"]["review_required"] == 1
def test_preserves_unmatched_and_ambiguous_identity_requests():
    audit = {
        "summary": {},
        "results": [{"resource_id": "rec101"}],
    }

    identity_resolution = {
        "total_requests": 2,
        "summary": {
            "MATCHED": 0,
            "UNMATCHED": 1,
            "AMBIGUOUS": 1,
        },
        "results": [
            {
                "case_id": "case_101",
                "status": "UNMATCHED",
                "matched_user_id": None,
                "reason": "No identity record matches this email.",
            },
            {
                "case_id": "case_102",
                "status": "AMBIGUOUS",
                "matched_user_id": None,
                "candidate_user_ids": ["u101", "u999"],
            },
        ],
    }

    result = build_final_summary(
        audit,
        [],
        identity_resolution=identity_resolution,
    )

    assert result["identity_resolution"]["total_requests"] == 2
    assert result["identity_resolution"]["summary"]["UNMATCHED"] == 1
    assert result["identity_resolution"]["summary"]["AMBIGUOUS"] == 1
    assert len(result["identity_resolution"]["results"]) == 2


def test_final_summary_supports_missing_identity_report():
    result = build_final_summary(
        {"summary": {}, "results": []},
        [],
    )

    assert result["identity_resolution"]["total_requests"] == 0
    assert result["identity_resolution"]["results"] == []