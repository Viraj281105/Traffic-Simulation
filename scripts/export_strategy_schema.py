"""Export JSON Schema for StrategyDescriptor (ADR-014)."""

import json
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parents[1] / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from src.strategies.models import StrategyDescriptor


def main() -> None:
    schema = StrategyDescriptor.model_json_schema()
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["title"] = "StrategyDescriptor"
    schema["description"] = (
        "Layered strategy descriptor (urbanflow-strategy v1) -- V3.0 W3 (ADR-014)"
    )

    out_path = (
        Path(__file__).resolve().parents[1]
        / "shared"
        / "schemas"
        / "v3"
        / "strategy-descriptor.schema.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Exported strategy schema to {out_path}")


if __name__ == "__main__":
    main()
