"""Feature-stratified scenario sampling for the RAG ablation experiments.

`stratified_sample_by_features` stratifies by decision type, then, within each
type, by one or two physics-driving parameters (HVAC: outdoor temperature band x
insulation; Appliance: appliance type x age band; Shower: flow-rate band), so a
small `--sample-size` still covers the parameter space instead of risking a
single-stage random draw that misses whole categories. When `sample_size` is
None or at least the pool size, the full pool is returned unchanged (the same
as `--sample-size all`).

Used by `run_rag_ablation_experiments.py` as `stratified_sample`.
"""

from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

DECISION_TYPES = ["HVAC", "Appliance", "Shower"]


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
        Output of `load_source_groups()` from run_rag_ablation_experiments.py.
        Maps decision_type -> list of scenario dicts.
    sample_size : int or None
        Total number of scenarios to draw across all types.
        None means "return everything" (same as `--sample-size all`).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    list of scenario dicts (same structure as run_rag_ablation_experiments.stratified_sample).
    """
    rng = np.random.default_rng(seed)

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
