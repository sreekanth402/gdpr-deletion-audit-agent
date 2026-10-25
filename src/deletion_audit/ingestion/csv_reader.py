
import csv
from pathlib import Path
from typing import Any


def read_csv_file(
    file_path: Path,
    required_columns: set[str] | None = None,
) -> dict[str, Any]:
    """Read a CSV file and validate its header and rows."""

    result: dict[str, Any] = {
        "file": str(file_path),
        "records": [],
        "columns": [],
        "errors": [],
        "valid": False,
    }

    if not file_path.is_file():
        result["errors"].append("File does not exist.")
        return result

    try:
        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            # Ignore blank lines before reading the CSV header or rows.
            reader = csv.reader(file)

            try:
                raw_headers = next(
                    row for row in reader
                    if row and any(value.strip() for value in row)
                )
            except StopIteration:
                result["errors"].append("CSV file is empty.")
                return result

            columns = [header.strip() for header in raw_headers]

            if not columns or any(not column for column in columns):
                result["errors"].append(
                    "CSV contains a missing or empty column name."
                )
                return result

            if len(columns) != len(set(columns)):
                result["errors"].append(
                    "CSV contains duplicate column names."
                )
                return result

            result["columns"] = columns

            if required_columns:
                normalized_required = {
                    column.strip() for column in required_columns
                }
                missing = normalized_required - set(columns)

                if missing:
                    result["errors"].append(
                        f"Missing required columns: {sorted(missing)}"
                    )
                    return result

            for values in reader:
                line_number = reader.line_num

                # Ignore blank rows while preserving physical line numbers.
                if not values or all(not value.strip() for value in values):
                    continue

                if len(values) != len(columns):
                    result["errors"].append(
                        f"Line {line_number}: expected {len(columns)} "
                        f"values, found {len(values)}."
                    )
                    continue

                normalized_row = {
                    column: value.strip() for column, value in zip(columns, values)
                }
                result["records"].append(normalized_row)

            result["valid"] = not result["errors"]

    except (OSError, UnicodeError, csv.Error) as exc:
        result["errors"].append(f"Could not read CSV: {exc}")

    return result
