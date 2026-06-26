import os
import sys
import json
import time
import logging
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
import requests
from dotenv import load_dotenv
import pandas as pd

"""ACROSS ALL THREE ARCHITECTURES
These sources were used to help build prompts:
 Prompt engineering components and their citations:

 1. Role prompting ("You are an expert in [domain]...")
 Shanahan, M., McDonell, K., & Reynolds, L. (2023).
 Role play with large language models. Nature, 623(7987), 493–498.
 https://doi.org/10.1038/s41586-023-06647-8

 2. Structured output constraint ("return ONLY JSON")
 Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models.
 NeurIPS 2022. https://proceedings.neurips.cc/paper/2022/file/9d5609613524ecf4f15af0f7b31abca4-Paper-Conference.pdf

 3. RAG context injection ("use retrieved examples as reference but score independently")
 Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks.
 NeurIPS 2020. https://proceedings.neurips.cc/paper/2020/file/6b493230205f780e1bc26945df7481e5-Paper.pdf

 4. LLM-Parameterized_Reference_Scoring parameter extraction ("extract parameters then compute")
 Khot, T., et al. (2023). Decomposed prompting: A modular approach for solving complex tasks.
 ICLR 2023. https://arxiv.org/abs/2210.02406

 5. "Reasonably estimate if not apparent" (bias mitigation)
 Galaz, V., et al. (2021). Artificial intelligence, systemic risks, and sustainability.
 Technology in Society, 67, 101741. https://doi.org/10.1016/j.techsoc.2021.101741

"""

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import (
    CRITERION_WEIGHTS,
    get_model_id,
    get_output_folder_for_model_id,
    get_reasoning_payload,
    N_RUNS,
    TEMPERATURE,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_BASE_DELAY,
    MAX_RETRY_BACKOFF,
    EXTRACTION_INVALID_JSON,
    FAILED_MISSING_SCORE,
    FAILED_OUT_OF_BOUNDS,
    FAILED_INVALID_SCORE_TYPE,
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN,
)
from sentinel_utils import (
    _atomic_write_json,
    _atomic_write_xlsx,
    _is_complete_run_file,
    has_sentinel_scores,
    read_table_clean,
    SENTINEL_VALUE,
    SENTINEL_FLOAT,
)

TEST_SCENARIOS = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"


load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")

# Allow debug level to be controlled via environment variable
DEBUG_API = os.getenv("DEBUG_API", "false").lower() == "true"
DEBUG_LEVEL = logging.DEBUG if DEBUG_API else logging.INFO

logging.basicConfig(
    level=DEBUG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

MODEL_ID = get_model_id()

# Log startup config
logger = logging.getLogger(__name__)
if DEBUG_API:
    logger.debug(f"DEBUG_API mode enabled - will log full API responses")
    logger.debug(f"Model: {MODEL_ID}")
    logger.debug(f"Temperature: {TEMPERATURE}")
    logger.debug(f"Max retries: {MAX_RETRIES}")
    logger.debug(f"Request timeout: {REQUEST_TIMEOUT}s")

API_CONFIG = {
    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    "model": MODEL_ID,
    "temperature": TEMPERATURE,  # shared across all three architectures (model_config)
    "reasoning": get_reasoning_payload(),
}
logger.info(f"Reasoning payload: {API_CONFIG['reasoning']} (exclude:true = no thinking tokens)")

TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}

PURE_FAILURE_COUNTER_KEYS = [
    EXTRACTION_INVALID_JSON,
    FAILED_MISSING_SCORE,
    FAILED_OUT_OF_BOUNDS,
    FAILED_INVALID_SCORE_TYPE,
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN
]


def _init_failure_counters() -> Dict[str, int]:
    return {key: 0 for key in PURE_FAILURE_COUNTER_KEYS}


def _increment_failure_counters(counters: Dict[str, int], failure_types: List[str]) -> None:
    for failure_type in set(failure_types):
        if failure_type in counters:
            counters[failure_type] += 1


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520

