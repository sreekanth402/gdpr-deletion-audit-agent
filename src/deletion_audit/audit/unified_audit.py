
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


RISK_FINDINGS = {
    "POST_DELETION_RESTORE",
    "POST_DELETION_SYNC",
    "POST_DELETION_EXPORT",
    "POST_DELETION_INDEX",
}


def normalize(value: Any) -> str:
    """Convert a value to a trimmed string."""
    return str(value or "").strip()


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp and normalize it to UTC."""
    text = normalize(value)

    if not text:
        return None

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        timestamp = datetime.fromisoformat(text)

        if timestamp.tzinfo is None:
            return None

        return timestamp.astimezone(timezone.utc)

    except (ValueError, TypeError):
        return None


def build_unified_audit(
    resource_mappings: list[dict[str, Any]],
    policy_report: dict[str, Any],
    timeline_report: dict[str, Any],
    verification_report: dict[str, Any],
) -> dict[str, Any]:
    """Combine policy, timeline, and resource-level verification evidence."""

    # Index policy decisions by normalized data type.
    policy_by_type = {}

    for item in policy_report.get("decisions", []):
        data_type = normalize(item.get("data_type"))

        if not data_type:
            continue

        key = data_type.casefold()

        if key in policy_by_type:
            raise ValueError(
                f"Duplicate policy decision for data type: {data_type}"
            )

        policy_by_type[key] = item

    # Validate and index resource mappings.
    mappings_by_resource = {}

    for row_number, mapping in enumerate(resource_mappings, start=2):
        resource_id = normalize(mapping.get("resource_id"))
        data_type = normalize(mapping.get("data_type"))

        if not resource_id or not data_type:
            raise ValueError(
                f"Missing resource_id or data_type "
                f"in resource mapping row {row_number}."
            )

        if resource_id in mappings_by_resource:
            raise ValueError(
                f"Duplicate resource_id in resource mappings: {resource_id}"
            )

        mappings_by_resource[resource_id] = data_type

    # Index timeline events by resource ID.
    events_by_resource = defaultdict(list)

    for user_id, events in timeline_report.get("timelines", {}).items():
        for event in events:
            resource_id = normalize(event.get("resource_id"))

            if not resource_id:
                continue

            timestamp = parse_timestamp(event.get("timestamp"))

            enriched_event = {
                **event,
                "user_id": normalize(event.get("user_id")) or user_id,
                "_parsed_timestamp": timestamp,
            }

            events_by_resource[resource_id].append(enriched_event)

    # Index timeline events by event ID for finding traceability.
    events_by_id = {}

    for events in events_by_resource.values():
        for event in events:
            event_id = normalize(event.get("event_id"))

            if event_id:
                events_by_id.setdefault(event_id, event)

    # Index timeline findings by resource ID.
    findings_by_resource = defaultdict(list)

    for finding in timeline_report.get("findings", []):
        resource_id = normalize(finding.get("resource_id"))

        if resource_id:
            findings_by_resource[resource_id].append(finding)

    # Index user-level verification results for context.
    verification_by_user = {
        normalize(item.get("user_id")): item
        for item in verification_report.get("results", [])
        if normalize(item.get("user_id"))
    }

    results = []

    for resource_id, data_type in mappings_by_resource.items():
        policy = policy_by_type.get(data_type.casefold())

        resource_events = events_by_resource.get(resource_id, [])

        resource_events = sorted(
            resource_events,
            key=lambda event: (
                event["_parsed_timestamp"] is None,
                event["_parsed_timestamp"]
                or datetime.max.replace(tzinfo=timezone.utc),
            ),
        )

        resource_findings = findings_by_resource.get(resource_id, [])

        if policy is None:
            policy_action = None
            policy_status = "REVIEW_REQUIRED"
        else:
            policy_action = (
                normalize(policy.get("action")).upper() or None
            )
            policy_status = (
                normalize(policy.get("status")) or "REVIEW_REQUIRED"
            )

        delete_events = [
            event
            for event in resource_events
            if normalize(event.get("event_type")).upper() == "DELETE"
            and event["_parsed_timestamp"] is not None
        ]

        latest_delete = (
            max(
                delete_events,
                key=lambda event: event["_parsed_timestamp"],
            )
            if delete_events
            else None
        )

        later_events = []

        if latest_delete:
            delete_timestamp = latest_delete["_parsed_timestamp"]

            later_events = [
                event
                for event in resource_events
                if event["_parsed_timestamp"] is not None
                and event["_parsed_timestamp"] > delete_timestamp
            ]

        absence_verifications = [
            event
            for event in later_events
            if normalize(event.get("event_type")).upper()
            == "VERIFY_ABSENT"
        ]

        # A risk finding is relevant to this deletion only if its
        # associated event is later than the latest DELETE event.
        later_risk_findings = []

        if latest_delete:
            delete_timestamp = latest_delete["_parsed_timestamp"]

            for finding in resource_findings:
                finding_type = normalize(
                    finding.get("finding_type")
                ).upper()

                if finding_type not in RISK_FINDINGS:
                    continue

                finding_event_id = normalize(finding.get("event_id"))
                finding_event = events_by_id.get(finding_event_id)

                if not finding_event:
                    continue

                finding_resource = normalize(
                    finding_event.get("resource_id")
                )

                finding_timestamp = finding_event.get(
                    "_parsed_timestamp"
                )

                if (
                    finding_resource == resource_id
                    and finding_timestamp is not None
                    and finding_timestamp > delete_timestamp
                ):
                    later_risk_findings.append(finding)

        # Determine resource audit status.
        if later_risk_findings:
            audit_status = "REVIEW_REQUIRED"
            recommended_action = (
                "Investigate post-deletion activity and determine whether "
                "the resource was restored, synchronized, exported, or indexed."
            )

        elif policy is None or policy_status != "RULE_MATCHED":
            audit_status = "POLICY_REVIEW"
            recommended_action = (
                "Resolve the missing or invalid policy decision before "
                "determining the required action."
            )

        elif policy_action != "DELETE":
            audit_status = "POLICY_REVIEW"
            recommended_action = (
                f"Apply and verify the configured {policy_action} policy "
                "as appropriate; this audit does not treat it as a deletion."
            )

        elif latest_delete is None:
            audit_status = "VERIFICATION_REQUIRED"
            recommended_action = (
                "Find evidence that deletion was attempted, or determine "
                "why no valid, timestamped DELETE event exists for this resource."
            )

        elif any(
            normalize(finding.get("finding_type")).upper()
            == "INVALID_TIMESTAMP"
            for finding in resource_findings
        ):
            audit_status = "VERIFICATION_REQUIRED"
            recommended_action = (
                "Resolve the invalid timestamp associated with this resource "
                "before making a verified-deletion claim."
            )

        elif not absence_verifications:
            audit_status = "VERIFICATION_REQUIRED"
            recommended_action = (
                "Obtain a resource-specific absence verification recorded "
                "after the latest deletion event."
            )

        else:
            audit_status = "VERIFIED_DELETED"
            recommended_action = (
                "A later absence-verification event was found. Retain the "
                "evidence and confirm that the verification method is reliable."
            )

        involved_users = sorted({
            normalize(event.get("user_id"))
            for event in resource_events
            if normalize(event.get("user_id"))
        } | {
            normalize(finding.get("user_id"))
            for finding in resource_findings
            if normalize(finding.get("user_id"))
        })

        user_verification_context = {
            user_id: verification_by_user.get(
                user_id, {}
            ).get("status", "INCONCLUSIVE")
            for user_id in involved_users
        }

        def event_evidence(event: dict[str, Any]) -> dict[str, Any]:
            """Return selected, auditable fields from an event."""
            return {
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "timestamp": event.get("timestamp"),
                "user_id": event.get("user_id"),
                "system_id": event.get("system_id"),
                "resource_id": event.get("resource_id"),
            }

        traceable_findings = []

        for finding in resource_findings:
            finding_event_id = normalize(finding.get("event_id"))
            finding_event = events_by_id.get(finding_event_id)

            traceable_findings.append({
                "finding_type": finding.get("finding_type"),
                "severity": finding.get("severity"),
                "event_id": finding.get("event_id"),
                "user_id": finding.get("user_id"),
                "system_id": (
                    finding.get("system_id")
                    or (
                        finding_event.get("system_id")
                        if finding_event
                        else None
                    )
                ),
                "timestamp": (
                    finding_event.get("timestamp")
                    if finding_event
                    else None
                ),
                "related_delete_event_id": finding.get(
                    "related_delete_event_id"
                ),
                "related_delete_system_id": finding.get(
                    "related_delete_system_id"
                ),
            })

        results.append({
            "resource_id": resource_id,
            "data_type": data_type,
            "policy_action": policy_action,
            "policy_status": policy_status,
            "audit_status": audit_status,
            "delete_event_id": (
                latest_delete.get("event_id") if latest_delete else None
            ),
            "delete_evidence": (
                event_evidence(latest_delete) if latest_delete else None
            ),
            "absence_verification_event_ids": [
                event.get("event_id")
                for event in absence_verifications
            ],
            "absence_verification_evidence": [
                event_evidence(event)
                for event in absence_verifications
            ],
            "timeline_findings": traceable_findings,
            "verification_statuses_by_user": user_verification_context,
            "recommended_action": recommended_action,
        })

    summary = {
        "resources_evaluated": len(results),
        "review_required": sum(
            item["audit_status"] == "REVIEW_REQUIRED"
            for item in results
        ),
        "policy_review": sum(
            item["audit_status"] == "POLICY_REVIEW"
            for item in results
        ),
        "verification_required": sum(
            item["audit_status"] == "VERIFICATION_REQUIRED"
            for item in results
        ),
        "verified_deleted": sum(
            item["audit_status"] == "VERIFIED_DELETED"
            for item in results
        ),
    }


    return {
        "summary": summary,
        "results": results,
        "integrity_findings": [
            finding
            for finding in timeline_report.get("findings", [])
            if finding.get("finding_type") in {
                "INVALID_EVENT_ID",
                "INVALID_TIMESTAMP",
                "POST_DELETION_RESTORE",
                "POST_DELETION_SYNC",
                "POST_DELETION_EXPORT",
                "POST_DELETION_INDEX",
            }
        ],
        "event_id_conflicts": timeline_report.get(
            "event_id_conflicts", []
        ),
        "limitations": [
            "Resource mappings are assumed to be accurate.",
            "User-level verification statuses are context only; "
            "resource-level status uses events linked by resource_id.",
            "A VERIFY_ABSENT event is accepted as evidence only if it "
            "occurs after the latest valid, timestamped DELETE event.",
            "The event data does not independently establish the reliability "
            "or completeness of the verification method.",
            "A resource ID must identify the same logical resource "
            "consistently across relevant events.",
            "Events with missing or invalid timestamps cannot establish "
            "chronological ordering for deletion verification.",
        ],
    }
