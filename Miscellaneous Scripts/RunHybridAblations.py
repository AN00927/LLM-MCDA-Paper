"""AH parameter-provenance ablation: true vs extracted vs default hidden parameters.

Isolates how much the LLM's parameter extraction contributes to A_H's ranking
accuracy, beyond the contribution of simply having the deterministic calculator.
Three arms, all scored by the same reference calculators over the same 195 test
scenarios:

  true_params    -- the calculator receives the scenario's true engineering values.
                    This is the reference ranking itself, so it is the ceiling:
                    the best A_H could do with perfect extraction.
  extracted      -- the calculator receives the values the LLM actually returned,
                    read from the extracted_* columns of an existing
                    LLM-Parameterized_Reference_Scoring_results.xlsx.
  default_params -- the calculator receives a fixed corpus-median value per
                    parameter, with no per-scenario inference at all. This is the
                    floor: calculator access without meaningful LLM contribution.

Extraction's contribution is the gap between default_params and extracted; the
headroom remaining is the gap between extracted and true_params.

MAKES ZERO API CALLS. Every arm is computed from files already in the repo, so
this is free to run and re-run. Gemini is excluded by default only for
consistency with the paid ablations; since nothing here costs money, pass
--models with all four keys if you want it included.

Sentinel handling: a scenario whose extraction failed carries the 1928 sentinel
and is excluded from that arm's metrics rather than being silently replaced by a
neutral default. Per-arm scenario counts are reported so any exclusion is visible.
"""

import argparse
import contextlib
import importlib.util
import io
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from model_config import MODEL_SPECS, CRITERION_WEIGHTS
from sentinel_utils import (
    CRITERIA,
    SENTINEL_FLOAT,
    apply_mavt_ranking,
    is_sentinel,
    read_table_clean,
)

SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"

