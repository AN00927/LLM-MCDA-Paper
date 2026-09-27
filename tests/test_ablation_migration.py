"""Mocked tests for the experiment scripts moved onto the shared OpenRouter
client (sentinel_utils.openrouter_chat), 2026-09-27:

  run_prompt_ablation_experiments.py   (own request loop -> shared client)
  run_rag_ablation_experiments.py      (own request loop -> shared client;
                                        Top-1/Top-2 failed-scenario rule)
  run_hybrid_ablation_experiments.py   (order arm logs api_diagnostics)
  run_position_bias_control.py         (unchanged; inherits via A_D)

No network: arch_patch_harness forces a dummy key and blocks every real
request; requests.post is mocked in each test, time.sleep is a no-op.

Run:
    OPENBLAS_NUM_THREADS=1 env -u OPENROUTER_API_KEY \\
        .venv/Scripts/python.exe -m pytest tests/test_ablation_migration.py -q
"""
import importlib.util
import json
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import requests

import arch_patch_harness as H
import sentinel_utils as SU
from model_config import MAX_RETRIES, MODEL_SPECS

EXP = H.REPO / "Miscellaneous Scripts" / "experiments"
CRIT = ["energy_cost", "environmental", "comfort", "practicality"]
META_FIELDS = ["provider", "response_id", "response_model", "finish_reason", "native_finish_reason",
               "usage", "cost", "reasoning_tokens", "reasoning", "request_params", "attempts",
               "retries", "attempt_errors", "truncated", "latency_ms", "collected_utc", "model"]


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, EXP / name)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m


PA = _load("run_prompt_ablation_experiments.py", "mig_prompt_ablation")
RA = _load("run_rag_ablation_experiments.py", "mig_rag_ablation")
HY = _load("run_hybrid_ablation_experiments.py", "mig_hybrid")
PB = _load("run_position_bias_control.py", "mig_position_bias")

GEMINI = MODEL_SPECS["gemini"]["openrouter_id"]
QWEN = MODEL_SPECS["qwen"]["openrouter_id"]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    SU._consecutive_api_failures = 0
    PA._ABORT.clear()
    RA._ABORT.clear()
    PA.RAW_LOG.stop()
    RA.RAW_LOG.stop()
    yield sleeps
    PA.RAW_LOG.stop()
    RA.RAW_LOG.stop()
    PA._ABORT.clear()
    RA._ABORT.clear()
    SU._consecutive_api_failures = 0


class ThreadSafePoster(H.Poster):
    """H.Poster with a lock, for the thread-pool tests."""

    def __init__(self, script):
        super().__init__(script)
        self._lock = threading.Lock()

    def __call__(self, url, headers=None, json=None, timeout=None):
        with self._lock:
            return super().__call__(url, headers=headers, json=json, timeout=timeout)


def after_n_ok(n, then):
    """Callable script: n successful replies, then *then* forever."""
    count = {"n": 0}

    def f(payload):
        count["n"] += 1
        return H.ok(H.SCORES_JSON) if count["n"] <= n else then
    return f


def fatal(status=402):
    return H.FakeResponse(status, {"error": {"code": status, "message": "Insufficient credits"}})


def check_wire(poster, model_id):
    """Every POST carries max_tokens and the MODEL_SPECS provider pin
    (require_parameters included) for the model actually sent."""
    want = next(s["provider"] for s in MODEL_SPECS.values() if s["openrouter_id"] == model_id)
    assert poster.calls, "no POST made"
    for c in poster.calls:
        p = c["payload"]
        assert p["model"] == model_id
        assert p["max_tokens"] == SU.MAX_OUTPUT_TOKENS
        assert p["provider"] == want and p["provider"]["require_parameters"] is True
        assert "usage" not in p


def check_meta(rec, model_id):
    missing = [f for f in META_FIELDS if f not in rec]
    assert not missing, missing
    assert rec["model"] == model_id
    assert datetime.fromisoformat(rec["collected_utc"]).utcoffset().total_seconds() == 0


