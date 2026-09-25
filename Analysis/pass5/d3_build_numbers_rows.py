#!/usr/bin/env python3
"""Build paper/pass5/NUMBERS_OF_RECORD_D3_rows.csv from the d3_*.csv outputs.
Same columns as paper/pass5/NUMBERS_OF_RECORD.csv. Per model; never pooled."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "Analysis" / "pass5"
COLS = ["number_id", "value", "where_in_paper", "quoted_context", "source_file",
        "source_sheet_or_column", "computing_script", "model", "decision_type",
        "basis_notes", "status"]
SRC_RUNS = "Output Files <model>/LLM-Parameterized_Reference_Scoring_results_run_01..05.xlsx"
SCRIPT = "Analysis/pass5/d3_gpm_mechanism.py"
rows = []

TAB = {"r_value": 931, "seer": 932, "hvac_age": 933, "kwh_per_cycle": 934,
       "gpm": 935, "tank_size": 936, "water_heater_temp": 937}
s = pd.read_csv(A / "d3_p_top1_change_summary.csv")
for _, r in s.iterrows():
    p, m = r.parameter, r.model
    if p in ("appliance", "baseline_time"):
        continue
    if pd.notna(r.p_change_mean):
        where = f"paper/paper_draft_v2.tex:{TAB[p]}" if p in TAB else "paper/paper_draft_v2.tex:945 (occupancy discussed, no P reported)"
        pub = r.published_aggregate_basis
        status = ("new (not in paper)" if pd.isna(pub) else
                  ("matches published" if abs(round(r.p_change_mean, 3) - pub) < 0.0015
                   else f"differs from published {pub:.3f} (published used 5-run aggregate parameters)"))
        rows.append({"number_id": f"D3_ptop1_{p}_{m}", "value": round(r.p_change_mean, 3),
                     "where_in_paper": where,
                     "quoted_context": f"tab:extraction_accuracy P(Top-1 change | error) {p}",
                     "source_file": SRC_RUNS,
                     "source_sheet_or_column": f"d3_p_top1_change_summary.csv p_change_mean ({int(r.n_flip_total)}/{int(r.n_error_total)} run-summed)",
                     "computing_script": SCRIPT, "model": m, "decision_type": r.decision_type,
                     "basis_notes": "per run: re-score with only this parameter at its extracted value, all else true; share of erroneous scenarios whose Top-1 changes; mean over 5 runs; failed scenario-runs excluded",
                     "status": status})
    if pd.notna(r.mae_per_run_mean):
        rows.append({"number_id": f"D3_mae_{p}_{m}", "value": round(r.mae_per_run_mean, 3),
                     "where_in_paper": f"paper/paper_draft_v2.tex:{TAB[p]}",
                     "quoted_context": f"tab:extraction_accuracy MAE {p}",
                     "source_file": SRC_RUNS, "source_sheet_or_column": "d3_p_top1_change_summary.csv mae_per_run_mean",
                     "computing_script": SCRIPT, "model": m, "decision_type": r.decision_type,
                     "basis_notes": "mean |extracted - true| per run over scored scenarios, mean of 5 runs",
                     "status": "per-run basis; published cell used 5-run aggregate parameters"})
    if p == "occupancy_context":
        rows.append({"number_id": f"D3_occupancy_match_{m}", "value": round(100 * (1 - r.error_rate_mean), 1),
                     "where_in_paper": "paper/paper_draft_v2.tex:945,1083",
                     "quoted_context": "HVAC occupancy context has the lowest match accuracy, at 75.4% GPT-OSS, 78.6% Qwen, 80.0% Gemini, 81.4% DeepSeek",
                     "source_file": SRC_RUNS, "source_sheet_or_column": "d3_p_top1_change_summary.csv 1-error_rate_mean",
                     "computing_script": SCRIPT, "model": m, "decision_type": "HVAC",
                     "basis_notes": "per-run match accuracy (%), mean of 5 runs",
                     "status": "per-run basis; published used 5-run modal occupancy"})

pa = pd.read_csv(A / "d3_gpm_attribution_per_run_mean.csv")
att = pd.read_csv(A / "d3_gpm_attribution_summary.csv")
for _, r in pa.iterrows():
    m = r.model
    a = att[att.model == m].iloc[0]
    for key, col, note in [
        ("linear_core_share", "share_linear_core", "share of GPM-only flips that persist with clipping, tank step, budget penalty and 2-dp rounding all switched off"),
        ("needs_tank_share", "share_needs_tank", "share of GPM-only flips that disappear when only the tank-capacity step is switched off"),
        ("needs_clip_share", "share_needs_clip", "share of GPM-only flips that disappear when only value-function clipping is switched off"),
        ("needs_round_share", "share_needs_round", "share of GPM-only flips that disappear when only 2-dp score rounding is switched off"),
        ("cross_tank_share", "share_cross_tank", "share of GPM-only flips in which some alternative's tank-capacity state changes"),
        ("cross_clip_share", "share_cross_clip", "share of GPM-only flips in which some alternative's cost or water value crosses a 5th/95th percentile bound"),
        ("margin_lt_0p02_share", "share_margin_lt_0.02", "share of GPM-only flips whose reference winner leads by < 0.02 MAVT"),
    ]:
        rows.append({"number_id": f"D3_gpmflip_{key}_{m}", "value": round(r[col], 3),
                     "where_in_paper": "proposed, paper/paper_draft_v2.tex:1057 / supplement",
                     "quoted_context": "GPM mechanism attribution", "source_file": SRC_RUNS,
                     "source_sheet_or_column": f"d3_gpm_attribution_per_run_mean.csv {col}",
                     "computing_script": SCRIPT, "model": m, "decision_type": "Shower",
                     "basis_notes": note + "; per run then mean of 5 runs",
                     "status": "new"})
    rows.append({"number_id": f"D3_gpmflip_comfort_prac_flat_survive_{m}",
                 "value": round(a["share_flips_surviving_comfort_and_prac_flat"], 3),
                 "where_in_paper": "proposed, paper/paper_draft_v2.tex:1057 / supplement",
                 "quoted_context": "GPM mechanism attribution", "source_file": SRC_RUNS,
                 "source_sheet_or_column": "d3_gpm_attribution_summary.csv share_flips_surviving_comfort_and_prac_flat",
                 "computing_script": SCRIPT, "model": m, "decision_type": "Shower",
                 "basis_notes": "share of GPM-only flips that persist when Comfort and the Practicality duration curve are held constant across alternatives; 5 runs summed within model",
                 "status": "new"})

fd = pd.read_csv(A / "d3_flip_distance_summary.csv")
for _, r in fd.iterrows():
    for col, lab in [("share_flippable_within_0p5_2x", "flippable_0p5_2x"),
                     ("share_flip_within_20pct", "flip_within_20pct")]:
        rows.append({"number_id": f"D3_flipdist_{lab}_{r.parameter}", "value": round(r[col], 3),
                     "where_in_paper": "proposed, supplement", "quoted_context": "flip distance",
                     "source_file": "Scenario Files/TestScenarios.xlsx + <Type>Scenarios.xlsx (true values)",
                     "source_sheet_or_column": f"d3_flip_distance_summary.csv {col}",
                     "computing_script": SCRIPT, "model": "none (no LLM)", "decision_type": r.decision_type,
                     "basis_notes": "share of scenarios whose Top-1 changes when the true parameter is multiplied by some factor in [0.5,2.0] (resp. within +/-20%), all else true",
                     "status": "new"})

pd.DataFrame(rows, columns=COLS).to_csv(ROOT / "paper" / "pass5" / "NUMBERS_OF_RECORD_D3_rows.csv", index=False)
print(f"wrote {len(rows)} rows")
