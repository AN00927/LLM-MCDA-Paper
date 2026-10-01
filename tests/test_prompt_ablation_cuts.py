"""Offline tests for the prompt-ablation cuts of 2026-09-27 (author decision).

- The 0-10 response-scale variant is gone.
- Every cell runs 3 times by default.
- The control cell is not collected by default. Main-suite runs 1..R stand in
  for it, so the control messages must equal the installed architectures'
  byte for byte.
- A_E strata have two variants (control, cot_scaffold). The significance
  script tests them with one paired Wilcoxon inside the same Holm family as
  the Friedman tests.

No network, no paid calls.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import arch_patch_harness as H  # noqa: F401  (dummy API key / no-network guard)

REPO = H.REPO
EXP = REPO / "Miscellaneous Scripts" / "experiments"
VAL = REPO / "Miscellaneous Scripts" / "validation"


def _load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m


PA = _load(EXP / "run_prompt_ablation_experiments.py", "cuts_pa")
SIG = _load(VAL / "test_prompt_ablation_significance.py", "cuts_pa_sig")
CRIT = ["energy_cost", "environmental", "comfort", "practicality"]


def test_scale_variant_cut_and_defaults():
    assert list(PA.VARIANT_SPECS) == ["control", "no_anchors", "cot_scaffold"]
    assert PA.DEFAULT_VARIANTS == ["no_anchors", "cot_scaffold"]
    assert PA.PROMPT_ABLATION_RUNS == 3


def test_ad_control_messages_equal_main_suite():
    PA._assert_control_is_main_suite(["AD"])


@pytest.mark.skipif(not (REPO / "chroma_rag_db").exists(), reason="Chroma index not built")
def test_ae_control_messages_equal_main_suite():
    PA._assert_control_is_main_suite(["AE"])


def test_ad_equality_check_catches_a_changed_user_prompt(monkeypatch):
    original = PA.build_user_prompt
    monkeypatch.setattr(PA, "build_user_prompt",
                        lambda sc, alt: original(sc, alt).replace("(0-1) ", ""))
    with pytest.raises(RuntimeError, match="differ from the installed main suite"):
        PA._assert_control_is_main_suite(["AD"])


def _main_run_rows(sid, dtype, scores_by_alt, run):
    return [{"scenario_id": sid, "decision_type": dtype, "alternative": a,
             **dict(zip(CRIT, s)), "rank": 0, "weighted_score": 0.0,
             "collected_utc": f"2026-09-28T00:0{run}:00+00:00", "model_id": "m"}
            for a, s in scores_by_alt.items()]


def test_main_suite_control_rows_scored_like_a_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(PA, "main_suite_run_path",
                        lambda mk, arch, r: tmp_path / f"{arch}_{mk}_run_{r:02d}.xlsx")
    good = {"A": (0.9, 0.9, 0.9, 0.9), "B": (0.5, 0.5, 0.5, 0.5), "C": (0.1, 0.1, 0.1, 0.1)}
    failed = {"A": (1928,) * 4, "B": (0.5,) * 4, "C": (0.1,) * 4}
    for run in (1, 2, 3):
        rows = _main_run_rows(1, "HVAC", good, run) + _main_run_rows(2, "HVAC", failed, run)
        pd.DataFrame(rows).to_excel(tmp_path / f"AD_gemini_run_{run:02d}.xlsx", index=False)
    ref = {sid: {"mavt_by_alt": {"A": 0.9, "B": 0.5, "C": 0.1},
                 "rank_by_alt": {"A": 1, "B": 2, "C": 3}} for sid in (1, 2)}
    out = PA.main_suite_control_rows("gemini", "AD", 3, ref)
    assert len(out) == 6 and set(out["run"]) == {1, 2, 3}
    ok = out[out["scenario_id"] == 1]
    assert (ok["top1"] == 1.0).all() and np.allclose(ok["kendall_tau"], 1.0)
    bad = out[out["scenario_id"] == 2]
    assert bad["failed"].all() and (bad["top1"] == 0.0).all() and (bad["kendall_tau"] == 0.0).all()
    assert (out["variant"] == "control").all()


def test_main_suite_control_rows_missing_run_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(PA, "main_suite_run_path",
                        lambda mk, arch, r: tmp_path / f"missing_{r}.xlsx")
    with pytest.raises(FileNotFoundError, match="main-suite runs 1..3"):
        PA.main_suite_control_rows("gemini", "AD", 3, {})


def _cell_rows(variant, arch, runs, n, rng, shift):
    rows = []
    for run in range(1, runs + 1):
        for sid in range(1, n + 1):
            rows.append({"variant": variant, "architecture": arch, "model": "gemini",
                         "run": run, "scenario_id": sid, "decision_type": "HVAC",
                         "kendall_tau": float(np.clip(rng.normal(shift, 0.3), -1, 1)),
                         "top1": float(rng.random() < 0.5 + shift / 2),
                         "top2": float(rng.random() < 0.8), "failed": False})
    return rows


def test_significance_uses_main_suite_control_and_wilcoxon_for_two_variants(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    monkeypatch.setattr(SIG, "CELLS_DIR", tmp_path)
    monkeypatch.setattr(SIG, "OUTPUT_XLSX", tmp_path / "sig.xlsx")
    for variant, arch, shift in (("no_anchors", "AD", 0.1), ("cot_scaffold", "AD", 0.3),
                                 ("cot_scaffold", "AE", 0.5)):
        pd.DataFrame(_cell_rows(variant, arch, 3, 40, rng, shift)).to_excel(
            tmp_path / f"cell_{variant}_{arch}_gemini_run_01.xlsx", index=False)

    calls = []

    def fake_control(model, arch, runs, reference, scenario_ids=None):
        calls.append((model, arch, runs, len(scenario_ids)))
        return pd.DataFrame(_cell_rows("control", arch, runs, 40, rng, 0.0))

    monkeypatch.setattr(SIG, "_load_prompt_ablation_module",
                        lambda: SimpleNamespace(load_reference=lambda: {},
                                                rescore_cell_rows=lambda df, ref: df,
                                                main_suite_control_rows=fake_control))
    SIG.main()
    assert sorted(calls) == [("gemini", "AD", 3, 40), ("gemini", "AE", 3, 40)]
    fr = pd.read_excel(tmp_path / "prompt_ablation_friedman_tests.xlsx")
    ad = fr[fr["architecture"] == "AD"]
    ae = fr[fr["architecture"] == "AE"]
    assert set(ad["test"]) == {"friedman"} and (ad["n_configs"] == 3).all()
    assert set(ae["test"]) == {"wilcoxon_signed_rank"} and (ae["n_configs"] == 2).all()
    # One Holm family across both kinds of omnibus test.
    assert fr["p_holm"].notna().all() and len(fr) == 6


def test_collected_control_is_used_instead_of_main_suite(tmp_path):
    rng = np.random.default_rng(1)
    df = pd.DataFrame(_cell_rows("control", "AD", 3, 10, rng, 0.0)
                      + _cell_rows("cot_scaffold", "AD", 3, 10, rng, 0.2))
    stub = SimpleNamespace(load_reference=lambda: pytest.fail("must not load"),
                           main_suite_control_rows=lambda *a, **k: pytest.fail("must not load"))
    out = SIG.add_main_suite_control(df, pa=stub)
    assert len(out) == len(df)


# ---------------------------------------------------------------------------
# A_H order arms: control arm cut (author decision 2026-09-27)
# ---------------------------------------------------------------------------

HY = _load(EXP / "run_hybrid_ablation_experiments.py", "cuts_hybrid")


def test_order_arm_default_collects_reversed_only(monkeypatch):
    assert HY.DEFAULT_ORDER_ARMS == ("reversed",)
    # Six reversed runs against the five main-suite A_H runs (author decision
    # 2026-09-29): unequal groups, so the permutation floor is 1/462.
    assert HY.ORDER_ARM_DEFAULT_RUNS["reversed"] == 6
    monkeypatch.setattr(sys, "argv", ["x", "--collect-only", "--models", "qwen"])
    calls = []
    monkeypatch.setattr(HY, "collect_order_arm",
                        lambda mk, run, arm: calls.append((mk, run, arm)))
    HY.main()
    assert calls == [("qwen", r, "reversed") for r in range(1, 7)]


def test_order_arm_run6_only_with_run_start(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["x", "--collect-only", "--models", "qwen",
                                      "--order-run-start", "6"])
    calls = []
    monkeypatch.setattr(HY, "collect_order_arm",
                        lambda mk, run, arm: calls.append((mk, run, arm)))
    HY.main()
    assert calls == [("qwen", 6, "reversed")]


def test_permutation_floor_accounts_for_complement_symmetry():
    assert HY.permutation_floor_p(5, 5) == pytest.approx(2 / 252)
    assert HY.permutation_floor_p(6, 5) == pytest.approx(1 / 462)
    assert np.isnan(HY.permutation_floor_p(0, 5))


def _perm_tags(n_ship, n_rev, effect):
    base = {s: s % 3 for s in range(60)}
    alt = {s: (s + 1) % 3 for s in range(60)}
    tags = {f"s{i}": dict(base) for i in range(n_ship)}
    tags.update({f"r{i}": dict(alt if effect else base) for i in range(n_rev)})
    return tags, [f"r{i}" for i in range(n_rev)], [f"s{i}" for i in range(n_ship)]


def test_exchangeability_test_reaches_its_floor():
    # Maximal effect: the observed labeling is the most extreme one, so p is
    # exactly the design's floor (5 v 5: 2/252; 6 v 5: 1/462).
    for n_rev, floor in ((5, 2 / 252), (6, 1 / 462)):
        tags, rev, ship = _perm_tags(5, n_rev, effect=True)
        sep, p, n = HY._exchangeability_test(tags, rev, ship)
        assert n == math.comb(5 + n_rev, n_rev)
        assert p == pytest.approx(floor)
        assert p == pytest.approx(HY.permutation_floor_p(n_rev, 5))


def test_exchangeability_test_null_is_one():
    tags, rev, ship = _perm_tags(5, 6, effect=False)
    _, p, _ = HY._exchangeability_test(tags, rev, ship)
    assert p == pytest.approx(1.0)


def test_order_arm_control_still_collectable_on_request(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["x", "--collect-only", "--models", "qwen",
                                      "--order-arms", "control"])
    calls = []
    monkeypatch.setattr(HY, "collect_order_arm",
                        lambda mk, run, arm: calls.append((mk, run, arm)))
    HY.main()
    assert calls == [("qwen", r, "control") for r in range(1, 4)]


REPLIES = [
    '{"energy_cost": 0.6, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '```json\n{"energy_cost": 0.6, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}\n```',
    'Here you go: {"energy_cost": 0.6, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    'Step 1 ... {"note": 1} ... final: {"energy_cost": 0.2, "environmental": 0.3, "comfort": 0.4, "practicality": 0.5}',
    '{"energy_cost": true, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '{"energy_cost": "0.6", "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '{"energy_cost": 1.2, "environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    '{"environmental": 0.5, "comfort": 0.7, "practicality": 0.8}',
    'no json here',
    '[0.6, 0.5, 0.7, 0.8]',
]


@pytest.mark.parametrize("reply", REPLIES)
def test_main_suite_and_ablation_parse_replies_identically(reply):
    """A_D, A_E and the prompt ablation accept and reject exactly the same
    replies, with the same scores (author decision 2026-09-27: the main suite
    uses the lenient parser)."""
    ad = PA._load_direct_module()
    ae_path = REPO / "Architectures" / "Example-Guided_LLM_Scoring.py"
    ae = sys.modules.get("cuts_ae") or _load(ae_path, "cuts_ae")
    pa_scores, pa_error = PA.parse_scores(reply, 1.0)
    ad_scores, ad_diag = ad._validate_scores(reply, {}, "alt")
    ae_scores, ae_diag = ae._validate_scores(reply, {}, [], "")
    ad_ok = not any(v == PA.SENTINEL_FLOAT for v in ad_scores.values())
    ae_ok = not any(ae_scores.get(c) == PA.SENTINEL_FLOAT for c in CRIT)
    assert ad_ok == ae_ok == (pa_error is None), (reply, pa_error, ad_diag, ae_diag)
    if pa_error is None:
        for c in CRIT:
            assert ad_scores[c] == ae_scores[c] == pa_scores[c]
