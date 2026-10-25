
import csv

from src.deletion_audit.reporting.identity_csv_export import (
    build_identity_csv_rows,
    export_identity_csv,
)


def test_build_identity_rows_preserves_resolution_statuses():
    report = {
        "results": [
            {
                "case_id": "case_101",
                "email": "john@example.com",
                "status": "MATCHED",
                "matched_user_id": "u101",
                "candidate_user_ids": ["u101"],
                "reason": "Exactly one identity matched.",
            },
            {
                "case_id": "case_102",
                "email": "unknown@example.com",
                "status": "UNMATCHED",
                "matched_user_id": None,
                "candidate_user_ids": [],
                "reason": "No identity record matches this email.",
            },
        ]
    }

    rows = build_identity_csv_rows(report)

    assert len(rows) == 2
    assert rows[0]["status"] == "MATCHED"
    assert rows[1]["status"] == "UNMATCHED"
    assert rows[1]["matched_user_id"] == ""


def test_export_identity_csv_writes_readable_rows(tmp_path):
    source = tmp_path / "identity.json"
    output = tmp_path / "identity.csv"

    source.write_text(
        '{"results":[{"case_id":"case_101",'
        '"email":"john@example.com","status":"MATCHED",'
        '"matched_user_id":"u101","candidate_user_ids":["u101"],'
        '"reason":"Exactly one identity matched."}]}',
        encoding="utf-8",
    )

    result = export_identity_csv(source, output)

    assert result.is_file()

    with result.open(
        encoding="utf-8-sig", newline=""
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["case_id"] == "case_101"
    assert rows[0]["status"] == "MATCHED"
    assert rows[0]["matched_user_id"] == "u101"
