import json

from src.deletion_audit.audit.report_validator import validate_final_summary
from src.deletion_audit.identity.identity_resolver import resolve_identities
from src.deletion_audit.ingestion.csv_reader import read_csv_file
from src.deletion_audit.reporting.final_summary import build_final_summary
from src.deletion_audit.reporting.identity_csv_export import (
    build_identity_csv_rows,
)


def test_richer_request_dataset_flows_through_identity_and_summary(tmp_path):
    source = tmp_path / "deletion_requests.csv"
    source.write_text(
        "case_id,email,requested_at,reported_status,reported_at,audit_at,request_text\n"
        'case_1,PERSON@example.com,2026-07-01T00:00:00Z,COMPLETE,2026-07-02T00:00:00Z,2026-07-03T00:00:00Z,"Please delete my account."\n'
        'case_2,person@example.com,2026-07-04T00:00:00Z,NOT_STARTED,2026-07-05T00:00:00Z,2026-07-06T00:00:00Z,"I still need the account and am not asking for deletion."\n'
        'case_3,unknown@example.com,2026-07-04T00:00:00Z,PARTIALLY_COMPLETE,2026-07-05T00:00:00Z,2026-07-06T00:00:00Z,"Solicito a exclusão permanente da conta."\n',
        encoding="utf-8",
    )

    parsed = read_csv_file(source, {"case_id", "email"})
    assert parsed["valid"] is True
    assert len(parsed["records"]) == 3

    resolved = resolve_identities(
        parsed["records"],
        [{"user_id": "u1", "email": "person@example.com"}],
    )
    assert [row["status"] for row in resolved] == [
        "MATCHED", "MATCHED", "UNMATCHED"
    ]
    assert [row["request_intent"] for row in resolved] == [
        "DELETION_REQUEST", "NOT_DELETION", "DELETION_REQUEST"
    ]

    identity_report = {"total_requests": len(resolved), "results": resolved}
    exported = build_identity_csv_rows(identity_report)
    assert exported[1]["reported_status"] == "NOT_STARTED"
    assert json.loads(exported[1]["request_data_quality_findings"])[0]["code"] == "REQUEST_INTENT_REVIEW"

    final = build_final_summary(
        {"summary": {
            "resources_evaluated": 0,
            "review_required": 0,
            "policy_review": 0,
            "verification_required": 0,
            "verified_deleted": 0,
        }, "results": []},
        [],
        identity_resolution=identity_report,
    )
    assert final["identity_resolution"]["request_status_summary"] == {
        "COMPLETE": 1,
        "NOT_STARTED": 1,
        "PARTIALLY_COMPLETE": 1,
    }
    assert final["identity_resolution"]["request_intent_summary"] == {
        "DELETION_REQUEST": 2,
        "NOT_DELETION": 1,
    }
    assert validate_final_summary(final) == []
