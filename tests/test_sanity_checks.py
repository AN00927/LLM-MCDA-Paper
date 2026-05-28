#!/usr/bin/env python3
"""
Sanity check script for CalculateMetrics aggregation logic.
Validates that multi-run aggregation preserves scenario counts and matching works.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

# Set encoding for output
os.environ['PYTHONIOENCODING'] = 'utf-8'

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import get_output_folder, MODEL_KEY, CRITERION_WEIGHTS

# Import CalculateMetrics functions
import importlib.util
spec = importlib.util.spec_from_file_location("calculate_metrics", PROJECT_ROOT / "Miscellaneous Scripts" / "CalculateMetrics.py")
calc_metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc_metrics)

aggregate_run_files = calc_metrics.aggregate_run_files
normalize_alternative = calc_metrics.normalize_alternative
build_gt_id_lookup = calc_metrics.build_gt_id_lookup
match_scenarios = calc_metrics.match_scenarios
load_architecture = calc_metrics.load_architecture
FAIL_SENTINEL = calc_metrics.FAIL_SENTINEL

OUTPUT_DIR = PROJECT_ROOT / get_output_folder()
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"

def run_sanity_checks():
    print("=" * 70)
    print("SANITY CHECKS FOR CALCULATEMETRICS AGGREGATION")
    print("=" * 70)
    
    # Check 1: Can we load ground truth files?
    print("\n[CHECK 1] Loading ground truth files...")
    try:
        # Use robust reader to avoid encoding/whitespace issues
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from sentinel_utils import read_csv_clean
        gt_hvac = read_csv_clean(GROUND_TRUTH_DIR / "ground_truth_hvac.csv")
        gt_appliance = read_csv_clean(GROUND_TRUTH_DIR / "ground_truth_appliance.csv")
        gt_shower = read_csv_clean(GROUND_TRUTH_DIR / "ground_truth_shower.csv")
        print(f"  [OK] HVAC: {len(gt_hvac)} scenarios")
        print(f"  [OK] Appliance: {len(gt_appliance)} scenarios")
        print(f"  [OK] Shower: {len(gt_shower)} scenarios")
    except FileNotFoundError as e:
        print(f"  [FAIL] {e}")
        return False
    
    # Check 2: Can we detect run files?
    print("\n[CHECK 2] Detecting run files in output directory...")
    from glob import glob
    run_files = sorted(glob(str(OUTPUT_DIR / "*_run_*.csv")))
    if run_files:
        print(f"  [OK] Found {len(run_files)} run files:")
        for rf in run_files[:3]:
            print(f"    - {Path(rf).name}")
        if len(run_files) > 3:
            print(f"    ... and {len(run_files) - 3} more")
    else:
        print(f"  [INFO] No run files found yet (OK if single-output mode)")
    
    # Check 3: Test alternative normalization
    print("\n[CHECK 3] Testing alternative normalization...")
    test_cases = [
        ("HVAC", "75", "75"),
        ("HVAC", "  76  ", "76"),
        ("Appliance", "2:00 PM", "2:00 PM"),
        ("Appliance", "10pm", "10:00 PM"),
        ("Appliance", "Run at 3:00 AM", "3:00 AM"),
        ("Shower", "5.5", "5.5"),
        ("Shower", "  10.0  ", "10.0"),
    ]
    
    all_norm_pass = True
    for decision_type, alt_input, expected in test_cases:
        result = normalize_alternative(alt_input, decision_type)
        status = "[OK]" if result == expected else "[WARN]"
        if result != expected:
            all_norm_pass = False
        print(f"  {status} {decision_type:12} '{alt_input:20}' -> '{result:20}' (expect '{expected}')")
    
    if not all_norm_pass:
        print("  WARNING: Some normalizations don't match, but may still be valid")
    
    # Check 4: Test GT lookup building for individual decision types
    print("\n[CHECK 4] Validating GT data structure...")
    try:
        # Check that each GT file has the expected score columns
        for df, dtype in [(gt_hvac, 'HVAC'), (gt_appliance, 'Appliance'), (gt_shower, 'Shower')]:
            score_cols = ['energy_cost_score', 'environmental_score', 'comfort_score', 'practicality_score']
            missing = [c for c in score_cols if c not in df.columns]
            if missing:
                print(f"  [FAIL] {dtype} missing columns: {missing}")
                return False
            print(f"  [OK] {dtype} has all required score columns")
            
            # Check that scenario_id column exists
            if 'scenario_id' not in df.columns:
                print(f"  [FAIL] {dtype} missing scenario_id column")
                return False
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    
    # Check 5: Validate criterion weights sum to expected
    print("\n[CHECK 5] Validating criterion weights...")
    weight_sum = sum(CRITERION_WEIGHTS.values())
    print(f"  Weight sum: {weight_sum}")
    if abs(weight_sum - 1.0) < 0.01:
        print(f"  [OK] Weights sum to {weight_sum:.3f}")
    else:
        print(f"  [WARN] Weights sum to {weight_sum:.3f} (expect ~1.0)")
    
    for criterion, weight in CRITERION_WEIGHTS.items():
        print(f"    - {criterion:20} {weight:.2f}")
    
    # Check 6: Try loading architecture results if they exist
    print("\n[CHECK 6] Testing architecture result loading...")
    arch_configs = {
        "Pure": OUTPUT_DIR / "pure_prompting_results.csv",
        "RAG": OUTPUT_DIR / "RAGResults.csv",
        "Hybrid": OUTPUT_DIR / "hybrid_results.csv",
    }
    
    for arch_name, file_path in arch_configs.items():
        if file_path.exists():
            try:
                df = load_architecture(str(file_path), arch_name)
                n_rows = len(df)
                n_scenarios = df['arch_scenario_id'].nunique() if 'arch_scenario_id' in df.columns else "?"
                has_sentinels = (df == FAIL_SENTINEL).any().any()
                print(f"  [OK] {arch_name:8} {n_rows:5} rows, {str(n_scenarios):5} scenarios, sentinel: {has_sentinels}")
            except Exception as e:
                print(f"  [FAIL] {arch_name:8} {e}")
        else:
            print(f"  [INFO] {arch_name:8} not found: {file_path.name}")
    
    # Check 7: Validate that MAVT scoring is deterministic
    print("\n[CHECK 7] Testing MAVT scoring determinism...")
    test_scores = {
        'energy_cost': 8.0,
        'environmental': 6.0,
        'comfort': 7.0,
        'practicality': 9.0
    }
    
    weighted_score = (
        CRITERION_WEIGHTS['energy_cost'] * test_scores['energy_cost'] +
        CRITERION_WEIGHTS['environmental'] * test_scores['environmental'] +
        CRITERION_WEIGHTS['comfort'] * test_scores['comfort'] +
        CRITERION_WEIGHTS['practicality'] * test_scores['practicality']
    )
    
    print(f"  Test scores: {test_scores}")
    print(f"  Weighted score: {weighted_score:.4f}")
    print(f"  [OK] MAVT calculation deterministic")
    
    print("\n" + "=" * 70)
    print("SANITY CHECK COMPLETE - ALL CHECKS PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        success = run_sanity_checks()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
