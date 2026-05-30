# LLM-MCDA: AI-Assisted Multi-Criteria Decision Analysis for Household Energy Optimization

**Author:** Ahaan Nigam  
**Institution:** Downingtown East High School  
**Collaborator:** Dr. River Huang, Paul Scherrer Institut (PSI), Switzerland  

---

## Research Question

Which AI-MCDA architecture most accurately replicates physics-based ground truth for household energy decisions, while still maintaining reasonable failure rate and API costs?

---

## Project Overview

[Abstract](Abstract.pdf)

This project compares three LLM-MCDA architectures for household energy decision-making against a physics-based Multi-Attribute Value Theory (MAVT) ground truth calculator across **185 scenarios** (for now) (95 HVAC, 50 Appliance, 40 Shower). Each scenario presents three alternatives; each architecture ranks them on four criteria.

**MAVT Criterion Weights:**
| Criterion | Weight |
|---|---|
| Environmental Impact | 35% |
| Energy Cost | 30% |
| Comfort | 20% |
| Practicality | 15% |

**Finalized Benchmark Model Set (2x2 open/closed x small/large):**
| Slot | Model | GPQA Diamond | IFBench | GDPval | OpenRouter string |
|---|---|---:|---:|---:|---|
| Large Closed | GPT-5.4 | 87.1% | 65.9% | 50.1% | `openai/gpt-5.4` |
| Small Closed | GPT-5.4 Nano | 81.7% | 75.9% | 34.8% | `openai/gpt-5.4-nano` |
| Large Open | Gemini 3.5 Flash | 82.8% | 47.3% | 47.2% | `google/gemini-3.5-flash` |
| Small Open | DeepSeek V4 Flash (Non-reasoning) | 71.6% | 47.2% | 44.5% | `deepseek/deepseek-v4-flash` |


Model selection and output routing are controlled in `model_config.py`.

### DeepSeek V4 Flash (Non-reasoning) — Benchmarks

