# Phase R smoke test (2026-09-27)

The author approved it on 2026-09-27 ("go ahead for phase R; stopping before full paid calls").
It covers step 1 of `paper/pass6/RERUN_RUNBOOK.md`, plus one extra call per model through the
installed A_D (`direct_one_call/`). Everything ran from the Linux cloud container with the
project venv.

## What ran

| Path | Command (runbook step 1) | Calls | Output |
|---|---|---|---|
| (a) RAG ablation | `--sample-size 3 --ablations retrieval_k1 --workers 1 --no-checkpoint` | 36 | `rag/` |
| (b) Prompt ablation | `--sample-size 3 --runs 1 --variants control --architectures AD --workers 1` | 36 | `prompt/` |
| (c) Position bias (A_D reversed) | `run --n 3` | 36 | `posbias/` (moved out of `Output Files*/position_bias/`, which are empty again) |
| Installed A_D, one call | `direct_one_call/smoke_test.py` | 4 | `direct_one_call/smoke_results.json` |

## Result: pass

- **Success:** 112 of 112 calls succeeded, with no parse errors and no `failed_*` records.
  Every call ended with `finish_reason` `stop`. There were no HTTP 400, 404 or 422 errors.
- **Parameters:** every model accepted `temperature` 0.3, `reasoning`, `max_tokens` 8192 and
  the provider pin with `require_parameters: true`. A pinned endpoint that rejected one of
  these would have returned an error.
- **Log fields:** every record carries `provider`, `response_id`, `response_model`,
  `finish_reason`, `usage`, `cost` and `collected_utc`.
- **Providers:** each model was served only by its pinned provider.
- **Charged cost:** $0.027 for the 108 runbook calls and about $0.001 for the 4 extra calls.

| Model | Provider served | Input tok/call | Output tok/call | Reasoning tok/call | Max output | Cost/call |
|---|---|---|---|---|---|---|
| gptoss (`openai/gpt-oss-20b:floor`, low) | Darkbloom (all 27) | 680 | 141 | 95 | 198 | $0.000025 |
| qwen (`qwen/qwen3.5-9b:floor`, none) | Venice (all 27) | 654 | 38 | 0 | 41 | $0.000071 |
| deepseek (`deepseek/deepseek-v4-flash-0731:floor`, none) | BaseTen (all 27) | 614 | 38 | 0 | 43 | $0.000084 |
| gemini (`google/gemini-3.8-flash:floor`, low) | Google AI Studio (all 27) | 639 | 310 | 269 | 571 | $0.00082 |

## Findings for the author

1. **DeepSeek is rate-limited upstream.** 12 of 27 DeepSeek calls got HTTP 429 ("temporarily
   rate-limited upstream") on the first attempt, even with one worker. The worst case took 4
   attempts. All 12 succeeded on retry, and 429s are not billed. At the scripts' default of 8
   workers, a streak of 429s could exhaust `MAX_RETRIES` and trip the 5-consecutive-failure
   abort. Recommendation: run DeepSeek's steps with `--workers 1` or `2` where the script
   takes the flag. The architectures are sequential already.
2. **Gemini reasoning effort (D2).**
   - `model_config.py` sends `low`; Gemini accepts it and returns about 269 reasoning tokens
     per call.
   - Main L737 says Gemini runs at "minimal", and it also names "Gemini 3.5 Flash" while the
     config uses 3.8. The paper and the config must agree before S4.
   - At `low`, Gemini is about two thirds of the whole budget. `minimal`, if accepted, would
     cut that roughly in half.
   - The config is the author's, so it is unchanged.
3. **Output cap (D9).** The largest completion was 571 tokens, far under the 8,192 cap. The
   only arms at risk are still Qwen's CoT arms in the prompt ablation (runbook step 6).
4. **Credit balance.**
   - OpenRouter reports total credits of $92.00, usage of $89.03 and **$2.97 remaining**.
   - The full collection needs about $35 (below). The runbook asks for at least twice the
     estimate, so **add about $70** before step 2.

## Collection estimate (paper-design prompt ablation, no optional arms)

The method re-costs `V_INFRA_cost_plan.csv` with the smoke measurements, current list prices
and three adjustments:
- Gemini gets +269 reasoning tokens per call.
- DeepSeek non-CoT output is capped at the measured 38 tokens per call, since it now runs with
  no reasoning.
- The CoT arms keep their old measured output.

| Model | Calls | Estimate |
|---|---|---|
| gptoss | 37,185 | $1.0 |
| qwen | 37,185 | $6.2 (Qwen CoT arms $4.0 of it) |
| deepseek | 37,185 | $3.9 |
| gemini | 23,145 | $23.6 (prompt ablation $14.1, main $5.9) |
| **Total** | **134,700** | **about $35** |

The breakdown by experiment for all models together:

| Experiment | Estimate |
|---|---|
| RAG ablation | $2.3 |
| Main benchmark | $7.2 |
| A_H order arms | $1.5 |
| Position bias | $0.6 |
| Prompt ablation | $23.0 |

The estimate for the script-default option of the prompt ablation (5 runs in every cell) is
not recomputed here. Gemini would get 5 runs instead of 3, so expect about $10 more.

## Still open before step 2 (runbook section 0)

- D2: Gemini effort.
- D5: prompt-ablation run counts.
- D6: nn-fallback.
- D7: the k rule.
- D8: optional arms.
- D9: Qwen CoT.
- The credit top-up.

B3 (Phase I done) is confirmed by the second cloud session: calculators were rerun, the RAG
scores synced and the index rebuilt last.
