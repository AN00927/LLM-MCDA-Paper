#!/usr/bin/env python3
"""
run_baseline_models.py - Non-LLM Baselines
Computes four baselines for MCDA architecture comparison.
"""
import argparse
import sys
import warnings
import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GT_CALC_DIR = PROJECT_ROOT / "Ground Truth Calculators"
if str(GT_CALC_DIR) not in sys.path:
    sys.path.insert(0, str(GT_CALC_DIR))

MISC_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(MISC_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(MISC_SCRIPTS_DIR))

from model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY
from sentinel_utils import read_table_clean, SENTINEL_VALUE, has_sentinel_scores, apply_mavt_ranking

from HVACGroundTruthCalculator import HVACGroundTruthCalculator
from ApplianceGroundTruthCalculator import ApplianceGroundTruthCalculator
from ShowerGroundTruthCalculator import ShowerGroundTruthCalculator

from run_rag_ablation_experiments import (
    nearest_neighbor_prediction,
    build_collection,
    retrieve_similar,
    load_source_groups,
    stratified_sample,
    format_embedding_text,
)

warnings.filterwarnings("default")

HVAC_DEFAULT_R_VALUE = 15
HVAC_DEFAULT_SEER = 13
HVAC_DEFAULT_HVAC_AGE = 13
HVAC_DEFAULT_SQFT_BY_HOUSING_TYPE = {
    "Single-family": 2000, "Townhouse": 1800, "Rowhouse": 1800,
    "Apartment": 916, "Condo": 1100,
}
HVAC_DEFAULT_SQFT_FALLBACK = 2000
HVAC_DEFAULT_HOUSEHOLD_SIZE = 2.54
HVAC_DEFAULT_OUTDOOR_TEMP = 51.8
HVAC_DEFAULT_UTILITY_BUDGET = 430

APPLIANCE_DEFAULT_KWH_PER_CYCLE = {
    "Washer": 0.55, "Dryer": 2.10, "Dishwasher": 1.00,
    "washing_machine": 0.55, "dryer": 2.10, "dishwasher": 1.00,
}
APPLIANCE_DEFAULT_KWH_FALLBACK = 1.00
APPLIANCE_DEFAULT_AGE_YEARS = 11
APPLIANCE_DEFAULT_HOUSEHOLD_SIZE = 2.54
APPLIANCE_DEFAULT_UTILITY_BUDGET = 430
APPLIANCE_DEFAULT_HOUSING_TYPE = "Single-family"

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
    'question', 'location', 'alternative', 'housing_type', 
    'insulation', 'appliance', 'appliance_age', 'house_age',
]

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

