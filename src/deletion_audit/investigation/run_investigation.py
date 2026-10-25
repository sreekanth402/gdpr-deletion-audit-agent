import sys
from google.genai import errors

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.deletion_audit.investigation.evidence_context import (
    build_evidence_context,
)
from src.deletion_audit.investigation.investigator import (
    investigate_resource,
)



PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = PROJECT_ROOT / "reports"



def load_json_report(filename: str) -> dict:
    """Load one existing JSON report."""
    path = REPORTS_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Required report not found: {path}. "
            "Run the regular audit pipeline first."
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an AI investigation for one audited resource."
    )
    parser.add_argument(
        "--resource",
        required=True,
        help="Resource ID to investigate, for example rec101.",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")

    timeline_report = load_json_report(
        "timeline_reconstruction_report.json"
    )
    unified_audit_report = load_json_report(
        "unified_audit_report.json"
    )

    evidence_context = build_evidence_context(
        resource_id=args.resource,
        timeline_report=timeline_report,
        unified_audit_report=unified_audit_report,
    )

    try:
        investigation = investigate_resource(evidence_context)
    except errors.APIError as exc:
        status_code = getattr(exc, "code", None)

        if status_code == 503:
            print(
                "\nGemini is temporarily unavailable (503). "
                "Please wait a few minutes and try again.",
                file=sys.stderr,
            )
        elif status_code == 429:
            print(
                "\nGemini API quota or rate limit reached (429). "
                "Check your API quota and retry later.",
                file=sys.stderr,
            )
        else:
            print(
                f"\nGemini API request failed: {exc}",
                file=sys.stderr,
            )

        sys.exit(1)

    output_path = REPORTS_DIR / (
        f"ai_investigation_{args.resource}.json"
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            investigation.model_dump(mode="json"),
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("\nAI investigation completed.")
    print(f"Resource: {args.resource}")
    print(f"Status: {investigation.investigation_status}")
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
