"""Offline tests for the listwise direct-ranking arm
(scripts/experiments/run_listwise_direct_ranking.py).

No network and no paid calls: requests.post is replaced by the harness Poster.
"""
import importlib.util
import json
import re
import sys
from unittest import mock

import numpy as np
import pandas as pd
import pytest

import arch_patch_harness as H
from llm_mcda.common import sentinel_utils as SU
from llm_mcda.common.model_config import CRITERION_WEIGHTS, MODEL_SPECS

EXP = H.REPO / "scripts" / "experiments"


def _load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m


LW = _load(EXP / "run_listwise_direct_ranking.py", "listwise_under_test")
PA = LW.PA
SCENARIOS = PA.load_scenarios(None, 13)


@pytest.fixture(autouse=True)
def _reset():
    SU._consecutive_api_failures = 0
    LW._ABORT.clear()
    yield
    SU._consecutive_api_failures = 0
    LW._ABORT.clear()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def test_system_prompt_reuses_ad_anchors_and_states_config_weights():
    sp = LW.build_system_prompt()
    _, anchors = LW._ad_parts()
    assert anchors.strip() and anchors in sp and anchors in PA.AD_SYSTEM_PROMPT
    for c, w in CRITERION_WEIGHTS.items():
        assert f"{c} {round(100 * w)}%" in sp
    assert '{"ranking":' in sp
    # Nothing of the value model beyond the weights: no scores, ranges or scale.
    assert "0-1 scale" not in sp and "1928" not in sp


def test_context_block_is_ad_context_for_every_test_scenario():
    for sc in SCENARIOS:
        alts = LW.alternatives_of(sc)
        ad = PA.build_user_prompt(sc, alts[0])
        block = LW.context_block(sc)
        assert block in ad and block.startswith('For the decision: "')
        assert "SCENARIO CONTEXT:" in block and "Score this alternative" not in block
        up = LW.build_user_prompt(sc)
        assert up.startswith("Rank these alternatives: " + json.dumps(alts))
        assert block in up


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

ALTS = ["72", "76", "80"]


@pytest.mark.parametrize("text,expected", [
    ('{"ranking": ["80", "72", "76"]}', ["80", "72", "76"]),
    ('{"ranking": [80, 72.0, "76"]}', ["80", "72", "76"]),
    ('```json\n{"ranking": ["76", "80", "72"]}\n```', ["76", "80", "72"]),
    ('Reasoning first.\n{"ranking": ["72", "76", "80"]}', ["72", "76", "80"]),
    ('{"ranking": [" 80 ", "72", "76"]}', ["80", "72", "76"]),
])
def test_parse_ranking_valid(text, expected):
    assert LW.parse_ranking(text, ALTS) == (expected, None)


@pytest.mark.parametrize("text,error", [
    (None, LW.ERR_EMPTY),
    ("   ", LW.ERR_EMPTY),
    ("not json", LW.ERR_MALFORMED),
    ('{"order": ["72", "76", "80"]}', LW.ERR_MALFORMED),
    ('{"ranking": ["72", "72", "80"]}', LW.ERR_INVALID_RANKING),
    ('{"ranking": ["72", "76"]}', LW.ERR_INVALID_RANKING),
    ('{"ranking": ["72", "76", "80", "84"]}', LW.ERR_INVALID_RANKING),
    ('{"ranking": ["72", "76", "81"]}', LW.ERR_INVALID_RANKING),
])
def test_parse_ranking_invalid(text, error):
    assert LW.parse_ranking(text, ALTS) == (None, error)


def test_parse_ranking_time_labels():
    alts = ["2:00 PM", "9:00 PM", "6:00 AM"]
    assert LW.parse_ranking('{"ranking": ["6:00 am", "9:00 PM", "2:00 PM"]}', alts) == (
        ["6:00 AM", "9:00 PM", "2:00 PM"], None)


def test_failed_ranking_is_failed_not_neutral():
    ref = {"mavt_by_alt": {a: 0.5 for a in ALTS}, "rank_by_alt": {"72": 1, "76": 2, "80": 3}}
    m = PA.scenario_metrics(LW.ranking_result(ALTS, None), ref)
    assert m["failed"] and m["top1"] == 0.0 and m["top2"] == 0.0 and m["kendall_tau"] == 0.0  # S4: chance
    m = PA.scenario_metrics(LW.ranking_result(ALTS, ["72", "76", "80"]), ref)
    assert not m["failed"] and m["top1"] == 1.0 and m["kendall_tau"] == pytest.approx(1.0)
    m = PA.scenario_metrics(LW.ranking_result(ALTS, ["80", "76", "72"]), ref)
    assert m["top1"] == 0.0 and m["kendall_tau"] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# Collection, mocked
# ---------------------------------------------------------------------------

def _alts_in(payload):
    user = payload["messages"][-1]["content"]
    return json.loads(re.match(r"Rank these alternatives: (\[.*?\])\n", user).group(1))


def _reference_first_is_best(scenarios):
    return {sc["scenario_id"]: {"mavt_by_alt": {a: 1.0 - i / 10 for i, a in enumerate(LW.alternatives_of(sc))},
                                "rank_by_alt": {a: i + 1 for i, a in enumerate(LW.alternatives_of(sc))}}
            for sc in scenarios}


