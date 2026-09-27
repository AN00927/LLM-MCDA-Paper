"""Mocked tests for the installed pre-rerun architecture patch.

Ported from Analysis/rerun_prep/arch_new/tests/test_arch_patch.py; MODS are the
installed Architectures/*.py. "live" / "prepatch" below means the code the
patch replaced, loaded read-only from git (see arch_patch_harness.py).

Run under every model key (MODEL_KEY is read once, at import of model_config):
    for MK in gptoss qwen deepseek gemini; do
      MODEL_KEY=$MK OPENBLAS_NUM_THREADS=1 env -u OPENROUTER_API_KEY \\
        .venv/Scripts/python.exe -m pytest tests/test_arch_patch.py -q
    done
No network: see arch_patch_harness.py.
"""
import importlib.util
import itertools
import json
import random
from datetime import datetime
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest
import requests

import arch_patch_harness as H
import sentinel_utils as SU
from model_config import (CRITERION_WEIGHTS, EXTRACTION_INVALID_JSON, FAILED_API_EXHAUSTED,
                          FAILED_EXTRACTION_NON_JSON_WRAPPER, FAILED_UNKNOWN, MAX_RETRIES,
                          TIE_BREAK_PRIORITY)

ARCHS = ["AD", "AE", "AH"]
DTYPES = ["HVAC", "Appliance", "Shower"]
CRIT = ["energy_cost", "environmental", "comfort", "practicality"]

MODS = {k: H.load_patched(k) for k in ARCHS}
SCN = H.get_test_scenarios()
AH_HIST = H.historical_ah_responses()

COMMON_FIELDS = [
    "collected_utc", "run", "scenario_id", "architecture", "decision_type", "model",
    "system_prompt_sha256", "prompt", "prompt_sha256", "response", "prompt_tokens",
    "completion_tokens", "latency_ms", "api_success", "request_params", "attempts", "retries",
    "attempt_errors", "response_id", "response_model", "provider", "system_fingerprint",
    "finish_reason", "native_finish_reason", "usage", "reasoning", "body_error", "truncated",
    "reasoning_tokens", "cost", "failure_types",
]
EXTRA_FIELDS = {
    "AD": ["alternative", "scores", "scores_valid"],
    "AE": ["alternative", "scores", "scores_valid", "rag_top_k", "rag_exemplar_ids",
           "rag_exemplar_distances"],
    "AH": ["alternatives", "parsed", "extraction_success", "extraction_error"],
}
N_CALLS = {"AD": 3, "AE": 3, "AH": 1}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    SU._consecutive_api_failures = 0
    MODS["AE"]._consecutive_retrieval_failures = 0
    for m in MODS.values():
        m.RAW_LOG.stop()
    MODS["AE"].chroma_collection = H.FakeCollection()
    MODS["AE"].embedding_model = H.FakeEmbedder()
    yield sleeps
    for m in MODS.values():
        m.RAW_LOG.stop()


def good_content(key, dt):
    if key == "AH":
        return AH_HIST[SCN[dt][0]]
    return H.SCORES_JSON


def scenario_for(key, dt):
    sid, sc = SCN[dt]
    sc = dict(sc)
    if key == "AD":
        sc["scenario_id"] = sid
    return sid, sc


def run_one(key, dt, script, tmp_path):
    """Drive the real run_scenario for one scenario with requests.post mocked.
    Returns (result, poster, raw records)."""
    mod = MODS[key]
    sid, sc = scenario_for(key, dt)
    raw = tmp_path / f"{key}_{dt}_results_run_01_raw.jsonl"
    mod.RAW_LOG.start(raw)
    mod.RAW_LOG.set_scenario(sid)
    poster = H.Poster(script)
    try:
        with mock.patch("requests.post", poster):
            result = mod.run_scenario(sc)
    finally:
        mod.RAW_LOG.stop()
    recs = H.read_jsonl(raw) if raw.exists() else []
    return result, poster, recs


def alt_scores(key, result):
    """Per-alternative criterion dicts for any architecture's result."""
    out = []
    for a in result["alternatives_scores"]:
        d = a.get("scores") if isinstance(a.get("scores"), dict) else a
        out.append({c: d.get(c) for c in CRIT})
    return out


def failure_codes(key, result, recs):
    if key == "AH":
        return [result.get("failure_types")]
    return [r["failure_types"] for r in recs]


def is_failed(key, result):
    """True iff every alternative is a sentinel / None (never a real score)."""
    if key == "AH":
        return bool(result["scenario_failed"]) and all(
            SU.is_sentinel(v) for a in alt_scores(key, result) for v in a.values())
    return all(v is None or SU.is_sentinel(v) for a in alt_scores(key, result) for v in a.values())


