# LLM-MCDA: AI-Assisted Multi-Criteria Decision Analysis for Household Energy Optimization

**Author:** Ahaan Nigam  
**Institution:** Downingtown East High School  
**Collaborator:** Dr. River Huang, Paul Scherrer Institut (PSI), Switzerland  
**Target Journal:** Environmental Modelling & Software

---

## Research Question

Which LLM integration architecture most accurately replicates physics-based MAVT ground truth for household energy decisions, while maintaining acceptable failure rates and API costs?

---

## Project Overview

This project benchmarks three LLM-MCDA architectures for household energy decision-making against a physics-based Multi-Attribute Value Theory (MAVT) ground truth calculator across **195 test scenarios** (70 HVAC, 65 Appliance, 60 Shower). Each scenario presents three alternatives scored on four criteria. A disjoint **90-scenario RAG corpus** (35 HVAC, 35 Appliance, 20 Shower) seeds the retrieval index used by the RAG-Enhanced architecture and never appears in evaluation.

We evaluate four models: Gemini 3.5 Flash, DeepSeek V4 Flash, GPT-OSS 20B, and Qwen 3.5 9B. Each runs 5 trials per architecture per scenario (58,500 total API calls for the full benchmark).

The three decision types target behavioral plasticity and contribution to residential energy/water use: HVAC (thermostat setpoints), Appliance (time-of-use scheduling), and Shower (duration).

---

## Setup

Requires **Python 3.11 or newer**.

```bash
git clone <repository-url>
cd LLM-MCDA-Paper

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell / cmd)
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### API key

The three architectures call models through [OpenRouter](https://openrouter.ai). Copy `.env.example` to `.env` at the repository root and fill in your key:

```
OPENROUTER_API_KEY=your_key_here
```

`.env` is gitignored and must never be committed.

### Selecting a model and run count

Both live in [model_config.py](model_config.py):

- `MODEL_KEY` -- one of `gptoss`, `qwen`, `deepseek`, `gemini` (see [Model Set](#model-set)). This also routes output to that model's folder.
- `N_RUNS` -- number of repeated trials per architecture (5 for the reported benchmark).

### Running the benchmark

```bash
# Build the ChromaDB retrieval index first -- required by the RAG architecture,
# and it must be rebuilt after any change to the RAG scenario workbooks.
python "Miscellaneous Scripts/build_rag_index.py"

