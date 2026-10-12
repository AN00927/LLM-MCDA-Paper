import os

# MODEL_KEY can be set per process (e.g. MODEL_KEY=qwen) without editing this file.
MODEL_KEY = os.getenv("MODEL_KEY", "gemini")
N_RUNS = 5



TEMPERATURE = 0.3


MAX_RETRIES = 10
REQUEST_TIMEOUT = 90
RETRY_BASE_DELAY = 2
MAX_RETRY_BACKOFF = 60


CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]

CRITERION_WEIGHTS = {
    "energy_cost": 0.30,
    "environmental": 0.35,
    "comfort": 0.20,
    "practicality": 0.15,
}


TIE_BREAK_PRIORITY = ["environmental", "energy_cost", "comfort", "practicality"]

TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520


MODEL_SPECS = {
    "gptoss": {
        "label": "input Price: $0.018/M, Output Price: $0.09/M",
        "openrouter_id": "openai/gpt-oss-20b:floor",
        "output_folder": "Output Files GPT-OSS 20B",
        "display_label": "GPT-OSS 20B",
        "reasoning_effort": "low",
        "provider": {
            "only": ["darkbloom/fp8"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    },
    "qwen": {
        "label": "Input Price: $0.10/M, Output Price: $0.15/M",
        "openrouter_id": "qwen/qwen3.5-9b:floor",
        "output_folder": "Output Files Qwen3.5 9B",
        "display_label": "Qwen3.5 9B",
        "reasoning_effort": "none",
        "provider": {
            "only": ["venice/fp8"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    },
    "deepseek": {
        "label": "Input Price: $0.13/M, Output Price: $0.26/M",
        "openrouter_id": "deepseek/deepseek-v4-flash-0731:floor",
        "output_folder": "Output Files DeepSeek V4 Flash 0731",
        "display_label": "DeepSeek V4 Flash",
        "reasoning_effort": "none",
        "provider": {
            "only": ["relace/fp4"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    },
    "gemini": {
        "label": "Input Price: $0.375/M, Output Price: $1.875/M",
        "openrouter_id": "google/gemini-3.8-flash:floor",
        "output_folder": "Output Files Gemini 3.8 Flash",
        "display_label": "Gemini 3.8 Flash",
        "reasoning_effort": "minimal",
        "provider": {
            "only": ["google-ai-studio/flex"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
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


def get_display_label(model_key: str = MODEL_KEY) -> str:
    """Return display name for model key."""
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["display_label"]


#: Per-model artifact subdirectories inside a model's output folder. Each holds
#: work whose scope is exactly one model; anything spanning models belongs in
#: the repository-level "Combined Metrics" directory instead.
MODEL_ARTIFACT_KINDS = (
    "position_bias",
    "hybrid_order_reversal",
    "listwise_direct",
    "prompt_ablation",
    "rag_ablation",
    "sensitivity",
    "metrics",
)


def get_model_artifact_subdir(model_key: str, kind: str) -> str:
    """Repo-relative directory holding one model's artifacts of a given kind."""
    if kind not in MODEL_ARTIFACT_KINDS:
        valid = ", ".join(MODEL_ARTIFACT_KINDS)
        raise ValueError(f"Unknown artifact kind: '{kind}'. Must be one of: {valid}")
    return f"{get_output_folder(model_key)}/{kind}"


def get_output_folder_for_model_id(model_id: str) -> str:
    for spec in MODEL_SPECS.values():
        if spec["openrouter_id"] == model_id:
            return spec["output_folder"]
    valid_models = ", ".join(sorted(spec["openrouter_id"] for spec in MODEL_SPECS.values()))
    raise ValueError(f"Unknown model id: '{model_id}'. Must be one of: {valid_models}")


def get_reasoning_payload(model_key: str = MODEL_KEY) -> dict:
    resolved_key = _resolve_model_key(model_key)
    reasoning_effort = MODEL_SPECS[resolved_key].get("reasoning_effort")
    if not reasoning_effort or reasoning_effort == "non-reasoning":
        return {"enabled": False}
    if reasoning_effort == "none":
        return {"effort": "none"}
    return {"enabled": True, "effort": reasoning_effort}


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

