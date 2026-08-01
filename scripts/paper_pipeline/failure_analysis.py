"""
failure_analysis.py

Scans per-run xlsx files for 1928 sentinel values, loads diagnostics JSONs for
failure mode breakdown, and outputs LaTeX tables for a failure analysis subsection.

Usage: python paper_pipeline/failure_analysis.py
"""
import json
import pandas as pd
import numpy as np
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS

SENTINEL_VALUE = 1928

OUTPUT_DIR = PROJECT_ROOT / "paper"
FAILURE_CSV = OUTPUT_DIR / "failure_analysis.csv"
FAILURE_TEX = OUTPUT_DIR / "failure_analysis_tables.tex"

MODELS = ["deepseek", "gemini", "gptoss", "qwen"]
ARCHS = ["Direct_LLM_Scoring", "Example-Guided_LLM_Scoring", "LLM-Parameterized_Reference_Scoring"]
SCORE_COLS = ["energy_cost", "environmental", "comfort", "practicality"]

FAILURE_TYPES_SHARED = [
    "EXTRACTION_INVALID_JSON", "FAILED_MISSING_SCORE", "FAILED_OUT_OF_BOUNDS",
    "FAILED_INVALID_SCORE_TYPE", "FAILED_API_EXHAUSTED", "FAILED_UNKNOWN"
]
FAILURE_TYPES_AH = [
    "FAILED_EXTRACTION_NON_JSON_WRAPPER", "FAILED_EXTRACTION_INVALID_DECISION_TYPE",
    "FAILED_EXTRACTION_INVALID_CALCULATOR", "FAILED_EXTRACTION_MISSING_PARAMETERS",
    "FAILED_EXTRACTION_INVALID_PARAMETERS", "FAILED_EXTRACTION_DECISION_TYPE_MISMATCH",
    "FAILED_EXTRACTION_EXCEPTION", "FAILED_GROUND_TRUTH_CALCULATION_EXCEPTION",
    "FAILED_GROUND_TRUTH_MISSING_KEY"
]

ARCH_SHORT = {
    "Direct_LLM_Scoring": r"$\mathcal{A}_{\text{D}}$",
    "Example-Guided_LLM_Scoring": r"$\mathcal{A}_{\text{E}}$",
    "LLM-Parameterized_Reference_Scoring": r"$\mathcal{A}_{\text{H}}$",
}

rows = []

for model_key in MODELS:
    output_folder = PROJECT_ROOT / MODEL_SPECS[model_key]["output_folder"]
    for arch in ARCHS:
        for run_num in range(1, 6):
            xlsx_path = output_folder / f"{arch}_results_run_{run_num:02d}.xlsx"
            diag_path = output_folder / f"{arch}_results_diagnostics_run_{run_num:02d}.json"

            if not xlsx_path.exists():
                continue

            diag = {}
            if diag_path.exists():
                with open(diag_path) as f:
                    diag = json.load(f)

            try:
                df = pd.read_excel(xlsx_path)
            except Exception:
                continue

            for _, row in df.iterrows():
                scenario_id = row.get("scenario_id", "unknown")
                decision_type = row.get("decision_type", "unknown")
                has_sentinel = False
                failed_criteria = []
                for col in SCORE_COLS:
                    val = row.get(col, None)
                    try:
                        fval = float(val)
                        if fval == SENTINEL_VALUE:
                            has_sentinel = True
                            failed_criteria.append(col)
                    except (ValueError, TypeError):
                        pass

                if has_sentinel:
                    record = {
                        "scenario_id": scenario_id,
                        "decision_type": decision_type,
                        "architecture": arch,
                        "model": model_key,
                        "run": run_num,
                        "failed_criteria": "_".join(failed_criteria),
                    }
                    for k, v in diag.items():
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            record[k] = v
                    rows.append(record)

if not rows:
    print("No failures found across any run.")
    exit(0)

failure_df = pd.DataFrame(rows)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
failure_df.to_csv(FAILURE_CSV, index=False)
print(f"Wrote {len(failure_df)} failure records to {FAILURE_CSV}")

# ── Build LaTeX tables ──
tex = []

# === Table F1: Total failures per architecture x model ===
tex.append(r"\begin{table}[htbp]")
tex.append(r"\small\centering")
tex.append(r"\caption{Failure counts per architecture and model (summed across 5 runs).}")
tex.append(r"\label{tab:failure_arch_model}")
tex.append(r"\begin{tabular}{lccccc}")
tex.append(r"\toprule")
tex.append(r"Architecture & Gemini & DeepSeek & GPT-OSS & Qwen & Total \\")
tex.append(r"\midrule")