python Architectures/Direct_LLM_Scoring.py
python Architectures/Example-Guided_LLM_Scoring.py
python Architectures/LLM-Parameterized_Reference_Scoring.py
```

Runs are resume-aware: a per-run `*_results_run_NN.xlsx` that already exists and is readable is skipped, so an interrupted benchmark can be relaunched without repaying for completed runs. Each run also writes `*_results_diagnostics_run_NN.json` (token counts, latency, failure-type counters, UTC collection timestamp) and `*_results_run_NN_raw.jsonl` (one record per API call with the prompt, the raw model response, and per-call latency and token counts).

### Regenerating every paper number and figure

```bash
python paper_pipeline/run_paper_pipeline.py
```

This is the single entry point for the analysis side. It runs every deterministic step -- objective weights, per-run metrics, sensitivity arms, results numbers, figures, and LaTeX snippet generators -- in dependency order, reading only files already on disk. It makes **no API calls** and costs nothing. `--list` shows the stages, `--only <stage>` runs one.

### Reproducing the paper

The two halves have very different requirements:

| | Needs an API key | Cost | Scripts |
| --- | --- | --- | --- |
| **Collecting the benchmark** | Yes | 58,500 API calls across 4 models x 3 architectures x 5 runs (see [API Costs](#api-costs-per-5-run-benchmark)) | `Architectures/*.py`, `Miscellaneous Scripts/run_*_experiments.py`, `run_baseline_models.py` |
| **Everything analytical** | No | Free | `paper_pipeline/run_paper_pipeline.py` and everything it calls |

The per-run outputs for all four models are committed under the `Output Files */` folders, so every metric, table, figure, significance test, ablation summary, and sensitivity arm in the paper can be regenerated from a fresh clone with no key and no spending -- `pip install -r requirements.txt` followed by `python paper_pipeline/run_paper_pipeline.py`. Re-collecting the benchmark is only necessary to change the model set, the scenario data, or a prompt.

Ground-truth scores are likewise reproducible offline: running a calculator in `Ground Truth Calculators/` directly regenerates its `Ground Truth/ground_truth_*.xlsx` from the scenario workbooks. If you change a calculator or the scenario data, see the refresh-order rules in [CLAUDE.md](CLAUDE.md) -- `build_rag_index.py` always runs last.

---

## MAVT Criterion Weights

Weights are constant across all decision types, architectures, and the ground-truth calculator. Score differences reflect input and value-function fidelity.

| Criterion | Weight | Justification |
| --- | --- | --- |
| Environmental Impact | 35% | VBN theory identifies environmental orientation as the most consistent normative driver of pro-environmental household behavior; entropy-based normalization independently assigns it above-average information weight |
| Energy Cost | 30% | Strongest independent predictor of consumer adoption; households underestimate energy use by ~2.8x on average (Attari et al., 2010) |
| Comfort | 20% | Dominant driver of HVAC behavior even when it conflicts with energy savings; ASHRAE 55 provides a physically interpretable anchor |
| Practicality | 15% | Constraint on feasibility and long-term adoption |

A sensitivity analysis confirms LLM-Parameterized_Reference_Scoring's advantage over RAG-Enhanced is unconditional across every weight vector tested. RAG-Enhanced's advantage over Pure Prompting holds under baseline, equal, and entropy-derived weights but narrows and reverses in a few model/decision-type cells under MEREC-derived weights, which load heavily onto Comfort rather than cost and emissions (see [Sensitivity Analysis](#sensitivity-analysis) below).

---

## Results Summary

LLM-Parameterized_Reference_Scoring dominates across all four models. RAG-Enhanced ranks second. Pure Prompting ranks third with near-random performance on HVAC and Appliance.

### Overall Metrics (5-run mean, 195 scenarios)

| Model | Architecture | Kendall's tau | Spearman rho | Top-1 Acc | Top-2 Acc | Overall MAE |
| --- | --- | --- | --- | --- | --- | --- |
| **Gemini 3.5 Flash** | LLM-Parameterized_Reference_Scoring | **0.923** | **0.935** | **0.931** | **0.985** | **0.048** |
| | RAG-Enhanced | 0.305 | 0.320 | 0.472 | 0.794 | 0.159 |
| | Pure Prompting | 0.176 | 0.173 | 0.362 | 0.697 | 0.220 |
| **DeepSeek V4 Flash** | LLM-Parameterized_Reference_Scoring | **0.897** | **0.910** | **0.908** | **0.977** | **0.046** |
| | RAG-Enhanced | 0.328 | 0.354 | 0.545 | 0.815 | 0.167 |
| | Pure Prompting | 0.144 | 0.145 | 0.367 | 0.722 | 0.231 |
| **GPT-OSS 20B** | LLM-Parameterized_Reference_Scoring | **0.897** | **0.911** | **0.916** | **0.981** | **0.052** |
| | RAG-Enhanced | 0.270 | 0.290 | 0.480 | 0.769 | 0.169 |
| | Pure Prompting | 0.041 | 0.038 | 0.333 | 0.665 | 0.241 |
| **Qwen 3.5 9B** | LLM-Parameterized_Reference_Scoring | **0.880** | **0.890** | **0.897** | **0.969** | **0.072** |
| | RAG-Enhanced | 0.207 | 0.222 | 0.470 | 0.768 | 0.192 |
| | Pure Prompting | 0.010 | 0.008 | 0.300 | 0.677 | 0.235 |

### By Decision Type (Gemini 3.5 Flash)

| Decision | Architecture | Kendall's tau | Spearman rho | Top-1 Acc | Overall MAE |
| --- | --- | --- | --- | --- | --- |
| **HVAC** | LLM-Parameterized_Reference_Scoring | **0.977** | **0.983** | **0.966** | **0.030** |
| | RAG-Enhanced | -0.116 | -0.094 | 0.153 | 0.203 |
| | Pure Prompting | -0.032 | -0.037 | 0.254 | 0.241 |
| **Appliance** | LLM-Parameterized_Reference_Scoring | **0.959** | **0.969** | **0.969** | **0.067** |
| | RAG-Enhanced | 0.344 | 0.335 | 0.563 | 0.159 |
| | Pure Prompting | -0.022 | -0.075 | 0.249 | 0.272 |
| **Shower** | LLM-Parameterized_Reference_Scoring | **0.822** | **0.842** | **0.850** | **0.048** |
| | RAG-Enhanced | 0.766 | 0.800 | 0.755 | 0.107 |
| | Pure Prompting | 0.633 | 0.688 | 0.610 | 0.139 |

### Key Findings

- **LLM-Parameterized_Reference_Scoring achieves near-perfect ranking on HVAC (tau=0.98) and Appliance (tau=0.96)** where its inferred parameters (R-value, SEER, kWh/cycle) map deterministically through physics formulas. Shower is lower (tau=0.82) because GPM estimation from flow-rate labels has inherent precision limits.
- **Pure Prompting performs at or below random on HVAC and Appliance** (HVAC tau: -0.03 to 0.24; Appliance tau: -0.19 to -0.02). It only works on Shower (tau: 0.10-0.63), where the decision space is simpler.
- **RAG-Enhanced provides a modest boost over Pure Prompting** on Appliance (tau: 0.07-0.34) and Shower (tau: 0.43-0.82) but fails on HVAC (tau: -0.12 to 0.27). The HVAC decision space has high scenario diversity that the 35-example RAG corpus cannot adequately cover.
- **Model capability correlates weakly with architecture ranking.** The cheapest model (GPT-OSS 20B at $0.029/M tokens) achieves comparable LLM-Parameterized_Reference_Scoring performance to the most expensive (Gemini 3.5 Flash at $1.50/M). Architecture design dominates model choice.
- **Failure rates are negligible** across all architectures and models (0-0.5%), except GPT-OSS 20B on LLM-Parameterized_Reference_Scoring (12.8% extraction failure rate, 0.5% overall scenario failure after multi-run averaging).

### API Costs (per 5-run benchmark)

| Architecture | Calls/run | Gemini | DeepSeek | GPT-OSS | Qwen |
| --- | --- | --- | --- | --- | --- |
| Pure Prompting | 585 | ~$4.00 | ~$0.45 | ~$0.12 | ~$0.22 |
| RAG-Enhanced | 585 | ~$5.10 | ~$0.20 | ~$0.12 | ~$0.21 |
| LLM-Parameterized_Reference_Scoring | 195 | ~$1.40 | ~$0.06 | ~$0.03 | ~$0.06 |

---

### Imputation Robustness Test

Per-run imputed robustness is computed via [paper_pipeline/generate_imputed_robustness_tables.py](paper_pipeline/generate_imputed_robustness_tables.py), which evaluates each run independently after replacing sentinel 1928 scores with 0.5 (scale midpoint) before MAVT ranking and metric averaging. Output is written to [Analysis/MetricsSummary/metrics_summary_all_models_imputed_perrun.xlsx](Analysis/MetricsSummary/metrics_summary_all_models_imputed_perrun.xlsx).

---

## Model Set

Set `MODEL_KEY` and `N_RUNS` in [model_config.py](model_config.py) to control model selection and output routing.

| Key | Label | OpenRouter string | Reasoning effort | Output folder |
| --- | --- | --- | --- | --- |
| `gptoss` | Smallest - GPT-OSS-20B | `openai/gpt-oss-20b:exacto` | low | `Output Files GPT-OSS 20B` |
| `qwen` | Small - Qwen 3.5 9B | `qwen/qwen3.5-9b:exacto` | non-reasoning | `Output Files Qwen3.5 9B` |
| `deepseek` | Medium - DeepSeek V4 Flash | `deepseek/deepseek-v4-flash:exacto` | non-reasoning | `Output Files DeepSeek V4 Flash` |
| `gemini` | Large - Gemini 3.5 Flash | `google/gemini-3.5-flash:exacto` | minimal | `Output Files Gemini 3.5 Flash` |

Model pricing (as of benchmark date): GPT-OSS $0.029/M in / $0.14/M out; Qwen $0.10/M / $0.15/M; DeepSeek $0.09/M / $0.18/M; Gemini $1.50/M / $9/M.

---

## Repository Structure

```
LLM-MCDA-Paper/
├── Architectures/
│   ├── Direct_LLM_Scoring.py
│   ├── Example-Guided_LLM_Scoring.py
│   └── LLM-Parameterized_Reference_Scoring.py
├── Ground Truth/
│   ├── ground_truth_appliance.xlsx
│   ├── ground_truth_hvac.xlsx
│   └── ground_truth_shower.xlsx
├── Ground Truth Calculators/
│   ├── ApplianceGroundTruthCalculator.py
│   ├── HVACGroundTruthCalculator.py
│   └── ShowerGroundTruthCalculator.py
├── Miscellaneous Scripts/
│   ├── build_rag_index.py
│   ├── evaluate_architecture_metrics.py
│   ├── CreateRepresentativeSample.py
│   ├── EntropyWeights.py
│   ├── evaluate_parameter_extraction.py
│   ├── generate_baseline_table.py
│   ├── implied_weights.py
│   ├── merec_weights.py
│   ├── run_baseline_models.py
│   ├── run_benchmarks.py
│   ├── run_rag_ablation_experiments.py
│   ├── SensitivityAnalysis.py
│   └── sync_rag_ground_truth_scores.py
├── paper_pipeline/
│   ├── run_paper_pipeline.py
│   ├── analyze_benchmark_failures.py
│   ├── calculate_per_run_metrics.py
│   ├── duplication_rate_analysis.py
│   ├── generate_boxplot_tex.py
│   ├── generate_imputed_robustness_tables.py
│   ├── generate_paper_figures.py
│   ├── generate_paper_results_numbers.py
│   ├── generate_variance_plot_tex.py
│   └── generate_violin_plot_tex.py
├── Scenario Files/
│   ├── ConsolidatedforSimaltaneousediting.xlsx
│   ├── HVACScenarios.xlsx
│   ├── ApplianceScenarios.xlsx
│   ├── ShowerScenarios.xlsx
│   ├── HVACRagScenarios.xlsx
│   ├── ApplianceRAGScenarios.xlsx
│   ├── ShowerRAGScenarios.xlsx
│   ├── TestScenarios.xlsx
│   └── build_consolidated_scenario_workbooks.py
├── Scoring Logic and Documentation/
│   └── method/
├── Output Files GPT-OSS 20B/
├── Output Files Qwen3.5 9B/
├── Output Files DeepSeek V4 Flash/
├── Output Files Gemini 3.5 Flash/
├── Output Files/ (baselines)
├── paper/
├── chroma_rag_db/
├── tests/
├── model_config.py
├── sentinel_utils.py
├── README.md
├── CLAUDE.md
├── LICENSE
├── DATA_LICENSE
├── .env.example
└── requirements.txt
```

---

## Three Architectures

### 1. Pure Prompting (`Direct_LLM_Scoring.py`)

LLM scores all four criteria directly via calibrated system prompts with per-decision-type rubric guidance. Input is a natural language scenario description with structured context fields. Outputs four 0-1 scores per alternative, then ranks by MAVT.

- **API calls per scenario:** 3 (one per alternative)
- **API calls per run (195 scenarios):** 585
- **API calls per 5-run benchmark (4 models):** 11,700

### 2. RAG-Enhanced (`Example-Guided_LLM_Scoring.py`)

Semantic retrieval from a ChromaDB vector index (90 pre-scored RAG scenarios) provides a calibration exemplar before the LLM scores each alternative. Uses sentence-transformers (all-MiniLM-L6-v2) embeddings with k=1 retrieval (selected via ablation: k=1,3,5 are statistically indistinguishable on ranking accuracy, and k=1 minimizes cost).

- **API calls per scenario:** 3
- **API calls per run (195 scenarios):** 585
- **Vector DB:** ChromaDB with sentence-transformers embeddings

### 3. LLM-Parameterized_Reference_Scoring (`LLM-Parameterized_Reference_Scoring.py`)

LLM extracts structured engineering parameters (SEER tier, appliance age kWh/cycle, GPM estimate, R-value, tank size) from the natural-language description. A deterministic MAVT calculator then runs the physics formulas on all three alternatives.

- **API calls per scenario:** 1 (all three alternatives in one extraction call)
- **API calls per run (195 scenarios):** 195
- **Extraction-to-GT accuracy varies by model:** Gemini 3.5 Flash achieves 0% extraction failures; GPT-OSS 20B has 12.8% extraction failures on run 1 (recovered across multi-run averaging)

---

## Scenario Corpus

### Test vs. RAG Pools

The 195 test scenarios and 90 RAG scenarios are disjoint. All three architectures and the ground-truth calculator evaluate test scenarios. RAG scenarios seed only the ChromaDB retrieval index.

| Pool | HVAC | Appliance | Shower | Total |
| --- | --- | --- | --- | --- |
| Test set | 70 | 65 | 60 | **195** |
| RAG corpus | 35 | 35 | 20 | **90** |

### Parameter Generalization

The ground-truth calculators receive exact engineering values; architectures receive homeowner-accessible labels or infer parameters from context (consistent with Attari et al. 2010).

| Parameter | LLM Label | Calculator Value | Source |
| --- | --- | --- | --- |
| **HVAC - Insulation** | Poor / Medium / Good | R-11 / R-13 / R-19 | CEC JA4.3; ENERGY STAR |
| **Shower - Flow Rate** | low_flow / standard / high_flow | actual GPM from scenario | EPA WaterSense |
| **Appliance - Age** | 1-15 yr band | Dishwasher: 0.72-1.70 kWh/cycle; Washer: 0.15-0.45; Dryer: 1.15-3.50 | ENERGY STAR certified datasets |

The LLM never directly sees SEER ratings, exact R-values, GPM values, kWh/cycle figures, or occupancy-context flags.

---

## MAVT Framework

### Value Function

```
s_j = sum(w_i * v_i(x_ij))   for i in {energy_cost, environmental, comfort, practicality}
```

All four criterion scores are on a 0-1 scale before weighting.

### Reference Ranges (5th-95th percentile of scenario distributions)

| Criterion | HVAC | Appliance | Shower |
| --- | --- | --- | --- |
| Energy Cost ($) | $0.38 - $3.29 | $0.025 - $0.71 | $0.14 - $1.14 |
| Environmental Impact | 1.96 - 18.04 lbs CO2 | 0.288 - 3.643 lbs CO2 | 6.0 - 45.0 gal water |
| Comfort | 0.0 - 1.0 | 0.0 - 1.0 | 0.0 - 1.0 |
| Practicality | 0.05 - 1.0 | 0.05 - 1.0 | 0.05 - 1.0 |

Shower environmental impact is water volume (gallons). HVAC and Appliance environmental impact is lbs CO2 using PJM marginal emissions factors (peak 1.041 / off-peak 0.976 lbs CO2/kWh).

Reference ranges are anchored to 5th-95th percentiles of the actual scenario distributions.

### Budget Penalty

A four-tier multiplicative budget penalty applies to the post-value-function energy-cost score, where `u = monthly_cost / budget`:

| Utilization u | Penalty |
| --- | --- |
| u < 0.80 | 1.0 (no penalty) |
| 0.80 <= u < 1.00 | Linear decay: 1 - 2.5(u - 0.80) |
| 1.00 <= u < 1.50 | Exponential: 0.5 * e^{-3(u - 1.0)} |
| u >= 1.50 | 0 (eliminated) |

Behavioral anchors: mental budget safety margins (Thaler 1999); linear self-control (Heath & Soll 1996); exponential loss aversion (Prelec & Loewenstein 1998); infeasibility elimination (Gathergood 2012).

---

## Ground Truth Calculators

Each calculator takes a scenario with three alternatives and returns four scores per alternative (Energy Cost, Environmental, Comfort, Practicality) on a 0-1 scale, plus raw physical quantities before value-function transformation

### Emissions Factors

HVAC and Appliance environmental impact uses PJM marginal emissions factors (shifting a residential load displaces the generator at the margin, so marginal factors apply):

| Period | Factor |
| --- | --- |
| Peak (7am-11pm) | 1.041 lbs CO2/kWh |
| Off-peak | 0.976 lbs CO2/kWh |

### HVAC Calculator

Thermal load uses four ASHRAE-style components (conductive + internal + solar + ventilation). Energy consumption over the 8-hour decision window:

```
E_kWh = (Q_load / (EER_eff * 1000)) * 8 hr * m_occ
```

EER comes from rated SEER via the AHRI 210/240 quadratic (`EER = -0.02*SEER^2 + 1.12*SEER`). Occupancy modifier `m_occ` adjusts for occupancy (fully occupied = 1.0, overnight = 0.75, daytime unoccupied = `1 - 0.5*(h_away/24)`). Age/maintenance degradation only enters the practicality score (as a reliability factor), not the energy path.

Comfort uses a tent function peaking at ASHRAE 55 optimal setpoints (76 F cooling, 70 F heating).

### Appliance Calculator

Per-cycle energy cost: `C = E_cyc * r(t, l)` where `r` is the TOU rate for one of six Pennsylvania utilities (PECO, PPL, West Penn, Penelec, MetEd, Duquesne) resolved by location `l` and run-time `t`.

Comfort decays piecewise from 10 at zero delay, with appliance-specific tolerance ceilings (dishwashers 12 hr, washers 8 hr, dryers 6 hr), plus a late-night noise penalty (dBA > 45 and run time 10pm-7am) and household-size penalty. Delays use minimum circular distance on a 24-hour clock.

### Shower Calculator

Mains inlet temperature comes from outdoor temperature via interpolation (45 F at <=32 F outdoor, 65 F at >=75 F outdoor, NREL seasonal model). Hot-water fraction:

```
f_hot = (T_target - T_inlet) / (T_heater - T_inlet),   T_target = 105 F
```

Shower energy:

```
E_kWh = (GPM * f_hot * 8.33 * (T_heater - T_inlet) * duration_min) / (3412 * eta)
```

where eta = 0.92 (UEF for 40-55 gal electric tank). Environmental impact = GPM * duration (gallons of water used). Comfort peaks at the REU2016 average of 7.8 min with penalties for temperature adequacy (CDC Legionella thresholds) and household contention. Practicality penalizes alternatives that exhaust available tank capacity.

---

## Sensitivity Analysis

[SensitivityAnalysis.py](Miscellaneous%20Scripts/SensitivityAnalysis.py) still computes the ten single-criterion `+/-0.05` perturbation scenarios below plus an equal-weight scenario, but these are **no longer the reported robustness check in the paper**: they move the RAG-Enhanced minus Pure Prompting gap only within 0.179-0.225, a narrower range than the entropy- and MEREC-derived weight vectors reach (0.090 under the MEREC HVAC vector), so they cannot establish weight robustness on their own. They are retained here for completeness and are still exercised by the script.

| Scenario | w(EnergyCost) | w(Environmental) | w(Comfort) | w(Practicality) |
| --- | --- | --- | --- | --- |
| Baseline | 0.3000 | 0.3500 | 0.2000 | 0.1500 |
| Ene +0.05 | 0.3500 | 0.3333 | 0.1833 | 0.1333 |
| Ene -0.05 | 0.2500 | 0.3667 | 0.2167 | 0.1667 |
| Env +0.05 | 0.2833 | 0.4000 | 0.1833 | 0.1333 |
| Env -0.05 | 0.3167 | 0.3000 | 0.2167 | 0.1667 |
| Com +0.05 | 0.2833 | 0.3333 | 0.2500 | 0.1333 |
| Com -0.05 | 0.3167 | 0.3667 | 0.1500 | 0.1667 |
| Pra +0.05 | 0.2833 | 0.3333 | 0.1833 | 0.2000 |
| Pra -0.05 | 0.3167 | 0.3667 | 0.2167 | 0.1000 |
| Equal | 0.2500 | 0.2500 | 0.2500 | 0.2500 |

### What the paper actually reports

The reported sensitivity check reweights both the ground-truth ranking and the architecture rankings under the baseline, equal, and the entropy- and MEREC-derived vectors (see [Objective Weight Validation Scripts](#objective-weight-validation-scripts) below), applied pooled and per decision type, per model (never pooled across models — see `tab:sensitivity_by_model` in `paper/paper_draft_working.tex`).

- **LLM-Parameterized_Reference_Scoring's advantage over RAG-Enhanced is unconditional**: it holds in all 28 model x weight-vector cells tested, by a margin of at least 0.277 Kendall's tau.
- **RAG-Enhanced's advantage over Pure Prompting is conditional, not invariant.** It survives the design (baseline), equal, and entropy vectors in all four models. MEREC weights — which load heavily onto Comfort rather than cost and emissions — narrow the gap sharply and reverse it in three cells plus one exact tie: Gemini under the MEREC HVAC vector (Pure Prompting 0.682 vs. RAG-Enhanced 0.617), DeepSeek under MEREC HVAC (0.528 vs. 0.470) and MEREC per-type (0.456 vs. 0.419), and Gemini under MEREC pooled (an exact tie at 0.655). The RAG-Enhanced > Pure Prompting result should be read as conditional on a weighting that gives substantial mass to cost and emissions, which the design and entropy vectors do and MEREC does not.

This reversal was hidden by an earlier four-model-mean presentation of the same analysis; per the project's no-pooling-across-models convention (see `CLAUDE.md`), sensitivity results are reported per model.

---

## Objective Weight Validation Scripts

Two scripts independently validate the subjective MAVT weights against the ground-truth score distributions:

- **[EntropyWeights.py](Miscellaneous Scripts/EntropyWeights.py)** -- Shannon entropy weights overall and by decision type. The environmental criterion receives above-average entropy weight, independently supporting the 0.35 allocation.
- **[merec_weights.py](Miscellaneous Scripts/merec_weights.py)** -- Computes MEREC (Method based on Removal Effects of Criteria) weights per-scenario then averages them. MEREC is correlation-free and robust to nonlinearity, making it appropriate for comfort and practicality which use nonlinear value functions.

---

## Miscellaneous Scripts

| Script | Purpose |
| --- | --- |
| [build_rag_index.py](Miscellaneous Scripts/build_rag_index.py) | Builds/refreshes ChromaDB vector index from RAG scenario files (35 HVAC, 35 Appliance, 20 Shower). Computes SHA-256 of source files and stores schema version in collection metadata to detect when rebuild is needed. Current schema version: 4. |
| [evaluate_architecture_metrics.py](Miscellaneous Scripts/evaluate_architecture_metrics.py) | Computes Top-1/2 accuracy, Kendall's tau, Spearman rho, MAE, RMSE per architecture/model/decision-type. Aggregates multi-run results, filters sentinel 1928 failures, matches to ground truth. Outputs metrics_summary_{MODEL_KEY}.xlsx. |
| [CreateRepresentativeSample.py](Miscellaneous Scripts/CreateRepresentativeSample.py) | Drop-in replacement for run_rag_ablation_experiments.py's stratified_sample. Stratafies by key physics-driving parameters (housing type, insulation, flow rate) within each decision type for representative ablation samples. |
| [sync_rag_ground_truth_scores.py](Miscellaneous Scripts/sync_rag_ground_truth_scores.py) | Syncs updated ground truth scores back into RAG scenario workbooks after re-running ground truth calculators. Matches on descriptor columns. Run after calculator updates, then re-run build_rag_index.py. |
| [SensitivityAnalysis.py](Miscellaneous Scripts/SensitivityAnalysis.py) | Per model, reruns ranking metrics across the baseline, the 8 +/-0.05 perturbation scenarios, equal weights, and the entropy- and MEREC-derived objective weight vectors (pooled and per decision type). The paper reports only the baseline/equal/entropy/MEREC arms (see [Sensitivity Analysis](#sensitivity-analysis)); the +/-0.05 arms are still computed but not reported. Outputs sensitivity_analysis_{MODEL_KEY}.xlsx. |
| [EntropyWeights.py](Miscellaneous Scripts/EntropyWeights.py) | Computes Shannon entropy weights from ground-truth score distributions overall and by decision type. Outputs entropy_weights.xlsx. |
| [merec_weights.py](Miscellaneous Scripts/merec_weights.py) | Computes MEREC objective weights per-scenario then averages (not pooled). Outputs merec_weights_summary.xlsx. |
| [implied_weights.py](Miscellaneous Scripts/implied_weights.py) | Recovers implied weights from ground-truth ranking structure using pairwise constrained linear regression (w >= 0, sum(w) = 1). Outputs implied_weights_summary.xlsx. |
| [run_baseline_models.py](Miscellaneous Scripts/run_baseline_models.py) | Computes 5 non-LLM baselines + Oracle upper bound: Random (20 seeds), Uniform (all scores = 0.5), Fixed-Default (GT calculators with fixed default params), Nearest-Neighbor (k=3 retrieval from RAG), Oracle (true GT scores). Outputs to Output Files/Baselines/. |
| [run_rag_ablation_experiments.py](Miscellaneous Scripts/run_rag_ablation_experiments.py) | Runs 9 RAG retrieval/exemplar ablations on stratified sample (default 15 scenarios x 3 types): Control (k=3, scores+ranks+hidden params), Random exemplars, No exemplars, Descriptions without scores/ranks, Exemplars without hidden params, Retrieval k=1/k=5, Alternate embedding, Nearest-neighbor. Outputs summary tables, plots, and Markdown report. |
| [evaluate_parameter_extraction.py](Miscellaneous Scripts/evaluate_parameter_extraction.py) | Evaluates LLM-Parameterized_Reference_Scoring parameter extraction accuracy vs ground truth: numeric params (MAE/RMSE/percentiles), categorical params (accuracy), counterfactual top-1 sensitivity. Outputs LLM-Parameterized_Reference_Scoring_parameter_evaluation.md. |
| [generate_baseline_table.py](Miscellaneous Scripts/generate_baseline_table.py) | Reads metrics_summary_{MODEL_KEY}.xlsx and generates incremental contribution table comparing all 8 systems (5 baselines + 3 LLM architectures). Outputs console table, LaTeX, and CSV. Default baseline for deltas: FixedDefault. |

---

## Documentation

[Codebase Guide](docs/CODEBASE_GUIDE.md) | [Ablation Experiments](docs/EXPERIMENTS.md) | [Metrics Pipeline](docs/metrics_calculation_pipeline.md) | [XLSX Schema Map](XLSX_Schema_Map.md) | [Provenance Audit](docs/PROVENANCE_AUDIT_PROMPT.md)

[Notebook](Scoring%20Logic%20and%20Documentation/paper/Notebook.pdf) | [Evaluation Metrics](Scoring%20Logic%20and%20Documentation/method/Evaluation_Metric_Derivations.pdf) | [Budget Penalties](Scoring%20Logic%20and%20Documentation/method/Budget_Penalties.pdf) | [Reference Ranges](Scoring%20Logic%20and%20Documentation/method/Reference_Ranges_for_Value_Functions.pdf) | [Worked Calculator Examples](Scoring%20Logic%20and%20Documentation/method/Calculator_Examples.pdf)

---

## License

Code is released under the MIT License ([LICENSE](LICENSE)). The scenario workbooks, ground-truth scores, and benchmark outputs are released under CC BY 4.0 ([DATA_LICENSE](DATA_LICENSE)).

---

## Citation / Collaborator

This project is being developed into a journal paper with **Dr. River Huang (Paul Scherrer Institut, Switzerland)**.
