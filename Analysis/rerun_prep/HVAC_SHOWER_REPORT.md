# P1-HVAC: HVAC reference calculator fixes and Shower comment fixes

Written 2026-09-25, revised 2026-09-26 (revision 2) for `paper/pass5/RERUN_PREP_PLAN.md`, section
P1-HVAC. Revision 2 implements the author's decisions on the revision 1 flags:
- the operating mode comes from the question, and the load is capped by that mode;
- the occupant gain is 220 Btu/h;
- the budget penalty is continuous in all three calculators.

Nothing shipped was edited. The new calculators are in `Analysis/rerun_prep/calc_new/`. I wrote
nothing to `Ground Truth/`, `Scenario Files/` or `chroma_rag_db/`, made no paid API calls and ran no
git commands.

## Files

| Path | What it is |
|---|---|
| `Analysis/rerun_prep/calc_new/HVACGroundTruthCalculator.py` | New HVAC calculator (changes a-g below) |
| `Analysis/rerun_prep/calc_new/ShowerGroundTruthCalculator.py` | Shower: comments plus the continuous budget penalty |
| `Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py` | P1-APP's calculator plus the continuous budget penalty (nothing else touched) |
| `Analysis/rerun_prep/hvac/shipped/` | Frozen byte-identical copies of the shipped HVAC and Shower calculators |
| `Analysis/rerun_prep/hvac/common.py` | Harness helpers: runs a calculator's own `process_*_scenarios()` into a temp file; RAG matching by the sync script's descriptor signature; ranking, exemplar and bounds helpers |
| `Analysis/rerun_prep/hvac/reproduce.py` | Regression gate. Exit 0 only if every check passes |
| `Analysis/rerun_prep/hvac/variants.py` | Per-change variant classes (the new class with the other changes reverted). `HVAC_CALC_PATH` overrides the new-calculator path |
| `Analysis/rerun_prep/hvac/impact.py` | Modes, bounds, per-change and combined impact, branch counts, budget, Stroudsburg |
| `Analysis/rerun_prep/hvac/out/impact_results.json` | Full impact output, with the scenario ids behind every count |
| `Analysis/rerun_prep/hvac/out/scenario_modes.csv` | Mode assigned to each of the 105 master scenarios, with the question |
| `Analysis/rerun_prep/hvac/out/HVACScenarios_stroudsburg_hvac_age40.xlsx` | Scratch master copy with the Stroudsburg data fix |
| `Analysis/rerun_prep/hvac/out/ground_truth_hvac_NEW_preview.xlsx` | What the new calculator produces over the current master (preview; P4 regenerates the real file) |
| `Analysis/rerun_prep/tests/test_hvac_reference.py` | 18 tests; `HVAC_CALC_PATH` selects the file under test |
| `Analysis/rerun_prep/tests/test_shower_reference.py` | 2 tests; `SHOWER_CALC_PATH` selects the file under test |
| `Analysis/rerun_prep/PROVENANCE_HVAC.md`, `PROVENANCE_SHOWER.md` (and the budget row of `PROVENANCE_APPLIANCE.md`) | One row per constant, function and value function: value, file:line, source, quote, status, previous source |

Run order:
1. `python Analysis/rerun_prep/hvac/reproduce.py`
2. `python Analysis/rerun_prep/hvac/impact.py`
3. `python -m pytest Analysis/rerun_prep/tests/`, with `APPLIANCE_CALC_PATH` set for the Appliance file.

## 1. Regression gate (all pass)

- The frozen copies are byte-identical (SHA-256) to `Ground Truth Calculators/*.py`.
- HVAC: the unmodified calculator, run over `Scenario Files/HVACScenarios.xlsx` (105 scenarios),
  reproduces `Ground Truth/ground_truth_hvac.xlsx`: 315 rows x 20 columns, 0 mismatches. That covers
  scores, rank and raw columns for all 70 test and 35 RAG scenarios.
- HVAC RAG: all 105 rows of `HVACRagScenarios.xlsx` match a GT row by descriptor signature, and every
  score column equals the GT value.
- Shower: the unmodified copy and the `calc_new` copy both reproduce `ground_truth_shower.xlsx`
  (240 rows) and all 60 `ShowerRAGScenarios.xlsx` score rows. The `calc_new` copy has the continuous
  budget penalty, but no Shower alternative reaches u = 1.0 (maximum 0.905), so nothing moves. The
  bounds recompute unchanged: cost p5 0.1449 and p95 1.1354 (class $0.14 / $1.14); water p5 6.00 and
  p95 45.00 gal (class 6.0 / 45.0).
