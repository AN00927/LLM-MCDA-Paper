"""Listwise direct ranking: an A_D arm that asks the LLM to rank the three
alternatives in one call instead of scoring each one on four criteria.

Why: the research question is about reproducing
a ranking, and A_D sits near chance on Top-1. A reader from the LLM-as-judge
literature will ask whether a model that scores badly can still rank well when
asked to rank directly. This arm answers that. If listwise ranking does no
better than pointwise A_D, A_D's failure is not an artifact of the scoring
format.

What the model sees:
  - System prompt: A_D's own header and per-criterion good/moderate/poor
    anchors, sliced verbatim out of the prompt-ablation script's copy, which is
    checked against the installed Direct_LLM_Scoring.py at startup. Then the
    decision-maker's weights, read from model_config.CRITERION_WEIGHTS.
    Pointwise A_D never needs the weights, because the code aggregates its
    scores. A listwise ranking is undefined without them. Nothing else from the
    value model is given: no value functions, no reference ranges, no scores.
  - User prompt: the alternatives in the scenario's own order, then A_D's
    scenario-context block, sliced out of A_D's user prompt so the two cannot
    drift.
  - The model returns {"ranking": [best, second, third]} using the exact labels.

One call per scenario. Metrics use the prompt ablation's scenario_metrics and
reference, so tau, Top-1 and Top-2 are computed exactly as for every other arm:
  - Failure-as-wrong: a failed or invalid ranking counts as a miss for Top-1
    and Top-2.
  - Kendall tau is 0 (chance) for a failed ranking, with every scenario in the
    denominator (failure rule).
The comparison arm is pointwise A_D, rebuilt from the main suite's five runs.

API: the architectures' shared client, through the prompt ablation's
query_openrouter. That means the same payload, provider pin, temperature,
reasoning, 8,192-token cap, retry policy and failure rules. Every call is
archived to a raw jsonl with its own collected_utc. Each run's xlsx carries
collected_utc and model_id. HTTP 401/402/403, or the consecutive-failure
breaker, stops the process, and the interrupted run is not written.

Outputs: <safe output-dir>/<model>/listwise_direct/AD_listwise_run_NN.xlsx and
..._raw.jsonl. Resume-aware per run. Analysis writes
<safe output-dir>/listwise_summary.xlsx. Pass the same output directory to
later `run` or `analyze` calls, or set LLM_MCDA_RUN_OUTPUT_DIR.

Run (paid; 195 calls per run, 5 runs per model by default):
    python "scripts/experiments/run_listwise_direct_ranking.py" run --output-dir results/listwise
    python "scripts/experiments/run_listwise_direct_ranking.py" run --models qwen --n 6 --runs 1 --output-dir results/listwise   # smoke
    python "scripts/experiments/run_listwise_direct_ranking.py" analyze --output-dir results/listwise
"""

import argparse
import importlib.util
import json
import logging
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap the checkout root before importing the shared modules.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMPORT_ROOT = PROJECT_ROOT
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))

import numpy as np
import pandas as pd

from common.paths import (
    RUN_OUTPUT_DIR_ENV,
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_directory,
)
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.model_config import CRITERION_WEIGHTS, MODEL_SPECS, N_RUNS
from common.sentinel_utils import (
    CRITERIA,
    FAILED_API_BAD_REQUEST,
    FAILED_TRUNCATED,
    SENTINEL_FLOAT,
    RawCallLog,
    RunAbort,
    _atomic_write_xlsx,
    _is_complete_run_file,
    read_table_clean,
)

logger = logging.getLogger("listwise_direct")

OUTPUT_SUBDIR = "listwise_direct"
RUN_XLSX = "AD_listwise_run_{run:02d}.xlsx"
RUN_JSONL = "AD_listwise_run_{run:02d}_raw.jsonl"
OUTPUT_DIR: Optional[Path] = None
METRIC_COLS = ["kendall_tau", "top1", "top2"]

ERR_API_EXHAUSTED = "failed_api_exhausted"
ERR_API_BAD_REQUEST = "failed_api_bad_request"
ERR_TRUNCATED = "failed_truncated"
ERR_EMPTY = "failed_empty_response"
ERR_MALFORMED = "failed_malformed_json"
ERR_INVALID_RANKING = "failed_invalid_ranking"


