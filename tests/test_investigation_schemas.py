
import pytest
from pydantic import ValidationError

from src.deletion_audit.investigation.schemas import (
    EvidenceReference,
    InvestigationReport,
)


def test_investigation_report_accepts_valid_data():
    report = InvestigationReport(
        resource_id="rec101",
        investigation_status="NEEDS_MORE_EVIDENCE",
        summary="A restore occurred after deletion.",
        observed_facts=["evt002 is a RESTORE event."],
        risk_analysis=["The resource may have become available again."],
        evidence_gaps=["No subsequent absence verification is supplied."],
        recommended_checks=["Verify the resource's current state."],
        evidence_references=[
            EvidenceReference(
                evidence_id="evt002",
                evidence_type="event",
                explanation="Identifies the restore event.",
            )
        ],
        limitations=["The event alone does not prove a GDPR violation."],
    )

    assert report.resource_id == "rec101"
    assert report.evidence_references[0].evidence_id == "evt002"


def test_investigation_report_rejects_invalid_status():
    with pytest.raises(ValidationError):
        InvestigationReport(
            resource_id="rec101",
            investigation_status="VIOLATION_CONFIRMED",
            summary="Test",
            observed_facts=[],
            risk_analysis=[],
            evidence_gaps=[],
            recommended_checks=[],
            evidence_references=[],
            limitations=[],
        )


def test_evidence_reference_rejects_invalid_type():
    with pytest.raises(ValidationError):
        EvidenceReference(
            evidence_id="evt002",
            evidence_type="database",
            explanation="Invalid evidence type.",
        )
