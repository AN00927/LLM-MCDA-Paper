#!/usr/bin/env python3
"""
PositionBiasControl.py

Additive control arm for alternative-order (position) bias. This does NOT
replace or modify the shipped five-run benchmark. It scores a stratified
subsample of the Test corpus once more with the order of the three
alternatives reversed, then compares that arm against the five shipped runs
restricted to the same scenarios.

Design
------
Manipulation:  scenario['alternative_1'], ['alternative_2'], ['alternative_3']
               are reversed before the scenario record reaches the
               architecture. That flips (a) the order of the "Other
               alternatives available for this decision" list in the user
               prompt, (b) the order in which the three independent scoring
               calls are issued, and (c) the row order, which is what the
               stable mergesort in apply_mavt_ranking uses to break ties.
               Nothing else in the prompt changes. The scenario context
               fields are NOT reordered -- this arm isolates the ordering of
               the choice set, not of the context.

Scope:        A_D (Direct) and A_E (Example-Guided) only. A_H has no
              exposure: its LLM call extracts physical parameters and never
              sees the alternatives, which the calculator enumerates itself.

Reference:    The shipped arm is the existing five runs subset to the same
              scenarios. That gives a five-value reference distribution per
              metric at zero additional API cost, so the reversed arm is
              judged against real run-to-run variation rather than against a
              single point estimate.

Cost:         n_scenarios x 3 alternatives x 2 architectures API calls.
              At the default n=60 that is 360 calls.

Usage
-----
    python "Miscellaneous Scripts/PositionBiasControl.py" run --model qwen
    python "Miscellaneous Scripts/PositionBiasControl.py" analyze --model qwen

    # weakest and strongest, if budget allows two:
    python "Miscellaneous Scripts/PositionBiasControl.py" run --model gemini

`run` is resume-aware per architecture: a complete output file is skipped.
`analyze` makes no API calls and can be re-run freely.
"""

import argparse
import json
import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import model_config
from model_config import MODEL_SPECS, get_output_folder
from sentinel_utils import (
    _atomic_write_json,
    _atomic_write_xlsx,
    _is_complete_run_file,
    read_table_clean,
    SENTINEL_VALUE,
    SENTINEL_FLOAT,
)

TEST_SCENARIOS = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"
ALT_COLS = ["alternative_1", "alternative_2", "alternative_3"]
CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]
DECISION_TYPES = ["HVAC", "Appliance", "Shower"]

DEFAULT_N = 60
DEFAULT_SEED = 20260803

ARCHITECTURES = {
    "Direct_LLM_Scoring": PROJECT_ROOT / "Architectures" / "Direct_LLM_Scoring.py",
    "Example-Guided_LLM_Scoring": PROJECT_ROOT / "Architectures" / "Example-Guided_LLM_Scoring.py",
}

RESULT_COLUMNS = [
    "scenario_id", "decision_type", "question", "location", "outdoor_temp",
    "appliance_age", "flow_rate", "alternative",
    "energy_cost", "environmental", "comfort", "practicality",
    "rank", "weighted_score",
]


# --------------------------------------------------------------------------
# sampling
# --------------------------------------------------------------------------

def load_scenarios():
    """Load the Test corpus with the same scenario_id convention the
    architectures use (row index + 1)."""
    df = read_table_clean(TEST_SCENARIOS, keep_str_cols=ALT_COLS)
    scenarios = []
    for i, row in df.iterrows():
        record = row.to_dict()
        record["scenario_id"] = i + 1
        scenarios.append(record)
    return scenarios


def allocate_by_largest_remainder(counts_by_type, n_total):
    """Proportional allocation with largest-remainder rounding, so the strata
    sizes track the corpus composition and sum exactly to n_total."""
    total = sum(counts_by_type.values())
    exact = {k: n_total * v / total for k, v in counts_by_type.items()}
    alloc = {k: int(np.floor(v)) for k, v in exact.items()}
    remaining = n_total - sum(alloc.values())
    order = sorted(exact, key=lambda k: (-(exact[k] - alloc[k]), k))
    for k in order[:remaining]:
        alloc[k] += 1
    for k in alloc:
        alloc[k] = min(alloc[k], counts_by_type[k])
    return alloc


