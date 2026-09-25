#!/usr/bin/env python3
"""
d2_reproduce_ah_numbers.py -- Pass 5, item D2 ("two sets of A_H numbers").

READ-ONLY. Makes no API calls, runs no architecture, writes only under
Analysis/pass5/. Every metric is computed per model; nothing is pooled across
models. Failed scenarios are detected with sentinel_utils.is_sentinel (via the
pipeline's own filter_failed_scenarios / the ablation's scenario_metrics) and
never enter an average.

What it does
  A. Reproduces the MAIN A_H numbers (supplement tab:overall_by_model; manuscript
     tau 0.880--0.923) from the five stored per-run files, with the same
     functions paper_pipeline/calculate_per_run_metrics.py uses (per-run metric,
     then mean over runs), per model and per decision type. Writes nothing into
     paper/per_run_metrics.
  B. Reproduces the PROVENANCE numbers (supplement tab:param_provenance;
     "LLM-extracted" tau 0.921/0.897/0.904/0.921) from
     Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx, and proves the
     mechanism: the "extracted" arm reads the 5-run AGGREGATE workbook
     LLM-Parameterized_Reference_Scoring_results.xlsx, whose extracted_*
     columns are the across-run MEAN (numeric) / MODE (categorical) of the
     parameters from the runs that succeeded. We rebuild that consensus from
     the per-run files, compare it with the aggregate file, re-score it through
     the ablation harness, and reproduce the published values.
  C. Like-for-like extraction effect (extraction vs dataset median, and vs
     fixed default): per run, on the scenarios that run scored, then mean over
     runs; per model and per decision type.
  D. Like-for-like significance: paired Wilcoxon (same helper functions the
     published test uses) on per-scenario run-means of the per-run arm vs the
     dataset-median arm; Holm across the 12 model x metric tests.
  E. GPT-OSS "recover each failed scenario from a run in which it succeeded"
     check (manuscript Section 5 failure paragraph).

Outputs (Analysis/pass5/):
  d2_main_ah_per_run.csv, d2_main_ah_summary.csv
  d2_provenance_repro.csv, d2_consensus_param_check.csv
  d2_effect_like_for_like.csv, d2_significance_like_for_like.csv
  d2_gptoss_recovery.csv
"""

import contextlib
import importlib.util
import io
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
warnings.filterwarnings("ignore")

from model_config import MODEL_SPECS  # noqa: E402
from sentinel_utils import is_sentinel, read_table_clean  # noqa: E402

OUT = PROJECT_ROOT / "Analysis" / "pass5"
OUT.mkdir(parents=True, exist_ok=True)
MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
DTYPES = ["HVAC", "Appliance", "Shower"]
AH = "LLM-Parameterized_Reference_Scoring"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


cm = _load("evaluate_architecture_metrics",
           "Miscellaneous Scripts/core-automation/evaluate_architecture_metrics.py")
prm = _load("calculate_per_run_metrics", "paper_pipeline/calculate_per_run_metrics.py")
hab = _load("run_hybrid_ablation_experiments",
            "Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py")
rag = _load("run_rag_ablation_experiments",
            "Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py")


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def per_scenario_rank_metrics(clean):
    """Per-scenario version of prm.compute_ranking_metrics_local (same rules)."""
    out = {}
    for sid in clean["arch_scenario_id"].unique():
        sc = clean[clean["arch_scenario_id"] == sid]
        if len(sc) < 2:
            continue
        gt_r = sc["gt_rank"].astype(float).values
        ar_r = sc["arch_rank"].astype(float).values
        if np.isnan(gt_r).any() or np.isnan(ar_r).any():
            continue
        if len(set(gt_r)) > 1 and len(set(ar_r)) > 1:
            t, _ = stats.kendalltau(gt_r, ar_r)
            t = 0.0 if np.isnan(t) else t
        else:
            t = 1.0 if np.array_equal(gt_r, ar_r) else 0.0
        g1 = sc.loc[sc["gt_rank"].astype(float).idxmin(), "norm_alternative"]
        a1 = sc.loc[sc["arch_rank"].astype(float).idxmin(), "norm_alternative"]
        out[sid] = {"tau": t, "top1": float(g1 == a1),
                    "decision_type": sc["decision_type"].iloc[0],
                    "key": (str(sc["question"].iloc[0]).strip(), str(sc["location"].iloc[0]).strip())}
    return out


