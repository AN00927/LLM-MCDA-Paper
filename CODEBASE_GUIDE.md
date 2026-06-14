# CODEBASE_GUIDE.md

This file is the single-file codebase map for the LLM-MCDA benchmark repository. It explains the architecture, execution flows, function/module interactions, data contracts, output artifacts, and change/refactor impact for someone unfamiliar with the codebase.

Line references are current at guide creation and use the form `path:line_number`.

## 1. Project purpose and core model

This repository benchmarks three LLM-MCDA architectures for household energy decisions against deterministic physics-based Multi-Attribute Value Theory (MAVT) ground truth.

- Research framing: `README.md:10`
- Repository structure and architecture overview: `README.md:146`
- Agent operating guide and invariants: `CLAUDE.md:1`
- Decision types: `HVAC`, `Appliance`, `Shower`
- Criteria: `energy_cost`, `environmental`, `comfort`, `practicality`
- Criterion weights live in `model_config.py:23`
- Tie-break priority lives in `model_config.py:31`
- Failure sentinel is `1928` / `1928.0` / `"1928"` in `sentinel_utils.py:13`

MAVT formula used throughout:

```text
weighted_score = 0.30 * energy_cost
               + 0.35 * environmental
               + 0.20 * comfort
               + 0.15 * practicality
```

Higher weighted score is better; rank `1` is best.

## 2. Canonical file layout

```text
LLM-MCDA Paper/
├── Architectures/
│   ├── PurePrompting.py
│   ├── RAGDatabaseOptimized.py
│   └── Hybrid.py
├── Ground Truth/
│   ├── ground_truth_hvac.xlsx
│   ├── ground_truth_appliance.xlsx
│   └── ground_truth_shower.xlsx
├── Ground Truth Calculators/
│   ├── HVACGroundTruthCalculator.py
│   ├── ApplianceGroundTruthCalculator.py
│   └── ShowerGroundTruthCalculator.py
├── Miscellaneous Scripts/
│   ├── BuildRAG.py
│   ├── CalculateMetrics.py
│   ├── SyncRAGGroundTruth.py
│   ├── SensitivityAnalysis.py
│   ├── EntropyWeights.py
│   ├── ImpliedWeights.py
│   ├── MERCECWeights.py
│   ├── EvaluateHybridExtraction.py
│   └── RunRAGAblations.py
├── Scenario Files/
│   ├── ConsolidatedforSimaltaneousediting.xlsx
│   ├── HVACScenarios.xlsx
│   ├── ApplianceScenarios.xlsx
│   ├── ShowerScenarios.xlsx
│   ├── HVACRagScenarios.xlsx
│   ├── ApplianceRAGScenarios.xlsx
│   ├── ShowerRAGScenarios.xlsx
│   ├── TestScenarios.xlsx
│   └── rebuild_consolidated.py
├── Scoring Logic and Documentation/
├── tests/
├── model_config.py
├── sentinel_utils.py
├── run_benchmarks.py
├── requirements.txt
├── README.md
├── CLAUDE.md
├── XLSX_Schema_Map.md
└── PROVENANCE_AUDIT_PROMPT.md
```

Runtime/generated artifacts:

```text
chroma_rag_db/
Output Files GPT-OSS 20B/
Output Files Qwen3.5 9B/
Output Files DeepSeek V4 Flash/
Output Files Gemini 3.5 Flash/
```

## 3. Shared configuration and utilities

### `model_config.py`

`model_config.py` is the single source of truth for global benchmark configuration.

Important constants:

- `MODEL_KEY = "gptoss_weakest"` at `model_config.py:1`
- `N_RUNS = 10` at `model_config.py:2`
- `TEMPERATURE = 0.3` at `model_config.py:9`
- retry policy at `model_config.py:17`
- `CRITERION_WEIGHTS` at `model_config.py:23`
- `TIE_BREAK_PRIORITY` at `model_config.py:31`
- model specs and output folders at `model_config.py:34`

Helper functions:

- `get_model_id()` at `model_config.py:62`
- `get_output_folder()` at `model_config.py:73`
- `get_reasoning_effort()` at `model_config.py:79`
- `get_reasoning_payload()` at `model_config.py:84`

Refactor impact: changing this file affects all three architectures and all model-specific output routing.

### `sentinel_utils.py`

`sentinel_utils.py` centralizes score coercion, sentinel handling, table reading, atomic writes, and label normalization.

Important functions:

- `coerce_score()` at `sentinel_utils.py:18`
- `is_sentinel()` at `sentinel_utils.py:34`
- `has_sentinel_scores()` at `sentinel_utils.py:43`
- `coerce_score_series()` at `sentinel_utils.py:51`
- `read_table_clean()` at `sentinel_utils.py:61`
- `_atomic_write_xlsx()` at `sentinel_utils.py:142`
- `_atomic_write_json()` at `sentinel_utils.py:157`
- `_is_complete_run_file()` at `sentinel_utils.py:170`
- `house_age_to_band_label()` at `sentinel_utils.py:190`
- `appliance_age_to_band_label()` at `sentinel_utils.py:216`
- `gpm_to_flow_rate_label()` at `sentinel_utils.py:240`
- `format_embedding_text()` at `sentinel_utils.py:258`

