
from pathlib import Path
import json

from .ingestion.csv_reader import read_csv_file
from .ingestion.json_reader import read_json_file
from .ingestion.event_normalizer import (
    extract_json_events,
    extract_csv_events,
)
from .ingestion.evidence_scanner import scan_evidence
from .identity.identity_resolver import resolve_identities
from .timeline.timeline_reconstructor import reconstruct_timelines
from .verification.deletion_verifier import verify_deletions
from .policy.policy_engine import evaluate_policy
from .audit.unified_audit import build_unified_audit
from .reporting.final_summary import (
    build_final_summary,
    write_final_summary,
)
from .audit.report_validator import validate_final_summary
from .reporting.csv_export import export_final_summary_csv
from .reporting.identity_csv_export import export_identity_csv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "data" / "input"
EVIDENCE_DIR = PROJECT_ROOT / "data" / "evidence"
REPORT_DIR = PROJECT_ROOT / "reports"

INPUT_SCHEMAS = {
    "deletion_requests.csv": {"case_id", "email"},
    "user_identities.csv": {"user_id", "email"},
    "user_audit_log.csv": {"email"},
    "system_activity.csv": {
        "event_id",
        "timestamp",
        "user_id",
        "system_id",
        "event_type",
        "resource_id",
    },
    "deletion_rules.csv": {"data_type", "action"},
    "resource_mapping.csv": {"resource_id", "data_type"},
}

