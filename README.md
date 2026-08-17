# LLM-MCDA: AI-Assisted Multi-Criteria Decision Analysis for Household Energy Optimization

**Author:** Ahaan Nigam
**Institution:** Downingtown East High School
**Collaborator:** River Huang, Paul Scherrer Institut (PSI), Switzerland
**Target Journal:** Environmental Modelling & Software

---

## Research Question

Which LLM-assisted architecture most accurately reproduces a deterministic ground-truth ranking for rapid household energy decisions, and how consistently does that ordering hold across models of varying capability and cost?

---

## Project Overview

This project benchmarks three LLM-MCDA architectures for household energy decision-making against a physics-based Multi-Attribute Value Theory (MAVT) ground-truth calculator, across **195 test scenarios** (70 HVAC, 65 Appliance, 60 Shower). Each scenario presents three alternatives scored on four criteria. A disjoint **90-scenario RAG corpus** (35 HVAC, 35 Appliance, 20 Shower) seeds the retrieval index used by the example-guided architecture and never appears in evaluation.

Four models are evaluated: Gemini 3.5 Flash, DeepSeek V4 Flash, GPT-OSS 20B, and Qwen 3.5 9B, each run at its lowest available reasoning tier. Each architecture--model pair runs 5 trials over the 195-scenario test set: 585 calls/run for the two architectures that score one alternative per call, 195 calls/run for the one that extracts once per scenario. Across all three architectures and four models, the main benchmark totals 27,300 API calls.

