#!/usr/bin/env python3
"""Build paper/pass5/NUMBERS_OF_RECORD.csv for Pass 5 item D2 (A_H numbers).

Reads only the CSVs written by Analysis/pass5/d2_reproduce_ah_numbers.py and the
published Analysis/Hybrid_Ablation workbooks. Writes one file. Per-model rows
only; nothing is pooled across models. ASCII output.
"""
import csv
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P5 = ROOT / "Analysis" / "pass5"
OUT = ROOT / "paper" / "pass5" / "NUMBERS_OF_RECORD.csv"

main = pd.read_csv(P5 / "d2_main_ah_summary.csv").set_index(["model", "decision_type"])
prov = pd.read_csv(P5 / "d2_provenance_repro.csv").set_index(["model", "decision_type"])
eff = pd.read_csv(P5 / "d2_effect_like_for_like.csv").set_index(["model", "decision_type"])
cons = pd.read_csv(P5 / "d2_effect_consensus_basis.csv").set_index(["model", "decision_type"])
sig = pd.read_csv(P5 / "d2_significance_like_for_like.csv")
rec = pd.read_csv(P5 / "d2_gptoss_recovery.csv").set_index(["model", "policy"])
pub_sig = pd.read_excel(ROOT / "Analysis/Hybrid_Ablation/hybrid_ablation_significance.xlsx", sheet_name="pairwise")
perrun = pd.read_csv(P5 / "d2_main_ah_per_run.csv")

PAPER = "paper/paper_draft_v2.tex"
SUPP = "paper/supplementary.tex"
S_MAIN = "Output Files <model>/LLM-Parameterized_Reference_Scoring_results_run_01..05.xlsx"
S_PRM = "paper/per_run_metrics/per_run_metrics_all.csv"
C_MAIN = "paper_pipeline/calculate_per_run_metrics.py (repro: Analysis/pass5/d2_reproduce_ah_numbers.py sec. A)"
S_HAB = "Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx"
C_HAB = "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py (repro: d2_reproduce_ah_numbers.py sec. B)"
S_SIG = "Analysis/Hybrid_Ablation/hybrid_ablation_significance.xlsx"
C_SIG = "Miscellaneous Scripts/validation/test_hybrid_ablation_significance.py"
C_P5 = "Analysis/pass5/d2_reproduce_ah_numbers.py"
B_MAIN = "per-run metric over that run's non-sentinel scenarios, then mean of 5 runs (Set A)"
B_CONS = ("Set B: 5-run CONSENSUS parameters (numeric mean / categorical mode over the runs that "
          "succeeded, from the aggregate LLM-Parameterized_Reference_Scoring_results.xlsx) scored once")
MN = {"deepseek": "DeepSeek", "gemini": "Gemini", "gptoss": "GPT-OSS", "qwen": "Qwen"}
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
DT = ["HVAC", "Appliance", "Shower"]
rows = []


def add(nid, value, where, ctx, src, col, script, model, dt, basis, status):
    rows.append([nid, value, where, ctx, src, col, script, model, dt, basis, status])


def f3(x):
    return f"{x:.3f}"


def pct(x):
    return f"{100 * x:.1f}"


# --- Set A: main A_H numbers, supplement tab:overall_by_model (L1524-1548)
line_tau = {"gemini": 1524, "deepseek": 1524, "gptoss": 1542, "qwen": 1542}
line_top = {"gemini": 1526, "deepseek": 1526, "gptoss": 1544, "qwen": 1544}
line_mae = {"gemini": 1528, "deepseek": 1528, "gptoss": 1546, "qwen": 1546}
line_sr = {"gemini": 1530, "deepseek": 1530, "gptoss": 1548, "qwen": 1548}
for m in MODELS:
    r = main.loc[(m, "Overall")]
    add(f"AH_tau_{m}", f3(r.tau), f"{SUPP}:{line_tau[m]}", f"tab:overall_by_model Kendall tau A_H {MN[m]} {f3(r.tau)} +- {r.tau_sd:.3f}",
        S_MAIN, "per_run_metrics_all.csv kendall_tau (architecture=LLM-Parameterized_Reference_Scoring, Overall)", C_MAIN, m, "Overall", B_MAIN, "verified")
    add(f"AH_top1_{m}", pct(r.top1), f"{SUPP}:{line_top[m]}", f"tab:overall_by_model Top-1 (%) A_H {MN[m]}",
        S_MAIN, "top1_accuracy", C_MAIN, m, "Overall", B_MAIN, "verified")
    add(f"AH_mae_{m}", f3(r.mae), f"{SUPP}:{line_mae[m]}", f"tab:overall_by_model MAE A_H {MN[m]}",
        S_MAIN, "overall_mae", C_MAIN, m, "Overall", B_MAIN, "verified")
    add(f"AH_success_{m}", pct(r.success_rate), f"{SUPP}:{line_sr[m]}", f"tab:overall_by_model Success rate (%) A_H {MN[m]}",
        S_MAIN, "n_scenarios / n_total per run", C_MAIN, m, "Overall",
        f"scored scenario-runs / 975 ({int(r.n_scored)}/{int(r.n_total)})", "verified")

