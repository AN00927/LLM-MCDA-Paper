"""Prompt-sensitivity ablation for A_D (direct scoring) and A_E (example-guided).

Tests whether A_D's and A_E's poor rank recovery is an artifact of the specific
prompt they ship with, rather than a property of direct LLM scoring. Variants:

  control      -- the shipped prompt, unmodified. NOT collected by default
                  (author decision 2026-09-27): its messages are byte-identical
                  to the main suite's (checked at startup by
                  _assert_control_is_main_suite), so the significance script
                  reads main-suite runs 1..N as the control cell instead of
                  paying for the same calls twice. Pass --variants control to
                  collect it anyway (smoke tests, harness checks).
  no_anchors   -- per-criterion good/moderate/poor calibration anchors stripped
                  from the system prompt, leaving criterion names and the scale.
                  A_D only (A_E ships without anchors).
  cot_scaffold -- an explicit reasoning scaffold before the JSON answer.

The 0-10 response-scale variant was cut on 2026-09-27 (author decision).
Every cell runs PROMPT_ABLATION_RUNS = 3 times by default, fixed in advance,
with no top-up runs.

This script NEVER edits the architecture files. The shipped A_D system prompt is
hardcoded inline in `score_alternative()` and A_E's in
`score_alternative_with_rag()`; both must keep producing the main-text results
byte-for-byte. So the prompts are re-declared here and the variant transforms
are applied to these local copies. `_assert_control_matches_shipped()` guards
the copies against drift by diffing them against the live architecture modules
at startup -- if someone edits an architecture prompt, this script fails loudly
instead of silently ablating a stale baseline.

Retry policy, temperature, timeout and the reasoning payload all come from
`model_config`, so `latency_ms` and failure semantics match the main runs.
Sentinel 1928 marks any failed or invalid score; it never enters a mean or a
ranking and is never replaced by a neutral default.

Outputs route to the required safe `--output-dir` (or
`LLM_MCDA_RUN_OUTPUT_DIR`) and never touch frozen paths.
Resume-aware per (variant, architecture, model, run).
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap the checkout's src/ package before importing llm_mcda.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from llm_mcda.common.paths import (
    RUN_OUTPUT_DIR_ENV,
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_directory,
)
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from scipy.stats import kendalltau

from llm_mcda.common.model_config import (
    MAX_RETRIES,
    MAX_RETRY_BACKOFF,
    MODEL_SPECS,
    N_RUNS,
    REQUEST_TIMEOUT,
    RETRY_BASE_DELAY,
    TEMPERATURE,
    TIE_BREAK_PRIORITY,
    TRANSIENT_HTTP_STATUS_CODES,
    _is_transient_http_status,
    get_reasoning_payload,
)
from llm_mcda.common.sentinel_utils import (
    CRITERIA,
    FAILED_API_BAD_REQUEST,
    FAILED_TRUNCATED,
    MAX_OUTPUT_TOKENS,
    SENTINEL_FLOAT,
    RawCallLog,
    RunAbort,
    apply_mavt_ranking,
    build_openrouter_payload,
    call_log_fields,
    extract_json_object,
    is_numeric_score,
    openrouter_chat,
    read_table_clean,
    response_meta,
)

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

TEST_SCENARIOS = PROJECT_ROOT / "workbooks/scenarios" / "TestScenarios.xlsx"
GROUND_TRUTH_DIR = PROJECT_ROOT / "workbooks/ground_truth"

logger = logging.getLogger("prompt_ablation")

# Per-call raw archive, same mechanism as the architectures (sentinel_utils.RawCallLog).
# Disabled unless .start() is called; each cell's run gets its own jsonl. Workers
# call .record() concurrently, so the file write is serialised by this lock and
# scenario_id is passed explicitly per call rather than via .set_scenario(), which
# is not thread-safe.
RAW_LOG = RawCallLog()
_raw_log_lock = threading.Lock()

# Set when any worker hits a RunAbort (HTTP 401/402/403, or the shared
# consecutive-failure breaker in sentinel_utils.openrouter_chat). Every worker
# checks it before each call, and the pool cancels queued scenarios, so an
# out-of-credit run stops paying at once instead of draining the queue.
_ABORT = threading.Event()

# Parse-error codes for a call that returned no usable completion. Lower-case,
# like the rest of this script's codes.
ERR_API_EXHAUSTED = "failed_api_exhausted"
ERR_API_BAD_REQUEST = "failed_api_bad_request"
ERR_TRUNCATED = "failed_truncated"
ERR_EMPTY = "failed_empty_response"
ERR_RAG_RETRIEVAL = "failed_rag_retrieval"


# ---------------------------------------------------------------------------
# Shipped prompts, re-declared (see module docstring for why)
# ---------------------------------------------------------------------------

# Byte-identical to Direct_LLM_Scoring.score_alternative's system_prompt.
AD_SYSTEM_PROMPT = """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
    You consistently utilize all information given in the scenario context. Score alternatives on four criteria using the inclusive 0-1 scale (0.0 <= score <= 1.0):

HVAC:
- energy_cost: good when the setpoint demands little from the system given outdoor
  conditions; moderate when the system must work harder; poor when the
  setpoint requires extreme effort.
- environmental: good when the system runs efficiently; moderate when
  runtime and load are average; poor when high load drives sustained high emissions.
- comfort: good when the setpoint feels comfortable for the outdoor temperature;
  moderate when slightly outside typical preference; poor when noticeably too
  hot or cold.
- practicality: good when the setpoint is easy for the user and system to maintain without
  strain; moderate when borderline; poor when extreme enough to risk override or
  system stress.

Appliance (scheduling):
- energy_cost: good during off-peak rate hours; moderate in shoulder periods;
  poor when scheduled during peak pricing windows.
- environmental: good when grid emissions are low (typically overnight);
  moderate during shoulder hours; poor when peak-period generation is dirtiest.
- comfort: good when the appliance is available with little or no delay; moderate
  when availability is pushed later into the evening; poor when results are not
  ready until the following morning.
- practicality: good when scheduling is easy to remember and socially unobtrusive;
  moderate when timing requires some planning; poor when running in the middle of
  the night creates noise or coordination difficulty.

Shower (duration):
- energy_cost: good when short; worsens continuously as duration increases.
- environmental: good when water volume used is low; worsens continuously as
  duration increases.
- comfort: good near a typical shower length; poor when too short to feel adequate
  or long enough to feel wasteful.
- practicality: good when the duration is sustainable as a daily habit; poor when
  too short to realistically maintain or long enough to cause hot water contention.

Return ONLY: {"energy_cost": X, "environmental": X, "comfort": X, "practicality": X} where each X is between 0.0 and 1.0. You must distinguish between the criteria: do not assign the same score to all 4 criteria for an alternative unless performance is actually identical across them.
"""

# Byte-identical to Example-Guided_LLM_Scoring.build_system_prompt()'s return.
# A_E deliberately ships WITHOUT per-criterion anchors because RAG supplies
# scored in-context examples instead.
AE_SYSTEM_PROMPT = """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
    You consistently utilize all information given in the scenario context. Score alternatives on four criteria using the inclusive 0-1 scale (0.0 <= score <= 1.0):
1. Energy Cost: Lower energy costs = higher score
2. Environmental Impact: Lower emissions = higher score
3. Comfort: Higher user comfort = higher score
4. Practicality: Easier to implement/maintain = higher score


Return ONLY: {"energy_cost": X, "environmental": X, "comfort": X, "practicality": X} where each X is between 0.0 and 1.0. You must distinguish between the criteria: do not assign the same score to all 4 criteria for an alternative unless performance is actually identical across them.
"""

# The anchor-free system prompt for A_D's `no_anchors` arm. Criterion names and
# the 0-1 scale are kept; the per-decision-type good/moderate/poor calibration
# text is what gets removed.
AD_SYSTEM_PROMPT_NO_ANCHORS = """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
    You consistently utilize all information given in the scenario context. Score alternatives on four criteria using the inclusive 0-1 scale (0.0 <= score <= 1.0):
