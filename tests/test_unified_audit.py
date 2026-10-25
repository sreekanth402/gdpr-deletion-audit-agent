
from src.deletion_audit.audit.unified_audit import build_unified_audit


def make_reports():
    resource_mappings = [
        {"resource_id": "rec101", "data_type": "Customer Profile"},
        {"resource_id": "rec102", "data_type": "Customer Profile"},
        {"resource_id": "exp101", "data_type": "Customer Profile"},
    ]

    policy_report = {
        "decisions": [
            {
                "data_type": "Customer Profile",
                "action": "DELETE",
                "status": "RULE_MATCHED",
            }
        ]
    }

    timeline_report = {
        "timelines": {
            "u101": [
                {
                    "event_id": "evt001",
                    "timestamp": "2026-10-20T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "event_type": "DELETE",
                    "resource_id": "rec101",
                },
                {
                    "event_id": "evt002",
                    "timestamp": "2026-10-21T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "event_type": "RESTORE",
                    "resource_id": "rec101",
                },
            ],
            "u102": [
                {
                    "event_id": "evt003",
                    "timestamp": "2026-10-20T11:00:00+00:00",
                    "user_id": "u102",
                    "system_id": "crm",
                    "event_type": "DELETE",
                    "resource_id": "rec102",
                },
                {
                    "event_id": "evt004",
                    "timestamp": "2026-10-20T11:30:00+00:00",
                    "user_id": "u102",
                    "system_id": "crm",
                    "event_type": "VERIFY_ABSENT",
                    "resource_id": "rec102",
                },
            ],
        },
        "findings": [
            {
                "finding_type": "POST_DELETION_RESTORE",
                "severity": "HIGH",
                "event_id": "evt002",
                "user_id": "u101",
                "resource_id": "rec101",
            }
        ],
    }

    verification_report = {
        "results": [
            {"user_id": "u101", "status": "REVIEW_REQUIRED"},
            {"user_id": "u102", "status": "VERIFIED"},
        ]
    }

    return (
        resource_mappings,
        policy_report,
        timeline_report,
        verification_report,
    )


def test_restore_after_deletion_requires_review():
    inputs = make_reports()

    report = build_unified_audit(*inputs)

    result = next(
        item for item in report["results"]
        if item["resource_id"] == "rec101"
    )

    assert result["audit_status"] == "REVIEW_REQUIRED"
    assert result["delete_event_id"] == "evt001"


def test_absence_verification_after_deletion_is_recorded():
    inputs = make_reports()

    report = build_unified_audit(*inputs)

    result = next(
        item for item in report["results"]
        if item["resource_id"] == "rec102"
    )

    assert result["audit_status"] == "VERIFIED_DELETED"
    assert result["absence_verification_event_ids"] == ["evt004"]


def test_invalid_timestamp_prevents_verified_deletion_claim():
    inputs = make_reports()
    inputs[2]["findings"].append({
        "finding_type": "INVALID_TIMESTAMP",
        "severity": "MEDIUM",
        "event_id": "evt-invalid",
        "user_id": "u102",
        "resource_id": "rec102",
    })

    report = build_unified_audit(*inputs)

    result = next(
        item for item in report["results"]
        if item["resource_id"] == "rec102"
    )

    assert result["audit_status"] == "VERIFICATION_REQUIRED"
    assert any(
        finding["finding_type"] == "INVALID_TIMESTAMP"
        for finding in result["timeline_findings"]
    )


def test_resource_without_delete_event_needs_verification():
    inputs = make_reports()

    report = build_unified_audit(*inputs)

    result = next(
        item for item in report["results"]
        if item["resource_id"] == "exp101"
    )

    assert result["audit_status"] == "VERIFICATION_REQUIRED"


def test_summary_counts_match_results():
    inputs = make_reports()

    report = build_unified_audit(*inputs)

    assert report["summary"]["resources_evaluated"] == 3
    assert report["summary"]["review_required"] == 1
    assert report["summary"]["verified_deleted"] == 1
    assert report["summary"]["verification_required"] == 1


def test_duplicate_resource_mapping_is_rejected():
    resource_mappings, policy, timeline, verification = make_reports()

    resource_mappings.append({
        "resource_id": "rec101",
        "data_type": "Customer Profile",
    })

    try:
        build_unified_audit(
            resource_mappings,
            policy,
            timeline,
            verification,
        )
    except ValueError as error:
        assert "Duplicate resource_id" in str(error)
    else:
        raise AssertionError("Expected duplicate mapping to be rejected")

def test_unified_audit_preserves_timeline_integrity_findings():
    from src.deletion_audit.audit.unified_audit import build_unified_audit

    timeline_report = {
        "timelines": {},
        "findings": [
            {
                "finding_type": "INVALID_TIMESTAMP",
                "severity": "MEDIUM",
                "event_id": "evt-bad",
                "description": "Invalid timestamp.",
            }
        ],
        "event_id_conflicts": [
            {
                "event_id": "evt-conflict",
                "description": "Conflicting event records.",
            }
        ],
    }

    report = build_unified_audit(
        resource_mappings=[],
        policy_report={"decisions": []},
        timeline_report=timeline_report,
        verification_report={"results": []},
    )

    assert len(report["integrity_findings"]) == 1
    assert (
        report["integrity_findings"][0]["finding_type"]
        == "INVALID_TIMESTAMP"
    )
    assert report["event_id_conflicts"][0]["event_id"] == "evt-conflict"

