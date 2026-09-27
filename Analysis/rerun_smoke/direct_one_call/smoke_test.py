"""Phase R smoke test: one real Direct scoring call per model.

Scores the first alternative of the first HVAC test scenario once per
MODEL_KEY, with the architecture's own prompt, payload and validation. The raw
record is captured here instead of the model's output folder, so nothing in
the benchmark folders changes. Writes smoke_results.json next to this file.

Run: python Analysis/rerun_smoke/direct_one_call/smoke_test.py  (spawns one child per model)
"""
import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("smoke_results.json")
MODELS = ["gptoss", "qwen", "deepseek", "gemini"]


def child():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "Architectures"))
    spec = importlib.util.spec_from_file_location(
        "direct", ROOT / "Architectures" / "Direct_LLM_Scoring.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    captured = {}
    mod._record_call = lambda scenario, alt, sp, up, response, diag, scores, ft, **kw: \
        captured.update(response=response, diagnostics=diag, scores=scores, failure_types=ft, **kw)
    df = mod.read_table_clean(mod.TEST_SCENARIOS,
                              keep_str_cols=["alternative_1", "alternative_2", "alternative_3"])
    row = df[df["decision_type"] == "HVAC"].iloc[0].to_dict()
    alt = row["alternative_1"]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    err = None
    try:
        mod.score_alternative(row, alt)
    except Exception as e:  # report, don't hide
        err = repr(e)
    d = captured.get("diagnostics") or {}
    print(json.dumps({
        "model_key": os.environ["MODEL_KEY"],
        "requested_model": mod.API_CONFIG["model"],
        "reasoning_sent": mod.API_CONFIG["reasoning"],
        "temperature_sent": mod.API_CONFIG["temperature"],
        "collected_utc": started,
        "scenario_id": row.get("scenario_id"), "alternative": str(alt),
        "success": d.get("success"), "error": err,
        "failure_types": captured.get("failure_types"),
        "response_model": d.get("response_model"), "provider": d.get("provider"),
        "finish_reason": d.get("finish_reason"),
        "tokens_input": d.get("tokens_input"), "tokens_output": d.get("tokens_output"),
        "reasoning_tokens": d.get("reasoning_tokens"), "cost_usd": d.get("cost"),
        "latency_ms": d.get("latency_ms"), "retries": d.get("retries"),
        "attempt_errors": d.get("attempt_errors"),
        "request_params": d.get("request_params"),
        "scores": captured.get("scores"), "response": captured.get("response"),
    }, default=str))


def main():
    results = []
    for key in MODELS:
        env = dict(os.environ, MODEL_KEY=key, SMOKE_CHILD="1")
        p = subprocess.run([sys.executable, __file__], env=env, capture_output=True, text=True)
        line = (p.stdout.strip().splitlines() or [""])[-1]
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            results.append({"model_key": key, "error": "child failed", "stderr": p.stderr[-2000:]})
        r = results[-1]
        print(key, r.get("success"), r.get("provider"), r.get("tokens_input"),
              r.get("tokens_output"), r.get("reasoning_tokens"), r.get("cost_usd"), r.get("error"))
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    child() if os.environ.get("SMOKE_CHILD") else main()
