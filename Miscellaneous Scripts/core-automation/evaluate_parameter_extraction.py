import argparse
import importlib.util
import math
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY, get_output_folder
from sentinel_utils import read_table_clean, SENTINEL_FLOAT, CRITERIA

SENTINEL = SENTINEL_FLOAT

PARAMETER_MAP = {
    "HVAC": {
        "numeric": ["r_value", "seer", "hvac_age"],
        "categorical": ["occupancy_context"],
    },
    "Appliance": {
        "numeric": ["kwh_per_cycle"],
        "categorical": ["appliance", "baseline_time"],
    },
    "Shower": {
        "numeric": ["gpm", "tank_size", "water_heater_temp"],
        "categorical": [],
    },
}

SCENARIO_FILES = {
    "HVAC": "HVACScenarios.xlsx",
    "Appliance": "ApplianceScenarios.xlsx",
    "Shower": "ShowerScenarios.xlsx",
}


def _load_calculator(decision_type: str):
    module_names = {
        "HVAC": ("HVACGroundTruthCalculator.py", "HVACGroundTruthCalculator"),
        "Appliance": ("ApplianceGroundTruthCalculator.py", "ApplianceGroundTruthCalculator"),
        "Shower": ("ShowerGroundTruthCalculator.py", "ShowerGroundTruthCalculator"),
    }
    filename, class_name = module_names[decision_type]
    module_path = PROJECT_ROOT / "Ground Truth Calculators" / filename
    spec = importlib.util.spec_from_file_location(class_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load calculator module {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


CALCULATORS = {dtype: _load_calculator(dtype) for dtype in SCENARIO_FILES}


def _to_float(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    if not math.isfinite(value):
        return np.nan
    return value


def _clean_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _normalize_occupancy(value: str) -> str:
    value = _clean_text(value).lower()
    if value in {"occupied_all_day", "standard", "occupied", "home_all_day"}:
        return "occupied_all_day"
    if value in {"occupied_sleep", "sleep", "night", "overnight_sleep", "overnight"}:
        return "occupied_sleep"
    if value.startswith("unoccupied"):
        hours = "".join(ch for ch in value if ch.isdigit())
        if hours:
            return f"unoccupied_{min(max(int(hours), 0), 24)}"
        return "unoccupied_8"
    return value if value else ""


def _normalize_appliance(value: str) -> str:
    value = _clean_text(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "washer": "washer",
        "washing_machine": "washer",
        "dishwasher": "dishwasher",
        "dryer": "dryer",
    }
    return aliases.get(value, value)


def _parse_time_to_hour(value: str) -> Optional[int]:
    import re

    value = _clean_text(value)
    match = re.search(r"(\d{1,2})(?::\d{2})?\s*(am|pm)", value, re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    am_pm = match.group(2).lower()
    if am_pm == "pm" and hour != 12:
        return hour + 12
    if am_pm == "am" and hour == 12:
        return 0
    return hour


def _normalize_baseline_time(value: str) -> str:
    hour = _parse_time_to_hour(value)
    if hour is None:
        return _clean_text(value).lower()
    return f"{hour:02d}:00"


def _normalize_categorical(value: str, parameter: str) -> str:
    if parameter == "occupancy_context":
        return _normalize_occupancy(value)
    if parameter == "appliance":
        return _normalize_appliance(value)
    if parameter == "baseline_time":
        return _normalize_baseline_time(value)
    return _clean_text(value).lower()


def _rank_alternatives(alternatives_scores: List[Dict]) -> Dict:
    valid = []
    for idx, alt_data in enumerate(alternatives_scores):
        scores = alt_data["scores"]
        if any(_to_float(scores.get(c)) == SENTINEL for c in CRITERIA):
            continue
        weighted = sum(CRITERION_WEIGHTS[c] * float(scores[c]) for c in CRITERIA)
        valid.append((idx, weighted))
    if not valid:
        return {"ranked_alternatives": [], "weighted_scores": []}
    valid.sort(
        key=lambda item: (
            item[1],
            *[float(alternatives_scores[item[0]]["scores"][c]) for c in TIE_BREAK_PRIORITY],
        ),
        reverse=True,
    )
    return {
        "ranked_alternatives": [alternatives_scores[idx]["alternative"] for idx, _ in valid],
        "weighted_scores": [weighted for _, weighted in valid],
    }


def _scenario_to_scores(decision_type: str, scenario: Dict) -> List[Dict]:
    calculator = CALCULATORS[decision_type]()
    result = calculator.calculate_scenario_scores(scenario)
    if decision_type == "Shower":
        return [
            {
                "alternative": alt_data["alternative"],
                "scores": {
                    "energy_cost": alt_data["transformed_values"]["energy_cost"],
                    "environmental": alt_data["transformed_values"]["environmental"],
                    "comfort": alt_data["transformed_values"]["comfort"],
                    "practicality": alt_data["transformed_values"]["practicality"],
                },
            }
            for alt_data in result["alternatives"]
        ]
    return [
        {
            "alternative": alt,
            "scores": {
                "energy_cost": data["energy_cost_score"],
                "environmental": data["environmental_score"],
                "comfort": data["comfort_score"],
                "practicality": data["practicality_score"],
            },
        }
        for alt, data in result.items()
    ]


def _top1_alternative(decision_type: str, scenario: Dict) -> str:
    scored = _scenario_to_scores(decision_type, scenario)
    ranked = _rank_alternatives(scored)
    return ranked["ranked_alternatives"][0] if ranked["ranked_alternatives"] else ""


def _alternatives_from_row(row: pd.Series) -> List[str]:
    return [
        _clean_text(row.get(f"alternative_{i}"))
        for i in range(1, 4)
        if _clean_text(row.get(f"alternative_{i}"))
    ]


def _build_ground_truth_scenario(decision_type: str, test_row: pd.Series, gt_row: pd.Series) -> Dict:
    base = {
        "question": gt_row.get("question", test_row.get("question", "")),
        "location": gt_row.get("location", test_row.get("location", "")),
        "alternatives": _alternatives_from_row(test_row),
        "alternative_1": test_row.get("alternative_1", ""),
        "alternative_2": test_row.get("alternative_2", ""),
        "alternative_3": test_row.get("alternative_3", ""),
    }
    if decision_type == "HVAC":
        base.update({
            "square_footage": float(gt_row["square_footage"]),
            "outdoor_temp": float(gt_row["outdoor_temp"]),
            "r_value": float(gt_row["r_value"]),
            "seer": float(gt_row["seer"]),
            "hvac_age": float(gt_row["hvac_age"]),
            "household_size": float(gt_row["household_size"]),
            "housing_type": _clean_text(gt_row.get("housing_type", "")),
            "utility_budget": float(gt_row.get("utility_budget", 0) or 0),
            "occupancy_context": _clean_text(gt_row.get("occupancy_context", "")),
        })
    elif decision_type == "Appliance":
        base.update({
            "location": _clean_text(gt_row["location"]),
            "utility_budget": float(gt_row.get("utility_budget", 0) or 0),
            "appliance": _clean_text(gt_row["appliance"]),
            "housing_type": _clean_text(gt_row.get("housing_type", "")),
            "household_size": float(gt_row["household_size"]),
            "kwh_per_cycle": float(gt_row["kwh_per_cycle"]),
            "baseline_time": _clean_text(gt_row.get("baseline_time", "")),
        })
    elif decision_type == "Shower":
        base.update({
            "household_size": float(gt_row["household_size"]),
            "tank_size": float(gt_row["tank_size"]),
            "gpm": float(gt_row["gpm"]),
            "utility_budget": float(gt_row.get("utility_budget", 0) or 0),
            "housing_type": _clean_text(gt_row.get("housing_type", "")),
            "outdoor_temp": float(gt_row["outdoor_temp"]),
            "water_heater_temp": float(gt_row["water_heater_temp"]),
        })
    return base


def _load_LLM_Parameterized_Reference_Scoring_results(path: Path) -> pd.DataFrame:
    df = read_table_clean(path)
    required = ["scenario_id", "question", "location", "decision_type"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"LLM-Parameterized_Reference_Scoring results missing required columns: {missing}")
    if "input_decision_type" in df.columns:
        df["decision_type"] = df["decision_type"].replace("", np.nan).fillna(df["input_decision_type"])
    df = df.drop_duplicates(["scenario_id"], keep="first").copy()
    df["scenario_id"] = pd.to_numeric(df["scenario_id"], errors="coerce").astype("Int64")
    return df


def _load_test_scenarios(path: Path) -> pd.DataFrame:
    df = read_table_clean(path)
    df["scenario_id"] = np.arange(1, len(df) + 1)
    df["_dtype_position"] = df.groupby("decision_type").cumcount() + 1
    return df


def _load_ground_truth(decision_type: str, scenario_dir: Path) -> pd.DataFrame:
    path = scenario_dir / SCENARIO_FILES[decision_type]
    keep_str_cols = {
        "HVAC": ["question", "location", "insulation", "housing_type", "house_age", "alternative_1", "alternative_2", "alternative_3", "occupancy_context"],
        "Appliance": ["question", "location", "appliance", "housing_type", "baseline_time", "alternative_1", "alternative_2", "alternative_3"],
        "Shower": ["question", "location", "housing_type", "flow_rate", "alternative_1", "alternative_2", "alternative_3"],
    }
    df = read_table_clean(path, keep_str_cols=keep_str_cols[decision_type])
    df["_source_position"] = np.arange(1, len(df) + 1)
    return df


# Descriptor columns used to disambiguate when question+location is not unique.
# Position cannot be used: _dtype_position indexes the Test sheet (1..n_test) while
# _source_position indexes the combined Test+RAG master (1..n_master), so the two
# coordinate systems do not correspond and the comparison silently drops rows.
MATCH_KEYS = {
    "HVAC": ["square_footage", "household_size", "outdoor_temp", "utility_budget",
             "housing_type", "alternative_1", "alternative_2", "alternative_3"],
    "Appliance": ["household_size", "outdoor_temp", "utility_budget", "housing_type",
                  "alternative_1", "alternative_2", "alternative_3"],
    "Shower": ["household_size", "outdoor_temp", "utility_budget", "housing_type",
               "alternative_1", "alternative_2", "alternative_3"],
}


def _match_ground_truth(test_row: pd.Series, gt_df: pd.DataFrame,
                        decision_type: Optional[str] = None) -> Optional[pd.Series]:
    question = _clean_text(test_row.get("question"))
    location = _clean_text(test_row.get("location"))
    candidates = gt_df[
        (gt_df["question"].map(_clean_text) == question) &
        (gt_df["location"].map(_clean_text) == location)
    ]
    if len(candidates) == 1:
        return candidates.iloc[0]
    if len(candidates) > 1:
        for key in MATCH_KEYS.get(decision_type or "", []):
            if len(candidates) == 1:
                break
            if key not in candidates.columns or key not in test_row.index:
                continue
            target = _clean_text(str(test_row.get(key)))
            narrowed = candidates[candidates[key].map(lambda v: _clean_text(str(v))) == target]
            if not narrowed.empty:
                candidates = narrowed
        if len(candidates) == 1:
            return candidates.iloc[0]
    return None


def _extracted_value(LLM_Parameterized_Reference_Scoring_row: pd.Series, parameter: str) -> object:
    col = f"extracted_{parameter}"
    if col not in LLM_Parameterized_Reference_Scoring_row.index:
        return ""
    return LLM_Parameterized_Reference_Scoring_row.get(col, "")


def _evaluate_numeric(decision_type: str, parameter: str, LLM_Parameterized_Reference_Scoring_row: pd.Series, gt_row: pd.Series) -> Dict:
    gt = _to_float(gt_row.get(parameter))
    extracted = _to_float(_extracted_value(LLM_Parameterized_Reference_Scoring_row, parameter))
    if pd.isna(gt) or pd.isna(extracted):
        return {"parameter": parameter, "decision_type": decision_type, "valid": False, "missing_gt": pd.isna(gt), "missing_extracted": pd.isna(extracted)}
    signed_error = extracted - gt
    return {
        "parameter": parameter,
        "decision_type": decision_type,
        "valid": True,
        "gt": gt,
        "extracted": extracted,
        "signed_error": signed_error,
        "abs_error": abs(signed_error),
    }


def _evaluate_categorical(decision_type: str, parameter: str, LLM_Parameterized_Reference_Scoring_row: pd.Series, gt_row: pd.Series) -> Dict:
    gt = _normalize_categorical(gt_row.get(parameter, ""), parameter)
    extracted = _normalize_categorical(_extracted_value(LLM_Parameterized_Reference_Scoring_row, parameter), parameter)
    if not gt or not extracted:
        return {
            "parameter": parameter,
            "decision_type": decision_type,
            "valid": False,
            "missing_gt": not bool(gt),
            "missing_extracted": not bool(extracted),
            "correct": False,
        }
    return {
        "parameter": parameter,
        "decision_type": decision_type,
        "valid": True,
        "gt": gt,
        "extracted": extracted,
        "correct": gt == extracted,
    }


def _summarize_numeric(rows: List[Dict]) -> Dict:
    valid = [row for row in rows if row.get("valid")]
    errors = np.array([row["abs_error"] for row in valid], dtype=float)
    if len(errors) == 0:
        return {
            "n": len(rows),
            "n_valid": 0,
            "MAE": np.nan,
            "RMSE": np.nan,
            "mean_abs_error": np.nan,
            "median_abs_error": np.nan,
            "std_abs_error": np.nan,
            "p25_abs_error": np.nan,
            "p75_abs_error": np.nan,
            "p90_abs_error": np.nan,
            "n_missing_gt": sum(row.get("missing_gt") for row in rows),
            "n_missing_extracted": sum(row.get("missing_extracted") for row in rows),
        }
    return {
        "n": len(rows),
        "n_valid": len(valid),
        "MAE": float(np.mean(errors)),
        "RMSE": float(np.sqrt(np.mean(errors ** 2))),
        "mean_abs_error": float(np.mean(errors)),
        "median_abs_error": float(np.median(errors)),
        "std_abs_error": float(np.std(errors, ddof=1)) if len(errors) > 1 else 0.0,
        "p25_abs_error": float(np.percentile(errors, 25)),
        "p75_abs_error": float(np.percentile(errors, 75)),
        "p90_abs_error": float(np.percentile(errors, 90)),
        "n_missing_gt": sum(row.get("missing_gt") is True for row in rows),
        "n_missing_extracted": sum(row.get("missing_extracted") is True for row in rows),
    }


def _summarize_categorical(rows: List[Dict]) -> Dict:
    valid = [row for row in rows if row.get("valid")]
    return {
        "n": len(rows),
        "n_valid": len(valid),
        "accuracy": float(np.mean([row["correct"] for row in valid])) if valid else np.nan,
        "n_correct": int(sum(row.get("correct") for row in valid)),
        "n_incorrect": int(len(valid) - sum(row.get("correct") for row in valid)),
        "n_missing_gt": sum(row.get("missing_gt") is True for row in rows),
        "n_missing_extracted": sum(row.get("missing_extracted") is True for row in rows),
    }


def _run_counterfactual(decision_type: str, gt_scenario: Dict, parameter: str, extracted_value: object) -> Dict:
    scenario = dict(gt_scenario)
    scenario[parameter] = extracted_value
    gt_top1 = _top1_alternative(decision_type, gt_scenario)
    cf_top1 = _top1_alternative(decision_type, scenario)
    return {
        "decision_type": decision_type,
        "parameter": parameter,
        "ground_truth_top1": gt_top1,
        "counterfactual_top1": cf_top1,
        "changed": gt_top1 != cf_top1,
    }


def _format_md_table(df: pd.DataFrame, float_cols=None, max_rows: Optional[int] = None) -> str:
    float_cols = set(float_cols or [])
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "_No rows._"
    rendered = df.copy()
    for col in rendered.columns:
        if col in float_cols:
            rendered[col] = rendered[col].map(lambda v: "N/A" if pd.isna(v) else f"{float(v):.4f}")
        else:
            rendered[col] = rendered[col].map(lambda v: "" if pd.isna(v) else str(v))
    headers = list(rendered.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def _write_report(path: Path, sections: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# LLM-Parameterized_Reference_Scoring Parameter Extraction Evaluation\n\n")
        for title, body in sections.items():
            f.write(f"## {title}\n\n{body}\n\n")


def evaluate(args) -> Dict:
    results_path = Path(args.results)
    output_path = Path(args.output)
    scenario_dir = Path(args.scenario_dir)
    test_df = _load_test_scenarios(scenario_dir / "TestScenarios.xlsx")
    LLM_Parameterized_Reference_Scoring_df = _load_LLM_Parameterized_Reference_Scoring_results(results_path)

    numeric_rows = []
    categorical_rows = []
    counterfactual_rows = []
    matched = 0
    unmatched = 0

    for _, LLM_Parameterized_Reference_Scoring_row in LLM_Parameterized_Reference_Scoring_df.iterrows():
        sid = LLM_Parameterized_Reference_Scoring_row.get("scenario_id")
        test_match = test_df[test_df["scenario_id"].astype(int) == int(sid)]
        if test_match.empty:
            unmatched += 1
            continue
        test_row = test_match.iloc[0]
        decision_type = _clean_text(LLM_Parameterized_Reference_Scoring_row.get("decision_type")) or _clean_text(test_row.get("decision_type"))
        gt_df = _load_ground_truth(decision_type, scenario_dir)
        gt_row = _match_ground_truth(test_row, gt_df, decision_type)
        if gt_row is None:
            unmatched += 1
            continue
        matched += 1
        params = PARAMETER_MAP.get(decision_type, {"numeric": [], "categorical": []})
        for parameter in params["numeric"]:
            numeric_rows.append(_evaluate_numeric(decision_type, parameter, LLM_Parameterized_Reference_Scoring_row, gt_row))
        for parameter in params["categorical"]:
            categorical_rows.append(_evaluate_categorical(decision_type, parameter, LLM_Parameterized_Reference_Scoring_row, gt_row))

        gt_scenario = _build_ground_truth_scenario(decision_type, test_row, gt_row)
        for parameter in params["numeric"] + params["categorical"]:
            extracted = _extracted_value(LLM_Parameterized_Reference_Scoring_row, parameter)
            if parameter in params["numeric"]:
                extracted_value = _to_float(extracted)
                gt_value = _to_float(gt_row.get(parameter))
                if pd.isna(extracted_value) or pd.isna(gt_value) or extracted_value == gt_value:
                    continue
            else:
                extracted_norm = _normalize_categorical(extracted, parameter)
                gt_norm = _normalize_categorical(gt_row.get(parameter, ""), parameter)
                if not extracted_norm or not gt_norm or extracted_norm == gt_norm:
                    continue
                extracted_value = extracted
            try:
                counterfactual_rows.append(_run_counterfactual(decision_type, gt_scenario, parameter, extracted_value))
            except Exception as exc:
                counterfactual_rows.append({
                    "decision_type": decision_type,
                    "parameter": parameter,
                    "ground_truth_top1": "",
                    "counterfactual_top1": "",
                    "changed": False,
                    "error": str(exc),
                })

    numeric_summary = []
    for (decision_type, parameter), rows in pd.DataFrame(numeric_rows).groupby(["decision_type", "parameter"]):
        summary = _summarize_numeric(rows.to_dict("records"))
        summary.update({"decision_type": decision_type, "parameter": parameter})
        numeric_summary.append(summary)

    categorical_summary = []
    cat_df = pd.DataFrame(categorical_rows)
    if not cat_df.empty:
        for (decision_type, parameter), rows in cat_df.groupby(["decision_type", "parameter"]):
            summary = _summarize_categorical(rows.to_dict("records"))
            summary.update({"decision_type": decision_type, "parameter": parameter})
            categorical_summary.append(summary)

    cf_df = pd.DataFrame(counterfactual_rows)
    sensitivity_summary = []
    if not cf_df.empty:
        for (decision_type, parameter), rows in cf_df.groupby(["decision_type", "parameter"]):
            if "error" in rows.columns:
                rows = rows[rows["error"].map(lambda v: _clean_text(str(v)) == "")]
            n_evaluated = len(rows)
            n_changes = int(rows["changed"].sum()) if n_evaluated else 0
            denominator_all = int((pd.DataFrame(numeric_rows).assign(decision_type=lambda d: d["decision_type"], parameter=lambda d: d["parameter"]) if numeric_rows else pd.DataFrame()).shape[0])
            if parameter in PARAMETER_MAP.get(decision_type, {}).get("numeric", []):
                denominator_all = int(test_df[test_df["decision_type"] == decision_type].shape[0])
            else:
                denominator_all = int(test_df[test_df["decision_type"] == decision_type].shape[0])
            sensitivity_summary.append({
                "decision_type": decision_type,
                "parameter": parameter,
                "n_error_cases_evaluated": n_evaluated,
                "n_top1_changes": n_changes,
                "conditional_change_probability": n_changes / n_evaluated if n_evaluated else np.nan,
                "unconditional_change_probability": n_changes / denominator_all if denominator_all else np.nan,
            })

    numeric_df = pd.DataFrame(numeric_summary)
    categorical_df = pd.DataFrame(categorical_summary)
    sensitivity_df = pd.DataFrame(sensitivity_summary)

    print("\nLLM-Parameterized_Reference_Scoring PARAMETER EXTRACTION EVALUATION")
    print(f"Matched scenarios: {matched}/{len(LLM_Parameterized_Reference_Scoring_df)}")
    if unmatched:
        print(f"Unmatched scenarios: {unmatched}")
    if not numeric_df.empty:
        print("\nNumeric parameter errors")
        print(_format_md_table(numeric_df, float_cols=[c for c in numeric_df.columns if c not in {"decision_type", "parameter"}]))
    if not categorical_df.empty:
        print("\nCategorical parameter accuracy")
        print(_format_md_table(categorical_df, float_cols=["accuracy"]))
    if not sensitivity_df.empty:
        print("\nCounterfactual top-1 sensitivity")
        print(_format_md_table(sensitivity_df, float_cols=["conditional_change_probability", "unconditional_change_probability"]))

    sections = {
        "Overview": (
            f"- Results file: `{results_path}`\n"
            f"- Matched scenarios: {matched}/{len(LLM_Parameterized_Reference_Scoring_df)}\n"
            f"- Unmatched scenarios: {unmatched}\n"
            f"- Counterfactual rows evaluated: {len(cf_df)}"
        ),
        "Numeric Parameter Error Distribution": _format_md_table(
            numeric_df,
            float_cols=[
                "n", "n_valid", "MAE", "RMSE", "mean_abs_error", "median_abs_error",
                "std_abs_error", "p25_abs_error", "p75_abs_error", "p90_abs_error",
                "n_missing_gt", "n_missing_extracted",
            ],
        ),
        "Categorical Parameter Accuracy": _format_md_table(
            categorical_df,
            float_cols=["n", "n_valid", "accuracy", "n_correct", "n_incorrect", "n_missing_gt", "n_missing_extracted"],
        ),
        "Counterfactual Top-1 Sensitivity": _format_md_table(
            sensitivity_df,
            float_cols=["n_error_cases_evaluated", "n_top1_changes", "conditional_change_probability", "unconditional_change_probability"],
        ),
    }
    if not cf_df.empty:
        sections["Counterfactual Case Detail"] = _format_md_table(
            cf_df,
            max_rows=50,
        )
    _write_report(output_path, sections)
    print(f"\nReport saved to: {output_path}")

    return {
        "matched_scenarios": matched,
        "unmatched_scenarios": unmatched,
        "numeric_summary": numeric_df,
        "categorical_summary": categorical_df,
        "sensitivity_summary": sensitivity_df,
        "counterfactual_detail": cf_df,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate LLM-Parameterized_Reference_Scoring parameter extraction against source scenario ground truth.")
    parser.add_argument(
        "--results",
        default=str(PROJECT_ROOT / get_output_folder() / "LLM-Parameterized_Reference_Scoring_results.xlsx"),
        help="Path to aggregated LLM-Parameterized_Reference_Scoring_results.xlsx or a per-run LLM-Parameterized_Reference_Scoring_results_run_XX.xlsx.",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / get_output_folder() / "LLM-Parameterized_Reference_Scoring_parameter_evaluation.md"),
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--scenario-dir",
        default=str(PROJECT_ROOT / "Scenario Files"),
        help="Directory containing TestScenarios.xlsx and domain scenario files.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    evaluate(parse_args())
