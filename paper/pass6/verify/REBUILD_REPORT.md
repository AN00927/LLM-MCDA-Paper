# Scenario rebuild: new script, reproduction gate, Phase I dry run

Date: 2026-09-26/27. Scope: replace the unrunnable `build_consolidated_scenario_workbooks.py`,
prove the replacement reproduces today's derived files, and dry-run the staged scenario fixes
end to end in scratch. Nothing in `Scenario Files/` was modified except two new files
(`build_scenario_workbooks.py`, `rag_membership.json`). No API calls.

## Result summary

| Check | Result |
|---|---|
| Reproduction gate: new script on unmodified masters vs current `TestScenarios.xlsx` + 3 RAG sheets (value, Python type, number_format, data_type of every cell; sheet names; used range) | **PASS: IDENTICAL, 0 differing cells** |
| Built-in audit A01-A09 (on the unmodified and on the fixed masters) | PASS |
| Staged fixes applied to scratch copies | 148 applied, 0 mismatched, 0 skipped |
| Dry-run diff (fixed-master rebuild vs current derived files) | 65 differing cells (20 Test, 45 ApplianceRAG), **all 65 traced to a staged fix**, 0 unexplained |
| HVAC heat/AC mode (`hvac_mode_from_question`, calc_new) on all 105 master questions | unchanged (54 cool / 51 heat before and after; none unmatched) |
| Embedding strings (`format_embedding_text`) | 15 of 90 RAG and 18 of 195 Test strings change, all Appliance. RAG index rebuild required, no schema bump |
| Extra: calc_new calculators on fixed vs unfixed masters | 0 score changes in all three GT files; only question text changes (HVAC 6 rows, Appliance 99 rows) |
| Extra: `sync_rag_ground_truth_scores.sync_domain(dry_run=True)` of the dry-run RAG sheets against the fixed-master GT | all three types match (35/35/20 scenarios) |

## 1. Design of `Scenario Files/build_scenario_workbooks.py`

**Inputs.** The three standalone masters (`HVACScenarios.xlsx`, `ApplianceScenarios.xlsx`,
`ShowerScenarios.xlsx`, snake_case headers), `Scenario Files/rag_membership.json`, and the
existing RAG sheets (read only to carry their score columns). Masters are never written; the old
script's "clean and write back" step is now in-memory only, and it reports how many master cells
normalisation touched (today: the 8 appliance `6pm`-style times).

**Partition (RAG membership).** Persisted in `rag_membership.json`, created once with
`--init-membership` from the current RAG sheets (35/35/20 entries). Each entry holds the RAG
`scenario_id`, a master-row signature, and, for humans only, `master_row` (0-based data index)
and the question. The signature is the old script's match key: the shared scenario parameters
plus the sorted alternative set (HVAC: location, square_footage, insulation, household_size,
utility_budget, housing_type, outdoor_temp, house_age; Appliance: location, utility_budget,
appliance, housing_type, household_size, kwh_per_cycle, appliance_age; Shower: location,
household_size, gpm, utility_budget, housing_type, outdoor_temp). The question text and the
engineering-only values (hvac_age, r_value, seer, tank_size, water_heater_temp) are left out, so
question edits, cell-type fixes and the Stroudsburg hvac_age fix cannot move a scenario between
RAG and Test. If an edit touches a signature field of a RAG row, the script aborts and says the
membership file must be updated deliberately. If a master row moves, it is still found by
signature and an INFO line reports the move.

**Derivation (unchanged rules from the old script).**
- Normalisation: `clean_text` (nbsp, em/en-dash folding, whitespace), `to_clock` (`6pm` becomes
  `6:00 PM`), `alt_norm` (HVAC/Shower alternatives become integer strings, `Off` stays text),
  appliance canonicalisation (`washer` becomes `washing_machine`).
- Test: every master row not in RAG, in HVAC, then Appliance, then Shower order, master order
  within type; banded `house_age` / `appliance_age` / `flow_rate` via the `sentinel_utils`
  helpers; no hvac_age/gpm columns; question from the master.
- RAG: 3 rows per scenario in master alternative order; `scenario_id` from the membership file
  (today 1..N in master-row order, same as before); raw engineering values; Shower `flow_rate`
  label plus raw `gpm`, `duration_min`; **question from the master**. The old script kept the
  question from the old RAG sheet, so a question fix would never have reached RAG and the sync
  (which matches RAG to GT on question) would then fail.
- Score columns (`*_score`, `mavt_score`, `rank`, `raw_*`) are carried verbatim from the existing
  RAG row with the same id and alternative, after checking that row's signature against the
  membership entry. `rank` is carried, not recomputed. The old script recomputed it from
  mavt; the results are identical today (no mavt ties in any RAG scenario), and a carried rank
  keeps GT's tie-break. The audit checks rank consistency. The sync refreshes all of these
  afterwards, as before.

