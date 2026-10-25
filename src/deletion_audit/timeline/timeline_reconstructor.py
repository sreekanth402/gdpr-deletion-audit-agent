
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
RISK_EVENTS = {"RESTORE", "SYNC", "EXPORT", "INDEX"}

def parse_timestamp(value: str) -> datetime:
    """Parse a timezone-aware timestamp and normalize it to UTC."""
    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    timestamp = datetime.fromisoformat(normalized)

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone.")

    return timestamp.astimezone(timezone.utc)


def reconstruct_timelines(
    activities: list[dict[str, Any]],
    resolved_user_ids: set[str] | None = None,
) -> dict[str, Any]:
    resolved_user_ids = (
        None if resolved_user_ids is None else set(resolved_user_ids)
    )

    timelines = defaultdict(list)
    findings = []
    seen_events = {}

    def add_finding(
        user_id: str,
        event_id: str | None,
        finding_type: str,
        severity: str,
        description: str,
        **extra: Any,
    ) -> None:
        finding = {
            "user_id": user_id or None,
            "event_id": event_id,
            "finding_type": finding_type,
            "severity": severity,
            "description": description,
        }
        finding.update(extra)
        findings.append(finding)

    for row in activities:
        user_id = str(row.get("user_id", "") or "").strip()
        event_type = str(row.get("event_type", "") or "").strip().upper()
        event_id = str(row.get("event_id", "") or "").strip()
        system_id = str(row.get("system_id", "") or "").strip()
        resource_id = str(row.get("resource_id", "") or "").strip()

        # Avoid generating timeline findings for unresolved identities.
        if (
            resolved_user_ids is not None
            and user_id not in resolved_user_ids
        ):
            continue

        if not event_id:
            add_finding(
                user_id,
                None,
                "INVALID_EVENT_ID",
                "MEDIUM",
                "Activity is missing an event ID and cannot be reliably "
                "referenced in the audit trail.",
            )

        try:
            raw_timestamp = str(row.get("timestamp", "") or "")
            timestamp = parse_timestamp(raw_timestamp)
        except (ValueError, TypeError, AttributeError):
            add_finding(
                user_id,
                event_id or None,
                "INVALID_TIMESTAMP",
                "MEDIUM",
                "Activity has a missing, invalid, or timezone-naive "
                "timestamp and cannot be placed reliably in the timeline.",
            )
            continue

        event = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "user_id": user_id,
            "system_id": system_id,
            "event_type": event_type,
            "resource_id": resource_id,
        }

        # Missing IDs cannot be safely deduplicated.
        if event_id:
            previous = seen_events.get(event_id)

            if previous is not None:
                if previous == event:
                    add_finding(
                        user_id,
                        event_id,
                        "DUPLICATE_EVENT",
                        "LOW",
                        "An identical event record appeared more than once. "
                        "Only one copy was retained in the timeline.",
                    )
                    continue

                add_finding(
                    user_id,
                    event_id,
                    "DUPLICATE_EVENT_CONFLICT",
                    "HIGH",
                    "The same event ID appears with conflicting event "
                    "details. The records require investigation.",
                    conflicting_event={
                        "previous": previous,
                        "current": event,
                    },
                )
                # Keep both conflicting records so neither is silently lost.
                timelines[user_id].append(event)
                continue

            seen_events[event_id] = event

        timelines[user_id].append(event)

    for user_id, events in timelines.items():
        events.sort(key=lambda event: event["timestamp"])
        latest_delete_by_resource = {}

        for event in events:
            event_type = event["event_type"]
            resource_id = event["resource_id"]

            # Missing resource IDs cannot establish a reliable resource match.
            if not resource_id:
                continue

            if event_type == "DELETE":
                latest_delete_by_resource[resource_id] = event
                continue

            delete_event = latest_delete_by_resource.get(resource_id)

            if (
                delete_event is None
                or event["timestamp"] <= delete_event["timestamp"]
            ):
                continue

            finding_types = {
                "RESTORE": (
                    "POST_DELETION_RESTORE",
                    "HIGH",
                    "A restore event occurred after deletion for the same "
                    "user and resource.",
                ),
                "SYNC": (
                    "POST_DELETION_SYNC",
                    "HIGH",
                    "A synchronization event occurred after deletion for "
                    "the same user and resource, potentially across systems.",
                ),
                "EXPORT": (
                    "POST_DELETION_EXPORT",
                    "HIGH",
                    "An export event occurred after deletion for the same "
                    "user and resource.",
                ),
                "INDEX": (
                    "POST_DELETION_INDEX",
                    "MEDIUM",
                    "An indexing event occurred after deletion for the same "
                    "user and resource.",
                ),
            }

            if event_type not in finding_types:
                continue

            finding_type, severity, description = finding_types[event_type]

            add_finding(
                user_id,
                event["event_id"] or None,
                finding_type,
                severity,
                description,
                system_id=event["system_id"],
                resource_id=resource_id,
                related_delete_event_id=delete_event["event_id"] or None,
                related_delete_system_id=delete_event["system_id"],
            )

    return {
        "timelines": dict(timelines),
        "findings": findings,
        "summary": {
            "users_with_activity": len(timelines),
            "events_processed": sum(
                len(events) for events in timelines.values()
            ),
            "finding_count": len(findings),
            "duplicate_event_conflicts": sum(
                finding["finding_type"] == "DUPLICATE_EVENT_CONFLICT"
                for finding in findings
            ),
        },
    }

def test_missing_resource_ids_do_not_create_false_restore_finding():
    activities = [
        {
            "event_id": "evt-delete",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "",
        },
        {
            "event_id": "evt-restore",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    assert not any(
        finding["finding_type"] == "POST_DELETION_RESTORE"
        for finding in report["findings"]
    )


def test_restore_at_same_timestamp_as_delete_is_not_post_deletion():
    activities = [
        {
            "event_id": "evt-delete",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-restore",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    assert not any(
        finding["finding_type"] == "POST_DELETION_RESTORE"
        for finding in report["findings"]
    )
