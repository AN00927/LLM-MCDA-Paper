from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(r"C:\Users\Ahaan\LLM-MCDA Paper")


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def rows(path):
    """Read an .xlsx scenario/ground-truth file as string-valued dict rows."""
    df = pd.read_excel(ROOT / path, dtype=str, engine="openpyxl").fillna("")
    return df.to_dict("records")


def key(row, key_col, loc_col="Location"):
    return (norm(row.get(key_col)), norm(row.get(loc_col)))


def gt_key(row, key_col):
    return (norm(row.get(key_col)), norm(row.get("location")))


def temp_band_hvac(v):
    t = float(v)
    if t <= 15:
        return "extreme cold <=15"
    if t <= 32:
        return "cold 16-32"
    if t <= 55:
        return "mild heating 33-55"
    if t <= 75:
        return "neutral 56-75"
    if t <= 83:
        return "mild cooling 76-83"
    if t <= 92:
        return "hot 84-92"
    return "extreme heat >=93"


def temp_band_shower(v):
    t = float(v)
    if t <= 32:
        return "winter <=32"
    if t <= 74:
        return "spring/fall 33-74"
    return "summer >=75"


def city(location):
    return str(location).split(",")[0].strip()


CITY_TO_UTILITY = {
    "Philadelphia": "PECO", "Norristown": "PECO", "Pottstown": "PECO",
    "Phoenixville": "PECO", "West Chester": "PECO", "Exton": "PECO",
    "King of Prussia": "PECO", "Blue Bell": "PECO", "Lower Merion": "PECO",
    "Media": "PECO", "Coatesville": "PECO", "Newtown": "PECO",
    "Doylestown": "PECO", "Chester": "PECO",
    "Allentown": "PPL", "Bethlehem": "PPL", "Hazleton": "PPL",
    "Reading": "PPL", "Scranton": "PPL", "Wilkes-Barre": "PPL",
    "Stroudsburg": "PPL", "Lebanon": "PPL", "Lancaster": "PPL",
    "State College": "PPL", "Harrisburg": "PPL", "Williamsport": "PPL",
    "Greensburg": "WestPenn", "Monroeville": "WestPenn",
    "Indiana": "WestPenn", "Uniontown": "WestPenn", "Butler": "WestPenn",
    "DuBois": "Penelec", "Oil City": "Penelec", "Meadville": "Penelec",
    "Erie": "Penelec", "Altoona": "Penelec", "Johnstown": "Penelec",
    "York": "MetEd", "Chambersburg": "MetEd", "Gettysburg": "MetEd",
    "Carlisle": "MetEd", "Easton": "MetEd",
    "Pittsburgh": "Duquesne", "McKeesport": "Duquesne",
}


def time_bucket(value):
    text = str(value or "")
    try:
        hour = float(text) * 24
    except ValueError:
        m = re.search(r"(\d{1,2})(?::\d{2})?\s*(am|pm)?", text, re.I)
        if not m:
            return "unknown"
        hour = int(m.group(1))
        suffix = (m.group(2) or "").lower()
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "overnight"


def audit():
    data = {
        "HVAC": {
            "scenarios": rows("Scenario Files/HVACScenarios.xlsx"),
            "gt": rows("Ground Truth/ground_truth_hvac.xlsx"),
            "rag": rows("Scenario Files/HVACRagScenarios.xlsx"),
            "key_col": "question",
            "gt_key_col": "question",
        },
        "Appliance": {
            "scenarios": rows("Scenario Files/ApplianceScenarios.xlsx"),
            "gt": rows("Ground Truth/ground_truth_appliance.xlsx"),
            "rag": rows("Scenario Files/ApplianceRAGScenarios.xlsx"),
            "key_col": "question",
            "gt_key_col": "question",
        },
        "Shower": {
            "scenarios": rows("Scenario Files/ShowerScenarios.xlsx"),
            "gt": rows("Ground Truth/ground_truth_shower.xlsx"),
            "rag": rows("Scenario Files/ShowerRAGScenarios.xlsx"),
            "key_col": "question",
            "gt_key_col": "question",
        },
    }
    test_rows = rows("Scenario Files/TestScenarios.xlsx")
    out = {"counts": {}, "underrepresented": {}, "checks": {}}
    for dtype, cfg in data.items():
        sc = cfg["scenarios"]
        sc_keys = [key(r, cfg["key_col"]) for r in sc]
        sc_set = set(sc_keys)
        gt_counts = Counter(gt_key(r, cfg["gt_key_col"]) for r in cfg["gt"])
        rag_keys = {gt_key(r, cfg["gt_key_col"]) for r in cfg["rag"]}
        test_keys = {
            (norm(r.get("question")), norm(r.get("location")))
            for r in test_rows
            if norm(r.get("decision_type")) == norm(dtype)
        }

        out["counts"][dtype] = {
            "scenario_rows": len(sc),
            "ground_truth_rows": len(cfg["gt"]),
            "ground_truth_scenarios": len(gt_counts),
            "rag_rows": len(cfg["rag"]),
            "rag_scenarios": len(rag_keys),
            "test_rows": len(test_keys),
        }
        out["checks"][dtype] = {
            "scenario_gt_not3": [list(k) + [gt_counts.get(k, 0)] for k in sc_keys if gt_counts.get(k, 0) != 3],
            "orphan_gt": [list(k) for k in gt_counts if k not in sc_set],
            "orphan_rag": [list(k) for k in rag_keys if k not in sc_set],
            "orphan_test": [list(k) for k in test_keys if k not in sc_set],
            "duplicate_scenarios": [list(k) + [v] for k, v in Counter(sc_keys).items() if v > 1],
            "incomplete_alternatives": [
                i + 2 for i, r in enumerate(sc)
                if not all(str(r.get(f"alternative_{n}", "")).strip() for n in (1, 2, 3))
            ],
        }

        flags = []
        if dtype == "HVAC":
            checks = [
                ("outdoor_temp band", Counter(temp_band_hvac(r["outdoor_temp"]) for r in sc), 3),
                ("occupancy_context", Counter(norm(r.get("occupancy_context")) for r in sc), 3),
                ("housing_type", Counter(norm(r.get("housing_type")) for r in sc), 3),
                ("insulation", Counter(norm(r.get("insulation")) for r in sc), 3),
            ]
        elif dtype == "Appliance":
            checks = [
                ("appliance", Counter(norm(r.get("appliance")) for r in sc), 3),
                ("Utility region", Counter(CITY_TO_UTILITY.get(city(r.get("location")), "unknown") for r in sc), 2),
                ("baseline_time bucket", Counter(time_bucket(r.get("baseline_time")) for r in sc), 3),
            ]
        else:
            checks = [
                ("gpm", Counter(norm(r.get("gpm")) for r in sc), 2),
                ("outdoor_temp seasonal band", Counter(temp_band_shower(r["outdoor_temp"]) for r in sc), 3),
            ]
        for parameter, counter, minimum in checks:
            for value, count in sorted(counter.items()):
                if value and count < minimum:
                    flags.append([parameter, value, count, minimum])
        out["underrepresented"][dtype] = flags
    return out


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
