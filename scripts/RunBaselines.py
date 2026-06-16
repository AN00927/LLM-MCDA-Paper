#!/usr/bin/env python3
"""
RunBaselines.py - Non-LLM Baselines & Oracle Upper Bound

Computes five baselines for MCDA architecture comparison:
1. Random-choice (chance floor)
2. Uniform/Equal scores
3. Fixed-default-parameter calculator (US/PA averages)
4. Nearest-neighbor (no LLM, from RunRAGAblations)
5. Oracle-parameter calculator (upper bound - true hidden params)

All baselines emit results DataFrames compatible with CalculateMetrics.py's
load_architecture() / match_scenarios() infrastructure.
"""

import argparse
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY
from sentinel_utils import read_table_clean, SENTINEL_VALUE, has_sentinel_scores
from Ground_Truth_Calculators.HVACGroundTruthCalculator import HVACGroundTruthCalculator
from Ground_Truth_Calculators.ApplianceGroundTruthCalculator import ApplianceGroundTruthCalculator
from Ground_Truth_Calculators.ShowerGroundTruthCalculator import ShowerGroundTruthCalculator
# apply_mavt_ranking is defined in each calculator file

# Import nearest-neighbor from RunRAGAblations
from RunRAGAblations import (
    nearest_neighbor_prediction,
    build_collection,
    retrieve_similar,
    load_source_groups,
    stratified_sample,
    format_embedding_text,
)

warnings.filterwarnings("default")

# =============================================================================
# FIXED DEFAULT PARAMETER VALUES (from implementation plan)
# =============================================================================

# HVAC Fixed Defaults
HVAC_DEFAULT_R_VALUE = 15
HVAC_DEFAULT_SEER = 13
HVAC_DEFAULT_HVAC_AGE = 13
HVAC_DEFAULT_SQFT_BY_HOUSING_TYPE = {
    "Single-family": 2000,
    "Townhouse": 1800,
    "Rowhouse": 1800,
    "Twin": 1800,
    "Apartment": 916,
    "Condo": 1100,
}
HVAC_DEFAULT_SQFT_FALLBACK = 2000
HVAC_DEFAULT_HOUSEHOLD_SIZE = 2.54
HVAC_DEFAULT_OUTDOOR_TEMP = 51.8  # Pittsburgh annual mean °F
HVAC_DEFAULT_UTILITY_BUDGET = 430

# Appliance Fixed Defaults
APPLIANCE_DEFAULT_KWH_PER_CYCLE = {
    "Washer": 0.55,
    "Dryer": 2.10,
    "Dishwasher": 1.00,
}
APPLIANCE_DEFAULT_KWH_FALLBACK = 1.00
APPLIANCE_DEFAULT_AGE_YEARS = 11
APPLIANCE_DEFAULT_HOUSEHOLD_SIZE = 2.54
APPLIANCE_DEFAULT_UTILITY_BUDGET = 430
APPLIANCE_DEFAULT_HOUSING_TYPE = "Single-family"

# Shower Fixed Defaults
SHOWER_DEFAULT_GPM = 2.5
SHOWER_DEFAULT_TANK_SIZE = 50
SHOWER_DEFAULT_WATER_HEATER_TEMP = 120
SHOWER_DEFAULT_OUTDOOR_TEMP = 51.8
SHOWER_DEFAULT_HOUSEHOLD_SIZE = 2.54
SHOWER_DEFAULT_HOUSING_TYPE = "Single-family"
SHOWER_DEFAULT_UTILITY_BUDGET = 430

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"
COMMON_STR_COLS = [
    'question', 'location', 'alternative',
    'housing_type', 'insulation', 'appliance', 'appliance_age', 'house_age',
]

def _coerce_score_columns(df, score_cols):
    for c in score_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _rank_with_deterministic_tiebreak(scores_df, weighted_col, tiebreak_cols, log_prefix=""):
    """Rank rows by `weighted_col` desc with deterministic tie-breaking."""
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


