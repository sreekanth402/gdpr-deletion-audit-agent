
from datetime import datetime


def _issue(code: str, message: str, resource_id=None) -> dict:
    """Build a consistent validation issue."""
    result = {
        "code": code,
        "message": message,
    }

    if resource_id is not None:
        result["resource_id"] = resource_id

    return result


def _parse_timestamp(value):
    """Parse an ISO timestamp, returning None when invalid."""
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        timestamp = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return None

        return timestamp
    except (ValueError, TypeError):
        return None


def validate_final_summary(report: dict) -> list[dict]:
    """Validate the structure and internal consistency of a final audit report."""
    issues = []

    if not isinstance(report, dict):
        return [
            _issue(
                "INVALID_REPORT",
                "The final report must be a dictionary.",
            )
        ]

    required_fields = [
        "report_type",
        "summary",
        "resource_count",
        "investigation_reports_available",
        "resources",
        "integrity_findings",
        "event_id_conflicts",
        "limitations",
        "decision_authority",
    ]

    for field in required_fields:
        if field not in report:
            issues.append(
                _issue(
                    "MISSING_REQUIRED_FIELD",
                    f"Required report field '{field}' is missing.",
                )
            )

    if report.get("report_type") != "FINAL_GDPR_DELETION_AUDIT_SUMMARY":
        issues.append(
            _issue(
                "INVALID_REPORT_TYPE",
                "Unexpected final report type.",
            )
        )

    resources = report.get("resources")
    summary = report.get("summary")

    if not isinstance(resources, list):
        issues.append(
            _issue("INVALID_RESOURCES", "'resources' must be a list.")
        )
        return issues

    if not isinstance(summary, dict):
        issues.append(
            _issue("INVALID_SUMMARY", "'summary' must be a dictionary.")
        )
        return issues

    expected_status_counts = {
        "REVIEW_REQUIRED": "review_required",
        "POLICY_REVIEW": "policy_review",
        "VERIFICATION_REQUIRED": "verification_required",
        "VERIFIED_DELETED": "verified_deleted",
    }

    actual_counts = {
        "resources_evaluated": len(resources),
        "review_required": 0,
        "policy_review": 0,
        "verification_required": 0,
        "verified_deleted": 0,
    }

    seen_resource_ids = set()
    actual_investigations_available = 0

    for resource in resources:
        if not isinstance(resource, dict):
            issues.append(
                _issue(
                    "INVALID_RESOURCE",
                    "Each resource entry must be a dictionary.",
                )
            )
            continue

        resource_id = resource.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            issues.append(
                _issue(
                    "MISSING_RESOURCE_ID",
                    "A resource is missing its resource ID.",
                )
            )
        elif resource_id in seen_resource_ids:
            issues.append(
                _issue(
                    "DUPLICATE_RESOURCE_ID",
                    "The same resource ID appears more than once.",
                    resource_id,
                )
            )
        else:
            seen_resource_ids.add(resource_id)

        audit = resource.get("deterministic_audit")
        if not isinstance(audit, dict):
            issues.append(
                _issue(
                    "MISSING_DETERMINISTIC_AUDIT",
                    "Resource is missing its deterministic audit result.",
                    resource_id,
                )
            )
            continue

        status = audit.get("audit_status")
        if status in expected_status_counts:
            actual_counts[expected_status_counts[status]] += 1

        if audit.get("resource_id") != resource_id:
            issues.append(
                _issue(
                    "RESOURCE_ID_MISMATCH",
                    "Resource ID differs between the summary and audit result.",
                    resource_id,
                )
            )

        delete_evidence = audit.get("delete_evidence")
        verification_evidence = audit.get(
            "absence_verification_evidence"
        )

        if not isinstance(verification_evidence, list):
            verification_evidence = []

        if status == "VERIFIED_DELETED":
            if not isinstance(delete_evidence, dict):
                issues.append(
                    _issue(
                        "MISSING_DELETE_EVIDENCE",
                        "Verified deletion has no deletion evidence.",
                        resource_id,
                    )
                )
            else:
                delete_timestamp = _parse_timestamp(
                    delete_evidence.get("timestamp")
                )

                if delete_evidence.get("event_type") != "DELETE":
                    issues.append(
                        _issue(
                            "INVALID_DELETE_EVIDENCE",
                            "Deletion evidence must describe a DELETE event.",
                            resource_id,
                        )
                    )

                if not delete_evidence.get("event_id"):
                    issues.append(
                        _issue(
                            "MISSING_DELETE_EVENT_ID",
                            "Deletion evidence is missing its event ID.",
                            resource_id,
                        )
                    )

                if delete_timestamp is None:
                    issues.append(
                        _issue(
                            "INVALID_DELETE_TIMESTAMP",
                            "Deletion evidence has an invalid timestamp.",
                            resource_id,
                        )
                    )

            if not verification_evidence:
                issues.append(
                    _issue(
                        "MISSING_ABSENCE_VERIFICATION",
                        "Verified deletion requires absence-verification evidence.",
                        resource_id,
                    )
                )

            for evidence in verification_evidence:
                if not isinstance(evidence, dict):
                    issues.append(
                        _issue(
                            "INVALID_ABSENCE_VERIFICATION",
                            "Absence-verification evidence must be a dictionary.",
                            resource_id,
                        )
                    )
                    continue

                if evidence.get("event_type") != "VERIFY_ABSENT":
                    issues.append(
                        _issue(
                            "INVALID_ABSENCE_VERIFICATION",
                            "Evidence must describe a VERIFY_ABSENT event.",
                            resource_id,
                        )
                    )
                    continue

                verification_timestamp = _parse_timestamp(
                    evidence.get("timestamp")
                )

                if verification_timestamp is None:
                    issues.append(
                        _issue(
                            "INVALID_ABSENCE_VERIFICATION",
                            "Verification timestamp is invalid or timezone-naive.",
                            resource_id,
                        )
                    )
                    continue

                if isinstance(delete_evidence, dict):
                    delete_timestamp = _parse_timestamp(
                        delete_evidence.get("timestamp")
                    )

                    if (
                        delete_timestamp is not None
                        and verification_timestamp <= delete_timestamp
                    ):
                        issues.append(
                            _issue(
                                "INVALID_ABSENCE_VERIFICATION",
                                "Absence verification must occur after deletion.",
                                resource_id,
                            )
                        )

            declared_ids = audit.get("absence_verification_event_ids", [])
            actual_ids = [
                evidence.get("event_id")
                for evidence in verification_evidence
                if isinstance(evidence, dict)
            ]

            if declared_ids != actual_ids:
                issues.append(
                    _issue(
                        "VERIFICATION_EVENT_ID_MISMATCH",
                        "Verification event IDs do not match the evidence records.",
                        resource_id,
                    )
                )

        ai = resource.get("ai_investigation")
        if not isinstance(ai, dict):
            issues.append(
                _issue(
                    "MISSING_AI_INVESTIGATION",
                    "Resource is missing its AI investigation section.",
                    resource_id,
                )
            )

        elif ai.get("available") is True:
            actual_investigations_available += 1
            if ai.get("status") == "NOT_RUN":
                issues.append(
                    _issue(
                        "AI_AVAILABILITY_MISMATCH",
                        "AI is marked available but its status is NOT_RUN.",
                        resource_id,
                    )
                )

        elif ai.get("available") is False:
            if ai.get("status") == "INVESTIGATION_COMPLETE":
                issues.append(
                    _issue(
                        "AI_AVAILABILITY_MISMATCH",
                        "AI is marked unavailable but its status is complete.",
                        resource_id,
                    )
                )

    for field, actual_value in actual_counts.items():
        declared_value = summary.get(field)

        if declared_value != actual_value:
            issues.append(
                _issue(
                    "SUMMARY_COUNT_MISMATCH",
                    f"Summary field '{field}' is {declared_value!r}, "
                    f"but the actual count is {actual_value}.",
                )
            )

    if report.get("resource_count") != len(resources):
        issues.append(
            _issue(
                "SUMMARY_COUNT_MISMATCH",
                "'resource_count' does not match the resources list.",
            )
        )

    if (
        report.get("investigation_reports_available")
        != actual_investigations_available
    ):
        issues.append(
            _issue(
                "SUMMARY_COUNT_MISMATCH",
                "'investigation_reports_available' does not match "
                "the number of available investigations.",
            )
        )

    return issues
