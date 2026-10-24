#!/usr/bin/env python3
"""
run_baseline_models.py - Non-LLM Baselines
Computes three baselines for MCDA architecture comparison: random, uniform and nearest-neighbor copy.
"""
import argparse
import os
import sys
import warnings
import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))

from common.paths import (
    RUN_OUTPUT_DIR_ENV,
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_directory,
)
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY
from common.sentinel_utils import (read_table_clean, SENTINEL_VALUE, has_sentinel_scores, apply_mavt_ranking,
                            MAVT_ROUND_DECIMALS)

from scripts.experiments.run_rag_ablation_experiments import (
    nearest_neighbor_prediction,
    NN_FALLBACKS,
    build_collection,
    retrieve_similar,
    load_source_groups,
    stratified_sample,
    format_embedding_text,
)

warnings.filterwarnings("default")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
SCENARIO_DIR = PROJECT_ROOT / "workbooks/scenarios"
GROUND_TRUTH_DIR = PROJECT_ROOT / "workbooks/ground_truth"
COMMON_STR_COLS = [
    'question', 'location', 'alternative', 'housing_type', 
    'insulation', 'appliance', 'appliance_age', 'house_age',
]

def _rank_with_deterministic_tiebreak(scores_df, weighted_col, tiebreak_cols, log_prefix=""):
    """Rank rows by `weighted_col` desc with deterministic tie-breaking. The
    weighted score is rounded to MAVT_ROUND_DECIMALS first, the same rule as
    sentinel_utils.apply_mavt_ranking, so floating-point noise can't split a tie."""
    df = scores_df.copy()
    df[weighted_col] = df[weighted_col].astype(float).round(MAVT_ROUND_DECIMALS)
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

def normalize_alternative(alt, decision_type):
    """Normalize alternative values for cross-file matching."""
    alt = str(alt).strip()
    if decision_type == "Appliance":
        import re
        match = re.search(r'(\d{1,2}:\d{2}\s*[AaPp][Mm])', alt)
        if match: return match.group(1).strip().upper()
        match = re.search(r'(\d{1,2})\s*([AaPp][Mm])', alt)
        if match: return f"{match.group(1)}:00 {match.group(2).upper()}"
        return alt.strip().upper()
    if decision_type == "HVAC":
        alt_lower = alt.lower()
        if "off" in alt_lower:
            import re
            match = re.search(r'(\d+(?:\.\d+)?)', alt_lower)
            return f"off_{match.group(1)}" if match else "off"
        try: return str(int(float(alt)))
        except ValueError: return alt
    if decision_type == "Shower":
        try:
            value = float(alt)
            return str(int(value)) if value.is_integer() else str(value)
        except ValueError: return alt
    return alt

# =============================================================================
# BASELINES
# =============================================================================
def run_nearest_neighbor_baseline(test_df, k=1, fallback="tie"):
    groups_by_type = load_source_groups()
    from scripts.experiments.run_rag_ablation_experiments import DEFAULT_EMBEDDING_MODEL
    import tempfile, shutil
    temp_path, collection, model, _ = build_collection(DEFAULT_EMBEDDING_MODEL, Path(tempfile.gettempdir()))
    try:
        all_rows = []
        for idx, row in test_df.iterrows():
            dtype = row['decision_type']
            # The retrieval query is built exactly as A_E builds its own: the
            # Test row's fields go to sentinel_utils.format_embedding_text
            # (called inside retrieve_similar), including the row's flow_rate
            # label for Shower. Nothing is parsed from the question and no hidden
            # parameter is filled in: the embedding reads only homeowner fields.
            # source_scenario_id is namespaced so it can never equal a RAG
            # scenario's id and wrongly exclude that exemplar from retrieval.
            scenario = {
                **row.to_dict(),
                'decision_type': dtype, 'scenario_id': f"{dtype.lower()}_{idx}",
                'source_scenario_id': f"test_{idx}", 'source_position': idx + 1,
                'alternatives': [],
            }

            for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
                if not pd.isna(row.get(alt_col)) and str(row.get(alt_col)).strip().lower() not in ('', 'nan'):
                    val = float(row[alt_col]) if dtype == "Shower" else str(row[alt_col]).strip()
                    scenario['alternatives'].append({'alternative': val})
            
            retrieved = retrieve_similar(collection, model, scenario, k)
            result = nearest_neighbor_prediction(scenario, retrieved, fallback=fallback)
            for pred in result["predictions"]:
                all_rows.append({
                    'scenario_id': idx, 'question': row['question'], 'location': row['location'], 'decision_type': dtype,
                    'alternative': pred['alternative'], 'energy_cost_score': pred['scores']['energy_cost'],
                    'environmental_score': pred['scores']['environmental'], 'comfort_score': pred['scores']['comfort'],
                    'practicality_score': pred['scores']['practicality'], 'mavt_score': pred['weighted_score'], 'rank': pred['rank']
                })
        return pd.DataFrame(all_rows)
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)

