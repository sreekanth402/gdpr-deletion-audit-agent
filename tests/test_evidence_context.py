
import pytest

from src.deletion_audit.investigation.evidence_context import (
    build_evidence_context,
)


@pytest.fixture
def reports():
    timeline_report = {
        "timelines": {
            "u101": [
                {
                    "event_id": "evt001",
                    "event_type": "DELETE",
                    "timestamp": "2026-10-20T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "resource_id": "rec101",
                },
                {
                    "event_id": "evt002",
                    "event_type": "RESTORE",
                    "timestamp": "2026-10-21T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "resource_id": "rec101",
                },
                {
                    "event_id": "evt003",
                    "event_type": "DELETE",
                    "timestamp": "2026-10-20T11:00:00+00:00",
                    "user_id": "u102",
                    "system_id": "crm",
                    "resource_id": "rec102",
                },
            ]
        },
        "findings": [
            {
                "finding_type": "POST_DELETION_RESTORE",
                "severity": "HIGH",
                "event_id": "evt002",
                "user_id": "u101",
                "resource_id": "rec101",
            }
        ],
    }

    unified_audit_report = {
        "results": [
            {
                "resource_id": "rec101",
                "data_type": "Customer Profile",
                "policy_action": "DELETE",
                "policy_status": "RULE_MATCHED",
                "audit_status": "REVIEW_REQUIRED",
                "recommended_action": "Investigate the restore event.",
            },
            {
                "resource_id": "rec102",
                "audit_status": "VERIFIED_DELETED",
            },
        ]
    }

    return timeline_report, unified_audit_report


def test_context_contains_only_requested_resource(reports):
    timeline, audit = reports

    context = build_evidence_context("rec101", timeline, audit)

    assert [event["event_id"] for event in context["events"]] == [
        "evt001",
        "evt002",
    ]
    assert all(
        event["resource_id"] == "rec101"
        for event in context["events"]
    )


def test_context_includes_risk_finding_and_references(reports):
    timeline, audit = reports

    context = build_evidence_context("rec101", timeline, audit)

    assert len(context["risk_events"]) == 1
    assert context["risk_events"][0]["event_id"] == "evt002"
    assert context["timeline_findings"][0]["finding_type"] == (
        "POST_DELETION_RESTORE"
    )

    references = context["evidence_references"]
    assert any(
        ref["evidence_id"] == "evt001"
        and ref["evidence_type"] == "event"
        for ref in references
    )
    finding = context["timeline_findings"][0]

    assert any(
        ref["evidence_id"] == finding["finding_id"]
        and ref["evidence_type"] == "finding"
        for ref in references
    )
    assert finding["finding_id"] != "evt002"
    assert finding["source_event_id"] == "evt002"

    event_reference = next(
        ref for ref in references
        if ref["evidence_type"] == "event"
        and ref["evidence_id"] == "evt002"
    )
    finding_reference = next(
        ref for ref in references
        if ref["evidence_type"] == "finding"
        and ref["evidence_id"] == finding["finding_id"]
    )

    assert event_reference["evidence_id"] == "evt002"
    assert finding["source_event_id"] == "evt002"
    assert finding_reference["evidence_id"] != "evt002"

def test_context_rejects_unknown_resource(reports):
    timeline, audit = reports

    with pytest.raises(ValueError, match="No unified audit result"):
        build_evidence_context("unknown", timeline, audit)


def test_context_rejects_empty_resource_id(reports):
    timeline, audit = reports

    with pytest.raises(ValueError, match="must not be empty"):
        build_evidence_context(" ", timeline, audit)