def build_scenario_from_test(row, decision_type):
    """Build a scenario dict from TestScenarios row for the GT calculators."""
    scenario = {
        'question': str(row.get('question', '')).strip(),
        'location': str(row.get('location', '')).strip(),
        'household_size': int(float(row.get('household_size', 2))),
        'utility_budget': float(row.get('utility_budget', 0)),
        'housing_type': str(row.get('housing_type', 'Single-family')),
    }
    if decision_type == "HVAC":
        scenario.update({
            'square_footage': int(float(row.get('square_footage', 2000))),
            'outdoor_temp': float(row.get('outdoor_temp', 50)),
            'hvac_age': HVAC_DEFAULT_HVAC_AGE,
            'r_value': HVAC_DEFAULT_R_VALUE,
            'seer': HVAC_DEFAULT_SEER,
            'occupancy_context': str(row.get('occupancy_context', 'occupied_all_day')),
            'electricity_rate': HVACGroundTruthCalculator.ELECTRICITY_RATE_PA,
            'alternative_1': str(row.get('alternative_1', '')),
            'alternative_2': str(row.get('alternative_2', '')),
            'alternative_3': str(row.get('alternative_3', '')),
        })
    elif decision_type == "Appliance":
        # TestScenarios has no 'appliance' column, so the default here decides the
        # appliance type for every scenario. Defaulting to 'Washer' made the
        # question-text detection below unreachable and typed all 65 appliance
        # scenarios as washing machines. Default to empty so detection runs.
        app_type = str(row.get('appliance', '')).strip()
        q_lower = str(row.get('question', '')).lower()
        if not app_type or app_type.lower() in ('nan', 'none'):
            # 'dishwasher' must be tested BEFORE 'washer': the substring 'washer'
            # is contained in 'dishwasher', so testing 'washer' first silently
            # classified every dishwasher scenario as a washing machine.
            if 'dishwasher' in q_lower: app_type = 'Dishwasher'
            elif 'dryer' in q_lower: app_type = 'Dryer'
            elif 'washing machine' in q_lower or 'washer' in q_lower: app_type = 'Washer'
            else: app_type = 'Washer'

        if 'washer' in app_type.lower() and 'dishwasher' not in app_type.lower(): app_type = 'washing_machine'
        elif 'dryer' in app_type.lower(): app_type = 'dryer'
        elif 'dishwasher' in app_type.lower(): app_type = 'dishwasher'
            
        # Parse appliance_age which might be a string band like "7-9 years" or a float/int
        raw_age = row.get('appliance_age')
        try:
            appliance_age_val = int(float(raw_age))
        except (ValueError, TypeError):
            import re
            m = re.search(r'(\d+)', str(raw_age))
            if m:
                appliance_age_val = int(m.group(1))
            else:
                appliance_age_val = APPLIANCE_DEFAULT_AGE_YEARS

        scenario.update({
            'appliance': app_type,
            # Fixed-Default means a per-appliance-type default, not one constant for
            # every appliance: a dryer and a dishwasher do not use the same energy.
            # TestScenarios carries no kwh_per_cycle column, so this lookup is what
            # actually supplies the value in practice.
            'kwh_per_cycle': float(row.get(
                'kwh_per_cycle',
                APPLIANCE_DEFAULT_KWH_PER_CYCLE.get(app_type, APPLIANCE_DEFAULT_KWH_FALLBACK),
            )),
            'appliance_age': appliance_age_val,
            'baseline_time': str(row.get('baseline_time', '7pm')),
            'alternative_1': str(row.get('alternative_1', '')),
            'alternative_2': str(row.get('alternative_2', '')),
            'alternative_3': str(row.get('alternative_3', '')),
        })
    elif decision_type == "Shower":
        scenario.update({
            'gpm': float(row.get('gpm', SHOWER_DEFAULT_GPM)),
            'tank_size': float(row.get('tank_size', SHOWER_DEFAULT_TANK_SIZE)),
            'water_heater_temp': float(row.get('water_heater_temp', SHOWER_DEFAULT_WATER_HEATER_TEMP)),
            'outdoor_temp': float(row.get('outdoor_temp', SHOWER_DEFAULT_OUTDOOR_TEMP)),
            'alternative_1': str(row.get('alternative_1', '')),
            'alternative_2': str(row.get('alternative_2', '')),
            'alternative_3': str(row.get('alternative_3', '')),
        })
    
    alternatives = []
    for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
        alt_val = str(row.get(alt_col, '')).strip()
        if pd.isna(row.get(alt_col)) or alt_val == '' or alt_val.lower() == 'nan':
            continue
        alternatives.append(float(alt_val) if decision_type == "Shower" else alt_val)
    scenario['alternatives'] = alternatives
    return scenario