# ---------------------------------------------------------------------------
# A. Main A_H numbers from stored per-run files
# ---------------------------------------------------------------------------
print("=== A. Main A_H numbers (per-run metric, mean over 5 runs) ===")
main_rows = []
for mk in MODELS:
    config = cm._build_config(mk)
    folder = Path(config["output_csv"]).parent
    gt = quiet(cm.load_ground_truth, config)
    gtl, gtid = cm.build_gt_lookup(gt), cm.build_gt_id_lookup(gt)
    for rp in prm._discover_run_files(folder, AH):
        run = int(rp.stem.split("_run_")[-1])
        arch = quiet(cm.load_architecture, rp, AH)
        merged, _ = quiet(cm.match_scenarios, gtl, gtid, arch, AH)
        clean, n_failed, n_total = cm.filter_failed_scenarios(merged)
        for dt in ["Overall"] + DTYPES:
            sub = clean if dt == "Overall" else clean[clean["decision_type"] == dt]
            r = prm.compute_ranking_metrics_local(sub)
            c = cm.compute_criterion_metrics(sub)
            tot = n_total if dt == "Overall" else merged[merged["decision_type"] == dt]["arch_scenario_id"].nunique()
            main_rows.append({"model": mk, "run": run, "decision_type": dt,
                              "kendall_tau": r["kendall_tau"], "top1": r["top1_accuracy"],
                              "mae": c["overall_MAE"], "n_scored": r["n_scenarios_evaluated"],
                              "n_total": tot})
main = pd.DataFrame(main_rows)
main.to_csv(OUT / "d2_main_ah_per_run.csv", index=False)
msum = (main.groupby(["model", "decision_type"])
        .agg(tau=("kendall_tau", "mean"), tau_sd=("kendall_tau", "std"),
             top1=("top1", "mean"), mae=("mae", "mean"),
             n_scored=("n_scored", "sum"), n_total=("n_total", "sum"))
        .reset_index())
msum["success_rate"] = msum["n_scored"] / msum["n_total"]
msum.to_csv(OUT / "d2_main_ah_summary.csv", index=False)
print(msum.round(4).to_string(index=False))

# ---------------------------------------------------------------------------
# B. Provenance numbers: reproduce from the ablation workbook, then prove the
#    consensus mechanism from the per-run files.
# ---------------------------------------------------------------------------
print("\n=== B. Provenance 'extracted' arm ===")
ps = pd.read_excel(PROJECT_ROOT / "Analysis/Hybrid_Ablation/hybrid_ablation_summary.xlsx",
                   sheet_name="per_scenario")
ps["failed"] = ps["failed"].astype(bool)

test_df = hab.load_test_scenarios()
gt_cache = {d: hab.load_ground_truth(d) for d in hab.SCENARIO_FILES}
defaults = hab.compute_defaults()
ref_cache = {}


def ref_scored_for(sid):
    if sid not in ref_cache:
        row = test_df[test_df["scenario_id"] == sid].iloc[0]
        dt = hab._clean_text(row["decision_type"])
        g = hab.match_ground_truth(row, gt_cache[dt], dt)
        ref_cache[sid] = (row, dt, g, hab.score_scenario(dt, hab.build_scenario(
            dt, row, g, hab.true_params(g, dt))))
    return ref_cache[sid]


def consensus_params(run_rows, dt):
    """Across-run mean (numeric) / mode (categorical) over SUCCESSFUL runs,
    i.e. what run_multi_and_aggregate writes into the aggregate workbook."""
    ok = [p for p in (hab.extracted_params(r, dt) for r in run_rows) if p is not None]
    if not ok:
        return None, 0
    out = {}
    for p in hab.HIDDEN_PARAMS[dt]["numeric"]:
        out[p] = float(np.mean([o[p] for o in ok]))
    for p in hab.HIDDEN_PARAMS[dt]["categorical"]:
        out[p] = pd.Series([o[p] for o in ok]).mode().iloc[0]
    return out, len(ok)