# Hidden engineering parameters the LLM is asked to estimate, by decision type.
# Must stay in lockstep with the extraction prompt in
# Architectures/LLM-Parameterized_Reference_Scoring.py.
HIDDEN_PARAMS = {
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

ARM_SPECS = OrderedDict([
    ("true_params", {
        "label": "True hidden parameters (reference ceiling)",
        "source": "truth",
    }),
    ("extracted", {
        "label": "LLM-extracted hidden parameters",
        "source": "extracted",
    }),
    ("default_params", {
        "label": "Corpus-median hidden parameters (no inference)",
        "source": "default",
    }),
])


def _load_calculator(decision_type: str):
    names = {
        "HVAC": ("HVACGroundTruthCalculator.py", "HVACGroundTruthCalculator"),
        "Appliance": ("ApplianceGroundTruthCalculator.py", "ApplianceGroundTruthCalculator"),
        "Shower": ("ShowerGroundTruthCalculator.py", "ShowerGroundTruthCalculator"),
    }
    filename, class_name = names[decision_type]
    path = PROJECT_ROOT / "Ground Truth Calculators" / filename
    spec = importlib.util.spec_from_file_location(class_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


CALCULATORS = {d: _load_calculator(d) for d in SCENARIO_FILES}


def _clean_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _to_float(value):
    if value is None:
        return np.nan
    try:
        if pd.isna(value):
            return np.nan
    except (TypeError, ValueError):
        pass
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return np.nan


# ---------------------------------------------------------------------------
# Scenario matching (mirrors the corrected matcher in EvaluateHybridExtraction)
# ---------------------------------------------------------------------------

MATCH_KEYS = {
    "HVAC": ["square_footage", "household_size", "outdoor_temp", "utility_budget",
             "housing_type", "alternative_1", "alternative_2", "alternative_3"],
    "Appliance": ["household_size", "outdoor_temp", "utility_budget", "housing_type",
                  "alternative_1", "alternative_2", "alternative_3"],
    "Shower": ["household_size", "outdoor_temp", "utility_budget", "housing_type",
               "alternative_1", "alternative_2", "alternative_3"],
}


def load_test_scenarios() -> pd.DataFrame:
    df = read_table_clean(SCENARIO_DIR / "TestScenarios.xlsx")
    df["scenario_id"] = np.arange(1, len(df) + 1)
    return df


def load_ground_truth(decision_type: str) -> pd.DataFrame:
    keep_str = {
        "HVAC": ["question", "location", "insulation", "housing_type", "house_age",
                 "alternative_1", "alternative_2", "alternative_3", "occupancy_context"],
        "Appliance": ["question", "location", "appliance", "housing_type", "baseline_time",
                      "alternative_1", "alternative_2", "alternative_3"],
        "Shower": ["question", "location", "housing_type", "flow_rate",
                   "alternative_1", "alternative_2", "alternative_3"],
    }
    return read_table_clean(SCENARIO_DIR / SCENARIO_FILES[decision_type],
                            keep_str_cols=keep_str[decision_type])


def match_ground_truth(test_row: pd.Series, gt_df: pd.DataFrame,
                       decision_type: str) -> Optional[pd.Series]:
    q = _clean_text(test_row.get("question"))
    loc = _clean_text(test_row.get("location"))
    cand = gt_df[(gt_df["question"].map(_clean_text) == q)
                 & (gt_df["location"].map(_clean_text) == loc)]
    if len(cand) == 1:
        return cand.iloc[0]
    for key in MATCH_KEYS.get(decision_type, []):
        if len(cand) == 1:
            break
        if key not in cand.columns or key not in test_row.index:
            continue
        target = _clean_text(str(test_row.get(key)))
        narrowed = cand[cand[key].map(lambda v: _clean_text(str(v))) == target]
        if not narrowed.empty:
            cand = narrowed
    return cand.iloc[0] if len(cand) == 1 else None


# ---------------------------------------------------------------------------
# Default (corpus-median) parameter values
# ---------------------------------------------------------------------------

def compute_defaults() -> Dict[str, Dict[str, object]]:
    """Median numeric / modal categorical value per hidden parameter, over the
    full source corpus for that decision type. These are the 'no inference'
    values: a single constant reused for every scenario."""
    defaults = {}
    for dtype, groups in HIDDEN_PARAMS.items():
        gt = load_ground_truth(dtype)
        d = {}
        for p in groups["numeric"]:
            d[p] = float(pd.to_numeric(gt[p], errors="coerce").median())
        for p in groups["categorical"]:
            vals = gt[p].map(_clean_text)
            vals = vals[vals != ""]
            d[p] = vals.mode().iloc[0] if not vals.empty else ""
        defaults[dtype] = d
    return defaults


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def build_scenario(decision_type: str, test_row: pd.Series, gt_row: pd.Series,
                   params: Dict[str, object]) -> Dict:
    """Known homeowner-reported fields come from the sheet; the hidden
    engineering parameters come from `params` (the arm under test)."""
    alts = [_clean_text(test_row.get(f"alternative_{i}")) for i in range(1, 4)]
    alts = [a for a in alts if a]
    base = {
        "question": _clean_text(gt_row.get("question")),
        "location": _clean_text(gt_row.get("location")),
        "alternatives": alts,
        "alternative_1": test_row.get("alternative_1", ""),
        "alternative_2": test_row.get("alternative_2", ""),
        "alternative_3": test_row.get("alternative_3", ""),
        "household_size": float(gt_row["household_size"]),
        "housing_type": _clean_text(gt_row.get("housing_type", "")),
        "utility_budget": float(gt_row.get("utility_budget", 0) or 0),
    }
    if decision_type == "HVAC":
        base.update({
            "square_footage": float(gt_row["square_footage"]),
            "outdoor_temp": float(gt_row["outdoor_temp"]),
        })
    elif decision_type == "Shower":
        base.update({"outdoor_temp": float(gt_row["outdoor_temp"])})
    base.update(params)
    return base


def score_scenario(decision_type: str, scenario: Dict) -> Optional[List[Dict]]:
    """Run the reference calculator. Returns per-alternative criterion scores, or
    None if the calculator raises (recorded as a failure, never defaulted).

    The three calculators do not share a return shape, so both are handled:
      HVAC / Appliance: {alt_label: {"<criterion>_score": v, ...}}
      Shower:           {"alternatives": [{"alternative": l,
                                           "transformed_values": {crit: v}}]}
    Verified against all three calculators rather than assumed.
    """
    calc = CALCULATORS[decision_type]()
    try:
        # The calculators print per-alternative progress; silence it so the
        # ablation's own output stays readable across ~1,700 scoring calls.
        with contextlib.redirect_stdout(io.StringIO()):
            result = calc.calculate_scenario_scores(scenario)
    except Exception:
        return None
    if not isinstance(result, dict):
        return None

    rows = []
    if "alternatives" in result and isinstance(result["alternatives"], list):
        for item in result["alternatives"]:
            if not isinstance(item, dict):
                return None
            vals = item.get("transformed_values", item)
            row = {"alternative": _clean_text(item.get("alternative"))}
            for c in CRITERIA:
                row[c] = vals.get(c, vals.get(f"{c}_score", SENTINEL_FLOAT))
            rows.append(row)
    else:
        for alt_label, scores in result.items():
            if not isinstance(scores, dict):
                continue
            row = {"alternative": _clean_text(alt_label)}
            for c in CRITERIA:
                row[c] = scores.get(f"{c}_score", scores.get(c, SENTINEL_FLOAT))
            rows.append(row)
    return rows or None


def ranks_from_scores(scored: List[Dict]) -> Tuple[List[str], List[int]]:
    r = apply_mavt_ranking(scored)
    return r["ranked_alternatives"], r["ranks"]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def scenario_metrics(arm_scored: List[Dict], ref_scored: List[Dict]) -> Optional[Dict]:
    """Kendall tau / Top-1 / MAE for one scenario, arm vs reference."""
    if arm_scored is None or ref_scored is None:
        return None
    if any(is_sentinel(a[c]) for a in arm_scored for c in CRITERIA):
        return None
    if any(is_sentinel(a[c]) for a in ref_scored for c in CRITERIA):
        return None

    ref_by_alt = {a["alternative"]: a for a in ref_scored}
    common = [a["alternative"] for a in arm_scored if a["alternative"] in ref_by_alt]
    if len(common) < 2:
        return None

    arm_r = apply_mavt_ranking([a for a in arm_scored if a["alternative"] in ref_by_alt])
    ref_r = apply_mavt_ranking([ref_by_alt[a] for a in common])

    arm_rank = {alt: rk for alt, rk in zip(
        [a["alternative"] for a in arm_scored if a["alternative"] in ref_by_alt], arm_r["ranks"])}
    ref_rank = {alt: rk for alt, rk in zip(common, ref_r["ranks"])}

    a_vec = [arm_rank[c] for c in common]
    r_vec = [ref_rank[c] for c in common]
    if len(set(a_vec)) < 2 or len(set(r_vec)) < 2:
        tau = np.nan
    else:
        tau = kendalltau(a_vec, r_vec).correlation

    top1 = 1.0 if (arm_r["ranked_alternatives"] and ref_r["ranked_alternatives"]
                   and arm_r["ranked_alternatives"][0] == ref_r["ranked_alternatives"][0]) else 0.0

    errs = [abs(float(a[c]) - float(ref_by_alt[a["alternative"]][c]))
            for a in arm_scored if a["alternative"] in ref_by_alt for c in CRITERIA]

    return {"kendall_tau": tau, "top1": top1, "mae": float(np.mean(errs)) if errs else np.nan}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def extracted_params(row: pd.Series, decision_type: str) -> Optional[Dict[str, object]]:
    groups = HIDDEN_PARAMS[decision_type]
    if str(row.get("extraction_failed", "")).strip().lower() in {"true", "1", "yes"}:
        return None
    out = {}
    for p in groups["numeric"]:
        v = _to_float(row.get(f"extracted_{p}"))
        if pd.isna(v) or is_sentinel(v):
            return None
        out[p] = v
    for p in groups["categorical"]:
        v = _clean_text(row.get(f"extracted_{p}"))
        if not v or is_sentinel(v):
            return None
        out[p] = v
    return out


def true_params(gt_row: pd.Series, decision_type: str) -> Dict[str, object]:
    groups = HIDDEN_PARAMS[decision_type]
    out = {}
    for p in groups["numeric"]:
        out[p] = _to_float(gt_row.get(p))
    for p in groups["categorical"]:
        out[p] = _clean_text(gt_row.get(p))
    return out


def run(args) -> pd.DataFrame:
    test_df = load_test_scenarios()
    gt_cache = {d: load_ground_truth(d) for d in SCENARIO_FILES}
    defaults = compute_defaults()

    print("Corpus-median default parameters (the 'no inference' arm):")
    for d, params in defaults.items():
        print(f"  {d}: " + ", ".join(f"{k}={v}" for k, v in params.items()))
    print()

    records = []
    for model_key in args.models:
        folder = PROJECT_ROOT / MODEL_SPECS[model_key]["output_folder"]
        results_path = folder / "LLM-Parameterized_Reference_Scoring_results.xlsx"
        if not results_path.exists():
            print(f"SKIP {model_key}: {results_path.name} not found")
            continue
        res = read_table_clean(results_path)
        # One row per scenario; the file repeats scenarios per alternative.
        res = res.drop_duplicates(subset=["scenario_id"])
        by_sid = {int(r["scenario_id"]): r for _, r in res.iterrows()}
        print(f"{model_key}: {len(by_sid)} scenarios in results file")

        matched = unmatched = 0
        for _, test_row in test_df.iterrows():
            sid = int(test_row["scenario_id"])
            dtype = _clean_text(test_row.get("decision_type"))
            if dtype not in HIDDEN_PARAMS:
                continue
            gt_row = match_ground_truth(test_row, gt_cache[dtype], dtype)
            if gt_row is None:
                unmatched += 1
                continue
            matched += 1

            ref_scored = score_scenario(dtype, build_scenario(
                dtype, test_row, gt_row, true_params(gt_row, dtype)))

            arm_params = {
                "true_params": true_params(gt_row, dtype),
                "default_params": defaults[dtype],
                "extracted": extracted_params(by_sid[sid], dtype) if sid in by_sid else None,
            }
            for arm_id in ARM_SPECS:
                p = arm_params[arm_id]
                if p is None:
                    records.append({"model": model_key, "arm": arm_id, "decision_type": dtype,
                                    "scenario_id": sid, "kendall_tau": np.nan,
                                    "top1": np.nan, "mae": np.nan, "failed": True})
                    continue
                scored = score_scenario(dtype, build_scenario(dtype, test_row, gt_row, p))
                m = scenario_metrics(scored, ref_scored)
                rec = {"model": model_key, "arm": arm_id, "decision_type": dtype,
                       "scenario_id": sid, "failed": m is None}
                rec.update(m or {"kendall_tau": np.nan, "top1": np.nan, "mae": np.nan})
                records.append(rec)
        print(f"  matched {matched}/{matched + unmatched} scenarios"
              + (f" ({unmatched} unmatched)" if unmatched else ""))

    return pd.DataFrame(records)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, arm), g in df.groupby(["model", "arm"], sort=False):
        ok = g[~g["failed"]]
        rows.append({
            "model": model,
            "arm": arm,
            "label": ARM_SPECS[arm]["label"],
            "n_scenarios": len(g),
            "n_scored": len(ok),
            "success_rate": len(ok) / len(g) if len(g) else np.nan,
            "kendall_tau": ok["kendall_tau"].mean(),
            "top1_accuracy": ok["top1"].mean(),
            "mae": ok["mae"].mean(),
        })
    return pd.DataFrame(rows)


def parse_args():
    p = argparse.ArgumentParser(
        description="AH parameter-provenance ablation (true vs extracted vs default). "
                    "Makes zero API calls.")
    p.add_argument("--models", nargs="+",
                   default=[k for k in MODEL_SPECS if k != "gemini"],
                   choices=list(MODEL_SPECS.keys()),
                   help="Model keys whose extracted parameters to evaluate. Default excludes "
                        "gemini for consistency with the paid ablations; this script is free, "
                        "so pass all four keys to include it.")
    p.add_argument("--output-dir", default=str(PROJECT_ROOT / "Analysis" / "Hybrid_Ablation"))
    p.add_argument("--output", default=str(PROJECT_ROOT / "hybrid_ablation_results.md"))
    return p.parse_args()


def main():
    args = parse_args()
    df = run(args)
    if df.empty:
        print("No records produced.")
        return
    summary = summarize(df)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_dir / "hybrid_ablation_summary.xlsx") as xl:
        summary.to_excel(xl, sheet_name="summary", index=False)
        df.to_excel(xl, sheet_name="per_scenario", index=False)

    print("\n=== AH parameter-provenance ablation ===")
    cols = ["model", "arm", "n_scored", "success_rate", "kendall_tau", "top1_accuracy", "mae"]
    print(summary[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # Hand-rolled markdown: pandas.to_markdown needs `tabulate`, which is not a
    # declared dependency of this repo.
    def _md(df: pd.DataFrame) -> str:
        hdr = list(df.columns)
        out = ["| " + " | ".join(hdr) + " |",
               "| " + " | ".join("---" for _ in hdr) + " |"]
        for _, r in df.iterrows():
            cells = [f"{r[h]:.4f}" if isinstance(r[h], float) else str(r[h]) for h in hdr]
            out.append("| " + " | ".join(cells) + " |")
        return "\n".join(out)

    lines = ["# AH Parameter-Provenance Ablation", "",
             "Arms: true (ceiling) / extracted (actual) / default (floor). Zero API calls.", "",
             _md(summary[cols])]
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {args.output} and {out_dir / 'hybrid_ablation_summary.xlsx'}")


if __name__ == "__main__":
    main()