# inclusive rows
for m in MODELS:
    o = perrun[(perrun.model == m) & (perrun.decision_type == "Overall")]
    ti = (o.kendall_tau * o.n_scored / 195).mean()
    t1 = ((o.top1 * o.n_scored + (195 - o.n_scored) / 3) / 195).mean()
    ln = 1525 if m in ("gemini", "deepseek") else 1543
    add(f"AH_tau_inclusive_{m}", f3(ti), f"{SUPP}:{ln}", f"tab:overall_by_model Kendall tau (inclusive) A_H {MN[m]}",
        S_MAIN, "derived: per run sum(tau)/195, failed=0", C_P5, m, "Overall", "failed scenario counted as tau=0; mean of 5 runs", "verified")
    add(f"AH_top1_inclusive_{m}", pct(t1), f"{SUPP}:{ln + 2}", f"tab:overall_by_model Top-1 (inclusive) A_H {MN[m]}",
        S_MAIN, "derived: failed scenario = 1/3", C_P5, m, "Overall", "failed scenario counted as Top-1=1/3; mean of 5 runs", "verified")
add("AH_gptoss_success_weighted_tau_text", "0.790", f"{PAPER}:889", "its 88.0% success rate lowers its success-weighted tau from 0.897 to 0.790",
    S_MAIN, "derived", C_P5, "gptoss", "Overall", "equals inclusive tau (failed=0) = tau x success", "verified")
add("AH_gptoss_success_weighted_top1_text", "84.7", f"{PAPER}:889", "and its Top-1 from 91.7% to 84.7%",
    S_MAIN, "derived", C_P5, "gptoss", "Overall",
    "84.7 is the INCLUSIVE value (failed=1/3); a strictly success-weighted Top-1 (failed=0) is 80.7", "mismatch")

# range quotes in manuscript
for ln, ctx in [(304, "abstract: Kendall's tau=0.880--0.923"),
                (808, "whose LLM extraction reaches tau = 0.880--0.923"),
                (837, "A_H reaches tau=0.880--0.923 and 89.7--93.1% Top-1"),
                (947, "The per-model tau of 0.880--0.923")]:
    add(f"AH_tau_range_L{ln}", "0.880-0.923", f"{PAPER}:{ln}", ctx, S_PRM, "kendall_tau", C_MAIN,
        "qwen (min) / gemini (max)", "Overall", B_MAIN, "verified")
for ln in (808, 837):
    add(f"AH_top1_range_L{ln}", "89.7-93.1", f"{PAPER}:{ln}", "Top-1 of 89.7--93.1%", S_PRM, "top1_accuracy", C_MAIN,
        "qwen (min) / gemini (max)", "Overall", B_MAIN, "verified")
add("AH_table_best_tau", "0.923", f"{PAPER}:795", "A_H (best: Gemini) & 93.1 & +22.9 & 0.923 & +0.310", S_PRM, "kendall_tau", C_MAIN, "gemini", "Overall", B_MAIN, "verified")
add("AH_table_best_dtau_vs_FD", "+0.310", f"{PAPER}:795", "A_H (best: Gemini) delta tau vs fixed default 0.614",
    "Output Files/Baselines/baseline_fixeddefault.xlsx + per-run files", "FD per-scenario tau", C_P5, "gemini", "Overall",
    f"like-for-like (FD on same scenarios) = {eff.loc[('gemini', 'Overall')].effect_vs_fd_like_for_like:+.3f}", "verified")
