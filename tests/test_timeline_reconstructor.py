
from src.deletion_audit.timeline.timeline_reconstructor import (
    reconstruct_timelines,
)


def test_detects_restore_after_deletion():
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

    report = reconstruct_timelines(activities, {"u101"})

    assert report["summary"]["finding_count"] == 1
    assert report["findings"][0]["finding_type"] == "POST_DELETION_RESTORE"


def test_duplicate_event_ids_are_deduplicated():
    from src.deletion_audit.main import deduplicate_events

    event = {
        "event_id": "evt001",
        "timestamp": "2026-10-20T10:00:00Z",
        "user_id": "u101",
        "system_id": "crm",
        "event_type": "DELETE",
        "resource_id": "rec101",
    }

    unique, conflicts = deduplicate_events([event, event.copy()])

    assert len(unique) == 1
    assert conflicts == []


def test_conflicting_event_ids_are_reported():
    from src.deletion_audit.main import deduplicate_events

    first = {
        "event_id": "evt001",
        "event_type": "DELETE",
        "resource_id": "rec101",
    }
    second = {
        "event_id": "evt001",
        "event_type": "RESTORE",
        "resource_id": "rec101",
    }

    unique, conflicts = deduplicate_events([first, second])

    assert len(unique) == 1
    assert len(conflicts) == 1
    assert conflicts[0]["event_id"] == "evt001"


def test_missing_event_id_is_flagged():
    from src.deletion_audit.timeline.timeline_reconstructor import (
        reconstruct_timelines,
    )

    activities = [
        {
            "event_id": "",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        }
    ]

    report = reconstruct_timelines(activities, {"u101"})

    assert any(
        finding["finding_type"] == "INVALID_EVENT_ID"
        for finding in report["findings"]
    )


def test_invalid_timestamp_is_flagged():
    from src.deletion_audit.timeline.timeline_reconstructor import (
        reconstruct_timelines,
    )

    activities = [
        {
            "event_id": "evt-invalid",
            "timestamp": "not-a-timestamp",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        }
    ]

    report = reconstruct_timelines(activities, {"u101"})

    assert any(
        finding["finding_type"] == "INVALID_TIMESTAMP"
        for finding in report["findings"]
    )


def test_naive_timestamp_is_flagged():
    from src.deletion_audit.timeline.timeline_reconstructor import (
        reconstruct_timelines,
    )

    activities = [
        {
            "event_id": "evt-naive",
            "timestamp": "2026-10-20T10:00:00",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        }
    ]

    report = reconstruct_timelines(activities, {"u101"})

    assert any(
        finding["finding_type"] == "INVALID_TIMESTAMP"
        for finding in report["findings"]
    )


