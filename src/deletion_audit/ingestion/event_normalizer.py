
from typing import Any


REQUIRED_EVENT_FIELDS = {
    "event_id",
    "timestamp",
    "user_id",
    "event_type",
    "resource_id",
}


def normalize_event_records(
    records: Any,
    default_system: str = "",
) -> list[dict[str, str]]:
    """Validate and normalize a list of event records."""

    if not isinstance(records, list):
        raise ValueError("Event records must be a list.")

    normalized_events: list[dict[str, str]] = []

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(
                f"Record {index + 1} must be an object."
            )

        missing = [
            field
            for field in sorted(REQUIRED_EVENT_FIELDS)
            if not str(record.get(field, "")).strip()
        ]

        if missing:
            raise ValueError(
                f"Record {index + 1} is missing required fields: "
                f"{missing}"
            )

        normalized_events.append({
            "event_id": str(record["event_id"]).strip(),
            "timestamp": str(record["timestamp"]).strip(),
            "user_id": str(record["user_id"]).strip(),
            "system_id": str(
                record.get("system_id") or default_system
            ).strip(),
            "event_type": str(record["event_type"]).strip().upper(),
            "resource_id": str(record["resource_id"]).strip(),
        })

    return normalized_events


def extract_json_events(data: Any) -> list[dict[str, str]]:
    """Extract and normalize events from a JSON evidence object."""

    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object.")

    records = data.get("records")

    if not isinstance(records, list):
        raise ValueError("JSON must contain a 'records' array.")

    default_system = str(
        data.get("system_id") or data.get("system") or ""
    ).strip()

    return normalize_event_records(records, default_system)


def extract_csv_events(
    records: Any,
    default_system: str = "",
) -> list[dict[str, str]]:
    """Normalize event records read from a CSV file."""

    return normalize_event_records(records, default_system)