prov_rows, pcheck_rows = [], []
for mk in MODELS:
    folder = PROJECT_ROOT / MODEL_SPECS[mk]["output_folder"]
    agg = read_table_clean(folder / f"{AH}_results.xlsx")
    agg_first = agg.drop_duplicates(subset=["scenario_id"])  # what the ablation does
    agg_by = {int(r["scenario_id"]): r for _, r in agg_first.iterrows()}
    runs = {}
    for p in sorted(folder.glob(f"{AH}_results_run_*.xlsx")):
        d = read_table_clean(p).drop_duplicates(subset=["scenario_id"])
        runs[p.stem[-2:]] = {int(r["scenario_id"]): r for _, r in d.iterrows()}
    rec = []
    max_abs_diff = 0.0
    n_first_row_failed_group = 0
    for sid in sorted(test_df["scenario_id"]):
        row, dt, g, ref = ref_scored_for(sid)
        cons, n_ok = consensus_params([runs[k][sid] for k in runs if sid in runs[k]], dt)
        a = agg_by.get(sid)
        a_params = hab.extracted_params(a, dt) if a is not None else None
        if str(a.get("extraction_failed")).strip().lower() == "true":
            n_first_row_failed_group += 1
        # compare consensus vs aggregate-file params
        if cons is not None and a_params is not None:
            for p in hab.HIDDEN_PARAMS[dt]["numeric"]:
                max_abs_diff = max(max_abs_diff, abs(cons[p] - a_params[p]))
            for p in hab.HIDDEN_PARAMS[dt]["categorical"]:
                if str(cons[p]) != str(a_params[p]):
                    max_abs_diff = max(max_abs_diff, np.inf)
        m = None
        if cons is not None:
            m = hab.scenario_metrics(hab.score_scenario(dt, hab.build_scenario(dt, row, g, cons)), ref)
        rec.append({"model": mk, "scenario_id": sid, "decision_type": dt,
                    "n_successful_runs": n_ok, "failed": m is None,
                    **(m or {"kendall_tau": np.nan, "top1": np.nan, "mae": np.nan})})
    rec = pd.DataFrame(rec)
    pcheck_rows.append({"model": mk, "scenarios": len(rec),
                        "scenarios_with_consensus": int((rec["n_successful_runs"] > 0).sum()),
                        "first_row_is_failed_group": n_first_row_failed_group,
                        "max_abs_param_diff_consensus_vs_aggregate_file": max_abs_diff,
                        "aggregate_file_rows": len(agg)})
    pub = ps[(ps.model == mk) & (ps.arm == "extracted")]
    for dt in ["Overall"] + DTYPES:
        r_ = rec if dt == "Overall" else rec[rec.decision_type == dt]
        p_ = pub if dt == "Overall" else pub[pub.decision_type == dt]
        ok, pok = r_[~r_.failed], p_[~p_.failed]
        prov_rows.append({"model": mk, "decision_type": dt,
                          "rebuilt_tau": ok.kendall_tau.mean(), "rebuilt_top1": ok.top1.mean(),
                          "rebuilt_mae": ok.mae.mean(), "rebuilt_n_scored": len(ok),
                          "published_tau": pok.kendall_tau.mean(), "published_top1": pok.top1.mean(),
                          "published_mae": pok.mae.mean(), "published_n_scored": len(pok),
                          "n_scenarios": len(r_)})
prov = pd.DataFrame(prov_rows)
prov.to_csv(OUT / "d2_provenance_repro.csv", index=False)
pd.DataFrame(pcheck_rows).to_csv(OUT / "d2_consensus_param_check.csv", index=False)
print(prov.round(4).to_string(index=False))
print(pd.DataFrame(pcheck_rows).to_string(index=False))

# ---------------------------------------------------------------------------
# C. Like-for-like effect: extraction (per run) minus baseline on the same
#    scenarios that run scored; mean over runs.
# ---------------------------------------------------------------------------
print("\n=== C. Like-for-like extraction effect ===")
# Fixed-default per-scenario metrics through the pipeline matcher.
fd_df = pd.read_excel(PROJECT_ROOT / "Output Files/Baselines/baseline_fixeddefault.xlsx")
fd_df = fd_df.rename(columns={f"{c}_score": c for c in ["energy_cost", "environmental", "comfort", "practicality"]})
for col in ("question", "location", "alternative"):
    fd_df[col] = fd_df[col].astype(str).str.strip()
