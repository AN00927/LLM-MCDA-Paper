# LLM-MCDA

**Benchmarking LLM integration strategies for MCDA-assisted household energy decision support**

[![CI](https://github.com/AN00927/LLM-MCDA-Paper/actions/workflows/test.yml/badge.svg)](https://github.com/AN00927/LLM-MCDA-Paper/actions/workflows/test.yml)

This repository contains the code, scenario workbooks, deterministic reference
calculators, collected model outputs, statistical analyses, and LaTeX source for
the study by Ahaan Nigam and River Huang. The study evaluates where a large
language model (LLM) should be placed in a multi-criteria decision analysis
(MCDA) workflow for routine household energy decisions.

The manuscript source is [`paper/Main.tex`](paper/Main.tex). The repository
snapshot includes the per-run outputs used by the paper, so the reported
analysis can be reproduced without an API key. Re-collecting model responses
requires an OpenRouter account and incurs provider charges.

## Main result

Three architectures are evaluated against a deterministic, physics-based
multi-attribute value theory (MAVT) reference:

1. **Direct LLM Scoring (`A_D`)**: the model assigns four criterion scores to
   each alternative.
2. **Example-Guided LLM Scoring (`A_E`)**: the model scores each alternative
   after receiving one retrieved, solved example from a disjoint corpus.
3. **LLM-Parameterized Reference Scoring (`A_H`)**: the model extracts withheld
   engineering parameters; deterministic calculators produce the criterion
   scores and MAVT ranking.

Across 195 evaluation scenarios, four models, and five runs per
architecture/model cell, `A_H` is the only architecture that consistently
exceeds the non-LLM dataset-median baseline. The five-run mean Kendall rank
correlations (`tau`) are:

| Model | `A_D` | `A_E` | `A_H` |
|---|---:|---:|---:|
| Gemini 3.8 Flash | 0.179 | 0.298 | **0.891** |
| DeepSeek V4 Flash | 0.125 | 0.253 | **0.856** |
| GPT-OSS 20B | 0.032 | 0.234 | **0.805** |
| Qwen3.5 9B | 0.005 | 0.147 | **0.836** |

These are five-run means over the 195 test scenarios; failed scenarios count
as incorrect. The deterministic calculator with dataset-median withheld
parameters reaches `tau = 0.590`, and a nearest-neighbor reuse baseline
(`k = 1`) reaches `tau = 0.374`. Thus, in this benchmark, extracting inputs
for a calculator is more accurate and less expensive than asking the model to
score alternatives directly.

The result is a benchmark finding, not a claim that the architecture is
universally optimal. The reference calculators, normative weights, Pennsylvania
tariffs and emissions factors, scenario construction, and model prompts define
the scope of the comparison. Limitations and planned extensions are summarized
in [Limitations and interpretation](#limitations-and-interpretation).

## Study design

### Evaluation corpus

The evaluation set contains **195** scenarios:

| Decision type | Test scenarios | Retrieval scenarios | Total scenarios |
|---|---:|---:|---:|
| Thermostat / HVAC | 70 | 35 | 105 |
| Appliance scheduling | 65 | 35 | 100 |
| Shower duration | 60 | 20 | 80 |
| **Total** | **195** | **90** | **285** |

The 90 retrieval scenarios are disjoint from the 195 test scenarios. They are
used only to build the ChromaDB index for `A_E` and to calculate the
dataset-median and nearest-neighbor baselines. Every test scenario presents
three alternatives. Each alternative is evaluated on:

- **Environmental Impact** — 35%;
- **Energy Cost** — 30%;
- **Comfort** — 20%; and
- **Practicality** — 15%.

The weights are fixed across decision types, architectures and models.
Environmental Impact and Energy Cost use linear value functions. Comfort uses a
logarithmic value function with `alpha = 1.5`; Practicality uses a logarithmic
value function with `alpha = 1.2`. Raw quantities are normalized to `[0, 1]`
against fixed domain bounds and clipped outside those bounds.

### Reference calculators

The reference ranking is the additive MAVT score

```text
aggregate(alternative) =
    0.35 * environmental
  + 0.30 * energy_cost
  + 0.20 * comfort
  + 0.15 * practicality
```

The calculators are deterministic and return criterion scores, aggregate
scores, ranks, and raw physical quantities:

- **HVAC**: conductive, infiltration, internal-gain and solar heat balance;
  SEER-to-EER conversion; and an ASHRAE-55-style thermal comfort function.
- **Appliance**: time-of-use electricity costs for six Pennsylvania utilities
  (PECO, PPL, West Penn, Penelec, Met-Ed and Duquesne) and PJM marginal
  emissions factors of **1.041 lb CO2/kWh during peak** and
  **0.976 lb CO2/kWh off peak**.
- **Shower**: mains-water temperature from the NREL-based model, mixing to a
  **105 deg F** delivery temperature, electric-resistance water heating, and
  water use as the environmental-impact quantity.

The detailed equations, bounds, constants and source citations are in
[`paper/Main.tex`](paper/Main.tex) and the calculator implementations under
[`calculators/`](calculators/).

### Models and API routing

The benchmark uses one fixed OpenRouter route and provider pin per model.
Fallbacks are disabled and required parameters are enforced.

| Configuration key | Model | OpenRouter model ID | Provider pin | Reasoning setting |
|---|---|---|---|---|
| `gemini` | Gemini 3.8 Flash | `google/gemini-3.8-flash:floor` | `google-ai-studio/flex` | `minimal` |
| `deepseek` | DeepSeek V4 Flash | `deepseek/deepseek-v4-flash-0731:floor` | `relace/fp4` | `none` |
| `gptoss` | GPT-OSS 20B | `openai/gpt-oss-20b:floor` | `darkbloom/fp8` | `low` |
| `qwen` | Qwen3.5 9B | `qwen/qwen3.5-9b:floor` | `venice/fp8` | `none` |

The default configuration is `MODEL_KEY=gemini`, `N_RUNS=5`, and
`TEMPERATURE=0.3`. Model configuration, retry policy and criterion weights are
defined in [`common/model_config.py`](common/model_config.py). Provider prices
can change; the costs below are the recorded benchmark costs, not a current
price guarantee.

### API-call budget and recorded cost

Each five-run model/architecture cell contains:

- `A_D`: 3 calls per scenario, **585 calls per run** and **2,925 calls per
  five-run cell**;
- `A_E`: 3 calls per scenario, **585 calls per run** and **2,925 calls per
  five-run cell**; and
- `A_H`: 1 call per scenario, **195 calls per run** and **975 calls per
  five-run cell**.

The complete benchmark therefore contains **27,300 API calls**:
`4 models x 5 runs x (585 + 585 + 195) calls`.

Recorded cost and token use are reported **per run** over all 195 test
scenarios. Tokens include prompts and completions.

| Architecture | Gemini cost / tokens | DeepSeek cost / tokens | GPT-OSS cost / tokens | Qwen cost / tokens |
|---|---:|---:|---:|---:|
| `A_D` | $0.4812 / 569.7k | $0.0140 / 397.1k | $0.0145 / 492.2k | $0.0435 / 423.7k |
| `A_E` | $0.4284 / 531.8k | $0.0136 / 385.7k | $0.0143 / 479.7k | $0.0419 / 407.8k |
| `A_H` | **$0.0800 / 121.7k** | **$0.0056 / 103.0k** | **$0.0039 / 123.0k** | **$0.0119 / 112.4k** |

Multiply the cost columns by five for the corresponding five-run cell:
approximately `$2.4060`, `$2.1420`, `$0.4000`, `$0.0280`, `$0.0725`,
`$0.0195`, `$0.2175`, `$0.2095`, `$0.0595`, respectively, in table order.

## Reproducibility

### Requirements

- Python **3.11 or newer**;
- a fresh virtual environment is recommended;
- an OpenRouter API key only for collecting new model responses;
- no GPU is required for the deterministic analysis. The `A_E` index uses
  `sentence-transformers` and PyTorch; CPU execution is supported.

The pinned dependencies are listed in [`requirements.txt`](requirements.txt)
and installed by the package metadata in [`pyproject.toml`](pyproject.toml).

### Installation

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### API credentials

Copy [`.env.example`](.env.example) to `.env` and set:

```text
OPENROUTER_API_KEY=your_key_here
```

The key is loaded locally and must not be committed. `DEBUG_API` is an
optional setting that echoes raw HTTP payloads to stderr; leave it unset unless
debugging a provider integration.

### Rebuild the retrieval index

`A_E` requires a ChromaDB collection built from the 90 retrieval scenarios:

```powershell
python scripts\collection\build_rag_index.py
```

The builder records a schema version and hashes its three source workbooks.
Rebuild the index whenever those inputs change. The retrieval configuration in
the main benchmark is `sentence-transformers/all-MiniLM-L6-v2` with
`k = 1`, restricted to the same decision type as the query.

### Run a new benchmark

Set the model for each process. Use a new, explicit scratch directory for each
model/architecture combination:

```powershell
$env:MODEL_KEY = "gemini"
python architectures\Direct_LLM_Scoring.py --output-dir results\scratch\gemini\direct
python architectures\Example-Guided_LLM_Scoring.py --output-dir results\scratch\gemini\example-guided
python architectures\LLM-Parameterized_Reference_Scoring.py --output-dir results\scratch\gemini\parameterized
```

Valid `MODEL_KEY` values are `gemini`, `deepseek`, `gptoss` and `qwen`.
Repeat the three commands for each model. The runners are resume-aware:
completed run files are skipped on relaunch. They validate model outputs,
record diagnostics and fail explicitly rather than silently treating malformed
responses as valid scores.

The runners require `--output-dir` because collected benchmark data and frozen
paper inputs are protected from accidental overwrites. See
[`common/paths.py`](common/paths.py) for the output policy. Do not write new
raw runs directly into the frozen `Output Files ...` roots.

### Reproduce the analysis without an API key

The paper analysis consumes the tracked benchmark outputs and writes derived
artifacts to the appropriate results directories:

```powershell
python -m scripts.paper_pipeline.run_paper_pipeline
```

To inspect available stages before running:

```powershell
python -m scripts.paper_pipeline.run_paper_pipeline --list
```

The pipeline covers the deterministic metrics, confidence intervals, baseline
comparisons, prompt/listwise/RAG/ordering ablations, sensitivity analyses and
statistical comparisons. It makes no model API calls. The committed
[`Combined Metrics/`](Combined%20Metrics/) directory contains the cross-model
artifacts used by the manuscript.

### Tests and continuous integration

Run the unit and offline pipeline checks:

```powershell
python -m pytest -v
```

GitHub Actions runs the same test suite on Ubuntu with Python 3.12 and also
checks the deterministic weights stage in a clean checkout. See
[`.github/workflows/test.yml`](.github/workflows/test.yml).

### Manuscript

The manuscript and supplementary source are in [`paper/`](paper/). With a
working LaTeX installation, compile the main manuscript from that directory
using the project’s existing bibliography and class files. The generated
auxiliary files and PDFs are build products; the reproducibility-critical
inputs are the `.tex`, `.bib`, `.sty`, `.cls`, `.bst`, workbook and result
files tracked by the repository.

## Reported results

### Overall accuracy

The complete five-run mean table is:

| Model | Architecture | Kendall's `tau` | Top-1 accuracy | RMSE | MAE |
|---|---|---:|---:|---:|---:|
| Gemini 3.8 Flash | `A_H` | **0.891** | **90.2%** | 0.096 | 0.048 |
|  | `A_E` | 0.298 | 47.5% | 0.210 | 0.147 |
|  | `A_D` | 0.179 | 39.8% | 0.276 | 0.207 |
| DeepSeek V4 Flash | `A_H` | **0.856** | **88.6%** | 0.114 | 0.055 |
|  | `A_E` | 0.253 | 48.3% | 0.240 | 0.170 |
|  | `A_D` | 0.125 | 39.1% | 0.284 | 0.223 |
| GPT-OSS 20B | `A_H` | **0.805** | **82.5%** | 0.156 | 0.079 |
|  | `A_E` | 0.234 | 46.5% | 0.252 | 0.179 |
|  | `A_D` | 0.032 | 34.1% | 0.312 | 0.246 |
| Qwen3.5 9B | `A_H` | **0.836** | **86.5%** | 0.162 | 0.074 |
|  | `A_E` | 0.147 | 43.9% | 0.266 | 0.199 |
|  | `A_D` | 0.005 | 30.8% | 0.301 | 0.239 |

### Decision-type range

The best-to-worst model ranges in Kendall's `tau` are:

| Decision type | `A_D` | `A_E` | `A_H` |
|---|---:|---:|---:|
| Thermostat | -0.200 to 0.091 | -0.118 to 0.202 | 0.657 to 0.872 |
| Appliance | -0.114 to 0.110 | -0.073 to 0.303 | 0.908 to 0.949 |
| Shower | 0.093 to 0.696 | 0.249 to 0.780 | 0.821 to 0.856 |

### Baselines and robustness

- Dataset-median calculator: `tau = 0.590`, Top-1 `70.3%`.
- Nearest-neighbor reuse (`k = 1`): `tau = 0.374`, Top-1 `64.6%`.
- `A_H` improves over the median by `0.215` to `0.302` in `tau` and by
  12 to 20 percentage points in Top-1 accuracy.
- The `A_H` range across models is only `0.086`; the corresponding ranges are
  `0.174` for `A_D` and `0.151` for `A_E`.
- Retrieval depth `k = 1, 3, 5`, an alternative embedding, removal of hidden
  parameters, random exemplars and removal of reference scores were tested in
  leave-one-out RAG ablations. The architecture ordering remains intact,
  although the quality and number of retrieved solved cases matter.
- Prompt perturbations, listwise scoring, alternative-order reversal, value
  function curvature (`alpha` from `1.0` to `2.0`) and three alternative
  weight vectors were also evaluated. The principal `A_H > A_E > A_D`
  ordering is robust, with one reported Gemini/MEREC Thermostat exception
  between `A_D` and `A_E`.

### Failure accounting

Across five runs, `A_H` produced 87 failed scenario-runs, compared with 11 for
`A_D` and 1 for `A_E`. GPT-OSS produced 85 of the 87 `A_H` failures, including
82 on Thermostat; DeepSeek produced the other 2. These failures were primarily
out-of-bounds extracted parameters and are counted as wrong in the headline
metrics. Replacing failed GPT-OSS scenarios with successful observations from a
different run raises its `A_H` result from `tau = 0.805` to `0.864` and Top-1
from `82.5%` to `88.5%`. A production implementation should retry rejected
extractions and expose uncertainty rather than silently fall back.

## Interpretation and limitations

The benchmark supports a narrow engineering conclusion: deterministic tools
control score ranges, units and arithmetic, while the LLM is used for
natural-language parameter extraction. Direct scoring allows the model to
implicitly change the realized influence of criteria by choosing score spreads;
retrieved examples improve direct scoring but do not reliably correct those
spreads. The result should not be read as evidence that LLMs can replace
household preference elicitation or physical modeling.

Important limitations are:

1. `A_H` is evaluated against the same calculators it calls, so independent
   reference implementations and expert scoring are needed to rule out
   shared-model inflation.
2. Several constants are modeling choices, including the linear mains-water
   interpolation, 0.35 air changes per hour, 80% usable water-heater capacity,
   occupancy-setback multipliers, and 8-hour/6-hour appliance delay ceilings.
   Changing usable capacity to 70% or 100% changes the reference winner in
   3 of 80 Shower scenarios.
3. The normative household uses fixed 35/30/20/15 weights, all-electric
   heating assumptions, a 105 deg F shower target, and comfort/practicality
   curves that are not elicited from individual households. Humidity, gas
   heating, atypical schedules and nonstandard preferences are not represented.
4. The scenario design spans prescribed parameter ranges and categorical
   combinations but does not reproduce the joint distribution of real homes.
   Every scenario has three alternatives; larger choice sets may reduce error
   cancellation.
5. Results use Pennsylvania tariffs and PJM emissions factors. Transfer to
   other grids, tariffs, climates, household types or non-energy decisions is
   untested.
6. API model versions, provider routing and prices can change. Re-collection
   after a route change is a new benchmark run and should record the complete
   route, prompt, parameters, raw response and cost metadata.

## Repository structure

The following roadmap preserves the separation between source code, frozen
inputs, collected outputs, derived analyses and manuscript materials:

```text
LLM-MCDA-Paper/
├── architectures/                 # The three LLM integration runners
│   ├── Direct_LLM_Scoring.py
│   ├── Example-Guided_LLM_Scoring.py
│   └── LLM-Parameterized_Reference_Scoring.py
├── calculators/                   # Deterministic HVAC, appliance, shower models
├── common/                        # Paths, model config, MAVT and API utilities
├── data/                          # Scenario and supporting data files
├── workbooks/
│   ├── scenarios/                 # Test and disjoint RAG scenario workbooks
│   ├── ground_truth/              # Frozen calculator outputs
│   └── methodology/              # Methodology and weighting inputs
├── Output Files <model>/          # Frozen per-model collected outputs
├── Combined Metrics/              # Cross-model metrics, CIs and comparisons
├── archive/                       # Earlier frozen runs and archival artifacts
├── results/                       # Scratch and generated analysis destinations
├── scripts/
│   ├── collection/                # Workbook and ChromaDB preparation
│   ├── analysis/                  # Metric and diagnostic calculations
│   ├── experiments/               # Baselines and robustness experiments
│   ├── validation/                # CIs, significance and sensitivity checks
│   └── paper_pipeline/            # Deterministic paper-analysis entry point
├── tests/                         # Unit and offline regression tests
├── paper/                         # Main manuscript, supplementary material and bibliography
├── run_registry.py                # Run metadata and artifact registration
├── pyproject.toml                 # Package metadata and pytest configuration
├── requirements.txt               # Pinned Python dependencies
├── CITATION.cff                   # Machine-readable citation metadata
├── LICENSE                        # MIT license for software and manuscript source
└── DATA_LICENSE                   # CC BY 4.0 license for benchmark data and outputs
```

Generated files such as Python caches, LaTeX auxiliary files and local virtual
environments are not research inputs. Do not commit API keys, unreviewed raw
responses, or new artifacts into frozen directories.

## Data, software and citation

Software and LaTeX source are released under the [MIT License](LICENSE).
Scenario workbooks, reference scores, collected benchmark outputs and derived
metrics are released under [CC BY 4.0](DATA_LICENSE). Third-party source data
and standards remain subject to their own terms; consult the data license for
the precise scope.

If you use the benchmark, code or data, cite [`CITATION.cff`](CITATION.cff):

```bibtex
@dataset{nigam2026llmmcda,
  author       = {Nigam, Ahaan and Huang, River},
  title        = {LLM-MCDA: AI-Assisted Multi-Criteria Decision Analysis
                  for Household Energy Optimization},
  year         = {2026},
  publisher    = {GitHub},
  url          = {https://github.com/AN00927/LLM-MCDA-Paper}
}
```

## Contact

For questions about the benchmark or manuscript, contact
[Ahaan Nigam](mailto:ishaannigam27@gmail.com). Please include the commit,
model route, architecture, scenario pool, and analysis command when reporting
a reproducibility issue.