The sentinel `1928` means failed/invalid score. It must not be averaged or ranked as a real value. Failed rows are converted to `NaN` during aggregation and then written back as `1928` only if all runs failed for that alternative.

The label helpers are shared by scenario rebuild, RAG index construction, and RAG query construction. Do not duplicate these transformations elsewhere.

## 4. Data ownership and schema contracts

### Master source

`Scenario Files/ConsolidatedforSimaltaneousediting.xlsx` is the source workbook for derived scenario sheets.

`Scenario Files/rebuild_consolidated.py` derives:

- `Scenario Files/TestScenarios.xlsx`
- `Scenario Files/HVACRagScenarios.xlsx`
- `Scenario Files/ApplianceRAGScenarios.xlsx`
- `Scenario Files/ShowerRAGScenarios.xlsx`

It also backs up first, cleans master pools, caches existing RAG scores, re-derives sheets, audits invariants, and enforces explicit Excel cell types.

Key constants:

- backup path and workbook path at `Scenario Files/rebuild_consolidated.py:29`
- shared label helpers imported at `Scenario Files/rebuild_consolidated.py:37`
- `backup()` at `Scenario Files/rebuild_consolidated.py:45`
- `clean_text()` at `Scenario Files/rebuild_consolidated.py:58`
- `to_clock()` at `Scenario Files/rebuild_consolidated.py:110`
- `alt_norm()` at `Scenario Files/rebuild_consolidated.py:137`
- `put()` for typed Excel writes at `Scenario Files/rebuild_consolidated.py:171`
- `export_standalone()` at `Scenario Files/rebuild_consolidated.py:184`
- canonical column definitions at `Scenario Files/rebuild_consolidated.py:224`
- `main()` at `Scenario Files/rebuild_consolidated.py:267`

Schema details are documented in `XLSX_Schema_Map.md:1`.

### Test scenarios

`Scenario Files/TestScenarios.xlsx` is architecture-facing. It contains generalized labels rather than exact engineering values:

- `house_age` is a band label.
- `appliance_age` is a band label.
- `flow_rate` is `low_flow`, `standard`, or `high_flow`.
- It does not expose exact HVAC `r_value`, `seer`, `hvac_age`, shower `gpm`, appliance `kwh_per_cycle`, or other true engineering values.
- Alternatives are text: HVAC setpoints, appliance times, shower durations.

### RAG scenarios

RAG scenario sheets are derived and should not be edited directly. They contain exact engineering values and ground-truth scores for the disjoint RAG corpus.

- HVAC RAG: `Scenario Files/HVACRagScenarios.xlsx`
- Appliance RAG: `Scenario Files/ApplianceRAGScenarios.xlsx`
- Shower RAG: `Scenario Files/ShowerRAGScenarios.xlsx`

RAG provenance rules are documented in `PROVENANCE_AUDIT_PROMPT.md:1`.

### Ground truth

Ground truth files are generated by the deterministic calculators:

- `Ground Truth/ground_truth_hvac.xlsx`
- `Ground Truth/ground_truth_appliance.xlsx`
- `Ground Truth/ground_truth_shower.xlsx`

They contain per-alternative criterion scores, `mavt_score`, `rank`, and raw physical quantities.

## 5. Execution flows

### 5.1 Run all architectures

Entry point: `run_benchmarks.py`.

Flow:

```text
run_benchmarks.main()
  -> run_architecture("RAGDatabaseOptimized")
  -> run_architecture("PurePrompting")
  -> run_architecture("Hybrid")
```

Important functions:

- `run_architecture()` at `run_benchmarks.py:14`
- `main()` at `run_benchmarks.py:30`

`run_architecture()` dynamically imports `Architectures.<architecture_name>` and sets a shared `API_CONFIG` at `run_benchmarks.py:19`.

### 5.2 Scenario derivation

Order when scenario data changes:

```text
python "Scenario Files/rebuild_consolidated.py"
python "Miscellaneous Scripts/BuildRAG.py"
```

`rebuild_consolidated.py` derives Test/RAG sheets from the master workbook. `BuildRAG.py` must run afterward because the Chroma source hash is computed from the RAG sheet bytes.

### 5.3 Ground truth generation

Order when a ground-truth calculator changes:

```text
python "Ground Truth Calculators/HVACGroundTruthCalculator.py"
python "Ground Truth Calculators/ApplianceGroundTruthCalculator.py"
python "Ground Truth Calculators/ShowerGroundTruthCalculator.py"
python "Miscellaneous Scripts/SyncRAGGroundTruth.py"
python "Miscellaneous Scripts/BuildRAG.py"
```

Calculator entry points:

- HVAC process entry: `Ground Truth Calculators/HVACGroundTruthCalculator.py:614`
- Appliance process entry: `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:543`
- Shower process entry: `Ground Truth Calculators/ShowerGroundTruthCalculator.py:474`

### 5.4 RAG index build

