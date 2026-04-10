import os
import sys
import json
import csv
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
 Role play with large language models. Nature, 623(7987), 493â€“498.
 https://doi.org/10.1038/s41586-023-06647-8

 2. Structured output constraint ("return ONLY JSON")
 Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models.
 NeurIPS 2022. https://proceedings.neurips.cc/paper/2022/file/9d5609613524ecf4f15af0f7b31abca4-Paper-Conference.pdf

 3. RAG context injection ("use retrieved examples as reference but score independently")
 Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks.
 NeurIPS 2020. https://proceedings.neurips.cc/paper/2020/file/6b493230205f780e1bc26945df7481e5-Paper.pdf

 4. Hybrid parameter extraction ("extract parameters then compute")
 Khot, T., et al. (2023). Decomposed prompting: A modular approach for solving complex tasks.
 ICLR 2023. https://arxiv.org/abs/2210.02406

 5. "Reasonably estimate if not apparent" (bias mitigation)
 Galaz, V., et al. (2021). Artificial intelligence, systemic risks, and sustainability.
 Technology in Society, 67, 101741. https://doi.org/10.1016/j.techsoc.2021.101741

"""

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import CRITERION_WEIGHTS, get_model_id, get_output_folder, N_RUNS
from sentinel_utils import has_sentinel_scores

TEST_SCENARIOS_CSV = PROJECT_ROOT / "Scenario Files" / "TestScenarios.csv"
OUTPUT_DIR = PROJECT_ROOT / get_output_folder()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

MODEL_ID = get_model_id()

API_CONFIG = {
    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    "model": MODEL_ID,
    "temperature": 0.3  # Need determinism for reliability
}

TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}

PURE_FAILURE_COUNTER_KEYS = [
    "failed_malformed_json",
    "failed_missing_score",
    "failed_out_of_bounds",
    "failed_invalid_score_type",
    "failed_unknown"
]


def _init_failure_counters() -> Dict[str, int]:
    return {key: 0 for key in PURE_FAILURE_COUNTER_KEYS}


def _increment_failure_counters(counters: Dict[str, int], failure_types: List[str], increment: int = 1) -> None:
    for failure_type in set(failure_types):
        if failure_type in counters:
            counters[failure_type] += increment


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520

def query_openrouter(messages: List[Dict], max_retries: int = 5) -> Tuple[str, Dict]:
    """
    Query OpenRouter API with retry logic

    Args:
        messages: List of message dicts with role and content
        max_retries: Number of retry attempts

    Returns:
        Tuple of (response_text, diagnostics_dict)
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": API_CONFIG["model"],
        "messages": messages,
        "temperature": API_CONFIG["temperature"]
    }

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
                timeout=60
            )
            latency = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Extract token usage if available
                usage = data.get("usage", {})
                diagnostics["tokens_input"] = usage.get("prompt_tokens", 0)
                diagnostics["tokens_output"] = usage.get("completion_tokens", 0)
                diagnostics["latency_ms"] = latency
                diagnostics["success"] = True
                diagnostics["retries"] = attempt - 1

                return content, diagnostics
            else:
                diagnostics["retries"] = attempt
                if _is_transient_http_status(response.status_code):
                    logging.warning(f"Transient API error {response.status_code}: {response.text}")
                else:
                    logging.error(f"API error {response.status_code}: {response.text}")

                if not retry_forever and attempt >= max_retries:
                    break

                time.sleep(min(2 ** min(attempt - 1, 6), 60))
                continue

        except requests.exceptions.RequestException as e:
            logging.warning(f"Request failed (attempt {attempt}): {e}")
            diagnostics["retries"] = attempt
            if not retry_forever and attempt >= max_retries:
                break
            time.sleep(min(2 ** min(attempt - 1, 6), 60))
            continue

        except ValueError as e:
            logging.warning(f"Invalid API JSON envelope (attempt {attempt}): {e}")
            diagnostics["retries"] = attempt
            if not retry_forever and attempt >= max_retries:
                break
            time.sleep(min(2 ** min(attempt - 1, 6), 60))
            continue

    # Only reachable when finite retries are exhausted.
    return None, diagnostics


