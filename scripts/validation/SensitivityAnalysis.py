"""Sensitivity analysis for architecture ranking robustness under weight perturbations."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MISC_DIR = PROJECT_ROOT / "Miscellaneous Scripts"

for p in (str(PROJECT_ROOT), str(MISC_DIR), str(MISC_DIR / "core-automation")):
    if p not in sys.path:
        sys.path.insert(0, p)

import argparse

from model_config import CRITERION_WEIGHTS, MODEL_KEY, MODEL_SPECS, TIE_BREAK_PRIORITY, get_output_folder
from sentinel_utils import _atomic_write_xlsx
from evaluate_architecture_metrics import (
    CRITERIA,
    _build_config,
    build_gt_lookup,
    build_gt_id_lookup,
    filter_failed_scenarios,
    load_architecture,
    load_ground_truth,
    match_scenarios,
    compute_ranking_metrics,
    _rank_with_deterministic_tiebreak,
)
from pathlib import Path

METHOD_DIR = PROJECT_ROOT / "Scoring Logic and Documentation" / "method"
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
ANALYSIS_DIR = PROJECT_ROOT / "Analysis"

# C1: value-function shape parameter sweep (ground-truth side only).
# The calculators use "logarithmic, a=1.5" for comfort and "logarithmic,
# a=1.2" for practicality; alpha = 1.0 is the linear value function.
ALPHA_SWEEP_VALUES = [1.0, 1.2, 1.5, 2.0]
VF_COMFORT_CURRENT_ALPHA = 1.5
VF_PRACTICALITY_CURRENT_ALPHA = 1.2


def _normalize(w: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, v) for v in w.values())
    if total <= 0:
        raise ValueError(f"Degenerate weight vector: {w}")
    return {c: max(0.0, v) / total for c, v in w.items()}


def _load_objective_weights() -> dict[str, dict[str, dict[str, float]]]:
    """Read the weight vectors the objective scripts already computed.

    Returns {method: {scope: {criterion: weight}}} for MEREC and Entropy.
    Implied weights are deliberately excluded: they collapse to corner
    solutions (a single criterion at 1.0), which is a statement about
    within-scenario discrimination rather than a usable weighting, and the
    Appliance fit reports a negative pairwise R-squared.
    """
    out: dict[str, dict[str, dict[str, float]]] = {}

    merec_path = METHOD_DIR / "merec_weights_summary.xlsx"
    if merec_path.exists():
        df = pd.read_excel(merec_path)
        out["merec"] = {
            scope: _normalize(dict(zip(g["criterion"], g["merec_weight"])))
            for scope, g in df.groupby("scope")
        }

    entropy_path = METHOD_DIR / "entropy_weights.xlsx"
    if entropy_path.exists():
        df = pd.read_excel(entropy_path)
        cols = {
            "Overall": "entropy_weight_overall",
            "HVAC": "entropy_weight_hvac",
            "Appliance": "entropy_weight_appliance",
            "Shower": "entropy_weight_shower",
        }
        out["entropy"] = {
            scope: _normalize(dict(zip(df["criterion"], df[col])))
            for scope, col in cols.items()
            if col in df.columns
        }

    return out


def generate_weight_scenarios(baseline: dict[str, float]) -> list[tuple[str, object]]:
    """Baseline, +/-0.05 perturbations, equal weights, and data-derived arms.

    The +/-0.05 arms are retained for continuity, but they are smaller than
    every divergence the objective weight methods report, so they cannot on
    their own establish that the architecture ordering is weight-robust. The
    data-derived arms below reach the region the corpus actually argues for:
    MEREC assigns HVAC comfort 0.663 against a design 0.200, a divergence
    nine times the +/-0.05 step.

    A scenario's weights are either a flat {criterion: weight} vector applied
    to every decision type, or a {decision_type: {criterion: weight}} mapping
    applied per type.
    """
    criteria = list(baseline.keys())
    scenarios: list[tuple[str, object]] = []

    scenarios.append(("baseline", dict(baseline)))

    # +/-0.05 perturbations
    for target in criteria:
        for sign, label in [(+0.05, "+0.05"), (-0.05, "-0.05")]:
            w = dict(baseline)
            w[target] = baseline[target] + sign
            others = [c for c in criteria if c != target]
            redistrib = -sign / len(others)
            for c in others:
                w[c] = baseline[c] + redistrib
            scenarios.append((f"{target[:3]} {label}", _normalize(w)))

    scenarios.append(("equal", {c: 0.25 for c in criteria}))

    # Data-derived arms
    objective = _load_objective_weights()
    for method in ("merec", "entropy"):
        by_scope = objective.get(method)
        if not by_scope:
            print(f"  WARNING: {method} weights not found in {METHOD_DIR}; "
                  f"skipping those arms.")
            continue

        # Each per-type vector applied globally: the stress test.
        for dt in DECISION_TYPES:
            if dt in by_scope:
                scenarios.append((f"{method} {dt.lower()}-vec", by_scope[dt]))

        # Per-type vectors applied to their own decision type: what the
        # benchmark would look like under objective per-type weighting.
        per_type = {dt: by_scope[dt] for dt in DECISION_TYPES if dt in by_scope}
        if len(per_type) == len(DECISION_TYPES):
            scenarios.append((f"{method} per-type", per_type))

    # C7: published per-decision-type vectors from tab:weight_comparison
    # (paper_draft_working.tex), applied to their matching decision type only.
    # MEREC arms: each vector on its own decision type, baseline elsewhere.
    # Entropy arm: all three published vectors applied to their matching types.
    # Rounding in the table makes the entropy rows sum to 0.999-1.001, so each
    # vector is renormalized before use.
    merec_tab = {
        "HVAC": {"energy_cost": 0.138, "environmental": 0.128,
                 "comfort": 0.663, "practicality": 0.071},
        "Appliance": {"energy_cost": 0.208, "environmental": 0.044,
                      "comfort": 0.292, "practicality": 0.456},
        "Shower": {"energy_cost": 0.251, "environmental": 0.245,
                   "comfort": 0.203, "practicality": 0.300},
    }
    entropy_tab = {
        "HVAC": {"energy_cost": 0.336, "environmental": 0.320,
                 "comfort": 0.269, "practicality": 0.074},
        "Appliance": {"energy_cost": 0.193, "environmental": 0.465,
                      "comfort": 0.124, "practicality": 0.218},
        "Shower": {"energy_cost": 0.335, "environmental": 0.316,
                   "comfort": 0.122, "practicality": 0.227},
    }
    for dt in DECISION_TYPES:
        arm = {d: dict(baseline) for d in DECISION_TYPES}
        arm[dt] = _normalize(merec_tab[dt])
        scenarios.append((f"merec {dt.lower()}-type only", arm))
    scenarios.append(("entropy per-type (tab)", {
        dt: _normalize(entropy_tab[dt]) for dt in DECISION_TYPES}))

    return scenarios


def _is_per_type(weights) -> bool:
    return all(isinstance(v, dict) for v in weights.values())


def _weighted_sum(df: pd.DataFrame, prefix: str, weights) -> pd.Series:
    """Weighted criterion sum, supporting a flat vector or one vector per
    decision type."""
    if not _is_per_type(weights):
        return sum(weights[c] * df[f"{prefix}{c}"].astype(float) for c in CRITERIA)

    out = pd.Series(np.nan, index=df.index, dtype=float)
    for dtype, w in weights.items():
        mask = df["decision_type"] == dtype
        if not mask.any():
            continue
        out.loc[mask] = sum(
            w[c] * df.loc[mask, f"{prefix}{c}"].astype(float) for c in CRITERIA
        )
    if out.isna().any():
        missing = sorted(set(df.loc[out.isna(), "decision_type"]))
        raise ValueError(f"No weight vector supplied for decision type(s): {missing}")
    return out


def rerank_with_weights(merged_df: pd.DataFrame, weights) -> pd.DataFrame:
    """Recompute GT and architecture ranks per scenario using the provided weights.

    Ranking uses the SAME deterministic tie-break (TIE_BREAK_PRIORITY, each desc)
    as CalculateMetrics and the ground-truth calculators, so the baseline-weight
    row of this analysis reproduces the headline metrics exactly instead of
    diverging through average-rank tie handling.
    """
    df = merged_df.copy()

    df["_gt_weighted"] = _weighted_sum(df, "gt_", weights)
    df["_arch_weighted"] = _weighted_sum(df, "arch_", weights)

    gt_tiebreak = [f"gt_{c}" for c in TIE_BREAK_PRIORITY]
    arch_tiebreak = [f"arch_{c}" for c in TIE_BREAK_PRIORITY]

    df["gt_rank"] = np.nan
    df["arch_rank"] = np.nan
    for sid, idx in df.groupby("arch_scenario_id").groups.items():
        sub = df.loc[idx]
        df.loc[idx, "gt_rank"] = _rank_with_deterministic_tiebreak(
            sub.rename(columns={"_gt_weighted": "_w"}), "_w", gt_tiebreak
        )
        df.loc[idx, "arch_rank"] = _rank_with_deterministic_tiebreak(
            sub.rename(columns={"_arch_weighted": "_w"}), "_w", arch_tiebreak
        )

    df = df.drop(columns=["_gt_weighted", "_arch_weighted"])
    return df


def metrics_per_run_then_average(frames: list[pd.DataFrame], weights) -> dict:
    """Method A: score each run under `weights`, then average the metrics.

    This is the protocol used for the headline results, so the design-vector row
    of the sensitivity analysis reproduces the main figure exactly. Averaging the
    runs before scoring is a different estimator and is not used.

    Every numeric key returned by compute_ranking_metrics is averaged, so callers
    that read counts (e.g. n_scenarios_evaluated) keep working.
    """
    per_run = [compute_ranking_metrics(rerank_with_weights(f, weights)) for f in frames]
    out = {}
    for k in per_run[0]:
        vals = [m[k] for m in per_run]
        try:
            out[k] = float(np.mean(vals))
        except (TypeError, ValueError):
            out[k] = vals[0]
    return out


def run_sensitivity_analysis(model_key: str = MODEL_KEY) -> pd.DataFrame:
    """Run sensitivity analysis and return per-architecture metrics by weight scenario."""
    print("Sensitivity analysis: MCDA architecture comparison")
    print(f"Model: {model_key}")

    CONFIG = _build_config(model_key)
    OUTPUT_DIR = PROJECT_ROOT / get_output_folder(model_key)

    # 1. Load data
    print("\n[1] Loading ground truth and architectures...")
    gt_by_type = load_ground_truth(CONFIG)
    gt_lookup = build_gt_lookup(gt_by_type)
    gt_id_lookup = build_gt_id_lookup(gt_by_type)

    arch_names = list(CONFIG["architectures"].keys())
    pure_name, rag_name, param_name = arch_names  # Direct_LLM_Scoring, Example-Guided_LLM_Scoring, LLM-Parameterized_Reference_Scoring
    # Per-run-then-average: keep the runs SEPARATE here and average metrics
    # across runs later. Aggregating the runs first (average the scores, then
    # score once) is a different estimator; using it here made the
    # design-vector row disagree with the headline figure by up to 0.104 in
    # Kendall's tau.
    clean_merged: dict[str, list[pd.DataFrame]] = {}
    for name, path in CONFIG["architectures"].items():
        base_path = Path(path)
        run_paths = sorted(base_path.parent.glob(f"{base_path.stem}_run_*.xlsx"))
        sources = list(run_paths) if run_paths else [path]
        frames: list[pd.DataFrame] = []
        for src in sources:
            arch_df = load_architecture(src, name)
            merged, _counts = match_scenarios(gt_lookup, gt_id_lookup, arch_df, name)
            if len(merged) == 0:
                continue
            filtered, n_failed, n_total = filter_failed_scenarios(merged)
            if n_failed:
                print(f"  [{name}] {Path(src).name}: filtered {n_failed}/{n_total} failed scenarios.")
            frames.append(filtered)
        if not frames:
            print(f"  WARNING: No matched data for {name} - skipping.")
            continue
        print(f"  [{name}] {len(frames)} run(s) held separate for per-run metrics.")
        clean_merged[name] = frames

    # 2. Weight scenarios
    weight_scenarios = generate_weight_scenarios(CRITERION_WEIGHTS)
    print(f"\n[2] Running {len(weight_scenarios)} weight scenarios...")

    # 3. Compute metrics for every (scenario, architecture) combination
    results: list[dict] = []

    for scen_name, weights in weight_scenarios:
        for arch_name in arch_names:
            if arch_name not in clean_merged:
                continue
            metrics = metrics_per_run_then_average(clean_merged[arch_name], weights)
            if _is_per_type(weights):
                weights_json = json.dumps(
                    {dt: {c: round(v, 6) for c, v in w.items()}
                     for dt, w in weights.items()}
                )
            else:
                weights_json = json.dumps({c: round(v, 6) for c, v in weights.items()})
            results.append({
                "model": model_key,
                "scenario_name": scen_name,
                "weights_json": weights_json,
                "architecture": arch_name,
                "kendall_tau": metrics["kendall_tau"],
                "spearman_rho": metrics["spearman_rho"],
                "top1_accuracy": metrics["top1_accuracy"],
                "top2_accuracy": metrics["top2_accuracy"],
            })

    results_df = pd.DataFrame(results)

    # 4. Print Kendall tau summary table
    print("\nKendall tau summary table")

    tau_pivot = results_df.pivot_table(
        index="scenario_name",
        columns="architecture",
        values="kendall_tau",
        aggfunc="first",
    )
    scen_order = [s for s, _ in weight_scenarios]
    tau_pivot = tau_pivot.reindex(scen_order)
    # Column order
    col_order = [c for c in arch_names if c in tau_pivot.columns]
    tau_pivot = tau_pivot[col_order]

    header = f"  {'Scenario':<22}" + "".join(f"{c:>10}" for c in col_order)
    print(header)
    print("  " + "-" * (22 + 10 * len(col_order)))
    for scen in scen_order:
        row = f"  {scen:<22}"
        for c in col_order:
            val = tau_pivot.loc[scen, c] if scen in tau_pivot.index else float("nan")
            row += f"{val:>10.4f}" if not (isinstance(val, float) and np.isnan(val)) else f"{'N/A':>10}"
        print(row)

    # 5. Robustness chec
    print(f"\nRobustness check ({param_name} tau > {rag_name} tau > {pure_name} tau)")

    preserved = 0
    for scen in scen_order:
        sub = results_df[results_df["scenario_name"] == scen]
        tau = {row["architecture"]: row["kendall_tau"] for _, row in sub.iterrows()}
        h = tau.get(param_name, float("nan"))
        r = tau.get(rag_name, float("nan"))
        p = tau.get(pure_name, float("nan"))
        ok = (not np.isnan(h)) and (not np.isnan(r)) and (not np.isnan(p)) and (h > r > p)
        preserved += int(ok)
        status = "PRESERVED" if ok else "VIOLATED "
        print(f"  {scen:<22}  {status}   {param_name}={h:.4f}  {rag_name}={r:.4f}  {pure_name}={p:.4f}")

    n_total_scen = len(weight_scenarios)
    print(f"\n  Architecture order ({param_name} > {rag_name} > {pure_name}) preserved in "
          f"{preserved}/{n_total_scen} scenarios")

    # 5b. Between-architecture gaps.
    #
    # Absolute per-architecture tau is the wrong quantity to read off this
    # analysis. Both the reference ranking and the architecture ranking are
    # recomputed with the same perturbed vector, because a MAVT reference IS
    # defined by its weights. A_H's criterion scores come from the same
    # calculator that produced the reference, so the two sides move together
    # and its near-invariance is structural rather than evidence about the
    # weights. The gap between architectures is the quantity the robustness
    # claim actually rests on, and A_E - A_D is the informative one because
    # those scores are produced independently of the reference.
    print("\nBetween-architecture gaps (the weight-robustness evidence)")
    print(f"  {'Scenario':<22}{'A_E - A_D':>12}{'A_H - A_E':>12}{'sign held':>12}")
    print("  " + "-" * 58)
    for scen in scen_order:
        sub = results_df[results_df["scenario_name"] == scen]
        tau = {row["architecture"]: row["kendall_tau"] for _, row in sub.iterrows()}
        ed = tau.get(rag_name, float("nan")) - tau.get(pure_name, float("nan"))
        he = tau.get(param_name, float("nan")) - tau.get(rag_name, float("nan"))
        held = "yes" if (ed > 0 and he > 0) else "NO"
        results_df.loc[results_df["scenario_name"] == scen, "gap_rag_minus_pure"] = ed
        results_df.loc[results_df["scenario_name"] == scen, "gap_param_minus_rag"] = he
        print(f"  {scen:<22}{ed:>+12.4f}{he:>+12.4f}{held:>12}")

    ed_all = results_df.groupby("scenario_name")["gap_rag_minus_pure"].first().dropna()
    if len(ed_all):
        print(f"\n  A_E - A_D gap across {len(ed_all)} weight vectors: "
              f"min {ed_all.min():+.4f}, max {ed_all.max():+.4f}, "
              f"positive in {int((ed_all > 0).sum())}/{len(ed_all)}")

    # 6. Export
    output_path = OUTPUT_DIR / f"sensitivity_analysis_{model_key}.xlsx"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_xlsx(results_df, output_path)
    print(f"\n  Results saved to: {output_path}")

    return results_df


def _load_arch_dfs(CONFIG: dict) -> tuple[dict, list]:
    """Load architecture per-run files into a LIST of arch-side dataframes each.

    The runs are kept separate so metrics can be computed per run and averaged
    (Method A), matching the headline protocol. The arch-side criterion scores
    are identical for every alpha value and weight arm, so they are loaded once
    and reused (zero API calls).
    """
    arch_names = list(CONFIG["architectures"].keys())
    arch_dfs: dict[str, list[pd.DataFrame]] = {}
    for name, path in CONFIG["architectures"].items():
        base_path = Path(path)
        run_paths = sorted(base_path.parent.glob(f"{base_path.stem}_run_*.xlsx"))
        sources = list(run_paths) if run_paths else [path]
        arch_dfs[name] = [load_architecture(src, name) for src in sources]
    return arch_dfs, arch_names


def _load_clean_merged(CONFIG: dict) -> tuple[dict, list]:
    """Load and aggregate architecture runs, match to GT, filter failed
    scenarios. Shared by the C1 alpha sweep and the C7 objective arms."""
    gt_by_type = load_ground_truth(CONFIG)
    gt_lookup = build_gt_lookup(gt_by_type)
    gt_id_lookup = build_gt_id_lookup(gt_by_type)

    arch_dfs, arch_names = _load_arch_dfs(CONFIG)
    clean_merged: dict[str, list[pd.DataFrame]] = {}
    for name, run_dfs in arch_dfs.items():
        frames: list[pd.DataFrame] = []
        for arch_df in run_dfs:
            merged, _counts = match_scenarios(gt_lookup, gt_id_lookup, arch_df, name)
            if len(merged) == 0:
                continue
            filtered, n_failed, n_total = filter_failed_scenarios(merged)
            if n_failed:
                print(f"  [{name}] Filtered {n_failed}/{n_total} failed scenarios.")
            frames.append(filtered)
        if not frames:
            print(f"  WARNING: No matched data for {name} - skipping.")
            continue
        clean_merged[name] = frames
    return clean_merged, arch_names


def _log_value_function(x, alpha: float) -> np.ndarray:
    """u = ln(alpha*x + 1) / ln(alpha + 1), clipped to [0, 1].

    Matches the calculators' logarithmic value function; alpha == 1.0 is the
    linear value function u = x (the sweep definition of alpha = 1.0).
    """
    x = np.asarray(x, dtype=float)
    if alpha == 1.0:
        return np.clip(x, 0.0, 1.0)
    return np.clip(np.log(alpha * x + 1.0) / np.log(alpha + 1.0), 0.0, 1.0)


def _inverse_log_value_function(u, alpha: float) -> np.ndarray:
    """Invert the logarithmic value function: x = (exp(u*ln(alpha+1)) - 1)/alpha.

    The ground-truth score columns store the value-function output, so the
    normalized position within the reference range is recovered before a new
    alpha is applied. alpha == 1.0 inverts the linear function.
    """
    u = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
    if alpha == 1.0:
        return u
    return np.clip((np.exp(u * np.log(alpha + 1.0)) - 1.0) / alpha, 0.0, 1.0)


def _sweep_gt_scores(gt_by_type: dict, alpha: float) -> dict:
    """Return gt_by_type copies whose comfort/practicality scores are
    re-evaluated with value-function shape parameter *alpha*.

    Only the ground-truth side changes; energy_cost and environmental use
    linear value functions in all three calculators and are untouched.
    Scores are rounded to 2dp to mirror the stored GT-file convention.
    """
    out = {}
    for dtype, df in gt_by_type.items():
        df = df.copy()
        # load_ground_truth renames the calculator score columns to gt_*.
        for col, current_a in (
            ("gt_comfort", VF_COMFORT_CURRENT_ALPHA),
            ("gt_practicality", VF_PRACTICALITY_CURRENT_ALPHA),
        ):
            x_norm = _inverse_log_value_function(df[col].astype(float), current_a)
            df[col] = np.round(_log_value_function(x_norm, alpha), 2)
        out[dtype] = df
    return out


def run_alpha_sweep(model_key: str = MODEL_KEY) -> pd.DataFrame:
    """C1: sweep the ground-truth value-function shape parameter alpha.

    Weights are held at CRITERION_WEIGHTS (35/30/20/15); architecture
    criterion scores are untouched. Reports whether the architecture
    ordering (A_H > A_E > A_D) is invariant across alpha values.
    """
    print("\nAlpha sensitivity sweep: ground-truth value-function curvature")
    print(f"Model: {model_key}")

    CONFIG = _build_config(model_key)
    arch_dfs, arch_names = _load_arch_dfs(CONFIG)
    pure_name, rag_name, param_name = arch_names
    baseline_weights = dict(CRITERION_WEIGHTS)

    labels = [("current (a=1.5/1.2)", None)] + [
        (f"alpha={a}", a) for a in ALPHA_SWEEP_VALUES
    ]

    results: list[dict] = []
    for label, alpha in labels:
        gt_by_type = load_ground_truth(CONFIG)
        if alpha is not None:
            gt_by_type = _sweep_gt_scores(gt_by_type, alpha)
        gt_lookup = build_gt_lookup(gt_by_type)
        gt_id_lookup = build_gt_id_lookup(gt_by_type)
        for arch_name in arch_names:
            frames: list[pd.DataFrame] = []
            for arch_df in arch_dfs[arch_name]:
                merged, _counts = match_scenarios(
                    gt_lookup, gt_id_lookup, arch_df, arch_name
                )
                filtered, n_failed, n_total = filter_failed_scenarios(merged)
                if n_failed:
                    print(f"  [{label} / {arch_name}] Filtered {n_failed}/{n_total} "
                          f"failed scenarios.")
                frames.append(filtered)
            metrics = metrics_per_run_then_average(frames, baseline_weights)
            results.append({
                "model": model_key,
                "scenario_name": label,
                "alpha": alpha if alpha is not None else float("nan"),
                "weights_json": json.dumps(
                    {c: round(v, 6) for c, v in baseline_weights.items()}),
                "architecture": arch_name,
                "kendall_tau": metrics["kendall_tau"],
                "spearman_rho": metrics["spearman_rho"],
                "top1_accuracy": metrics["top1_accuracy"],
                "top2_accuracy": metrics["top2_accuracy"],
                "n_scenarios_evaluated": metrics["n_scenarios_evaluated"],
            })

    results_df = pd.DataFrame(results)

    print("\nKendall tau by alpha (weights held at baseline)")
    tau_pivot = results_df.pivot_table(
        index="scenario_name", columns="architecture",
        values="kendall_tau", aggfunc="first")
    tau_pivot = tau_pivot.reindex([l for l, _ in labels])
    tau_pivot = tau_pivot[[c for c in arch_names if c in tau_pivot.columns]]
    print(tau_pivot.round(4).to_string())

    print("\nTop-1 accuracy by alpha")
    top1_pivot = results_df.pivot_table(
        index="scenario_name", columns="architecture",
        values="top1_accuracy", aggfunc="first")
    top1_pivot = top1_pivot.reindex([l for l, _ in labels])
    top1_pivot = top1_pivot[[c for c in arch_names if c in top1_pivot.columns]]
    print(top1_pivot.round(4).to_string())

    print("\nArchitecture ordering verdict (A_H > A_E > A_D)")
    order_rows = []
    for label, _ in labels:
        sub = results_df[results_df["scenario_name"] == label]
        tau = {r["architecture"]: r["kendall_tau"] for _, r in sub.iterrows()}
        top1 = {r["architecture"]: r["top1_accuracy"] for _, r in sub.iterrows()}
        ok_tau = tau.get(param_name) > tau.get(rag_name) > tau.get(pure_name)
        ok_top1 = top1.get(param_name) > top1.get(rag_name) > top1.get(pure_name)
        order_rows.append({
            "scenario_name": label,
            "tau_verdict": "PRESERVED" if ok_tau else "VIOLATED",
            "top1_verdict": "PRESERVED" if ok_top1 else "VIOLATED",
            "tau_ah": tau.get(param_name), "tau_ae": tau.get(rag_name),
            "tau_ad": tau.get(pure_name),
            "top1_ah": top1.get(param_name), "top1_ae": top1.get(rag_name),
            "top1_ad": top1.get(pure_name),
        })
        print(f"  {label:<20} tau: {'PRESERVED' if ok_tau else 'VIOLATED':<10} "
              f"top1: {'PRESERVED' if ok_top1 else 'VIOLATED'}")
    order_df = pd.DataFrame(order_rows)
    n_alpha = len(ALPHA_SWEEP_VALUES)
    sweep = order_df[order_df["scenario_name"].isin(
        [f"alpha={a}" for a in ALPHA_SWEEP_VALUES])]
    print(f"\n  A_H > A_E > A_D by tau preserved in {int((sweep['tau_verdict'] == 'PRESERVED').sum())}"
          f"/{n_alpha} alpha values; by top1 in "
          f"{int((sweep['top1_verdict'] == 'PRESERVED').sum())}/{n_alpha}")

    output_path = ANALYSIS_DIR / f"Sensitivity_alpha_sweep_{model_key}.xlsx"
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_xlsx(results_df, output_path)
    print(f"\n  Results saved to: {output_path}")

    return results_df


def run_objective_arms_analysis(model_key: str = MODEL_KEY) -> pd.DataFrame:
    """C7: MEREC/Entropy per-decision-type weight arms.

    Three MEREC arms apply one published per-type vector to its own decision
    type only (baseline elsewhere); the published Entropy per-type set is a
    fourth arm. The disk-derived full per-type arms run alongside for
    comparison. Reports whether A_E > A_D survives under each arm.
    """
    print("\nObjective per-decision-type weight arms (MEREC/Entropy)")
    print(f"Model: {model_key}")

    CONFIG = _build_config(model_key)
    clean_merged, arch_names = _load_clean_merged(CONFIG)
    pure_name, rag_name, param_name = arch_names

    weight_scenarios = generate_weight_scenarios(CRITERION_WEIGHTS)
    arm_names = [
        "merec hvac-type only",
        "merec appliance-type only",
        "merec shower-type only",
        "entropy per-type (tab)",
        "merec per-type",
        "entropy per-type",
    ]
    print(f"\n[1] Running {len(arm_names)} objective arms...")

    results: list[dict] = []
    for scen_name, weights in weight_scenarios:
        if scen_name not in arm_names:
            continue
        for arch_name in arch_names:
            if arch_name not in clean_merged:
                continue
            metrics = metrics_per_run_then_average(clean_merged[arch_name], weights)
            weights_json = json.dumps(
                {dt: {c: round(v, 6) for c, v in w.items()}
                 for dt, w in weights.items()})
            results.append({
                "model": model_key,
                "scenario_name": scen_name,
                "weights_json": weights_json,
                "architecture": arch_name,
                "kendall_tau": metrics["kendall_tau"],
                "spearman_rho": metrics["spearman_rho"],
                "top1_accuracy": metrics["top1_accuracy"],
                "top2_accuracy": metrics["top2_accuracy"],
            })

    results_df = pd.DataFrame(results)

    print("\nKendall tau summary table (objective arms)")
    tau_pivot = results_df.pivot_table(
        index="scenario_name", columns="architecture",
        values="kendall_tau", aggfunc="first")
    tau_pivot = tau_pivot.reindex(arm_names)
    tau_pivot = tau_pivot[[c for c in arch_names if c in tau_pivot.columns]]
    print(tau_pivot.round(4).to_string())

    print("\nA_E vs A_D verdict per arm")
    print(f"  {'Scenario':<24}{'A_E - A_D':>12}{'A_H':>10}{'A_E > A_D':>12}")
    print("  " + "-" * 58)
    for scen in arm_names:
        sub = results_df[results_df["scenario_name"] == scen]
        tau = {r["architecture"]: r["kendall_tau"] for _, r in sub.iterrows()}
        ed = tau.get(rag_name, float("nan")) - tau.get(pure_name, float("nan"))
        ah = tau.get(param_name, float("nan"))
        held = "YES" if ed > 0 else "NO"
        results_df.loc[results_df["scenario_name"] == scen, "gap_ae_minus_ad"] = ed
        results_df.loc[results_df["scenario_name"] == scen, "tau_ah"] = ah
        print(f"  {scen:<24}{ed:>+12.4f}{ah:>10.4f}{held:>12}")

    output_path = ANALYSIS_DIR / f"Sensitivity_merec_entropy_arms_{model_key}.xlsx"
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_xlsx(results_df, output_path)
    print(f"\n  Results saved to: {output_path}")

    return results_df


def main():
    parser = argparse.ArgumentParser(
        description="Weight-perturbation sensitivity analysis"
    )
    parser.add_argument("--model", choices=list(MODEL_SPECS.keys()), default=None)
    parser.add_argument("--all-models", action="store_true",
                        help="Run every model and write a pooled workbook. The "
                             "four-model table in the paper needs this; it was "
                             "previously produced by editing model_config.py.")
    parser.add_argument("--alpha-sweep", action="store_true",
                        help="C1: sweep the ground-truth value-function shape "
                             "parameter alpha and write one workbook per model, "
                             "Analysis/Sensitivity_alpha_sweep_<model>.xlsx. "
                             "Never an unsuffixed pooled file.")
    parser.add_argument("--objective-arms", action="store_true",
                        help="C7: run the MEREC/Entropy per-decision-type arms "
                             "and write one workbook per model, Analysis/"
                             "Sensitivity_merec_entropy_arms_<model>.xlsx. "
                             "Never an unsuffixed pooled file.")
    args = parser.parse_args()

    if args.alpha_sweep or args.objective_arms:
        if args.all_models:
            models = list(MODEL_SPECS.keys())
        elif args.model:
            models = [args.model]
        else:
            models = [MODEL_KEY]
        for mk in models:
            if args.alpha_sweep:
                run_alpha_sweep(mk)
            if args.objective_arms:
                run_objective_arms_analysis(mk)
        return

    if args.all_models:
        models = list(MODEL_SPECS.keys())
    elif args.model:
        models = [args.model]
    else:
        models = [MODEL_KEY]

    frames = []
    for mk in models:
        print("\n" + "=" * 70)
        frames.append(run_sensitivity_analysis(mk))

    if args.all_models and frames:
        pooled = pd.concat(frames, ignore_index=True)
        pooled_path = PROJECT_ROOT / "paper" / "sensitivity_analysis_all.xlsx"
        pooled_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_xlsx(pooled, pooled_path)
        pooled.to_csv(pooled_path.with_suffix(".csv"), index=False)
        print(f"\n  Pooled results saved to: {pooled_path}")

        print("\n" + "=" * 70)
        print("MEAN KENDALL TAU ACROSS MODELS, BY WEIGHT VECTOR")
        print("=" * 70)
        piv = pooled.pivot_table(index="scenario_name", columns="architecture",
                                 values="kendall_tau", aggfunc="mean")
        print(piv.round(4).to_string())


if __name__ == "__main__":
    main()
