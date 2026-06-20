MODEL_KEY = "gptoss_weakest"
N_RUNS = 10


# Sampling temperature for every architecture. Kept here (not hard-coded per
# file) so all three architectures share one value and a single edit re-tunes
# the whole benchmark. Low temperature keeps scoring as reproducible as the
# model allows.
TEMPERATURE = 0.3

# OpenRouter request policy, shared by all three architectures so retry/timeout
# behaviour is identical until we take a hard failure from OpenRouter:
#   MAX_RETRIES        - attempts before giving up (<=0 means retry forever)
#   REQUEST_TIMEOUT    - per-request socket timeout, seconds
#   RETRY_BASE_DELAY   - base for exponential backoff, seconds
#   MAX_RETRY_BACKOFF  - cap on a single backoff sleep, seconds
MAX_RETRIES = 10
REQUEST_TIMEOUT = 90
RETRY_BASE_DELAY = 2
MAX_RETRY_BACKOFF = 60


CRITERION_WEIGHTS = {
    "energy_cost": 0.30,
    "environmental": 0.35,
    "comfort": 0.20,
    "practicality": 0.15,
}


TIE_BREAK_PRIORITY = ["environmental", "energy_cost", "comfort", "practicality"]


MODEL_SPECS = {
    "gptoss_weakest": {
        "label": "input Price: $0.029/M, Output Price: $0.14/M",
        "openrouter_id": "openai/gpt-oss-20b:exacto",
        "output_folder": "Output Files GPT-OSS 20B",
        "reasoning_effort": "low",
    },
    "qwen_weak": {
        "label": "0.04/M, 0.15M",
        "openrouter_id": "qwen/qwen3.5-9b:exacto",
        "output_folder": "Output Files Qwen3.5 9B",
        "reasoning_effort": "non-reasoning",
    },
    "deepseek_medium": {
        "label": "Input Price: $0.0983/M, Output Price: $0.1966/M",
        "openrouter_id": "deepseek/deepseek-v4-flash:exacto",
        "output_folder": "Output Files DeepSeek V4 Flash",
        "reasoning_effort": "non-reasoning",
    },
    "gemini_strong": {
        "label": "Input Price: $1.50/M, Output Price: $9/M",
        "openrouter_id": "google/gemini-3.5-flash:exacto",
        "output_folder": "Output Files Gemini 3.5 Flash",
        "reasoning_effort": "minimal",
    },
}


def get_model_id(model_key: str = MODEL_KEY) -> str:
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["openrouter_id"]

def _resolve_model_key(model_key: str) -> str:
    if model_key not in MODEL_SPECS:
        valid_keys = ", ".join(sorted(MODEL_SPECS.keys()))
        raise ValueError(f"Unknown MODEL_KEY: '{model_key}'. Must be one of: {valid_keys}")
    return model_key


def get_output_folder(model_key: str = MODEL_KEY) -> str:
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["output_folder"]



def get_reasoning_effort(model_key: str = MODEL_KEY) -> str:
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["reasoning_effort"]


def get_reasoning_payload(model_key: str = MODEL_KEY) -> dict:
    resolved_key = _resolve_model_key(model_key)
    reasoning_effort = MODEL_SPECS[resolved_key].get("reasoning_effort")
    # "non-reasoning" is an INTERNAL sentinel (not an OpenRouter value): it omits the
    # reasoning field entirely. Real OpenRouter efforts are xhigh/high/medium/low/minimal/none.
    if not reasoning_effort or reasoning_effort == "non-reasoning":
        return {}
    return {"enabled": True, "effort": reasoning_effort}


# ===========================================================================
# STANDARDIZED FAILURE TYPE CONSTANTS (Phase 2)
# ===========================================================================
EXTRACTION_INVALID_JSON = "EXTRACTION_INVALID_JSON"
FAILED_MISSING_SCORE = "FAILED_MISSING_SCORE"
FAILED_OUT_OF_BOUNDS = "FAILED_OUT_OF_BOUNDS"
FAILED_INVALID_SCORE_TYPE = "FAILED_INVALID_SCORE_TYPE"
FAILED_API_EXHAUSTED = "FAILED_API_EXHAUSTED"
FAILED_UNKNOWN = "FAILED_UNKNOWN"