The three decision types were chosen for high behavioral plasticity and contribution to controllable residential energy/water use: HVAC (thermostat setpoints), Appliance (time-of-use scheduling), and Shower (duration).

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
# Build the ChromaDB retrieval index first -- required by the example-guided architecture,
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
| **Collecting the benchmark and ablations** | Yes | 27,300 calls for the main benchmark, plus the ablation suites (see [Ablation Suites](#ablation-suites)) | `Architectures/*.py`, `Miscellaneous Scripts/run_*_experiments.py`, `run_baseline_models.py` |
| **Everything analytical** | No | Free | `paper_pipeline/run_paper_pipeline.py` and everything it calls |

The per-run outputs for all four models are committed under the `Output Files */` folders, so every metric, table, figure, significance test, ablation summary, and sensitivity arm in the paper can be regenerated from a fresh clone with no key and no spending -- `pip install -r requirements.txt` followed by `python paper_pipeline/run_paper_pipeline.py`. Re-collecting the benchmark is only necessary to change the model set, the scenario data, or a prompt.

Ground-truth scores are likewise reproducible offline: running a calculator in `Ground Truth Calculators/` directly regenerates its `Ground Truth/ground_truth_*.xlsx` from the scenario workbooks. If you change a calculator or the scenario data, see the refresh-order rules in [CLAUDE.md](CLAUDE.md) -- `build_rag_index.py` always runs last.

---

## MAVT Criterion Weights

Weights are constant across all decision types, architectures, and the ground-truth calculator. Score differences reflect input and value-function fidelity, not a difference in how criteria are weighted per decision type.

| Criterion | Weight | Justification |
| --- | --- | --- |
| Environmental Impact | 35% | VBN theory identifies environmental orientation as the most consistent normative driver of pro-environmental household behavior; entropy-based normalization independently assigns it above-average weight |
| Energy Cost | 30% | Strongest independent predictor of consumer adoption; households underestimate energy use by roughly 2.8x on average (Attari et al., 2010) |
| Comfort | 20% | Dominant driver of HVAC behavior even when it conflicts with energy savings; ASHRAE 55 provides a physically interpretable anchor |
| Practicality | 15% | Constraint on feasibility and long-term adoption |

A sensitivity analysis confirms the LLM-Parameterized architecture's advantage over the example-guided one is unconditional across every weight vector tested. The example-guided architecture's advantage over direct prompting holds under baseline, equal, and entropy-derived weights but narrows -- and reverses for one model -- under MEREC-derived weights, which load heavily onto Comfort rather than cost and emissions (see [Sensitivity Analysis](#sensitivity-analysis) below).

---

## Results Summary

The LLM-Parameterized architecture dominates across all four models (Kendall's tau 0.880--0.923, Top-1 89.7--93.1%). The example-guided architecture ranks second (tau 0.208--0.310). Direct prompting ranks third, near-random on HVAC and Appliance (tau 0.010--0.176 overall).

### Overall Metrics (5-run mean, 195 scenarios)

| Model | Architecture | Kendall's tau | Top-1 Acc | RMSE | MAE |
| --- | --- | --- | --- | --- | --- |
| **Gemini 3.5 Flash** | LLM-Parameterized | **0.923** | **93.1%** | **0.101** | **0.048** |
| | Example-Guided | 0.310 | 48.7% | 0.231 | 0.158 |
| | Direct Prompting | 0.176 | 36.2% | 0.295 | 0.219 |
| **DeepSeek V4 Flash** | LLM-Parameterized | **0.897** | **90.8%** | **0.092** | **0.045** |
| | Example-Guided | 0.307 | 53.5% | 0.237 | 0.168 |
| | Direct Prompting | 0.144 | 36.7% | 0.302 | 0.231 |
| **GPT-OSS 20B** | LLM-Parameterized | **0.897** | **91.7%** | **0.101** | **0.052** |
| | Example-Guided | 0.272 | 47.4% | 0.242 | 0.169 |
| | Direct Prompting | 0.041 | 33.3% | 0.306 | 0.241 |
| **Qwen 3.5 9B** | LLM-Parameterized | **0.880** | **89.7%** | **0.162** | **0.072** |
| | Example-Guided | 0.208 | 46.6% | 0.261 | 0.194 |
| | Direct Prompting | 0.010 | 30.0% | 0.295 | 0.235 |

Across models, the LLM-Parameterized architecture's tau spans only 0.043 despite a 45x difference in per-token cost between the cheapest and most expensive model, versus 0.166 for direct prompting -- architecture design matters more than model choice.

### By Decision Type (best/worst model per cell, 5-run mean)

| Decision Type | Direct Prompting tau | Example-Guided tau | LLM-Parameterized tau |
| --- | --- | --- | --- |
| HVAC | -0.102 (DeepSeek) to 0.135 (GPT-OSS) | -0.116 (Gemini) to 0.265 (GPT-OSS) | 0.881 (Qwen) to 0.977 (Gemini) |
| Appliance | -0.147 (GPT-OSS) to 0.029 (DeepSeek) | -0.048 (GPT-OSS) to 0.417 (DeepSeek) | 0.906 (Qwen) to 0.975 (DeepSeek) |
| Shower | 0.069 (Qwen) to 0.633 (Gemini) | 0.240 (Qwen) to 0.767 (Gemini) | 0.787 (GPT-OSS, tied with DeepSeek) to 0.851 (Qwen) |

HVAC is the highest-dimensional task (insulation, SEER, age, occupancy, square footage, outdoor temperature) and shows the widest gap between the LLM-Parameterized and example-guided architectures. Shower is the lowest-dimensional and shows the narrowest gap, because a single well-estimated parameter (flow rate) can carry the ranking on its own.

### Key Findings

- **Calculator access alone is not enough.** Running the same ground-truth calculator on corpus-median parameters instead of LLM-extracted ones reaches only tau = 0.641 -- well above chance, but far below the LLM-Parameterized architecture's 0.880--0.923. LLM extraction itself accounts for 0.24--0.28 of the architecture's tau advantage; the calculator alone is not sufficient.
- **Extraction errors mostly cancel in ranking, not in score error.** Because the LLM estimates scenario-level parameters that enter every alternative identically, an error shifts the whole choice set rather than reordering it, so ranking accuracy is far more robust to weak extraction than absolute score error is. The one consistent exception is shower flow rate (GPM), which multiplies against each alternative's own duration rather than scaling all three by a common amount -- it carries the highest top-1 flip probability of any extracted parameter for every model.
- **A non-LLM baseline rules out "the benchmark just rewards calculator access."** A Fixed-Default baseline (calculator run on constant, non-inferred parameters) reaches a per-type tau of 0.610 but collapses on Appliance (tau = 0.097), since a fixed run time can't track a household's actual schedule -- well below every LLM architecture's floor. Separately, an offline Nearest-Neighbor baseline (directly assigning a retrieved RAG scenario's scores, no LLM call, leave-one-out on the 90-scenario RAG corpus) reaches tau = 0.001, indistinguishable from random ranking.
- **In the RAG ablation, exemplar scores matter more than exemplar content.** Removing the ground-truth scores from retrieved exemplars degrades ranking far more than removing their hidden engineering parameters (R-value, SEER, GPM, etc.) -- scored exemplars anchor the LLM's output scale, they don't teach it new physics.
- **Reversing alternative order in the prompt changed what two of four models extracted, but never changed which alternative any model ranked first** -- a null result at the ranking layer that only means something because the same perturbation is detectably present one layer up, at the LLM's parameter estimates.
- **Model capability correlates weakly with architecture ranking.** The cheapest model (GPT-OSS 20B, $0.029/M input tokens) achieves comparable LLM-Parameterized performance to the most expensive (Gemini 3.5 Flash, $1.50/M) -- but see the [Limitations](paper/paper_draft_working.tex) section of the paper: all four models are run at their lowest reasoning tier, so this claim is scoped to that regime, not to frontier or reasoning-enabled models.
- **Failure rates are near-zero** across all architectures and models, with one exception: GPT-OSS 20B on the LLM-Parameterized architecture has a 12.0% per-scenario-run extraction failure rate (88.0% success), concentrated in HVAC scenarios where an extracted parameter falls outside its physical validation bounds. Cross-run recovery and per-run imputation both confirm the architecture ordering is unaffected.

### API Costs (per 5-run benchmark)

| Architecture | Calls/run | Gemini | DeepSeek | GPT-OSS | Qwen |
| --- | --- | --- | --- | --- | --- |
| Direct Prompting | 585 | ~$4.01 | ~$0.44 | ~$0.12 | ~$0.22 |
| Example-Guided | 585 | ~$5.12 | ~$0.18 | ~$0.12 | ~$0.21 |
| LLM-Parameterized | 195 | ~$1.40 | ~$0.06 | ~$0.03 | ~$0.06 |

Priced at OpenRouter list rates as of August 1, 2026. The LLM-Parameterized architecture costs 2.9--7.9x less than direct prompting and 3.3--3.8x less than the example-guided architecture on the same model, from issuing one API call per scenario instead of three.

---

### Imputation Robustness Test

Per-run imputed robustness is computed via [paper_pipeline/generate_imputed_robustness_tables.py](paper_pipeline/generate_imputed_robustness_tables.py), which evaluates each run independently after replacing sentinel 1928 scores with 0.5 (scale midpoint) before MAVT ranking and metric averaging. Output is written to [Analysis/MetricsSummary/metrics_summary_all_models_imputed_perrun.xlsx](Analysis/MetricsSummary/metrics_summary_all_models_imputed_perrun.xlsx).

---

## Model Set

Set `MODEL_KEY` and `N_RUNS` in [model_config.py](model_config.py) to control model selection and output routing.

| Key | Label | OpenRouter string | Reasoning effort | Output folder |
| --- | --- | --- | --- | --- |
| `gptoss` | GPT-OSS-20B | `openai/gpt-oss-20b:exacto` | low | `Output Files GPT-OSS 20B` |
| `qwen` | Qwen 3.5 9B | `qwen/qwen3.5-9b:exacto` | none | `Output Files Qwen3.5 9B` |
| `deepseek` | DeepSeek V4 Flash | `deepseek/deepseek-v4-flash:exacto` | none | `Output Files DeepSeek V4 Flash` |
| `gemini` | Gemini 3.5 Flash | `google/gemini-3.5-flash:exacto` | minimal | `Output Files Gemini 3.5 Flash` |

Model pricing (as of benchmark date): GPT-OSS $0.029/M in / $0.14/M out; Qwen $0.10/M / $0.15/M; DeepSeek $0.09/M / $0.18/M; Gemini $1.50/M / $9/M. All four are run at their lowest available reasoning tier; no reasoning-enabled or frontier-tier model is part of the reported benchmark.

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
│   ├── evaluate_baseline_metrics.py
│   ├── run_baseline_models.py
│   ├── run_benchmarks.py
│   ├── run_rag_ablation_experiments.py
│   ├── run_prompt_ablation_experiments.py
│   ├── run_hybrid_ablation_experiments.py
│   ├── run_position_bias_control.py
│   ├── significance_testing.py
│   ├── compute_confidence_intervals.py
│   ├── EntropyWeights.py
│   ├── merec_weights.py
│   ├── implied_weights.py
│   ├── sync_rag_ground_truth_scores.py
│   └── ... (see Miscellaneous Scripts table below for the rest)
├── paper_pipeline/
│   ├── run_paper_pipeline.py
│   ├── analyze_benchmark_failures.py
│   ├── calculate_per_run_metrics.py
│   ├── generate_paper_figures.py
│   ├── generate_paper_results_numbers.py
│   ├── generate_imputed_robustness_tables.py
│   └── ... (see paper_pipeline/ for the full stage list)
├── Scenario Files/
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
├── Analysis/
├── paper/
├── chroma_rag_db/
├── tests/
├── docs/
├── model_config.py
├── sentinel_utils.py
├── README.md
├── CLAUDE.md
├── LICENSE
├── DATA_LICENSE
├── CITATION.cff
├── SECURITY.md
├── .env.example
└── requirements.txt
```

---

## Three Architectures

The paper refers to these as A_D, A_E, and A_H respectively.

### 1. Direct Prompting (`Direct_LLM_Scoring.py`)

LLM scores all four criteria directly via calibrated system prompts with per-decision-type qualitative anchors (a good/moderate/poor description of each criterion, not numeric targets). Input is a natural-language scenario description with structured context fields. Outputs four 0--1 scores per alternative, then ranks by MAVT.

- **API calls per scenario:** 3 (one per alternative, deliberately, so the model scores each alternative on an absolute scale rather than ranking them against each other)
- **API calls per run (195 scenarios):** 585
- **API calls per 5-run benchmark (4 models):** 11,700

### 2. Example-Guided LLM Scoring (`Example-Guided_LLM_Scoring.py`)

Retrieval from a ChromaDB vector index (90 pre-scored RAG scenarios) supplies one worked exemplar -- its household-reported parameters, engineering parameters, and all four ground-truth criterion scores plus MAVT rank -- before the LLM scores each alternative. Uses sentence-transformers (all-MiniLM-L6-v2) embeddings with k=1 retrieval by default (selected via ablation: k=1, 3, and 5 are statistically indistinguishable on ranking accuracy for three of four models, and k=1 minimizes token and API cost).

- **API calls per scenario:** 3
- **API calls per run (195 scenarios):** 585
- **Vector DB:** ChromaDB (Euclidean/L2 distance, the library default) with sentence-transformers embeddings

### 3. LLM-Parameterized Reference Scoring (`LLM-Parameterized_Reference_Scoring.py`)

A single LLM call extracts the withheld engineering parameters (R-value, SEER, HVAC age, kWh/cycle, GPM, tank size, water-heater setpoint) from the natural-language scenario description. A deterministic MAVT calculator -- the same one that generated the ground truth -- then scores all three alternatives from those extracted values plus the parameters already known from the scenario sheet.

- **API calls per scenario:** 1 (all three alternatives scored by the calculator from one extraction call)
- **API calls per run (195 scenarios):** 195
- **Extraction reliability varies by model:** Gemini, DeepSeek, and Qwen have near-zero extraction failures; GPT-OSS 20B has a 12.0% per-scenario-run failure rate, concentrated in HVAC, recovered almost entirely across the 5-run average

---

## Scenario Corpus

### Test vs. RAG Pools

The 195 test scenarios and 90 RAG scenarios are disjoint: no test scenario shares an identical parameter signature with a retrieval-index entry. All three architectures and the ground-truth calculator evaluate test scenarios. RAG scenarios seed only the ChromaDB retrieval index.

| Pool | HVAC | Appliance | Shower | Total |
| --- | --- | --- | --- | --- |
| Test set | 70 | 65 | 60 | **195** |
| RAG corpus | 35 | 35 | 20 | **90** |

### Parameter Generalization

The ground-truth calculators receive exact engineering values; architectures receive homeowner-accessible labels or infer parameters from context (consistent with Attari et al., 2010, on what a homeowner can realistically report).

| Parameter | LLM Label | Calculator Value | Source |
| --- | --- | --- | --- |
| **HVAC - Insulation** | Poor / Medium / Good | R-11 / R-13 / R-19 | CEC JA4.3; ENERGY STAR |
| **Shower - Flow Rate** | low_flow / standard / high_flow | actual GPM from scenario | EPA WaterSense |
| **Appliance - Age** | banded age label | true age in years -> kWh/cycle | ENERGY STAR certified datasets |

The LLM never directly sees SEER ratings, exact R-values, GPM values, kWh/cycle figures, or occupancy-context flags. Bands are computed by single-source helpers in `sentinel_utils.py` so the test-sheet label and the RAG-index embedding string stay byte-identical.

---

## MAVT Framework

### Value Function

```
s_j = sum(w_i * v_i(x_ij))   for i in {energy_cost, environmental, comfort, practicality}
```

All four criterion scores are on a 0--1 scale before weighting. Energy cost and environmental impact use a linear value function; comfort and practicality use a logarithmic one (shape parameter alpha = 1.5 and 1.2 respectively) to capture diminishing marginal returns near an already-acceptable outcome.

### Reference Ranges (5th-95th percentile of scenario distributions)

| Criterion | HVAC | Appliance | Shower |
| --- | --- | --- | --- |
| Energy Cost ($) | $0.38 - $3.29 | $0.025 - $0.71 | $0.14 - $1.14 |
| Environmental Impact | 1.96 - 18.04 lbs CO2 | 0.288 - 3.643 lbs CO2 | 6.0 - 45.0 gal water |
| Comfort | 0.0 - 1.0 | 0.0 - 1.0 | 0.0 - 1.0 |
| Practicality | 0.05 - 1.0 | 0.05 - 1.0 | 0.05 - 1.0 |

Shower environmental impact is water volume (gallons), not CO2 -- chosen because it's the major environmental footprint of showering, but it means cross-type comparisons of environmental MAE should account for the unit difference. HVAC and Appliance environmental impact is lbs CO2 using PJM marginal emissions factors (peak 1.041 / off-peak 0.976 lbs CO2/kWh), not eGRID averages, to avoid collinearity with energy cost.

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

Each calculator takes a scenario with three alternatives and returns four scores per alternative (Energy Cost, Environmental, Comfort, Practicality) on a 0--1 scale, plus raw physical quantities before value-function transformation.

### Emissions Factors

HVAC and Appliance environmental impact uses PJM marginal emissions factors (shifting a residential load displaces the generator at the margin, so marginal factors apply, not grid-average ones):

| Period | Factor |
| --- | --- |
| Peak (7am-11pm) | 1.041 lbs CO2/kWh |
| Off-peak | 0.976 lbs CO2/kWh |

### HVAC Calculator

Thermal load uses a four-component ASHRAE-style balance (conductive + infiltration + internal-gain + solar, with a housing-type envelope multiplier). Energy consumption over the 8-hour decision window:

```
E_kWh = (Q_load / (EER_eff * 1000)) * 8 hr * m_occ
```

EER comes from rated SEER via the AHRI 210/240 quadratic (`EER = -0.02*SEER^2 + 1.12*SEER`), applied identically whether the scenario is in heating or cooling mode -- the calculator has no separate heating-fuel-type field. Occupancy modifier `m_occ` adjusts for occupancy (fully occupied = 1.0, overnight = 0.75, daytime unoccupied = `1 - 0.5*(h_away/24)`). Age/maintenance degradation enters only the practicality score (as a reliability factor), not the energy path.

Comfort uses a tent function peaking at ASHRAE 55 optimal setpoints (76 F cooling, 70 F heating).

### Appliance Calculator

Per-cycle energy cost: `C = E_cyc * r(t, l)` where `r` is the TOU rate for one of six Pennsylvania utilities (PECO, PPL, West Penn, Penelec, MetEd, Duquesne) resolved by location `l` and run-time `t`. The PJM emissions window (7am-11pm) applies regardless of the utility's own billing window, since emissions follow the regional grid rather than the bill.

Comfort decays piecewise from delay and appliance type, with appliance-specific tolerance ceilings, plus a late-night noise penalty (rated dBA > 45 and run time 10pm-7am, scaled by housing type) and a household-size penalty. Practicality follows the same delay and timing-complexity structure.

### Shower Calculator

Mains inlet temperature is interpolated from outdoor temperature (45 F winter to 65 F summer, NREL seasonal model). Hot-water mixing fraction targets a fixed 105 F delivery temperature:

```
f_hot = (T_target - T_inlet) / (T_heater - T_inlet),   T_target = 105 F
```

Shower energy:

```
E_kWh = (GPM * f_hot * 8.33 * (T_heater - T_inlet) * duration_min) / (3412 * eta)
```

where eta = 0.92 (electric water-heater efficiency). Because `f_hot` and the temperature rise move inversely, energy depends on inlet temperature but not on heater setpoint, for any setpoint at or above the delivery target. Environmental impact = GPM * duration (gallons of water used). Comfort peaks near the REU2016 average duration with penalties for temperature adequacy (CDC Legionella/scald thresholds) and household contention. Practicality penalizes alternatives that exhaust available tank capacity, using a fixed 0.8 tank-availability factor.

---

## Sensitivity Analysis

[SensitivityAnalysis.py](Miscellaneous%20Scripts/SensitivityAnalysis.py) still computes ten single-criterion `+/-0.05` perturbation scenarios plus an equal-weight scenario, but these are **not the reported robustness check in the paper**: they move the example-guided-minus-direct-prompting gap only within a narrow range across the four models, narrower than the entropy- and MEREC-derived weight vectors reach, so they cannot establish weight robustness on their own. They are retained here for completeness and are still exercised by the script.

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

The reported sensitivity check reweights both the ground-truth ranking and the architecture rankings under the baseline, equal, and the entropy- and MEREC-derived vectors (see [Objective Weight Validation Scripts](#objective-weight-validation-scripts) below), applied pooled and per decision type, per model (never pooled across models -- see the no-pooling convention in `CLAUDE.md`).

- **The LLM-Parameterized architecture's advantage over the example-guided one is unconditional**: it holds in all 28 model x weight-vector cells tested, by a margin of at least 0.304 Kendall's tau.
- **The example-guided architecture's advantage over direct prompting is conditional, not invariant.** It survives the design (baseline), equal, and entropy vectors in all four models. MEREC weights -- which load heavily onto Comfort (0.663 for HVAC against the design's 0.200) rather than cost and emissions -- narrow the gap and reverse it for Gemini in two of the 28 cells: the MEREC HVAC vector (direct prompting 0.676 vs. example-guided 0.600) and the MEREC pooled vector (0.655 vs. 0.632). The example-guided architecture's advantage should be read as conditional on a weighting that gives substantial mass to cost and emissions, which the design and entropy vectors do and MEREC does not.

Per the project's no-pooling-across-models convention (see `CLAUDE.md`), sensitivity results are reported and should be read per model, not as a four-model mean.

---

## Ablation Suites

Three ablation suites, run on top of the main benchmark, test whether the reported architecture ordering depends on design choices inside the architectures rather than on the architectures themselves. All three cover the same four models and use a Holm-corrected nonparametric protocol within each model (never pooled across models). Full methodology and results are in `paper/paper_draft_working.tex` (Sections 3.9 and 5) and `docs/EXPERIMENTS.md`.

- **Prompt-sensitivity ablation** (`run_prompt_ablation_experiments.py`, `test_prompt_ablation_significance.py`, `AggregatePromptAblations.py`) -- reruns direct prompting and the example-guided architecture under three prompt perturbations (removing scoring anchors, adding a chain-of-thought scaffold, rescaling the 0--1 response range to 0--10) on the full 195-scenario test set. The architecture ordering survives every variant.
- **RAG ablation** (`run_rag_ablation_experiments.py`, `compare_retrieval_k_bootstrap_ci.py`, `measure_rag_retrieval_distance.py`) -- runs on the 90-scenario RAG corpus under leave-one-out retrieval, varying retrieval depth (k=1, 3, 5), the embedding model, and what the retrieved exemplar exposes (scores, ranks, hidden engineering parameters). Removing exemplar scores hurts far more than removing hidden parameters.
- **Parameter-provenance ablation** (`run_hybrid_ablation_experiments.py`, `test_hybrid_ablation_significance.py`) -- isolates how much of the LLM-Parameterized architecture's accuracy comes from LLM extraction versus the calculator alone, by comparing LLM-extracted parameters against a fixed corpus-median parameter set (floor) on the same 195 test scenarios. No new API calls; re-derives results from files already on disk.
- **Alternative-ordering test** (`run_position_bias_control.py`, `aggregate_position_bias_results.py`) -- reverses the order alternatives are listed in the prompt/extraction call and re-scores all 195 test scenarios, using an exact permutation test for the LLM-Parameterized architecture's extraction layer. Tests whether the reported ranking is sensitive to positional framing rather than to the alternatives themselves.

---

## Objective Weight Validation Scripts

Three scripts independently validate the subjective MAVT weights against the ground-truth score distributions. They are **validation only**: no architecture or calculator imports them or changes weights at runtime.

- **[EntropyWeights.py](Miscellaneous Scripts/EntropyWeights.py)** -- Shannon entropy weights overall and by decision type. The environmental criterion receives above-average entropy weight, independently supporting the 0.35 allocation.
- **[merec_weights.py](Miscellaneous Scripts/merec_weights.py)** -- Computes MEREC (Method based on Removal Effects of Criteria) weights per-scenario then averages them. MEREC is correlation-free and robust to nonlinearity, making it informative for comfort and practicality, which use nonlinear value functions.
- **[implied_weights.py](Miscellaneous Scripts/implied_weights.py)** -- Recovers implied weights from the ground-truth ranking structure via constrained least squares on pairwise alternative comparisons. Collapses to single-criterion corner solutions for HVAC and Appliance, because those decision types' cost/environmental criteria have no within-scenario variance left to discriminate on once the dominant criterion is factored out -- a property of the calculator's structure, not evidence that those criteria are unimportant.

---

## Miscellaneous Scripts

| Script | Purpose |
| --- | --- |
| [build_rag_index.py](Miscellaneous Scripts/build_rag_index.py) | Builds/refreshes the ChromaDB vector index from the RAG scenario files. Computes SHA-256 of source files and stores a schema version in collection metadata to detect when a rebuild is needed. Current schema version: 4. |
| [evaluate_architecture_metrics.py](Miscellaneous Scripts/evaluate_architecture_metrics.py) | Computes Top-1/2 accuracy, Kendall's tau, MAE, RMSE per architecture/model/decision-type. Aggregates multi-run results, filters sentinel 1928 failures, matches to ground truth. Outputs `metrics_summary_{MODEL_KEY}.xlsx`. |
| [evaluate_baseline_metrics.py](Miscellaneous Scripts/evaluate_baseline_metrics.py) | Same metric computation as above, applied to the non-LLM baseline outputs in `Output Files/Baselines/`. |
| [run_baseline_models.py](Miscellaneous Scripts/run_baseline_models.py) | Computes the non-LLM baselines used in the incremental-contribution table: Fixed-Default (calculator on constant parameters) and Nearest-Neighbor (k=3 retrieval from the RAG corpus, no LLM call). Outputs to `Output Files/Baselines/`. |
| [run_rag_ablation_experiments.py](Miscellaneous Scripts/run_rag_ablation_experiments.py) | Runs the RAG retrieval/exemplar-content ablation configurations described above. Outputs summary tables and a Markdown report. |
| [compare_retrieval_k_bootstrap_ci.py](Miscellaneous Scripts/compare_retrieval_k_bootstrap_ci.py) | Percentile-bootstrap confidence intervals on the k=1-minus-k=3 Kendall's tau difference, per model, from the RAG ablation output. |
| [measure_rag_retrieval_distance.py](Miscellaneous Scripts/measure_rag_retrieval_distance.py) | Computes nearest-neighbor vs. random-draw embedding distances between Test and RAG-corpus scenarios, used to characterize how tightly the retrieval index actually separates a good match from a random one. |
| [run_prompt_ablation_experiments.py](Miscellaneous Scripts/run_prompt_ablation_experiments.py) | Runs the prompt-sensitivity ablation (no-anchors, chain-of-thought scaffold, 0--10 rescale) for direct prompting and the example-guided architecture across all four models. |
| [test_prompt_ablation_significance.py](Miscellaneous Scripts/test_prompt_ablation_significance.py) / [AggregatePromptAblations.py](Miscellaneous Scripts/AggregatePromptAblations.py) | Holm-corrected Friedman/Wilcoxon significance testing and aggregation for the prompt ablation. |
| [run_hybrid_ablation_experiments.py](Miscellaneous Scripts/run_hybrid_ablation_experiments.py) | Runs the parameter-provenance ablation (extracted / corpus-median parameters) for the LLM-Parameterized architecture. Re-derives from existing result files; no new API calls. |
| [test_hybrid_ablation_significance.py](Miscellaneous Scripts/test_hybrid_ablation_significance.py) | Significance testing for the parameter-provenance ablation. |
| [run_position_bias_control.py](Miscellaneous Scripts/run_position_bias_control.py) / [aggregate_position_bias_results.py](Miscellaneous Scripts/aggregate_position_bias_results.py) | Runs and aggregates the alternative-ordering (position-bias) test, including the exact permutation test on the LLM-Parameterized architecture's extraction layer. |
| [significance_testing.py](Miscellaneous Scripts/significance_testing.py) / [compute_confidence_intervals.py](Miscellaneous Scripts/compute_confidence_intervals.py) | Shared Holm-corrected Friedman/Wilcoxon and percentile-bootstrap CI utilities used across the ablation suites. |
| [SensitivityAnalysis.py](Miscellaneous Scripts/SensitivityAnalysis.py) | Per model, reruns ranking metrics across the baseline, the 8 +/-0.05 perturbation scenarios, equal weights, and the entropy- and MEREC-derived objective weight vectors (pooled and per decision type). The paper reports only the baseline/equal/entropy/MEREC arms (see [Sensitivity Analysis](#sensitivity-analysis)); the +/-0.05 arms are still computed but not reported. Outputs `sensitivity_analysis_{MODEL_KEY}.xlsx`. |
| [WeightDiagnostics.py](Miscellaneous Scripts/WeightDiagnostics.py) | Diagnostic breakdown of within-scenario criterion dispersion and zero-variance rates by decision type, feeding the implied-weights corner-solution discussion. |
| [EntropyWeights.py](Miscellaneous Scripts/EntropyWeights.py) | Computes Shannon entropy weights from ground-truth score distributions overall and by decision type. Outputs `entropy_weights.xlsx`. |
| [merec_weights.py](Miscellaneous Scripts/merec_weights.py) | Computes MEREC objective weights per-scenario then averages (not pooled). Outputs `merec_weights_summary.xlsx`. |
| [implied_weights.py](Miscellaneous Scripts/implied_weights.py) | Recovers implied weights from ground-truth ranking structure using pairwise constrained linear regression (w >= 0, sum(w) = 1). Outputs `implied_weights_summary.xlsx`. |
| [evaluate_parameter_extraction.py](Miscellaneous Scripts/evaluate_parameter_extraction.py) | Evaluates the LLM-Parameterized architecture's parameter extraction accuracy vs. ground truth: numeric params (MAE/RMSE/percentiles), categorical params (accuracy), counterfactual top-1 sensitivity. |
| [generate_baseline_table.py](Miscellaneous Scripts/generate_baseline_table.py) | Reads `metrics_summary_{MODEL_KEY}.xlsx` and generates the incremental-contribution table comparing the LLM architectures against the non-LLM baselines. Outputs console table, LaTeX, and CSV. |
| [sync_rag_ground_truth_scores.py](Miscellaneous Scripts/sync_rag_ground_truth_scores.py) | Syncs updated ground-truth scores back into the RAG scenario workbooks after re-running a ground-truth calculator. Matches on descriptor columns, time-aware for Appliance. Run after calculator updates, then re-run `build_rag_index.py`. |
| [CreateRepresentativeSample.py](Miscellaneous Scripts/CreateRepresentativeSample.py) | Stratifies by key physics-driving parameters (housing type, insulation, flow rate) within each decision type for representative ablation sampling. |

For full per-experiment methodology (exact prompt variants, permutation counts, run-count decisions), see [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

---

## Documentation

[Codebase Guide](docs/CODEBASE_GUIDE.md) | [Ablation Experiments](docs/EXPERIMENTS.md) | [Metrics Pipeline](docs/metrics_calculation_pipeline.md) | [XLSX Schema Map](XLSX_Schema_Map.md) | [Provenance Audit](docs/PROVENANCE_AUDIT_PROMPT.md)

[Notebook](Scoring%20Logic%20and%20Documentation/paper/Notebook.pdf) | [Evaluation Metrics](Scoring%20Logic%20and%20Documentation/method/Evaluation_Metric_Derivations.pdf) | [Budget Penalties](Scoring%20Logic%20and%20Documentation/method/Budget_Penalties.pdf) | [Reference Ranges](Scoring%20Logic%20and%20Documentation/method/Reference_Ranges_for_Value_Functions.pdf) | [Worked Calculator Examples](Scoring%20Logic%20and%20Documentation/method/Calculator_Examples.pdf)

---

## License

Code is released under the MIT License ([LICENSE](LICENSE)). The scenario workbooks, ground-truth scores, and benchmark outputs are released under CC BY 4.0 ([DATA_LICENSE](DATA_LICENSE)).

---

## Citation / Collaborator

This project is being developed into a journal paper with **River Huang (Paul Scherrer Institut, Switzerland)**, targeting *Environmental Modelling & Software*.
