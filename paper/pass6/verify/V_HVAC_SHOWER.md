# V_HVAC_SHOWER: independent verification of the HVAC and Shower rerun-prep calculators

Verifier: Phase V sub-agent, 2026-09-26. Scope: HVAC and Shower only.

Files checked:
- `Analysis/rerun_prep/calc_new/{HVAC,Shower}GroundTruthCalculator.py`;
- the shipped `Ground Truth Calculators/` files and the frozen copies in `Analysis/rerun_prep/hvac/shipped/`;
- the harness scripts, the tests, the GT xlsx files and the scenario sheets.

All scratch scripts and outputs are in the session scratchpad under `v_hvac/`. The main one is
`indep.py`, with its output in `indep_out.txt`. It is my own check and does not use the rerun_prep
harness.

Python: `.venv/Scripts/python.exe`. On this machine, numpy intermittently failed with "OpenBLAS
memory allocation" errors. Commands after the first ones were therefore run with
`OPENBLAS_NUM_THREADS=1`, which does not affect the results.

## 1. Reproduction: PASS

The frozen copies are the same files that are live now:
- `sha256sum` gives HVAC `e60a2315...` and Shower `42831287...`. The frozen copies and
  `Ground Truth Calculators/` are byte-identical.
- `git diff --stat c6cdf60 HEAD -- "Ground Truth Calculators" "Ground Truth" "Scenario Files"` is
  empty. The prep commit touched none of these directories; it changed only `sentinel_utils.py`
  among the files I checked.

| Check | Command | Result |
|---|---|---|
| Agent gate | `python Analysis/rerun_prep/hvac/reproduce.py` | ALL PASS, exit 0. HVAC 315x20 with 0 mismatches; HVAC RAG 105/105; Shower frozen and calc_new 240 rows each; Shower RAG 60/60; Shower bounds recompute to 0.1449/1.1354 and 6.00/45.00 |
| My reproduction (no harness) | `indep.py` section 1 | Shipped HVAC and shipped Shower, run through their own `process_*`, equal the GT xlsx in every column. The only difference is `mavt_score`, off by at most 2.2e-16 (the 10-dp rounding in `sentinel_utils`). calc_new Shower equals the GT exactly. |
| RAG score columns | Own match on the full descriptor tuple (question, location, sqft, household, budget, outdoor, housing, insulation/gpm, alternative); no duplicate keys | HVAC 105/105 and Shower 60/60 rows matched, with 0 mismatches in every score, rank and raw column. A first attempt keyed on question+location+alternative alone gave false mismatches, because 2 HVAC and 40 Shower keys are duplicated at that level. |
| "New code with old parameters reproduces" | `python Analysis/rerun_prep/hvac/impact.py` | PASS: the all-reverted variant reproduces the shipped GT with 0 mismatches. The new class equals the all-changes/new-bounds variant with 0 mismatches. Every row of the report's impact table reproduces: 13/17 test and 10/10 RAG; 327/630 exemplar cells; solar sensitivity 8/12 and 4/4. |
| Output drift | `impact_results.json` and `scenario_modes.csv` compared with pre-run copies | Byte-identical. The two regenerated xlsx files have identical content; only the zip metadata differs. |
| Stroudsburg `hvac_age` 95 -> 40 | From `impact.py` | 0 cell changes for both the shipped and the new calculator, because degradation caps at 40 years. It is a test scenario, not a RAG one. |

I also confirmed the partition: the 105 HVAC master rows are exactly the 70 test rows plus the 35
RAG rows, disjoint, matched on normalized descriptors.

## 2. Tests: PASS