def normalize_alternative(alt, decision_type):
    """Normalize alternative values for cross-file matching (copied from CalculateMetrics)."""
    alt = str(alt).strip()
    if decision_type == "Appliance":
        import re
        match = re.search(r'(\d{1,2}:\d{2}\s*[AaPp][Mm])', alt)
        if match:
            return match.group(1).strip().upper()
        match = re.search(r'(\d{1,2})\s*([AaPp][Mm])', alt)
        if match:
            hour = match.group(1)
            ampm = match.group(2).upper()
            return f"{hour}:00 {ampm}"
        return alt.strip().upper()
    if decision_type == "HVAC":
        alt_lower = alt.lower()
        if "off" in alt_lower:
            import re
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


def build_scenario_from_test(row, decision_type):
    """Build a scenario dict from TestScenarios row for the GT calculators."""
    scenario = {
        'question': row['question'],
        'location': row['location'],
        'household_size': int(row['household_size']),
        'utility_budget': float(row.get('utility_budget', 0)),
        'housing_type': str(row.get('housing_type', 'Single-family')),
    }
    
    if decision_type == "HVAC":
        scenario.update({
            'square_footage': int(row['square_footage']),
            'outdoor_temp': float(row['outdoor_temp']),
            'hvac_age': HVAC_DEFAULT_HVAC_AGE,
            'r_value': HVAC_DEFAULT_R_VALUE,
            'seer': HVAC_DEFAULT_SEER,
            'occupancy_context': 'occupied_all_day',
            'electricity_rate': HVACGroundTruthCalculator.ELECTRICITY_RATE_PA,
            'alternative_1': str(row['alternative_1']),
            'alternative_2': str(row['alternative_2']),
            'alternative_3': str(row['alternative_3']),
        })
        # Collect alternatives
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()
            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)
        scenario['alternatives'] = alternatives
        
    elif decision_type == "Appliance":
        # For fixed-default, we use the appliance type from the question
        # and kWh per cycle from defaults
        app_type = None
        q_lower = row['question'].lower()
        if 'washing machine' in q_lower or 'washer' in q_lower:
            app_type = 'Washer'
        elif 'dryer' in q_lower:
            app_type = 'Dryer'
        elif 'dishwasher' in q_lower:
            app_type = 'Dishwasher'
        
        kwh_per_cycle = APPLIANCE_DEFAULT_KWH_PER_CYCLE.get(app_type, APPLIANCE_DEFAULT_KWH_FALLBACK)
        
        scenario.update({
            'appliance': app_type or 'Washer',
            'kwh_per_cycle': kwh_per_cycle,
            'appliance_age': APPLIANCE_DEFAULT_AGE_YEARS,
            'baseline_time': '7pm',  # Default baseline
            'alternative_1': str(row['alternative_1']),
            'alternative_2': str(row['alternative_2']),
            'alternative_3': str(row['alternative_3']),
        })
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()
            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)
        scenario['alternatives'] = alternatives
        
    elif decision_type == "Shower":
        scenario.update({
            'gpm': SHOWER_DEFAULT_GPM,
            'tank_size': SHOWER_DEFAULT_TANK_SIZE,
            'water_heater_temp': SHOWER_DEFAULT_WATER_HEATER_TEMP,
            'outdoor_temp': SHOWER_DEFAULT_OUTDOOR_TEMP,
            'alternative_1': str(row['alternative_1']),
            'alternative_2': str(row['alternative_2']),
            'alternative_3': str(row['alternative_3']),
        })
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()
            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(float(alt_val))
        scenario['alternatives'] = alternatives
        
    return scenario


