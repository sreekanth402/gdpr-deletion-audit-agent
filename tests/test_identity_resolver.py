
from src.deletion_audit.identity.identity_resolver import (
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