# ===========================================================================
# Prompt ablation
# ===========================================================================

def pa_scenario(dt="HVAC"):
    sid, sc = H.get_test_scenarios()[dt]
    return dict(sc, scenario_id=sid)


def pa_score(tmp_path, script, arch="AD", variant="control", model_key="gemini", dt="HVAC"):
    raw = tmp_path / f"pa_{arch}_{variant}_run_01_raw.jsonl"
    PA.RAW_LOG.start(raw, run=1)
    poster = H.Poster(script)
    try:
        with mock.patch("requests.post", poster):
            res = PA.score_scenario(pa_scenario(dt), arch, PA.VARIANT_SPECS[variant],
                                    MODEL_SPECS[model_key]["openrouter_id"], model_key)
    finally:
        PA.RAW_LOG.stop()
    return res, poster, (H.read_jsonl(raw) if raw.exists() else [])


def test_pa_success_logs_metadata(tmp_path):
    res, poster, recs = pa_score(tmp_path, [H.ok(H.SCORES_JSON)])
    assert len(poster.calls) == 3 and len(recs) == 3
    check_wire(poster, GEMINI)
    assert res["failure_types"] == [] and res["diagnostics"]["successful_calls"] == 3
    for r in recs:
        check_meta(r, GEMINI)
        assert r["provider"] == "Google AI Studio" and r["response_id"] == "gen-abc123"
        assert r["usage"]["cost"] == H.COST and r["cost"] == H.COST
        assert r["reasoning_tokens"] == 7 and r["finish_reason"] == "stop"
        assert r["request_params"]["max_tokens"] == SU.MAX_OUTPUT_TOKENS
        assert r["request_params"]["provider"] == MODEL_SPECS["gemini"]["provider"]
        assert r["api_success"] is True and r["parse_error"] is None and r["truncated"] is False
        assert r["model_key"] == "gemini" and r["variant"] == PA.VARIANT_SPECS["control"]["label"]


def test_pa_pins_follow_model_key(tmp_path):
    """The pin is looked up by the id sent, not by the MODEL_KEY of the process."""
    res, poster, recs = pa_score(tmp_path, [H.ok(H.SCORES_JSON)], model_key="qwen")
    check_wire(poster, QWEN)


@pytest.mark.parametrize("finish", ["length"])
def test_pa_truncation_is_failure(tmp_path, finish):
    # valid JSON, but cut off: must never be scored
    res, poster, recs = pa_score(tmp_path, [H.ok(H.SCORES_JSON, finish=finish, native="MAX_TOKENS")])
    assert len(poster.calls) == 3  # not retried
    assert res["failure_types"] == [PA.ERR_TRUNCATED] * 3
    assert all(SU.is_sentinel(a[c]) for a in res["scored"] for c in CRIT)
    assert PA.scenario_metrics(res, {"mavt_by_alt": {}, "rank_by_alt": {}})["failed"] is True
    for r in recs:
        assert r["truncated"] is True and r["finish_reason"] == "length"
        assert r["parse_error"] == PA.ERR_TRUNCATED and r["failure_type"] == SU.FAILED_TRUNCATED
        assert r["response"]  # partial text kept for audit


def test_pa_null_content_is_failure(tmp_path):
    res, poster, recs = pa_score(tmp_path, [H.ok(None, reasoning="thinking...")])
    assert len(poster.calls) == 3
    assert res["failure_types"] == [PA.ERR_EMPTY] * 3
    assert all(SU.is_sentinel(a[c]) for a in res["scored"] for c in CRIT)
    assert all(r["parse_error"] == PA.ERR_EMPTY and r["reasoning"] == "thinking..." for r in recs)


def test_pa_whitespace_content_is_failure(tmp_path):
    res, poster, recs = pa_score(tmp_path, [H.ok("   \n")])
    assert res["failure_types"] == [PA.ERR_EMPTY] * 3