`Miscellaneous Scripts/BuildRAG.py` builds a ChromaDB persistent collection.

Important constants:

- `CHROMA_DB_PATH = PROJECT_ROOT / "chroma_rag_db"` at `Miscellaneous Scripts/BuildRAG.py:23`
- `COLLECTION_NAME = "mcda_scenarios"` at `Miscellaneous Scripts/BuildRAG.py:24`
- embedding model `sentence-transformers/all-MiniLM-L6-v2` at `Miscellaneous Scripts/BuildRAG.py:25`
- `RAG_SCHEMA_VERSION = 4` at `Miscellaneous Scripts/BuildRAG.py:44`

Important functions:

- `compute_source_table_hash()` at `Miscellaneous Scripts/BuildRAG.py:47`
- `load_hvac_data()` at `Miscellaneous Scripts/BuildRAG.py:63`
- `load_appliance_data()` at `Miscellaneous Scripts/BuildRAG.py:74`
- `load_shower_data()` at `Miscellaneous Scripts/BuildRAG.py:84`
- `format_scenario_text()` at `Miscellaneous Scripts/BuildRAG.py:94`
- `build_scenario_metadata()` at `Miscellaneous Scripts/BuildRAG.py:119`
- `build_rag_database()` at `Miscellaneous Scripts/BuildRAG.py:183`
- `test_retrieval()` at `Miscellaneous Scripts/BuildRAG.py:314`

`BuildRAG.py` stores full scenario metadata in Chroma, including per-alternative criterion scores, MAVT scores, and ranks. See metadata construction at `Miscellaneous Scripts/BuildRAG.py:168`.

### 5.5 Metrics evaluation

`Miscellaneous Scripts/CalculateMetrics.py` compares architecture outputs against ground truth.

Entry point:

- `evaluate_all()` at `Miscellaneous Scripts/CalculateMetrics.py:799`

Main flow:

```text
evaluate_all()
  -> load_ground_truth()
  -> load_architecture()
  -> aggregate_run_files() if per-run files exist
  -> _load_diagnostics_json()
  -> build_gt_lookup()
  -> build_gt_id_lookup()
  -> match_scenarios()
  -> filter_failed_scenarios()
  -> compute_criterion_metrics()
  -> compute_ranking_metrics()
  -> write metrics_summary_<MODEL_KEY>.xlsx
```

Important functions:

- config at `Miscellaneous Scripts/CalculateMetrics.py:25`
- deterministic ranking helper at `Miscellaneous Scripts/CalculateMetrics.py:81`
- sentinel row detection at `Miscellaneous Scripts/CalculateMetrics.py:127`
- alternative normalization at `Miscellaneous Scripts/CalculateMetrics.py:170`
- ground truth loading at `Miscellaneous Scripts/CalculateMetrics.py:197`
- architecture loading at `Miscellaneous Scripts/CalculateMetrics.py:224`
- per-run aggregation at `Miscellaneous Scripts/CalculateMetrics.py:257`
- GT lookup construction at `Miscellaneous Scripts/CalculateMetrics.py:349`
- scenario matching at `Miscellaneous Scripts/CalculateMetrics.py:410`
- criterion metrics at `Miscellaneous Scripts/CalculateMetrics.py:607`
- ranking metrics at `Miscellaneous Scripts/CalculateMetrics.py:633`
- failure-rate metrics at `Miscellaneous Scripts/CalculateMetrics.py:681`
- diagnostics JSON loading at `Miscellaneous Scripts/CalculateMetrics.py:725`

Scenario matching is content-based, not strict ID-based. Strict ID matching is disabled because architecture scenario IDs and GT scenario IDs do not align across files. See `Miscellaneous Scripts/CalculateMetrics.py:65` and `Miscellaneous Scripts/CalculateMetrics.py:410`.

## 6. Architecture comparison

| Architecture | File | LLM role | Deterministic role | API calls per scenario | Main output |
| --- | --- | --- | --- | --- | --- |
| Pure Prompting | `Architectures/PurePrompting.py` | Scores all four criteria directly for each alternative | Only MAVT aggregation after LLM scores | 3 | `pure_prompting_results.xlsx` |
| RAG-Enhanced | `Architectures/RAGDatabaseOptimized.py` | Scores alternatives with retrieved exemplar context | Retrieval + MAVT aggregation | 3 | `rag_results.xlsx` |
| Hybrid | `Architectures/Hybrid.py` | Extracts engineering parameters and calculator choice | Ground-truth calculator computes scores | 1 | `hybrid_results.xlsx` |

## 7. Pure Prompting architecture

File: `Architectures/PurePrompting.py`.

Purpose: ask the LLM to directly score each alternative on the four criteria, then aggregate by MAVT.

Important constants:

- test input: `TEST_SCENARIOS = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"` at `Architectures/PurePrompting.py:64`
- output files at `Architectures/PurePrompting.py:65`
- OpenRouter config at `Architectures/PurePrompting.py:82`
- failure counters at `Architectures/PurePrompting.py:94`

Important functions:

- `_init_failure_counters()` at `Architectures/PurePrompting.py:101`
- `query_openrouter()` at `Architectures/PurePrompting.py:114`
- `build_user_prompt()` at `Architectures/PurePrompting.py:213`
- `score_alternative()` at `Architectures/PurePrompting.py:248`
- `apply_mavt_ranking()` at `Architectures/PurePrompting.py:378`
- `run_scenario()` at `Architectures/PurePrompting.py:417`
- `run_test_set()` at `Architectures/PurePrompting.py:486`
- `run_multi_and_aggregate()` at `Architectures/PurePrompting.py:650`
- `main()` at `Architectures/PurePrompting.py:789`

Pure flow:

```text
main()
  -> run_multi_and_aggregate()
    -> for each run:
       -> run_test_set()
         -> read TestScenarios.xlsx
         -> for each scenario:
            -> run_scenario()
              -> for each alternative:
                 -> score_alternative()
                    -> build_user_prompt()
                    -> query_openrouter()
                    -> parse JSON scores
                    -> validate 0-10 range
                    -> return 1928 sentinel on failure
              -> apply_mavt_ranking()
         -> write per-run xlsx/json
    -> aggregate per-run xlsx files
    -> write averaged xlsx + stats xlsx
```

Output row fields are defined at `Architectures/PurePrompting.py:478`.

Aggregation details:

- per-run resume uses `_is_complete_run_file()` at `Architectures/PurePrompting.py:663`
- combines per-run files at `Architectures/PurePrompting.py:707`
- converts sentinel to `NaN` at `Architectures/PurePrompting.py:710`
- averages valid scores at `Architectures/PurePrompting.py:729`
- restores `1928` when every run failed at `Architectures/PurePrompting.py:752`
- recomputes rank from averaged scores at `Architectures/PurePrompting.py:760`

## 8. RAG-Enhanced architecture

File: `Architectures/RAGDatabaseOptimized.py`.

Purpose: retrieve similar pre-scored scenarios from ChromaDB and include them as exemplars before asking the LLM to score each alternative.

Important constants:

- test input at `Architectures/RAGDatabaseOptimized.py:40`
- output files at `Architectures/RAGDatabaseOptimized.py:41`
- Chroma path at `Architectures/RAGDatabaseOptimized.py:62`
- collection name at `Architectures/RAGDatabaseOptimized.py:63`
- embedding model at `Architectures/RAGDatabaseOptimized.py:64`
- retrieval count `RETRIEVE_K = 3` at `Architectures/RAGDatabaseOptimized.py:65`
- expected RAG schema version at `Architectures/RAGDatabaseOptimized.py:67`
- RAG source files at `Architectures/RAGDatabaseOptimized.py:68`

Important functions:

- `_compute_expected_source_hash()` at `Architectures/RAGDatabaseOptimized.py:75`
- `init_rag_resources()` at `Architectures/RAGDatabaseOptimized.py:121`
- `query_openrouter()` at `Architectures/RAGDatabaseOptimized.py:152`
- `build_system_prompt()` at `Architectures/RAGDatabaseOptimized.py:236`
- `format_scenario_text_for_retrieval()` at `Architectures/RAGDatabaseOptimized.py:253`
- `retrieve_similar_scenarios()` at `Architectures/RAGDatabaseOptimized.py:264`
- `_exemplar_param_lines()` at `Architectures/RAGDatabaseOptimized.py:317`
- `format_rag_context()` at `Architectures/RAGDatabaseOptimized.py:361`
- `build_user_prompt_with_rag()` at `Architectures/RAGDatabaseOptimized.py:408`
- `score_alternative_with_rag()` at `Architectures/RAGDatabaseOptimized.py:450`
- `apply_mavt_ranking()` at `Architectures/RAGDatabaseOptimized.py:553`
- `run_scenario()` at `Architectures/RAGDatabaseOptimized.py:595`
- `run_test_set()` at `Architectures/RAGDatabaseOptimized.py:677`
- `run_multi_and_aggregate()` at `Architectures/RAGDatabaseOptimized.py:865`
- `main()` at `Architectures/RAGDatabaseOptimized.py:1009`

RAG flow:

```text
main()
  -> run_multi_and_aggregate()
    -> init_rag_resources()
       -> load Chroma collection
       -> verify schema_version == 4
       -> verify source_table_sha256 matches current RAG sheets
       -> load SentenceTransformer embedding model
    -> for each run:
       -> run_test_set()
         -> read TestScenarios.xlsx
         -> for each scenario:
            -> run_scenario()
              -> for each alternative:
                 -> score_alternative_with_rag()
                    -> retrieve_similar_scenarios()
                       -> format_scenario_text_for_retrieval()
                       -> format_embedding_text()
                       -> Chroma query filtered by decision_type
                    -> format_rag_context()
                    -> build_user_prompt_with_rag()
                    -> query_openrouter()
                    -> parse/validate JSON
              -> apply_mavt_ranking()
         -> write per-run xlsx/json
    -> aggregate per-run xlsx files
    -> write averaged xlsx + stats xlsx
```

RAG schema/version contract:

- `BuildRAG.py` writes `schema_version` and `source_table_sha256` into Chroma metadata at `Miscellaneous Scripts/BuildRAG.py:203`.
- `RAGDatabaseOptimized.py` verifies those values at `Architectures/RAGDatabaseOptimized.py:128`.
- If the RAG sheets change but Chroma is stale, rerun `Miscellaneous Scripts/BuildRAG.py`.
- If the embedding text or metadata schema changes, bump `RAG_SCHEMA_VERSION` in both `Miscellaneous Scripts/BuildRAG.py:44` and `Architectures/RAGDatabaseOptimized.py:67`, then rebuild.

## 9. Hybrid architecture

File: `Architectures/Hybrid.py`.

Purpose: use the LLM only to infer hidden engineering parameters, then use deterministic ground-truth calculators to score all alternatives.

Important constants:

- test input at `Architectures/Hybrid.py:36`
- ground-truth calculator directory at `Architectures/Hybrid.py:39`
- calculator loader at `Architectures/Hybrid.py:41`
- loaded calculators at `Architectures/Hybrid.py:51`
- output files at `Architectures/Hybrid.py:85`
- output columns at `Architectures/Hybrid.py:88`
- numeric extraction columns at `Architectures/Hybrid.py:102`
- categorical extraction columns at `Architectures/Hybrid.py:107`
- failure counters at `Architectures/Hybrid.py:112`
- numeric parameter bounds at `Architectures/Hybrid.py:128`

Important functions:

- `_load_calculator_class()` at `Architectures/Hybrid.py:41`
- `_validate_numeric_params()` at `Architectures/Hybrid.py:152`
- `_init_failure_counters()` at `Architectures/Hybrid.py:175`
- `_extracted_parameter_cells()` at `Architectures/Hybrid.py:179`
- `query_openrouter()` at `Architectures/Hybrid.py:259`
- `format_scenario_for_extraction()` at `Architectures/Hybrid.py:330`
- `extract_all_with_ai()` at `Architectures/Hybrid.py:352`
- `score_with_ground_truth()` at `Architectures/Hybrid.py:510`
- `apply_mavt_ranking()` at `Architectures/Hybrid.py:585`
- `run_scenario()` at `Architectures/Hybrid.py:624`
- `run_test_set()` at `Architectures/Hybrid.py:802`
- `run_multi_and_aggregate()` at `Architectures/Hybrid.py:1007`
- `main()` at `Architectures/Hybrid.py:1195`

Hybrid flow:

```text
main()
  -> run_multi_and_aggregate()
    -> for each run:
       -> run_test_set()
         -> read TestScenarios.xlsx
         -> for each scenario:
            -> run_scenario()
              -> extract_all_with_ai()
                 -> format_scenario_for_extraction()
                 -> query_openrouter()
                 -> require strict JSON wrapper
                 -> validate decision_type/calculator
                 -> validate required params
                 -> validate numeric bounds
              -> if extraction failed:
                 -> return sentinel scores or API fallback
              -> score_with_ground_truth()
                 -> merge scenario + extracted parameters
                 -> instantiate correct calculator
                 -> call calculate_scenario_scores()
              -> apply_mavt_ranking()
         -> write per-run xlsx/json
    -> aggregate per-run xlsx files
    -> write averaged xlsx + stats xlsx
```

Important Hybrid invariants:

- The LLM extracts only engineering parameters. Alternatives come verbatim from `TestScenarios.xlsx` at `Architectures/Hybrid.py:510`.
- The extracted decision type must match the known scenario decision type; mismatches are rejected rather than scored by the wrong calculator at `Architectures/Hybrid.py:439`.
- Numeric extraction failures must not be coerced to `0.0`; invalid extracted parameters become failure/sentinel outputs at `Architectures/Hybrid.py:152`.
- Hybrid output includes extraction diagnostics and flags such as `extraction_failed` and `gt_calculation_failed` at `Architectures/Hybrid.py:88`.

Aggregation details:

- resume logic at `Architectures/Hybrid.py:1020`
- combine per-run files at `Architectures/Hybrid.py:1063`
- convert sentinel to `NaN` at `Architectures/Hybrid.py:1066`
- aggregate numeric extracted parameters by mean at `Architectures/Hybrid.py:1095`
- aggregate categorical extracted parameters by mode at `Architectures/Hybrid.py:1108`
- aggregate boolean flags with `any()` at `Architectures/Hybrid.py:1129`
- restore sentinel when all runs failed at `Architectures/Hybrid.py:1154`
- recompute rank from averaged scores at `Architectures/Hybrid.py:1162`

## 10. Ground-truth calculators

The calculators are deterministic physics/behavioral models. They produce the scores that RAG exemplars and metrics use as ground truth.

### HVAC calculator

File: `Ground Truth Calculators/HVACGroundTruthCalculator.py`.

Important constants:

- emissions factors at `Ground Truth Calculators/HVACGroundTruthCalculator.py:20`
- electricity rate at `Ground Truth Calculators/HVACGroundTruthCalculator.py:29`
- comfort ranges at `Ground Truth Calculators/HVACGroundTruthCalculator.py:39`
- value-function types at `Ground Truth Calculators/HVACGroundTruthCalculator.py:46`