| Run | Command | Result |
|---|---|---|
| calc_new | `python -m pytest -q Analysis/rerun_prep/tests/test_hvac_reference.py Analysis/rerun_prep/tests/test_shower_reference.py` | 20 passed (HVAC 18, Shower 2) |
| Shipped files | Same command, with `HVAC_CALC_PATH` and `SHOWER_CALC_PATH` pointing at `hvac/shipped/` | 18 failed, 2 passed. HVAC: 17 of 18 fail; only `test_unparseable_alternative_is_sentinel` passes. Shower: the budget test fails and `test_values_unchanged` passes. This matches the report. |
| Sentinel suite | `python -m pytest -q tests/test_sentinel_aggregation_matching.py` | 46 passed |
| After my comment fix (D1) | Re-ran the calc_new tests | 20 passed. The new HVAC output is still identical to `ground_truth_hvac_NEW_preview.xlsx`. |

## 3. Hunk-by-hunk diff audit: PASS, no unapproved hunk

Command: `diff -u --strip-trailing-cr` of shipped against calc_new.

### HVAC

| Hunk | Maps to (Section 2) |
|---|---|
| PJM comment "non-holiday weekdays" | Weekdays decision |
| Rate comment (0.19 is PA PUC bundled, not EIA) | Comment corrections |
| ACH comment "ASHRAE Standard 62-1989 minimum" | Comment corrections |
| New `OCCUPANT_SENSIBLE_GAIN_BTUH = 220`, `EQUIPMENT_GAIN_BTUH_PER_SQFT = 1.0`, `BASE_INTERNAL_GAIN_BTUH = 800`, the last two labelled as our assumptions | HVAC constants. The actual change is **400 -> 220**, not 230 -> 220; see D8. |
| `HSPF_BY_SEER` anchors and `heating_hspf` | HVAC heating (HSPF paired with SEER) |
| `HVAC_MODES`, `_HEAT_WORDS` and `_COOL_WORDS`; `hvac_mode_from_question`; `resolve_hvac_mode` | HVAC mode |
| `WINTER_COMFORT_RANGE` (68, 75) -> (68, 74) and `WINTER_OPTIMAL` 70 -> 71 | HVAC constants |
| `calculate_net_heat_gain` (the old cooling body with the clamp removed, plus `include_solar`). `calculate_cooling_load` and `calculate_heating_load` become wrappers. | HVAC mode (net-balance load capped by mode). The refactor preserves behaviour: the old heating load (loss minus internal gains, no solar) equals max(0, -net) without solar, and the all-reverted gate proves it. No live code outside the calculator calls these methods; the only other callers are historical `Analysis/pass5` Shower scripts. |
| Envelope-multiplier comment "our multipliers" | Comment corrections |
| `calculate_energy_consumption(mode=...)`: HSPF for heat, EER for cool, and the EER comment now cites HSP Eq. 3 / Wassmer | HVAC heating; comment corrections |
| Comfort takes `mode`, and raises on an invalid mode | Mode: comfort follows the mode |
| Degradation docstring "our assumptions" | Comment corrections |
| Practicality takes `mode` | Mode: practicality follows the mode |
| Budget penalty: the `u >= 1.5 -> 0` branch removed | Budget penalty continuous |
| `apply_value_function` bounds 0.38/3.29 -> 0.59/3.27 and 1.96/18.04 -> 3.03/17.90, with comments | Bounds |
| `_free_float_temp(ac_mode)` | Mode: the "Off" free-float follows the mode |
| `calculate_scenario_scores`: resolve the mode, sentinel when none, net gain capped by mode, `mode=` passed on | Mode |

Every hunk maps to an approved change or a comment correction. Every approved HVAC change is
present:
- HSPF, with COP = HSPF/3.412 (implicit, since both HSPF and EER are in Btu/Wh), while cooling keeps
  EER;
- the mode rule with the explicit-override and sentinel paths;
- the capped load;
- comfort, practicality and free-float following the mode;
- 71 F with range (68, 74);
- 220 Btu/h;
- the continuous budget penalty;
- the new bounds;
- the comments.

No outdoor-temperature season test remains. The Stroudsburg edit is data, handled at Phase I.

### Shower