def check_record_schema(key, recs, sid):
    assert len(recs) == N_CALLS[key], (key, len(recs))
    for r in recs:
        missing = [f for f in COMMON_FIELDS + EXTRA_FIELDS[key] if f not in r]
        assert not missing, (key, missing)
        assert r["run"] == 1 and r["scenario_id"] == sid
        assert r["architecture"] == MODS[key].ARCHITECTURE
        assert datetime.fromisoformat(r["collected_utc"]).utcoffset().total_seconds() == 0
        if key in ("AD", "AE"):
            assert len(r["system_prompt_sha256"]) == 64
        rp = r["request_params"]
        if rp is not None:
            assert "messages" not in rp
            assert rp["max_tokens"] == SU.MAX_OUTPUT_TOKENS
            assert rp["provider"] == SU.provider_prefs_for_model(MODS[key].API_CONFIG["model"])
            assert rp["temperature"] == MODS[key].API_CONFIG["temperature"]
            assert "reasoning" in rp


# ---------------------------------------------------------------------------
# 1. The ten mocked response kinds, every architecture x decision type
# ---------------------------------------------------------------------------

CASES = ["success", "null_content", "empty_choices_then_ok", "error_body_then_ok",
         "empty_choices_always", "truncated", "truncated_valid_json", "429_then_ok",
         "timeout_then_ok", "timeout_always", "400"]


def script_for(case, key, dt):
    good = H.ok(good_content(key, dt))
    return {
        "success": [good],
        "null_content": [H.ok(None, reasoning="Let me think about the setpoint...")],
        "empty_choices_then_ok": [H.FakeResponse(200, {"id": "gen-empty", "choices": []}), good],
        "error_body_then_ok": [H.FakeResponse(200, {"error": {"code": 502, "message": "Provider returned error"}}), good],
        "empty_choices_always": [H.FakeResponse(200, {"id": "gen-empty", "choices": []})],
        "truncated": [H.ok('{"energy_cost": 0.6, "environ', finish="length", native="MAX_TOKENS")],
        "truncated_valid_json": [H.ok(good_content(key, dt), finish="length", native="MAX_TOKENS")],
        "429_then_ok": [H.FakeResponse(429, {"error": {"code": 429, "message": "rate limited"}}), good],
        "timeout_then_ok": [requests.exceptions.Timeout("read timed out"), good],
        "timeout_always": [requests.exceptions.Timeout("read timed out")],
        "400": [H.FakeResponse(400, {"error": {"code": 400, "message": "bad parameter"}})],
    }[case]


EXPECTED_FAILURE = {
    "null_content": {"AD": FAILED_UNKNOWN, "AE": EXTRACTION_INVALID_JSON, "AH": FAILED_EXTRACTION_NON_JSON_WRAPPER},
    "empty_choices_always": FAILED_API_EXHAUSTED,
    "truncated": SU.FAILED_TRUNCATED,
    "truncated_valid_json": SU.FAILED_TRUNCATED,
    "timeout_always": FAILED_API_EXHAUSTED,
    "400": SU.FAILED_API_BAD_REQUEST,
}
# POSTs per logical call
EXPECTED_POSTS = {
    "success": 1, "null_content": 1, "truncated": 1, "truncated_valid_json": 1,
    "empty_choices_always": MAX_RETRIES, "timeout_always": MAX_RETRIES, "400": 2,
}