def test_events_are_sorted_chronologically():
    from src.deletion_audit.timeline.timeline_reconstructor import (
        reconstruct_timelines,
    )

    activities = [
        {
            "event_id": "evt-later",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-earlier",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})
    events = report["timelines"]["u101"]

    assert [
        event["event_id"] for event in events
    ] == ["evt-earlier", "evt-later"]

    assert any(
        finding["finding_type"] == "POST_DELETION_RESTORE"
        for finding in report["findings"]
    )

def test_restore_before_delete_does_not_produce_post_deletion_finding():
    activities = [
        {
            "event_id": "evt-restore",
            "timestamp": "2026-10-19T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-delete",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    assert not any(
        finding["finding_type"] == "POST_DELETION_RESTORE"
        for finding in report["findings"]
    )


def test_latest_delete_is_used_for_later_risk_detection():
    activities = [
        {
            "event_id": "evt-delete-1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-restore",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-delete-2",
            "timestamp": "2026-10-22T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    restore_findings = [
        finding for finding in report["findings"]
        if finding["finding_type"] == "POST_DELETION_RESTORE"
    ]

    assert len(restore_findings) == 1
    assert restore_findings[0]["related_delete_event_id"] == "evt-delete-1"


def test_same_resource_ids_for_different_users_are_isolated():
    activities = [
        {
            "event_id": "evt-delete-u101",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec-shared",
        },
        {
            "event_id": "evt-restore-u102",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u102",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec-shared",
        },
    ]

    report = reconstruct_timelines(activities, {"u101", "u102"})

    assert not any(
        finding["finding_type"] == "POST_DELETION_RESTORE"
        for finding in report["findings"]
    )


def test_timestamp_with_different_timezone_offsets_is_ordered_correctly():
    activities = [
        {
            "event_id": "evt-restore",
            "timestamp": "2026-10-21T12:00:00+02:00",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-delete",
            "timestamp": "2026-10-21T09:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    assert any(
        finding["finding_type"] == "POST_DELETION_RESTORE"
        for finding in report["findings"]
    )

def test_same_event_id_in_different_systems_is_preserved():
    from src.deletion_audit.main import deduplicate_events

    crm_event = {
        "event_id": "evt001",
        "timestamp": "2026-10-20T10:00:00Z",
        "user_id": "u101",
        "system_id": "crm",
        "event_type": "DELETE",
        "resource_id": "rec101",
    }

    warehouse_event = {
        "event_id": "evt001",
        "timestamp": "2026-10-20T10:05:00Z",
        "user_id": "u101",
        "system_id": "warehouse",
        "event_type": "SYNC",
        "resource_id": "rec101",
    }

    unique, conflicts = deduplicate_events(
        [crm_event, warehouse_event]
    )

    assert len(unique) == 2
    assert conflicts == []

def test_restore_after_delete_is_reported():
    activities = [
        {
            "event_id": "delete-1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "restore-1",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities)

    findings = [
        finding
        for finding in report["findings"]
        if finding["finding_type"] == "POST_DELETION_RESTORE"
    ]

    assert len(findings) == 1
    assert findings[0]["event_id"] == "restore-1"
    assert findings[0]["related_delete_event_id"] == "delete-1"


def test_sync_after_delete_is_reported():
    activities = [
        {
            "event_id": "delete-1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "sync-1",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "warehouse",
            "event_type": "SYNC",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities)

    findings = [
        finding
        for finding in report["findings"]
        if finding["finding_type"] == "POST_DELETION_SYNC"
    ]

    assert len(findings) == 1
    assert findings[0]["event_id"] == "sync-1"
    assert findings[0]["related_delete_event_id"] == "delete-1"

def test_restore_for_one_resource_does_not_flag_another_resource():
    activities = [
        {
            "event_id": "evt-delete-101",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-delete-102",
            "timestamp": "2026-10-20T10:30:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec102",
        },
        {
            "event_id": "evt-restore-101",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    restore_findings = [
        finding
        for finding in report["findings"]
        if finding["finding_type"] == "POST_DELETION_RESTORE"
    ]

    assert len(restore_findings) == 1
    assert restore_findings[0]["resource_id"] == "rec101"
    assert (
        restore_findings[0]["related_delete_event_id"]
        == "evt-delete-101"
    )


def test_restore_references_latest_prior_delete():
    activities = [
        {
            "event_id": "evt-delete-1",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-delete-2",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-restore",
            "timestamp": "2026-10-22T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    restore_findings = [
        finding
        for finding in report["findings"]
        if finding["finding_type"] == "POST_DELETION_RESTORE"
    ]

    assert len(restore_findings) == 1
    assert (
        restore_findings[0]["related_delete_event_id"]
        == "evt-delete-2"
    )


def test_conflicting_event_id_is_reported_and_both_records_are_preserved():
    activities = [
        {
            "event_id": "evt-shared",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-shared",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    conflicts = [
        finding
        for finding in report["findings"]
        if finding["finding_type"] == "DUPLICATE_EVENT_CONFLICT"
    ]

    assert len(conflicts) == 1
    assert len(report["timelines"]["u101"]) == 2
    assert report["summary"]["duplicate_event_conflicts"] == 1


def test_system_id_matching_is_case_insensitive_for_delete_and_restore():
    activities = [
        {
            "event_id": "evt-delete",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "CRM",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt-restore",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    report = reconstruct_timelines(activities, {"u101"})

    restore_findings = [
        finding
        for finding in report["findings"]
        if finding["finding_type"] == "POST_DELETION_RESTORE"
    ]

    assert len(restore_findings) == 1
    assert restore_findings[0]["related_delete_event_id"] == "evt-delete"
    assert restore_findings[0]["related_delete_system_id"] == "CRM"
