import json
from pathlib import Path

from voiceos_api.main import app

target = Path("packages/shared-ts/openapi.json")
target.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"Wrote {target}")