def build_scenario_from_test_oracle(row, decision_type):
    """Build a scenario dict from TestScenarios row using TRUE hidden params from GT files."""
    # We need to look up the true hidden parameters from the ground truth XLSX
    gt_files = {
        "HVAC": GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx",
        "Appliance": GROUND_TRUTH_DIR / "ground_truth_appliance.xlsx",
        "Shower": GROUND_TRUTH_DIR / "ground_truth_shower.xlsx",
    }
    gt_df = read_table_clean(gt_files[decision_type], keep_str_cols=COMMON_STR_COLS)
    
    # Match by question and location
    q = row['question'].strip()
    loc = row['location'].strip()
    
    gt_match = gt_df[(gt_df['question'].str.strip() == q) & (gt_df['location'].str.strip() == loc)]
    if gt_match.empty:
        raise ValueError(f"No GT match for {decision_type}: '{q}' at '{loc}'")
    
    # Get the first matching scenario's hidden params
    gt_row = gt_match.iloc[0]
    
    scenario = {
        'question': row['question'],
        'location': row['location'],
        'household_size': int(row['household_size']),
        'utility_budget': float(row.get('utility_budget', 0)),
        'housing_type': str(row.get('housing_type', 'Single-family')),
    }
    
    if decision_type == "HVAC":
        scenario.update({
            'square_footage': int(gt_row['square_footage']),
            'outdoor_temp': float(gt_row['outdoor_temp']),
            'hvac_age': int(gt_row['hvac_age']),
            'r_value': int(gt_row['r_value']),
            'seer': int(gt_row['seer']),
            'occupancy_context': 'occupied_all_day',
            'electricity_rate': HVACGroundTruthCalculator.ELECTRICITY_RATE_PA,
            'alternative_1': str(row['alternative_1']),
            'alternative_2': str(row['alternative_2']),
            'alternative_3': str(row['alternative_3']),
        })
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()
            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)
        scenario['alternatives'] = alternatives
        
    elif decision_type == "Appliance":
        app_type = gt_row['appliance']
        kwh_per_cycle = float(gt_row['kwh_per_cycle'])
        scenario.update({
            'appliance': app_type,
            'kwh_per_cycle': kwh_per_cycle,
            'appliance_age': gt_row['appliance_age'],
            'baseline_time': gt_row.get('baseline_time', '7pm'),
            'alternative_1': str(row['alternative_1']),
            'alternative_2': str(row['alternative_2']),
            'alternative_3': str(row['alternative_3']),
        })
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()
            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)
        scenario['alternatives'] = alternatives
        
    elif decision_type == "Shower":
        scenario.update({
            'gpm': float(gt_row['gpm']),
            'tank_size': float(gt_row['tank_size']),
            'water_heater_temp': float(gt_row['water_heater_temp']),
            'outdoor_temp': float(gt_row['outdoor_temp']),
            'alternative_1': str(row['alternative_1']),
            'alternative_2': str(row['alternative_2']),
            'alternative_3': str(row['alternative_3']),
        })
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()
            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(float(alt_val))
        scenario['alternatives'] = alternatives
        
    return scenario


