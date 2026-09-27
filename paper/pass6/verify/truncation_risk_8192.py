import glob, re, json
import numpy as np, pandas as pd
R = "C:/Users/Ahaan/LLM-MCDA Paper/"
CAP = 8192
def bounds(S, n_calls):
    S = np.asarray(S, dtype=float); n = np.asarray(n_calls, dtype=float)
    lo = ((S > n * CAP) & (n > 0)).astype(int)            # >=1 call over cap guaranteed
    up = np.minimum(n, np.floor(S / (CAP + 1)))           # at most this many calls over
    eq = np.where((n > 0) & (S / np.maximum(n, 1) > CAP), n, 0)  # equal split
    return lo.sum(), eq.sum(), up.sum()
rows = []
# prompt ablation cells: one row per scenario, completion_tokens = sum over its api_calls
parts = []
for p in glob.glob(R + "Analysis/Prompt_Ablation/cell_*_run_*.xlsx"):
    d = pd.read_excel(p, usecols=["variant", "architecture", "model", "run", "scenario_id", "api_calls",
                                  "successful_calls", "completion_tokens"])
    parts.append(d)
pa = pd.concat(parts)
for (m, v, a), g in pa.groupby(["model", "variant", "architecture"]):
    calls = int(g.api_calls.sum()); ok = int(g.successful_calls.sum())
    lo, eq, up = bounds(g.completion_tokens, g.successful_calls)
    rows.append(dict(source="prompt_ablation", model=m, arm=f"{a}:{v}", runs=g.run.nunique(),
                     scored_calls=ok, mean_completion_per_call=g.completion_tokens.sum() / max(ok, 1),
                     max_scenario_sum_3calls=int(g.completion_tokens.max()),
                     pct_lower=100 * lo / ok, pct_equal_split=100 * eq / ok, pct_upper=100 * up / ok))
# RAG ablation: per-alternative rows, token columns are scenario-level
r = pd.read_excel(R + "Analysis/RAG_Ablation/rag_ablation_results.xlsx")
r = r[r.llm.astype(bool)].drop_duplicates(["model_key", "ablation_id", "source_scenario_id"])
for (m, a), g in r.groupby(["model_key", "ablation_id"]):
    ok = int(g.successful_calls.sum())
    lo, eq, up = bounds(g.completion_tokens, g.successful_calls)
    rows.append(dict(source="rag_ablation", model=m, arm=a, runs=1, scored_calls=ok,
                     mean_completion_per_call=g.completion_tokens.sum() / max(ok, 1),
                     max_scenario_sum_3calls=int(g.completion_tokens.max()),
                     pct_lower=100 * lo / ok, pct_equal_split=100 * eq / ok, pct_upper=100 * up / ok))
# A_H order arm: exact per call
ah = []
for p in glob.glob(R + "Output Files*/hybrid_order_reversal/*_raw.jsonl"):
    m = p.split("Output Files ")[1].split("/")[0].split("\\")[0]
    for line in open(p, encoding="utf-8"):
        if line.strip():
            ah.append((m, json.loads(line).get("completion_tokens") or 0))
ahd = pd.DataFrame(ah, columns=["folder", "ct"])
for f, g in ahd.groupby("folder"):
    rows.append(dict(source="AH_order_arm (exact per call)", model=f, arm="AH extraction", runs=8,
                     scored_calls=len(g), mean_completion_per_call=g.ct.mean(),
                     max_scenario_sum_3calls=int(g.ct.max()),
                     pct_lower=100 * (g.ct > CAP).mean(), pct_equal_split=100 * (g.ct > CAP).mean(),
                     pct_upper=100 * (g.ct > CAP).mean()))
out = pd.DataFrame(rows).sort_values(["source", "model", "arm"])
out.to_csv(R + "paper/pass6/verify/truncation_risk_8192.csv", index=False, float_format="%.2f")
pd.set_option("display.width", 250)
print(out.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