def stratified_sample(scenarios, n_total, seed):
    """Deterministic stratified sample by decision_type."""
    by_type = {}
    for sc in scenarios:
        by_type.setdefault(sc.get("decision_type", "UNKNOWN"), []).append(sc)

    counts = {k: len(v) for k, v in by_type.items()}
    alloc = allocate_by_largest_remainder(counts, n_total)

    rng = np.random.default_rng(seed)
    sampled = []
    for dtype in sorted(by_type):
        pool = sorted(by_type[dtype], key=lambda s: s["scenario_id"])
        k = alloc.get(dtype, 0)
        idx = rng.choice(len(pool), size=k, replace=False)
        sampled.extend(pool[i] for i in sorted(idx))

    sampled.sort(key=lambda s: s["scenario_id"])
    return sampled, alloc


def reverse_alternatives(scenario):
    """Return a copy with alternative_1/2/3 reversed. Blank slots are left in
    place so a scenario with fewer than three alternatives is not corrupted."""
    out = dict(scenario)
    present = [scenario.get(c) for c in ALT_COLS]
    filled = [a for a in present if a not in (None, "", "N/A") and str(a).strip() != ""]
    reversed_filled = list(reversed(filled))
    it = iter(reversed_filled)
    for col, original in zip(ALT_COLS, present):
        if original in (None, "", "N/A") or str(original).strip() == "":
            out[col] = original
        else:
            out[col] = next(it)
    return out


# --------------------------------------------------------------------------
# architecture loading
# --------------------------------------------------------------------------

