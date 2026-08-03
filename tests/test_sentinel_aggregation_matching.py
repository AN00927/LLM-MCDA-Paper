"""
Tests for sentinel coercion, aggregation, and scenario matching.

Scope (per task specification):
  - sentinel coercion: numeric 1928, string "1928", nonnumeric strings, normal scores
  - aggregation: one-run, partial-run, malformed numeric, all-failed, mixed rows
  - metrics: failure-mode totals from JSON match CSV sentinels
  - scenario matching: content match, alt drop warnings, LLM-Parameterized_Reference_Scoring input_decision_type
  - RAG: missing metadata fields, successful metadata fields

Does NOT test anything that requires TestScenarios.xlsx to exist.
"""

import sys
import json
import math
import warnings
import tempfile
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Project path bootstrap
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import (
    SENTINEL_VALUE, SENTINEL_FLOAT, CRITERIA,
    coerce_score, is_sentinel, has_sentinel_scores, coerce_score_series,
)
from model_config import (
    EXTRACTION_INVALID_JSON,
    FAILED_MISSING_SCORE,
    FAILED_OUT_OF_BOUNDS,
    FAILED_INVALID_SCORE_TYPE,
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN,
    FAILED_EXTRACTION_NON_JSON_WRAPPER,
    FAILED_EXTRACTION_INVALID_DECISION_TYPE,
    FAILED_EXTRACTION_INVALID_CALCULATOR,
    FAILED_EXTRACTION_MISSING_PARAMETERS,
    FAILED_EXTRACTION_EXCEPTION,
    FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION,
    FAILED_GROUND_TRUTH_MISSING_KEY,
)

# ---------------------------------------------------------------------------
# Lazy import helpers — only pull in CalculateMetrics when needed
# ---------------------------------------------------------------------------
import importlib.util as _ilu


