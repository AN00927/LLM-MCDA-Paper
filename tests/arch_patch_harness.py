"""Test harness for the installed architecture patch (2026-09 rerun).

Ported from Analysis/rerun_prep/arch_new/tests/harness.py; it now drives the
INSTALLED files: Architectures/*.py and the repo-root sentinel_utils.py.

No network, no paid calls:
  - OPENROUTER_API_KEY is forced to a dummy value before any module loads
    (load_dotenv never overrides an existing variable);
  - requests.Session.request is replaced with a function that raises, so any
    request that escapes the per-test requests.post mock fails loudly;
  - time.sleep is patched per test.

Pre-patch reference. A few tests compare the installed code against the code
it replaced (tie rounding, A_H key override, the A_H historical-response and
A_D/A_E synthetic regressions). That code is read, read-only, from git at
PREPATCH_COMMIT (`git show <commit>:<path>`), the last commit before the
install; the tests that need it skip if git or the commit is unavailable.
Set ARCH_PREPATCH_DIR to a folder holding the three pre-patch architecture
files to use a copy instead of git.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("ARCH_TEST_REPO") or HERE.parent)
ARCH_DIR = REPO / "Architectures"
PREPATCH_COMMIT = "19862aa"

os.environ["OPENROUTER_API_KEY"] = "test-dummy-key-no-network"
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.pop("RAG_TOP_K", None)

while str(REPO) in sys.path:
    sys.path.remove(str(REPO))
sys.path.insert(0, str(REPO))

import requests  # noqa: E402


def _no_network(*args, **kwargs):
    raise RuntimeError("NETWORK BLOCKED IN TESTS: an unmocked HTTP request was attempted")


requests.Session.request = _no_network

import sentinel_utils  # noqa: E402

assert Path(sentinel_utils.__file__).resolve().parent == REPO.resolve(), sentinel_utils.__file__
assert hasattr(sentinel_utils, "openrouter_chat"), "installed sentinel_utils lacks the patch"

ARCH_FILES = {
    "AD": "Direct_LLM_Scoring.py",
    "AE": "Example-Guided_LLM_Scoring.py",
    "AH": "LLM-Parameterized_Reference_Scoring.py",
}


def load_module(path: Path, as_file: Path, name: str):
    """Execute *path*'s source as a module whose __file__ is *as_file*."""
    mod = types.ModuleType(name)
    mod.__file__ = str(as_file)
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    sys.modules[name] = mod
    exec(code, mod.__dict__)
    return mod


def load_patched(key: str, tag: str = ""):
    """The installed (patched) architecture module."""
    fname = ARCH_FILES[key]
    return load_module(ARCH_DIR / fname, ARCH_DIR / fname, f"patched_{key}{tag}")


_PREPATCH_CACHE = {}


def prepatch_source(key: str):
    """Path to the pre-patch source of architecture *key*, or None."""
    fname = ARCH_FILES[key]
    if os.environ.get("ARCH_PREPATCH_DIR"):
        p = Path(os.environ["ARCH_PREPATCH_DIR"]) / fname
        return p if p.exists() else None
    if key in _PREPATCH_CACHE:
        return _PREPATCH_CACHE[key]
    try:
        blob = subprocess.run(
            ["git", "show", f"{PREPATCH_COMMIT}:Architectures/{fname}"],
            cwd=str(REPO), capture_output=True, check=True).stdout
    except Exception:
        _PREPATCH_CACHE[key] = None
        return None
    d = Path(tempfile.mkdtemp(prefix="arch_prepatch_"))
    p = d / fname
    p.write_bytes(blob)
    _PREPATCH_CACHE[key] = p
    return p


def load_prepatch(key: str):
    """The architecture module as it was before the install, executed as if it
    lived in Architectures/ (so PROJECT_ROOT resolves to the repo). It runs
    against the installed sentinel_utils, which only added names."""
    import pytest
    src = prepatch_source(key)
    if src is None:
        pytest.skip(f"pre-patch source for {key} unavailable (git show {PREPATCH_COMMIT})")
    fname = ARCH_FILES[key]
    return load_module(src, ARCH_DIR / fname, f"prepatch_{key}")


# ---------------------------------------------------------------------------
# Fake OpenRouter
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, body=None, text=None, bad_json=False):
        self.status_code = status_code
        self._body = body
        self._bad_json = bad_json
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")

    def json(self):
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return copy.deepcopy(self._body)


COST = 0.000321
MODEL_RETURNED = "google/gemini-3.8-flash-20260902"