- The harness itself is checked two ways. The new HVAC class with every change reverted and the old
  bounds reproduces the shipped xlsx exactly. The new class as written equals the
  all-changes/new-bounds variant exactly.
- **Concurrent change outside my files.** `sentinel_utils.apply_mavt_ranking` now rounds the weighted
  sum to 10 dp before ranking (`MAVT_ROUND_DECIMALS`), a P3 tie-break change. A fresh `mavt_score`
  can therefore differ from the stored one by about 1e-16. The gate compares `mavt_score` to 1e-9 and
  every other column, rank included, exactly; no rank changes. In three RAG cells the rounding moves
  the 2-dp MAVT that exemplars display, with nothing else changed. That is the "(0)" row in the
  impact table, and those 3 cells are part of every exemplar count below.

## 2. HVAC changes

### (a) Heating efficiency: HSPF paired with SEER (unchanged from revision 1)

Old: heating kWh = heating load / EER, with EER taken from the SEER quadratic (the cooling efficiency).
New: heating kWh = load / (HSPF x 1000) per hour of run time, with HSPF interpolated from the
scenario's SEER. Cooling keeps the EER path. Degradation stays in Practicality only.

Conversion: HSPF is seasonal Btu of heat per Wh of electricity, the same unit as EER. So
kWh = Btu / (HSPF x 1000) is the heating twin of kWh = Btu / (EER x 1000), and seasonal COP = HSPF / 3.412.

Anchors (`HSPF_BY_SEER`) are joined piecewise-linearly, and extended linearly along the end segments
outside 6.5-22 (only A_H extractions can reach that; its admissible SEER range is 6-30).

| SEER | HSPF | Source |
|---|---|---|
| 6.5 | 6.0 | HSP Table 32, split heat pump, reciprocating, before 1981 |
| 8 | 6.6 | HSP Table 32, split heat pump, reciprocating, 1981-1991 |
| 10 | 7.1 | HSP Table 32, split heat pump, reciprocating, after 1991 |
| 13 | 7.7 | HSP Table 4, Benchmark air source heat pump |
| 14 | 8.0 | HSP Table 32, split heat pump, scroll, BPM, TXV |
| 18 | 9.3 | NREL ResStock option "ASHP, SEER 18, 9.3 HSPF" |
| 22 | 10.0 | NREL ResStock option "ASHP, SEER 22, 10 HSPF" |

Sources:
- Hendron & Engebrecht (2010), *Building America House Simulation Protocols*, NREL TP-550-49426,
  https://www1.eere.energy.gov/buildings/publications/pdfs/building_america/house_simulation_revised.pdf
  - Table 32 (p. 40): "Split heat pump, single-speed scroll compressor, BPM air handler motor,
    thermostatic expansion valve 14 10.5 8.0"; "... reciprocating compressor, PSC air handler motor (after
    1991) 10 9.3 7.1"; "(1981-1991) 8 7.7 6.6"; "(before 1981) 6.5 6.4 6.0".
  - Table 32 text: "Default efficiencies for equipment not listed in the table may either be interpolated
    or estimated by referring to the original references."
  - Table 4 (p. 8): "Air source heat pump (split) Heating/Cooling 7.7 HSPF/13 SEER air source heat pump".
- ResStock v3.2.0 `resources/options_lookup.tsv`, lines 9698-9699,
  https://github.com/NREL/resstock/blob/v3.2.0/resources/options_lookup.tsv
  (`heat_pump_heating_efficiency_type=HSPF heat_pump_heating_efficiency=9.3 ...
  heat_pump_cooling_efficiency=18`, and the matching row for SEER 22 / HSPF 10).

Heating kWh versus the old EER path rises by a factor of 1.16 at SEER 8, 1.30 at SEER 10, 1.45 at
SEER 13, 1.48 at SEER 16 and 1.50 at SEER 22.

### (b) Operating mode from the question; load capped by mode (revision 2)

Old (shipped) used three tests:
- Comfort: outdoor > 75 F.
- "Off" free-float: outdoor > 73 F.
- Load and Practicality: outdoor > setpoint.

Revision 1 used a 66 F outdoor season threshold plus the sign of the heat balance. Both are gone.

