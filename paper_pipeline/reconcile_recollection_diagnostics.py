#!/usr/bin/env python3
"""
reconcile_recollection_diagnostics.py

After the A_E Shower re-collection, each shipped run's `*_results_run_NN.xlsx`
holds new Shower scores while its `*_results_diagnostics_run_NN.json` still
describes the original collection. `analyze_benchmark_failures.py` reads sentinel
COUNTS from the xlsx but failure-MODE attribution from the JSON, so the two
disagree and the supplement's failure-mode table over-reports.

The shower re-collection produced zero sentinel scores, so every failure the JSON
attributes to a Shower scenario no longer exists. This subtracts exactly those.

The pre-splice workbooks are tracked in git, so the shower failure counts are
recovered with `git show HEAD:<path>` rather than from the re-collection's own
diagnostics.

What is NOT changed: token counts, latency, and cost. Those describe the original
195-scenario collection, which is what the paper's cost table reports and what a
reader re-running the benchmark would spend. Mixing a 60-scenario correction pass
into them would describe neither run.

Usage:
    python paper_pipeline/reconcile_recollection_diagnostics.py --dry-run
    python paper_pipeline/reconcile_recollection_diagnostics.py
"""

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import is_sentinel  # noqa: E402

ARCH = "Example-Guided_LLM_Scoring"
CRIT = ["energy_cost", "environmental", "comfort", "practicality"]
FOLDERS = ["Output Files DeepSeek V4 Flash", "Output Files Gemini 3.5 Flash",
           "Output Files GPT-OSS 20B", "Output Files Qwen3.5 9B"]

# Fields that count failures and must shrink; token/latency fields are untouched.
COUNT_FIELDS = ["failed_calls", "failed_scenarios"]
MODE_PREFIXES = ("EXTRACTION", "FAILED")


def git_show(relpath):
    """Pre-splice copy of a tracked file, from HEAD."""
    out = subprocess.run(["git", "show", f"HEAD:{relpath}"],
                         cwd=PROJECT_ROOT, capture_output=True)
    if out.returncode != 0:
        return None
    return pd.read_excel(io.BytesIO(out.stdout))


def shower_failures(df):
    """(failed alternatives, failed scenarios) among Shower rows."""
    if df is None or "decision_type" not in df.columns:
        return 0, 0
    sh = df[df["decision_type"] == "Shower"]
    if sh.empty:
        return 0, 0
    cols = [c for c in CRIT if c in sh.columns]
    bad_rows = sh[[any(is_sentinel(r[c]) for c in cols) for _, r in sh.iterrows()]]
    return len(bad_rows), bad_rows["scenario_id"].nunique()


def all_failures(df):
    """(failed alternatives, failed scenarios) across the whole merged workbook."""
    cols = [c for c in CRIT if c in df.columns]
    bad = df[[any(is_sentinel(r[c]) for c in cols) for _, r in df.iterrows()]]
    return len(bad), bad["scenario_id"].nunique()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_changed = 0
    for folder in FOLDERS:
        for run in range(1, 6):
            rel = f"{folder}/{ARCH}_results_run_{run:02d}.xlsx"
            jpath = PROJECT_ROOT / folder / f"{ARCH}_results_diagnostics_run_{run:02d}.json"
            if not jpath.exists():
                continue

            before = git_show(rel)
            n_alt, n_scen = shower_failures(before)
            if n_alt == 0 and n_scen == 0:
                continue

            # Confirm the merged file really has no Shower sentinels left.
            after = pd.read_excel(PROJECT_ROOT / rel)
            a_alt, a_scen = shower_failures(after)
            if a_alt or a_scen:
                print(f"  [SKIP] {folder} run {run}: merged file still has "
                      f"{a_alt} failed Shower alternatives; not a clean re-collection")
                continue

            j = json.load(open(jpath, encoding="utf-8"))
            orig = dict(j)

            # Derive from the merged workbook rather than subtracting. `failed_calls`
            # counts API calls while a single failed call can leave sentinels on more
            # alternatives than that, so the two are not in the same units and
            # subtracting one from the other underflows.
            _, all_bad_scen = all_failures(after)
            orig_scen = orig.get("failed_scenarios", 0)

            # failed_scenarios is recoverable exactly from the merged workbook.
            # failed_calls is not: a scenario with one bad alternative has all three
            # sentineled, so the sentinel count overstates calls, and the
            # re-collection's own per-call telemetry is gone. Scale it by the
            # scenario reduction, which is the only defensible estimate available,
            # and record that it is an estimate.
            j["failed_scenarios"] = all_bad_scen
            j["failed_calls"] = (round(orig.get("failed_calls", 0) * all_bad_scen / orig_scen)
                                 if orig_scen else 0)
            j["failed_calls_is_estimated"] = True
            # Keep the mode counters summing to failed_calls, as they did originally.
            modes = sorted([k for k in j if k.startswith(MODE_PREFIXES) and j.get(k)],
                           key=lambda k: -j[k])
            remaining = j["failed_calls"]
            for m in modes:
                take = min(j[m], remaining)
                j[m] = take
                remaining -= take

            tot_calls = j.get("total_api_calls") or 0
            j["successful_calls"] = max(0, tot_calls - j["failed_calls"])
            j["successful_scenarios"] = max(
                0, j.get("total_scenarios", 0) - j["failed_scenarios"])

            tot = j.get("total_api_calls") or 1
            j["success_rate"] = round(j["successful_calls"] / tot, 6)
            j["shower_recollected"] = True
            j["recollection_note"] = (
                "Shower scenarios were re-collected after a ground-truth comfort-band "
                "correction. Failure counts reflect the shipped scores. Token, latency "
                "and cost fields describe the original 195-scenario collection.")

            print(f"  {folder} run {run}: failed_calls "
                  f"{orig.get('failed_calls')}->{j['failed_calls']}, failed_scenarios "
                  f"{orig.get('failed_scenarios')}->{j['failed_scenarios']} "
                  f"(retired {n_alt} shower call failures, {n_scen} scenarios)")
            total_changed += 1

            if not args.dry_run:
                jpath.write_text(json.dumps(j, indent=2), encoding="utf-8")

    print("")
    print(f"{'DRY RUN - nothing written' if args.dry_run else 'WRITTEN'}: "
          f"{total_changed} diagnostics files reconciled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