**Formats.** `TestScenarios.xlsx` uses the old export's explicit formats (`@` / `0` /
`0.######`, blank cells formatted too). The RAG sheets are written with
`sync_rag_ground_truth_scores.write_xlsx` (imported from that script): General formats, pandas
typing. That matches their on-disk state today, because the sync rewrites them with pandas after
every rebuild. A pandas round-trip of the current RAG sheets is a fixed point (checked: 0 cell
differences), so rebuild followed by sync changes nothing but score values.

**Audit (runs on the files as written, read back from disk; any FAIL gives exit code 1).**
A01 canonical headers; A02 counts 70/35, 65/35, 60/20, and test + RAG = master per type; A03 every
Test row matches exactly one master row under the transform rules, namely the row it was built
from; A04 every RAG scenario matches exactly one master row (question, params, raw engineering
values, flow label, alternatives in master order); A05 disjoint and complete, with RAG rows equal
to the membership rows; A06 ids 1..N, 3 consecutive rows each; A07 scores/raw numeric, no `1928`
sentinel, ranks {1,2,3} consistent with mavt; A08 Test cell formats and types; A09 no corrupt
characters, valid enums, appliance times `H:MM AM/PM`, HVAC alternatives integer or `Off`.

**Output and safety.** Default output is a new scratch dir (`%TEMP%/scenario_rebuild_<UTC>`),
or `--out-dir DIR`, with a `rebuild_audit.txt` that records the UTC run time. `--in-place` stages in
a temp dir, audits, and only on PASS copies each file over the live one after backing it up to
`Scenario Files/Backups/<stem>_BACKUP_<UTC>.xlsx`. `--masters-dir` and `--rag-scores-dir` allow
scratch runs. All printing is ASCII.