JSON_INPUT_FILES = [
    "sample_evidence.json",
]


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    parsed_files = {}
    ingestion_report = {
    "input_files": {},
    "json_input_files": {},
    "evidence_files": [],
    "summary": {},
}

    # Phase 2: Read and validate the input CSV files.
    for filename, required_columns in INPUT_SCHEMAS.items():
        parsed = read_csv_file(
            INPUT_DIR / filename,
            required_columns=required_columns,
        )

        parsed_files[filename] = parsed

        ingestion_report["input_files"][filename] = {
            "valid": parsed["valid"],
            "columns": parsed["columns"],
            "record_count": len(parsed["records"]),
            "errors": parsed["errors"],
        }

        status = "OK" if parsed["valid"] else "ERROR"
        print(
            f"{filename}: {status} "
            f"({len(parsed['records'])} records)"
        )

        for error in parsed["errors"]:
            print(f"  Error: {error}")

    json_events = []

    for filename in JSON_INPUT_FILES:
        parsed = read_json_file(INPUT_DIR / filename)

        if parsed["valid"]:
            try:
                events = extract_json_events(parsed["data"])
                json_events.extend(events)
                parsed["event_count"] = len(events)
            except ValueError as exc:
                parsed["valid"] = False
                parsed["errors"].append(str(exc))
                parsed["event_count"] = 0
        else:
            parsed["event_count"] = 0

    # Read and validate the JSON input files.
    parsed_json_files = {}

    for filename in JSON_INPUT_FILES:
        parsed = read_json_file(INPUT_DIR / filename)
        parsed_json_files[filename] = parsed

        data = parsed["data"]

        if isinstance(data, list):
            item_count = len(data)
        elif isinstance(data, dict) and isinstance(
            data.get("records"), list
        ):
            item_count = len(data["records"])
        elif data is not None:
            item_count = 1
        else:
            item_count = 0

        ingestion_report["json_input_files"][filename] = {
            "valid": parsed["valid"],
            "item_count": item_count,
            "errors": parsed["errors"],
        }

        status = "OK" if parsed["valid"] else "ERROR"

        print(
            f"{filename}: {status} "
            f"({item_count} items)"
        )

        for error in parsed["errors"]:
            print(f"  Error: {error}")


    # Scan evidence files.
    evidence = scan_evidence(EVIDENCE_DIR)
    evidence_events, evidence_event_errors = (
        extract_evidence_events(evidence)
    )

    ingestion_report["evidence_files"] = [
        {
            "file": item["file"],
            "format": item["format"],
            "status": item["status"],
            "errors": item["errors"],
        }
        for item in evidence
    ]
    ingestion_report["evidence_events"] = evidence_events
    ingestion_report["evidence_event_errors"] = evidence_event_errors

    ingestion_report["summary"] = {
        "input_file_count": len(INPUT_SCHEMAS),
        "valid_input_count": sum(
            item["valid"]
            for item in parsed_files.values()
        ),
        "json_input_file_count": len(JSON_INPUT_FILES),
        "valid_json_input_count": sum(
            item["valid"] for item in parsed_json_files.values()
        ),
        "evidence_file_count": len(evidence),
        "evidence_ok_count": sum(
            item["status"] == "OK" for item in evidence
        ),
        "evidence_error_count": sum(
            item["status"] == "ERROR" for item in evidence
        ),
        "unsupported_evidence_count": sum(
            item["status"] == "UNSUPPORTED"
            for item in evidence
        ),
        "evidence_event_count": len(evidence_events),
        "evidence_event_error_count": len(evidence_event_errors),
    }

    ingestion_path = REPORT_DIR / "ingestion_report.json"
    ingestion_path.write_text(
        json.dumps(ingestion_report, indent=2),
        encoding="utf-8",
    )

    print(f"\nIngestion report saved: {ingestion_path}")

    # Stop identity resolution if either required dataset is invalid.
    required_files = [
        "deletion_requests.csv",
        "user_identities.csv",
    ]

    if not all(
        parsed_files[name]["valid"]
        for name in required_files
    ):
        print(
            "\nIdentity resolution skipped: "
            "deletion requests or user identities are invalid."
        )
        return

    # Phase 3: Resolve deletion requests to internal identities.
    requests = parsed_files[
        "deletion_requests.csv"
    ]["records"]

    identities = parsed_files[
        "user_identities.csv"
    ]["records"]

    results = resolve_identities(requests, identities)

    counts = {
        status: sum(
            result["status"] == status for result in results
        )
        for status in ["MATCHED", "UNMATCHED", "AMBIGUOUS"]
    }

    identity_report = {
        "total_requests": len(results),
        "summary": counts,
        "results": results,
    }

    identity_path = REPORT_DIR / "identity_resolution_report.json"
    identity_path.write_text(
        json.dumps(identity_report, indent=2),
        encoding="utf-8",
    )

    identity_csv_path = (
        REPORT_DIR / "identity_resolution_results.csv"
    )

    export_identity_csv(
        identity_path,
        identity_csv_path,
    )

    print(f"Identity CSV saved: {identity_csv_path}")

    print("\nIdentity Resolution Summary:")
    print(json.dumps(counts, indent=2))
    print(f"Identity report saved: {identity_path}")

    for result in results:
        print(
            f"{result['case_id']}: "
            f"{result['status']} "
            f"(user_id={result['matched_user_id']})"
        )

    # Phase 4: Reconstruct activity timelines.
    matched_user_ids = {
        result["matched_user_id"]
        for result in results
        if result["status"] == "MATCHED"
        and result["matched_user_id"] is not None
    }

    activity_file = parsed_files["system_activity.csv"]

    if activity_file["valid"]:
        all_activities = (
            activity_file["records"]
            + json_events
            + evidence_events
        )

        all_activities, event_id_conflicts = deduplicate_events(
            all_activities
        )

        timeline_report = reconstruct_timelines(
            all_activities,
            matched_user_ids,
        )

        timeline_report["event_id_conflicts"] = event_id_conflicts
        timeline_report["summary"]["duplicate_event_conflicts"] = len(
            event_id_conflicts
        )

        timeline_path = (
            REPORT_DIR / "timeline_reconstruction_report.json"
        )

        timeline_path.write_text(
            json.dumps(timeline_report, indent=2),
            encoding="utf-8",
        )

        print("\nTimeline Summary:")
        print(json.dumps(timeline_report["summary"], indent=2))

        for finding in timeline_report["findings"]:
            print(
                f"{finding['severity']}: "
                f"{finding['finding_type']} "
                f"(user_id={finding['user_id']})"
            )

        print(f"Timeline report saved: {timeline_path}")

    else:
        print(
            "\nTimeline reconstruction skipped: "
            "system_activity.csv is invalid."
        )

    # Phase 5: Verify deletion evidence.
    if activity_file["valid"]:
        verification_report = verify_deletions(
            all_activities,
            matched_user_ids,
        )

        verification_path = (
            REPORT_DIR / "deletion_verification_report.json"
        )

        verification_path.write_text(
            json.dumps(verification_report, indent=2),
            encoding="utf-8",
        )

        print("\nDeletion Verification Summary:")
        print(
            json.dumps(
                verification_report["summary"],
                indent=2,
            )
        )

        for result in verification_report["results"]:
            print(
                f"{result['user_id']}: "
                f"{result['status']}"
            )

        print(
            f"Deletion verification report saved: "
            f"{verification_path}"
        )
    else:
        print(
            "\nDeletion verification skipped: "
            "system_activity.csv is invalid."
        )

    # Phase 4: Evaluate configured deletion policies.
    rules_file = parsed_files["deletion_rules.csv"]

    if rules_file["valid"]:
        rules = rules_file["records"]

        data_types = [
            row.get("data_type", "")
            for row in rules
        ]

        policy_report = evaluate_policy(
            data_types,
            rules,
        )

        policy_path = REPORT_DIR / "policy_audit_report.json"
        policy_path.write_text(
            json.dumps(policy_report, indent=2),
            encoding="utf-8",
        )

        print("\nPolicy Evaluation Summary:")
        print(json.dumps(policy_report["summary"], indent=2))

        for decision in policy_report["decisions"]:
            print(
                f"{decision['data_type']}: "
                f"{decision['status']} "
                f"(action={decision['action']})"
            )

        print(f"Policy report saved: {policy_path}")

    else:
        print(
            "\nPolicy evaluation skipped: "
            "deletion_rules.csv is invalid."
        )

    # Unified audit report: combine policy and evidence results.
    required_for_unified_report = [
        "system_activity.csv",
        "deletion_rules.csv",
        "resource_mapping.csv",
    ]

    if all(
        parsed_files[name]["valid"]
        for name in required_for_unified_report
    ):
        # Reuse the reports created by the earlier pipeline stages.
        resource_mappings = parsed_files[
            "resource_mapping.csv"
        ]["records"]

        # Reuse the policy report generated in Phase 4.
        # Do not reevaluate policies using resource mappings.
        rules = parsed_files["deletion_rules.csv"]["records"]

        timeline_report = reconstruct_timelines(
            all_activities,
            matched_user_ids,
        )

        verification_report = verify_deletions(
            all_activities,
            matched_user_ids,
        )


        unified_report = build_unified_audit(
            resource_mappings=resource_mappings,
            policy_report=policy_report,
            timeline_report=timeline_report,
            verification_report=verification_report,
        )

        unified_path = REPORT_DIR / "unified_audit_report.json"
        unified_path.write_text(
            json.dumps(unified_report, indent=2),
            encoding="utf-8",
        )

        print("\nUnified Audit Summary:")
        print(json.dumps(unified_report["summary"], indent=2))
        print(f"Unified audit report saved: {unified_path}")

        # Generate the final GDPR deletion audit summary.
        investigation_files = sorted(
            REPORT_DIR.glob("ai_investigation_*.json")
        )

        investigations = []

        for investigation_path in investigation_files:
            with investigation_path.open("r", encoding="utf-8") as file:
                investigation_data = json.load(file)

            if not isinstance(investigation_data, dict):
                raise ValueError(
                    f"Expected a JSON object in {investigation_path}"
                )

            investigations.append(investigation_data)

            final_summary = build_final_summary(
            unified_audit=unified_report,
            investigations=investigations,
            identity_resolution=identity_report,
        )

        validation_issues = validate_final_summary(final_summary)

        if validation_issues:
            print("\nFinal report validation FAILED:")

            for issue in validation_issues:
                print(
                    f"[{issue.get('severity', 'ERROR')}] "
                    f"{issue.get('code', 'VALIDATION_ERROR')}: "
                    f"{issue.get('message', str(issue))}"
                )

            raise SystemExit(1)

        final_summary_path = (
            REPORT_DIR / "final_gdpr_deletion_audit_summary.json"
        )

        write_final_summary(final_summary, final_summary_path)
        csv_path = REPORT_DIR / "gdpr_deletion_audit_results.csv"

        export_final_summary_csv(
            final_summary_path,
            csv_path,
        )

        print(f"CSV audit report saved: {csv_path}")
        print("\nFinal report validation PASSED.")
        print(f"Final summary saved: {final_summary_path}")
        print(f"Resources: {final_summary['resource_count']}")
        print(
            "AI investigation reports included: "
            f"{final_summary['investigation_reports_available']}"
        )

    else:
        print(
            "\nUnified audit report skipped: "
            "one or more required input files are invalid."
        )


