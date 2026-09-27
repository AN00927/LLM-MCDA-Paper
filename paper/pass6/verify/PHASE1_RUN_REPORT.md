# Phase I run report (cloud session, 2026-09-27)

No paid API calls. No git commit or push. Network to openrouter.ai and huggingface.co is
denied in the cloud sandbox, which blocks the two steps marked BLOCKED.

## Done

| Step | Result |
|---|---|
| Pipeline gate on old data | unchanged: G1 66/68, G2 33/36, G3 48/48, G4 5/5 (only the 5 known Gemini A_H tie cells) |
| Snapshot | git HEAD `c5f0773` on `cloud-work` holds every pre-Phase-I file (nothing but `.venv` was ignored) |
| Scenario fixes | `apply_scenario_fixes.py --apply`: 148 applied, 0 mismatched; backups in `Scenario Files/Backups/` |
| Rebuild | `build_scenario_workbooks.py --in-place`: AUDIT PASSED; preview diff 65 cells, as REBUILD_REPORT predicted |
| Calculators + tests installed | `calc_new` copied to `Ground Truth Calculators/`; 3 tests copied to `tests/`, repointed at the installed files; 121/121 |
| Calculators run | 315 / 300 / 240 rows, no sentinel. Against the agents' previews: only question text (HVAC 6, Appliance 99) and the 6 `6pm`-style appliance times differ; no score differs. Shower unchanged |
| RAG sync | dry run then write, all three types matched; HVAC and Appliance score columns refreshed, Shower unchanged |
| `tests/audit_scenarios.py` | city map now loaded from the installed Appliance calculator (was 6 stale + 2 missing cities) |
| README ranges | HVAC cost $0.59-$3.27, HVAC environmental 3.03-17.90 (derived, see calculator comment), Appliance cost $0.028-$0.774 |
| Provenance | `docs/CALCULATOR_PROVENANCE.md` (new; `!docs/*.md` added to `.gitignore`) |
| Duquesne D9 | resolved (composition), 13.75 c unchanged; see `V_APPLIANCE.md` D9 and the Appliance provenance |
| Fixed-default baseline | regenerated (`Output Files/Baselines/baseline_fixeddefault.xlsx`) |
| Archive | 301 files moved to `archive/2026-09_pre_rerun/` (GPT-OSS, Qwen incl. `position_bias/` and `hybrid_order_reversal/`, `Analysis/Prompt_Ablation`, `RAG_Ablation`, `Hybrid_Ablation`, 3 orphan baselines), sha256-verified; source folders empty |
| Code changes a-c | see `PHASE1_CODE_CHANGES_REPORT.md`; prompts byte-identical (504 calls hashed) |
| Tests | `tests/` 367/368 under each MODEL_KEY; the one failure is `test_ae_real_chroma_retrieval_distances` (no Chroma index, BLOCKED below) |
| Gate after a-c | unchanged; `after.csv` identical to the pre-change run |

Test-harness fixes made with the archive: `tests/arch_patch_harness.iter_raw_jsonl` now reads the
four pre-rerun folders explicitly (A_H regression: 6,240 historical replies, 0 differences). The
stored Gemini 3.5 A_H reply for Appliance test 71 says `"appliance": "Waser"`; the old calculator
scored it silently, the installed one returns the sentinel. The success fixture now uses the
canonical name and a new test pins the sentinel behaviour.

## Still to do on the author's machine

1. BLOCKED here: `build_rag_index.py` (needs the SentenceTransformer download). Run it, then
   `pytest tests` (expect 368/368 under each MODEL_KEY).
2. BLOCKED here: nearest-neighbour baseline (same embedding model). Dataset-median condition,
   single-criterion floors and baseline metrics need the new runs (runbook step 8).
3. The `cot_scaffold` endpoint-cap GET runs at prompt-ablation start; if it cannot resolve the
   pinned endpoint it aborts, and `--cot-max-tokens N` sets the cap by hand.
4. `tests/audit_scenarios.py` reports every scenario as an orphan both before and after Phase I
   (pre-existing key mismatch in that script, not a data problem).
5. Cost with the higher CoT cap: at most about +$3.6 for Qwen (old mean completion lengths),
   so about $28-32 in total. Other models' CoT arms were far below 8,192.