def run_calculator_on_scenarios(decision_type, scenarios, calculator_class):
    """Run a GT calculator on a list of scenarios and return results DataFrame."""
    calculator = calculator_class()
    all_results = []
    
    for idx, scenario in enumerate(scenarios):
        try:
            scores = calculator.calculate_scenario_scores(scenario)
            alts_for_ranking = [
                {
                    "alternative": alt,
                    "energy_cost": scores[alt]["energy_cost_score"],
                    "environmental": scores[alt]["environmental_score"],
                    "comfort": scores[alt]["comfort_score"],
                    "practicality": scores[alt]["practicality_score"]
                }
                for alt in scores
            ]
            ranking_result = apply_mavt_ranking(alts_for_ranking)
            
            for alt_idx, (alt, alt_scores) in enumerate(scores.items()):
                result_row = {
                    'scenario_id': idx,
                    'question': scenario['question'],
                    'location': scenario['location'],
                    'decision_type': decision_type,
                    'alternative': alt,
                    'energy_cost_score': alt_scores['energy_cost_score'],
                    'environmental_score': alt_scores['environmental_score'],
                    'comfort_score': alt_scores['comfort_score'],
                    'practicality_score': alt_scores['practicality_score'],
                    'mavt_score': ranking_result["weighted_scores"][alt_idx],
                    'rank': ranking_result["ranks"][alt_idx],
                }
                # Add decision-type specific fields
                if decision_type == "HVAC":
                    result_row.update({
                        'square_footage': scenario['square_footage'],
                        'insulation': scenario.get('insulation', ''),
                        'outdoor_temp': scenario['outdoor_temp'],
                        'house_age': scenario.get('house_age', ''),
                        'housing_type': scenario['housing_type'],
                    })
                elif decision_type == "Appliance":
                    result_row.update({
                        'appliance': scenario['appliance'],
                        'appliance_age': scenario['appliance_age'],
                        'housing_type': scenario['housing_type'],
                        'household_size': scenario['household_size'],
                        'kwh_per_cycle': scenario['kwh_per_cycle'],
                    })
                elif decision_type == "Shower":
                    result_row.update({
                        'household_size': scenario['household_size'],
                        'gpm': scenario['gpm'],
                        'utility_budget': scenario['utility_budget'],
                        'housing_type': scenario['housing_type'],
                        'outdoor_temp': scenario['outdoor_temp'],
                        'duration_min': alt_scores.get('duration_min', 0),
                    })
                all_results.append(result_row)
        except Exception as e:
            print(f"ERROR processing {decision_type} scenario {idx}: {e}")
            # Emit sentinel rows for all alternatives
            for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
                if alt_col in scenario:
                    alt_val = scenario[alt_col]
                    if alt_val:
                        all_results.append({
                            'scenario_id': idx,
                            'question': scenario['question'],
                            'location': scenario['location'],
                            'decision_type': decision_type,
                            'alternative': alt_val,
                            'energy_cost_score': SENTINEL_VALUE,
                            'environmental_score': SENTINEL_VALUE,
                            'comfort_score': SENTINEL_VALUE,
                            'practicality_score': SENTINEL_VALUE,
                            'mavt_score': SENTINEL_VALUE,
                            'rank': SENTINEL_VALUE,
                        })
            continue
    
    results_df = pd.DataFrame(all_results)
    return results_df


# =============================================================================
# BASELINE 1: RANDOM-CHOICE
# =============================================================================

def run_random_baseline(test_df, n_seeds=1000):
    """Random permutation of ranks for each scenario. Average over N seeds."""
    results_by_seed = []
    
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        all_rows = []
        
        for idx, row in test_df.iterrows():
            dtype = row['decision_type']
            alternatives = []
            for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
                alt_val = str(row[alt_col]).strip()
                if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                    continue
                alternatives.append(alt_val)
            
            if len(alternatives) < 2:
                continue
            
            # Random permutation of ranks 1..n
            n = len(alternatives)
            ranks = list(range(1, n + 1))
            rng.shuffle(ranks)
            
            # Criterion scores: 0.5 + tiny noise to break ties toward random permutation
            for alt_idx, alt in enumerate(alternatives):
                noise = rng.normal(0, 1e-6, 4)
                all_rows.append({
                    'scenario_id': idx,
                    'question': row['question'],
                    'location': row['location'],
                    'decision_type': dtype,
                    'alternative': alt,
                    'energy_cost_score': 0.5 + noise[0],
                    'environmental_score': 0.5 + noise[1],
                    'comfort_score': 0.5 + noise[2],
                    'practicality_score': 0.5 + noise[3],
                    'mavt_score': 0.5 + noise.mean(),
                    'rank': ranks[alt_idx],
                })
        
        df = pd.DataFrame(all_rows)
        # Compute overall metrics for this seed
        merged_rows = []
        for sid in df['scenario_id'].unique():
            sc = df[df['scenario_id'] == sid]
            if len(sc) < 2:
                continue
            # We need ground truth ranks to compute metrics - but for the baseline
            # script we just return the raw predictions. CalculateMetrics will handle matching.
            pass
        results_by_seed.append(df)
    
    # Return list of DataFrames (one per seed) - CalculateMetrics will aggregate
    # For now, return the first seed's results with a marker for multi-seed
    # Actually, let's return the averaged results (mean over seeds)
    # But since ranks are discrete, we average the metrics, not the ranks
    
    # Instead, return all seeds' DataFrames concatenated with a 'seed' column
    for seed, df in enumerate(results_by_seed):
        df['seed'] = seed
    return pd.concat(results_by_seed, ignore_index=True)


