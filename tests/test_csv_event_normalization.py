
import pytest

from src.deletion_audit.ingestion.event_normalizer import (
    extract_csv_events,
)


def test_normalizes_valid_csv_events():
    records = [{
        "event_id": " evt201 ",
        "timestamp": "2026-10-20T12:00:00Z",
        "user_id": "u101",
        "event_type": "delete",
        "resource_id": "rec201",
    }]

    events = extract_csv_events(records, "CRM")

    assert events == [{
        "event_id": "evt201",
        "timestamp": "2026-10-20T12:00:00Z",
        "user_id": "u101",
        "system_id": "CRM",
        "event_type": "DELETE",
        "resource_id": "rec201",
    }]


def test_rejects_csv_event_missing_required_field():
    records = [{
        "event_id": "evt201",
        "timestamp": "2026-10-20T12:00:00Z",
        "user_id": "u101",
        "event_type": "DELETE",
    }]

    with pytest.raises(ValueError, match="resource_id"):
        extract_csv_events(records)


def test_rejects_non_list_csv_records():
    with pytest.raises(ValueError, match="must be a list"):
        extract_csv_events({"event_id": "evt201"})