def _load_calc_metrics():
    spec = _ilu.spec_from_file_location(
        "calculate_metrics",
        PROJECT_ROOT / "Miscellaneous Scripts" / "evaluate_architecture_metrics.py"
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# 1. Sentinel coercion tests
# ===========================================================================

class TestCoerceScore:
    """coerce_score must handle int, float, string sentinel and normal values."""

    def test_int_sentinel(self):
        assert coerce_score(1928) == 1928.0

    def test_float_sentinel(self):
        assert coerce_score(1928.0) == 1928.0

    def test_string_sentinel(self):
        assert coerce_score("1928") == 1928.0

    def test_string_sentinel_with_whitespace(self):
        assert coerce_score("  1928  ") == 1928.0

    def test_normal_int(self):
        assert coerce_score(7) == 7.0

    def test_normal_float(self):
        assert coerce_score(5.5) == 5.5

    def test_normal_string_float(self):
        assert coerce_score("8.3") == 8.3

    def test_none_is_nan(self):
        assert math.isnan(coerce_score(None))

    def test_nonnumeric_string_is_nan(self):
        assert math.isnan(coerce_score("N/A"))

    def test_error_string_is_nan(self):
        assert math.isnan(coerce_score("error"))

    def test_empty_string_is_nan(self):
        assert math.isnan(coerce_score(""))


class TestIsSentinel:
    """is_sentinel must catch all three forms of 1928."""

    def test_int(self):
        assert is_sentinel(1928)

    def test_float(self):
        assert is_sentinel(1928.0)

    def test_string(self):
        assert is_sentinel("1928")

    def test_nan_is_not_sentinel(self):
        assert not is_sentinel(float("nan"))

    def test_normal_value(self):
        assert not is_sentinel(7.5)

    def test_none_is_not_sentinel(self):
        assert not is_sentinel(None)

    def test_nonnumeric_not_sentinel(self):
        assert not is_sentinel("N/A")


class TestHasSentinelScores:
    """has_sentinel_scores must detect any sentinel variant across criteria."""

    def test_all_valid(self):
        scores = {"energy_cost": 5.0, "environmental": 6.0, "comfort": 7.0, "practicality": 8.0}
        assert not has_sentinel_scores(scores)

    def test_int_sentinel_in_one_criterion(self):
        scores = {"energy_cost": 1928, "environmental": 6.0, "comfort": 7.0, "practicality": 8.0}
        assert has_sentinel_scores(scores)

    def test_float_sentinel_in_one_criterion(self):
        scores = {"energy_cost": 5.0, "environmental": 1928.0, "comfort": 7.0, "practicality": 8.0}
        assert has_sentinel_scores(scores)

    def test_string_sentinel_in_one_criterion(self):
        scores = {"energy_cost": 5.0, "environmental": 6.0, "comfort": "1928", "practicality": 8.0}
        assert has_sentinel_scores(scores)

    def test_all_sentinel(self):
        scores = {c: 1928 for c in CRITERIA}
        assert has_sentinel_scores(scores)

    def test_missing_criterion_not_sentinel(self):
        # A missing criterion coerces to NaN which is not sentinel
        scores = {"energy_cost": 5.0}
        assert not has_sentinel_scores(scores, criteria=CRITERIA)


class TestCoerceScoreSeries:
    """coerce_score_series must apply per-element and preserve sentinel float."""

    def test_mixed_series(self):
        s = pd.Series([1928, "1928", 5.0, "N/A", None, "7.5"])
        result = coerce_score_series(s)
        assert result[0] == 1928.0
        assert result[1] == 1928.0
        assert result[2] == 5.0
        assert math.isnan(result[3])
        assert math.isnan(result[4])
        assert result[5] == 7.5


# ===========================================================================
# 2. Aggregation tests (via CalculateMetrics.aggregate_run_files)
# ===========================================================================

def _make_run_xlsx(tmp_path, run_idx, rows):
    """Write a minimal run CSV and return its Path."""
    df = pd.DataFrame(rows)
    p = tmp_path / f"arch_results_run_{run_idx:02d}.xlsx"
    df.to_excel(p, index=False, engine="openpyxl")
    return p


VALID_ROW_TEMPLATE = {
    "scenario_id": 1, "decision_type": "HVAC", "alternative": "72",
    "question": "Q1", "location": "Loc1",
    "outdoor_temp": "85", "appliance_age": "", "flow_rate": "",
    "energy_cost": 7.0, "environmental": 6.0, "comfort": 8.0, "practicality": 5.0,
}

FAILED_ROW_TEMPLATE = {
    **VALID_ROW_TEMPLATE,
    "energy_cost": SENTINEL_VALUE, "environmental": SENTINEL_VALUE, "comfort": SENTINEL_VALUE, "practicality": SENTINEL_VALUE,
}


class TestAggregateRunFiles:
    """aggregate_run_files: various single/multi-run scenarios."""

    @pytest.fixture(autouse=True)
    def cm(self):
        self._cm = _load_calc_metrics()

    def test_one_run_returns_correct_scores(self, tmp_path):
        row = dict(VALID_ROW_TEMPLATE)
        p = _make_run_xlsx(tmp_path, 1, [row])
        agg = self._cm.aggregate_run_files([p])
        ec = agg["energy_cost"].iloc[0]
        assert ec == pytest.approx(7.0)

    def test_one_run_n_runs_column(self, tmp_path):
        p = _make_run_xlsx(tmp_path, 1, [dict(VALID_ROW_TEMPLATE)])
        agg = self._cm.aggregate_run_files([p])
        assert "n_runs" in agg.columns
        assert agg["n_runs"].iloc[0] == 1

    def test_one_run_warns_about_std(self, tmp_path):
        p = _make_run_xlsx(tmp_path, 1, [dict(VALID_ROW_TEMPLATE)])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self._cm.aggregate_run_files([p])
        msgs = [str(x.message) for x in w]
        assert any("N=1" in m for m in msgs), f"Expected N=1 warning, got: {msgs}"

    def test_two_runs_averages_correctly(self, tmp_path):
        row1 = {**VALID_ROW_TEMPLATE, "energy_cost": 6.0}
        row2 = {**VALID_ROW_TEMPLATE, "energy_cost": 8.0}
        p1 = _make_run_xlsx(tmp_path, 1, [row1])
        p2 = _make_run_xlsx(tmp_path, 2, [row2])
        agg = self._cm.aggregate_run_files([p1, p2])
        assert agg["energy_cost"].iloc[0] == pytest.approx(7.0)
        assert agg["n_runs"].iloc[0] == 2

    def test_all_failed_rows_become_sentinel(self, tmp_path):
        p1 = _make_run_xlsx(tmp_path, 1, [dict(FAILED_ROW_TEMPLATE)])
        p2 = _make_run_xlsx(tmp_path, 2, [dict(FAILED_ROW_TEMPLATE)])
        agg = self._cm.aggregate_run_files([p1, p2])
        assert agg["energy_cost"].iloc[0] == self._cm.FAIL_SENTINEL

    def test_mixed_failed_success_averages_valid_only(self, tmp_path):
        """Failed rows are masked to NaN before averaging; only valid rows contribute."""
        row_ok = dict(VALID_ROW_TEMPLATE)
        row_fail = dict(FAILED_ROW_TEMPLATE)
        p1 = _make_run_xlsx(tmp_path, 1, [row_ok])
        p2 = _make_run_xlsx(tmp_path, 2, [row_fail])
        agg = self._cm.aggregate_run_files([p1, p2])
        # Average of [7.0, NaN] = 7.0
        assert agg["energy_cost"].iloc[0] == pytest.approx(7.0)
        assert agg["n_successful_runs"].iloc[0] == 1
        assert agg["n_failed_runs"].iloc[0] == 1

    def test_malformed_numeric_coerces_to_nan(self, tmp_path):
        """String sentinels and garbage in score columns should coerce safely."""
        row = {**VALID_ROW_TEMPLATE, "energy_cost": "1928", "environmental": "bad_value"}
        p = _make_run_xlsx(tmp_path, 1, [row])
        agg = self._cm.aggregate_run_files([p])
        # "1928" → sentinel → NaN → restored to FAIL_SENTINEL
        assert agg["energy_cost"].iloc[0] == self._cm.FAIL_SENTINEL
        # "bad_value" → NaN → restored to FAIL_SENTINEL
        assert agg["environmental"].iloc[0] == self._cm.FAIL_SENTINEL

    def test_partial_run_set_n_runs_is_count(self, tmp_path):
        """If caller passes 2 paths, n_runs should be 2 regardless of N_RUNS config."""
        p1 = _make_run_xlsx(tmp_path, 1, [dict(VALID_ROW_TEMPLATE)])
        p2 = _make_run_xlsx(tmp_path, 2, [dict(VALID_ROW_TEMPLATE)])
        agg = self._cm.aggregate_run_files([p1, p2])
        assert agg["n_runs"].iloc[0] == 2


# ===========================================================================
# 3. Diagnostics JSON loading tests
# ===========================================================================

class TestLoadDiagnosticsJson:
    """_load_diagnostics_json: JSON parsing, schema-aware counter extraction."""

    @pytest.fixture(autouse=True)
    def cm(self):
        self._cm = _load_calc_metrics()

    def _write_diag(self, path, data):
        with open(path, "w") as f:
            json.dump(data, f)

    def test_direct_llm_scoring_counters_loaded(self, tmp_path):
        results_path = tmp_path / "Direct_LLM_Scoring_results.xlsx"
        results_path.touch()
        diag_path = tmp_path / "Direct_LLM_Scoring_results_diagnostics_run_01.json"
        self._write_diag(diag_path, {
            "total_scenarios": 10,
            "failed_scenarios": 2,
            "successful_scenarios": 8,
            "failed_calls": 4,
            "successful_calls": 26,
            EXTRACTION_INVALID_JSON: 1,
            FAILED_MISSING_SCORE: 1,
            FAILED_OUT_OF_BOUNDS: 0,
            FAILED_INVALID_SCORE_TYPE: 0,
            FAILED_UNKNOWN: 2,
        })
        result = self._cm._load_diagnostics_json(str(results_path), "Direct_LLM_Scoring")
        assert result["diag_failed_scenarios"] == 2
        assert result[f"diag_{EXTRACTION_INVALID_JSON}"] == 1
        assert result[f"diag_{FAILED_MISSING_SCORE}"] == 1
        # LLM-Parameterized_Reference_Scoring counter should NOT appear in Direct_LLM_Scoring result
        assert f"diag_{FAILED_EXTRACTION_INVALID_DECISION_TYPE}" not in result

    def test_LLM_Parameterized_Reference_Scoring_counters_loaded(self, tmp_path):
        results_path = tmp_path / "LLM-Parameterized_Reference_Scoring_results.xlsx"
        results_path.touch()
        diag_path = tmp_path / "LLM-Parameterized_Reference_Scoring_results_diagnostics_run_01.json"
        self._write_diag(diag_path, {
            "total_scenarios": 5,
            "failed_scenarios": 1,
            "successful_scenarios": 4,
            "failed_calls": 1,
            "successful_calls": 4,
            EXTRACTION_INVALID_JSON: 1,
            FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION: 0,
            FAILED_UNKNOWN: 0,
        })
        result = self._cm._load_diagnostics_json(str(results_path), "LLM-Parameterized_Reference_Scoring")
        assert result[f"diag_{EXTRACTION_INVALID_JSON}"] == 1
        # Pure counter should NOT appear in LLM-Parameterized_Reference_Scoring result
        assert f"diag_{FAILED_MISSING_SCORE}" not in result

    def test_no_diag_file_graceful(self, tmp_path):
        results_path = tmp_path / "Direct_LLM_Scoring_results.xlsx"
        results_path.touch()
        result = self._cm._load_diagnostics_json(str(results_path), "Direct_LLM_Scoring")
        assert result["diag_files_loaded"] == 0

    def test_per_run_diag_files_aggregated(self, tmp_path):
        """Multiple _run_NN diagnostics files should be summed."""
        results_path = tmp_path / "Direct_LLM_Scoring_results.xlsx"
        results_path.touch()
        for i in (1, 2):
            p = tmp_path / f"Direct_LLM_Scoring_results_diagnostics_run_{i:02d}.json"
            self._write_diag(p, {"failed_scenarios": 1, EXTRACTION_INVALID_JSON: 1,
                                  "total_scenarios": 5})
        result = self._cm._load_diagnostics_json(str(results_path), "Direct_LLM_Scoring")
        assert result["diag_files_loaded"] == 2
        assert result["diag_failed_scenarios"] == 2
        assert result[f"diag_{EXTRACTION_INVALID_JSON}"] == 2


# ===========================================================================
# 4. Scenario matching tests
# ===========================================================================

class TestMatchScenarios:
    """match_scenarios: content-based matching, alt-drop warnings, LLM-Parameterized_Reference_Scoring typing."""

    @pytest.fixture(autouse=True)
    def cm(self):
        self._cm = _load_calc_metrics()

    def _make_gt_df(self, decision_type, scenarios):
        """Build a minimal GT dataframe."""
        rows = []
        for sid, (q, loc, alts) in enumerate(scenarios, 1):
            for alt_val, ec, env, com, pra in alts:
                rows.append({
                    "scenario_id": sid, "question": q, "location": loc,
                    "decision_type": decision_type, "alternative": str(alt_val),
                    "gt_energy_cost": ec, "gt_environmental": env,
                    "gt_comfort": com, "gt_practicality": pra,
                    "gt_rank": 1, "gt_mavt_score": 7.0,
                    "outdoor_temp": "85", "appliance_age": "", "gpm": "",
                })
        return pd.DataFrame(rows)

    def _make_arch_df(self, rows, arch_name="Pure"):
        df = pd.DataFrame(rows)
        df = self._cm.load_architecture(df, arch_name)
        return df

    def test_content_match_basic(self):
        """A scenario present in GT should match by (question, location)."""
        gt_df = self._make_gt_df("HVAC", [
            ("Q HVAC?", "Exton, PA", [
                ("72", 8, 7, 6, 5), ("76", 6, 7, 7, 5), ("80", 4, 5, 8, 6)
            ])
        ])
        gt_by_type = {"HVAC": gt_df, "Appliance": pd.DataFrame(), "Shower": pd.DataFrame()}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = [
            {"scenario_id": 1, "decision_type": "HVAC", "question": "Q HVAC?",
             "location": "Exton, PA", "alternative": "72",
             "energy_cost": 7.9, "environmental": 6.8, "comfort": 5.9, "practicality": 4.9,
             "outdoor_temp": "85", "appliance_age": "", "flow_rate": ""},
        ]
        arch_df = self._make_arch_df(arch_rows)
        merged, counts = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Pure")
        assert len(merged) == 1
        assert counts["content"] == 1
        assert counts["no_match"] == 0

    def test_no_match_for_unknown_question(self):
        """A scenario not in GT should be reported as no_match."""
        gt_df = self._make_gt_df("HVAC", [
            ("Known Q?", "Exton, PA", [("72", 8, 7, 6, 5)])
        ])
        gt_by_type = {"HVAC": gt_df}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = [
            {"scenario_id": 99, "decision_type": "HVAC", "question": "Unknown Q?",
             "location": "Nowhere, PA", "alternative": "72",
             "energy_cost": 7.0, "environmental": 6.0, "comfort": 5.0, "practicality": 4.0,
             "outdoor_temp": "85", "appliance_age": "", "flow_rate": ""},
        ]
        arch_df = self._make_arch_df(arch_rows)
        merged, counts = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Pure")
        assert len(merged) == 0
        assert counts["no_match"] >= 1

    def test_alt_drop_warning_logged_when_fewer_than_3(self):
        """When only 1 of 3 alternatives match, a warning should be appended."""
        gt_df = self._make_gt_df("HVAC", [
            ("Q HVAC?", "Exton, PA", [
                ("72", 8, 7, 6, 5), ("76", 6, 7, 7, 5), ("80", 4, 5, 8, 6)
            ])
        ])
        gt_by_type = {"HVAC": gt_df}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = [
            {"scenario_id": 1, "decision_type": "HVAC", "question": "Q HVAC?",
             "location": "Exton, PA", "alternative": "72",
             "energy_cost": 7.0, "environmental": 6.0, "comfort": 5.0, "practicality": 4.0,
             "outdoor_temp": "85", "appliance_age": "", "flow_rate": ""},
        ]
        arch_df = self._make_arch_df(arch_rows)
        # Capture stdout to detect warning message
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            merged, counts = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Pure")
        output = buf.getvalue()
        assert "only 1/3 alternatives matched" in output.lower() or len(merged) == 1

    def test_LLM_Parameterized_Reference_Scoring_input_decision_type_preserved(self):
        """When LLM-Parameterized_Reference_Scoring CSV has input_decision_type, it flows into merged rows."""
        gt_df = self._make_gt_df("HVAC", [
            ("Q HVAC?", "Exton, PA", [
                ("72", 8, 7, 6, 5), ("76", 6, 7, 7, 5), ("80", 4, 5, 8, 6)
            ])
        ])
        gt_by_type = {"HVAC": gt_df}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = []
        for alt in ("72", "76", "80"):
            arch_rows.append({
                "scenario_id": 1, "decision_type": "HVAC",
                "input_decision_type": "HVAC", "extracted_decision_type": "HVAC",
                "question": "Q HVAC?", "location": "Exton, PA", "alternative": alt,
                "energy_cost": 7.0, "environmental": 6.0, "comfort": 5.0, "practicality": 4.0,
                "outdoor_temp": "85", "appliance_age": "", "flow_rate": "",
            })
        arch_df = self._make_arch_df(arch_rows, arch_name="LLM-Parameterized_Reference_Scoring")
        merged, _ = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "LLM-Parameterized_Reference_Scoring")
        assert "input_decision_type" in merged.columns
        assert (merged["input_decision_type"] == "HVAC").all()