@pytest.mark.parametrize("dt", DTYPES)
@pytest.mark.parametrize("key", ARCHS)
@pytest.mark.parametrize("case", CASES)
def test_response_kinds(case, key, dt, tmp_path, _env):
    sid = SCN[dt][0]
    result, poster, recs = run_one(key, dt, script_for(case, key, dt), tmp_path)
    check_record_schema(key, recs, sid)
    n = N_CALLS[key]

    # payload sent on every POST
    for c in poster.calls:
        p = c["payload"]
        assert p["max_tokens"] == SU.MAX_OUTPUT_TOKENS
        assert p["provider"] == SU.provider_prefs_for_model(MODS[key].API_CONFIG["model"])
        assert "usage" not in p
        assert p["model"] == MODS[key].API_CONFIG["model"]

    if case in EXPECTED_POSTS:
        assert len(poster.calls) == EXPECTED_POSTS[case] * n, (case, len(poster.calls))
    else:  # one failed attempt, then success, on the first call only
        assert len(poster.calls) == n + 1

    if case in EXPECTED_FAILURE:
        exp = EXPECTED_FAILURE[case]
        exp = exp[key] if isinstance(exp, dict) else exp
        assert is_failed(key, result), (case, key, alt_scores(key, result))
        for fc in failure_codes(key, result, recs):
            assert fc == [exp], (case, key, fc)
        for r in recs:
            assert r["failure_types"] == [exp]
            assert r["scores_valid"] is False if key != "AH" else r["extraction_success"] is False
    else:
        assert not is_failed(key, result)
        for a in alt_scores(key, result):
            assert not any(SU.is_sentinel(v) for v in a.values())
        for r in recs:
            assert r["failure_types"] == []
            assert r["api_success"] is True
            assert r["response_id"] == "gen-abc123" and r["provider"] == "Google AI Studio"
            assert r["response_model"] == H.MODEL_RETURNED
            assert r["usage"]["cost"] == H.COST and r["cost"] == H.COST
            assert r["reasoning_tokens"] == 7
            assert r["finish_reason"] == "stop"

    # case-specific details
    first = recs[0]
    if case == "null_content":
        assert all(r["response"] == "" and r["reasoning"].startswith("Let me think") for r in recs)
        assert all(r["api_success"] is True for r in recs)
    if case in ("truncated", "truncated_valid_json"):
        assert all(r["truncated"] is True and r["finish_reason"] == "length" for r in recs)
        assert all(r["response"] for r in recs)  # partial text kept
    if case in ("empty_choices_then_ok", "error_body_then_ok"):
        assert first["attempts"] == 2 and first["retries"] == 1
        assert first["attempt_errors"][0]["kind"] == "error_in_200_body"
        assert first["attempt_errors"][0]["status"] == 200
        assert len(_env) == 1
    if case == "429_then_ok":
        assert first["attempts"] == 2 and first["attempt_errors"][0]["status"] == 429
        assert "rate limited" in first["attempt_errors"][0]["detail"]
    if case == "timeout_then_ok":
        assert first["attempt_errors"][0]["kind"] == "Timeout"
    if case in ("empty_choices_always", "timeout_always"):
        for r in recs:
            assert len(r["attempt_errors"]) == MAX_RETRIES and r["api_success"] is False
            assert [e["attempt"] for e in r["attempt_errors"]] == list(range(1, MAX_RETRIES + 1))
            assert all(datetime.fromisoformat(e["utc"]) for e in r["attempt_errors"])
    if case == "400":
        for r in recs:
            assert [e["status"] for e in r["attempt_errors"]] == [400, 400]
            assert "bad parameter" in r["attempt_errors"][0]["detail"]

    # diagnostics sums
    if key == "AH":
        ed = result["extraction_diagnostics"]
        if case == "success":
            assert ed["cost"] == H.COST and ed["reasoning_tokens"] == 7
    else:
        d = result["diagnostics"]
        expected_cost_calls = 0 if case in ("empty_choices_always", "timeout_always", "400") else n
        assert d["calls_with_cost"] == expected_cost_calls
        assert d["total_cost_usd"] == pytest.approx(H.COST * expected_cost_calls)
        assert d["total_tokens_reasoning"] == 7 * expected_cost_calls
        if case in EXPECTED_FAILURE:
            assert d["scenario_failed"] is True and d["failed_calls"] == n
            exp = EXPECTED_FAILURE[case]
            exp = exp[key] if isinstance(exp, dict) else exp
            assert d[exp] == n


def test_ae_success_logs_distances_and_true_api_success(tmp_path):
    result, poster, recs = run_one("AE", "HVAC", [H.ok(H.SCORES_JSON)], tmp_path)
    for r in recs:
        assert r["api_success"] is True  # M5: was always False
        assert r["rag_top_k"] == 1
        assert r["rag_exemplar_ids"] == ["rag_HVAC_0"]
        assert r["rag_exemplar_distances"] == [pytest.approx(0.1234)]


def test_ah_api_exhausted_marks_scenario_failed(tmp_path):
    result, poster, recs = run_one("AH", "HVAC", [H.FakeResponse(503, {"error": {"code": 503}})], tmp_path)
    assert result["scenario_failed"] is True  # S5
    assert result["failure_types"] == [FAILED_API_EXHAUSTED]
    assert len(poster.calls) == MAX_RETRIES
    assert [a["alternative"] for a in result["alternatives_scores"]] == [
        str(SCN["HVAC"][1][c]) for c in H.ALT_COLS]


# ---------------------------------------------------------------------------
# 2. Fatal statuses abort, through every `except Exception`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [401, 402, 403])
@pytest.mark.parametrize("key", ARCHS)
def test_fatal_status_aborts(key, status, tmp_path):
    script = [H.FakeResponse(status, {"error": {"code": status, "message": "nope"}})]
    swallowed = False
    with pytest.raises(SU.OpenRouterFatalError) as ei:
        try:  # mimic the position-bias / order-arm `except Exception` wrappers
            run_one(key, "Shower", script, tmp_path)
        except Exception:
            swallowed = True
    assert not swallowed
    assert f"HTTP {status}" in str(ei.value)
    recs = H.read_jsonl(tmp_path / f"{key}_Shower_results_run_01_raw.jsonl")
    assert len(recs) == 1  # the failing call is archived before the abort
    assert recs[0]["failure_types"] == [f"FATAL_HTTP_{status}"]
    assert recs[0]["attempts"] == 1 and recs[0]["attempt_errors"][0]["status"] == status


def test_consecutive_bad_requests_abort(tmp_path):
    """5 calls in a row with no usable completion stop the process (AD: the
    5th call is scenario 2, alternative 2)."""
    script = [H.FakeResponse(400, {"error": {"code": 400, "message": "effort 'minimal' not supported"}})]
    run_one("AD", "HVAC", script, tmp_path)  # 3 failed calls
    with pytest.raises(SU.OpenRouterFatalError) as ei:
        run_one("AD", "Appliance", script, tmp_path)
    assert "5 consecutive" in str(ei.value)


