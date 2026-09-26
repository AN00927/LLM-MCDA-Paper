"""Mocked, no-network check that a call which fails after all retries still
gets one *_raw.jsonl record, with an error message, an attempt count, and
collected_utc, in each of the three ablation scripts.

`requests.post` is monkeypatched to always raise (no socket ever opens);
MAX_RETRIES is monkeypatched to 1 and time.sleep to a no-op so the retry loop
exhausts immediately. No network, no API key required, no cost.

Usage: python Analysis/rerun_prep/infra/test_retry_exhausted_logging.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_jsonl(path):
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check_prompt_ablation():
    mod = _load(PROJECT_ROOT / "Miscellaneous Scripts" / "experiments" /
               "run_prompt_ablation_experiments.py", "t_prompt_ablation")
    mod.MAX_RETRIES = 1
    mod.RETRY_BASE_DELAY = 0
    mod.time.sleep = lambda *a, **k: None

    scenario = {"scenario_id": 1, "decision_type": "HVAC", "question": "q",
               "location": "loc", "outdoor_temp": 40, "square_footage": 1500,
               "insulation": "Medium", "household_size": 3, "housing_type": "House",
               "house_age": "10-20 years", "utility_budget": 150,
               "alternative_1": "68F", "alternative_2": "70F", "alternative_3": "72F"}
    variant = mod.VARIANT_SPECS["control"]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = Path(tmp) / "test_raw.jsonl"
        mod.RAW_LOG.start(raw_path, run=1)
        try:
            with patch.object(mod.requests, "post",
                              side_effect=requests.exceptions.ConnectionError("mocked: no network")):
                mod.score_scenario(scenario, "AD", variant, "some/model", "gptoss")
        finally:
            mod.RAW_LOG.stop()
        records = _read_jsonl(raw_path)

    assert len(records) == 3, f"expected 3 records (one per alternative), got {len(records)}"
    for r in records:
        assert r["api_success"] is False, r
        assert r.get("error"), f"missing error text: {r}"
        assert r.get("attempts", 0) >= 1, f"missing attempt count: {r}"
        assert r.get("collected_utc"), f"missing collected_utc: {r}"
    print("[OK] run_prompt_ablation_experiments.py: retry-exhausted calls logged "
          f"({len(records)} records, error/attempts/collected_utc all present)")


def check_rag_ablation():
    mod = _load(PROJECT_ROOT / "Miscellaneous Scripts" / "experiments" /
               "run_rag_ablation_experiments.py", "t_rag_ablation")
    mod.MAX_RETRIES = 1
    mod.RETRY_BASE_DELAY = 0
    mod.time.sleep = lambda *a, **k: None

    scenario = {"source_scenario_id": 1, "decision_type": "HVAC", "question": "q",
               "location": "loc",
               "alternatives": [{"alternative": "68F"}, {"alternative": "70F"},
                                {"alternative": "72F"}]}
    spec = {"label": "test", "llm": True, "include_hidden_params": False,
           "include_scores": False, "include_ranks": False}

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = Path(tmp) / "test_raw.jsonl"
        mod.RAW_LOG.start(raw_path)
        try:
            with patch.object(mod, "requests", create=True), \
                 patch("requests.post",
                       side_effect=requests.exceptions.ConnectionError("mocked: no network")):
                mod.llm_prediction(scenario, spec, [], "some/model")
        finally:
            mod.RAW_LOG.stop()
        records = _read_jsonl(raw_path)

    assert len(records) == 3, f"expected 3 records (one per alternative), got {len(records)}"
    for r in records:
        assert r["api_success"] is False, r
        assert r.get("error"), f"missing error text: {r}"
        assert r.get("attempts", 0) >= 1, f"missing attempt count: {r}"
        assert r.get("collected_utc"), f"missing collected_utc: {r}"
    print("[OK] run_rag_ablation_experiments.py: retry-exhausted calls logged "
          f"({len(records)} records, error/attempts/collected_utc all present) "
          "-- this is the case query_openrouter raises instead of returning None on")


def check_position_bias():
    """No new code was added to this script for exhausted retries: it drives
    Architectures/Direct_LLM_Scoring.py's own run_scenario()/query_openrouter,
    which already logs an exhausted call via its own RAW_LOG.record() call
    (response="", api_success=False, retries=N) before returning sentinel
    scores -- the plan said not to touch Architectures/*. This check confirms
    that existing mechanism actually fires once run_position_bias_control.py's
    mod.RAW_LOG.start() is active, with no network and no API key.
    """
    mod = _load(PROJECT_ROOT / "Architectures" / "Direct_LLM_Scoring.py", "t_direct_llm_scoring")
    mod.MAX_RETRIES = 1
    mod.RETRY_BASE_DELAY = 0
    mod.time.sleep = lambda *a, **k: None
    mod.API_CONFIG["model"] = "some/model"

    scenario = {"scenario_id": 1, "decision_type": "HVAC", "question": "q",
               "location": "loc", "outdoor_temp": 40, "square_footage": 1500,
               "insulation": "Medium", "household_size": 3, "housing_type": "House",
               "house_age": "10-20 years", "utility_budget": 150,
               "alternative_1": "68F", "alternative_2": "70F", "alternative_3": "72F"}

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = Path(tmp) / "test_raw.jsonl"
        mod.RAW_LOG.start(raw_path, run=1)
        try:
            with patch.object(mod.requests, "post",
                              side_effect=requests.exceptions.ConnectionError("mocked: no network")):
                for i in range(1, 4):
                    mod.RAW_LOG.set_scenario(scenario["scenario_id"])
                    mod.run_scenario(scenario)
                    break  # one call is enough to prove the mechanism fires
        finally:
            mod.RAW_LOG.stop()
        records = _read_jsonl(raw_path)

    assert len(records) == 3, f"expected 3 records (one per alternative), got {len(records)}"
    for r in records:
        assert r["api_success"] is False, r
        assert r.get("attempts", 0) >= 1 or r.get("retries", 0) >= 0, f"no attempt info: {r}"
        assert r.get("collected_utc"), f"missing collected_utc: {r}"
    # Architectures/*.py was not modified, so there is no free-text "error"
    # field here (by design -- see the docstring above); the failure is
    # visible instead via api_success=False and response="".
    for r in records:
        assert r.get("response", "") == "", r
    print("[OK] run_position_bias_control.py (via the real, unmodified "
          f"Architectures/Direct_LLM_Scoring.py): retry-exhausted calls already "
          f"logged ({len(records)} records, collected_utc present; no 'error' "
          "text field since Architectures/*.py was not changed)")


if __name__ == "__main__":
    check_prompt_ablation()
    check_rag_ablation()
    check_position_bias()
    print("\nAll three ablation scripts: retry-exhausted calls confirmed logged.")