Important functions:

- `calculate_cooling_load()` at `Ground Truth Calculators/HVACGroundTruthCalculator.py:59`
- `calculate_heating_load()` at `Ground Truth Calculators/HVACGroundTruthCalculator.py:101`
- `calculate_scenario_scores()` at `Ground Truth Calculators/HVACGroundTruthCalculator.py:448`
- `process_hvac_scenarios()` at `Ground Truth Calculators/HVACGroundTruthCalculator.py:614`
- `apply_mavt_ranking()` at `Ground Truth Calculators/HVACGroundTruthCalculator.py:721`

HVAC scoring highlights:

- parses numeric setpoints and `Off` alternatives at `Ground Truth Calculators/HVACGroundTruthCalculator.py:457`
- computes cooling or heating load at `Ground Truth Calculators/HVACGroundTruthCalculator.py:486`
- computes kWh, cost, emissions, comfort, and practicality at `Ground Truth Calculators/HVACGroundTruthCalculator.py:511`
- applies budget penalty to energy-cost value at `Ground Truth Calculators/HVACGroundTruthCalculator.py:583`
- writes `ground_truth_hvac.xlsx` at `Ground Truth Calculators/HVACGroundTruthCalculator.py:614`

### Appliance calculator

File: `Ground Truth Calculators/ApplianceGroundTruthCalculator.py`.

Important constants:

- emissions factors at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:19`
- utility rate windows at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:27`
- city-to-utility mapping at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:48`
- noise limit at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:73`
- value-function types at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:78`

Important functions:

- `calculate_scenario_scores()` at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:434`
- `process_appliance_scenarios()` at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:543`
- `apply_mavt_ranking()` at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:672`

Appliance scoring highlights:

- parses alternatives into run time and delay at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:442`
- computes energy cost, emissions, comfort, and practicality at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:451`
- emits sentinel if a scoring alternative fails at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:465`
- applies budget penalty at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:498`
- writes `ground_truth_appliance.xlsx` at `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:543`

### Shower calculator

File: `Ground Truth Calculators/ShowerGroundTruthCalculator.py`.

Important constants:

- electricity rate at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:27`
- inlet water temperatures at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:32`
- heater efficiency and target shower temp at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:38`
- comfort duration thresholds at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:46`
- cold-weather comfort shift at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:53`
- heater safety thresholds at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:66`
- value-function types at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:84`

Important functions:

- `determine_inlet_temp()` at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:94`
- `calculate_shower_energy()` at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:105`
- `calculate_scenario_scores()` at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:359`
- `process_shower_scenarios()` at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:474`
- `apply_mavt_ranking()` at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:568`

Shower scoring highlights:

