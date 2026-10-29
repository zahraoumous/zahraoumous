"""Export only implemented endpoints; the supplied contract stays a reference."""

import json
from pathlib import Path

from app.main import app

path = Path(__file__).resolve().parents[1] / "packages/api-contract/openapi.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