def test_pa_400_limited_attempts(tmp_path):
    bad = H.FakeResponse(400, {"error": {"code": 400, "message": "bad parameter"}})
    res, poster, recs = pa_score(tmp_path, [bad])
    assert len(poster.calls) == 3 * SU.BAD_REQUEST_MAX_ATTEMPTS == 6
    assert res["failure_types"] == [PA.ERR_API_BAD_REQUEST] * 3
    for r in recs:
        assert r["api_success"] is False and r["attempts"] == 2
        assert [e["status"] for e in r["attempt_errors"]] == [400, 400]
        assert "bad parameter" in r["attempt_errors"][0]["detail"]
        assert r["error"].startswith(SU.FAILED_API_BAD_REQUEST)


def test_pa_429_retried(tmp_path, _env):
    rl = H.FakeResponse(429, {"error": {"code": 429, "message": "rate limited"}})
    res, poster, recs = pa_score(tmp_path, [rl, H.ok(H.SCORES_JSON)])
    assert len(poster.calls) == 4 and len(_env) == 1
    assert res["failure_types"] == []
    assert recs[0]["attempts"] == 2 and recs[0]["retries"] == 1
    assert recs[0]["attempt_errors"][0]["status"] == 429


def test_pa_exhausted_is_failure(tmp_path):
    res, poster, recs = pa_score(tmp_path, [requests.exceptions.Timeout("read timed out")])
    assert len(poster.calls) == 3 * MAX_RETRIES
    assert res["failure_types"] == [PA.ERR_API_EXHAUSTED] * 3
    assert all(len(r["attempt_errors"]) == MAX_RETRIES for r in recs)


def test_pa_ae_empty_retrieval_fails_without_call(tmp_path, monkeypatch):
    ae = H.load_patched("AE", tag="_pa_retrieval")
    ae.chroma_collection, ae.embedding_model = H.FakeCollection(mode="empty"), H.FakeEmbedder()
    monkeypatch.setattr(PA, "_ae_module", ae)
    res, poster, recs = pa_score(tmp_path, [H.ok(H.SCORES_JSON)], arch="AE")
    assert len(poster.calls) == 0  # nothing paid for
    assert res["failure_types"] == [PA.ERR_RAG_RETRIEVAL] * 3
    assert res["diagnostics"]["api_calls"] == 0
    assert all(r["api_called"] is False and r["retrieval_error"] for r in recs)


def test_pa_ae_success_logs_exemplars(tmp_path, monkeypatch):
    ae = H.load_patched("AE", tag="_pa_ok")
    ae.chroma_collection, ae.embedding_model = H.FakeCollection(), H.FakeEmbedder()
    monkeypatch.setattr(PA, "_ae_module", ae)
    res, poster, recs = pa_score(tmp_path, [H.ok(H.SCORES_JSON)], arch="AE")
    assert len(poster.calls) == 3 and res["failure_types"] == []
    for r in recs:
        assert r["rag_exemplar_ids"] == ["rag_HVAC_0"] and r["rag_top_k"] == 1
        assert r["rag_exemplar_distances"] == [pytest.approx(0.1234)]


def test_pa_fatal_aborts_through_pool_and_main(tmp_path, monkeypatch):
    """A 402 mid-run: the process aborts, queued scenarios are cancelled, and no
    cell xlsx, summary or report is written. A rerun then completes the cell."""
    out_dir = tmp_path / "Prompt_Ablation"
    report = tmp_path / "report.md"
    argv = ["x", "--sample-size", "24", "--runs", "1", "--variants", "control",
            "--architectures", "AD", "--models", "gemini", "--workers", "4",
            "--output-dir", str(out_dir), "--output", str(report)]
    monkeypatch.setattr(sys, "argv", argv)
    poster = ThreadSafePoster(after_n_ok(10, fatal(402)))
    with mock.patch("requests.post", poster), pytest.raises(SU.OpenRouterFatalError):
        try:
            PA.main()
        except Exception:
            pytest.fail("the abort was swallowed by `except Exception`")
    total = 24 * 3
    # 10 ok + at most one in-flight call per worker after the first 402
    assert len(poster.calls) <= 10 + 4 < total, len(poster.calls)
    assert not list(out_dir.glob("cell_*.xlsx")) and not list(out_dir.glob("*.tmp"))
    assert not (out_dir / "prompt_ablation_summary.xlsx").exists() and not report.exists()
    raw = out_dir / "cell_control_AD_gemini_run_01_raw.jsonl"
    recs = H.read_jsonl(raw)
    assert any(r.get("failure_type") == "FATAL_HTTP_402" for r in recs)  # the 402 is archived
    # resume: the same command re-collects the cell
    PA._ABORT.clear()
    SU._consecutive_api_failures = 0
    ok_poster = ThreadSafePoster([H.ok(H.SCORES_JSON)])
    with mock.patch("requests.post", ok_poster):
        PA.main()
    cell = pd.read_excel(out_dir / "cell_control_AD_gemini_run_01.xlsx")
    assert len(cell) == 24 and len(ok_poster.calls) == total
    assert report.exists()