cfg = cm._build_config("gemini")
gt = quiet(cm.load_ground_truth, cfg)
fd_arch = quiet(cm.load_architecture, fd_df, "FixedDefault")
fd_m, _ = quiet(cm.match_scenarios, cm.build_gt_lookup(gt), cm.build_gt_id_lookup(gt), fd_arch, "FixedDefault")
fd_clean, _, _ = cm.filter_failed_scenarios(fd_m)
fd_ps = per_scenario_rank_metrics(fd_clean)
# baseline_fixeddefault.xlsx scenario_id is the 0-based Test row index; the
# ablation's scenario_id is the 1-based Test row index (verified: questions,
# locations and alternative sets agree row by row for all 195).
fd_by_q = {int(sid) + 1: v for sid, v in fd_ps.items()}
q_by_sid = {s: s for s in fd_by_q}
assert len(fd_by_q) == 195, "FD scenario count"
for dt in DTYPES:
    print(f"  FD {dt}: tau {np.mean([v['tau'] for v in fd_ps.values() if v['decision_type'] == dt]):.4f}")
print(f"FixedDefault per-scenario rows: {len(fd_ps)}; "
      f"overall tau {np.mean([v['tau'] for v in fd_ps.values()]):.4f}")

eff_rows = []
for mk in MODELS:
    pr = ps[(ps.model == mk) & (ps.arm == "extracted_per_run")]
    de = ps[(ps.model == mk) & (ps.arm == "default_params")].set_index("scenario_id")
    for dt in ["Overall"] + DTYPES:
        per_run = []
        for run, g in pr.groupby("source_run"):
            g = g if dt == "Overall" else g[g.decision_type == dt]
            ok = g[~g.failed]
            sids = ok.scenario_id.values
            fd_tau = [fd_by_q[q_by_sid[s]]["tau"] for s in sids]
            fd_t1 = [fd_by_q[q_by_sid[s]]["top1"] for s in sids]
            all_sids = g.scenario_id.values
            per_run.append({
                "ext_tau": ok.kendall_tau.mean(), "ext_top1": ok.top1.mean(), "ext_mae": ok.mae.mean(),
                "med_tau_same": de.loc[sids, "kendall_tau"].mean(),
                "med_top1_same": de.loc[sids, "top1"].mean(),
                "med_mae_same": de.loc[sids, "mae"].mean(),
                "med_tau_all": de.loc[all_sids, "kendall_tau"].mean(),
                "fd_tau_same": np.mean(fd_tau), "fd_top1_same": np.mean(fd_t1),
                "fd_tau_all": np.mean([fd_by_q[q_by_sid[s]]["tau"] for s in all_sids]),
                "fd_top1_all": np.mean([fd_by_q[q_by_sid[s]]["top1"] for s in all_sids]),
                "n_scored": len(ok), "n": len(g)})
        R = pd.DataFrame(per_run)
        row = {"model": mk, "decision_type": dt, "n_runs": len(R),
               "n_scored_mean": R.n_scored.mean(), "n": R.n.iloc[0]}
        for c in R.columns:
            if c not in ("n_scored", "n"):
                row[c] = R[c].mean()
        row["effect_vs_median_published_basis"] = row["ext_tau"] - row["med_tau_all"]
        row["effect_vs_median_like_for_like"] = (R.ext_tau - R.med_tau_same).mean()
        row["effect_vs_median_like_for_like_run_min"] = (R.ext_tau - R.med_tau_same).min()
        row["effect_vs_median_like_for_like_run_max"] = (R.ext_tau - R.med_tau_same).max()
        row["top1_effect_vs_median_like_for_like"] = (R.ext_top1 - R.med_top1_same).mean()
        row["effect_vs_fd_published_basis"] = row["ext_tau"] - row["fd_tau_all"]
        row["effect_vs_fd_like_for_like"] = (R.ext_tau - R.fd_tau_same).mean()
        row["top1_effect_vs_fd_published_basis"] = row["ext_top1"] - row["fd_top1_all"]
        row["top1_effect_vs_fd_like_for_like"] = (R.ext_top1 - R.fd_top1_same).mean()
        eff_rows.append(row)
eff = pd.DataFrame(eff_rows)
eff.to_csv(OUT / "d2_effect_like_for_like.csv", index=False)
print(eff[["model", "decision_type", "ext_tau", "med_tau_all", "med_tau_same",
           "effect_vs_median_published_basis", "effect_vs_median_like_for_like",
           "fd_tau_all", "fd_tau_same", "effect_vs_fd_published_basis",
           "effect_vs_fd_like_for_like"]].round(4).to_string(index=False))

