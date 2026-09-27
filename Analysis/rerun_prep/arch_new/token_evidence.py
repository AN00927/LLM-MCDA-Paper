"""Historical output-token evidence for choosing sentinel_utils.MAX_OUTPUT_TOKENS.

Read-only. Sources (no network):
  - Output Files*/<arch>_results_diagnostics_run_NN.json: per-run totals ->
    mean completion tokens per call, per model x architecture (main benchmark).
  - Output Files*/hybrid_order_reversal/*_raw.jsonl: exact per-call completion
    tokens for A_H extraction (the only per-call record for any architecture).
  - Analysis/Prompt_Ablation/cell_*.xlsx: per-scenario completion tokens (sum of
    the 3 per-alternative calls), so max-per-scenario is an UPPER bound on the
    max per call for A_D / A_E prompts.
  - Analysis/RAG_Ablation/rag_ablation_results.xlsx: completion tokens per row.

Prints ASCII tables; writes token_evidence.csv next to this file.
"""
import glob
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "token_evidence.csv"


def _stats(vals):
    a = np.asarray([v for v in vals if v is not None and not pd.isna(v)], dtype=float)
    if a.size == 0:
        return dict(n=0, mean=np.nan, p99=np.nan, max=np.nan)
    return dict(n=int(a.size), mean=float(a.mean()), p99=float(np.percentile(a, 99)),
                max=float(a.max()))


rows = []

# 1. Main benchmark diagnostics JSON (per-run mean per call).
for folder in sorted(REPO.glob("Output Files*")):
    for arch in ("Direct_LLM_Scoring", "Example-Guided_LLM_Scoring",
                 "LLM-Parameterized_Reference_Scoring"):
        per_run = []
        for p in sorted(folder.glob(f"{arch}_results_diagnostics_run_*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            calls = max(d.get("total_api_calls", 0), 1)
            per_run.append(d.get("total_tokens_output", 0) / calls)
        if per_run:
            rows.append(dict(source="main diagnostics (mean/call per run)", model=folder.name,
                             arch=arch, unit="run-mean per call", **_stats(per_run)))

# 2. A_H order-arm raw jsonl: exact per-call completion tokens.
for folder in sorted(REPO.glob("Output Files*")):
    vals, prompt_vals = [], []
    for p in sorted(folder.glob("hybrid_order_reversal/*_raw.jsonl")):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                vals.append(rec.get("completion_tokens"))
    if vals:
        rows.append(dict(source="A_H order-arm raw jsonl", model=folder.name,
                         arch="LLM-Parameterized_Reference_Scoring", unit="per call", **_stats(vals)))

# 3. Prompt ablation cells: per-scenario sums (upper bound per call).
cell_re = re.compile(r"cell_(?P<variant>.+)_(?P<arch>AD|AE)_(?P<model>[a-z]+)_run_\d+\.xlsx")
groups = {}
for p in sorted((REPO / "Analysis" / "Prompt_Ablation").glob("cell_*.xlsx")):
    m = cell_re.match(p.name)
    if not m:
        continue
    df = pd.read_excel(p, usecols=["completion_tokens", "api_calls"])
    key = (m["variant"], m["arch"], m["model"])
    g = groups.setdefault(key, {"scen": [], "percall": []})
    g["scen"].extend(df["completion_tokens"].tolist())
    g["percall"].extend((df["completion_tokens"] / df["api_calls"].clip(lower=1)).tolist())
for (variant, arch, model), g in sorted(groups.items()):
    rows.append(dict(source=f"prompt ablation {variant} (scenario sum of 3 calls)", model=model,
                     arch=arch, unit="scenario sum = upper bound per call", **_stats(g["scen"])))

# 4. RAG ablation rows.
rag = REPO / "Analysis" / "RAG_Ablation" / "rag_ablation_results.xlsx"
if rag.exists():
    df = pd.read_excel(rag, usecols=["model_key", "ablation_id", "completion_tokens", "api_calls"])
    for (mk, ab), sub in df.groupby(["model_key", "ablation_id"]):
        rows.append(dict(source=f"RAG ablation {ab} (row)", model=mk, arch="AE-like",
                         unit="row completion_tokens", **_stats(sub["completion_tokens"].tolist())))

out = pd.DataFrame(rows)
out.to_csv(OUT, index=False)
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_colwidth", 60)
print(out.to_string(index=False, float_format=lambda v: f"{v:.1f}"))
print(f"\nwrote {OUT}")
