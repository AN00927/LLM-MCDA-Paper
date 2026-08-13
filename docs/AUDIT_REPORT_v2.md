# Numerical-Provenance Audit — Consolidated Report v2 (final)

Audit of `paper/paper_draft_working.tex` + `paper/supplementary_material.tex`, current state 2026-08-09.
287 indexed claim-rows; verified by 10 parallel subagents (briefs 00-08 v2). All values read from repo
artifacts or independently recomputed by me from raw files — nothing invented.
Verifier idents: V00 front/figs, V01 corpus/MAVT, V02 calculators, V03 ablations/metrics, V04 results
3.1-3.4, V05a provenance/by-type, V05b sensitivity/efficiency/failures/ordering, V06 discussion,
V07 supplement S1, V08 supplement S2.

## TIER 1 — mismatches that change/undermine a claim

| # | Location | Claim | Source artifact | Value found | Verdict / correct value |
|---|----------|-------|-----------------|-------------|-------------------------|
| 1 | supp tab:failure_modes (~293-308) | A_D 27 / A_E 60 failures; footnote "only these two codes ever fired" | paper/failure_analysis.csv + per-run xlsx + diagnostics | A_D = 5 INVALID_JSON + 1 FAILED_MISSING_SCORE; A_E = 21; FAILED_MISSING_SCORE did fire (Qwen A_D run 3) | MISMATCH — supplement table never regenerated with the 05b fix: main-text Table 12 now correct (9/20/120 unique scenario-runs) but supplement still prints 3x (alternatives basis 27/60) alongside scenario-basis 120; footnote contradicted by FAILED_MISSING_SCORE=1 |
| 2 | main ~line 936 | "no cell moves by more than 6.5 points" (single-criterion 285 recovery) | paper/dispersion_diagnostics.csv | Appliance environmental moves 55.0-46.2 = 8.8 | MISMATCH — bound false; 8.8 > 6.5 |
| 3 | main ~952 | "Qwen A_H Appliance env MAE 0.294 worse than two of the four A_D" | per_run_metrics_*.csv | A_D Appliance env: 0.368/0.381/0.380/0.373 — all > 0.294 | MISMATCH — beats all four; only true vs A_D *overall* env |
| 4 | main ~903/927 | pooling "moves neither baseline by >0.004" | baseline_metrics.csv | NN: top1 +0.0083, tau +0.0154 | MISMATCH — NN violates; FixedDefault passes |
| 5 | main ~952 | A_D env spread "0.265-0.292" | per_run_metrics_*.csv | Gemini 0.248 omitted | MISMATCH — true 0.248-0.292 |
| 6 | main ~504 | "endpoints to three decimals" | table cells | mostly 2 dp | MISMATCH — mixed precision |
| 7 | fig 4 label | "Shipped k=3" | Example-Guided_LLM_Scoring.py:97 | RETRIEVE_K=1 | MISMATCH (label) — data OK, label wrong |
| 8 | S1 worked example | "Chicago" / gym-bag; scores 0.75/0.75/0.60/0.80 | all Test/RAG sheets; all Gemini run files | no Chicago scenario exists (all PA); scores in no run file | NO-SOURCE — relic of older corpus |

## TIER 2 — rounding / boundary (9)

1. DeepSeek k1-vs-k3 CI upper: artifact -0.160462. Main ~1070 fixed to -0.160; main ~661 still **-0.161** — fix applied only once.
2. main ~1157 IQR: [0.157,0.167] → now [0.157,0.166] (fixed, verified V08 claim 10).
3. V04: Qwen A_D Top-1 0.301 vs 0.3005; AE-best -0.150/-0.272 vs -0.1502/-0.2725.
4. S1 worked example MAVT: 0.352/0.441 vs code 0.353/0.442 (0.001).
5. S2 Wilcoxon "21 <= 1.1e-4": largest remaining p = Qwen AD-vs-AE tau 1.108e-4 — 0.8% above the printed bound (rounding edge).
6. S2 prompt-ablation: 4 of 56 cells (AD ctrl DS tau 0.129, AD ctrl GPT 0.053, AD no_anchors GPT 0.100, AD ctrl Qwen top1 0.289) match pooled aggregation (0.1291/0.0527/0.0995/0.2885), not the summary sheet's run-mean (0.1310/0.0518/0.0993/0.2879); caption says "mean over runs" — ≤0.002 deviation.
7. main ~632 contention "above four occupants": code fires at >=4.
8. main ~441 "101/105 rho=1.000": holds on raw columns only (stored scores: 94/105).
9. main worked example "72F exceeds $200": 76/80F also exceed.

## TIER 3 — no locatable source / base ambiguity / stale artifacts

