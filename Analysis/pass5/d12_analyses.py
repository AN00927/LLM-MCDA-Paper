#!/usr/bin/env python3
"""
d12_analyses.py -- Pass 5, item D12 (optional analyses on existing data).

READ-ONLY. No API calls, no architecture reruns, writes only under
Analysis/pass5/. Every metric is computed per model (never pooled across
models). Failed scenarios are detected with sentinel_utils.is_sentinel through
the pipeline's own filter_failed_scenarios and never enter a mean or a ranking.

Harness: the same functions paper_pipeline/calculate_per_run_metrics.py uses
(load_architecture, match_scenarios, filter_failed_scenarios,
compute_ranking_metrics_local, compute_criterion_metrics), so tau / Top-1 / MAE
have the pipeline's definitions and tie handling:
  * ranks come from the stored strict ranks (1,2,3); the architectures break
    weighted-score ties by TIE_BREAK_PRIORITY (environmental, energy_cost,
    comfort, practicality), then by input order (stable sort);
  * tau is per scenario on those strict ranks, then averaged over scenarios;
  * a scenario with any sentinel in any alternative is dropped from that run.
A reproduction gate (section 0) checks the harness against
paper/per_run_metrics/per_run_metrics_all.csv before anything else is reported.

Sections
  0. Harness gate: per-run tau / Top-1 / MAE vs per_run_metrics_all.csv.
  a. Ensembled A_D / A_E: each alternative's four criterion scores averaged over
     the runs in which the scenario succeeded, ranked with the architectures'
     own apply_mavt_ranking (same weights, same tie-break, input order), then
     scored once. Compared with the per-run mean (numbers of record).
     Also a scenario-level paired Wilcoxon (ensemble tau vs the scenario's
     run-mean tau), Holm across the 8 model x architecture tests.
  b. Decision regret for A_D / A_E / A_H: reference MAVT value of the reference
     winner minus reference MAVT value of the alternative the architecture
     ranks first; per run, then mean over runs. Also share of zero-regret
     scenarios, mean regret given a Top-1 miss, and the expected regret of a
     uniformly random pick on the same scenarios.
  c. Ties: share of scenarios where >= 2 alternatives share the top weighted
     score; how the tie was resolved (criterion priority vs input order); where
     the reference winner lands; Top-1 as shipped vs expected Top-1 under a
     uniformly random tie-break among the tied-top set vs input-order-only
     tie-break.
  d. Tokens: input vs output tokens per run from the stored diagnostics JSON.

Outputs (Analysis/pass5/): d12_harness_gate.csv, d12_ensemble.csv,
d12_ensemble_wilcoxon.csv, d12_regret_per_run.csv, d12_regret_summary.csv,
d12_ties_per_run.csv, d12_ties_summary.csv, d12_gt_winner_position.csv,
d12_tokens.csv
"""

import contextlib
import io
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "paper_pipeline"))
warnings.filterwarnings("ignore")

from model_config import MODEL_SPECS, CRITERION_WEIGHTS, TIE_BREAK_PRIORITY  # noqa: E402
from sentinel_utils import apply_mavt_ranking, CRITERIA  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import calculate_per_run_metrics as cprm  # noqa: E402

OUT = PROJECT_ROOT / "Analysis" / "pass5"
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
ARCHS = {
    "A_D": "Direct_LLM_Scoring",
    "A_E": "Example-Guided_LLM_Scoring",
    "A_H": "LLM-Parameterized_Reference_Scoring",
}
DTYPES = ["HVAC", "Appliance", "Shower"]
EPS = 1e-9
MERGED_ALL = {}


def wsum(row, prefix="arch_"):
    return sum(CRITERION_WEIGHTS[c] * float(row[f"{prefix}{c}"]) for c in CRITERIA)


