# Cloud agent context (temporary; written 2026-09-27)

**New session? Read the section "State at the end of the second cloud session" below first**; `paper/pass6/NEXT_SESSION_HANDOFF.md` sections 2-4 are done.

Read this first, then `CLAUDE.md`, then `paper/pass6/PASS6_HANDOFF.md` and
`paper/pass6/RERUN_RUNBOOK.md`. This file carries the standing rules and decisions that live in
the author's local agent memory, which a cloned repo does not have.

## Standing rules (author's, all binding)

- **Never commit or push unless the author says so in the conversation**, and then only to the
  `cloud-work` branch (see the last section). Otherwise leave changes in the working tree and list
  the files. Read-only git is fine.
- **No paid API call without the author's explicit go-ahead in the conversation**, including smoke
  tests. Show the cost estimate first. Tests mock HTTP.
- **Never pool across models.** Every number is per model (gptoss, qwen, deepseek, gemini). No
  four-model means, not even "for brevity". A cross-model claim is stated as "holds in all N cells"
  with the worst-case margin. Watch for pooling hidden as `aggfunc='first'` data discard.
- **Fix, don't disclose.** For any error or gap, propose the code fix or rerun (with cost) first.
  A limitation sentence is only the fallback if the author declines.
- **Minimal-diff paper edits** (see CLAUDE.md), and run the `stop-slop` skill before writing any
  paper or supplement prose. If the skill is not available, apply its rules by hand: no filler,
  no em-dashes, no false agency, calibrated hedging, third person in Results.
- **Study design is intentional:** A_D/A_E are not given the value model; that is not a limitation.
  Baselines stay simple medians/modes (no question-template parsers). Token counts and costs beyond
  the paper's cost table go in repo docs, not the paper.
- **Provenance:** any change to a calculator or baseline constant updates its provenance entry
  (value, code location, citation + URL + page/table, verbatim quote, status sourced/derived/
  assumption). The merged record is `docs/CALCULATOR_PROVENANCE.md`.
- The active manuscript is `paper/paper_draft_v2.tex` with `paper/supplementary.tex`. Architecture
  names match the Python files: direct LLM scoring (A_D), example-guided LLM scoring (A_E),
  LLM-parameterized reference scoring (A_H). Never "hybrid reference scoring". Target journal:
  Environmental Modelling & Software.
- Use subagents for heavy work; cheaper models with precise prompts for mechanical tasks.
- Windows paths in older docs refer to the author's machine; in the cloud use repo-relative paths.

## Rerun decisions (fixed; do not reopen)

