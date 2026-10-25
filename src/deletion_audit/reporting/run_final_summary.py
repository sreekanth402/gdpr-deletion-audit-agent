
import json
from pathlib import Path

from src.deletion_audit.reporting.final_summary import (
    build_final_summary,
    write_final_summary,
)
from src.deletion_audit.audit.report_validator import (
    validate_final_summary,
)

def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Required report not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def main() -> None:
    reports_dir = Path("reports")

    unified_audit = load_json(
        reports_dir / "unified_audit_report.json"
    )

    investigation_files = sorted(
        reports_dir.glob("ai_investigation_*.json")
    )

    investigations = [
        load_json(path) for path in investigation_files
    ]

    summary = build_final_summary(
        unified_audit=unified_audit,
        investigations=investigations,
    )
    issues = validate_final_summary(summary)

    if issues:
        print("Final report validation FAILED:")

        for issue in issues:
            print(
                f"[{issue.get('severity', 'ERROR')}] "
                f"{issue.get('code', 'VALIDATION_ERROR')}: "
                f"{issue.get('message', str(issue))}"
            )
        raise SystemExit(1)

    print("Final report validation PASSED.")

    output_path = write_final_summary(
        summary,
        reports_dir / "final_gdpr_deletion_audit_summary.json",
    )

    print("Final GDPR deletion audit summary created.")
    print(f"Output: {output_path}")
    print(f"Resources: {summary['resource_count']}")
    print(
        "AI investigation reports included: "
        f"{summary['investigation_reports_available']}"
    )


if __name__ == "__main__":
    main()