def test_pa_serial_breaker_aborts(tmp_path):
    """workers=1: five 400-failed calls in a row stop the cell (shared breaker)."""
    bad = H.FakeResponse(400, {"error": {"code": 400, "message": "effort not supported"}})
    scenarios = PA.load_scenarios(6, 13)
    poster = H.Poster([bad])
    with mock.patch("requests.post", poster), pytest.raises(SU.OpenRouterFatalError, match="5 consecutive"):
        PA.run_cell(scenarios, {}, "AD", "control", PA.VARIANT_SPECS["control"], "gemini", 1, 1,
                    raw_log_path=tmp_path / "c_run_01_raw.jsonl")
    assert len(poster.calls) == 5 * SU.BAD_REQUEST_MAX_ATTEMPTS


# ===========================================================================
# RAG ablation
# ===========================================================================

GROUPS = RA.load_source_groups()


def ra_case(dt="HVAC", i=0):
    sc = GROUPS[dt][i]
    others = [c for c in GROUPS[dt] if c["scenario_id"] != sc["scenario_id"]][:3]
    retrieved = [{"id": c["scenario_id"], "text": "", "metadata": c, "distance": 0.1 * (j + 1)}
                 for j, c in enumerate(others)]
    return sc, retrieved


SPEC = RA.ABLATION_SPECS["control_k3"]


def ra_predict(tmp_path, script, model_id=GEMINI, dt="HVAC"):
    sc, retrieved = ra_case(dt)
    raw = tmp_path / "rag_raw.jsonl"
    RA.RAW_LOG.start(raw)
    poster = H.Poster(script)
    try:
        with mock.patch("requests.post", poster):
            res = RA.llm_prediction(sc, SPEC, retrieved, model_id)
    finally:
        RA.RAW_LOG.stop()
    return sc, res, poster, (H.read_jsonl(raw) if raw.exists() else [])


def test_ra_success_logs_metadata(tmp_path):
    sc, res, poster, recs = ra_predict(tmp_path, [H.ok(H.SCORES_JSON)])
    assert len(poster.calls) == 3 and len(recs) == 3
    check_wire(poster, GEMINI)
    assert not any(p["failed"] for p in res["predictions"])
    for r in recs:
        check_meta(r, GEMINI)
        assert r["provider"] == "Google AI Studio" and r["response_id"] == "gen-abc123"
        assert r["cost"] == H.COST and r["reasoning_tokens"] == 7 and r["finish_reason"] == "stop"
        assert r["api_success"] is True and r["parse_error"] is None
        assert r["retrieved_ids"] and len(r["retrieved_distances"]) == 3
        assert r["ablation"] == SPEC["label"] and r["k"] == 3


def test_ra_truncation_is_failure(tmp_path):
    sc, res, poster, recs = ra_predict(tmp_path, [H.ok(H.SCORES_JSON, finish="length", native="MAX_TOKENS")])
    assert len(poster.calls) == 3
    assert all(p["failed"] and p["error"] == RA.ERR_TRUNCATED for p in res["predictions"])
    assert all(SU.is_sentinel(p["weighted_score"]) for p in res["predictions"])
    assert all(r["truncated"] is True and r["parse_error"] == RA.ERR_TRUNCATED for r in recs)
    m = RA.scenario_metrics(res["predictions"], sc)
    assert m["scenario_failed"] and not m["top1_correct"] and not m["top2_correct"]


