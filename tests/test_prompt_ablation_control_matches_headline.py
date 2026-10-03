"""The prompt-ablation control cell must equal the headline per-run metrics.

The control cell is main-suite runs 1..R rescored by run_prompt_ablation_experiments
(`main_suite_control_rows`, which reads `load_reference`). The headline is
the aggregate per-run metrics CSV (evaluate_architecture_metrics
under the S4 failure rule). Both score the same run files, so every per-run
Kendall tau / Top-1 / Top-2 must agree. They disagreed for 16 Shower scenarios
when load_reference matched ground truth on question + location alone.

Offline: no network, no API calls. Skips when the output folders or the
per-run CSV are absent.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

import arch_patch_harness as H  # noqa: F401  (dummy API key / no-network guard)

REPO = H.REPO
SOURCE_ROOT = REPO / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from llm_mcda.common.paths import local_manuscript_input_path

CSV = local_manuscript_input_path("paper", "per_run_metrics", "per_run_metrics_all.csv")
STEM = {"AD": "Direct_LLM_Scoring", "AE": "Example-Guided_LLM_Scoring"}
TOL = 6e-5  # the CSV is rounded to 4 decimals


def _load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m


PA = _load(REPO / "scripts" / "experiments" / "run_prompt_ablation_experiments.py",
           "ctrl_pa")


@pytest.fixture(scope="module")
def reference():
    return PA.load_reference()


@pytest.fixture(scope="module")
def headline():
    if not CSV.exists():
        pytest.skip("per_run_metrics_all.csv not present")
    d = pd.read_csv(CSV)
    return d[d["decision_type"] == "Overall"]


def test_reference_covers_every_test_scenario(reference):
    assert len(reference) == 195
    assert all(len(r["rank_by_alt"]) == 3 for r in reference.values())


@pytest.mark.parametrize("arch", ["AD", "AE"])
@pytest.mark.parametrize("model", list(PA.MODEL_SPECS))
def test_control_per_run_equals_headline(model, arch, reference, headline):
    runs = 5
    try:
        rows = PA.main_suite_control_rows(model, arch, runs, reference)
    except FileNotFoundError:
        pytest.skip(f"main-suite runs for {model}/{arch} not present")
    per_run = rows.assign(kendall_tau=rows["kendall_tau"].fillna(PA.FAILED_SCENARIO_TAU)) \
        .groupby("run")[["kendall_tau", "top1", "top2"]].mean()
    h = headline[(headline["model"] == model) & (headline["architecture"] == STEM[arch])] \
        .set_index("run")
    for run, r in per_run.iterrows():
        assert abs(r["kendall_tau"] - h.loc[run, "kendall_tau"]) < TOL, (model, arch, run, "tau")
        assert abs(r["top1"] - h.loc[run, "top1_accuracy"]) < TOL, (model, arch, run, "top1")
        assert abs(r["top2"] - h.loc[run, "top2_accuracy"]) < TOL, (model, arch, run, "top2")
