
from src.deletion_audit.identity.identity_resolver import (
    classify_request_intent,
    normalize_email,
    resolve_identities,
)


def test_normalize_email():
    assert normalize_email(" JOHN@Example.com ") == "john@example.com"


def test_unique_identity_match():
    requests = [
        {"case_id": "case_101", "email": "john@example.com"}
    ]
    identities = [
        {"user_id": "u101", "email": "john@example.com"}
    ]

    result = resolve_identities(requests, identities)

    assert result[0]["status"] == "MATCHED"
    assert result[0]["matched_user_id"] == "u101"


def test_unmatched_identity():
    requests = [
        {"case_id": "case_102", "email": "unknown@example.com"}
    ]
    identities = [
        {"user_id": "u101", "email": "john@example.com"}
    ]

    result = resolve_identities(requests, identities)

    assert result[0]["status"] == "UNMATCHED"
    assert result[0]["matched_user_id"] is None


def test_ambiguous_identity():
    requests = [
        {"case_id": "case_103", "email": "john@example.com"}
    ]
    identities = [
        {"user_id": "u101", "email": "john@example.com"},
        {"user_id": "u999", "email": "john@example.com"},
    ]

    result = resolve_identities(requests, identities)

    assert result[0]["status"] == "AMBIGUOUS"
    assert result[0]["matched_user_id"] is None
    assert result[0]["candidate_user_ids"] == ["u101", "u999"]


def test_normalize_email_handles_empty_and_missing_values():
    assert normalize_email("") == ""
    assert normalize_email("   ") == ""
    assert normalize_email(None) == ""


def test_email_matching_is_case_insensitive():
    requests = [
        {"case_id": "case_104", "email": "JOHN@EXAMPLE.COM"}
    ]
    identities = [
        {"user_id": "u101", "email": "john@example.com"}
    ]

    result = resolve_identities(requests, identities)

    assert result[0]["status"] == "MATCHED"
    assert result[0]["matched_user_id"] == "u101"


def test_duplicate_identity_records_are_not_silently_ambiguous():
    requests = [
        {"case_id": "case_105", "email": "john@example.com"}
    ]
    identities = [
        {"user_id": "u101", "email": "john@example.com"},
        {"user_id": "u101", "email": "john@example.com"},
    ]

    result = resolve_identities(requests, identities)

    # Duplicate records for the same user should not create two distinct candidates.
    assert result[0]["status"] == "MATCHED"
    assert result[0]["matched_user_id"] == "u101"


def test_preserves_request_metadata_and_flags_invalid_chronology():
    result = resolve_identities(
        [{
            "case_id": "case_106",
            "email": " JOHN@example.com ",
            "requested_at": "2026-07-20T00:00:00Z",
            "reported_status": "COMPLETE",
            "reported_at": "2026-07-19T00:00:00Z",
            "audit_at": "2026-07-21T00:00:00Z",
            "request_text": "Solicito a exclusão.",
        }],
        [{"user_id": "u101", "email": "john@example.com"}],
    )[0]

    assert result["status"] == "MATCHED"
    assert result["request_metadata"]["reported_status"] == "COMPLETE"
    assert result["request_metadata"]["request_text"] == "Solicito a exclusão."
    assert result["request_data_quality_findings"][0]["code"] == "REPORTED_BEFORE_REQUEST"


def test_classifies_obvious_non_deletion_and_multilingual_requests():
    assert classify_request_intent(
        "I still need the account and am not asking for deletion."
    )[0] == "NOT_DELETION"
    assert classify_request_intent(
        "Solicito a exclusão permanente da conta."
    )[0] == "DELETION_REQUEST"
    assert classify_request_intent("Unclear request")[0] == "UNKNOWN"
