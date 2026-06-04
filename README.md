# LLM-MCDA: AI-Assisted Multi-Criteria Decision Analysis for Household Energy Optimization

**Author:** Ahaan Nigam  
**Institution:** Downingtown East High School  
**Collaborator:** Dr. River Huang, Paul Scherrer Institut (PSI), Switzerland  
**Target Journal:** Decision Support Systems

---

## Research Question

Which LLM integration architecture most accurately replicates physics-based MAVT ground truth for household energy decisions, while maintaining acceptable failure rates and API costs?

---

## Project Overview

This project benchmarks three LLM-MCDA architectures for household energy decision-making against a physics-based Multi-Attribute Value Theory (MAVT) ground truth calculator across **185 test scenarios** (69 HVAC, 62 Appliance, 54 Shower). Each scenario presents three alternatives scored on four criteria. A disjoint **240-scenario RAG corpus** (105 HVAC, 90 Appliance, 45 Shower) seeds the retrieval index used by the RAG-Enhanced architecture and never appears in evaluation.

The three decision types were selected for their high behavioral plasticity and contribution to residential energy/water use: HVAC (thermostat setpoints), Appliance (time-of-use scheduling), and Shower (duration).

> **Note on quantitative results:** Multi-model benchmark runs are in progress. Accuracy metrics (Top-1, Kendall's τ, MAE, token counts, latencies) are not reported here pending a corrected multi-model run; placeholder values from earlier runs have been removed to avoid citing stale numbers.

---

## MAVT Criterion Weights

Weights are held constant across all decision types, all architectures, and the ground-truth calculator so that score differences reflect input and value-function fidelity rather than criterion framing.

| Criterion | Weight | Justification summary |
| --- | --- | --- |
| Environmental Impact | 35% | VBN theory identifies environmental orientation as the most consistent normative driver of pro-environmental household behavior; entropy-based normalization independently assigns it above-average information weight |
| Energy Cost | 30% | Strongest independent predictor of consumer adoption; households underestimate energy use by ~2.8× on average (Attari et al., 2010), making explicit cost feedback essential |
| Comfort | 20% | Dominant driver of HVAC behavior even when it conflicts with energy savings; ASHRAE 55 provides a physically interpretable anchor |
| Practicality | 15% | Constraint on feasibility and long-term adoption rather than a primary preference; weighted below comfort to reflect that role |

A sensitivity analysis confirms architecture ordering is stable under ±0.05 perturbations to each criterion weight (see [Sensitivity Analysis](#sensitivity-analysis) below).

---

## Model Set

Model selection and output routing are controlled in [model_config.py](model_config.py).

| Key | Label | OpenRouter string | Reasoning effort | Output folder |
| --- | --- | --- | --- | --- |
| `gptoss_smallest` | Smallest — GPT-OSS-20B | `openai/gpt-oss-20b:exacto` | low | `Output Files GPT-OSS 20B` |
| `qwen_small` | Small — Qwen 3.5 9B | `qwen/qwen3.5-9b:exacto` | low | `Output Files Qwen3.5 9B` |
| `deepseek_medium` | Medium — DeepSeek V4 Flash | `deepseek/deepseek-v4-flash:exacto` | minimal | `Output Files DeepSeek V4 Flash` |
| `gemini_large` | Large — Gemini 3.5 Flash | `google/gemini-3.5-flash:exacto` | minimal | `Output Files Gemini 3.5 Flash` |

### DeepSeek V4 Flash (Non-reasoning) — Representative Benchmarks

Overall intelligence: **36.5** — Artificial Analysis Intelligence Index (better than 66% of compared models)  
Coding capability: **35.2** — Artificial Analysis Coding Index (better than 73%)  
Agentic capability: **61.3** — Artificial Analysis Agentic Index (better than 89%)

Selected benchmarks: GPQA Diamond 71.6% · HLE 7.0% · IFBench 47.2% · τ²-Bench Telecom 94.4% · SciCode 37.3% · AA-Omniscience Non-Hallucination Rate 4.9%

### GPT-OSS-20B — Benchmarks

Overall intelligence score combining multiple benchmarks: **24.5** — Artificial Analysis Intelligence Index (Better than 41% of models compared) ([OpenRouter benchmarks](https://openrouter.ai/openai/gpt-oss-20b/benchmarks)).

Composite coding capability score: **18.5** — Artificial Analysis Coding Index (Better than 39% of models compared) ([OpenRouter benchmarks](https://openrouter.ai/openai/gpt-oss-20b/benchmarks)).

Composite agentic capability score: **27.6** — Artificial Analysis Agentic Index (Better than 46% of models compared) ([OpenRouter benchmarks](https://openrouter.ai/openai/gpt-oss-20b/benchmarks)).

#### Reasoning (selected benchmarks)
- GPQA Diamond (graduate-level scientific reasoning): **68.8%**
- HLE (Humanity's Last Exam): **9.8%**
- IFBench (instruction-following): **65.1%**
- τ²-Bench Telecom (dual-control conversational agents): **60.2%**
- AA-LCR (long-context reasoning): **30.7%**
- GDPval-AA (economically valuable tasks): **7.6%**
- CritPt (research-level physics reasoning): **1.4%**

#### Coding (selected benchmarks)
- SciCode (Python scientific computing): **34.4%**
- Terminal-Bench Hard (agentic coding & terminal use): **10.6%**

#### Knowledge
- AA-Omniscience Accuracy (proportion correct): **15.5%**
- AA-Omniscience Non-Hallucination Rate: **5.9%**

Metrics sourced from OpenRouter benchmark pages and Artificial Analysis model pages.

### Qwen 3.5 9B — Benchmarks

Overall intelligence score combining multiple benchmarks: **32.4** — Artificial Analysis Intelligence Index ([OpenRouter benchmarks](https://openrouter.ai/qwen/qwen3.5-9b/benchmarks)).

Composite coding capability score: **25.3** — Artificial Analysis Coding Index ([OpenRouter benchmarks](https://openrouter.ai/qwen/qwen3.5-9b/benchmarks)).

Composite agentic capability score: **37.4** — Artificial Analysis Agentic Index ([OpenRouter benchmarks](https://openrouter.ai/qwen/qwen3.5-9b/benchmarks)).

#### Reasoning (selected benchmarks)
- GPQA Diamond (graduate-level scientific reasoning): **80.6%**
- HLE (Humanity's Last Exam): **13.3%**
- IFBench (instruction-following): **66.7%**
- τ²-Bench Telecom (dual-control conversational agents): **86.8%**
- AA-LCR (long-context reasoning): **59.0%**
- GDPval-AA (economically valuable tasks): **10.7%**
- CritPt (research-level physics reasoning): **0.3%**

#### Coding (selected benchmarks)
- SciCode (Python scientific computing): **27.5%**
- Terminal-Bench Hard (agentic coding & terminal use): **24.2%**

#### Knowledge
- AA-Omniscience Accuracy (proportion correct): **15.9%**
- AA-Omniscience Non-Hallucination Rate: **18.6%**

Metrics sourced from OpenRouter benchmark pages and Artificial Analysis model pages.

### Gemini 3.5 Flash — Benchmarks

Overall intelligence score combining multiple benchmarks: **55.3** — Artificial Analysis Intelligence Index (Better than 97% of models compared) ([OpenRouter benchmarks](https://openrouter.ai/google/gemini-3.5-flash/benchmarks)).

Composite coding capability score: **45.0** — Artificial Analysis Coding Index (Better than 91% of models compared) ([OpenRouter benchmarks](https://openrouter.ai/google/gemini-3.5-flash/benchmarks)).

Composite agentic capability score: **70.3** — Artificial Analysis Agentic Index (Better than 98% of models compared) ([OpenRouter benchmarks](https://openrouter.ai/google/gemini-3.5-flash/benchmarks)).

#### Reasoning (selected benchmarks)
- GPQA Diamond (graduate-level scientific reasoning): **92.2%**
- HLE (Humanity's Last Exam): **41.0%**
- IFBench (instruction-following): **76.3%**
- τ²-Bench Telecom (dual-control conversational agents): **95.3%**
- AA-LCR (long-context reasoning): **69.3%**
- GDPval-AA (economically valuable tasks): **57.8%**
- CritPt (research-level physics reasoning): **13.1%**

#### Coding (selected benchmarks)
- SciCode (Python scientific computing): **53.1%**
- Terminal-Bench Hard (agentic coding & terminal use): **40.9%**

#### Knowledge
- AA-Omniscience Accuracy (proportion correct): **51.9%**
- AA-Omniscience Non-Hallucination Rate: **39.3%**

Metrics sourced from OpenRouter benchmark pages and Artificial Analysis model pages.


Metrics from [Artificial Analysis](https://artificialanalysis.ai/models/deepseek-v4-flash-non-reasoning) and OpenRouter model pages. DeepSeek is configured as a non-reasoning model; the architectures omit the `reasoning` payload for non-reasoning models.

---

## Repository Structure

```
LLM-MCDA-Paper/
├── Architectures/
│   ├── Hybrid.py
│   ├── PurePrompting.py
│   └── RAGDatabaseOptimized.py
├── Ground Truth/
│   ├── ground_truth_appliance.xlsx     # 288 rows (96 scenarios × 3 alternatives)
│   ├── ground_truth_hvac.xlsx          # 309 rows (103 scenarios × 3 alternatives)
│   └── ground_truth_shower.xlsx        # 231 rows (77 scenarios × 3 alternatives)
├── Ground Truth Calculators/
│   ├── ApplianceGroundTruthCalculator.py
│   ├── HVACGroundTruthCalculator.py
│   └── ShowerGroundTruthCalculator.py
├── Miscellaneous Scripts/
│   ├── BuildRAG.py
│   ├── CalculateMetrics.py
│   ├── EntropyWeights.py
│   ├── ImpliedWeights.py
│   ├── MERCECWeights.py
│   └── SensitivityAnalysis.py
├── Scenario Files/
│   ├── ApplianceRAGScenarios.xlsx      # 90 RAG-only scenarios
│   ├── ApplianceScenarios.xlsx         # 98 total appliance scenarios
│   ├── HVACRagScenarios.xlsx           # 105 RAG-only scenarios
│   ├── HVACScenarios.xlsx              # 103 total HVAC scenarios
│   ├── ShowerRAGScenarios.xlsx         # 45 RAG-only scenarios
│   ├── ShowerScenarios.xlsx            # 77 total shower scenarios
│   └── TestScenarios.xlsx              # 185 test scenarios (69 HVAC, 62 Appliance, 54 Shower)
├── Scoring Logic and Documentation/
│   ├── method/
│   └── paper/
├── Output Files GPT-OSS 20B/
├── Output Files Qwen3.5 9B/
├── Output Files DeepSeek V4 Flash/
├── Output Files Gemini 3.5 Flash/
├── Output Files Claude/
├── Output Files Gemini/
├── chroma_rag_db/
├── tests/
├── model_config.py
├── sentinel_utils.py
├── XLSX_Schema_Map.md
├── README.md
└── requirements.txt
```

---

## Three Architectures

### 1. Pure Prompting

- **Approach:** LLM scores all four criteria directly via calibrated system prompts with per-decision-type rubric guidance
- **Input:** Natural language scenario description + structured context fields
- **Output:** Four 0–10 scores per alternative → MAVT ranking
- **API calls per scenario:** 3 (one per alternative)
- **API calls per run (185 scenarios):** 555
- **API calls per 10-run benchmark:** 5,550

### 2. RAG-Enhanced

- **Approach:** Semantic retrieval from a ChromaDB vector index (240 pre-scored RAG scenarios) provides calibration examples before the LLM scores each alternative
- **Input:** Scenario description → sentence-transformer embedding → top-k retrieval → LLM scores with retrieved context
- **Output:** Four 0–10 scores per alternative → MAVT ranking
- **API calls per scenario:** 3 (one per alternative)
- **API calls per run (185 scenarios):** 555
- **API calls per 10-run benchmark:** 5,550
- **Vector DB:** ChromaDB with sentence-transformers embeddings

### 3. Hybrid (AI Extraction + Deterministic Calculator)

- **Approach:** LLM extracts structured engineering parameters (SEER tier, appliance age kWh/cycle, GPM estimate, etc.) from the natural-language description; a deterministic MAVT calculator runs the physics
- **Input:** Scenario description → LLM parameter extraction → ground-truth-style calculator
- **Output:** Four 0–10 scores from physics formulas → MAVT ranking
- **API calls per scenario:** 1 (all three alternatives processed in one call)
- **API calls per run (185 scenarios):** 185
- **API calls per 10-run benchmark:** 1,850

### Estimated API Call Totals (10-run benchmark, 4 models)

| Architecture | Calls/model | × 4 models |
| --- | --- | --- |
| Pure | 5,550 | 22,200 |
| RAG | 5,550 | 22,200 |
| Hybrid | 1,850 | 7,400 |
| **Total** | **12,950** | **51,800** |

---

## Scenario Corpus

### Test vs. RAG Pools

The 185 test scenarios and 240 RAG scenarios are **disjoint**. Test scenarios are evaluated by all three architectures and the ground-truth calculator. RAG scenarios seed only the ChromaDB retrieval index.

| Pool | HVAC | Appliance | Shower | Total |
| --- | --- | --- | --- | --- |
| Test set | 69 | 62 | 54 | **185** |
| RAG corpus | 105 | 90 | 45 | **240** |

### Parameter Generalization

The ground-truth calculators receive exact engineering values; architectures receive homeowner-accessible labels or infer parameters from context (consistent with what a household member would actually know, Attari et al. 2010).

| Parameter | LLM Label | Calculator Value | Source |
| --- | --- | --- | --- |
| **HVAC — Insulation** | Poor | R-11 | CEC JA4.3; ENERGY STAR |
| | Medium | R-13 | |
| | Good | R-19 | |
| **Shower — Flow Rate** | `low_flow` | 1.5 GPM | EPA WaterSense |
| | `standard` | 2.5 GPM | Energy Policy Act 1992 |
| **Appliance — Age** | 1–15 yr | Dishwasher: 0.72–1.70 kWh/cycle | ENERGY STAR certified datasets |
| | | Washer: 0.15–0.45 kWh/cycle | |
| | | Dryer: 1.15–3.50 kWh/cycle | |

The LLM never directly sees SEER ratings, exact R-values, GPM values, kWh/cycle figures, or occupancy-context flags. The Hybrid architecture infers structured estimates of these parameters before invoking the calculator.

---

## MAVT Framework

### Value Function

MAVT additive form:

```
s_j = Σ w_i · v_i(x_ij)   for i ∈ {energy_cost, environmental, comfort, practicality}
```

All four criterion scores are on a 0–10 scale before weighting.

### Reference Ranges (5th–95th percentile of scenario distributions)

| Criterion | HVAC | Appliance | Shower |
| --- | --- | --- | --- |
| Energy Cost ($) | $0.47 – $3.31 | $0.017 – $1.12 | $0.15 – $1.50 |
| Environmental Impact | 2.42 – 18.14 lbs CO₂ | 0.244 – 3.644 lbs CO₂ | 7.5 – 75.0 gal water |
| Comfort | 0.0 – 10.0 | 0.0 – 10.0 | 0.0 – 10.0 |
| Practicality | 0.5 – 10.0 | 0.5 – 10.0 | 0.5 – 10.0 |

Shower environmental impact is defined as **water volume (gallons)**, not CO₂. HVAC and Appliance environmental impact is in lbs CO₂ using PJM marginal emissions factors (not the EPA eGRID average factor).

Reference ranges are anchored to 5th–95th percentiles of the actual scenario distributions rather than theoretical extremes, concentrating score sensitivity in the range households actually encounter.

### Budget Penalty

A four-tier multiplicative budget penalty is applied to the post-value-function energy-cost score, where `u = monthly_cost / budget`:

| Utilization `u` | Penalty |
| --- | --- |
| `u < 0.80` | 1.0 (no penalty) |
| `0.80 ≤ u < 1.00` | Linear decay: `1 − 2.5(u − 0.80)` |
| `1.00 ≤ u < 1.50` | Exponential: `0.5 · e^{−3(u − 1.0)}` |
| `u ≥ 1.50` | 0 (eliminated) |

Behavioral anchors: mental budget safety margins (Thaler 1999); linear self-control (Heath & Soll 1996); exponential loss aversion (Prelec & Loewenstein 1998); infeasibility elimination (Gathergood 2012).

---

## Ground Truth Calculators

Each calculator takes a scenario with three alternatives and returns four scores per alternative (Energy Cost in $, Environmental Impact, Comfort 0–10, Practicality 0–10) plus raw physical quantities before value-function transformation.

### Emissions Factors

HVAC and Appliance environmental impact uses **PJM marginal emissions factors** (marginal rather than average, because shifting a residential load displaces the generator at the margin):

| Period | Factor |
| --- | --- |
| Peak (7am–11pm) | 1.041 lbs CO₂/kWh |
| Off-peak | 0.976 lbs CO₂/kWh |

### HVAC Calculator

Thermal load uses four ASHRAE-style components (conductive + internal + solar + ventilation). Energy consumption over the 8-hour decision window:

```
E_kWh = (Q_load / (EER_eff × 1000)) · 8 hr · m_occ
```

where `EER_eff` is derived from age-degraded SEER via the AHRI 210/240 quadratic (`EER_eff = −0.02·SEER²_eff + 1.12·SEER_eff`), and `m_occ` adjusts for occupancy (fully occupied = 1.0, overnight = 0.75, daytime unoccupied = `1 − 0.5·(h_away/24)`).

Comfort uses a tent function peaking at ASHRAE 55 optimal setpoints (76 °F cooling, 70 °F heating).

### Appliance Calculator

Per-cycle energy cost: `C = E_cyc · r(t, ℓ)` where `r` is the TOU rate for one of six Pennsylvania utilities (PECO, PPL, West Penn, Penelec, MetEd, Duquesne) resolved by location `ℓ` and run-time `t`.

Comfort decays piecewise from 10 at zero delay, with appliance-specific tolerance ceilings (dishwashers 12 hr, washers 8 hr, dryers 6 hr), plus a late-night noise penalty (applied when dBA exceeds 45 and run time is 10pm–7am) and a household-size penalty.

Delays are computed as minimum circular distance on a 24-hour clock to avoid wrap-around artifacts.

### Shower Calculator

Mains inlet temperature interpolated from outdoor temperature (45 °F at ≤32 °F outdoor, 65 °F at ≥75 °F outdoor, NREL seasonal model). Hot-water fraction:

```
f_hot = (T_target − T_inlet) / (T_heater − T_inlet),   T_target = 105 °F
```

Shower energy:

```
E_kWh = (GPM · f_hot · 8.33 · (T_heater − T_inlet) · duration_min) / (3412 · η)
```

where η = 0.92 (UEF for 40–55 gal electric tank). Environmental impact = GPM × duration (gallons of water used).

Comfort peaks at the REU2016 average of 7.8 min with penalties for temperature adequacy (CDC Legionella thresholds) and household contention. Practicality additionally penalizes alternatives that exhaust available tank capacity.

---

## Sensitivity Analysis

Ten weight scenarios test stability of architecture ordering under ±0.05 perturbations to each criterion weight (difference redistributed equally across the remaining three) plus an equal-weight scenario.

| Scenario | w(EnergyCost) | w(Environmental) | w(Comfort) | w(Practicality) |
| --- | --- | --- | --- | --- |
| Baseline | 0.3000 | 0.3500 | 0.2000 | 0.1500 |
| Ene +0.05 | **0.3500** | 0.3333 | 0.1833 | 0.1333 |
| Ene −0.05 | **0.2500** | 0.3667 | 0.2167 | 0.1667 |
| Env +0.05 | 0.2833 | **0.4000** | 0.1833 | 0.1333 |
| Env −0.05 | 0.3167 | **0.3000** | 0.2167 | 0.1667 |
| Com +0.05 | 0.2833 | 0.3333 | **0.2500** | 0.1333 |
| Com −0.05 | 0.3167 | 0.3667 | **0.1500** | 0.1667 |
| Pra +0.05 | 0.2833 | 0.3333 | 0.1833 | **0.2000** |
| Pra −0.05 | 0.3167 | 0.3667 | 0.2167 | **0.1000** |
| Equal | 0.2500 | 0.2500 | 0.2500 | 0.2500 |

Architecture Kendall's τ values across these scenarios are pending the corrected multi-model run.

---

## Objective Weight Validation Scripts

Two scripts independently validate the subjective MAVT weights against the ground-truth score distributions:

- **[EntropyWeights.py](Miscellaneous Scripts/EntropyWeights.py)** — Shannon entropy weights overall and by decision type. The environmental criterion receives above-average entropy weight, independently supporting the 0.35 allocation.
- **[MERCECWeights.py](Miscellaneous Scripts/MERCECWeights.py)** — MEREC (Method based on Removal Effects of Criteria) weights computed per-scenario then averaged. MEREC is used over CRITIC because comfort and practicality use nonlinear value functions; MEREC is correlation-free and robust to nonlinearity.

---

## Miscellaneous Scripts

| Script | Purpose |
| --- | --- |
| [BuildRAG.py](Miscellaneous Scripts/BuildRAG.py) | Builds/refreshes the ChromaDB vector index from RAG scenario files |
| [CalculateMetrics.py](Miscellaneous Scripts/CalculateMetrics.py) | Computes Top-1 accuracy, Kendall's τ, MAE per architecture/model/decision-type |
| [SensitivityAnalysis.py](Miscellaneous Scripts/SensitivityAnalysis.py) | Reruns ranking metrics across the 10 weight perturbation scenarios |
| [EntropyWeights.py](Miscellaneous Scripts/EntropyWeights.py) | Shannon entropy weight validation |
| [MERCECWeights.py](Miscellaneous Scripts/MERCECWeights.py) | MEREC objective weight validation |
| [ImpliedWeights.py](Miscellaneous Scripts/ImpliedWeights.py) | Recovers implied criterion weights from architecture outputs |

---

## Documentation

[Notebook](Scoring%20Logic%20and%20Documentation/paper/Notebook.pdf) | [Evaluation Metrics](Scoring%20Logic%20and%20Documentation/method/Evaluation_Metric_Derivations.pdf) | [Budget Penalties](Scoring%20Logic%20and%20Documentation/method/Budget_Penalties.pdf) | [Reference Ranges](Scoring%20Logic%20and%20Documentation/method/Reference_Ranges_for_Value_Functions.pdf) | [Worked Calculator Examples](Scoring%20Logic%20and%20Documentation/method/Calculator_Examples.pdf)

---

## Haiku

Four minds weigh one home,
Open, closed, both small and large,
Truth keeps every score.

---

## Citation / Collaborator

This project is being developed into a journal paper with **Dr. River Huang (Paul Scherrer Institut, Switzerland)**.