New rule (our design, the author's decision of 2026-09-26):
- **Operating mode = the system the household asked about.**
  - `hvac_mode_from_question` is a strict matcher. `\bheat(ing)?\b` (any case) means 'heat'.
    `\bAC\b`, `\bA/C\b` or "air conditioning/conditioner" means 'cool'.
  - A question that names neither, or both, returns None, and every alternative becomes sentinel 1928.
    The mode is never guessed.
  - An explicit `scenario['hvac_mode']` of 'heat' or 'cool' overrides the matcher. Any other explicit
    value also gives the sentinel.
  - No outdoor-temperature season test remains anywhere in the calculator.
- **Load.** It is taken from the setpoint against the house's free-float balance (conduction +
  infiltration + internal gains, plus solar in AC mode), then capped by the mode:
  - heat mode: the heating load if the balance calls for heat, otherwise 0;
  - AC mode: the cooling load if it calls for cooling, otherwise 0.

  There is never cooling in heat mode or heating in AC mode.
- **Everything else follows the mode.** Practicality uses it. The Comfort optimum is 71 F (range 68-74)
  in heat mode and 76 F (range 73-79) in AC mode. The "Off" free-float is outdoor + 10 F in heat mode
  and outdoor + 5 F in AC mode.
- **Solar.** Solar gain enters the balance in AC mode only, which keeps the shipped convention that
  the heating load takes no solar credit. The author's wording mentioned solar in the free-float
  temperature without naming a mode; see flag 2 for the effect of crediting solar in heat mode too.

Modes assigned (full list in `hvac/out/scenario_modes.csv`): all 105 match the question wording one to
one.

| Mode | Scenarios | Test | RAG | Outdoor range |
|---|---|---|---|---|
| heat | 51 | 33 | 18 | 5-62 F |
| cool | 54 | 37 | 17 | 68-102 F |
| none (sentinel) | 0 | 0 | 0 | |

Branch changes against the shipped file (alternatives out of 210 test / 105 RAG):

| Count | Test | RAG |
|---|---|---|
| Load/Practicality branch changes (shipped heating branch, now AC mode) | 9 (7 excluding the 2 Off) | 8 |
| Comfort optimum changes (the three "AC" scenarios at 68/72 F outdoors, ids 68, 75, 77) | 6 | 3 |
| Zero-load alternatives, shipped | 9 | 17 |
| Zero-load alternatives, new (excluding Off) | 0 | 7 |
| Alternatives whose zero/nonzero load status changes | 9 | 10 |

All 7 new zero-load alternatives are heat-mode setpoints where internal gains exceed the losses:
ids 72 (62, 66 F at 50 F outdoors), 74 (68, 72, 76 F at 62 F) and 76 (64, 68 F at 59 F). The shipped
code also gave them zero load, so they are unchanged.

Code paths that build an HVAC scenario and call the calculator. All pass `question`; none was edited.

