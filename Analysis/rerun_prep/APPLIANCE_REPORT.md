# P1-APP: Appliance reference calculator fixes

Written 2026-09-25. New calculator: `Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py`.
The shipped file (`Ground Truth Calculators/ApplianceGroundTruthCalculator.py`) and
`Ground Truth/ground_truth_appliance.xlsx` are untouched.

## Files

| Path | What it is |
|---|---|
| `Analysis/rerun_prep/calc_new/ApplianceGroundTruthCalculator.py` | New calculator, ready to install over the shipped file |
| `Analysis/rerun_prep/appliance/shipped/ApplianceGroundTruthCalculator.py` | Byte-identical copy of the shipped calculator, kept as the "before" for comparisons |
| `Analysis/rerun_prep/appliance/harness.py` | Runs any calculator file over the 100 master scenarios via that file's own `process_appliance_scenarios()`, output redirected to `appliance/out/`; `python harness.py <calc.py>` compares against the shipped ground truth |
| `Analysis/rerun_prep/appliance/impact.py` | Per-fix and combined impact, bounds recomputation; writes `appliance/out/impact_summary.txt` and `appliance/out/ground_truth_appliance_NEW.xlsx` (what the new calculator would write) |
| `Analysis/rerun_prep/appliance/calc_new.diff` | Full diff, shipped -> new |
| `Analysis/rerun_prep/PROVENANCE_APPLIANCE.md` | Source, verbatim quote and status (sourced / derived / our assumption) for every constant and value function in `calc_new` |
| `Analysis/rerun_prep/tests/test_appliance_tariffs.py` | 101 pytest regression tests; file under test = `APPLIANCE_CALC_PATH` env var, else `calc_new` |

## Reproduction check (before any edit)

- The unmodified copy reproduces `Ground Truth/ground_truth_appliance.xlsx` exactly: 300 rows
  (100 scenarios x 3 alternatives), 0 differences in `alternative`, the four criterion scores,
  `mavt_score`, `rank`, `raw_cost`, `raw_emissions`.
- The new logic run with the shipped rates, mapping and bounds also reproduces it exactly
  (`impact.py`, "New logic + shipped data vs GT: IDENTICAL"). So every change in the impact
  tables comes from the data changes, not from the refactored period lookup.
- Test/RAG split: `scenario_id` = master row index. The 35 RAG scenarios are the master rows
  whose descriptors (location, budget, appliance, housing type, household size, kWh/cycle,
  appliance age) match `Scenario Files/ApplianceRAGScenarios.xlsx`; the other 65 are test.
  Question text alone can't split them (16 questions appear in both sets).

## Changes, old -> new, with sources

One common rate period for every utility: **December 1, 2025 - May 31, 2026.** Windows are
`[start, end)` clock hours; a window with start > end wraps past midnight.

One common rate basis (coordinator follow-up, 2026-09-25): every utility uses its full price to
compare, generation plus transmission. PECO and PPL were first implemented as generation-only
and then moved to the PTC basis. FirstEnergy and Duquesne were already on it.

### PECO (super off-peak added; transmission-inclusive)

| Item | Old (generation only, rounded) | New (TOU pricing option incl. transmission) |
|---|---|---|
| Peak (2-6 p.m. Mon-Fri) | 0.320 | 0.32747 |
| Off-peak | 0.076 | 0.08382 |
| Super off-peak (midnight-6 a.m. every day) | not modeled | 0.06061 |

Source: PECO Price to Compare sheet, updated 5/15/2026,
https://azure-na-assets.contentstack.com/v3/assets/blt1b5616c79bacadb4/bltf7c1eb06cdfe6ab9/6a0e7050df378b4731251e82/2026_RESIDENTIAL_Final_Electric_PTC_Effective_06-01-2026.pdf