| # | Location | Claim | Status |
|---|----------|-------|--------|
| 1 | main ~435 | Spearman rho = 0.92 | NO-SOURCE (printed-only); my recompute: 195-pool 0.9248→0.92, 285-pool 0.9126→0.91. Persist + state scope |
| 2 | main ~735 | "disagreement roughly half" + "~14 pp" bound | Gemini exception (agreement 0.7477, ~25%); "14 pp" has no derivation — NO-SOURCE |
| 3 | S1 | combinatorial-coverage audit | impossible: 380 combos vs 70 HVAC scenarios; audit has no coverage check |
| 4 | main §4 | "MAE roughly $0.20 / 1.4 lbs / 3 gallons" | derivation unpersisted — unverified |
| 5 | main §2.7 | "56-test family" cited to per_model_pvalues.csv | wrong artifact: CSV has 24 rows; 56-family in significance_tests.xlsx; CSV vs xlsx p_holm drift ≤1.7e-4 (two implementations); text quotes 24-family values — consistent with per_model_pvalues.csv (V08 F2) |
| 6 | Analysis/MetricsSummary/metrics_summary_all_models.xlsx | stale workbook | pre-batch GPT-OSS A_H (n=194, tau 0.9072) vs current (n~171.6, tau 0.897); do not cite |
| 7 | duplication reference 51.1/15.4/8.0 | base never stated | VERIFIED by my recompute: exact on 285-corpus (51.11/15.42/8.00); test-only = 46.0/16.9/9.1. Earlier verifier numbers (46.7/17.2/9.2 and 54.3/7.7/17.2) were both wrong |
| 8 | main ~1274-1278 | DeepSeek agreement 0.42/0.64/0.67 | RESOLVED: hybrid_order_reversal.xlsx — shipped 0.4230, control 0.639, reversed 0.67026 (V08 F4). The "0.616" in the original brief was a misquote (it is a MEREC-pooled tau cell); paper is correct |
| 9 | main fig/RAG | NN k1-vs-k3 CI [-0.172, 0.175] | RESOLVED: k1_vs_k3_bootstrap_ci.xlsx = [-0.1724744, 0.1752806] → [-0.172, 0.175]; current text correct, the old -0.173 draft was wrong (V08 F3) |
| 10 | S2 | energy estimate (0.24/0.31 Wh, 445 g/kWh, 13/17 kg) | EXTERNAL + arithmetic VERIFIED (V08 claim 27): 0.24→30.27 kWh→13.47 kg "13"; 0.31→17.40 "17"; IQR→8.98/33.67 "9.0/34"; "20-76 kWh" OK; citations present |
| 11 | main fig 5 / S2 | ICC(2,1) → caption now ICC(1,1) | RESOLVED: significance_testing.py:469-486 implements ICC(1,1); caption matches (V08 F1) |
| 12 | S2 | "0.03%" failure rate (2/7,560) | VERIFIED: 2/7560 = 0.0265% → rounds to 0.03%; the 2 failures identified (deepseek random_exemplars_k3 hvac_29; exemplars_no_hidden_params appliance_13) |

## What the fixer subagent (V05b) applied — verified status

1. failure_analysis_tables.tex F1 (9/20/120 unique scenario-runs) — CORRECT; my independent recount from per-run xlsx: AD DS 7 + Q 2, AE G 20, AH DS 1 + GO 117 + Q 2. ✓
2. F2 mode table in the same file (5+1/21/120 per-run-dedupe) — internally inconsistent with F1 denominators (6 vs 9, 21 vs 20); a units issue, flagged.
3. Main §3.10 "0.886/90.8%" sentence — replaced with "both give 0.897/91.6%"; supported (only GPT-OSS A_H 1 scenario failed all 5 runs).
4. CI/IQR fixes — partially applied: -0.160 at ~1070 ✓, -0.161 remains at ~661 ✗; IQR [0.157,0.166] ✓; NN CI [-0.172,0.175] ✓.
5. Supplement tab:failure_modes — NOT regenerated (Tier 1 #1).

## Coverage / residuals

- V08: 30/30 S2 claims MATCH (incl. sensitivity 84+84 cells, RAG 28+28, bootstrap 36 CI cells, imputed 24 cells, footprint, duplication 48 cells); F1-F6 resolved; F7 = the one supplement MISMATCH. No S2 NO-SOURCE rows.
- EXTERNAL claims (V00 rows 56-61; V02 rows): bib keys exist; internal conversions recompute correctly; not verified against external literature itself.
- Sentinel 1928 discipline: clean everywhere checked.
- Remaining unverified: main §4 derivation claims (Tier 3 #4); external literature values.