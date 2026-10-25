
import csv
import json
from pathlib import Path
from typing import Any


CSV_COLUMNS = [
    "case_id",
    "email",
    "status",
    "matched_user_id",
    "candidate_user_ids",
    "reason",
    "reported_status",
    "requested_at",
    "reported_at",
    "audit_at",
    "request_text",
    "request_intent",
    "request_intent_reason",
    "request_data_quality_findings",
]


def build_identity_csv_rows(
    identity_report: dict[str, Any],
) -> list[dict[str, str]]:
    results = identity_report.get("results", [])

    if not isinstance(results, list):
        raise ValueError("Identity results must be a list.")

    rows = []
    seen_case_ids = set()

    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Each identity result must be a dictionary.")

        case_id = str(result.get("case_id", "")).strip()

        if not case_id:
            raise ValueError("Every identity result must contain a case_id.")

        if case_id in seen_case_ids:
            raise ValueError(f"Duplicate case_id: {case_id}")

        seen_case_ids.add(case_id)

        candidates = result.get("candidate_user_ids", [])

        if not isinstance(candidates, list):
            raise ValueError(
                f"candidate_user_ids must be a list for case {case_id}."
            )

        rows.append({
            "case_id": case_id,
            "email": str(result.get("email") or ""),
            "status": str(result.get("status") or "UNMATCHED"),
            "matched_user_id": str(
                result.get("matched_user_id") or ""
            ),
            "candidate_user_ids": json.dumps(
                candidates, ensure_ascii=False
            ),
            "reason": str(result.get("reason") or ""),
            "reported_status": str(result.get("request_metadata", {}).get("reported_status") or ""),
            "requested_at": str(result.get("request_metadata", {}).get("requested_at") or ""),
            "reported_at": str(result.get("request_metadata", {}).get("reported_at") or ""),
            "audit_at": str(result.get("request_metadata", {}).get("audit_at") or ""),
            "request_text": str(result.get("request_metadata", {}).get("request_text") or ""),
            "request_intent": str(result.get("request_intent") or "UNKNOWN"),
            "request_intent_reason": str(result.get("request_intent_reason") or ""),
            "request_data_quality_findings": json.dumps(
                result.get("request_data_quality_findings", []),
                ensure_ascii=False,
            ),
        })

    return rows


def export_identity_csv(
    identity_report_path: str | Path,
    output_path: str | Path,
) -> Path:
    source = Path(identity_report_path)
    report = json.loads(source.read_text(encoding="utf-8"))

    if not isinstance(report, dict):
        raise ValueError("Identity report must be a JSON object.")

    rows = build_identity_csv_rows(report)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=CSV_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)

    return destination