def load_runs(model_key, arch_stem):
    """Return list of (run_num, clean merged df with input position, n_failed)."""
    config = cprm._build_config(model_key)
    folder = Path(config["output_csv"]).parent
    gt_by_type = cprm.load_ground_truth(config)
    gt_lookup = cprm.build_gt_lookup(gt_by_type)
    gt_id_lookup = cprm.build_gt_id_lookup(gt_by_type)
    out = []
    for p in cprm._discover_run_files(folder, arch_stem):
        run = int(p.stem.split("_run_")[-1])
        with contextlib.redirect_stdout(io.StringIO()):
            arch_df = cprm.load_architecture(p, arch_stem)
            merged, _ = cprm.match_scenarios(gt_lookup, gt_id_lookup, arch_df, arch_stem)
        # input position = order of the alternative within the scenario in the
        # stored run file (== alternative_1..3 order on the Test sheet; checked)
        merged["input_pos"] = merged.groupby("arch_scenario_id").cumcount() + 1
        clean, n_failed, n_total = cprm.filter_failed_scenarios(merged)
        clean = clean.copy()
        for c in CRITERIA:
            clean[f"arch_{c}"] = clean[f"arch_{c}"].astype(float)
            clean[f"gt_{c}"] = clean[f"gt_{c}"].astype(float)
        clean["gt_mavt_score"] = clean["gt_mavt_score"].astype(float)
        clean["run"] = run
        MERGED_ALL[(model_key, arch_stem, run)] = merged
        out.append((run, clean, n_failed, n_total))
    return out


def metrics(df):
    r = cprm.compute_ranking_metrics_local(df)
    c = cprm.compute_criterion_metrics(df)
    return r["kendall_tau"], r["top1_accuracy"], c["overall_MAE"], r["n_scenarios_evaluated"]


def by_type(df):
    yield "Overall", df
    for dt in DTYPES:
        sub = df[df["decision_type"] == dt]
        if len(sub):
            yield dt, sub


