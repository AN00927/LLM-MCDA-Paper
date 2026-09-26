"""B60 verification: per-scenario Kendall tau must take only {-1, -1/3, 1/3, 1}
once ties are broken by TIE_BREAK_PRIORITY, for the three ablation scripts
P3 was asked to check (prompt, RAG, position-bias).

Read-only on existing outputs. Writes its findings to this same directory.
No API calls.

Usage: python Analysis/rerun_prep/infra/verify_b60_tiebreak.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import apply_mavt_ranking, SENTINEL_VALUE, SENTINEL_FLOAT  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
ALLOWED = {-1.0, -1 / 3, 1 / 3, 1.0}


def _closest_allowed(t):
    return min(ALLOWED, key=lambda a: abs(a - t))


def check_rag_ablation():
    """Recompute tau from Analysis/RAG_Ablation/rag_ablation_results.xlsx using
    apply_mavt_ranking's tie-break on the stored per-criterion prediction
    scores, and the ground truth's own stored rank. This is real historical
    LLM output, not synthetic data.
    """
    path = PROJECT_ROOT / "Analysis" / "RAG_Ablation" / "rag_ablation_results.xlsx"
    lines = ["## RAG ablation (Analysis/RAG_Ablation/rag_ablation_results.xlsx)", ""]
    if not path.exists():
        lines.append("File not found; skipped.")
        return lines

    df = pd.read_excel(path)
    n_changed_rank = 0
    n_alt_rows = 0
    taus_old = []
    taus_new = []

    group_cols = ["model_key", "ablation_id", "source_scenario_id"]
    for _, g in df.groupby(group_cols):
        if len(g) < 2:
            continue
        # Old (buggy) tau, as stored -- tau_b on raw weighted_score / mavt_score.
        old_pred = g["pred_weighted_score"].astype(float).values
        old_gt = g["gt_mavt_score"].astype(float).values
        valid_old = np.isfinite(old_pred) & np.isfinite(old_gt) & (old_pred != SENTINEL_FLOAT)
        if valid_old.sum() >= 2 and len(set(old_pred[valid_old])) > 1 and len(set(old_gt[valid_old])) > 1:
            taus_old.append(float(kendalltau(old_pred[valid_old], old_gt[valid_old]).statistic))

        # New tau: predicted ranks re-derived via apply_mavt_ranking (TIE_BREAK_PRIORITY),
        # ground-truth ranks taken from the stored "gt_rank" column (already the GT
        # calculator's own apply_mavt_ranking output).
        mavt_input = []
        for _, row in g.iterrows():
            mavt_input.append({
                "alternative": row["alternative"],
                "energy_cost": row["pred_energy_cost"],
                "environmental": row["pred_environmental"],
                "comfort": row["pred_comfort"],
                "practicality": row["pred_practicality"],
            })
        new_ranks = apply_mavt_ranking(mavt_input)["ranks"]
        n_alt_rows += len(g)
        for old_r, new_r in zip(g["pred_rank"].astype(float).values, new_ranks):
            if old_r != SENTINEL_VALUE and new_r != SENTINEL_VALUE and int(old_r) != int(new_r):
                n_changed_rank += 1

        gt_ranks = g["gt_rank"].astype(float).values
        valid_new = np.array([r != SENTINEL_VALUE for r in new_ranks]) & np.isfinite(gt_ranks) & (gt_ranks != SENTINEL_VALUE)
        new_ranks_arr = np.array(new_ranks, dtype=float)
        if valid_new.sum() >= 2 and len(set(new_ranks_arr[valid_new])) > 1 and len(set(gt_ranks[valid_new])) > 1:
            taus_new.append(float(kendalltau(new_ranks_arr[valid_new], gt_ranks[valid_new]).statistic))

    taus_old = np.array(taus_old)
    taus_new = np.array(taus_new)
    off_set_old = sorted({round(t, 6) for t in taus_old if _closest_allowed(t) != round(t, 10) and
                          not any(abs(t - a) < 1e-9 for a in ALLOWED)})
    off_set_new = sorted({round(t, 6) for t in taus_new if not any(abs(t - a) < 1e-9 for a in ALLOWED)})

    lines.append(f"Per-alternative rows examined: {n_alt_rows}")
    lines.append(f"Predicted ranks changed by the TIE_BREAK_PRIORITY fix: {n_changed_rank}")
    lines.append(f"Scenario-cells with an old (stored) tau value: {len(taus_old)}")
    lines.append(f"  old tau values outside {{-1,-1/3,1/3,1}}: {len(off_set_old)} "
                f"(example values: {off_set_old[:8]})")
    lines.append(f"Scenario-cells with a new (rank-based) tau value: {len(taus_new)}")
    lines.append(f"  new tau values outside {{-1,-1/3,1/3,1}}: {len(off_set_new)} "
                f"(should be 0; values if any: {off_set_new[:8]})")
    return lines


def check_position_bias():
    """Position-bias-control.py drives the real architecture's run_scenario
    (which calls the real apply_mavt_ranking) and reuses the real
    paper_pipeline/calculate_per_run_metrics.py for tau -- both already use
    TIE_BREAK_PRIORITY, so no B60 fix was needed there. Confirmed here by
    recomputing tau directly from each model's stored per-run "rank" column
    (already the tie-broken rank apply_mavt_ranking assigned at collection time).
    """
    lines = ["", "## Position-bias control (per-model Output Files*/position_bias/*_reversed_run_01.xlsx)", ""]
    gt_files = {
        "HVAC": PROJECT_ROOT / "Ground Truth" / "ground_truth_hvac.xlsx",
        "Appliance": PROJECT_ROOT / "Ground Truth" / "ground_truth_appliance.xlsx",
        "Shower": PROJECT_ROOT / "Ground Truth" / "ground_truth_shower.xlsx",
    }
    gt_cache = {dt: pd.read_excel(p) for dt, p in gt_files.items() if p.exists()}

    model_folders = [d for d in PROJECT_ROOT.glob("Output Files*") if d.is_dir()]
    total_off = 0
    total_scenarios = 0
    for folder in model_folders:
        f = folder / "position_bias" / "Direct_LLM_Scoring_reversed_run_01.xlsx"
        if not f.exists():
            continue
        df = pd.read_excel(f)
        for sid, g in df.groupby("scenario_id"):
            if len(g) < 2:
                continue
            dtype = g["decision_type"].iloc[0]
            gt = gt_cache.get(dtype)
            if gt is None:
                continue
            cand = gt[(gt["question"].astype(str).str.strip() == str(g["question"].iloc[0]).strip()) &
                     (gt["location"].astype(str).str.strip() == str(g["location"].iloc[0]).strip())]
            alts = set(g["alternative"].astype(str))
            cand = cand[cand["alternative"].astype(str).isin(alts)]
            if cand.empty:
                continue
            arch_ranks = g.set_index("alternative")["rank"].astype(float)
            gt_ranks = cand.set_index("alternative")["rank"].astype(float)
            common = [a for a in arch_ranks.index if a in gt_ranks.index]
            if len(common) < 2:
                continue
            ar = arch_ranks.loc[common].values
            gr = gt_ranks.loc[common].values
            if SENTINEL_VALUE in ar or len(set(ar)) < 2 or len(set(gr)) < 2:
                continue
            tau = float(kendalltau(ar, gr).statistic)
            total_scenarios += 1
            if not any(abs(tau - a) < 1e-9 for a in ALLOWED):
                total_off += 1
        lines.append(f"{folder.name}: checked")
    lines.append(f"Scenarios checked across models: {total_scenarios}")
    lines.append(f"Tau values outside {{-1,-1/3,1/3,1}}: {total_off} (expected 0)")
    return lines


def check_prompt_ablation():
    """The shipped Analysis/Prompt_Ablation/*.xlsx cells only ever stored the
    aggregate kendall_tau per scenario, never the per-alternative scores that
    produced it (confirmed: cell xlsx columns have no per-criterion or rank
    columns). So the old bug (tau_b on raw scores) can be shown directly from
    those files, but the fixed code path cannot be re-run against them --
    there is nothing to feed it. Instead this exercises the actual patched
    function with a small set of constructed cases, including a tied-score
    case, to show it can only produce the four canonical values.
    """
    lines = ["", "## Prompt ablation", ""]
    old_path = PROJECT_ROOT / "Analysis" / "Prompt_Ablation" / "cell_control_AD_deepseek_run_01.xlsx"
    if old_path.exists():
        df = pd.read_excel(old_path)
        taus = df["kendall_tau"].dropna().values
        off = sorted({round(t, 6) for t in taus if not any(abs(t - a) < 1e-9 for a in ALLOWED)})
        lines.append(f"Historical file {old_path.name}: {len(taus)} scenario tau values stored, "
                    f"{len(off)} distinct values outside " + "{-1,-1/3,1/3,1}" +
                    f" (confirms the pre-fix bug was real): {off[:8]}")
        lines.append("This file has no per-alternative score or rank columns, so the fixed "
                    "code cannot be re-run against it (nothing to feed it). Verified instead "
                    "by exercising the patched scenario_metrics() directly below.")
    else:
        lines.append("No historical cell file found to demonstrate the old bug.")

    import importlib.util
    mod_path = PROJECT_ROOT / "Miscellaneous Scripts" / "experiments" / "run_prompt_ablation_experiments.py"
    spec = importlib.util.spec_from_file_location("prompt_ablation_verify", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cases = []
    # Case A: no ties -- ordinary distinct scores both sides.
    cases.append({
        "scored": [{"alternative": "a", "energy_cost": 0.9, "environmental": 0.8, "comfort": 0.7, "practicality": 0.6},
                   {"alternative": "b", "energy_cost": 0.5, "environmental": 0.5, "comfort": 0.5, "practicality": 0.5},
                   {"alternative": "c", "energy_cost": 0.1, "environmental": 0.2, "comfort": 0.3, "practicality": 0.4}],
        "ref": {"mavt_by_alt": {"a": 0.5, "b": 0.9, "c": 0.1},
                "rank_by_alt": {"a": 2, "b": 1, "c": 3}},
    })
    # Case B: predicted weighted-score TIE between "a" and "b", computed exactly
    # (not rounded) so it is a genuine float tie -- the exact condition that
    # used to push tau_b to values like 0.5/0/0.816 instead of the canonical
    # set. ec_b is solved so 0.30*ec_b + 0.35*0.5 == 0.30*0.5 + 0.35*0.6 (comfort
    # and practicality equal on both sides). TIE_BREAK_PRIORITY (environmental
    # first) must then rank "a" (env 0.6) above "b" (env 0.5) despite the tie.
    ec_b = 0.5 + (0.35 / 0.30) * (0.6 - 0.5)
    ws_a = 0.30 * 0.5 + 0.35 * 0.6 + 0.20 * 0.5 + 0.15 * 0.5
    ws_b = 0.30 * ec_b + 0.35 * 0.5 + 0.20 * 0.5 + 0.15 * 0.5
    assert ws_a == ws_b, f"test case B is not an exact tie: {ws_a} != {ws_b}"
    cases.append({
        "scored": [{"alternative": "a", "energy_cost": 0.5, "environmental": 0.6, "comfort": 0.5, "practicality": 0.5},
                   {"alternative": "b", "energy_cost": ec_b, "environmental": 0.5, "comfort": 0.5, "practicality": 0.5},
                   {"alternative": "c", "energy_cost": 0.1, "environmental": 0.1, "comfort": 0.1, "practicality": 0.1}],
        "ref": {"mavt_by_alt": {"a": 0.5, "b": 0.9, "c": 0.1},
                "rank_by_alt": {"a": 2, "b": 1, "c": 3}},
    })

    taus = []
    for case in cases:
        result = {"scored": case["scored"], "ranking": mod.apply_mavt_ranking(case["scored"])}
        m = mod.scenario_metrics(result, case["ref"])
        taus.append(m["kendall_tau"])
    off = [t for t in taus if not (np.isnan(t) or any(abs(t - a) < 1e-9 for a in ALLOWED))]
    lines.append(f"Patched scenario_metrics() on {len(cases)} constructed cases "
                f"(one with a genuine predicted weighted_score tie): tau values = {taus}")
    lines.append(f"Values outside " + "{-1,-1/3,1/3,1}" + f": {off} (expected empty list)")
    return lines


def main():
    report = ["# B60 tie-break verification", ""]
    report += check_rag_ablation()
    report += check_position_bias()
    report += check_prompt_ablation()
    text = "\n".join(report)
    print(text)
    (OUT_DIR / "b60_tiebreak_verification.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