1. Energy Cost: Lower energy costs = higher score
2. Environmental Impact: Lower emissions = higher score
3. Comfort: Higher user comfort = higher score
4. Practicality: Easier to implement/maintain = higher score

Return ONLY: {"energy_cost": X, "environmental": X, "comfort": X, "practicality": X} where each X is between 0.0 and 1.0. You must distinguish between the criteria: do not assign the same score to all 4 criteria for an alternative unless performance is actually identical across them.
"""

COT_SCAFFOLD = """
Before answering, reason explicitly through these steps:
Step 1. For each of the four criteria, state how this alternative performs given the scenario context.
Step 2. State which criteria this alternative is relatively strong on and which it is relatively weak on.
Step 3. Compare it against the other listed alternatives on each criterion.
Step 4. Convert each judgement to a number on the scale, keeping the criteria distinct.

Write your reasoning first, then on the final line return ONLY the JSON object.
"""


VARIANT_SPECS = OrderedDict([
    ("control", {
        "label": "Control (shipped prompt)",
        "scale_max": 1.0,
        "cot": False,
        "system": {"AD": AD_SYSTEM_PROMPT, "AE": AE_SYSTEM_PROMPT},
    }),
    ("no_anchors", {
        "label": "Calibration anchors removed",
        "scale_max": 1.0,
        "cot": False,
        # A_E ships with no anchors, so its prompt is unchanged here and its
        # no_anchors arm is definitionally identical to control. Reported rather
        # than hidden: see NO_ANCHORS_AE_NOTE.
        "system": {"AD": AD_SYSTEM_PROMPT_NO_ANCHORS, "AE": AE_SYSTEM_PROMPT},
    }),
    ("cot_scaffold", {
        "label": "Explicit reasoning scaffold",
        "scale_max": 1.0,
        "cot": True,
        "system": {"AD": AD_SYSTEM_PROMPT + COT_SCAFFOLD,
                   "AE": AE_SYSTEM_PROMPT + COT_SCAFFOLD},
    }),
])

# Variants collected when --variants is not given: control comes from the main
# suite (see module docstring).
DEFAULT_VARIANTS = [v for v in VARIANT_SPECS if v != "control"]

# Runs per cell, fixed in advance (author decision 2026-09-27). Deliberately not
# N_RUNS: the main suite keeps 5 runs, and runs 1..PROMPT_ABLATION_RUNS of it are
# the control cell.
PROMPT_ABLATION_RUNS = 3

NO_ANCHORS_AE_NOTE = (
    "A_E's shipped system prompt contains no per-criterion calibration anchors "
    "(RAG supplies scored exemplars instead), so for A_E the no_anchors arm is "
    "identical to control by construction and is skipped rather than billed twice."
)

ARCHITECTURES = OrderedDict([
    ("AD", {"label": "Direct LLM scoring", "rag": False}),
    ("AE", {"label": "Example-guided (RAG) scoring", "rag": True}),
])


# ---------------------------------------------------------------------------
# cot_scaffold max_tokens: raised per model from the pinned endpoint's own
# limit (2026-09-27 author decision). Every other arm, and both architectures'
# non-CoT cells, keep sentinel_utils.MAX_OUTPUT_TOKENS (8192) unchanged.
# ---------------------------------------------------------------------------

# Hard ceiling regardless of what an endpoint reports.
COT_MAX_TOKENS_CAP = 32768

# Populated once per run by resolve_cot_max_tokens(), before any cot_scaffold
# cell is collected: {model_key: max_tokens to send for that model's CoT arm}.
COT_MAX_TOKENS: Dict[str, int] = {}

OPENROUTER_ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{author}/{slug}/endpoints"


def _pinned_provider_tag(model_key: str) -> str:
    """The single provider *MODEL_SPECS[model_key]["provider"]["only"]* pins
    (e.g. "darkbloom/fp8"): the string an /endpoints entry must match."""
    only = (MODEL_SPECS[model_key].get("provider") or {}).get("only") or []
    if len(only) != 1:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup: MODEL_SPECS['{model_key}']['provider']['only'] "
            f"must pin exactly one provider to know which /endpoints entry to read; got {only!r}."
        )
    return only[0]


def _endpoint_matches_pin(endpoint: Dict, tag: str) -> bool:
    """True if an OpenRouter /endpoints entry is the pinned provider.

    Matched on the entry's own `tag` field first (the documented identity for
    an endpoint); if that field is absent or blank, falls back to
    `<provider_name>/<quantization>` lower-cased, which is the same string
    shape the pin itself uses (e.g. "darkbloom/fp8").
    """
    tag = tag.strip().lower()
    ep_tag = str(endpoint.get("tag") or "").strip().lower()
    if ep_tag:
        return ep_tag == tag
    provider_name = str(endpoint.get("provider_name") or "").strip().lower()
    quantization = str(endpoint.get("quantization") or "").strip().lower()
    return f"{provider_name}/{quantization}" == tag


def _fetch_endpoint_max_completion_tokens(model_key: str) -> int:
    """GET the pinned endpoint's max_completion_tokens for *model_key* from
    OpenRouter's free, keyless `/api/v1/models/<author>/<slug>/endpoints`.

    Raises RuntimeError with a clear ASCII message on any failure -- network
    error, non-200 status, unparseable body, no endpoint matching the pinned
    provider tag, or a null max_completion_tokens -- rather than silently
    falling back to a default cap.
    """
    model_id = MODEL_SPECS[model_key]["openrouter_id"]
    base_id = model_id.split(":", 1)[0]  # strip ":floor" (or any other suffix)
    if "/" not in base_id:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"cannot split '{base_id}' into author/slug for the OpenRouter /endpoints URL."
        )
    author, slug = base_id.split("/", 1)
    url = OPENROUTER_ENDPOINTS_URL.format(author=author, slug=slug)
    tag = _pinned_provider_tag(model_key)
    how_to_fix = ("Pass --cot-max-tokens N to override (still capped at "
                  f"{COT_MAX_TOKENS_CAP}), or fix the cause before collecting cot_scaffold cells.")

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"GET {url} raised {type(exc).__name__}: {exc}. {how_to_fix}"
        ) from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"GET {url} returned HTTP {resp.status_code}. {how_to_fix}"
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"GET {url} returned a body that is not valid JSON. {how_to_fix}"
        ) from exc

    endpoints = ((body or {}).get("data") or {}).get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"GET {url} returned no endpoints. {how_to_fix}"
        )

    matches = [ep for ep in endpoints if isinstance(ep, dict) and _endpoint_matches_pin(ep, tag)]
    if not matches:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"no entry in GET {url} matches the pinned provider '{tag}'. {how_to_fix}"
        )

    max_completion_tokens = matches[0].get("max_completion_tokens")
    if max_completion_tokens is None:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"the pinned endpoint '{tag}' reports max_completion_tokens = null. {how_to_fix}"
        )
    try:
        return int(max_completion_tokens)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"cot_scaffold max_tokens lookup FAILED for model '{model_key}' ({model_id}): "
            f"max_completion_tokens={max_completion_tokens!r} is not an integer. {how_to_fix}"
        ) from exc


def resolve_cot_max_tokens(model_keys: List[str], override: Optional[int] = None) -> Dict[str, int]:
    """Populate and return COT_MAX_TOKENS for *model_keys*: the max_tokens to
    send on every cot_scaffold call for that model, min(COT_MAX_TOKENS_CAP,
    the pinned endpoint's max_completion_tokens). Run once per model at the
    start of the prompt-ablation run, before any cot_scaffold cell is
    collected; every other arm keeps sentinel_utils.MAX_OUTPUT_TOKENS.

    With *override* given (the --cot-max-tokens CLI flag), every model gets
    min(COT_MAX_TOKENS_CAP, override) and the network lookup is skipped
    entirely -- the author's escape hatch when the free GET is unavailable.
    Otherwise each model_key's cap is fetched fresh (not cached across calls),
    so a rerun in the same process reflects the endpoint's current state; a
    failed lookup raises and aborts before any cot_scaffold cell runs.
    """
    for model_key in model_keys:
        if override is not None:
            cap = min(COT_MAX_TOKENS_CAP, int(override))
        else:
            cap = min(COT_MAX_TOKENS_CAP, _fetch_endpoint_max_completion_tokens(model_key))
        COT_MAX_TOKENS[model_key] = cap
        logger.info("cot_scaffold max_tokens for %s: %s", model_key, cap)
    return dict(COT_MAX_TOKENS)


def _assert_control_matches_shipped() -> None:
    """Fail loudly if an architecture's shipped prompt has drifted from the copy
    above. Compares whitespace-normalised text, so reflowing a line is tolerated
    but a wording or anchor change is not."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    ad_src = (PROJECT_ROOT / "src/llm_mcda/architectures" / "Direct_LLM_Scoring.py").read_text(encoding="utf-8")
    ae_src = (PROJECT_ROOT / "src/llm_mcda/architectures" / "Example-Guided_LLM_Scoring.py").read_text(encoding="utf-8")

    problems = []
    # Anchor on distinctive sentences rather than trying to re-parse the files.
    ad_probe = "good when the setpoint demands little from the system given outdoor"
    if norm(ad_probe) not in norm(ad_src):
        problems.append("A_D anchor text not found in Direct_LLM_Scoring.py")
    if norm(ad_probe) not in norm(AD_SYSTEM_PROMPT):
        problems.append("A_D anchor text missing from this script's copy")

    ae_probe = "1. Energy Cost: Lower energy costs = higher score"
    if norm(ae_probe) not in norm(ae_src):
        problems.append("A_E criterion list not found in Example-Guided_LLM_Scoring.py")

    tail = ("You must distinguish between the criteria: do not assign the same score to all 4 "
            "criteria for an alternative unless performance is actually identical across them.")
    for name, src in (("Direct_LLM_Scoring.py", ad_src), ("Example-Guided_LLM_Scoring.py", ae_src)):
        if norm(tail) not in norm(src):
            problems.append(f"anti-clustering instruction not found in {name}")

    if problems:
        raise RuntimeError(
            "Shipped prompts have drifted from this script's copies:\n  - "
            + "\n  - ".join(problems)
            + "\nUpdate the constants in run_prompt_ablation_experiments.py before running, or the "
              "ablation will be measured against a stale baseline."
        )


class _CapturedMessages(BaseException):
    """Raised by a stubbed query function to stop an architecture right after it
    has built its messages. A BaseException, so the architectures' own
    `except Exception` handlers cannot swallow it."""

    def __init__(self, messages):
        super().__init__("captured")
        self.messages = messages


def _capture_stub(*args, **kwargs):
    messages = args[0] if args else kwargs.get("messages")
    raise _CapturedMessages(messages)


def _load_direct_module():
    import importlib.util
    path = PROJECT_ROOT / "src/llm_mcda/architectures" / "Direct_LLM_Scoring.py"
    spec = importlib.util.spec_from_file_location("direct_llm_scoring_for_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main_suite_messages(architecture: str, scenario: Dict, alternative: str) -> List[Dict]:
    """The exact messages the installed main-suite architecture would send for
    one (scenario, alternative), captured by stubbing its query function. No
    API call is made."""
    if ARCHITECTURES[architecture]["rag"]:
        module, fn = _load_ae_module(), "score_alternative_with_rag"
    else:
        module, fn = _load_direct_module(), "score_alternative"
    original = module.query_openrouter
    module.query_openrouter = _capture_stub
    try:
        getattr(module, fn)(scenario, alternative)
    except _CapturedMessages as captured:
        return captured.messages
    finally:
        module.query_openrouter = original
    raise RuntimeError(f"{architecture}: the architecture returned without calling its query "
                       f"function (for A_E, retrieval found no exemplar).")


def _assert_control_is_main_suite(architectures: List[str]) -> None:
    """Fail loudly unless this script's control messages equal the installed
    architectures' byte for byte, on the first test scenario of each decision
    type and every alternative. That equality is what lets the significance
    script use main-suite runs as the control cell (author decision
    2026-09-27); the other variants then differ from the main suite only in
    their system prompt."""
    scenarios = load_scenarios(None, 13)
    firsts = {}
    for sc in scenarios:
        firsts.setdefault(sc.get("decision_type"), sc)
    problems = []
    for arch in architectures:
        for dtype, sc in firsts.items():
            for i in (1, 2, 3):
                alt = str(sc.get(f"alternative_{i}"))
                ours = build_messages(arch, VARIANT_SPECS["control"], sc, alt)
                theirs = main_suite_messages(arch, sc, alt)
                if ours != theirs:
                    problems.append(f"{arch} {dtype} scenario {sc['scenario_id']} alternative {alt!r}")
    if problems:
        raise RuntimeError(
            "Control messages differ from the installed main suite's, so main-suite runs "
            "cannot stand in for the control cell:\n  - " + "\n  - ".join(problems))


MAIN_SUITE_FILE_STEM = {"AD": "Direct_LLM_Scoring", "AE": "Example-Guided_LLM_Scoring"}


def main_suite_run_path(model_key: str, architecture: str, run_idx: int) -> Path:
    """Per-run workbook of the main suite (k = 1, untagged A_E files only)."""
    return (PROJECT_ROOT / MODEL_SPECS[model_key]["output_folder"]
            / f"{MAIN_SUITE_FILE_STEM[architecture]}_results_run_{run_idx:02d}.xlsx")


def main_suite_control_rows(model_key: str, architecture: str, runs: int,
                            reference: Dict[int, Dict],
                            scenario_ids: Optional[List[int]] = None) -> pd.DataFrame:
    """The control cell rebuilt from main-suite runs 1..runs, scored with this
    script's own scenario_metrics, so control and variant rows are computed by
    the same code. The main suite parses replies with the same rule as this
    script (sentinel_utils.extract_json_object and is_numeric_score). Columns match run_cell's rows for everything the summary and the
    significance tests read. A missing run file raises: a partial control
    would bias every comparison against it."""
    rows = []
    for run_idx in range(1, runs + 1):
        path = main_suite_run_path(model_key, architecture, run_idx)
        if not path.exists():
            raise FileNotFoundError(
                f"Main-suite run {run_idx} for {model_key}/{architecture} not found at {path}. "
                f"The prompt-ablation control comes from main-suite runs 1..{runs}; collect them first.")
        df = read_table_clean(path, keep_str_cols=["alternative"])
        for sid, g in df.groupby("scenario_id", sort=True):
            sid = int(sid)
            if scenario_ids is not None and sid not in scenario_ids:
                continue
            scored = [{"alternative": str(r["alternative"]), **{c: float(r[c]) for c in CRITERIA}}
                      for _, r in g.iterrows()]
            result = {"scored": scored, "ranking": apply_mavt_ranking(scored)}
            metrics = scenario_metrics(result, reference.get(sid))
            valid = [a for a in scored if not any(a[c] == SENTINEL_FLOAT for c in CRITERIA)]
            rows.append({
                "variant": "control",
                "variant_label": VARIANT_SPECS["control"]["label"] + " [main-suite run]",
                "architecture": architecture, "model": model_key,
                "model_id": str(g["model_id"].iloc[0]) if "model_id" in g else "",
                "run": run_idx,
                "collected_utc": str(g["collected_utc"].iloc[0]) if "collected_utc" in g else "",
                "scenario_id": sid,
                "decision_type": str(g["decision_type"].iloc[0]),
                "alt_scores_json": json.dumps([{**a, "rank": r} for a, r in
                                               zip(scored, result["ranking"]["ranks"])]),
                "kendall_tau": metrics["kendall_tau"], "top1": metrics["top1"],
                "top2": metrics["top2"], "failed": metrics["failed"],
                "pred_top1": metrics["pred_top1"],
                "total_tokens": np.nan,
                "mean_criterion_sd": float(np.mean([np.std([a[c] for c in CRITERIA]) for a in valid]))
                                     if valid and not metrics["failed"] else np.nan,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

# Kept under its old name for any caller; the fields are sentinel_utils'.
_response_meta = response_meta


def _call_diagnostics(call: Dict, model_id: str) -> Dict:
    """This script's per-call diagnostics from an openrouter_chat result."""
    errors = call.get("attempt_errors") or []
    return {
        "prompt_tokens": call.get("prompt_tokens", 0),
        "completion_tokens": call.get("completion_tokens", 0),
        "total_tokens": call.get("total_tokens", 0),
        "latency_ms": call.get("latency_ms", 0.0),
        "model": model_id,
        "failure_type": call.get("failure_type"),
        "error": (call.get("failure_type") or "") + (
            f": {errors[-1].get('detail')}" if errors and call.get("failure_type") else ""),
        **call_log_fields(call),
    }


def query_openrouter(messages: List[Dict], model_id: str, model_key: str,
                     max_tokens: Optional[int] = None) -> Tuple[Optional[str], Dict]:
    """POST to OpenRouter through the architectures' shared client,
    sentinel_utils.openrouter_chat: same payload builder (max_tokens
    MAX_OUTPUT_TOKENS unless *max_tokens* overrides it -- the cot_scaffold
    arm's raised cap -- and the MODEL_SPECS provider pin for model_id), same
    retry policy from model_config, same failure rules.

    Returns (content, diagnostics). content is None when the call failed
    (retries exhausted, or a 400/404/422 on its one retry). A truncated reply
    (finish_reason length) returns its partial text with
    diagnostics["failure_type"] == FAILED_TRUNCATED; it is never parsed.
    HTTP 401/402/403 raise OpenRouterFatalError (a RunAbort), as does the
    consecutive-failure breaker. `latency_ms` is the successful POST only.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE,
    }
    payload = build_openrouter_payload(model_id, messages, TEMPERATURE,
                                       get_reasoning_payload(model_key),
                                       max_tokens=max_tokens)
    # logger=None: 8 workers x ~80k calls would flood the console with one line
    # per call; every attempt is in the raw jsonl instead.
    call = openrouter_chat(
        payload, headers,
        endpoint=OPENROUTER_URL,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
        is_transient=_is_transient_http_status,
        base_delay=RETRY_BASE_DELAY,
        max_backoff=MAX_RETRY_BACKOFF,
        logger=None,
    )
    diagnostics = _call_diagnostics(call, model_id)
    if call.get("failure_type"):
        logger.warning("call failed (%s) after %s attempt(s) for %s",
                       call["failure_type"], call.get("attempts"), model_id)
    if call.get("failure_type") and call.get("content") is None:
        return None, diagnostics
    return call.get("content"), diagnostics


def parse_scores(response_text: str, scale_max: float) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
    """Extract and validate the 4 criterion scores, rescaling by `scale_max`.

    Bounds are checked on the raw scale the model was asked for, so a 0-10 arm
    is not penalised for returning 7.0. CoT arms emit prose before the JSON, so
    the last balanced {...} block is used rather than requiring a bare object.
    """
    if not response_text:
        return None, "failed_empty_response"
    # The same extraction rule as the installed A_D and A_E (sentinel_utils).
    parsed = extract_json_object(response_text, CRITERIA)
    if not isinstance(parsed, dict):
        return None, "failed_malformed_json"

    scores = {}
    for criterion in CRITERIA:
        if criterion not in parsed:
            return None, f"failed_missing_score:{criterion}"
        raw = parsed[criterion]
        if not is_numeric_score(raw):
            return None, "failed_invalid_score_type"
        value = float(raw)
        if not (0.0 <= value <= scale_max):
            return None, "failed_out_of_bounds"
        scores[criterion] = value / scale_max
    return scores, None


# ---------------------------------------------------------------------------
# Prompts (user side)
# ---------------------------------------------------------------------------

def build_user_prompt(scenario: Dict, alternative: str) -> str:
    """Byte-identical to Direct_LLM_Scoring.build_user_prompt (checked at
    startup by _assert_control_is_main_suite). A_D only: A_E's user prompt is
    built by the installed A_E's own build_user_prompt_with_rag. Homeowner-facing
    fields only -- the true engineering values are never placed in a prompt."""
    decision_type = scenario.get("decision_type", "N/A")
    all_alts = [scenario.get("alternative_1", ""), scenario.get("alternative_2", ""),
                scenario.get("alternative_3", "")]
    other_alts = [str(a) for a in all_alts
                  if a not in (None, "", "N/A") and str(a) != str(alternative)]

    prompt = f'Score this alternative: "{alternative}"\n'
    prompt += f'Other alternatives available for this decision: {other_alts}\n\n'
    prompt += f'For the decision: "{scenario.get("question", "N/A")}"\n'
    prompt += "SCENARIO CONTEXT:\n"
    prompt += f"- Location: {scenario.get('location', 'N/A')}\n"

    if decision_type == "HVAC":
        prompt += f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
        prompt += f"- Square Footage: {scenario.get('square_footage', 'N/A')} sqft\n"
        prompt += f"- Insulation: {scenario.get('insulation', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
        prompt += f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
        prompt += f"- House Age: {scenario.get('house_age', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"
    elif decision_type == "Appliance":
        prompt += f"- Appliance Age Range: {scenario.get('appliance_age', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
        prompt += f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"
    elif decision_type == "Shower":
        prompt += f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
        prompt += f"- Flow Rate: {scenario.get('flow_rate', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
        prompt += f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"

    prompt += "\nProvide scores (0-1) for all 4 criteria.\n"
    prompt += "Consider how this specific alternative performs given the scenario context.\n"
    return prompt


# ---------------------------------------------------------------------------
# RAG (A_E arms only) -- reuses the shipped Chroma index and retrieval code
# ---------------------------------------------------------------------------

_ae_module = None
_ae_lock = threading.Lock()
# Chroma's client is not thread-safe for concurrent queries, and constructing it
# from several threads at once corrupts its initialisation outright (the tenant
# lookup fails with a missing-bindings AttributeError). One lock serialises both
# the one-time construction and every subsequent retrieval.
_retrieval_lock = threading.Lock()


def _load_ae_module():
    """Import the A_E architecture module and initialise its RAG resources.

    Imported by file path because the filename is not a valid identifier. Its
    `retrieve_similar_scenarios` / `format_rag_context` / `RETRIEVE_K` are
    reused verbatim, so the A_E control arm retrieves exactly what the shipped
    architecture retrieves.

    Double-checked locking: worker threads all call this, and Chroma cannot
    survive concurrent construction. Call `preload_ae_module()` before starting a
    pool to do the work up front on the main thread.
    """
    global _ae_module
    if _ae_module is not None:
        return _ae_module
    with _ae_lock:
        if _ae_module is not None:
            return _ae_module
        import importlib.util
        path = PROJECT_ROOT / "src/llm_mcda/architectures" / "Example-Guided_LLM_Scoring.py"
        spec = importlib.util.spec_from_file_location("example_guided_llm_scoring", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.init_rag_resources()
        _ae_module = module
        return module


def preload_ae_module():
    """Initialise the RAG stack on the main thread, before any pool starts."""
    _load_ae_module()


def build_messages(architecture: str, variant: Dict, scenario: Dict, alternative: str,
                   retrieved_out: Optional[List] = None,
                   retrieval_errors: Optional[List] = None,
                   distances_out: Optional[List] = None) -> List[Dict]:
    system_prompt = variant["system"][architecture]
    if not ARCHITECTURES[architecture]["rag"]:
        user_prompt = build_user_prompt(scenario, alternative)
    else:
        ae = _load_ae_module()
        # Chroma queries and the SentenceTransformer encode are serialised; only
        # the OpenRouter call below runs concurrently. Retrieval is local and
        # fast relative to the network wait, so this costs little parallelism.
        with _retrieval_lock:
            retrieved = ae.retrieve_similar_scenarios(scenario, k=ae.RETRIEVE_K,
                                                      error_out=retrieval_errors)
        if retrieved_out is not None:
            # Exemplar ids for the raw log, so retrieval can be audited later.
            retrieved_out.extend(r.get("id", "") for r in retrieved)
        if distances_out is not None:
            distances_out.extend(r.get("distance") for r in retrieved)
        rag_context = ae.format_rag_context(retrieved)
        # The installed A_E's own builder, so the user prompt is the main
        # suite's byte for byte. With no exemplar, score_scenario fails the
        # call before any API request.
        user_prompt = ae.build_user_prompt_with_rag(scenario, alternative, rag_context)
    return [{"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}]


# ---------------------------------------------------------------------------
# Scenario scoring
# ---------------------------------------------------------------------------

def _max_tokens_for(variant: Dict, model_key: str) -> int:
    """The max_tokens cap for one (variant, model) cell: the raised
    cot_scaffold cap resolved by resolve_cot_max_tokens() for a CoT variant,
    else sentinel_utils.MAX_OUTPUT_TOKENS unchanged. Never falls back
    silently: a CoT variant with no resolved cap is a bug (main() always
    resolves it before the cell loop), so it raises rather than sending 8192."""
    if not variant["cot"]:
        return MAX_OUTPUT_TOKENS
    cap = COT_MAX_TOKENS.get(model_key)
    if cap is None:
        raise RuntimeError(
            f"cot_scaffold max_tokens not resolved for model '{model_key}'. "
            f"Call resolve_cot_max_tokens([...]) before collecting any cot_scaffold cell."
        )
    return cap


def score_scenario(scenario: Dict, architecture: str, variant: Dict,
                   model_id: str, model_key: str) -> Dict:
    """Score every alternative in one scenario. Returns per-alternative scores
    plus the MAVT ranking. A failed alternative carries the 1928 sentinel and
    poisons the scenario's ranking rather than being defaulted to a neutral."""
    alternatives = [scenario.get(f"alternative_{i}") for i in range(1, 4)]
    alternatives = [str(a) for a in alternatives if a not in (None, "", "N/A")]

    scored = []
    diag = {"api_calls": 0, "successful_calls": 0, "failed_calls": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "latency_ms": 0.0}
    failure_types = []

    is_rag = ARCHITECTURES[architecture]["rag"]
    max_tokens = _max_tokens_for(variant, model_key)
    for alternative in alternatives:
        if _ABORT.is_set():
            raise RunAbort("aborted: another worker hit a fatal OpenRouter error")
        retrieved_ids: List = []
        retrieved_distances: List = []
        retrieval_errors: List = []
        messages = build_messages(architecture, variant, scenario, alternative,
                                  retrieved_out=retrieved_ids,
                                  retrieval_errors=retrieval_errors,
                                  distances_out=retrieved_distances)
        user_prompt = messages[-1]["content"]
        system_prompt = messages[0]["content"]

        def _record(response, call_diag, error, api_called=True):
            with _raw_log_lock:
                RAW_LOG.record(
                    scenario_id=scenario.get("scenario_id"),
                    decision_type=scenario.get("decision_type", ""),
                    architecture=architecture,
                    variant=variant["label"],
                    alternative=alternative,
                    model_key=model_key,
                    model=model_id,
                    system_prompt_sha256=hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
                    prompt=user_prompt,
                    prompt_sha256=hashlib.sha256(user_prompt.encode("utf-8")).hexdigest(),
                    rag_exemplar_ids=retrieved_ids if is_rag else None,
                    rag_exemplar_distances=retrieved_distances if is_rag else None,
                    rag_top_k=_load_ae_module().RETRIEVE_K if is_rag else None,
                    retrieval_error="; ".join(retrieval_errors) if retrieval_errors else None,
                    api_called=api_called,
                    response=response or "",
                    prompt_tokens=call_diag.get("prompt_tokens", 0),
                    completion_tokens=call_diag.get("completion_tokens", 0),
                    latency_ms=call_diag.get("latency_ms", 0),
                    error=call_diag.get("error", "") or (error or ""),
                    failure_type=call_diag.get("failure_type"),
                    # The per-arm cap actually sent (8192, or the raised
                    # cot_scaffold cap): recorded even when no call was made
                    # (the RAG-retrieval-failure branch), since it is fixed by
                    # (variant, model) and known regardless.
                    max_tokens=max_tokens,
                    **call_log_fields(call_diag),
                    api_success=response is not None,
                    parse_error=error,
                )

        # A_E arm with no exemplar: scoring would silently turn the call into
        # A_D. Fail it like the installed A_E does, without paying for a call.
        if is_rag and not retrieved_ids:
            error = ERR_RAG_RETRIEVAL
            _record(None, {"error": ERR_RAG_RETRIEVAL + ": " + "; ".join(retrieval_errors)},
                    error, api_called=False)
            diag["failed_calls"] += 1
            failure_types.append(error)
            scored.append({"alternative": alternative,
                           **{c: SENTINEL_FLOAT for c in CRITERIA}})
            continue

        diag["api_calls"] += 1
        try:
            response, call_diag = query_openrouter(messages, model_id, model_key,
                                                    max_tokens=max_tokens)
        except RunAbort as abort:
            # Archive the failing call (e.g. the 402) before the process stops.
            fatal = _call_diagnostics(getattr(abort, "diagnostics", {}) or {}, model_id)
            fatal["error"] = str(abort)
            _record(None, fatal, fatal.get("failure_type") or "fatal")
            _ABORT.set()
            raise
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
            diag[key] += call_diag.get(key, 0) or 0

        failure_type = call_diag.get("failure_type")
        if failure_type == FAILED_TRUNCATED:
            scores, error = None, ERR_TRUNCATED   # partial text is logged, never parsed
        elif response is None:
            scores, error = None, (ERR_API_BAD_REQUEST if failure_type == FAILED_API_BAD_REQUEST
                                   else ERR_API_EXHAUSTED)
        elif not response.strip():
            scores, error = None, ERR_EMPTY       # content null / "" / whitespace
        else:
            scores, error = parse_scores(response, variant["scale_max"])
        _record(response, call_diag, error)

        if error:
            diag["failed_calls"] += 1
            failure_types.append(error)
            scored.append({"alternative": alternative,
                           **{c: SENTINEL_FLOAT for c in CRITERIA}})
        else:
            diag["successful_calls"] += 1
            scored.append({"alternative": alternative, **scores})

    ranking = apply_mavt_ranking(scored)
    return {"scored": scored, "ranking": ranking, "diagnostics": diag,
            "failure_types": failure_types}


# ---------------------------------------------------------------------------
# Reference ranking
# ---------------------------------------------------------------------------

def load_reference() -> Dict[int, Dict]:
    """Reference MAVT ranking per test scenario, keyed by scenario_id.

    Built from the same workbooks/ground_truth workbooks the paper's reference calculators
    write, matched to the Test sheet by question+location with progressive
    narrowing on the alternative labels (the coordinate-system bug fixed in
    evaluate_parameter_extraction came from matching on positional indices instead).
    """
    test_df = read_table_clean(
        TEST_SCENARIOS, keep_str_cols=["alternative_1", "alternative_2", "alternative_3"])

    # Scenario-to-ground-truth matching is the headline's own
    # (evaluate_architecture_metrics.match_scenarios), not a re-implementation.
    # Matching on question + location alone is ambiguous: several Shower test
    # scenarios share both, and picking among their ground-truth scenarios by
    # alternative overlap alone attached the wrong scenario's ranks to 16
    # Shower scenarios, so control cells differed from the headline metrics
    # computed from the same runs. The headline match also uses the scenario's
    # outdoor_temp / appliance_age / flow_rate and consumes each ground-truth
    # scenario once, in scenario order.
    import importlib.util
    cm_path = PROJECT_ROOT / "scripts" / "analysis" / "evaluate_architecture_metrics.py"
    spec = importlib.util.spec_from_file_location("evaluate_architecture_metrics_for_ref", cm_path)
    cm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cm)
    gt_by_type = cm.load_ground_truth(cm._build_config(next(iter(MODEL_SPECS))))
    gt_lookup = cm.build_gt_lookup(gt_by_type)
    gt_id_lookup = cm.build_gt_id_lookup(gt_by_type)

    # Long-format frame shaped like a per-run architecture workbook (the columns
    # match_scenarios reads), one row per scenario x alternative.
    long_rows = []
    for i, row in test_df.iterrows():
        for j in range(1, 4):
            alt = str(row.get(f"alternative_{j}") or "").strip()
            if alt and alt.lower() != "nan":
                long_rows.append({
                    "scenario_id": i + 1,
                    "decision_type": row.get("decision_type"),
                    "question": row.get("question"),
                    "location": row.get("location"),
                    "outdoor_temp": row.get("outdoor_temp"),
                    "appliance_age": row.get("appliance_age"),
                    "flow_rate": row.get("flow_rate"),
                    "alternative": alt,
                })
    arch_df = cm.load_architecture(pd.DataFrame(long_rows), "reference")
    merged, _ = cm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, "reference")

    reference = {}
    for sid, sc in merged.groupby("arch_scenario_id", sort=True):
        sc = sc.sort_values("gt_rank")
        reference[int(sid)] = {
            "ranked_alternatives": [str(a).strip() for a in sc["alternative"]],
            "mavt_by_alt": {str(r["alternative"]).strip(): float(r["gt_mavt_score"])
                            for _, r in sc.iterrows()},
            # Ground-truth "rank" is already the deterministic TIE_BREAK_PRIORITY
            # tie-break applied by apply_mavt_ranking (see the GT calculators) --
            # reused here rather than re-deriving ranks from mavt_score, which
            # would tie whenever two alternatives share a weighted sum.
            "rank_by_alt": {str(r["alternative"]).strip(): int(r["gt_rank"])
                            for _, r in sc.iterrows()},
        }
    return reference


def rescore_cell_rows(df: pd.DataFrame, reference: Dict[int, Dict]) -> pd.DataFrame:
    """Recompute kendall_tau / top1 / top2 / failed / pred_top1 of stored cell
    rows from their stored per-alternative scores and ranks (`alt_scores_json`),
    against `reference`. No API call. Cells collected before the load_reference
    fix carry metrics scored against a wrong reference ranking for 16 Shower
    scenarios; the raw scores in the cell are unaffected, so the analysis
    rescores them here rather than rewriting the collected files. A row with no
    stored scores (a harness exception) keeps its stored failed values."""
    df = df.reset_index(drop=True)
    for idx, row in df.iterrows():
        raw = row.get("alt_scores_json")
        if not isinstance(raw, str) or not raw.strip():
            continue
        alts = json.loads(raw)
        result = {"scored": [{"alternative": str(a["alternative"]),
                              **{c: float(a[c]) for c in CRITERIA}} for a in alts],
                  "ranking": {"ranks": [a.get("rank") for a in alts]}}
        m = scenario_metrics(result, reference.get(int(row["scenario_id"])))
        for k in ("kendall_tau", "top1", "top2", "failed", "pred_top1"):
            df.at[idx, k] = m[k]
    return df


# Failure rule (S4, author decision 2026-09-29), the same as the main suite's
# (evaluate_architecture_metrics.FAILED_SCENARIO_*): a failed or unscored
# scenario is WRONG for Top-1/Top-2 and at chance (0) for Kendall tau, and it
# stays in every denominator.
FAILED_SCENARIO_TAU = 0.0


def scenario_metrics(result: Dict, ref: Optional[Dict]) -> Dict:
    """Kendall tau / Top-1 / Top-2 against the reference ranking.

    Accuracy rule (author decision, 2026-09-27; same rule the RAG ablation
    already uses -- see run_rag_ablation_experiments.scenario_metrics): a
    scenario that failed or is unscored -- no reference ranking at all, any
    alternative scored the sentinel, or no alternative overlaps the reference
    -- counts as WRONG for Top-1 and Top-2 (0.0, never NaN), and stays in the
    denominator: callers average top1/top2 over every scenario in the cell,
    not only the scored ones. Kendall tau follows the same failure rule (S4,
    2026-09-29): a failed scenario gets FAILED_SCENARIO_TAU = 0 (chance) and
    stays in the denominator. A scored scenario whose tau is undefined (fewer
    than two overlapping alternatives) is NaN here and 0 in summarize().

    Tau is computed on ranks, not raw scores: `result["ranking"]` already
    applies apply_mavt_ranking's deterministic TIE_BREAK_PRIORITY tie-break
    (B60), and the reference side reuses the ground truth's own tie-broken
    "rank" column, so neither side scores tau_b on tied values.
    """
    out = {"kendall_tau": FAILED_SCENARIO_TAU, "top1": 0.0, "top2": 0.0,
           "failed": True, "pred_top1": ""}
    if ref is None:
        return out
    scored = result["scored"]
    if any(float(a[c]) == SENTINEL_FLOAT for a in scored for c in CRITERIA):
        return out

    common = [a["alternative"] for a in scored if a["alternative"] in ref["mavt_by_alt"]]
    if not common:
        return out

    pred_rank_by_alt = {a["alternative"]: r for a, r in
                        zip(scored, result["ranking"]["ranks"])}
    ref_rank_by_alt = ref["rank_by_alt"]
    pred_ranks = [pred_rank_by_alt[a] for a in common]
    ref_ranks = [ref_rank_by_alt[a] for a in common]
    if len(common) < 2 or len(set(pred_ranks)) < 2 or len(set(ref_ranks)) < 2:
        tau = np.nan
    else:
        tau = float(kendalltau(pred_ranks, ref_ranks).correlation)

    pred_top1 = min(common, key=lambda a: pred_rank_by_alt[a])
    ref_top1 = min(common, key=lambda a: ref_rank_by_alt[a])
    pred_top2 = {a for a in common if pred_rank_by_alt[a] <= 2}
    return {
        "kendall_tau": tau,
        "top1": 1.0 if pred_top1 == ref_top1 else 0.0,
        "top2": 1.0 if ref_top1 in pred_top2 else 0.0,
        "failed": False,
        "pred_top1": pred_top1,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _failed_record(scenario: Dict, variant_id: str, variant: Dict, architecture: str,
                   model_key: str, run_idx: int, error: str, collected_utc: str) -> Dict:
    """A scenario that raised rather than returning scores. Marked failed so it
    is excluded from the kendall_tau mean (NaN, skipped by pandas' mean()) and
    counted WRONG in top1/top2 (0.0, not NaN -- the failure-as-wrong rule),
    with the error preserved for diagnosis."""
    return {
        "variant": variant_id, "variant_label": variant["label"],
        "architecture": architecture, "model": model_key,
        "model_id": MODEL_SPECS[model_key]["openrouter_id"], "run": run_idx,
        "collected_utc": collected_utc,
        "scenario_id": scenario["scenario_id"],
        "decision_type": scenario.get("decision_type", ""),
        "kendall_tau": FAILED_SCENARIO_TAU, "top1": 0.0, "top2": 0.0, "failed": True, "pred_top1": "",
        "api_calls": 0, "successful_calls": 0, "failed_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "latency_ms": 0.0, "failure_types": f"harness_exception: {error[:200]}",
        "mean_criterion_sd": np.nan,
    }


def run_cell(scenarios: List[Dict], reference: Dict[int, Dict], architecture: str,
             variant_id: str, variant: Dict, model_key: str, run_idx: int,
             workers: int, raw_log_path: Optional[Path] = None) -> pd.DataFrame:
    """One (variant, architecture, model, run) cell over all scenarios."""
    model_id = MODEL_SPECS[model_key]["openrouter_id"]
    records: List[Optional[Dict]] = [None] * len(scenarios)
    collected_utc = datetime.now(timezone.utc).isoformat()

    def work(i: int) -> Tuple[int, Dict]:
        scenario = scenarios[i]
        result = score_scenario(scenario, architecture, variant, model_id, model_key)
        metrics = scenario_metrics(result, reference.get(scenario["scenario_id"]))
        diag = result["diagnostics"]
        return i, {
            "variant": variant_id,
            "variant_label": variant["label"],
            "architecture": architecture,
            "model": model_key,
            "model_id": model_id,
            "run": run_idx,
            "collected_utc": collected_utc,
            "scenario_id": scenario["scenario_id"],
            "decision_type": scenario.get("decision_type", ""),
            # Per-alternative scores and tie-broken ranks, so tau/Top-1 can be
            # recomputed from this sheet without re-parsing the raw log.
            "alt_scores_json": json.dumps([
                {**a, "rank": r} for a, r in zip(result["scored"], result["ranking"]["ranks"])
            ]),
            "kendall_tau": metrics["kendall_tau"],
            "top1": metrics["top1"],
            "top2": metrics["top2"],
            "failed": metrics["failed"],
            "pred_top1": result["ranking"]["ranked_alternatives"][0]
                         if result["ranking"]["ranked_alternatives"] else "",
            "api_calls": diag["api_calls"],
            "successful_calls": diag["successful_calls"],
            "failed_calls": diag["failed_calls"],
            "prompt_tokens": diag["prompt_tokens"],
            "completion_tokens": diag["completion_tokens"],
            "total_tokens": diag["total_tokens"],
            "latency_ms": diag["latency_ms"],
            "failure_types": ";".join(result["failure_types"]),
            # Per-alternative spread, for the central-tendency analysis: the
            # mean within-alternative SD across the 4 criteria.
            "mean_criterion_sd": float(np.mean([
                np.std([float(a[c]) for c in CRITERIA])
                for a in result["scored"]
                if not any(float(a[cc]) == SENTINEL_FLOAT for cc in CRITERIA)
            ])) if not metrics["failed"] else np.nan,
        }

    # Build the RAG stack before any worker touches it; concurrent construction
    # of the Chroma client fails outright.
    if ARCHITECTURES[architecture]["rag"]:
        preload_ae_module()

    if raw_log_path is not None:
        RAW_LOG.start(raw_log_path, run=run_idx)
    try:
        n_workers = max(1, int(workers))
        if n_workers > 1:
            pool = ThreadPoolExecutor(max_workers=n_workers)
            try:
                futures = {pool.submit(work, i): i for i in range(len(scenarios))}
                done = 0
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        i, rec = future.result()
                        records[i] = rec
                    except Exception as exc:
                        # One scenario must not abort a multi-hour campaign. Record it
                        # as a failed scenario so it is excluded from every mean and
                        # stays visible in the per-scenario sheet. A RunAbort is a
                        # BaseException and is not caught here.
                        logger.warning("scenario %s raised: %s",
                                       scenarios[idx]["scenario_id"], exc)
                        records[idx] = _failed_record(scenarios[idx], variant_id, variant,
                                                      architecture, model_key, run_idx,
                                                      str(exc), collected_utc)
                    done += 1
                    if done % 25 == 0 or done == len(scenarios):
                        logger.info("      %s/%s scenarios", done, len(scenarios))
            except BaseException as exc:
                # RunAbort (401/402/403 or the failure breaker) or Ctrl-C: stop every
                # worker at its next call, drop the queued scenarios, and let the
                # abort propagate. The cell xlsx is written only by main() after a
                # normal return, so nothing partial is ever saved as complete.
                if not isinstance(exc, Exception):
                    _ABORT.set()
                pool.shutdown(wait=True, cancel_futures=True)
                raise
            pool.shutdown(wait=True)
        else:
            for idx in range(len(scenarios)):
                try:
                    i, rec = work(idx)
                    records[i] = rec
                except Exception as exc:
                    logger.warning("scenario %s raised: %s",
                                   scenarios[idx]["scenario_id"], exc)
                    records[idx] = _failed_record(scenarios[idx], variant_id, variant,
                                                  architecture, model_key, run_idx,
                                                  str(exc), collected_utc)
    finally:
        if raw_log_path is not None:
            RAW_LOG.stop()

    return pd.DataFrame([r for r in records if r is not None])


def load_scenarios(sample_size: Optional[int], seed: int) -> List[Dict]:
    df = read_table_clean(
        TEST_SCENARIOS, keep_str_cols=["alternative_1", "alternative_2", "alternative_3"])
    scenarios = []
    for i, row in df.iterrows():
        record = row.to_dict()
        record["scenario_id"] = i + 1
        scenarios.append(record)
    if sample_size is None or sample_size >= len(scenarios):
        return scenarios
    # Stratify by decision type so a subset keeps all three represented.
    rng = np.random.default_rng(seed)
    by_type: Dict[str, List[Dict]] = {}
    for s in scenarios:
        by_type.setdefault(s.get("decision_type", "?"), []).append(s)
    types = sorted(by_type)
    per = sample_size // len(types)
    extra = sample_size % len(types)
    picked = []
    for idx, dtype in enumerate(types):
        n = min(per + (1 if idx < extra else 0), len(by_type[dtype]))
        sel = rng.choice(len(by_type[dtype]), size=n, replace=False)
        picked.extend(by_type[dtype][int(j)] for j in sorted(sel))
    return sorted(picked, key=lambda s: s["scenario_id"])


def parse_sample_size(value: str) -> Optional[int]:
    if value.strip().lower() == "all":
        return None
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("--sample-size must be positive or 'all'")
    return n


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Per-run means first, then mean +/- SD across runs, so the reported SD is
    the run-to-run SD the control gate is checked against.

    Accuracy rule (author decision, 2026-09-27, mirroring the RAG ablation): a
    failed or unscored scenario counts as WRONG for top1_accuracy and
    top2_accuracy, so their denominator is every scenario in the cell
    (`g`/`len(g)`), not just the scored ones (`ok`/`len(ok)`). This falls out
    of scenario_metrics/_failed_record already writing 0.0 (never NaN) for a
    failed scenario's top1/top2, so `g["top1"].mean()` divides by n_scenarios
    automatically. kendall_tau follows the same failure rule (S4): a failed
    scenario counts at tau 0 (chance) and every scenario is in the denominator.
    """
    rows = []
    per_run = []
    for (variant, arch, model, run), g in df.groupby(
            ["variant", "architecture", "model", "run"], sort=False):
        ok = g[~g["failed"]]
        per_run.append({
            "variant": variant, "architecture": arch, "model": model, "run": run,
            "n_scenarios": len(g), "n_scored": len(ok),
            "n_failed_scenarios": int(g["failed"].astype(bool).sum()),
            # Failure rule (S4): every scenario in the denominator, a failed
            # one at tau 0 (scenario_metrics / _failed_record write it).
            "kendall_tau": g["kendall_tau"].fillna(FAILED_SCENARIO_TAU).mean(),
            "top1_accuracy": g["top1"].mean(),
            "top2_accuracy": g["top2"].mean(),
            "mean_criterion_sd": ok["mean_criterion_sd"].mean(),
            "total_tokens": g["total_tokens"].sum(),
        })
    per_run_df = pd.DataFrame(per_run)
    for (variant, arch, model), g in per_run_df.groupby(
            ["variant", "architecture", "model"], sort=False):
        rows.append({
            "variant": variant,
            "variant_label": VARIANT_SPECS[variant]["label"],
            "architecture": arch,
            "model": model,
            "n_runs": len(g),
            "kendall_tau": g["kendall_tau"].mean(),
            "kendall_tau_sd": g["kendall_tau"].std(),
            "top1_accuracy": g["top1_accuracy"].mean(),
            "top1_accuracy_sd": g["top1_accuracy"].std(),
            "top2_accuracy": g["top2_accuracy"].mean(),
            "top2_accuracy_sd": g["top2_accuracy"].std(),
            "n_failed_scenarios": g["n_failed_scenarios"].mean(),
            "mean_criterion_sd": g["mean_criterion_sd"].mean(),
            "success_rate": g["n_scored"].sum() / max(g["n_scenarios"].sum(), 1),
            "tokens_per_run": g["total_tokens"].mean(),
        })
    return pd.DataFrame(rows), per_run_df


def _md(df: pd.DataFrame) -> str:
    """Hand-rolled markdown; pandas.to_markdown needs `tabulate`, not a repo dep."""
    hdr = list(df.columns)
    lines = ["| " + " | ".join(hdr) + " |",
             "| " + " | ".join("---" for _ in hdr) + " |"]
    for _, r in df.iterrows():
        cells = []
        for h in hdr:
            v = r[h]
            if isinstance(v, float):
                cells.append("N/A" if pd.isna(v) else f"{v:.4f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Prompt-sensitivity ablation for A_D and A_E. Does not modify "
                    "the architecture files or write into Output Files*.")
    parser.add_argument("--sample-size", default="all",
                        help="Test scenarios to evaluate (default 'all' = 195), "
                             "stratified by decision type when subsetting.")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--runs", type=int, default=PROMPT_ABLATION_RUNS,
                        help=f"Runs per cell (default {PROMPT_ABLATION_RUNS}, fixed in advance).")
    parser.add_argument("--variants", nargs="+", default=DEFAULT_VARIANTS,
                        choices=list(VARIANT_SPECS.keys()),
                        help="Default: every variant except control, which the significance "
                             "script takes from main-suite runs 1..--runs.")
    parser.add_argument("--architectures", nargs="+", default=list(ARCHITECTURES.keys()),
                        choices=list(ARCHITECTURES.keys()))
    parser.add_argument("--models", nargs="+",
                        default=list(MODEL_SPECS.keys()),
                        choices=list(MODEL_SPECS.keys()),
                        help="Model keys to evaluate. Defaults to all four, which is the set "
                             "the paper reports. Gemini costs roughly 50x the output price of "
                             "the other three; pass the other three keys explicitly to skip "
                             "it, at the cost of no longer matching the paper.")
    parser.add_argument("--workers", type=int, default=8,
                        help="Concurrent scenario threads. 1 runs serially.")
    parser.add_argument("--cot-max-tokens", type=int, default=None,
                        help="Override the cot_scaffold max_tokens cap for every model "
                             f"requested (still capped at {COT_MAX_TOKENS_CAP}), skipping the "
                             "OpenRouter /endpoints GET lookup entirely. Use only when that "
                             "free lookup is unavailable.")
    parser.add_argument("--output-dir", default=os.environ.get(RUN_OUTPUT_DIR_ENV),
                        help=f"New or existing safe output directory (or set {RUN_OUTPUT_DIR_ENV}); "
                             "required to write results outside frozen repository data.")
    parser.add_argument("--output", default=None,
                        help="Optional markdown report path (defaults inside --output-dir).")
    args = parser.parse_args()
    try:
        args.output_dir = require_safe_output_directory(
            args.output_dir, option=f"--output-dir (or {RUN_OUTPUT_DIR_ENV})", root=PROJECT_ROOT
        )
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))
    if args.output is not None:
        output_path = Path(args.output).expanduser().resolve()
        try:
            require_safe_output_directory(
                output_path.parent, option="--output parent", root=PROJECT_ROOT
            )
        except UnsafeOutputPathError as exc:
            parser.error(str(exc))
        if output_path.is_dir():
            parser.error(f"--output must name a file: {output_path}")
        args.output = output_path

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found in .env")

    _assert_control_matches_shipped()
    _assert_control_is_main_suite(args.architectures)
    logger.info("Shipped-prompt drift check passed; control messages equal the main suite's.")

    if "cot_scaffold" in args.variants:
        # Resolved once per model, before any cot_scaffold cell is collected
        # (every other variant keeps sentinel_utils.MAX_OUTPUT_TOKENS and needs
        # no lookup). A failed lookup raises here and aborts the whole run
        # rather than silently falling back to the 8192 default.
        resolve_cot_max_tokens(args.models, override=args.cot_max_tokens)

    sample_size = parse_sample_size(args.sample_size)
    scenarios = load_scenarios(sample_size, args.seed)
    reference = load_reference()
    logger.info("Loaded %s scenarios; %s have a reference ranking",
                len(scenarios), len(reference))
    missing_ref = [s["scenario_id"] for s in scenarios if s["scenario_id"] not in reference]
    if missing_ref:
        logger.warning("%s scenario(s) have no reference ranking and will report as "
                       "failed: %s", len(missing_ref), missing_ref[:10])

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    all_parts = []
    for variant_id in args.variants:
        variant = VARIANT_SPECS[variant_id]
        for arch in args.architectures:
            if variant_id == "no_anchors" and arch == "AE":
                logger.info("SKIP no_anchors x AE: %s", NO_ANCHORS_AE_NOTE)
                continue
            for model_key in args.models:
                for run_idx in range(1, args.runs + 1):
                    cell_path = out_dir / (
                        f"cell_{variant_id}_{arch}_{model_key}_run_{run_idx:02d}.xlsx")
                    if cell_path.exists() and cell_path.stat().st_size > 0:
                        try:
                            all_parts.append(rescore_cell_rows(read_table_clean(cell_path), reference))
                            logger.info("Resume %s", cell_path.name)
                            continue
                        except Exception:
                            logger.info("Unreadable, re-running %s", cell_path.name)
                    logger.info("Running %s / %s / %s / run %s",
                                variant_id, arch, model_key, run_idx)
                    raw_log_path = cell_path.with_name(f"{cell_path.stem}_raw.jsonl")
                    try:
                        cell_df = run_cell(scenarios, reference, arch, variant_id, variant,
                                           model_key, run_idx, args.workers,
                                           raw_log_path=raw_log_path)
                    except RunAbort as exc:
                        # 401/402/403 or the consecutive-failure breaker: every later
                        # call would fail the same way. Stop the whole process; this
                        # cell is not written (a rerun re-collects it) and completed
                        # cells stay on disk. No summary is written.
                        logger.error("ABORT in cell %s/%s/%s run %s; cell not written, "
                                     "summary not written. Fix the cause, then rerun the "
                                     "same command to resume: %s",
                                     variant_id, arch, model_key, run_idx, exc)
                        raise
                    except Exception as exc:
                        # Skip this cell rather than lose every completed cell.
                        # Reruns resume from the xlsx files already on disk.
                        logger.error("Cell %s/%s/%s run %s failed, continuing: %s",
                                     variant_id, arch, model_key, run_idx, exc)
                        continue
                    if cell_df.empty:
                        logger.warning("Empty cell, not written: %s", cell_path.name)
                        continue
                    tmp = cell_path.with_suffix(".xlsx.tmp")
                    cell_df.to_excel(tmp, index=False, engine="openpyxl")
                    os.replace(tmp, cell_path)
                    all_parts.append(cell_df)

    if not all_parts:
        logger.error("No results produced.")
        return

    df = pd.concat(all_parts, ignore_index=True)
    if "control" not in args.variants:
        # The control cell is the main suite's runs 1..--runs. It is collected
        # last (author decision: main suite after every ablation), so it is
        # often absent here; the significance script adds it when it exists.
        for arch in args.architectures:
            for model_key in args.models:
                try:
                    control = main_suite_control_rows(
                        model_key, arch, args.runs, reference,
                        scenario_ids={s["scenario_id"] for s in scenarios})
                except FileNotFoundError as exc:
                    logger.info("Control for %s/%s not in the summary yet: %s", arch, model_key, exc)
                    continue
                df = pd.concat([df, control], ignore_index=True)
    summary, per_run_df = summarize(df)

    with pd.ExcelWriter(out_dir / "prompt_ablation_summary.xlsx") as xl:
        summary.to_excel(xl, sheet_name="summary", index=False)
        per_run_df.to_excel(xl, sheet_name="per_run", index=False)
        df.to_excel(xl, sheet_name="per_scenario", index=False)

    cols = ["variant", "architecture", "model", "n_runs", "kendall_tau",
            "kendall_tau_sd", "top1_accuracy", "top1_accuracy_sd",
            "top2_accuracy", "top2_accuracy_sd", "n_failed_scenarios",
            "mean_criterion_sd", "success_rate"]
    print("\n=== PROMPT ABLATION ===")
    print(summary[cols].to_string(index=False,
                                  float_format=lambda v: f"{v:.4f}"))

    lines = [
        "# Prompt-Sensitivity Ablation (A_D / A_E)", "",
        f"- Scenarios per cell: {len(scenarios)}",
        f"- Runs per cell: {args.runs}",
        f"- Models: {', '.join(args.models)}",
        f"- Workers: {args.workers}", "",
        f"Note: {NO_ANCHORS_AE_NOTE}", "",
        "## Summary (mean over runs; SD is run-to-run)", "",
        _md(summary[cols]), "",
        "## Per-run detail", "",
        _md(per_run_df),
    ]
    output_path = args.output or (out_dir / "prompt_ablation_results.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {output_path} and {out_dir / 'prompt_ablation_summary.xlsx'}")


if __name__ == "__main__":
    main()