def test_success_resets_consecutive_counter(tmp_path):
    bad = H.FakeResponse(400, {"error": {"code": 400}})
    run_one("AD", "HVAC", [bad], tmp_path)
    run_one("AD", "Shower", [H.ok(H.SCORES_JSON)], tmp_path)
    assert SU._consecutive_api_failures == 0
    run_one("AD", "Appliance", [bad], tmp_path)  # 3 more: no abort


# ---------------------------------------------------------------------------
# 3. run_test_set / run_multi_and_aggregate: per-run files, sums, resume guard
# ---------------------------------------------------------------------------

def tiny_test_xlsx(tmp_path):
    df = pd.read_excel(H.REPO / "Scenario Files" / "TestScenarios.xlsx")
    rows = [df[df.decision_type == dt].iloc[0] for dt in DTYPES]
    p = tmp_path / "tiny_test.xlsx"
    pd.DataFrame(rows).to_excel(p, index=False)
    return p


def responder(key):
    def f(payload):
        text = payload["messages"][-1]["content"]
        if key != "AH":
            return H.ok(H.SCORES_JSON)
        for dt in DTYPES:
            if f"- decision_type: {dt}\n" in text:
                return H.ok(good_content("AH", dt))
        raise AssertionError("no decision type in prompt")
    return f


@pytest.mark.parametrize("key", ARCHS)
def test_run_test_set_outputs(key, tmp_path):
    mod = MODS[key]
    test_xlsx = tiny_test_xlsx(tmp_path)
    out = tmp_path / f"{key}_results_run_01.xlsx"
    diag = tmp_path / f"{key}_results_diagnostics_run_01.json"
    poster = H.Poster(responder(key))
    with mock.patch("requests.post", poster):
        mod.run_test_set(str(test_xlsx), str(out), str(diag))
    df = pd.read_excel(out)
    assert {"collected_utc", "model_id"} <= set(df.columns)
    assert df["collected_utc"].notna().all() and (df["model_id"] == mod.API_CONFIG["model"]).all()
    for v in df["collected_utc"]:
        assert datetime.fromisoformat(v).utcoffset().total_seconds() == 0
    assert SU.run_file_state(out) == "complete"
    d = json.loads(diag.read_text(encoding="utf-8"))
    n_calls = 3 * N_CALLS[key]
    assert d["collected_utc_start"] == d["collected_utc"]
    assert datetime.fromisoformat(d["collected_utc_end"]) >= datetime.fromisoformat(d["collected_utc_start"])
    assert d["model_id"] == mod.API_CONFIG["model"] and d["max_output_tokens"] == SU.MAX_OUTPUT_TOKENS
    assert d["total_cost_usd"] == pytest.approx(H.COST * n_calls)
    assert d["calls_with_cost"] == n_calls and d["total_tokens_reasoning"] == 7 * n_calls
    assert d["failed_scenarios"] == 0
    if key == "AE":
        assert d["rag_top_k"] == 1
    recs = H.read_jsonl(out.with_name(f"{out.stem}_raw.jsonl"))
    assert len(recs) == n_calls
    assert sorted({r["scenario_id"] for r in recs}) == [1, 2, 3]
    assert all(r["run"] == 1 for r in recs)


@pytest.mark.parametrize("key", ARCHS)
def test_run_multi_fatal_aborts_without_saving(key, tmp_path, monkeypatch):
    mod = MODS[key]
    monkeypatch.setattr(mod, "N_RUNS", 2)
    test_xlsx = tiny_test_xlsx(tmp_path)
    base = tmp_path / f"{key}_results.xlsx"
    poster = H.Poster([H.FakeResponse(402, {"error": {"code": 402, "message": "Insufficient credits"}})])
    with mock.patch("requests.post", poster), pytest.raises(SU.OpenRouterFatalError):
        mod.run_multi_and_aggregate(str(test_xlsx), str(base), str(tmp_path / f"{key}_diag.json"))
    assert len(poster.calls) == 1
    assert not (tmp_path / f"{key}_results_run_01.xlsx").exists()
    assert not base.exists()
    events = (tmp_path / f"{key}_results_events.log").read_text(encoding="utf-8")
    assert "START run 1/2" in events and "ABORT run 1/2" in events and "402" in events


@pytest.mark.parametrize("key", ARCHS)
def test_resume_guard(key, tmp_path, monkeypatch):
    mod = MODS[key]
    monkeypatch.setattr(mod, "N_RUNS", 1)
    test_xlsx = tiny_test_xlsx(tmp_path)
    base = tmp_path / f"{key}_results.xlsx"
    run1 = tmp_path / f"{key}_results_run_01.xlsx"
    diag = tmp_path / f"{key}_diag.json"
    poster = H.Poster(responder(key))
    # a complete new-format run -> skipped, logged, aggregated, no POST
    with mock.patch("requests.post", poster):
        mod.run_test_set(str(test_xlsx), str(run1), str(tmp_path / f"{key}_diag_run_01.json"))
    n_posts = len(poster.calls)
    with mock.patch("requests.post", poster):
        mod.run_multi_and_aggregate(str(test_xlsx), str(base), str(diag))
    assert len(poster.calls) == n_posts
    events = (tmp_path / f"{key}_results_events.log").read_text(encoding="utf-8")
    assert "SKIP run 1/1" in events and base.exists()
    # an old-format run (no collected_utc) -> refused, nothing overwritten, no POST
    old = pd.read_excel(run1).drop(columns=["collected_utc", "model_id"])
    old.to_excel(run1, index=False)
    before = run1.read_bytes()
    assert SU.run_file_state(run1) == "old_format"
    with mock.patch("requests.post", poster), pytest.raises(RuntimeError, match="Refusing to run"):
        mod.run_multi_and_aggregate(str(test_xlsx), str(base), str(diag))
    assert len(poster.calls) == n_posts and run1.read_bytes() == before
    assert "REFUSED" in (tmp_path / f"{key}_results_events.log").read_text(encoding="utf-8")