def build_user_prompt(scenario: Dict, alternative: str) -> str:
    decision_type = scenario.get('Decision Type', 'HVAC')
    prompt = f'Score this alternative: "{alternative}"\n\n'
    prompt += f'For the decision: "{scenario.get("Question", "N/A")}"\n\n'
    prompt += "SCENARIO CONTEXT:\n"
    prompt += f"- Location: {scenario.get('Location', 'N/A')}\n"

    if decision_type == 'HVAC':
        prompt += f"- Outdoor Temperature: {scenario.get('Outdoor Temp', 'N/A')}°F\n"
        prompt += f"- Home Size: {scenario.get('Square Footage', 'N/A')} sq ft\n"
        prompt += f"- Insulation: {scenario.get('Insulation', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('Household Size', 'N/A')} people\n"
        prompt += f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
        prompt += f"- House Age: {scenario.get('House Age', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"

    elif decision_type == 'Appliance':
        prompt += f"- Appliance Age: {scenario.get('Appliance Age', 'N/A')}\n"
        prompt += f"- Household Size: {scenario.get('Household Size', 'N/A')} people\n"
        prompt += f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"

    elif decision_type == 'Shower':
        prompt += f"- Flow Rate: {scenario.get('Flow rate', 'N/A')}\n"
        prompt += f"- Outdoor Temperature: {scenario.get('Outdoor Temp', 'N/A')}°F\n"
        prompt += f"- Household Size: {scenario.get('Household Size', 'N/A')} people\n"
        prompt += f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
        prompt += f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"

    prompt += "\nProvide scores (0-10) for all 4 criteria using the calibrations in the system prompt.\n"
    prompt += "Consider how this specific alternative performs given the scenario context.\n"

    return prompt


def score_alternative(scenario: Dict, alternative: str) -> Tuple[Dict, Dict]:
    system_prompt = f"""You are an expert household energy decision analyst. Score alternatives on 
four criteria using the full 0-10 scale:
- energy_cost: lower cost = higher score
- environmental: lower emissions = higher score  
- comfort: higher comfort = higher score
- practicality: easier adoption = higher score

Return ONLY: {"energy_cost": X, "environmental": X, "comfort": X, "practicality": X}
"""
    user_prompt = build_user_prompt(scenario, alternative)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response, diagnostics = query_openrouter(messages)
    diagnostics["failure_types"] = []

    api_fallback_scores = {
        "energy_cost": 1928,
        "environmental": 1928,
        "comfort": 1928,
        "practicality": 1928,
        "reasoning": "API/environment failure - using neutral defaults"
    }

    parse_failure_scores = {
        "energy_cost": 1928,
        "environmental": 1928,
        "comfort": 1928,
        "practicality": 1928,
        "reasoning": "Parsing/validation failure - using sentinel defaults"
    }

    if not response:
        logging.error(f"LLM scoring failed for alternative: {alternative}")
        diagnostics["failure_types"] = ["failed_unknown"]
        return api_fallback_scores, diagnostics


    diagnostics["success"] = False

    try:
        # Strip markdown code fences if present (Claude via OpenRouter wraps JSON in ```json ... ```)
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
                logging.warning(f"Missing score for {criterion}; using sentinel 1928")
                validated_scores[criterion] = 1928
                validation_failed = True
                validation_failure_types.add("failed_missing_score")
                continue

            raw_score = scores[criterion]

            if isinstance(raw_score, (int, float)):
                raw_value = float(raw_score)
                if 0.0 <= raw_value <= 10.0:
                    validated_scores[criterion] = raw_value
                else:
                    logging.warning(f"Out-of-range score for {criterion}: {raw_value}; using sentinel 1928")
                    validated_scores[criterion] = 1928
                    validation_failed = True
                    validation_failure_types.add("failed_out_of_bounds")
            else:
                logging.warning(f"Invalid score type for {criterion}: {raw_score}")
                validated_scores[criterion] = 1928
                validation_failed = True
                validation_failure_types.add("failed_invalid_score_type")

        if validation_failed:
            diagnostics["success"] = False
            diagnostics["failure_types"] = sorted(validation_failure_types) if validation_failure_types else ["failed_unknown"]
            validated_scores["reasoning"] = "Validation failure - sentinel applied"
            return validated_scores, diagnostics

        validated_scores["reasoning"] = scores.get("reasoning", "No reasoning provided")
        diagnostics["failure_types"] = []

        return validated_scores, diagnostics

    except (json.JSONDecodeError, ValueError) as e:
        diagnostics["success"] = False
        diagnostics["failure_types"] = ["failed_malformed_json"]
        logging.error(f"JSON parse failed: {e}. Raw response: {response[:200]}")
        return parse_failure_scores, diagnostics


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    """
    Apply MAVT weighted sum to rank alternatives.

    Alternatives with sentinel scores (1928) or marked failed are excluded
    from ranking. No fallback averaging — if ranking fails, it propagates.

    Args:
        alternatives_scores: List of dicts with keys: alternative, energy_cost, environmental, comfort, practicality

    Returns:
        Dict with ranked_alternatives, ranks, weighted_scores
    """
    alternatives = [alt["alternative"] for alt in alternatives_scores]
    valid_indices = []

    # Calculate weighted sum for each alternative
    weighted_scores = []
    for idx, alt_scores in enumerate(alternatives_scores):
        if has_sentinel_scores(alt_scores) or alt_scores.get("failed", False):
            continue

        weighted_sum = (
                CRITERION_WEIGHTS["energy_cost"] * alt_scores["energy_cost"] +
                CRITERION_WEIGHTS["environmental"] * alt_scores["environmental"] +
                CRITERION_WEIGHTS["comfort"] * alt_scores["comfort"] +
                CRITERION_WEIGHTS["practicality"] * alt_scores["practicality"]
        )
        weighted_scores.append(weighted_sum)
        valid_indices.append(idx)

    if not valid_indices:
        return {
            "ranked_alternatives": [],
            "ranks": [1928] * len(alternatives),
            "weighted_scores": []
        }

    # Rank alternatives (higher weighted sum = better = lower rank number)
    ranked_indices = np.argsort(weighted_scores)[::-1]  # Descending order
    ranked_alternatives = [alternatives[valid_indices[i]] for i in ranked_indices]

    # Create rank numbers (1 = best, 2 = second, 3 = third)
    ranks = [1928] * len(alternatives)
    for rank_position, local_index in enumerate(ranked_indices):
        ranks[valid_indices[local_index]] = rank_position + 1

    return {
        "ranked_alternatives": ranked_alternatives,
        "ranks": ranks,
        "weighted_scores": weighted_scores
    }

