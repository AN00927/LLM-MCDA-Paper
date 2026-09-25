#!/usr/bin/env python3
"""
d12_build_numbers_rows.py -- collects the D9 / D12 numbers into
paper/pass5/NUMBERS_OF_RECORD_D9_D12_rows.csv, with the same columns as
paper/pass5/NUMBERS_OF_RECORD.csv (which this script never touches).
Run after d9_prompt_checks.py, d12_analyses.py and d12_position_baseline.py.
READ-ONLY with respect to every existing file.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "Analysis" / "pass5"
OUT = ROOT / "paper" / "pass5" / "NUMBERS_OF_RECORD_D9_D12_rows.csv"
COLS = ["number_id", "value", "where_in_paper", "quoted_context", "source_file",
        "source_sheet_or_column", "computing_script", "model", "decision_type",
        "basis_notes", "status"]
rows = []


def add(nid, val, src, col, script, model, dt, notes, status="new", where="not in paper", quote=""):
    rows.append(dict(number_id=nid, value=round(float(val), 4), where_in_paper=where,
                     quoted_context=quote, source_file=src, source_sheet_or_column=col,
                     computing_script=script, model=model, decision_type=dt,
                     basis_notes=notes, status=status))


RUNS = "Output Files <model>/<arch>_results_run_01..05.xlsx"

# ---- D9 appliance contrast ----
c = pd.read_csv(A / "d9_appliance_env_contrast.csv").set_index("item")["value"]
S9 = "Analysis/pass5/d9_prompt_checks.py"
add("D9_pjm_peak_offpeak_gap_share_of_peak", c["peak_minus_offpeak_as_share_of_peak"],
    "Ground Truth Calculators/ApplianceGroundTruthCalculator.py L22-23", "EMISSIONS_FACTOR_PEAK/OFFPEAK",
    S9, "all", "Appliance", "(1.041-0.976)/1.041; peak is 6.7% above off-peak", "verified",
    "paper/MOCK_EMS_REVIEW.md (reviewer's 6.2%)", "6.2% reference contrast")
add("D9_env_score_gap_per_kwh", c["appliance_env_score_gap_per_kwh_peak_vs_offpeak"],
    "ApplianceGroundTruthCalculator.py apply_value_function", "environmental min/max 0.288/3.643",
    S9, "all", "Appliance", "max Environmental Impact score change per kWh of cycle energy, peak vs off-peak")
for crit in ["environmental", "energy_cost", "comfort", "practicality"]:
    add(f"D9_appliance_ref_within_range_{crit}", c[f"appliance_test_mean_within_scenario_range_{crit}"],
        "Ground Truth/ground_truth_appliance.xlsx", f"{crit}_score", S9, "reference", "Appliance",
        "mean over 65 Appliance test scenarios of max-min reference criterion score")
add("D9_appliance_ref_env_zero_range_share", c["appliance_test_share_scenarios_zero_range_environmental"],
    "Ground Truth/ground_truth_appliance.xlsx", "environmental_score", S9, "reference", "Appliance",
    "share of 65 Appliance test scenarios whose three alternatives share one Environmental Impact score")

# ---- D9 prompt ablation by type ----
bt = pd.read_csv(A / "d9_prompt_ablation_by_type.csv")
te = pd.read_csv(A / "d9_prompt_ablation_tests.csv")
for r in bt[bt.arch == "A_D"].itertuples():
    note = (f"prompt-ablation cell, {r.n_runs} runs, per-run mean then mean over runs; tau is the ablation's "
            f"tau-b on continuous weighted scores (all-tied scenarios dropped), collected against the reference as it "
            f"stood in Jul-Aug 2026 (old shower comfort function)")
    if r.decision_type != "Overall" and r.variant == "no_anchors":
        t = te[(te.model == r.model) & (te.decision_type == r.decision_type) & (te.metric == "kendall_tau_stored")].iloc[0]
        note += f"; no_anchors-control diff {t['diff']:+.3f}, Wilcoxon p_Holm(12) {t.p_holm:.3g}"
    add(f"D9_ablation_AD_{r.variant}_tau_{r.model}_{r.decision_type}", r.stored_tau,
        f"Analysis/Prompt_Ablation/cell_{r.variant}_AD_{r.model}_run_*.xlsx", "kendall_tau", S9, r.model,
        r.decision_type, note)
    note2 = "Top-1 recomputed from stored pred_top1 against the CURRENT reference"
    if r.decision_type != "Overall" and r.variant == "no_anchors":
        t = te[(te.model == r.model) & (te.decision_type == r.decision_type) & (te.metric == "top1_current_ref")].iloc[0]
        note2 += f"; no_anchors-control diff {t['diff']:+.3f}, Wilcoxon p_Holm(12) {t.p_holm:.3g}"
    add(f"D9_ablation_AD_{r.variant}_top1cur_{r.model}_{r.decision_type}", r.top1_vs_current_ref,
        f"Analysis/Prompt_Ablation/cell_{r.variant}_AD_{r.model}_run_*.xlsx", "pred_top1 vs current reference",
        S9, r.model, r.decision_type, note2)

# ---- D12a ensemble ----
en = pd.read_csv(A / "d12_ensemble.csv")
wi = pd.read_csv(A / "d12_ensemble_wilcoxon.csv")
S12 = "Analysis/pass5/d12_analyses.py"
for r in en.itertuples():
    base = (f"criterion scores averaged over the runs in which the scenario succeeded (mean {r.mean_runs_per_scenario:.2f}), "
            f"ranked with sentinel_utils.apply_mavt_ranking, scored once")
    for m, v, pr in (("tau", r.ens_tau, r.perrun_tau), ("top1", r.ens_top1, r.perrun_top1), ("mae", r.ens_mae, r.perrun_mae)):
        note = f"{base}; per-run mean (number of record) {pr:.3f}, diff {v - pr:+.3f}"
        if r.decision_type == "Overall" and m in ("tau", "top1"):
            w = wi[(wi.model == r.model) & (wi.arch == r.arch) & (wi.metric == ("kendall_tau" if m == "tau" else "top1"))].iloc[0]
            note += f"; scenario-level Wilcoxon vs run-mean p_Holm(8) {w.p_holm:.3g}"
        add(f"D12a_ensemble_{r.arch}_{m}_{r.model}_{r.decision_type}", v, RUNS, "energy_cost..practicality",
            S12, r.model, r.decision_type, note)

# ---- D12b regret ----
rg = pd.read_csv(A / "d12_regret_summary.csv")
for r in rg.itertuples():
    add(f"D12b_regret_{r.arch}_{r.model}_{r.decision_type}", r.mean_regret, RUNS, "gt_mavt_score via pipeline match",
        S12, r.model, r.decision_type,
        f"reference MAVT of reference winner minus reference MAVT of architecture's rank-1 alternative; per run then mean "
        f"of 5; zero-regret share {r.zero_regret_share:.3f} (= Top-1; no reference ties at the top); random-pick regret on "
        f"same scenarios {r.random_pick_regret:.4f}; share of scenario MAVT range lost {r.mean_norm_regret:.3f}")
    add(f"D12b_regret_given_miss_{r.arch}_{r.model}_{r.decision_type}", r.mean_regret_given_miss, RUNS,
        "gt_mavt_score", S12, r.model, r.decision_type,
        f"mean regret over Top-1 misses only; mean misses per run {r.n_miss:.1f}")

# ---- D12c ties ----
ti = pd.read_csv(A / "d12_ties_summary.csv")
s1 = {("A_D", "gemini"): 3.2, ("A_D", "deepseek"): 5.9, ("A_D", "gptoss"): 12.6, ("A_D", "qwen"): 21.3,
      ("A_E", "gemini"): 2.7, ("A_E", "deepseek"): 19.1, ("A_E", "gptoss"): 6.4, ("A_E", "qwen"): 13.9}
for r in ti.itertuples():
    if r.arch == "A_H":
        continue
    if r.decision_type == "Overall":
        pub = s1[(r.arch, r.model)]
        ok = abs(100 * r.any_tie_share - pub) < 0.05
        add(f"D12c_any_tie_{r.arch}_{r.model}", 100 * r.any_tie_share, RUNS, "weighted sum of 4 criteria (1e-9 tol.)",
            S12, r.model, "Overall", f"share (%) of scored scenario-runs where >=2 alternatives share a weighted score; "
            f"supplement says {pub}", "verified" if ok else "mismatch", "paper/supplementary.tex:203",
            "At least two alternatives share a weighted score in ...")
    add(f"D12c_top_tie_{r.arch}_{r.model}_{r.decision_type}", 100 * r.top_tie_share, RUNS, "weighted sum",
        S12, r.model, r.decision_type,
        f"share (%) with >=2 alternatives tied at the TOP weighted score; decided by input order {100 * r.top_tie_input_order_share:.1f}%")
    add(f"D12c_top1_random_tiebreak_{r.arch}_{r.model}_{r.decision_type}", 100 * r.top1_random_tiebreak, RUNS,
        "arch_rank / weighted sum", S12, r.model, r.decision_type,
        f"expected Top-1 (%) if top ties broke uniformly at random; shipped {100 * r.top1_shipped:.1f}, "
        f"difference {r.top1_inflation_vs_random_pp:+.2f} pp; ties-as-miss lower bound {100 * r.top1_ties_as_miss:.1f}")

# ---- position baseline ----
pb = pd.read_csv(A / "d12_position_baseline.csv")
for r in pb[pb.rule == "input_order"].itertuples():
    for m, v in (("tau", r.kendall_tau), ("top1", 100 * r.top1), ("regret", r.mean_regret)):
        add(f"D12c_listed_order_{m}_{r.decision_type}", v, "Scenario Files/TestScenarios.xlsx + Ground Truth/*.xlsx",
            "alternative_1..3 order", "Analysis/pass5/d12_position_baseline.py", "none (no LLM)", r.decision_type,
            "ranking the alternatives in the order the Test sheet lists them; pipeline metric functions; "
            "Top-1 equals the share of scenarios whose reference winner is listed first")

# ---- D12d tokens ----
tk = pd.read_csv(A / "d12_tokens.csv")
t8 = {("gemini", "A_D"): 414.2, ("deepseek", "A_D"): 667.7, ("gptoss", "A_D"): 493.1, ("qwen", "A_D"): 423.6,
      ("gemini", "A_E"): 428.7, ("deepseek", "A_E"): 384.4, ("gptoss", "A_E"): 482.5, ("qwen", "A_E"): 407.6,
      ("gemini", "A_H"): 113.3, ("deepseek", "A_H"): 110.2, ("gptoss", "A_H"): 122.7, ("qwen", "A_H"): 112.4}
for r in tk.itertuples():
    src = f"Output Files <model>/<arch>_results_diagnostics_run_01..05.json"
    add(f"D12d_tokens_in_k_{r.arch}_{r.model}", r.input_tokens_per_run / 1000, src, "total_tokens_input", S12,
        r.model, "Overall", f"mean per run over 5 runs; {r.input_per_call:.0f} per call")
    add(f"D12d_tokens_out_k_{r.arch}_{r.model}", r.output_tokens_per_run / 1000, src, "total_tokens_output", S12,
        r.model, "Overall", f"mean per run over 5 runs; {r.output_per_call:.1f} per call")
    tot = r.total_tokens_per_run / 1000
    add(f"D12d_tokens_total_k_{r.arch}_{r.model}", tot, src, "input+output", S12, r.model, "Overall",
        "check against Table tab:item8", "verified" if abs(tot - t8[(r.model, r.arch)]) < 0.06 else "mismatch",
        "paper/paper_draft_v2.tex tab:item8 (L1034-1036)", f"{t8[(r.model, r.arch)]}k")

pd.DataFrame(rows, columns=COLS).to_csv(OUT, index=False)
print(f"wrote {len(rows)} rows to {OUT}")
