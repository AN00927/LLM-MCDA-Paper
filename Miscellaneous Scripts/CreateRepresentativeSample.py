#!/usr/bin/env python3
"""
CreateRepresentativeSample.py

Drop-in replacement for the `stratified_sample` function in RunRAGAblations.py.

Problem with the original implementation
-----------------------------------------
`stratified_sample` in RunRAGAblations.py stratifies only by *decision type*
(equal counts per type).  Within each type it draws uniformly at random.

With the default `--sample-size 15` (5 per type from pools of 20–35 scenarios)
a single-stage random draw is very likely to:
  - Miss entire housing-type or insulation categories (HVAC)
  - Miss the old-appliance range (age >10 years, Appliance)
  - Miss extreme flow-rate tails (1.5 GPM low-flow, 3.0–3.5 GPM high-flow, Shower)

This module provides `stratified_sample_by_features`, which:
  1. Stratifies by decision type (same as before).
  2. Within each type, further stratifies by one or two key physics-driving
     parameters so that the sample covers the parameter space proportionally.
  3. Falls back to pure random sampling when sample_size >= pool size (i.e.
     the full pool is returned unchanged, same as `--sample-size all`).

Usage
-----
Option A — use as a standalone script to inspect the sample:
    python "Miscellaneous Scripts/CreateRepresentativeSample.py" --sample-size 33

Option B — replace `stratified_sample` in RunRAGAblations.py:
    from CreateRepresentativeSample import stratified_sample_by_features as stratified_sample

    # Then in run():
    sample = stratified_sample(groups_by_type, sample_size, args.seed)
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import read_table_clean

DECISION_TYPES = ["HVAC", "Appliance", "Shower"]

RAG_FILES = {
    "HVAC":      "HVACRagScenarios.xlsx",
    "Appliance": "ApplianceRAGScenarios.xlsx",
    "Shower":    "ShowerRAGScenarios.xlsx",
}
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"


# ---------------------------------------------------------------------------
# Stratum definitions
# The key variable driving scores for each type, used to bin scenarios into
# strata for proportional sampling.
# ---------------------------------------------------------------------------

def _hvac_stratum(scenario: dict) -> str:
    """Bin HVAC scenario by outdoor_temp quartile + insulation quality."""
    try:
        temp = float(scenario.get("outdoor_temp", 50))
    except (TypeError, ValueError):
        temp = 50.0
    insulation = str(scenario.get("insulation", "Medium")).strip()
    if temp < 30:
        temp_bin = "very_cold"
    elif temp < 55:
        temp_bin = "cold"
    elif temp < 75:
        temp_bin = "mild"
    else:
        temp_bin = "hot"
    return f"{temp_bin}_{insulation}"


def _appliance_stratum(scenario: dict) -> str:
    """Bin Appliance scenario by appliance type + age band."""
    appliance = str(scenario.get("appliance", "unknown")).strip().lower()
    try:
        age = float(scenario.get("appliance_age", 5))
    except (TypeError, ValueError):
        age = 5.0
    if age <= 3:
        age_bin = "new"      # <3 yr
    elif age <= 8:
        age_bin = "mid"      # 4–8 yr
    elif age <= 15:
        age_bin = "old"      # 9–15 yr
    else:
        age_bin = "very_old" # >15 yr
    return f"{appliance}_{age_bin}"


def _shower_stratum(scenario: dict) -> str:
    """Bin Shower scenario by GPM band."""
    try:
        gpm = float(scenario.get("gpm", 2.5))
    except (TypeError, ValueError):
        gpm = 2.5
    if gpm < 2.0:
        return "low_flow"
    elif gpm < 2.5:
        return "medium_low"
    elif gpm < 3.0:
        return "medium_high"
    else:
        return "high_flow"


STRATUM_FN = {
    "HVAC":      _hvac_stratum,
    "Appliance": _appliance_stratum,
    "Shower":    _shower_stratum,
}


def stratified_sample_by_features(
    groups_by_type: Dict[str, List[dict]],
    sample_size: Optional[int],
    seed: int,
) -> List[dict]:
    """
    Stratified sample that covers key feature ranges within each decision type.

    Parameters
    ----------
    groups_by_type : dict
        Output of `load_source_groups()` from RunRAGAblations.py.
        Maps decision_type -> list of scenario dicts.
    sample_size : int or None
        Total number of scenarios to draw across all types.
        None means "return everything" (same as `--sample-size all`).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    list of scenario dicts (same structure as RunRAGAblations.stratified_sample).
    """
    rng = np.random.default_rng(seed)

    # --- full pass-through when sample_size is None or >= total ---
    total_available = sum(len(groups_by_type[dt]) for dt in DECISION_TYPES)
    if sample_size is None or sample_size >= total_available:
        sampled = []
        for dt in DECISION_TYPES:
            sampled.extend(groups_by_type[dt])
        return sampled

    # --- per-type allocation (same as original) ---
    counts = {dt: len(groups_by_type[dt]) for dt in DECISION_TYPES}
    base = sample_size // len(DECISION_TYPES)
    remainder = sample_size % len(DECISION_TYPES)
    allocations = {dt: min(base, counts[dt]) for dt in DECISION_TYPES}
    ordered = sorted(DECISION_TYPES, key=lambda dt: counts[dt], reverse=True)
    for dt in ordered:
        if remainder <= 0:
            break
        if allocations[dt] < counts[dt]:
            allocations[dt] += 1
            remainder -= 1

    # Ensure each type gets at least as many scenarios as it has non-empty strata
    for dt in DECISION_TYPES:
        stratum_fn = STRATUM_FN[dt]
        n_strata = len(set(stratum_fn(s) for s in groups_by_type[dt]))
        if allocations[dt] < n_strata:
            deficit = n_strata - allocations[dt]
            # Steal from types with surplus
            for donor in ordered:
                if donor == dt:
                    continue
                surplus = allocations[donor] - len(set(STRATUM_FN[donor](s) for s in groups_by_type[donor]))
                transfer = min(deficit, surplus)
                if transfer > 0:
                    allocations[donor] -= transfer
                    allocations[dt] += transfer
                    deficit -= transfer
                if deficit <= 0:
                    break

    sampled = []
    for dt in DECISION_TYPES:
        n = allocations[dt]
        pool = groups_by_type[dt]
        if n <= 0:
            continue
        if n >= len(pool):
            sampled.extend(pool)
            continue

        # --- within-type feature stratification ---
        stratum_fn = STRATUM_FN[dt]
        strata: Dict[str, List[int]] = defaultdict(list)
        for idx, scenario in enumerate(pool):
            strata[stratum_fn(scenario)].append(idx)

        selected_indices: List[int] = []

        # Round 1: draw at least 1 from each stratum (shuffle strata order for fairness)
        stratum_keys = list(strata.keys())
        rng.shuffle(stratum_keys)
        for sk in stratum_keys:
            if len(selected_indices) >= n:
                break
            candidates = [i for i in strata[sk] if i not in selected_indices]
            if candidates:
                pick = rng.choice(candidates)
                selected_indices.append(int(pick))

        # Round 2: fill remaining quota uniformly from leftovers
        remaining_quota = n - len(selected_indices)
        if remaining_quota > 0:
            all_idx = set(range(len(pool)))
            leftover = sorted(all_idx - set(selected_indices))
            rng.shuffle(leftover)
            selected_indices.extend(leftover[:remaining_quota])

        selected_indices.sort()
        sampled.extend([pool[i] for i in selected_indices])

    return sampled


# ---------------------------------------------------------------------------
# Diagnostic helper — compares original vs. feature-stratified sample
# ---------------------------------------------------------------------------

def _load_groups():
    """Load the RAG source groups the same way RunRAGAblations does."""
    from sentinel_utils import read_table_clean

    def _to_float(v):
        try:
            return float(v)
        except Exception:
            return float("nan")

    def _clean(v):
        if v is None:
            return ""
        try:
            import pandas as pd
            if pd.isna(v):
                return ""
        except Exception:
            pass
        return str(v).strip()

    groups_by_type = {}
    for dt, fname in RAG_FILES.items():
        df = read_table_clean(SCENARIO_DIR / fname)
        groups = []
        for pos, (sid, grp) in enumerate(df.groupby("scenario_id", sort=False), 1):
            first_row = grp.iloc[0].to_dict()
            alts = []
            for _, row in grp.iterrows():
                alt = {
                    "alternative": _clean(row.get("alternative")),
                    "energy_cost":    _to_float(row.get("energy_cost_score")),
                    "environmental":  _to_float(row.get("environmental_score")),
                    "comfort":        _to_float(row.get("comfort_score")),
                    "practicality":   _to_float(row.get("practicality_score")),
                    "mavt_score":     _to_float(row.get("mavt_score")),
                    "rank":           int(round(_to_float(row.get("rank", 1)))),
                }
                if "duration_min" in row:
                    alt["duration_min"] = _to_float(row.get("duration_min"))
                alts.append(alt)
            # Build a scenario dict compatible with RunRAGAblations
            scenario = dict(first_row)
            scenario.update({
                "decision_type":     dt,
                "source_scenario_id": sid,
                "source_position":   pos,
                "filename":          RAG_FILES[dt],
                "alternatives":      alts,
                "scenario_id":       f"{dt.lower()}_{sid}",
            })
            groups.append(scenario)
        groups_by_type[dt] = groups

    return groups_by_type


def print_coverage_report(groups_by_type, sample, label="sample"):
    """Print a summary of how the sample covers key parameters."""
    from collections import Counter

    print(f"\n--- Coverage report: {label} ---")
    sample_by_type = defaultdict(list)
    for s in sample:
        sample_by_type[s["decision_type"]].append(s)

    for dt in DECISION_TYPES:
        pool  = groups_by_type[dt]
        samp  = sample_by_type[dt]
        fn    = STRATUM_FN[dt]
        full_strata  = Counter(fn(s) for s in pool)
        samp_strata  = Counter(fn(s) for s in samp)
        all_keys = sorted(full_strata.keys())
        print(f"\n  {dt}  (pool={len(pool)}, sample={len(samp)})")
        print(f"  {'Stratum':<30}  {'Pool':>6}  {'Sample':>8}  {'Sample%':>8}")
        for k in all_keys:
            pct = f"{samp_strata[k]/full_strata[k]*100:.0f}%" if full_strata[k] else "—"
            print(f"  {k:<30}  {full_strata[k]:>6}  {samp_strata[k]:>8}  {pct:>8}")
        missing = [k for k in all_keys if samp_strata[k] == 0]
        if missing:
            print(f"  WARN - Missing strata: {missing}")
        else:
            print("  OK - All strata covered")


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Demonstrate representative RAG sampling.")
    parser.add_argument("--sample-size", default="33", help="Total scenarios to draw (int or 'all')")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--compare-original", action="store_true",
                        help="Also run the original stratified_sample and compare coverage")
    args = parser.parse_args()

    sample_size = None if args.sample_size.strip().lower() == "all" else int(args.sample_size)
    print(f"Loading RAG source groups from {SCENARIO_DIR}...")
    groups_by_type = _load_groups()

    for dt in DECISION_TYPES:
        print(f"  {dt}: {len(groups_by_type[dt])} scenarios")

    # --- Feature-stratified sample ---
    feat_sample = stratified_sample_by_features(groups_by_type, sample_size, args.seed)
    print_coverage_report(groups_by_type, feat_sample, label=f"feature-stratified (n={len(feat_sample)})")

    # --- Original random sample (for comparison) ---
    if args.compare_original:
        rng = np.random.default_rng(args.seed)
        counts = {dt: len(groups_by_type[dt]) for dt in DECISION_TYPES}
        n = sample_size or sum(counts.values())
        base = n // 3
        rem  = n % 3
        alloc = {dt: min(base, counts[dt]) for dt in DECISION_TYPES}
        for dt in sorted(DECISION_TYPES, key=lambda x: counts[x], reverse=True):
            if rem <= 0: break
            if alloc[dt] < counts[dt]:
                alloc[dt] += 1; rem -= 1
        orig_sample = []
        for dt in DECISION_TYPES:
            nn = min(alloc[dt], counts[dt])
            idx = rng.choice(counts[dt], size=nn, replace=False)
            orig_sample.extend([groups_by_type[dt][int(i)] for i in sorted(idx)])
        print_coverage_report(groups_by_type, orig_sample, label=f"original random (n={len(orig_sample)})")

    print(f"\nDone. Feature-stratified sample has {len(feat_sample)} scenarios.")


if __name__ == "__main__":
    main()