**Negative controls run.** The comparator flagged a changed number_format and an added trailing
space. A membership file with a corrupted signature aborted the run ("matches 0 master rows ...
REBUILD ABORTED, nothing written", exit 1). A second rebuild produced output identical to the
first (deterministic). An integral float vs int in a numeric cell is not representable in xlsx:
openpyxl stores both as the same XML number, so no comparison of the files can see that
difference.

## 2. Reproduction gate

```
PY=.venv/Scripts/python.exe; export OPENBLAS_NUM_THREADS=1
$PY "Scenario Files/build_scenario_workbooks.py" --out-dir <scratch>/gate_out     # AUDIT PASSED
$PY paper/pass6/verify/compare_scenario_workbooks.py "Scenario Files" <scratch>/gate_out
```
Result: `TestScenarios.xlsx 0, HVACRagScenarios.xlsx 0, ApplianceRAGScenarios.xlsx 0,
ShowerRAGScenarios.xlsx 0 -> IDENTICAL`. No hand edits were found in the current derived files,
and no differences had to be accepted.

## 3. Staged-fix changes

- `scenario_fixes.json` #73: now the author's decision, a **question** edit on Appliance data row
  64 (Lebanon, dishwasher, RAG id 14), `It's just after 8 AM. When should I run the dishwasher?`
  becomes `It's just after 9 AM. When should I run the dishwasher?`, kind `other-approved`, so it
  is applied by default. `baseline_time` and the alternatives stay at 9:00 AM. It chains after #28
  (the comma-splice fix on the same cell), so its `old` is the text #28 leaves.
- `scenario_fixes.json` #84 (new): `HVACScenarios.xlsx` data row 30, `hvac_age` 95 becomes 40,
  kind `other-approved`. The row was confirmed as `Stroudsburg, PA` (heat, 2050 sqft, SEER 8).
  This matches `Analysis/rerun_prep/hvac/out/HVACScenarios_stroudsburg_hvac_age40.xlsx`.
- `apply_scenario_fixes.py`: new `--masters-dir DIR`, which looks files up by basename in DIR,
  puts backups in `DIR/Backups/`, and leaves `Scenario Files/` untouched. Fixes are now checked
  in file order against the value an earlier fix on the same cell leaves, so chained edits work
  and a stale chain reports MISMATCH. The docstring states that `other-approved` is applied by
  default.
- `SCENARIO_FIXES.md`: #37/#38 marked SUPERSEDED by #39; #73 rewritten as author-decided
  (question edit); #84 added; the intro now names the new script.

## 4. Dry run of the Phase I chain (scratch only)

Commands (scratch = session scratchpad):
```
cp "Scenario Files"/{HVAC,Appliance,Shower}Scenarios.xlsx <scratch>/masters_fixed/
$PY paper/pass6/verify/apply_scenario_fixes.py --apply --masters-dir <scratch>/masters_fixed   # 148 applied, 0 mismatched
$PY "Scenario Files/build_scenario_workbooks.py" --masters-dir <scratch>/masters_fixed \
    --rag-scores-dir "Scenario Files" --out-dir <scratch>/dry_out                          # AUDIT PASSED
$PY paper/pass6/verify/compare_scenario_workbooks.py "Scenario Files" <scratch>/dry_out      # 65 cells
```

Master cells changed by the apply step: HVAC `alternative_3` 101, `question` 2, `hvac_age` 1;
Appliance `question` 33, `baseline_time` 2, `alternative_1/2/3` 2 each; Shower none. (#82/#83,
`kwh_per_cycle` 3 to 3.0, are applied but do not persist; see section 7.)

Every derived-cell difference, traced by an automated attribution (derived row, then its master
row, then the chain of staged fixes on that cell; checked that the old value equals the first
fix's `old` and the new value equals the last fix's `new`):

| Staged fix(es) | Master cells | Where the rows live | Derived cells changed | Explanation |
|---|---|---|---|---|
| #1-15, 19, 20, 24 (Appliance question grammar) | 18 | Test | 18 (`TestScenarios` col B) | question text, as staged |
| #16-18, 21-23, 25-27, 29-32, 65 (Appliance question grammar) | 14 | RAG | 42 (`ApplianceRAGScenarios` col B, 3 rows each) | question text, as staged |
| #28 then #73 (Appliance row 64 question: comma splice, then 8 AM to 9 AM) | 1 | RAG (id 14) | 3 (ApplianceRAG B41:B43) | final text `It's just after 9 AM. When should I run the dishwasher?` |
| #35, #36 (HVAC "single-family" to "single-family home") | 2 | Test | 2 (Test B35, B60) | question text |
| #39 (HVAC `alternative_3` text to int, 101 cells) | 101 | 33 RAG / 68 Test | 0 | `alt_norm` renders `'80'` and `80` identically |
| #33, 34, 75-77, 79-81 (Appliance `6pm`-style times) | 8 | RAG (rows 98, 99) | 0 | `to_clock` already canonicalised them |
| #82, #83 (`kwh_per_cycle` 3 to 3.0) | 2 | Test | 0 | not in Test; no-op on disk anyway |
| #84 (Stroudsburg `hvac_age` 95 to 40) | 1 | Test | 0 | Stroudsburg is a Test scenario and Test has no hvac_age column (it is not in RAG) |
| **Total** | | | **65** (20 Test + 45 ApplianceRAG; HVAC RAG and Shower RAG 0) | **65/65 explained, 0 unexplained** |

No score, rank, raw, id, number_format or type cell changed. The RAG/Test membership is unchanged
(35/35/20 and 70/65/60).

## 5. Embedding changes (`sentinel_utils.format_embedding_text`)

Computed the way the pipeline does it: RAG side = first row of each scenario group of
`read_table_clean(<RAG sheet>)` (as in `build_rag_index.py`); query side = each row of
`read_table_clean(TestScenarios.xlsx, keep_str_cols=alternatives)` (as in
`Example-Guided_LLM_Scoring.py`). Current files compared with the dry-run output:

- **RAG: 15 of 90 change**, all Appliance: ids 1, 2, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 20, 22,
  32 (master rows 39, 40, 45, 49, 52, 53, 55, 58, 61, 63, 64, 67, 72, 75, 96). Only the question
  prefix changes, e.g. id 14: `It's just after 8 AM, when should I run the dishwasher?, appliance
  age 4-6 years, ...` becomes `It's just after 9 AM. When should I run the dishwasher?, appliance
  age 4-6 years, ...`.
- **Test: 18 of 195 change**, all Appliance: sheet rows 76, 79, 80, 81, 83, 87, 88, 89, 90, 94,
  96, 100, 101, 103, 105, 114, 115, 118 (master rows 4, 7, 8, 9, 11, 15, 16, 17, 18, 22, 24,
  28, 29, 31, 33, 47, 48, 54).
- HVAC and Shower: 0 changes (their embedding text has no question; the two HVAC question edits
  are not embedded).

Consequence: `build_rag_index.py` must be re-run, which the workflow requires anyway. Its
source-table hash changes with the sheets and forces this. **No `RAG_SCHEMA_VERSION` bump**:
the embedding *code* is unchanged, and only a code change needs a bump. A_E retrieval neighbours
for the 18 changed Test queries may shift slightly because the query text changes; this is part
of the planned full rerun.

## 6. HVAC mode check

`HVACGroundTruthCalculator.hvac_mode_from_question` (from
`Analysis/rerun_prep/calc_new/HVACGroundTruthCalculator.py`) on all 105 HVAC master questions,
before and after the fixes: **0 changes**, 0 unmatched (None); 54 cool / 51 heat both times. The
two edited questions: row 43 "... what AC temperature should I set for the single-family home?"
gives cool; row 85 "... what heat temperature should I set for the single-family home?" gives
heat. All 175 HVAC question cells in the dry-run Test/RAG output resolve to a mode (88 cool /
87 heat). As an extra check, the calc_new calculators were run in scratch on the unfixed and on the
fixed masters: 0 score changes in all three GT files. That confirms #84 is score-neutral (the
degradation cap is 40 years) and #73 is score-neutral (baseline_time unchanged). Then
`sync_domain(dry_run=True)` matched the dry-run RAG sheets to the fixed-master GT for all three
types.