| Path | Passes `question`? | How |
|---|---|---|
| `HVACGroundTruthCalculator.process_hvac_scenarios` (the calculator's loader) | yes | `'question': row['question']` from the master sheet |
| `Architectures/LLM-Parameterized_Reference_Scoring.py`, `score_with_ground_truth` | yes | `gt_scenario = {**scenario, **extracted_result['parameters']}`; `scenario` is the Test-sheet row, which requires `question` |
| `Miscellaneous Scripts/core-automation/run_baseline_models.py`, `build_scenario_from_test` -> `run_calculator_on_scenarios` | yes | `'question': str(row.get('question', ''))` |
| `Miscellaneous Scripts/experiments/run_hybrid_ablation_experiments.py`, `build_scenario` -> `score_scenario` | yes | `"question": _clean_text(gt_row.get("question"))` |
| `Miscellaneous Scripts/core-automation/evaluate_parameter_extraction.py`, `_build_ground_truth_scenario` and counterfactuals | yes | `"question": gt_row.get("question", test_row.get("question", ""))`; counterfactuals copy it |
| `Analysis/pass5/d1_lookup_baseline.py` | yes | uses `run_hybrid_ablation_experiments.build_scenario` |
| `Miscellaneous Scripts/core-automation/sync_rag_ground_truth_scores.py` | n/a | never calls the calculator; it copies scores from the GT xlsx by descriptor signature |
| Harness and tests in `Analysis/rerun_prep/` | yes | through the loader, or explicit `question` |

One risk, not a failing path. A_H merges the LLM's `parameters` dict over the scenario without a key
whitelist (it only requires `r_value`, `seer`, `hvac_age` and `occupancy_context`). An extraction that
also returned `question` or `hvac_mode` would override the scenario's value. This was already true for
`outdoor_temp` and every other field. The A_H extraction prompt asks only for the four parameters.

### (c) Heating comfort optimum 70 -> 71 F

`WINTER_OPTIMAL = 71`, `WINTER_COMFORT_RANGE = (68, 74)`, midpoint 71. The comfort function picks
`SUMMER_OPTIMAL` or `WINTER_OPTIMAL` by mode. HSP p. 49, citing ASHRAE 55-2004: "Thermostat set points
based on the optimum seasonal temperature for human comfort as defined in ASHRAE Standard 55-2004
(ASHRAE 2004b). Set point for cooling: 76°F with no setup period Set point for heating: 71°F with no
setback period."

### (d) Occupant gain 400 -> 220 Btu/h sensible (revision 2)

`OCCUPANT_SENSIBLE_GAIN_BTUH = 220`, the single-zone row of HSP Table 44 (p. 64), "Peak Sensible and
Latent Heat Gain From Occupants (ASHRAE 2009)": "Single Zone ... Sensible load 220 ... Latent load 164".
Our balance is single-zone. Revision 1 used the 230 Btu/h multi-zone living-area row.
`EQUIPMENT_GAIN_BTUH_PER_SQFT = 1.0` and `BASE_INTERNAL_GAIN_BTUH = 800` are kept as our
assumptions. The HSP gives appliance, MEL and lighting gains only as annual kWh by bedroom count
(Table 21, Eq. 7), and our scenarios have no bedroom count.

### (e) Code comments (B76 and the audit)

As in revision 1:
- EER quadratic: now HSP Eq. 3 citing Wassmer (2003), replacing "AHRI 210/240".
- ACH: now the ASHRAE Standard 62-1989 minimum. Persily (2015): "In 1989, the standard required an air
  change rate of 0.35 h−1 in living areas ...", https://pmc.ncbi.nlm.nih.gov/articles/PMC6605073/.
- Labelled as our values: envelope multipliers, equipment and base gains, solar gain per ft²,
  free-float offsets, degradation rates and cap, Practicality factors.
- Glazing fraction: IECC R405 reference design.
- Rate comment corrected; PJM weekday note added.
- Bounds comments now state the convention.

Revision 2 adds comments on the mode rule, the mode-capped load and the continuous budget penalty.

### (f) Bounds

Convention, confirmed on the shipped file: the 5th and 95th percentiles (numpy linear) of the nonzero
cent-rounded `raw_cost` over all 315 alternatives of the 105 master scenarios, test and RAG pooled.
Environmental = those percentiles / $0.19, times 0.976 (floor) and 1.041 (ceiling). The shipped
$0.38 / $3.29 and 1.96 / 18.04 reproduce exactly. They do not reproduce from unrounded costs.

New, over the new calculator's costs (306 active alternatives: 315 minus 2 Off minus the 7 heat-mode
zero loads):

| Bound | Shipped | Revision 1 | **Revision 2 (in the file)** | Derivation |
|---|---|---|---|---|
| Energy cost min | $0.38 | $0.42 | **$0.59** | p5 = 0.590 |
| Energy cost max | $3.29 | $3.26 | **$3.27** | p95 = 3.2675 |
| Environmental min | 1.96 | 2.14 | **3.03** lbs CO2 | 0.590 / 0.19 = 3.105 kWh x 0.976 |
| Environmental max | 18.04 | 17.84 | **17.90** lbs CO2 | 3.2675 / 0.19 = 17.197 kWh x 1.041 |

The floor rises because the low-cost cooling loads that revision 1 charged in heat-mode scenarios are
now zero, and zeros are excluded. p95 = 3.2675 sits on a rounding boundary; Python's `round` gives
3.27. Appliance and Shower bounds are unchanged (their raw outputs did not change).

### (g) Continuous budget penalty (all three calculators; revision 2)

Old: 1.0 below u = 0.80, then 1 - 2.5(u - 0.8) up to u = 1.0, then 0.5 e^(-3(u-1)) up to u = 1.5,
then 0. New: 0.5 e^(-3(u-1)) for every u >= 1.0, with no drop to 0. u is monthly cost / monthly budget.
Status: our assumption. The paper already says "The values 0.80, 2.5 and 1.5 and the exponential form
are our own choices"; removing the cliff is the author's decision.

Effect:
- **Shower** (max u 0.905) and **Appliance** (max u about 0.23, recomputed 0.2292): no score changes. The Appliance
  `calc_new` output is identical to P1-APP's `calc_new_final.xlsx`, and all 101 Appliance tests pass.
