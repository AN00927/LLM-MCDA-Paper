"""Run one P2 script as __main__ with each model spec pointed at its shipped
output folder while model_config.py names a rerun folder that is still empty.
Usage: python _run_with_gemini35.py <script> [args...]"""
import runpy, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from model_config import MODEL_SPECS
# model_config.py is being repointed at the rerun's folders (P3: Gemini 3.8
# Flash, DeepSeek V4.1 Flash). The data these checks use is the shipped
# collection, so each in-process spec whose folder holds no A_H run files yet
# is redirected to the shipped folder. model_config.py itself is not touched.
SHIPPED_FOLDERS = {"gptoss": "Output Files GPT-OSS 20B", "qwen": "Output Files Qwen3.5 9B",
                   "deepseek": "Output Files DeepSeek V4 Flash",
                   "gemini": "Output Files Gemini 3.5 Flash"}
for _mk, _shipped in SHIPPED_FOLDERS.items():
    if (not list((ROOT / MODEL_SPECS[_mk]["output_folder"]).glob(
            "LLM-Parameterized_Reference_Scoring_results_run_*.xlsx"))
            and (ROOT / _shipped).exists()):
        MODEL_SPECS[_mk]["output_folder"] = _shipped
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
