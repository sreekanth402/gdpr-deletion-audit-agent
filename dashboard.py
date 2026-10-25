import json
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent

REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "final_gdpr_deletion_audit_summary.json"
)


def validate_final_summary(report):
    """Return a list of validation issues for the final summary JSON."""
    issues = []

    if not isinstance(report, dict):
        return [{
            "code": "invalid_report",
            "message": "The report JSON must contain a JSON object.",
        }]

    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        issues.append({
            "code": "invalid_summary",
            "message": "The report's summary field must be a JSON object.",
            "value": summary,
        })

    resources = report.get("resources", [])
    if not isinstance(resources, list):
        issues.append({
            "code": "invalid_resources",
            "message": "The report's resources field must be a list.",
            "value": resources,
        })
    else:
        for index, item in enumerate(resources):
            if not isinstance(item, dict):
                issues.append({
                    "code": "invalid_resource_entry",
                    "index": index,
                    "message": "Each resource entry must be a JSON object.",
                    "value": item,
                })
                continue

            resource_id = item.get("resource_id")
            if resource_id is None:
                issues.append({
                    "code": "missing_resource_id",
                    "index": index,
                    "message": "Resource entry is missing the resource_id field.",
                    "value": item,
                })

            audit = item.get("deterministic_audit", {})
            if not isinstance(audit, dict):
                issues.append({
                    "code": "invalid_deterministic_audit",
                    "index": index,
                    "message": "Resource deterministic_audit field must be an object.",
                    "value": audit,
                })

            ai = item.get("ai_investigation", {})
            if not isinstance(ai, dict):
                issues.append({
                    "code": "invalid_ai_investigation",
                    "index": index,
                    "message": "Resource ai_investigation field must be an object.",
                    "value": ai,
                })

    integrity_findings = report.get("integrity_findings", [])
    if integrity_findings is not None and not isinstance(integrity_findings, list):
        issues.append({
            "code": "invalid_integrity_findings",
            "message": "The report's integrity_findings field must be a list.",
            "value": integrity_findings,
        })

    return issues


if not REPORT_PATH.exists():
    st.error(f"Report file not found: {REPORT_PATH}")
    st.stop()

with REPORT_PATH.open("r", encoding="utf-8") as file:
    report = json.load(file)

if not isinstance(report, dict):
    st.error("The report JSON must contain a JSON object.")
    st.stop()

resources = report.get("resources", [])

st.set_page_config(
    page_title="GDPR Deletion Audit",
    page_icon="🔍",
    layout="wide",
)

st.title("GDPR Deletion Audit Dashboard")
st.caption("Read-only view of audit evidence and investigation results.")

if not REPORT_PATH.exists():
    st.error(f"Final report not found: {REPORT_PATH}")
    st.info(
        "Generate the report first using "
        "`python -m src.deletion_audit.reporting.run_final_summary`."
    )
    st.stop()

try:
    with REPORT_PATH.open("r", encoding="utf-8") as file:
        report = json.load(file)
except (OSError, json.JSONDecodeError) as exc:
    st.error(f"Could not load the final report: {exc}")
    st.stop()

issues = validate_final_summary(report)
resources = report.get("resources", [])

if not isinstance(resources, list):
    st.error("The report's resources field is invalid.")
    st.stop()

st.caption(f"Report file: {REPORT_PATH.name}")

if issues:
    st.warning(
        f"Validation found {len(issues)} issue(s). "
        "Review them before relying on this report."
    )
else:
    st.success("Final report validation passed.")

# Summary metrics
summary = report.get("summary", {})

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Resources evaluated",
    summary.get("resources_evaluated", len(resources)),
)
col2.metric(
    "Verified deleted",
    summary.get("verified_deleted", 0),
)
col3.metric(
    "Review required",
    summary.get("review_required", 0),
)
col4.metric(
    "Verification required",
    summary.get("verification_required", 0),
)

st.divider()

# Filters
st.subheader("Resource audit results")

audit_statuses = sorted({
    str(item.get("deterministic_audit", {}).get(
        "audit_status", "UNKNOWN"
    ))
    for item in resources
    if isinstance(item, dict)
})

selected_statuses = st.multiselect(
    "Filter by audit status",
    options=audit_statuses,
    default=audit_statuses,
)

search_text = st.text_input("Search resource ID", placeholder="e.g. rec101")

filtered_resources = []

for item in resources:
    if not isinstance(item, dict):
        continue

    audit = item.get("deterministic_audit", {})
    resource_id = str(item.get("resource_id", ""))
    status = str(audit.get("audit_status", "UNKNOWN"))

    if status not in selected_statuses:
        continue

    if search_text.strip().lower() not in resource_id.lower():
        continue

    filtered_resources.append(item)

if not filtered_resources:
    st.info("No resources match the selected filters.")

for item in filtered_resources:
    resource_id = item.get("resource_id", "Unknown")
    audit = item.get("deterministic_audit", {})
    ai = item.get("ai_investigation", {})

    status = audit.get("audit_status", "UNKNOWN")

    with st.expander(f"{resource_id} — {status}", expanded=False):
        left, right = st.columns(2)

        with left:
            st.markdown("**Deterministic audit**")
            st.write("Data type:", audit.get("data_type", "Not available"))
            st.write("Policy action:", audit.get("policy_action", "Not available"))
            st.write("Policy status:", audit.get("policy_status", "Not available"))
            st.write("Delete event:", audit.get("delete_event_id") or "Not recorded")
            st.write("Recommended action:", audit.get("recommended_action", "Not available"))

        with right:
            st.markdown("**AI investigation**")
            st.write("Available:", ai.get("available", False))
            st.write("Status:", ai.get("status", "NOT_RUN"))
            st.write("Summary:", ai.get("summary") or "No investigation summary.")

            gaps = ai.get("evidence_gaps", [])
            if gaps:
                st.markdown("**Evidence gaps**")
                for gap in gaps:
                    st.write(f"- {gap}")

            checks = ai.get("recommended_checks", [])
            if checks:
                st.markdown("**Recommended checks**")
                for check in checks:
                    st.write(f"- {check}")

        findings = audit.get("timeline_findings", [])
        if findings:
            st.markdown("**Timeline findings**")
            st.dataframe(findings, use_container_width=True)

        with st.expander("View complete resource evidence"):
            st.json(item)

# Integrity findings
st.divider()
st.subheader("Timeline integrity findings")

integrity_findings = report.get("integrity_findings", [])

if integrity_findings:
    st.dataframe(integrity_findings, use_container_width=True)
else:
    st.info("No timeline integrity findings are recorded.")

# Validation details
st.divider()
st.subheader("Report validation details")

if issues:
    st.dataframe(issues, use_container_width=True)
else:
    st.write("No validation issues detected.")

# Download the exact report loaded by the dashboard
st.download_button(
    label="Download final audit report (JSON)",
    data=json.dumps(report, indent=2, ensure_ascii=False),
    file_name="final_gdpr_deletion_audit_summary.json",
    mime="application/json",
)

st.caption(
    "AI investigation content is advisory. "
    "Deterministic audit results remain authoritative."
)