# LLM-Parameterized_Reference_Scoring-specific
FAILED_EXTRACTION_NON_JSON_WRAPPER = "FAILED_EXTRACTION_NON_JSON_WRAPPER"
FAILED_EXTRACTION_INVALID_DECISION_TYPE = "FAILED_EXTRACTION_INVALID_DECISION_TYPE"
FAILED_EXTRACTION_INVALID_CALCULATOR = "FAILED_EXTRACTION_INVALID_CALCULATOR"
FAILED_EXTRACTION_MISSING_PARAMETERS = "FAILED_EXTRACTION_MISSING_PARAMETERS"
FAILED_EXTRACTION_INVALID_PARAMETERS = "FAILED_EXTRACTION_INVALID_PARAMETERS"
FAILED_EXTRACTION_DECISION_TYPE_MISMATCH = "FAILED_EXTRACTION_DECISION_TYPE_MISMATCH"
FAILED_EXTRACTION_EXCEPTION = "FAILED_EXTRACTION_EXCEPTION"
FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION = "FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION"
FAILED_GROUND_TRUTH_MISSING_KEY = "FAILED_GROUND_TRUTH_MISSING_KEY"


# ===========================================================================
# PARAMETER NAME STANDARDIZATION PLAN (Phase 3)
# ===========================================================================
"""
This section documents the canonical variable name plan for future implementation:

1. LLM-Parameterized_Reference_Scoring.py internal variables:
   - Canonical `extracted_result` instead of `extraction_result`.
   - Canonical `extraction_diagnostics` instead of `extraction_diag`.
   - Keep input `decision_type` separate from LLM-extracted `extracted_decision_type`.
   - Canonical `failure_types` instead of `extraction_failure_types` / `failure_types_out`.

2. Direct_LLM_Prompting.py internal variables:
   - Canonical `scenario_diagnostics` (per-scenario) instead of `diagnostics`.
   - Canonical `cumulative_diagnostics` (final/cumulative metrics) instead of `total_diagnostics`.
   - Canonical `alternatives_scores` instead of `alt_scores` / `alternatives_scores`.
   - Canonical `scenario_failed` boolean flag instead of reading `diag.get("scenario_failed")`.

3. Example-Guided_LLM scoring.py.py internal variables:
   - Canonical `alternatives_scores` instead of `alternative`.
   - Canonical `cumulative_diagnostics` instead of `total_diagnostics`.
   - Canonical `ranking_results` instead of `ranking_result`.

4. Output Columns & Schema:
   - `scenario_id` (int): Unique identifier of the test scenario.
   - `question` (str): Scenario question text.
   - `location` (str): Location of the household/building.
   - `decision_type` (str): HVAC | Appliance | Shower
   - `outdoor_temp` (float/str): Outdoor temperature parameter.
   - `appliance_age` (float/str): Appliance age in years.
   - `flow_rate` (str): Shower flow rate label/value.
   - `alternative` (str): Decision alternative name/option.
   - `energy_cost` (float): Cost score or sentinel.
   - `environmental` (float): Environmental score or sentinel.
   - `comfort` (float): Comfort score or sentinel.
   - `practicality` (float): Practicality score or sentinel.
   - `rank` (int): Calculated alternative rank (1-3) or sentinel.
   - `weighted_score` (float): Calculated multi-attribute score or sentinel.
   - `calculator` (str): Ground truth calculator name used.
   - `extraction_failed` (bool): (LLM-Parameterized_Reference_Scoring only) True if LLM parameter extraction failed.
   - `gt_calculation_failed` (bool): (LLM-Parameterized_Reference_Scoring only) True if downstream calculator raised an exception.
"""