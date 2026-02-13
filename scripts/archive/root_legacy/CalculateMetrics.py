import pandas as pd
import numpy as np
from scipy.stats import kendalltau, spearmanr
from typing import Dict, List, Tuple
import sys
GROUND_TRUTH_CSV = 'ground_truth_results.csv'
ARCHITECTURE_CSVS = {
    'Pure': 'pure_prompting_results.csv',
    'RAG': 'rag_enhanced_results.csv',
    'Hybrid': 'hybrid_results.csv'
}
OUTPUT_CSV = 'metrics_comparison.csv'

CRITERIA = ['energy_cost', 'environmental', 'comfort', 'practicality']

def validate_csv_structure(df: pd.DataFrame, filename: str) -> None:
    """Validate that CSV has required columns."""
    required_cols = ['scenario', 'alternative', 'rank'] + CRITERIA
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"{filename} missing required columns: {missing_cols}")

    print(f"✓ {filename}: {len(df)} rows, {df['scenario'].nunique()} scenarios")

def match_alternatives_by_position(gt_df: pd.DataFrame, pred_df: pd.DataFrame,
                                   scenario: str) -> Tuple[List, List, Dict, Dict]:
    """
    Match alternatives by POSITION (Alternative 1 → Alternative 1, etc.)

    Returns:
        (gt_ranks, pred_ranks, gt_scores, pred_scores)

    gt_ranks: [1, 2, 3] - GT ranks sorted by position
    pred_ranks: [2, 1, 3] - Predicted ranks sorted by position
    gt_scores: {criterion: [score1, score2, score3]} - GT scores by position
    pred_scores: {criterion: [score1, score2, score3]} - Predicted scores by position
    """
    # Filter to this scenario
    gt_scenario = gt_df[gt_df['scenario'] == scenario].copy()
    pred_scenario = pred_df[pred_df['scenario'] == scenario].copy()

    # Check we have exactly 3 alternatives each
    if len(gt_scenario) != 3:
        raise ValueError(f"GT scenario '{scenario}' has {len(gt_scenario)} alternatives, expected 3")
    if len(pred_scenario) != 3:
        raise ValueError(f"Predicted scenario '{scenario}' has {len(pred_scenario)} alternatives, expected 3")
    gt_scenario_sorted = gt_scenario.sort_values('alternative').reset_index(drop=True)
    pred_scenario_sorted = pred_scenario.sort_values('alternative').reset_index(drop=True)
    gt_ranks = gt_scenario_sorted['rank'].tolist()
    pred_ranks = pred_scenario_sorted['rank'].tolist()
    # Extract scores
    gt_scores = {criterion: gt_scenario_sorted[criterion].tolist() for criterion in CRITERIA}
    pred_scores = {criterion: pred_scenario_sorted[criterion].tolist() for criterion in CRITERIA}

    return gt_ranks, pred_ranks, gt_scores, pred_scores


def calculate_kendalls_tau(gt_ranks: List[int], pred_ranks: List[int]) -> float:
    """
    Calculate Kendall's tau-b rank correlation coefficient.

    Measures ordinal association between two rankings.
    Range: -1 (perfect disagreement) to +1 (perfect agreement)

    Math verification:
    - tau = (concordant pairs - discordant pairs) / total pairs
    - scipy.stats.kendalltau handles this correctly
    """
    tau, _ = kendalltau(gt_ranks, pred_ranks)

    # Self-check: tau should be in [-1, 1]
    if not -1 <= tau <= 1:
        f"Kendall's tau out of range: {tau}"

    return tau


def calculate_spearmans_rho(gt_ranks: List[int], pred_ranks: List[int]) -> float:
    """
    Calculate Spearman's rho rank correlation coefficient.

    Measures monotonic relationship between two rankings.
    Range: -1 (perfect negative correlation) to +1 (perfect positive correlation)

    Math verification:
    - rho = 1 - (6 * sum(d_i^2)) / (n * (n^2 - 1))
    - where d_i is the difference between ranks
    - scipy.stats.spearmanr handles this correctly
    """
    rho, _ = spearmanr(gt_ranks, pred_ranks)

    # Self-check: rho should be in [-1, 1]
    if not -1 <= rho <= 1:
        f"Spearman's rho out of range: {rho}"

    return rho


def calculate_top1_match(gt_ranks: List[int], pred_ranks: List[int]) -> int:
    """
    Check if top-ranked alternative matches between GT and predicted.

    Returns: 1 if match, 0 if no match

    Math verification:
    - Find position where GT rank == 1
    - Find position where Pred rank == 1
    - Return 1 if same position, else 0
    """
    gt_top1_position = gt_ranks.index(1)
    pred_top1_position = pred_ranks.index(1)

    match = 1 if gt_top1_position == pred_top1_position else 0

    # Self-check: match must be 0 or 1
    if not match in [0, 1]:
        f"Top-1 match must be binary: {match}"

    return match


