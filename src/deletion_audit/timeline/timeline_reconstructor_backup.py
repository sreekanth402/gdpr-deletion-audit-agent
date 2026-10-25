
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


RISK_EVENTS = {
    "RESTORE",
    "SYNC",
    "EXPORT",
    "INDEX",
    "SEARCH",
    "DOWNLOAD",
}


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and ensure it is timezone-aware."""
    if value is None:
        raise ValueError("Timestamp is missing")

    timestamp = str(value).strip()
    if not timestamp:
        raise ValueError("Timestamp is empty")

    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"

    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")

    return parsed.astimezone(timezone.utc)


def reconstruct_timelines(
    activities: list[dict[str, Any]],
    resolved_user_ids: set[str],
) -> dict[str, Any]:
    timelines = defaultdict(list)
    findings = []

    for row in activities:
        user_id = str(row.get("user_id", "")).strip()
        event_type = str(row.get("event_type", "")).strip().upper()

        if not user_id or user_id not in resolved_user_ids:
            continue

        try:
            timestamp = parse_timestamp(str(row.get("timestamp", "")))
        except (ValueError, TypeError):
            findings.append({
                "user_id": user_id,
                "event_id": row.get("event_id"),
                "finding_type": "INVALID_TIMESTAMP",
                "severity": "MEDIUM",
                "description": (
                    "Activity has a missing or invalid "
                    "timezone-aware timestamp."
                ),
            })
            continue

        timelines[user_id].append({
            "event_id": str(row.get("event_id", "")),
            "timestamp": timestamp.isoformat(),
            "user_id": user_id,
            "system_id": str(row.get("system_id", "")).strip(),
            "event_type": event_type,
            "resource_id": str(row.get("resource_id", "")).strip(),
        })

    for user_id, events in timelines.items():
        events.sort(key=lambda event: event["timestamp"])

        # Track deletions by resource across systems.
        latest_delete_by_resource = {}

        for event in events:
            event_type = event["event_type"]
            resource_id = event["resource_id"]

            if event_type == "DELETE":
                latest_delete_by_resource[resource_id] = event
                continue

            if event_type not in RISK_EVENTS:
                continue

            delete_event = latest_delete_by_resource.get(resource_id)

            if (
                delete_event is None
                or event["timestamp"] <= delete_event["timestamp"]
            ):
                continue

            if event_type == "RESTORE":
                finding_type = "POST_DELETION_RESTORE"
                severity = "HIGH"
                description = (
                    "A restore event occurred after deletion "
                    "for the same user and resource."
                )
            elif event_type == "SYNC":
                finding_type = "POST_DELETION_SYNC"
                severity = "HIGH"
                description = (
                    "A synchronization event occurred after deletion "
                    "for the same user and resource, potentially across systems."
                )
            elif event_type == "EXPORT":
                finding_type = "POST_DELETION_EXPORT"
                severity = "HIGH"
                description = (
                    "An export event occurred after deletion "
                    "for the same user and resource."
                )
            else:
                finding_type = "POST_DELETION_INDEX"
                severity = "MEDIUM"
                description = (
                    "An indexing event occurred after deletion "
                    "for the same user and resource."
                )

            findings.append({
                "user_id": user_id,
                "event_id": event["event_id"],
                "system_id": event["system_id"],
                "resource_id": resource_id,
                "finding_type": finding_type,
                "severity": severity,
                "description": description,
                "related_delete_event_id": delete_event["event_id"],
                "related_delete_system_id": delete_event["system_id"],
            })

    return {
        "timelines": dict(timelines),
        "findings": findings,
        "summary": {
            "users_with_activity": len(timelines),
            "events_processed": sum(
                len(events) for events in timelines.values()
            ),
            "finding_count": len(findings),
        },
    }
