#!/usr/bin/env python3
"""
build_numbers_of_record.py -- regenerate the rows of
paper/pass5/NUMBERS_OF_RECORD.csv that a pipeline output alone can recompute,
so a fresh rerun's numbers can be diffed against the ones on record without
hand-checking each cell.

Scope: paper/pass5/NUMBERS_OF_RECORD.csv carries 122 numbers, each tagged with
the script that computed it. 37 of them (the AH_* rows) are tagged
"paper_pipeline/calculate_per_run_metrics.py" and are recomputable directly
from paper/per_run_metrics/per_run_metrics_all.csv, which that script already
produces. The other 85 rows come from Miscellaneous Scripts/experiments/
run_hybrid_ablation_experiments.py, Miscellaneous Scripts/validation/
test_hybrid_ablation_significance.py, Miscellaneous Scripts/core-automation/
evaluate_baseline_metrics.py and Analysis/pass5/d2_reproduce_ah_numbers.py --
P2/P1 territory, not reproduced here. This script marks those
"not_regenerated" with the script that owns them, rather than guessing.

READ-ONLY: never writes paper/pass5/NUMBERS_OF_RECORD.csv itself. Writes a
sibling CSV in the same schema plus a "regen_value"/"regen_status" pair of
columns, diffable against the original.

Usage:
    python paper_pipeline/build_numbers_of_record.py
    python paper_pipeline/build_numbers_of_record.py --output-dir Analysis/rerun_prep/infra
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SOURCE_CSV = PROJECT_ROOT / "paper" / "pass5" / "NUMBERS_OF_RECORD.csv"
PER_RUN_METRICS_CSV = PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "Analysis"

AH_ARCH = "LLM-Parameterized_Reference_Scoring"
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]

# number_id patterns this script knows how to regenerate, matched in order.
RE_SIMPLE = re.compile(r"^AH_(tau|top1|mae|success)_(deepseek|gemini|gptoss|qwen)$")
RE_BY_TYPE = re.compile(r"^AH_tau_(deepseek|gemini|gptoss|qwen)_(HVAC|Appliance|Shower)$")
RE_RANGE_TAU = re.compile(r"^AH_tau_range_L\d+$")
RE_RANGE_TOP1 = re.compile(r"^AH_top1_range_L\d+$")


def _per_run_agg(prm, model, decision_type):
    sub = prm[(prm.model == model) & (prm.architecture == AH_ARCH) &
              (prm.decision_type == decision_type)]
    if sub.empty:
        return None
    return dict(
        tau=round(float(sub.kendall_tau.mean()), 3),
        top1=round(float(sub.top1_accuracy.mean()) * 100, 1),
        mae=round(float(sub.overall_mae.mean()), 3),
        success=round(float((sub.n_scenarios / sub.n_total).mean()) * 100, 1),
        n_failed_total=int(sub.n_failed.sum()),
    )


def regenerate(row, prm, overall_by_model):
    """Return (regen_value, regen_status, regen_note) for one row, or
    (None, "not_regenerated", reason) if this script does not cover it."""
    nid = row["number_id"]

    m = RE_SIMPLE.match(nid)
    if m:
        metric, model = m.groups()
        agg = _per_run_agg(prm, model, "Overall")
        if agg is None:
            return None, "not_regenerated", "no per_run_metrics_all.csv rows for this model"
        return agg[metric], "regenerated", "mean over 5 runs, per_run_metrics_all.csv"

    m = RE_BY_TYPE.match(nid)
    if m:
        model, dtype = m.groups()
        agg = _per_run_agg(prm, model, dtype)
        if agg is None:
            return None, "not_regenerated", "no per_run_metrics_all.csv rows for this model/type"
        return agg["tau"], "regenerated", f"mean over 5 runs, per_run_metrics_all.csv, {dtype}"

    if RE_RANGE_TAU.match(nid) or nid == "AH_table_best_tau" or nid == "AH_table_worst_tau":
        taus = {mk: overall_by_model[mk]["tau"] for mk in MODELS if mk in overall_by_model}
        if not taus:
            return None, "not_regenerated", "no per-model tau available"
        lo_model, lo = min(taus.items(), key=lambda kv: kv[1])
        hi_model, hi = max(taus.items(), key=lambda kv: kv[1])
        if nid == "AH_table_best_tau":
            return hi, "regenerated", f"max over models ({hi_model})"
        if nid == "AH_table_worst_tau":
            return lo, "regenerated", f"min over models ({lo_model})"
        return f"{lo:.3f}-{hi:.3f}", "regenerated", f"min({lo_model})-max({hi_model}) over models"

    if RE_RANGE_TOP1.match(nid):
        vals = {mk: overall_by_model[mk]["top1"] for mk in MODELS if mk in overall_by_model}
        if not vals:
            return None, "not_regenerated", "no per-model top1 available"
        lo_model, lo = min(vals.items(), key=lambda kv: kv[1])
        hi_model, hi = max(vals.items(), key=lambda kv: kv[1])
        return f"{lo:.1f}-{hi:.1f}", "regenerated", f"min({lo_model})-max({hi_model}) over models"

    if nid == "AH_failures_total":
        parts = {mk: overall_by_model[mk]["n_failed_total"] for mk in MODELS if mk in overall_by_model}
        if not parts:
            return None, "not_regenerated", "no per-model failure counts available"
        total = sum(parts.values())
        detail = "/".join(f"{mk}={parts[mk]}" for mk in MODELS if mk in parts)
        return total, "regenerated", f"sum of n_failed over 5 runs per model ({detail})"

    return None, "not_regenerated", f"requires {row['computing_script']}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                    help="Where to write the regenerated CSV (default: Analysis/).")
    args = ap.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not SOURCE_CSV.exists():
        print(f"[ERROR] {SOURCE_CSV} not found; nothing to regenerate against.")
        return
    if not PER_RUN_METRICS_CSV.exists():
        print(f"[ERROR] {PER_RUN_METRICS_CSV} not found; run "
              "paper_pipeline/calculate_per_run_metrics.py --all-models first.")
        return

    records = pd.read_csv(SOURCE_CSV)
    prm = pd.read_csv(PER_RUN_METRICS_CSV)

    overall_by_model = {}
    for mk in MODELS:
        agg = _per_run_agg(prm, mk, "Overall")
        if agg is not None:
            overall_by_model[mk] = agg

    regen_values, regen_status, regen_notes, matches = [], [], [], []
    for _, row in records.iterrows():
        value, status, note = regenerate(row, prm, overall_by_model)
        regen_values.append(value)
        regen_status.append(status)
        regen_notes.append(note)
        if status == "regenerated":
            orig = str(row["value"])
            new = str(value)
            try:
                match = abs(float(orig) - float(new)) < 5e-4
            except ValueError:
                match = orig.strip() == new.strip()
            matches.append(match)
        else:
            matches.append(np.nan)

    out = records.copy()
    out["regen_value"] = regen_values
    out["regen_status"] = regen_status
    out["regen_note"] = regen_notes
    out["regen_matches_value"] = matches

    out_path = out_dir / "numbers_of_record_regenerated.csv"
    out.to_csv(out_path, index=False)

    n_regen = (out.regen_status == "regenerated").sum()
    n_match = out.regen_matches_value.eq(True).sum()
    n_mismatch = out.regen_matches_value.eq(False).sum()
    print(f"[OK] Wrote {out_path} ({len(out)} rows)")
    print(f"Regenerated: {n_regen}/{len(out)}  "
          f"(matches original value: {n_match}, mismatches: {n_mismatch})")
    if n_mismatch:
        print("Mismatches:")
        print(out[out.regen_matches_value == False][
            ["number_id", "value", "regen_value", "regen_note"]].to_string(index=False))
    not_covered = out[out.regen_status == "not_regenerated"]["computing_script"].value_counts()
    print("\nNot regenerated by this script, grouped by owning script:")
    print(not_covered.to_string())


if __name__ == "__main__":
    main()
