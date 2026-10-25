
from collections import defaultdict
from datetime import datetime, timezone
import re
from typing import Any


def normalize_email(email: Any) -> str:
    """Normalize an email for consistent matching."""
    if not isinstance(email, str):
        return ""

    return email.strip().casefold()


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse a timezone-aware ISO timestamp into UTC."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def classify_request_intent(value: Any) -> tuple[str, str]:
    """Conservatively flag obvious non-deletion requests and known phrases."""
    text = str(value or "").strip().casefold()
    if not text:
        return "UNKNOWN", "Request text is empty."

    non_deletion_patterns = (
        r"\bnot asking for deletion\b",
        r"\bdo not (?:delete|close|remove)\b",
        r"\bdon't (?:delete|close|remove)\b",
        r"\bstill need the account\b",
        r"\b(?:correct|update|replace) (?:my |the )?(?:profile|surname|mobile|phone|address)\b",
        r"\bstop (?:the )?(?:promotional )?emails\b",
        r"\bdownload my account information\b",
        r"\breset(?:ting)? the login\b",
    )
    if any(re.search(pattern, text) for pattern in non_deletion_patterns):
        return "NOT_DELETION", "Text indicates another request type or explicitly rejects deletion."

    deletion_patterns = (
        r"\bdelet(?:e|ion|ed|ing)\b", r"\beras(?:e|ed|ure)\b",
        r"\bremov(?:e|al)\b", r"\bclose (?:my |the )?account\b",
        r"\bsuppression\b", r"\bexclus(?:\u00e3|a)o\b",
        r"\beliminaci(?:\u00f3|o)n\b", r"\bsuppression d\u00e9finitive\b",
        r"\bl\u00f6sch(?:en|ung)\b", r"\u524a\u9664",
        r"\uc0ad\uc81c",
    )
    if any(re.search(pattern, text) for pattern in deletion_patterns):
        return "DELETION_REQUEST", "Text contains a recognized deletion phrase; human review may still be needed."
    return "UNKNOWN", "Could not confidently classify request text."


def resolve_identities(
    deletion_requests: list[dict[str, Any]],
    user_identities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Match deletion requests to internal user identities.

    Possible statuses:
    MATCHED, UNMATCHED, AMBIGUOUS
    """

    identities_by_email = defaultdict(set)

    # Build an email-to-user-ID lookup.
    for identity in user_identities:
        email = normalize_email(identity.get("email"))
        user_id = str(identity.get("user_id", "")).strip()

        if email and user_id:
            identities_by_email[email].add(user_id)

    results = []

    # Resolve each deletion request.
    for request in deletion_requests:
        case_id = str(request.get("case_id", "")).strip()
        email = normalize_email(request.get("email"))

        result = {
            "case_id": case_id,
            "email": email,
            "matched_user_id": None,
            "candidate_user_ids": [],
            "status": "UNMATCHED",
            "reason": "",
            # Preserve source fields (including request status, dates, and
            # multilingual request text) for downstream audit/reporting.
            "request_metadata": {
                key: value for key, value in request.items()
                if key not in {"case_id", "email"}
            },
            "request_data_quality_findings": [],
        }

        requested_at = _parse_timestamp(request.get("requested_at"))
        reported_at = _parse_timestamp(request.get("reported_at"))
        audit_at = _parse_timestamp(request.get("audit_at"))
        quality_findings = result["request_data_quality_findings"]
        intent, intent_reason = classify_request_intent(
            request.get("request_text")
        )
        result["request_intent"] = intent
        result["request_intent_reason"] = intent_reason
        if intent != "DELETION_REQUEST":
            quality_findings.append({
                "code": "REQUEST_INTENT_REVIEW",
                "field": "request_text",
                "intent": intent,
                "message": intent_reason,
            })
        reported_status = str(
            request.get("reported_status", "") or ""
        ).strip().upper()
        if reported_status and reported_status not in {
            "COMPLETE", "PARTIALLY_COMPLETE", "NOT_STARTED"
        }:
            quality_findings.append({
                "code": "UNKNOWN_REPORTED_STATUS",
                "field": "reported_status",
                "value": request.get("reported_status"),
                "message": "Reported status is outside the recognized dataset values.",
            })
        for field in ("requested_at", "reported_at", "audit_at"):
            raw_value = request.get(field)
            if raw_value and _parse_timestamp(raw_value) is None:
                quality_findings.append({
                    "code": "INVALID_REQUEST_TIMESTAMP",
                    "field": field,
                    "value": raw_value,
                    "message": "Timestamp must be valid ISO 8601 with a timezone.",
                })
        if requested_at and reported_at and reported_at < requested_at:
            quality_findings.append({
                "code": "REPORTED_BEFORE_REQUEST",
                "field": "reported_at",
                "message": "Reported date precedes the request date.",
            })
        if requested_at and audit_at and audit_at < requested_at:
            quality_findings.append({
                "code": "AUDIT_BEFORE_REQUEST",
                "field": "audit_at",
                "message": "Audit date precedes the request date.",
            })
        if reported_at and audit_at and audit_at < reported_at:
            quality_findings.append({
                "code": "AUDIT_BEFORE_REPORTED_DATE",
                "field": "audit_at",
                "message": "Audit date precedes the reported completion date.",
            })

        if not case_id:
            result["reason"] = "Missing case ID."

        elif not email:
            result["reason"] = "Missing or invalid email value."

        else:
            candidates = sorted(identities_by_email.get(email, set()))
            result["candidate_user_ids"] = candidates

            if len(candidates) == 1:
                result["matched_user_id"] = candidates[0]
                result["status"] = "MATCHED"
                result["reason"] = "Exactly one identity matched."

            elif len(candidates) > 1:
                result["status"] = "AMBIGUOUS"
                result["reason"] = (
                    "Multiple user IDs share this email. "
                    "Manual review is required."
                )

            else:
                result["reason"] = (
                    "No identity record matches this email."
                )

        results.append(result)

    return results
