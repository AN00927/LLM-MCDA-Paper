# SCRIPT_FIXES_REPORT: pre-rerun fixes to the experiment and analysis scripts

Written 2026-09-26. Scope: the ten items in the brief, all in non-architecture scripts. No
edit to `Architectures/`, `sentinel_utils.py`, `model_config.py`, `Analysis/rerun_prep/arch_new/`,
the paper, the supplement, the bib, `README.md` or `CLAUDE.md`. No provider routing,
`max_tokens` or truncation handling was added to the ablation scripts. No API call.

- Full diff of these changes only: `paper/pass6/verify/SCRIPT_FIXES.diff` (base = each file as
  it stood immediately before my edits, so the other agents' earlier uncommitted hunks in the
  experiment scripts are not in it; `git diff` on those files would mix both).
- New files: `paper_pipeline/single_criterion.py`, `paper/pass6/RERUN_RUNBOOK.md`, this report.
- Scratch (session scratchpad `sf/`): pre-edit snapshots (`orig/`), `nn/nn_eval.py` and
  `nn/ckpt_test.py`, `sc_eval.py`, `gate/` (pipeline-gate copy), `nor*/`, `t8/`, `cw/`.
- Line numbers below are in the edited files as they now stand.

`model_config.py` changed on disk while I worked (the author's edit, not mine): `MODEL_KEY` now
comes from the environment, every model has a pinned `provider` entry, Gemini effort is `low`,
DeepSeek writes to `Output Files DeepSeek V4 Flash 0731`, labels were repriced. The runbook
reflects it. One consequence to check: the entries have `only` + `allow_fallbacks: false` but
no `"require_parameters": true`, and an entry replaces the arch patch's default, so that flag
is no longer sent.

---

## Item 1. Nearest-neighbour label matching (MUST-FIX) and `--nn-fallback`

**Diff.**
- `Miscellaneous Scripts/experiments/run_rag_ablation_experiments.py`
  - L718 `NN_FALLBACKS = ("tie", "nearest", "unscored")`.
  - L721-757 `canonical_alternative(value, decision_type)`: one key for both sides. Shower:
    minutes as a float (`8`, `"8"`, `8.0`, `"8 min"` all give `8.0`); HVAC: int setpoint or
    `"off"`; Appliance: minutes after midnight from `"2:00 PM"`, `"2pm"` or `"14:00"`.
  - L760-770 `_alternative_distance`: degrees, minutes on a 24 h circle, shower minutes; None
    for HVAC Off.
  - L773-850 `nearest_neighbor_prediction(scenario, retrieved, fallback="tie")`: both labels go
    through `canonical_alternative`; the fallback applies to a target alternative no exemplar
    shares:
    - `tie` (default, the old rule): mean over every retrieved alternative.
    - `nearest`: mean over the exemplar alternatives nearest in value (all ties at the minimum
      distance); a target with no numeric value (HVAC Off) or no numeric exemplar falls back to
      `tie`.
    - `unscored`: when **no** target alternative matches (the case where `tie` makes all three
      identical), every alternative gets the sentinel and the scenario drops out of the means;
      a partial miss keeps the `tie` rule. This is V_BASELINE issue 2's definition. A stricter
      "any miss" version left only 11/70 HVAC and 5/65 Appliance test scenarios scored, so I
      did not keep it.
  - L1590 the copy-only arm passes `fallback=nn_fallback`; L2085-2094 `--nn-fallback` option;
    the result rows gain an `nn_fallback` column.
- `Miscellaneous Scripts/core-automation/run_baseline_models.py` (the test-set NN):
  L41 imports `NN_FALLBACKS`; L351/L380 `run_nearest_neighbor_baseline(..., fallback)`;
  L473/L483 `run_all_baselines(..., nn_fallback)`; L491-494 `--nn-fallback`; L511.

Callers (grep): the RAG ablation's `build_result_rows` and `run_baseline_models.run_nearest_neighbor_baseline`
are the only two live ones. `Analysis/rerun_prep/pipeline/nn_check.py` reaches the second through
`run_baseline_models`; `Analysis/rerun_prep/pipeline/orig/` is an archived copy (not edited).

**Numbers, current data (shipped calculators and RAG sheets).** "before" = the code as it stood.
Test-set NN is scored by `evaluate_baseline_metrics`' matcher (as `nn_check.py`); the copy-only
control by the RAG ablation's own `scenario_metrics` (90 RAG scenarios, leave-one-out).

Test-set NN (195 Test scenarios):

| Variant | HVAC tau / Top-1 (n) | Appliance tau / Top-1 (n) | Shower tau / Top-1 (n) | all-3-identical H/A/S |
|---|---|---|---|---|
| before | 0.133 / 42.9% (70) | 0.292 / 55.4% (65) | **0.733 / 75.0%** (60) | 8 / 10 / **60** |
| after, `tie` | 0.133 / 42.9% (70) | 0.292 / 55.4% (65) | **0.278 / 43.3%** (60) | 8 / 10 / 10 |
| after, `nearest` | 0.257 / 48.6% (70) | 0.128 / 38.5% (65) | 0.511 / 65.0% (60) | 6 / 0 / 5 |
| after, `unscored` (conditional) | 0.108 / 41.9% (62) | 0.188 / 47.3% (55) | 0.160 / 34.0% (50) | 0 / 0 / 0 |
| after, `unscored` (inclusive: tau 0, Top-1 1/3) | 0.095 / 41.0% | 0.159 / 45.1% | 0.133 / 33.9% | |

RAG-ablation copy-only control (35 / 35 / 20):

| Variant | HVAC tau / Top-1 (n scored) | Appliance | Shower |
|---|---|---|---|
| before | 0.010 / 34.3% (35) | 0.200 / 40.0% (35) | 0.433 / 65.0% (20) |
| after, `tie` | 0.010 / 34.3% (35) | 0.200 / 40.0% (35) | 0.233 / 60.0% (20) |
| after, `nearest` | 0.124 / 51.4% (35) | -0.029 / 25.7% (35) | 0.400 / 60.0% (20) |
| after, `unscored` | 0.000 / 31.4% (28) | 0.146 / 31.4% (32) | 0.263 / 60.0% (19) |

- The fix changes Shower only; HVAC and Appliance labels already matched (confirmed: same numbers).
- The "before" copy-only row is the current rank-based tau, not the published 0.001 (which
  dropped 30 tied scenarios, V_BASELINE issue 3).
- Under `nearest`, 6 HVAC and 5 Shower test scenarios still get three identical predictions
  (two targets nearest to the same exemplar value, or HVAC Off), so list order still decides
  those.
- Under `unscored`, the RAG ablation's `scenario_metrics` drops an unscored scenario from tau
  but counts it as Top-1 wrong (the same pre-existing convention it applies to a failed LLM
  scenario). Top-1 over scored scenarios only: 39.3% / 34.4% / 63.2%. Not changed; see open items.

**Left for the author:** D6 in the runbook, the choice of `tie` / `nearest` / `unscored` (pass
the same value to both scripts).

## Item 2. RAG-ablation Top-1 / Top-2 from tie-broken ranks (S6)

**Diff.** `run_rag_ablation_experiments.py` L1027-1032 (`scenario_metrics`): `gt_top1` is the
alternative with reference `rank == 1`, `pred_top1` the one with predicted `rank == 1`,
`pred_top2` those with `rank <= 2` (over non-sentinel predictions), replacing the raw-sum sorts.

**Numbers.** Recomputed from the stored `gt_rank` / `pred_rank` of the shipped
`rag_ablation_results.xlsx`: Top-1 and Top-2 identical in 2,610 / 2,610 scenario rows (no
exact predicted tie reached a different winner on the shipped data). The fix only matters for
future exact ties.

## Item 3. RAG-ablation checkpoint (S7)

**Diff.** `run_rag_ablation_experiments.py`:
- L1414-1482: `CHECKPOINT_FORMAT`, `_json_default`, `source_files_sha256`, `checkpoint_path`,
  `_checkpoint_header`, `load_checkpoint`, `write_checkpoint` (tmp file + `os.replace`).
- L1484-1515 docstring and signature: `build_result_rows(..., checkpoint_dir=None, run_meta=None)`.
- L1530-1561: per unit, load the checkpoint; retrieval is always re-run (cheap, local) so the
  random arm's shared `rng` keeps the draw order of an uninterrupted run, and the saved exemplar
  ids must equal the recomputed ones or the run stops.
- L1563-1670: rows carry the unit's `collected_utc` (start) and `collected_utc_end`; the unit
  is written after its thread pool has been joined (main thread only, so writes never race),
  then read back, so the final xlsx is the union of the checkpoints. A unit in which every API
  call failed is not saved and stops the run.
- L1791-1812 `run()`: `run_meta` (seed, sample size, RAG-sheet SHA-256, `nn_fallback`); the
  per-row `collected_utc` is kept instead of one stamp for the whole collection.
- L2095-2101 `--no-checkpoint`.
- Checkpoints: `<output-dir>/checkpoints/<ablation_id>__<model_key>.json`. A header mismatch
  (model id, seed, sample, RAG-sheet hash, spec, fallback) raises instead of mixing runs.

**Test** (`nn/ckpt_test.py`, fake LLM, 4 worker threads, control + random + copy-only, 2
models): the first run wrote 5 units (360 fake calls). After deleting two checkpoints (one of
them a random-arm unit that comes after a skipped random unit), the rerun made exactly
180 calls, and the final 1,350 rows were identical to the first run's apart from timestamps. A
changed seed raised the mismatch error.

**Caveat found in testing:** the header does not cover code changes. A checkpoint written by an
older version of the script is reused if the configuration matches. The runbook requires an
empty `checkpoints/` before collection.

## Item 4. Single-criterion tie handling (fractional credit), one shared implementation

**Diff.**
- New `paper_pipeline/single_criterion.py`: `top1_credit(ref_ranks, crit_values)` (1/k when the
  reference winner is among the k alternatives tied for the best value, else 0) and
  `expected_tau` (tied pairs count 0, i.e. the mean tau over all tie-break orders). Values are
  compared after rounding to `MAVT_ROUND_DECIMALS`.
- `paper_pipeline/compute_dispersion_diagnostics.py`: L59-60 import; L187-212
  `single_criterion_recovery` uses `top1_credit`; L409-413 table note ("A tie for the best
  value ... earns 1/k ...") replaces "Ties are broken by first occurrence".
- `paper_pipeline/competitive_baselines.py`: L55-56 import; L160-168 Top-1 via `top1_credit`
  and tau via `expected_tau`; `_rank_desc_first_occurrence` removed; docstring L30-34. The
  `_tau` helper is now unused (left in place).
- **Bug fixed on the way** (`compute_dispersion_diagnostics.py` L248-258): the reference table
  took rows from the matched frame *before* failure filtering, so an A_H scenario-run whose
  extraction failed added a second copy of the scenario under placeholder labels
  ("Alternative 1 (extraction failed)"). 54 of 195 Test scenarios were doubled. First occurrence
  hid it; 1/k credit would not have (HVAC Comfort read 53.2% instead of 85.0%). The rows now
  come from the clean frame. This also moves the ground-truth dispersion statistics in
  `paper/dispersion_diagnostics.csv`: marginal n 2,988 -> 2,340 (= 585 x 4), marginal sd
  0.2653 -> 0.2702, central-band share 0.3685 -> 0.3667, HVAC within-scenario sds up about 9%
  (e.g. comfort 0.198 -> 0.216). The within-scenario **ranges** (what `tab:dispersion`
  prints) do not change.

**Numbers** (shipped calculators, 195 Test scenarios; both scripts now give the same Top-1):

| Type | Criterion | Top-1 old (first occurrence) | Top-1 new (1/k) | tau old -> new (competitive_baselines) |
|---|---|---|---|---|
| HVAC | Energy cost | 10.0 | 10.2 | -0.219 -> -0.214 |
| HVAC | Environmental | 10.0 | 10.2 | -0.219 -> -0.214 |
| HVAC | Comfort | 85.7 | 85.0 | 0.705 -> 0.710 |
| HVAC | Practicality | 27.1 | **35.7** | 0.162 -> 0.143 |
| Appliance | Energy cost | 61.5 | **30.8** | 0.405 -> 0.021 |
| Appliance | Environmental | 46.2 | **26.9** | 0.323 -> -0.103 |
| Appliance | Comfort | 92.3 | 92.3 | 0.826 -> 0.826 |
| Appliance | Practicality | 90.8 | 90.8 | 0.815 -> 0.821 |
| Shower | Energy cost | 75.0 | 73.9 | 0.733 -> 0.711 |
| Shower | Environmental | 75.0 | 74.7 | 0.733 -> 0.711 |
| Shower | Comfort | 18.3 | 17.5 | -0.189 -> -0.200 |
| Shower | Practicality | 20.0 | 19.2 | -0.378 -> -0.383 |

Full 285-scenario set, old -> new: HVAC 14.3/14.3/81.0/26.7 -> 13.5/13.5/80.0/35.4; Appliance
68.0/55.0/93.0/92.0 -> 32.3/28.5/93.0/92.0; Shower 72.5/72.5/21.2/22.5 -> 71.7/72.3/20.6/21.9
(energy, environmental, comfort, practicality). The main text's "no cell moves by more than
8.8 pp" must be recomputed (Appliance energy cost is now 1.5 pp apart, HVAC practicality 0.3).
All of these move again under the new calculators.

Both scripts' `main()` ran to completion with their outputs redirected to scratch; nothing in
`paper/` or `Analysis/` was overwritten.

## Item 5. Collection defaults match the paper's design

What the paper says: main L754 and S L1340-1343 (A_H order arm: 5 reversed runs + 3
same-session original-order runs per model, 13 runs with the 5 main runs); main L754 and S L1349
(position bias: A_D reversed on all 195 test scenarios, one reversed run compared with each of
the five original runs, per model); S L1238 and L1243 (prompt ablation run counts).

**Diff.**
- `run_hybrid_ablation_experiments.py`: L157-164 `ORDER_ARM_DEFAULT_RUNS = {"reversed": 5,
  "control": 3}` replaces `DEFAULT_ORDER_RUNS = 3`; L1406 `--order-arms` defaults to both
  arms; L1418-1423 `--order-runs` defaults to None and its help now says it is the last run
  index (inclusive), not a count; L1437-1441 each arm runs to its own total unless
  `--order-runs` is given; docstring L79-86 example and call count (6,240) updated.
  Dry run with `collect_order_arm` stubbed: no flags -> 32 units (reversed 1-5 and control 1-3
  for each of the 4 models); `--models qwen --order-arms reversed --order-run-start 4
  --order-runs 5` -> runs 4 and 5 only.
- `run_position_bias_control.py` L736-760: `--model` is now `--model/--models`, `nargs="+"`,
  default all four keys, looped in one process (each iteration loads a fresh A_D module and
  repoints `API_CONFIG`, as before); `--n` default 195 and `--runs` default 1 unchanged, help
  text updated. `--help` checked.

**Prompt ablation: not changed** (author's decision). Current default vs the paper:

| Cell | Script default (`--runs N_RUNS`) | Paper (S L1238, L1243) |
|---|---|---|
| A_D control, DeepSeek / GPT-OSS / Qwen | 5 | 10 |
| A_D no_anchors, DeepSeek / GPT-OSS / Qwen | 5 | 10 |
| A_D cot_scaffold, scale_0_10, DeepSeek / GPT-OSS / Qwen | 5 | 5 |
| A_E control, cot_scaffold, scale_0_10, DeepSeek / GPT-OSS / Qwen | 5 | 5 |
| every Gemini cell (7) | 5 | 3 |
| Total cell-runs / calls | 140 / 81,900 | 156 / 91,260 |

One `--runs` applies to every selected cell, so the paper design needs three invocations
(runbook step 6), and each invocation rewrites `prompt_ablation_summary.xlsx` with only its own
run range; the significance script reads every `cell_*.xlsx` and is unaffected.

## Item 6. Table 8 from charged cost

**Diff.** `paper_pipeline/generate_paper_results_numbers.py`:
- L14-26 `add(..., cost_source=None)` writes a `cost_source` column (NaN outside Table 8).
- L108-127 header comment; L148-186 per run: `total_cost_usd` when the diagnostics JSON has it,
  else that run's tokens at the label price. The cost row's `cost_source` is `charged`,
  `label_price` or `mixed:<k>/<n>_charged`; when a charged run's `calls_with_cost` is below
  `total_api_calls`, `;cost_covers_<a>/<b>_calls` is appended (the missing calls' cost is
  missing, not zero). The label is parsed only when a run needs the fallback.

**Test** (synthetic diagnostics copies in scratch): Qwen with `total_cost_usd` on all five runs
-> `charged`, value = mean of the five; DeepSeek with it on two runs and `calls_with_cost` = 500
-> `mixed:2/5_charged;cost_covers_1000/1164_calls`; GPT-OSS untouched -> `label_price`. On the
shipped data every row is `label_price` and the values are unchanged (pipeline gate, below).

## Item 7. Pooled rows removed

Re-checked the paper first: no `RobustnessComparison` value (0.0927 / 0.0944, 0.2743 / 0.2740,
0.8996 / 0.8709, 0.0540 / 0.0605, 91.3 / 89.3, at 3 and 4 dp) appears in `paper_draft_v2.tex` or
`supplementary.tex`; every hit is a plot coordinate or the unrelated Qwen 0.054 separation.

**Diff.**
- `generate_paper_results_numbers.py` L412-418: the `RobustnessComparison` block is replaced by
  a comment; the `imputed` workbook read (only that block used it) is removed.
- `paper_pipeline/generate_imputed_robustness_tables.py` L352-354: no `pooled` sheet; the
  "pooled tau" verdict lines are gone; L375-383 the largest-movement line is now per (model,
  architecture, metric), restricted to the table metrics. Ran with the workbook redirected to
  scratch: sheets `comparison`, `imputation_counts`, `per_run_detail`. (Its Gemini rows are NaN
  because `Output Files Gemini 3.8 Flash` is empty; that predates this change.)
- `Analysis/rerun_prep/pipeline/gate_checks.py` L98-106, L115-116: `NUMBERS:RobustnessComparison`
  added to the gate's intentionally-removed set, so G4 still checks every other numbers row.

## Item 8. Collection window from recorded timestamps

**Diff.** `paper_pipeline/emit_collection_window.py` rewritten (same outputs, new columns):
per artifact it reads the diagnostics JSON `collected_utc_start` / `_end` (else
`collected_utc`, start only), the per-run xlsx `collected_utc` column (min / max), and the raw
jsonl records' `collected_utc` (min / max); only an artifact with none of these falls back to
its mtime. Each row has `start_utc_iso`, `end_utc_iso` and `time_source`; the summary has
`time_sources` and `n_mtime_fallback`. Covers the main runs, `position_bias/` and
`hybrid_order_reversal/`. New `--out-dir` (default `paper/`). The git commit-date columns stay.

**Check.** On the shipped data: 141 artifacts, all `mtime` (none carries a timestamp, as
expected). On synthetic new-format files each reader returned the right window and source.

## Item 9. Numbers of record (D4)

**Diff.** `paper_pipeline/build_numbers_of_record.py` rewritten around the old per-run rules.
Inputs, each a CLI option defaulting to where the scripts write: per-run metrics, the hybrid
summary workbook (`per_scenario` sheet; per-run arm `extracted`, or `extracted_per_run` in the
old layout), the pairwise tests, `baseline_metrics.csv`, `baseline_fixeddefault.xlsx` (scored
per scenario for the like-for-like A_H - FD gaps) and `numbers_master.csv`. The arithmetic is
`pipeline_gate.py`'s (`arm_aggregate`, the DM/FD like-for-like blocks,
`per_scenario_rank_metrics`). New `--strict` (exit 1 on any mismatch; without it the script
reports and exits 0, because `run_paper_pipeline.py` calls it and most rows will move after the
rerun) and `--allow-deviation`. It refuses to write next to the record.

Row rules: AH_* per model and type, inclusive tau / Top-1 (failed scenario-runs at 0 and 1/3),
GPT-OSS "success-weighted" text (= the inclusive values, per the record's own note), ranges,
best / worst, table A_H - FD (model's A_H tau minus the FD row's all-195 tau, the table's basis),
the two "not in paper" A_H - FD gaps (like-for-like), failure count by type and "failed in all
runs", GPT-OSS recovery (numbers_master `recovered_5run`), dataset-median rows and the
`PROV_median_*` triples, `MEDIAN_tau_gptoss_same_scenarios`, `EFFECT_like_for_like_*` and the
range, `FD_tau_*`, `SIG_cliff_*`.

**Retired (25 rows), with the reason in `regen_note`:** the 24 `PROV_extracted_*` rows (Set B,
the five-run consensus arm, removed from the harness; the provenance table's extracted row is
now the per-run A_H value, i.e. the AH_* rows) and `PROV_gptoss_194of195` (Set B count).
`AH_gptoss_recovery_tau` is **not** retired: its source, `GPTOSS_recovery/recovered_5run` in
`numbers_master.csv`, is written by the current `generate_paper_results_numbers.py`. The shipped
`paper/numbers_master.csv` predates that block, so on it the row is "not regenerated".

Two rows carry a value the record itself flags as wrong ("mismatch"); they are checked against
the reproduction in the record's `basis_notes`: `AH_gptoss_recovery_tau` (expected 0.904, the
recomputed backfill 0.9045; the paper's 0.897 is the unrecovered value) and `EFFECT_range_text`
(expected 0.24-0.30, from 0.239-0.300; the paper's 0.24-0.28 mixes two bases).

**Gate on the current data** (`--strict`, output in scratch `sf/nor/`): 96 regenerated, 25
retired, 1 not regenerated (recovery row, shipped numbers_master lacks it); **96 / 96 match the
record, exit 0**. With `--numbers-master` pointed at the gate's freshly generated
`numbers_master.csv`: **97 / 97 match** (recovery 0.904). The known Gemini A_H tie cells did not
need an exception, because the regeneration reads the stored per-run metrics (0.923).

For information, the same script on freshly regenerated current-code outputs (the gate's
`work_after/`) matches 66 / 97; the 31 differences are exactly the approved changes V_PIPELINE
lists: the retrieval-set dataset median (MEDIAN_top1 76.9 -> 75.9, Shower 0.800 -> 0.789,
`PROV_median` 0.769 / 0.122 -> 0.759 / 0.133, the EFFECT per-type gains), the FD change (the two
"not in paper" gaps 0.284 -> 0.270 and 0.329 -> 0.313) and the per-run significance basis
(`SIG_cliff_*`, e.g. DeepSeek tau -0.223 -> -0.207).

## Item 10. Runbook

`paper/pass6/RERUN_RUNBOOK.md`: blockers and decisions table; the folders that must be empty
(all four `Output Files*` model folders with their `position_bias/` and `hybrid_order_reversal/`,
`Analysis/Prompt_Ablation/`, `Analysis/RAG_Ablation/` including `checkpoints/`,
`Analysis/Hybrid_Ablation/`, the orphan baselines) with a check command; a re-derived call
budget (134,700 calls for the paper design, 108 for the smoke test); then, in order: smoke test
(three request paths, 36 calls each, and the position-bias smoke output that must be deleted),
RAG ablation (confirms k), main benchmark per model (`MODEL_KEY=<key>`), collection-window
check, A_H order arms and position bias (no flags needed now) with their offline analyses,
prompt ablation (both run-count options), optional arms, and the offline pipeline, each with
where it writes and what to check.

Placeholders: `[AUTHOR: ...]` for the prompt-ablation run counts, the nn fallback, the k rule,
optional arms, `require_parameters` in the pinned provider entries, confirming Gemini `low`
effort and `MAX_OUTPUT_TOKENS` after the smoke test, and the go-ahead for the arch patch and the
ablation-script request switch.

---

## Verification

- `py_compile` passes on every changed script.
- Ran offline on current data: the RAG ablation's copy-only arm (all three fallbacks), the
  test-set NN baseline, the checkpoint test, both single-criterion scripts' `main()`,
  `generate_paper_results_numbers.py` (in the gate and with synthetic cost data),
  `generate_imputed_robustness_tables.py`, `emit_collection_window.py`,
  `build_numbers_of_record.py`, the hybrid script's `run()` (in the gate) and its order-arm
  defaults with collection stubbed, the position-bias CLI. The position-bias `run` / `analyze`
  and every API path were not run.
- **Pipeline gate** (`pipeline_gate.py after`, `diff`, `gate_checks.py`, run from a scratch copy
  that differs only in `PROJECT_ROOT`, so nothing in `Analysis/rerun_prep/pipeline/` was
  overwritten): **G1 66/68, G2 33/36, G3 48/48, G4 5/5**, the same result as before; the only
  failures are the five known Gemini A_H tie cells (0.923 -> 0.920, HVAC 0.977 -> 0.968). The
  new `after.csv` equals the committed one value for value except the 18 removed
  `RobustnessComparison` rows.
- Nothing under `paper/`, `Analysis/` result files or `Output Files*` was written. My test runs
  created `.rag_ablation_temp/` (the RAG ablation's temporary Chroma collections, gitignored,
  absent before); I removed it.

## Open items for the author

1. `--nn-fallback`: `tie`, `nearest` or `unscored` (item 1 numbers).
2. Prompt-ablation run counts (item 5 table).
3. `require_parameters: true` in the pinned `provider` entries (not sent now).
4. RAG-ablation Top-1 counts an unscored or failed scenario as wrong while tau drops it
   (pre-existing, affects the LLM arms too); decide whether both should drop it.
5. Paper text that these fixes move (not edited): the single-criterion table note and cells
   (main L811-829, "8.8 pp"), the copy-only tau and its n (main L811, S L966-974), and the
   ground-truth dispersion sds if printed.
6. Still pending from other reports, not done here: the ablation scripts' switch to the arch
   patch's payload and POST (after the patch lands), the RAG ablation's stale
   "--ablations nearest-neighbor" message (the choice is `nearest_neighbor_k3`), and NN output
   rows carrying no disambiguating columns (V_BASELINE issue 10).

Git: read-only only (`git status --short`, `git diff --stat`, `git check-ignore`). No commit,
checkout, stash, reset or other state-changing command.
