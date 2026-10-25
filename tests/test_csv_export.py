
import csv
import json

import pytest

from src.deletion_audit.reporting.csv_export import (
    CSV_COLUMNS,
    build_csv_rows,
    export_final_summary_csv,
)


def sample_summary():
    return {
        "resources": [
            {
                "deterministic_audit": {
                    "resource_id": "rec101",
                    "data_type": "Customer Profile",
                    "policy_action": "DELETE",
                    "policy_status": "RULE_MATCHED",
                    "audit_status": "REVIEW_REQUIRED",
                    "delete_event_id": "evt001",
                    "absence_verification_event_ids": [],
                    "timeline_findings": [
                        {
                            "finding_type": "POST_DELETION_RESTORE",
                            "event_id": "evt002",
                        }
                    ],
                    "verification_statuses_by_user": {
                        "u101": "REVIEW_REQUIRED"
                    },
                    "recommended_action": "Investigate restore",
                },
                "ai_investigation": {
                    "available": True,
                    "status": "COMPLETED",
                    "summary": "Review restore event",
                    "evidence_gaps": ["Current state"],
                    "recommended_checks": ["Check storage"],
                },
            },
            {
                "deterministic_audit": {
                    "resource_id": "rec102",
                    "data_type": "Logs",
                    "policy_action": "ANONYMIZE",
                    "policy_status": "RULE_MATCHED",
                    "audit_status": "POLICY_REVIEW",
                    "delete_event_id": None,
                    "absence_verification_event_ids": [],
                    "timeline_findings": [],
                    "verification_statuses_by_user": {},
                    "recommended_action": "Apply configured policy",
                },
                "ai_investigation": {
                    "available": False,
                    "status": "NOT_RUN",
                    "summary": None,
                    "evidence_gaps": [],
                    "recommended_checks": [],
                },
            },
        ]
    }


def test_build_csv_rows_preserves_resource_statuses():
    rows = build_csv_rows(sample_summary())

    assert len(rows) == 2
    assert rows[0]["resource_id"] == "rec101"
    assert rows[0]["audit_status"] == "REVIEW_REQUIRED"
    assert rows[0]["ai_investigation_status"] == "COMPLETED"
    assert rows[1]["audit_status"] == "POLICY_REVIEW"
    assert rows[1]["ai_investigation_status"] == "NOT_RUN"


def test_nested_findings_remain_readable_json():
    rows = build_csv_rows(sample_summary())

    findings = json.loads(rows[0]["timeline_findings"])

    assert findings[0]["event_id"] == "evt002"


def test_export_writes_stable_headers_and_rows(tmp_path):
    source = tmp_path / "summary.json"
    output = tmp_path / "nested" / "results.csv"

    source.write_text(
        json.dumps(sample_summary()),
        encoding="utf-8",
    )

    returned_path = export_final_summary_csv(source, output)

    assert returned_path == output
    assert output.exists()

    with output.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert reader.fieldnames == CSV_COLUMNS
    assert len(rows) == 2
    assert rows[0]["resource_id"] == "rec101"
    assert rows[0]["audit_status"] == "REVIEW_REQUIRED"


def test_duplicate_resource_ids_are_rejected():
    summary = sample_summary()
    summary["resources"].append(summary["resources"][0])

    with pytest.raises(ValueError, match="Duplicate resource"):
        build_csv_rows(summary)


def test_invalid_resources_shape_is_rejected():
    with pytest.raises(ValueError, match="must be a list"):
        build_csv_rows({"resources": {}})