def _load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The prompt ablation carries the checked copy of A_D's prompts, the reference
# ranking, the metric function and the shared-client wrapper; reusing them keeps
# this arm on exactly the same definitions.
PA = _load(PROJECT_ROOT / "scripts" / "experiments" / "run_prompt_ablation_experiments.py",
           "listwise_prompt_ablation")

RAW_LOG = RawCallLog()
_raw_log_lock = threading.Lock()
_ABORT = threading.Event()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_AD_HEADER_END = "Score alternatives on four criteria using the inclusive 0-1 scale (0.0 <= score <= 1.0):\n"
_AD_ANCHORS_END = "\nReturn ONLY:"


def _ad_parts() -> Tuple[str, str]:
    """(header, anchors) cut verbatim out of A_D's system prompt."""
    text = PA.AD_SYSTEM_PROMPT
    i = text.index(_AD_HEADER_END)
    j = text.index(_AD_ANCHORS_END)
    return text[:i], text[i + len(_AD_HEADER_END):j]


_CRITERION_NAMES = {"energy_cost": "energy_cost", "environmental": "environmental",
                    "comfort": "comfort", "practicality": "practicality"}


def weights_sentence() -> str:
    parts = [f"{_CRITERION_NAMES[c]} {round(100 * w)}%"
             for c, w in sorted(CRITERION_WEIGHTS.items(), key=lambda kv: -kv[1])]
    return ("The household weighs the four criteria as follows: " + ", ".join(parts)
            + ". Rank the alternatives by their overall performance under these weights.")


def build_system_prompt() -> str:
    header, anchors = _ad_parts()
    return (header
            + "Rank the alternatives from best to worst for this household, judging them on four criteria:\n"
            + anchors
            + "\n" + weights_sentence() + "\n\n"
            + 'Return ONLY: {"ranking": ["<best alternative>", "<second>", "<third>"]} '
              "using each alternative label exactly as given, each exactly once.\n")


def alternatives_of(scenario: Dict) -> List[str]:
    alts = [scenario.get(f"alternative_{i}") for i in (1, 2, 3)]
    return [str(a) for a in alts if a not in (None, "", "N/A")]


def context_block(scenario: Dict) -> str:
    """A_D's scenario description (decision and SCENARIO CONTEXT lines), cut
    out of A_D's own user prompt so both arms describe the scenario identically."""
    alts = alternatives_of(scenario)
    ad = PA.build_user_prompt(scenario, alts[0])
    start = ad.index('For the decision: "')
    end = ad.index("\nProvide scores (0-1) for all 4 criteria.")
    return ad[start:end]


def build_user_prompt(scenario: Dict) -> str:
    return (f"Rank these alternatives: {json.dumps(alternatives_of(scenario))}\n\n"
            + context_block(scenario)
            + "\nRank all of the alternatives from best to worst.\n")


