MODEL_KEY = "deepseek_small"
N_RUNS = 10


CRITERION_WEIGHTS = {
    "energy_cost": 0.30,
    "environmental": 0.35,
    "comfort": 0.20,
    "practicality": 0.15,
}


MODEL_SPECS = {
    "deepseek_small": {
        "label": "Small Open - DeepSeek V4 Flash",
        "openrouter_id": "deepseek/deepseek-v4-flash",
        "output_folder": "Output Files DeepSeek V4 Flash",
        "reasoning_effort": "non-reasoning",
    },
    "qwen_large": {
        "label": "Large Open - Qwen 3.5 27B",
        "openrouter_id": "qwen/qwen3.5-27b",
        "output_folder": "Output Files Qwen3.5 27B",
    },
    "gemini": {
        "label": "Small Closed - GPT-5.4 nano",
        "openrouter_id": "openai/gpt-5.4",
        "output_folder": "Output Files GPT-5.4 nano",
        "reasoning_effort": "medium",
    },
    "gpt54": {
        "label": "Large Closed - Gemini 3.5 Flash",
        "openrouter_id": "google/gemini-3.5-flash",
        "output_folder": "Output Files Gemini 3.5 Flash",
        "reasoning_effort": "minimal",
    },
}



def _resolve_model_key(model_key: str) -> str:
    if model_key not in MODEL_SPECS:
        valid_keys = ", ".join(sorted(MODEL_SPECS.keys()))
        raise ValueError(f"Unknown MODEL_KEY: '{model_key}'. Must be one of: {valid_keys}")
    return model_key


def get_output_folder(model_key: str = MODEL_KEY) -> str:
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["output_folder"]


def get_model_id(model_key: str = MODEL_KEY) -> str:
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["openrouter_id"]


def get_reasoning_effort(model_key: str = MODEL_KEY) -> str:
    resolved_key = _resolve_model_key(model_key)
    return MODEL_SPECS[resolved_key]["reasoning_effort"]


def get_reasoning_payload(model_key: str = MODEL_KEY) -> dict:
    if "reasoning_effort"  not in MODEL_SPECS[_resolve_model_key(model_key)]:
        return {"effort": get_reasoning_effort(model_key)}