add("AH_table_worst_tau", "0.880", f"{PAPER}:796", "A_H (worst: Qwen) & 89.7 & +19.5 & 0.880 & +0.266", S_PRM, "kendall_tau", C_MAIN, "qwen", "Overall", B_MAIN, "verified")
add("AH_table_worst_dtau_vs_FD", "+0.266", f"{PAPER}:796", "A_H (worst: Qwen) delta tau vs fixed default",
    "Output Files/Baselines/baseline_fixeddefault.xlsx + per-run files", "FD per-scenario tau", C_P5, "qwen", "Overall",
    f"like-for-like = {eff.loc[('qwen', 'Overall')].effect_vs_fd_like_for_like:+.3f}", "verified")
for m in ("deepseek", "gptoss"):
    add(f"AH_dtau_vs_FD_{m}_not_in_paper", f"{eff.loc[(m, 'Overall')].effect_vs_fd_like_for_like:+.3f}", "not quoted", "",
        "Output Files/Baselines/baseline_fixeddefault.xlsx + per-run files", "FD per-scenario tau", C_P5, m, "Overall",
        f"like-for-like; published-basis (FD over all 195) = {eff.loc[(m, 'Overall')].effect_vs_fd_published_basis:+.3f}", "verified")

# per decision type A_H (Set A), manuscript by-type table L970-977
bt = {("HVAC", "gemini"): (970, "HVAC Best 0.977 (G) 96.6"), ("HVAC", "qwen"): (971, "HVAC Worst 0.881 (Q) 87.4"),
      ("Appliance", "deepseek"): (973, "Appliance Best 0.975 (D) 98.5"), ("Appliance", "qwen"): (974, "Appliance Worst 0.906 (Q) 92.9"),
      ("Shower", "qwen"): (976, "Shower Best 0.851 (Q) 89.0"), ("Shower", "deepseek"): (977, "Shower Worst 0.787 (D, tied with O) 81.0")}
for m in MODELS:
    for dt in DT:
        r = main.loc[(m, dt)]
        where, ctx, st = "not quoted", "", "verified"
        if (dt, m) in bt:
            where, ctx = f"{PAPER}:{bt[(dt, m)][0]}", bt[(dt, m)][1]
        if (dt, m) == ("Shower", "gptoss"):
            where, ctx = f"{PAPER}:977", "tied with O (GPT-OSS) at 0.787"
        add(f"AH_tau_{m}_{dt}", f3(r.tau), where, ctx, S_MAIN, "kendall_tau by decision_type", C_MAIN, m, dt,
            B_MAIN + f"; Top-1 {pct(r.top1)}; success {pct(r.success_rate)}%", st)

# failure counts
fails = {m: int(main.loc[(m, 'Overall')].n_total - main.loc[(m, 'Overall')].n_scored) for m in MODELS}
add("AH_failures_total", str(sum(fails.values())), f"{PAPER}:909", "GPT-OSS accounts for 117 of the 120 A_H failures",
    S_MAIN, "sentinel scenario-runs", C_MAIN, "per model: " + "/".join(f"{MN[m]}={fails[m]}" for m in MODELS), "Overall",
    "count of sentinel scenario-runs over 5 runs; not a pooled metric", "verified")
add("AH_gptoss_failures_HVAC", "117 (all HVAC)", f"{PAPER}:909", "most of them on HVAC scenarios", S_MAIN, "sentinel scenario-runs",
    C_P5, "gptoss", "HVAC", "HVAC scored 233/350 scenario-runs; Appliance and Shower 0 failures. 'most' understates: all 117 are HVAC", "verified")
add("AH_gptoss_failed_all_runs", "1", f"{PAPER}:909", "only one scenario failed in all five runs", S_MAIN, "n_successful_runs==0",
    C_P5, "gptoss", "HVAC", "scenario with no successful run", "verified")

