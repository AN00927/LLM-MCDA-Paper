# Provenance Audit Prompt — TestScenarios + RAG ⟵ 3 Masters

Use this prompt to verify that **every** row in `TestScenarios.xlsx` and in the three
RAG sheets (`HVACRagScenarios.xlsx`, `ApplianceRAGScenarios.xlsx`,
`ShowerRAGScenarios.xlsx`) traces back to a row in one of the three master pools,
under the documented transformation rules. It is written so an LLM (or a person)
can run it against the workbooks and report violations. It does **not** assume the
derived sheets are byte-identical to the masters — several columns are
*intentionally* transformed, and those transformations are part of the audit.

---

## Inputs

- **Masters (source of truth):** `HVACScenarios`, `ApplianceScenarios`,
  `ShowerScenarios` (live in `ConsolidatedforSimaltaneousediting.xlsx`; standalone
  copies exist for HVAC/Shower/Appliance scenario files and for the
  `Ground Truth/ground_truth_*.xlsx` files).
- **Derived sheets under audit:** `TestScenarios` + the three `*RAGScenarios`.

## Partition invariants (structural)

1. **RAG ⊆ masters, Test = masters∖RAG, and RAG ∩ Test = ∅.** Every RAG scenario
   must match exactly one master row on its shared parameters + 3-alternative set.
   Every Test scenario must match exactly one master row **not** claimed by RAG.
   No master row may be claimed by both, and none may be orphaned.
2. **Counts must reconcile:** `|RAG_type| + |Test_type| == |master_type|` for each of
   HVAC / Appliance / Shower (a scenario = 3 alternative rows).
3. **RAG `scenario_id` is a per-type sequential 1..N**, NOT the master row index.
   Do not match RAG↔master/GT by `scenario_id`; match by descriptor parameters.

## Field transformation rules (a "match" must respect these, not demand equality)

For each derived row, identify its master row and check each field under the right rule:

| Field | Test sheet | RAG sheet | Rule vs master |
| --- | --- | --- | --- |
| `house_age` | **band label** | HVAC-RAG: **raw years** | Test = `house_age_to_band_label(master House Age)` (5-yr bands ≤20: `1-5/6-10/11-15/16-20 years`, then 10-yr `21-30…`). HVAC-RAG keeps raw numeric. Both derive from the master **building** age, not equipment age. |
| `appliance_age` | **band label** | Appliance-RAG: **raw years** | Test = `appliance_age_to_band_label(master appliance_age)` (3-yr bands ≤12: `1-3/4-6/7-9/10-12 years`, then 5-yr `13-17…`). Appliance-RAG keeps raw numeric. |
| `flow_rate` | **label** | Shower-RAG: **label** (alongside raw `gpm`) | `gpm_to_flow_rate_label(master gpm)`: `low_flow` ≤2.0, `standard` ≤3.0, `high_flow` >3.0. Shower-RAG keeps BOTH the label and raw `gpm`. |
| `hvac_age`, `gpm` | **absent in Test** | present (raw) in RAG/GT | Test is the architecture-facing sheet and omits these; do not flag their absence in Test. |
| appliance `alternative` | time strings | time strings | Times may be canonicalized `6pm → 6:00 PM`; treat `6pm` and `6:00 PM` as equal (parse to 24h before comparing). |
| HVAC `alternative` | setpoints incl. `Off` | setpoints | `Off` is a legitimate non-numeric setpoint (text), not an error. |
| `question` | from master | RAG may keep a **grammar-corrected** variant | Wording may be normalized (e.g. fix `"It's just got home" → "I've just got home"`, em-dash → comma) but the scenario must otherwise be the same row. Flag only *semantic* divergence, not punctuation/grammar cleanups. |
| score columns (`energy_cost_score`, `environmental_score`, `comfort_score`, `practicality_score`, `mavt_score`, `raw_*`) | n/a | carried **verbatim** from the ground-truth files | Must equal the GT row for the matched (scenario, alternative). |
| `rank` | n/a | **recomputed** from `mavt_score` | rank 1 = highest mavt; do NOT expect it to match any stored source rank. |
| free-text `location` | verbatim | verbatim | byte-match (after whitespace/encoding normalization). |
| all other shared params (`square_footage`, `insulation`, `household_size`, `utility_budget`, `housing_type`, `outdoor_temp`, `r_value`, `seer`, `tank_size`, `water_heater_temp`, `kwh_per_cycle`, `appliance`) | verbatim | verbatim | byte-match after numeric normalization (`75` ≡ `75.0`). |

## Matching procedure (per derived row)

1. Normalize for comparison: trim whitespace; fold unicode look-alikes
   (curly→straight quotes, em/en-dash→hyphen); numbers compare value-wise
   (`75.0` ≡ `75`); appliance times parse to 24h `HH:MM`.
2. Build the row's **descriptor signature** from the *verbatim* shared params +
   the alternative (apply the transform rules above to ages/flow before comparing,
   i.e. band the master value and compare to the Test label; compare RAG raw to
   master raw). Exclude `scenario_id`, `rank`, scores, and `raw_*` from the key.
3. Find the unique master row with that signature.
   - 0 matches → **VIOLATION (orphan):** report the row, its sheet, and which
     field(s) had no master counterpart.
   - >1 match → **VIOLATION (ambiguous):** report the colliding master rows.
4. For the matched pair, verify the score columns equal the GT row and that `rank`
   is consistent with `mavt_score` ordering.

## Report format

Emit, per decision type:

- Counts: `|RAG|`, `|Test|`, `|master|`, and whether `RAG + Test == master`.
- Orphans: any RAG/Test row with no master match (+ offending fields).
- Double-claims: any master row claimed by both a RAG and a Test scenario.
- Score mismatches: RAG rows whose scores ≠ the matched GT row.
- Rank inconsistencies: RAG rows where `rank` ≠ mavt ordering.
- A final `PASS` only if all of: counts reconcile, zero orphans, zero
  double-claims, zero score mismatches, zero rank inconsistencies.

> Note: `build_consolidated_scenario_workbooks.py` already encodes most of these as automated
> checks (A01–A14). This prompt is the human-/LLM-readable contract those checks
> enforce, and the reference for auditing the sheets outside that script.
