"""Mocked/offline tests for the prompt-ablation failure-as-wrong accuracy
rule added 2026-09-27 (mirrors the RAG ablation's rule -- see
run_rag_ablation_experiments.scenario_metrics and INSTALL_MIGRATE_REPORT.md
section 5): a failed or unscored scenario counts as WRONG for Top-1 and
Top-2, and the denominator is every scenario in the cell. kendall_tau is not
an accuracy metric and is unchanged (NaN for a failed scenario, averaged over
scored scenarios only).

Covers:
  - scenario_metrics(): a failed alternative (sentinel score) or no ground
    truth reference makes top1/top2 0.0 (never NaN) and failed True; kendall
    tau stays NaN in both cases.
  - summarize(): a cell with failures gets a LOWER top1_accuracy than the old
    scored-only rule would report, with the denominator equal to every
    scenario (n_scenarios), and n_failed_scenarios reported at both the
    per-run and per-cell level.
  - the significance script's load_matrix(): failed rows are kept (not
    dropped), so a per-scenario mean over runs correctly treats a failed run
    as a miss instead of shrinking the average to the scored subset.

No network, no paid calls (offline data manipulation only).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import arch_patch_harness as H  # noqa: F401  (forces the dummy API key / no-network guard)

REPO = H.REPO
EXP = REPO / "Miscellaneous Scripts" / "experiments"
VAL = REPO / "Miscellaneous Scripts" / "validation"


def _load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m


PA = _load(EXP / "run_prompt_ablation_experiments.py", "phase1_pa_accuracy")
SIG = _load(VAL / "test_prompt_ablation_significance.py", "phase1_pa_sig")

CRIT = ["energy_cost", "environmental", "comfort", "practicality"]


def alt(name, energy_cost, environmental, comfort, practicality):
    return {"alternative": name, "energy_cost": energy_cost, "environmental": environmental,
            "comfort": comfort, "practicality": practicality}


def sentinel_alt(name):
    return {"alternative": name, **{c: PA.SENTINEL_FLOAT for c in CRIT}}


def result_of(scored):
    ranking = PA.apply_mavt_ranking(scored)
    return {"scored": scored, "ranking": ranking}


REF = {
    "mavt_by_alt": {"A": 0.8, "B": 0.5, "C": 0.2},
    "rank_by_alt": {"A": 1, "B": 2, "C": 3},
}


# ---------------------------------------------------------------------------
# scenario_metrics
# ---------------------------------------------------------------------------

def test_all_scored_correct_top1_and_top2():
    scored = [alt("A", 0.9, 0.9, 0.9, 0.9), alt("B", 0.5, 0.5, 0.5, 0.5), alt("C", 0.1, 0.1, 0.1, 0.1)]
    m = PA.scenario_metrics(result_of(scored), REF)
    assert m["failed"] is False
    assert m["top1"] == 1.0 and m["top2"] == 1.0
    assert m["kendall_tau"] == pytest.approx(1.0)


def test_sentinel_alternative_counts_wrong_not_nan():
    """One alternative failed (sentinel): the whole scenario is WRONG (0.0),
    never NaN, and stays failed."""
    scored = [alt("A", 0.9, 0.9, 0.9, 0.9), sentinel_alt("B"), alt("C", 0.1, 0.1, 0.1, 0.1)]
    m = PA.scenario_metrics(result_of(scored), REF)
    assert m["failed"] is True
    assert m["top1"] == 0.0 and m["top2"] == 0.0  # not NaN
    assert m["kendall_tau"] == 0.0  # failure rule S4: chance level


def test_no_reference_counts_wrong_not_nan():
    scored = [alt("A", 0.9, 0.9, 0.9, 0.9), alt("B", 0.5, 0.5, 0.5, 0.5), alt("C", 0.1, 0.1, 0.1, 0.1)]
    m = PA.scenario_metrics(result_of(scored), None)
    assert m["failed"] is True
    assert m["top1"] == 0.0 and m["top2"] == 0.0
    assert m["kendall_tau"] == 0.0


def test_top2_credits_the_second_ranked_alternative():
    """Predicted order B, A, C (A is GT top1 but ranked 2nd): Top-1 misses,
    Top-2 hits because GT's top1 (A) is within the predicted top two."""
    scored = [alt("A", 0.6, 0.6, 0.6, 0.6), alt("B", 0.9, 0.9, 0.9, 0.9), alt("C", 0.1, 0.1, 0.1, 0.1)]
    m = PA.scenario_metrics(result_of(scored), REF)
    assert m["failed"] is False
    assert m["top1"] == 0.0
    assert m["top2"] == 1.0


def test_failed_record_counts_wrong_too():
    rec = PA._failed_record({"scenario_id": 7, "decision_type": "HVAC"}, "control",
                            PA.VARIANT_SPECS["control"], "AD", "gemini", 1,
                            "boom", "2026-09-27T00:00:00+00:00")
    assert rec["failed"] is True
    assert rec["top1"] == 0.0 and rec["top2"] == 0.0
    assert rec["kendall_tau"] == 0.0


# ---------------------------------------------------------------------------
# summarize(): denominator is every scenario in the cell
# ---------------------------------------------------------------------------