def build_messages(scenario: Dict) -> List[Dict]:
    return [{"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(scenario)}]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _norm(label) -> str:
    s = str(label).strip().strip('"').strip().lower()
    try:
        return f"{float(s):g}"
    except ValueError:
        return s


def parse_ranking(text: Optional[str], alternatives: List[str]) -> Tuple[Optional[List[str]], Optional[str]]:
    """The model's ranking mapped back onto the scenario's own labels, best
    first, or (None, error). It must name every alternative exactly once."""
    if text is None or not text.strip():
        return None, ERR_EMPTY
    body = text.strip()
    if body.startswith("```"):
        parts = body.split("```")
        if len(parts) >= 2:
            body = parts[1]
            if body.lower().startswith("json"):
                body = body[4:]
            body = body.strip()
    parsed = None
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        for match in reversed(list(re.finditer(r"\{[^{}]*\}", body, re.DOTALL))):
            try:
                candidate = json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(candidate, dict) and "ranking" in candidate:
                parsed = candidate
                break
    if not isinstance(parsed, dict) or not isinstance(parsed.get("ranking"), list):
        return None, ERR_MALFORMED
    by_norm = {_norm(a): a for a in alternatives}
    if len(by_norm) != len(alternatives):
        return None, ERR_INVALID_RANKING   # two labels normalise alike; cannot map back
    ranked = [by_norm.get(_norm(x)) for x in parsed["ranking"]]
    if None in ranked or len(ranked) != len(alternatives) or len(set(ranked)) != len(alternatives):
        return None, ERR_INVALID_RANKING
    return ranked, None


def ranking_result(alternatives: List[str], ranked: Optional[List[str]]) -> Dict:
    """The shape PA.scenario_metrics reads. A failed ranking carries the
    sentinel so scenario_metrics marks it failed (never a neutral default)."""
    if ranked is None:
        scored = [{"alternative": a, **{c: SENTINEL_FLOAT for c in CRITERIA}} for a in alternatives]
        return {"scored": scored, "ranking": {"ranks": [None] * len(alternatives),
                                              "ranked_alternatives": []}}
    pos = {a: i + 1 for i, a in enumerate(ranked)}
    scored = [{"alternative": a, **{c: 0.0 for c in CRITERIA}} for a in alternatives]
    return {"scored": scored, "ranking": {"ranks": [pos[a] for a in alternatives],
                                          "ranked_alternatives": list(ranked)}}


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def output_dir_for(model_key: str) -> Path:
    if OUTPUT_DIR is None:
        raise RuntimeError("Output directory has not been validated; call main() first.")
    return OUTPUT_DIR / model_key / OUTPUT_SUBDIR


def rank_scenario(scenario: Dict, model_key: str, reference: Dict[int, Dict]) -> Dict:
    model_id = MODEL_SPECS[model_key]["openrouter_id"]
    alternatives = alternatives_of(scenario)
    messages = build_messages(scenario)
    if _ABORT.is_set():
        raise RunAbort("aborted: another worker hit a fatal OpenRouter error")
    try:
        response, diag = PA.query_openrouter(messages, model_id, model_key)
    except RunAbort as abort:
        fatal = PA._call_diagnostics(getattr(abort, "diagnostics", {}) or {}, model_id)
        with _raw_log_lock:
            RAW_LOG.record(scenario_id=scenario["scenario_id"], model_key=model_key, model=model_id,
                           prompt=messages[-1]["content"], response="", error=str(abort),
                           failure_type=fatal.get("failure_type") or "fatal", api_success=False)
        _ABORT.set()
        raise

    failure_type = diag.get("failure_type")
    if failure_type == FAILED_TRUNCATED:
        ranked, error = None, ERR_TRUNCATED
    elif response is None:
        ranked, error = None, (ERR_API_BAD_REQUEST if failure_type == FAILED_API_BAD_REQUEST
                               else ERR_API_EXHAUSTED)
    else:
        ranked, error = parse_ranking(response, alternatives)

    with _raw_log_lock:
        RAW_LOG.record(scenario_id=scenario["scenario_id"],
                       decision_type=scenario.get("decision_type", ""),
                       architecture="AD_listwise", model_key=model_key, model=model_id,
                       alternatives=alternatives, prompt=messages[-1]["content"],
                       response=response or "", ranking=ranked,
                       prompt_tokens=diag.get("prompt_tokens", 0),
                       completion_tokens=diag.get("completion_tokens", 0),
                       latency_ms=diag.get("latency_ms", 0), error=diag.get("error", ""),
                       failure_type=failure_type,
                       **{k: v for k, v in diag.items()
                          if k in ("provider", "response_id", "response_model", "finish_reason",
                                   "usage", "cost", "reasoning_tokens", "attempts", "retries",
                                   "attempt_errors", "request_params")},
                       api_success=response is not None, parse_error=error)

    result = ranking_result(alternatives, ranked)
    metrics = PA.scenario_metrics(result, reference.get(scenario["scenario_id"]))
    return {
        "scenario_id": scenario["scenario_id"],
        "decision_type": scenario.get("decision_type", ""),
        "alternatives_json": json.dumps(alternatives),
        "ranking_json": json.dumps(ranked) if ranked else "",
        "kendall_tau": metrics["kendall_tau"], "top1": metrics["top1"], "top2": metrics["top2"],
        "failed": metrics["failed"],
        "pred_top1": ranked[0] if ranked else "",
        "failure_type": error or "",
        "prompt_tokens": diag.get("prompt_tokens", 0) or 0,
        "completion_tokens": diag.get("completion_tokens", 0) or 0,
        "reasoning_tokens": diag.get("reasoning_tokens") or 0,
        "cost_usd": diag.get("cost"),
        "provider": diag.get("provider"),
    }


def run_one(model_key: str, run_idx: int, scenarios: List[Dict], reference: Dict[int, Dict],
            workers: int) -> Optional[Path]:
    out_dir = output_dir_for(model_key)
    xlsx = out_dir / RUN_XLSX.format(run=run_idx)
    if _is_complete_run_file(xlsx):
        logger.info("SKIP %s run %s: %s already complete", model_key, run_idx, xlsx.name)
        return xlsx
    collected_utc = datetime.now(timezone.utc).isoformat()
    RAW_LOG.start(out_dir / RUN_JSONL.format(run=run_idx), run=run_idx)
    rows: List[Optional[Dict]] = [None] * len(scenarios)
    try:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(rank_scenario, sc, model_key, reference): i
                       for i, sc in enumerate(scenarios)}
            try:
                for fut in as_completed(futures):
                    i = futures[fut]
                    try:
                        rows[i] = fut.result()
                    except RunAbort:
                        raise
                    except Exception as exc:  # one scenario must not sink the run
                        logger.warning("scenario %s raised: %s", scenarios[i]["scenario_id"], exc)
                        rows[i] = {"scenario_id": scenarios[i]["scenario_id"],
                                   "decision_type": scenarios[i].get("decision_type", ""),
                                   "kendall_tau": np.nan, "top1": 0.0, "top2": 0.0,
                                   "failed": True, "failure_type": f"harness_exception: {exc}"[:200]}
            except BaseException:
                _ABORT.set()
                pool.shutdown(wait=True, cancel_futures=True)
                raise
    finally:
        RAW_LOG.stop()
    df = pd.DataFrame(rows)
    df.insert(0, "run", run_idx)
    df.insert(0, "model_id", MODEL_SPECS[model_key]["openrouter_id"])
    df.insert(0, "model", model_key)
    df["collected_utc"] = collected_utc
    _atomic_write_xlsx(df, xlsx)
    logger.info("DONE %s run %s: tau %.3f, top1 %.3f, failed %d of %d", model_key, run_idx,
                df["kendall_tau"].mean(), df["top1"].mean(), int(df["failed"].sum()), len(df))
    return xlsx


# ---------------------------------------------------------------------------
# Analysis (offline)
# ---------------------------------------------------------------------------

def load_listwise_runs(model_key: str) -> pd.DataFrame:
    paths = sorted(output_dir_for(model_key).glob("AD_listwise_run_*.xlsx"))
    paths = [p for p in paths if not p.name.endswith("_raw.jsonl")]
    if not paths:
        return pd.DataFrame()
    df = pd.concat([read_table_clean(p) for p in paths], ignore_index=True)
    # Rescore from the stored rankings against the corrected reference (see
    # run_prompt_ablation_experiments.load_reference): runs collected before
    # that fix stored metrics against a wrong reference for 16 Shower scenarios.
    reference = PA.load_reference()
    for idx, row in df.iterrows():
        ranked = json.loads(row["ranking_json"]) if isinstance(row.get("ranking_json"), str) \
            and row["ranking_json"].strip() else None
        if ranked is None or not isinstance(row.get("alternatives_json"), str):
            continue
        m = PA.scenario_metrics(ranking_result(json.loads(row["alternatives_json"]), ranked),
                                reference.get(int(row["scenario_id"])))
        for k in ("kendall_tau", "top1", "top2", "failed", "pred_top1"):
            df.at[idx, k] = m[k]
    # Failure rule: runs written before 2026-09-29 stored NaN for a failed
    # ranking's tau; it is the chance value 0, like every other arm.
    df.loc[df["failed"].astype(bool), "kendall_tau"] = PA.FAILED_SCENARIO_TAU
    return df


def analyze(models: List[str], pointwise_runs: int = N_RUNS) -> Dict[str, pd.DataFrame]:
    """Listwise vs pointwise A_D, per model, never pooled. Per-scenario metrics
    are averaged over runs first, then compared with a paired Wilcoxon
    signed-rank test; Holm across (model x metric)."""
    rag = _load(PROJECT_ROOT / "scripts" / "experiments" / "run_rag_ablation_experiments.py",
                "listwise_rag_stats")
    reference = PA.load_reference()
    summary, tests = [], []
    for model_key in models:
        lw = load_listwise_runs(model_key)
        if lw.empty:
            print(f"SKIP {model_key}: no listwise runs in {output_dir_for(model_key)}")
            continue
        try:
            pw = PA.main_suite_control_rows(model_key, "AD", pointwise_runs, reference,
                                            scenario_ids=set(int(s) for s in lw["scenario_id"]))
        except FileNotFoundError as exc:
            print(f"{model_key}: pointwise A_D not available yet ({exc}); listwise summary only")
            pw = pd.DataFrame()
        for arm, df in (("listwise", lw), ("pointwise", pw)):
            if df.empty:
                continue
            per_run = df.groupby("run").agg(kendall_tau=("kendall_tau", "mean"),
                                            top1=("top1", "mean"), top2=("top2", "mean"),
                                            n_failed=("failed", "sum"), n=("scenario_id", "size"))
            summary.append({"model": model_key, "arm": arm, "n_runs": len(per_run),
                            **{f"{m}_mean": per_run[m].mean() for m in METRIC_COLS},
                            **{f"{m}_sd": per_run[m].std() for m in METRIC_COLS},
                            "failed_per_run": per_run["n_failed"].mean(),
                            "scenarios": int(per_run["n"].iloc[0])})
        if pw.empty:
            continue
        both = pd.concat([lw.assign(arm="listwise"), pw.assign(arm="pointwise")], ignore_index=True)
        per_scenario = both.groupby(["arm", "scenario_id"], as_index=False)[METRIC_COLS].mean()
        for metric in METRIC_COLS:
            ph = rag.posthoc_wilcoxon_holm(per_scenario, metric, config_col="arm",
                                           scenario_col="scenario_id")
            if ph.empty:
                continue
            r = ph.iloc[0]
            tests.append({"model": model_key, "metric": metric, "config_i": r["config_i"],
                          "config_j": r["config_j"], "statistic": r["statistic"],
                          "p_value": r["p_value"],
                          "rank_biserial": r["rank_biserial"],
                          "rank_biserial_interpretation": r["rank_biserial_interpretation"],
                          "n_nonzero": r["n_nonzero"],
                          "cliff_delta": r["cliff_delta"],
                          "cliff_delta_interpretation": r["cliff_delta_interpretation"],
                          "n_pairs": r["n_pairs"]})
    summary_df, tests_df = pd.DataFrame(summary), pd.DataFrame(tests)
    if len(tests_df):
        tests_df["p_holm"], tests_df["significant_holm"] = rag.holm_correct(tests_df["p_value"].values)
    if OUTPUT_DIR is None:
        raise RuntimeError("Output directory has not been validated; call main() first.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / "listwise_summary.xlsx"
    with pd.ExcelWriter(summary_path) as xl:
        summary_df.to_excel(xl, sheet_name="summary", index=False)
        tests_df.to_excel(xl, sheet_name="wilcoxon_vs_pointwise", index=False)
    if len(summary_df):
        print(summary_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    if len(tests_df):
        print(tests_df.to_string(index=False, float_format=lambda v: f"{v:.4g}"))
    print(f"Wrote {summary_path}")
    return {"summary": summary_df, "tests": tests_df}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    global OUTPUT_DIR
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("command", choices=["run", "analyze"])
    p.add_argument("--models", nargs="+", default=list(MODEL_SPECS), choices=list(MODEL_SPECS))
    p.add_argument("--runs", type=int, default=N_RUNS, help=f"Runs per model (default {N_RUNS}).")
    p.add_argument("--n", default="all", help="Test scenarios ('all' = 195, or a stratified count).")
    p.add_argument("--seed", type=int, default=13)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--output-dir", default=os.environ.get(RUN_OUTPUT_DIR_ENV),
                   help=f"New or existing safe output directory (or set {RUN_OUTPUT_DIR_ENV}); "
                        "required to write results outside frozen repository data.")
    args = p.parse_args(argv)
    try:
        OUTPUT_DIR = require_safe_output_directory(
            args.output_dir, option=f"--output-dir (or {RUN_OUTPUT_DIR_ENV})", root=PROJECT_ROOT
        )
    except UnsafeOutputPathError as exc:
        p.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if args.command == "analyze":
        analyze(args.models)
        return

    if not PA.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found in .env")
    PA._assert_control_matches_shipped()      # the anchors this arm reuses are A_D's
    PA._assert_control_is_main_suite(["AD"])  # and the context block is A_D's
    scenarios = PA.load_scenarios(PA.parse_sample_size(args.n), args.seed)
    reference = PA.load_reference()
    for model_key in args.models:
        for run_idx in range(1, args.runs + 1):
            logger.info("Listwise A_D: %s run %s/%s (%s scenarios)",
                        model_key, run_idx, args.runs, len(scenarios))
            run_one(model_key, run_idx, scenarios, reference, args.workers)


if __name__ == "__main__":
    main()