Overall intelligence score combining multiple benchmarks: **36.5** — Artificial Analysis Intelligence Index (Better than 66% of models compared) ([OpenRouter rankings](https://openrouter.ai/rankings?benchmark=intelligence#benchmarks)).

Composite coding capability score: **35.2** — Artificial Analysis Coding Index (Better than 73% of models compared) ([OpenRouter rankings](https://openrouter.ai/rankings?benchmark=coding#benchmarks)).

Composite agentic capability score: **61.3** — Artificial Analysis Agentic Index (Better than 89% of models compared) ([OpenRouter rankings](https://openrouter.ai/rankings?benchmark=agentic#benchmarks)).

#### Reasoning (selected benchmarks)
- GPQA Diamond (graduate-level scientific reasoning): **71.6%**
- HLE (Humanity's Last Exam): **7.0%**
- IFBench (instruction-following): **47.2%**
- τ²-Bench Telecom (dual-control conversational agents): **94.4%**
- AA-LCR (long-context reasoning): **33.3%**
- GDPval-AA (economically valuable tasks): **44.5%**
- CritPt (research-level physics reasoning): **0.3%**

#### Coding (selected benchmarks)
- SciCode (Python scientific computing): **37.3%**
- Terminal-Bench Hard (agentic coding & terminal use): **34.1%**

#### Knowledge
- AA-Omniscience Accuracy (proportion correct): **26.1%**
- AA-Omniscience Non-Hallucination Rate: **4.9%**

Metrics sourced from [Artificial Analysis](https://artificialanalysis.ai/models/deepseek-v4-flash-non-reasoning) and OpenRouter model pages. DeepSeek is configured here as a non-reasoning model in `model_config.py` (the architectures omit the `reasoning` payload for non-reasoning models).

**RAG Database:** ChromaDB  
**Score Scale:** 0–10

---

## Repository Structure TO UPDATE

```
LLM-MCDA/
├── Architectures/
│   ├── Hybrid.py
│   ├── PurePrompting.py
│   └── RAGDatabaseOptimized.py
├── Ground Truth/
│   ├── ground_truth_appliance.xlsx
│   ├── ground_truth_hvac.xlsx
│   └── ground_truth_shower.xlsx
├── Ground Truth Calculators/
│   ├── ApplianceGroundTruthCalculator.py
│   ├── HVACGroundTruthCalculator.py
│   └── ShowerGroundTruthCalculator.py
├── Miscellaneous Files/
│   └── CalculateMetrics.py
├── Output Files DeepSeek V4 Flash/
├── Output Files Gemini 3.5 Flash/
├── Output Files GPT-5.4 Nano/
└── Output Files GPT-5.4/
├── Scenario Files/
│   ├── ApplianceRAGScenarios.xlsx
│   ├── ApplianceScenarios.xlsx
│   ├── HVACRagScenarios.xlsx
│   ├── HVACScenarios.xlsx
│   ├── ShowerRAGScenarios.xlsx
│   ├── ShowerScenarios.xlsx
│   └── TestScenarios.xlsx
├── BuildRAG.py
├── MCDA Files Consolidated.xlsx
├── README.md
└── requirements.txt
```

---

## Three Architectures

### 1. Pure Prompting

**NOTE**: API CALLS NUMBERS ARE ESTIMATES

- **Approach:** LLM scores all four criteria directly via calibrated system prompts
- **Input:** Natural language scenario description
- **Output:** Four 0–10 scores per alternative
- **API calls per scenario:** 3 (one per alternative)
- **API calls per run (181 scenarios):** 543
- **API calls per 10-run benchmark:** 5,430

### 2. RAG-Enhanced
- **Approach:** LLM retrieves relevant ground truth scenario chunks from ChromaDB vector database before scoring
- **Input:** User description → semantic retrieval → LLM scores with retrieved context
- **Output:** Four 0–10 scores per alternative
- **API calls per scenario:** 3 (one per alternative)
- **API calls per run (181 scenarios):** 543
- **API calls per 10-run benchmark:** 5,430

### 3. Hybrid (AI Extraction + Deterministic Calculator)
- **Approach:** LLM extracts structured parameters (SEER tier, appliance age, flow rate, etc.) → deterministic MAVT calculator computes scores using physics formulas
- **Input:** User description → AI maps to parameters → calculator runs
- **Output:** Four 0–10 scores from physics-backed formulas
- **API calls per scenario:** 1 (single call processes all three alternatives)
- **API calls per run (181 scenarios):** 181
- **API calls per 10-run benchmark:** 1,810

**Four-model full benchmark estimates (10 runs each):**
| Architecture | Calls/model | × 4 models |
|---|---|---|
| Pure | 5,430 | 21,720 |
| RAG | 5,430 | 21,720 |
| Hybrid | 1,810 | 7,240 |
| **Total** | **12,670** | **50,680** |

---

## Ground Truth Methodology TO UPDATEEE

Ground truth scores are calculated using deterministic MAVT value functions with empirically derived reference ranges (5th–95th percentile from actual scenario data).

**Value function structure (identical across all three calculators):**
- Energy Cost & Environmental Impact: Linear value function
- Comfort: Logarithmic (a = 1.5)
- Practicality: Logarithmic (a = 1.2)

**Budget penalty tiers** (Thaler 1999; Heath & Soll 1996; Prelec & Loewenstein 1998; Gathergood 2012):
- Less than 80% of budget: no penalty
- 80–100%: linear penalty
- 100–150%: exponential penalty
- Greater than 150%: eliminated

**Domain-specific methods:**
| Domain | Method |
|---|---|
| HVAC Energy | ASHRAE cooling/heating load calculations, SEER degradation (Domanski 2014) |
| Appliance Energy | DOE consumption benchmarks, Energy Star data |
| Shower Energy | Flow rate × temperature × duration |
| Emissions | EPA eGRID PJM factor: **0.6458 lbs CO₂/kWh** |
| Comfort | ASHRAE 55 thermal comfort standards |
| Practicality | Behavioral adoption research; floor = 1.5 |

**Reference ranges:**
| Domain | Energy Cost | Environmental |
|---|---|---|
| HVAC | $0.47–$3.31 | 1.60–11.25 lbs CO₂ |
| Appliance | $0.02–$0.90 | 0.09–3.83 lbs CO₂ |
| Shower | $0.20–$1.40 | 1.10–5.90 lbs CO₂ |

> Pre-transformation clamping is NOT applied — values extrapolate beyond reference bounds freely; final clamping occurs only after value function transformation to preserve MAVT independence.

---

[Notebook](Notebook.pdf) | [Evaluation Metrics](Evaluation_Metrics_Derivations.pdf) | [How Budget Penalties Were applied](Budget_Penalties.pdf) | [Reference Ranges for Value Functions](Reference_Ranges_for_Value_Functions) | [Worked Calculator Examples](Calculator_Examples.pdf)

---

## Haiku

Four minds weigh one home,
Open, closed, both small and large,
Truth keeps every score.

---

## Citation / Collaborator

This project is being developed into a journal paper with **Dr. River Huang (Paul Scherrer Institut, Switzerland)**.
