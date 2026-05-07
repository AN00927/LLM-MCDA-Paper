MODEL_KEY = "mistral"
N_RUNS = 10

CRITERION_WEIGHTS = {
    "energy_cost": 0.30,
    "environmental": 0.35,
    "comfort": 0.20,
    "practicality": 0.15,
}
def get_output_folder(model_key: str = MODEL_KEY) -> str:
    if model_key == "mistral":
        return "Output Files Mistral"
    elif model_key == "qwen":
        return "Output Files Qwen"
    elif model_key == "claude":
        return "Output Files Claude"
    elif model_key == "gemini":
        return "Output Files Gemini"
    else:
        raise ValueError(
            f"Unknown MODEL_KEY: '{model_key}'. Must be one of: mistral, qwen, claude, gemini"
        )


def get_model_id(model_key: str = MODEL_KEY) -> str:
    if model_key == "mistral":
        return "mistralai/mistral-small-3.2-24b-instruct"
    elif model_key == "qwen":
        return "qwen/qwen-2.5-72b-instruct"
    elif model_key == "claude":
        return "anthropic/claude-sonnet-4"
    elif model_key == "gemini":
        return "google/gemini-2.5-pro"
    else:
        raise ValueError(
            f"Unknown MODEL_KEY: '{model_key}'. Must be one of: mistral, qwen, claude, gemini"
        )