def test_run_file_state_missing_and_tmp(tmp_path):
    p = tmp_path / "x_run_01.xlsx"
    assert SU.run_file_state(p) == "missing"
    pd.DataFrame({"a": [1], "collected_utc": ["t"]}).to_excel(p, index=False)
    assert SU.run_file_state(p) == "complete"
    p.with_suffix(".xlsx.tmp").write_text("partial")
    assert SU.run_file_state(p) == "missing"


# ---------------------------------------------------------------------------
# 4. A_E retrieval failure and k
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["raise", "empty", "uninitialised"])
def test_ae_retrieval_failure(mode, tmp_path):
    mod = MODS["AE"]
    if mode == "uninitialised":
        mod.chroma_collection = None
    else:
        mod.chroma_collection = H.FakeCollection(mode=mode)
    result, poster, recs = run_one("AE", "HVAC", [H.ok(H.SCORES_JSON)], tmp_path)
    assert len(poster.calls) == 0  # nothing paid for
    assert is_failed("AE", result)
    assert result["diagnostics"][SU.FAILED_RAG_RETRIEVAL] == 3
    assert len(recs) == 3
    for r in recs:
        assert r["failure_types"] == [SU.FAILED_RAG_RETRIEVAL]
        assert r["api_called"] is False and r["retrieval_error"]
        assert r["rag_exemplar_ids"] == []


def test_ae_consecutive_retrieval_failures_abort(tmp_path):
    MODS["AE"].chroma_collection = H.FakeCollection(mode="empty")
    run_one("AE", "HVAC", [H.ok(H.SCORES_JSON)], tmp_path)  # 3 failures
    with pytest.raises(SU.RunAbort, match="5 consecutive A_E calls retrieved no exemplar"):
        try:
            run_one("AE", "Shower", [H.ok(H.SCORES_JSON)], tmp_path)
        except Exception:
            pytest.fail("RunAbort swallowed by `except Exception`")
    # a successful retrieval resets the streak
    MODS["AE"]._consecutive_retrieval_failures = 4
    MODS["AE"].chroma_collection = H.FakeCollection()
    run_one("AE", "Appliance", [H.ok(H.SCORES_JSON)], tmp_path)
    assert MODS["AE"]._consecutive_retrieval_failures == 0


def test_ae_rag_top_k_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_TOP_K", "3")
    mod3 = H.load_patched("AE", tag="_k3")
    monkeypatch.delenv("RAG_TOP_K")
    assert mod3.RETRIEVE_K == 3 and MODS["AE"].RETRIEVE_K == 1 == MODS["AE"].DEFAULT_RETRIEVE_K
    coll = H.FakeCollection(k_available=5)
    mod3.chroma_collection, mod3.embedding_model = coll, H.FakeEmbedder()
    raw = tmp_path / "k3_run_01_raw.jsonl"
    mod3.RAW_LOG.start(raw)
    mod3.RAW_LOG.set_scenario(1)
    with mock.patch("requests.post", H.Poster([H.ok(H.SCORES_JSON)])):
        mod3.run_scenario(dict(SCN["HVAC"][1]))
    mod3.RAW_LOG.stop()
    assert all(q["n_results"] == 3 for q in coll.queries)
    recs = H.read_jsonl(raw)
    assert all(r["rag_top_k"] == 3 and len(r["rag_exemplar_ids"]) == 3
               and len(r["rag_exemplar_distances"]) == 3 for r in recs)
    # file naming: k only in the name when non-default
    captured = {}
    monkeypatch.setattr(mod3, "run_multi_and_aggregate",
                        lambda **kw: captured.update(kw))
    mod3.main()
    assert Path(captured["base_output_csv"]).name == "Example-Guided_LLM_Scoring_k3_results.xlsx"
    assert Path(captured["base_diagnostics_path"]).name == "Example-Guided_LLM_Scoring_k3_results_diagnostics.json"
    monkeypatch.setattr(MODS["AE"], "run_multi_and_aggregate", lambda **kw: captured.update(kw))
    MODS["AE"].main()
    assert Path(captured["base_output_csv"]).name == "Example-Guided_LLM_Scoring_results.xlsx"


