"""Run from repository root: python -m backend.scripts.export_schemas."""
import json
from pathlib import Path
from backend import models


def schemas():
    return {
        name: cls.model_json_schema()
        for name, cls in vars(models).items()
        if isinstance(cls, type) and issubclass(cls, models.Model)
        and cls is not models.Model
    }


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[2] / "contracts" / "schemas.json"
    path.write_text(json.dumps(schemas(), indent=2) + "\n")
