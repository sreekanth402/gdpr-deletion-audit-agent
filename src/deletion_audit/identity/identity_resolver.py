
from collections import defaultdict
from typing import Any


def normalize_email(email: Any) -> str:
    """Normalize an email for consistent matching."""
    if not isinstance(email, str):
        return ""

    return email.strip().casefold()


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
        }

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
