#!/usr/bin/env python3
"""
d1_build_numbers_rows.py -- writes paper/pass5/NUMBERS_OF_RECORD_D1_rows.csv:
one row per number that D1_REPORT.md proposes for the paper or supplement,
same columns as paper/pass5/NUMBERS_OF_RECORD.csv. Reads only the d1_* CSVs.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "Analysis" / "pass5"
OUTF = ROOT / "paper" / "pass5" / "NUMBERS_OF_RECORD_D1_rows.csv"
SCRIPT = "Analysis/pass5/d1_lookup_baseline.py"
PAPER = "paper/paper_draft_v2.tex"
SUPP = "paper/supplementary.tex"

bs = pd.read_csv(A / "d1_baseline_summary.csv")
gain = pd.read_csv(A / "d1_ah_gain_like_for_like.csv")
sig = pd.read_csv(A / "d1_significance_ah_vs_lookup.csv")
ci = pd.read_csv(A / "d1_bootstrap_ci_gain.csv")
acc = pd.read_csv(A / "d1_parser_accuracy.csv")
rows = []


def add(nid, val, where, ctx, src, col, script, model, dt, basis):
    rows.append({"number_id": nid, "value": val, "where_in_paper": where, "quoted_context": ctx,
                 "source_file": src, "source_sheet_or_column": col, "computing_script": script,
                 "model": model, "decision_type": dt, "basis_notes": basis,
                 "status": "new (proposed in D1_REPORT.md; not yet in paper)"})


BNAME = {"LU": "label-lookup/text-parse baseline", "FD+time": "fixed default + parsed baseline time",
         "LU-corpus": "corpus-lookup variant", "LU-literal": "lookup without occupancy parser",
         "FD": "fixed default", "DM": "dataset median"}
for b in ["LU", "FD+time", "LU-corpus", "LU-literal"]:
    for dt in ["Overall", "HVAC", "Appliance", "Shower"]:
        r = bs[(bs.baseline == b) & (bs.decision_type == dt)].iloc[0]
        for m, v, fmt in [("tau", r.tau, "{:.3f}"), ("top1", 100 * r.top1, "{:.1f}"), ("mae", r.mae, "{:.3f}")]:
            if b in ("LU-corpus", "LU-literal") and (dt != "Overall" or m == "mae"):
                continue
            where = {"LU": f"{PAPER}:796 (new table row) / {PAPER}:808 (new paragraph) / {SUPP}:1334 (new subsection)",
                     "FD+time": f"{PAPER}:1071 (new sentence) / {SUPP}:1334 (new subsection)"}.get(b, f"{SUPP}:1334 (new subsection)")
            add(f"D1_{b}_{m}_{dt}", fmt.format(v), where, f"{BNAME[b]} {m} {dt}",
                "Analysis/pass5/d1_baseline_per_scenario.csv", f"baseline=={b}; {m}", SCRIPT, "model-free", dt,
                "deterministic non-LLM parameters through the reference calculators (hab harness); mean over scenarios; Top-1 in %")

fd = bs[(bs.baseline == "FD") & (bs.decision_type == "Overall")].iloc[0]
for b in ["LU", "FD+time"]:
    r = bs[(bs.baseline == b) & (bs.decision_type == "Overall")].iloc[0]
    add(f"D1_{b}_dtau_vs_FD", f"+{r.tau - fd.tau:.3f}", f"{PAPER}:796 (new table row)", f"{BNAME[b]} delta tau vs fixed default 0.614",
        "Analysis/pass5/d1_baseline_summary.csv", "tau Overall", SCRIPT, "model-free", "Overall", "difference before rounding")
    add(f"D1_{b}_dtop1_vs_FD", f"+{100 * (r.top1 - fd.top1):.1f}", f"{PAPER}:796 (new table row)", f"{BNAME[b]} delta Top-1 (pp) vs fixed default 70.3",
        "Analysis/pass5/d1_baseline_summary.csv", "top1 Overall", SCRIPT, "model-free", "Overall", "difference before rounding")

for _, r in gain.iterrows():
    add(f"D1_gain_tau_vs_LU_{r.model}_{r.decision_type}", f"{r.gain_tau_vs_LU:+.3f}",
        f"{PAPER}:808 (new paragraph) / {SUPP}:1334 (new subsection)",
        f"A_H tau minus lookup tau, like-for-like ({r.model}, {r.decision_type})",
        "Analysis/pass5/d1_ah_gain_like_for_like.csv", "gain_tau_vs_LU", SCRIPT, r.model, r.decision_type,
        "per run: A_H tau on the scenarios that run scored minus LU tau on the same scenarios; mean of 5 runs")
    add(f"D1_gain_tau_vs_FDtime_{r.model}_{r.decision_type}", f"{r['gain_tau_vs_FD+time']:+.3f}",
        f"{SUPP}:1334 (new subsection)", f"A_H tau minus FD+time tau, like-for-like ({r.model}, {r.decision_type})",
        "Analysis/pass5/d1_ah_gain_like_for_like.csv", "gain_tau_vs_FD+time", SCRIPT, r.model, r.decision_type,
        "same like-for-like basis")
    if r.decision_type == "Overall":
        add(f"D1_gain_top1_vs_LU_{r.model}", f"{100 * r.gain_top1_vs_LU:+.1f}", f"{SUPP}:1334 (new subsection)",
            f"A_H Top-1 minus lookup Top-1 (pp), {r.model}", "Analysis/pass5/d1_ah_gain_like_for_like.csv",
            "gain_top1_vs_LU", SCRIPT, r.model, "Overall", "like-for-like, pp")

c = ci[(ci.baseline == "LU") & (ci.scope == "Overall") & (ci.metric == "kendall_tau")]
for _, r in c.iterrows():
    add(f"D1_gain_tau_vs_LU_CI95_{r.model}", f"[{r.ci95_lo:.3f}, {r.ci95_hi:.3f}]", f"{SUPP}:1334 (new subsection)",
        f"95% paired bootstrap CI of A_H minus LU tau, {r.model}", "Analysis/pass5/d1_bootstrap_ci_gain.csv",
        "ci95_lo/ci95_hi", "Analysis/pass5/d1_bootstrap_ci.py", r.model, "Overall",
        "per-scenario run-mean basis, 10,000 scenario resamples; mean differs slightly from like-for-like for GPT-OSS")
s = sig[(sig.comparison == "AH vs LU") & (sig.scope == "Overall")]
for _, r in s.iterrows():
    add(f"D1_pHolm_AH_vs_LU_{r.metric}_{r.model}", f"{r.p_holm:.3g}", f"{SUPP}:1334 (new subsection)",
        f"Holm p, A_H vs lookup, {r.metric}, {r.model}", "Analysis/pass5/d1_significance_ah_vs_lookup.csv",
        "p_holm (family overall12)", SCRIPT, r.model, "Overall",
        "paired Wilcoxon on per-scenario run means (Methods protocol); Holm over 4 models x 3 metrics")
    add(f"D1_cliff_AH_vs_LU_{r.metric}_{r.model}", f"{r.cliff_delta_ah_minus_base:.3f}", f"{SUPP}:1334 (new subsection)",
        f"Cliff's delta (A_H minus lookup), {r.metric}, {r.model}", "Analysis/pass5/d1_significance_ah_vs_lookup.csv",
        "cliff_delta_ah_minus_base", SCRIPT, r.model, "Overall", "run_rag_ablation_experiments.cliff_delta")
for p, g in acc.groupby("param"):
    add(f"D1_parser_accuracy_{p}", f"{100 * g.match.mean():.1f}", f"{SUPP}:1334 (new subsection)",
        f"rule parser match rate vs true {p} ({int(g.match.sum())}/{len(g)})", "Analysis/pass5/d1_parser_accuracy.csv",
        "match", SCRIPT, "model-free", "HVAC" if p == "occupancy_context" else "Appliance",
        "occupancy compared after the calculator's normalize_occupancy_context; time compared as clock hour")

pd.DataFrame(rows).to_csv(OUTF, index=False)
print(f"wrote {len(rows)} rows to {OUTF.relative_to(ROOT)}")