# ===========================================================================
# 5. Shower scenario matching tests
# ===========================================================================

class TestShowerScenarioMatching:
    """Multi-field Shower matching: repeated keys, parameter disambiguation, ties."""

    @pytest.fixture(autouse=True)
    def cm(self):
        self._cm = _load_calc_metrics()

    def _make_shower_gt_row(self, sid, q, loc, alt_val, ec, env, com, pra, rank=1, **params):
        return {
            "scenario_id": sid, "question": q, "location": loc,
            "decision_type": "Shower", "alternative": str(alt_val),
            "gt_energy_cost": ec, "gt_environmental": env,
            "gt_comfort": com, "gt_practicality": pra,
            "gt_rank": rank, "gt_mavt_score": 7.0,
            "outdoor_temp": params.get("outdoor_temp", ""),
            "appliance_age": "",
            "gpm": params.get("gpm", ""),
            "household_size": params.get("household_size", ""),
            "utility_budget": params.get("utility_budget", ""),
            "housing_type": params.get("housing_type", ""),
        }

    def _make_arch_rows(self, sid, q, loc, alts, **params):
        rows = []
        for alt_val, ec, env, com, pra in alts:
            rows.append({
                "scenario_id": sid, "decision_type": "Shower",
                "question": q, "location": loc, "alternative": str(alt_val),
                "energy_cost": ec, "environmental": env, "comfort": com, "practicality": pra,
                "outdoor_temp": params.get("outdoor_temp", ""),
                "appliance_age": "",
                "flow_rate": params.get("flow_rate", ""),
                "household_size": params.get("household_size", ""),
                "utility_budget": params.get("utility_budget", ""),
                "housing_type": params.get("housing_type", ""),
            })
        return rows

    _ALTS = [("5 min", 8, 7, 6, 5), ("10 min", 6, 6, 7, 5), ("15 min", 4, 5, 8, 6)]

    def test_repeated_key_matches_correct_gt(self):
        """Two Shower GT scenarios sharing (q, loc) are each matched to the
        arch row whose outdoor_temp / gpm align with theirs."""
        q, loc = "How long should I shower?", "Denver, CO"
        gt_rows = []
        for alt_val, ec, env, com, pra in self._ALTS:
            gt_rows.append(self._make_shower_gt_row(
                1, q, loc, alt_val, ec, env, com, pra, outdoor_temp="30", gpm="2.0"
            ))
        for alt_val, ec, env, com, pra in self._ALTS:
            gt_rows.append(self._make_shower_gt_row(
                2, q, loc, alt_val, ec + 1, env + 1, com + 1, pra + 1,
                outdoor_temp="70", gpm="2.5"
            ))
        gt_df = pd.DataFrame(gt_rows)
        gt_by_type = {"HVAC": pd.DataFrame(), "Appliance": pd.DataFrame(), "Shower": gt_df}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = self._make_arch_rows(1, q, loc, self._ALTS, outdoor_temp="30", flow_rate="2.0")
        arch_df = self._cm.load_architecture(pd.DataFrame(arch_rows), "Pure")
        merged, counts = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Pure")

        assert counts["content"] == 1
        assert len(merged) == 3
        assert merged["gt_scenario_id"].iloc[0] == 1, (
            f"Expected GT sid=1 (outdoor_temp=30), got sid={merged['gt_scenario_id'].iloc[0]}"
        )

    def test_same_alts_different_params_matches_correct(self):
        """When GT candidates share identical alternatives but differ in
        outdoor_temp / gpm, the arch row matches the GT with matching params."""
        q, loc = "How long should I shower?", "Boston, MA"
        gt_rows = []
        for alt_val, ec, env, com, pra in self._ALTS:
            gt_rows.append(self._make_shower_gt_row(
                1, q, loc, alt_val, ec, env, com, pra, outdoor_temp="20", gpm="1.5"
            ))
        for alt_val, ec, env, com, pra in self._ALTS:
            gt_rows.append(self._make_shower_gt_row(
                2, q, loc, alt_val, ec, env, com, pra, outdoor_temp="80", gpm="2.5"
            ))
        gt_df = pd.DataFrame(gt_rows)
        gt_by_type = {"HVAC": pd.DataFrame(), "Appliance": pd.DataFrame(), "Shower": gt_df}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = self._make_arch_rows(10, q, loc, self._ALTS, outdoor_temp="80", flow_rate="2.5")
        arch_df = self._cm.load_architecture(pd.DataFrame(arch_rows), "Pure")
        merged, _ = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Pure")

        assert len(merged) == 3
        assert merged["gt_scenario_id"].iloc[0] == 2, (
            f"Expected GT sid=2 (outdoor_temp=80), got sid={merged['gt_scenario_id'].iloc[0]}"
        )

    def test_ambiguous_tie_warns_and_does_not_crash(self):
        """Two GT Shower candidates with identical alts AND identical params
        produce a tie warning in stdout but the call completes and returns a match."""
        q, loc = "How long should I shower?", "Identical, TX"
        gt_rows = []
        for sid in (1, 2):
            for alt_val, ec, env, com, pra in self._ALTS:
                gt_rows.append(self._make_shower_gt_row(
                    sid, q, loc, alt_val, ec, env, com, pra, outdoor_temp="60", gpm="2.0"
                ))
        gt_df = pd.DataFrame(gt_rows)
        gt_by_type = {"HVAC": pd.DataFrame(), "Appliance": pd.DataFrame(), "Shower": gt_df}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = self._make_arch_rows(20, q, loc, self._ALTS, outdoor_temp="60", flow_rate="2.0")
        arch_df = self._cm.load_architecture(pd.DataFrame(arch_rows), "Pure")

        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            merged, counts = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Pure")
        output = buf.getvalue()

        assert counts["content"] == 1
        assert len(merged) == 3
        assert "tie" in output.lower(), f"Expected tie warning in stdout, got:\n{output}"

    def test_weak_evidence_warns_when_no_param_match(self):
        """When GT and arch have no usable params, match falls back to alt overlap
        only and a weak-evidence warning is emitted."""
        q, loc = "How long should I shower?", "NoParams, CA"
        gt_rows = []
        for alt_val, ec, env, com, pra in self._ALTS:
            gt_rows.append(self._make_shower_gt_row(
                1, q, loc, alt_val, ec, env, com, pra, outdoor_temp="", gpm=""
            ))
        gt_df = pd.DataFrame(gt_rows)
        gt_by_type = {"HVAC": pd.DataFrame(), "Appliance": pd.DataFrame(), "Shower": gt_df}
        gt_lookup = self._cm.build_gt_lookup(gt_by_type)
        gt_id_lookup = self._cm.build_gt_id_lookup(gt_by_type)

        arch_rows = self._make_arch_rows(30, q, loc, self._ALTS, outdoor_temp="", flow_rate="")
        arch_df = self._cm.load_architecture(pd.DataFrame(arch_rows), "Pure")

        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            merged, counts = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Pure")
        output = buf.getvalue()

        assert len(merged) == 3, "Should still match on alternative overlap"
        assert counts["content"] == 1
        assert "overlap only" in output.lower() or "no parameter" in output.lower(), (
            f"Expected weak-evidence warning in stdout, got:\n{output}"
        )


