#!/usr/bin/env python3
"""
calculate_metrics.py - Metrics evaluation for MCDA architecture comparison
Science Fair Project: LLM-assisted MCDA for Household Emissions Optimization

Compares Direct LLM Scoring, Example-Guided LLM Scoring, and LLM-Parameterized Reference Scoring architectures against
physics-based ground truth using MAVT scoring across HVAC, Appliance,
and Shower decision scenarios.
"""

import argparse
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

from model_config import (
    get_output_folder,
    MODEL_KEY,
    MODEL_SPECS,
    CRITERION_WEIGHTS,
    TIE_BREAK_PRIORITY,
    EXTRACTION_INVALID_JSON,
    FAILED_MISSING_SCORE,
    FAILED_OUT_OF_BOUNDS,
    FAILED_INVALID_SCORE_TYPE,
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN,
    FAILED_EXTRACTION_NON_JSON_WRAPPER,
    FAILED_EXTRACTION_INVALID_DECISION_TYPE,
    FAILED_EXTRACTION_INVALID_CALCULATOR,
    FAILED_EXTRACTION_MISSING_PARAMETERS,
    FAILED_EXTRACTION_EXCEPTION,
    FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION,
    FAILED_GROUND_TRUTH_MISSING_KEY,
)
from sentinel_utils import _atomic_write_xlsx, read_table_clean, SENTINEL_VALUE, SENTINEL_FLOAT

_COMMON_STR_COLS = [
    'question', 'location', 'alternative',
    'housing_type', 'insulation', 'appliance', 'appliance_age', 'house_age',
]

GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"