def scen_tau_top1(sc):
    """Per-scenario tau and top1, identical logic to compute_ranking_metrics_local."""
    gt_r = sc["gt_rank"].astype(float).values
    ar_r = sc["arch_rank"].astype(float).values
    if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
        tau, _ = stats.kendalltau(gt_r, ar_r)
        tau = 0.0 if np.isnan(tau) else tau
    else:
        tau = 1.0 if np.array_equal(gt_r, ar_r) else 0.0
    gt_top = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
    ar_top = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
    return tau, float(gt_top == ar_top)


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for i, idx in enumerate(order):
        running = max(running, (m - i) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


def main():
    gate_rows, ens_rows, wil_rows = [], [], []
    reg_rows, tie_rows, pos_rows = [], [], []
    prm = pd.read_csv(PROJECT_ROOT / "paper" / "per_run_metrics" / "per_run_metrics_all.csv")
    gt_pos_done = False

    for model in MODELS:
        for arch, stem in ARCHS.items():
            print(f"[{model}] {arch} ...")
            runs = load_runs(model, stem)

            # ---------- 0. harness gate ----------
            for run, clean, n_failed, n_total in runs:
                for dt, sub in by_type(clean):
                    tau, top1, mae, n = metrics(sub)
                    ref = prm[(prm.model == model) & (prm.architecture == stem)
                              & (prm.run == run) & (prm.decision_type == dt)]
                    if len(ref):
                        ref = ref.iloc[0]
                        gate_rows.append(dict(
                            model=model, arch=arch, run=run, decision_type=dt,
                            tau=tau, tau_csv=ref.kendall_tau, top1=top1, top1_csv=ref.top1_accuracy,
                            mae=mae, mae_csv=ref.overall_mae, n=n, n_csv=ref.n_scenarios,
                            max_abs_diff=max(abs(tau - ref.kendall_tau), abs(top1 - ref.top1_accuracy),
                                             abs(mae - ref.overall_mae))))

            allr = pd.concat([c for _, c, _, _ in runs], ignore_index=True)

            # ---------- GT winner input position (model-independent; once) ----------
            if not gt_pos_done:
                r1 = MERGED_ALL[(model, stem, runs[0][0])].copy()
                r1 = r1[r1["gt_rank"].notna()]
                r1["gt_mavt_score"] = r1["gt_mavt_score"].astype(float)
                for dt, sub in by_type(r1):
                    winners = sub[sub["gt_rank"].astype(float) == 1]
                    cnt = winners["input_pos"].value_counts().reindex([1, 2, 3], fill_value=0)
                    nsc = sub["arch_scenario_id"].nunique()
                    # reference ties at the top (mavt equal to 4 dp)
                    gt_top_tie = 0
                    for sid, sc in sub.groupby("arch_scenario_id"):
                        m = sc["gt_mavt_score"].values
                        if (np.abs(m - m.max()) < EPS).sum() > 1:
                            gt_top_tie += 1
                    pos_rows.append(dict(decision_type=dt, n_scenarios=nsc,
                                         gt_winner_pos1=cnt[1] / nsc, gt_winner_pos2=cnt[2] / nsc,
                                         gt_winner_pos3=cnt[3] / nsc, gt_top_tied_share=gt_top_tie / nsc,
                                         note=f"all matched scenarios of {model} {arch} run {runs[0][0]} (before failure filtering)"))
                gt_pos_done = True

            # ---------- b. regret and c. ties, per run ----------
            for run, clean, _, _ in runs:
                per_s = []
                for sid, sc in clean.groupby("arch_scenario_id", sort=False):
                    sc = sc.sort_values("input_pos")
                    dt = sc["decision_type"].iloc[0]
                    gm = sc["gt_mavt_score"].values
                    gt_top_idx = sc["gt_rank"].astype(float).values.argmin()
                    ar_top_idx = sc["arch_rank"].astype(float).values.argmin()
                    best = gm[gt_top_idx]
                    regret = best - gm[ar_top_idx]
                    rand_regret = float(np.mean(best - gm))
                    rng = gm.max() - gm.min()
                    hit = float(sc["norm_alternative"].values[gt_top_idx] == sc["norm_alternative"].values[ar_top_idx])
                    # ties on the architecture's weighted score
                    ws = np.array([wsum(r) for _, r in sc.iterrows()])
                    top_set = np.where(np.abs(ws - ws.max()) < EPS)[0]
                    any_tie = int(len(np.unique(np.round(ws, 9))) < len(ws))
                    top_tie = int(len(top_set) > 1)
                    # within the tied-top set, is the choice decided by criterion
                    # priority or does it fall through to input order?
                    input_order_decided = 0
                    if top_tie:
                        keys = [tuple(round(float(sc.iloc[i][f"arch_{c}"]), 9) for c in TIE_BREAK_PRIORITY)
                                for i in top_set]
                        best_key = max(keys)
                        if sum(k == best_key for k in keys) > 1:
                            input_order_decided = 1
                    all_identical = int(len({tuple(round(float(r[f'arch_{c}']), 9) for c in CRITERIA)
                                             for _, r in sc.iterrows()}) == 1)
                    gt_in_top = int(gt_top_idx in top_set)
                    rand_top1 = (gt_in_top / len(top_set)) if top_tie else hit
                    input_first_top1 = float(top_set[0] == gt_top_idx) if top_tie else hit
                    gt_pos_in_tie = (int(np.where(top_set == gt_top_idx)[0][0]) + 1) if (top_tie and gt_in_top) else 0
                    per_s.append(dict(sid=sid, dt=dt, regret=regret, rand_regret=rand_regret,
                                      norm_regret=(regret / rng) if rng > EPS else 0.0,
                                      hit=hit, any_tie=any_tie, top_tie=top_tie,
                                      top_tie_size=len(top_set) if top_tie else 1,
                                      input_order_decided=input_order_decided,
                                      all_identical=all_identical, gt_in_top=gt_in_top,
                                      rand_top1=rand_top1, input_first_top1=input_first_top1,
                                      gt_pos_in_tie=gt_pos_in_tie,
                                      shipped_top_pos=int(sc["input_pos"].values[ar_top_idx])))
                ps = pd.DataFrame(per_s)
                for dt in ["Overall"] + DTYPES:
                    s = ps if dt == "Overall" else ps[ps.dt == dt]
                    if not len(s):
                        continue
                    miss = s[s.hit == 0]
                    reg_rows.append(dict(
                        model=model, arch=arch, run=run, decision_type=dt, n=len(s),
                        mean_regret=s.regret.mean(), mean_norm_regret=s.norm_regret.mean(),
                        zero_regret_share=(s.regret.abs() < EPS).mean(),
                        top1=s.hit.mean(), n_miss=len(miss),
                        mean_regret_given_miss=miss.regret.mean() if len(miss) else np.nan,
                        zero_regret_share_given_miss=(miss.regret.abs() < EPS).mean() if len(miss) else np.nan,
                        max_regret=s.regret.max(), random_pick_regret=s.rand_regret.mean()))
                    tt = s[s.top_tie == 1]
                    tie_rows.append(dict(
                        model=model, arch=arch, run=run, decision_type=dt, n=len(s),
                        any_tie_share=s.any_tie.mean(), top_tie_share=s.top_tie.mean(),
                        top_tie_input_order_share=s.input_order_decided.mean(),
                        all_three_identical_share=s.all_identical.mean(),
                        n_top_tie=len(tt),
                        gt_in_tied_top_share=tt.gt_in_top.mean() if len(tt) else np.nan,
                        gt_first_in_tie_share=(tt.gt_pos_in_tie == 1).mean() if len(tt) else np.nan,
                        shipped_hit_in_ties=tt.hit.mean() if len(tt) else np.nan,
                        top1_shipped=s.hit.mean(), top1_random_tiebreak=s.rand_top1.mean(),
                        top1_input_order_only=s.input_first_top1.mean(),
                        top1_ties_as_miss=((s.hit == 1) & (s.top_tie == 0)).mean(),
                        shipped_top_pos1_share=(s.shipped_top_pos == 1).mean()))

            # ---------- a. ensemble (A_D, A_E only) ----------
            if arch in ("A_D", "A_E"):
                rows = []
                for sid, g in allr.groupby("arch_scenario_id", sort=False):
                    n_runs = g["run"].nunique()
                    first = g[g["run"] == g["run"].min()].sort_values("input_pos")
                    alts = []
                    for _, fr in first.iterrows():
                        a = g[g["norm_alternative"] == fr["norm_alternative"]]
                        alts.append({"alternative": fr["norm_alternative"],
                                     **{c: a[f"arch_{c}"].mean() for c in CRITERIA}})
                    rk = apply_mavt_ranking(alts)
                    for i, (_, fr) in enumerate(first.iterrows()):
                        d = fr.to_dict()
                        for c in CRITERIA:
                            d[f"arch_{c}"] = alts[i][c]
                        d["arch_rank"] = rk["ranks"][i]
                        d["n_runs_used"] = n_runs
                        rows.append(d)
                ens = pd.DataFrame(rows)
                for dt, sub in by_type(ens):
                    e_tau, e_top1, e_mae, e_n = metrics(sub)
                    ref = prm[(prm.model == model) & (prm.architecture == stem) & (prm.decision_type == dt)]
                    ens_rows.append(dict(
                        model=model, arch=arch, decision_type=dt,
                        perrun_tau=ref.kendall_tau.mean(), ens_tau=e_tau, d_tau=e_tau - ref.kendall_tau.mean(),
                        perrun_tau_min=ref.kendall_tau.min(), perrun_tau_max=ref.kendall_tau.max(),
                        perrun_top1=ref.top1_accuracy.mean(), ens_top1=e_top1,
                        d_top1=e_top1 - ref.top1_accuracy.mean(),
                        perrun_mae=ref.overall_mae.mean(), ens_mae=e_mae, d_mae=e_mae - ref.overall_mae.mean(),
                        ens_n_scenarios=e_n, mean_runs_per_scenario=sub.groupby("arch_scenario_id")["n_runs_used"].first().mean()))
                # scenario-level paired test, Overall
                ens_s = {sid: scen_tau_top1(sc) for sid, sc in ens.groupby("arch_scenario_id")}
                runmean = {}
                for sid, g in allr.groupby("arch_scenario_id"):
                    vals = [scen_tau_top1(sc) for _, sc in g.groupby("run")]
                    runmean[sid] = (np.mean([v[0] for v in vals]), np.mean([v[1] for v in vals]))
                sids = sorted(set(ens_s) & set(runmean))
                for k, name in ((0, "kendall_tau"), (1, "top1")):
                    a = np.array([ens_s[s][k] for s in sids])
                    b = np.array([runmean[s][k] for s in sids])
                    diff = a - b
                    try:
                        w = stats.wilcoxon(a, b, zero_method="wilcox", correction=True, mode="approx")
                        p = w.pvalue
                    except ValueError:
                        p = np.nan
                    wil_rows.append(dict(model=model, arch=arch, metric=name, n=len(sids),
                                         mean_ensemble=a.mean(), mean_runmean=b.mean(),
                                         mean_diff=diff.mean(), n_better=(diff > 1e-12).sum(),
                                         n_worse=(diff < -1e-12).sum(), p=p))

    gate = pd.DataFrame(gate_rows)
    gate.to_csv(OUT / "d12_harness_gate.csv", index=False)
    print(f"harness gate: {len(gate)} cells, max abs diff {gate.max_abs_diff.max():.6f}")

    ens = pd.DataFrame(ens_rows)
    ens.to_csv(OUT / "d12_ensemble.csv", index=False)
    wil = pd.DataFrame(wil_rows)
    for metric in wil.metric.unique():
        m = wil.metric == metric
        wil.loc[m, "p_holm"] = holm(wil.loc[m, "p"].fillna(1.0).values)
    wil.to_csv(OUT / "d12_ensemble_wilcoxon.csv", index=False)

    reg = pd.DataFrame(reg_rows)
    reg.to_csv(OUT / "d12_regret_per_run.csv", index=False)
    agg = {c: "mean" for c in ["n", "mean_regret", "mean_norm_regret", "zero_regret_share", "top1",
                               "n_miss", "mean_regret_given_miss", "zero_regret_share_given_miss",
                               "max_regret", "random_pick_regret"]}
    regs = reg.groupby(["model", "arch", "decision_type"], sort=False).agg(agg).reset_index()
    regs["n_runs"] = reg.groupby(["model", "arch", "decision_type"], sort=False).size().values
    regs.to_csv(OUT / "d12_regret_summary.csv", index=False)

    tie = pd.DataFrame(tie_rows)
    tie.to_csv(OUT / "d12_ties_per_run.csv", index=False)
    tcols = [c for c in tie.columns if c not in ("model", "arch", "run", "decision_type")]
    ties = tie.groupby(["model", "arch", "decision_type"], sort=False)[tcols].mean().reset_index()
    # pooled-over-runs (within one model) share of all scenario-runs with an any-tie,
    # the basis the supplement's S1 tie sentence appears to use
    ties["top1_inflation_vs_random_pp"] = 100 * (ties.top1_shipped - ties.top1_random_tiebreak)
    ties.to_csv(OUT / "d12_ties_summary.csv", index=False)

    pd.DataFrame(pos_rows).to_csv(OUT / "d12_gt_winner_position.csv", index=False)

    # ---------- d. tokens ----------
    tok_rows = []
    for model in MODELS:
        folder = PROJECT_ROOT / MODEL_SPECS[model]["output_folder"]
        for arch, stem in ARCHS.items():
            paths = sorted(folder.glob(f"{stem}_results_diagnostics_run_*.json"))
            ins, outs, calls, okc = [], [], [], []
            for p in paths:
                d = json.loads(p.read_text())
                ins.append(d.get("total_tokens_input", 0))
                outs.append(d.get("total_tokens_output", 0))
                calls.append(d.get("total_api_calls", 0))
                okc.append(d.get("successful_calls", 0))
            if not paths:
                continue
            tin, tout, tc = np.mean(ins), np.mean(outs), np.mean(calls)
            tok_rows.append(dict(model=model, arch=arch, n_runs=len(paths),
                                 input_tokens_per_run=tin, output_tokens_per_run=tout,
                                 total_tokens_per_run=tin + tout,
                                 output_share=tout / (tin + tout) if tin + tout else np.nan,
                                 api_calls_per_run=tc, successful_calls_per_run=np.mean(okc),
                                 input_per_call=tin / tc if tc else np.nan,
                                 output_per_call=tout / tc if tc else np.nan,
                                 input_per_scenario=tin / 195, output_per_scenario=tout / 195))
    pd.DataFrame(tok_rows).to_csv(OUT / "d12_tokens.csv", index=False)
    print("done")


if __name__ == "__main__":
    main()