def _rank_with_weights_and_tiebreak(group):
    """Rank alternatives within a group by mavt_score desc with deterministic tie-break."""
    tiebreak_cols = [f"{c}_score" for c in TIE_BREAK_PRIORITY]
    # Sort on the rounded sum (same rule as sentinel_utils.apply_mavt_ranking);
    # the stored mavt_score keeps its full value.
    group = group.assign(_mavt_sort=group['mavt_score'].astype(float).round(MAVT_ROUND_DECIMALS))
    sort_cols = ['_mavt_sort'] + tiebreak_cols
    group_sorted = group.sort_values(sort_cols, ascending=[False] * len(sort_cols), kind="mergesort")
    group_sorted = group_sorted.drop(columns=['_mavt_sort'])
    group_sorted['rank'] = range(1, len(group_sorted) + 1)
    return group_sorted

def run_random_baseline(test_df, n_seeds=20, rng_seed=42):
    """Random baseline: random scores for every alternative."""
    rng = np.random.default_rng(rng_seed)
    weights = CRITERION_WEIGHTS
    criteria = list(weights.keys())
    all_rows = []
    for idx, row in test_df.iterrows():
        dtype = row['decision_type']
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            if not pd.isna(row.get(alt_col)) and str(row.get(alt_col)).strip().lower() not in ('', 'nan'):
                val = float(row[alt_col]) if dtype == "Shower" else str(row[alt_col]).strip()
                alternatives.append(val)
        for seed in range(n_seeds):
            rng = np.random.default_rng(rng_seed + seed + idx * 7)
            group_rows = []
            for alt in alternatives:
                scores = {c: rng.uniform(0, 100) for c in criteria}
                mavt = sum(weights[c] * scores[c] for c in criteria)
                group_rows.append({
                    'scenario_id': idx, 'seed': seed,
                    'question': str(row['question']).strip(),
                    'location': str(row['location']).strip(),
                    'decision_type': dtype,
                    'alternative': str(alt),
                    'energy_cost_score': scores['energy_cost'],
                    'environmental_score': scores['environmental'],
                    'comfort_score': scores['comfort'],
                    'practicality_score': scores['practicality'],
                    'mavt_score': mavt,
                })
            group_df = pd.DataFrame(group_rows)
            ranked = _rank_with_weights_and_tiebreak(group_df)
            all_rows.append(ranked)
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()

def run_uniform_baseline(test_df):
    """Uniform baseline: all alternatives get identical scores."""
    weights = CRITERION_WEIGHTS
    criteria = list(weights.keys())
    uniform_scores = {c: 50.0 for c in criteria}
    uniform_mavt = sum(weights[c] * uniform_scores[c] for c in criteria)
    all_rows = []
    for idx, row in test_df.iterrows():
        dtype = row['decision_type']
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            if not pd.isna(row.get(alt_col)) and str(row.get(alt_col)).strip().lower() not in ('', 'nan'):
                val = float(row[alt_col]) if dtype == "Shower" else str(row[alt_col]).strip()
                alternatives.append(val)
        group_rows = []
        for alt in alternatives:
            group_rows.append({
                'scenario_id': idx,
                'question': str(row['question']).strip(),
                'location': str(row['location']).strip(),
                'decision_type': dtype,
                'alternative': str(alt),
                'energy_cost_score': uniform_scores['energy_cost'],
                'environmental_score': uniform_scores['environmental'],
                'comfort_score': uniform_scores['comfort'],
                'practicality_score': uniform_scores['practicality'],
                'mavt_score': uniform_mavt,
            })
        group_df = pd.DataFrame(group_rows)
        ranked = _rank_with_weights_and_tiebreak(group_df)
        all_rows.append(ranked)
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()