- Full fresh rerun of every experiment in one window, with UTC timestamps and raw logs.
- Models (`model_config.py`, author's file, do not edit without approval): gpt-oss-20b, Qwen3.5 9B,
  DeepSeek V4 Flash 0731, Gemini 3.8 Flash, each with `:floor` and a provider pin
  `{"only": [...], "allow_fallbacks": False, "require_parameters": True}`: gptoss `darkbloom/fp8`,
  qwen `venice/fp8`, deepseek `baseten/fp8`, gemini `google-ai-studio/flex`. No streaming. Gemini
  reasoning effort `low`. `MODEL_KEY` comes from the environment variable.
- Benchmark A_E uses k=1; the rerun RAG ablation is the evidence. No k=3 or listwise extra arms.
- Prompt ablation: uniform 5 runs per cell for every model.
- RAG ablation: a failed or unscored scenario counts as wrong for Top-1 (denominator = all
  scenarios). Nearest-neighbour baseline fallback stays `tie`.
- HVAC: heat-pump HSPF paired with SEER, one net-heat-balance mode rule, heating optimum 71 F,
  occupant gain 220 Btu/h sensible, solar gain out of heat mode, Stroudsburg hvac_age 95 -> 40.
  Appliance: tariff-faithful (super off-peak, corrected PPL, city fixes, one rate period). Every
  scenario is a weekday. Prompts unchanged.
- Scenario fixes: `paper/pass6/verify/scenario_fixes.json` (keep all, including #82/#83), applied
  with `apply_scenario_fixes.py`; rebuild with `Scenario Files/build_scenario_workbooks.py`
  (the old `build_consolidated_scenario_workbooks.py` cannot run: its source workbook is gone).
- Old GPT-OSS and Qwen outputs must never be overwritten: move the CONTENTS of
  `Output Files GPT-OSS 20B/` and `Output Files Qwen3.5 9B/` (including `position_bias/` and
  `hybrid_order_reversal/`) to `archive/2026-09_pre_rerun/<folder name>/`, verify every file
  arrived, and keep the emptied folders as the new output folders. Archive old
  `Analysis/Prompt_Ablation/` cells the same way; RAG-ablation `checkpoints/` must be empty.
- Paper edits from the stopped S1 agent are kept (partial, no log). To see what it changed, diff
  the current files against the pre-S1 copies in `paper/pass6/s1_snapshot/` (paper_draft_v2.tex,
  supplementary.tex, cas-refs.bib, README.md, taken 2026-09-26 before S1 started). All four
  differ from the current files. Some of that difference may be edits the author made later.

## State at the end of the second cloud session (2026-09-27, later)

Everything from `NEXT_SESSION_HANDOFF.md` sections 2-4 is done and pushed to `cloud-work`:
- Value review of every provenance row: `paper/pass6/verify/VALUE_REVIEW.md` (+ `value_review/`).
  The author approved A1-A8 and they are installed (commit 95d7fce): HVAC solar gain from IECC
  R405 SHGC/IAC and Harrisburg TMY3 24-h irradiance (7.85 / 11.19 Btu/h per ft2 glass), attached
  glazing factor F (0.75 / 0.56), IECC internal gains, HSP Eq. 20 degradation (M = 0.02); Shower
  inlet 48.5 / 68.2 F and 0.69 showers/day; fixed default tank 40 gal and dryer 2.27 kWh.
  Bounds: HVAC $0.40-$2.81, 2.05-15.40 lbs; Shower $0.13-$1.07. GT, RAG scores, both baselines,
  `baseline_metrics.csv`, the Chroma index, entropy/MEREC weights refreshed; 388 tests pass
  under all four MODEL_KEYs; pipeline gate differences are only the caused score changes.
- `docs/CALCULATOR_PROVENANCE.md` updated (open items 1-10 closed; item 11 lists what stays
  unverified). `tests/audit_scenarios.py` deleted; `tests/test_appliance_validation.py` added.
- Paper: S1 done (`S1_APPLY_LOG.md`), S-CALC done (`SCALC_APPLY_LOG.md`), ground-truth-derived
  stale text fixed (`STALE_FIX_LOG.md`). No local LaTeX: the author compiles in Overleaf.
- Network: all *.nrel.gov hosts and codes.iccsafe.org stay blocked; mirrors were used.

Update, 2026-09-27 (end of session):
- B10, B11 and B63 were applied as option (a), and B77 was approved and applied.
- The Phase R smoke test (runbook step 1, with the author's go-ahead) passed: 112 of 112 calls
  succeeded for $0.03 (`Analysis/rerun_smoke/SMOKE_REPORT.md`).
- The re-costed full collection is about $35.
- The OpenRouter balance was $2.97, so the author must top up before step 2.
- The author's call was to stop before the full paid calls.

Next:
1. Resolve the runbook's section-0 decisions D2 and D5-D9.
2. The author tops up the credit.
3. Collect (runbook steps 2-8), then do S4, S5 and S6. Items `STALE_FIX_LOG.md` lists under
   "needs the rerun" belong to S4.

Still open for the author: the title.

## State on 2026-09-27

Done and verified (no paid calls):
- Architecture patch installed (pins sent, per-call metadata, truncation/empty = failure, 401/402/403
  abort, tie rule, A_H key limit, `collected_utc`). Prompt and RAG ablations migrated to
  `sentinel_utils.openrouter_chat`. 214/214 tests pass under every MODEL_KEY; pipeline gate
  unchanged (G1 66/68, G2 33/36, G3 48/48, G4 5/5, only known Gemini A_H tie cells).
  Report: `paper/pass6/verify/INSTALL_MIGRATE_REPORT.md`.
- New calculators staged in `Analysis/rerun_prep/calc_new/` (not installed).
- Scenario rebuild script written; reproduction gate identical; dry run 65 cells, all traced.
  Report: `paper/pass6/verify/REBUILD_REPORT.md`.
- Cost estimate at pinned prices: about $28 for 125,340 calls (Gemini $17.1, Qwen $5.8,
  DeepSeek $4.0, GPT-OSS $0.9); budget ~$40. Gemini 3.8 reasoning length is the main unknown.

Next (only when the author says go):
1. Phase I, offline only, per `REBUILD_REPORT.md` and the runbook: apply scenario fixes; rebuild;
   install `calc_new` + tests; run calculators (row counts 315/300/240); sync RAG scores;
   `build_rag_index.py` last (local SentenceTransformer, free); update `tests/audit_scenarios.py`
   and README ranges; merge provenance into `docs/CALCULATOR_PROVENANCE.md`; offline baselines
   (fixed-default, dataset-median, nearest-neighbour, single-criterion; no API calls); archive old
   outputs as above.
   Also in Phase I, three code changes the author approved on 2026-09-27 (all with mocked-HTTP
   tests; prompts stay byte-identical; rerun `tests/` under all four MODEL_KEYs and the pipeline
   gate afterwards):
   a. **Raise max_tokens to 32768 for the prompt-ablation CoT arms** (A_D and A_E `cot_scaffold`,
      every model). Old logs: Qwen A_D CoT ~12.7% of calls over 8,192, A_E CoT ~3.7%
      (`paper/pass6/verify/truncation_risk_8192.csv`). Venice's Qwen endpoint allows 32,768.
      Check each pinned endpoint's `max_completion_tokens` (free GET
      `https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints`) and use
      min(32768, that limit). Other arms and the architectures keep 8192. Record the per-arm cap
      in the raw log.
   b. **Prompt ablation Top-1 (and Top-2 / any accuracy metric): a failed or unscored scenario
      counts as wrong; the denominator is all scenarios in the cell.** Same rule the RAG ablation
      already uses (see `INSTALL_MIGRATE_REPORT.md`). Tau/MAE unchanged. Carry it through summaries,
      significance tests and the report; add failed-scenario counts.
   c. **Lock the five-consecutive-failures breaker** in `sentinel_utils` so the counter is
      thread-safe under the ablations' ThreadPoolExecutor.
   d. **Duquesne tariff (item D9 in `V_APPLIANCE.md`).** The author downloaded Duquesne Light
      **Supplement No. 108** to Electric Pa. P.U.C. No. 25 (the latest; issued July 1, 2026,
      effective September 1, 2026) instead of No. 96:
      `temppapers/currenttariff_108_256018e393-caba-4589-8360-f64513d80451.pdf`. **It is 168
      pages. The subagent that reads it must first read only the table of contents / page index
      (the first few pages), then open only the pages it needs** (the residential price-to-compare /
      default service supply rider, the transmission rider, and the residential rate schedule RS),
      extracting page ranges with `pypdf`, never the whole file. Goal: primary-confirm what the
      residential price to compare is made of (supply + transmission, and any gross-up), which
      `V_APPLIANCE.md` could only support with secondary sources. Caution: the calculator uses
      one common rate period, Dec 2025 - May 2026 (13.75 c/kWh, confirmed by the PA PUC release);
      Supplement 108 is effective September 2026, so its rate VALUES are for a later period. Use it
      for the composition; do not change the 13.75 c value unless the supplement shows the Dec
      2025 - May 2026 value differs, and in that case report to the author instead of editing.
      Record the result (page numbers + verbatim quotes, status) in the Appliance provenance and
      `docs/CALCULATOR_PROVENANCE.md`, and mark D9 resolved or still open.
2. Update Phase I in `PASS6_HANDOFF.md`: name the new rebuild script
   (`Scenario Files/build_scenario_workbooks.py` + `rag_membership.json`), the archive rule, items
   a-d above, and the Duquesne supplement's location.
3. Smoke test and full collection only after the author approves the final cost. Recompute the
   cost estimate with the higher CoT cap (expected +$1-4 for Qwen).

Open for the author:
- Handoff items: title (G3), citation style (B63), CLAUDE.md edit (B77), delivered vs total energy
  (B11), reason for the alpha values (B10), Stroudsburg/Quakertown utility (both PPL for now).

## Git in the cloud phase, and the wrap-up when EVERYTHING is done

The cloud phase runs on the temporary branch `cloud-work`, branched from `main` at 7a39cb3. On
that branch `.gitignore` was loosened and the manuscript, the working docs and the Duquesne PDF are
tracked, so the cloud agents can see them. The repo is private for this phase only.

While working:
- Commit and push only to `cloud-work`, and only when the author says so. Never push to `main`.
- **Do not open GitHub pull requests from `cloud-work`.** GitHub keeps PR refs even after the
  branch is deleted, so the manuscript would stay reachable once the repo is public again.

When the author confirms that everything is done (rerun, analysis, paper edits), the goal is to
put the useful changes on `main` and leave no trace of the temporary documentation or the
`.gitignore` loosening. Do these steps only with the author's go-ahead, and preferably on the
author's own machine, since the ignored files must end up on that disk:

1. **Pull everything down first.** On the author's machine: `git fetch origin` and
   `git switch cloud-work`. The manuscript and working docs edited in the cloud now land on the
   local disk. Check `paper/paper_draft_v2.tex` and `paper/supplementary.tex` before going on,
   because after the next steps those files are no longer in git anywhere.
2. **Untrack the temporary files, keeping them on disk.** On `cloud-work`:
   `git rm --cached -r` everything that was force-added only for the cloud phase:
   - `paper/paper_draft_v2.tex`, `paper/paper_draft_working.tex`, `paper/supplementary.tex`
   - `paper/pass5/`, `paper/pass6/` (including this file, `s1_snapshot/` and `verify/*.md`)
   - `Analysis/rerun_prep/*.md` and the `.md` files under `Analysis/rerun_prep/pipeline/`
   - `Analysis/Sensitivity_alpha_sweep_gemini.xlsx`
   - `temppapers/`

   Keep the scripts (`.py`), `.json`/`.csv` data and the real deliverables tracked:
   - code, tests and scenario/ground-truth/output files;
   - `docs/CALCULATOR_PROVENANCE.md`, which should stay tracked permanently: add a `!docs/*.md`
     exception or force-add it. The author chose the exception (2026-09-27): `!docs/*.md` is
     already in `cloud-work`'s `.gitignore`, after `!CODE_OF_CONDUCT.md`;
   - README.
3. **Restore `.gitignore`** to the version on `main`: `git checkout main -- .gitignore`, then
   re-add the line `!docs/*.md` after `!CODE_OF_CONDUCT.md` (main's version lacks it). Then
   check with `git status --ignored` that every file untracked in step 2 now shows as ignored
   (`!!`) and still exists on disk.
4. **Squash-merge, don't merge.** `git switch main`, then `git merge --squash cloud-work`, review
   `git status` and the staged diff, then commit. A squash brings only the final state onto
   `main`. A normal merge would carry `cloud-work`'s history, in which the manuscript was
   tracked, into `main`, and it would become public with the repo.
5. **Delete the branch everywhere:** `git branch -D cloud-work` and
   `git push origin --delete cloud-work`. Then check that no PR, tag or other branch points at its
   commits, and delete `paper/pass6/CLOUD_AGENT_CONTEXT.md` from disk if it is no longer wanted.
6. Only then may the author make the repo public again, which is the author's decision.

The author runs the commit and push steps. An agent may prepare them and list the exact commands.