> "PECO Time-of-Use (TOU) Pricing Option Effective December 1, 2025 through May 31, 2026"
> "Residential (R) Peak kWhs 32.747 31.960 0.787"
> "Off-Peak kWhs 8.382 7.595 0.787"
> "Super Off-Peak kWhs 6.061 5.274 0.787"
> (columns: TOU Pricing Option (A) = TOU Generation Charge (B) + Transmission Charge (C), cents/kWh)
> "(5) Peak period refers to 2:00 p.m. through 6:00 p.m., Monday through Friday, excluding PJM holidays; Super Off-Peak period refers to midnight (12 a.m.) through 6 a.m., every day; Off-Peak period refers to all other hours that are not Peak and Super Off-Peak periods."

The new values are column (A), which includes the 0.787 c transmission charge. The old
0.320/0.076 were column (B), generation only, rounded.

### PPL (Dec 2025 winter rates and the winter window)

| Item | Old | New |
|---|---|---|
| On-peak window | 2-6 p.m. (summer window, used year-round) | 4-8 p.m. Mon-Fri (winter) |
| On-peak | 0.160 | 0.13986 (GSC 10.643 + TSC 3.343 c) |
| Off-peak | 0.070 | 0.11987 (GSC 8.644 + TSC 3.343 c) |

Source: PPL Electric Pa. P.U.C. No. 201, **Supplement No. 402**, Twenty-Third Revised Page
No. 19Z.5B, issued October 31, 2025, effective December 1, 2025 (in the master tariff posted
2025-12-01),
https://www.pplelectric.com/site/-/media/PPLElectric/At-Your-Service/Docs/Current-Electric-Tariff/2025/Dec/master402-403-posted-2025-12-1.pdf

> "The following Generation Supply Charges apply for service under the TOU Program during the period December 1, 2025 through May 31, 2026. On-Peak hours will be set based on schedule below Monday through Friday, excluding weekends and holidays."
> "Rate Schedule RS and RTS (R) (4:00 PM to 8:00 PM) ... December 1 to May 31"
> "On-Peak Hours 10.643 cts per kWh (I)"
> "Off Peak Hours 8.644 cts per kWh (I)"

Supplement 402 gives only the generation supply charge (GSC). The transmission-inclusive TOU
figures come from PPL's own price-to-compare sheet, "Price to Compare December 1, 2025 through
May 31, 2026",
https://www.pplelectric.com/site/-/media/PPLElectric/At-Your-Service/Docs/Current-Electric-Tariff/2025/Nov/PTC-December-1-2025--May-31-2026.ashx
(columns: "Generation Supply Charge ( ¢ / KWH )", "Transmission Service Charge ( ¢ / KWH )",
"2025 PA Tax Adj Surchg.(1) ( ¢ / KWH )", "Price to Compare ( ¢ / KWH )"):

> "Residential (TOU On peak - Non-Summer) 10.643 3.343 0.000 13.986"
> "Residential (TOU Off peak - Non-Summer) 8.644 3.343 0.000 11.987"
> "RS (Residential Service) 9.610 3.343 0.000 12.953"

So PPL does publish a transmission-inclusive TOU figure, and it is used directly: 13.986 and
11.987 c. Its generation column matches Supplement 402, and the flat RS PTC of 12.953 c matches
the PA PUC release ("PPL: 12.49 to 12.953").

Note on Supplement 393: it covers "the period June 1, 2025 through November 30, 2025". Its winter
column (7.938 / 6.471 c, not marked as changed) is the prior winter's rate, so it is not the
source for Dec 2025-May 2026.

### FirstEnergy: West Penn, Penelec, Met-Ed (super off-peak added; Dec 2025 PTCs)

TOU rate = residential PTCDefault x Supplement No. 20 multiplier. PTCDefault includes
transmission. The rider's formula (FE PA tariff, Original Page 205, consolidated Jan 2026
tariff) contains "PTCNITS = When the Company purchases Network Integration Transmission Service
from PJM on behalf of customers, a Network Integration Transmission Service Charge for Default
Service ...", so FE is already on the PTC basis.