def load_architecture_module(arch_name, model_key):
    """Load an architecture module from its path (the names contain hyphens,
    so a plain import will not work) and repoint it at the requested model.

    API_CONFIG is read inside query_openrouter at call time, so patching it
    after import is sufficient and leaves model_config untouched.
    """
    path = ARCHITECTURES[arch_name]
    spec = spec_from_file_location(f"posbias_{arch_name.replace('-', '_')}", path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.API_CONFIG["model"] = model_config.get_model_id(model_key)
    mod.API_CONFIG["reasoning"] = model_config.get_reasoning_payload(model_key)
    print(f"  [INFO] {arch_name} pointed at {mod.API_CONFIG['model']}")
    return mod


def normalize_result(result, scenario):
    """Flatten one run_scenario() return into result rows.

    The two architectures return slightly different shapes: A_D puts criterion
    scores directly on each alternative entry and returns 'ranking_results';
    A_E nests them under 'scores' and returns 'ranking_result'. Failure
    semantics are mirrored from A_D exactly -- if any alternative in the
    scenario failed, every row for that scenario is written as the sentinel,
    which is what filter_failed_scenarios expects downstream.
    """
    alt_entries = result.get("alternatives_scores", [])
    ranking = result.get("ranking_results") or result.get("ranking_result") or {}
    ranks = ranking.get("ranks", [])
    weighted = ranking.get("weighted_scores", [])

    diagnostics = result.get("diagnostics", {})
    scenario_failed = bool(diagnostics.get("scenario_failed", False))

    rows = []
    for idx, entry in enumerate(alt_entries):
        payload = entry.get("scores") if isinstance(entry.get("scores"), dict) else entry
        values = {c: payload.get(c) for c in CRITERIA}

        entry_failed = bool(entry.get("failed", False))
        if any(v is None for v in values.values()):
            entry_failed = True
        if any(str(v) == str(SENTINEL_VALUE) for v in values.values()):
            entry_failed = True

        if scenario_failed or entry_failed:
            values = {c: SENTINEL_VALUE for c in CRITERIA}
            rank = SENTINEL_VALUE
            weighted_score = SENTINEL_FLOAT
        else:
            rank = ranks[idx] if idx < len(ranks) else SENTINEL_VALUE
            weighted_score = weighted[idx] if idx < len(weighted) else SENTINEL_FLOAT

        rows.append({
            "scenario_id": scenario.get("scenario_id"),
            "decision_type": scenario.get("decision_type", "N/A"),
            "question": scenario.get("question", "N/A"),
            "location": scenario.get("location", "N/A"),
            "outdoor_temp": scenario.get("outdoor_temp", "N/A"),
            "appliance_age": scenario.get("appliance_age", ""),
            "flow_rate": scenario.get("flow_rate", ""),
            "alternative": entry.get("alternative", ""),
            **values,
            "rank": rank,
            "weighted_score": weighted_score,
        })

    # A scenario that produced no rows at all is a hard failure; emit sentinel
    # rows so it is counted as failed rather than silently vanishing.
    if not rows:
        for col in ALT_COLS:
            alt = scenario.get(col)
            if alt in (None, "", "N/A"):
                continue
            rows.append({
                "scenario_id": scenario.get("scenario_id"),
                "decision_type": scenario.get("decision_type", "N/A"),
                "question": scenario.get("question", "N/A"),
                "location": scenario.get("location", "N/A"),
                "outdoor_temp": scenario.get("outdoor_temp", "N/A"),
                "appliance_age": scenario.get("appliance_age", ""),
                "flow_rate": scenario.get("flow_rate", ""),
                "alternative": alt,
                **{c: SENTINEL_VALUE for c in CRITERIA},
                "rank": SENTINEL_VALUE,
                "weighted_score": SENTINEL_FLOAT,
            })
    return rows


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def output_dir_for(model_key):
    return PROJECT_ROOT / get_output_folder(model_key) / "position_bias"


def write_sample_manifest(sampled, alloc, model_key, n_total, seed):
    out_dir = output_dir_for(model_key)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for sc in sampled:
        rev = reverse_alternatives(sc)
        rows.append({
            "scenario_id": sc["scenario_id"],
            "decision_type": sc.get("decision_type", ""),
            "question": sc.get("question", ""),
            "location": sc.get("location", ""),
            "shipped_order": " | ".join(str(sc.get(c, "")) for c in ALT_COLS),
            "reversed_order": " | ".join(str(rev.get(c, "")) for c in ALT_COLS),
        })
    manifest_path = out_dir / "position_bias_sample.xlsx"
    _atomic_write_xlsx(pd.DataFrame(rows), manifest_path)

    spec_path = out_dir / "position_bias_sample_spec.json"
    _atomic_write_json({
        "model_key": model_key,
        "n_requested": n_total,
        "n_sampled": len(sampled),
        "seed": seed,
        "allocation_by_decision_type": alloc,
        "scenario_ids": [int(s["scenario_id"]) for s in sampled],
        "manipulation": "alternative_1/2/3 reversed; scenario context fields unchanged",
        "architectures": sorted(ARCHITECTURES),
    }, spec_path)

    print(f"  [OK] Wrote {manifest_path.name} and {spec_path.name}")
    return manifest_path


def run_reversed_arm(model_key, n_total, seed):
    scenarios = load_scenarios()
    sampled, alloc = stratified_sample(scenarios, n_total, seed)

    print(f"Sampled {len(sampled)} scenarios (seed={seed})")
    for dtype in sorted(alloc):
        print(f"  {dtype}: {alloc[dtype]}")

    out_dir = output_dir_for(model_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_sample_manifest(sampled, alloc, model_key, n_total, seed)

    for arch_name in ARCHITECTURES:
        out_path = out_dir / f"{arch_name}_reversed_run_01.xlsx"
        if _is_complete_run_file(out_path):
            print(f"[SKIP] {arch_name}: {out_path.name} already complete")
            continue

        print(f"\n=== {arch_name}: reversed arm, {len(sampled)} scenarios ===")

        # Per-scenario checkpoint. A long arm (195 scenarios x 3 alternatives)
        # should survive a dropped connection, so completed scenarios are
        # appended to a jsonl and skipped on restart.
        ckpt_path = out_dir / f"{arch_name}_reversed_partial.jsonl"
        rows = []
        done_ids = set()
        if ckpt_path.exists():
            with open(ckpt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    rows.append(row)
                    done_ids.add(row["scenario_id"])
            print(f"  [RESUME] {len(done_ids)} scenarios already checkpointed")

        todo = [s for s in sampled if s["scenario_id"] not in done_ids]
        if not todo:
            print("  [INFO] all scenarios checkpointed; writing final file")
        else:
            mod = load_architecture_module(arch_name, model_key)

        n_failed_scenarios = 0
        for i, scenario in enumerate(todo, 1):
            reversed_scenario = reverse_alternatives(scenario)
            print(f"  [{i}/{len(todo)}] sid={scenario['scenario_id']} "
                  f"{scenario.get('decision_type', '')}", flush=True)
            try:
                result = mod.run_scenario(reversed_scenario)
            except Exception as e:
                print(f"    [ERROR] scenario crashed, marked failed: {e}")
                result = {"alternatives_scores": [], "diagnostics": {"scenario_failed": True}}
                n_failed_scenarios += 1
            new_rows = normalize_result(result, reversed_scenario)
            rows.extend(new_rows)
            with open(ckpt_path, "a", encoding="utf-8") as f:
                for row in new_rows:
                    f.write(json.dumps(row) + "\n")

        df = pd.DataFrame(rows).reindex(columns=RESULT_COLUMNS)
        df = df.sort_values("scenario_id", kind="mergesort")
        _atomic_write_xlsx(df, out_path)
        print(f"  [OK] Wrote {out_path.name} ({len(df)} rows, "
              f"{n_failed_scenarios} crashed scenarios)")


# --------------------------------------------------------------------------
# analyze
# --------------------------------------------------------------------------

def _load_metrics_helpers():
    path = PROJECT_ROOT / "paper_pipeline" / "calculate_per_run_metrics.py"
    spec = spec_from_file_location("posbias_metrics", path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _metrics_for(mod, gt_lookup, gt_id_lookup, arch_df, arch_name, sampled_ids):
    """Restrict to the sampled scenarios, then compute the paper's own
    ranking metrics with the paper's own matching and failure filtering."""
    sub = arch_df[arch_df["scenario_id"].isin(sampled_ids)]
    if sub.empty:
        return None, None

    merged, _ = mod.match_scenarios(gt_lookup, gt_id_lookup, sub, arch_name)
    if merged.empty:
        return None, None

    clean, n_failed, n_total = mod.filter_failed_scenarios(merged)
    if clean.empty:
        return None, None

    overall = mod.compute_ranking_metrics_local(clean)
    overall["n_failed_scenarios"] = n_failed
    overall["n_total_scenarios"] = n_total

    by_type = {}
    for dt in DECISION_TYPES:
        dt_clean = clean[clean["decision_type"] == dt]
        if dt_clean.empty:
            continue
        by_type[dt] = mod.compute_ranking_metrics_local(dt_clean)

    return overall, by_type


def _top1_by_scenario(mod, gt_lookup, gt_id_lookup, arch_df, arch_name, sampled_ids):
    """Per-scenario top-1 correctness, keyed by scenario_id, for paired tests."""
    sub = arch_df[arch_df["scenario_id"].isin(sampled_ids)]
    merged, _ = mod.match_scenarios(gt_lookup, gt_id_lookup, sub, arch_name)
    if merged.empty:
        return {}
    clean, _, _ = mod.filter_failed_scenarios(merged)

    correct = {}
    for sid in clean["arch_scenario_id"].unique():
        sc = clean[clean["arch_scenario_id"] == sid]
        if len(sc) < 2:
            continue
        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values
        if np.isnan(gt_r).any() or np.isnan(ar_r).any():
            continue
        gt_top1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        ar_top1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        correct[sid] = int(gt_top1 == ar_top1)
    return correct


def _decision_type_by_scenario(mod, gt_lookup, gt_id_lookup, arch_df, arch_name, sampled_ids):
    """Map scenario_id to decision type, so the paired tests can be run within
    type. The pooled test hides opposite-signed per-type effects, which is
    exactly the failure mode an order manipulation produces when the shipped
    alternative order relates differently to the correct answer in each type.
    """
    sub = arch_df[arch_df["scenario_id"].isin(sampled_ids)]
    merged, _ = mod.match_scenarios(gt_lookup, gt_id_lookup, sub, arch_name)
    if merged.empty:
        return {}
    clean, _, _ = mod.filter_failed_scenarios(merged)
    return (
        clean.groupby("arch_scenario_id")["decision_type"].first().to_dict()
    )


def _top1_choice_by_scenario(mod, gt_lookup, gt_id_lookup, arch_df, arch_name, sampled_ids):
    """Which alternative the architecture ranked first, keyed by scenario_id.

    This is the instrument that matters when accuracy is near chance: a model
    that ranks by content picks the same alternative whichever order it is
    shown, even when that pick is wrong. Agreement here is independent of how
    accurate the architecture is.
    """
    sub = arch_df[arch_df["scenario_id"].isin(sampled_ids)]
    merged, _ = mod.match_scenarios(gt_lookup, gt_id_lookup, sub, arch_name)
    if merged.empty:
        return {}
    clean, _, _ = mod.filter_failed_scenarios(merged)

    choice = {}
    for sid in clean["arch_scenario_id"].unique():
        sc = clean[clean["arch_scenario_id"] == sid]
        if len(sc) < 2:
            continue
        ar_r = sc["arch_rank"].astype(float).values
        if np.isnan(ar_r).any():
            continue
        choice[sid] = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
    return choice


def _choice_agreement(a, b):
    """Fraction of shared scenarios where two arms picked the same top-1."""
    common = sorted(set(a) & set(b))
    if not common:
        return float("nan"), 0
    agree = sum(1 for k in common if a[k] == b[k])
    return agree / len(common), len(common)


def _mcnemar_exact(shipped, reversed_):
    """Exact McNemar (binomial) on paired top-1 correctness. Returns
    (n_pairs, b, c, p_value), where b = shipped right / reversed wrong."""
    common = sorted(set(shipped) & set(reversed_))
    b = sum(1 for k in common if shipped[k] == 1 and reversed_[k] == 0)
    c = sum(1 for k in common if shipped[k] == 0 and reversed_[k] == 1)
    if b + c == 0:
        return len(common), b, c, 1.0
    p = stats.binomtest(b, b + c, 0.5, alternative="two-sided").pvalue
    return len(common), b, c, p


def analyze(model_key):
    mod = _load_metrics_helpers()
    out_dir = output_dir_for(model_key)

    spec_path = out_dir / "position_bias_sample_spec.json"
    if not spec_path.exists():
        print(f"[ERROR] {spec_path} not found. Run the 'run' subcommand first.")
        return
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    sampled_ids = set(spec["scenario_ids"])
    print(f"Sample: {len(sampled_ids)} scenarios, seed={spec['seed']}, "
          f"model={spec['model_key']}")

    config = mod._build_config(model_key)
    gt_by_type = mod.load_ground_truth(config)
    gt_lookup = mod.build_gt_lookup(gt_by_type)
    gt_id_lookup = mod.build_gt_id_lookup(gt_by_type)

    shipped_dir = PROJECT_ROOT / get_output_folder(model_key)
    metric_keys = ["kendall_tau", "top1_accuracy", "top2_accuracy", "spearman_rho"]

    rows = []
    paired_rows = []

    for arch_name in ARCHITECTURES:
        reversed_path = out_dir / f"{arch_name}_reversed_run_01.xlsx"
        if not reversed_path.exists():
            print(f"[SKIP] {arch_name}: {reversed_path.name} not found")
            continue

        rev_df = mod.load_architecture(reversed_path, arch_name)
        rev_overall, rev_by_type = _metrics_for(
            mod, gt_lookup, gt_id_lookup, rev_df, arch_name, sampled_ids
        )
        if rev_overall is None:
            print(f"[WARN] {arch_name}: reversed arm produced no evaluable scenarios")
            continue

        shipped_files = sorted(shipped_dir.glob(f"{arch_name}_results_run_*.xlsx"))
        shipped_files = [f for f in shipped_files if _is_complete_run_file(f)]
        if not shipped_files:
            print(f"[WARN] {arch_name}: no shipped run files in {shipped_dir}")
            continue

        shipped_overall = []
        shipped_by_type = {dt: [] for dt in DECISION_TYPES}
        for f in shipped_files:
            sh_df = mod.load_architecture(f, arch_name)
            ov, bt = _metrics_for(
                mod, gt_lookup, gt_id_lookup, sh_df, arch_name, sampled_ids
            )
            if ov is None:
                continue
            shipped_overall.append(ov)
            for dt, m in (bt or {}).items():
                shipped_by_type[dt].append(m)

        def emit(scope, rev_metrics, shipped_list):
            for key in metric_keys:
                vals = [m[key] for m in shipped_list
                        if m.get(key) is not None and not np.isnan(m[key])]
                if not vals or rev_metrics.get(key) is None:
                    continue
                mean = float(np.mean(vals))
                sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else float("nan")
                delta = float(rev_metrics[key]) - mean
                z = delta / sd if sd and not np.isnan(sd) and sd > 0 else float("nan")
                rows.append({
                    "architecture": arch_name,
                    "scope": scope,
                    "metric": key,
                    "reversed": round(float(rev_metrics[key]), 4),
                    "shipped_mean": round(mean, 4),
                    "shipped_sd": round(sd, 4) if not np.isnan(sd) else np.nan,
                    "shipped_min": round(float(np.min(vals)), 4),
                    "shipped_max": round(float(np.max(vals)), 4),
                    "delta": round(delta, 4),
                    "delta_in_sd": round(z, 2) if not np.isnan(z) else np.nan,
                    "within_shipped_range": bool(
                        np.min(vals) <= float(rev_metrics[key]) <= np.max(vals)
                    ),
                    "n_shipped_runs": len(vals),
                    "model": model_key,
                })

        emit("Overall", rev_overall, shipped_overall)
        for dt in DECISION_TYPES:
            if rev_by_type and dt in rev_by_type and shipped_by_type[dt]:
                emit(dt, rev_by_type[dt], shipped_by_type[dt])

        # Paired per-scenario top-1, reversed arm against each shipped run
        rev_top1 = _top1_by_scenario(
            mod, gt_lookup, gt_id_lookup, rev_df, arch_name, sampled_ids
        )
        rev_choice = _top1_choice_by_scenario(
            mod, gt_lookup, gt_id_lookup, rev_df, arch_name, sampled_ids
        )
        dtype_map = _decision_type_by_scenario(
            mod, gt_lookup, gt_id_lookup, rev_df, arch_name, sampled_ids
        )

        shipped_choices = {}
        for f in shipped_files:
            run_id = f.stem.split("_run_")[-1]
            sh_df = mod.load_architecture(f, arch_name)
            sh_top1 = _top1_by_scenario(
                mod, gt_lookup, gt_id_lookup, sh_df, arch_name, sampled_ids
            )
            shipped_choices[run_id] = _top1_choice_by_scenario(
                mod, gt_lookup, gt_id_lookup, sh_df, arch_name, sampled_ids
            )
            n_pairs, b, c, p = _mcnemar_exact(sh_top1, rev_top1)
            agree, n_common = _choice_agreement(shipped_choices[run_id], rev_choice)

            # Same test within each decision type.
            for dt in DECISION_TYPES:
                dt_ids = {k for k, v in dtype_map.items() if v == dt}
                sh_dt = {k: v for k, v in sh_top1.items() if k in dt_ids}
                rv_dt = {k: v for k, v in rev_top1.items() if k in dt_ids}
                if not sh_dt or not rv_dt:
                    continue
                n_dt, b_dt, c_dt, p_dt = _mcnemar_exact(sh_dt, rv_dt)
                agree_dt, n_agree_dt = _choice_agreement(
                    {k: v for k, v in shipped_choices[run_id].items() if k in dt_ids},
                    {k: v for k, v in rev_choice.items() if k in dt_ids},
                )
                paired_rows.append({
                    "architecture": arch_name,
                    "comparison": f"reversed_vs_shipped[{dt}]",
                    "shipped_run": run_id,
                    "n_paired_scenarios": n_dt,
                    "shipped_right_reversed_wrong": b_dt,
                    "shipped_wrong_reversed_right": c_dt,
                    "mcnemar_exact_p": round(p_dt, 4),
                    "top1_choice_agreement": round(agree_dt, 4) if not np.isnan(agree_dt) else np.nan,
                    "n_choice_compared": n_agree_dt,
                    "model": model_key,
                })

            paired_rows.append({
                "architecture": arch_name,
                "comparison": "reversed_vs_shipped",
                "shipped_run": run_id,
                "n_paired_scenarios": n_pairs,
                "shipped_right_reversed_wrong": b,
                "shipped_wrong_reversed_right": c,
                "mcnemar_exact_p": round(p, 4),
                "top1_choice_agreement": round(agree, 4) if not np.isnan(agree) else np.nan,
                "n_choice_compared": n_common,
                "model": model_key,
            })

        # Shipped-vs-shipped agreement is the noise ceiling: two runs in the
        # SAME order still disagree this often from sampling temperature
        # alone. The reversed arm only implicates position bias if it agrees
        # with shipped runs less than shipped runs agree with each other.
        run_ids = sorted(shipped_choices)
        for i in range(len(run_ids)):
            for j in range(i + 1, len(run_ids)):
                agree, n_common = _choice_agreement(
                    shipped_choices[run_ids[i]], shipped_choices[run_ids[j]]
                )
                paired_rows.append({
                    "architecture": arch_name,
                    "comparison": "shipped_vs_shipped",
                    "shipped_run": f"{run_ids[i]}v{run_ids[j]}",
                    "n_paired_scenarios": np.nan,
                    "shipped_right_reversed_wrong": np.nan,
                    "shipped_wrong_reversed_right": np.nan,
                    "mcnemar_exact_p": np.nan,
                    "top1_choice_agreement": round(agree, 4) if not np.isnan(agree) else np.nan,
                    "n_choice_compared": n_common,
                    "model": model_key,
                })

    if not rows:
        print("[ERROR] No comparisons produced.")
        return

    summary = pd.DataFrame(rows)
    summary_path = out_dir / f"position_bias_summary_{model_key}.xlsx"
    _atomic_write_xlsx(summary, summary_path)
    summary.to_csv(out_dir / f"position_bias_summary_{model_key}.csv", index=False)
    print(f"\n[OK] Wrote {summary_path.name}")

    if paired_rows:
        paired = pd.DataFrame(paired_rows)
        paired_path = out_dir / f"position_bias_paired_top1_{model_key}.xlsx"
        _atomic_write_xlsx(paired, paired_path)
        paired.to_csv(out_dir / f"position_bias_paired_top1_{model_key}.csv", index=False)
        print(f"[OK] Wrote {paired_path.name}")

    print("\n" + "=" * 78)
    print("REVERSED ARM vs SHIPPED RUNS (same scenarios)")
    print("=" * 78)
    show = summary[summary["scope"] == "Overall"]
    for _, r in show.iterrows():
        flag = "within" if r["within_shipped_range"] else "OUTSIDE"
        print(f"{r['architecture']:<32} {r['metric']:<16} "
              f"rev={r['reversed']:<8} shipped={r['shipped_mean']:.4f} "
              f"(sd={r['shipped_sd']}) delta={r['delta']:+.4f} "
              f"[{flag} shipped range]")

    if paired_rows:
        pdf = pd.DataFrame(paired_rows)
        print("\n" + "=" * 78)
        print("TOP-1 CHOICE AGREEMENT (order-independent; works at chance accuracy)")
        print("=" * 78)
        for arch_name in sorted(pdf["architecture"].unique()):
            a = pdf[pdf["architecture"] == arch_name]
            rev = a[a["comparison"] == "reversed_vs_shipped"]["top1_choice_agreement"]
            sxs = a[a["comparison"] == "shipped_vs_shipped"]["top1_choice_agreement"]
            if rev.empty or sxs.empty:
                continue
            gap = rev.mean() - sxs.mean()
            verdict = ("no order effect beyond run-to-run noise"
                       if gap >= -sxs.std(ddof=1) else "REVERSED ARM AGREES LESS")
            print(f"{arch_name}")
            print(f"  reversed vs shipped : {rev.mean():.4f} "
                  f"(range {rev.min():.4f}-{rev.max():.4f}, n={len(rev)})")
            print(f"  shipped vs shipped  : {sxs.mean():.4f} "
                  f"(range {sxs.min():.4f}-{sxs.max():.4f}, n={len(sxs)})")
            print(f"  gap                 : {gap:+.4f}  -> {verdict}")

    outside = summary[~summary["within_shipped_range"]]
    print("\n" + "-" * 78)
    if outside.empty:
        print("Every reversed-arm metric falls inside the shipped run-to-run range.")
        print("This supports a null position-bias claim.")
    else:
        print(f"{len(outside)} metric/scope cell(s) fall OUTSIDE the shipped range:")
        for _, r in outside.iterrows():
            print(f"  {r['architecture']} / {r['scope']} / {r['metric']}: "
                  f"rev={r['reversed']} vs shipped "
                  f"[{r['shipped_min']}, {r['shipped_max']}]")
        print("Report these rather than claiming a null.")


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Position-bias control arm")
    parser.add_argument("command", choices=["run", "analyze"])
    parser.add_argument("--model", choices=list(MODEL_SPECS.keys()),
                        default="qwen",
                        help="Default qwen: position bias hits weaker scorers "
                             "harder, so a null there is stronger evidence.")
    parser.add_argument("--n", type=int, default=DEFAULT_N,
                        help=f"Scenarios to sample (default {DEFAULT_N})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    if args.command == "run":
        run_reversed_arm(args.model, args.n, args.seed)
    else:
        analyze(args.model)


if __name__ == "__main__":
    main()
