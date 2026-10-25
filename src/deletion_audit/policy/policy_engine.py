
from typing import Any


ALLOWED_ACTIONS = {"DELETE", "RETAIN", "ANONYMIZE"}


def normalize_value(value: Any) -> str:
    """Normalize a policy value for reliable comparisons."""
    return str(value or "").strip()


def load_deletion_rules(
    rules: list[dict[str, Any]],
) -> dict[str, str]:
    """Validate and index deletion rules by data type."""
    indexed_rules: dict[str, str] = {}

    for row_number, row in enumerate(rules, start=2):
        data_type = normalize_value(row.get("data_type"))
        action = normalize_value(row.get("action")).upper()

        if not data_type:
            raise ValueError(
                f"Missing data_type in deletion rules row {row_number}."
            )

        if action not in ALLOWED_ACTIONS:
            raise ValueError(
                f"Invalid action '{action}' in deletion rules row "
                f"{row_number}. Allowed actions: {sorted(ALLOWED_ACTIONS)}"
            )

        normalized_key = data_type.casefold()

        if normalized_key in indexed_rules:
            raise ValueError(
                f"Duplicate data_type '{data_type}' in deletion rules."
            )

        indexed_rules[normalized_key] = action

    return indexed_rules


def evaluate_policy(
    data_types: list[str],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply configured deletion rules to supplied data types."""
    indexed_rules = load_deletion_rules(rules)
    decisions = []

    for value in data_types:
        data_type = normalize_value(value)
        action = indexed_rules.get(data_type.casefold())

        if not data_type:
            decisions.append({
                "data_type": data_type,
                "status": "INVALID_INPUT",
                "action": None,
                "reason": "Data type is missing.",
            })
        elif action is None:
            decisions.append({
                "data_type": data_type,
                "status": "REVIEW_REQUIRED",
                "action": None,
                "reason": "No matching deletion rule was found.",
            })
        else:
            decisions.append({
                "data_type": data_type,
                "status": "RULE_MATCHED",
                "action": action,
                "reason": f"Action '{action}' was selected from deletion_rules.csv.",
            })

    return {
        "decisions": decisions,
        "summary": {
            "total": len(decisions),
            "rule_matched": sum(
                item["status"] == "RULE_MATCHED" for item in decisions
            ),
            "review_required": sum(
                item["status"] == "REVIEW_REQUIRED" for item in decisions
            ),
            "invalid_input": sum(
                item["status"] == "INVALID_INPUT" for item in decisions
            ),
        },
    }