def test_ra_null_content_is_failure(tmp_path):
    sc, res, poster, recs = ra_predict(tmp_path, [H.ok(None)])
    assert all(p["failed"] and p["error"] == RA.ERR_EMPTY for p in res["predictions"])
    assert all(r["parse_error"] == RA.ERR_EMPTY for r in recs)


def test_ra_400_limited_attempts(tmp_path):
    bad = H.FakeResponse(400, {"error": {"code": 400, "message": "bad parameter"}})
    sc, res, poster, recs = ra_predict(tmp_path, [bad])
    assert len(poster.calls) == 3 * SU.BAD_REQUEST_MAX_ATTEMPTS
    assert all(p["failed"] and p["error"].startswith(RA.ERR_API_BAD_REQUEST) for p in res["predictions"])
    for r in recs:
        assert r["api_success"] is False
        assert [e["status"] for e in r["attempt_errors"]] == [400, 400]
        assert r["failure_type"] == SU.FAILED_API_BAD_REQUEST


def test_ra_429_retried(tmp_path, _env):
    rl = H.FakeResponse(429, {"error": {"code": 429, "message": "rate limited"}})
    sc, res, poster, recs = ra_predict(tmp_path, [rl, H.ok(H.SCORES_JSON)])
    assert len(poster.calls) == 4 and len(_env) == 1
    assert not any(p["failed"] for p in res["predictions"])
    assert recs[0]["retries"] == 1 and recs[0]["attempt_errors"][0]["status"] == 429


def test_ra_exhausted_is_failure(tmp_path):
    sc, res, poster, recs = ra_predict(tmp_path, [requests.exceptions.ConnectionError("down")])
    assert len(poster.calls) == 3 * MAX_RETRIES
    assert all(p["failed"] and p["error"].startswith(RA.ERR_API_EXHAUSTED) for p in res["predictions"])
    assert all(len(r["attempt_errors"]) == MAX_RETRIES and r["api_success"] is False for r in recs)


def _ra_collections():
    return {RA.DEFAULT_EMBEDDING_MODEL: (None, None, H.FakeEmbedder(), GROUPS)}


def test_ra_fatal_aborts_without_checkpoint(tmp_path):
    """402 mid-unit with 4 workers: RunAbort propagates, queued scenarios are
    cancelled, and the unit is NOT checkpointed (so it cannot resume as done)."""
    specs = RA.OrderedDict([("random_exemplars_k3", RA.ABLATION_SPECS["random_exemplars_k3"])])
    sample = RA.stratified_sample(GROUPS, 30, 13)
    ckpt = tmp_path / "checkpoints"
    poster = ThreadSafePoster(after_n_ok(10, fatal(402)))
    raw = tmp_path / "rag_raw.jsonl"
    RA.RAW_LOG.start(raw)
    try:
        with mock.patch("requests.post", poster), pytest.raises(SU.OpenRouterFatalError):
            try:
                RA.build_result_rows(sample, specs, _ra_collections(), np.random.default_rng(13),
                                     ["gemini"], workers=4, checkpoint_dir=ckpt,
                                     run_meta={"seed": 13, "sample_size": 30})
            except Exception:
                pytest.fail("the abort was swallowed by `except Exception`")
    finally:
        RA.RAW_LOG.stop()
    assert len(poster.calls) <= 10 + 4 < 30 * 3, len(poster.calls)
    assert not ckpt.exists() or not list(ckpt.glob("*.json")), "aborted unit was checkpointed"
    assert any(r.get("failure_type") == "FATAL_HTTP_402" for r in H.read_jsonl(raw))


