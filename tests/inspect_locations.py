from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\Ahaan\LLM-MCDA Paper")
targets = [
    ("HVACScenarios.xlsx", "Gettysburg"),
    ("TestScenarios.xlsx", "Gettysburg"),
    ("ShowerScenarios.xlsx", "Phoenixville"),
    ("ShowerScenarios.xlsx", "Scranton"),
    ("TestScenarios.xlsx", "Phoenixville"),
    ("TestScenarios.xlsx", "Scranton"),
]
out = {}
for filename, city in targets:
    rows = pd.read_excel(ROOT / "Scenario Files" / filename, dtype=str,
                         engine="openpyxl").fillna("").to_dict("records")
    out[f"{filename} {city}"] = [
        {"row": i + 2, **row} for i, row in enumerate(rows) if city in row.get("location", "")
    ]
print(json.dumps(out, indent=2))