- **HVAC**, shipped model: no alternative reaches u = 1.5 (max 1.39), so no change.
- **HVAC**, new calculator: 3 alternatives reach u >= 1.5 (max 1.84), 9 fall in [1.0, 1.5) and 24 in
  [0.8, 1.0).
- **Bradford** (id 96, test, heat mode, 5 F outdoors, SEER 10, R-9, budget $235): the three
  alternatives cost $4.29, $4.55 and $4.81. That is above the $3.27 upper bound, so their linear Energy
  Cost value is already 0 before the penalty. The continuous penalty therefore leaves their score at 0
  and does not reorder them (68 F first, as in the shipped file, where it scored 0.01 / 0 / 0). Keeping
  the cliff instead changes 0 rankings against the new calculator.

## 3. Stroudsburg data fix (scratch only)

`HVACScenarios.xlsx` row index 30 (Stroudsburg, SEER 8, test scenario): `hvac_age` 95 -> 40 in the
scratch copy. The shipped and new calculators each give 0 cell differences against their own run on
the original master, because degradation caps at 40 years. It is not a RAG scenario, so no exemplar
text changes.

## 4. Shower

Comment edits (no value changes):
- Docstring: 0.9 showers/person/day is our assumption.
- Budget call: "our assumption, not an REU2016 figure".
- Rate comment: bundled default-service rate.
- Mains temperature: "our linear approximation to Burch & Christensen (2007) ... ~2-5 F warmer for PA".
  The code never cited Zhang (2023) for mains temperature.
