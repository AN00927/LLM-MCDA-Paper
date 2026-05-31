MODEL_KEY = "gptoss_smallest"
N_RUNS = 10


CRITERION_WEIGHTS = {
    "energy_cost": 0.30,
    "environmental": 0.35,
    "comfort": 0.20,
    "practicality": 0.15,
}


MODEL_SPECS = {
    "gptoss_smallest": {
        "label": "Smallest - GPT-OSS-20B",
        "openrouter_id": "openai/gpt-oss-20b:exacto",
        "output_folder": "Output Files GPT-OSS 20B",
        "reasoning_effort": "low",
    },
    "qwen_small": {
        "label": "Small - Qwen 3.5 9B",
        "openrouter_id": "qwen/qwen3.5-9b:exacto",
        "output_folder": "Output Files Qwen3.5 9B",
        "reasoning_effort": "low",
    },
    "deepseek_medium": {
        "label": "Medium - DeepSeek V4 Flash",
        "openrouter_id": "deepseek/deepseek-v4-flash:exacto",
        "output_folder": "Output Files DeepSeek V4 Flash",
        "reasoning_effort": "minimal",
    },
    "gemini_large": {
        "label": "Large - Gemini 3.5 Flash",
        "openrouter_id": "google/gemini-3.5-flash:exacto",
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
    resolved_key = _resolve_model_key(model_key)
    reasoning_effort = MODEL_SPECS[resolved_key].get("reasoning_effort")
    if not reasoning_effort or reasoning_effort == "non-reasoning":
        return {}
    return {"enabled": True, "effort": reasoning_effort}