# =============================================================================
# BASELINE 2: UNIFORM/EQUAL SCORES
# =============================================================================

def run_uniform_baseline(test_df):
    """All alternatives get 0.5 on every criterion. Tie-break by TIE_BREAK_PRIORITY."""
    all_rows = []
    
    for idx, row in test_df.iterrows():
        dtype = row['decision_type']
        alternatives = []
        for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
            alt_val = str(row[alt_col]).strip()
            if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                continue
            alternatives.append(alt_val)
        
        n = len(alternatives)
        if n == 0:
            continue
        
        # All scores = 0.5
        for alt in alternatives:
            all_rows.append({
                'scenario_id': idx,
                'question': row['question'],
                'location': row['location'],
                'decision_type': dtype,
                'alternative': alt,
                'energy_cost_score': 0.5,
                'environmental_score': 0.5,
                'comfort_score': 0.5,
                'practicality_score': 0.5,
                'mavt_score': 0.5,
                'rank': SENTINEL_VALUE,  # Will be computed by ranking
            })
    
    df = pd.DataFrame(all_rows)
    
    # Compute ranks with deterministic tie-break (TIE_BREAK_PRIORITY)
    # Since all scores are identical, tie-break will use the priority order
    arch_score_to_col = {
        "energy_cost": "energy_cost_score",
        "environmental": "environmental_score",
        "comfort": "comfort_score",
        "practicality": "practicality_score",
    }
    tiebreak_cols = [arch_score_to_col[c] for c in TIE_BREAK_PRIORITY]
    
    for sid in df['scenario_id'].unique():
        sc_mask = df['scenario_id'] == sid
        sc = df[sc_mask]
        ranks = _rank_with_deterministic_tiebreak(sc, 'mavt_score', tiebreak_cols)
        df.loc[sc_mask, 'rank'] = ranks.astype(int)
    
    return df


# =============================================================================
# BASELINE 3: FIXED-DEFAULT PARAMETER CALCULATOR
# =============================================================================

def run_fixed_default_baseline(test_df):
    """Run GT calculators with US/PA average hidden parameters."""
    hvac_scenarios = []
    appliance_scenarios = []
    shower_scenarios = []
    
    for idx, row in test_df.iterrows():
        dtype = row['decision_type']
        if dtype == "HVAC":
            hvac_scenarios.append(build_scenario_from_test(row, "HVAC"))
        elif dtype == "Appliance":
            appliance_scenarios.append(build_scenario_from_test(row, "Appliance"))
        elif dtype == "Shower":
            shower_scenarios.append(build_scenario_from_test(row, "Shower"))
    
    all_results = []
    
    if hvac_scenarios:
        hvac_results = run_calculator_on_scenarios("HVAC", hvac_scenarios, HVACGroundTruthCalculator)
        all_results.append(hvac_results)
    
    if appliance_scenarios:
        appliance_results = run_calculator_on_scenarios("Appliance", appliance_scenarios, ApplianceGroundTruthCalculator)
        all_results.append(appliance_results)
    
    if shower_scenarios:
        shower_results = run_calculator_on_scenarios("Shower", shower_scenarios, ShowerGroundTruthCalculator)
        all_results.append(shower_results)
    
    if all_results:
        return pd.concat(all_results, ignore_index=True)
    return pd.DataFrame()


