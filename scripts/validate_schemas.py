from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "shared" / "schemas"

    if not schema_dir.is_dir():
        print(f"Schema directory not found: {schema_dir}")
        return 1

    schema_files = sorted(schema_dir.glob("*.json"))
    if not schema_files:
        print(f"No schema files found in {schema_dir}")
        return 1

    errors: list[str] = []

    for schema_file in schema_files:
        try:
            with schema_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            errors.append(f"{schema_file}: invalid JSON ({exc})")
            continue

        if not isinstance(data, dict):
            errors.append(f"{schema_file}: schema root must be a JSON object")
            continue

        if "$schema" not in data:
            errors.append(f"{schema_file}: missing required '$schema' field")

    if errors:
        print("Schema validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"Schema validation passed for {len(schema_files)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
