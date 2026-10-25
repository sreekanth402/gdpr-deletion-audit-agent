import pytest

from src.deletion_audit.ingestion.event_normalizer import (
    extract_json_events,
)


def test_normalizes_valid_json_events():
    data = {
        "system": "CRM",
        "records": [
            {
                "event_id": "evt101",
                "timestamp": "2026-10-20T12:00:00Z",
                "user_id": "u101",
                "event_type": "delete",
                "resource_id": "rec103",
            }
        ],
    }

    events = extract_json_events(data)

    assert len(events) == 1
    assert events[0]["system_id"] == "CRM"
    assert events[0]["event_type"] == "DELETE"
    assert events[0]["resource_id"] == "rec103"


def test_rejects_missing_required_fields():
    data = {
        "records": [
            {
                "event_id": "evt101",
                "user_id": "u101",
                "event_type": "DELETE",
                "resource_id": "rec103",
            }
        ]
    }

    with pytest.raises(ValueError, match="missing required fields"):
        extract_json_events(data)


def test_rejects_non_object_record():
    data = {"records": ["not-an-event"]}

    with pytest.raises(ValueError, match="must be an object"):
        extract_json_events(data)


def test_rejects_missing_records_array():
    data = {"system": "CRM"}

    with pytest.raises(ValueError, match="records"):
        extract_json_events(data)


def test_rejects_non_object_root():
    with pytest.raises(ValueError, match="root must be an object"):
        extract_json_events([])


def test_uses_system_id_as_default():
    data = {
        "system_id": "CRM_PROD",
        "records": [
            {
                "event_id": "evt102",
                "timestamp": "2026-10-20T12:00:00Z",
                "user_id": "u102",
                "event_type": "delete",
                "resource_id": "rec104",
            }
        ],
    }

    events = extract_json_events(data)

    assert events[0]["system_id"] == "CRM_PROD"


def test_record_system_id_overrides_default():
    data = {
        "system": "CRM",
        "records": [
            {
                "event_id": "evt103",
                "timestamp": "2026-10-20T12:00:00Z",
                "user_id": "u103",
                "system_id": "CRM_ARCHIVE",
                "event_type": "delete",
                "resource_id": "rec105",
            }
        ],
    }

    events = extract_json_events(data)

    assert events[0]["system_id"] == "CRM_ARCHIVE"


def test_rejects_invalid_record_without_silently_skipping_it():
    data = {
        "records": [
            {
                "event_id": "evt104",
                "timestamp": "2026-10-20T12:00:00Z",
                "user_id": "u104",
                "event_type": "delete",
                "resource_id": "rec106",
            },
            {
                "event_id": "evt105",
                "timestamp": "2026-10-20T12:01:00Z",
                "user_id": "u105",
                "event_type": "delete",
            },
        ]
    }

    with pytest.raises(ValueError, match="missing required fields"):
        extract_json_events(data)
