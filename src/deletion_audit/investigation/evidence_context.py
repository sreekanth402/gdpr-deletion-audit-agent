
import hashlib
import json
from datetime import datetime, timezone
from typing import Any


RISK_EVENT_TYPES = {"RESTORE", "SYNC", "EXPORT", "INDEX"}


def _stable_finding_id(finding: dict[str, Any]) -> str:
    """Generate a deterministic ID from a finding's contents."""
    canonical = json.dumps(
        finding,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"finding-{digest}"


def build_evidence_context(
    resource_id: str,
    timeline_report: dict[str, Any],
    unified_audit_report: dict[str, Any],
) -> dict[str, Any]:
    """Build a focused, evidence-based context for one resource."""

    resource_id = str(resource_id or "").strip()

    if not resource_id:
        raise ValueError("resource_id must not be empty.")

    events = []

    for user_id, user_events in timeline_report.get("timelines", {}).items():
        for event in user_events:
            if str(event.get("resource_id", "")).strip() != resource_id:
                continue

            events.append({
                "event_id": event.get("event_id"),
                "event_type": str(
                    event.get("event_type", "")
                ).strip().upper(),
                "timestamp": event.get("timestamp"),
                "user_id": str(
                    event.get("user_id") or user_id
                ).strip(),
                "system_id": event.get("system_id"),
                "resource_id": resource_id,
            })

    def sort_key(event: dict[str, Any]) -> tuple[bool, datetime, str]:
        timestamp_text = str(event.get("timestamp") or "").strip()

        try:
            if timestamp_text.endswith("Z"):
                timestamp_text = timestamp_text[:-1] + "+00:00"

            parsed = datetime.fromisoformat(timestamp_text)

            if parsed.tzinfo is None:
                raise ValueError("Timezone is required.")

            return (
                False,
                parsed.astimezone(timezone.utc),
                str(event.get("event_id") or ""),
            )
        except (ValueError, TypeError):
            return (
                True,
                datetime.max.replace(tzinfo=timezone.utc),
                str(event.get("event_id") or ""),
            )

    events.sort(key=sort_key)

    event_ids = {
        str(event.get("event_id")).strip()
        for event in events
        if event.get("event_id")
    }

    # Copy and identify findings without modifying the original report.
    findings = []

    for original in timeline_report.get("findings", []):
        if str(original.get("resource_id", "")).strip() != resource_id:
            continue

        finding = dict(original)
        finding["finding_id"] = _stable_finding_id(original)

        source_event_id = str(
            finding.get("event_id") or ""
        ).strip()

        finding["source_event_id"] = (
            source_event_id if source_event_id in event_ids else None
        )

        findings.append(finding)

    audit_result = next(
        (
            result
            for result in unified_audit_report.get("results", [])
            if str(result.get("resource_id", "")).strip() == resource_id
        ),
        None,
    )

    if audit_result is None:
        raise ValueError(
            f"No unified audit result found for resource {resource_id}."
        )

    evidence_references = [
        {
            "evidence_id": event["event_id"],
            "evidence_type": "event",
            "explanation": (
                f"Recorded {event['event_type']} event in "
                f"{event.get('system_id') or 'an unspecified system'}."
            ),
        }
        for event in events
        if event.get("event_id")
    ]

    for finding in findings:
        finding_id = finding["finding_id"]
        source_event_id = finding.get("source_event_id")
        finding_type = finding.get("finding_type", "UNKNOWN")

        # A finding is a separate evidence object from its source event.
        explanation = f"Deterministic finding: {finding_type}."

        if source_event_id:
            explanation += f" Source event: {source_event_id}."

        evidence_references.append({
            "evidence_id": finding_id,
            "evidence_type": "finding",
            "explanation": explanation,
        })

    return {
        "resource_id": resource_id,
        "audit_result": {
            "data_type": audit_result.get("data_type"),
            "policy_action": audit_result.get("policy_action"),
            "policy_status": audit_result.get("policy_status"),
            "audit_status": audit_result.get("audit_status"),
            "recommended_action": audit_result.get("recommended_action"),
        },
        "events": events,
        "timeline_findings": findings,
        "risk_events": [
            event
            for event in events
            if event["event_type"] in RISK_EVENT_TYPES
        ],
        "evidence_references": evidence_references,
        "limitations": [
            "The context contains only events and findings linked to this resource.",
            "Missing events cannot be interpreted as proof that an action did not occur.",
            "Recorded activity does not independently establish the current resource state.",
        ],
    }