- environmental impact is water volume, not CO₂.
- inlet temperature is interpolated from outdoor temperature at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:94`.
- hot-water fraction and shower energy are computed in `calculate_shower_energy()` at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:105`.
- comfort and practicality account for duration, heater temperature, occupants, tank size, and outdoor temperature at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:381`.
- budget penalty is applied at `Ground Truth Calculators/ShowerGroundTruthCalculator.py:439`.

## 11. Output artifacts

Each architecture writes per-run files and an averaged final file under the active model output folder from `model_config.py`.

### Pure Prompting

- per-run: `<output_folder>/pure_prompting_results_run_NN.xlsx`
- per-run diagnostics: `<output_folder>/pure_prompting_results_diagnostics_run_NN.json`
- averaged: `<output_folder>/pure_prompting_results.xlsx`
- diagnostics: `<output_folder>/pure_prompting_results_diagnostics.json`
- stats: `<output_folder>/pure_prompting_results_stats.xlsx`

### RAG-Enhanced

- per-run: `<output_folder>/rag_results_run_NN.xlsx`
- per-run diagnostics: `<output_folder>/rag_results_diagnostics_run_NN.json`
- averaged: `<output_folder>/rag_results.xlsx`
- diagnostics: `<output_folder>/rag_results_diagnostics.json`
- stats: `<output_folder>/rag_results_stats.xlsx`

### Hybrid

- per-run: `<output_folder>/hybrid_results_run_NN.xlsx`
- per-run diagnostics: `<output_folder>/hybrid_results_diagnostics_run_NN.json`
- averaged: `<output_folder>/hybrid_results.xlsx`
- diagnostics: `<output_folder>/hybrid_results_diagnostics.json`
- stats: `<output_folder>/hybrid_results_stats.xlsx`

### Metrics

`CalculateMetrics.py` writes:

```text
<output_folder>/metrics_summary_<MODEL_KEY>.xlsx
```

It also prints overall and per-decision-type metric tables.

## 12. Module interaction graph

### Shared utilities used by architecture modules

All architecture modules import:

- `_atomic_write_json`
- `_atomic_write_xlsx`
- `_is_complete_run_file`
- `has_sentinel_scores`
- `read_table_clean`

RAG also imports `format_embedding_text`.

See imports:

- Pure: `Architectures/PurePrompting.py:44`
- RAG: `Architectures/RAGDatabaseOptimized.py:19`
- Hybrid: `Architectures/Hybrid.py:16`

### Ground truth calculators used by Hybrid

Hybrid dynamically loads calculator classes at import time:

- HVAC: `Architectures/Hybrid.py:51`
- Appliance: `Architectures/Hybrid.py:58`
- Shower: `Architectures/Hybrid.py:65`

`score_with_ground_truth()` dispatches to the correct calculator at `Architectures/Hybrid.py:538`.

### RAG index used by RAG architecture

`BuildRAG.py` writes Chroma metadata. `RAGDatabaseOptimized.py` reads and validates it.

- source hash in BuildRAG: `Miscellaneous Scripts/BuildRAG.py:47`
- source hash in RAG runtime: `Architectures/RAGDatabaseOptimized.py:75`
- metadata write: `Miscellaneous Scripts/BuildRAG.py:203`
- metadata validation: `Architectures/RAGDatabaseOptimized.py:128`
- retrieval query: `Architectures/RAGDatabaseOptimized.py:280`

### Metrics script reads architecture outputs and ground truth

`CalculateMetrics.py` does not consume architecture JSON directly for scoring metrics. It reads XLSX outputs or per-run XLSX files and separately loads diagnostics JSON for failure-mode counters.

- architecture config at `Miscellaneous Scripts/CalculateMetrics.py:33`
- aggregate run files at `Miscellaneous Scripts/CalculateMetrics.py:257`
- diagnostics JSON at `Miscellaneous Scripts/CalculateMetrics.py:725`

## 13. Tests and audits

### `tests/test_sentinel_aggregation_matching.py`

Covers sentinel coercion, aggregation, diagnostics JSON loading, scenario matching, RAG metadata fields, and retry policy.

Scope documented at `tests/test_sentinel_aggregation_matching.py:1`.

Important test groups:

- sentinel coercion at `tests/test_sentinel_aggregation_matching.py:56`
- aggregation at `tests/test_sentinel_aggregation_matching.py:186`
- diagnostics JSON loading at `tests/test_sentinel_aggregation_matching.py:263`
- scenario matching at `tests/test_sentinel_aggregation_matching.py:340`
- shower matching at `tests/test_sentinel_aggregation_matching.py:467`
- RAG metadata fields at `tests/test_sentinel_aggregation_matching.py:626`
- retry policy at `tests/test_sentinel_aggregation_matching.py:692`

### `tests/audit_scenarios.py`

Audits scenario/GT/RAG relationships and coverage.

Entry point: `tests/audit_scenarios.py:105`.

### `PROVENANCE_AUDIT_PROMPT.md`

Human/LLM-readable provenance contract for Test/RAG derivation.

Important invariants:

- RAG/Test partition at `PROVENANCE_AUDIT_PROMPT.md:22`
- field transformation rules at `PROVENANCE_AUDIT_PROMPT.md:37`
- matching procedure at `PROVENANCE_AUDIT_PROMPT.md:51`

## 14. Requirements

Dependencies are listed in `requirements.txt:1`.

Key packages:

- `chromadb==1.5.2`
- `numpy==2.4.2`
- `openpyxl==3.1.5`
- `pandas==3.0.1`
- `python-dotenv==1.2.1`
- `requests==2.32.5`
- `scipy==1.17.1`
- `sentence-transformers==5.2.3`

## 15. Common commands

Use PowerShell-style quoting for paths with spaces.

Run all architectures:

```powershell
python run_benchmarks.py
```

Run one architecture:

```powershell
python "Architectures/PurePrompting.py"
python "Architectures/RAGDatabaseOptimized.py"
python "Architectures/Hybrid.py"
```

Rebuild Test/RAG sheets from the master workbook:

```powershell
python "Scenario Files/rebuild_consolidated.py"
```

Regenerate ground truth:

```powershell
python "Ground Truth Calculators/HVACGroundTruthCalculator.py"
python "Ground Truth Calculators/ApplianceGroundTruthCalculator.py"
python "Ground Truth Calculators/ShowerGroundTruthCalculator.py"
```

Refresh RAG score columns after calculator changes:

```powershell
python "Miscellaneous Scripts/SyncRAGGroundTruth.py"
```

Rebuild the RAG vector database:

```powershell
python "Miscellaneous Scripts/BuildRAG.py"
```

Compute metrics:

```powershell
python "Miscellaneous Scripts/CalculateMetrics.py"
```

Run focused tests:

```powershell
python -m pytest tests/test_sentinel_aggregation_matching.py
```

Run scenario audit script:

```powershell
python "tests/audit_scenarios.py"
```

## 16. Change and refactor impact matrix

| Change | Immediate affected files | Required follow-up | Risk if skipped |
| --- | --- | --- | --- |
| Change `CRITERION_WEIGHTS` | `model_config.py:23`, all architectures, calculators, metrics | rerun all architectures and metrics | scores/ranks become incomparable |
| Change `TIE_BREAK_PRIORITY` | `model_config.py:31`, calculators, metrics | update architecture rankers if they should match GT tie-break; rerun metrics | GT and architecture ranks may disagree on ties |
| Change API model, temperature, retry policy | `model_config.py`, all architecture `query_openrouter` functions | rerun affected architectures | outputs reflect different model behavior |
| Change `N_RUNS` | `model_config.py`, all `run_multi_and_aggregate` loops | rerun benchmarks | old outputs may mix different run counts |
| Change scenario master workbook | `Scenario Files/rebuild_consolidated.py` | rerun rebuild, rebuild RAG, rerun affected outputs | Test/RAG sheets drift from source |
| Change age/flow banding | `sentinel_utils.py`, `rebuild_consolidated.py`, `BuildRAG.py`, `RAGDatabaseOptimized.py` | rebuild Test/RAG, rebuild Chroma | RAG query/index text no longer matches |
| Change ground-truth formula | domain calculator | rerun calculator, `SyncRAGGroundTruth.py`, `BuildRAG.py`, all architectures, metrics | RAG exemplars and metrics use stale GT |
| Change RAG metadata schema or embedding text | `BuildRAG.py`, `RAGDatabaseOptimized.py`, `sentinel_utils.py` | bump `RAG_SCHEMA_VERSION` in both files, rebuild Chroma | stale Chroma metadata can silently corrupt retrieval |
| Change Pure prompt | `Architectures/PurePrompting.py` | rerun Pure only | other architectures remain comparable |
| Change RAG prompt/context | `Architectures/RAGDatabaseOptimized.py` | rerun RAG only | Pure/Hybrid remain comparable |
| Change Hybrid extraction prompt or validation | `Architectures/Hybrid.py` | rerun Hybrid only | Pure/RAG remain comparable |
| Change metric matching | `Miscellaneous Scripts/CalculateMetrics.py` | rerun metrics only | benchmark outputs need not change |
| Change output schema | architecture and metrics | update `CalculateMetrics.py` column mappings and tests | metrics may drop columns or misread fields |
| Add new architecture | new file under `Architectures/`, `run_benchmarks.py`, metrics config | add tests for sentinel/aggregation/output schema | new outputs may not be evaluated |

## 17. Known consistency points to watch during refactors

1. Sentinel handling must remain centralized. Do not introduce new failure values.
2. Do not average `1928` as if it were a score.
3. Do not let failed numeric extraction become `0.0`; zero energy/cost can become a fabricated perfect score.
4. RAG query text and RAG index text must be produced from the same embedding formatter. The shared function is `format_embedding_text()` at `sentinel_utils.py:258`.
5. RAG schema version must be bumped in both `BuildRAG.py` and `RAGDatabaseOptimized.py` when embedding or metadata changes.
6. Scenario IDs are not globally aligned across Test, RAG, and Ground Truth. Metrics match by content and normalized alternatives, not by raw ID.
7. Ground-truth calculators currently use `TIE_BREAK_PRIORITY` in their ranking helpers, while the three architecture `apply_mavt_ranking()` functions sort by weighted score only:
   - Pure: `Architectures/PurePrompting.py:378`
   - RAG: `Architectures/RAGDatabaseOptimized.py:553`
   - Hybrid: `Architectures/Hybrid.py:585`
   - HVAC GT tie-break: `Ground Truth Calculators/HVACGroundTruthCalculator.py:736`
   - Appliance GT tie-break: `Ground Truth Calculators/ApplianceGroundTruthCalculator.py:691`
   - Shower GT tie-break: `Ground Truth Calculators/ShowerGroundTruthCalculator.py:583`
8. If ranking determinism matters for tied alternatives, centralize MAVT ranking in one helper and update all callers.

## 18. Suggested refactor directions

Good refactor targets, if the goal is maintainability:

- Centralize OpenRouter request logic into one client module.
- Centralize MAVT scoring and deterministic tie-break into one helper.
- Centralize output row construction so architecture outputs share column semantics.
- Split large prompt strings into smaller builders.
- Replace dynamic imports in `run_benchmarks.py` with an explicit architecture registry.
- Add a shared architecture contract describing required functions and output schema.
- Move RAG schema/version constants into a shared config module to avoid two-version drift.
- Add integration tests that use synthetic in-memory data for aggregation and metrics without requiring API calls.

Refactors that would be risky:

- Changing the sentinel value.
- Changing RAG embedding text without rebuilding Chroma.
- Changing scenario-derived sheet schemas without updating `XLSX_Schema_Map.md`, `CalculateMetrics.py`, and tests.
- Changing ground-truth formulas without refreshing RAG exemplars and metrics.

## 19. Practical mental model

Think of the repository as four layers:

1. **Scenario layer**: master workbook -> derived Test/RAG sheets.
2. **Truth layer**: deterministic calculators -> `Ground Truth/*.xlsx`.
3. **Architecture layer**: Pure, RAG, Hybrid produce per-run and averaged architecture outputs.
4. **Evaluation layer**: metrics script matches architecture outputs to ground truth and reports MAE/RMSE, ranking correlation, top-1/top-2 accuracy, failure rates, and diagnostics.

The safest way to reason about a change is to identify which layer it touches, then follow the required refresh chain above.
