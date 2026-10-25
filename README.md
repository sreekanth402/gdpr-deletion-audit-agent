# GDPR Deletion Audit Agent

A Python-based audit-support tool that analyzes personal-data deletion requests against identity records, system activity, evidence, and configured retention policies.

## Features

- Validates and ingests CSV and JSON inputs.
- Resolves deletion-request identities and flags unmatched or ambiguous identities.
- Reconstructs event timelines and identifies potentially risky post-deletion activity.
- Evaluates deletion evidence and configured data-retention rules.
- Produces unified audit results and JSON/CSV reports.
- Runs automated tests with pytest.

## Project Structure

- `src/deletion_audit/` — application modules and audit pipeline.
- `tests/` — automated tests.
- `data/input/` — sample input files.
- `data/evidence/` — sample evidence files.
- `dashboard.py` — dashboard entry point.
- `requirements.txt` — pinned Python dependencies.
- `reports/` — generated reports; excluded from Git.

## Requirements

- Python 3.11 or another version supported by the installed dependencies.
- PowerShell on Windows (commands below use PowerShell syntax).

## Setup

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, you can run the venv's Python directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the Audit Agent

```powershell
python -m src.deletion_audit.main
```

The application reads the configured sample inputs and writes audit reports under `reports/`.

## Run Tests

```powershell
python -m pytest -q
```

## Run the Dashboard

```powershell
python -m streamlit run dashboard.py
```

If Streamlit is not installed, check the dashboard imports and add its verified dependency to `requirements.txt` before running this command.

## Important Limitations

This is an audit-support prototype. Its results depend on the completeness and accuracy of supplied records, evidence, identity mappings, and policy rules. A `VERIFIED` result is based on implemented checks; it is not by itself a legal determination or proof of compliance with every GDPR obligation.

Use synthetic data for demos. Do not commit real personal data, credentials, API keys, or `.env` files.
