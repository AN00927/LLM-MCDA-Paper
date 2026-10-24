# LLM-MCDA: AI-Assisted Multi-Criteria Decision Analysis for Household Energy Optimization

**Authors:** Ahaan Nigam; River Huang (Paul Scherrer Institut, Switzerland)

---

## Overview

This project benchmarks three LLM-MCDA architectures for household energy decision-making against a physics-based Multi-Attribute Value Theory (MAVT) reference calculator, across **195 test scenarios** (70 HVAC, 65 Appliance, 60 Shower). Each scenario presents three alternatives scored on four criteria. A disjoint **90-scenario RAG corpus** (35 HVAC, 35 Appliance, 20 Shower) seeds the retrieval index used by the example-guided architecture.

Four models are evaluated: Gemini 3.8 Flash, DeepSeek V4 Flash, GPT-OSS 20B, and Qwen3.5 9B, each run 5 trials per architecture. The main benchmark totals **27,300 API calls** across all architecture–model pairs.

---

## Setup

Requires **Python 3.11+**.

```bash
git clone https://github.com/AN00927/LLM-MCDA-Paper.git
cd LLM-MCDA-Paper
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -e .
```

### API Key

Models are called through [OpenRouter](https://openrouter.ai). Copy `.env.example` to `.env` and fill in your key:

```
OPENROUTER_API_KEY=your_key_here
```

### Configuration

Set `MODEL_KEY` and `N_RUNS` in [`model_config.py`](common/model_config.py):

- `MODEL_KEY` — one of `gemini`, `deepseek`, `gptoss`, `qwen`
- `N_RUNS` — number of repeated trials per architecture (default 5)

### Running the Benchmark

```bash
# Build the ChromaDB retrieval index (required by example-guided architecture)
python scripts/collection/build_rag_index.py

# Run each architecture (set MODEL_KEY first, use a separate --output-dir per model/arch)
python architectures/Direct_LLM_Scoring.py --output-dir results/scratch/deepseek/direct
python architectures/Example-Guided_LLM_Scoring.py --output-dir results/scratch/deepseek/example-guided
python architectures/LLM-Parameterized_Reference_Scoring.py --output-dir results/scratch/deepseek/parameterized
```

Runs are resume-aware: completed per-run result files are skipped on relaunch.

### Deterministic Analysis Pipeline

```bash
python scripts/paper_pipeline/run_paper_pipeline.py
```

Makes **no API calls**. Reads existing benchmark files and produces all analytical outputs. Use `--list` to preview stages.

---

## Results

The LLM-parameterized reference scoring architecture dominates across all four models. The example-guided architecture ranks second. Direct LLM scoring ranks third, near-random on HVAC and Appliance.

### Overall Metrics (5-run mean, 195 scenarios)

| Model | Architecture | Kendall's τ | Top-1 Acc | RMSE | MAE |
| --- | --- | --- | --- | --- | --- |
| **Gemini 3.8 Flash** | LLM-Parameterized Reference Scoring | **0.891** | **90.2%** | **0.096** | **0.048** |
| | Example-Guided LLM Scoring | 0.298 | 47.5% | 0.210 | 0.147 |
| | Direct LLM Scoring | 0.179 | 39.8% | 0.276 | 0.207 |
| **DeepSeek V4 Flash** | LLM-Parameterized Reference Scoring | **0.856** | **88.6%** | **0.114** | **0.055** |
| | Example-Guided LLM Scoring | 0.253 | 48.3% | 0.240 | 0.170 |
| | Direct LLM Scoring | 0.125 | 39.1% | 0.284 | 0.223 |
| **GPT-OSS 20B** | LLM-Parameterized Reference Scoring | **0.805** | **82.5%** | **0.156** | **0.079** |
| | Example-Guided LLM Scoring | 0.234 | 46.5% | 0.252 | 0.179 |
| | Direct LLM Scoring | 0.032 | 34.1% | 0.312 | 0.246 |
| **Qwen3.5 9B** | LLM-Parameterized Reference Scoring | **0.836** | **86.5%** | **0.162** | **0.074** |
| | Example-Guided LLM Scoring | 0.147 | 43.9% | 0.266 | 0.199 |
| | Direct LLM Scoring | 0.005 | 30.8% | 0.301 | 0.239 |

### By Decision Type (best/worst model, 5-run mean τ)

| Decision Type | Direct LLM Scoring | Example-Guided LLM Scoring | LLM-Parameterized Reference Scoring |
| --- | --- | --- | --- |
| HVAC | −0.200 (Gemini) to 0.091 (GPT-OSS) | −0.118 (Gemini) to 0.202 (GPT-OSS) | 0.657 (GPT-OSS) to 0.872 (Gemini) |
| Appliance | −0.114 (GPT-OSS) to 0.110 (Gemini) | −0.073 (GPT-OSS) to 0.303 (Gemini) | 0.908 (Qwen) to 0.949 (GPT-OSS) |
| Shower | 0.093 (Qwen) to 0.696 (Gemini) | 0.249 (Qwen) to 0.780 (Gemini) | 0.821 (GPT-OSS) to 0.856 (Gemini) |

### Key Findings

- **Cross-architecture performance stability.** The LLM-parameterized architecture's τ spans 0.086 across a ~21× difference in configured token price, versus 0.174 for direct LLM scoring.
- **Reference calculator with fixed parameters.** Running the calculator on dataset-median parameters reaches only τ = 0.590 — well above chance, but far below the LLM-parameterized architecture's 0.805–0.891.
- **Non-LLM baseline comparison.** A nearest-neighbor copy baseline (k = 1) reaches τ = 0.374, above direct and example-guided LLM scoring for every model (τ 0.005–0.298); only LLM-parameterized reference scoring clears the dataset-median calculator's τ = 0.590.
- **Failure rates are near-zero** across all architectures and models, with one exception: GPT-OSS 20B on LLM-parameterized scoring has an 8.7% per-scenario-run extraction failure rate, concentrated in HVAC. Cross-run recovery confirms the architecture ordering is unaffected.

### API Costs (per 5-run benchmark)

| Architecture | Calls/run | Gemini | DeepSeek | GPT-OSS | Qwen |
| --- | --- | --- | --- | --- | --- |
| Direct LLM Scoring | 585 | ~\$2.41 | ~\$0.07 | ~\$0.07 | ~\$0.22 |
| Example-Guided LLM Scoring | 585 | ~\$2.14 | ~\$0.07 | ~\$0.07 | ~\$0.21 |
| LLM-Parameterized Reference Scoring | 195 | ~\$0.40 | ~\$0.03 | ~\$0.02 | ~\$0.06 |

---

## Three Architectures

### 1. Direct LLM Scoring

LLM scores all four criteria directly via calibrated system prompts with per-decision-type qualitative anchors. One API call per alternative (3 per scenario, 585 per run).

→ [`Direct_LLM_Scoring.py`](architectures/Direct_LLM_Scoring.py)

### 2. Example-Guided LLM Scoring

Retrieval from a ChromaDB vector index (90 pre-scored RAG scenarios, sentence-transformers `all-MiniLM-L6-v2`, k=1) supplies one worked exemplar before the LLM scores each alternative. 3 calls per scenario, 585 per run.

→ [`Example-Guided_LLM_Scoring.py`](architectures/Example-Guided_LLM_Scoring.py)

### 3. LLM-Parameterized Reference Scoring

A single LLM call extracts withheld engineering parameters (R-value, SEER, kWh/cycle, GPM, etc.) from the scenario description. The deterministic MAVT calculator then scores all three alternatives. 1 call per scenario, 195 per run.

→ [`LLM-Parameterized_Reference_Scoring.py`](architectures/LLM-Parameterized_Reference_Scoring.py)

---

## Model Set

| Key | Display Label | OpenRouter Route | Provider Pin | Reasoning |
| --- | --- | --- | --- | --- |
| `gemini` | Gemini 3.8 Flash | `google/gemini-3.8-flash:floor` | `google-ai-studio/flex` | minimal |
| `deepseek` | DeepSeek V4 Flash | `deepseek/deepseek-v4-flash-0731:floor` | `relace/fp4` | none |
| `gptoss` | GPT-OSS 20B | `openai/gpt-oss-20b:floor` | `darkbloom/fp8` | low |
| `qwen` | Qwen3.5 9B | `qwen/qwen3.5-9b:floor` | `venice/fp8` | none |

All routes set `allow_fallbacks: false` and `require_parameters: true`.

---

## Scenario Corpus

| Pool | HVAC | Appliance | Shower | Total |
| --- | --- | --- | --- | --- |
| Test set | 70 | 65 | 60 | **195** |
| RAG corpus | 35 | 35 | 20 | **90** |

The two pools are disjoint. RAG scenarios seed only the ChromaDB retrieval index and never appear in evaluation.

---

## MAVT Criterion Weights

| Criterion | Weight |
| --- | --- |
| Environmental Impact | 35% |
| Energy Cost | 30% |
| Comfort | 20% |
| Practicality | 15% |

Weights are constant across all decision types, architectures, and the reference calculator.

---

## Ablation Suites

Four ablation suites test whether the architecture ordering depends on design choices within the architectures:

- **Prompt-sensitivity** — reruns direct and example-guided scoring under three prompt perturbations (no anchors, chain-of-thought scaffold, 0–10 rescale). Architecture ordering survives every variant.
- **RAG ablation** — varies retrieval depth (k=1, 3, 5), embedding model, and exemplar content on the 90-scenario RAG corpus under leave-one-out. Removing exemplar scores hurts far more than removing hidden parameters.
- **Parameter-provenance** — compares LLM-extracted parameters against a fixed dataset-median set. No new API calls.
- **Alternative-ordering** — reverses alternative order in the prompt. Never changes which alternative any model ranked first.

---

## Ground Truth Calculators

Each calculator takes a scenario with three alternatives and returns four 0–1 criterion scores plus raw physical quantities.

- **HVAC** — ASHRAE-style thermal balance (conductive + infiltration + internal-gain + solar). SEER-to-EER via Building America conversion. Comfort uses ASHRAE 55 tent function.
- **Appliance** — TOU-rate energy cost across six PA utilities (PECO, PPL, West Penn, Penelec, MetEd, Duquesne). PJM marginal emissions factors (peak 1.041 / off-peak 0.976 lbs CO₂/kWh).
- **Shower** — Mains temperature from NREL model, mixing fraction to 105 °F delivery. Environmental impact = gallons of water used.

---

## Repository Structure

```text
LLM-MCDA-Paper/
├── architectures/          # Three architecture implementations
├── calculators/            # HVAC, Appliance, Shower reference calculators
├── common/                 # Model config, weights, sentinel utils
├── run_registry.py
├── scripts/
│   ├── collection/             # RAG index builder, scenario workbook builder
│   ├── analysis/               # Metric evaluation scripts
│   ├── experiments/            # Ablation and baseline runners
│   ├── validation/             # Significance testing, sensitivity, CIs
│   └── paper_pipeline/         # Deterministic analysis entry point
├── workbooks/
│   ├── scenarios/              # Scenario master workbooks
│   └── ground_truth/           # Reference calculator outputs (frozen)
├── Combined Metrics/           # Cross-model artifacts (metrics, significance, ablations)
├── Output Files <model>/       # Four per-model folders (frozen benchmark outputs)
├── archive/                    # Frozen archival run outputs
├── data/scenarios/             # Scenario data files
├── pyproject.toml
└── XLSX_Schema_Map.md
```

---

## License

Code is released under the MIT License ([LICENSE](LICENSE)). Scenario workbooks, reference scores, and benchmark outputs are released under CC BY 4.0 ([DATA_LICENSE](DATA_LICENSE)).