# =============================================================================
# BASELINE 4: NEAREST-NEIGHBOR (NO LLM)
# =============================================================================

def run_nearest_neighbor_baseline(test_df, k=3):
    """Run nearest-neighbor prediction using RAG exemplars (llm=False)."""
    # Load source groups (RAG exemplars)
    groups_by_type = load_source_groups()
    
    # Build embedding model and collection (use default embedding model)
    from RunRAGAblations import DEFAULT_EMBEDDING_MODEL
    import tempfile
    
    temp_root = Path(tempfile.gettempdir())
    temp_path, collection, model, groups_by_type_loaded = build_collection(DEFAULT_EMBEDDING_MODEL, temp_root)
    
    try:
        all_rows = []
        
        for idx, row in test_df.iterrows():
            dtype = row['decision_type']
            
            # Build scenario dict in the format expected by nearest_neighbor_prediction
            # Need to match the format from load_source_groups
            scenario = {
                'decision_type': dtype,
                'scenario_id': f"{dtype.lower()}_{idx}",
                'source_scenario_id': idx,
                'source_position': idx + 1,
                'question': row['question'],
                'location': row['location'],
                'household_size': row['household_size'],
                'housing_type': row['housing_type'],
                'utility_budget': row.get('utility_budget', 0),
                'alternatives': [],
            }
            
            if dtype == "HVAC":
                scenario.update({
                    'outdoor_temp': row['outdoor_temp'],
                    'insulation': row['insulation'],
                    'square_footage': row['square_footage'],
                    'house_age': row['house_age'],
                })
            elif dtype == "Appliance":
                # Parse appliance type from question
                q_lower = row['question'].lower()
                if 'washing machine' in q_lower or 'washer' in q_lower:
                    app_type = 'washing_machine'
                elif 'dryer' in q_lower:
                    app_type = 'dryer'
                elif 'dishwasher' in q_lower:
                    app_type = 'dishwasher'
                else:
                    app_type = 'washing_machine'
                scenario.update({
                    'appliance': app_type,
                    'appliance_age': row['appliance_age'],
                    'kwh_per_cycle': 0,  # Not used for retrieval
                })
            elif dtype == "Shower":
                scenario.update({
                    'outdoor_temp': row['outdoor_temp'],
                    'gpm': 2.5,  # Default for retrieval
                    'flow_rate': 'standard',
                    'tank_size': 50,
                    'water_heater_temp': 120,
                })
            
            # Add alternatives
            for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
                alt_val = str(row[alt_col]).strip()
                if pd.isna(row[alt_col]) or alt_val == '' or alt_val == 'nan':
                    continue
                if dtype == "Shower":
                    alt_val = float(alt_val)
                scenario['alternatives'].append({'alternative': alt_val})
            
            # Retrieve similar
            retrieved = retrieve_similar(collection, model, scenario, k)
            
            # Run nearest neighbor prediction (llm=False)
            result = nearest_neighbor_prediction(scenario, retrieved)
            predictions = result["predictions"]
            
            for pred in predictions:
                all_rows.append({
                    'scenario_id': idx,
                    'question': row['question'],
                    'location': row['location'],
                    'decision_type': dtype,
                    'alternative': pred['alternative'],
                    'energy_cost_score': pred['scores']['energy_cost'],
                    'environmental_score': pred['scores']['environmental'],
                    'comfort_score': pred['scores']['comfort'],
                    'practicality_score': pred['scores']['practicality'],
                    'mavt_score': pred['weighted_score'],
                    'rank': pred['rank'],
                })
        
        return pd.DataFrame(all_rows)
    finally:
        # Cleanup temp directory
        import shutil
        shutil.rmtree(temp_path, ignore_errors=True)


# =============================================================================
# BASELINE 5: ORACLE (TRUE HIDDEN PARAMETERS)
# =============================================================================

