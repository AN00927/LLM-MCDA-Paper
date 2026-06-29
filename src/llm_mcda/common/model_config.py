MODEL_KEY = "qwen"
N_RUNS = 5



TEMPERATURE = 0.3


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
    "gptoss": {
        "label": "input Price: $0.029/M, Output Price: $0.14/M",
        "openrouter_id": "openai/gpt-oss-20b:exacto",
        "output_folder": "Output Files GPT-OSS 20B",
        "reasoning_effort": "low",  
    },
    "qwen": {
        "label": "0.04/M, 0.15M",
        "openrouter_id": "qwen/qwen3.5-9b:exacto",
        "output_folder": "Output Files Qwen3.5 9B",
        "reasoning_effort": "non-reasoning",
    },
    "deepseek": {
        "label": "Input Price: $0.0983/M, Output Price: $0.1966/M",
        "openrouter_id": "deepseek/deepseek-v4-flash:exacto",
        "output_folder": "Output Files DeepSeek V4 Flash",
        "reasoning_effort": "non-reasoning",
    },
    "gemini": {
        "label": "Input Price: $1.50/M, Output Price: $9/M",
        "openrouter_id": "google/gemini-3.5-flash:exacto",
        "output_folder": "Output Files Gemini 3.5 Flash",
        "reasoning_effort": "non-reasoning",  
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


def get_output_folder_for_model_id(model_id: str) -> str:
    for spec in MODEL_SPECS.values():
        if spec["openrouter_id"] == model_id:
            return spec["output_folder"]
    valid_models = ", ".join(sorted(spec["openrouter_id"] for spec in MODEL_SPECS.values()))
    raise ValueError(f"Unknown model id: '{model_id}'. Must be one of: {valid_models}")



def get_reasoning_effort(model_key: str = MODEL_KEY) -> str:
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["reasoning_effort"]


def get_reasoning_payload(model_key: str = MODEL_KEY) -> dict:
    resolved_key = _resolve_model_key(model_key)
    reasoning_effort = MODEL_SPECS[resolved_key].get("reasoning_effort")
    # "non-reasoning" is an INTERNAL sentinel: actively disable reasoning.
    # OpenRouter's {"exclude": True} only hides reasoning text from the response;
    # Qwen can still spend tokens thinking internally unless enabled is false.
    # Real OpenRouter efforts are xhigh/high/medium/low/minimal/none.
    if not reasoning_effort or reasoning_effort == "non-reasoning":
        return {"enabled": False}
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

