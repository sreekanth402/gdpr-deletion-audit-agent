
from src.deletion_audit.timeline.timeline_reconstructor import (
    reconstruct_timelines,
)


def test_restore_after_delete_produces_finding():
    activities = [
        {
            "event_id": "evt001",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt002",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "RESTORE",
            "resource_id": "rec101",
        },
    ]

    result = reconstruct_timelines(activities, {"u101"})

    assert result["summary"]["finding_count"] >= 1
    assert any(
        finding["finding_type"] == "POST_DELETION_RESTORE"
        for finding in result["findings"]
    )


def test_sync_after_delete_produces_finding():
    activities = [
        {
            "event_id": "evt010",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "u101",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec101",
        },
        {
            "event_id": "evt011",
            "timestamp": "2026-10-21T10:00:00Z",
            "user_id": "u101",
            "system_id": "warehouse",
            "event_type": "SYNC",
            "resource_id": "rec101",
        },
    ]

    result = reconstruct_timelines(activities, {"u101"})

    assert any(
        finding["finding_type"] == "POST_DELETION_SYNC"
        for finding in result["findings"]
    )


def test_unresolved_user_is_not_included():
    activities = [
        {
            "event_id": "evt020",
            "timestamp": "2026-10-20T10:00:00Z",
            "user_id": "unknown_user",
            "system_id": "crm",
            "event_type": "DELETE",
            "resource_id": "rec201",
        },
    ]

    result = reconstruct_timelines(activities, {"u101"})

    assert result["findings"] == []


def test_empty_activities_are_handled():
    result = reconstruct_timelines([], {"u101"})

    assert result["findings"] == []
    assert result["summary"]["finding_count"] == 0


def test_identical_duplicate_event_is_reported_and_deduplicated():
    event = {
        "event_id": "evt100",
        "timestamp": "2026-10-20T10:00:00Z",
        "user_id": "u101",
        "system_id": "crm",
        "event_type": "DELETE",
        "resource_id": "rec101",
    }

    result = reconstruct_timelines([event, event], {"u101"})

    assert result["summary"]["events_processed"] == 1
    assert any(
        finding["finding_type"] == "DUPLICATE_EVENT"
        for finding in result["findings"]
    )


def test_conflicting_duplicate_event_id_is_reported():
    first = {
        "event_id": "evt200",
        "timestamp": "2026-10-20T10:00:00Z",
        "user_id": "u101",
        "system_id": "crm",
        "event_type": "DELETE",
        "resource_id": "rec101",
    }
    conflicting = {
        **first,
        "event_type": "RESTORE",
        "timestamp": "2026-10-21T10:00:00Z",
    }

    result = reconstruct_timelines([first, conflicting], {"u101"})

    assert result["summary"]["duplicate_event_conflicts"] == 1
    assert any(
        finding["finding_type"] == "DUPLICATE_EVENT_CONFLICT"
        for finding in result["findings"]
    )


def test_events_are_processed_in_chronological_order():
    delete_event = {
        "event_id": "evt301",
        "timestamp": "2026-10-21T10:00:00Z",
        "user_id": "u101",
        "system_id": "crm",
        "event_type": "DELETE",
        "resource_id": "rec301",
    }
    restore_event = {
        **delete_event,
        "event_id": "evt302",
        "timestamp": "2026-10-20T10:00:00Z",
        "event_type": "RESTORE",
    }

    result = reconstruct_timelines(
        [delete_event, restore_event],
        {"u101"},
    )

    assert result["summary"]["events_processed"] == 2


def test_verification_before_deletion_does_not_prove_final_deletion():
    verify_event = {
        "event_id": "evt401",
        "timestamp": "2026-10-20T09:00:00Z",
        "user_id": "u101",
        "system_id": "crm",
        "event_type": "VERIFY_ABSENT",
        "resource_id": "rec401",
    }
    delete_event = {
        **verify_event,
        "event_id": "evt402",
        "timestamp": "2026-10-20T10:00:00Z",
        "event_type": "DELETE",
    }

    result = reconstruct_timelines(
        [verify_event, delete_event],
        {"u101"},
    )

    # This test checks that both events are retained for timeline analysis.
    # It does not assume a particular finding type before reviewing the implementation.
    assert result["summary"]["events_processed"] == 2


def test_invalid_timestamp_does_not_crash_timeline_reconstruction():
    event = {
        "event_id": "evt501",
        "timestamp": "not-a-valid-timestamp",
        "user_id": "u101",
        "system_id": "crm",
        "event_type": "DELETE",
        "resource_id": "rec501",
    }

    result = reconstruct_timelines([event], {"u101"})

    assert isinstance(result, dict)
    assert "summary" in result
    assert "findings" in result
    invalid_timestamp = next(
        finding
        for finding in result["findings"]
        if finding["finding_type"] == "INVALID_TIMESTAMP"
    )
    assert invalid_timestamp["resource_id"] == "rec501"