def calculate_top2_match(gt_ranks: List[int], pred_ranks: List[int]) -> int:
    """
    Check if predicted top-1 alternative is in GT's top-2.

    Returns: 1 if match, 0 if no match

    Math verification:
    - Find position where Pred rank == 1
    - Check if that position has GT rank == 1 or GT rank == 2
    - Return 1 if yes, else 0
    """
    pred_top1_position = pred_ranks.index(1)
    gt_rank_at_that_position = gt_ranks[pred_top1_position]

    match = 1 if gt_rank_at_that_position in [1, 2] else 0

    # Self-check: match must be 0 or 1
    if not match in [0, 1]:
        f"Top-2 match must be binary: {match}"

    return match


def calculate_mae(gt_scores: List[float], pred_scores: List[float]) -> float:
    """
    Calculate Mean Absolute Error.

    MAE = mean(|predicted - ground_truth|)

    Math verification:
    - For each alternative: |pred_i - gt_i|
    - Average across all alternatives
    - Should always be >= 0
    """
    assert len(gt_scores) == len(pred_scores), "GT and Pred scores must have same length"

    absolute_errors = [abs(pred - gt) for pred, gt in zip(pred_scores, gt_scores)]
    mae = np.mean(absolute_errors)

    # Self-check: MAE must be non-negative
    if not mae >= 0:
        f"MAE must be non-negative: {mae}"

    return mae


def calculate_rmse(gt_scores: List[float], pred_scores: List[float]) -> float:
    """
    Calculate Root Mean Squared Error.

    RMSE = sqrt(mean((predicted - ground_truth)^2))

    Math verification:
    - For each alternative: (pred_i - gt_i)^2
    - Average across all alternatives
    - Take square root
    - Should always be >= 0
    """
    assert len(gt_scores) == len(pred_scores), "GT and Pred scores must have same length"

    squared_errors = [(pred - gt) ** 2 for pred, gt in zip(pred_scores, gt_scores)]
    mse = np.mean(squared_errors)
    rmse = np.sqrt(mse)

    # Self-check: RMSE must be non-negative and >= MAE
    if not rmse >= 0:
        f"RMSE must be non-negative: {rmse}"

    return rmse


def calculate_scenario_metrics(gt_df: pd.DataFrame, pred_df: pd.DataFrame,
                               scenario: str) -> Dict:
    """
    Calculate all metrics for a single scenario.

    Returns dict with all metrics for this scenario.
    """
    # Match alternatives by position
    gt_ranks, pred_ranks, gt_scores, pred_scores = match_alternatives_by_position(
        gt_df, pred_df, scenario
    )

    # Calculate ranking metrics
    kendalls_tau = calculate_kendalls_tau(gt_ranks, pred_ranks)
    spearmans_rho = calculate_spearmans_rho(gt_ranks, pred_ranks)
    top1_match = calculate_top1_match(gt_ranks, pred_ranks)
    top2_match = calculate_top2_match(gt_ranks, pred_ranks)

    # Calculate score metrics for each criterion
    mae_per_criterion = {}
    rmse_per_criterion = {}

    for criterion in CRITERIA:
        mae_per_criterion[criterion] = calculate_mae(
            gt_scores[criterion], pred_scores[criterion]
        )
        rmse_per_criterion[criterion] = calculate_rmse(
            gt_scores[criterion], pred_scores[criterion]
        )

    # Assemble results
    results = {
        'kendalls_tau': kendalls_tau,
        'spearmans_rho': spearmans_rho,
        'top1_match': top1_match,
        'top2_match': top2_match,
    }

    # Add MAE and RMSE for each criterion
    for criterion in CRITERIA:
        results[f'mae {criterion}'] = mae_per_criterion[criterion]
        results[f'rmse {criterion}'] = rmse_per_criterion[criterion]

    return results


def aggregate_metrics(metrics_df: pd.DataFrame, group_label: str) -> Dict:
    """
    Aggregate metrics across multiple scenarios.

    For ranking metrics: mean
    For score metrics: mean
    """
    aggregated = {
        'scenario': group_label,
        'kendalls_tau': metrics_df['kendalls_tau'].mean(),
        'spearmans_rho': metrics_df['spearmans_rho'].mean(),
        'top1_match': metrics_df['top1_match'].mean(),
        'top2_match': metrics_df['top2_match'].mean(),
    }

    # Aggregate MAE and RMSE for each criterion
    for criterion in CRITERIA:
        aggregated[f'mae_{criterion}'] = metrics_df[f'mae_{criterion}'].mean()
        aggregated[f'rmse_{criterion}'] = metrics_df[f'rmse_{criterion}'].mean()

    return aggregated