## 7. Items for the author

1. **Commit** `Scenario Files/build_scenario_workbooks.py` and `Scenario Files/rag_membership.json`
   (and the `paper/pass6/verify` changes) yourself; no git state was changed by this work.
2. `PASS6_HANDOFF.md` Phase I step 3 and section 3C step 1 still name
   `build_consolidated_scenario_workbooks.py`. It cannot run (its workbook is gone). Point them
   at the commands below. I did not edit the handoff.
3. #82/#83 (`kwh_per_cycle` 3 to 3.0) are no-ops on disk: xlsx stores 3.0 as the integer 3, so
   after `--apply` the cell still reads back as int. They are harmless; drop them or leave them.
4. The old `build_consolidated_scenario_workbooks.py` is untouched. Retire it once the new script
   has been used for Phase I.
5. Minor: `SCENARIO_FIXES.md` lists kind `other` for #74-81 while the JSON has `type`; the JSON is
   what the apply script reads. The JSON also de-duplicates the md's V_APPLIANCE repeats of
   #1-32 (#40-64, 66-72).

## 8. Exact commands for the live Phase I run (in order)

Run after PASS6_HANDOFF Phase I steps 1-2 (gate on old data, snapshot). Bash, from the repo root:
```
PY=.venv/Scripts/python.exe; export OPENBLAS_NUM_THREADS=1

# a. preview the fixes (read-only): expect 148 WOULD_APPLY, 0 mismatched, 0 skipped
$PY paper/pass6/verify/apply_scenario_fixes.py --dry-run

# b. apply the fixes to the three masters (backups to Scenario Files/Backups/)
$PY paper/pass6/verify/apply_scenario_fixes.py --apply

# c. rebuild into a preview dir and diff: expect AUDIT PASSED and exactly 65 differing cells
#    (20 TestScenarios + 45 ApplianceRAGScenarios, all column B question text)
$PY "Scenario Files/build_scenario_workbooks.py" --out-dir "$TEMP/rebuild_preview"
$PY paper/pass6/verify/compare_scenario_workbooks.py "Scenario Files" "$TEMP/rebuild_preview"

# d. live rebuild (audits first; backs up the 4 derived files to Scenario Files/Backups/)
$PY "Scenario Files/build_scenario_workbooks.py" --in-place

# e. install calculators + tests (PASS6_HANDOFF 3B), run the tests, then regenerate GT
$PY "Ground Truth Calculators/HVACGroundTruthCalculator.py"
$PY "Ground Truth Calculators/ApplianceGroundTruthCalculator.py"
$PY "Ground Truth Calculators/ShowerGroundTruthCalculator.py"

# f. refresh RAG score columns from the new GT (dry run first; it fails loudly on any
#    descriptor mismatch, e.g. if step e was skipped the questions will not match)
$PY "Miscellaneous Scripts/core-automation/sync_rag_ground_truth_scores.py" --dry-run
$PY "Miscellaneous Scripts/core-automation/sync_rag_ground_truth_scores.py"

# g. always last: rebuild the Chroma index (no RAG_SCHEMA_VERSION bump needed)
$PY "Miscellaneous Scripts/core-automation/build_rag_index.py"
```
Steps b to d only read masters and derived files, so the order of d relative to e does not
matter. f must come after both d and e.

## Files

- New: `Scenario Files/build_scenario_workbooks.py`, `Scenario Files/rag_membership.json`,
  `paper/pass6/verify/compare_scenario_workbooks.py`, this report.
- Edited: `paper/pass6/verify/apply_scenario_fixes.py`, `paper/pass6/verify/scenario_fixes.json`,
  `paper/pass6/verify/SCENARIO_FIXES.md`.
- Scratch only (session scratchpad): fixed master copies, gate and dry-run outputs, the
  attribution/embedding/mode analysis script `analyze_dry_run.py`, and GT previews.