def run_calculator_on_scenarios(decision_type, scenarios, calculator_class, id_offset=0):
    """Run a GT calculator on a list of scenarios and return results DataFrame."""
    calculator = calculator_class()
    all_results = []
    for idx, scenario in enumerate(scenarios, start=id_offset):
        try:
            raw_scores = calculator.calculate_scenario_scores(scenario)

            if decision_type == "Shower":
                scores = {}
                for alt_data in raw_scores["alternatives"]:
                    key = str(alt_data["alternative"])
                    tv  = alt_data["transformed_values"]
                    scores[key] = {
                        "energy_cost_score":   tv["energy_cost"],
                        "environmental_score": tv["environmental"],
                        "comfort_score":       tv["comfort"],
                        "practicality_score":  tv["practicality"],
                        "duration_min":        int(alt_data["duration"]),
                    }
            else:
                scores = raw_scores
            # ──────────────────────────────────────────────────────────────────

            alts_for_ranking = [
                {
                    "alternative":  alt,
                    "energy_cost":  scores[alt]["energy_cost_score"],
                    "environmental":scores[alt]["environmental_score"],
                    "comfort":      scores[alt]["comfort_score"],
                    "practicality": scores[alt]["practicality_score"],
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
# BASELINES
# =============================================================================
def run_fixed_default_baseline(test_df):
    scenarios = {"HVAC": [], "Appliance": [], "Shower": []}
    for _, row in test_df.iterrows():
        scenarios[row['decision_type']].append(build_scenario_from_test(row, row['decision_type']))
    
    results = []
    offset = 0
    if scenarios["HVAC"]:
        results.append(run_calculator_on_scenarios("HVAC", scenarios["HVAC"], HVACGroundTruthCalculator, id_offset=offset))
        offset += len(scenarios["HVAC"])
    if scenarios["Appliance"]:
        results.append(run_calculator_on_scenarios("Appliance", scenarios["Appliance"], ApplianceGroundTruthCalculator, id_offset=offset))
        offset += len(scenarios["Appliance"])
    if scenarios["Shower"]:
        results.append(run_calculator_on_scenarios("Shower", scenarios["Shower"], ShowerGroundTruthCalculator, id_offset=offset))
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

def run_nearest_neighbor_baseline(test_df, k=3):
    groups_by_type = load_source_groups()
    from run_rag_ablation_experiments import DEFAULT_EMBEDDING_MODEL
    import tempfile, shutil
    temp_path, collection, model, _ = build_collection(DEFAULT_EMBEDDING_MODEL, Path(tempfile.gettempdir()))
    try:
        all_rows = []
        for idx, row in test_df.iterrows():
            dtype = row['decision_type']
            scenario = {
                'decision_type': dtype, 'scenario_id': f"{dtype.lower()}_{idx}", 'source_scenario_id': idx,
                'source_position': idx + 1, 'question': row['question'], 'location': row['location'],
                'household_size': row['household_size'], 'housing_type': row['housing_type'],
                'utility_budget': row.get('utility_budget', 0), 'alternatives': []
            }
            if dtype == "HVAC":
                scenario.update({'outdoor_temp': row['outdoor_temp'], 'insulation': row['insulation'],
                                 'square_footage': row['square_footage'], 'house_age': row['house_age']})
            elif dtype == "Appliance":
                q_lower = str(row['question']).lower()
                app_type = 'washing_machine' if 'washer' in q_lower else ('dryer' if 'dryer' in q_lower else 'dishwasher')
                scenario.update({'appliance': app_type, 'appliance_age': row.get('appliance_age', 11), 'kwh_per_cycle': 0})
            elif dtype == "Shower":
                scenario.update({'outdoor_temp': row['outdoor_temp'], 'gpm': 2.5, 'flow_rate': 'standard',
                                 'tank_size': 50, 'water_heater_temp': 120})
            
            for alt_col in ['alternative_1', 'alternative_2', 'alternative_3']:
                if not pd.isna(row.get(alt_col)) and str(row.get(alt_col)).strip().lower() not in ('', 'nan'):
                    val = float(row[alt_col]) if dtype == "Shower" else str(row[alt_col]).strip()
                    scenario['alternatives'].append({'alternative': val})
            
            retrieved = retrieve_similar(collection, model, scenario, k)
            result = nearest_neighbor_prediction(scenario, retrieved)
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
    sort_cols = ['mavt_score'] + tiebreak_cols
    group_sorted = group.sort_values(sort_cols, ascending=[False] * len(sort_cols), kind="mergesort")
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

def run_all_baselines(test_df, baselines=None, k=3):
    if baselines is None: baselines = ['random', 'uniform', 'fixed_default', 'nearest_neighbor']
    results = {}
    if 'random' in baselines:
        print("Running Random baseline..."); results['Random'] = run_random_baseline(test_df)
    if 'uniform' in baselines:
        print("Running Uniform baseline..."); results['Uniform'] = run_uniform_baseline(test_df)
    if 'fixed_default' in baselines:
        print("Running Fixed-Default baseline..."); results['FixedDefault'] = run_fixed_default_baseline(test_df)
    if 'nearest_neighbor' in baselines:
        print("Running Nearest-Neighbor baseline..."); results['NearestNeighbor'] = run_nearest_neighbor_baseline(test_df, k=k)
    return results

def main():
    parser = argparse.ArgumentParser(description="Run non-LLM baselines for MCDA architecture comparison")
    parser.add_argument('--baselines', nargs='+', default=['fixed_default', 'nearest_neighbor'],
                        choices=['fixed_default', 'nearest_neighbor', 'all'], help='Which baselines to run')
    parser.add_argument('--k', type=int, default=3, help='k for Nearest-Neighbor baseline')
    parser.add_argument('--verify', action='store_true', help='Run verification checks')
    parser.add_argument('--baseline', type=str, help='Run single baseline (for verification)')
    parser.add_argument('--assert-top1-min', type=float, help='Assert minimum Top-1 accuracy')
    args = parser.parse_args()
    
    baselines = ['fixed_default', 'nearest_neighbor'] if args.baselines == ['all'] else args.baselines
    
    test_path = SCENARIO_DIR / "TestScenarios.xlsx"
    test_df = read_table_clean(test_path)
    print(f"Loaded {len(test_df)} test scenarios")
    print(f"Decision types: {test_df['decision_type'].value_counts().to_dict()}")
    
    if args.baseline: baselines = [args.baseline]
    
    results = run_all_baselines(test_df, baselines, k=args.k)
    
    OUTPUT_DIR = PROJECT_ROOT / "Output Files" / "Baselines"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in results.items():
        df.to_excel(OUTPUT_DIR / f"baseline_{name.lower()}.xlsx", index=False, engine="openpyxl")
        print(f"Saved {name} baseline to {OUTPUT_DIR} ({len(df)} rows)")

if __name__ == "__main__":
    main()
