from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(r"C:\Users\Ahaan\LLM-MCDA Paper")


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def read_rows(path):
    """Read an .xlsx scenario file as a list of string-valued dict rows."""
    df = pd.read_excel(ROOT / path, dtype=str, engine="openpyxl").fillna("")
    return df.to_dict("records")


out = {}
for name, path, key_col in [
    ("HVAC", "Scenario Files/HVACScenarios.xlsx", "Question"),
    ("Appliance", "Scenario Files/ApplianceScenarios.xlsx", "Description"),
    ("Shower", "Scenario Files/ShowerScenarios.xlsx", "Description"),
]:
    grouped = {}
    for idx, row in enumerate(read_rows(path), start=2):
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