total_all = 0
for arch in ARCHS:
    arch_fails = failure_df[failure_df["architecture"] == arch]
    row_str = ARCH_SHORT[arch]
    arch_total = 0
    for model_key in MODELS:
        n = int(len(arch_fails[arch_fails["model"] == model_key]))
        row_str += f" & {n}"
        arch_total += n
        total_all += n
    row_str += f" & {arch_total} \\\\"
    tex.append(row_str)

tex.append(r"\bottomrule")
tex.append(r"\end{tabular}")
tex.append(r"\end{table}")

# === Table F2: Failure mode breakdown per architecture ===
tex.append(r"\begin{table}[htbp]")
tex.append(r"\small\centering")
tex.append(r"\caption{Failure mode counts per architecture (5-run total across all models).}")
tex.append(r"\label{tab:failure_modes}")
all_failure_types = FAILURE_TYPES_SHARED + FAILURE_TYPES_AH
tex.append(r"\begin{tabular}{l" + "c" * len(all_failure_types) + "}")
tex.append(r"\toprule")
tex.append("Mode & " + " & ".join(all_failure_types) + r" \\")
tex.append(r"\midrule")

for arch in ARCHS:
    arch_fails = failure_df[failure_df["architecture"] == arch]
    row_str = ARCH_SHORT[arch]
    for ft in all_failure_types:
        if ft in failure_df.columns:
            cnt = int(arch_fails[ft].sum())
            row_str += f" & {cnt}"
        else:
            row_str += " & --"
    tex.append(row_str + r" \\")

tex.append(r"\bottomrule")
tex.append(r"\end{tabular}")
tex.append(r"\end{table}")

# === Table F3: Decision-type clustering ===
tex.append(r"\begin{table}[htbp]")
tex.append(r"\small\centering")
tex.append(r"\caption{Failure distribution by decision type (total across all runs).}")
tex.append(r"\label{tab:failure_dt}")
tex.append(r"\begin{tabular}{lccc}")
tex.append(r"\toprule")
tex.append(r"Architecture & HVAC & Appliance & Shower \\")
tex.append(r"\midrule")
for arch in ARCHS:
    arch_fails = failure_df[failure_df["architecture"] == arch]
    n_hvac = int(len(arch_fails[arch_fails["decision_type"] == "HVAC"]))
    n_app = int(len(arch_fails[arch_fails["decision_type"] == "Appliance"]))
    n_shower = int(len(arch_fails[arch_fails["decision_type"] == "Shower"]))
    tex.append(f"{ARCH_SHORT[arch]} & {n_hvac} & {n_app} & {n_shower} \\\\")
tex.append(r"\bottomrule")
tex.append(r"\end{tabular}")
tex.append(r"\end{table}")

# === Table F4: Per-scenario-parameter failure patterns ===
scenario_master = pd.read_excel(PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx")
scenario_master = scenario_master.drop(columns=["decision_type"], errors="ignore")
scenario_master["scenario_id"] = scenario_master.index + 1

merged = failure_df.merge(scenario_master, on="scenario_id", how="left")

tex.append(r"\begin{table}[htbp]")
tex.append(r"\small\centering")
tex.append(r"\caption{Scenario parameters associated with failure. Shows failure count}")
tex.append(r"for parameter combinations with >1 failure across all runs.}")
tex.append(r"\label{tab:failure_params}")

DT_PARAM_GROUPS = {
    "HVAC": ["outdoor_temp", "insulation", "house_age"],
    "Appliance": ["appliance_age"],
    "Shower": ["flow_rate"],
}

for dt in ["HVAC", "Appliance", "Shower"]:
    dt_merged = merged[merged["decision_type"] == dt]
    if len(dt_merged) == 0:
        continue
    group_cols = DT_PARAM_GROUPS[dt]
    avail_cols = [c for c in group_cols if c in dt_merged.columns]
    if not avail_cols:
        continue

    combo_counts = dt_merged.groupby(avail_cols).size().reset_index(name="failure_count")
    combo_counts = combo_counts.sort_values("failure_count", ascending=False).head(5)

    header = "Count & " + " & ".join(avail_cols)
    tex.append(f"\n\\noindent\\textbf{{{dt} failures by parameter combination:}}")
    col_spec = "l" + "c" * len(avail_cols)
    tex.append(r"\begin{tabular}{" + col_spec + r"}")
    tex.append(r"\toprule")
    tex.append(header + r" \\")
    tex.append(r"\midrule")
    for _, rc in combo_counts.iterrows():
        vals = [str(rc["failure_count"])] + [str(rc[c]) for c in avail_cols]
        tex.append(" & ".join(vals) + r" \\")
    tex.append(r"\bottomrule")
    tex.append(r"\end{tabular}")

tex.append(r"\end{table}")

with open(FAILURE_TEX, "w") as f:
    f.write("\n".join(tex))

print(f"Wrote failure analysis LaTeX to {FAILURE_TEX}")
