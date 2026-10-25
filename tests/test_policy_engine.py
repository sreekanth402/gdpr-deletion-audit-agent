
import pytest

from src.deletion_audit.policy.policy_engine import (
    evaluate_policy,
    load_deletion_rules,
)


@pytest.fixture
def rules():
    return [
        {"data_type": "Customer Profile", "action": "DELETE"},
        {"data_type": "Financial Record", "action": "RETAIN"},
        {"data_type": "Logs", "action": "ANONYMIZE"},
    ]


def test_matches_configured_actions(rules):
    report = evaluate_policy(
        ["Customer Profile", "Financial Record", "Logs"],
        rules,
    )

    assert [
        item["action"] for item in report["decisions"]
    ] == ["DELETE", "RETAIN", "ANONYMIZE"]

    assert report["summary"]["rule_matched"] == 3


def test_unknown_data_type_requires_review(rules):
    report = evaluate_policy(["Unknown Data"], rules)

    assert report["decisions"][0]["status"] == "REVIEW_REQUIRED"
    assert report["decisions"][0]["action"] is None


def test_rule_lookup_is_case_insensitive(rules):
    report = evaluate_policy(["customer profile"], rules)

    assert report["decisions"][0]["action"] == "DELETE"


def test_invalid_action_is_rejected():
    with pytest.raises(ValueError, match="Invalid action"):
        load_deletion_rules([
            {"data_type": "Customer Profile", "action": "IGNORE"}
        ])


def test_duplicate_data_type_is_rejected():
    with pytest.raises(ValueError, match="Duplicate data_type"):
        load_deletion_rules([
            {"data_type": "Logs", "action": "DELETE"},
            {"data_type": "logs", "action": "ANONYMIZE"},
        ])


def test_missing_data_type_is_rejected():
    with pytest.raises(ValueError, match="Missing data_type"):
        load_deletion_rules([
            {"data_type": "", "action": "DELETE"}
        ])