def body(content, finish="stop", native=None, reasoning=None, cost=COST,
         reasoning_tokens=7, prompt_tokens=500, completion_tokens=40, gen_id="gen-abc123",
         provider="Google AI Studio"):
    return {
        "id": gen_id,
        "model": MODEL_RETURNED,
        "provider": provider,
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "finish_reason": finish,
            "native_finish_reason": native if native is not None else str(finish).upper(),
            "message": {"role": "assistant", "content": content, "reasoning": reasoning},
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": cost,
            "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
        },
    }


def ok(content, **kw):
    return FakeResponse(200, body(content, **kw))


class Poster:
    """Stand-in for requests.post. *script* is a list of FakeResponse /
    Exception instances consumed in order (the last one repeats), or a
    callable(payload) -> FakeResponse."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "payload": copy.deepcopy(json), "timeout": timeout})
        if callable(self.script):
            item = self.script(json)
        else:
            idx = min(len(self.calls) - 1, len(self.script) - 1)
            item = self.script[idx]
        if isinstance(item, BaseException):
            raise item
        return item


SCORES_JSON = '{"energy_cost": 0.6, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}'


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

ALT_COLS = ["alternative_1", "alternative_2", "alternative_3"]


def get_test_scenarios():
    """First Test scenario of each decision type, as (scenario_id, dict)."""
    from sentinel_utils import read_table_clean
    df = read_table_clean(REPO / "Scenario Files" / "TestScenarios.xlsx", keep_str_cols=ALT_COLS)
    out = {}
    for i, row in df.iterrows():
        dt = row["decision_type"]
        if dt not in out:
            out[dt] = (i + 1, row.to_dict())
    return out


def historical_ah_responses():
    """{scenario_id: response text} from one model's order-arm control run 1,
    used as realistic A_H extraction replies."""
    p = REPO / "Output Files Gemini 3.5 Flash" / "hybrid_order_reversal" / "AH_extraction_order_control_run_01_raw.jsonl"
    out = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                out[int(rec["scenario_id"])] = rec["response"]
    return out


# Pre-rerun collections only: GPT-OSS and Qwen were archived on 2026-09-27 (their
# folder names are reused by the rerun); the old DeepSeek and Gemini 3.5 folders are
# never written to again.
HISTORICAL_OUTPUT_DIRS = [
    REPO / "archive" / "2026-09_pre_rerun" / "Output Files GPT-OSS 20B",
    REPO / "archive" / "2026-09_pre_rerun" / "Output Files Qwen3.5 9B",
    REPO / "Output Files DeepSeek V4 Flash",
    REPO / "Output Files Gemini 3.5 Flash",
]


def iter_raw_jsonl():
    paths = [p for d in HISTORICAL_OUTPUT_DIRS for p in d.glob("**/*_raw.jsonl")]
    for p in sorted(paths):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield p, json.loads(line)


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ---------------------------------------------------------------------------
# Fake Chroma for A_E
# ---------------------------------------------------------------------------

EXEMPLAR_META = {
    "decision_type": "HVAC", "question": "What AC setpoint?", "location": "Lancaster, PA",
    "outdoor_temp": 90, "square_footage": 1500, "insulation": "Medium", "household_size": 3,
    "housing_type": "House", "house_age": "21-30 years", "r_value": 13, "seer": 14, "hvac_age": 10,
    "utility_budget": 150,
    "alt1": "72", "alt1_energy_cost": 0.3, "alt1_environmental": 0.3, "alt1_comfort": 0.9,
    "alt1_practicality": 0.8, "alt1_mavt": 0.5, "alt1_rank": 2,
    "alt2": "76", "alt2_energy_cost": 0.6, "alt2_environmental": 0.6, "alt2_comfort": 0.7,
    "alt2_practicality": 0.8, "alt2_mavt": 0.65, "alt2_rank": 1,
    "alt3": "80", "alt3_energy_cost": 0.9, "alt3_environmental": 0.9, "alt3_comfort": 0.2,
    "alt3_practicality": 0.4, "alt3_mavt": 0.6, "alt3_rank": 3,
}


class FakeEmbedder:
    def encode(self, text):
        import numpy as np
        return np.zeros(384, dtype="float32")


class FakeCollection:
    def __init__(self, mode="ok", k_available=1):
        self.mode = mode
        self.k_available = k_available
        self.queries = []

    def query(self, query_embeddings, n_results, where):
        self.queries.append({"n_results": n_results, "where": where})
        if self.mode == "raise":
            raise RuntimeError("simulated chroma backend failure")
        if self.mode == "empty":
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        n = min(n_results, self.k_available)
        md = dict(EXEMPLAR_META, decision_type=where["decision_type"])
        return {
            "ids": [[f"rag_{where['decision_type']}_{i}" for i in range(n)]],
            "documents": [["doc"] * n],
            "metadatas": [[md] * n],
            "distances": [[0.1234 + 0.01 * i for i in range(n)]],
        }

    def count(self):
        return 90
