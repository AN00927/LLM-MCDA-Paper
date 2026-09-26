#!/usr/bin/env python3
"""
nn_check.py -- nearest-neighbour baseline, old vs new, on current data.

    python Analysis/rerun_prep/pipeline/nn_check.py run before   # before the edit
    python Analysis/rerun_prep/pipeline/nn_check.py run after    # after the edit
    python Analysis/rerun_prep/pipeline/nn_check.py compare

`run` calls run_baseline_models.run_nearest_neighbor_baseline() as it stands on
disk, writes the predictions to nn_<phase>/baseline_nearestneighbor.xlsx next to
this file, and scores them with evaluate_baseline_metrics' machinery (the path
behind Output Files/Baselines/baseline_metrics.csv). `after` also checks that
every query string equals the one A_E builds for the same Test row. Offline:
the encoder is loaded from the local cache and no API is called.
"""

import contextlib
import importlib.util
import io
import sys
import warnings
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
for sub in ("Miscellaneous Scripts/core-automation", "Miscellaneous Scripts/experiments",
            "Ground Truth Calculators"):
    sys.path.insert(0, str(ROOT / sub))
warnings.filterwarnings("ignore")

from sentinel_utils import read_table_clean, format_embedding_text  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


def score(path):
    ebm = _load("evaluate_baseline_metrics", "Miscellaneous Scripts/core-automation/evaluate_baseline_metrics.py")
    cm = ebm._cm
    with contextlib.redirect_stdout(io.StringIO()):
        gt = cm.load_ground_truth(cm._build_config("gemini"))
        arch = ebm.load_baseline(path, "NearestNeighbor")
        merged, _ = cm.match_scenarios(cm.build_gt_lookup(gt), cm.build_gt_id_lookup(gt),
                                       arch, "NearestNeighbor")
    clean, n_failed, _ = cm.filter_failed_scenarios(merged)
    out = []
    for dt in ["HVAC", "Appliance", "Shower", "Overall"]:
        sub = clean if dt == "Overall" else clean[clean["decision_type"] == dt]
        r = cm.compute_ranking_metrics(sub)
        c = cm.compute_criterion_metrics(sub)
        out.append({"decision_type": dt, "kendall_tau": r["kendall_tau"],
                    "top1": r["top1_accuracy"], "mae": c["overall_MAE"],
                    "n_scored": r["n_scenarios_evaluated"], "n_failed": n_failed})
    return pd.DataFrame(out)


def run(phase):
    rbm = _load("run_baseline_models", "Miscellaneous Scripts/core-automation/run_baseline_models.py")
    test_df = read_table_clean(ROOT / "Scenario Files" / "TestScenarios.xlsx")
    out_dir = HERE / f"nn_{phase}"
    out_dir.mkdir(exist_ok=True)

    queries = []
    if phase == "after":
        import run_rag_ablation_experiments as rag
        orig = rag.retrieve_similar

        def spy(collection, model, scenario, k):
            queries.append((scenario["source_scenario_id"],
                            format_embedding_text(scenario["decision_type"], scenario)))
            return orig(collection, model, scenario, k)
        rbm.retrieve_similar = spy

    with contextlib.redirect_stdout(io.StringIO()):
        nn = rbm.run_nearest_neighbor_baseline(test_df, k=3)
    path = out_dir / "baseline_nearestneighbor.xlsx"
    nn.to_excel(path, index=False, engine="openpyxl")
    res = score(path)
    res.insert(0, "phase", phase)
    res.to_csv(out_dir / "nn_metrics.csv", index=False)
    print(res.to_string(index=False))

    if phase == "after":
        # A_E's query: format_embedding_text on the Test row as A_E loads it.
        ae = _load("aeg", "Architectures/Example-Guided_LLM_Scoring.py")
        te = read_table_clean(ROOT / "Scenario Files" / "TestScenarios.xlsx",
                              keep_str_cols=["alternative_1", "alternative_2", "alternative_3"])
        mism = 0
        for (sid, q), (_, row) in zip(queries, te.iterrows()):
            ae_q, _ = ae.format_scenario_text_for_retrieval(row.to_dict())
            mism += (ae_q != q)
        print(f"queries: {len(queries)}; differ from A_E's query string: {mism}")
        pd.DataFrame([{"n_queries": len(queries), "n_differ_from_AE": mism}]).to_csv(
            out_dir / "query_parity.csv", index=False)


def compare():
    b = pd.read_csv(HERE / "nn_before" / "nn_metrics.csv")
    a = pd.read_csv(HERE / "nn_after" / "nn_metrics.csv")
    ship = pd.read_csv(ROOT / "Output Files" / "Baselines" / "baseline_metrics.csv")
    ship = ship[ship.baseline == "NearestNeighbor"].replace({"Overall_pooled": "Overall"})
    rows = []
    for _, r in b.iterrows():
        n = a[a.decision_type == r.decision_type].iloc[0]
        for m, sm in (("kendall_tau", "kendall_tau"), ("top1", "top1_accuracy"), ("mae", "overall_MAE")):
            s = ship[(ship.decision_type == r.decision_type) & (ship.metric == sm)]["value"]
            rows.append({"decision_type": r.decision_type, "metric": m,
                         "shipped_baseline_metrics_csv": float(s.iloc[0]) if len(s) else None,
                         "old": r[m], "new": n[m], "delta": n[m] - r[m]})
    out = pd.DataFrame(rows)
    out.to_csv(HERE / "nn_old_vs_new.csv", index=False)
    print(out.round(4).to_string(index=False))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2])
    else:
        compare()