def query_openrouter(messages: List[Dict], max_retries: int = MAX_RETRIES) -> Tuple[str, Dict]:
    """Query openrouter.

    Shared request policy across all three architectures (model_config):
    MAX_RETRIES attempts, REQUEST_TIMEOUT-second socket timeout, exponential
    backoff capped at MAX_RETRY_BACKOFF. latency_ms is the wall-clock round trip
    of the *successful* HTTP request only (measured around requests.post),
    excluding retry sleeps and local JSON parsing.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE
    }

    payload = {
        "model": API_CONFIG["model"],
        "messages": messages,
        "temperature": API_CONFIG["temperature"],
    }
    if API_CONFIG["reasoning"]:
        payload["reasoning"] = API_CONFIG["reasoning"]

    diagnostics = {
        "tokens_input": 0,
        "tokens_output": 0,
        "latency_ms": 0,
        "retries": 0,
        "success": False
    }

    attempt = 0
    retry_forever = max_retries <= 0

    while True:
        attempt += 1
        try:
            start_time = time.time()
            response = requests.post(
                API_CONFIG["endpoint"],
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            latency = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                
                # DEBUG: Log full response structure (always log reasoning/thinking data)
                logger.debug(f"=== API RESPONSE (attempt {attempt}) ===")
                logger.debug(f"Full response keys: {list(data.keys())}")
                logger.debug(f"Usage: {data.get('usage', {})}")
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    logger.debug(f"Choice keys: {list(choice.keys())}")
                    if "message" in choice:
                        msg = choice["message"]
                        logger.debug(f"Message keys: {list(msg.keys())}")
                        logger.debug(f"Message role: {msg.get('role')}")
                        logger.debug(f"Message content (first 500 chars): {msg.get('content', '')[:500]}")
                        # Check for reasoning/thinking fields
                        for key in msg.keys():
                            if key not in ['role', 'content']:
                                logger.debug(f"Message extra field '{key}': {msg.get(key)}")

                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Grab token counts if the API sent them
                usage = data.get("usage", {})
                reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                finish_reason = data.get("choices", [{}])[0].get("finish_reason", "?")
                # Always-on progress log: shows pipeline is alive + catches surprise reasoning
                logger.info(
                    f"  [call ok] attempt={attempt} latency={latency/1000:.1f}s "
                    f"prompt={usage.get('prompt_tokens', 0)} "
                    f"completion={usage.get('completion_tokens', 0)} "
                    f"reasoning_tokens={reasoning_tokens} "
                    f"finish={finish_reason}"
                )
                if reasoning_tokens > 0:
                    logger.warning(
                        f"  [WARN] reasoning_tokens={reasoning_tokens} > 0 "
                        f"-- thinking was NOT suppressed despite exclude:true. "
                        f"Consider switching provider or adding /no-think suffix."
                    )

                diagnostics["tokens_input"] = usage.get("prompt_tokens", 0)
                diagnostics["tokens_output"] = usage.get("completion_tokens", 0)
                diagnostics["latency_ms"] = latency
                diagnostics["success"] = True
                diagnostics["retries"] = attempt - 1

                if DEBUG_API:
                    logger.debug(f"Returning content (len={len(content)}): {content[:200]}...")

                return content, diagnostics
            else:
                diagnostics["retries"] = attempt
                if _is_transient_http_status(response.status_code):
                    logging.warning(f"Transient API error {response.status_code}: {response.text}")
                else:
                    logging.error(f"API error {response.status_code}: {response.text}")

                if not retry_forever and attempt >= max_retries:
                    break

                time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
                continue

        except requests.exceptions.RequestException as e:
            logging.warning(f"Request failed (attempt {attempt}): {e}")
            diagnostics["retries"] = attempt
            if not retry_forever and attempt >= max_retries:
                break
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
            continue

        except ValueError as e:
            logging.warning(f"Invalid API JSON envelope (attempt {attempt}): {e}")
            diagnostics["retries"] = attempt
            if not retry_forever and attempt >= max_retries:
                break
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
            continue

    # Retries exhausted — mark API exhaustion explicitly
    diagnostics["failure_types"] = [FAILED_API_EXHAUSTED]
    return None, diagnostics



def build_user_prompt(scenario: Dict, alternative: str) -> str:
    decision_type = scenario.get('decision_type', 'N/A')
    prompt = f'Score this alternative: "{alternative}"\n\n'
    prompt += f'For the decision: "{scenario.get("question", "N/A")}"\n'
    prompt += "SCENARIO CONTEXT:\n"
    prompt += f"- Location: {scenario.get('location', 'N/A')}\n"

    if decision_type == 'HVAC':
        prompt += f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
        prompt += f"- Square Footage: {scenario.get('square_footage', 'N/A')} sqft\n"
        prompt += f"- Insulation: {scenario.get('insulation', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
        prompt += f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
        prompt += f"- House Age: {scenario.get('house_age', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"

    elif decision_type == 'Appliance':
        prompt += f"- Appliance Age Range: {scenario.get('appliance_age', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
        prompt += f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"

    elif decision_type == 'Shower':
        prompt += f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
        prompt += f"- Flow Rate: {scenario.get('flow_rate', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
        prompt += f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"

    prompt += "\nProvide scores (0-1) for all 4 criteria.\n"
    prompt += "Consider how this specific alternative performs given the scenario context.\n"

    return prompt


def score_alternative(scenario: Dict, alternative: str) -> Tuple[Dict, Dict]:

    system_prompt = """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
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

