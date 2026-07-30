"""Prompt-sensitivity ablation for A_D (direct scoring) and A_E (example-guided).

Tests whether A_D's and A_E's poor rank recovery is an artifact of the specific
prompt they ship with, rather than a property of direct LLM scoring. Four
variants, applied to both architectures:

  control      -- the shipped prompt, unmodified. Gate: must reproduce the
                  main-text tau within run-to-run SD, otherwise the harness
                  itself is wrong and no other arm can be trusted.
  no_anchors   -- per-criterion good/moderate/poor calibration anchors stripped
                  from the system prompt, leaving criterion names and the scale.
  cot_scaffold -- an explicit reasoning scaffold before the JSON answer.
  scale_0_10   -- response scale changed 0-1 -> 0-10, rescaled post hoc by /10.
                  The sharpest probe of the central-tendency finding: if the
                  clustering is a scale artifact it should move here.

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

Outputs route to `Analysis/Prompt_Ablation/` and never touch `Output Files*`.
Resume-aware per (variant, architecture, model, run).
"""

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from scipy.stats import kendalltau

from model_config import (
    CRITERION_WEIGHTS,
    MAX_RETRIES,
    MAX_RETRY_BACKOFF,
    MODEL_SPECS,
    N_RUNS,
    REQUEST_TIMEOUT,
    RETRY_BASE_DELAY,
    TEMPERATURE,
    TIE_BREAK_PRIORITY,
    get_reasoning_payload,
)
from sentinel_utils import (
    CRITERIA,
    SENTINEL_FLOAT,
    apply_mavt_ranking,
    read_table_clean,
)

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

TEST_SCENARIOS = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}

logger = logging.getLogger("prompt_ablation")


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


def _rescale_prompt_0_10(prompt: str) -> str:
    """Rewrite a 0-1 system prompt to ask for 0-10. Applied to the shipped text
    so the variant differs from control in the scale and nothing else."""
    out = prompt.replace(
        "using the inclusive 0-1 scale (0.0 <= score <= 1.0)",
        "using the inclusive 0-10 scale (0.0 <= score <= 10.0)",
    )
    out = out.replace(
        'where each X is between 0.0 and 1.0.',
        'where each X is between 0.0 and 10.0.',
    )
    return out


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
    ("scale_0_10", {
        "label": "Response scale 0-10 (rescaled post hoc)",
        "scale_max": 10.0,
        "cot": False,
        "system": {"AD": _rescale_prompt_0_10(AD_SYSTEM_PROMPT),
                   "AE": _rescale_prompt_0_10(AE_SYSTEM_PROMPT)},
    }),
])

NO_ANCHORS_AE_NOTE = (
    "A_E's shipped system prompt contains no per-criterion calibration anchors "
    "(RAG supplies scored exemplars instead), so for A_E the no_anchors arm is "
    "identical to control by construction and is skipped rather than billed twice."
)

ARCHITECTURES = OrderedDict([
    ("AD", {"label": "Direct LLM scoring", "rag": False}),
    ("AE", {"label": "Example-guided (RAG) scoring", "rag": True}),
])


def _assert_control_matches_shipped() -> None:
    """Fail loudly if an architecture's shipped prompt has drifted from the copy
    above. Compares whitespace-normalised text, so reflowing a line is tolerated
    but a wording or anchor change is not."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    ad_src = (PROJECT_ROOT / "Architectures" / "Direct_LLM_Scoring.py").read_text(encoding="utf-8")
    ae_src = (PROJECT_ROOT / "Architectures" / "Example-Guided_LLM_Scoring.py").read_text(encoding="utf-8")

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
            + "\nUpdate the constants in RunPromptAblations.py before running, or the "
              "ablation will be measured against a stale baseline."
        )


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520


def query_openrouter(messages: List[Dict], model_id: str, model_key: str) -> Tuple[Optional[str], Dict]:
    """POST to OpenRouter under the shared retry policy from model_config.

    `latency_ms` is measured around the successful POST only, matching the
    architectures, so latency stays comparable to the main-run diagnostics even
    when this harness runs many requests concurrently.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE,
    }
    payload = {"model": model_id, "messages": messages, "temperature": TEMPERATURE}
    reasoning_payload = get_reasoning_payload(model_key)
    if reasoning_payload is not None:
        payload["reasoning"] = reasoning_payload

    diagnostics = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                   "latency_ms": 0.0, "model": model_id, "retries": 0}
    last_error = None
    attempt = 0
    retry_forever = MAX_RETRIES <= 0

    while True:
        attempt += 1
        diagnostics["retries"] = attempt - 1
        try:
            start = time.time()
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload,
                                     timeout=REQUEST_TIMEOUT)
            latency_ms = (time.time() - start) * 1000
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                diagnostics.update({
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "latency_ms": latency_ms,
                })
                return content, diagnostics
            last_error = f"Status {response.status_code}: {response.text[:200]}"
            if _is_transient_http_status(response.status_code):
                logger.debug("Transient %s on attempt %s", response.status_code, attempt)
        except Exception as exc:
            last_error = str(exc)
            logger.debug("Request failed on attempt %s: %s", attempt, exc)

        if not retry_forever and attempt >= MAX_RETRIES:
            break
        time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))

    diagnostics["error"] = last_error
    return None, diagnostics