| Utility | PTCDefault old -> new ($/kWh) | On-peak x | Off-peak x | Super off-peak x | Peak old -> new | Off-peak old -> new | Super off-peak new |
|---|---|---|---|---|---|---|---|
| West Penn | 0.10317 -> 0.10947 | 1.6649 | 0.8542 | 0.6298 | 0.172 -> 0.18226 | 0.088 -> 0.09351 | 0.06894 |
| Penelec | 0.11003 -> 0.11747 | 1.6792 | 0.8482 | 0.6510 | 0.185 -> 0.19726 | 0.093 -> 0.09964 | 0.07647 |
| Met-Ed | 0.11903 -> 0.12965 | 1.7060 | 0.8397 | 0.6215 | 0.203 -> 0.22118 | 0.100 -> 0.10887 | 0.08058 |

Windows: on-peak 2-9 p.m. Mon-Fri (unchanged); super off-peak 11 p.m.-6 a.m. every day (new);
off-peak all other hours. The code stores the products as `PTC * multiplier` expressions.

Multipliers: FirstEnergy Pennsylvania Electric Company, Electric Pa P.U.C. No. 1, **Supplement
No. 20**, First Revised Page 221, issued April 22, 2025, effective June 1, 2025,
https://www.puc.pa.gov/pcdocs/1875621.pdf

> Met-Ed Residential: "PTCDefault Rate x 1.7060" (On-Peak), "PTCDefault Rate x 0.8397" (Off-Peak), "PTCDefault Rate x 0.6215" (Super Off-Peak)
> Penelec Residential: "PTCDefault Rate x 1.6792", "PTCDefault Rate x 0.8482", "PTCDefault Rate x 0.6510"
> West Penn Residential: "PTCDefault Rate x 1.6649", "PTCDefault Rate x 0.8542", "PTCDefault Rate x 0.6298"
> "On-Peak 2 PM - 9 PM Monday - Friday"; "Off-Peak All Other Hours"; "Super Off-Peak 11 PM - 6 AM Every day"

The utility-to-multiplier assignment was read from the rate page (each block headed "Customer
Class Met-Ed / Penelec / Penn Power / West Penn") and matches Schedule 1, "Updated June 1, 2025
TOU Multipliers" (Met-Ed 0.8397 / 1.7060 / 0.6215; Penelec 0.8482 / 1.6792 / 0.6510; West Penn
0.8542 / 1.6649 / 0.6298, in off / on / super order). So the audit's "x0.6298/0.6510/0.6215"
list was in West Penn / Penelec / Met-Ed order. Page 221 is still the Supplement 20 page in
FirstEnergy's consolidated tariff dated January 1, 2026 ("Issued: April 22, 2025 Effective: June
1, 2025"),
https://www.firstenergycorp.com/content/dam/customer/Customer%20Choice/Files/PA/tariffs/fe-pa-retail-tariff-1-1-26.pdf,
so the multipliers were in force for the whole period. The rider says the multipliers are
reviewed every two years.

PTCDefault: FirstEnergy PA **Supplement No. 28**, Sixth Revised Page 203 (Price to Compare
Default Service Rate Rider), issued October 15, 2025, effective December 1, 2025,
https://www.firstenergycorp.com/content/dam/customer/Customer%20Choice/Files/PA/tariffs/FEPA-Supp-No-28-PTC-HPS-Rider-Changs-12-1-2025.pdf
(retrieved directly; also archived at web.archive.org, 2026-01-09)

> "For service rendered December 1, 2025 through May 30, 2026 the PTCDefault rates billed by Customer Class are as follows:"
> Met-Ed, Residential, Rate Schedule RS, GS-V: "$ 0.12965 (I) per kWh"
> Penelec, Residential: "$0.11747 (I) per kWh"
> West Penn, Residential: "$0.10947 (I) per kWh"

The same three values appear in the PA PUC release (below): "Met-Ed: 11.905 to 12.965", "Penelec:
11.004 to 11.747", "West Penn Power: 10.318 to 10.947".

### Duquesne (value confirmed; placeholder window removed)

| Item | Old | New |
|---|---|---|
| Window | `peak_hours: (14, 21)` placeholder with equal rates | `peak_hours: None` -> period "flat" |
| Rate | 0.1375 peak = off-peak | `flat_rate: 0.1375` |

