
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    """Reference to an event or finding in the audit evidence."""

    evidence_id: str = Field(
        description="Exact event ID or finding ID from the supplied evidence."
    )
    evidence_type: Literal["event", "finding"] = Field(
        description="Whether this reference identifies an event or finding."
    )
    explanation: str = Field(
        description="What this evidence supports in the investigation."
    )


class RemediationRecommendation(BaseModel):
    """A proposed corrective action for a human auditor to review."""

    action: str = Field(
        description="Specific corrective action to consider."
    )
    rationale: str = Field(
        description="Why the action is relevant to the supplied evidence."
    )
    priority: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        description="Suggested urgency based on evidence and potential impact."
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Exact supplied event or finding IDs supporting this action.",
    )
    requires_human_approval: bool = Field(
        default=True,
        description="Whether a human must approve the action before execution.",
    )


class VerificationStep(BaseModel):
    """A check needed to verify the outcome of remediation."""

    step: str = Field(
        description="Concrete verification procedure for the auditor."
    )
    expected_evidence: str = Field(
        description="Evidence that should be collected to establish the result."
    )
    pass_criteria: str = Field(
        description="Observable condition required for this check to pass."
    )


class InvestigationReport(BaseModel):
    """Structured output produced by the AI investigator."""

    resource_id: str = Field(
        description="Resource being investigated."
    )
    investigation_status: Literal[
        "COMPLETED",
        "NEEDS_MORE_EVIDENCE",
        "INCONCLUSIVE",
    ] = Field(
        description="Whether the investigation reached a supported conclusion."
    )
    summary: str = Field(
        description="Concise summary grounded in the supplied evidence."
    )
    observed_facts: list[str] = Field(
        description="Facts directly supported by the supplied evidence."
    )
    risk_analysis: list[str] = Field(
        description="Potential risks and why they warrant investigation."
    )
    evidence_gaps: list[str] = Field(
        description="Information needed but missing from the supplied evidence."
    )
    recommended_checks: list[str] = Field(
        description="Concrete follow-up checks for a human auditor."
    )
    evidence_references: list[EvidenceReference] = Field(
        description="Exact evidence references supporting the analysis."
    )
    limitations: list[str] = Field(
        description="Uncertainties and conclusions the evidence cannot establish."
    )
    remediation_recommendations: list[RemediationRecommendation] = Field(
        default_factory=list,
        description="Proposed corrective actions; never execute automatically.",
    )
    verification_steps: list[VerificationStep] = Field(
        default_factory=list,
        description="Steps to verify remediation and collect proof.",
    )
    required_proof: list[str] = Field(
        default_factory=list,
        description="Evidence required before a human auditor closes the case.",
    )
    closure_criteria: list[str] = Field(
        default_factory=list,
        description="Conditions that must be satisfied before case closure.",
    )
