
from datetime import datetime
from typing import Any


VALID_AUDIT_STATUSES = {
    "REVIEW_REQUIRED",
    "VERIFIED_DELETED",
    "VERIFICATION_REQUIRED",
    "POLICY_REVIEW",
}

VALID_AI_STATUSES = {
    "NOT_RUN",
    "NEEDS_MORE_EVIDENCE",
    "INVESTIGATION_COMPLETE",
}


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp, including a trailing Z."""
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        # Normalize naive timestamps to UTC for consistent comparison.
        if parsed.tzinfo is None:
            from datetime import timezone
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed
    except ValueError:
        return None


def validate_final_summary(
    report: dict[str, Any],
) -> list[dict[str, str]]:
    """
    Return validation issues without modifying the report.

    Each issue contains a severity, code, and message.
    """
    issues: list[dict[str, str]] = []

    def add_issue(
        code: str,
        message: str,
        severity: str = "ERROR",
    ) -> None:
        issues.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
            }
        )

    if not isinstance(report, dict):
        return [
            {
                "severity": "ERROR",
                "code": "INVALID_REPORT",
                "message": "The final report must be a JSON object.",
            }
        ]

    if report.get("report_type") != "FINAL_GDPR_DELETION_AUDIT_SUMMARY":
        add_issue(
            "INVALID_REPORT_TYPE",
            "Missing or invalid final report type.",
        )

    resources = report.get("resources")

    if not isinstance(resources, list):
        add_issue(
            "INVALID_RESOURCES",
            "The resources field must be a list.",
        )
        return issues

    seen_resource_ids: set[str] = set()
    observed_counts = {
        "resources_evaluated": len(resources),
        "review_required": 0,
        "policy_review": 0,
        "verification_required": 0,
        "verified_deleted": 0,
    }

    for index, item in enumerate(resources):
        prefix = f"resources[{index}]"

        if not isinstance(item, dict):
            add_issue(
                "INVALID_RESOURCE",
                f"{prefix} must be an object.",
            )
            continue

        resource_id = item.get("resource_id")

        if not isinstance(resource_id, str) or not resource_id.strip():
            add_issue(
                "MISSING_RESOURCE_ID",
                f"{prefix} has no valid resource_id.",
            )
            continue

        resource_id = resource_id.strip()

        if resource_id in seen_resource_ids:
            add_issue(
                "DUPLICATE_RESOURCE_ID",
                f"Resource {resource_id} appears more than once.",
            )
        seen_resource_ids.add(resource_id)

        audit = item.get("deterministic_audit")
        ai = item.get("ai_investigation")

        if not isinstance(audit, dict):
            add_issue(
                "MISSING_DETERMINISTIC_AUDIT",
                f"{resource_id} has no deterministic audit object.",
            )
            continue

        audit_status = audit.get("audit_status")

        if audit_status not in VALID_AUDIT_STATUSES:
            add_issue(
                "INVALID_AUDIT_STATUS",
                f"{resource_id} has unknown audit status: {audit_status!r}.",
            )
            continue

        status_key = audit_status.lower()
        if status_key in observed_counts:
            observed_counts[status_key] += 1

        if audit_status == "VERIFIED_DELETED":
            delete_evidence = audit.get("delete_evidence")
            absence_evidence = audit.get("absence_verification_evidence", [])

            if not isinstance(delete_evidence, dict):
                add_issue(
                    "MISSING_DELETE_EVIDENCE",
                    f"{resource_id} is VERIFIED_DELETED but has no delete evidence.",
                )
            else:
                delete_timestamp = _parse_timestamp(
                    delete_evidence.get("timestamp")
                )

                if not delete_evidence.get("event_id"):
                    add_issue(
                        "MISSING_DELETE_EVENT_ID",
                        f"{resource_id} has no delete event ID.",
                    )

                if delete_timestamp is None:
                    add_issue(
                        "INVALID_DELETE_TIMESTAMP",
                        f"{resource_id} has an invalid delete timestamp.",
                    )

            if not isinstance(absence_evidence, list) or not absence_evidence:
                add_issue(
                    "MISSING_ABSENCE_VERIFICATION",
                    f"{resource_id} is VERIFIED_DELETED but has no absence-verification evidence.",
                )
            elif isinstance(delete_evidence, dict):
                delete_timestamp = _parse_timestamp(
                    delete_evidence.get("timestamp")
                )

                valid_later_verification = False

                for event in absence_evidence:
                    if not isinstance(event, dict):
                        continue

                    if event.get("event_type") != "VERIFY_ABSENT":
                        continue

                    verification_timestamp = _parse_timestamp(
                        event.get("timestamp")
                    )

                    if (
                        delete_timestamp is not None
                        and verification_timestamp is not None
                        and verification_timestamp > delete_timestamp
                    ):
                        valid_later_verification = True
                        break

                if not valid_later_verification:
                    add_issue(
                        "INVALID_ABSENCE_VERIFICATION",
                        f"{resource_id} has no valid VERIFY_ABSENT event after deletion.",
                    )

        if audit_status in {
            "REVIEW_REQUIRED",
            "VERIFICATION_REQUIRED",
            "POLICY_REVIEW",
        }:
            action = audit.get("recommended_action")

            if not isinstance(action, str) or not action.strip():
                add_issue(
                    "MISSING_FOLLOW_UP_ACTION",
                    f"{resource_id} requires follow-up but has no recommended action.",
                    severity="WARNING",
                )

        if not isinstance(ai, dict):
            add_issue(
                "MISSING_AI_SECTION",
                f"{resource_id} has no AI investigation section.",
            )
            continue

        ai_available = ai.get("available")
        ai_status = ai.get("status")

        if not isinstance(ai_available, bool):
            add_issue(
                "INVALID_AI_AVAILABILITY",
                f"{resource_id} has an invalid AI availability flag.",
            )

        if ai_status not in VALID_AI_STATUSES:
            add_issue(
                "INVALID_AI_STATUS",
                f"{resource_id} has unknown AI status: {ai_status!r}.",
            )

        if ai_available is False and ai_status != "NOT_RUN":
            add_issue(
                "AI_AVAILABILITY_MISMATCH",
                f"{resource_id} says AI is unavailable but status is {ai_status!r}.",
            )

        if ai_available is True and ai_status == "NOT_RUN":
            add_issue(
                "AI_AVAILABILITY_MISMATCH",
                f"{resource_id} says AI is available but status is NOT_RUN.",
            )

    summary = report.get("summary")

    if not isinstance(summary, dict):
        add_issue(
            "MISSING_SUMMARY",
            "The final report summary must be an object.",
        )
    else:
        for key, actual in observed_counts.items():
            expected = summary.get(key)

            if expected != actual:
                add_issue(
                    "SUMMARY_COUNT_MISMATCH",
                    f"Summary {key} is {expected!r}, but resource results count is {actual}.",
                )

    if report.get("resource_count") != len(resources):
        add_issue(
            "RESOURCE_COUNT_MISMATCH",
            "resource_count does not match the number of resource entries.",
        )

    actual_ai_count = sum(
        1
        for item in resources
        if isinstance(item, dict)
        and isinstance(item.get("ai_investigation"), dict)
        and item["ai_investigation"].get("available") is True
    )

    if report.get("investigation_reports_available") != actual_ai_count:
        add_issue(
            "AI_REPORT_COUNT_MISMATCH",
            "investigation_reports_available does not match the available AI sections.",
        )

    if not report.get("decision_authority"):
        add_issue(
            "MISSING_DECISION_AUTHORITY",
            "The report must explain that deterministic audit results remain authoritative.",
            severity="WARNING",
        )

    return issues
