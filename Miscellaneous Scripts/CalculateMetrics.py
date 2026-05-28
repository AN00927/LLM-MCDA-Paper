#!/usr/bin/env python3
"""
calculate_metrics.py - Metrics evaluation for MCDA architecture comparison
Science Fair Project: LLM-assisted MCDA for Household Emissions Optimization

Compares Pure Prompting, RAG-Enhanced, and Hybrid architectures against
physics-based ground truth using MAVT scoring across HVAC, Appliance,
and Shower decision scenarios.
"""

import pandas as pd
import numpy as np
from scipy import stats
import re
import warnings
import sys
from pathlib import Path
from collections import defaultdict

warnings.filterwarnings("default")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import get_output_folder, MODEL_KEY, CRITERION_WEIGHTS
from sentinel_utils import _atomic_write_xlsx, read_table_clean

GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"
OUTPUT_DIR = PROJECT_ROOT / get_output_folder()

CONFIG = {
    "ground_truth": {
        "HVAC": str(GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx"),
        "Appliance": str(GROUND_TRUTH_DIR / "ground_truth_appliance.xlsx"),
        "Shower": str(GROUND_TRUTH_DIR / "ground_truth_shower.xlsx"),
    },
    "architectures": {
        "Pure": str(OUTPUT_DIR / "pure_prompting_results.xlsx"),
        "RAG": str(OUTPUT_DIR / "rag_results.xlsx"),
        "Hybrid": str(OUTPUT_DIR / "hybrid_results.xlsx"),
    },
    "output_csv": str(OUTPUT_DIR / f"metrics_summary_{MODEL_KEY}.xlsx"),
    "gt_score_cols": {
        "energy_cost": "energy_cost_score",
        "environmental": "environmental_score",
        "comfort": "comfort_score",
        "practicality": "practicality_score",
    },
    "arch_score_cols": {
        "energy_cost": "energy_cost",
        "environmental": "environmental",
        "comfort": "comfort",
        "practicality": "practicality",
    },
}

CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]
FAIL_SENTINEL = 1928

# Scenario matching uses (question, location) content keys only. Strict
# (decision_type, scenario_id) lookup is disabled because architecture
# scenario_ids are assigned from TestScenarios while GT tables number
# independently by domain, so those ID namespaces do not align.
#
# Architecture *_results files are not used here. This script
# re-aggregates per-run outputs via aggregate_run_files and serves as the
# source for reported metrics.

_STRICT_ID_MATCH_ENABLED = False

# Secondary criterion priority used when weighted scores tie.
TIE_BREAK_PRIORITY = ["environmental", "energy_cost", "comfort", "practicality"]


def _rank_with_deterministic_tiebreak(scores_df, weighted_col, tiebreak_cols, log_prefix=""):
    """Rank rows by `weighted_col` desc with deterministic tie-breaking.

    Returns a pd.Series of integer ranks aligned to scores_df.index. Ties on
    weighted_score are broken by `tiebreak_cols` (each desc, in order). When
    ties on weighted_score are detected, emits a UserWarning so reviewers can
    inspect cases where the tie-break rule changed the outcome.
    """
    df = scores_df.copy()
    if df[weighted_col].duplicated().any():
        tied_groups = df.groupby(weighted_col).size()
        n_tied = (tied_groups > 1).sum()
        warnings.warn(
            f"{log_prefix}weighted_score ties detected for {n_tied} group(s); "
            f"applying deterministic tie-break by {tiebreak_cols} (each desc).",
            UserWarning, stacklevel=2,
        )
    sort_cols = [weighted_col] + tiebreak_cols
    df_sorted = df.sort_values(sort_cols, ascending=[False] * len(sort_cols), kind="mergesort")
    ranks = pd.Series(range(1, len(df_sorted) + 1), index=df_sorted.index, dtype=int)
    return ranks.reindex(df.index)