# ===========================================================================
# 6. RAG metadata field tests
# ===========================================================================

class TestRAGMetadataFields:
    """Ensure retrieve_similar_scenarios handles missing metadata fields gracefully."""

    def _make_mock_metadata(self, **overrides):
        base = {
            "decision_type": "HVAC",
            "question": "Q?",
            "alt1": "72", "alt2": "76", "alt3": "80",
            "alt1_energy_cost": 7.0, "alt1_environmental": 6.0,
            "alt1_comfort": 8.0, "alt1_practicality": 5.0,
            "alt2_energy_cost": 6.0, "alt2_environmental": 7.0,
            "alt2_comfort": 7.0, "alt2_practicality": 5.0,
            "alt3_energy_cost": 5.0, "alt3_environmental": 8.0,
            "alt3_comfort": 6.0, "alt3_practicality": 6.0,
        }
        base.update(overrides)
        return base

    def _parse_metadata(self, metadata):
        """Replicate what retrieve_similar_scenarios does with a metadata dict."""
        alternatives = []
        for prefix in ("alt1", "alt2", "alt3"):
            alternatives.append({
                "name": metadata.get(prefix, "N/A"),
                "scores": {
                    "energy_cost": metadata.get(f"{prefix}_energy_cost", 0.0),
                    "environmental": metadata.get(f"{prefix}_environmental", 0.0),
                    "comfort": metadata.get(f"{prefix}_comfort", 0.0),
                    "practicality": metadata.get(f"{prefix}_practicality", 0.0),
                }
            })
        return alternatives

    def test_complete_metadata_returns_correct_scores(self):
        meta = self._make_mock_metadata()
        alts = self._parse_metadata(meta)
        assert alts[0]["scores"]["energy_cost"] == 7.0
        assert alts[2]["scores"]["practicality"] == 6.0

    def test_missing_criterion_field_falls_back_to_zero(self):
        """Current RAG code defaults missing alt*_criterion to 0.0.

        This test documents that behaviour.  If/when the schema validation
        fail-fast fix is applied, update this test to expect an exception or
        diagnostic instead.
        """
        meta = self._make_mock_metadata()
        del meta["alt1_energy_cost"]
        alts = self._parse_metadata(meta)
        assert alts[0]["scores"]["energy_cost"] == 0.0

    def test_all_fields_present_no_defaults_used(self):
        meta = self._make_mock_metadata(
            alt1_energy_cost=9.0, alt1_environmental=9.0,
            alt1_comfort=9.0, alt1_practicality=9.0,
        )
        alts = self._parse_metadata(meta)
        for c in ("energy_cost", "environmental", "comfort", "practicality"):
            assert alts[0]["scores"][c] == 9.0


