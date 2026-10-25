
import json
from pathlib import Path
from typing import Any


def _request_status_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    """Count source-reported statuses without treating them as audit results."""
    counts: dict[str, int] = {}
    for item in results:
        metadata = item.get("request_metadata", {})
        status = str(metadata.get("reported_status", "") or "").strip().upper()
        if status:
            counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _request_intent_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in results:
        intent = str(item.get("request_intent", "UNKNOWN") or "UNKNOWN")
        counts[intent] = counts.get(intent, 0) + 1
    return dict(sorted(counts.items()))


def build_final_summary(
    unified_audit: dict[str, Any],
    investigations: list[dict[str, Any]],
    identity_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine deterministic audit results with optional AI investigations."""
    if identity_resolution is None:
        identity_resolution = {}

    if not isinstance(identity_resolution, dict):
        raise ValueError("Identity resolution report must be a dictionary.")

    identity_results = identity_resolution.get("results", [])

    if not isinstance(identity_results, list):
        raise ValueError("Identity resolution results must be a list.")

    identity_summary = identity_resolution.get("summary", {})

    if not isinstance(identity_summary, dict):
        raise ValueError("Identity resolution summary must be a dictionary.")

    results = unified_audit.get("results", [])

    if not isinstance(results, list):
        raise ValueError("Unified audit 'results' must be a list.")

    investigation_by_resource: dict[str, dict[str, Any]] = {}

    for report in investigations:
        resource_id = str(report.get("resource_id", "")).strip()

        if not resource_id:
            raise ValueError(
                "Every investigation report must contain a resource_id."
            )

        if resource_id in investigation_by_resource:
            raise ValueError(
                f"Duplicate investigation report for resource: {resource_id}"
            )

        investigation_by_resource[resource_id] = report

    summary_resources = []

    for result in results:
        resource_id = str(result.get("resource_id", "")).strip()

        if not resource_id:
            raise ValueError(
                "Every unified audit result must contain a resource_id."
            )

        investigation = investigation_by_resource.get(resource_id)

        if investigation is None:
            ai_investigation = {
                "available": False,
                "status": "NOT_RUN",
                "summary": None,
                "evidence_gaps": [],
                "recommended_checks": [],
                "limitations": [],
            }
        else:
            ai_investigation = {
                "available": True,
                "status": investigation.get(
                    "investigation_status", "UNKNOWN"
                ),
                "summary": investigation.get("summary"),
                "evidence_gaps": investigation.get("evidence_gaps", []),
                "recommended_checks": investigation.get(
                    "recommended_checks", []
                ),
                "limitations": investigation.get("limitations", []),
            }

        summary_resources.append(
            {
                "resource_id": resource_id,
                "deterministic_audit": result,
                "ai_investigation": ai_investigation,
            }
        )

    return {
        "report_type": "FINAL_GDPR_DELETION_AUDIT_SUMMARY",
        "summary": unified_audit.get("summary", {}),
        "identity_resolution": {
            "total_requests": identity_resolution.get(
                "total_requests", len(identity_results)
            ),
            "summary": identity_summary,
            "results": identity_results,
            "request_status_summary": _request_status_summary(identity_results),
            "request_intent_summary": _request_intent_summary(identity_results),
            "request_data_quality_findings": [
                {
                    "case_id": item.get("case_id"),
                    **finding,
                }
                for item in identity_results
                for finding in item.get("request_data_quality_findings", [])
            ],
        },
        "resource_count": len(summary_resources),
        "investigation_reports_available": sum(
            1
            for resource in summary_resources
            if resource["ai_investigation"]["available"]
        ),
        "resources": summary_resources,
        "integrity_findings": unified_audit.get(
            "integrity_findings", []
        ),
        "event_id_conflicts": unified_audit.get("event_id_conflicts", []),
        "limitations": unified_audit.get("limitations", []),
        "decision_authority": (
            "Deterministic audit results remain authoritative. "
            "AI output provides explanations and recommendations only."
        ),
    }


def write_final_summary(
    summary: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Write the final summary as formatted JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
