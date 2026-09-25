#!/usr/bin/env python3
"""
d12_position_baseline.py -- Pass 5, D12(c) companion. READ-ONLY, no API calls.

Model-independent diagnostic behind the tie analysis: where the reference
winner sits in the input order (alternative_1..3 on the Test sheet), and what a
trivial "take the alternatives in listed order" rule scores against the
reference with the pipeline's own metric functions (tau / Top-1 per scenario,
then mean; regret in reference MAVT units). This tells the direction in which
an input-order tie-break biases Top-1.

Uses one stored run file only to obtain the pipeline's scenario matching (all
195 scenarios, before failure filtering); the architecture's scores are not
used. Output: Analysis/pass5/d12_position_baseline.csv
"""

import contextlib
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "paper_pipeline"))
warnings.filterwarnings("ignore")

with contextlib.redirect_stdout(io.StringIO()):
    import calculate_per_run_metrics as cprm  # noqa: E402

OUT = PROJECT_ROOT / "Analysis" / "pass5"


def main():
    model, stem = "gemini", "Direct_LLM_Scoring"
    config = cprm._build_config(model)
    folder = Path(config["output_csv"]).parent
    gt_by_type = cprm.load_ground_truth(config)
    gl, gil = cprm.build_gt_lookup(gt_by_type), cprm.build_gt_id_lookup(gt_by_type)
    p = cprm._discover_run_files(folder, stem)[0]
    with contextlib.redirect_stdout(io.StringIO()):
        a = cprm.load_architecture(p, stem)
        merged, _ = cprm.match_scenarios(gl, gil, a, stem)
    merged["input_pos"] = merged.groupby("arch_scenario_id").cumcount() + 1
    merged["gt_mavt_score"] = merged["gt_mavt_score"].astype(float)

    rows = []
    for rule, rank_fn in (("input_order", lambda pos: pos),
                          ("reverse_input_order", lambda pos: 4 - pos)):
        m = merged.copy()
        m["arch_rank"] = rank_fn(m["input_pos"])
        for dt in ["Overall", "HVAC", "Appliance", "Shower"]:
            sub = m if dt == "Overall" else m[m.decision_type == dt]
            r = cprm.compute_ranking_metrics_local(sub)
            reg = []
            for _, sc in sub.groupby("arch_scenario_id"):
                g = sc["gt_mavt_score"].values
                reg.append(g.max() - g[sc["arch_rank"].values.argmin()])
            rows.append(dict(rule=rule, decision_type=dt, n=r["n_scenarios_evaluated"],
                             kendall_tau=r["kendall_tau"], top1=r["top1_accuracy"],
                             mean_regret=float(np.mean(reg))))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "d12_position_baseline.csv", index=False)
    print(df.round(4).to_string())


if __name__ == "__main__":
    main()
