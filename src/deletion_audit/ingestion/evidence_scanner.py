
from pathlib import Path
from typing import Any

from .csv_reader import read_csv_file
from .json_reader import read_json_file

TEXT_EXTENSIONS = {".txt", ".log", ".sql"}


def scan_evidence(root: Path) -> list[dict[str, Any]]:
    """Discover evidence files, classify formats, and validate content."""

    results: list[dict[str, Any]] = []

    if not root.exists():
        return [{
            "file": str(root),
            "format": "directory",
            "status": "ERROR",
            "content": None,
            "errors": ["Evidence directory does not exist."],
        }]

    if not root.is_dir():
        return [{
            "file": str(root),
            "format": "directory",
            "status": "ERROR",
            "content": None,
            "errors": ["Evidence path is not a directory."],
        }]

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        extension = path.suffix.lower()

        item: dict[str, Any] = {
            "file": str(path),
            "format": extension or "unknown",
            "status": "UNSUPPORTED",
            "content": None,
            "errors": [],
        }

        try:
            if extension == ".csv":
                parsed = read_csv_file(path)

                item["content"] = parsed["records"]
                item["errors"] = parsed["errors"]
                item["status"] = (
                    "OK" if parsed["valid"] else "ERROR"
                )

            elif extension == ".json":
                parsed = read_json_file(path)

                item["content"] = parsed["data"]
                item["errors"] = parsed["errors"]
                item["status"] = (
                    "OK" if parsed["valid"] else "ERROR"
                )

            elif extension in TEXT_EXTENSIONS:
                content = path.read_text(encoding="utf-8-sig")

                if not content.strip():
                    item["status"] = "ERROR"
                    item["errors"].append(
                        "Evidence file is empty or contains only whitespace."
                    )
                else:
                    item["content"] = content
                    item["status"] = "OK"

            else:
                item["errors"].append(
                    "Reader for this format is not implemented."
                )

        except (OSError, UnicodeError) as exc:
            item["status"] = "ERROR"
            item["errors"].append(
                f"Could not read evidence: {exc}"
            )

        results.append(item)

    if not results:
        return [{
            "file": str(root),
            "format": "directory",
            "status": "WARNING",
            "content": None,
            "errors": ["Evidence directory contains no files."],
        }]

    return results