Source: PA PUC press release "PUC Alerts Consumers of December 1 Electric Price Changes",
published 11/24/2025,
https://www.puc.pa.gov/press-release/2025/puc-alerts-consumers-of-december-1-electric-price-changes-11242025

> "Duquesne Light: 12.43 to 13.75 ¢/kWh ( +10.6% )"

The audit's "13.75 c unverified" is now verified: 13.75 c is Duquesne's residential PTC
effective December 1, 2025. Duquesne's result is identical by construction (variant b5).

### City-to-utility mapping

| City | Old | New | Test/RAG rows | Source |
|---|---|---|---|---|
| Indiana | West Penn | Penelec | test sid 1, 6 | FE tariff: "INDIANA COUNTY - Penelec and West Penn Rate Districts / Penelec Rate District / Boroughs of Armagh, Blairsville, ..., Homer City, Indiana, Marion Center, ..." |
| Carlisle | Met-Ed | PPL | test sid 20 | PPL tariff p. 4: "CUMBERLAND COUNTY Boroughs of Camp Hill, Carlisle, Lemoyne, ..." (FE's Cumberland list for Met-Ed has only "Borough of Mt. Holly Springs" and five townships) |
| Reading | PPL | Met-Ed | RAG sid 46 | FE tariff: "BERKS COUNTY - Met-Ed Rate District / City of Reading." |
| Lebanon | PPL | Met-Ed | RAG sid 64 | FE tariff: "LEBANON COUNTY - Met-Ed Rate District / City of Lebanon." (PPL's Lebanon County list: "Borough of Richland. Townships of Heidelberg and Millcreek.") |
| State College | PPL | West Penn | RAG sid 52 | FE tariff: "CENTRE COUNTY - Penelec, PSU and West Penn Rate Districts ... West Penn Rate District / Boroughs of Bellefonte, Centre Hall, Howard, Milesburg, Millheim, Port Matilda, State College, Unionville." |
| Chambersburg | Met-Ed | West Penn | RAG sid 68 | FE tariff: "FRANKLIN COUNTY - Penelec and West Penn Rate Districts ... West Penn Rate District / Boroughs of Chambersburg, Greencastle, Mercersburg, Mont Alto, Waynesboro." |
| Stroudsburg | PPL | PPL (unchanged, flagged) | test sid 91 | see flags |
| Quakertown | PPL | PPL (unchanged, flagged) | test sid 95 | see flags |

FE tariff = FirstEnergy PA Electric Pa P.U.C. No. 1, "Description of Territory" (pp. 6-20),
consolidated tariff of Jan 1, 2026 (URL above). PPL tariff = PPL Electric Pa. P.U.C. No. 201,
"Territory Covered by this Tariff" (pp. 4, 4A, 4B), in the Dec 2025 master tariff (URL above).

### Weekday rule and comments

- Weekday rule: one line added where the TOU windows are defined, "All scenarios are treated as
  non-holiday weekdays: the weekday windows below apply as coded." The PJM comment "Weekday/holiday
  distinction not modeled" now reads "Peak window: 7am-11pm on non-holiday weekdays (PJM's
  definition); every scenario is treated as a non-holiday weekday, so the window applies as
  coded." No weekday logic changed.
- B76 comment fixes: PPL "Rate RTS" -> "GSC-1 TOU Program for Rate Schedules RS and RTS
  (Supplement No. 402)"; FirstEnergy multipliers "FirstEnergy Corp. (2026)" -> "FE PA tariff
  Supplement No. 20, PA PUC doc 1875621"; PTCs "Jun-2025 PTCs (FirstEnergy Corp. (2025))" ->
  "FE PA tariff Supplement No. 28"; PECO "(PECO Energy Company (2026))" -> the PECO Price to
  Compare sheet for Dec 2025-May 2026; Duquesne "(Duquesne Light Company (2026))" -> the PA PUC
  release; "strongly correlated" -> "moderately correlated"; the mapping comment "verified
  against PA PUC service-territory maps" (which was wrong for six cities) -> the two tariff
  territory lists; the MODELING SCOPE comment ("single (summer) weekday peak window ... seasonal
  summer/winter peak-window shifts are NOT modeled") -> one common Dec-May period whose winter
  windows apply to every scenario.

### Code structure (behavior-neutral)

- `UTILITY_RATES` entries may carry `super_offpeak_hours` / `super_offpeak_rate`; a `peak_hours`
  of `None` means flat (`flat_rate`).
- New `_in_window(hour, (start, end))` handles windows that wrap past midnight (11 p.m.-6 a.m.).
- `determine_rate_period` returns `"peak"`, `"super_offpeak"`, `"offpeak"` or `"flat"`; peak is
  tested first, then super off-peak. `calculate_energy_cost` reads `rates[period + "_rate"]`.
  The `location=None` default (2-6 p.m.) is kept.
- The two physical-criterion bounds moved from literals inside `apply_value_function` to class
  constants `ENERGY_COST_BOUNDS` and `ENVIRONMENTAL_BOUNDS`, so tests and variants can read or
  override them. The public API used by `LLM-Parameterized_Reference_Scoring.py`
  (`calculate_scenario_scores`) is unchanged.

## New bounds

Convention check first: numpy linear 5th/95th percentiles of the shipped ground truth's
`raw_cost` (4 dp) and `raw_emissions` (3 dp) columns over all 300 alternatives (test + RAG
pooled), then `np.round(x, 3)`, reproduce all four shipped constants:
cost p5 0.024595 -> 0.025, p95 0.7105 -> 0.71; emissions p5 0.2884 -> 0.288, p95 3.643 -> 3.643.
Two details matter: the unrounded per-alternative values give emissions p5 0.288878 -> 0.289,
not 0.288; and Python's `round(0.7105, 3)` gives 0.711, not 0.71. Only the output-column,
`np.round` version reproduces all four.

| Bound | Old | New | Unrounded percentile (new) |
|---|---|---|---|
| Energy cost min ($/cycle) | 0.025 | **0.028** | 0.0276 |
| Energy cost max ($/cycle) | 0.71 | **0.774** | 0.7741 |
| Environmental min (lbs CO2) | 0.288 | 0.288 | 0.2884 |
| Environmental max (lbs CO2) | 3.643 | 3.643 | 3.643 |

Emissions don't depend on tariffs or mapping, so their bounds can't move. `impact.py` recomputes
these and warns if the constants in the file drift from the derived values.

## Impact

W = scenarios whose winner changes; R = scenarios whose full ranking changes; S = scenarios with
any criterion-score change. Baseline = shipped calculator. Test n = 65, RAG n = 35. Each fix
alone keeps everything else at the shipped value, including the shipped bounds.

| Variant | Test W | Test R | Test S | RAG W | RAG R | RAG S |
|---|---|---|---|---|---|---|
| a: super off-peak only (shipped rates; PECO 5.274 c generation-only to match the shipped basis, FE old PTC x super multiplier) | 4 | 4 | 23 | 0 | 0 | 7 |
| b: Dec 2025-May 2026 rates and windows (PTC basis), no super off-peak | 1 | 2 | 49 | 0 | 0 | 29 |
| b1: PPL PTC-basis rates (13.986/11.987) + 4-8 p.m. window | 1 | 1 | 9 | 0 | 0 | 12 |
| b2: PPL 4-8 p.m. window only (old PPL rates) | 1 | 2 | 8 | 0 | 0 | 9 |
| b3: PECO PTC-basis values only (0.32747/0.08382) | 0 | 1 | 21 | 0 | 0 | 11 |
| b4: FE Dec 2025 PTCs only (no super off-peak) | 0 | 0 | 19 | 0 | 0 | 6 |
| b5: Duquesne flat, no window | 0 | 0 | 0 | 0 | 0 | 0 |
| c: city mapping only (6 cities) | 0 | 0 | 3 | 0 | 0 | 3 |
| a+b: all tariff fixes | 5 | 6 | 49 | 0 | 0 | 31 |
| a+b+c: all fixes, shipped bounds | 5 | 6 | 49 | 0 | 0 | 31 |
| f: new bounds only (shipped rates and map) | 1 | 2 | 62 | 3 | 3 | 33 |
| **ALL: a+b+c+f (the new file)** | **5** | **5** | **55** | **2** | **2** | **30** |
| sensitivity: ALL + Stroudsburg -> Met-Ed | 6 | 6 | 55 | 2 | 2 | 30 |

The new bounds, applied on top of a+b+c, change 0 test winners, 1 test ranking (sid 54
Philadelphia, which a+b+c had reordered and the new bounds put back), and 2 RAG winners. They
change scores in 63 test and 33 RAG scenarios, since widening the cost range rescales every
cost score.

Which scenarios change:
- a: test sid 1 Indiana, 4 Greensburg, 30 Gettysburg, 36 Chester (the four audit flips: dryers
  where 11 p.m. or midnight now beats the afternoon/evening baseline).
- b / b1: test sid 74 Bethlehem (PPL; under the 4-8 p.m. window, 4 p.m. and 6 p.m. are both
  on-peak, so the zero-delay 4 p.m. wins). b2 also swaps the second and third alternatives in test sid 44 Allentown.
- b3 (and so b, a+b, a+b+c): test sid 54 Philadelphia swaps its second and third alternatives
  under the shipped bounds. Under the new bounds its shipped order returns.
- f alone: test sid 36 Chester (winner), 6 Indiana (ranking); RAG sid 77 Erie, 80 King of
  Prussia, 83 Philadelphia.
- ALL (the new file), full orderings:

| Set | sid | City | Appliance | Baseline | Old ranking | New ranking | New MAVT gap |
|---|---|---|---|---|---|---|---|
| test | 1 | Indiana | dryer | 7 PM | 7 PM > 11 PM > 2 PM | 11 PM > 7 PM > 2 PM | 0.0145 |
| test | 4 | Greensburg | dryer | 5 PM | 5 PM > 11 PM > 2 PM | 11 PM > 5 PM > 2 PM | 0.0155 |
| test | 30 | Gettysburg | dryer | 3 PM | 3 PM > 11 PM > 1 AM | 11 PM > 3 PM > 1 AM | 0.0200 |
| test | 36 | Chester | dryer | 5 PM | 5 PM > 12 AM > 2 PM | 12 AM > 5 PM > 2 PM | 0.0210 |
| test | 74 | Bethlehem | dryer | 4 PM | 6 PM > 4 PM > 10 PM | 4 PM > 6 PM > 10 PM | 0.0490 |
| RAG | 80 | King of Prussia | dishwasher | 5 PM | 11 PM > 5 PM > 8 AM | 5 PM > 11 PM > 8 AM | 0.0030 |
| RAG | 83 | Philadelphia | dishwasher | 2 PM | 8 PM > 2 PM > 2 AM | 2 PM > 8 PM > 2 AM | 0.0040 |

The two RAG flips are near-ties (old gaps 0.006 and 0.005) that the wider cost range tips. They
change A_E exemplar ranks, not just scores.

## Dishwasher peak-to-off-peak savings

The saving is a rate ratio, so it doesn't depend on kWh/cycle. Dollar figures use the master
set's median dishwasher cycle, 1.1 kWh.

| Utility | Old peak -> off-peak | New peak -> off-peak | New peak -> super off-peak | New $/cycle at 1.1 kWh (peak / off / super) |
|---|---|---|---|---|
| PECO | 76.25% | 74.4% | 81.5% | 0.360 / 0.092 / 0.067 |
| PPL | 56.25% | **14.3%** | n/a | 0.154 / 0.132 / n/a |
| West Penn | 48.8% | 48.7% | 62.2% | 0.200 / 0.103 / 0.076 |
| Penelec | 49.7% | 49.5% | 61.2% | 0.217 / 0.110 / 0.084 |
| Met-Ed | 50.7% | 50.8% | 63.6% | 0.243 / 0.120 / 0.089 |
| Duquesne | 0 (flat) | 0 (flat) | n/a | 0.151 flat |

The supplement's "49-76%" becomes **14-74% to off-peak** across the five TOU utilities, and
**61-81.5% to super off-peak** for the four utilities that have one. Adding the same
transmission charge to both periods narrows PECO's and PPL's percentage spread. PPL's winter
spread is small (13.986 vs 11.987 c). The 38% that B39 quoted is its summer generation-only
spread.

## Flags

1. **Stroudsburg left on PPL.** Both tariffs list the borough: PPL p. 4A, "MONROE COUNTY Boroughs
   of East Stroudsburg (part), Mount Pocono, and Stroudsburg (part)."; FE, "MONROE COUNTY - Met-Ed
   Rate District / Boroughs of Delaware Water Gap, East Stroudsburg, Stroudsburg." The FE tariff
   never uses "(part)" anywhere, so its listing doesn't show whole-borough coverage. Wikipedia
   (not primary) says "In the borough, the two companies' service areas overlap and they share
   utility lines, with the electric provider varying by home or business." No primary source
   settles which utility a Stroudsburg household has. Moving it to Met-Ed changes 1 more test
   winner (sid 91): 6/65 instead of 5/65.
2. **Quakertown left on PPL; it is a municipal utility.** The borough runs its own system
   (quakertown.org, archived 2026-06-06,
   http://web.archive.org/web/20260606022823/https://www.quakertown.org/government/electric-department:
   "The Borough has owned and operated its own electric system since the early 1890's. We generated
   our own power until 1969, at which time we started to purchase our power at the wholesale level.").
   The borough is in neither PPL's Bucks County list (Richlandtown, Sellersville, Silverdale,
   Telford, Trumbauersville boroughs; East Rockhill, Haycock, Hilltown, Milford, Richland,
   Springfield, West Rockhill townships) nor FE's (Riegelsville; Bridgeton, Durham, Nockamixon,
   Tinicum). PPL serves the surrounding townships (Richland, Milford). The municipal rates aren't
   in the model, so the scenario (test sid 95) stays on PPL. Options for the author: keep PPL as
   "the surrounding PPL area", or replace the city in the scenario data.
3. **Chambersburg is also a municipal system.** chambersburgpa.gov/government/electric.html:
   "operates the largest of the thirty-five such municipal power systems in Pennsylvania, and is
   the only one that still generates its own electricity", and "Prior to 2002, municipal electric
   utilities purchased their power though the host utility. In our case this was West Penn Power,
   now a First Energy Company." The FE tariff lists the borough under West Penn, so it is mapped
   to West Penn as the plan says. This is a RAG row (sid 68) and changes no ranking.
4. **Rate basis, resolved.** Every utility is now on the full price-to-compare basis. PECO: TOU
   column (A), including 0.787 c transmission. PPL: PTC-sheet TOU figures, GSC + 3.343 c TSC.
   FirstEnergy: PTCDefault, which includes the PTCNITS transmission term. Duquesne: residential
   PTC; I did not inspect Duquesne's PTC formula, and the coordinator said it stays as it is. No
   distribution charges are included for any utility.
5. **FirstEnergy period end date.** Supplement 28 says "through May 30, 2026", not May 31. Recorded
   in the code comment; it has no effect.
6. **Holidays.** PECO excludes "PJM holidays" from peak, PPL excludes "weekends and holidays", and
   FE's rider says "Monday - Friday". Under the author's weekday rule every scenario is a
   non-holiday weekday, so all three weekday windows apply as coded.
7. **No figure was left unverified.** Every rate, multiplier, window and mapping above comes from
   a primary document (tariff supplement, utility rate sheet, or PA PUC release) for Dec 2025-May
   2026.

## Knock-ons outside this task (not edited)

- `tests/audit_scenarios.py` has its own copy of `CITY_TO_UTILITY` with the six old assignments.
- README appliance reference-range table (CLAUDE.md requires it to match the bounds): cost
  0.025-0.71 -> 0.028-0.774.
- Supplement Table S1.6 (rates, PPL window, Duquesne "2-9pm"), the "49-76%" sentence, the
  "weekday summer rates" sentence (B40), "PPL (Rate RTS)" (B39), and the B38 bib entries. The PECO
  URL the B38 entry asked for is the contentstack link above. Supplement 20 was issued April 22,
  2025. New sources to cite: FE Supplement 28, PPL Supplement 402 plus PPL's Dec 2025-May 2026
  PTC sheet, and the PUC release (Duquesne).
- Install sequence (P4): copy `calc_new` over the shipped file -> run it (writes
  `ground_truth_appliance.xlsx`) -> `sync_rag_ground_truth_scores.py` -> `build_rag_index.py`.
  30/35 RAG scenarios' exemplar scores change and 2 RAG exemplar rankings change, so A_E Appliance
  must be re-collected (already in the G1(c) rerun). A_H and the baselines recompute offline.
- `harness.py` with no argument now reports "DIFFERS" for `calc_new`, as it should. Use it on
  `appliance/shipped/` to re-prove reproduction, or `impact.py` for the full before/after.

## Diff summary

`git diff --no-index --stat`: 1 file changed, 89 insertions(+), 44 deletions(-). Full diff in
`Analysis/rerun_prep/appliance/calc_new.diff`. By area:

- Class comments, lines ~21-33: PJM weekday comment; rate-period, basis, weekday and FE-source comments.
- `UTILITY_RATES`: all six entries replaced (values, windows, super off-peak keys, Duquesne flat).
- Mapping comment rewritten; 6 values changed (Reading, Lebanon, State College, Indiana,
  Chambersburg, Carlisle).
- New `ENERGY_COST_BOUNDS = (0.028, 0.774)`, `ENVIRONMENTAL_BOUNDS = (0.288, 3.643)` with a
  derivation comment.
- New `_in_window`; `determine_rate_period` returns peak / super_offpeak / offpeak / flat;
  `calculate_energy_cost` reads `rates[period + "_rate"]`.
- `apply_value_function`: bounds read from the class constants; comments point to them.
- "strongly" -> "moderately".

Everything else is unchanged: comfort, practicality, noise, budget penalty, parsing, sentinel
handling, output columns and rounding.

## Tests

`python -m pytest Analysis/rerun_prep/tests/test_appliance_tariffs.py`: 101 passed against
`calc_new`. Against the shipped file (`APPLIANCE_CALC_PATH="Ground Truth Calculators/ApplianceGroundTruthCalculator.py"`),
46 fail, as expected. The tests pin:
- PECO super off-peak at hours 0-5, off-peak at 6, 7, 13, 18, 22, 23, and peak at 14-17, with the three PTC-basis rates.
- FE super off-peak at 23 and 0-5, off-peak at 6, 7, 13, 21, 22, and peak at 14-20, for all three
  utilities, with rates = PTC x multiplier.
- PPL peak at 16-19, off-peak elsewhere, no super off-peak, PTC-basis rates (0.13986/0.11987).
- Duquesne: no window, the same 0.1375 at all 24 hours, period "flat".
- The six corrected city mappings; every master location mapped; an unmapped city emits sentinel 1928.
- The recomputed bounds.

## Addendum (2026-09-25, P1-HVAC agent): continuous budget penalty

By the author's decision, `calculate_budget_penalty` in `calc_new/ApplianceGroundTruthCalculator.py`
no longer drops to 0 at u >= 1.5; the exponential 0.5 exp(-3(u - 1)) continues for every u >= 1.0
(the same change was made in the HVAC and Shower calculators). No Appliance alternative comes near
u = 1.0 (max about 0.23, recomputed 0.2292), so the output is identical to the P1-APP `calc_new` output
(`appliance/out/calc_new_final.xlsx`, 0 cell differences), the bounds are unchanged and all 101 tests
in `tests/test_appliance_tariffs.py` pass. The sentence above that lists the budget penalty as
unchanged refers to the tariff work only. The calculator file is 2 lines shorter from line 464 on;
`PROVENANCE_APPLIANCE.md` line references were shifted to match.
