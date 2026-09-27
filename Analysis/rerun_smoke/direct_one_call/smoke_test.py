"""Phase R smoke test: one real Direct scoring call per model.

Scores the first alternative of the first HVAC test scenario once per
MODEL_KEY, with the architecture's own prompt, payload and validation. The raw
record is captured here instead of the model's output folder, so nothing in
the benchmark folders changes. Writes smoke_results.json next to this file.

Run: python Analysis/rerun_smoke/direct_one_call/smoke_test.py  (spawns one child per model)

Optional environment, for testing a setting before it goes into model_config.py:
  SMOKE_MODELS    comma-separated model keys (default: all four)
  SMOKE_OVERRIDE  JSON {model_key: {spec_field: value}} merged into MODEL_SPECS in memory
  SMOKE_N         number of HVAC test scenarios, all three alternatives each (default: one call)
  SMOKE_WORKERS   concurrent calls (default 1)
  SMOKE_OUT       output file name (default smoke_results.json)
"""
import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name(os.environ.get("SMOKE_OUT", "smoke_results.json"))
MODELS = os.environ.get("SMOKE_MODELS", "gptoss,qwen,deepseek,gemini").split(",")


def child():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "Architectures"))
    import model_config
    for field, value in json.loads(os.environ.get("SMOKE_OVERRIDE", "{}")).get(
            os.environ["MODEL_KEY"], {}).items():
        model_config.MODEL_SPECS[os.environ["MODEL_KEY"]][field] = value
    spec = importlib.util.spec_from_file_location(
        "direct", ROOT / "Architectures" / "Direct_LLM_Scoring.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._record_call = lambda *a, **k: None
    df = mod.read_table_clean(mod.TEST_SCENARIOS,
                              keep_str_cols=["alternative_1", "alternative_2", "alternative_3"])
    hvac = df[df["decision_type"] == "HVAC"]
    n = int(os.environ.get("SMOKE_N", "0"))
    jobs = ([(hvac.iloc[0].to_dict(), hvac.iloc[0]["alternative_1"])] if n == 0 else
            [(r, r[f"alternative_{i}"]) for r in (hvac.iloc[j].to_dict() for j in range(n))
             for i in (1, 2, 3)])

    def one(job):
        row, alt = job
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        err, scores, d = None, None, {}
        try:
            scores, d = mod.score_alternative(row, alt)
        except Exception as e:  # report, don't hide
            err = repr(e)
            d = getattr(e, "diagnostics", {}) or {}
        return {
            "model_key": os.environ["MODEL_KEY"],
            "requested_model": mod.API_CONFIG["model"],
            "reasoning_sent": mod.API_CONFIG["reasoning"],
            "temperature_sent": mod.API_CONFIG["temperature"],
            "collected_utc": started,
            "scenario_id": row.get("scenario_id"), "alternative": str(alt),
            "success": d.get("success"), "error": err,
            "failure_types": d.get("failure_types"),
            "response_model": d.get("response_model"), "provider": d.get("provider"),
            "finish_reason": d.get("finish_reason"),
            "tokens_input": d.get("tokens_input"), "tokens_output": d.get("tokens_output"),
            "reasoning_tokens": d.get("reasoning_tokens"), "cost_usd": d.get("cost"),
            "latency_ms": d.get("latency_ms"), "retries": d.get("retries"),
            "attempt_errors": d.get("attempt_errors"),
            "request_params": d.get("request_params"), "scores": scores,
        }

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(int(os.environ.get("SMOKE_WORKERS", "1"))) as ex:
        records = list(ex.map(one, jobs))
    print(json.dumps(records, default=str))


def main():
    results = []
    for key in MODELS:
        env = dict(os.environ, MODEL_KEY=key, SMOKE_CHILD="1")
        p = subprocess.run([sys.executable, __file__], env=env, capture_output=True, text=True)
        line = (p.stdout.strip().splitlines() or [""])[-1]
        try:
            recs = json.loads(line)
        except json.JSONDecodeError:
            recs = [{"model_key": key, "error": "child failed", "stderr": p.stderr[-2000:]}]
        results.extend(recs)
        for r in recs:
            print(key, r.get("success"), r.get("provider"), r.get("tokens_input"),
                  r.get("tokens_output"), r.get("reasoning_tokens"), r.get("cost_usd"),
                  r.get("retries"), r.get("error"))
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    child() if os.environ.get("SMOKE_CHILD") else main()
