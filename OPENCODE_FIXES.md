# Task brief: LLM-MCDA paper — verified corrections

You are working in the repo `LLM-MCDA Paper`. A prior review verified a set of defects
by running the actual code and data. Every claim below has already been confirmed
empirically — **do not re-litigate whether these are real; implement them.**

The paper source is `paper/paper_draft_working.tex`.

---

## HARD RULES — read before touching anything

1. **NEVER run `git commit` or `git push`.** Not once, not "to be safe". The user
   handles all commits. You may run read-only git commands.
2. **Compilation happens in Overleaf, by the user.** You may run
   `pdflatex -interaction=nonstopmode -draftmode paper/paper_draft_working.tex`
   locally **as a syntax check only**. Run it twice to resolve cross-references.
   Requirement: exit 0, zero lines matching `^! `, and zero undefined
   references/citations. The local PDF is never the source of truth.
3. **Minimal edits.** Change the smallest span that satisfies the task. Prefer
   word-level swaps over sentence rewrites. Do not reword neighbouring prose for
   flow, clarity, or consistency. Do not reorder or restructure anything.
4. **Do not touch** the Introduction, the Literature Review, or Methodology up to
   and including §2.2 (the MAVT framework design) **except** where a task below
   explicitly names a line in that range. Tasks A1, A2, A3, A5, A6, A11, A13 do name
   such lines — those are pre-approved; nothing else in that range is.
5. **Never print non-ASCII from Python** that runs in the pipeline. The Windows
   console is cp1252 and `✓`/`✗`/em-dash raise `UnicodeEncodeError`. Plain ASCII only.
6. **Sentinel value `1928`** marks a failed/invalid score. Never let it enter an
   average or a ranking. Use `sentinel_utils.has_sentinel_scores` / `is_sentinel`.
   A failed sub-calculation must surface as the sentinel, never as a neutral
   default (a `0.0` cost is a *perfect* score — that is silent corruption).
7. **Do not change** `CRITERION_WEIGHTS` (35/30/20/15), the reference ranges, the
   emissions factors, or any architecture behaviour. Nothing here should alter a
   single existing result number. Task C1 and C2 add *new* analyses; they must not
   overwrite existing outputs.
8. Report at the end: every file touched, every task completed, and anything you
   could not verify.
9. **Use subagents aggressively.** This brief holds 24 independent tasks. Fan them
   out. Part A splits cleanly by document region (weights/value functions, reference
   ranges, calculators, architectures, ablations, metrics), Part B is two isolated
   code edits, and Part C holds six analyses that share no state. Run a verification
   subagent at the end that re-reads every changed span against this brief and
   compiles. Do not work through 24 tasks in one serial pass.