def parse_scores(response_text: str, scale_max: float) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
    """Extract and validate the 4 criterion scores, rescaling by `scale_max`.

    Bounds are checked on the raw scale the model was asked for, so a 0-10 arm
    is not penalised for returning 7.0. CoT arms emit prose before the JSON, so
    the last balanced {...} block is used rather than requiring a bare object.
    """
    if not response_text:
        return None, "failed_empty_response"
    text = response_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()

    parsed = None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Fall back to the last {...} span, which is where the scaffolded arms
        # put the answer.
        for match in reversed(list(re.finditer(r"\{[^{}]*\}", text, re.DOTALL))):
            try:
                candidate = json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(candidate, dict) and any(c in candidate for c in CRITERIA):
                parsed = candidate
                break
    if not isinstance(parsed, dict):
        return None, "failed_malformed_json"

    scores = {}
    for criterion in CRITERIA:
        if criterion not in parsed:
            return None, f"failed_missing_score:{criterion}"
        raw = parsed[criterion]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
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
    """Mirrors Direct_LLM_Scoring.build_user_prompt. Homeowner-facing fields
    only -- the true engineering values are never placed in an A_D/A_E prompt."""
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

    prompt += "\nProvide scores for all 4 criteria.\n"
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
        path = PROJECT_ROOT / "Architectures" / "Example-Guided_LLM_Scoring.py"
        spec = importlib.util.spec_from_file_location("example_guided_llm_scoring", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.init_rag_resources()
        _ae_module = module
        return module


def preload_ae_module():
    """Initialise the RAG stack on the main thread, before any pool starts."""
    _load_ae_module()


def build_messages(architecture: str, variant: Dict, scenario: Dict, alternative: str) -> List[Dict]:
    system_prompt = variant["system"][architecture]
    user_prompt = build_user_prompt(scenario, alternative)
    if ARCHITECTURES[architecture]["rag"]:
        ae = _load_ae_module()
        # Chroma queries and the SentenceTransformer encode are serialised; only
        # the OpenRouter call below runs concurrently. Retrieval is local and
        # fast relative to the network wait, so this costs little parallelism.
        with _retrieval_lock:
            retrieved = ae.retrieve_similar_scenarios(scenario, k=ae.RETRIEVE_K)
        rag_context = ae.format_rag_context(retrieved)
        if rag_context:
            user_prompt = user_prompt + "\n" + rag_context
    return [{"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}]


# ---------------------------------------------------------------------------
# Scenario scoring
# ---------------------------------------------------------------------------

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

    for alternative in alternatives:
        messages = build_messages(architecture, variant, scenario, alternative)
        diag["api_calls"] += 1
        response, call_diag = query_openrouter(messages, model_id, model_key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
            diag[key] += call_diag.get(key, 0)

        scores, error = parse_scores(response, variant["scale_max"]) if response else (None, "failed_api_exhausted")
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

    Built from the same Ground Truth workbooks the paper's reference calculators
    write, matched to the Test sheet by question+location with progressive
    narrowing on the alternative labels (the coordinate-system bug fixed in
    EvaluateHybridExtraction came from matching on positional indices instead).
    """
    test_df = read_table_clean(
        TEST_SCENARIOS, keep_str_cols=["alternative_1", "alternative_2", "alternative_3"])
    gt_files = {"HVAC": "ground_truth_hvac.xlsx",
                "Appliance": "ground_truth_appliance.xlsx",
                "Shower": "ground_truth_shower.xlsx"}
    gt_cache = {}
    for dtype, filename in gt_files.items():
        path = GROUND_TRUTH_DIR / filename
        if path.exists():
            gt_cache[dtype] = read_table_clean(
                path, keep_str_cols=["question", "location", "alternative"])

    def clean(v) -> str:
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        return str(v).strip()

    reference = {}
    for i, row in test_df.iterrows():
        sid = i + 1
        dtype = clean(row.get("decision_type"))
        gt = gt_cache.get(dtype)
        if gt is None:
            continue
        cand = gt[(gt["question"].map(clean) == clean(row.get("question")))
                  & (gt["location"].map(clean) == clean(row.get("location")))]
        if cand.empty:
            continue
        alts = [clean(row.get(f"alternative_{j}")) for j in range(1, 4)]
        alts = [a for a in alts if a]
        sub = cand[cand["alternative"].map(clean).isin(alts)]
        if sub.empty:
            continue
        ordered = sub.sort_values("mavt_score", ascending=False)
        reference[sid] = {
            "ranked_alternatives": [clean(a) for a in ordered["alternative"]],
            "mavt_by_alt": {clean(r["alternative"]): float(r["mavt_score"])
                            for _, r in sub.iterrows()},
        }
    return reference


def scenario_metrics(result: Dict, ref: Optional[Dict]) -> Dict:
    """Kendall tau / Top-1 against the reference ranking. A scenario with any
    sentinel score is reported as failed and contributes to no mean."""
    out = {"kendall_tau": np.nan, "top1": np.nan, "failed": True}
    if ref is None:
        return out
    scored = result["scored"]
    if any(float(a[c]) == SENTINEL_FLOAT for a in scored for c in CRITERIA):
        return out

    common = [a["alternative"] for a in scored if a["alternative"] in ref["mavt_by_alt"]]
    if len(common) < 2:
        return out

    pred = {a["alternative"]: sum(CRITERION_WEIGHTS[c] * float(a[c]) for c in CRITERIA)
            for a in scored}
    pred_vec = [pred[a] for a in common]
    ref_vec = [ref["mavt_by_alt"][a] for a in common]
    if len(set(pred_vec)) < 2 or len(set(ref_vec)) < 2:
        tau = np.nan
    else:
        tau = float(kendalltau(pred_vec, ref_vec).correlation)

    pred_top1 = max(common, key=lambda a: pred[a])
    ref_top1 = max(common, key=lambda a: ref["mavt_by_alt"][a])
    return {"kendall_tau": tau, "top1": 1.0 if pred_top1 == ref_top1 else 0.0,
            "failed": False}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _failed_record(scenario: Dict, variant_id: str, variant: Dict, architecture: str,
                   model_key: str, run_idx: int, error: str) -> Dict:
    """A scenario that raised rather than returning scores. Marked failed so it is
    excluded from every mean, with the error preserved for diagnosis."""
    return {
        "variant": variant_id, "variant_label": variant["label"],
        "architecture": architecture, "model": model_key, "run": run_idx,
        "scenario_id": scenario["scenario_id"],
        "decision_type": scenario.get("decision_type", ""),
        "kendall_tau": np.nan, "top1": np.nan, "failed": True, "pred_top1": "",
        "api_calls": 0, "successful_calls": 0, "failed_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "latency_ms": 0.0, "failure_types": f"harness_exception: {error[:200]}",
        "mean_criterion_sd": np.nan,
    }


def run_cell(scenarios: List[Dict], reference: Dict[int, Dict], architecture: str,
             variant_id: str, variant: Dict, model_key: str, run_idx: int,
             workers: int) -> pd.DataFrame:
    """One (variant, architecture, model, run) cell over all scenarios."""
    model_id = MODEL_SPECS[model_key]["openrouter_id"]
    records: List[Optional[Dict]] = [None] * len(scenarios)

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
            "run": run_idx,
            "scenario_id": scenario["scenario_id"],
            "decision_type": scenario.get("decision_type", ""),
            "kendall_tau": metrics["kendall_tau"],
            "top1": metrics["top1"],
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

    n_workers = max(1, int(workers))
    if n_workers > 1:
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
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
                    # stays visible in the per-scenario sheet.
                    logger.warning("scenario %s raised: %s",
                                   scenarios[idx]["scenario_id"], exc)
                    records[idx] = _failed_record(scenarios[idx], variant_id, variant,
                                                  architecture, model_key, run_idx, str(exc))
                done += 1
                if done % 25 == 0 or done == len(scenarios):
                    logger.info("      %s/%s scenarios", done, len(scenarios))
    else:
        for idx in range(len(scenarios)):
            try:
                i, rec = work(idx)
                records[i] = rec
            except Exception as exc:
                logger.warning("scenario %s raised: %s",
                               scenarios[idx]["scenario_id"], exc)
                records[idx] = _failed_record(scenarios[idx], variant_id, variant,
                                              architecture, model_key, run_idx, str(exc))

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
    the run-to-run SD the control gate is checked against."""
    rows = []
    per_run = []
    for (variant, arch, model, run), g in df.groupby(
            ["variant", "architecture", "model", "run"], sort=False):
        ok = g[~g["failed"]]
        per_run.append({
            "variant": variant, "architecture": arch, "model": model, "run": run,
            "n_scenarios": len(g), "n_scored": len(ok),
            "kendall_tau": ok["kendall_tau"].mean(),
            "top1_accuracy": ok["top1"].mean(),
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
    parser.add_argument("--runs", type=int, default=N_RUNS,
                        help=f"Runs per cell (default N_RUNS={N_RUNS}).")
    parser.add_argument("--variants", nargs="+", default=list(VARIANT_SPECS.keys()),
                        choices=list(VARIANT_SPECS.keys()))
    parser.add_argument("--architectures", nargs="+", default=list(ARCHITECTURES.keys()),
                        choices=list(ARCHITECTURES.keys()))
    parser.add_argument("--models", nargs="+",
                        default=[k for k in MODEL_SPECS if k != "gemini"],
                        choices=list(MODEL_SPECS.keys()),
                        help="Default excludes gemini (roughly 50x the output price).")
    parser.add_argument("--workers", type=int, default=8,
                        help="Concurrent scenario threads. 1 runs serially.")
    parser.add_argument("--output-dir",
                        default=str(PROJECT_ROOT / "Analysis" / "Prompt_Ablation"))
    parser.add_argument("--output",
                        default=str(PROJECT_ROOT / "prompt_ablation_results.md"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found in .env")

    _assert_control_matches_shipped()
    logger.info("Shipped-prompt drift check passed.")

    sample_size = parse_sample_size(args.sample_size)
    scenarios = load_scenarios(sample_size, args.seed)
    reference = load_reference()
    logger.info("Loaded %s scenarios; %s have a reference ranking",
                len(scenarios), len(reference))
    missing_ref = [s["scenario_id"] for s in scenarios if s["scenario_id"] not in reference]
    if missing_ref:
        logger.warning("%s scenario(s) have no reference ranking and will report as "
                       "failed: %s", len(missing_ref), missing_ref[:10])

    out_dir = Path(args.output_dir)
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
                            all_parts.append(read_table_clean(cell_path))
                            logger.info("Resume %s", cell_path.name)
                            continue
                        except Exception:
                            logger.info("Unreadable, re-running %s", cell_path.name)
                    logger.info("Running %s / %s / %s / run %s",
                                variant_id, arch, model_key, run_idx)
                    try:
                        cell_df = run_cell(scenarios, reference, arch, variant_id, variant,
                                           model_key, run_idx, args.workers)
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
    summary, per_run_df = summarize(df)

    with pd.ExcelWriter(out_dir / "prompt_ablation_summary.xlsx") as xl:
        summary.to_excel(xl, sheet_name="summary", index=False)
        per_run_df.to_excel(xl, sheet_name="per_run", index=False)
        df.to_excel(xl, sheet_name="per_scenario", index=False)

    cols = ["variant", "architecture", "model", "n_runs", "kendall_tau",
            "kendall_tau_sd", "top1_accuracy", "top1_accuracy_sd",
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
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {args.output} and {out_dir / 'prompt_ablation_summary.xlsx'}")


if __name__ == "__main__":
    main()