def _row(variant, arch, model, run, scenario_id, *, failed, top1, top2, tau,
         mean_sd=0.05, total_tokens=100):
    return {
        "variant": variant, "architecture": arch, "model": model, "run": run,
        "scenario_id": scenario_id, "decision_type": "HVAC",
        "kendall_tau": tau, "top1": top1, "top2": top2, "failed": failed,
        "mean_criterion_sd": mean_sd, "total_tokens": total_tokens,
    }


def test_cell_with_failures_scores_lower_top1_than_dropping_them():
    """4 scenarios, 1 run: 2 correct, 1 wrong-but-scored, 1 failed. The
    failure-as-wrong denominator is 4 (0.5), not 3 (0.667, the old
    scored-only rule)."""
    rows = [
        _row("control", "AD", "gemini", 1, 1, failed=False, top1=1.0, top2=1.0, tau=1.0),
        _row("control", "AD", "gemini", 1, 2, failed=False, top1=1.0, top2=1.0, tau=1.0),
        _row("control", "AD", "gemini", 1, 3, failed=False, top1=0.0, top2=0.0, tau=-1.0),
        _row("control", "AD", "gemini", 1, 4, failed=True, top1=0.0, top2=0.0, tau=np.nan),
    ]
    df = pd.DataFrame(rows)
    summary, per_run_df = PA.summarize(df)
    row = per_run_df.iloc[0]
    assert row["n_scenarios"] == 4
    assert row["n_failed_scenarios"] == 1
    assert row["top1_accuracy"] == pytest.approx(2 / 4)          # denominator ALL scenarios
    old_rule_scored_only = 2 / 3
    assert row["top1_accuracy"] < old_rule_scored_only
    assert row["top2_accuracy"] == pytest.approx(2 / 4)
    # failure rule S4: the failed scenario is at tau 0 and in the denominator
    assert row["kendall_tau"] == pytest.approx((1.0 + 1.0 - 1.0 + 0.0) / 4)
    final = summary.iloc[0]
    assert final["n_failed_scenarios"] == pytest.approx(1.0)
    assert final["top1_accuracy"] == pytest.approx(2 / 4)
    assert final["top2_accuracy"] == pytest.approx(2 / 4)


def test_all_failed_scenarios_give_zero_accuracy_not_nan():
    rows = [_row("control", "AD", "gemini", 1, i, failed=True, top1=0.0, top2=0.0, tau=np.nan)
            for i in range(1, 4)]
    df = pd.DataFrame(rows)
    summary, per_run_df = PA.summarize(df)
    row = per_run_df.iloc[0]
    assert row["n_scenarios"] == 3 and row["n_failed_scenarios"] == 3
    assert row["top1_accuracy"] == 0.0 and row["top2_accuracy"] == 0.0
    assert row["kendall_tau"] == 0.0  # every scenario at chance


def test_no_failures_matches_the_old_scored_only_denominator():
    rows = [
        _row("control", "AD", "gemini", 1, 1, failed=False, top1=1.0, top2=1.0, tau=1.0),
        _row("control", "AD", "gemini", 1, 2, failed=False, top1=0.0, top2=1.0, tau=0.0),
    ]
    df = pd.DataFrame(rows)
    _, per_run_df = PA.summarize(df)
    row = per_run_df.iloc[0]
    assert row["n_failed_scenarios"] == 0
    assert row["top1_accuracy"] == pytest.approx(0.5)
    assert row["top2_accuracy"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Significance script: load_matrix keeps failed rows in
# ---------------------------------------------------------------------------

def test_load_matrix_keeps_failed_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(SIG, "CELLS_DIR", tmp_path)
    rows = [
        _row("control", "AD", "gemini", r, 1, failed=False, top1=1.0, top2=1.0, tau=1.0)
        for r in range(1, 4)
    ] + [_row("control", "AD", "gemini", 4, 1, failed=True, top1=0.0, top2=0.0, tau=np.nan)]
    pd.DataFrame(rows).to_excel(tmp_path / "cell_control_AD_gemini_run_01.xlsx", index=False)
    df = SIG.load_matrix()
    assert len(df) == 4  # nothing dropped
    assert df["failed"].sum() == 1


def test_per_scenario_average_treats_a_failed_run_as_a_miss(tmp_path, monkeypatch):
    """Scenario 1, 4 runs for variant 'control': 3 hits, 1 failed run. Under
    the failure-as-wrong rule the run-averaged top1 for this scenario is
    3/4, not 3/3 (which is what dropping the failed row would give)."""
    monkeypatch.setattr(SIG, "CELLS_DIR", tmp_path)
    rows = [_row("control", "AD", "gemini", r, 1, failed=False, top1=1.0, top2=1.0, tau=1.0)
            for r in range(1, 4)]
    rows.append(_row("control", "AD", "gemini", 4, 1, failed=True, top1=0.0, top2=0.0, tau=np.nan))
    pd.DataFrame(rows).to_excel(tmp_path / "cell_control_AD_gemini_run_01.xlsx", index=False)
    df = SIG.load_matrix()
    per_scenario = (
        df.groupby(["variant", "architecture", "model", "scenario_id"], as_index=False)[SIG.METRIC_COLS]
        .mean()
    )
    row = per_scenario.iloc[0]
    assert row["top1"] == pytest.approx(3 / 4)
    assert row["top2"] == pytest.approx(3 / 4)
    assert row["kendall_tau"] == pytest.approx(3 / 4)  # failed run at tau 0 (S4)


def test_metric_cols_includes_top2():
    assert SIG.METRIC_COLS == ["kendall_tau", "top1", "top2"]