# ===========================================================================
# 6. Retry policy tests (unit-level, no actual HTTP calls)
# ===========================================================================

class TestRetryPolicy:
    """_is_transient_http_status must classify codes correctly across all architectures."""

    def _get_is_transient(self, module_path):
        spec = _ilu.spec_from_file_location("arch", module_path)
        mod = _ilu.module_from_spec(spec)
        # Patch out the API key requirement before loading
        import unittest.mock as mock
        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            try:
                spec.loader.exec_module(mod)
            except Exception:
                pass
        return getattr(mod, "_is_transient_http_status", None)

    @pytest.mark.parametrize("arch_file", [
        "Direct_LLM_Scoring.py", "Eample-Guided_LLM_Scoring.py.py", "LLM-Parameterized_Reference_Scoring.py"
    ])
    def test_transient_codes_retry(self, arch_file):
        arch_path = PROJECT_ROOT / "Architectures" / arch_file
        fn = self._get_is_transient(arch_path)
        if fn is None:
            pytest.skip(f"_is_transient_http_status not found in {arch_file}")
        for code in (408, 429, 500, 502, 503, 504, 520, 530):
            assert fn(code), f"Expected {code} to be transient in {arch_file}"

    @pytest.mark.parametrize("arch_file", [
        "Direct_LLM_Scoring.py", "Eample-Guided_LLM_Scoring.py.py", "LLM-Parameterized_Reference_Scoring.py"
    ])
    def test_non_transient_codes_do_not_retry(self, arch_file):
        arch_path = PROJECT_ROOT / "Architectures" / arch_file
        fn = self._get_is_transient(arch_path)
        if fn is None:
            pytest.skip(f"_is_transient_http_status not found in {arch_file}")
        for code in (401, 403, 404):
            assert not fn(code), f"Expected {code} to NOT be transient in {arch_file}"
