
import csv
import json
from pathlib import Path
from typing import Any


CSV_COLUMNS = [
    "resource_id",
    "data_type",
    "policy_action",
    "policy_status",
    "audit_status",
    "delete_event_id",
    "absence_verification_event_ids",
    "timeline_findings",
    "verification_statuses_by_user",
    "recommended_action",
    "ai_investigation_available",
    "ai_investigation_status",
    "ai_investigation_summary",
    "ai_evidence_gaps",
    "ai_recommended_checks",
]


def _json_cell(value: Any) -> str:
    """Serialize nested values consistently for a CSV cell."""
    return json.dumps(
        value if value is not None else [],
        ensure_ascii=False,
        sort_keys=True,
    )


def build_csv_rows(
    final_summary: dict[str, Any],
) -> list[dict[str, str]]:
    """Flatten the final summary into one row per audited resource."""
    resources = final_summary.get("resources", [])

    if not isinstance(resources, list):
        raise ValueError("Final summary resources must be a list.")

    rows = []
    seen_resource_ids = set()

    for item in resources:
        if not isinstance(item, dict):
            raise ValueError("Each resource entry must be an object.")

        audit = item.get("deterministic_audit", {})
        investigation = item.get("ai_investigation", {})

        if not isinstance(audit, dict) or not isinstance(
            investigation, dict
        ):
            raise ValueError(
                "Resource audit and investigation values must be objects."
            )

        resource_id = str(audit.get("resource_id", "")).strip()

        if not resource_id:
            raise ValueError("Every resource must have a resource_id.")

        if resource_id in seen_resource_ids:
            raise ValueError(
                f"Duplicate resource in final summary: {resource_id}"
            )

        seen_resource_ids.add(resource_id)

        rows.append({
            "resource_id": resource_id,
            "data_type": str(audit.get("data_type") or ""),
            "policy_action": str(audit.get("policy_action") or ""),
            "policy_status": str(audit.get("policy_status") or ""),
            "audit_status": str(audit.get("audit_status") or ""),
            "delete_event_id": str(audit.get("delete_event_id") or ""),
            "absence_verification_event_ids": _json_cell(
                audit.get("absence_verification_event_ids", [])
            ),
            "timeline_findings": _json_cell(
                audit.get("timeline_findings", [])
            ),
            "verification_statuses_by_user": _json_cell(
                audit.get("verification_statuses_by_user", {})
            ),
            "recommended_action": str(
                audit.get("recommended_action") or ""
            ),
            "ai_investigation_available": str(
                bool(investigation.get("available", False))
            ).lower(),
            "ai_investigation_status": str(
                investigation.get("status") or "NOT_RUN"
            ),
            "ai_investigation_summary": str(
                investigation.get("summary") or ""
            ),
            "ai_evidence_gaps": _json_cell(
                investigation.get("evidence_gaps", [])
            ),
            "ai_recommended_checks": _json_cell(
                investigation.get("recommended_checks", [])
            ),
        })

    return rows


def export_final_summary_csv(
    summary_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Export a final JSON audit summary to a stable CSV schema."""
    summary_path = Path(summary_path)
    output_path = Path(output_path)

    with summary_path.open("r", encoding="utf-8") as file:
        summary = json.load(file)

    if not isinstance(summary, dict):
        raise ValueError("Final summary must be a JSON object.")

    rows = build_csv_rows(summary)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=CSV_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)

    return output_path
