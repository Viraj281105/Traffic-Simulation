"""Regenerate shared/schemas/v2/*.schema.json from the Pydantic models.

cd backend && python -m src.planning.export_schemas
"""

import json
from pathlib import Path
from typing import Any, Dict, Tuple, Type

from pydantic import BaseModel

from src.calibration.models import CalibrationOptions, ObservationSet
from src.networks.models import NetworkDocument
from src.planning.models import PlanningStudy
from src.planning.report import Report

OUT = Path(__file__).resolve().parents[3] / "shared" / "schemas" / "v2"

MODELS: Tuple[Tuple[str, Type[BaseModel]], ...] = (
    ("planning-study", PlanningStudy),
    ("planning-report", Report),
    ("calibration-observations", ObservationSet),
    ("calibration-options", CalibrationOptions),
    ("network", NetworkDocument),
)


def schemas() -> Dict[str, Any]:
    return {name: model.model_json_schema() for name, model in MODELS}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas().items():
        (OUT / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", name)


if __name__ == "__main__":
    main()