def run_all_baselines(test_df, baselines=None, k=1, nn_fallback="tie"):
    if baselines is None: baselines = ['random', 'uniform', 'nearest_neighbor']
    results = {}
    if 'random' in baselines:
        print("Running Random baseline..."); results['Random'] = run_random_baseline(test_df)
    if 'uniform' in baselines:
        print("Running Uniform baseline..."); results['Uniform'] = run_uniform_baseline(test_df)
    if 'nearest_neighbor' in baselines:
        print("Running Nearest-Neighbor baseline..."); results['NearestNeighbor'] = run_nearest_neighbor_baseline(test_df, k=k, fallback=nn_fallback)
    return results

def main(argv=None):
    parser = argparse.ArgumentParser(description="Run non-LLM baselines for MCDA architecture comparison")
    parser.add_argument('--baselines', nargs='+', default=['nearest_neighbor'],
                        choices=['nearest_neighbor', 'all'], help='Which baselines to run')
    # k = 1 matches the benchmark A_E, which retrieves one exemplar,
    # so the copy-only baseline shows what A_E's LLM
    # adds over copying the exemplar it retrieves. The RAG ablation's own copy-only
    # control keeps k = 3 there.
    parser.add_argument('--k', type=int, default=1, help='k for Nearest-Neighbor baseline (default 1, A_E\'s k)')
    parser.add_argument('--nn-fallback', choices=list(NN_FALLBACKS), default='tie',
                        help='Nearest-Neighbor rule for an alternative no exemplar shares: tie (mean over all '
                             'retrieved alternatives, the original rule), nearest (exemplar alternatives nearest '
                             'in value), unscored (a scenario with no label match gets the sentinel)')
    parser.add_argument('--verify', action='store_true', help='Run verification checks')
    parser.add_argument('--baseline', type=str, help='Run single baseline (for verification)')
    parser.add_argument('--assert-top1-min', type=float, help='Assert minimum Top-1 accuracy')
    parser.add_argument('--output-dir', default=os.environ.get(RUN_OUTPUT_DIR_ENV),
                        help=f'Required safe destination for baseline_*.xlsx files '
                             f'(or set {RUN_OUTPUT_DIR_ENV})')
    parser.add_argument('--list', action='store_true',
                        help='List available --baselines choices and exit')
    args = parser.parse_args(argv)

    if args.list:
        print("Available --baselines choices: nearest_neighbor, all")
        return

    try:
        output_dir = require_safe_output_directory(
            args.output_dir,
            option=f"--output-dir (or {RUN_OUTPUT_DIR_ENV})",
            root=PROJECT_ROOT,
        )
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))
    
    baselines = ['nearest_neighbor'] if args.baselines == ['all'] else args.baselines
    
    test_path = SCENARIO_DIR / "TestScenarios.xlsx"
    test_df = read_table_clean(test_path)
    print(f"Loaded {len(test_df)} test scenarios")
    print(f"Decision types: {test_df['decision_type'].value_counts().to_dict()}")
    
    if args.baseline: baselines = [args.baseline]
    
    results = run_all_baselines(test_df, baselines, k=args.k, nn_fallback=args.nn_fallback)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in results.items():
        df.to_excel(output_dir / f"baseline_{name.lower()}.xlsx", index=False, engine="openpyxl")
        print(f"Saved {name} baseline to {output_dir} ({len(df)} rows)")

if __name__ == "__main__":
    main()