def extract_evidence_events(evidence):
    """Extract valid event records from scanned CSV evidence."""

    events = []
    errors = []

    required_fields = {
        "event_id",
        "timestamp",
        "user_id",
        "event_type",
        "resource_id",
    }

    for item in evidence:
        # Only process successfully scanned CSV files.
        if item["status"] != "OK":
            continue

        if item["format"].lower() != ".csv":
            continue

        records = item["content"]

        # Ignore CSVs that are not event-record files.
        if not isinstance(records, list) or not records:
            continue

        if not all(
            isinstance(record, dict)
            and required_fields.issubset(record.keys())
            for record in records
        ):
            continue

        try:
            # Use the file name as a fallback system identifier.
            default_system = Path(item["file"]).stem.upper()

            normalized = extract_csv_events(
                records,
                default_system=default_system,
            )
            events.extend(normalized)

        except ValueError as exc:
            errors.append({
                "file": item["file"],
                "error": str(exc),
            })

    return events, errors

def deduplicate_events(
    activities: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Deduplicate events within each source system."""

    unique_events = []
    events_by_id = {}
    conflicts = []

    for event in activities:
        event_id = str(event.get("event_id", "")).strip()

        # Events without IDs cannot be safely deduplicated.
        if not event_id:
            unique_events.append(event)
            continue

        system_id = str(event.get("system_id", "")).strip()
        event_key = (system_id, event_id)

        if event_key not in events_by_id:
            events_by_id[event_key] = event
            unique_events.append(event)
            continue

        original = events_by_id[event_key]

        if event == original:
            # Exact duplicate: retain only the first occurrence.
            continue

        # Same ID in the same system, but different event data.
        conflicts.append({
            "event_id": event_id,
            "system_id": system_id,
            "reason": (
                "Conflicting records share the same event ID "
                "within the same system."
            ),
            "original_event": original,
            "conflicting_event": event,
        })

    return unique_events, conflicts



if __name__ == "__main__":
    main()
