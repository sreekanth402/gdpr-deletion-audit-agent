
from src.deletion_audit.verification.deletion_verifier import (
    verify_deletions,
)


def test_verified_when_delete_has_later_absence_confirmation():
    activities = [
        {
            "event_id": "evt1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt2",
            "timestamp": "2026-10-20T10:30:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "VERIFY_ABSENT",
            "resource_id": "rec101",
        },
    ]

    report = verify_deletions(activities, {"u101"})

    assert report["summary"]["verified"] == 1
    assert report["results"][0]["status"] == "VERIFIED"


def test_review_required_when_resource_is_restored():
    activities = [
        {
            "event_id": "evt1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt2",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    report = verify_deletions(activities, {"u101"})

    assert report["summary"]["review_required"] == 1
    assert report["results"][0]["status"] == "REVIEW_REQUIRED"


def test_inconclusive_when_no_delete_event_exists():
    activities = [
        {
            "event_id": "evt1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "EXPORT",
            "resource_id": "rec101",
        },
    ]

    report = verify_deletions(activities, {"u101"})

    assert report["summary"]["inconclusive"] == 1
    assert report["results"][0]["status"] == "INCONCLUSIVE"


def test_unresolved_user_activity_is_ignored():
    activities = [
        {
            "event_id": "evt1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u999",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec999",
        },
    ]

    report = verify_deletions(activities, {"u101"})

    assert report["summary"]["inconclusive"] == 1
    assert report["results"][0]["status"] == "INCONCLUSIVE"


def test_absence_confirmation_before_delete_is_not_sufficient():
    activities = [
        {
            "event_id": "evt10",
            "timestamp": "2026-10-20T09:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "VERIFY_ABSENT",
            "resource_id": "rec110",
        },
        {
            "event_id": "evt11",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec110",
        },
    ]

    report = verify_deletions(activities, {"u101"})

    assert report["summary"]["verified"] == 0
    assert report["results"][0]["status"] != "VERIFIED"


def test_sync_after_delete_prevents_unqualified_verification():
    activities = [
        {
            "event_id": "evt20",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec120",
        },
        {
            "event_id": "evt21",
            "timestamp": "2026-10-20T10:30:00Z",
            "user_id": "u101",
            "system_id": "warehouse",
            "event_type": "SYNC",
            "resource_id": "rec120",
        },
        {
            "event_id": "evt22",
            "timestamp": "2026-10-20T11:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "VERIFY_ABSENT",
            "resource_id": "rec120",
        },
    ]

    report = verify_deletions(activities, {"u101"})

    assert report["summary"]["verified"] == 0
    assert report["results"][0]["status"] != "VERIFIED"


def test_empty_activities_are_handled():
    report = verify_deletions([], {"u101"})

    assert report["summary"]["verified"] == 0
    assert report["summary"]["inconclusive"] == 1
    assert report["summary"]["users_evaluated"] == 1
    assert len(report["results"]) == 1
    assert report["results"][0]["user_id"] == "u101"
    assert report["results"][0]["status"] == "INCONCLUSIVE"