# recovery claim L909
r1 = rec.loc[("gptoss", "first_other_success")]
add("AH_gptoss_recovery_tau", "0.897", f"{PAPER}:909",
    "When we recover each failed scenario from a run in which it succeeded, the reported figures do not change (tau 0.897, Top-1 91.7%).",
    S_HAB + " (per_scenario, arm extracted_per_run)", "kendall_tau", C_P5 + " sec. E", "gptoss", "Overall",
    f"backfill recomputed: tau {r1.tau:.4f}, Top-1 {pct(r1.top1)}% (first other successful run); "
    f"{rec.loc[('gptoss', 'all_success_mean')].tau:.4f} / {pct(rec.loc[('gptoss', 'all_success_mean')].top1)}% (mean of other successful runs). "
    "The quoted 0.897/91.7 are the NON-recovered values; paper_pipeline/generate_paper_results_numbers.py block 'GPTOSS_recovery' "
    "(L298-324) only copies per-run values and implements no recovery", "mismatch")

# --- Set B: provenance table
pl = {"gptoss": 1312, "qwen": 1315, "deepseek": 1318, "gemini": 1321}
for m in MODELS:
    p = prov.loc[(m, "Overall")]
    a = main.loc[(m, "Overall")]
    add(f"PROV_extracted_tau_{m}", f3(p.published_tau), f"{SUPP}:{pl[m]}",
        f"{MN[m]} & LLM-extracted & {f3(p.published_tau)} & {f3(p.published_top1)} & {f3(p.published_mae)}",
        S_HAB, "summary arm=extracted kendall_tau", C_HAB, m, "Overall",
        B_CONS + f"; reproduced exactly ({p.rebuilt_tau:.4f}). Set A value for the same model = {a.tau:.4f}", "mismatch")
    add(f"PROV_extracted_top1_{m}", f3(p.published_top1), f"{SUPP}:{pl[m]}", "Top-1 column", S_HAB, "top1_accuracy", C_HAB, m, "Overall",
        B_CONS + f"; Set A = {a.top1:.4f}", "mismatch")
    add(f"PROV_extracted_mae_{m}", f3(p.published_mae), f"{SUPP}:{pl[m]}", "MAE column", S_HAB, "mae", C_HAB, m, "Overall",
        B_CONS + f"; Set A = {a.mae:.4f}", "mismatch")
    for dt in DT:
        pp = prov.loc[(m, dt)]
        add(f"PROV_extracted_tau_{m}_{dt}", f3(pp.published_tau), "not quoted", "", S_HAB, "per_scenario arm=extracted", C_HAB, m, dt,
            B_CONS + f"; Set A = {main.loc[(m, dt)].tau:.4f}", "verified")
    add(f"PROV_median_{m}", "0.641 / 0.769 / 0.122", f"{SUPP}:{pl[m] + 1}", f"{MN[m]} & Dataset median & 0.641 & 0.769 & 0.122",
        S_HAB, "summary arm=default_params", C_HAB, m, "Overall", "over all 195 scenarios; model-independent", "verified")
add("PROV_gptoss_194of195", "194 of 195", f"{SUPP}:1328", "the extracted condition scored 194 of 195 scenarios for GPT-OSS and 195 for the other three models",
    S_HAB, "summary n_scored arm=extracted", C_HAB, "gptoss", "Overall",
    "true only for the consensus arm (a scenario counts if ANY run succeeded). Per-run basis: 858 of 975 scenario-runs (88.0%), mean 171.6 per run", "mismatch")
add("MEDIAN_tau_text", "0.641", f"{PAPER}:808", "it reaches tau = 0.641", S_HAB, "arm=default_params", C_HAB, "all (model-independent)", "Overall",
    "dataset median over all 195", "verified")
add("MEDIAN_top1_text", "76.9", f"{PAPER}:808", "Top-1 of 76.9%", S_HAB, "arm=default_params", C_HAB, "all (model-independent)", "Overall",
    "dataset median over all 195", "verified")
for dt in DT:
    add(f"MEDIAN_tau_{dt}", f3(eff.loc[('gemini', dt)].med_tau_all), "not quoted", "", S_HAB, "arm=default_params", C_HAB,
        "all (model-independent)", dt, "dataset median condition by decision type", "verified")
