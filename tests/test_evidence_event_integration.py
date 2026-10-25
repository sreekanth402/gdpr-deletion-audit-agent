
from src.deletion_audit.main import extract_evidence_events


def test_extracts_valid_event_csv():
    evidence = [{
        "file": "data/evidence/crm_events.csv",
        "format": ".csv",
        "status": "OK",
        "content": [{
            "event_id": "evt201",
            "timestamp": "2026-10-20T12:00:00Z",
            "user_id": "u101",
            "event_type": "delete",
            "resource_id": "rec201",
        }],
        "errors": [],
    }]

    events, errors = extract_evidence_events(evidence)

    assert len(events) == 1
    assert events[0]["event_type"] == "DELETE"
    assert events[0]["system_id"] == "CRM_EVENTS"
    assert errors == []


def test_ignores_non_event_csv():
    evidence = [{
        "file": "data/evidence/users.csv",
        "format": ".csv",
        "status": "OK",
        "content": [{
            "user_id": "u101",
            "email": "john@example.com",
        }],
        "errors": [],
    }]

    events, errors = extract_evidence_events(evidence)

    assert events == []
    assert errors == []


def test_ignores_non_csv_evidence():
    evidence = [{
        "file": "data/evidence/notes.txt",
        "format": ".txt",
        "status": "OK",
        "content": "Deletion completed.",
        "errors": [],
    }]

    events, errors = extract_evidence_events(evidence)

    assert events == []
    assert errors == []
