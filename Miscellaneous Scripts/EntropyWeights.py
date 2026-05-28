"""Compute Shannon entropy weights for the ground-truth MCDA datasets.

This script loads the HVAC, Appliance, and Shower ground-truth CSV files,
concatenates them into one DataFrame, and compares the subjective MAVT weights
with objective entropy-derived weights overall and by decision type.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sentinel_utils import read_csv_clean


SUBJECTIVE_WEIGHTS = {
    "environmental": 0.35,
    "energy_cost": 0.30,
    "comfort": 0.20,
    "practicality": 0.15,
}

DECISION_TYPES = ("HVAC", "Appliance", "Shower")

CRITERION_COLUMN_MAP = {
    "energy_cost": ("gt_energy_cost", "energy_cost_score", "energy_cost"),
    "environmental": ("gt_environmental", "environmental_score", "environmental"),
    "comfort": ("gt_comfort", "comfort_score", "comfort"),
    "practicality": ("gt_practicality", "practicality_score", "practicality"),
}


def get_project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[1]


def resolve_existing_path(project_root: Path, relative_candidates: tuple[str, ...]) -> Path:
    """Return the first existing path from a list of relative candidates."""
    for relative_candidate in relative_candidates:
        candidate_path = project_root / relative_candidate
        if candidate_path.exists():
            return candidate_path
    raise FileNotFoundError(
        "Could not find any of the expected files: "
        + ", ".join(relative_candidates)
    )


def resolve_criterion_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map canonical criterion names to the actual columns present in a DataFrame."""
    resolved_columns: dict[str, str] = {}
    for canonical_name, candidate_names in CRITERION_COLUMN_MAP.items():
        for candidate_name in candidate_names:
            if candidate_name in df.columns:
                resolved_columns[canonical_name] = candidate_name
                break
        else:
            raise KeyError(
                f"Missing criterion column for {canonical_name}. "
                f"Looked for: {candidate_names}"
            )
    return resolved_columns


def load_ground_truth_data(project_root: Path) -> pd.DataFrame:
    """Load and concatenate all ground-truth CSVs into one DataFrame."""
    file_specs = (
        ("HVAC", ("Ground Truth/ground_truth_hvac.csv", "Output Files/ground_truth_hvac.csv")),
        (
            "Appliance",
            ("Ground Truth/ground_truth_appliance.csv", "Output Files/ground_truth_appliance.csv"),
        ),
        (
            "Shower",
            ("Ground Truth/ground_truth_shower.csv", "Output Files/ground_truth_shower.csv"),
        ),
    )

    data_frames: list[pd.DataFrame] = []
    for decision_type, relative_candidates in file_specs:
        csv_path = resolve_existing_path(project_root, relative_candidates)
        df = read_csv_clean(csv_path)
        df = df.copy()
        df["decision_type"] = decision_type
        df["source_file"] = csv_path.name
        data_frames.append(df)

    return pd.concat(data_frames, ignore_index=True)


def entropy_weights(data: pd.DataFrame, column_map: dict[str, str], epsilon: float = 1e-10) -> pd.Series:
    """Compute Shannon entropy weights for the provided criterion columns.

    The calculation follows:
    1. Normalize each criterion column to a probability distribution.
    2. Replace zero probabilities with a small epsilon before computing logs.
    3. Compute entropy: E_j = -k * sum(p_ij * ln(p_ij)), where k = 1 / ln(n).
    4. Compute divergence: d_j = 1 - E_j.
    5. Compute objective weight: w_j = d_j / sum(d_j).
    """
    criterion_names = list(column_map.keys())
    if len(data) <= 1:
        return pd.Series(
            data=np.full(len(criterion_names), 1.0 / len(criterion_names)),
            index=criterion_names,
            dtype=float,
        )

    criteria_matrix = data[[column_map[name] for name in criterion_names]].apply(pd.to_numeric, errors="coerce")
    criteria_matrix = criteria_matrix.fillna(0.0)

    entropy_values = {}
    for canonical_name in criterion_names:
        column = criteria_matrix[column_map[canonical_name]].to_numpy(dtype=float)
        total = column.sum()
        if total == 0:
            probabilities = np.full(column.shape, 1.0 / len(column), dtype=float)
        else:
            probabilities = column / total
            probabilities = np.where(probabilities <= 0, epsilon, probabilities)

        n = probabilities.size
        if n <= 1:
            entropy_values[canonical_name] = 0.0
            continue

        k = 1.0 / np.log(n)
        entropy = -k * np.sum(probabilities * np.log(probabilities))
        entropy_values[canonical_name] = float(entropy)

    entropy_series = pd.Series(entropy_values, dtype=float)
    divergence_series = 1.0 - entropy_series
    divergence_sum = divergence_series.sum()

    if divergence_sum == 0:
        return pd.Series(
            data=np.full(len(criterion_names), 1.0 / len(criterion_names)),
            index=criterion_names,
            dtype=float,
        )

    return divergence_series / divergence_sum


def build_comparison_table(data: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
    """Build a wide comparison table for subjective and entropy-based weights."""
    rows = []

    overall_entropy = entropy_weights(data, column_map)
    per_type_entropy = {
        decision_type: entropy_weights(data[data["decision_type"] == decision_type], column_map)
        for decision_type in DECISION_TYPES
    }

    for criterion in column_map.keys():
        subjective_weight = SUBJECTIVE_WEIGHTS[criterion]
        overall_weight = float(overall_entropy[criterion])
        hvac_weight = float(per_type_entropy["HVAC"][criterion])
        appliance_weight = float(per_type_entropy["Appliance"][criterion])
        shower_weight = float(per_type_entropy["Shower"][criterion])

        rows.append(
            {
                "criterion": criterion,
                "subjective_weight": subjective_weight,
                "entropy_weight_overall": overall_weight,
                "entropy_weight_hvac": hvac_weight,
                "entropy_weight_appliance": appliance_weight,
                "entropy_weight_shower": shower_weight,
                "abs_diff_overall": abs(subjective_weight - overall_weight),
                "abs_diff_hvac": abs(subjective_weight - hvac_weight),
                "abs_diff_appliance": abs(subjective_weight - appliance_weight),
                "abs_diff_shower": abs(subjective_weight - shower_weight),
            }
        )

    comparison_table = pd.DataFrame(rows).set_index("criterion")
    return comparison_table


def export_results(comparison_table: pd.DataFrame, project_root: Path) -> Path:
    """Write the comparison table to Scoring Logic and Documentation/method/entropy_weights.csv."""
    output_dir = project_root / "Scoring Logic and Documentation" / "method"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "entropy_weights.csv"
    comparison_table.reset_index().to_csv(output_path, index=False, encoding='utf-8-sig')
    return output_path


def main() -> None:
    """Run the entropy-weight comparison workflow."""
    project_root = get_project_root()
    ground_truth = load_ground_truth_data(project_root)
    column_map = resolve_criterion_columns(ground_truth)

    comparison_table = build_comparison_table(ground_truth, column_map)
    output_path = export_results(comparison_table, project_root)

    print("Entropy Weights Comparison")
    print(comparison_table.round(6).to_string())
    print()
    print(f"Saved results to: {output_path}")


if __name__ == "__main__":
    main()