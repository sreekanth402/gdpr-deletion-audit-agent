
import pytest

from src.deletion_audit.investigation.investigator import (
    investigate_resource,
)
from src.deletion_audit.investigation.schemas import (
    EvidenceReference,
    InvestigationReport,
)


class FakeResponse:
    def __init__(self, report):
        self.text = report.model_dump_json()


class FakeModelsAPI:
    def __init__(self, report):
        self.report = report
        self.last_request = None

    def generate_content(self, **kwargs):
        self.last_request = kwargs
        return FakeResponse(self.report)


class FakeClient:
    def __init__(self, report):
        self.models = FakeModelsAPI(report)


def test_investigator_accepts_valid_evidence_references():
    context = {
        "resource_id": "rec101",
        "events": [{"event_id": "evt002"}],
        "evidence_references": [
            {
                "evidence_id": "evt002",
                "evidence_type": "event",
            }
        ],
    }

    report = InvestigationReport(
        resource_id="rec101",
        investigation_status="NEEDS_MORE_EVIDENCE",
        summary="A restore event needs further investigation.",
        observed_facts=["evt002 is supplied as evidence."],
        risk_analysis=["The event may indicate post-deletion activity."],
        evidence_gaps=["The current resource state is unknown."],
        recommended_checks=["Verify the resource state."],
        evidence_references=[
            EvidenceReference(
                evidence_id="evt002",
                evidence_type="event",
                explanation="The supplied restore event.",
            )
        ],
        limitations=["This does not prove a legal violation."],
    )

    client = FakeClient(report)

    result = investigate_resource(
        context,
        client=client,
        model="test-model",
    )

    assert result.resource_id == "rec101"
    assert (
        client.models.last_request["config"].response_schema
        is InvestigationReport
    )


def test_investigator_rejects_unknown_evidence_reference():
    context = {
        "resource_id": "rec101",
        "evidence_references": [
            {
                "evidence_id": "evt002",
                "evidence_type": "event",
            }
        ],
    }

    report = InvestigationReport(
        resource_id="rec101",
        investigation_status="INCONCLUSIVE",
        summary="Insufficient evidence.",
        observed_facts=[],
        risk_analysis=[],
        evidence_gaps=[],
        recommended_checks=[],
        evidence_references=[
            EvidenceReference(
                evidence_id="evt999",
                evidence_type="event",
                explanation="Unknown event.",
            )
        ],
        limitations=["The evidence is incomplete."],
    )

    with pytest.raises(ValueError, match="not provided in the context"):
        investigate_resource(
            context,
            client=FakeClient(report),
            model="test-model",
        )


def test_investigator_requires_resource_id():
    with pytest.raises(ValueError, match="resource_id"):
        investigate_resource(
            {},
            client=FakeClient(None),
            model="test-model",
        )

def test_investigator_rejects_evidence_reference_with_wrong_type():
    context = {
        "resource_id": "rec101",
        "events": [{"event_id": "evt002"}],
        "evidence_references": [
            {
                "evidence_id": "evt002",
                "evidence_type": "event",
            }
        ],
    }

    report = InvestigationReport(
        resource_id="rec101",
        investigation_status="INCONCLUSIVE",
        summary="Insufficient evidence.",
        observed_facts=[],
        risk_analysis=[],
        evidence_gaps=[],
        recommended_checks=[],
        evidence_references=[
            EvidenceReference(
                evidence_id="evt002",
                evidence_type="finding",
                explanation="Incorrectly classified event.",
            )
        ],
        limitations=["The evidence is incomplete."],
    )

    with pytest.raises(ValueError, match="not provided in the context"):
        investigate_resource(
            context,
            client=FakeClient(report),
            model="test-model",
        )


def test_investigator_rejects_finding_with_missing_source_event():
    context = {
        "resource_id": "rec101",
        "events": [],
        "timeline_findings": [
            {
                "finding_id": "finding-123",
                "finding_type": "POST_DELETION_RESTORE",
                "source_event_id": "evt999",
            }
        ],
        "evidence_references": [
            {
                "evidence_id": "finding-123",
                "evidence_type": "finding",
            }
        ],
    }

    report = InvestigationReport(
        resource_id="rec101",
        investigation_status="INCONCLUSIVE",
        summary="Insufficient evidence.",
        observed_facts=[],
        risk_analysis=[],
        evidence_gaps=[],
        recommended_checks=[],
        evidence_references=[
            EvidenceReference(
                evidence_id="finding-123",
                evidence_type="finding",
                explanation="A supplied finding.",
            )
        ],
        limitations=["The evidence is incomplete."],
    )

    with pytest.raises(
        ValueError,
        match="source event not provided in the context",
    ):
        investigate_resource(
            context,
            client=FakeClient(report),
            model="test-model",
        )

def test_investigator_rejects_unknown_remediation_evidence():
    from src.deletion_audit.investigation.schemas import (
        RemediationRecommendation,
    )

    context = {
        "resource_id": "rec101",
        "events": [{"event_id": "evt002"}],
        "evidence_references": [
            {
                "evidence_id": "evt002",
                "evidence_type": "event",
            }
        ],
    }

    report = InvestigationReport(
        resource_id="rec101",
        investigation_status="NEEDS_MORE_EVIDENCE",
        summary="A restore event requires investigation.",
        observed_facts=["evt002 is present in the supplied context."],
        risk_analysis=["The resource state needs confirmation."],
        evidence_gaps=["Current resource state is unknown."],
        recommended_checks=["Check the authoritative resource store."],
        evidence_references=[
            EvidenceReference(
                evidence_id="evt002",
                evidence_type="event",
                explanation="Supplied restore event.",
            )
        ],
        limitations=["The event does not prove current data presence."],
        remediation_recommendations=[
            RemediationRecommendation(
                action="Investigate the resource state.",
                rationale="The current state is not established.",
                priority="HIGH",
                evidence_ids=["evt999"],
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match="Remediation recommendation references evidence",
    ):
        investigate_resource(
            context,
            client=FakeClient(report),
            model="test-model",
        )


def test_investigation_report_supports_verification_plan():
    from src.deletion_audit.investigation.schemas import VerificationStep

    report = InvestigationReport(
        resource_id="rec101",
        investigation_status="NEEDS_MORE_EVIDENCE",
        summary="The resource state remains unverified.",
        observed_facts=[],
        risk_analysis=[],
        evidence_gaps=["No authoritative state check was supplied."],
        recommended_checks=["Inspect the authoritative resource store."],
        evidence_references=[],
        limitations=["No deletion proof is currently available."],
        verification_steps=[
            VerificationStep(
                step="Query the authoritative resource store.",
                expected_evidence="Timestamped query result.",
                pass_criteria="The resource is absent from the authoritative store.",
            )
        ],
        required_proof=["Timestamped authoritative query result."],
        closure_criteria=["Required proof is reviewed and accepted."],
    )

    assert report.verification_steps[0].pass_criteria
    assert report.required_proof
    assert report.closure_criteria