add("MEDIAN_tau_gptoss_same_scenarios", f3(eff.loc[('gptoss', 'Overall')].med_tau_same), "not quoted", "", S_HAB, "arm=default_params restricted",
    C_P5, "gptoss", "Overall", "dataset median on the scenarios each GPT-OSS run scored, mean of 5 runs", "verified")
add("FD_tau_overall", "0.614", f"{PAPER}:775", "for an overall tau of 0.614", "Output Files/Baselines/baseline_metrics.csv",
    "FixedDefault Overall_pooled kendall_tau", "Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py", "all (model-independent)", "Overall", "", "verified")
for dt, v, ln in (("HVAC", "0.933", 775), ("Appliance", "0.097", 775), ("Shower", "0.800", 775)):
    add(f"FD_tau_{dt}", v, f"{PAPER}:{ln}", f"fixed default {dt} tau", "Output Files/Baselines/baseline_metrics.csv",
        "FixedDefault kendall_tau", "Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py", "all (model-independent)", dt, "", "verified")

# --- extraction effect
add("EFFECT_range_text", "0.24-0.28", f"{PAPER}:808", "Extraction therefore adds 0.24--0.28 in tau beyond what the calculator provides.",
    S_PRM + " + " + S_HAB, "Set A tau minus 0.641", C_P5 + " sec. C", "qwen (min) / gemini (max)", "Overall",
    "published basis mixes Set A (scenarios each run scored) with the median over all 195; like-for-like range is 0.239-0.300 (GPT-OSS 0.300)", "mismatch")
for m in MODELS:
    e = eff.loc[(m, "Overall")]
    add(f"EFFECT_like_for_like_{m}", f3(e.effect_vs_median_like_for_like), "not quoted", "", S_HAB, "extracted_per_run minus default_params, same scenarios per run",
        C_P5 + " sec. C", m, "Overall",
        f"per run then mean; run range {e.effect_vs_median_like_for_like_run_min:.3f}-{e.effect_vs_median_like_for_like_run_max:.3f}; "
        f"published basis {e.effect_vs_median_published_basis:.3f}; consensus basis {cons.loc[(m, 'Overall')].cons_effect:.3f}; "
        f"Top-1 effect {100 * e.top1_effect_vs_median_like_for_like:.1f} pp", "verified")
    for dt in DT:
        e = eff.loc[(m, dt)]
        s = sig[(sig.model == m) & (sig.metric == f"kendall_tau<{dt}>")]
        ph = s.p_holm_bytype_24.iloc[0] if len(s) else float("nan")
        add(f"EFFECT_like_for_like_{m}_{dt}", f"{e.effect_vs_median_like_for_like:+.3f}", "not quoted", "", S_HAB,
            "extracted_per_run minus default_params", C_P5 + " sec. C/D", m, dt,
            f"ext {e.ext_tau:.3f} vs median {e.med_tau_same:.3f}; Wilcoxon (run-mean) p_Holm(24 by-type tests) = {ph:.3g}", "verified")

# --- significance (published vs like-for-like)
for m in MODELS:
    for met in ("kendall_tau", "top1", "mae"):
        pb = pub_sig[(pub_sig.model == m) & (pub_sig.metric == met)].iloc[0]
        lf = sig[(sig.model == m) & (sig.metric == met)].iloc[0]
        ln = 1332
        add(f"SIG_cliff_{met}_{m}", f"{pb.cliff_delta:.3f}", f"{SUPP}:{ln} and {PAPER}:808",
            "Cliff's delta range quoted in text", S_SIG, "pairwise cliff_delta", C_SIG, m, "Overall",
            f"computed on consensus arm (Set B), p_Holm {pb.p_holm:.2g}, n={int(pb.n_pairs)}. Like-for-like (per-scenario run-mean of per-run arm): "
            f"delta {lf.cliff_delta:.3f} ({lf.cliff_interp}), p_Holm {lf.p_holm_12:.2g}, n={int(lf.n_pairs)}", "mismatch")

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["number_id", "value", "where_in_paper", "quoted_context", "source_file", "source_sheet_or_column",
                "computing_script", "model", "decision_type", "basis_notes", "status"])
    w.writerows(rows)
print(f"wrote {len(rows)} rows to {OUT}")
