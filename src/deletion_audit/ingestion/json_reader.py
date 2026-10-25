
import json
from pathlib import Path
from typing import Any


def read_json_file(file_path: Path) -> dict[str, Any]:
    """Read a JSON file and validate its syntax."""

    result: dict[str, Any] = {
        "file": str(file_path),
        "data": None,
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
        ) as file:
            data = json.load(file)

        result["data"] = data
        result["valid"] = True

    except json.JSONDecodeError as exc:
        result["errors"].append(
            f"Invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )

    except (OSError, UnicodeError) as exc:
        result["errors"].append(
            f"Could not read JSON: {exc}"
        )

    return result
