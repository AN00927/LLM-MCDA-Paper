from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(r"C:\Users\Ahaan\LLM-MCDA Paper")
targets = [
    ("HVACScenarios.csv", "Gettysburg"),
    ("TestScenarios.csv", "Gettysburg"),
    ("ShowerScenarios.csv", "Phoenixville"),
    ("ShowerScenarios.csv", "Scranton"),
    ("TestScenarios.csv", "Phoenixville"),
    ("TestScenarios.csv", "Scranton"),
]
out = {}
for filename, city in targets:
    with (ROOT / "Scenario Files" / filename).open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    out[f"{filename} {city}"] = [
        {"row": i + 2, **row} for i, row in enumerate(rows) if city in row.get("Location", "")
    ]
print(json.dumps(out, indent=2))