10. **Prose style for anything you write into the paper.** No adverbs. No em dashes.
   Active voice with a human or named subject. No "not X, but Y" contrasts. No
   throat-clearing openers. Name the specific number or mechanism instead of a vague
   declarative. Keep calibrated hedges that carry statistical meaning ("differences
   were within the bootstrap CI"); cut hedges that only soften. Vary sentence length.
   Match the surrounding section's register.

---

# PART A — LaTeX text corrections in `paper/paper_draft_working.tex`

Line numbers are current as of this brief. **Locate by the quoted string, not by
line number**, in case of drift.

### A1. "Theorem" → "Theory" (line 392)

`The Multi-Attribute Value Theorem (MAVT)` → `The Multi-Attribute Value Theory (MAVT)`

It is Multi-Attribute Value **Theory**. One-word fix.

---

### A2. The α values are asserted, not calibrated (line 459)

Current text ends with:

> The shape parameter $\alpha = 1.5$ for comfort and $\alpha = 1.2$ for practicality
> **were calibrated so that** moderate gains (e.g., moving from the 25th to the 50th
> percentile of the criterion range) receive meaningful credit without over-rewarding
> marginal further improvements, while keeping the function close enough to linear
> that the difference in weights---rather than curvature---remains the dominant driver
> of the final MAVT score.

**Verified problem.** "Calibrated" is unsupported. In the calculators these are bare
string constants (`VF_COMFORT = "logarithmic, a=1.5"`, `VF_PRACTICALITY =
"logarithmic, a=1.2"`, e.g. `Ground Truth Calculators/HVACGroundTruthCalculator.py`
lines 53-54) with **no derivation comment** — the only unannotated constants in a file
where every other constant carries a sourced comment block. No elicitation was
performed (MAVT single-attribute value functions are normally elicited via midvalue
splitting, Keeney & Raiffa 1976 Ch. 3). `Miscellaneous Scripts/SensitivityAnalysis.py`
perturbs **weights only** — α is never varied.

**Required change.** Replace "were calibrated so that" with an explicit a-priori
assumption statement. State that the values were set a priori to introduce mild
concavity, that no elicitation was performed, and that they are not derived from
data. Keep the rest of the sentence. Then add a forward reference to the α
sensitivity result produced by task C1.

Also add one sentence to the Limitations section (`\subsubsection{Calculator
Simplifications}`) recording that the value-function curvature parameters were
assumed rather than elicited.

---

### A3. The reference-range description is false for half the table (line 463)

Current text:

> The reference ranges in Table~\ref{table:reference_ranges} are computed as the
> 5th--95th percentiles of the ground-truth quantity distributions over the scenario
> corpus (cost and emissions for HVAC and Appliance; cost and water volume for Shower)

**Verified problems — three separate falsehoods:**

1. **HVAC emissions bounds are not percentiles of anything.** They are *derived* from
   the cost percentile envelope. See `Ground Truth Calculators/HVACGroundTruthCalculator.py`
   lines 351-356: env bounds = kWh envelope × emission factors
   (`2.011 × 0.976 = 1.96`, `17.326 × 1.041 = 18.04`). This is an analytic transform
   using best/worst-case emission factors.
2. **Line 486-ish of the same .tex already describes the correct derived procedure**
   ("Using this kWh distribution with PJM marginal emissions factors ... yields HVAC
   environmental bounds") — the document contradicts itself within ~25 lines.
3. **Comfort (0.0-1.0) and Practicality (0.05-1.0) are not percentiles at all.** They
   are raw constructed score bounds. The practicality code comment says so:
   "Internal normalization choice (not a literature value)."

**Required change.** Rewrite so it says: percentiles apply to the **cost** quantities
(and Shower water volume); HVAC/Appliance environmental bounds are **derived** from
the cost/kWh envelope through the marginal emission factors; comfort and practicality
bounds are **constructed score bounds, not percentiles**. Update the caption of
`table:reference_ranges` if it asserts "5th–95th percentiles" for all rows.

---

### A4. Delete the specification-search admission (line 493)

Final sentence of the Shower environmental paragraph:

> This was done as opposed to using simple carbon dioxide because CO\textsubscript{2}
> estimates would reduce the level of seperation between the Environmental and Energy
> Cost criteria.

**Verified problem.** This states that the environmental *metric was selected because
of its correlation with another criterion*. That is specification searching and a
reviewer will read it as an admission. It is also **false** — verified within-scenario
Spearman ρ(cost, water) = **1.000 for all 80 Shower scenarios**, so the choice did not
achieve separation.

**Required change.** Delete that sentence. Replace with a justification on water's own
merits: water volume is the household-salient environmental externality of showering,
and showers are a major share of indoor residential water use (cite the already-present
`reu2016`). Note the misspelling "seperation" disappears with the sentence.

---

### A5. Entropy weighting is not independent support (line 435)

> Finally, entropy-based normalization of the scenario distributions assigns higher
> information weight to the environmental criterion, **independently supporting** an
> above-average allocation \cite{roszkowska2026}

**Verified problems.** (a) `Miscellaneous Scripts/EntropyWeights.py` lines 34-37
resolves criteria to the `*_score` columns — entropy is computed on **post-value-function**
outputs, which depend on the reference ranges, the α values, and the budget penalty
you chose. It is not independent of the design it is offered to support. (b) Entropy
weighting measures **dispersion, not preference** (Zeleny 1982; critique in Zardari et
al. 2015) — using it to support a *normative* weight is a category error. The paper's
own appendix already makes this argument about implied weights while exempting entropy.

**Required change.** Replace "independently supporting" with "is consistent with".
Add a clause noting entropy is computed on post-value-function scores and is therefore
not independent of the design, and that dispersion-based weights are descriptive
rather than normative.

---

### A6. The "30–50%" savings figure is uncited and contradicted by the repo's own rates (line 437)

> a dishwasher shifted from peak to off-peak can cut its per-cycle cost by 30--50\%

**Verified problem.** No citation, and contradicted by 4 of the 6 utilities actually
modelled. From `Ground Truth Calculators/ApplianceGroundTruthCalculator.py`
`UTILITY_RATES` (lines 34-45):

| Utility | peak | off-peak | reduction |
|---|---|---|---|
| PECO | 0.320 | 0.076 | 76% |
| PPL | 0.160 | 0.070 | 56% |
| WestPenn | 0.172 | 0.088 | 49% |
| Penelec | 0.185 | 0.093 | 50% |
| MetEd | 0.203 | 0.100 | 51% |
| Duquesne | 0.1375 | 0.1375 | **0%** |

**Required change.** Replace "30--50\%" with the realized range from the model:
**49--76% across the five time-of-use utilities modelled**. Do not add a citation —
cite the model itself implicitly by phrasing it as the realized range.

---

### A7. Peak-window count is wrong and a flat-rate utility is undisclosed (line 610)

> In the implementation, the six utilities use **distinct peak windows** (e.g., 2--6pm
> for PECO and PPL, 2--9pm for most FirstEnergy utilities).

**Verified problems.** (a) There are only **two** distinct windows in the code —
`(14,18)` and `(14,21)` — not six. (b) **Duquesne is modelled as a flat rate**
(peak_rate == offpeak_rate == 0.1375). The code comment states its PUC-approved
3--9pm TOU "exists but is not used." For every Duquesne scenario the energy-cost
criterion is **completely insensitive to run time** — the decision variable has zero
effect on 30% of the criterion weight. This is disclosed in code but not in the paper,
in a paragraph that otherwise carefully discloses the weekend and seasonal
simplifications.

**Required change.** Change "distinct peak windows" to "two distinct peak windows
(2--6pm and 2--9pm)". Add a sentence disclosing the Duquesne flat-rate simplification
and its consequence (scheduling does not affect energy cost for Duquesne-served
scenarios). **Also compute and report how many Test scenarios are Duquesne-served** —
read `Scenario Files/TestScenarios.xlsx`, map location→utility using the same mapping
the calculator uses, and state the count.

---

### A8. The temperature justification describes a mechanism that does not exist (line 666)

> Temperature 0.0 **amplifies** any single-run extraction error into the final ranking,
> whereas 0.3 introduces controlled diversity that lets cross-run recovery filter out
> transient failures.

**Verified problem.** At T=0.0 sampling is approximately deterministic, so five runs
return five identical outputs. T=0 does not *amplify* error — it **freezes** it, and
prevents averaging. "Amplifies" is the wrong verb for "prevents averaging", and a
reviewer reads it as claiming a mechanism that does not exist. The argument is also
entirely parasitic on the 5-run protocol (undisclosed), and there is **no temperature
ablation anywhere** — the Ablation Designs section covers retrieval-k, embedding model,
exemplar content, anchoring, random exemplars, NN baseline, and three prompt
perturbations, and the prompt ablation explicitly holds temperature fixed.

**Required change.** Replace with the honest mechanism: at temperature 0 the five runs
would be identical, collapsing the repeated-measures design to a single sample and
making run-to-run variance unestimable; 0.3 preserves enough sampling variation for
the five-run averaging and the reported variance to be meaningful. State explicitly
that temperature was **not ablated** and that the choice is a design constraint of the
repeated-measures protocol rather than an empirically tuned value. Add the
non-ablation to Limitations.

---

### A9. "numeric anchors" contradicts the paper and the code (line 721, and line 1122)

Line 721: `removing the **numeric** anchors that define the endpoints of the scoring scale (no\_anchors)`
Line 1122: `removing the **numeric** anchors from the scoring instructions (no\_anchors)`
Line 1157 (table note): `$\mathcal{A}_{\text{E}}$ has no no\_anchors arm because its shipped prompt contains no **numeric** anchors.`

**Verified problem.** Line 684 of the same document states the opposite about the very
same text: "The anchors are deliberately qualitative rather than numeric ... with no
numeric thresholds, units, or example values attached." The code confirms line 684 —
`Architectures/Direct_LLM_Scoring.py` lines 315-347 contain **no numerals in any anchor**.

**Required change.** Delete the word "numeric" in all three places (and anywhere else
"numeric anchors" appears). Do not otherwise alter those sentences.

---

### A10. Occupancy context is not a withheld engineering parameter (line 701)

> The LLM is asked only to estimate the genuinely withheld engineering parameters that
> are absent from the household-reported description: for HVAC, the wall R-value, SEER
> rating, HVAC age, and **occupancy context**

**Verified problem.** `occupancy_context` is neither an engineering parameter nor
withheld — it is routinely stated in the question text. The paper's own worked example
uses the scenario "I'm working from home today with 1 person", which states it.

**Required change.** Reword to distinguish the three withheld engineering parameters
from the occupancy label inferred from the question text. Check the Appliance and
Shower lists in the same sentence for the same issue and fix consistently.

---

### A11. The practicality-as-constraint example is defeated by the implementation (line 443)

> Additionally, practicality is a constraint on what is reasonable rather than a true
> user preference. ... A 15-minute shower may score near-optimally on comfort, but if
> four occupants share a 40-gallon tank, available hot water runs out before the third
> person showers---making that alternative **infeasible regardless of comfort preference**.

**Verified problem.** Two issues. (a) If practicality were a *constraint* it would
screen alternatives out; instead it enters the additive sum at w=0.15 where it is
fully compensable — the opposite of what the sentence claims. (b) The example is
quantitatively false in the implementation:
`ShowerGroundTruthCalculator.calculate_practicality_score` line 221 applies
`capacity_penalty = 3.0` on a 0-10 scale. After ÷10, the log VF (α=1.2) on range
[0.05, 1.0], and w=0.15, that penalty is worth **≈0.04 of a 1.0-scale MAVT score** —
while Cost+Environmental contribute a mean within-scenario swing of ≈0.236 for Shower.
A cheaper "infeasible" alternative can comfortably beat a feasible one.

**Required change.** Rewrite the final clause so it says practicality **penalizes**
rather than eliminates infeasible options, and delete "regardless of comfort
preference". **Verify the ≈0.04 figure yourself** by computing it from the code before
citing any number; if you include it, include the number you computed, not the one above.

---

### A12. The practicality clipping range is misdescribed (line 550)

> the practicality score is clipped to $[0.5, 10]$

**Verified problem.** `max(0.5, base_score)` is applied **before** the ΔT multiplier
and degradation (lines 221→235→242). The *final* clip is `max(0.15, min(1.0, base/10))`
(line 244). So 0.5/10 is an intermediate guard and the real output floor is **0.15 on
the 0-1 scale**.

**Required change.** Restate: an intermediate floor of 0.5 (on the 0-10 scale) is
applied before the ΔT and degradation multipliers; the final score is clipped to
[0.15, 1.0].

---

### A13. Eq. `eq:linear_vf` is printed in the wrong direction (around line 448)

```latex
\label{eq:linear_vf}
v_i(x) = \frac{x - x_{\min}}{x_{\max} - x_{\min}}
```

**Verified problem.** Table `tab:item3` applies this to Environmental and Energy Cost,
both marked "Lower raw = better". As printed, the equation returns **1.0 at maximum
cost** — inverted. The code (`apply_value_function`) uses
`(x_max - x)/(x_max - x_min)` when `decreasing=True`. The paper never writes the
decreasing form; it offloads the sign to a table column. `eq:log_vf` has the same
issue — its inner argument is the *direction-adjusted* normalized value, not the
expression printed.

**Required change.** Define a direction-adjusted normalized value once, e.g.
`\tilde{x} = (x - x_min)/(x_max - x_min)` for increasing criteria and
`\tilde{x} = (x_max - x)/(x_max - x_min)` for decreasing criteria, then express both
`eq:linear_vf` and `eq:log_vf` in terms of `\tilde{x}`. A reader implementing from the
paper as printed gets inverted cost and environmental scores.

---

### A14. Attari is named in prose but not cited (line 437)

> amplifying the underestimation bias found by **Attari et al.** and making
> cost-feedback interventions similarly effective.  \cite{reu2016,harrispoll2024}.

Neither cited key is Attari. **Required change:** add the reference —
Attari, S.Z., DeKay, M.L., Davidson, C.I., & Bruine de Bruin, W. (2010), "Public
perceptions of energy consumption and savings", *PNAS* 107(37):16054–16059 — to
`paper/cas-refs.bib` and cite it on that sentence. If you cannot add it cleanly,
remove the name instead. Also fix the stray double space before `\cite`.

---

### A15. Heater-setpoint independence holds only conditionally (line 491)

> it depends only on the rise from the mains inlet ... to that target and is
> **independent of heater setpoint**

**Verified problem.** True only for T_heater ≥ 105°F. `calculate_hot_water_fraction`
clamps the fraction with `min(1.0, ·)` (line 126), so below 105°F energy **does**
depend on setpoint. All corpus scenarios have T_heater ∈ [105, 140] so the claim holds
for this data — **but A_H extracts heater setpoint from context**, and its validation
range admits 80–160°F, so an extracted value below 105 silently changes the physics.

**Required change.** Qualify: "independent of heater setpoint for setpoints at or above
the 105°F delivery target; all corpus setpoints satisfy this." Add one sentence in the
A_H validation-bounds discussion noting that an extracted setpoint below 105°F falls
outside the regime where this holds.

---

### A16. Verify three probable citation misattributions (lines 538, 540)

You cannot read the cited standards, so **do not assert** — investigate what you can
and flag clearly in your final report.

1. Line 538: `$m$ is a housing-type envelope multiplier (1.7 single-family, 1.6
   twin/semi-detached, 1.5 townhouse/rowhouse, 1.2 apartment/condo) \cite{accamanualj}`
   — ACCA Manual J prescribes a surface-by-surface area takeoff specifically to *avoid*
   such rules of thumb; it is unlikely to define per-housing-type multipliers.
2. Line 538: `The 800\,BTU/hr baseline captures always-on standby loads per ACCA
   Manual~J \cite{accamanualj}` — Manual J has no such constant.
3. Line 540: `Effective EER is estimated from the unit's rated SEER via the
   AHRI\,210/240 quadratic \cite{ahri2008}` — AHRI 210/240 specifies **test conditions
   and rating procedures**, not this regression. The relation
   `EER = -0.02·SEER² + 1.12·SEER` traces to Wassmer (2003) and propagates through
   NREL's *Building America House Simulation Protocols*.

**Required change.** For each, either re-source the citation or relabel the values
explicitly as authors' modelling assumptions. If you cannot resolve one, leave the text
alone and list it in your report as requiring the author's decision.

---

### A17. The insulation-tier detectability claim (line ~380)

> The tier boundaries are chosen so that adjacent tiers differ by 15--20\% in wall
> R-value, matching the minimum difference a homeowner could detect by inspecting
> cavity depth.

**Verified problems.** No citation on the detectability claim. The arithmetic does not
support 15–20% under any reading: tier midpoints give 10 → 15.5 → 21.5 (+55%, +39%);
tier boundaries give 12 → 13 (+8%) and 18 → 19 (+5.5%). And the physical claim is
wrong — R-value depends on material and density, not cavity depth alone (R-13 and R-15
batts both fit a 3.5" 2×4 cavity, so cavity inspection cannot distinguish them).

**Required change.** Delete the sentence, or replace with the true midpoint deltas and
drop the detectability claim entirely. **This line is inside the protected §2.1 range —
it is pre-approved, but change nothing else in that paragraph.**

---

### A18. Two incomplete parameter lists

1. Shower comfort (around line 649 / 655): described as parameterized by "duration,
   heater setpoint, and household contention". The code also makes the optimum
   **outdoor-temperature dependent**: `optimal_duration = 7.8 × temp_multiplier`, up
   to ~10.3 min in cold weather (lines 146-152). Add outdoor temperature to the list
   and note the cold-weather shift. The code itself flags the elasticity as "a
   MODELING ASSUMPTION, not a directly reported coefficient" and the cap as a
   cross-population extrapolation — disclose both.
2. Appliance comfort (around line 606 / 612): described as parameterized by "delay,
   appliance type, housing type, and household size". The code also uses
   `run_time_hour` for the late-night (22:00–07:00) noise penalty (lines 181-193),
   which the paper lists only under practicality. Add run-time hour.

---

### A19. State up front that A_H invokes the reference calculators

In the `\subsubsection{... (LLM-Parameterized Reference Scoring)}` block (around
line 701), the text says the validated parameters are "passed to the corresponding
ground-truth calculator." A reader takes that to mean a physics model. It means the
label-generating code itself.

**Verified.** `Architectures/LLM-Parameterized_Reference_Scoring.py` lines 56-80
`importlib`-loads `HVACGroundTruthCalculator.py`, `ApplianceGroundTruthCalculator.py`,
and `ShowerGroundTruthCalculator.py` at runtime. Given true parameters, A_H reproduces
the reference ranking with tau = 1.0 by construction. The paper concedes this, but only
in the Ablation Designs subsection describing the `true_params` arm, roughly 30 lines
after the reader has formed a mental model of what A_H is.

**Required change.** Add two sentences at the end of the A_H subsubsection, before the
paragraph beginning "Because the parameters the LLM estimates are scenario-level":

- The calculators A_H invokes are the same modules that generated the reference scores,
  so A_H's ceiling is the reference itself and its error is confined to parameter
  estimation.
- A_D and A_E instead produce criterion scores end to end, so the comparison measures
  what a correct physical model plus estimated parameters buys over direct LLM
  judgment rather than pitting three interchangeable systems against each other.

Also state in the same place that A_H's LLM never parses the alternatives; the
calculator does. Point forward to the `default_params` floor arm as the control that
bounds how much of A_H's accuracy comes from the calculator alone.

Keep it to two or three sentences. Do not restructure the subsection.

### A20. Reconcile the comfort/practicality modelling justifications between code and paper

**Framing: this is an audit-and-reconcile task, not a blanket "add citations" task.**
The calculators carry substantive modelling justifications for how comfort and
practicality are constructed, and the paper reproduces some of them but not all, and in
one case cites a source the code explicitly rejects. Fix the mismatches; do not bulk-add.

#### A20a. PRIORITY — the paper cites de Dear & Brager for a method the code refuses to use

`Ground Truth Calculators/HVACGroundTruthCalculator.py` `calculate_comfort_score`
(line 161 onward) states in full:

> Tent comfort function around PMV-neutral indoor setpoints for mechanical HVAC.
> Optimal indoor 76F in cooling (outdoor > 75F) and 70F in heating: 76F is the midpoint
> of the ASHRAE 55-2020 summer comfort band (73-79F, 0.5 clo); 70F sits within the winter
> band (68-74F, 1.0 clo), ~1F below its 71F midpoint -- both for sedentary occupants.
> Score = 10 - |indoor - optimal|, clipped to [0,10]; the -1.0/F slope mirrors the rising
> PPD per F outside neutral in Fanger's PMV/PPD model. **The adaptive method (de Dear &
> Brager (2002)) applies only to naturally conditioned spaces and is not used here.**
> Sources: ASHRAE 55-2020 (Sec 5.3.1 graphic zone); Fanger (1970); van Hoof (2008).

The paper cites `dedear2002` in at least two places for comfort modelling, including the
value-function justification (~line 459): *"moving from a temperature far outside the
ASHRAE~55 band toward the neutral setpoint produces large subjective gains ...
\cite{ashrae55,dedear2002}"*.

**The code deliberately rejects the adaptive model as inapplicable to mechanically
conditioned spaces, and the paper leans on it anyway.** A reviewer who knows the thermal
comfort literature will catch this, because the naturally-ventilated-only scope of the
adaptive method is the single best-known caveat about that paper.

**Required change.** Audit every `dedear2002` citation in the manuscript. Where it is
supporting the mechanical-HVAC comfort model, replace it with `fanger1970` /
`vanhoof2008` / `ashrae55_2020`, which is what the code actually implements. Add the
code's own scope note to the paper: the PMV/PPD basis applies to mechanically conditioned
spaces, and the adaptive method is not used. If `dedear2002` is genuinely supporting
something else (a general statement about comfort as a driver), leave it.

Also check whether `ashrae55` and `ashrae55_2020` are two keys for the same standard. If
so, consolidate.

#### A20b. Reproduce the PMV/PPD derivation in the calculator subsection

The paper cites `{ashrae55_2020,vanhoof2008,fanger1970}` once, but does not reproduce the
derivation that makes the comfort function defensible: that 76F/70F are the ASHRAE band
midpoints at the stated clo levels for sedentary occupants, and that the -1.0/degree-F
slope is chosen to mirror rising PPD per degree from PMV neutrality. That derivation is
the answer to "where did this comfort function come from," and it currently lives only in
a code comment. Move it into the HVAC calculator subsection.

#### A20c. Sources present in the bib but never cited in the manuscript

Verified by counting occurrences in `paper/cas-refs.bib` versus
`paper/paper_draft_working.tex`:

| Source | in bib | cited in paper | used in code for |
|---|---|---|---|
| DeOreo et al. (2016) | yes | **0 times** | Shower practicality long-duration tail |
| Ibanez-Rueda et al. (2023) | yes | **0 times** | Shower comfort duration elasticity |
| Wong et al. (2022) | yes | **0 times** | Shower comfort temperature response |
| Bellingham Electric (2026) | yes | **0 times** | Dishwasher ~45 dBA, appliance noise penalty |
| Coolblue (2026) | yes | **0 times** | Dryer ~65 dBA, appliance noise penalty |
| de Dear & Brager | yes | **0 times** (only `dedear2002`) | Explicitly **rejected** in code, see A20a |
| Maguire et al. (2013), NREL/TP-5500-58756 | **not in bib** | 0 times | Shower inlet-temperature model |

The appliance comfort function's noise component is built on measured dBA values
(dishwasher ~45, washer ~74 spin-cycle peak, dryer ~65) with a source per appliance, and
the code notes that only the >45 dBA threshold test reads them, so washer and dryer
trigger the penalty regardless of the exact figure. The paper describes a noise
propagation factor without any of this. Add the dBA basis and the threshold logic.

Examples of code citations with no counterpart in the manuscript:

- `ShowerGroundTruthCalculator.py` line 56: the duration elasticity is flagged as a
  "MODELING ASSUMPTION, not a directly reported coefficient", supported by Wong et al.
  (2022), with the 11.6 vs 8.8 min ratio (~1.318) taken from Ibanez-Rueda et al. (2023)
  and noted as a southern-Spain sample extrapolated cross-population.
- `ShowerGroundTruthCalculator.py` lines 204-206: the long-duration practicality tail
  cites Harris Poll (2024) self-report against DeOreo et al. (2016) metered data and
  states the tail is modelled conservatively because the two disagree.
- `ApplianceGroundTruthCalculator.py` line 227: `timing_penalty` cites Paetz et al. on
  low-price zones at the brink of day being perceived as too early or too late.
- `ShowerGroundTruthCalculator.py` lines 66-72: the heater-temperature thresholds cite
  CDC (2026) Legionella guidance and explicitly note the values are comfort boundaries,
  **not** CDC setpoints.

**Required work.**

(a) **Audit.** Walk `calculate_comfort_score` and `calculate_practicality_score` in all
    three files in `Ground Truth Calculators/`, plus their class-level constant blocks.
    Build a list of every source named in a comment. For each, record whether it appears
    in `cas-refs.bib` and whether the paper cites it.

(b) **Port the missing ones** into the calculator subsections of the paper, attached to
    the specific constant or breakpoint they support. Add `maguire2013` to
    `cas-refs.bib` (NREL/TP-5500-58756).

(c) **Carry over the code's own hedges.** Where the code flags a value as a modelling
    assumption or a cross-population extrapolation, say so in the paper. The Shower
    duration elasticity and the DeOreo-versus-Harris-Poll disagreement both belong in
    the text. These hedges strengthen the paper; they are candour the code already has
    and the manuscript lacks.

(d) **Distinguish anchors from magnitudes.** State plainly which numbers are sourced and
    which are calibration choices. The band boundaries are sourced (REU2016 7.8-minute
    average, Harris Poll 15-minute threshold, CDC Legionella range, ASHRAE 55 comfort
    band). The penalty magnitudes and slopes between those boundaries are design
    choices: `capacity_penalty = 3.0`, `contention_penalty = excess_duration * 0.5`, the
    0.80 usable-tank fraction, the piecewise slopes in `base_practicality`. Do not claim
    sources for the second group. One sentence in the calculators section drawing this
    line is worth more than any rewording.

**Do not** change any constant. This task moves citations from code comments into the
manuscript and marks the boundary between sourced and assumed.

---

## Weight-specification cluster (A21-A24)

Background, all verified. The weights (Env 0.35 / Cost 0.30 / Comfort 0.20 / Prac 0.15)
were assigned from behavioural literature on standalone criterion importance. Because
the value functions normalize against **global** reference ranges (5th-95th corpus
percentiles), each `w_i` already functions as a swing weight over that global range:
swinging a criterion from global worst to global best moves the MAVT score by exactly
`w_i`. The problem is that the three-alternative choice sets do not exercise those global
ranges. Measured mean within-scenario MAVT swing (weight x within-scenario score range):

| Criterion | nominal w | HVAC | Appliance | Shower |
|---|---|---|---|---|
| Energy Cost | 0.30 | 0.027 | 0.066 | 0.108 |
| Environmental | 0.35 | 0.032 | **0.008** | 0.128 |
| Comfort | 0.20 | **0.086** | 0.098 | 0.069 |
| Practicality | 0.15 | 0.015 | 0.095 | 0.054 |

For HVAC, Comfort at w=0.20 out-swings Cost+Environmental at w=0.65 combined. For
Appliance, Environmental holds the largest weight and the smallest influence.

### A21. Present the weight vector as a configurable benchmark input

Line ~411 reads *"we chose the following weights: Environmental Impact (35\%), Energy
Cost (30\%), Comfort (20\%), and Practicality (15\%)"*. That phrasing asks the reader to
accept the vector as a normative claim the paper defends, which invites an attack the
paper does not need to absorb.

**Required change.** Reframe the vector as a stated configuration of the benchmark
harness rather than a claim about household preferences: the weights are an input, held
constant across architectures and decision types so the comparison is controlled, and
results are reported across multiple weight configurations (baseline, nine perturbations,
equal weights, and the objective vectors in the weights appendix). Keep the literature
justifications; they explain why this configuration was chosen as the default. Do not
delete them. Change what the paper *claims* about the vector, not where it came from.

### A22. Disclose that the sensitivity analysis reweights both sides

`Miscellaneous Scripts/SensitivityAnalysis.py` `rerank_with_weights` (lines 79-98)
recomputes **both** `_gt_weighted` and `_arch_weighted` with the same perturbed vector.
For A_H, whose per-criterion scores come from the same calculator modules that generated
the reference (see A19), the two vectors being recombined are near-identical, so rank
concordance is close to mechanically insensitive to the weight vector. A_H's tau holding
in [0.867, 0.928] across nine perturbations is expected by construction.

**What survives and must be stated as the actual result:** A_E > A_D under every
perturbation is a genuine weight-robust finding, because those criterion scores differ
substantively from the reference.

**Required change.** Add a short paragraph to the Sensitivity Analysis results
subsection stating that both sides are reweighted, that A_H's criterion scores originate
from the reference calculator, and that A_H's invariance therefore reflects architecture
structure rather than evidence about the weight vector. Then state the A_E vs A_D
invariance as the informative result. Do not weaken or restate any number.

### A23. REQUIRED — correct the weights appendix, which currently misreports its own table

Appendix `app:weights`, closing paragraph (~line 1443), says: *"Entropy and MEREC
therefore provide the informative objective comparisons here"* and treats both as
supporting the design. The table directly above it (`tab:weight_comparison`, lines
1421-1437) shows MEREC **contradicting** the design weights for two of three decision
types:

| | a priori | MEREC |
|---|---|---|
| HVAC Comfort | 0.200 | **0.663** |
| HVAC Environmental | 0.350 | **0.128** |
| Appliance Environmental | 0.350 | **0.044** (its smallest weight) |
| Shower (all four) | — | close to a priori |

The prose engages only the pooled MEREC figure (0.404 Comfort) and never the per-type
divergence, which reaches 0.463 against a sensitivity analysis that perturbs by ±0.05.

**This is the single most checkable defect in the paper: the contradicting numbers sit
in the table immediately above the sentence that misreports them.**

**Required change.** Rewrite the paragraph to state what the table shows. MEREC's
per-decision-type weights diverge sharply from the design weights for HVAC and Appliance
and converge for Shower, and the direction of divergence matches the realized within-
scenario swing (A24). Present this as a range-calibration finding: the criteria on which
the three alternatives actually differ are not the criteria carrying the largest nominal
weight, because nominal weights were assigned over the global reference range while each
scenario's alternatives span a fraction of it. Do not claim MEREC supports the design
weights. Do not delete the Entropy discussion.

### A24. Report realized swing alongside nominal weights

**Required change.** Add the swing table above to §2.2 (MAVT Framework and Weighting
Design), computed by the agent from `Ground Truth/ground_truth_*.xlsx` rather than copied
from this brief. For each criterion and decision type: mean over scenarios of
(weight x within-scenario score range). Present it in the same register the section now
uses for the cost/environmental collinearity disclosure. Two or three sentences, no
editorialising.

### A25. Disclose the Appliance anchor asymmetry between A_D and A_E

`Architectures/Direct_LLM_Scoring.py` lines 329-332, in A_D's system prompt:

```
- energy_cost: good during off-peak rate hours; moderate in shoulder periods;
  poor when scheduled during peak pricing windows.
- environmental: good when grid emissions are low (typically overnight);
  moderate during shoulder hours; poor when peak-period generation is dirtiest.
```

The Appliance decision **is** a scheduling decision; the three alternatives are run times.
These two lines hand the model the diurnal structure of both the TOU rate schedule and
the marginal-emissions profile, which is the mechanism the Appliance calculator encodes.
"Typically overnight" functions as a categorical answer key for the environmental
criterion on that decision type. The HVAC and Shower anchors are calibration-only by
comparison. **A_E's prompt does not contain these lines** (see A/M on the A_E prompt
description), so on Appliance specifically A_D receives domain information A_E must
recover from a single retrieved exemplar.

**Required change.** In the A_D subsubsection, state that the Appliance anchors reference
off-peak/peak rate periods and the overnight emissions minimum, that this is coarser
domain information than the HVAC and Shower anchors carry, and that A_E's prompt omits
it. Add one clause to the per-decision-type results telling the reader to read the
Appliance A_D-vs-A_E comparison with this asymmetry in mind. Revise the claim at line 684
that the anchors are stated purely "in terms of the physical situation" so it does not
overclaim for Appliance. No new runs.

### A26. Multiple comparisons on the headline result

Every ablation applies Holm correction within its family (lines ~713, ~721, ~729), but
the main architecture comparison (4 models x 3 architectures across at least four
metrics) describes paired Wilcoxon tests with no correction mentioned (~line 737). The
ablations are held to a stricter standard than the primary result.

**Required change.** Either apply Holm across the main comparison family and report the
corrected p-values, or state explicitly why it is exempt (for example a single
pre-specified primary contrast). If the p-values already exist in the per-run metrics
outputs, this needs no new runs. Report which route you took.

---

# PART B — Code fixes

### B1. Dead-code trap in `Miscellaneous Scripts/CalculateMetrics.py` (~lines 795-812)

```python
# top-2
gt_top1_val = sc["gt_rank"].astype(float).min()          # assigned, never used
gt_top2 = set(sc.loc[sc["gt_rank"].astype(float).nsmallest(2).index, "norm_alternative"])
ar_top2 = set(sc.loc[sc["arch_rank"].astype(float).nsmallest(2).index, "norm_alternative"])
if gt_top2 & ar_top2:
    top2_ok += 1
```

**Verified problem.** This tests whether the two top-2 **sets intersect**. With 3
alternatives, |A| + |B| = 4 > 3, so by pigeonhole the intersection is **never empty** —
`top2_accuracy` from this function is identically 1.0 for every scenario, every
architecture, every model, every run. It does not match the paper's stated definition
("ground-truth top alternative appears in the architecture's top two").

**Important context:** this function does **NOT** produce the paper's numbers.
`paper_pipeline/calculate_per_run_metrics.py` line 101 has the correct implementation
(`if gt_top1 in ar_top2`) and is what generated the reported results. This was
confirmed by an exhaustive repo search — there are exactly two implementations.
**So this is a latent trap, not a results bug. Do not touch
`paper_pipeline/calculate_per_run_metrics.py`.**

**Required change.** In `Miscellaneous Scripts/CalculateMetrics.py`, fix the
implementation to match the paper's definition and the pipeline's behaviour:
`if gt_top1 in ar_top2:`, reusing the `gt_top1` already computed just above for the
top-1 metric. Remove the unused `gt_top1_val`. Add a short comment recording that with
n=3 the set-intersection form is degenerate (always true), so the containment form is
required. **Verify** that `paper_pipeline/calculate_per_run_metrics.py` is untouched
and that no reported number changes.

### B2. Defensive allowlist in the A_H extraction prompt builder

`Architectures/LLM-Parameterized_Reference_Scoring.py`, `format_scenario_for_extraction`
(~lines 406-425) iterates **every non-empty key** in the scenario dict and emits
`- {key}: {value}` with no allowlist.

**Verified:** `Scenario Files/TestScenarios.xlsx` currently has 15 columns and contains
**no** engineering-truth column (no `r_value`, `gpm`, `kwh_per_cycle`), so **there is no
live leak today.** But the function would forward one if a column were ever added,
handing the LLM the exact value it is being scored on estimating — a violation of the
repo's proxy/true-pair rule.

**Required change.** Convert to an explicit allowlist of household-reported fields, and
raise (or log a loud ASCII warning) if an unexpected key appears. Confirm by running
A_H's prompt builder on a few scenarios that the emitted text is byte-identical to
before. **This must not change any existing result.**

---

# PART C — New zero-cost analyses

None of these require API calls. All reuse data already on disk.

### C1. α sensitivity sweep

`Miscellaneous Scripts/SensitivityAnalysis.py` currently perturbs weights only
(`generate_weight_scenarios`: baseline, ±0.05 per criterion, equal weights). Extend it
to sweep the value-function shape parameter **α ∈ {1.0 (linear), 1.2, 1.5, 2.0}** on the
ground-truth side, holding weights at baseline, and report whether the **architecture
ordering is invariant**.

This converts task A2 from a liability into a robustness result. Write the output to a
**new** file; do not overwrite existing sensitivity outputs. Then add the result to the
paper (Sensitivity Analysis subsection) and forward-reference it from A2.

### C2. Correct the retrieval-distance claim and measure the right quantity (line 691)

> the single closest exemplar showed a **mean cosine distance of 0.05** across all
> scenarios, confirming that every scenario in a representative draw has a closely
> matching corpus entry. Because the RAG corpus was designed for complete
> parameter-space coverage, **this holds for the full test set**

**Verified problems — three:**

1. **It is not a cosine distance.** `Miscellaneous Scripts/BuildRAG.py` line 204
   creates the collection with `metadata={"description", "source_table_sha256",
   "schema_version"}` and **no `hnsw:space` key** — so ChromaDB uses its default,
   **L2**. The ablation harness separately computes `np.linalg.norm(...)` — Euclidean.
   **No cosine is computed anywhere in the pipeline.**
2. **The vectors are not normalized.** `encode()` is called bare at `BuildRAG.py`
   lines 227, 255, 282 and `Example-Guided_LLM_Scoring.py` line 327 — no
   `normalize_embeddings=True`. So the number is not even scale-free.
3. **It measures the wrong pairing.** The 0.05 is a **RAG→RAG** leave-one-out distance.
   The claim it supports is about **Test→RAG** — the production regime, where 195 test
   scenarios query a 90-scenario index. Test queries are out-of-distribution relative
   to the index and will sit further away.

**Required change — two parts.**

(a) **Do NOT change the Chroma distance metric.** Adding `hnsw:space: cosine` or
    `normalize_embeddings=True` would change retrieval, force a `RAG_SCHEMA_VERSION`
    bump in **both** `BuildRAG.py` and `Example-Guided_LLM_Scoring.py` (they are kept
    in lockstep), and require re-running A_E entirely. Out of scope. Instead, **rename
    the metric in the paper** to what is actually computed (L2 distance between
    unnormalized all-MiniLM-L6-v2 embeddings) and report the value in those units.

(b) **Write a new script** that measures the quantity the claim actually needs:
    for all 195 Test scenarios, the nearest-neighbour distance to the 90-scenario RAG
    index, using the exact same embedding and query path as
    `Example-Guided_LLM_Scoring.py` lines 327-340. Report min / median / max and a
    per-decision-type breakdown. **Critically, also report a null:** the mean distance
    to a *random* corpus entry, in the same units. If nearest-neighbour and random are
    comparable, retrieval provides no discrimination and the coverage sentence must be
    deleted rather than rephrased. Report which outcome you find.

Then replace the sentence with the measured Test→RAG numbers and delete "Because the
RAG corpus was designed for complete parameter-space coverage, this holds for the full
test set" — that substitutes a design intention for a measurement.

### C3. Add chance baselines to the Evaluation Metrics subsection (line 739) and the Discussion (line ~1266)

**Verified problem.** With n=3 alternatives, a uniformly random ranking gives
**Top-1 = 1/3**, **Top-2 = 2/3**, **E[Kendall's τ] = 0**. None of these baselines
appears anywhere in the paper. This matters most at the Discussion line that reads
A_E's 80% Top-2 as a positive result ("the ground-truth best alternative appears in
the architecture's top two four times out of five") when chance is 66.7%.

**Required change.** Add the three chance baselines in one clause in the Evaluation
Metrics subsection. Then revise the Discussion sentence so the 80% figure is stated
relative to the 66.7% chance level. **Do not change any reported number** — only add
the baseline context. Note that A_H's 97.8% remains strong against the same baseline;
keep that contrast intact.

### C4. Soften the k=1 equivalence claim (lines 689 and ~713)

> all retrieval counts ($k=1,3,5$) produced statistically indistinguishable ranking
> accuracy, so $k=1$ was chosen ... within that **equivalence cluster**

and later: `Based on this equivalence, $k=1$ was selected ... it **matches** the
ranking accuracy of $k=3$ and $k=5$`

**Verified problem.** "Statistically indistinguishable" is a **failure to reject**, and
the paper converts it into a positive claim of equivalence. This is the
absence-of-evidence error. It is aggravated by the test design: a 7-configuration
Friedman omnibus with Holm correction across a four-metric family and gated post-hoc
Wilcoxon — every one of those choices **reduces power**, so the design is optimized not
to reject. Concluding equivalence from a deliberately conservative test is backwards.
No power analysis, minimum detectable effect, or equivalence test (TOST) is reported.

**Required change.** (a) Compute and report the **percentile bootstrap 95% CI on the
k=1 minus k=3 Kendall's τ difference** — the bootstrap machinery already exists for the
prompt ablation, and the ablation result files are on disk, so this needs no new runs.
(b) Reword both sentences: no configuration differed detectably at the power available
(give the CI), and k=1 was adopted as **the cheapest configuration not shown to be
worse** — making cost, not equivalence, the stated rationale. Drop "equivalence
cluster" and "matches".

### C5. Rebuild the imputed robustness check to catch per-run failures

`paper/supplementary_material.tex` §"Imputed Robustness Check" (~line 946) currently
says: *"an imputed alternative in which scenarios that fail in **all five runs** receive
the scale midpoint (0.5) before metric computation."*

**Problem with the current design.** Requiring failure in all five runs makes the check
far weaker than it reads. A scenario that fails in three runs and succeeds in two is
still dropped from those three runs' metrics and contributes only its two successes.
That is the exact selection effect the check exists to test, and the current rule does
not touch it. Failures are also not missing-at-random: extraction fails on the scenarios
that are hardest to parameterize, so the excluded set is systematically harder than the
retained set. The exclusion is architecture-asymmetric as well: A_D and A_E fail a
scenario if **any of three** calls trips the sentinel, A_H if **its single** call does,
so A_D and A_E lose more scenarios by construction.

**Required change.** Re-implement the imputed variant at **per-run granularity**:

- For each run independently, any scenario carrying a sentinel **in that run** receives
  the 0.5 scale midpoint for the affected criterion scores before that run's metrics are
  computed. Every run then evaluates the full 195-scenario test set.
- Keep the existing all-five-runs variant as a third column so the two imputation rules
  can be compared against Method A. Do not delete it.
- Recompute the comparison table for all four models and all three architectures.
- **Report per-cell failure counts** (scenarios imputed per run, mean across runs) in
  the table notes so the size of the correction is visible.

**Guard rails.** Impute 0.5 at the **criterion-score** level, then let the existing MAVT
aggregation and ranking run on the imputed scores. Do not impute a MAVT score or a rank
directly. Never let `1928` reach an average; use `sentinel_utils.is_sentinel` to detect.
Write to a **new** output file. Leave the main-text Method A numbers untouched.

**Then update the supplementary text.** The current conclusion is *"The A_H > A_E > A_D
ordering is unchanged ... This confirms that failure exclusion does not bias the
results."* Recheck that claim against the per-run variant and rewrite it to match what
you find. If the ordering holds, say so and give the largest metric movement. If it
does not hold under per-run imputation, that belongs in the **main text**, not the
supplementary. Flag it loudly in your report either way.

Also add one clause to the main text where the sentinel rule is defined (~line 764)
noting that failure rates differ across models and architectures, so success-conditioned
metrics are not strictly comparable across cells, with a pointer to this supplementary
section.

### C6. Report the cost/environmental score-duplication rate

**This is a new finding to add to the paper, not a correction.**

**Verified measurement.** Across run 01 for all four models, the fraction of scored
alternatives where the architecture assigned the **identical** value to `energy_cost`
and `environmental` (sentinel rows excluded):

| Model | Arch | HVAC | Shower | Appliance |
|---|---|---|---|---|
| Gemini 3.5 Flash | A_D | 77.6% | 98.3% | 13.3% |
| GPT-OSS 20B | A_D | 60.5% | 99.4% | 92.8% |
| Qwen3.5 9B | A_D | 98.6% | 100.0% | 94.9% |
| DeepSeek V4 Flash | A_D | 57.6% | 77.8% | 56.6% |
| Gemini 3.5 Flash | A_E | 98.6% | 70.6% | 21.5% |
| GPT-OSS 20B | A_E | 92.9% | 61.1% | 43.1% |
| Qwen3.5 9B | A_E | 99.0% | 92.2% | 61.5% |
| DeepSeek V4 Flash | A_E | 94.8% | 67.2% | 27.7% |

**Why it matters.** Three things connect here.

1. Both system prompts instruct the model not to assign the same score to all four
   criteria unless performance is identical. Models violate that instruction on a
   majority of alternatives.
2. The reference itself is collinear on two of the three decision types. Verified
   within-scenario Spearman correlation between raw cost and the raw environmental
   quantity is **1.000 for all 101 HVAC and all 80 Shower scenarios**, and **0.61 for
   Appliance** (exactly collinear in 22% of Appliance scenarios). So on HVAC and
   Shower, a model that duplicates its two scores matches the reference more closely,
   and the criterion-level MAE for cost and environmental are not independent
   measurements.
3. Appliance is where the two criteria separate, and it is where the models diverge
   from each other. Gemini duplicates 13.3% (A_D) and 21.5% (A_E) on Appliance against
   77.6% and 98.6% on HVAC. Qwen duplicates at 61.5% to 100% across every decision
   type. Tracking the reference's collinearity structure is a discrimination signal;
   collapsing every criterion is not.

**Required work.**

(a) Compute the full table across **all five runs and all four models**, not run 01
    alone. Report the mean and standard deviation per cell. Use exact float equality
    with a tolerance (`np.isclose`), exclude sentinel rows, and split by decision type.
    Write to a new metrics file plus a LaTeX table snippet matching the conventions of
    the existing per-run metric generators in `paper_pipeline/`.

(b) Add the table and a short passage to the **Criterion-Level Error** results
    subsection. Follow the float placement rules: put the table after the text that
    references it, keep it before the next `\FloatBarrier`, and add `\FloatBarrier`
    before any new `\subsection` you introduce.

(c) Cross-reference the collinearity disclosure already present in §2.2 rather than
    restating the correlation figures in full.

**Prose requirements for (b).** Apply rule 10 above. Specifically:

- No adverbs. No em dashes. No "not X, but Y" constructions.
- Give the numbers. Do not write "models frequently duplicated scores."
- Name the mechanism. The reference is collinear on HVAC and Shower because the
  parameters that separate the environmental quantity from cost (the occupancy-resolved
  emissions factor for HVAC, flow rate and heater setpoint for Shower) are
  scenario-level and identical across the three alternatives.
- Do not claim the models "understand" the collinearity or "learn" it. State what they
  did: duplication rates track the reference's correlation structure for Gemini and
  DeepSeek and do not for Qwen.
- Do not oversell. This is one measurement on a four-model sample. Say what it shows
  and stop.

**Do not** change any existing reported number. This adds a table and a passage.

### C7. Add MEREC per-decision-type weights as sensitivity arms

The sensitivity analysis perturbs weights by ±0.05 plus one equal-weight scenario. The
paper's own appendix reports MEREC weights differing from the design vector by up to
0.463 (HVAC Comfort 0.663 vs 0.200). **The sensitivity analysis never probes the region
the paper's own appendix says is plausible.**

**Required change.** Extend `Miscellaneous Scripts/SensitivityAnalysis.py` with three
additional arms using the MEREC per-decision-type vectors already published in
`tab:weight_comparison`, applied to their matching decision type:

- HVAC: Ene 0.138 / Env 0.128 / Com 0.663 / Pra 0.071
- Appliance: Ene 0.208 / Env 0.044 / Com 0.292 / Pra 0.456
- Shower: Ene 0.248 / Env 0.244 / Com 0.203 / Pra 0.305

Also add the Entropy per-decision-type vectors from the same table as a fourth arm set.
**Zero API calls** — this reuses existing result files and the existing reranking path.

Report whether the A_E > A_D ordering survives. That is the result that matters; A_H's
invariance is structural per A22 and should be reported with that caveat attached. Write
to a new output file. Then add the arms to the sensitivity results table and reference
them from A23.

If the ordering survives MEREC-HVAC weights, the weight-specification objection is
answered with the paper's own data. If it does not, that is a main-text finding and you
must flag it loudly in your report rather than burying it in a supplementary table.

---

# PART D — Full citation audit (run this as a dedicated subagent)

**Scope: all three files in `Ground Truth Calculators/`, in full — not just the comfort
and practicality functions.** A20 covers specific known gaps. This task is the systematic
sweep.

Every constant, threshold, coefficient, breakpoint, and modelling choice in the three
calculators either carries a source comment or does not. Build the complete map and
reconcile it against the manuscript **and** `paper/supplementary_material.tex`.

**Method.**

1. Walk each calculator top to bottom: class-level constants, every `calculate_*`
   method, every helper. Record each numeric constant or modelling decision, its source
   comment if any, and its line number.
2. For each source named in code, check whether it exists in `paper/cas-refs.bib` and
   whether it is cited in `paper_draft_working.tex` and/or `supplementary_material.tex`.
3. For each quantity described in the paper's calculator subsections, check the reverse
   direction: does the paper attribute it to a source the code does not name, or a source
   the code explicitly rejects? A20a documents one confirmed instance of the latter
   (`dedear2002`). **Look for others.** This direction is the one that damages the paper
   most, because it is a citation the author cannot defend if challenged.
4. Flag any value that carries no source in either place. Those are modelling assumptions
   and the paper should say so rather than leave provenance ambiguous.

**Deliverable.** A table with columns: file, line, quantity, value, source in code,
in bib?, cited in paper?, cited in supplementary?, verdict. Verdicts: `OK`,
`PORT` (in code, missing from paper), `ADD_BIB` (named in code, absent from bib),
`CONFLICT` (paper cites something the code rejects or does not use), `UNSOURCED`
(no provenance anywhere), `PAPER_ONLY` (paper claims a source the code never names).

Then apply the `PORT` and `ADD_BIB` fixes. **Report `CONFLICT` and `PAPER_ONLY` rows to
the author without editing them** — those need a human decision, because the fix may be
to change the model rather than the citation.

Do not change any constant.

---

# Final verification checklist

- [ ] `pdflatex ... -draftmode` run **twice**: exit 0, zero `^! ` lines, zero undefined
      refs/citations.
- [ ] No `git commit` / `git push` was run.
- [ ] `paper_pipeline/calculate_per_run_metrics.py` untouched.
- [ ] `CRITERION_WEIGHTS`, reference ranges, and emissions factors unchanged.
- [ ] No existing result number changed by any edit.
- [ ] New analyses (C1, C2, C4, C5, C6) wrote to **new** files; no existing output
      overwritten. The all-five-runs imputation column survives alongside the new
      per-run one.
- [ ] C6's table was computed over all five runs, not run 01.
- [ ] Any prose written into the paper passes rule 10 (no adverbs, no em dashes,
      active voice, specific numbers).
- [ ] Subagents were used to parallelise; a final verification pass re-read every
      changed span.
- [ ] Report every file touched, every task completed, and every item you could not
      resolve (especially A16's citation checks and C2's null-distribution outcome).
