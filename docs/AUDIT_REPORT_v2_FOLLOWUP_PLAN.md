# Follow-up Fix Plan — Group C items + k=1/k=3 labeling cluster

Companion to `docs/AUDIT_REPORT_v2.md`. That audit's Group A (mechanical, pinned-value)
fixes are already applied to `paper/paper_draft_working.tex` — see git history for that
work. This document plans the remaining items: the eight Group C judgment calls flagged
in that pass, plus a labeling inconsistency discovered while verifying one of the Group A
fixes (the "shipped k=1 vs k=3" cluster). Nothing in this document has been applied to the
paper yet. Every item below needs either a decision from the author or independent
verification before editing.

**Read `CLAUDE.md` in full before touching either paper file.** The load-bearing rule:
touch ONLY the exact span identified for each item — do not rewrite, rephrase, or "improve"
neighboring sentences, even mid-paragraph, even if already editing that paragraph for
another item on this list. If executing this plan with a subagent, that instruction must
be passed through verbatim; a prior pass in this repo was caught doing exactly this and
had to be reverted.

Two files are in scope: `paper/paper_draft_working.tex` and `paper/supplementary_material.tex`.
Line numbers below are current as of 2026-08-09 but may drift — search by the quoted text,
not the number, and if a quoted span can't be found verbatim, stop and report rather than
guessing at a paraphrase.

---

## PRIORITY ITEM — the "shipped k=1 vs k=3" inconsistency

This is not one of the original eight Group C items. It surfaced during verification of
Group A item #7 (Figure 4's "Shipped k=3" label, which was mechanically relabeled to
"Shipped k=1" because the audit found the figure's *data* correct but its *label* stale
against `Example-Guided_LLM_Scoring.py`'s current `RETRIEVE_K = 1`). That fix was correct
in isolation, but it exposed a deeper ambiguity that now needs resolving across several
more locations, and it should be resolved as one coherent decision, not four separate
find-replace edits.

### The core ambiguity

"Shipped" is used in this paper in two different senses that happen to collide:

1. **Current production setting**, used consistently in the Architecture Implementations
   section and the main results: $\mathcal{A}_{\text{E}}$'s production retrieval count is
   $k=1$ (paper/paper_draft_working.tex, Section 2.6/`sec:architectures`: *"$k=1$ was chosen
   as the production setting to minimize token and API cost..."*). This is the meaning a
   reader carries into the rest of the paper.

2. **The RAG ablation's own control condition**, which was genuinely $k=3$ at the time that
   ablation ran — confirmed in the ablation script itself:
   `Miscellaneous Scripts/run_rag_ablation_experiments.py:70-71` names this arm
   `"control_k3"` / `"Control k=3 standard"`. The ablation methods section already hedges
   this correctly: *"Seven configurations are compared against the shipped $k=3$ control
   **of the time**"* (paper/paper_draft_working.tex line 794, emphasis added) — i.e., $k=3$
   was standard when the ablation was run; the ablation's own findings are what later
   justified moving production to $k=1$.

The problem: **the same underlying data point** (Qwen, RAG-ablation control arm,
Kendall's $\tau = 0.154$) is now labeled two different ways in two places that describe the
identical number:

- Figure 4 / `\plotRagAblation` macro (already fixed this session): `Shipped $k{=}1$, 0.154`
- Discussion, line 1297: *"...exceeds its score under the shipped, curated $k=3$ exemplars
  (0.154; Supplementary Material S2)..."*
- Supplement table row (paper/supplementary_material.tex line 676/685):
  `Shipped $k{=}3$ setting (all-MiniLM-L6-v2) & 0.489 & 0.387 & 0.187 & 0.154`

A reader who looks at the figure and then reads either of the other two will see the exact
same 0.154 called "shipped k=1" in one place and "shipped k=3" in another, for what is
provably the same run. That is a real, citable inconsistency — worse than the original
audit finding, because the Group A fix (correctly, in isolation) just relocated the
mismatch rather than resolving the underlying ambiguity.

### Locations to reconcile (do not blindly find-replace — read each one)

| # | File | Location | Current text | Diagnosis |
|---|------|----------|---------------|-----------|
| 1 | main | line 794 (`sec:rag-ablation-methods`) | *"...compared against the shipped $k=3$ control of the time..."* | Likely correct as-is — "of the time" already scopes it historically. Candidate for a small wording tweak only if the chosen resolution (below) demands consistency. |
| 2 | main | line 796 (same paragraph) | *"...not shown to be worse than $k=3$ or $k=5$..."* | Comparison between ablation arms, not a "shipped" claim — almost certainly no change needed. |
| 3 | main | line 1166 (`sec:rag-ablation`, NearestNeighbor baseline description) | *"the corpus-level \texttt{NearestNeighbor} baseline... ($k=3$ majority vote..."* | **Different system entirely** — this describes the standalone NearestNeighbor baseline's own retrieval count (defined in Section~\ref{sec:res-baselines}), which is unrelated to $\mathcal{A}_{\text{E}}$'s shipped setting. Verify against the baseline's definition (Table~\ref{tab:incremental-contribution} discussion, ~line 1016) but this is very likely correct and **should not be touched**. |
| 4 | main | line 1168 | *"...its $k=1$ configuration scores below the shipped $k=3$ setting..."* and *"...$k{=}1$ minus $k{=}3$ Kendall's $\tau$ CI..."* | Same ablation-arm framing as #1 — describes the ablation's own two conditions being compared to each other. Likely correct if #1's resolution keeps "of the time"-style historical framing; otherwise needs the same edit applied. |
| 5 | main | **line 1297** | *"...exceeds its score under the shipped, curated $k=3$ exemplars (0.154; Supplementary Material S2)..."* | **This is the clearest problem.** No "of the time" hedge here — reads as a bare factual claim about what's "shipped," directly contradicting the current-production meaning used everywhere else in the paper, for the exact same 0.154 value the fixed Figure 4 now calls "Shipped k=1." **Highest-priority fix in this cluster.** |
| 6 | supplement | lines 676, 685 | `Shipped $k{=}3$ setting (all-MiniLM-L6-v2) & 0.489 & 0.387 & 0.187 & 0.154` (two rows: Kendall's τ and MAE) | Same 0.154 Qwen value as Figure 4 and line 1297. Row label needs to match whatever convention is chosen. |
| 7 | supplement | lines 680, 689 | `Random exemplars ($k=3$)` | **Different, unrelated usage** — this "$k=3$" describes how many exemplars the random-draw condition itself uses (for comparability with the control), not a "shipped" claim at all. **Do not touch.** |

### Recommended resolution (pick one, then apply consistently)

**Option A (recommended): keep "shipped" = current production (k=1) as the paper-wide
meaning, since that's how it's used in the Architecture Implementations section and
throughout the Results.** Where the RAG-ablation-methods section and Discussion need to
refer to the ablation's own k=3 control arm, replace "shipped" with neutral language that
doesn't collide with the production-setting meaning — e.g. "the ablation's $k=3$ control
arm," "the $k=3$ configuration used as this ablation's baseline," or similar. Under this
option:
- Line 794: reword "the shipped $k=3$ control of the time" → "the $k=3$ control condition"
  (the "of the time" qualifier becomes redundant once "shipped" is removed, but decide
  whether to keep it for historical clarity or drop it — judgment call, minor either way).
- Line 1168: same treatment for "the shipped $k=3$ setting" (first occurrence in that
  sentence only — the `$k{=}1$ minus $k{=}3$ CI` phrase later in the same sentence is fine,
  it's just naming the comparison arms).
- **Line 1297: this is the one that actually changes the reader's takeaway** — reword
  "the shipped, curated $k=3$ exemplars" to "the curated $k=3$ control exemplars" (or
  equivalent), removing "shipped" specifically, so it no longer contradicts Figure 4.
- Supplement row label (lines 676/685): reword "Shipped $k{=}3$ setting" → "$k{=}3$ control
  setting" (drop "Shipped" only), consistently in both rows.
- Line 1166 and the "Random exemplars (k=3)" rows: **leave untouched** — confirmed unrelated
  to this ambiguity.

**Option B (alternative, larger change, not recommended without author sign-off): revert
Figure 4's label back to "Shipped k=3"** on the theory that within the RAG-ablation
section specifically, "shipped" has always meant "the production setting at ablation-time,"
and add a footnote to Figure 4 clarifying that production later moved to k=1 based on
these results. This preserves the ablation's own internal terminology but reopens the
original Group A finding (the figure would again disagree with
`Example-Guided_LLM_Scoring.py`'s current `RETRIEVE_K=1` on its face, requiring the
footnote to carry the disambiguation weight). Not recommended — Option A achieves the same
clarity with smaller, more localized edits and no footnote dependency.

**Before editing, re-verify `Example-Guided_LLM_Scoring.py`'s current `RETRIEVE_K` value**
and the ablation script's control-arm naming, in case either has changed since this plan
was written (2026-08-09/10).

---

## Group C items (from `docs/AUDIT_REPORT_v2.md`)

### 1. Supplement `tab:failure_modes` table not regenerated (Tier 1 #1)

**File:** `paper/supplementary_material.tex`, `tab:failure_modes` (~lines 293–308).
**Problem:** Main-text Table 12 (`tab:failure_arch_model`, paper_draft_working.tex) was
already corrected to report unique scenario-run failures: 9 ($\mathcal{A}_{\text{D}}$) / 20
($\mathcal{A}_{\text{E}}$) / 120 ($\mathcal{A}_{\text{H}}$). The supplement table was never
regenerated to match — it still reports an "alternatives basis" count (27/60, i.e. 3× the
scenario-run count, since $\mathcal{A}_{\text{D}}$/$\mathcal{A}_{\text{E}}$ score one
alternative per call). Its footnote also claims only two failure codes ever fired across the
whole benchmark, which is contradicted by one `FAILED_MISSING_SCORE` occurrence (Qwen,
$\mathcal{A}_{\text{D}}$, run 3) — confirmed against `paper/failure_analysis.csv` and the
per-run xlsx files by the original audit.

**Recommended fix:** Regenerate the supplement table on the same scenario-run basis as
the main text (9/20/120), for consistency — having the "same" quantity reported on two
different, unlabeled bases across two documents is confusing and is exactly what
triggered this finding. Correct the footnote to note the third failure code
(`FAILED_MISSING_SCORE`) that fired once.

**Before editing:** re-derive the exact corrected table contents from
`paper/failure_analysis.csv` and the per-run xlsx files (same source the main-text Table 12
fix used) — do not guess at cell values. Cross-check against the note in
`docs/AUDIT_REPORT_v2.md`'s "What the fixer subagent (V05b) applied" section, item 2:
*"F2 mode table in the same file (5+1/21/120 per-run-dedupe) — internally inconsistent with
F1 denominators (6 vs 9, 21 vs 20); a units issue, flagged."* — this suggests there may be
**two** internally-inconsistent tables/footnotes in the supplement stemming from the same
regeneration gap, not just one. Check both before editing either.

---

### 2. "Endpoints reported to three decimals" claim vs. actual table precision (Tier 1 #6)

**File:** `paper/paper_draft_working.tex`, line 494 (end of the paragraph introducing
`table:reference_ranges`).
**Current text:** *"...Using dataset percentiles rather than the full theoretical physics
envelope is a choice \cite{roszkowska2026} which comes the cost of truncating scores for
extreme outlier scenarios. **The endpoints below are reported to three decimals.**"*
**Problem:** Table~\ref{table:reference_ranges} cells are mostly 2 decimal places
(e.g. `0.38--3.29`, `1.96--18.04`), not 3.

**Two legitimate options — pick one:**
- (a) Soften the prose: remove "to three decimals" or change to "to two or three decimals"
  (some cells, e.g. Appliance's `0.025--0.71`, do carry 3 decimals — check the whole table
  before wording this, since "two or three" may itself be imprecise if the actual pattern
  is decimal-place-varies-by-magnitude rather than a clean two-vs-three split).
- (b) Reformat the table to consistently show three decimals throughout.

**Recommendation:** (a) — reformatting risks a much larger diff across a data table for a
cosmetic claim, and doesn't change any reported value; softening the prose is the smaller,
safer, and sufficient fix. Whichever is chosen, this is a single-sentence or single-word
edit — do not touch the rest of the paragraph.

**Note found while locating this item:** the same line carries a leftover author comment
immediately after the flagged sentence: `%explain somewhere why practicality is 0.05 (its
just about nothing being truly impossible find some source to back that up)`. This is not
part of the original audit and not one of the eight Group C items, but it's a live,
unresolved TODO-style note sitting in the same line and should be flagged to the author
separately — it is out of scope for this plan's items and should not be touched while
executing item 2 above.

---

### 3. Orphaned "Chicago" worked example in Supplementary Material S1 (Tier 1 #8)

**File:** `paper/supplementary_material.tex`, lines ~160–186 (§"Retrieved Exemplar
Rendering," inside the prompt-template documentation for $\mathcal{A}_{\text{E}}$).
**Current text:** shows a rendered RAG exemplar with `Location: Chicago`, a set of HVAC
parameters, and expert scores (`76°F: Energy Cost 0.4, Environmental 0.3, Comfort 0.9,
Practicality 0.8 | MAVT: 0.58, Rank: 2`). The original audit found no Chicago scenario in
any current Test/RAG sheet and no matching scores in any Gemini run file — it appears to be
a relic of an older, since-replaced scenario draft.

**Context worth weighing:** this block sits directly below a genuinely generic JSON-schema
template (lines 150–159, using placeholder `<number>` tokens) in a section that documents
*prompt format*, not corpus content — so it's plausible this was always intended as an
illustrative example rather than a literal corpus entry, similar to the schema block above
it. That said, the paper repeatedly and explicitly claims elsewhere (Limitations, Scope
Boundaries) that *"every scenario sits in one of 48 Pennsylvania municipalities"* — so even
as an illustrative example, a non-Pennsylvania "Chicago" location contradicts that claim on
its face for a careful reader, and should be corrected either way.

**Options:**
- (a) Replace `Chicago` with a real Pennsylvania location and pull matching real
  parameters/scores from an actual current RAG scenario (requires picking a specific real
  scenario and tracing its true stored scores from a current run/RAG file — this is
  drafting work, not a one-line fix).
- (b) Keep it illustrative but swap only the location field to a generic/consistent
  Pennsylvania placeholder (e.g. "Philadelphia" or similar) without re-deriving real scores,
  explicitly noting in prose (if not already implied by context) that the values shown are
  illustrative rather than sourced from a specific corpus row.
- (c) Delete the worked example entirely if it's not load-bearing for understanding the
  prompt format (the JSON schema block above it may already suffice).

**Recommendation:** (a) if the author wants full accuracy and has ~15–20 minutes to spend
picking a real scenario; (b) as the faster, still-correct fix if illustrative framing was
always the intent. Either way this needs the author's call before a subagent drafts
specific replacement content — do not have a subagent invent a "real-looking" example
without pulling it from an actual current scenario file, since that would just create a new
version of the same problem.

---

### 4. Spearman ρ = 0.92 missing scenario-pool scope (Tier 3 #1)

**File:** `paper/paper_draft_working.tex`, line 425.
**Current text:** *"In our dataset the energy cost and environmental impact criteria are
not statistically independent: Spearman's $\rho$ between them is 0.92."* ... *"the additive
form remains admissible at $\rho = 0.92$."*
**Problem:** No stated scope for which scenario pool this is computed over. Independent
recomputation (per the original audit) gives 195-scenario Test pool → 0.9248 (rounds to
0.92) and 285-scenario full corpus (Test+RAG) → 0.9126 (rounds to 0.91). The printed 0.92
matches the 195-pool figure, but the text doesn't say so, leaving room for a careful reader
to recompute on the 285-pool and get a different rounded value.

**Recommended fix:** Add a brief scope clause naming the 195-scenario Test pool at first
mention (e.g. "...between them across the 195 test scenarios is 0.92"), touching only that
first clause — the paper uses $\rho = 0.92$ two more times in the same paragraph
("A household willing to accept... at 20°F would accept the same trade at 90°F, so the
additive form remains admissible at $\rho = 0.92$") which do not need the scope clause
repeated, only the first introduction of the number needs it.

**Before editing:** independently re-run the Spearman correlation on both pools to confirm
the audit's 0.9248/0.9126 figures still hold against the current data files (energy_cost
and environmental columns, HVAC+Appliance+Shower combined) — quick to verify, don't skip it
just because the audit already did this once.

---

### 5. "Disagreement roughly half" / "~14pp bound" — Gemini exception (Tier 3 #2)

**File:** `paper/paper_draft_working.tex`, line 823 (Alternative Ordering results
discussion).
**Current text:** *"...$\mathcal{A}_{\text{D}}$'s shipped runs disagree with each other on
top-1 for roughly half of scenarios, so this bounds the effect at about 14 percentage
points rather than excluding it."*
**Problem:** No locatable derivation for either "roughly half" or "~14 percentage points."
Per the original audit, Gemini's own inter-run agreement is 0.7477 (≈25% disagreement),
which does not fit "roughly half" — so the claim doesn't hold uniformly across all four
models even before considering whether "14pp" has any real derivation.

**Options:**
- (a) Call out Gemini as an explicit exception to the "roughly half" pattern.
- (b) Replace "roughly half" with a range that actually covers all four models' true
  disagreement rates (e.g. "~25% to ~50%" — exact wording depends on pulling the actual
  per-model figures).
- (c) Re-derive the missing "~14 percentage point" bound's actual source/logic before
  touching the sentence at all, in case it has a real basis not yet located.

**Recommendation:** (b), pending the actual per-model disagreement numbers. The
McNemar statistics this sentence's own text says are "in Supplementary Material S2" are
the right first place to pull those exact per-model rates from — check that file/table
before drafting new wording, since the corrected sentence should be built from real
per-model numbers, not another approximation.

---

### 6. "Combinatorial-coverage audit" overstated in main text (Tier 3 #3)

**File:** `paper/paper_draft_working.tex`, line 301.
**Current text:** *"...with coverage of every categorical combination ensured by a
combinatorial audit (detailed in Supplementary Material S1)."*
**Problem:** Read literally, "every categorical combination" implies full combinatorial
coverage (380 possible combinations per the audit vs. only 70 HVAC scenarios — arithmetically
impossible for HVAC alone).

**Important finding while planning this item:** `paper/supplementary_material.tex` lines
199–205 already describe what the audit *actually* checks, and it's a materially weaker
(and achievable) claim: *"A combinatorial audit ensured that no parameter combination was
underrepresented: each categorical **cross-cell** (insulation tier × housing type,
appliance type × flow-rate band, etc.) contained at least one scenario..."* — i.e., the
audit checks 2-way marginal cross-cell coverage, not full combinatorial coverage of every
possible joint combination. **The supplement text is accurate as-is and does not need
editing.** Only the main text's shorthand ("coverage of every categorical combination") is
the overstatement — it's summarizing S1 imprecisely, not describing a different, broken
audit.

**Recommended fix:** Reword the main-text clause to match what S1 actually says — e.g.
"...with every categorical cross-cell (not every full combination) covered by a
combinatorial audit..." or similar — a same-sentence wording correction, not a rewrite of
the audit methodology itself (which is fine as documented in S1).

---

### 7. Unverified "$0.20 / 1.4 lbs / 3 gallons" derivation (Tier 3 #4)

**File:** `paper/paper_draft_working.tex`, line 1288 (`sec:interpretation`, Discussion).
**Current text:** *"...in absolute terms, $\mathcal{A}_{\text{H}}$'s residual error is
roughly \$0.20 per scenario for energy cost, and about 1.4 lbs CO$_2$ (HVAC/Appliance) or
3 gallons of water (Shower), using the reference ranges in Table~\ref{table:reference_ranges}..."*
**Problem:** Per the original audit, the derivation behind these three specific numbers
isn't persisted anywhere findable in the repo — not proven wrong, just unconfirmed from
artifacts.

**Options:**
- (a) Re-derive and verify: these figures should be reconstructible from
  $\mathcal{A}_{\text{H}}$'s MAE-on-the-0–1-scale figures (Figure~\ref{fig:mae_criterion} /
  Table in Supplementary Material S2) multiplied back out against the reference ranges in
  `table:reference_ranges` (e.g. MAE fraction × range width). This is a bounded, mechanical
  re-derivation, not open-ended research — a good candidate for a focused subagent pass with
  access to the MAE-by-criterion data and the reference-range table.
- (b) Leave as-is with the understanding the figures are plausible but currently unconfirmed.

**Recommendation:** (a) if time permits — these are exactly the kind of concrete, quotable,
checkable numbers a reviewer is likely to spot-check, so verifying (or correcting) them
before submission is worth the bounded effort. If not prioritized now, (b) is an acceptable
interim state, but should not be treated as resolved.

---

### 8. "56-test family" cites the wrong artifact (Tier 3 #5)

**File:** `paper/paper_draft_working.tex`, line 840 (`sec:eval-metrics`, end of section).
**Current text:** *"The paired Wilcoxon tests on the main architecture comparison are
Holm-corrected across a single 56-test family (full test-family enumeration in
Supplementary Material S2): 55 of the 56 tests remain significant at the 0.05 level, the
sole exception being the DeepSeek $\mathcal{A}_{\text{D}}$-versus-$\mathcal{A}_{\text{E}}$
RMSE/MAE-ratio comparison ($p_{\mathrm{Holm}} = 0.093$)."*
**Problem:** Per the original audit, this passage's printed numbers are consistent with
`paper/per_model_pvalues.csv` (confirmed to exist, 24 rows), not with the 56-test family,
which actually lives in `paper/per_run_metrics/significance_tests.xlsx` (confirmed to
exist). The text describes a 56-test family but the numbers it prints come from the 24-row
file.

**Two genuinely different fixes depending on which is actually wrong:**
- (a) The description is wrong: this passage should say "24-test family" (or however many
  rows `per_model_pvalues.csv` actually represents after independent recount), keeping the
  currently-printed numbers and citation as-is.
- (b) The citation is wrong: this passage should cite/use `significance_tests.xlsx`'s
  56-test family instead, which would require replacing "55 of the 56... 0.093" with
  whatever the actual 56-test-family results are — a larger change touching every number in
  the sentence, not just the family-size count.

**Recommendation:** (a) — matching the description to the citation and the already-printed
numbers is a much smaller, lower-risk change than re-sourcing the whole sentence from a
different file. But **before editing, open both `paper/per_model_pvalues.csv` and
`paper/per_run_metrics/significance_tests.xlsx` and count rows / read structure directly** —
confirm which file the printed "55 of the 56... 0.093" figures actually trace to, since the
original audit's characterization should be independently re-checked before committing to
option (a) over (b). If the 24-row file turns out to itself be a subset/aggregation of the
56-row file rather than a wholly separate computation, the right fix might be neither (a)
nor (b) as stated but a citation to both with a clarifying clause — don't assume until the
files are actually opened.

---

## Summary checklist for the executing agent

- [ ] Re-verify `RETRIEVE_K` in `Example-Guided_LLM_Scoring.py` and the RAG ablation
      control-arm naming before touching the k=1/k=3 cluster.
- [ ] Resolve the k=1/k=3 cluster (7 locations across 2 files) as one coherent decision —
      recommended: Option A (de-scope "shipped" to mean current production only).
- [ ] Item 1: regenerate supplement `tab:failure_modes` — check for a *second* related
      inconsistent table/footnote (the "F2 mode table" noted in the audit) before
      considering this done.
- [ ] Item 2: soften "reported to three decimals" (recommend option a) — do not touch the
      adjacent leftover author comment about the 0.05 practicality floor; flag that
      separately.
- [ ] Item 3: get author decision on Chicago example (replace vs. illustrative-relabel vs.
      delete) before drafting any replacement content.
- [ ] Item 4: independently re-verify the 0.92/0.91 Spearman figures on both pools, then
      add the 195-pool scope clause at first mention only.
- [ ] Item 5: pull real per-model disagreement rates from Supplementary Material S2's
      McNemar table before rewording "roughly half"/"~14pp".
- [ ] Item 6: reword main-text line 301 only — S1's own description (lines 199–205) is
      already correct and needs no change.
- [ ] Item 7: attempt re-derivation of $0.20/1.4 lbs/3 gallons from MAE × reference-range
      data; fall back to leaving as-is (with a note, not silently) if not tractable.
- [ ] Item 8: open both `per_model_pvalues.csv` and `significance_tests.xlsx` directly and
      confirm which is the true source before choosing between "24-test family" and
      re-sourcing from the 56-test file.

Every edit above must be applied as its own isolated, minimal change per CLAUDE.md's
minimal-diff rule — do not batch multiple items into one Edit call if they land in the same
paragraph, and do not touch any sentence not explicitly named above.