def test_run_one_writes_run_file_and_raw_log(tmp_path, monkeypatch):
    monkeypatch.setattr(LW, "output_dir_for", lambda mk: tmp_path / mk)
    scs = SCENARIOS[:6]
    ref = _reference_first_is_best(scs)
    poster = H.Poster(lambda p: H.ok(json.dumps({"ranking": _alts_in(p)})))
    with mock.patch("requests.post", poster):
        path = LW.run_one("gemini", 1, scs, ref, workers=2)
    df = pd.read_excel(path)
    assert len(df) == 6 and len(poster.calls) == 6
    assert (df["top1"] == 1.0).all() and np.allclose(df["kendall_tau"], 1.0)
    assert (df["model_id"] == MODEL_SPECS["gemini"]["openrouter_id"]).all()
    assert df["collected_utc"].notna().all() and (df["run"] == 1).all()
    payload = poster.calls[0]["payload"]
    assert payload["model"] == MODEL_SPECS["gemini"]["openrouter_id"]
    assert payload["provider"] == MODEL_SPECS["gemini"]["provider"]
    assert payload["max_tokens"] == SU.MAX_OUTPUT_TOKENS
    raw = H.read_jsonl(tmp_path / "gemini" / "AD_listwise_run_01_raw.jsonl")
    assert len(raw) == 6 and all(r["collected_utc"] and r["provider"] for r in raw)
    assert {r["scenario_id"] for r in raw} == {sc["scenario_id"] for sc in scs}

    # Resume: a complete run is skipped without a call.
    poster2 = H.Poster([H.ok("{}")])
    with mock.patch("requests.post", poster2):
        LW.run_one("gemini", 1, scs, ref, workers=2)
    assert poster2.calls == []


def test_invalid_reply_counts_as_a_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(LW, "output_dir_for", lambda mk: tmp_path / mk)
    scs = SCENARIOS[:3]
    poster = H.Poster([H.ok('{"ranking": ["nope"]}')])
    with mock.patch("requests.post", poster):
        df = pd.read_excel(LW.run_one("qwen", 1, scs, _reference_first_is_best(scs), workers=1))
    assert df["failed"].all() and (df["top1"] == 0.0).all() and (df["kendall_tau"] == 0.0).all()
    assert set(df["failure_type"]) == {LW.ERR_INVALID_RANKING}


def test_fatal_http_stops_and_writes_no_run_file(tmp_path, monkeypatch):
    monkeypatch.setattr(LW, "output_dir_for", lambda mk: tmp_path / mk)
    scs = SCENARIOS[:4]
    poster = H.Poster([H.FakeResponse(402, {"error": {"message": "insufficient credits"}})])
    with mock.patch("requests.post", poster), pytest.raises(SU.RunAbort):
        LW.run_one("deepseek", 1, scs, _reference_first_is_best(scs), workers=1)
    assert not (tmp_path / "deepseek" / "AD_listwise_run_01.xlsx").exists()


# ---------------------------------------------------------------------------
# Analysis, offline
# ---------------------------------------------------------------------------

def test_analyze_compares_with_pointwise_per_model(tmp_path, monkeypatch):
    monkeypatch.setattr(LW, "output_dir_for", lambda mk: tmp_path / mk)
    monkeypatch.setattr(LW, "OUTPUT_DIR", tmp_path / "analysis")
    rng = np.random.default_rng(3)

    def rows(n_runs, n, p_hit):
        return pd.DataFrame([{"run": r, "scenario_id": s, "decision_type": "HVAC",
                              "kendall_tau": float(rng.choice([-1.0, 1.0], p=[1 - p_hit, p_hit])),
                              "top1": float(rng.random() < p_hit), "top2": 1.0, "failed": False}
                             for r in range(1, n_runs + 1) for s in range(1, n + 1)])

    lw = rows(5, 60, 0.9)
    for r, g in lw.groupby("run"):
        SU._atomic_write_xlsx(g, tmp_path / "gemini" / f"AD_listwise_run_{r:02d}.xlsx")
    monkeypatch.setattr(PA, "load_reference", lambda: {})
    monkeypatch.setattr(PA, "main_suite_control_rows",
                        lambda mk, arch, runs, ref, scenario_ids=None: rows(runs, 60, 0.35))
    out = LW.analyze(["gemini", "qwen"])  # qwen has no runs and is skipped
    s = out["summary"]
    assert set(s["arm"]) == {"listwise", "pointwise"} and set(s["model"]) == {"gemini"}
    t = out["tests"]
    tested = t[t["metric"] != "top2"]
    assert set(tested["metric"]) == {"kendall_tau", "top1"}
    assert tested["p_holm"].notna().all() and tested["significant_holm"].all()
    # top2 is identical in both arms: its p is NaN and stays out of the Holm family.
    top2 = t[t["metric"] == "top2"].iloc[0]
    assert np.isnan(top2["p_value"]) and not top2["significant_holm"]
    assert (tested["p_holm"] >= tested["p_value"]).all()  # a family of two, not one
    assert (tmp_path / "analysis" / "listwise_summary.xlsx").exists()
