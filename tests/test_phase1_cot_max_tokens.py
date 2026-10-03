"""Mocked tests for the cot_scaffold max_tokens lookup added 2026-09-27:

  - COT arm sends min(32768, the pinned endpoint's max_completion_tokens);
  - every other arm (and every non-CoT architecture cell) keeps
    sentinel_utils.MAX_OUTPUT_TOKENS (8192) unchanged;
  - the free GET lookup failing (network error, bad status, no match, null
    max_completion_tokens) aborts with a clear RuntimeError rather than
    silently falling back;
  - --cot-max-tokens (resolve_cot_max_tokens(..., override=N)) skips the GET
    entirely and applies min(32768, N) to every requested model;
  - the raw log records the per-arm cap actually sent, for both a real POST
    and the no-call RAG-retrieval-failure path.

No network: requests.get and requests.post are both mocked; arch_patch_harness
blocks anything unmocked via requests.Session.request.
"""
import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest
import requests

import arch_patch_harness as H
from llm_mcda.common import sentinel_utils as SU
from llm_mcda.common.model_config import MODEL_SPECS

EXP = H.REPO / "scripts" / "experiments"


def _load_pa():
    spec = importlib.util.spec_from_file_location("phase1_prompt_ablation", EXP / "run_prompt_ablation_experiments.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["phase1_prompt_ablation"] = m
    spec.loader.exec_module(m)
    return m


PA = _load_pa()
GEMINI = MODEL_SPECS["gemini"]["openrouter_id"]
QWEN = MODEL_SPECS["qwen"]["openrouter_id"]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    SU._consecutive_api_failures = 0
    PA._ABORT.clear()
    PA.RAW_LOG.stop()
    PA.COT_MAX_TOKENS.clear()
    yield
    PA.RAW_LOG.stop()
    PA._ABORT.clear()
    PA.COT_MAX_TOKENS.clear()
    SU._consecutive_api_failures = 0


# ---------------------------------------------------------------------------
# Fake /endpoints GET
# ---------------------------------------------------------------------------

class GetResponse:
    def __init__(self, status_code=200, body=None, bad_json=False):
        self.status_code = status_code
        self._body = body
        self._bad_json = bad_json
        self.text = "" if body is None else str(body)

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._body


def endpoint_entry(tag, max_completion_tokens, **extra):
    provider_name, _, quantization = tag.partition("/")
    entry = {
        "tag": tag,
        "provider_name": provider_name,
        "quantization": quantization,
        "max_completion_tokens": max_completion_tokens,
        "supported_parameters": ["temperature", "reasoning", "max_tokens"],
    }
    entry.update(extra)
    return entry


def endpoints_body(entries):
    return {"data": {"endpoints": entries}}


class Getter:
    """Stand-in for requests.get. *script* maps a substring of the URL to a
    GetResponse (or raises if it's an Exception instance)."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def __call__(self, url, timeout=None):
        self.calls.append(url)
        for key, item in self.script.items():
            if key in url:
                if isinstance(item, BaseException):
                    raise item
                return item
        raise AssertionError(f"no script entry matches {url}")


def gptoss_url():
    return "https://openrouter.ai/api/v1/models/openai/gpt-oss-20b/endpoints"


def qwen_url():
    return "https://openrouter.ai/api/v1/models/qwen/qwen3.5-9b/endpoints"


# ---------------------------------------------------------------------------
# resolve_cot_max_tokens: happy path, capping, no-match, null cap, bad status,
# network error, bad json
# ---------------------------------------------------------------------------

def test_cot_cap_uses_endpoint_value_under_ceiling():
    getter = Getter({"gpt-oss-20b": GetResponse(200, endpoints_body([
        endpoint_entry("akashml/fp4", 8192),
        endpoint_entry("darkbloom/fp8", 20000),
    ]))})
    with mock.patch("requests.get", getter):
        out = PA.resolve_cot_max_tokens(["gptoss"])
    assert out == {"gptoss": 20000}
    assert PA.COT_MAX_TOKENS["gptoss"] == 20000
    assert getter.calls == [gptoss_url()]


def test_cot_cap_is_capped_at_32768():
    getter = Getter({"gpt-oss-20b": GetResponse(200, endpoints_body([
        endpoint_entry("darkbloom/fp8", 65536),
    ]))})
    with mock.patch("requests.get", getter):
        out = PA.resolve_cot_max_tokens(["gptoss"])
    assert out == {"gptoss": PA.COT_MAX_TOKENS_CAP} == {"gptoss": 32768}


def test_cot_cap_matches_by_provider_name_and_quantization_when_tag_blank():
    """Some /endpoints entries may not carry `tag`; provider_name/quantization
    is the fallback match."""
    getter = Getter({"qwen3.5-9b": GetResponse(200, endpoints_body([
        {"tag": "", "provider_name": "Venice", "quantization": "fp8",
         "max_completion_tokens": 32768},
    ]))})
    with mock.patch("requests.get", getter):
        out = PA.resolve_cot_max_tokens(["qwen"])
    assert out == {"qwen": 32768}


@pytest.mark.parametrize("break_it", [
    "network_error", "bad_status", "no_endpoints", "no_match", "null_cap", "bad_json",
])
def test_cot_lookup_failure_aborts(break_it):
    if break_it == "network_error":
        script = {"gpt-oss-20b": requests.exceptions.ConnectionError("blocked")}
    elif break_it == "bad_status":
        script = {"gpt-oss-20b": GetResponse(500, {"error": "server error"})}
    elif break_it == "no_endpoints":
        script = {"gpt-oss-20b": GetResponse(200, endpoints_body([]))}
    elif break_it == "no_match":
        script = {"gpt-oss-20b": GetResponse(200, endpoints_body([
            endpoint_entry("akashml/fp4", 8192),  # not the pinned darkbloom/fp8
        ]))}
    elif break_it == "null_cap":
        script = {"gpt-oss-20b": GetResponse(200, endpoints_body([
            endpoint_entry("darkbloom/fp8", None),
        ]))}
    else:  # bad_json
        script = {"gpt-oss-20b": GetResponse(200, bad_json=True)}

    getter = Getter(script)
    with mock.patch("requests.get", getter), pytest.raises(RuntimeError, match="cot_scaffold max_tokens lookup FAILED"):
        PA.resolve_cot_max_tokens(["gptoss"])
    assert PA.COT_MAX_TOKENS == {}  # nothing collected as a side effect of the aborted lookup


def test_cot_lookup_never_falls_back_silently_on_partial_failure():
    """Two models requested, the first fails: the second's cap must not be
    silently substituted or defaulted -- the whole resolution aborts."""
    getter = Getter({
        "gpt-oss-20b": GetResponse(404, {"error": "not found"}),
        "qwen3.5-9b": GetResponse(200, endpoints_body([endpoint_entry("venice/fp8", 32768)])),
    })
    with mock.patch("requests.get", getter), pytest.raises(RuntimeError):
        PA.resolve_cot_max_tokens(["gptoss", "qwen"])
    assert "qwen" not in PA.COT_MAX_TOKENS


# ---------------------------------------------------------------------------
# --cot-max-tokens override: skips the GET entirely
# ---------------------------------------------------------------------------

def test_cot_override_skips_the_get_and_is_capped():
    def poison(*a, **kw):
        raise AssertionError("requests.get must not be called when --cot-max-tokens overrides")
    with mock.patch("requests.get", poison):
        out = PA.resolve_cot_max_tokens(["gptoss", "qwen"], override=99999)
    assert out == {"gptoss": 32768, "qwen": 32768}  # capped at COT_MAX_TOKENS_CAP

    with mock.patch("requests.get", poison):
        out2 = PA.resolve_cot_max_tokens(["gptoss"], override=5000)
    assert out2["gptoss"] == 5000  # re-resolving overwrites the earlier value


# ---------------------------------------------------------------------------
# Wire: cot_scaffold sends the resolved cap; every other arm sends 8192
# ---------------------------------------------------------------------------

def pa_scenario(dt="HVAC"):
    sid, sc = H.get_test_scenarios()[dt]
    return dict(sc, scenario_id=sid)


def test_control_arm_sends_default_8192(tmp_path):
    raw = tmp_path / "control_raw.jsonl"
    PA.RAW_LOG.start(raw, run=1)
    poster = H.Poster([H.ok(H.SCORES_JSON)])
    try:
        with mock.patch("requests.post", poster):
            PA.score_scenario(pa_scenario(), "AD", PA.VARIANT_SPECS["control"], GEMINI, "gemini")
    finally:
        PA.RAW_LOG.stop()
    assert poster.calls, "no POST made"
    for c in poster.calls:
        assert c["payload"]["max_tokens"] == SU.MAX_OUTPUT_TOKENS == 8192
    for r in H.read_jsonl(raw):
        assert r["max_tokens"] == 8192
        assert r["request_params"]["max_tokens"] == 8192


def test_cot_scaffold_sends_resolved_cap(tmp_path):
    getter = Getter({"gpt-oss-20b": GetResponse(200, endpoints_body([
        endpoint_entry("darkbloom/fp8", 20000),
    ]))})
    with mock.patch("requests.get", getter):
        PA.resolve_cot_max_tokens(["gptoss"])
    assert PA.COT_MAX_TOKENS["gptoss"] == 20000

    raw = tmp_path / "cot_raw.jsonl"
    PA.RAW_LOG.start(raw, run=1)
    poster = H.Poster([H.ok(H.SCORES_JSON)])
    gptoss_id = MODEL_SPECS["gptoss"]["openrouter_id"]
    try:
        with mock.patch("requests.post", poster):
            PA.score_scenario(pa_scenario(), "AD", PA.VARIANT_SPECS["cot_scaffold"],
                              gptoss_id, "gptoss")
    finally:
        PA.RAW_LOG.stop()
    for c in poster.calls:
        assert c["payload"]["max_tokens"] == 20000
        assert c["payload"]["model"] == gptoss_id
    for r in H.read_jsonl(raw):
        assert r["max_tokens"] == 20000
        assert r["request_params"]["max_tokens"] == 20000


def test_cot_scaffold_capped_at_32768_on_the_wire(tmp_path):
    with mock.patch("requests.get", lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("must not call the GET when overridden"))):
        PA.resolve_cot_max_tokens(["qwen"], override=200000)
    assert PA.COT_MAX_TOKENS["qwen"] == 32768

    poster = H.Poster([H.ok(H.SCORES_JSON)])
    with mock.patch("requests.post", poster):
        PA.score_scenario(pa_scenario(), "AD", PA.VARIANT_SPECS["cot_scaffold"], QWEN, "qwen")
    for c in poster.calls:
        assert c["payload"]["max_tokens"] == 32768


def test_cot_scaffold_without_resolved_cap_raises_rather_than_defaulting(tmp_path):
    """If main() didn't call resolve_cot_max_tokens first (a bug), scoring a
    cot_scaffold cell must fail loudly, never silently send 8192."""
    with pytest.raises(RuntimeError, match="not resolved"):
        PA.score_scenario(pa_scenario(), "AD", PA.VARIANT_SPECS["cot_scaffold"], GEMINI, "gemini")


def test_non_cot_arms_unaffected_by_a_resolved_cot_cap(tmp_path):
    """Resolving a cot_scaffold cap for a model must not change what its other
    arms send."""
    with mock.patch("requests.get", lambda *a, **kw: (_ for _ in ()).throw(AssertionError)):
        PA.resolve_cot_max_tokens(["gptoss"], override=32768)
    gptoss_id = MODEL_SPECS["gptoss"]["openrouter_id"]
    for variant_id in ("control", "no_anchors"):
        poster = H.Poster([H.ok(H.SCORES_JSON)])
        with mock.patch("requests.post", poster):
            PA.score_scenario(pa_scenario(), "AD", PA.VARIANT_SPECS[variant_id],
                              gptoss_id, "gptoss")
        for c in poster.calls:
            assert c["payload"]["max_tokens"] == 8192, variant_id


def test_ae_rag_retrieval_failure_still_logs_the_intended_cap(tmp_path, monkeypatch):
    """No API call is made on this path, but the cap the arm WOULD have sent
    is still per-arm-known and recorded."""
    with mock.patch("requests.get", lambda *a, **kw: (_ for _ in ()).throw(AssertionError)):
        PA.resolve_cot_max_tokens(["gemini"], override=15000)
    ae = H.load_patched("AE", tag="_phase1_cap")
    ae.chroma_collection, ae.embedding_model = H.FakeCollection(mode="empty"), H.FakeEmbedder()
    monkeypatch.setattr(PA, "_ae_module", ae)

    raw = tmp_path / "ae_cot_raw.jsonl"
    PA.RAW_LOG.start(raw, run=1)
    poster = H.Poster([H.ok(H.SCORES_JSON)])
    try:
        with mock.patch("requests.post", poster):
            res = PA.score_scenario(pa_scenario(), "AE", PA.VARIANT_SPECS["cot_scaffold"],
                                    GEMINI, "gemini")
    finally:
        PA.RAW_LOG.stop()
    assert len(poster.calls) == 0
    for r in H.read_jsonl(raw):
        assert r["max_tokens"] == 15000
        assert r["api_called"] is False