def _to_float_or_nan(val):
    """Coerce a value to float; return NaN on any failure (covers strings,
    None, empty, '1928', 'FAILED'). Used by D6 type-safe sentinel checks."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return float("nan")


def is_failed_row(row):
    """Check if a row has the 1928 failure sentinel in any score column.

    D6 fix: coerce the value via a tolerant helper before comparing — a string
    "1928" should still register as a sentinel, not silently leak through.
    """
    for c in CRITERIA:
        val = _to_float_or_nan(row.get(f"arch_{c}", np.nan))
        if val == FAIL_SENTINEL:
            return True
    return False


def filter_failed_scenarios(merged_df):
    """Remove all rows for scenarios that contain any 1928 sentinel values.
    Returns (clean_df, n_failed_scenarios, n_total_scenarios)."""
    failed_sids = set()
    for sid in merged_df["arch_scenario_id"].unique():
        sc = merged_df[merged_df["arch_scenario_id"] == sid]
        if sc.apply(is_failed_row, axis=1).any():
            failed_sids.add(sid)

    n_total = merged_df["arch_scenario_id"].nunique()
    n_failed = len(failed_sids)
    clean_df = merged_df[~merged_df["arch_scenario_id"].isin(failed_sids)]
    return clean_df, n_failed, n_total


def extract_time_from_alt(alt_str):
    """Extract time pattern from alternative string.
    Handles: '2:00 PM', 'Run dishwasher at 2:00 PM', '4PM', '1AM'."""
    alt_str = str(alt_str).strip()
    # Try the full time format first: '2:00 PM'
    match = re.search(r'(\d{1,2}:\d{2}\s*[AaPp][Mm])', alt_str)
    if match:
        return match.group(1).strip().upper()
    # Then try the short version: '4PM', '1AM'\
    match = re.search(r'(\d{1,2})\s*([AaPp][Mm])', alt_str)
    if match:
        hour = match.group(1)
        ampm = match.group(2).upper()
        return f"{hour}:00 {ampm}"
    return alt_str.strip().upper()
def normalize_alternative(alt, decision_type):
    """Normalize alternative values for cross-file matching."""
    alt = str(alt).strip()
    if decision_type == "Appliance":
        return extract_time_from_alt(alt)
    if decision_type == "HVAC":
        alt_lower = alt.lower()
        if "off" in alt_lower:
            match = re.search(r'(\d+(?:\.\d+)?)', alt_lower)
            if match:
                return f"off_{match.group(1)}"
            return "off"
        try:
            return str(int(float(alt)))
        except ValueError:
            return alt
    if decision_type == "Shower":
        try:
            value = float(alt)
            if value.is_integer():
                return str(int(value))
            return str(value)
        except ValueError:
            return alt
    return alt


def load_ground_truth(config):
    """Load the GT files separately by decision type (IDs overlap across types)."""
    gt_by_type = {}

    for dtype, filepath in config["ground_truth"].items():
        df = read_table_clean(filepath)
        df["decision_type"] = dtype

        if "description" in df.columns and "question" not in df.columns:
            df = df.rename(columns={"description": "question"})

        rename_map = {}
        for criterion, gt_col in config["gt_score_cols"].items():
            if gt_col in df.columns:
                rename_map[gt_col] = f"gt_{criterion}"
        df = df.rename(columns=rename_map)

        if "rank" in df.columns:
            df = df.rename(columns={"rank": "gt_rank"})
        if "mavt_score" in df.columns:
            df = df.rename(columns={"mavt_score": "gt_mavt_score"})

        df["question"] = df["question"].str.strip()
        df["location"] = df["location"].str.strip()
        df["alternative"] = df["alternative"].astype(str).str.strip()

        gt_by_type[dtype] = df

    return gt_by_type

def load_architecture(source, arch_name):
    """Load an architecture results file or dataframe."""
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    else:
        df = read_table_clean(source)
    df["architecture"] = arch_name
    df["question"] = df["question"].str.strip()
    df["location"] = df["location"].str.strip()
    df["alternative"] = df["alternative"].astype(str).str.strip()

    rename_map = {}
    for criterion in CRITERIA:
        col = CONFIG["arch_score_cols"][criterion]
        if col in df.columns:
            rename_map[col] = f"arch_{criterion}"
    df = df.rename(columns=rename_map)

    if "rank" in df.columns:
        df = df.rename(columns={"rank": "arch_rank"})
    if "weighted_score" in df.columns:
        df = df.rename(columns={"weighted_score": "arch_weighted_score"})

    return df


def _coerce_score_columns(df, score_cols):
    for c in score_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def aggregate_run_files(run_paths):
    """Aggregate multi-run results into a single dataframe with mean/std scores.

    The returned dataframe includes n_runs, n_successful_runs, and n_failed_runs
    so downstream callers can report on run coverage without re-counting.
    When std is NaN because only one run was aggregated, it is annotated.
    """
    run_dfs = []
    for p in run_paths:
        run_dfs.append(read_table_clean(p))
    n_readable = len(run_dfs)
    combined = pd.concat(run_dfs, ignore_index=True)

    score_cols = [
        CONFIG["arch_score_cols"]["energy_cost"],
        CONFIG["arch_score_cols"]["environmental"],
        CONFIG["arch_score_cols"]["comfort"],
        CONFIG["arch_score_cols"]["practicality"],
    ]
    combined = _coerce_score_columns(combined, score_cols)

    # Treat sentinel rows as NaN for averaging
    for c in score_cols:
        combined.loc[combined[c] == FAIL_SENTINEL, c] = np.nan

    group_keys = ["scenario_id", "decision_type", "alternative"]
    meta_cols = [c for c in [
        "question", "location", "outdoor_temp", "appliance_age", "flow_rate",
        "calculator", "extraction_failed", "gt_calculation_failed"
    ] if c in combined.columns]

    # Count successful (non-NaN) runs per (scenario, alternative)
    n_valid_runs = combined.groupby(group_keys)[score_cols[0]].apply(
        lambda s: s.notna().sum()
    ).reset_index(name="n_successful_runs")

    avg_scores = combined.groupby(group_keys, as_index=False)[score_cols].mean()
    std_scores = combined.groupby(group_keys, as_index=False)[score_cols].std()
    avg_meta = combined.groupby(group_keys, as_index=False)[meta_cols].first() if meta_cols else None

    aggregated = avg_scores
    if avg_meta is not None:
        aggregated = aggregated.merge(avg_meta, on=group_keys)
    aggregated = aggregated.merge(n_valid_runs, on=group_keys)
    aggregated["n_runs"] = n_readable
    aggregated["n_failed_runs"] = aggregated["n_runs"] - aggregated["n_successful_runs"]

    std_scores = std_scores.rename(columns={c: f"{c}_std" for c in score_cols})
    aggregated = aggregated.merge(std_scores, on=group_keys)

    # If N=1, std is undefined — annotate rather than leave unexplained NaN
    if n_readable == 1:
        warnings.warn(
            "Only 1 run file aggregated — std columns are NaN (undefined for N=1).",
            UserWarning, stacklevel=2
        )

    # Fill NaN (all runs failed) back to sentinel
    for c in score_cols:
        aggregated[c] = aggregated[c].fillna(FAIL_SENTINEL)

    # Recompute weighted score + rank per scenario_id
    aggregated["weighted_score"] = float(FAIL_SENTINEL)
    aggregated["rank"] = int(FAIL_SENTINEL)
    arch_score_to_col = {
        "energy_cost": score_cols[0],
        "environmental": score_cols[1],
        "comfort": score_cols[2],
        "practicality": score_cols[3],
    }
    tiebreak_cols = [arch_score_to_col[c] for c in TIE_BREAK_PRIORITY]
    for sid in aggregated["scenario_id"].unique():
        sc_mask = aggregated["scenario_id"] == sid
        sc = aggregated[sc_mask]
        valid_idx = sc.index[~sc[score_cols].eq(FAIL_SENTINEL).any(axis=1)]
        if len(valid_idx) > 0:
            ws = (
                aggregated.loc[valid_idx, score_cols[0]] * CRITERION_WEIGHTS["energy_cost"] +
                aggregated.loc[valid_idx, score_cols[1]] * CRITERION_WEIGHTS["environmental"] +
                aggregated.loc[valid_idx, score_cols[2]] * CRITERION_WEIGHTS["comfort"] +
                aggregated.loc[valid_idx, score_cols[3]] * CRITERION_WEIGHTS["practicality"]
            )
            aggregated.loc[valid_idx, "weighted_score"] = ws
            sub = aggregated.loc[valid_idx, [*score_cols]].copy()
            sub["weighted_score"] = ws
            ranks = _rank_with_deterministic_tiebreak(
                sub, "weighted_score", tiebreak_cols,
                log_prefix=f"[aggregate_run_files sid={sid}] "
            )
            aggregated.loc[valid_idx, "rank"] = ranks.astype(int)

    return aggregated
def build_gt_lookup(gt_by_type):
    """Build a lookup like (question, location) -> list of GT scenario entries."""
    gt_lookup = defaultdict(list)

    for dtype, gt_df in gt_by_type.items():
        if gt_df.empty or "scenario_id" not in gt_df.columns:
            continue
        for sid in gt_df["scenario_id"].unique():
            sub = gt_df[gt_df["scenario_id"] == sid]
            q = sub["question"].iloc[0]
            loc = sub["location"].iloc[0]

            alt_map = {}
            for _, row in sub.iterrows():
                norm_alt = normalize_alternative(row["alternative"], dtype)
                alt_map[norm_alt] = row

            gt_lookup[(q, loc)].append({
                "gt_sid": sid,
                "decision_type": dtype,
                "alt_map": alt_map,
                "used": False,
                # Little tie-breaker fields for each decision type
                "outdoor_temp": str(sub["outdoor_temp"].iloc[0]).strip() if "outdoor_temp" in sub.columns else "",
                "appliance_age_type": str(sub["appliance_age_type"].iloc[0]).strip() if "appliance_age_type" in sub.columns else "",
                "gpm": str(sub["gpm"].iloc[0]).strip() if "gpm" in sub.columns else "",
            })

    return gt_lookup


def build_gt_id_lookup(gt_by_type):
    """Build a lookup like (decision_type, scenario_id) -> GT scenario entry."""
    gt_id_lookup = {}
    for dtype, gt_df in gt_by_type.items():
        if gt_df.empty or "scenario_id" not in gt_df.columns:
            continue
        for sid in gt_df["scenario_id"].unique():
            sub = gt_df[gt_df["scenario_id"] == sid]
            alt_map = {}
            for _, row in sub.iterrows():
                norm_alt = normalize_alternative(row["alternative"], dtype)
                alt_map[norm_alt] = row
            gt_id_lookup[(dtype, str(sid))] = {
                "gt_sid": sid,
                "decision_type": dtype,
                "alt_map": alt_map,
                "used": False,
                "question": sub["question"].iloc[0],
                "location": sub["location"].iloc[0],
                "outdoor_temp": str(sub["outdoor_temp"].iloc[0]).strip() if "outdoor_temp" in sub.columns else "",
                "appliance_age_type": str(sub["appliance_age_type"].iloc[0]).strip() if "appliance_age_type" in sub.columns else "",
                "gpm": str(sub["gpm"].iloc[0]).strip() if "gpm" in sub.columns else "",
            }
    return gt_id_lookup


def match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_name):
    """Match architecture scenarios to GT by (question, location) content keys.

    Strict (decision_type, scenario_id) matching is disabled because the
    two ID namespaces do not correspond.
    Content-based matching is logged so reviewers can inspect the method used.
    Warnings are emitted when fewer than 3 alternatives match for a scenario.
    """
    matched_rows = []
    warnings_log = []
    match_method_counts = {"content": 0, "no_match": 0}

    for arch_sid in arch_df["scenario_id"].unique():
        arch_sub = arch_df[arch_df["scenario_id"] == arch_sid]
        arch_dtype = arch_sub["decision_type"].iloc[0]
        q = arch_sub["question"].iloc[0]
        loc = arch_sub["location"].iloc[0]

        # Content-based match only (strict ID match intentionally disabled)
        key = (q, loc)
        if key not in gt_lookup:
            warnings_log.append(
                f"No GT match: sid={arch_sid} ({arch_dtype}, '{q[:50]}', '{loc}')"
            )
            match_method_counts["no_match"] += 1
            continue

        # Normalize the architecture alternatives
        arch_norm_alts = {}
        for _, row in arch_sub.iterrows():
            norm_alt = normalize_alternative(row["alternative"], arch_dtype)
            arch_norm_alts[norm_alt] = row

        best_match = None
        best_score = -1

        # Pull the one extra parameter for this decision type (skip blanks and N/A)
        def _clean(val):
            s = str(val).strip()
            return "" if s.lower() in ("", "n/a", "nan", "none") else s

        if arch_dtype == "HVAC":
            arch_param = _clean(arch_sub["outdoor_temp"].iloc[0]) if "outdoor_temp" in arch_sub.columns else ""
            gt_param_key = "outdoor_temp"
        elif arch_dtype == "Appliance":
            arch_param = _clean(arch_sub["appliance_age"].iloc[0]) if "appliance_age" in arch_sub.columns else ""
            gt_param_key = "appliance_age_type"
        else:  # Shower
            arch_param = _clean(arch_sub["flow_rate"].iloc[0]) if "flow_rate" in arch_sub.columns else ""
            gt_param_key = "gpm"

        for gt_entry in gt_lookup[key]:
            if gt_entry["used"]:
                continue
            if gt_entry["decision_type"] != arch_dtype:
                continue
            overlap = len(set(gt_entry["alt_map"].keys()) & set(arch_norm_alts.keys()))
            extra = 0
            gt_param = _clean(gt_entry.get(gt_param_key, ""))
            if arch_param and gt_param and arch_param == gt_param:
                extra += 100
            score = overlap + extra
            if score > best_score:
                best_score = score
                best_match = gt_entry

        if best_match is None or best_score == 0:
            warnings_log.append(
                f"No alt overlap: sid={arch_sid} ({arch_dtype}, '{q[:50]}', "
                f"arch_alts={list(arch_norm_alts.keys())})"
            )
            match_method_counts["no_match"] += 1
            continue

        match_method_counts["content"] += 1
        best_match["used"] = True

        matched_alts = 0
        for norm_alt, arch_row in arch_norm_alts.items():
            if norm_alt in best_match["alt_map"]:
                gt_row = best_match["alt_map"][norm_alt]

                merged = {
                    "arch_scenario_id": arch_sid,
                    "gt_scenario_id": best_match["gt_sid"],
                    "decision_type": arch_dtype,
                    "alternative": arch_row["alternative"],
                    "norm_alternative": norm_alt,
                    "architecture": arch_name,
                    "match_method": "content",
                    "question": q,
                    "location": loc,
                }

                for c in CRITERIA:
                    merged[f"gt_{c}"] = gt_row.get(f"gt_{c}", np.nan)
                    merged[f"arch_{c}"] = arch_row.get(f"arch_{c}", np.nan)

                merged["gt_rank"] = gt_row.get("gt_rank", np.nan)
                merged["arch_rank"] = arch_row.get("arch_rank", np.nan)

                if "gt_mavt_score" in gt_row.index:
                    merged["gt_mavt_score"] = gt_row["gt_mavt_score"]
                if "arch_weighted_score" in arch_row.index:
                    merged["arch_weighted_score"] = arch_row["arch_weighted_score"]

                if "extraction_failed" in arch_row.index:
                    merged["extraction_failed"] = arch_row["extraction_failed"]
                if "gt_calculation_failed" in arch_row.index:
                    merged["gt_calculation_failed"] = arch_row["gt_calculation_failed"]
                if "input_decision_type" in arch_row.index:
                    merged["input_decision_type"] = arch_row["input_decision_type"]

                matched_rows.append(merged)
                matched_alts += 1
            else:
                warnings_log.append(
                    f"Alt not in GT: sid={arch_sid}, alt='{norm_alt}' "
                    f"(GT has: {list(best_match['alt_map'].keys())})"
                )

        # Warn when fewer than 3 alternatives matched — affects metric quality
        if 0 < matched_alts < 3:
            warnings_log.append(
                f"WARN: only {matched_alts}/3 alternatives matched for "
                f"sid={arch_sid} ({arch_dtype}) — ranking metrics may be unreliable"
            )

    # Reset used flags for next architecture
    for entries in gt_lookup.values():
        for e in entries:
            e["used"] = False
    for e in gt_id_lookup.values():
        e["used"] = False

    merged_df = pd.DataFrame(matched_rows)
    n_arch = arch_df["scenario_id"].nunique()
    n_matched = merged_df["arch_scenario_id"].nunique() if len(merged_df) > 0 else 0

    print(f"\n  [{arch_name}] Matched {n_matched}/{n_arch} scenarios "
          f"({len(merged_df)} alt rows) | method: content-only")
    print(f"    match_method_counts: {match_method_counts}")

    if n_matched < n_arch:
        # B8: surface dropped scenarios as a warning so silent alt-normalization
        # mismatches don't reduce ranking metrics to binary without anyone noticing.
        warnings.warn(
            f"[{arch_name}] Matched only {n_matched}/{n_arch} architecture scenarios "
            f"to ground truth. Dropped scenarios will not contribute to metrics — "
            f"see per-type breakdown below.",
            UserWarning, stacklevel=2,
        )
        for dtype in ["HVAC", "Appliance", "Shower"]:
            arch_sids = set(arch_df[arch_df["decision_type"] == dtype]["scenario_id"].unique())
            matched_sids = set(
                merged_df[merged_df["decision_type"] == dtype]["arch_scenario_id"].unique()
            ) if len(merged_df) > 0 else set()
            unmatched = arch_sids - matched_sids
            if unmatched:
                print(f"    {dtype}: {len(matched_sids)}/{len(arch_sids)} matched, "
                      f"{len(unmatched)} missing (sids: {sorted(unmatched)[:10]}{'...' if len(unmatched) > 10 else ''})")

    if warnings_log:
        n_show = min(5, len(warnings_log))
        print(f"    ({len(warnings_log)} warnings, showing {n_show})")
        for w in warnings_log[:n_show]:
            print(f"      {w}")

    return merged_df, match_method_counts


def compute_criterion_metrics(merged_df):
    """Compute MAE and RMSE for each criterion and overall."""
    results = {}
    all_abs_errors = []
    all_sq_errors = []

    for c in CRITERIA:
        gt = merged_df[f"gt_{c}"].astype(float)
        arch = merged_df[f"arch_{c}"].astype(float)
        ae = (arch - gt).abs()
        se = (arch - gt) ** 2

        results[f"{c}_MAE"] = round(ae.mean(), 4)
        results[f"{c}_RMSE"] = round(np.sqrt(se.mean()), 4)

        all_abs_errors.extend(ae.tolist())
        all_sq_errors.extend(se.tolist())

    results["overall_MAE"] = round(np.mean(all_abs_errors), 4)
    results["overall_RMSE"] = round(np.sqrt(np.mean(all_sq_errors)), 4)
    return results


def compute_ranking_metrics(merged_df):
    """Kendall tau, Spearman rho, Top-1/Top-2 - per-scenario then averaged."""
    taus, rhos = [], []
    top1_ok = top2_ok = 0
    n = 0

    for sid in merged_df["arch_scenario_id"].unique():
        sc = merged_df[merged_df["arch_scenario_id"] == sid].copy()
        if len(sc) < 2:
            continue

        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values
        n += 1

        # Kendall
        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            tau, _ = stats.kendalltau(gt_r, ar_r)
            taus.append(tau if not np.isnan(tau) else 0.0)
        else:
            taus.append(1.0 if np.array_equal(gt_r, ar_r) else 0.0)

        # Spearman
        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            rho, _ = stats.spearmanr(gt_r, ar_r)
            rhos.append(rho if not np.isnan(rho) else 0.0)
        else:
            rhos.append(1.0 if np.array_equal(gt_r, ar_r) else 0.0)

        # top-1
        gt_top1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        ar_top1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        if gt_top1 == ar_top1:
            top1_ok += 1
        # top-2
        ar_top2 = set(sc.sort_values("arch_rank").head(2)["norm_alternative"])
        if gt_top1 in ar_top2:
            top2_ok += 1

    return {
        "kendall_tau": round(np.mean(taus), 4) if taus else np.nan,
        "spearman_rho": round(np.mean(rhos), 4) if rhos else np.nan,
        "top1_accuracy": round(top1_ok / n, 4) if n else np.nan,
        "top2_accuracy": round(top2_ok / n, 4) if n else np.nan,
        "n_scenarios_evaluated": n,
    }


def compute_failure_rate(arch_df):
    """Failure rate for any architecture. Detects failures via the 1928 sentinel
    in score columns. For Hybrid, also reports extraction/calculation breakdown."""
    n_total = arch_df["scenario_id"].nunique()
    n_failed = 0

    for sid in arch_df["scenario_id"].unique():
        g = arch_df[arch_df["scenario_id"] == sid]
        has_sentinel = False
        for c in ["energy_cost", "environmental", "comfort", "practicality"]:
            col = c if c in g.columns else f"arch_{c}"
            if col in g.columns:
                # D6: tolerant coercion catches stringified sentinel ("1928")
                # and NaN-as-failed without raising on parse errors.
                coerced = pd.to_numeric(g[col], errors="coerce")
                if (coerced == FAIL_SENTINEL).any():
                    has_sentinel = True
                    break
        if has_sentinel:
            n_failed += 1

    result = {
        "n_failed_scenarios": n_failed,
        "n_total_arch_scenarios": n_total,
        "total_failure_rate": round(n_failed / n_total, 4) if n_total else 0,
    }

    # Hybrid-specific breakdown
    if "extraction_failed" in arch_df.columns:
        n_ef = n_cf = 0
        for sid in arch_df["scenario_id"].unique():
            g = arch_df[arch_df["scenario_id"] == sid]
            ef = g["extraction_failed"].astype(str).str.lower().str.strip().eq("true").any()
            cf = ("gt_calculation_failed" in g.columns and
                  g["gt_calculation_failed"].astype(str).str.lower().str.strip().eq("true").any())
            if ef: n_ef += 1
            if cf: n_cf += 1
        result["extraction_failure_rate"] = round(n_ef / n_total, 4) if n_total else 0
        result["calculation_failure_rate"] = round(n_cf / n_total, 4) if n_total else 0
        result["n_extraction_failures"] = n_ef
        result["n_calculation_failures"] = n_cf

    return result

def _load_diagnostics_json(arch_path_str, arch_name):
    """Discover and load diagnostics JSON file(s) next to the run CSVs.

    Looks for *_diagnostics_run_NN.json patterns (per-run) and falls back to
    the single-run diagnostics file.  Returns a merged summary dict with
    failure-mode counters aggregated across runs.

    The schema differs per architecture:
      Pure/RAG: failed_malformed_json, failed_missing_score, failed_out_of_bounds,
                failed_invalid_score_type, failed_unknown
      Hybrid:   failed_extraction_*, failed_ground_truth_calculation_exception,
                failed_unknown

    Counters present in the JSON are summed; counters absent in a schema are
    omitted rather than fabricated.
    """
    base_path = Path(arch_path_str)
    result = {"arch_name": arch_name, "diag_files_loaded": 0}

    # All three architectures now write diagnostics as
    # `{output_stem}_diagnostics_run_NN.json` next to the results xlsx.
    all_diag_paths = sorted(
        base_path.parent.glob(f"{base_path.stem}_diagnostics_run_*.json")
    )

    if not all_diag_paths:
        print(f"    [{arch_name}] No diagnostics JSON found next to {base_path.name}")
        return result

    # Aggregate counters across all found files
    import json as _json
    summed = {}
    for dp in all_diag_paths:
        try:
            with open(dp, "r", encoding="utf-8-sig") as f:
                blob = _json.load(f)
            result["diag_files_loaded"] += 1
            for k, v in blob.items():
                if isinstance(v, (int, float)):
                    summed[k] = summed.get(k, 0) + v
        except Exception as e:
            print(f"    [{arch_name}] Could not read {dp.name}: {e}")

    # Identify failure counters present in the data (schema-agnostic).
    # Keep aligned with PURE_FAILURE_COUNTER_KEYS / RAG_FAILURE_COUNTER_KEYS /
    # HYBRID_FAILURE_COUNTER_KEYS in the architecture modules.
    PURE_RAG_COUNTERS = [
        "failed_malformed_json", "failed_missing_score", "failed_out_of_bounds",
        "failed_invalid_score_type", "failed_api_exhausted", "failed_unknown"
    ]
    HYBRID_COUNTERS = [
        "failed_extraction_non_json_wrapper", "failed_extraction_invalid_json",
        "failed_extraction_invalid_decision_type", "failed_extraction_invalid_calculator",
        "failed_extraction_missing_parameters", "failed_extraction_exception",
        "failed_ground_truth_calculation_exception", "failed_ground_truth_missing_key",
        "failed_api_exhausted", "failed_unknown"
    ]
    expected_counters = HYBRID_COUNTERS if arch_name == "Hybrid" else PURE_RAG_COUNTERS

    result["diag_total_scenarios"] = summed.get("total_scenarios", np.nan)
    result["diag_failed_scenarios"] = summed.get("failed_scenarios", np.nan)
    result["diag_successful_scenarios"] = summed.get("successful_scenarios", np.nan)
    result["diag_failed_calls"] = summed.get("failed_calls", np.nan)
    result["diag_successful_calls"] = summed.get("successful_calls", np.nan)

    for k in expected_counters:
        if k in summed:
            result[f"diag_{k}"] = summed[k]

    print(f"    [{arch_name}] Loaded {result['diag_files_loaded']} diagnostics file(s) "
          f"from {base_path.parent.name}")
    return result


def evaluate_all(config):
    print("=" * 72)
    print("  MCDA ARCHITECTURE EVALUATION - METRICS REPORT")
    print("=" * 72)

    # 1. Load
    print("\n[1] Loading ground truth...")
    gt_by_type = load_ground_truth(config)
    for dt, df in gt_by_type.items():
        print(f"    {dt}: {df['scenario_id'].nunique()} scenarios, {len(df)} rows")

    print("\n[2] Loading architectures...")
    arch_dfs = {}
    for name, path in config["architectures"].items():
        base_path = Path(path)
        run_paths = sorted(base_path.parent.glob(f"{base_path.stem}_run_*.xlsx"))
        if run_paths:
            aggregated = aggregate_run_files(run_paths)
            arch_dfs[name] = load_architecture(aggregated, name)
            dtc = arch_dfs[name]["decision_type"].value_counts().to_dict()
            print(f"    {name}: {arch_dfs[name]['scenario_id'].nunique()} scenarios {dtc} (aggregated {len(run_paths)} runs)")
        else:
            arch_dfs[name] = load_architecture(path, name)
            dtc = arch_dfs[name]["decision_type"].value_counts().to_dict()
            print(f"    {name}: {arch_dfs[name]['scenario_id'].nunique()} scenarios {dtc}")

    # Load architecture diagnostics JSONs for failure-mode breakdown
    print("\n[2b] Loading architecture diagnostics...")
    arch_diagnostics = {}
    for name, path in config["architectures"].items():
        if Path(path).parent.exists():
            arch_diagnostics[name] = _load_diagnostics_json(path, name)
        else:
            arch_diagnostics[name] = {"arch_name": name, "diag_files_loaded": 0}

    # 2. Match
    print("\n[3] Matching...")
    gt_lookup = build_gt_lookup(gt_by_type)
    gt_id_lookup = build_gt_id_lookup(gt_by_type)
    print(f"    GT lookup: {len(gt_lookup)} unique (question, location) keys")
    print(f"    GT id lookup: {len(gt_id_lookup)} (decision_type, scenario_id) keys "
          f"(built for reference; strict ID match is disabled)")

    merged_dfs = {}
    all_match_counts = {}
    for name, adf in arch_dfs.items():
        merged_dfs[name], all_match_counts[name] = match_scenarios(gt_lookup, gt_id_lookup, adf, name)

    print("  RESULTS")


    all_metrics = []

    for arch_name in ["Pure", "RAG", "Hybrid"]:
        merged = merged_dfs[arch_name]
        if len(merged) == 0:
            print(f"\n{arch_name}: No matched data")
            continue


        print(f"  {arch_name.upper()}")

        # Record match method counts
        mc = all_match_counts.get(arch_name, {})
        for k, v in mc.items():
            all_metrics.append({
                "architecture": arch_name,
                "decision_type": "Overall",
                "metric": f"match_{k}", "value": v,
            })

        # Diagnostics-based failure-mode counters
        diag = arch_diagnostics.get(arch_name, {})
        for k, v in diag.items():
            if k not in ("arch_name",) and not isinstance(v, str):
                all_metrics.append({
                    "architecture": arch_name,
                    "decision_type": "Overall",
                    "metric": k, "value": v,
                })

        # n_runs from aggregated dataframe (if available)
        arch_df_this = arch_dfs[arch_name]
        if "n_runs" in arch_df_this.columns:
            n_runs_val = arch_df_this["n_runs"].iloc[0]
            all_metrics.append({"architecture": arch_name, "decision_type": "Overall",
                                 "metric": "n_runs", "value": n_runs_val})
        if "n_successful_runs" in arch_df_this.columns:
            n_succ_val = arch_df_this["n_successful_runs"].mean()
            all_metrics.append({"architecture": arch_name, "decision_type": "Overall",
                                 "metric": "n_successful_runs_mean", "value": round(n_succ_val, 2)})

        # Failure rate (all architectures via 1928 sentinel detection)
        fail = compute_failure_rate(arch_dfs[arch_name])
        if fail["n_failed_scenarios"] > 0:
            print(f"\n  Failures: {fail['n_failed_scenarios']}"
                  f"/{fail['n_total_arch_scenarios']} "
                  f"({fail['total_failure_rate']*100:.1f}%)")
            if "n_extraction_failures" in fail:
                print(f"    extraction={fail['n_extraction_failures']}, "
                      f"calc={fail['n_calculation_failures']}")
        for k, v in fail.items():
            all_metrics.append({
                "architecture": arch_name,
                "decision_type": "Overall",
                "metric": k, "value": v,
            })

        # Filter out failed scenarios (1928 sentinel) before computing metrics
        merged, n_failed, n_total = filter_failed_scenarios(merged)
        if n_failed > 0:
            print(f"  Filtered {n_failed}/{n_total} failed scenarios; "
                  f"evaluating {n_total - n_failed} successful scenarios")

        if len(merged) == 0:
            print(f"  No successful scenarios to evaluate after filtering")
            continue

        crit = compute_criterion_metrics(merged)
        rank = compute_ranking_metrics(merged)
        n_eval = rank["n_scenarios_evaluated"]

        print(f"\n  OVERALL ({n_eval} scenarios):")
        print(f"    Criterion MAE / RMSE:")
        for c in CRITERIA:
            print(f"      {c:20s}  MAE={crit[f'{c}_MAE']:.4f}  "
                  f"RMSE={crit[f'{c}_RMSE']:.4f}")
        print(f"      {'OVERALL':20s}  MAE={crit['overall_MAE']:.4f}  "
              f"RMSE={crit['overall_RMSE']:.4f}")

        print(f"    Ranking:")
        print(f"      Kendall tau:  {rank['kendall_tau']:.4f}")
        print(f"      Spearman rho: {rank['spearman_rho']:.4f}")
        print(f"      Top-1:      {rank['top1_accuracy']:.4f} "
              f"({int(rank['top1_accuracy'] * n_eval)}/{n_eval})")
        print(f"      Top-2:      {rank['top2_accuracy']:.4f} "
              f"({int(rank['top2_accuracy'] * n_eval)}/{n_eval})")

        # Store overall
        for k, v in {**crit, **rank}.items():
            all_metrics.append({
                "architecture": arch_name,
                "decision_type": "Overall",
                "metric": k, "value": v,
            })

        # per decision type
        for dtype in ["HVAC", "Appliance", "Shower"]:
            dt_data = merged[merged["decision_type"] == dtype]
            if len(dt_data) == 0:
                print(f"\n  {dtype}: No matched data")
                continue

            dt_crit = compute_criterion_metrics(dt_data)
            dt_rank = compute_ranking_metrics(dt_data)
            n_dt = dt_rank["n_scenarios_evaluated"]

            print(f"\n  {dtype} ({n_dt} scenarios, {len(dt_data)} alt rows):")
            print(f"    MAE:  EC={dt_crit['energy_cost_MAE']:.3f}  "
                  f"ENV={dt_crit['environmental_MAE']:.3f}  "
                  f"COM={dt_crit['comfort_MAE']:.3f}  "
                  f"PRA={dt_crit['practicality_MAE']:.3f}  "
                  f"All={dt_crit['overall_MAE']:.3f}")
            print(f"    RMSE: EC={dt_crit['energy_cost_RMSE']:.3f}  "
                  f"ENV={dt_crit['environmental_RMSE']:.3f}  "
                  f"COM={dt_crit['comfort_RMSE']:.3f}  "
                  f"PRA={dt_crit['practicality_RMSE']:.3f}  "
                  f"All={dt_crit['overall_RMSE']:.3f}")
            print(f"    tau={dt_rank['kendall_tau']:.4f}  "
                  f"rho={dt_rank['spearman_rho']:.4f}  "
                  f"Top1={dt_rank['top1_accuracy']:.4f} "
                  f"({int(dt_rank['top1_accuracy']*n_dt)}/{n_dt})  "
                  f"Top2={dt_rank['top2_accuracy']:.4f} "
                  f"({int(dt_rank['top2_accuracy']*n_dt)}/{n_dt})")

            for k, v in {**dt_crit, **dt_rank}.items():
                all_metrics.append({
                    "architecture": arch_name,
                    "decision_type": dtype,
                    "metric": k, "value": v,
                })



    def _get(arch, dtype, metric):
        """Helper to pull a metric value from all_metrics list."""
        val = next(
            (m["value"] for m in all_metrics
             if m["architecture"] == arch
             and m["decision_type"] == dtype
             and m["metric"] == metric),
            np.nan
        )
        return val

    def _fmt(val, is_int=False):
        if isinstance(val, float) and np.isnan(val):
            return f"{'N/A':>10}"
        return f"{int(val):>10}" if is_int else f"{val:>10.4f}"

    archs = ["Pure", "RAG", "Hybrid"]

    # Overall table
    header = f"  {'Metric':<24}" + "".join(f"{a:>10}" for a in archs)
    print(f"\n{header}")
    print("  " + "-" * (24 + 10 * len(archs)))

    for metric in ["overall_MAE", "overall_RMSE", "kendall_tau", "spearman_rho",
                    "top1_accuracy", "top2_accuracy", "n_scenarios_evaluated"]:
        is_int = metric == "n_scenarios_evaluated"
        row = f"  {metric:<24}"
        for a in archs:
            row += _fmt(_get(a, "Overall", metric), is_int)
        print(row)

    # Per-criterion MAE
    print(f"\n  {'Criterion MAE':<24}" + "".join(f"{a:>10}" for a in archs))
    print("  " + "-" * (24 + 10 * len(archs)))
    for c in CRITERIA:
        row = f"  {c:<24}"
        for a in archs:
            row += _fmt(_get(a, "Overall", f"{c}_MAE"))
        print(row)

    # Kendall tau by decision type
    print(f"\n  {'Kendall tau by Type':<24}" + "".join(f"{a:>10}" for a in archs))
    print("  " + "-" * (24 + 10 * len(archs)))
    for dtype in ["HVAC", "Appliance", "Shower"]:
        row = f"  {dtype:<24}"
        for a in archs:
            row += _fmt(_get(a, dtype, "kendall_tau"))
        print(row)

    # Top-1 by decision type
    print(f"\n  {'Top-1 by Type':<24}" + "".join(f"{a:>10}" for a in archs))
    print("  " + "-" * (24 + 10 * len(archs)))
    for dtype in ["HVAC", "Appliance", "Shower"]:
        row = f"  {dtype:<24}"
        for a in archs:
            row += _fmt(_get(a, dtype, "top1_accuracy"))
        print(row)
    metrics_df = pd.DataFrame(all_metrics, columns=["architecture", "decision_type", "metric", "value"])
    _atomic_write_xlsx(metrics_df, config["output_csv"])
    print(f"\n\nMetrics saved to: {config['output_csv']}")
    print(f"Total metric rows: {len(metrics_df)}")

    return metrics_df, merged_dfs

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Usage: python calculate_metrics.py")
        print("  Modify CONFIG dict at top of file to change paths.")
        sys.exit(0)

    metrics_df, merged_dfs = evaluate_all(CONFIG)