def test_ra_old_format_checkpoint_refused(tmp_path):
    """A checkpoint written under the old request path / Top-1 rule is refused."""
    specs = RA.OrderedDict([("random_exemplars_k3", RA.ABLATION_SPECS["random_exemplars_k3"])])
    sample = RA.stratified_sample(GROUPS, 3, 13)
    run_meta = {"seed": 13, "sample_size": 3}
    header = RA._checkpoint_header("random_exemplars_k3", specs["random_exemplars_k3"], "gemini",
                                   GEMINI, sample, run_meta)
    header["format"] = 1
    p = RA.checkpoint_path(tmp_path, "random_exemplars_k3", "gemini")
    p.write_text(json.dumps({"header": header, "unit": {}, "rows": []}), encoding="utf-8")
    with mock.patch("requests.post", H.Poster([H.ok(H.SCORES_JSON)])) as _:
        with pytest.raises(RuntimeError, match="different configuration"):
            RA.build_result_rows(sample, specs, _ra_collections(), np.random.default_rng(13),
                                 ["gemini"], workers=1, checkpoint_dir=tmp_path, run_meta=run_meta)


def _gt_ranked_responder(sample, truncate_alts):
    """Scores that reproduce each scenario's GT order (so the prediction is a
    Top-1 hit when scored); alternatives in *truncate_alts* come back cut off."""
    rank_of = {}
    for sc in sample:
        for a in sc["alternatives"]:
            rank_of[(sc["question"], a["alternative"])] = a["rank"]

    def f(payload):
        text = payload["messages"][-1]["content"]
        alt = re.search(r'Score this alternative: "(.*)"', text).group(1)
        q = re.search(r'For the decision: "(.*)"', text).group(1)
        r = rank_of[(q, alt)]
        v = round(1.0 - 0.3 * (r - 1), 2)
        body = json.dumps({c: v for c in CRIT})
        if (q, alt) in truncate_alts:
            return H.ok(body, finish="length", native="MAX_TOKENS")
        return H.ok(body)
    return f


def test_ra_top1_counts_failed_scenarios_as_wrong(tmp_path):
    """Three scenarios, denominator 3: one fully scored and correct, one with a
    single truncated NON-top alternative (the old rule scored it a hit from the
    two survivors), one fully truncated. Top-1 = 1/3, not 2/3 or 1/1."""
    specs = RA.OrderedDict([("random_exemplars_k3", RA.ABLATION_SPECS["random_exemplars_k3"])])
    sample = [GROUPS["HVAC"][0], GROUPS["HVAC"][1], GROUPS["HVAC"][2]]
    for s in sample:
        assert len(s["alternatives"]) == 3
    s2_non_top = next(a["alternative"] for a in sample[1]["alternatives"] if a["rank"] == 3)
    truncate = {(sample[1]["question"], s2_non_top)} | {
        (sample[2]["question"], a["alternative"]) for a in sample[2]["alternatives"]}
    with mock.patch("requests.post", H.Poster(_gt_ranked_responder(sample, truncate))):
        rows = RA.build_result_rows(sample, specs, _ra_collections(), np.random.default_rng(13),
                                    ["gemini"], workers=1, checkpoint_dir=None,
                                    run_meta={"seed": 13})
    df = pd.DataFrame(rows)
    df["top1_accuracy"] = df["top1_correct"].astype(float)
    df["top2_accuracy"] = df["top2_correct"].astype(float)
    per = RA.scenario_level_df(df).set_index("source_scenario_id")
    ids = [s["source_scenario_id"] for s in sample]
    assert per.loc[ids, "scenario_failed"].tolist() == [False, True, True]
    assert per.loc[ids, "top1_correct"].tolist() == [True, False, False]
    # the old rule would have scored scenario 2 a hit: its pred_top1 is the GT top1
    assert per.loc[ids[1], "pred_top1"] == per.loc[ids[1], "gt_top1"]
    summ = RA.summarize_rows(df)
    row = summ.iloc[0]
    assert row["n_scenarios"] == 3 and row["n_failed_scenarios"] == 2
    assert row["top1_accuracy"] == pytest.approx(1 / 3)
    assert row["top2_accuracy"] == pytest.approx(1 / 3)
    # tau is not an accuracy metric: unchanged rule, averaged over scored rows only
    assert np.isnan(per.loc[ids[2], "kendall_tau"])
    by_dt = RA.summarize_by_decision_type(df)
    assert by_dt.iloc[0]["n_failed_scenarios"] == 2
    assert by_dt.iloc[0]["top1_accuracy"] == pytest.approx(1 / 3)


