MODEL_KEY = "qwen_small"
N_RUNS = 10


CRITERION_WEIGHTS = {
    "energy_cost": 0.30,
    "environmental": 0.35,
    "comfort": 0.20,
    "practicality": 0.15,
}


def get_output_folder(model_key: str = MODEL_KEY) -> str:
    if model_key == "qwen_small":
        return "Output Files Qwen3.5 9B"
    elif model_key == "qwen_large":
        return "Output Files Qwen3.5 27B"
    elif model_key == "gemini":
        return "Output Files Gemini 3.5 Flash"
    elif model_key == "gpt5":
        return "Output Files GPT-5"
    else:
        raise ValueError(
            f"Unknown MODEL_KEY: '{model_key}'. Must be one of: qwen_small, qwen_large, gemini, gpt5"
        )


def get_model_id(model_key: str = MODEL_KEY) -> str:
    if model_key == "qwen_small":
        return "qwen/qwen3.5-9b"
    elif model_key == "qwen_large":
        return "qwen/qwen3.5-27b"
    elif model_key == "gemini":
        return "google/gemini-3.5-flash"
    elif model_key == "gpt5":
        return "openai/gpt-5"
    else:
        raise ValueError(
            f"Unknown MODEL_KEY: '{model_key}'. Must be one of: qwen_small, qwen_large, gemini, gpt5"
        )