def run_scenario(scenario: Dict) -> Dict:
    """
    Process one scenario: score all alternatives and rank them

    Args:
        scenario: Full scenario dict

    Returns:
        Results dict with rankings, scores, and diagnostics
    """
    alternatives = [
        scenario.get("Alternative 1", ""),
        scenario.get("Alternative 2", ""),
        scenario.get("Alternative 3", "")

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
        alt_failed = any(scores.get(c) == 1928 for c in ["energy_cost", "environmental", "comfort", "practicality"])
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
            failure_types = diagnostics.get("failure_types")
            if failure_types:
                total_diagnostics["failed_calls"] += 1
                _increment_failure_counters(total_diagnostics, failure_types)
            elif failure_types is None:
                total_diagnostics["failed_calls"] += 1
                _increment_failure_counters(total_diagnostics, ["failed_unknown"])

    total_diagnostics["scenario_failed"] = total_diagnostics["failed_calls"] > 0

    ranking_results = apply_mavt_ranking(alternatives_scores)

    return {
        "decision_type": scenario.get("Decision Type", "N/A"),
        "scenario_id": scenario.get("scenario_id", "N/A"),

        "question": scenario.get("Question", "N/A"),
        "location": scenario.get("Location", "N/A"),
        "outdoor_temp": scenario.get("Outdoor Temp", "N/A"),
        "appliance_age": scenario.get("Appliance Age", ""),
        "flow_rate": scenario.get("Flow rate", ""),
        "alternatives_scores": alternatives_scores,
        "ranking_results": ranking_results,
        "diagnostics": total_diagnostics
    }


def run_test_set(test_csv_path: str, output_csv_path: str) -> Dict:
    """
    Run Pure Prompting on test set

    Args:
        test_csv_path: Path to test scenarios CSV
        output_csv_path: Path to save results CSV

    Returns:
        Summary statistics dict
    """
    test_csv_path = Path(test_csv_path)
    output_csv_path = Path(output_csv_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    scenarios = []
    with open(test_csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            row['scenario_id'] = i + 1
            scenarios.append(row)

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
        logging.info(f"Processing scenario {i + 1}/{len(scenarios)}: {scenario.get('Question', 'N/A')[:50]}...")

        try:
            result = run_scenario(scenario)
        except Exception as e:
            logging.exception(f"Scenario crashed and was marked failed: {e}")
            fallback_alternatives = [
                scenario.get("Alternative 1", ""),
                scenario.get("Alternative 2", ""),
                scenario.get("Alternative 3", "")
            ]
            result = {
                "decision_type": scenario.get("Decision Type", "N/A"),
                "scenario_id": scenario.get("scenario_id", "N/A"),
                "question": scenario.get("Question", "N/A"),
                "location": scenario.get("Location", "N/A"),
                "outdoor_temp": scenario.get("Outdoor Temp", "N/A"),
                "appliance_age": scenario.get("Appliance Age", ""),
                "flow_rate": scenario.get("Flow rate", ""),
                "alternatives_scores": [
                    {
                        "alternative": alt,
                        "energy_cost": None,
                        "environmental": None,
                        "comfort": None,
                        "practicality": None,
                        "reasoning": "Scenario runtime failure"
                    }
                    for alt in fallback_alternatives
                ],
                "ranking_results": {
                    "ranked_alternatives": fallback_alternatives,
                    "ranks": [1, 2, 3],
                    "weighted_scores": [0.0, 0.0, 0.0],
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
    success_rate = cumulative_diagnostics["successful_scenarios"] / max(cumulative_diagnostics["total_scenarios"], 1)

    cumulative_diagnostics["avg_latency_ms"] = avg_latency
    cumulative_diagnostics["success_rate"] = success_rate

    with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            "scenario_id", "decision_type", "question", "location", "outdoor_temp", "appliance_age", "flow_rate",
            "alternative", "energy_cost", "environmental", "comfort", "practicality",
            "rank", "weighted_score"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

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
            ranked_alts = result["ranking_results"]["ranked_alternatives"]
            ws_list = result["ranking_results"]["weighted_scores"]
            ws_lookup = {alt: ws_list[i] for i, alt in enumerate(ranked_alts)}

            for alt_idx, alt_scores in enumerate(result["alternatives_scores"]):
                alt = alt_scores["alternative"]

                if scenario_failed:
                    energy_cost = 1928
                    environmental = 1928
                    comfort = 1928
                    practicality = 1928
                    rank = 1928
                    weighted_score = 1928
                else:
                    energy_cost = alt_scores["energy_cost"]
                    environmental = alt_scores["environmental"]
                    comfort = alt_scores["comfort"]
                    practicality = alt_scores["practicality"]
                    rank = ranks[alt_idx]
                    weighted_score = ws_lookup.get(alt, 1928)

                writer.writerow({
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

    logging.info(f"Results saved to {output_csv_path}")

    diagnostics_path = output_csv_path.with_name(f"{output_csv_path.stem}_diagnostics.json")
    with open(diagnostics_path, 'w') as f:
        json.dump(cumulative_diagnostics, f, indent=2)

    logging.info(f"Diagnostics saved to {diagnostics_path}")

    return cumulative_diagnostics


def run_multi_and_aggregate(test_csv_path: str, base_output_csv: str) -> None:
    """
    Run the test set N_RUNS times, save per-run CSVs, then write a single
    averaged results CSV (same schema as a single run) to base_output_csv.
    Also writes a _stats.csv with per-criterion std dev.
    """
    base = Path(base_output_csv)
    run_paths = []

    for run_idx in range(1, N_RUNS + 1):
        run_path = base.with_name(f"{base.stem}_run_{run_idx:02d}{base.suffix}")
        logging.info(f"--- Run {run_idx}/{N_RUNS} -> {run_path.name} ---")
        try:
            run_test_set(str(test_csv_path), str(run_path))
            run_paths.append(run_path)
        except Exception as e:
            logging.error(f"Run {run_idx} failed and will be excluded from aggregation: {e}")

    if len(run_paths) == 0:
        logging.error("All runs failed. No aggregation possible.")
        return
    if len(run_paths) < N_RUNS:
        logging.warning(
            f"Only {len(run_paths)}/{N_RUNS} runs completed. "
            f"Aggregating over {len(run_paths)} runs."
        )
    logging.info(f"{len(run_paths)}/{N_RUNS} runs complete. Aggregating scores...")

    valid_run_paths = []
    run_dfs = []
    for p in run_paths:
        try:
            run_dfs.append(pd.read_csv(p, encoding='utf-8-sig'))
            valid_run_paths.append(p)
        except Exception as e:
            logging.warning(f"Could not read {p.name}, skipping from aggregation: {e}")
    if len(run_dfs) == 0:
        logging.error("No run files could be read. Aggregation aborted.")
        return
    if len(run_dfs) < len(run_paths):
        logging.warning(f"Aggregating over {len(run_dfs)}/{len(run_paths)} readable runs.")
    combined = pd.concat(run_dfs, ignore_index=True)
    combined = combined.drop(columns=["rank", "weighted_score"], errors="ignore")

    CRITERIA_COLS = ["energy_cost", "environmental", "comfort", "practicality"]
    SENTINEL = 1928.0

    for c in CRITERIA_COLS:
        combined[c] = combined[c].astype(float)

    # Exclude the entire row from averaging if any criterion is sentinel
    failed_mask = combined[CRITERIA_COLS].eq(SENTINEL).any(axis=1)
    combined.loc[failed_mask, CRITERIA_COLS] = np.nan

    GROUP_KEYS = ["scenario_id", "alternative"]
    META_COLS = [
        "decision_type", "question", "location",
        "outdoor_temp", "appliance_age", "flow_rate",
    ]

    avg_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].mean()
    std_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].std()
    avg_meta = combined.groupby(GROUP_KEYS, as_index=False)[META_COLS].first()

    avg = avg_criteria.merge(avg_meta, on=GROUP_KEYS)
    std_criteria = std_criteria.rename(columns={c: f"{c}_std" for c in CRITERIA_COLS})
    stats_df = avg.merge(std_criteria, on=GROUP_KEYS)

    # Fill NaN (all runs failed for that alternative) back to sentinel
    for c in CRITERIA_COLS:
        avg[c] = avg[c].fillna(SENTINEL)

    # Re-rank within each scenario using averaged scores
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
    ]
    avg = avg.reindex(columns=col_order)
    avg.to_csv(base_output_csv, index=False, encoding='utf-8-sig')
    logging.info(f"Averaged results ({N_RUNS} runs) saved to {base_output_csv}")

    stats_path = base.with_name(f"{base.stem}_stats{base.suffix}")
    stats_df.to_csv(str(stats_path), index=False, encoding='utf-8-sig')
    logging.info(f"Score statistics saved to {stats_path}")


def main():
    """Main execution function"""

    if not os.getenv("OPENROUTER_API_KEY"):
        logging.error("OPENROUTER_API_KEY not found in .env file")
        return

    test_csv = TEST_SCENARIOS_CSV
    output_csv = OUTPUT_DIR / "pure_prompting_results.csv"

    logging.info("Starting Pure Prompting Architecture Test...")
    logging.info(f"Model: {API_CONFIG['model']}")
    logging.info(f"Temperature: {API_CONFIG['temperature']}")
    import csv as csv_module
    try:
        with open(test_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv_module.DictReader(f)
            first_row = next(reader)

            required_cols = ['Question', 'Decision Type', 'Alternative 1', 'Alternative 2', 'Alternative 3']
            missing_cols = [col for col in required_cols if col not in first_row]

            if missing_cols:
                logging.error(f"Missing required columns: {missing_cols}")
                logging.error("CSV must have: Question, Decision Type, Alternative 1, Alternative 2, Alternative 3")
                logging.error("Plus decision-type-specific columns")
                return

            # Check decision types
            f.seek(0)
            fresh_reader = csv_module.DictReader(f)
            decision_types = set([row.get('Decision Type', 'UNKNOWN') for row in fresh_reader])

            logging.info(f"CSV validation passed")
            logging.info(f"  Decision types found: {decision_types}")

    except FileNotFoundError:
        logging.error(f"Test file not found: {test_csv}")
        return
    except Exception as e:
        logging.error(f" CSV validation error: {e}")
        return

    run_multi_and_aggregate(str(test_csv), str(output_csv))
    logging.info("PURE PROMPTING MULTI-RUN COMPLETE")



if __name__ == "__main__":
    main()