# Consensus basis (what the provenance table reports) vs median on the same scenarios
cons_rows = []
for mk in MODELS:
    ex = ps[(ps.model == mk) & (ps.arm == "extracted") & (~ps.failed)]
    de = ps[(ps.model == mk) & (ps.arm == "default_params")].set_index("scenario_id")
    for dt in ["Overall"] + DTYPES:
        e = ex if dt == "Overall" else ex[ex.decision_type == dt]
        cons_rows.append({"model": mk, "decision_type": dt, "cons_tau": e.kendall_tau.mean(),
                          "med_tau_same": de.loc[e.scenario_id, "kendall_tau"].mean(),
                          "cons_effect": e.kendall_tau.mean() - de.loc[e.scenario_id, "kendall_tau"].mean(),
                          "cons_top1": e.top1.mean(), "med_top1_same": de.loc[e.scenario_id, "top1"].mean()})
cons = pd.DataFrame(cons_rows)
cons.to_csv(OUT / "d2_effect_consensus_basis.csv", index=False)
print()
print("Consensus-basis effect (provenance-table basis):")
print(cons.round(4).to_string(index=False))

# Check: ablation per-run arm reproduces the pipeline per-run numbers run by run
chk = []
for mk in MODELS:
    pr = ps[(ps.model == mk) & (ps.arm == "extracted_per_run") & (~ps.failed)]
    for run, g in pr.groupby("source_run"):
        rn = int(run[-2:])
        m = main[(main.model == mk) & (main.run == rn) & (main.decision_type == "Overall")].iloc[0]
        chk.append({"model": mk, "run": rn, "ablation_tau": g.kendall_tau.mean(), "pipeline_tau": m.kendall_tau,
                    "ablation_top1": g.top1.mean(), "pipeline_top1": m.top1,
                    "ablation_n": len(g), "pipeline_n": m.n_scored})
chk = pd.DataFrame(chk)
chk.to_csv(OUT / "d2_perrun_harness_check.csv", index=False)
print()
print("Max |ablation - pipeline| per-run tau:", float((chk.ablation_tau - chk.pipeline_tau).abs().max()),
      " top1:", float((chk.ablation_top1 - chk.pipeline_top1).abs().max()),
      " n mismatches:", int((chk.ablation_n != chk.pipeline_n).sum()))

# ---------------------------------------------------------------------------
# D. Like-for-like significance: per-scenario run-mean of the per-run arm vs
#    the dataset-median arm; same Wilcoxon / Cliff / Holm helpers.
# ---------------------------------------------------------------------------
print("\n=== D. Like-for-like significance (per-scenario run-mean vs dataset median) ===")
sig_rows = []
for mk in MODELS:
    pr = ps[(ps.model == mk) & (ps.arm == "extracted_per_run") & (~ps.failed)]
    runmean = pr.groupby("scenario_id")[["kendall_tau", "top1", "mae"]].mean().reset_index()
    runmean["arm"] = "extracted_runmean"
    de = ps[(ps.model == mk) & (ps.arm == "default_params") & (~ps.failed)][
        ["scenario_id", "kendall_tau", "top1", "mae"]].assign(arm="default_params")
    stratum = pd.concat([runmean, de], ignore_index=True)
    for metric in ["kendall_tau", "top1", "mae"]:
        ph = rag.posthoc_wilcoxon_holm(stratum, metric, config_col="arm", scenario_col="scenario_id")
        for _, r in ph.iterrows():
            sig_rows.append({"model": mk, "metric": metric, "config_i": r.config_i,
                             "config_j": r.config_j, "statistic": r.statistic,
                             "p_value": r.p_value, "cliff_delta": r.cliff_delta,
                             "cliff_interp": r.cliff_delta_interpretation, "n_pairs": r.n_pairs})
    # robustness: each shipped run separately
    for run, g in ps[(ps.model == mk) & (ps.arm == "extracted_per_run") & (~ps.failed)].groupby("source_run"):
        st = pd.concat([g[["scenario_id", "kendall_tau", "top1", "mae"]].assign(arm="extracted_run"), de],
                       ignore_index=True)
        for metric in ["kendall_tau", "top1", "mae"]:
            ph = rag.posthoc_wilcoxon_holm(st, metric, config_col="arm", scenario_col="scenario_id")
            for _, r in ph.iterrows():
                sig_rows.append({"model": mk, "metric": f"{metric}[{run}]", "config_i": r.config_i,
                                 "config_j": r.config_j, "statistic": r.statistic, "p_value": r.p_value,
                                 "cliff_delta": r.cliff_delta, "cliff_interp": r.cliff_delta_interpretation,
                                 "n_pairs": r.n_pairs})
    # per decision type, tau and top1, run-mean basis (descriptive; separate family)
    for dt in DTYPES:
        sids = set(test_df[test_df["decision_type"].map(hab._clean_text) == dt]["scenario_id"])
        st = stratum[stratum.scenario_id.isin(sids)]
        for metric in ["kendall_tau", "top1"]:
            ph = rag.posthoc_wilcoxon_holm(st, metric, config_col="arm", scenario_col="scenario_id")
            if ph.empty:
                sig_rows.append({"model": mk, "metric": f"{metric}<{dt}>", "p_value": np.nan,
                                 "n_pairs": st.scenario_id.nunique()})
            for _, r in ph.iterrows():
                sig_rows.append({"model": mk, "metric": f"{metric}<{dt}>", "config_i": r.config_i,
                                 "config_j": r.config_j, "statistic": r.statistic, "p_value": r.p_value,
                                 "cliff_delta": r.cliff_delta, "cliff_interp": r.cliff_delta_interpretation,
                                 "n_pairs": r.n_pairs,
                                 "mean_ext": st[st.arm == "extracted_runmean"][metric].mean(),
                                 "mean_med": st[st.arm == "default_params"][metric].mean()})