def test_ae_real_chroma_retrieval_distances(tmp_path, monkeypatch):
    """Against a COPY of the real index and the cached embedding model."""
    import shutil
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    db = tmp_path / "chroma_copy"
    shutil.copytree(H.REPO / "chroma_rag_db", db)
    mod = H.load_patched("AE", tag="_realchroma")
    mod.CHROMA_DB_PATH = db
    mod.init_rag_resources()
    for dt in DTYPES:
        errs = []
        got = mod.retrieve_similar_scenarios(dict(SCN[dt][1]), k=mod.RETRIEVE_K, error_out=errs)
        assert len(got) == 1 and not errs
        assert got[0]["decision_type"] == dt and isinstance(got[0]["distance"], float)


# ---------------------------------------------------------------------------
# 5. Tie rounding
# ---------------------------------------------------------------------------

def _find_noise_ties(n_wanted=20, seed=7):
    """2-dp score vectors whose weighted sums are exactly equal in decimal but
    differ as floats, with the float order OPPOSITE to TIE_BREAK_PRIORITY."""
    from decimal import Decimal
    rng = random.Random(seed)
    grid = [round(0.05 * i, 2) for i in range(21)]
    W = {c: Decimal(str(CRITERION_WEIGHTS[c])) for c in CRIT}
    wf = CRITERION_WEIGHTS
    by_exact = {}
    found = []
    for _ in range(200000):
        v = tuple(rng.choice(grid) for _ in CRIT)
        exact = sum(W[c] * Decimal(str(x)) for c, x in zip(CRIT, v))
        fl = (wf["energy_cost"] * v[0] + wf["environmental"] * v[1]
              + wf["comfort"] * v[2] + wf["practicality"] * v[3])
        for (u, ufl) in by_exact.get(exact, []):
            if ufl == fl or u == v:
                continue
            ud, vd = dict(zip(CRIT, u)), dict(zip(CRIT, v))
            tb_u = tuple(ud[c] for c in TIE_BREAK_PRIORITY)
            tb_v = tuple(vd[c] for c in TIE_BREAK_PRIORITY)
            if tb_u == tb_v:
                continue
            # keep pairs where float noise and the tie-break disagree
            if (ufl > fl) != (tb_u > tb_v):
                found.append((ud, vd))
        by_exact.setdefault(exact, []).append((v, fl))
        if len(found) >= n_wanted:
            break
    assert found, "no float-noise tie found"
    return found


def test_tie_rounding_per_run_ae_ah():
    live = {k: H.load_prepatch(k) for k in ("AE", "AH")}
    pairs = _find_noise_ties()
    live_wrong = 0
    for a, b in pairs:
        ref = SU.apply_mavt_ranking([{"alternative": "A", **a}, {"alternative": "B", **b}])
        assert ref["weighted_scores"][0] == ref["weighted_scores"][1]
        nested = [{"alternative": "A", "scores": a}, {"alternative": "B", "scores": b}]
        for k in ("AE", "AH"):
            got = MODS[k].apply_mavt_ranking(nested)
            assert got["ranks"] == ref["ranks"], (k, a, b)
            if live[k].apply_mavt_ranking(nested)["ranks"] != ref["ranks"]:
                live_wrong += 1
    assert live_wrong > 0  # the live copies really did mis-rank these
    print(f"\n[tie] {len(pairs)} noise-tie pairs; pre-patch AE+AH mis-ranked {live_wrong} of {2 * len(pairs)}")


@pytest.mark.parametrize("key", ARCHS)
def test_tie_rounding_aggregate(key, tmp_path, monkeypatch):
    """The averaged-results ranking applies the same rounding + tie-break."""
    mod = MODS[key]
    monkeypatch.setattr(mod, "N_RUNS", 1)
    a, b = _find_noise_ties(1)[0]
    test_xlsx = tiny_test_xlsx(tmp_path)
    run1 = tmp_path / f"{key}_results_run_01.xlsx"
    with mock.patch("requests.post", H.Poster(responder(key))):
        mod.run_test_set(str(test_xlsx), str(run1), str(tmp_path / f"{key}_d_run_01.json"))
    df = pd.read_excel(run1)
    sid = df["scenario_id"].iloc[0]
    idx = df.index[df["scenario_id"] == sid][:3]
    c = {x: 0.05 for x in CRIT}  # a clear third place
    for i, sc in zip(idx, (a, b, c)):
        for k2 in CRIT:
            df.loc[i, k2] = sc[k2]
    df.to_excel(run1, index=False)
    base = tmp_path / f"{key}_results.xlsx"
    mod.run_multi_and_aggregate(str(test_xlsx), str(base), str(tmp_path / f"{key}_d.json"))
    agg = pd.read_excel(base)
    agg = agg[agg["scenario_id"] == sid]
    alts = df.loc[idx, "alternative"].astype(str).tolist()
    ref = SU.apply_mavt_ranking([{"alternative": alts[0], **a}, {"alternative": alts[1], **b},
                                 {"alternative": alts[2], **c}])
    got = {str(r["alternative"]): int(r["rank"]) for _, r in agg.iterrows()}
    assert [got[x] for x in alts] == ref["ranks"]


# ---------------------------------------------------------------------------
# 6. A_H key restriction
# ---------------------------------------------------------------------------

