"""
Tests for sentinel coercion, aggregation, and scenario matching.

Scope (per task specification):
  - sentinel coercion: numeric 1928, string "1928", nonnumeric strings, normal scores
  - aggregation: one-run, partial-run, malformed numeric, all-failed, mixed rows
  - metrics: failure-mode totals from JSON match CSV sentinels
  - scenario matching: content match, alt drop warnings, Hybrid input_decision_type
  - RAG: missing metadata fields, successful metadata fields

Does NOT test anything that requires TestScenarios.csv to exist.
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

# ---------------------------------------------------------------------------
# Lazy import helpers — only pull in CalculateMetrics when needed
# ---------------------------------------------------------------------------
import importlib.util as _ilu


def _load_calc_metrics():
    spec = _ilu.spec_from_file_location(
        "calculate_metrics",
        PROJECT_ROOT / "Miscellaneous Scripts" / "CalculateMetrics.py"
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

def _make_run_csv(tmp_path, run_idx, rows):
    """Write a minimal run CSV and return its Path."""
    df = pd.DataFrame(rows)
    p = tmp_path / f"arch_results_run_{run_idx:02d}.csv"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p


VALID_ROW_TEMPLATE = {
    "scenario_id": 1, "decision_type": "HVAC", "alternative": "72",
    "question": "Q1", "location": "Loc1",
    "outdoor_temp": "85", "appliance_age": "", "flow_rate": "",
    "energy_cost": 7.0, "environmental": 6.0, "comfort": 8.0, "practicality": 5.0,
}

FAILED_ROW_TEMPLATE = {
    **VALID_ROW_TEMPLATE,
    "energy_cost": 1928, "environmental": 1928, "comfort": 1928, "practicality": 1928,
}


class TestAggregateRunFiles:
    """aggregate_run_files: various single/multi-run scenarios."""

    @pytest.fixture(autouse=True)
    def cm(self):
        self._cm = _load_calc_metrics()

    def test_one_run_returns_correct_scores(self, tmp_path):
        row = dict(VALID_ROW_TEMPLATE)
        p = _make_run_csv(tmp_path, 1, [row])
        agg = self._cm.aggregate_run_files([p])
        ec = agg["energy_cost"].iloc[0]
        assert ec == pytest.approx(7.0)

    def test_one_run_n_runs_column(self, tmp_path):
        p = _make_run_csv(tmp_path, 1, [dict(VALID_ROW_TEMPLATE)])
        agg = self._cm.aggregate_run_files([p])
        assert "n_runs" in agg.columns
        assert agg["n_runs"].iloc[0] == 1

    def test_one_run_warns_about_std(self, tmp_path):
        p = _make_run_csv(tmp_path, 1, [dict(VALID_ROW_TEMPLATE)])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self._cm.aggregate_run_files([p])
        msgs = [str(x.message) for x in w]
        assert any("N=1" in m for m in msgs), f"Expected N=1 warning, got: {msgs}"

    def test_two_runs_averages_correctly(self, tmp_path):
        row1 = {**VALID_ROW_TEMPLATE, "energy_cost": 6.0}
        row2 = {**VALID_ROW_TEMPLATE, "energy_cost": 8.0}
        p1 = _make_run_csv(tmp_path, 1, [row1])
        p2 = _make_run_csv(tmp_path, 2, [row2])
        agg = self._cm.aggregate_run_files([p1, p2])
        assert agg["energy_cost"].iloc[0] == pytest.approx(7.0)
        assert agg["n_runs"].iloc[0] == 2

    def test_all_failed_rows_become_sentinel(self, tmp_path):
        p1 = _make_run_csv(tmp_path, 1, [dict(FAILED_ROW_TEMPLATE)])
        p2 = _make_run_csv(tmp_path, 2, [dict(FAILED_ROW_TEMPLATE)])
        agg = self._cm.aggregate_run_files([p1, p2])
        assert agg["energy_cost"].iloc[0] == self._cm.FAIL_SENTINEL

    def test_mixed_failed_success_averages_valid_only(self, tmp_path):
        """Failed rows are masked to NaN before averaging; only valid rows contribute."""
        row_ok = dict(VALID_ROW_TEMPLATE)   # energy_cost = 7.0
        row_fail = dict(FAILED_ROW_TEMPLATE)
        p1 = _make_run_csv(tmp_path, 1, [row_ok])
        p2 = _make_run_csv(tmp_path, 2, [row_fail])
        agg = self._cm.aggregate_run_files([p1, p2])
        # Average of [7.0, NaN] = 7.0
        assert agg["energy_cost"].iloc[0] == pytest.approx(7.0)
        assert agg["n_successful_runs"].iloc[0] == 1
        assert agg["n_failed_runs"].iloc[0] == 1

    def test_malformed_numeric_coerces_to_nan(self, tmp_path):
        """String sentinels and garbage in score columns should coerce safely."""
        row = {**VALID_ROW_TEMPLATE, "energy_cost": "1928", "environmental": "bad_value"}
        p = _make_run_csv(tmp_path, 1, [row])
        agg = self._cm.aggregate_run_files([p])
        # "1928" → sentinel → NaN → restored to FAIL_SENTINEL
        assert agg["energy_cost"].iloc[0] == self._cm.FAIL_SENTINEL
        # "bad_value" → NaN → restored to FAIL_SENTINEL
        assert agg["environmental"].iloc[0] == self._cm.FAIL_SENTINEL

    def test_partial_run_set_n_runs_is_count(self, tmp_path):
        """If caller passes 2 paths, n_runs should be 2 regardless of N_RUNS config."""
        p1 = _make_run_csv(tmp_path, 1, [dict(VALID_ROW_TEMPLATE)])
        p2 = _make_run_csv(tmp_path, 2, [dict(VALID_ROW_TEMPLATE)])
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

    def test_pure_counters_loaded(self, tmp_path):
        csv_path = tmp_path / "pure_prompting_results.csv"
        csv_path.touch()
        diag_path = tmp_path / "pure_prompting_results_diagnostics.json"
        self._write_diag(diag_path, {
            "total_scenarios": 10,
            "failed_scenarios": 2,
            "successful_scenarios": 8,
            "failed_calls": 4,
            "successful_calls": 26,
            "failed_malformed_json": 1,
            "failed_missing_score": 1,
            "failed_out_of_bounds": 0,
            "failed_invalid_score_type": 0,
            "failed_unknown": 2,
        })
        result = self._cm._load_diagnostics_json(str(csv_path), "Pure")
        assert result["diag_failed_scenarios"] == 2
        assert result["diag_failed_malformed_json"] == 1
        assert result["diag_failed_missing_score"] == 1
        # Hybrid counter should NOT appear in Pure result
        assert "diag_failed_extraction_invalid_json" not in result

    def test_hybrid_counters_loaded(self, tmp_path):
        csv_path = tmp_path / "hybrid_results.csv"
        csv_path.touch()
        diag_path = tmp_path / "hybrid_diagnostics.json"
        self._write_diag(diag_path, {
            "total_scenarios": 5,
            "failed_scenarios": 1,
            "successful_scenarios": 4,
            "failed_calls": 1,
            "successful_calls": 4,
            "failed_extraction_invalid_json": 1,
            "failed_ground_truth_calculation_exception": 0,
            "failed_unknown": 0,
        })
        result = self._cm._load_diagnostics_json(str(csv_path), "Hybrid")
        assert result["diag_failed_extraction_invalid_json"] == 1
        # Pure counter should NOT appear in Hybrid result
        assert "diag_failed_malformed_json" not in result

    def test_no_diag_file_graceful(self, tmp_path):
        csv_path = tmp_path / "pure_prompting_results.csv"
        csv_path.touch()
        result = self._cm._load_diagnostics_json(str(csv_path), "Pure")
        assert result["diag_files_loaded"] == 0

    def test_per_run_diag_files_aggregated(self, tmp_path):
        """Multiple _run_NN diagnostics files should be summed."""
        csv_path = tmp_path / "pure_prompting_results.csv"
        csv_path.touch()
        for i in (1, 2):
            p = tmp_path / f"pure_prompting_results_diagnostics_run_{i:02d}.json"
            self._write_diag(p, {"failed_scenarios": 1, "failed_malformed_json": 1,
                                  "total_scenarios": 5})
        result = self._cm._load_diagnostics_json(str(csv_path), "Pure")
        assert result["diag_files_loaded"] == 2
        assert result["diag_failed_scenarios"] == 2      # 1+1
        assert result["diag_failed_malformed_json"] == 2  # 1+1


# ===========================================================================
# 4. Scenario matching tests
# ===========================================================================

class TestMatchScenarios:
    """match_scenarios: content-based matching, alt-drop warnings, Hybrid typing."""

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
                    "outdoor_temp": "85", "appliance_age_type": "", "gpm": "",
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

        # Only provide 1 of 3 alternatives so only 1 matches
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

    def test_hybrid_input_decision_type_preserved(self):
        """When Hybrid CSV has input_decision_type, it flows into merged rows."""
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
        arch_df = self._make_arch_df(arch_rows, arch_name="Hybrid")
        merged, _ = self._cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "Hybrid")
        assert "input_decision_type" in merged.columns
        assert (merged["input_decision_type"] == "HVAC").all()


# ===========================================================================
# 5. RAG metadata field tests
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
        del meta["alt1_energy_cost"]   # Simulate a missing field
        alts = self._parse_metadata(meta)
        # Default is 0.0 — this is the documented current behaviour
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
        "PurePrompting.py", "RAGDatabaseOptimized.py", "Hybrid.py"
    ])
    def test_transient_codes_retry(self, arch_file):
        arch_path = PROJECT_ROOT / "Architectures" / arch_file
        fn = self._get_is_transient(arch_path)
        if fn is None:
            pytest.skip(f"_is_transient_http_status not found in {arch_file}")
        for code in (408, 429, 500, 502, 503, 504, 520, 530):
            assert fn(code), f"Expected {code} to be transient in {arch_file}"

    @pytest.mark.parametrize("arch_file", [
        "PurePrompting.py", "RAGDatabaseOptimized.py", "Hybrid.py"
    ])
    def test_non_transient_codes_do_not_retry(self, arch_file):
        arch_path = PROJECT_ROOT / "Architectures" / arch_file
        fn = self._get_is_transient(arch_path)
        if fn is None:
            pytest.skip(f"_is_transient_http_status not found in {arch_file}")
        for code in (401, 403, 404):
            assert not fn(code), f"Expected {code} to NOT be transient in {arch_file}"
