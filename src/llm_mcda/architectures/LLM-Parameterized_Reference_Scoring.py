import os
import sys
import json
import requests
import time
import importlib.util
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import (
    CRITERION_WEIGHTS,
    TIE_BREAK_PRIORITY,
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
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN,
    FAILED_EXTRACTION_NON_JSON_WRAPPER,
    FAILED_EXTRACTION_INVALID_DECISION_TYPE,
    FAILED_EXTRACTION_INVALID_CALCULATOR,
    FAILED_EXTRACTION_MISSING_PARAMETERS,
    FAILED_EXTRACTION_INVALID_PARAMETERS,
    FAILED_EXTRACTION_DECISION_TYPE_MISMATCH,
    FAILED_EXTRACTION_EXCEPTION,
    FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION,
    FAILED_GROUND_TRUTH_MISSING_KEY,
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
GROUND_TRUTH_CALCULATORS_DIR = PROJECT_ROOT / "Ground Truth Calculators"

def _load_calculator_class(module_filename: str, class_name: str):
    module_path = GROUND_TRUTH_CALCULATORS_DIR / module_filename
    spec = importlib.util.spec_from_file_location(class_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


try:
    HVACGroundTruthCalculator = _load_calculator_class(
        "HVACGroundTruthCalculator.py", "HVACGroundTruthCalculator"
    )
except Exception as e:
    raise RuntimeError(f"Cannot initialize LLM-Parameterized_Reference_Scoring without HVAC calculator: {e}") from e

try:
    ApplianceGroundTruthCalculator = _load_calculator_class(
        "ApplianceGroundTruthCalculator.py", "ApplianceGroundTruthCalculator"
    )
except Exception as e:
    raise RuntimeError(f"Cannot initialize LLM-Parameterized_Reference_Scoring without Appliance calculator: {e}") from e

try:
    ShowerGroundTruthCalculator = _load_calculator_class(
        "ShowerGroundTruthCalculator.py", "ShowerGroundTruthCalculator"
    )
except Exception as e:
    raise RuntimeError(f"Cannot initialize LLM-Parameterized_Reference_Scoring without Shower calculator: {e}") from e


load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

DEBUG_API = os.getenv("DEBUG_API", "false").lower() == "true"

import logging
DEBUG_LEVEL = logging.DEBUG if DEBUG_API else logging.INFO
logging.basicConfig(
    level=DEBUG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables!")

OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")

MODEL_ID = get_model_id()
REASONING_PAYLOAD = get_reasoning_payload()

API_CONFIG = {
    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    "model": MODEL_ID,
    "temperature": TEMPERATURE,
    "reasoning": REASONING_PAYLOAD,
}
logger.info(f"Reasoning payload: {API_CONFIG['reasoning']}")

if DEBUG_API:
    logger.debug(f"DEBUG_API mode enabled - will log full API responses")
    logger.debug(f"Model: {MODEL_ID}")
    logger.debug(f"Temperature: {TEMPERATURE}")
    logger.debug(f"Max retries: {MAX_RETRIES}")
    logger.debug(f"Request timeout: {REQUEST_TIMEOUT}s")

TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}

LLM_Parameterized_Reference_Scoring_RESULT_FIELDNAMES = [
    'scenario_id', 'question', 'location',
    'input_decision_type', 'extracted_decision_type', 'decision_type',
    'outdoor_temp', 'appliance_age', 'flow_rate',
    'extracted_r_value', 'extracted_seer', 'extracted_hvac_age',
    'extracted_occupancy_context', 'extracted_appliance',
    'extracted_kwh_per_cycle', 'extracted_baseline_time',
    'extracted_gpm', 'extracted_tank_size', 'extracted_water_heater_temp',
    'calculator', 'extraction_failed', 'gt_calculation_failed',
    'alternative', 'extracted_alternative',
    'energy_cost', 'environmental', 'comfort', 'practicality',
    'rank', 'weighted_score',
]

LLM_Parameterized_Reference_Scoring_NUMERIC_EXTRACTED_COLS = [
    'extracted_r_value', 'extracted_seer', 'extracted_hvac_age',
    'extracted_kwh_per_cycle', 'extracted_gpm',
    'extracted_tank_size', 'extracted_water_heater_temp',
]
LLM_Parameterized_Reference_Scoring_CATEGORICAL_EXTRACTED_COLS = [
    'extracted_occupancy_context', 'extracted_appliance', 'extracted_baseline_time',
]


LLM_Parameterized_Reference_Scoring_FAILURE_COUNTER_KEYS = [
    FAILED_EXTRACTION_NON_JSON_WRAPPER,
    EXTRACTION_INVALID_JSON,
    FAILED_EXTRACTION_INVALID_DECISION_TYPE,
    FAILED_EXTRACTION_INVALID_CALCULATOR,
    FAILED_EXTRACTION_MISSING_PARAMETERS,
    FAILED_EXTRACTION_INVALID_PARAMETERS,
    FAILED_EXTRACTION_DECISION_TYPE_MISMATCH,
    FAILED_EXTRACTION_EXCEPTION,
    FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION,
    FAILED_GROUND_TRUTH_MISSING_KEY,
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN
]


# Numeric engineering parameters the calculators do arithmetic on, with the
# physically admissible range each must fall in. A value outside the range (or
# one that does not parse as a finite number) is an extraction failure that must
# surface as the sentinel -- NEVER silently coerced to 0.0, which would fabricate
# a perfect (zero-cost / zero-emission) score and corrupt the benchmark. The
# string fields ('occupancy_context', 'appliance', 'baseline_time') are validated
# separately by the calculators themselves and are not range-checked here.
LLM_Parameterized_Reference_Scoring_NUMERIC_PARAM_BOUNDS = {
    "HVAC": {
        "r_value": (1.0, 60.0),      # whole-wall R; R-1..R-60 spans all residential assemblies
        "seer": (6.0, 30.0),         # rated SEER of any fielded residential AC
        "hvac_age": (0.0, 60.0),     # equipment age in years
    },
    "Appliance": {
        "kwh_per_cycle": (0.05, 10.0),  # per-cycle energy for dishwasher/washer/dryer
    },
    "Shower": {
        "gpm": (0.5, 8.0),               # showerhead flow rate
        "tank_size": (10.0, 120.0),      # nominal water-heater tank gallons
        "water_heater_temp": (80.0, 160.0),  # setpoint deg F
    },
}


def _validate_numeric_params(decision_type: str, params: Dict) -> List[str]:
    """Return the list of numeric parameters that fail to parse as a finite
    number inside their physical range. An empty list means all are valid.

    This is the guard that stops a non-numeric extraction (e.g. gpm="low_flow"
    or water_heater_temp="120 F") from being silently turned into 0.0 in
    score_with_ground_truth -- which would produce a fabricated perfect score.
    """
    import math
    bad = []
    for key, (lo, hi) in LLM_Parameterized_Reference_Scoring_NUMERIC_PARAM_BOUNDS.get(decision_type, {}).items():
        if key not in params:
            continue  # presence is handled by the required_params check
        try:
            v = float(params[key])
        except (TypeError, ValueError):
            bad.append(key)
            continue
        if not math.isfinite(v) or not (lo <= v <= hi):
            bad.append(key)
    return bad


def _init_failure_counters() -> Dict[str, int]:
    return {key: 0 for key in LLM_Parameterized_Reference_Scoring_FAILURE_COUNTER_KEYS}


def _extracted_parameter_cells(extracted_result: Optional[Dict]) -> Dict:
    params = (extracted_result or {}).get('parameters', {})
    cells = {col: '' for col in LLM_Parameterized_Reference_Scoring_NUMERIC_EXTRACTED_COLS + LLM_Parameterized_Reference_Scoring_CATEGORICAL_EXTRACTED_COLS}
    for col in LLM_Parameterized_Reference_Scoring_NUMERIC_EXTRACTED_COLS:
        key = col.removeprefix('extracted_')
        if key in params:
            try:
                cells[col] = float(params[key])
            except (TypeError, ValueError):
                cells[col] = ''
    for col in LLM_Parameterized_Reference_Scoring_CATEGORICAL_EXTRACTED_COLS:
        key = col.removeprefix('extracted_')
        if key in params:
            value = params[key]
            cells[col] = '' if value is None else str(value).strip()
    return cells


def _increment_failure_counters(counters: Dict[str, int], failure_types: List[str], increment: int = 1) -> None:
    for failure_type in set(failure_types):
        if failure_type in counters:
            counters[failure_type] += increment


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520


UNIFIED_EXTRACTION_PROMPT = """You are a household-systems engineer. 
You base all assumptions off of given information.
Understand how each parameter affects another. When extrapolating missing values, use all information given to specify a reasonable value for the value being extrapolated.

SCENARIO:
{scenario_text}

QUESTION: {question}

INSTRUCTIONS:
1. Identify the Decision Type: HVAC, Appliance, or Shower.
2. Estimate ONLY the parameters listed for that type below. 
3. Every listed parameter is mandatory. If a value is not stated, it is mandatory to reasonably estimate it from the scenario context.
4. Return ONLY valid JSON in the exact structure shown.

For HVAC decisions:
{{
  "decision_type": "HVAC",
  "calculator": "HVACGroundTruthCalculator",
  "parameters": {{
    "r_value": <number>,
    "seer": <number>,
    "hvac_age": <number>,
    "occupancy_context": "occupied_all_day | unoccupied_<hours> | occupied_sleep"
  }}
}}

For Appliance decisions:
{{
  "decision_type": "Appliance",
  "calculator": "ApplianceGroundTruthCalculator",
  "parameters": {{
    "appliance": "Dishwasher | Washer | Dryer",
    "kwh_per_cycle": <number>,
    "baseline_time": "<the time it currently is, e.g. 7pm, 8am>"
  }}
}}

For Shower decisions:
{{
  "decision_type": "Shower",
  "calculator": "ShowerGroundTruthCalculator",
  "parameters": {{
    "gpm": <number>,
    "tank_size": <number>,
    "water_heater_temp": <number>
  }}
}}

Return ONLY the JSON, no explanation.
"""

def query_openrouter(messages: List[Dict], model: str = None,
                     temperature: float = None) -> Tuple[str, Dict]:
    if model is None:
        model = API_CONFIG["model"]
    if temperature is None:
        temperature = API_CONFIG["temperature"]
    url = API_CONFIG["endpoint"]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    reasoning_payload = API_CONFIG["reasoning"]
    if reasoning_payload is not None:
        payload["reasoning"] = reasoning_payload


    attempt = 0
    retry_forever = MAX_RETRIES <= 0

    while True:
        attempt += 1
        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                
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
                        for key in msg.keys():
                            if key not in ['role', 'content']:
                                logger.debug(f"Message extra field '{key}': {msg.get(key)}")

                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                usage = data.get('usage', {})
                reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                finish_reason = data.get("choices", [{}])[0].get("finish_reason", "?")
                logger.info(
                    f"  [call ok] attempt={attempt} latency={latency_ms/1000:.1f}s "
                    f"prompt={usage.get('prompt_tokens', 0)} "
                    f"completion={usage.get('completion_tokens', 0)} "
                    f"reasoning_tokens={reasoning_tokens} "
                    f"finish={finish_reason}"
                )
                if reasoning_tokens > 0:
                    logger.warning(
                        f"  [WARN] reasoning_tokens={reasoning_tokens} > 0 "
                        f"-- reasoning was not disabled for this provider/model."
                    )

                diagnostics = {
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                    'latency_ms': latency_ms,
                    'model': model
                }

                if DEBUG_API:
                    logger.debug(f"Returning content (len={len(content)}): {content[:200]}...")

                return content, diagnostics
            else:
                if _is_transient_http_status(response.status_code):
                    print(f"  Transient API error (attempt {attempt}): {response.status_code}")
                else:
                    print(f"  API error (attempt {attempt}): {response.status_code}")

                if not retry_forever and attempt >= MAX_RETRIES:
                    break

                time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
                continue

        except requests.exceptions.RequestException as e:
            print(f"  Request failed (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
            continue

        except ValueError as e:
            print(f"  Invalid API JSON envelope (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
            continue

    raise Exception(f"{FAILED_API_EXHAUSTED}: Failed to get response after {MAX_RETRIES} attempts")

# Household-reported fields the LLM extraction prompt may see. Engineering-truth
# keys (r_value, gpm, kwh_per_cycle, ...) must NEVER reach the prompt -- the LLM
# is scored on estimating exactly those values (proxy/true-pair rule). Any key
# outside this allowlist is a schema violation and must fail loudly instead of
# being forwarded. 'question' is handled by its own skip below and is not a
# member here.
EXTRACTION_SCENARIO_ALLOWLIST = frozenset({
    'decision_type', 'location', 'square_footage', 'insulation',
    'household_size', 'utility_budget', 'housing_type', 'outdoor_temp',
    'house_age', 'appliance_age', 'flow_rate',
    'alternative_1', 'alternative_2', 'alternative_3',
})

def format_scenario_for_extraction(scenario: Dict) -> str:
    """Format scenario for extraction.

    Skips the Question (rendered separately) and any cells that are blank,
    NaN, or the literal string 'nan' so noise from columns irrelevant to the
    current decision type doesn't leak into the LLM context. Only keys in
    EXTRACTION_SCENARIO_ALLOWLIST are emitted; an unexpected key raises
    before its value can reach the prompt.
    """
    lines = []
    for key, value in scenario.items():
        if key == 'question':
            continue
        if key not in EXTRACTION_SCENARIO_ALLOWLIST:
            raise ValueError(
                f"ERROR: unexpected scenario key {key!r} is not in the "
                f"extraction allowlist; refusing to forward it to the LLM "
                f"(proxy/true-pair guard)."
            )
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        text = str(value).strip()
        if text == '' or text.lower() == 'nan':
            continue
        lines.append(f"- {key}: {text}")
    return '\n'.join(lines)


def extract_all_with_ai(scenario: Dict,
                        expected_decision_type: Optional[str] = None) -> Tuple[Optional[Dict], Dict]:

    scenario_text = format_scenario_for_extraction(scenario)
    question = str(scenario.get('question', '')).strip()

    prompt = UNIFIED_EXTRACTION_PROMPT.format(
        scenario_text=scenario_text,
        question=question
    )

    messages = [{"role": "user", "content": prompt}]

    extraction_diagnostics = {
        'attempts': 1,
        'success': False,
        'extraction_error': None,
        'failure_types': []
    }

    try:
        response_text, api_diagnostics = query_openrouter(messages)
        extraction_diagnostics.update({
            'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
            'completion_tokens': api_diagnostics.get('completion_tokens', 0),
            'latency_ms': api_diagnostics.get('latency_ms', 0)
        })
        
        logger.debug(f"=== EXTRACTION RESPONSE ===")
        logger.debug(f"Raw response (first 1000 chars): {response_text[:1000]}")
        logger.debug(f"Response length: {len(response_text)} chars")
        
        stripped_response = response_text.strip()
        if stripped_response.startswith("```"):
            stripped_response = stripped_response.split("```", 2)[1]
            if stripped_response.lower().startswith("json"):
                stripped_response = stripped_response[4:]
            stripped_response = stripped_response.strip()
        strict_json_only = stripped_response.startswith('{') and stripped_response.endswith('}')
        if not strict_json_only:
            print("Extraction failed: non-JSON wrapper text detected")
            extraction_diagnostics['extraction_error'] = "Non-JSON wrapper text detected"
            extraction_diagnostics['failure_types'] = [FAILED_EXTRACTION_NON_JSON_WRAPPER]
            return None, extraction_diagnostics

        import re
        json_match = re.search(r'\{.*\}', stripped_response, re.DOTALL)

        if not json_match:
            print("Extraction failed: could not parse JSON")
            extraction_diagnostics['extraction_error'] = "Invalid JSON format"
            extraction_diagnostics['failure_types'] = [EXTRACTION_INVALID_JSON]
            extraction_diagnostics.update({
                'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
                'completion_tokens': api_diagnostics.get('completion_tokens', 0),
                'latency_ms': api_diagnostics.get('latency_ms', 0)
            })
            return None, extraction_diagnostics

        try:
            extracted = json.loads(json_match.group())
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Extraction failed: could not parse JSON: {e}")
            extraction_diagnostics['extraction_error'] = "Invalid JSON format"
            extraction_diagnostics['failure_types'] = [EXTRACTION_INVALID_JSON]
            extraction_diagnostics.update({
                'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
                'completion_tokens': api_diagnostics.get('completion_tokens', 0),
                'latency_ms': api_diagnostics.get('latency_ms', 0)
            })
            return None, extraction_diagnostics

        required_top_level = ['decision_type', 'calculator', 'parameters']
        if all(k in extracted for k in required_top_level):

            if extracted['decision_type'] not in ['HVAC', 'Appliance', 'Shower']:
                print(f" invalid decision_type: {extracted['decision_type']}")
                extraction_diagnostics['extraction_error'] = "Invalid decision_type"
                extraction_diagnostics['failure_types'] = [FAILED_EXTRACTION_INVALID_DECISION_TYPE]
                return None, extraction_diagnostics

            valid_calculators = ['HVACGroundTruthCalculator', 'ApplianceGroundTruthCalculator',
                                 'ShowerGroundTruthCalculator']
            if extracted['calculator'] not in valid_calculators:
                print(f" invalid calculator: {extracted['calculator']}")
                extraction_diagnostics['extraction_error'] = "Invalid calculator"
                extraction_diagnostics['failure_types'] = [FAILED_EXTRACTION_INVALID_CALCULATOR]
                return None, extraction_diagnostics

            params = extracted['parameters']
            decision_type = extracted['decision_type']

            if expected_decision_type is not None and decision_type != expected_decision_type:
                print(f" decision_type mismatch: extracted {decision_type!r}, "
                      f"expected {expected_decision_type!r}")
                extraction_diagnostics['extraction_error'] = (
                    f"decision_type mismatch: {decision_type} != {expected_decision_type}"
                )
                extraction_diagnostics['failure_types'] = [FAILED_EXTRACTION_DECISION_TYPE_MISMATCH]
                return None, extraction_diagnostics

            if decision_type == 'HVAC':
                required_params = ['r_value', 'seer', 'hvac_age', 'occupancy_context']
            elif decision_type == 'Appliance':
                required_params = ['appliance', 'kwh_per_cycle', 'baseline_time']
            elif decision_type == 'Shower':
                required_params = ['gpm', 'tank_size', 'water_heater_temp']
            if all(k in params for k in required_params):
                bad_numeric = _validate_numeric_params(decision_type, params)
                if bad_numeric:
                    print(f"Invalid numeric parameters for {decision_type}: {bad_numeric}")
                    extraction_diagnostics['extraction_error'] = (
                        f"Invalid numeric parameters: {bad_numeric}"
                    )
                    extraction_diagnostics['failure_types'] = [FAILED_EXTRACTION_INVALID_PARAMETERS]
                    return None, extraction_diagnostics

                extraction_diagnostics['success'] = True
                extraction_diagnostics['failure_types'] = []
                extraction_diagnostics.update({
                    'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
                    'completion_tokens': api_diagnostics.get('completion_tokens', 0),
                    'latency_ms': api_diagnostics.get('latency_ms', 0)
                })
                return extracted, extraction_diagnostics

            print(f"Missing required parameters for {decision_type}")
            extraction_diagnostics['extraction_error'] = f"Missing parameters: {required_params}"
            extraction_diagnostics['failure_types'] = [FAILED_EXTRACTION_MISSING_PARAMETERS]
            return None, extraction_diagnostics

        print("Extraction failed: could not parse JSON")
        extraction_diagnostics['extraction_error'] = "Invalid JSON format"
        extraction_diagnostics['failure_types'] = [EXTRACTION_INVALID_JSON]
        extraction_diagnostics.update({
            'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
            'completion_tokens': api_diagnostics.get('completion_tokens', 0),
            'latency_ms': api_diagnostics.get('latency_ms', 0)
        })
        return None, extraction_diagnostics

    except Exception as e:
        print(f"Extraction error: {e}")
        extraction_diagnostics['extraction_error'] = str(e)
        error_text = str(e).lower()
        # Distinguish API/network exhaustion (transient infrastructure failure)
        # from genuine extraction errors (bad LLM output, code bugs).
        if "failed to get response" in error_text or "request failed" in error_text:
            extraction_diagnostics['failure_types'] = [FAILED_API_EXHAUSTED]
        else:
            extraction_diagnostics['failure_types'] = [FAILED_EXTRACTION_EXCEPTION]
        return None, extraction_diagnostics

def score_with_ground_truth(extracted_result: Dict, scenario: Dict) -> List[Dict]:
    # Alternatives are taken verbatim from the test scenario (the sheet already
    # holds them in canonical form); the LLM only supplies engineering params.
    scenario_alts = [scenario.get(f'alternative_{i}') for i in range(1, 4)]
    scenario_alts = [
        a for a in scenario_alts
        if a not in (None, '') and str(a).strip().lower() != 'nan'
    ]

    gt_scenario = {**scenario, **extracted_result['parameters']}
    gt_scenario['alternatives'] = scenario_alts  # HVAC calc reads this list
    for i, alt in enumerate(scenario_alts[:3], 1):
        gt_scenario[f'alternative_{i}'] = alt

    # Coerce every numeric field the calculators do arithmetic on — scenario
    # passthroughs may arrive as strings/pandas scalars, extracted ones as JSON.
    for key in ['utility_budget', 'household_size', 'kwh_per_cycle',
                'square_footage', 'outdoor_temp', 'r_value', 'seer', 'hvac_age',
                'gpm', 'tank_size', 'water_heater_temp']:
        if key in gt_scenario and isinstance(gt_scenario[key], str):
            try:
                gt_scenario[key] = float(gt_scenario[key])
            except (ValueError, TypeError):
                raise ValueError(
                    f"Cannot parse scenario field '{key}' = {gt_scenario[key]!r} as float. "
                    f"This field is required by the ground truth calculator."
                )

    calculator_name = extracted_result['calculator']
    print(f"  Using calculator: {calculator_name}")

    if calculator_name == 'HVACGroundTruthCalculator':
        calc = HVACGroundTruthCalculator()
        result = calc.calculate_scenario_scores(gt_scenario)
    elif calculator_name == 'ApplianceGroundTruthCalculator':
        calc = ApplianceGroundTruthCalculator()
        result = calc.calculate_scenario_scores(gt_scenario)
    elif calculator_name == 'ShowerGroundTruthCalculator':
        calc = ShowerGroundTruthCalculator()
        result = calc.calculate_scenario_scores(gt_scenario)
    else:
        raise ValueError(f"Unknown calculator: {calculator_name}")
    alternatives_scores = []
    if calculator_name == 'ShowerGroundTruthCalculator':
        for alt_data in result['alternatives']:
            alternatives_scores.append({
                'alternative': str(alt_data['alternative']),
                'scores': {
                    'energy_cost': alt_data['transformed_values']['energy_cost'],
                    'environmental': alt_data['transformed_values']['environmental'],
                    'comfort': alt_data['transformed_values']['comfort'],
                    'practicality': alt_data['transformed_values']['practicality']
                }
            })
    else:
        for alt_key, alt_data in result.items():
            alternatives_scores.append({
                'alternative': str(alt_key),
                'scores': {
                    'energy_cost': alt_data['energy_cost_score'],
                    'environmental': alt_data['environmental_score'],
                    'comfort': alt_data['comfort_score'],
                    'practicality': alt_data['practicality_score']
                }
            })


    # Alternatives already came from the scenario verbatim, so the scored
    # 'alternative' is the canonical one; mirror it into extracted_alternative
    # for output-column continuity.
    if len(alternatives_scores) != len(scenario_alts):
        print(f"  WARNING: scoring produced {len(alternatives_scores)} alternatives, "
              f"expected {len(scenario_alts)}.")
    for alt_data in alternatives_scores:
        alt_data['extracted_alternative'] = alt_data.get('alternative', '')
    return alternatives_scores


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    alternatives = [ad['alternative'] for ad in alternatives_scores]

    valid_pairs = []  # (input_idx, weighted_sum)
    for idx, alt_data in enumerate(alternatives_scores):
        scores = alt_data['scores']
        if has_sentinel_scores(scores):
            continue
        weighted_sum = (
                CRITERION_WEIGHTS['energy_cost'] * scores['energy_cost'] +
                CRITERION_WEIGHTS['environmental'] * scores['environmental'] +
                CRITERION_WEIGHTS['comfort'] * scores['comfort'] +
                CRITERION_WEIGHTS['practicality'] * scores['practicality']
        )
        valid_pairs.append((idx, weighted_sum))

    if not valid_pairs:
        return {
            'ranked_alternatives': [],
            'ranks': [SENTINEL_VALUE] * len(alternatives),
            'weighted_scores': [SENTINEL_FLOAT] * len(alternatives)
        }

    def sort_key(pair):
        idx, ws = pair
        scores = alternatives_scores[idx]['scores']
        return (ws,) + tuple(scores.get(crit, 0.0) for crit in TIE_BREAK_PRIORITY)

    valid_pairs_sorted = sorted(valid_pairs, key=sort_key, reverse=True)
    ranked_alternatives = [alternatives[idx] for idx, _ in valid_pairs_sorted]

    ranks = [SENTINEL_VALUE] * len(alternatives)
    weighted_scores = [SENTINEL_FLOAT] * len(alternatives)
    for rank_position, (input_idx, ws) in enumerate(valid_pairs_sorted):
        ranks[input_idx] = rank_position + 1
        weighted_scores[input_idx] = ws

    return {
        'ranked_alternatives': ranked_alternatives,
        'ranks': ranks,
        'weighted_scores': weighted_scores
    }

def run_scenario(scenario: Dict) -> Dict:
    print(f"SCENARIO: {scenario.get('question', 'N/A')}")
   
    print(f"Extracting decision type, parameters, and calculator...")

    # The scenario sheet already knows the decision type; pass it so a
    # mismatched extraction is rejected (wrong-calculator guard, T1-2) rather
    # than silently scored by the wrong calculator.
    expected_decision_type = scenario.get('decision_type')
    if isinstance(expected_decision_type, str):
        expected_decision_type = expected_decision_type.strip() or None
    extraction_result, extraction_diag = extract_all_with_ai(
        scenario, expected_decision_type=expected_decision_type
    )

    if extraction_result is None:
        extraction_failure_types = extraction_diag.get('failure_types', [])
        if extraction_failure_types == [FAILED_API_EXHAUSTED]:
            print(f" EXTRACTION FAILED DUE TO API/ENVIRONMENT. Using fallback scores")

            neutral_alternatives = []
            for alt in [
                scenario.get('alternative_1', 'Alt1'),
                scenario.get('alternative_2', 'Alt2'),
                scenario.get('alternative_3', 'Alt3')
            ]:
                neutral_alternatives.append({
                    'alternative': str(alt),
                    'scores': {
                        'energy_cost': SENTINEL_VALUE,
                        'environmental': SENTINEL_VALUE,
                        'comfort': SENTINEL_VALUE,
                        'practicality': SENTINEL_VALUE
                    }
                })

            ranking_result = apply_mavt_ranking(neutral_alternatives)

            return {
                'scenario': scenario.get('question', 'N/A'),
                'decision_type': scenario.get('decision_type', 'UNKNOWN'),
                'calculator': 'NONE',
                'extraction_failed': True,
                'gt_calculation_failed': False,
                'scenario_failed': False,
                'failure_types': extraction_failure_types,
                'extracted_result': None,
                'alternatives_scores': neutral_alternatives,
                'ranking_result': ranking_result,
                'extraction_diagnostics': extraction_diag
            }

        print(f" EXTRACTION FAILED. Outputting sentinel scores")

        zero_alternatives = []
        for i in range(1, 4):
            zero_alternatives.append({
                'alternative': f'Alternative {i} (extraction failed)',
                'scores': {
                    'energy_cost': SENTINEL_VALUE,
                    'environmental': SENTINEL_VALUE,
                    'comfort': SENTINEL_VALUE,
                    'practicality': SENTINEL_VALUE
                }
            })

        ranking_result = apply_mavt_ranking(zero_alternatives)

        return {
            'scenario': scenario.get('question', 'N/A'),
            'decision_type': 'UNKNOWN',
            'calculator': 'NONE',
            'extraction_failed': True,
            'gt_calculation_failed': False,
            'scenario_failed': True,
            'failure_types': extraction_failure_types,
            'extracted_result': None,
            'alternatives_scores': zero_alternatives,
            'ranking_result': ranking_result,
            'extraction_diagnostics': extraction_diag
        }

    decision_type = extraction_result['decision_type']
    calculator = extraction_result['calculator']
    parameters = extraction_result['parameters']

    print(f"   Extraction succeeded")
    print(f"  Decision type: {decision_type}")
    print(f"  Calculator: {calculator}")
    print(f"  Parameters: {parameters}")
    print(f"Calculating ground truth scores")

    try:
        alternatives_scores = score_with_ground_truth(extraction_result, scenario)

        for alt_data in alternatives_scores:
            scores = alt_data['scores']
            print(f"  {alt_data['alternative']}: "
                  f"Energy={scores['energy_cost']:.2f}, "
                  f"Env={scores['environmental']:.2f}, "
                  f"Comfort={scores['comfort']:.2f}, "
                  f"Pract={scores['practicality']:.2f}")

    except Exception as e:
        print(f" Ground truth calculation failed: {e}")
        if isinstance(e, KeyError):
            missing_key = e.args[0] if e.args else 'unknown'
            failure_type = FAILED_GROUND_TRUTH_MISSING_KEY
            failure_detail = f"missing scenario key: {missing_key!r}"
            failure_types_out = [failure_type]
            extra_diag = {'missing_scenario_key': missing_key}
        else:
            failure_type = FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION
            failure_detail = str(e)
            failure_types_out = [failure_type]
            extra_diag = {}

        # If GT calc blows up, send back sentinel values for the scenario's
        # own alternatives (extraction no longer carries them).
        fallback_alts = [
            scenario.get('alternative_1', 'Alt1'),
            scenario.get('alternative_2', 'Alt2'),
            scenario.get('alternative_3', 'Alt3'),
        ]
        zero_alternatives = []
        for alt in fallback_alts[:3]:
            zero_alternatives.append({
                'alternative': str(alt),
                'scores': {
                    'energy_cost': SENTINEL_VALUE,
                    'environmental': SENTINEL_VALUE,
                    'comfort': SENTINEL_VALUE,
                    'practicality': SENTINEL_VALUE
                }
            })

        ranking_result = apply_mavt_ranking(zero_alternatives)

        result_payload = {
            'scenario': scenario.get('question', 'N/A'),
            'decision_type': decision_type,
            'calculator': calculator,
            'extraction_failed': False,
            'gt_calculation_failed': True,
            'scenario_failed': True,
            'failure_types': failure_types_out,
            'extracted_result': extraction_result,
            'alternatives_scores': zero_alternatives,
            'ranking_result': ranking_result,
            'error': failure_detail,
            'extraction_diagnostics': extraction_diag
        }
        result_payload.update(extra_diag)
        return result_payload

    ranking_result = apply_mavt_ranking(alternatives_scores)

    print(f"\nRANKING:")
    alt_names = [ad['alternative'] for ad in alternatives_scores]
    for i, alt in enumerate(ranking_result['ranked_alternatives'], 1):
        ws = ranking_result['weighted_scores'][alt_names.index(alt)]
        print(f"  {i}. {alt} (weighted score: {ws:.2f})")

    return {
        'scenario': scenario.get('question', 'N/A'),
        'decision_type': decision_type,
        'calculator': calculator,
        'extraction_failed': False,
        'gt_calculation_failed': False,
        'scenario_failed': False,
        'failure_types': [],
        'extracted_result': extraction_result,
        'alternatives_scores': alternatives_scores,
        'ranking_result': ranking_result,
        'extraction_diagnostics': extraction_diag
    }


def run_test_set(test_path: str, output_path: str,
                 output_diagnostics_path: str) -> Dict:
    test_csv_path = Path(test_path)
    output_csv_path = Path(output_path)
    output_diagnostics_path = Path(output_diagnostics_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_diagnostics_path.parent.mkdir(parents=True, exist_ok=True)


    print(f"Loading test scenarios from: {test_csv_path}")

    scenarios = []
    df = read_table_clean(
        test_csv_path,
        keep_str_cols=["alternative_1", "alternative_2", "alternative_3"],
    )
    required_cols = ['question', 'decision_type']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f" Missing required columns: {missing_cols}")

    for _, row in df.iterrows():
        scenarios.append(row.to_dict())

    print(f" Loaded {len(scenarios)} test scenarios")
    print(f"  Decision types: {set([s.get('decision_type', 'UNKNOWN') for s in scenarios])}\n")

    all_results = []
    cumulative_diagnostics = {
        'total_scenarios': len(scenarios),
        'total_api_calls': 0,
        'total_latency_ms': 0.0,
        'total_tokens_input': 0,
        'total_tokens_output': 0,
        'successful_calls': 0,
        'failed_calls': 0,
        'successful_scenarios': 0,
        'failed_scenarios': 0,
        **_init_failure_counters()
    }
    for i, scenario in enumerate(scenarios):
        print(f"\n[{i + 1}/{len(scenarios)}] Processing: {scenario.get('question', 'N/A')[:60]}...")

        try:
            result = run_scenario(scenario)
        except Exception as e:
            print(f" Scenario crashed and was marked failed: {e}")
            fallback_alternatives = [
                scenario.get('alternative_1', 'Alt1'),
                scenario.get('alternative_2', 'Alt2'),
                scenario.get('alternative_3', 'Alt3')
            ]
            result = {
                'scenario': scenario.get('question', 'N/A'),
                'decision_type': scenario.get('decision_type', 'UNKNOWN'),
                'calculator': 'NONE',
                'extraction_failed': True,
                'gt_calculation_failed': False,
                'scenario_failed': True,
                'failure_types': [],
                'alternatives_scores': [
                    {
                        'alternative': str(alt),
                        'scores': {
                            'energy_cost': SENTINEL_VALUE,
                            'environmental': SENTINEL_VALUE,
                            'comfort': SENTINEL_VALUE,
                            'practicality': SENTINEL_VALUE
                        }
                    }
                    for alt in fallback_alternatives
                ],
                'ranking_result': {
                    'ranked_alternatives': [],
                    'ranks': [SENTINEL_VALUE, SENTINEL_VALUE, SENTINEL_VALUE],
                    'weighted_scores': [SENTINEL_FLOAT, SENTINEL_FLOAT, SENTINEL_FLOAT]
                },
                'extraction_diagnostics': {
                    'attempts': 0,
                    'success': False,
                    'extraction_error': str(e),
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'latency_ms': 0.0
                }
            }

        all_results.append(result)

        ext_diag = result.get('extraction_diagnostics', {})
        attempts = ext_diag.get('attempts', 0)
        try:
            attempts = int(attempts)
        except (TypeError, ValueError):
            attempts = 0
        cumulative_diagnostics['total_api_calls'] += max(attempts, 0)

        cumulative_diagnostics['total_tokens_input'] += ext_diag.get('prompt_tokens', 0)
        cumulative_diagnostics['total_tokens_output'] += ext_diag.get('completion_tokens', 0)
        cumulative_diagnostics['total_latency_ms'] += ext_diag.get('latency_ms', 0.0)

        failure_types = result.get('failure_types')
        if failure_types:
            _increment_failure_counters(cumulative_diagnostics, failure_types)

        if result.get('scenario_failed', False):
            cumulative_diagnostics['failed_calls'] += 1
            cumulative_diagnostics['failed_scenarios'] += 1
            if not failure_types:
                _increment_failure_counters(cumulative_diagnostics, [FAILED_UNKNOWN])
        else:
            cumulative_diagnostics['successful_calls'] += 1
            cumulative_diagnostics['successful_scenarios'] += 1
    cumulative_diagnostics['avg_latency_ms'] = (
            cumulative_diagnostics['total_latency_ms'] /
            max(cumulative_diagnostics['total_api_calls'], 1)
    )
    cumulative_diagnostics['success_rate'] = (
            cumulative_diagnostics['successful_scenarios'] /
            max(cumulative_diagnostics['total_scenarios'], 1)
    )
    print(f"\nSaving results to: {output_csv_path}")

    rows: List[Dict] = []
    for scenario_id, result in enumerate(all_results, 1):
        question = result['scenario']
        calculator = result['calculator']
        extraction_failed = result.get('extraction_failed', False)
        gt_calc_failed = result.get('gt_calculation_failed', False)
        scenario_failed = result.get('scenario_failed', False)

        location = scenarios[scenario_id - 1].get('location', 'N/A')
        outdoor_temp = scenarios[scenario_id - 1].get('outdoor_temp', '')
        appliance_age = scenarios[scenario_id - 1].get('appliance_age', '')
        flow_rate = scenarios[scenario_id - 1].get('flow_rate', '')
        input_decision_type = scenarios[scenario_id - 1].get('decision_type', 'UNKNOWN')
        extracted_decision_type = result.get('decision_type', 'UNKNOWN')
        decision_type = input_decision_type
        extracted_param_cells = _extracted_parameter_cells(result.get('extracted_result'))

        ranks = result['ranking_result']['ranks']
        weighted_scores = result['ranking_result']['weighted_scores']

        for alt_idx, alt_data in enumerate(result['alternatives_scores']):
            alternative = alt_data['alternative']
            extracted_alternative = alt_data.get('extracted_alternative', '')
            scores = alt_data['scores']

            if scenario_failed:
                energy_cost = environmental = comfort = practicality = SENTINEL_VALUE
                rank = weighted_score = SENTINEL_VALUE
            else:
                energy_cost = scores['energy_cost']
                environmental = scores['environmental']
                comfort = scores['comfort']
                practicality = scores['practicality']
                rank = ranks[alt_idx]
                weighted_score = weighted_scores[alt_idx]

            rows.append({
                'scenario_id': scenario_id,
                'question': question,
                'location': location,
                'input_decision_type': input_decision_type,
                'extracted_decision_type': extracted_decision_type,
                'decision_type': decision_type,
                'outdoor_temp': outdoor_temp,
                'appliance_age': appliance_age,
                'flow_rate': flow_rate,
                **extracted_param_cells,
                'calculator': calculator,
                'extraction_failed': extraction_failed,
                'gt_calculation_failed': gt_calc_failed,
                'alternative': alternative,
                'extracted_alternative': extracted_alternative,
                'energy_cost': energy_cost,
                'environmental': environmental,
                'comfort': comfort,
                'practicality': practicality,
                'rank': rank,
                'weighted_score': weighted_score,
            })

    _atomic_write_xlsx(pd.DataFrame(rows, columns=LLM_Parameterized_Reference_Scoring_RESULT_FIELDNAMES), output_csv_path)
    print(f" Results saved to: {output_csv_path}")

    _atomic_write_json(cumulative_diagnostics, output_diagnostics_path)
    print(f" Diagnostics saved to: {output_diagnostics_path}")


    print(f"LLM-Parameterized_Reference_Scoring TEST COMPLETE")
    print(f"Total scenarios: {cumulative_diagnostics['total_scenarios']}")
    print(f"Total API calls: {cumulative_diagnostics['total_api_calls']}")
    print(f"Successful calls: {cumulative_diagnostics['successful_calls']}")
    print(f"Failed calls: {cumulative_diagnostics['failed_calls']}")
    print(f"Total tokens (input): {cumulative_diagnostics['total_tokens_input']}")
    print(f"Total tokens (output): {cumulative_diagnostics['total_tokens_output']}")
    print(f"Average latency: {cumulative_diagnostics['avg_latency_ms']:.0f} ms")
    print(f"Success rate: {cumulative_diagnostics['success_rate']:.1%}")

    return cumulative_diagnostics


def run_multi_and_aggregate(test_csv_path: str, base_output_csv: str,
                            base_diagnostics_path: str) -> None:
    """Run the benchmark N_RUNS times and average the per-run xlsx outputs.

    Resume-aware: a per-run xlsx that already exists, has size > 0, has no
    leftover .tmp sibling, and reads as a non-empty DataFrame is treated as
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
            print(f"--- Run {run_idx}/{N_RUNS}: resuming from {run_path.name} ---")
            run_paths.append(run_path)
            skipped_runs.append(run_idx)
            continue
        print(f"--- Run {run_idx}/{N_RUNS} -> {run_path.name} ---")
        try:
            run_test_set(str(test_csv_path), str(run_path), str(diag_path))
            run_paths.append(run_path)
        except Exception as e:
            print(f"ERROR: Run {run_idx} failed and will be excluded from aggregation: {e}")

    if skipped_runs:
        print(f"Resumed {len(skipped_runs)} existing run(s): {skipped_runs}")

    n_runs = len(run_paths)
    if n_runs == 0:
        print("ERROR: All runs failed. No aggregation possible.")
        return
    if n_runs < N_RUNS:
        print(
            f"WARNING: Only {n_runs}/{N_RUNS} runs completed. "
            f"Aggregating over {n_runs} runs."
        )
    print(f"{n_runs}/{N_RUNS} runs complete. Aggregating scores...")

    valid_run_paths = []
    run_dfs = []
    for p in run_paths:
        try:
            run_dfs.append(read_table_clean(p))
            valid_run_paths.append(p)
        except Exception as e:
            print(f"WARNING: Could not read {p.name}, skipping from aggregation: {e}")
    if len(run_dfs) == 0:
        print("ERROR: No run files could be read. Aggregation aborted.")
        return
    n_readable = len(run_dfs)
    if n_readable < n_runs:
        print(f"WARNING: Aggregating over {n_readable}/{n_runs} readable runs.")
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
    STABLE_META_COLS = ["question", "location", "outdoor_temp", "appliance_age", "flow_rate", "calculator"]
    PARAMETER_NUMERIC_COLS = LLM_Parameterized_Reference_Scoring_NUMERIC_EXTRACTED_COLS
    PARAMETER_CATEGORICAL_COLS = LLM_Parameterized_Reference_Scoring_CATEGORICAL_EXTRACTED_COLS
    # extracted_alternative is per-run diagnostic — keep one example via .first()
    OPTIONAL_META_COLS = ["extracted_alternative"]
    BOOL_META_COLS = ["extraction_failed", "gt_calculation_failed"]

    for col in PARAMETER_NUMERIC_COLS:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce")

    def _mode_or_blank(series):
        cleaned = series.dropna()
        cleaned = cleaned[cleaned.astype(str).str.strip().ne('')]
        if cleaned.empty:
            return ''
        mode = cleaned.mode(dropna=True)
        return mode.iloc[0] if not mode.empty else cleaned.iloc[0]

    n_valid_runs = combined.groupby(GROUP_KEYS)[CRITERIA_COLS[0]].apply(
        lambda s: s.notna().sum()
    ).reset_index(name="n_successful_runs")

    avg_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].mean()
    std_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].std()

    # Stable cols: just take the first one since these should match across runs
    avg_meta = combined.groupby(GROUP_KEYS, as_index=False)[STABLE_META_COLS].first()
    if PARAMETER_NUMERIC_COLS:
        avg_param_numeric = combined.groupby(GROUP_KEYS, as_index=False)[PARAMETER_NUMERIC_COLS].mean()
        avg_meta = avg_meta.merge(avg_param_numeric, on=GROUP_KEYS, how="left")
    if PARAMETER_CATEGORICAL_COLS:
        avg_param_categorical = combined.groupby(GROUP_KEYS)[PARAMETER_CATEGORICAL_COLS].agg(_mode_or_blank).reset_index()
        avg_meta = avg_meta.merge(avg_param_categorical, on=GROUP_KEYS, how="left")

    def _mode_decision_type(series):
        non_unknown = series[series != 'UNKNOWN']
        if len(non_unknown) == 0:
            return 'UNKNOWN'
        return non_unknown.mode().iloc[0]

    dt_mode = combined.groupby(GROUP_KEYS)['decision_type'].agg(_mode_decision_type).reset_index()
    avg_meta = avg_meta.merge(dt_mode, on=GROUP_KEYS)

    # input_decision_type / extracted_decision_type — preserve both for traceability
    for col in ['input_decision_type', 'extracted_decision_type']:
        if col in combined.columns:
            col_first = combined.groupby(GROUP_KEYS)[col].first().reset_index()
            avg_meta = avg_meta.merge(col_first, on=GROUP_KEYS)

    # Boolean flags: use any() so one bad run marks the scenario as flaky
    for col in BOOL_META_COLS:
        if col in combined.columns:
            bool_agg = (
                combined.groupby(GROUP_KEYS)[col]
                .agg(lambda s: bool(s.astype(str).str.lower().str.strip().eq('true').any()))
                .reset_index()
            )
            avg_meta = avg_meta.merge(bool_agg, on=GROUP_KEYS)

    avg = avg_criteria.merge(avg_meta, on=GROUP_KEYS)
    avg = avg.merge(n_valid_runs, on=GROUP_KEYS)
    avg["n_runs"] = n_readable
    avg["n_failed_runs"] = avg["n_runs"] - avg["n_successful_runs"]

    std_criteria = std_criteria.rename(columns={c: f"{c}_std" for c in CRITERIA_COLS})
    stats_df = avg.merge(std_criteria, on=GROUP_KEYS)

    # When N=1, pandas std returns NaN — annotate clearly in the stats output
    if n_readable == 1:
        print("WARNING: Only 1 run aggregated — std columns will be NaN (undefined for N=1).")
        for c in CRITERIA_COLS:
            col = f"{c}_std"
            if col in stats_df.columns:
                stats_df[col] = "N/A (N=1)"

    # Put 1928 back anywhere every run failed for that alternative
    for c in CRITERIA_COLS:
        avg[c] = avg[c].fillna(SENTINEL)

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
            sub = avg.loc[valid_idx].copy()
            sub["weighted_score"] = ws
            sort_cols = ["weighted_score"] + TIE_BREAK_PRIORITY
            sub_sorted = sub.sort_values(sort_cols, ascending=[False] * len(sort_cols), kind="mergesort")
            avg.loc[sub_sorted.index, "rank"] = list(range(1, len(sub_sorted) + 1))

    col_order = [
        "scenario_id", "question", "location", "decision_type",
        "input_decision_type", "extracted_decision_type",
        "outdoor_temp", "appliance_age", "flow_rate",
        *LLM_Parameterized_Reference_Scoring_NUMERIC_EXTRACTED_COLS,
        *LLM_Parameterized_Reference_Scoring_CATEGORICAL_EXTRACTED_COLS,
        "calculator", "extraction_failed", "gt_calculation_failed", "alternative",
        "energy_cost", "environmental", "comfort", "practicality",
        "rank", "weighted_score",
        "n_runs", "n_successful_runs", "n_failed_runs",
    ]
    _atomic_write_xlsx(avg.reindex(columns=col_order), base_output_csv)
    print(f"Averaged results ({n_readable} runs) saved to {base_output_csv}")

    stats_path = base.with_name(f"{base.stem}_stats{base.suffix}")
    _atomic_write_xlsx(stats_df, stats_path)
    print(f"Score statistics saved to {stats_path}")


def main():
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY not found in .env file")

    if not TEST_SCENARIOS.exists():
        raise FileNotFoundError(f"Test scenarios file not found: {TEST_SCENARIOS}")

    print("Starting LLM-Parameterized_Reference_Scoring Architecture Test...")
    print(f"Model: {API_CONFIG['model']}")
    print(f"Temperature: {API_CONFIG['temperature']}")

    output_dir = PROJECT_ROOT / get_output_folder_for_model_id(API_CONFIG["model"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "LLM-Parameterized_Reference_Scoring_results.xlsx"
    output_diagnostics = output_dir / "LLM-Parameterized_Reference_Scoring_results_diagnostics.json"

    run_multi_and_aggregate(
        test_csv_path=str(TEST_SCENARIOS),
        base_output_csv=str(output_csv),
        base_diagnostics_path=str(output_diagnostics),
    )
    print("LLM-Parameterized_Reference_Scoring MULTI-RUN COMPLETE")


if __name__ == "__main__":
    main()