- Heater efficiency: 10 CFR 430.32(d) "0.9307 − (0.0002 × Vr)", 0.9207 at 50 gal
  (https://www.law.cornell.edu/cfr/text/10/430.32).
- 105 F: "our delivery convention; Zhang et al. (2023) assume 89.6-104 F (32-40 C)".
- CDC: 120 F is the circulation floor and 140 F the storage recommendation
  (https://www.cdc.gov/control-legionella/php/guidance/monitor-water-guidance.html: "Store hot water at
  temperatures above 140°F (60°C)."; "Ensure hot water in circulation doesn't fall below 120°F (49°C)").
  The >140 F penalty is our assumption.

Behavior change: the continuous budget penalty, (g). The output is still identical to the shipped xlsx
and the bounds are unchanged.

## 5. Impact (HVAC, against the shipped reference)

W = changed winner, Full = changed full ordering; test out of 70, RAG out of 35. Exemplar cells are
RAG score cells as A_E renders them (four criteria at 1 dp, MAVT at 2 dp, rank), out of 630.

| Variant | Test W | Test Full | RAG W | RAG Full | Exemplar cells | RAG scenarios changed |
|---|---|---|---|---|---|---|
| (0) nothing changed (MAVT 10-dp rounding only) | 0 | 0 | 0 | 0 | 3 | 3 |
| (a) HSPF alone, old bounds | 3 | 8 | 4 | 6 | 140 | 16 |
| (a) HSPF alone, own bounds (0.55/3.38, 2.84/18.52) | 3 | 7 | 5 | 7 | 211 | 32 |
| (b) mode from question alone, old bounds | 3 | 3 | 3 | 3 | 42 | 8 |
| (b) mode from question alone, own bounds (0.41/3.27, 2.09/17.92) | 3 | 3 | 3 | 3 | 71 | 21 |
| (c) 71 F alone (bounds unaffected) | 8 | 16 | 6 | 6 | 113 | 20 |
| (d) 220 Btu/h alone, old bounds | 2 | 2 | 1 | 1 | 132 | 32 |
| (d) 220 Btu/h alone, own bounds (0.41/3.23, 2.08/17.67) | 1 | 1 | 2 | 2 | 128 | 32 |
| (g) continuous budget alone | 0 | 0 | 0 | 0 | 3 | 3 |
| (f) new bounds alone, shipped model | 1 | 4 | 2 | 2 | 167 | 32 |
| Stroudsburg hvac_age 40 alone | 0 | 0 | 0 | 0 | 0 | 0 |
| All combined, old bounds | 11 | 14 | 10 | 10 | 301 | 35 |
| **All combined, new bounds (the new calculator)** | **13** | **17** | **10** | **10** | **327** | **35** |

Changed winners, new calculator (master row ids):
- test: 3, 15, 29, 39, 45, 48, 55, 56, 59, 68, 69, 75, 86;
- RAG: 25, 27, 35, 47, 73, 74, 76, 77, 81, 103.

Exemplar cells by column: energy cost 77, environmental 73, comfort 47, practicality 5, MAVT 104,
rank 21. All 105 RAG rows change at least one cell, so `sync_rag_ground_truth_scores.py` then
`build_rag_index.py` is required in P4, and A_E HVAC must be rerun (it is, under G1(c)). Scores are not
in the embedding text, so no `RAG_SCHEMA_VERSION` bump is needed.

Sensitivities (all changes combined, each with its own recomputed bounds):

| Variant | vs shipped W/Full (test; RAG) | vs new calculator W/Full (test; RAG) |
|---|---|---|
| Occupant gain 230 instead of 220 | 13/16; 9/9 | 0/1; 1/1 |
| Solar credited in heat mode too (bounds 0.19/3.21, 0.97/17.59) | 11/17; 8/9 | 8/12; 4/4 |
| Budget cliff kept at u = 1.5 | 13/17; 10/10 | 0/0; 0/0 |

## 6. Flags

1. **Mode rule status.** Taking the mode from the question is our design, not a sourced rule. It
   matches every scenario's wording one to one. It also means the reference now depends on the question
   text, so a changed question template changes the mode. The strict matcher returns the sentinel
   rather than guessing.
2. **Solar in heat mode is the largest open choice.** I kept solar out of the heat-mode balance, as the
   shipped heating load did. Crediting it would change 8 test winners against the new calculator,
   because the cost floor falls to $0.19. The author's wording ("outdoor plus internal and solar gains
   ...") could be read either way; please confirm.
3. **A_H has no parameter-key whitelist** (see the code-path table). Not a current failure; noting it.
4. **HSPF anchors above SEER 14 are ResStock option definitions**, not measured pairs. HSPF is also
   seasonal, so there is no low-temperature capacity or COP loss. Every heating scenario is still an
   electric heat pump. The paper's disclosure should say "at the HSPF paired with its SEER" instead of
   "at its cooling efficiency".
5. **Bradford is still all-zero on Energy Cost**, because its costs sit above the 95th-percentile
   bound, not because of the budget penalty.
6. **Stale paper text** (not edited here):
   - Eq. 9's 400 Btu/h per occupant (now 220);
   - "70 F in heating mode" (now 71 F);
   - the B32/B33 disclosure text;
   - B29's budget sentence (the cliff no longer exists);
   - the bounds (1.96-18.04 and $0.38-$3.29, now 3.03-17.90 and $0.59-$3.27);
   - the README reference-range table (P4 step 7);
   - the HVAC worked example and single-criterion numbers.
7. **HSP report number** confirmed on the cover: TP-550-49426, DOE/GO-102010-3141.
8. **The bounds rounding is part of the convention**; p95 = 3.2675 is a half-cent boundary.
9. **P3's MAVT rounding change** (section 1) moves 3 exemplar MAVT cells on its own.

## 7. Tests

`test_hvac_reference.py`: 18 tests. All pass on `calc_new`; 17 fail on the frozen shipped copy.
- HSPF: anchors and interpolation; heating uses HSPF and cooling uses EER; a cold heat-mode scenario is
  priced at HSPF.
- Mode:
  - matcher wording, and sentinel for unmatched or ambiguous questions;
  - explicit `hvac_mode` overrides the matcher (an invalid value gives None);
  - all 105 master questions map to their wording;
  - no season threshold or `is_cooling_season` remains;
  - an AC-mode setpoint just above outdoor carries a cooling load;
  - never cooling in heat mode; never heating in AC mode;
  - Off free-float and Practicality follow the mode.
- Constants: 71 F optimum with range (68, 74); 220 Btu/h per occupant.
- Budget: continuous and strictly decreasing above u = 1.0, positive at u = 2.
- Conventions: sentinel for an unparseable alternative; the new bounds in the value function.

`test_shower_reference.py`: 2 tests (continuous budget; unchanged values and bounds). Both pass on
`calc_new`; the budget test fails on the frozen copy.

`test_appliance_tariffs.py` (P1-APP): 101 pass with
`APPLIANCE_CALC_PATH=Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py`.

## 8. For P4

- Install the three `calc_new` calculators; the files are CRLF, like the shipped ones. The regenerated
  `ground_truth_hvac.xlsx` should match `hvac/out/ground_truth_hvac_NEW_preview.xlsx`.
- After installation, run the tests with `HVAC_CALC_PATH` / `SHOWER_CALC_PATH` /
  `APPLIANCE_CALC_PATH` pointing at `Ground Truth Calculators/`. `impact.py` also honours
  `HVAC_CALC_PATH`.
