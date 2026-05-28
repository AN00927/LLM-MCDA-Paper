from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(r"C:\Users\Ahaan\LLM-MCDA Paper")


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def read_csv(path):
    with (ROOT / path).open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


out = {}
for name, path, key_col in [
    ("HVAC", "Scenario Files/HVACScenarios.csv", "Question"),
    ("Appliance", "Scenario Files/ApplianceScenarios.csv", "Description"),
    ("Shower", "Scenario Files/ShowerScenarios.csv", "Description"),
]:
    grouped = {}
    for idx, row in enumerate(read_csv(path), start=2):
        key = (norm(row.get(key_col)), norm(row.get("Location")))
        grouped.setdefault(key, []).append((idx, row))
    out[name] = [
        {
            "key": key,
            "rows": [
                {
                    "row": idx,
                    key_col: row.get(key_col),
                    "Location": row.get("Location"),
                    **{k: row.get(k) for k in row if k not in {key_col, "Location"}},
                }
                for idx, row in values
            ],
        }
        for key, values in grouped.items()
        if len(values) > 1
    ]

print(json.dumps(out, indent=2))