def run_oracle_baseline(test_df):
    """Run GT calculators with TRUE hidden parameters from GT XLSX files."""
    hvac_scenarios = []
    appliance_scenarios = []
    shower_scenarios = []
    
    for idx, row in test_df.iterrows():
        dtype = row['decision_type']
        if dtype == "HVAC":
            hvac_scenarios.append(build_scenario_from_test_oracle(row, "HVAC"))
        elif dtype == "Appliance":
            appliance_scenarios.append(build_scenario_from_test_oracle(row, "Appliance"))
        elif dtype == "Shower":
            shower_scenarios.append(build_scenario_from_test_oracle(row, "Shower"))
    
    all_results = []
    
    if hvac_scenarios:
        hvac_results = run_calculator_on_scenarios("HVAC", hvac_scenarios, HVACGroundTruthCalculator)
        all_results.append(hvac_results)
    
    if appliance_scenarios:
        appliance_results = run_calculator_on_scenarios("Appliance", appliance_scenarios, ApplianceGroundTruthCalculator)
        all_results.append(appliance_results)
    
    if shower_scenarios:
        shower_results = run_calculator_on_scenarios("Shower", shower_scenarios, ShowerGroundTruthCalculator)
        all_results.append(shower_results)
    
    if all_results:
        return pd.concat(all_results, ignore_index=True)
    return pd.DataFrame()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_all_baselines(test_df, baselines=None, n_seeds=1000, k=3):
    """Run specified baselines and return dict of DataFrames."""
    if baselines is None:
        baselines = ['random', 'uniform', 'fixed_default', 'nearest_neighbor', 'oracle']
    
    results = {}
    
    if 'random' in baselines:
        print("Running Random baseline...")
        results['Random'] = run_random_baseline(test_df, n_seeds=n_seeds)
    
    if 'uniform' in baselines:
        print("Running Uniform baseline...")
        results['Uniform'] = run_uniform_baseline(test_df)
    
    if 'fixed_default' in baselines:
        print("Running Fixed-Default baseline...")
        results['FixedDefault'] = run_fixed_default_baseline(test_df)
    
    if 'nearest_neighbor' in baselines:
        print("Running Nearest-Neighbor baseline...")
        results['NearestNeighbor'] = run_nearest_neighbor_baseline(test_df, k=k)
    
    if 'oracle' in baselines:
        print("Running Oracle baseline...")
        results['Oracle'] = run_oracle_baseline(test_df)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Run non-LLM baselines and oracle upper bound")
    parser.add_argument('--baselines', nargs='+', default=['random', 'uniform', 'fixed_default', 'nearest_neighbor', 'oracle'],
                        choices=['random', 'uniform', 'fixed_default', 'nearest_neighbor', 'oracle', 'all'],
                        help='Which baselines to run')
    parser.add_argument('--seeds', type=int, default=1000, help='Number of seeds for Random baseline')
    parser.add_argument('--k', type=int, default=3, help='k for Nearest-Neighbor baseline')
    parser.add_argument('--verify', action='store_true', help='Run verification checks')
    parser.add_argument('--baseline', type=str, help='Run single baseline (for verification)')
    parser.add_argument('--assert-top1-min', type=float, help='Assert minimum Top-1 accuracy')
    
    args = parser.parse_args()
    
    if args.baselines == ['all']:
        baselines = ['random', 'uniform', 'fixed_default', 'nearest_neighbor', 'oracle']
    else:
        baselines = args.baselines
    
    # Load TestScenarios
    test_path = SCENARIO_DIR / "TestScenarios.xlsx"
    test_df = read_table_clean(test_path)
    print(f"Loaded {len(test_df)} test scenarios")
    print(f"Decision types: {test_df['decision_type'].value_counts().to_dict()}")
    
    if args.baseline:
        # Single baseline for verification
        baselines = [args.baseline]
    
    results = run_all_baselines(test_df, baselines, n_seeds=args.seeds, k=args.k)
    
    # Save each baseline's results
    OUTPUT_DIR = PROJECT_ROOT / "Output Files" / "Baselines"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for name, df in results.items():
        if name == 'Random':
            # Save all seeds separately for analysis
            for seed in df['seed'].unique():
                seed_df = df[df['seed'] == seed].drop(columns=['seed'])
                out_path = OUTPUT_DIR / f"baseline_random_seed_{seed}.xlsx"
                seed_df.to_excel(out_path, index=False, engine="openpyxl")
            # Also save aggregated
            out_path = OUTPUT_DIR / "baseline_random_aggregated.xlsx"
            df.to_excel(out_path, index=False, engine="openpyxl")
        else:
            out_path = OUTPUT_DIR / f"baseline_{name.lower()}.xlsx"
            df.to_excel(out_path, index=False, engine="openpyxl")
        print(f"Saved {name} baseline to {out_path} ({len(df)} rows)")
    
    # Verification checks
    if args.verify or args.assert_top1_min is not None:
        print("\n=== VERIFICATION ===")
        
        # Load GT for comparison
        from CalculateMetrics import load_ground_truth, build_gt_lookup, build_gt_id_lookup, match_scenarios, compute_ranking_metrics, filter_failed_scenarios
        
        config = {
            "ground_truth": {
                "HVAC": str(GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx"),
                "Appliance": str(GROUND_TRUTH_DIR / "ground_truth_appliance.xlsx"),
                "Shower": str(GROUND_TRUTH_DIR / "ground_truth_shower.xlsx"),
            },
            "gt_score_cols": {
                "energy_cost": "energy_cost_score",
                "environmental": "environmental_score",
                "comfort": "comfort_score",
                "practicality": "practicality_score",
            },
        }
        
        gt_by_type = load_ground_truth(config)
        gt_lookup = build_gt_lookup(gt_by_type)
        gt_id_lookup = build_gt_id_lookup(gt_by_type)
        
        for name, df in results.items():
            if name == 'Random':
                # Average over seeds
                seed_metrics = []
                for seed in df['seed'].unique():
                    seed_df = df[df['seed'] == seed].drop(columns=['seed'])
                    merged, _ = match_scenarios(gt_lookup, gt_id_lookup, seed_df, f"{name}_seed{seed}")
                    merged, _, _ = filter_failed_scenarios(merged)
                    if len(merged) > 0:
                        metrics = compute_ranking_metrics(merged)
                        seed_metrics.append(metrics)
                if seed_metrics:
                    avg_top1 = np.mean([m['top1_accuracy'] for m in seed_metrics])
                    avg_tau = np.mean([m['kendall_tau'] for m in seed_metrics])
                    print(f"  {name}: Top-1 = {avg_top1:.4f} ± {np.std([m['top1_accuracy'] for m in seed_metrics]):.4f}, tau = {avg_tau:.4f} ± {np.std([m['kendall_tau'] for m in seed_metrics]):.4f}")
                    if args.assert_top1_min is not None:
                        assert avg_top1 >= args.assert_top1_min, f"Random Top-1 {avg_top1} < {args.assert_top1_min}"
            else:
                merged, _ = match_scenarios(gt_lookup, gt_id_lookup, df, name)
                merged, _, _ = filter_failed_scenarios(merged)
                if len(merged) > 0:
                    metrics = compute_ranking_metrics(merged)
                    print(f"  {name}: Top-1 = {metrics['top1_accuracy']:.4f}, tau = {metrics['kendall_tau']:.4f}")
                    if args.assert_top1_min is not None:
                        assert metrics['top1_accuracy'] >= args.assert_top1_min, f"{name} Top-1 {metrics['top1_accuracy']} < {args.assert_top1_min}"
    
    print("\nDone!")


if __name__ == "__main__":
    main()