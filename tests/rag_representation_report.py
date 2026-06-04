from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(r"C:\Users\Ahaan\LLM-MCDA Paper")


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def rows(path):
    """Read an .xlsx scenario/RAG file as string-valued dict rows."""
    df = pd.read_excel(ROOT / path, dtype=str, engine="openpyxl").fillna("")
    return df.to_dict("records")


def unique_by(rows_, key_col, loc_col):
    seen = {}
    for row in rows_:
        seen.setdefault((norm(row.get(key_col)), norm(row.get(loc_col))), row)
    return list(seen.values())


def temp_band_hvac(value):
    t = float(value)
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


def temp_band_shower(value):
    t = float(value)
    if t <= 32:
        return "winter <=32"
    if t <= 74:
        return "spring/fall 33-74"
    return "summer >=75"


def time_bucket(value):
    text = str(value or "")
    m = re.search(r"(\d{1,2})(?::\d{2})?\s*(am|pm)?", text, re.I)
    if not m:
        try:
            hour = float(text) * 24
        except ValueError:
            return "unknown"
    else:
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


def pct(counter):
    total = sum(counter.values()) or 1
    return {k: {"count": v, "pct": round(v / total, 3)} for k, v in sorted(counter.items())}


hvac_s = rows("Scenario Files/HVACScenarios.xlsx")
hvac_r = unique_by(rows("Scenario Files/HVACRagScenarios.xlsx"), "question", "location")
hvac_lookup = {(norm(r["question"]), norm(r["location"])): r for r in hvac_s}
# Skip RAG rows whose source scenario is no longer in the current scenario set
# (e.g. when the RAG export is stale relative to HVACScenarios) instead of
# crashing on a missing key.
hvac_r_src = [
    hvac_lookup[k] for r in hvac_r
    if (k := (norm(r["question"]), norm(r["location"]))) in hvac_lookup
]
app_s = rows("Scenario Files/ApplianceScenarios.xlsx")
app_r = unique_by(rows("Scenario Files/ApplianceRAGScenarios.xlsx"), "question", "location")
sh_s = rows("Scenario Files/ShowerScenarios.xlsx")
sh_r = unique_by(rows("Scenario Files/ShowerRAGScenarios.xlsx"), "question", "location")

report = {
    "HVAC": {
        "all_temp_band": pct(Counter(temp_band_hvac(r["outdoor_temp"]) for r in hvac_s)),
        "rag_temp_band": pct(Counter(temp_band_hvac(r["outdoor_temp"]) for r in hvac_r)),
        "all_occupancy": pct(Counter(norm(r["occupancy_context"]) for r in hvac_s)),
        "rag_occupancy": pct(Counter(norm(r["occupancy_context"]) for r in hvac_r_src)),
    },
    "Appliance": {
        "all_appliance": pct(Counter(norm(r["appliance"]) for r in app_s)),
        "rag_appliance": pct(Counter(norm(r["appliance"]) for r in app_r)),
        "all_time_bucket": pct(Counter(time_bucket(r["baseline_time"]) for r in app_s)),
        "rag_time_bucket": "not available in ground_truth-derived RAG rows",
    },
    "Shower": {
        "all_gpm": pct(Counter(norm(r["gpm"]) for r in sh_s)),
        "rag_gpm": pct(Counter(norm(r["gpm"]) for r in sh_r)),
        "all_temp_band": pct(Counter(temp_band_shower(r["outdoor_temp"]) for r in sh_s)),
        "rag_temp_band": pct(Counter(temp_band_shower(r["outdoor_temp"]) for r in sh_r)),
    },
}

print(json.dumps(report, indent=2))
