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

This project compares three LLM-MCDA architectures for household energy decision-making against a physics-based Multi-Attribute Value Theory (MAVT) ground truth calculator across **181 scenarios** (for now) (91 HVAC, 50 Appliance, 40 Shower). Each scenario presents three alternatives; each architecture ranks them on four criteria.

**MAVT Criterion Weights:**
| Criterion | Weight |
|---|---|
| Environmental Impact | 35% |
| Energy Cost | 30% |
| Comfort | 20% |
| Practicality | 15% |

**Underlying LLM:** Mistral Small 3.2 24B via OpenRouter  
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
│   ├── ground_truth_appliance.csv
│   ├── ground_truth_hvac.csv
│   └── ground_truth_shower.csv
├── Ground Truth Calculators/
│   ├── ApplianceGroundTruthCalculator.py
│   ├── HVACGroundTruthCalculator.py
│   └── ShowerGroundTruthCalculator.py
├── Miscellaneous Files/
│   └── CalculateMetrics.py
├── Output Files/
│   ├── hybrid_diagnostics.json
│   ├── hybrid_results.csv
│   ├── metrics_summary.csv
│   ├── pure_prompting_results.csv
│   ├── pure_prompting_results_diagnostics.json
│   ├── RAGDiagnostics.json
│   └── RAGResults.csv
├── Scenario Files/
│   ├── ApplianceRAGScenariosGT.csv
│   ├── ApplianceScenarios.csv
│   ├── HVACRagScenarios.csv
│   ├── HVACScenarios.csv
│   ├── ShowerRAGScenarios.csv
│   ├── ShowerScenarios.csv
│   └── TestScenarios.csv
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

## Citation / Collaborator

This project is being developed into a journal paper with **Dr. River Huang (Paul Scherrer Institut, Switzerland)**.