def test_ah_key_override_blocked():
    mod, live = MODS["AH"], H.load_prepatch("AH")
    sid, sc = SCN["HVAC"]
    clean = json.loads(AH_HIST[sid])
    dirty = json.loads(AH_HIST[sid])
    dirty["parameters"].update({
        "question": "It is freezing, what heat setting?", "hvac_mode": "heating",
        "location": "Phoenix, AZ", "outdoor_temp": 20, "utility_budget": 1,
        "household_size": 9, "square_footage": 9000,
    })
    s_clean = mod.score_with_ground_truth(clean, dict(sc))
    s_dirty = mod.score_with_ground_truth(dirty, dict(sc))
    assert s_dirty == s_clean
    s_live_dirty = live.score_with_ground_truth(json.loads(json.dumps(dirty)), dict(sc))
    assert s_live_dirty != s_clean  # the live merge let the extra keys through
    # completeness check and merge use the same key list
    assert mod.EXTRACTION_REQUIRED_PARAMS == {
        "HVAC": ['r_value', 'seer', 'hvac_age', 'occupancy_context'],
        "Appliance": ['appliance', 'kwh_per_cycle', 'baseline_time'],
        "Shower": ['gpm', 'tank_size', 'water_heater_temp'],
    }


# ---------------------------------------------------------------------------
# 7. Regression: historical responses parse identically
# ---------------------------------------------------------------------------

def _all_test_rows():
    df = SU.read_table_clean(H.REPO / "Scenario Files" / "TestScenarios.xlsx", keep_str_cols=H.ALT_COLS)
    return {i + 1: row.to_dict() for i, row in df.iterrows()}


def test_regression_ah_historical_raw_jsonl(capsys):
    """Every stored A_H order-arm response (4 models x 8 runs x 195) through
    the patched and the live extract_all_with_ai: identical parsed result and
    failure code, and identical to what was stored at collection time."""
    live = H.load_prepatch("AH")
    rows = _all_test_rows()
    n = diff_live = diff_stored = 0
    by_folder = {}
    for path, rec in H.iter_raw_jsonl():
        if "hybrid_order_reversal" not in str(path):
            continue
        sid = int(rec["scenario_id"])
        sc = dict(rows[sid])
        for col, v in zip(H.ALT_COLS, rec.get("order_as_sent") or []):
            sc[col] = v
        dt = rec["decision_type"] or None
        resp = H.ok(rec["response"])
        with mock.patch("requests.post", H.Poster([resp])):
            got = MODS["AH"].extract_all_with_ai(dict(sc), expected_decision_type=dt)
        with mock.patch("requests.post", H.Poster([resp])):
            ref = live.extract_all_with_ai(dict(sc), expected_decision_type=dt)
        n += 1
        folder = path.parent.parent.name
        by_folder[folder] = by_folder.get(folder, 0) + 1
        if (got[0], got[1]["failure_types"]) != (ref[0], ref[1]["failure_types"]):
            diff_live += 1
        if (got[0], got[1]["failure_types"]) != (rec.get("parsed"), rec.get("failure_types")):
            diff_stored += 1
        SU._consecutive_api_failures = 0
    capsys.readouterr()
    print(f"\n[regression A_H] {n} historical responses {by_folder}; "
          f"differ from pre-patch code: {diff_live}; differ from stored outcome: {diff_stored}")
    assert n == 4 * 8 * 195
    assert diff_live == 0 and diff_stored == 0


