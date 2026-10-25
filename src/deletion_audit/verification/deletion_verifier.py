
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

RISK_EVENTS = {"RESTORE", "SYNC", "EXPORT", "INDEX"}


def parse_timestamp(value: str) -> datetime:
    value = value.strip()

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    timestamp = datetime.fromisoformat(value)

    if timestamp.tzinfo is None:
        raise ValueError("Timestamp must include a timezone.")

    return timestamp.astimezone(timezone.utc)


def verify_deletions(
    activities: list[dict[str, Any]],
    resolved_user_ids: set[str],
) -> dict[str, Any]:
    """Evaluate deletion evidence in the supplied activity logs."""
    events_by_resource = defaultdict(list)
    findings = []

    for row in activities:
        user_id = str(row.get("user_id", "")).strip()

        if user_id not in resolved_user_ids:
            continue

        try:
            timestamp = parse_timestamp(str(row.get("timestamp", "")))
        except (ValueError, TypeError):
            findings.append({
                "user_id": user_id,
                "event_id": row.get("event_id"),
                "finding": "INVALID_TIMESTAMP",
            })
            continue

        system_id = str(row.get("system_id", "")).strip()
        resource_id = str(row.get("resource_id", "")).strip()
        event_type = str(row.get("event_type", "")).strip().upper()

        if not system_id or not resource_id:
            continue

        key = (user_id, resource_id)
        events_by_resource[key].append({
            "event_id": str(row.get("event_id", "")),
            "timestamp": timestamp,
            "event_type": event_type,
            "system_id": system_id,
        })

    results = []

    for user_id in sorted(resolved_user_ids):
        user_resources = [
            (key, events)
            for key, events in events_by_resource.items()
            if key[0] == user_id
        ]

        user_findings = []
        deleted_resources = 0
        verified_resources = 0

        for (resource_user_id, resource_id), events in user_resources:
            if resource_user_id != user_id:
                continue

            delete_events = [
                event for event in events
                if event["event_type"] == "DELETE"
            ]

            if not delete_events:
                continue

            deleted_resources += 1
            delete_events.sort(key=lambda event: event["timestamp"])
            latest_delete = delete_events[-1]

            later_events = [
                event for event in events
                if event["timestamp"] > latest_delete["timestamp"]
            ]

            risk_events = [
                event for event in later_events
                if event["event_type"] in RISK_EVENTS
            ]

            verification_events = [
                event for event in later_events
                if event["event_type"] == "VERIFY_ABSENT"
            ]

            if risk_events:
                user_findings.append({
                    "system_id": latest_delete["system_id"],
                    "resource_id": resource_id,
                    "finding": "POST_DELETION_ACTIVITY",
                    "events": [
                        event["event_id"] for event in risk_events
                    ],
                    "systems_involved": sorted({
                        event["system_id"]
                        for event in [latest_delete, *risk_events]
                        if event.get("system_id")
                    }),
                })
            elif verification_events:
                verified_resources += 1
            else:
                user_findings.append({
                    "system_id": latest_delete["system_id"],
                    "resource_id": resource_id,
                    "finding": "VERIFICATION_MISSING",
                    "events": [],
                })

        if user_findings:
            status = "REVIEW_REQUIRED"
            reasons = user_findings
        elif deleted_resources == 0:
            status = "INCONCLUSIVE"
            reasons = ["No usable deletion event was found."]
        elif verified_resources == deleted_resources:
            status = "VERIFIED"
            reasons = [
                "Each observed deleted resource has a later absence-verification event."
            ]
        else:
            status = "INCONCLUSIVE"
            reasons = ["The available evidence is insufficient."]

        results.append({
            "user_id": user_id,
            "status": status,
            "reasons": reasons,
        })

    counts = defaultdict(int)

    for result in results:
        counts[result["status"]] += 1

    return {
        "results": results,
        "findings": findings,
        "summary": {
            "users_evaluated": len(results),
            "verified": counts["VERIFIED"],
            "review_required": counts["REVIEW_REQUIRED"],
            "inconclusive": counts["INCONCLUSIVE"],
        },
    }