def _build_config(model_key: str) -> dict:
    """Build the CONFIG dict for a given model_key."""
    output_dir = PROJECT_ROOT / get_output_folder(model_key)
    return {
        "ground_truth": {
            "HVAC": str(GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx"),
            "Appliance": str(GROUND_TRUTH_DIR / "ground_truth_appliance.xlsx"),
            "Shower": str(GROUND_TRUTH_DIR / "ground_truth_shower.xlsx"),
        },
        "architectures": {
            "Direct_LLM_Scoring": str(output_dir / "Direct_LLM_Scoring_results.xlsx"),
            "Example-Guided_LLM_Scoring": str(output_dir / "Example-Guided_LLM_Scoring_results.xlsx"),
            "LLM-Parameterized_Reference_Scoring": str(output_dir / "LLM-Parameterized_Reference_Scoring_results.xlsx"),
        },
        "output_csv": str(output_dir / f"metrics_summary_{model_key}.xlsx"),
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


# Default CONFIG uses the MODEL_KEY from model_config (for import compatibility)
CONFIG = _build_config(MODEL_KEY)

CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]
FAIL_SENTINEL = SENTINEL_VALUE
PLACEHOLDER_ALT_RE = re.compile(
    r"^Alternative\s+(\d+)\s+\(extraction failed\)$", re.IGNORECASE
)

# Scenario matching uses (question, location) content keys only. Strict
# (decision_type, scenario_id) lookup is disabled because architecture
# scenario_ids are assigned from TestScenarios while GT tables number
# independently by domain, so those ID namespaces do not align.
#
# Architecture *_results files are not used here. This script
# re-aggregates per-run outputs via aggregate_run_files and serves as the
# source for reported metrics.

_STRICT_ID_MATCH_ENABLED = False

# Secondary criterion priority used when weighted scores tie is imported from
# model_config so the ground-truth calculators and this script break ties
# identically (single source of truth).


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


def _clean_match_value(value):
    """Coerce a match parameter to a clean string; return '' for blanks/N/A."""
    s = str(value).strip()
    return "" if s.lower() in ("", "n/a", "nan", "none") else s


def _numeric_close(a, b, tolerance=0.5):
    """Return True if both a and b parse as floats and |a - b| <= tolerance."""
    try:
        return abs(float(a) - float(b)) <= tolerance
    except (ValueError, TypeError):
        return False


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
        df = read_table_clean(filepath, keep_str_cols=_COMMON_STR_COLS)
        df["decision_type"] = dtype

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
        df = read_table_clean(source, keep_str_cols=_COMMON_STR_COLS)
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


def _align_failed_placeholder_alternatives(combined, score_cols):
    """Map failed-run placeholder alternatives onto real alternatives.

    LLM-Parameterized_Reference_Scoring writes rows like
    "Alternative 1 (extraction failed)" when extraction fails before the
    calculator sees the original alternatives. In multi-run aggregation, those
    placeholders should count as failed attempts for the real alternatives, not
    become separate unmatched alternatives.
    """
    out = combined.copy()

    for (sid, dtype), idx in out.groupby(["scenario_id", "decision_type"]).groups.items():
        group = out.loc[idx]
        placeholder_positions = []
        real_alternatives = []

        for row_idx, alt in group["alternative"].items():
            alt_text = str(alt).strip()
            match = PLACEHOLDER_ALT_RE.match(alt_text)
            if match:
                placeholder_positions.append((row_idx, int(match.group(1))))
            elif alt_text not in real_alternatives:
                real_alternatives.append(alt_text)

        if not placeholder_positions or len(real_alternatives) < 3:
            continue

        for row_idx, alt_num in placeholder_positions:
            if 1 <= alt_num <= len(real_alternatives):
                out.at[row_idx, "alternative"] = real_alternatives[alt_num - 1]

    return out


def aggregate_run_files(run_paths):
    """Aggregate multi-run results into a single dataframe with mean/std scores.

    The returned dataframe includes n_runs, n_successful_runs, and n_failed_runs
    so downstream callers can report on run coverage without re-counting.
    When std is NaN because only one run was aggregated, it is annotated.
    """
    run_dfs = []
    for p in run_paths:
        run_dfs.append(read_table_clean(p, keep_str_cols=_COMMON_STR_COLS))
    n_readable = len(run_dfs)
    combined = pd.concat(run_dfs, ignore_index=True)

    score_cols = [
        CONFIG["arch_score_cols"]["energy_cost"],
        CONFIG["arch_score_cols"]["environmental"],
        CONFIG["arch_score_cols"]["comfort"],
        CONFIG["arch_score_cols"]["practicality"],
    ]
    combined = _coerce_score_columns(combined, score_cols)
    combined = _align_failed_placeholder_alternatives(combined, score_cols)

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
                # Tie-breaker fields for each decision type
                "outdoor_temp": str(sub["outdoor_temp"].iloc[0]).strip() if "outdoor_temp" in sub.columns else "",
                "appliance_age": str(sub["appliance_age"].iloc[0]).strip() if "appliance_age" in sub.columns else "",
                "gpm": str(sub["gpm"].iloc[0]).strip() if "gpm" in sub.columns else "",
                # Additional Shower match fields
                "household_size": str(sub["household_size"].iloc[0]).strip() if "household_size" in sub.columns else "",
                "utility_budget": str(sub["utility_budget"].iloc[0]).strip() if "utility_budget" in sub.columns else "",
                "housing_type": str(sub["housing_type"].iloc[0]).strip() if "housing_type" in sub.columns else "",
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
                "appliance_age": str(sub["appliance_age"].iloc[0]).strip() if "appliance_age" in sub.columns else "",
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
        best_score = 0
        best_param_count = 0

        # Build (arch_value, gt_key) pairs for this decision type.
        # Each pair that matches adds +100 to the candidate score.
        # Shower gets more pairs since its scenarios share (question, location)
        # more often and need multiple parameters to disambiguate.
        param_pairs = []  # [(arch_value, gt_key), ...]
        if arch_dtype == "HVAC":
            _pairs = [("outdoor_temp", "outdoor_temp")]
        elif arch_dtype == "Appliance":
            _pairs = [("appliance_age", "appliance_age")]
        else:  # Shower
            _pairs = [
                ("outdoor_temp",   "outdoor_temp"),
                ("flow_rate",      "gpm"),
                ("household_size", "household_size"),
                ("utility_budget", "utility_budget"),
                ("housing_type",   "housing_type"),
            ]
        for arch_col, gt_key in _pairs:
            v = _clean_match_value(arch_sub[arch_col].iloc[0]) if arch_col in arch_sub.columns else ""
            if v:
                param_pairs.append((v, gt_key))

        candidates = []  # (score, param_match_count, gt_entry)
        for gt_entry in gt_lookup[key]:
            if gt_entry["used"]:
                continue
            if gt_entry["decision_type"] != arch_dtype:
                continue
            overlap = len(set(gt_entry["alt_map"].keys()) & set(arch_norm_alts.keys()))
            extra = 0
            param_count = 0
            for arch_val, gt_key in param_pairs:
                gt_val = _clean_match_value(gt_entry.get(gt_key, ""))
                if gt_val and arch_val == gt_val:
                    extra += 100
                    param_count += 1
            score = overlap + extra
            candidates.append((score, param_count, gt_entry))

        valid_candidates = [(s, pc, e) for s, pc, e in candidates if s > 0]
        if valid_candidates:
            best_score = max(s for s, _, _ in valid_candidates)
            top = [(s, pc, e) for s, pc, e in valid_candidates if s == best_score]
            _, best_param_count, best_match = top[0]
            if len(top) > 1:
                warnings_log.append(
                    f"WARN: {len(top)}-way tie (score={best_score}) for "
                    f"sid={arch_sid} ({arch_dtype}, '{q[:40]}') — using first GT candidate"
                )
            if arch_dtype == "Shower" and best_param_count == 0:
                warnings_log.append(
                    f"WARN: Shower sid={arch_sid} matched on alternative overlap only "
                    f"(no parameter matches) — match confidence is low"
                )

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
            gt_row = None
            if norm_alt in best_match["alt_map"]:
                gt_row = best_match["alt_map"][norm_alt]
            else:
                m = PLACEHOLDER_ALT_RE.match(norm_alt)
                if m:
                    alt_num = int(m.group(1))
                    gt_alts = list(best_match["alt_map"].keys())
                    if 1 <= alt_num <= len(gt_alts):
                        gt_row = best_match["alt_map"][gt_alts[alt_num - 1]]

            if gt_row is not None:
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


def compute_cross_criterion_correlation(merged_df):
    """Compute Spearman rho between energy_cost and environmental impact.

    Uses ground-truth scores across all alternatives in all matched scenarios.
    Returns overall rho plus per-decision-type breakdowns. This measures how
    correlated the two criteria are in the dataset, which is relevant to the
    preferential-independence assumption in MAVT.
    """
    results = {}

    gt_ec = merged_df["gt_energy_cost"].astype(float)
    gt_env = merged_df["gt_environmental"].astype(float)
    valid = gt_ec.notna() & gt_env.notna()
    if valid.sum() >= 3:
        rho, pval = stats.spearmanr(gt_ec[valid], gt_env[valid])
        results["cross_criterion_rho_overall"] = round(rho, 4)
        results["cross_criterion_rho_pvalue"] = round(pval, 6)
    else:
        results["cross_criterion_rho_overall"] = np.nan
        results["cross_criterion_rho_pvalue"] = np.nan

    for dtype in ["HVAC", "Appliance", "Shower"]:
        subset = merged_df[merged_df["decision_type"] == dtype]
        ec = subset["gt_energy_cost"].astype(float)
        env = subset["gt_environmental"].astype(float)
        v = ec.notna() & env.notna()
        if v.sum() >= 3:
            rho, pval = stats.spearmanr(ec[v], env[v])
            results[f"cross_criterion_rho_{dtype}"] = round(rho, 4)
            results[f"cross_criterion_rho_{dtype}_pvalue"] = round(pval, 6)
        else:
            results[f"cross_criterion_rho_{dtype}"] = np.nan
            results[f"cross_criterion_rho_{dtype}_pvalue"] = np.nan

    return results


def compute_criterion_metrics(merged_df):
    """Compute MAE and RMSE for each criterion and overall.

    Rows where either gt or arch score is NaN (genuinely missing, not sentinel)
    are dropped per-criterion before computing errors so a single bad cell does
    not propagate NaN across the whole result.
    """
    results = {}
    all_abs_errors = []
    all_sq_errors = []

    for c in CRITERIA:
        gt = merged_df[f"gt_{c}"].astype(float)
        arch = merged_df[f"arch_{c}"].astype(float)
        # Drop pairs where either value is NaN
        valid_mask = gt.notna() & arch.notna()
        gt_v = gt[valid_mask]
        arch_v = arch[valid_mask]
        if len(gt_v) == 0:
            results[f"{c}_MAE"] = np.nan
            results[f"{c}_RMSE"] = np.nan
            continue
        ae = (arch_v - gt_v).abs()
        se = (arch_v - gt_v) ** 2

        results[f"{c}_MAE"] = round(ae.mean(), 4)
        results[f"{c}_RMSE"] = round(np.sqrt(se.mean()), 4)

        all_abs_errors.extend(ae.tolist())
        all_sq_errors.extend(se.tolist())

    # Use nan-skipping aggregation to stay consistent with the per-criterion
    # MAE/RMSE above (pandas .mean() already skips NaN). Plain np.mean would
    # return NaN for the overall figure if any single cell were missing.
    results["overall_MAE"] = round(np.nanmean(all_abs_errors), 4) if all_abs_errors else np.nan
    results["overall_RMSE"] = round(np.sqrt(np.nanmean(all_sq_errors)), 4) if all_sq_errors else np.nan
    results["overall_rmse_mae_ratio"] = round(results["overall_RMSE"] / results["overall_MAE"], 4) if results["overall_MAE"] != 0 else np.nan
    return results


def compute_ranking_metrics(merged_df):
    """Kendall tau, Top-1 - per-scenario then averaged.

    Scenarios where any rank value is NaN (genuinely missing) are skipped
    entirely so a single bad row does not turn the whole scenario's tau
    into NaN.
    """
    taus = []
    top1_ok = 0
    n = 0

    for sid in merged_df["arch_scenario_id"].unique():
        sc = merged_df[merged_df["arch_scenario_id"] == sid].copy()
        if len(sc) < 2:
            continue

        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values

        # Skip scenario if any rank is NaN (not sentinel-filtered, genuinely missing)
        if np.isnan(gt_r).any() or np.isnan(ar_r).any():
            continue

        n += 1

        # Kendall
        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            tau, _ = stats.kendalltau(gt_r, ar_r)
            taus.append(tau if not np.isnan(tau) else 0.0)
        else:
            taus.append(1.0 if np.array_equal(gt_r, ar_r) else 0.0)

        # top-1
        gt_top1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        ar_top1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        if gt_top1 == ar_top1:
            top1_ok += 1

    return {
        "kendall_tau": round(np.mean(taus), 4) if taus else np.nan,
        "top1_accuracy": round(top1_ok / n, 4) if n else np.nan,
        "n_scenarios_evaluated": n,
    }


def compute_failure_rate(arch_df):
    """Failure rate for any architecture. Detects failures via the 1928 sentinel
    in score columns. For LLM-Parameterized_Reference_Scoring, also reports extraction/calculation breakdown."""
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

    # LLM-Parameterized_Reference_Scoring-specific breakdown
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

def impute_failed_scores(merged_df, impute_value=0.5):
    """Replace sentinel 1928 scores in arch_* columns with impute_value.

    Returns (imputed_df, n_imputed_rows, n_imputed_scenarios).
    Only touches arch_* score columns (energy_cost, environmental, comfort,
    practicality). GT columns and metadata columns are left untouched.
    """
    df = merged_df.copy()
    arch_score_cols = [f"arch_{c}" for c in CRITERIA]
    n_imputed_rows = 0
    imputed_sids = set()

    for c in arch_score_cols:
        if c not in df.columns:
            continue
        sentinel_mask = df[c] == FAIL_SENTINEL
        if sentinel_mask.any():
            n_imputed_rows += sentinel_mask.sum()
            imputed_sids.update(df.loc[sentinel_mask, "arch_scenario_id"].unique())
            df.loc[sentinel_mask, c] = float(impute_value)

    n_imputed_scenarios = len(imputed_sids)
    if n_imputed_rows > 0:
        print(f"  Imputed {n_imputed_rows} sentinel scores to {impute_value} "
              f"across {n_imputed_scenarios} scenarios")

    return df, n_imputed_rows, n_imputed_scenarios


def recompute_arch_ranks(merged_df):
    """Recompute arch_weighted_score and arch_rank after imputation.

    Uses CRITERION_WEIGHTS and TIE_BREAK_PRIORITY from model_config,
    same logic as aggregate_run_files() so imputed ranks are consistent
    with non-imputed output.
    """
    df = merged_df.copy()
    arch_score_cols = [f"arch_{c}" for c in CRITERIA]
    tiebreak_cols = [f"arch_{c}" for c in TIE_BREAK_PRIORITY]

    for sid in df["arch_scenario_id"].unique():
        sc_mask = df["arch_scenario_id"] == sid
        idx = df.index[sc_mask]
        sc = df.loc[idx]

        ws = (
            sc[arch_score_cols[0]] * CRITERION_WEIGHTS["energy_cost"] +
            sc[arch_score_cols[1]] * CRITERION_WEIGHTS["environmental"] +
            sc[arch_score_cols[2]] * CRITERION_WEIGHTS["comfort"] +
            sc[arch_score_cols[3]] * CRITERION_WEIGHTS["practicality"]
        )
        df.loc[idx, "arch_weighted_score"] = ws.values

        sub = df.loc[idx, [*arch_score_cols]].copy()
        sub["weighted_score"] = ws.values
        ranks = _rank_with_deterministic_tiebreak(
            sub, "weighted_score", tiebreak_cols,
            log_prefix=f"[recompute_arch_ranks sid={sid}] "
        )
        df.loc[idx, "arch_rank"] = ranks.astype(int).values

    return df


def _load_diagnostics_json(arch_path_str, arch_name):
    """Discover and load diagnostics JSON file(s) next to the run CSVs.

    Looks for *_diagnostics_run_NN.json patterns (per-run) and falls back to
    the single-run diagnostics file.  Returns a merged summary dict with
    failure-mode counters aggregated across runs.

    The schema differs per architecture:
      Pure/RAG: failed_malformed_json, failed_missing_score, failed_out_of_bounds,
                failed_invalid_score_type, failed_unknown
      Direct_LLM_Scoring / Example-Guided_LLM_Scoring share the same counter schema.
      LLM-Parameterized_Reference_Scoring:   failed_extraction_*, failed_ground_truth_calculation_exception,
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
    # LLM-Parameterized_Reference_Scoringrameterized_Reference_Scoring_FAILURE_COUNTER_KEYS in the architecture modules.
    PURE_RAG_COUNTERS = [
        EXTRACTION_INVALID_JSON, FAILED_MISSING_SCORE, FAILED_OUT_OF_BOUNDS,
        FAILED_INVALID_SCORE_TYPE, FAILED_API_EXHAUSTED, FAILED_UNKNOWN
    ]
    LLM_Parameterized_Reference_Scoring_COUNTERS = [
        FAILED_EXTRACTION_NON_JSON_WRAPPER, EXTRACTION_INVALID_JSON,
        FAILED_EXTRACTION_INVALID_DECISION_TYPE, FAILED_EXTRACTION_INVALID_CALCULATOR,
        FAILED_EXTRACTION_MISSING_PARAMETERS, FAILED_EXTRACTION_EXCEPTION,
        FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION, FAILED_GROUND_TRUTH_MISSING_KEY,
        FAILED_API_EXHAUSTED, FAILED_UNKNOWN
    ]
    expected_counters = LLM_Parameterized_Reference_Scoring_COUNTERS if arch_name == "LLM-Parameterized_Reference_Scoring" else PURE_RAG_COUNTERS

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


def evaluate_all(config, include_baselines=False, model_key=None, impute_value=0.5):
    """Evaluate all architectures against ground truth and return metrics.

    Always runs both filtered (failed scenarios dropped) and imputed
    (failed scores replaced with impute_value) modes.

    Args:
        config: CONFIG dict with paths for this model.
        include_baselines: If True, also evaluate non-LLM baselines.
        model_key: Human-readable model identifier shown in headers.
        impute_value: Value to substitute for sentinel 1928 (default 0.5).
    """
    model_label = f" [{model_key.upper()}]" if model_key else ""
    print("=" * 72)
    print(f"  MCDA ARCHITECTURE EVALUATION - METRICS REPORT{model_label}")
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

    # Load baselines if requested
    if include_baselines:
        print("\n[2b] Loading baselines...")
        from RunBaselines import run_all_baselines
        test_path = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"
        test_df = read_table_clean(test_path)
        baseline_results = run_all_baselines(test_df)
        for name, df in baseline_results.items():
            if name == 'Random':
                # For random, use the first seed for metrics computation
                # (CalculateMetrics will average over seeds in verification)
                seed_df = df[df['seed'] == 0].drop(columns=['seed']) if 'seed' in df.columns else df
                arch_dfs[name] = load_architecture(seed_df, name)
            else:
                arch_dfs[name] = load_architecture(df, name)
            dtc = arch_dfs[name]["decision_type"].value_counts().to_dict()
            print(f"    {name}: {arch_dfs[name]['scenario_id'].nunique()} scenarios {dtc}")

    # Load architecture diagnostics JSONs for failure-mode breakdown
    print("\n[2c] Loading architecture diagnostics...")
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

    # Determine architecture list based on whether baselines are included
    if include_baselines:
        arch_list = ["Random", "Uniform", "FixedDefault", "NearestNeighbor", "Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]
    else:
        arch_list = ["Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]

    for arch_name in arch_list:
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

        # Cross-criterion correlation (ground-truth scores only)
        xcorr = compute_cross_criterion_correlation(merged)
        for k, v in xcorr.items():
            all_metrics.append({
                "architecture": arch_name,
                "decision_type": "Overall",
                "metric": k, "value": v,
            })
        print(f"\n  Cross-criterion Spearman rho (cost vs. environmental):")
        print(f"    Overall: {xcorr['cross_criterion_rho_overall']:.4f} "
              f"(p={xcorr['cross_criterion_rho_pvalue']:.2e})")
        for dtype in ["HVAC", "Appliance", "Shower"]:
            print(f"    {dtype}: {xcorr[f'cross_criterion_rho_{dtype}']:.4f} "
                  f"(p={xcorr[f'cross_criterion_rho_{dtype}_pvalue']:.2e})")

        # Run both modes: filtered (drop failures) and imputed (5.0 substitute)
        merged_filtered, n_failed, n_total = filter_failed_scenarios(merged.copy())
        merged_imputed, n_imputed_rows, n_imputed_sids = impute_failed_scores(merged.copy())
        merged_imputed = recompute_arch_ranks(merged_imputed)

        if n_failed > 0:
            print(f"  Filtered {n_failed}/{n_total} failed scenarios; "
                  f"evaluating {n_total - n_failed} successful scenarios")
        if n_imputed_sids > 0:
            print(f"  Imputed {n_imputed_sids} scenario(s) had sentinel scores "
                  f"({n_imputed_rows} total cells set to {impute_value})")

        for mode, merged_mode in [("filtered", merged_filtered), ("imputed", merged_imputed)]:
            if len(merged_mode) == 0:
                continue

            crit = compute_criterion_metrics(merged_mode)
            rank = compute_ranking_metrics(merged_mode)
            n_eval = rank["n_scenarios_evaluated"]

            print(f"\n  {mode.upper()} ({n_eval} scenarios):")
            print(f"    Criterion MAE / RMSE:")
            for c in CRITERIA:
                print(f"      {c:20s}  MAE={crit[f'{c}_MAE']:.4f}  "
                      f"RMSE={crit[f'{c}_RMSE']:.4f}")
            print(f"      {'OVERALL':20s}  MAE={crit['overall_MAE']:.4f}  "
                  f"RMSE={crit['overall_RMSE']:.4f}")

            print(f"    Ranking:")
            print(f"      Kendall tau:  {rank['kendall_tau']:.4f}")
            print(f"      Top-1:      {rank['top1_accuracy']:.4f} "
                  f"({round(rank['top1_accuracy'] * n_eval)}/{n_eval})")

            # Store overall
            for k, v in {**crit, **rank}.items():
                all_metrics.append({
                    "architecture": arch_name,
                    "decision_type": "Overall",
                    "mode": mode, "metric": k, "value": v,
                })

            # per decision type
            for dtype in ["HVAC", "Appliance", "Shower"]:
                dt_data = merged_mode[merged_mode["decision_type"] == dtype]
                if len(dt_data) == 0:
                    continue

                dt_crit = compute_criterion_metrics(dt_data)
                dt_rank = compute_ranking_metrics(dt_data)
                n_dt = dt_rank["n_scenarios_evaluated"]

                print(f"\n  {mode.upper()} {dtype} ({n_dt} scenarios, {len(dt_data)} alt rows):")
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
                      f"Top1={dt_rank['top1_accuracy']:.4f} "
                      f"({round(dt_rank['top1_accuracy']*n_dt)}/{n_dt})")

                for k, v in {**dt_crit, **dt_rank}.items():
                    all_metrics.append({
                        "architecture": arch_name,
                        "decision_type": dtype,
                        "mode": mode, "metric": k, "value": v,
                    })



    def _get_mode(arch, dtype, metric, mode):
        """Helper to pull a metric value from all_metrics list."""
        val = next(
            (m["value"] for m in all_metrics
             if m["architecture"] == arch
             and m["decision_type"] == dtype
             and m["metric"] == metric
             and m.get("mode") == mode),
            np.nan
        )
        return val

    def _fmt(val, is_int=False):
        if isinstance(val, float) and np.isnan(val):
            return f"{'N/A':>10}"
        return f"{int(val):>10}" if is_int else f"{val:>10.4f}"

    if include_baselines:
        archs = ["Random", "Uniform", "FixedDefault", "NearestNeighbor", "Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]
    else:
        archs = ["Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]

    for mode_label in ("filtered", "imputed"):
        print(f"\n{'='*60}")
        print(f"  {mode_label.upper()} METRICS")
        print(f"{'='*60}")

        # Overall table
        header = f"  {'Metric':<24}" + "".join(f"{a:>10}" for a in archs)
        print(f"\n{header}")
        print("  " + "-" * (24 + 10 * len(archs)))

        for metric in ["overall_MAE", "overall_RMSE", "overall_rmse_mae_ratio", "kendall_tau",
                        "top1_accuracy", "n_scenarios_evaluated"]:
            is_int = metric == "n_scenarios_evaluated"
            row = f"  {metric:<24}"
            for a in archs:
                row += _fmt(_get_mode(a, "Overall", metric, mode_label), is_int)
            print(row)

        # Per-criterion MAE
        print(f"\n  {'Criterion MAE':<24}" + "".join(f"{a:>10}" for a in archs))
        print("  " + "-" * (24 + 10 * len(archs)))
        for c in CRITERIA:
            row = f"  {c:<24}"
            for a in archs:
                row += _fmt(_get_mode(a, "Overall", f"{c}_MAE", mode_label))
            print(row)

        # Kendall tau by decision type
        print(f"\n  {'Kendall tau by Type':<24}" + "".join(f"{a:>10}" for a in archs))
        print("  " + "-" * (24 + 10 * len(archs)))
        for dtype in ["HVAC", "Appliance", "Shower"]:
            row = f"  {dtype:<24}"
            for a in archs:
                row += _fmt(_get_mode(a, dtype, "kendall_tau", mode_label))
            print(row)

        # Top-1 by decision type
        print(f"\n  {'Top-1 by Type':<24}" + "".join(f"{a:>10}" for a in archs))
        print("  " + "-" * (24 + 10 * len(archs)))
        for dtype in ["HVAC", "Appliance", "Shower"]:
            row = f"  {dtype:<24}"
            for a in archs:
                row += _fmt(_get_mode(a, dtype, "top1_accuracy", mode_label))
            print(row)

    metrics_df = pd.DataFrame(all_metrics, columns=["architecture", "decision_type", "mode", "metric", "value"])

    # Duplicate shared (no-mode) rows into both modes
    shared = metrics_df[metrics_df["mode"].isna()]
    df_f = pd.concat([
        metrics_df[metrics_df["mode"] == "filtered"],
        shared.assign(mode="filtered"),
    ], ignore_index=True).drop(columns=["mode"])

    df_i = pd.concat([
        metrics_df[metrics_df["mode"] == "imputed"],
        shared.assign(mode="imputed"),
    ], ignore_index=True).drop(columns=["mode"])

    base_out = Path(config["output_csv"])
    out_dir = base_out.parent
    stem = base_out.stem

    filtered_path = str(out_dir / f"{stem}.xlsx")
    imputed_path = str(out_dir / f"{stem}_imputed.xlsx")

    _atomic_write_xlsx(df_f, filtered_path)
    _atomic_write_xlsx(df_i, imputed_path)

    print(f"\n\nFiltered metrics saved to: {filtered_path}")
    print(f"Imputed metrics saved to: {imputed_path}")
    print(f"Total metric rows: {len(metrics_df)} ({len(df_f)} filtered + {len(df_i)} imputed)")

    return metrics_df, merged_dfs

if __name__ == "__main__":
    _all_model_keys = sorted(MODEL_SPECS.keys())
    parser = argparse.ArgumentParser(
        description="Calculate MCDA architecture metrics",
        epilog=(
            f"Available model keys: {', '.join(_all_model_keys)}. "
            "Defaults to MODEL_KEY in model_config.py when --model is omitted."
        )
    )
    parser.add_argument(
        '--model', metavar='MODEL_KEY',
        choices=_all_model_keys,
        default=None,
        help=(
            f"Which model's output folder to evaluate "
            f"({', '.join(_all_model_keys)}). "
            "Defaults to the MODEL_KEY set in model_config.py."
        )
    )
    parser.add_argument(
        '--all-models', action='store_true',
        help='Evaluate ALL models sequentially and write one metrics file per model.'
    )
    parser.add_argument('--include-baselines', action='store_true',
                        help='Include 4 non-LLM baselines (Random, Uniform, FixedDefault, NearestNeighbor)')
    args = parser.parse_args()

    def _output_stem(mk):
        """Return output path stem for model mk."""
        od = PROJECT_ROOT / get_output_folder(mk)
        return str(od / f"metrics_summary_{mk}.xlsx")

    if args.all_models:
        all_mode_dfs = {"filtered": [], "imputed": []}
        for mk in _all_model_keys:
            cfg = _build_config(mk)
            cfg["output_csv"] = _output_stem(mk)
            mdf, _ = evaluate_all(cfg, include_baselines=args.include_baselines, model_key=mk)
            shared = mdf[mdf["mode"].isna()]
            for mode_key in ("filtered", "imputed"):
                md = pd.concat([
                    mdf[mdf["mode"] == mode_key],
                    shared.assign(mode=mode_key),
                ], ignore_index=True).drop(columns=["mode"])
                md["model"] = mk
                all_mode_dfs[mode_key].append(md)
        for mode_key in ("filtered", "imputed"):
            combined = pd.concat(all_mode_dfs[mode_key], ignore_index=True)
            suffix = "" if mode_key == "filtered" else "_imputed"
            _atomic_write_xlsx(combined, str(PROJECT_ROOT / "Analysis" / "MetricsSummary" / f"metrics_summary_all_models{suffix}.xlsx"))
        print(f"\nCombined metrics saved for all models.")
    else:
        mk = args.model if args.model else MODEL_KEY
        cfg = _build_config(mk)
        cfg["output_csv"] = _output_stem(mk)
        metrics_df, merged_dfs = evaluate_all(cfg, include_baselines=args.include_baselines, model_key=mk)