The Shower diff changes comments only (docstring, rate, mains temperature, CFR heater efficiency,
105 F, CDC thresholds, the >140 F note, 0.9 showers per person) plus the budget-penalty branch.
**The bounds are unchanged**: $0.14/$1.14 and 6.0/45.0 gal, recomputed as p5 0.1449, p95 1.1354,
6.00 and 45.00. PASS.

## 4. Physics sanity: PASS, with notes

- **HSPF and COP.** HSPF rises strictly with SEER over 6-30. The anchor range 6.5-22 gives COP
  1.76-2.93. The master's SEERs (8-22) give COP 1.93-2.93, and A_H's admissible range (6-30) gives
  1.70-3.34. HSPF would go negative only below SEER -8.5, which is unreachable. The cooling EER
  quadratic peaks at SEER 28 (15.68) and dips slightly by 30 (15.60); this is pre-existing and
  negligible.
- **Modes.** I read all 105 questions myself (`indep.py`, section 4b, grouped by template). Every
  one contains exactly one of "heat temperature" or "AC temperature". That includes the two
  free-form ones: "spring cold snap ... What heat temperature is best for sleeping?" (heat) and
  "very humid summer night ... What AC temperature should I use?" (cool). The matcher gives heat
  51 and cool 54, with 0 sentinels, and agrees with the wording in 105/105. Heat-mode outdoor
  temperatures run 5-62 F and AC-mode 68-102 F.
- **Load cap and zero load.** I swept setpoints 40-95 F on all 105 scenarios (5,880 points) and
  computed each scenario's balance point from the calculator's own `calculate_net_heat_gain`.
  - Heat mode: kWh is 0 at or below the balance point, positive above it, and non-decreasing in the
    setpoint.
  - AC mode: the mirror image.
  - 0 violations. Heat mode never produces cooling energy and AC mode never produces heating.
  - Hand-computed kWh (load / efficiency / 1000 x 8 h x runtime multiplier, HSPF for heat and EER
    for cool) matches the calculator on all 313 non-Off master alternatives with 0 mismatches.
- **Budget penalty** (HVAC and Shower identical on a 4,001-point grid):

  | u | Penalty |
  |---|---|
  | 1.5 - 1e-9 | 0.111565080409 |
  | 1.5 | 0.111565080074 |
  | 1.5 + 1e-9 | 0.111565079740 |

  It is also continuous at u = 0.8 (1.0) and at u = 1.0 (0.5000000025 just below, 0.5 at 1.0). It
  is non-increasing on [0, 4], the largest grid step is 0.0025, and it stays positive (6.2e-5 at
  u = 4).