Return ONLY: {"energy_cost": X, "environmental": X, "comfort": X, "practicality": X} where each X is between 0.0 and 1.0.
"""

    user_prompt = build_user_prompt(scenario, alternative)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response, diagnostics = query_openrouter(messages)
    
    # DEBUG: Log the raw scoring response (always log reasoning/thinking data)
    logger.debug(f"=== SCORING RESPONSE for '{alternative}' ===")
    logger.debug(f"Raw response (first 1000 chars): {response[:1000] if response else 'None'}")
    logger.debug(f"Response length: {len(response) if response else 0} chars")
    
    diagnostics.setdefault("failure_types", [])

    api_fallback_scores = {
        "energy_cost": SENTINEL_VALUE,
        "environmental": SENTINEL_VALUE,
        "comfort": SENTINEL_VALUE,
        "practicality": SENTINEL_VALUE,
    }

    parse_failure_scores = {
        "energy_cost": SENTINEL_VALUE,
        "environmental": SENTINEL_VALUE,
        "comfort": SENTINEL_VALUE,
        "practicality": SENTINEL_VALUE,
    }

    if not response:
        logging.error(f"LLM scoring failed for alternative: {alternative}")
        if not diagnostics.get("failure_types"):
            diagnostics["failure_types"] = [FAILED_UNKNOWN]
        return api_fallback_scores, diagnostics


    diagnostics["success"] = False

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        scores = json.loads(text)

        diagnostics["success"] = True
        validation_failed = False
        validation_failure_types = set()

        validated_scores = {}
        for criterion in ["energy_cost", "environmental", "comfort", "practicality"]:
            if criterion not in scores:
                logging.warning(f"Missing score for {criterion}; using sentinel {SENTINEL_VALUE}")
                validated_scores[criterion] = SENTINEL_VALUE
                validation_failed = True
                validation_failure_types.add(FAILED_MISSING_SCORE)
                continue

            raw_score = scores[criterion]

            if isinstance(raw_score, (int, float)):
                raw_value = float(raw_score)
                if 0.0 <= raw_value <= 1.0:
                    validated_scores[criterion] = raw_value
                else:
                    logging.warning(f"Out-of-range score for {criterion}: {raw_value}; using sentinel {SENTINEL_VALUE}")
                    validated_scores[criterion] = SENTINEL_VALUE
                    validation_failed = True
                    validation_failure_types.add(FAILED_OUT_OF_BOUNDS)
            else:
                logging.warning(f"Invalid score type for {criterion}: {raw_score}")
                validated_scores[criterion] = SENTINEL_VALUE
                validation_failed = True
                validation_failure_types.add(FAILED_INVALID_SCORE_TYPE)

        if validation_failed:
            diagnostics["success"] = False
            diagnostics["failure_types"] = sorted(validation_failure_types) if validation_failure_types else [FAILED_UNKNOWN]
            return validated_scores, diagnostics

        diagnostics["failure_types"] = []

        return validated_scores, diagnostics

    except (json.JSONDecodeError, ValueError) as e:
        diagnostics["success"] = False
        diagnostics["failure_types"] = [EXTRACTION_INVALID_JSON]
        logging.error(f"JSON parse failed: {e}. Raw response: {response[:200]}")
        return parse_failure_scores, diagnostics


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    alternatives = [alt["alternative"] for alt in alternatives_scores]


    valid_pairs = []  # (input_idx, weighted_sum)
    for idx, alt_scores in enumerate(alternatives_scores):
        if has_sentinel_scores(alt_scores) or alt_scores.get("failed", False):
            continue
        weighted_sum = (
                CRITERION_WEIGHTS["energy_cost"] * alt_scores["energy_cost"] +
                CRITERION_WEIGHTS["environmental"] * alt_scores["environmental"] +
                CRITERION_WEIGHTS["comfort"] * alt_scores["comfort"] +
                CRITERION_WEIGHTS["practicality"] * alt_scores["practicality"]
        )
        valid_pairs.append((idx, weighted_sum))

    if not valid_pairs:
        return {
            "ranked_alternatives": [],
            "ranks": [SENTINEL_VALUE] * len(alternatives),
            "weighted_scores": [SENTINEL_FLOAT] * len(alternatives)
        }

    valid_pairs_sorted = sorted(valid_pairs, key=lambda x: x[1], reverse=True)
    ranked_alternatives = [alternatives[idx] for idx, _ in valid_pairs_sorted]

    # Keep the indices lined up with the original order
    ranks = [SENTINEL_VALUE] * len(alternatives)
    weighted_scores = [SENTINEL_FLOAT] * len(alternatives)
    for rank_position, (input_idx, ws) in enumerate(valid_pairs_sorted):
        ranks[input_idx] = rank_position + 1
        weighted_scores[input_idx] = ws

    return {
        "ranked_alternatives": ranked_alternatives,
        "ranks": ranks,
        "weighted_scores": weighted_scores
    }

def run_scenario(scenario: Dict) -> Dict:
    alternatives = [
        scenario.get("alternative_1", ""),
        scenario.get("alternative_2", ""),
        scenario.get("alternative_3", "")

    ]

    alternatives_scores = []
    total_diagnostics = {
        "api_calls": 0,
        "total_latency_ms": 0,
        "total_tokens_input": 0,
        "total_tokens_output": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        **_init_failure_counters()
    }

    for alt in alternatives:
        scores, diagnostics = score_alternative(scenario, alt)
        alt_failed = has_sentinel_scores(scores)
        if alt_failed:
            diagnostics["success"] = False

        alternatives_scores.append({
            "alternative": alt,
            "failed": alt_failed,
            **scores
        })

        total_diagnostics["api_calls"] += 1
        total_diagnostics["total_latency_ms"] += diagnostics["latency_ms"]
        total_diagnostics["total_tokens_input"] += diagnostics["tokens_input"]
        total_diagnostics["total_tokens_output"] += diagnostics["tokens_output"]

        if diagnostics["success"]:
            total_diagnostics["successful_calls"] += 1
        else:
            failure_types = diagnostics.get("failure_types") or [FAILED_UNKNOWN]
            total_diagnostics["failed_calls"] += 1
            _increment_failure_counters(total_diagnostics, failure_types)

    total_diagnostics["scenario_failed"] = total_diagnostics["failed_calls"] > 0

    ranking_results = apply_mavt_ranking(alternatives_scores)

    return {
        "decision_type": scenario.get("decision_type", "N/A"),
        "scenario_id": scenario.get("scenario_id", "N/A"),
        "question": scenario.get("question", "N/A"),
        "location": scenario.get("location", "N/A"),
        "outdoor_temp": scenario.get("outdoor_temp", "N/A"),
        "appliance_age": scenario.get("appliance_age", ""),
        "flow_rate": scenario.get("flow_rate", ""),
        "alternatives_scores": alternatives_scores,
        "ranking_results": ranking_results,
        "diagnostics": total_diagnostics
    }


PURE_RESULT_FIELDNAMES = [
    "scenario_id", "decision_type", "question", "location", "outdoor_temp",
    "appliance_age", "flow_rate", "alternative",
    "energy_cost", "environmental", "comfort", "practicality",
    "rank", "weighted_score",
]


def run_test_set(test_path: str, output_path: str, output_diagnostics_path: str) -> Dict:
    """Run a single benchmark pass over the test scenarios and write its xlsx + diagnostics."""
    test_csv_path = Path(test_path)
    output_csv_path = Path(output_path)
    output_diagnostics_path = Path(output_diagnostics_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_diagnostics_path.parent.mkdir(parents=True, exist_ok=True)

    scenarios = []
    df = read_table_clean(
        test_csv_path,
        keep_str_cols=["alternative_1", "alternative_2", "alternative_3"],
    )
    for i, row in df.iterrows():
        record = row.to_dict()
        record["scenario_id"] = i + 1
        scenarios.append(record)

    logging.info(f"Loaded {len(scenarios)} test scenarios from {test_csv_path}")

    all_results = []
    cumulative_diagnostics = {
        "total_scenarios": len(scenarios),
        "total_api_calls": 0,
        "total_latency_ms": 0,
        "total_tokens_input": 0,
        "total_tokens_output": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "successful_scenarios": 0,
        "failed_scenarios": 0,
        **_init_failure_counters()
    }

    for i, scenario in enumerate(scenarios):
        logging.info(f"Processing scenario {i + 1}/{len(scenarios)}: {scenario.get('question', 'N/A')[:50]}...")

        try:
            result = run_scenario(scenario)
        except Exception as e:
            logging.exception(f"Scenario crashed and was marked failed: {e}")
            fallback_alternatives = [
                scenario.get("alternative_1", ""),
                scenario.get("alternative_2", ""),
                scenario.get("alternative_3", "")
            ]
            result = {
                "decision_type": scenario.get("decision_type", "N/A"),
                "scenario_id": scenario.get("scenario_id", "N/A"),
                "question": scenario.get("question", "N/A"),
                "location": scenario.get("location", "N/A"),
                "outdoor_temp": scenario.get("outdoor_temp", "N/A"),
                "appliance_age": scenario.get("appliance_age", ""),
                "flow_rate": scenario.get("flow_rate", ""),
                "alternatives_scores": [
                    {
                        "alternative": alt,
                        "energy_cost": None,
                        "environmental": None,
                        "comfort": None,
                        "practicality": None,
                    }
                    for alt in fallback_alternatives
                ],
                "ranking_results": {
                    "ranked_alternatives": [],
                    "ranks": [SENTINEL_VALUE, SENTINEL_VALUE, SENTINEL_VALUE],
                    "weighted_scores": [SENTINEL_FLOAT, SENTINEL_FLOAT, SENTINEL_FLOAT],
                    "error": str(e)
                },
                "diagnostics": {
                    "api_calls": 0,
                    "total_latency_ms": 0,
                    "total_tokens_input": 0,
                    "total_tokens_output": 0,
                    "successful_calls": 0,
                    "failed_calls": len(fallback_alternatives),
                    "scenario_failed": True,
                    "scenario_error": str(e),
                    **_init_failure_counters()
                }
            }

        all_results.append(result)

        diag = result["diagnostics"]
        cumulative_diagnostics["total_api_calls"] += diag["api_calls"]
        cumulative_diagnostics["total_latency_ms"] += diag["total_latency_ms"]
        cumulative_diagnostics["total_tokens_input"] += diag["total_tokens_input"]
        cumulative_diagnostics["total_tokens_output"] += diag["total_tokens_output"]
        cumulative_diagnostics["successful_calls"] += diag["successful_calls"]
        cumulative_diagnostics["failed_calls"] += diag["failed_calls"]
        for counter_key in PURE_FAILURE_COUNTER_KEYS:
            cumulative_diagnostics[counter_key] += diag.get(counter_key, 0)
        if diag.get("scenario_failed", False):
            cumulative_diagnostics["failed_scenarios"] += 1
        else:
            cumulative_diagnostics["successful_scenarios"] += 1

    avg_latency = cumulative_diagnostics["total_latency_ms"] / max(cumulative_diagnostics["total_api_calls"], 1)
    scenario_success_rate = cumulative_diagnostics["successful_scenarios"] / max(cumulative_diagnostics["total_scenarios"], 1)

    cumulative_diagnostics["avg_latency_ms"] = avg_latency
    cumulative_diagnostics["scenario_success_rate"] = scenario_success_rate

    # Build a rows list and write via pandas to preserve Excel output semantics
    rows = []
    for result in all_results:
        scenario_id = result["scenario_id"]
        question = result["question"]
        location = result["location"]
        outdoor_temp = result["outdoor_temp"]
        appliance_age = result["appliance_age"]
        flow_rate = result["flow_rate"]
        decision_type = result["decision_type"]
        scenario_failed = result.get("diagnostics", {}).get("scenario_failed", False)

        ranks = result["ranking_results"]["ranks"]
        weighted_scores = result["ranking_results"]["weighted_scores"]

        for alt_idx, alt_scores in enumerate(result["alternatives_scores"]):
            alt = alt_scores["alternative"]

            if scenario_failed:
                energy_cost = SENTINEL_VALUE
                environmental = SENTINEL_VALUE
                comfort = SENTINEL_VALUE
                practicality = SENTINEL_VALUE
                rank = SENTINEL_VALUE
                weighted_score = SENTINEL_FLOAT
            else:
                energy_cost = alt_scores["energy_cost"]
                environmental = alt_scores["environmental"]
                comfort = alt_scores["comfort"]
                practicality = alt_scores["practicality"]
                rank = ranks[alt_idx]
                weighted_score = weighted_scores[alt_idx]

            rows.append({
                "scenario_id": scenario_id,
                "decision_type": decision_type,
                "question": question,
                "location": location,
                "outdoor_temp": outdoor_temp,
                "appliance_age": appliance_age,
                "flow_rate": flow_rate,
                "alternative": alt,
                "energy_cost": energy_cost,
                "environmental": environmental,
                "comfort": comfort,
                "practicality": practicality,
                "rank": rank,
                "weighted_score": weighted_score
            })

    _atomic_write_xlsx(pd.DataFrame(rows, columns=PURE_RESULT_FIELDNAMES), output_csv_path)
    logging.info(f"Results saved to {output_csv_path}")

    _atomic_write_json(cumulative_diagnostics, output_diagnostics_path)
    logging.info(f"Diagnostics saved to {output_diagnostics_path}")

    return cumulative_diagnostics


def run_multi_and_aggregate(test_csv_path: str, base_output_csv: str,
                            base_diagnostics_path: str) -> None:
    """Run the benchmark N_RUNS times and average the per-run xlsx outputs.

    Resume-aware: a per-run xlsx that already exists, has size > 0, has no
    leftover .tmp sibling, and is a readable non-empty DataFrame is treated as
    a completed run and skipped. Any other state triggers a re-run.
    """
    base = Path(base_output_csv)
    base_diag = Path(base_diagnostics_path)
    run_paths = []
    skipped_runs = []

    for run_idx in range(1, N_RUNS + 1):
        run_path = base.with_name(f"{base.stem}_run_{run_idx:02d}{base.suffix}")
        diag_path = base_diag.with_name(f"{base_diag.stem}_run_{run_idx:02d}{base_diag.suffix}")
        if _is_complete_run_file(run_path):
            logging.info(f"--- Run {run_idx}/{N_RUNS}: resuming from {run_path.name} ---")
            run_paths.append(run_path)
            skipped_runs.append(run_idx)
            continue
        logging.info(f"--- Run {run_idx}/{N_RUNS} -> {run_path.name} ---")
        try:
            run_test_set(str(test_csv_path), str(run_path), str(diag_path))
            run_paths.append(run_path)
        except Exception as e:
            logging.error(f"Run {run_idx} failed and will be excluded from aggregation: {e}")

    if skipped_runs:
        logging.info(f"Resumed {len(skipped_runs)} existing run(s): {skipped_runs}")

    n_runs = len(run_paths)
    if n_runs == 0:
        logging.error("All runs failed. No aggregation possible.")
        return
    if n_runs < N_RUNS:
        logging.warning(
            f"Only {n_runs}/{N_RUNS} runs completed. "
            f"Aggregating over {n_runs} runs."
        )
    logging.info(f"{n_runs}/{N_RUNS} runs complete. Aggregating scores...")

    valid_run_paths = []
    run_dfs = []
    for p in run_paths:
        try:
            run_dfs.append(read_table_clean(p))
            valid_run_paths.append(p)
        except Exception as e:
            logging.warning(f"Could not read {p.name}, skipping from aggregation: {e}")
    if len(run_dfs) == 0:
        logging.error("No run files could be read. Aggregation aborted.")
        return
    n_readable = len(run_dfs)
    if n_readable < n_runs:
        logging.warning(f"Aggregating over {n_readable}/{n_runs} readable runs.")

    combined = pd.concat(run_dfs, ignore_index=True)
    combined = combined.drop(columns=["rank", "weighted_score"], errors="ignore")

    CRITERIA_COLS = ["energy_cost", "environmental", "comfort", "practicality"]
    SENTINEL = SENTINEL_FLOAT

    # Use pd.to_numeric (coerce) — handles string "1928" and malformed values
    for c in CRITERIA_COLS:
        combined[c] = pd.to_numeric(combined[c], errors="coerce")
        # Treat exact sentinel float as a failed row
        combined.loc[combined[c] == SENTINEL, c] = np.nan

    GROUP_KEYS = ["scenario_id", "alternative"]
    META_COLS = [
        "decision_type", "question", "location",
        "outdoor_temp", "appliance_age", "flow_rate",
    ]

    # Count how many runs contributed a non-NaN value per (scenario, alternative)
    n_valid_runs = combined.groupby(GROUP_KEYS)[CRITERIA_COLS[0]].apply(
        lambda s: s.notna().sum()
    ).reset_index(name="n_successful_runs")

    avg_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].mean()
    std_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].std()
    avg_meta = combined.groupby(GROUP_KEYS, as_index=False)[META_COLS].first()

    avg = avg_criteria.merge(avg_meta, on=GROUP_KEYS)
    avg = avg.merge(n_valid_runs, on=GROUP_KEYS)
    avg["n_runs"] = n_readable
    avg["n_failed_runs"] = avg["n_runs"] - avg["n_successful_runs"]

    std_criteria = std_criteria.rename(columns={c: f"{c}_std" for c in CRITERIA_COLS})
    stats_df = avg.merge(std_criteria, on=GROUP_KEYS)

    # When N=1, pandas std returns NaN — annotate clearly in the stats output
    if n_readable == 1:
        logging.warning(
            "Only 1 run aggregated — std columns will be NaN (undefined for N=1)."
        )
        for c in CRITERIA_COLS:
            col = f"{c}_std"
            if col in stats_df.columns:
                stats_df[col] = "N/A (N=1)"

    # Put 1928 back anywhere every run failed for that alternative
    for c in CRITERIA_COLS:
        avg[c] = avg[c].fillna(SENTINEL)

    # Re-rank each scenario using the averaged scores
    avg["rank"] = int(SENTINEL)
    avg["weighted_score"] = float(SENTINEL)

    for sid in avg["scenario_id"].unique():
        sc_mask = avg["scenario_id"] == sid
        sc = avg[sc_mask]
        valid_idx = sc.index[~sc[CRITERIA_COLS].eq(SENTINEL).any(axis=1)]
        if len(valid_idx) > 0:
            ws = (
                avg.loc[valid_idx, "energy_cost"] * CRITERION_WEIGHTS["energy_cost"] +
                avg.loc[valid_idx, "environmental"] * CRITERION_WEIGHTS["environmental"] +
                avg.loc[valid_idx, "comfort"] * CRITERION_WEIGHTS["comfort"] +
                avg.loc[valid_idx, "practicality"] * CRITERION_WEIGHTS["practicality"]
            )
            avg.loc[valid_idx, "weighted_score"] = ws
            avg.loc[valid_idx, "rank"] = ws.rank(ascending=False, method="min").astype(int)

    col_order = [
        "scenario_id", "decision_type", "question", "location", "outdoor_temp",
        "appliance_age", "flow_rate", "alternative",
        "energy_cost", "environmental", "comfort", "practicality",
        "rank", "weighted_score",
        "n_runs", "n_successful_runs", "n_failed_runs",
    ]
    _atomic_write_xlsx(avg.reindex(columns=col_order), base_output_csv)
    logging.info(f"Averaged results ({n_readable} runs) saved to {base_output_csv}")

    stats_path = base.with_name(f"{base.stem}_stats{base.suffix}")
    _atomic_write_xlsx(stats_df, stats_path)
    logging.info(f"Score statistics saved to {stats_path}")


def main():
    if not os.getenv("OPENROUTER_API_KEY"):
        logging.error("OPENROUTER_API_KEY not found in .env file")
        return

    logging.info("Starting Direct LLM Scoring Architecture Test...")
    logging.info(f"Model: {API_CONFIG['model']}")
    logging.info(f"Temperature: {API_CONFIG['temperature']}")
    try:
        df = read_table_clean(
            TEST_SCENARIOS,
            keep_str_cols=["alternative_1", "alternative_2", "alternative_3"],
        )
        required_cols = ['question', 'decision_type', 'alternative_1', 'alternative_2', 'alternative_3']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logging.error(f"Missing required columns: {missing_cols}")
            logging.error("Input must have: question, decision_type, alternative_1, alternative_2, alternative_3")
            logging.error("Plus decision-type-specific columns")
            return

        decision_types = set(df.get('decision_type', pd.Series(dtype=str)).fillna('UNKNOWN'))
        logging.info("Input validation passed")
        logging.info(f"  Decision types found: {decision_types}")

    except FileNotFoundError:
        logging.error(f"Test file not found: {TEST_SCENARIOS}")
        return
    except Exception as e:
        logging.error(f" Input validation error: {e}")
        return

    output_dir = PROJECT_ROOT / get_output_folder_for_model_id(API_CONFIG["model"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_xlsx = output_dir / "Direct_LLM_Scoring_results.xlsx"
    output_diagnostics = output_dir / "Direct_LLM_Scoring_results_diagnostics.json"

    run_multi_and_aggregate(str(TEST_SCENARIOS), str(output_xlsx), str(output_diagnostics))
    logging.info("DIRECT LLM SCORING MULTI-RUN COMPLETE")



if __name__ == "__main__":
    main()