def test_ra_nn_unscored_counts_as_wrong():
    """The copy-only 'unscored' fallback marks a scenario failed; it stays in
    the Top-1 denominator as a miss."""
    sc, _ = ra_case("Shower")
    res = RA.nearest_neighbor_prediction(sc, [], fallback="unscored")
    m = RA.scenario_metrics(res["predictions"], sc)
    assert m["scenario_failed"] and m["top1_correct"] is False


# ===========================================================================
# Hybrid order arm
# ===========================================================================

def _ah_responder(fail_sids=(), sid_of_prompt=None):
    hist = H.historical_ah_responses()
    by_dt = {dt: hist[H.get_test_scenarios()[dt][0]] for dt in ("HVAC", "Appliance", "Shower")}

    def f(payload):
        text = payload["messages"][-1]["content"]
        for dt, resp in by_dt.items():
            if f"- decision_type: {dt}\n" in text:
                return H.ok(resp)
        raise AssertionError("no decision type in prompt")
    return f


def test_hybrid_order_arm_logs_api_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(HY, "order_arm_dir", lambda mk: tmp_path / mk)
    good = _ah_responder()
    n = {"i": 0}

    def script(payload):
        n["i"] += 1
        # the 2nd scenario's call fails (503 until retries are exhausted)
        if 2 <= n["i"] <= 1 + MAX_RETRIES:
            return H.FakeResponse(503, {"error": {"code": 503, "message": "overloaded"}})
        return good(payload)
    poster = H.Poster(script)
    with mock.patch("requests.post", poster):
        xlsx = HY.collect_order_arm("qwen", run=1, arm="control")
    check_wire(poster, QWEN)
    recs = H.read_jsonl(tmp_path / "qwen" / "AH_extraction_order_control_run_01_raw.jsonl")
    assert len(recs) == 195
    for r in recs:
        api = r["api_diagnostics"]
        assert api is not None, r["scenario_id"]
        assert api["request_params"]["max_tokens"] == SU.MAX_OUTPUT_TOKENS
        assert api["request_params"]["provider"] == MODEL_SPECS["qwen"]["provider"]
    ok_rec, failed_rec = recs[0], recs[1]
    assert ok_rec["api_diagnostics"]["provider"] == "Google AI Studio"
    assert ok_rec["api_diagnostics"]["response_id"] == "gen-abc123"
    assert ok_rec["api_diagnostics"]["cost"] == H.COST
    assert ok_rec["api_diagnostics"]["finish_reason"] == "stop"
    assert failed_rec["extraction_failed"] is True
    assert len(failed_rec["api_diagnostics"]["attempt_errors"]) == MAX_RETRIES
    assert failed_rec["api_diag"] is None  # why api_diagnostics is needed
    json.dumps(recs)
    assert Path(xlsx).exists()


def test_hybrid_order_arm_fatal_aborts(tmp_path, monkeypatch):
    monkeypatch.setattr(HY, "order_arm_dir", lambda mk: tmp_path / mk)
    good = _ah_responder()
    n = {"i": 0}

    def script(payload):
        n["i"] += 1
        return good(payload) if n["i"] <= 3 else fatal(402)
    with mock.patch("requests.post", H.Poster(script)), pytest.raises(SU.OpenRouterFatalError):
        HY.collect_order_arm("qwen", run=1, arm="control")
    d = tmp_path / "qwen"
    assert not (d / "AH_extraction_order_control_run_01.xlsx").exists()
    recs = H.read_jsonl(d / "AH_extraction_order_control_run_01_raw.jsonl")
    assert len(recs) == 3 and not any(r["extraction_failed"] for r in recs)  # completed only