def calculate_all_metrics():
    """
    Main function to calculate all metrics and generate output CSV.
    """
    #70 is wrong i believe
    print(f"\n{'=' * 70}")
    print(f"METRICS CALCULATOR")
    print(f"{'=' * 70}\n")

    try:
        gt_df = pd.read_csv(GROUND_TRUTH_CSV)
        validate_csv_structure(gt_df, GROUND_TRUTH_CSV)
    except FileNotFoundError:
        print(" {GROUND_TRUTH_CSV} not found!")
        sys.exit(1)

    has_decision_type = 'decision_type' in gt_df.columns
    if not has_decision_type:
        print("'decision_type' column not found in GT. Will skip by-decision-type metrics.")

    all_rows = []
    for arch_name, arch_csv in ARCHITECTURE_CSVS.items():
        print(f"\n{'-' * 70}")
        print(f"Processing: {arch_name}")
        print(f"{'-' * 70}")

        try:
            pred_df = pd.read_csv(arch_csv)
            validate_csv_structure(pred_df, arch_csv)
        except FileNotFoundError:
            print(f"error: {arch_csv} not found; Skipping {arch_name}.")
            continue

        gt_scenarios = set(gt_df['scenario'].unique())
        pred_scenarios = set(pred_df['scenario'].unique())
        common_scenarios = gt_scenarios & pred_scenarios

        if not common_scenarios:
            print(f"Error: No common scenarios between GT and {arch_name}!")
            continue

        missing_in_pred = gt_scenarios - pred_scenarios
        if missing_in_pred:
            print(f"Warning: {len(missing_in_pred)} scenarios in GT missing from {arch_name}")

        print(f"Calculating metrics for {len(common_scenarios)} scenarios (should be [AHAAN UPDATE NUMBER WHEN UPDATING LENGTH]")

        # Calculate per-scenario metrics
        scenario_metrics = []
        for scenario in sorted(common_scenarios):
            try:
                metrics = calculate_scenario_metrics(gt_df, pred_df, scenario)
                decision_type = gt_df[gt_df['scenario'] == scenario]['decision_type'].iloc[0]


                row = {
                    'architecture': arch_name,
                    'scenario': scenario,
                    'decision_type': decision_type,
                    **metrics
                }
                scenario_metrics.append(row)
                all_rows.append(row)

            except Exception as e:
                print(f"Error calculating metrics for scenario '{scenario}': {e}")
                continue

        # Convert to DataFrame for aggregation
        scenario_df = pd.DataFrame(scenario_metrics)

        print(f"✓ Calculated metrics for {len(scenario_metrics)} scenarios")

        # Calculate OVERALL aggregation
        overall_agg = aggregate_metrics(scenario_df, 'OVERALL_MEAN')
        overall_agg['architecture'] = arch_name
        overall_agg['decision_type'] = 'all'
        all_rows.append(overall_agg)

        print(f"  Overall Kendall's tau: {overall_agg['kendalls_tau']:.3f}")
        print(f"  Overall Spearman's rho: {overall_agg['spearmans_rho']:.3f}")
        print(f"  Overall Top-1 accuracy: {overall_agg['top1_match']:.1%}")
        print(f"  Overall Top-2 accuracy: {overall_agg['top2_match']:.1%}")

        # Calculate by decision type aggregation
        if has_decision_type:
            decision_types = scenario_df['decision_type'].unique()
            for dt in sorted(decision_types):
                dt_df = scenario_df[scenario_df['decision_type'] == dt]
                dt_agg = aggregate_metrics(dt_df, f'{dt}_MEAN')
                dt_agg['architecture'] = arch_name
                dt_agg['decision_type'] = dt
                all_rows.append(dt_agg)

                print(f"  {dt} - Kendall's tau: {dt_agg['kendalls_tau']:.3f}, Top-1: {dt_agg['top1_match']:.1%}")

    # Create final DataFrame
    results_df = pd.DataFrame(all_rows)

    # Reorder columns for readability
    col_order = ['architecture', 'scenario', 'decision_type',
                 'kendalls_tau', 'spearmans_rho', 'top1_match', 'top2_match']
    for criterion in CRITERIA:
        col_order.append(f'mae_{criterion}')
    for criterion in CRITERIA:
        col_order.append(f'rmse_{criterion}')

    results_df = results_df[col_order]
    results_df.to_csv(OUTPUT_CSV, index=False)

    print(f"Total rows: {len(results_df)}")


if __name__ == '__main__':
    calculate_all_metrics()