SYNTHETIC = [
    '{"energy_cost": 0.6, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '```json\n{"energy_cost": 0.2, "environmental": 0.3, "comfort": 0.9, "practicality": 1}\n```',
    '```\n{"energy_cost": 0, "environmental": 1.0, "comfort": 0.5, "practicality": 0.5}\n```',
    '{"energy_cost": 1.2, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '{"energy_cost": -0.1, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '{"energy_cost": "0.6", "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '{"environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    'Sure! {"energy_cost": 0.6, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    'not json at all',
    '   {"energy_cost": 0.61, "environmental": 0.52, "comfort": 0.73, "practicality": 0.84}  ',
    '{"energy_cost": true, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
]


@pytest.mark.parametrize("key", ["AD", "AE"])
def test_regression_ad_ae_synthetic(key):
    """No historical A_D/A_E raw responses exist; replay a corpus of response
    shapes through the live and patched scorers and require identical scores
    and failure codes (sentinels compared as sentinels)."""
    live = H.load_prepatch(key)
    live.chroma_collection, live.embedding_model = H.FakeCollection(), H.FakeEmbedder()
    sc = dict(SCN["HVAC"][1])
    alt = sc["alternative_1"]
    for text in SYNTHETIC:
        outs = []
        for m in (MODS[key], live):
            fn = m.score_alternative if key == "AD" else m.score_alternative_with_rag
            with mock.patch("requests.post", H.Poster([H.ok(text)])):
                s, d = fn(dict(sc), alt)
            outs.append(({c: s.get(c) for c in CRIT}, d.get("failure_types"), bool(d.get("success"))))
        assert outs[0] == outs[1], (key, text, outs)


# ---------------------------------------------------------------------------
# 8. Callers: position bias (A_D) and the hybrid order arm (A_H)
# ---------------------------------------------------------------------------

def _load_script(name):
    path = H.REPO / "Miscellaneous Scripts" / "experiments" / name
    spec = importlib.util.spec_from_file_location(f"caller_{name[:-3]}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_position_bias_normalize_result_compat(tmp_path):
    pb = _load_script("run_position_bias_control.py")
    sid, sc = scenario_for("AD", "HVAC")
    for script, failed in (([H.ok(H.SCORES_JSON)], False),
                           ([H.ok("x", finish="length")], True)):
        with mock.patch("requests.post", H.Poster(script)):
            result = MODS["AD"].run_scenario(dict(sc))
        rows = pb.normalize_result(result, sc)
        assert len(rows) == 3
        assert all(SU.is_sentinel(r["rank"]) for r in rows) == failed


def test_hybrid_order_arm_capture_compat():
    hy = _load_script("run_hybrid_ablation_experiments.py")
    mod = H.load_patched("AH", tag="_hybrid")
    sink = hy.instrument_capture(mod)
    sid, sc = SCN["Shower"]
    with mock.patch("requests.post", H.Poster([H.ok(AH_HIST[sid])])):
        ext, diag = mod.extract_all_with_ai(dict(sc), expected_decision_type="Shower")
    assert ext is not None and diag["failure_types"] == []
    api = sink[-1]["api_diag"]
    assert api["provider"] == "Google AI Studio" and api["response_id"] == "gen-abc123"
    assert api["usage"]["cost"] == H.COST and api["request_params"]["max_tokens"] == SU.MAX_OUTPUT_TOKENS
    json.dumps(sink[-1])  # the order arm writes it to jsonl
    sink.clear()
    with mock.patch("requests.post", H.Poster([H.FakeResponse(503, {"error": {"code": 503}})])):
        ext, diag = mod.extract_all_with_ai(dict(sc), expected_decision_type="Shower")
    assert ext is None and diag["failure_types"] == [FAILED_API_EXHAUSTED]
    assert sink[-1]["prompt"] and sink[-1]["response"] == ""  # prompt kept on failure
    assert len(diag["api_diagnostics"]["attempt_errors"]) == MAX_RETRIES
    sink.clear()
    with mock.patch("requests.post", H.Poster([H.ok(AH_HIST[sid], finish="length")])):
        ext, diag = mod.extract_all_with_ai(dict(sc), expected_decision_type="Shower")
    assert ext is None and diag["failure_types"] == [SU.FAILED_TRUNCATED]
    assert sink[-1]["api_diag"]["truncated"] is True
    SU._consecutive_api_failures = 0
    with mock.patch("requests.post", H.Poster([H.FakeResponse(402, {})])):
        with pytest.raises(SU.OpenRouterFatalError):
            try:  # collect_order_arm wraps extract_all_with_ai in `except Exception`
                mod.extract_all_with_ai(dict(sc), expected_decision_type="Shower")
            except Exception:
                pytest.fail("fatal error was swallowed by `except Exception`")


def test_provider_prefs_follow_model_id():
    from model_config import MODEL_SPECS
    for spec in MODEL_SPECS.values():
        assert SU.provider_prefs_for_model(spec["openrouter_id"]) == spec.get("provider", {"require_parameters": True})
    assert SU.provider_prefs_for_model("unknown/model") == {"require_parameters": True}
    # a returned copy can be mutated without touching the default
    SU.provider_prefs_for_model("unknown/model")["order"] = ["x"]
    assert SU.DEFAULT_PROVIDER_PREFS == {"require_parameters": True}


def test_payload_passes_model_specs_provider_pin_unchanged():
    """build_openrouter_payload sends MODEL_SPECS[...]["provider"] exactly as the
    author wrote it (only / allow_fallbacks / require_parameters, nothing added,
    nothing dropped), for every model, and every architecture's query_openrouter
    puts that same dict on the wire."""
    from model_config import MODEL_SPECS
    for key, spec in MODEL_SPECS.items():
        pin = spec["provider"]
        assert pin.get("require_parameters") is True, (key, pin)
        p = SU.build_openrouter_payload(spec["openrouter_id"], [{"role": "user", "content": "x"}],
                                        0.3, {"effort": "none"})
        assert p["provider"] == pin, (key, p["provider"], pin)
        assert set(p["provider"]) == set(pin)
        assert p["provider"] is not pin  # a copy: mutating the payload cannot edit MODEL_SPECS
        assert p["max_tokens"] == SU.MAX_OUTPUT_TOKENS
    # on the wire, through each installed architecture, for the active MODEL_KEY
    for key in ARCHS:
        mod = MODS[key]
        poster = H.Poster([H.ok(H.SCORES_JSON)])
        with mock.patch("requests.post", poster):
            mod.query_openrouter([{"role": "user", "content": "x"}])
        sent = poster.calls[0]["payload"]["provider"]
        want = next(s["provider"] for s in MODEL_SPECS.values()
                    if s["openrouter_id"] == mod.API_CONFIG["model"])
        assert sent == want and sent["require_parameters"] is True