# ===========================================================================
# Position bias (A_D): inherits pins, metadata and abort from the installed A_D
# ===========================================================================

def test_position_bias_inherits_client(tmp_path, monkeypatch):
    monkeypatch.setattr(PB, "output_dir_for", lambda mk: tmp_path / mk)
    poster = H.Poster([H.ok(H.SCORES_JSON)])
    with mock.patch("requests.post", poster):
        PB.run_reversed_arm("qwen", 3, 7)
    check_wire(poster, QWEN)
    d = tmp_path / "qwen"
    recs = H.read_jsonl(d / "Direct_LLM_Scoring_reversed_run_01_raw.jsonl")
    assert len(recs) == 9
    for r in recs:
        assert r["provider"] == "Google AI Studio" and r["cost"] == H.COST
        assert r["request_params"]["provider"] == MODEL_SPECS["qwen"]["provider"]
        assert r["finish_reason"] == "stop" and r["reasoning_tokens"] == 7
    df = pd.read_excel(d / "Direct_LLM_Scoring_reversed_run_01.xlsx")
    assert (df["model_id"] == QWEN).all() and df["collected_utc"].notna().all()


def test_position_bias_truncation_is_sentinel(tmp_path, monkeypatch):
    """First scenario's three calls come back truncated (valid JSON, finish
    length): its rows are sentinels, never scores; the rest are scored."""
    monkeypatch.setattr(PB, "output_dir_for", lambda mk: tmp_path / mk)
    n = {"i": 0}

    def script(payload):
        n["i"] += 1
        return H.ok(H.SCORES_JSON, finish="length") if n["i"] <= 3 else H.ok(H.SCORES_JSON)
    with mock.patch("requests.post", H.Poster(script)):
        PB.run_reversed_arm("qwen", 3, 7)
    df = pd.read_excel(tmp_path / "qwen" / "Direct_LLM_Scoring_reversed_run_01.xlsx")
    first = json.loads((tmp_path / "qwen" / "Direct_LLM_Scoring_reversed_partial_run_01.jsonl")
                       .read_text(encoding="utf-8").splitlines()[0])["scenario_id"]
    bad = df[df["scenario_id"] == first]
    good = df[df["scenario_id"] != first]
    assert len(bad) == 3 and bad["rank"].map(SU.is_sentinel).all()
    assert not good["rank"].map(SU.is_sentinel).any()


def test_position_bias_truncation_streak_aborts(tmp_path, monkeypatch):
    """Five truncated calls in a row trip the shared breaker."""
    monkeypatch.setattr(PB, "output_dir_for", lambda mk: tmp_path / mk)
    poster = H.Poster([H.ok(H.SCORES_JSON, finish="length")])
    with mock.patch("requests.post", poster), pytest.raises(SU.OpenRouterFatalError, match="5 consecutive"):
        PB.run_reversed_arm("qwen", 3, 7)
    assert len(poster.calls) == 5
    assert not (tmp_path / "qwen" / "Direct_LLM_Scoring_reversed_run_01.xlsx").exists()


def test_position_bias_fatal_aborts(tmp_path, monkeypatch):
    monkeypatch.setattr(PB, "output_dir_for", lambda mk: tmp_path / mk)
    n = {"i": 0}

    def script(payload):
        n["i"] += 1
        return H.ok(H.SCORES_JSON) if n["i"] <= 3 else fatal(402)
    poster = H.Poster(script)
    with mock.patch("requests.post", poster), pytest.raises(SU.OpenRouterFatalError):
        PB.run_reversed_arm("qwen", 3, 7)
    assert len(poster.calls) == 4
    d = tmp_path / "qwen"
    assert not (d / "Direct_LLM_Scoring_reversed_run_01.xlsx").exists()
    ckpt = [json.loads(l) for l in (d / "Direct_LLM_Scoring_reversed_partial_run_01.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len({r["scenario_id"] for r in ckpt}) == 1  # only the completed scenario