- **Bounds.** The population is every alternative of the 105 HVAC master scenarios (70 test + 35
  RAG = 315 alternatives), excluding $0 costs, using the cent-rounded `raw_cost`. This is the
  HVAC share of the handoff's "285 scenarios", and it is the same convention as the shipped
  bounds: that recipe reproduces 0.38/3.29 and 1.96/18.04 exactly (289 active alternatives).
  - New: 306 active alternatives, p5 = 0.590 and p95 = 3.2675, which rounds to $0.59/$3.27.
  - Environmental: 0.590/0.19 x 0.976 = 3.03 and 3.2675/0.19 x 1.041 = 17.90. Both are derived from
    the cost percentiles, as the decision requires.
  - `apply_value_function` returns 1.0 and 0.0 at those endpoints, so the bounds are used.
  - Note: the recipe depends on the cent rounding. Unrounded costs give p5/p95 = 0.5879/3.2648,
    which would round to 0.59/**3.26**. The report documents this, and it is the convention the
    shipped bounds follow.
- **Sentinel paths.** There is no `.get(..., 0.0)` on a scored quantity. An unmatched question or
  an invalid `hvac_mode` gives 1928 for every alternative, and an unparseable alternative gives
  1928. The remaining defaults are all pre-existing and outside Section 2:
  - `ceiling_height` 8.0;
  - `housing_type` Single-family (x1.7);
  - `maintenance_level` moderate;
  - `electricity_rate` 0.19;
  - `utility_budget` 0, meaning no penalty;
  - an unrecognized `occupancy_context` becomes occupied_all_day (D4);
  - the bare `except:` blocks in `apply_value_function` only parse "a=" from the VF spec strings.

  The "Off" alternative's $0 is by design. Non-positive `square_footage` or `r_value` and a NaN
  outdoor temperature are unguarded (D5); none is reachable from the current data.
- **Units and signs.** Loads are Btu/h and efficiencies Btu/Wh, so kW = Btu/h / eff / 1000.
  Temperatures are all F. Net gain uses (outdoor - indoor), so positive means a gain, i.e. cooling.
- **Degradation.** 0.15 at 10 years, 0.30 at 40 years, and flat at 0.30 for 41, 60 and 95 years.
  The cap is at 40 years, as stated.
- **"Off" alternative.** It is consistent across modes. Its effective temperature is the
  mode-dependent free-float (AC +5 F, heat +10 F) for comfort and practicality, and its energy is
  zeroed. Both Off rows are in test scenarios (ids 56, 57). Note (no action): the +10 F heat
  offset roughly matches the model's own no-solar balance point (about +11 F for a typical
  house). The +5 F AC offset is well below the model's with-solar balance point (about +27 F).
  Both are labelled our assumptions and are unchanged in value.
- **Observation, pre-existing and not in Section 2.** Occupant gains (n x 220) are counted for the
  full 8 h period even in `unoccupied_H` contexts. The effect is small; no action proposed.

## 5. Source spot-checks: PASS

I downloaded the HSP PDF (NREL TP-550-49426, cover confirmed) and extracted its text.
- **Table 32, printed p. 40.** The split heat-pump rows read "14 10.5 8.0", "(after 1991) 10 9.3
  7.1", "(1981–1991) 8 7.7 6.6" and "(before 1981) 6.5 6.4 6.0", as quoted. The interpolation
  sentence is also verbatim.
- **Table 4, printed p. 8.** "Air source heat pump (split) Heating/Cooling 7.7 HSPF/13 SEER air
  source heat pump" is confirmed.
- **Eq. 3.** "EER = –0.02 × SEER2 + 1.12 × SEER (Wassmer 2003)" is confirmed.
- **71 F, printed p. 49 (and the front-matter revision note).** "Thermostat set points based on
  the optimum seasonal temperature for human comfort as defined in ASHRAE Standard 55-2004 ... Set
  point for cooling: 76°F with no setup period / Set point for heating: 71°F with no setback
  period" is confirmed.
- **Occupant gain: 220 Btu/h is correct, and "sensible" is correct.** Table 44 (printed p. 64),
  "Peak Sensible and Latent Heat Gain From Occupants (ASHRAE 2009)", has two blocks:
  - Multiple Zones: "Living area 230 190" (sensible, latent);
  - Single Zone: "Sensible load 220 / Latent load 164".

  So 230 is the multi-zone living-area sensible value and 220 the single-zone sensible value. Our
  balance is single-zone and sensible-only, so 220 is the right row. The table calls these *peak*
  gains, which HSP applies with hourly occupancy profiles; using them as a constant 8 h value is
  our simplification.
- **ResStock v3.2.0 `options_lookup.tsv`** (raw GitHub file at tag v3.2.0). Line 9698 is
  `"ASHP, SEER 18, 9.3 HSPF"` with `heat_pump_heating_efficiency=9.3`, and line 9699 is
  `"ASHP, SEER 22, 10 HSPF"` with `=10`. Both are confirmed. The same block also lists pairs the
  anchors do not use: 10/6.2, 10.3/7.0, 11.5/7.5, 13/7.7, 13/8.0, 14/8.2, 14.3/8.5, 15/8.5, 15/9.0,
  16/9.0 and 17/8.7 (D7).
- **Solar context.** ASHRAE Handbook Fundamentals Ch. 17 (residential loads,
  https://handbook.ashrae.org/Handbooks/F17/IP/f17_ch17/f17_ch17_ip.aspx) says: "Heating
  calculations use simple worst-case assumptions: no solar or internal gains, and no heat storage"
  and "Heating load calculations ignore solar and internal gains, providing a built-in safety
  factor." I read this through a fetch summary, not the full page.

## 6. Solar gain in heat mode: quantified; recommendation below

I re-ran it through `impact.py`: all changes, solar credited in heat mode, and its own recomputed
bounds.
- **Bounds:** cost $0.19/$3.21 and Environmental 0.97/17.59 (against 0.59/3.27 and 3.03/17.90).
- **Against the new calculator:** test winners change in **8/70** (ids 11, 21, 29, 39, 49, 55, 56,
  69), full orderings in 12/70, and RAG winners in 4/35 (25, 64, 73, 103). 283/630 exemplar cells
  change.
- **Against shipped:** test winners 11/70 and RAG 8/35.
- Two of the changed test winners (39 Carlisle at 102 F, 56 Media at 92 F) are AC scenarios. They
  move only because the pooled cost bounds move.

The recommendation is at the end of this file.

## 7. Robustness for A_H: PASS through A_H's guards, with gaps noted

**Direct calls to the new calculator** (`indep.py` section 7):

| Input | Behaviour |
|---|---|
| String `seer` | Works in heat mode (`heating_hspf` calls `float()`); raises TypeError in AC mode |
| String `r_value` or `hvac_age` | Raises TypeError |
| Missing `seer` | Raises KeyError |
| `r_value` = 0 | Raises ZeroDivisionError |
| SEER 5 or 3 (below the first anchor) | Linear extrapolation, sensible and monotone |
| SEER 35 | Works |
| SEER 60 | Negative kWh, giving a perfect cost score. Unreachable: EER goes negative above SEER 56, and A_H caps SEER at 30. |
| Negative sqft | 0 kWh and a perfect cost score, silently |
| Negative `hvac_age` | Works; practicality clamps at 1.0 |
| `hvac_mode='heating'` | Sentinel |
| `hvac_mode='Heat '` | Heat |
| Missing `question` | Sentinel |
| Junk `occupancy_context` | Silently occupied_all_day |
| NaN budget | No penalty |
| NaN outdoor temperature | 0 kWh and a perfect score, silently |
| Float alternative 70.0 | AttributeError at `'off' in alt.lower()` (pre-existing) |

**What A_H does before and around the call** (`Architectures/LLM-Parameterized_Reference_Scoring.py`):
- It requires `r_value`, `seer`, `hvac_age` and `occupancy_context`, so a missing key becomes an
  extraction failure and a sentinel.
- `_validate_numeric_params` requires `r_value` in [1, 60], `seer` in [6, 30] and `hvac_age` in
  [0, 60], so a string that doesn't parse, zero, negatives or out-of-range values become a sentinel.
- It coerces numeric strings to float before the call, so "13" is safe.
- Any exception inside `score_with_ground_truth` is caught and emitted as 1928 with
  `gt_calculation_failed`.
- Alternatives come from the Test sheet as strings, and `square_footage` and `outdoor_temp` come
  from the sheet too.

Every crash case above therefore reaches the run as the sentinel, and SEER below 6.5 is
extrapolated sensibly. The silent cases reachable through A_H are two:
- a junk `occupancy_context` (D4);
- any extra key the LLM returns that overrides a sheet field (`question`, `hvac_mode`,
  `square_footage`, `outdoor_temp`), because the merge `{**scenario, **parameters}` has no
  whitelist (D3; this is the handoff's existing item).

## Discrepancies

No MATERIAL items. None changes a reference score or rank; none goes beyond Section 2.

| ID | Severity | Description | Evidence | Proposed fix | Applied? |
|---|---|---|---|---|---|
| D1 | MINOR | Stale comment in `calculate_net_heat_gain`: "occupants (230 BTU/hr sensible each)" and example "(3 x 230) ... = 2,990" | calc_new L120-121, while the constant is 220 | Change to 220 and 2,960 | **Yes.** Before: `(230 BTU/hr sensible each)` / `(3 x 230) + (1500 x 1.0) + 800 = 2,990 BTU/hr`. After: `(220 ...)` / `(3 x 220) + (1500 x 1.0) + 800 = 2,960 BTU/hr`. Comment only; the file stays CRLF, tests pass and the output is unchanged. |
| D2 | MINOR | The mode matcher is fragile to future wording. `_COOL_WORDS` has no IGNORECASE, so "Air conditioning ..." at the start of a sentence doesn't match. "heat wave" or "heat pump" inside an AC question matches both patterns and gives the sentinel. No current question is affected (105/105 match). | `indep.py` 4b; regex at calc_new L67-68 | Use `r"\bAC\b\|\bA/C\b\|\b(?i:air[- ]condition(?:ing\|er))\b"`, and add a test for capitalized "Air conditioning". Optionally, anchor on "heat temperature" / "AC temperature". | No: it changes matcher behaviour (though no score). The author or lead decides. |
| D3 | MINOR (required before the rerun, per the handoff) | A_H merges extracted `parameters` over the scenario with no key whitelist. Demonstrated: `hvac_mode='heating'` gives an all-sentinel scenario; an extracted `question` can flip the mode; a negative `square_footage` gives a silent perfect cost score. | `score_with_ground_truth` L652; `indep.py` 7 | Restrict the merge to the requested extraction keys, as the handoff already proposes. Show the author the diff. | No (architecture file) |
| D4 | MINOR (pre-existing, outside Section 2) | An unrecognized `occupancy_context` silently becomes `occupied_all_day`, while A_H extracts this field and its comment says "string fields ... are validated separately by the calculators themselves" | `normalize_occupancy_context` L405; A_H L176-177 | Return the sentinel for unrecognized tokens (keep None/NaN handling as the author prefers). All 7 master tokens are recognized, so the reference doesn't change. | No (behaviour change; the author decides) |
| D5 | MINOR (pre-existing) | No guard on `square_footage <= 0`, `r_value <= 0` or NaN `outdoor_temp`. These give 0 kWh (a perfect cost score) or a ZeroDivisionError. Unreachable from the current data and from A_H's validation, except through D3. | `indep.py` 7 | Emit the sentinel in `calculate_scenario_scores` when any of these is non-finite or non-positive | No |
| D6 | MINOR (pre-existing) | `process_hvac_scenarios` catches every exception and silently drops the scenario from the GT xlsx, and Shower is analogous. A failure during the Phase I regeneration would shrink the file without stopping. | calc_new L790-792 | In Phase I, assert HVAC GT = 315 rows and Shower = 240 before running sync, or make the loader re-raise | No |
| D7 | MINOR (documentation) | Provenance does not say that ResStock lists other ASHP pairs, or why only 18/9.3 and 22/10 were taken. The SEERs 15-17 that occur in the master interpolate to 8.33/8.65/8.98; ResStock lists 15/8.5 and 15/9.0, 16/9.0 and 17/8.7, which are non-monotone. | ResStock tsv L9687-9699 | Add one sentence to `PROVENANCE_HVAC.md` / `docs/CALCULATOR_PROVENANCE.md`: HSP Table 32/4 takes precedence up to SEER 14; above that, the two ResStock options that keep HSPF monotone are used, and the other options are listed. | No (the provenance merge is the lead's task) |
| D8 | MINOR (documentation) | The handoff, Section 1 item 1, says "Occupant gain 230 → 220". The shipped value is **400** (sensible plus latent, credited to the ASHRAE HoF). 230 was only revision 1. The paper's Eq. 9 (400) is what has to change. | Shipped L103 `household_size * 400`; the report's §2(d) states 400 -> 220 correctly | Correct the wording wherever the change is described | No (handoff file) |
| D9 | MINOR (comment) | Two comments disagree with the provenance: the ACH comment still leads "Source: ACCA Manual J (2016)", while the provenance gives ASHRAE 62-1989 via Persily as the source and Manual J as context; the rate comment cites "EIA ... Table 2.10", while the provenance cites "EIA Table 5A" | calc_new L29-36 | Settle it in the provenance merge. I didn't change it because I didn't re-open the EIA source to see which table is right. | No |
| D10 | NOTE | The bounds convention depends on the cent rounding: unrounded p95 = 3.2648 would give $3.26, not $3.27 | `indep.py` 4e | None needed. It is the shipped convention and is documented, but state "cent-rounded costs" wherever the convention is described. | n/a |
| D11 | NOTE (scenario data) | `alternative_3` in `HVACScenarios.xlsx` is text in 101 numeric rows, while `alternative_1/2` are numeric in all 105 rows. This conflicts with SCENARIO_FIXES #37/#38, which say the reverse. | openpyxl `data_type`: row 0 has 72 'n', 76 'n', '80' 's' | Logged as SCENARIO_FIXES #39 for the lead to pick one direction. There is no score effect either way. | Logged |

## Solar-gain recommendation

**Keep solar out of the heat-mode balance, as the calculator does now.** Reasons:

1. **The only solar number we have is unsourced and suits cooling.** 20 Btu/h per ft² of glass,
   applied as a constant, credits a 1,500 ft² house with 4,500 Btu/h. That is about 40% of its
   loss at 30 F outdoors and 70 F indoors (about 272 Btu/h·F x 40 F).
2. **It would be credited in the dark.** 10 of the 51 heat-mode scenarios are overnight
   (`overnight_sleep` 9, `sleep` 1), and the scenarios have no time of day. A constant credit
   would give night-time heating the same solar offset as noon.
3. **Standard practice leaves it out.** The standard residential method (ASHRAE Fundamentals
   Ch. 17) excludes solar from heating calculations: "Heating load calculations ignore solar and
   internal gains." Our heat mode already credits internal gains, so it is already less
   conservative than that method. Adding solar would move it further from it.
4. **No sourced heating-season value exists for us to use.** The HSP models solar hourly from
   weather files with SHGC, window orientation and shading, and gives no heating-season constant.
   I found no primary source for a single winter solar credit that fits our scenario fields.
5. **The effect is large.** Crediting it changes 8/70 test winners and 4/35 RAG winners, and
   drops the pooled cost floor from $0.59 to $0.19, which moves AC scenarios too.

If the author wants some winter solar anyway, the defensible version would take a sourced
transmitted-solar value for PA winter days, apply it only in daytime occupancy contexts (never
overnight), and set it lower than the cooling value. That needs a new source and a time-of-day
rule, both beyond Section 2.

Suggested paper wording, for the lead to adapt: "the heating balance credits internal gains but
takes no solar credit". Don't claim "per ASHRAE": ASHRAE also drops internal gains.

## Git and file writes

Git: I ran only read-only commands, `git diff --stat c6cdf60 HEAD -- ...` and
`git status --short`.

Files written:
- this report;
- one appended row (#39) in `paper/pass6/verify/SCENARIO_FIXES.md`;
- the comment fix D1 in `Analysis/rerun_prep/calc_new/HVACGroundTruthCalculator.py`;
- a regeneration of `Analysis/rerun_prep/hvac/out/*` by `impact.py` (identical content);
- scratch files.

Nothing in `Scenario Files/`, `Ground Truth/`, `Ground Truth Calculators/`, `Architectures/`,
`chroma_rag_db/` or the paper was touched.