sig = pd.DataFrame(sig_rows)
fam = ~sig.metric.str.contains(r"[\[<]")
dtfam = sig.metric.str.contains("<")
if dtfam.any():
    ph_, _ = rag.holm_correct(sig.loc[dtfam, "p_value"].values)
    sig.loc[dtfam, "p_holm_bytype_24"] = ph_
p_holm, s_holm = rag.holm_correct(sig.loc[fam, "p_value"].values)
sig.loc[fam, "p_holm_12"] = p_holm
sig.loc[fam, "significant_holm_12"] = s_holm
sig.to_csv(OUT / "d2_significance_like_for_like.csv", index=False)
print(sig[fam].to_string(index=False, float_format=lambda v: f"{v:.4g}"))
print("per-run tau tests (raw p):")
prun = sig.metric.str.contains(r"\[")
print(sig[prun][["model", "metric", "p_value", "cliff_delta", "n_pairs"]].to_string(index=False, float_format=lambda v: f"{v:.3g}"))
print("per decision type (run-mean basis):")
print(sig[dtfam][["model", "metric", "mean_ext", "mean_med", "p_value", "p_holm_bytype_24", "cliff_delta", "n_pairs"]].to_string(index=False, float_format=lambda v: f"{v:.3g}"))

# ---------------------------------------------------------------------------
# E. GPT-OSS recovery claim
# ---------------------------------------------------------------------------
print("\n=== E. Backfill each failed scenario-run from a run where it succeeded ===")
rec_rows = []
for mk in MODELS:
    pr = ps[(ps.model == mk) & (ps.arm == "extracted_per_run")].copy()
    runs_sorted = sorted(pr.source_run.unique())
    tab = {(r.source_run, r.scenario_id): r for r in pr.itertuples()}
    for policy in ("first_other_success", "all_success_mean"):
        per_run = []
        for run in runs_sorted:
            vals = []
            for sid in sorted(pr.scenario_id.unique()):
                r = tab[(run, sid)]
                if not r.failed:
                    vals.append((r.kendall_tau, r.top1)); continue
                others = [tab[(o, sid)] for o in runs_sorted if o != run and not tab[(o, sid)].failed]
                if not others:
                    continue
                if policy == "first_other_success":
                    vals.append((others[0].kendall_tau, others[0].top1))
                else:
                    vals.append((np.mean([o.kendall_tau for o in others]), np.mean([o.top1 for o in others])))
            v = np.array(vals)
            per_run.append((v[:, 0].mean(), v[:, 1].mean(), len(v)))
        P = np.array(per_run)
        rec_rows.append({"model": mk, "policy": policy, "tau": P[:, 0].mean(),
                         "top1": P[:, 1].mean(), "n_scored_mean": P[:, 2].mean()})
recov = pd.DataFrame(rec_rows)
recov.to_csv(OUT / "d2_gptoss_recovery.csv", index=False)
print(recov.round(4).to_string(index=False))
print("\nDone. Outputs in Analysis/pass5/")