def test_traceable_finding_includes_source_event_details():
    from src.deletion_audit.audit.unified_audit import build_unified_audit

    resource_mappings = [
        {"resource_id": "rec101", "data_type": "Customer Profile"}
    ]

    policy_report = {
        "decisions": [
            {
                "data_type": "Customer Profile",
                "action": "DELETE",
                "status": "RULE_MATCHED",
            }
        ]
    }

    timeline_report = {
        "timelines": {
            "u101": [
                {
                    "event_id": "evt001",
                    "event_type": "DELETE",
                    "timestamp": "2026-10-20T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "resource_id": "rec101",
                },
                {
                    "event_id": "evt002",
                    "event_type": "RESTORE",
                    "timestamp": "2026-10-21T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "resource_id": "rec101",
                },
            ]
        },
        "findings": [
            {
                "finding_type": "POST_DELETION_RESTORE",
                "severity": "HIGH",
                "event_id": "evt002",
                "user_id": "u101",
                "resource_id": "rec101",
                "related_delete_event_id": "evt001",
                "related_delete_system_id": "crm",
            }
        ],
        "event_id_conflicts": [],
    }

    report = build_unified_audit(
        resource_mappings=resource_mappings,
        policy_report=policy_report,
        timeline_report=timeline_report,
        verification_report={"results": []},
    )

    result = report["results"][0]
    finding = result["timeline_findings"][0]

    assert result["delete_evidence"]["event_id"] == "evt001"
    assert finding["event_id"] == "evt002"
    assert finding["timestamp"] == "2026-10-21T10:00:00+00:00"
    assert finding["system_id"] == "crm"
    assert finding["related_delete_event_id"] == "evt001"

def test_unified_audit_preserves_event_id_conflicts():
    from src.deletion_audit.audit.unified_audit import build_unified_audit

    conflicts = [
        {
            "event_id": "evt001",
            "system_id": "crm",
            "reason": "Conflicting records share the same event ID.",
        }
    ]

    timeline_report = {
        "timelines": {},
        "findings": [],
        "event_id_conflicts": conflicts,
        "summary": {
            "duplicate_event_conflicts": len(conflicts)
        },
    }

    report = build_unified_audit(
        resource_mappings=[],
        policy_report={"decisions": []},
        timeline_report=timeline_report,
        verification_report={"results": []},
    )

    assert report["event_id_conflicts"] == conflicts
    assert report["summary"]["resources_evaluated"] == 0

def test_traceability_uses_correct_event_when_ids_repeat_across_systems():
    resource_mappings = [
        {"resource_id": "rec101", "data_type": "Customer Profile"}
    ]

    policy_report = {
        "decisions": [
            {
                "data_type": "Customer Profile",
                "action": "DELETE",
                "status": "RULE_MATCHED",
            }
        ]
    }

    timeline_report = {
        "timelines": {
            "u101": [
                {
                    "event_id": "evt002",
                    "event_type": "RESTORE",
                    "timestamp": "2026-10-21T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "resource_id": "rec101",
                },
                {
                    "event_id": "evt002",
                    "event_type": "EXPORT",
                    "timestamp": "2026-10-22T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "warehouse",
                    "resource_id": "rec101",
                },
                {
                    "event_id": "evt001",
                    "event_type": "DELETE",
                    "timestamp": "2026-10-20T10:00:00+00:00",
                    "user_id": "u101",
                    "system_id": "crm",
                    "resource_id": "rec101",
                },
            ]
        },
        "findings": [
            {
                "finding_type": "POST_DELETION_RESTORE",
                "severity": "HIGH",
                "event_id": "evt002",
                "system_id": "crm",
                "user_id": "u101",
                "resource_id": "rec101",
                "related_delete_event_id": "evt001",
                "related_delete_system_id": "crm",
            }
        ],
        "event_id_conflicts": [],
    }

    report = build_unified_audit(
        resource_mappings=resource_mappings,
        policy_report=policy_report,
        timeline_report=timeline_report,
        verification_report={"results": []},
    )

    finding = report["results"][0]["timeline_findings"][0]

    assert finding["event_id"] == "evt002"
    assert finding["system_id"] == "crm"
    assert finding["timestamp"] == "2026-10-21T10:00:00+00:00"

def test_timeline_findings_are_associated_with_the_correct_resource():
    from src.deletion_audit.audit.unified_audit import build_unified_audit

    resource_mappings = [
        {"resource_id": "rec101", "user_id": "u101", "data_type": "Customer Profile"},
        {"resource_id": "rec102", "user_id": "u101", "data_type": "Customer Profile"},
    ]

    policy_report = {
        "results": [
            {"resource_id": "rec101", "action": "DELETE", "status": "RULE_MATCHED"},
            {"resource_id": "rec102", "action": "DELETE", "status": "RULE_MATCHED"},
        ]
    }

    timeline_report = {
        "findings": [
            {
                "user_id": "u101",
                "event_id": "evt-restore-101",
                "finding_type": "POST_DELETION_RESTORE",
                "severity": "HIGH",
                "resource_id": "rec101",
                "related_delete_event_id": "evt-delete-101",
                "system_id": "crm",
                "related_delete_system_id": "crm",
            }
        ]
    }

    verification_report = {"results": []}

    report = build_unified_audit(
        resource_mappings=resource_mappings,
        policy_report=policy_report,
        timeline_report=timeline_report,
        verification_report=verification_report,
    )

    results_by_resource = {
        item["resource_id"]: item for item in report["results"]
    }

    assert len(results_by_resource["rec101"]["timeline_findings"]) == 1
    assert results_by_resource["rec102"]["timeline_findings"] == []
