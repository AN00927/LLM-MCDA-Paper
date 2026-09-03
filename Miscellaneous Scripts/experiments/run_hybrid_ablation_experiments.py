"""AH parameter-provenance ablation: extracted vs default hidden parameters.

Isolates how much the LLM's parameter extraction contributes to A_H's ranking
accuracy, beyond the contribution of simply having the deterministic calculator.
Two arms, both scored by the same reference calculators over the same 195 test
scenarios:

  extracted      -- the calculator receives the values the LLM actually returned,
                    read from the extracted_* columns of an existing
                    LLM-Parameterized_Reference_Scoring_results.xlsx.
  default_params -- the calculator receives a fixed corpus-median value per
                    parameter, with no per-scenario inference at all. This is the
                    floor: calculator access without meaningful LLM contribution.

  order_reversed -- the calculator receives values extracted from a prompt whose
                    alternative_1/2/3 values were reversed. Everything else,
                    including the alternative order handed to the calculator, is
                    identical to the `extracted` arm. See below.

Both arms are scored against the ranking the reference calculator produces from
the scenario's true engineering values. That reference is the scoring target,
not a reported arm: entering it as an arm would only restate tau = 1.0 and
MAE = 0 for every scenario, which is true by construction and says nothing about
the LLM. Extraction's contribution is the gap between default_params and
extracted.

ALTERNATIVE-ORDER ARM
---------------------
A_H is the only architecture whose prompt shows the model all three alternatives
as a numbered sequence, which is the presentation format the position-bias
literature is about. A_D and A_E score one alternative per stateless call, so
reversal there changes only a two-element "other options" list; A_H is where the
classic construct actually applies, so it is the one that gets tested.

The arm reverses the alternative values inside the extraction prompt and nothing
else. The extracted parameters are then handed to the reference calculator with
the alternatives in their canonical order, exactly as the `extracted` arm does.
Two consequences, both deliberate:

  1. The only difference between `extracted` and `order_reversed` is the text of
     the extraction prompt. Any metric gap is attributable to the ordering.
  2. apply_mavt_ranking resolves exact score ties by input row order (its sort is
     stable). Scoring both arms in canonical order means that tie-break can never
     manufacture a difference, which is the confound that would otherwise inflate
     the effect.

The arm is collected over several runs, because at temperature 0.3 the same
prompt does not extract identical parameters twice, so "reversal changed
something" only means anything relative to how much re-asking changes on its own.

A same-session CONTROL arm is collected alongside it, sending the shipped order
through the identical code path. This exists because the five shipped runs were
collected days earlier and recorded no timestamps: a reversed-vs-shipped gap
could be an ordering effect or provider-side drift, and the two are
indistinguishable. Reversed-vs-control holds the session fixed and isolates
ordering; control-vs-shipped measures the drift by itself.

The headline test is an exact label-permutation test over the runs rather than
per-pair McNemar. A_H's shipped runs disagree on top-1 for only about 5-15 of 195
scenarios, and an exact binomial on five discordant pairs cannot reach p &lt; 0.05
at any split, so a McNemar null here would be an artefact of the test rather than
evidence about ordering. See _exchangeability_test.

API CALLS
---------
Analysis makes zero API calls; every arm is read from files already in the repo.
Collecting the reversed arm costs one extraction call per scenario per run, and
is a separate, resumable step. --models defaults to all four keys, which is the
set the paper reports:

    python "Miscellaneous Scripts/run_hybrid_ablation_experiments.py" --collect-only \
        --order-runs 3

That is 195 x 3 x 4 = 2,340 calls. Run one model per process to parallelise.

Raw prompts and raw model responses are written to a per-model jsonl alongside
the tidy workbook, so any statistic here can be recomputed later without paying
for the calls again.

Passing --models with a subset OVERWRITES the analysis workbooks with only those
models. The omitted models are not merged back in, so a partial run silently
drops them from the shipped results. Narrow the set only when collecting.

Sentinel handling: a scenario whose extraction failed carries the 1928 sentinel
and is excluded from that arm's metrics rather than being silently replaced by a
neutral default. Per-arm scenario counts are reported so any exclusion is visible.
"""

import argparse
import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy.stats import binomtest, kendalltau

import model_config
from model_config import MODEL_SPECS, CRITERION_WEIGHTS
from sentinel_utils import (
    CRITERIA,
    SENTINEL_FLOAT,
    _atomic_write_xlsx,
    apply_mavt_ranking,
    is_sentinel,
    read_table_clean,
)

SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
TEST_SCENARIOS = SCENARIO_DIR / "TestScenarios.xlsx"
AH_ARCHITECTURE = PROJECT_ROOT / "Architectures" / "LLM-Parameterized_Reference_Scoring.py"

ALT_COLS = ["alternative_1", "alternative_2", "alternative_3"]

# Where the order arms land, per model.
#
# Two arms, collected in the same session. `reversed` reverses the alternative
# values in the extraction prompt; `control` re-runs the SHIPPED order through
# the identical code path. The control exists because the shipped five runs were
# collected days earlier and carry no timestamps, so a reversed-vs-shipped gap
# could be an ordering effect or provider drift, and those two have the same
# signature. Reversed-vs-control holds time fixed and isolates ordering;
# control-vs-shipped measures the drift on its own.
ORDER_ARM_SUBDIR = "hybrid_order_reversal"
ORDER_ARM_XLSX = "AH_extraction_order_{arm}_run_{run:02d}.xlsx"
ORDER_ARM_JSONL = "AH_extraction_order_{arm}_run_{run:02d}_raw.jsonl"
ORDER_ARMS = ("reversed", "control")

# Default repeat runs of the reversed arm per invocation. A single reversed run
# could only be placed against the shipped runs' spread, never given a spread of
# its own; more than one lets the reversed arm carry its own run-to-run variance,
# so the comparison is between two distributions instead of a point and a range.
# This is the per-invocation default, not the shipped total: the reversed arm was
# extended to five runs via --order-run-start, against eight in the shipped order
# (the five original runs plus three contemporaneous controls).
DEFAULT_ORDER_RUNS = 3

# Hidden engineering parameters the LLM is asked to estimate, by decision type.
# Must stay in lockstep with the extraction prompt in
# Architectures/LLM-Parameterized_Reference_Scoring.py.
HIDDEN_PARAMS = {
    "HVAC": {
        "numeric": ["r_value", "seer", "hvac_age"],
        "categorical": ["occupancy_context"],
    },
    "Appliance": {
        "numeric": ["kwh_per_cycle"],
        "categorical": ["appliance", "baseline_time"],
    },
    "Shower": {
        "numeric": ["gpm", "tank_size", "water_heater_temp"],
        "categorical": [],
    },
}

SCENARIO_FILES = {
    "HVAC": "HVACScenarios.xlsx",
    "Appliance": "ApplianceScenarios.xlsx",
    "Shower": "ShowerScenarios.xlsx",
}

ARM_SPECS = OrderedDict([
    ("extracted", {
        "label": "LLM-extracted hidden parameters (5-run aggregate)",
        "source": "extracted",
    }),
    # The three per-run arms below are the like-for-like set. `extracted` reads
    # the aggregate workbook, which resolves a scenario that failed in one run
    # using the others, so its success rate is structurally higher than any
    # single run's and it must not be compared directly against a per-run arm.
    # gptoss made that concrete: 194/195 aggregate against 516/585 per-run, an
    # artefact of the aggregation, not of the manipulation.
    ("extracted_per_run", {
        "label": "LLM-extracted, shipped order, per shipped run",
        "source": "extracted_per_run",
    }),
    ("order_control", {
        "label": "LLM-extracted, shipped order, same session as reversed",
        "source": "order_control",
    }),
    ("order_reversed", {
        "label": "LLM-extracted, alternative order reversed in prompt",
        "source": "order_reversed",
    }),
    ("default_params", {
        "label": "Corpus-median hidden parameters (no inference)",
        "source": "default",
    }),
])


def _load_calculator(decision_type: str):
    names = {
        "HVAC": ("HVACGroundTruthCalculator.py", "HVACGroundTruthCalculator"),
        "Appliance": ("ApplianceGroundTruthCalculator.py", "ApplianceGroundTruthCalculator"),
        "Shower": ("ShowerGroundTruthCalculator.py", "ShowerGroundTruthCalculator"),
    }
    filename, class_name = names[decision_type]
    path = PROJECT_ROOT / "Ground Truth Calculators" / filename
    spec = importlib.util.spec_from_file_location(class_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


CALCULATORS = {d: _load_calculator(d) for d in SCENARIO_FILES}


def _clean_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _to_float(value):
    if value is None:
        return np.nan
    try:
        if pd.isna(value):
            return np.nan
    except (TypeError, ValueError):
        pass
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return np.nan


# ---------------------------------------------------------------------------
# Scenario matching (mirrors the corrected matcher in evaluate_parameter_extraction)
# ---------------------------------------------------------------------------

MATCH_KEYS = {
    "HVAC": ["square_footage", "household_size", "outdoor_temp", "utility_budget",
             "housing_type", "alternative_1", "alternative_2", "alternative_3"],
    "Appliance": ["household_size", "outdoor_temp", "utility_budget", "housing_type",
                  "alternative_1", "alternative_2", "alternative_3"],
    "Shower": ["household_size", "outdoor_temp", "utility_budget", "housing_type",
               "alternative_1", "alternative_2", "alternative_3"],
}


def load_test_scenarios() -> pd.DataFrame:
    df = read_table_clean(SCENARIO_DIR / "TestScenarios.xlsx")
    df["scenario_id"] = np.arange(1, len(df) + 1)
    return df


def load_ground_truth(decision_type: str) -> pd.DataFrame:
    keep_str = {
        "HVAC": ["question", "location", "insulation", "housing_type", "house_age",
                 "alternative_1", "alternative_2", "alternative_3", "occupancy_context"],
        "Appliance": ["question", "location", "appliance", "housing_type", "baseline_time",
                      "alternative_1", "alternative_2", "alternative_3"],
        "Shower": ["question", "location", "housing_type", "flow_rate",
                   "alternative_1", "alternative_2", "alternative_3"],
    }
    return read_table_clean(SCENARIO_DIR / SCENARIO_FILES[decision_type],
                            keep_str_cols=keep_str[decision_type])


def match_ground_truth(test_row: pd.Series, gt_df: pd.DataFrame,
                       decision_type: str) -> Optional[pd.Series]:
    q = _clean_text(test_row.get("question"))
    loc = _clean_text(test_row.get("location"))
    cand = gt_df[(gt_df["question"].map(_clean_text) == q)
                 & (gt_df["location"].map(_clean_text) == loc)]
    if len(cand) == 1:
        return cand.iloc[0]
    for key in MATCH_KEYS.get(decision_type, []):
        if len(cand) == 1:
            break
        if key not in cand.columns or key not in test_row.index:
            continue
        target = _clean_text(str(test_row.get(key)))
        narrowed = cand[cand[key].map(lambda v: _clean_text(str(v))) == target]
        if not narrowed.empty:
            cand = narrowed
    return cand.iloc[0] if len(cand) == 1 else None


# ---------------------------------------------------------------------------
# Alternative-order arm: collection (the only part that costs API calls)
# ---------------------------------------------------------------------------

def order_arm_dir(model_key: str) -> Path:
    return PROJECT_ROOT / MODEL_SPECS[model_key]["output_folder"] / ORDER_ARM_SUBDIR


def reverse_alternative_values(payload: Dict) -> Dict:
    """Reverse the values of alternative_1/2/3 in place-order.

    Keys are reassigned rather than reinserted, so dict iteration order is
    untouched and format_scenario_for_extraction emits the same lines in the
    same positions -- only the three values move. Blank slots stay blank, so a
    scenario with fewer than three alternatives is not corrupted.
    """
    out = dict(payload)
    present = [payload.get(c) for c in ALT_COLS]
    filled = [a for a in present
              if a is not None and str(a).strip() not in ("", "nan", "N/A")]
    it = iter(list(reversed(filled)))
    for col, original in zip(ALT_COLS, present):
        if original is None or str(original).strip() in ("", "nan", "N/A"):
            out[col] = original
        else:
            out[col] = next(it)
    return out


def load_ah_module(model_key: str):
    """Load A_H from its path (the filename has a hyphen) and repoint it at the
    requested model. API_CONFIG is read inside query_openrouter at call time, so
    patching after import is enough and model_config is left untouched."""
    spec = importlib.util.spec_from_file_location("ah_order_arm", AH_ARCHITECTURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.API_CONFIG["model"] = model_config.get_model_id(model_key)
    mod.API_CONFIG["reasoning"] = model_config.get_reasoning_payload(model_key)
    print(f"  [INFO] A_H pointed at {mod.API_CONFIG['model']} "
          f"(reasoning={mod.API_CONFIG['reasoning']})")
    return mod


def instrument_capture(mod) -> List[Dict]:
    """Wrap the module's query_openrouter so the exact prompt and the raw
    response text are retained. extract_all_with_ai returns only parsed
    parameters, and a parsed-only record cannot be re-analysed later or audited
    for whether the reversal actually reached the prompt."""
    sink: List[Dict] = []
    original = mod.query_openrouter

    def wrapper(messages, *args, **kwargs):
        # The prompt is recorded BEFORE the call. If query_openrouter exhausts
        # its retries and raises, a record written only on success would leave
        # the prompt blank for exactly the rows most worth auditing -- the ones
        # where you want to rule out a garbled reversed prompt as the cause.
        entry = {"prompt": messages[-1]["content"], "response": "",
                 "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0}
        sink.append(entry)
        text, diag = original(messages, *args, **kwargs)
        entry.update({
            "response": text,
            "prompt_tokens": diag.get("prompt_tokens", 0),
            "completion_tokens": diag.get("completion_tokens", 0),
            "latency_ms": diag.get("latency_ms", 0),
        })
        return text, diag

    mod.query_openrouter = wrapper
    return sink


def load_test_payloads() -> List[Tuple[int, Dict]]:
    """(scenario_id, extraction payload) pairs.

    scenario_id is kept OUT of the payload on purpose: A_H's
    format_scenario_for_extraction raises on any key outside its allowlist, so
    smuggling an id into the dict would abort every call.
    """
    df = read_table_clean(TEST_SCENARIOS, keep_str_cols=ALT_COLS)
    return [(i + 1, row.to_dict()) for i, row in df.iterrows()]


def verify_reversal_reaches_prompt(mod, payloads) -> None:
    """Fail before spending anything if the manipulation is a no-op.

    Renders the shipped and reversed prompts locally and requires that they
    differ, that they differ only on the alternative lines, and that the
    alternative values are genuinely transposed. A silent no-op here would
    produce a confident null that means nothing, which is the exact failure this
    project already hit once on the A_E arm.
    """
    checked = set()
    for sid, payload in payloads:
        dtype = _clean_text(payload.get("decision_type"))
        if dtype in checked or not dtype:
            continue
        rev = reverse_alternative_values(payload)
        a = mod.format_scenario_for_extraction(payload).splitlines()
        b = mod.format_scenario_for_extraction(rev).splitlines()
        if len(a) != len(b):
            raise RuntimeError(f"{dtype}: reversal changed the prompt line count.")
        differing = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if not differing:
            raise RuntimeError(
                f"{dtype}: reversed prompt is identical to shipped. The arm would "
                f"measure nothing. Check that alternative_1/2/3 are distinct.")
        for i in differing:
            key = a[i].split(":", 1)[0].lstrip("- ").strip()
            if key not in ALT_COLS:
                raise RuntimeError(
                    f"{dtype}: reversal changed a non-alternative line ({key!r}). "
                    f"The arm would confound ordering with content.")
        shipped_alts = [str(payload.get(c, "")).strip() for c in ALT_COLS]
        reversed_alts = [str(rev.get(c, "")).strip() for c in ALT_COLS]
        if sorted(shipped_alts) != sorted(reversed_alts):
            raise RuntimeError(f"{dtype}: reversal changed the alternative set.")
        print(f"  [CHECK] {dtype} sid={sid}: "
              f"{shipped_alts} -> {reversed_alts}, {len(differing)} line(s) differ")
        checked.add(dtype)
    if len(checked) < 3:
        raise RuntimeError(f"Only verified {sorted(checked)}; expected all three types.")


def collect_order_arm(model_key: str, run: int = 1, arm: str = "reversed") -> Path:
    """Collect one run of an order arm. Resumable: completed scenarios are
    appended to a jsonl and skipped on restart.

    arm="reversed" reverses the alternative values in the extraction prompt.
    arm="control" sends the shipped order through this same code path, so the
    two arms differ only in the manipulation and never in collection time,
    loader, or capture machinery.
    """
    if arm not in ORDER_ARMS:
        raise ValueError(f"arm must be one of {ORDER_ARMS}, got {arm!r}")
    out_dir = order_arm_dir(model_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = out_dir / ORDER_ARM_XLSX.format(arm=arm, run=run)
    jsonl_path = out_dir / ORDER_ARM_JSONL.format(arm=arm, run=run)

    payloads = load_test_payloads()
    # The arm covers the whole Test corpus. A short payload list means something
    # upstream filtered it, which would silently turn this into a subsample.
    if len(payloads) != 195:
        raise RuntimeError(
            f"Expected all 195 Test scenarios, got {len(payloads)}. The arm must "
            f"not run on a subsample.")

    done: Dict[int, Dict] = {}
    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        for i, line in enumerate(lines):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # Only a truncated final line is recoverable: that is a crash
                # mid-write. A bad line anywhere else means the file is corrupt
                # and silently dropping records would shrink the arm invisibly.
                if i == len(lines) - 1:
                    print("  [WARN] discarding truncated final checkpoint line")
                    break
                raise
            done[int(rec["scenario_id"])] = rec
        n_failed_done = sum(1 for r in done.values() if r.get("extraction_failed"))
        print(f"  [RESUME] {len(done)} scenarios already collected for {model_key}"
              + (f" ({n_failed_done} failed, will retry)" if n_failed_done else ""))

    # A transient API failure should not permanently shrink the arm, so failed
    # scenarios are retried on resume. The jsonl is append-only and read
    # last-write-wins, so the retry supersedes the failure without losing it.
    todo = [(sid, p) for sid, p in payloads
            if sid not in done or done[sid].get("extraction_failed")]
    if todo:
        mod = load_ah_module(model_key)
        verify_reversal_reaches_prompt(mod, payloads)
        sink = instrument_capture(mod)

        with open(jsonl_path, "a", encoding="utf-8") as f:
            for n, (sid, payload) in enumerate(todo, 1):
                dtype = _clean_text(payload.get("decision_type")) or None
                rev = (reverse_alternative_values(payload) if arm == "reversed"
                       else dict(payload))
                sink.clear()
                try:
                    extracted, diag = mod.extract_all_with_ai(
                        rev, expected_decision_type=dtype)
                except Exception as exc:
                    extracted, diag = None, {
                        "failure_types": ["FAILED_EXTRACTION_EXCEPTION"],
                        "extraction_error": str(exc),
                    }
                call = sink[-1] if sink else {}
                prompt_text = call.get("prompt", "")
                rec = {
                    "scenario_id": sid,
                    "model_key": model_key,
                    "arm": arm,
                    "run": run,
                    "decision_type": dtype or "",
                    "shipped_order": [str(payload.get(c, "")) for c in ALT_COLS],
                    "order_as_sent": [str(rev.get(c, "")) for c in ALT_COLS],
                    "prompt_sha256": hashlib.sha256(
                        prompt_text.encode("utf-8")).hexdigest(),
                    "prompt": prompt_text,
                    "response": call.get("response", ""),
                    "parsed": extracted,
                    "extraction_failed": extracted is None,
                    "failure_types": diag.get("failure_types", []),
                    "extraction_error": diag.get("extraction_error"),
                    "prompt_tokens": call.get("prompt_tokens", 0),
                    "completion_tokens": call.get("completion_tokens", 0),
                    "latency_ms": call.get("latency_ms", 0),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                done[sid] = rec
                status = "FAILED" if rec["extraction_failed"] else "ok"
                print(f"  [{n}/{len(todo)}] sid={sid} {dtype}: {status}")

    rows = []
    for sid, _ in payloads:
        rec = done[sid]
        params = (rec.get("parsed") or {}).get("parameters", {}) or {}
        row = {
            "scenario_id": sid,
            "arm": arm,
            "run": run,
            "decision_type": rec.get("decision_type", ""),
            "shipped_order": " | ".join(rec.get("shipped_order", [])),
            "order_as_sent": " | ".join(
                rec.get("order_as_sent", rec.get("reversed_order", []))),
            "extraction_failed": bool(rec.get("extraction_failed")),
            "failure_types": ";".join(rec.get("failure_types") or []),
            "extracted_decision_type": (rec.get("parsed") or {}).get("decision_type", ""),
            "prompt_sha256": rec.get("prompt_sha256", ""),
            "prompt_tokens": rec.get("prompt_tokens", 0),
            "completion_tokens": rec.get("completion_tokens", 0),
            "latency_ms": rec.get("latency_ms", 0),
        }
        for group in HIDDEN_PARAMS.values():
            for p in group["numeric"] + group["categorical"]:
                col = f"extracted_{p}"
                if col not in row:
                    row[col] = params.get(p, "")
        rows.append(row)

    df = pd.DataFrame(rows)
    _atomic_write_xlsx(df, xlsx_path)
    n_failed = int(df["extraction_failed"].sum())
    print(f"  [OK] {model_key} {arm} run {run}: {len(df)} scenarios, "
          f"{n_failed} extraction failures")
    print(f"       {xlsx_path}")
    print(f"       {jsonl_path}")
    return xlsx_path


def order_arm_run_paths(model_key: str, arm: str = "reversed") -> List[Path]:
    d = order_arm_dir(model_key)
    if not d.exists():
        return []
    return sorted(d.glob(f"AH_extraction_order_{arm}_run_*.xlsx"))


def load_order_arm(model_key: str, arm: str = "reversed") -> Dict[str, Dict[int, pd.Series]]:
    """Every collected run of one arm, keyed by run tag. Empty if none exist."""
    out = {}
    for path in order_arm_run_paths(model_key, arm):
        tag = f"{arm}_" + path.stem.rsplit("_", 1)[-1]
        df = read_table_clean(path)
        out[tag] = {int(r["scenario_id"]): r for _, r in df.iterrows()}
    return out


# ---------------------------------------------------------------------------
# Default (corpus-median) parameter values
# ---------------------------------------------------------------------------

def compute_defaults() -> Dict[str, Dict[str, object]]:
    """Median numeric / modal categorical value per hidden parameter, over the
    full source corpus for that decision type. These are the 'no inference'
    values: a single constant reused for every scenario."""
    defaults = {}
    for dtype, groups in HIDDEN_PARAMS.items():
        gt = load_ground_truth(dtype)
        d = {}
        for p in groups["numeric"]:
            d[p] = float(pd.to_numeric(gt[p], errors="coerce").median())
        for p in groups["categorical"]:
            vals = gt[p].map(_clean_text)
            vals = vals[vals != ""]
            d[p] = vals.mode().iloc[0] if not vals.empty else ""
        defaults[dtype] = d
    return defaults


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def build_scenario(decision_type: str, test_row: pd.Series, gt_row: pd.Series,
                   params: Dict[str, object]) -> Dict:
    """Known homeowner-reported fields come from the sheet; the hidden
    engineering parameters come from `params` (the arm under test)."""
    alts = [_clean_text(test_row.get(f"alternative_{i}")) for i in range(1, 4)]
    alts = [a for a in alts if a]
    base = {
        "question": _clean_text(gt_row.get("question")),
        "location": _clean_text(gt_row.get("location")),
        "alternatives": alts,
        "alternative_1": test_row.get("alternative_1", ""),
        "alternative_2": test_row.get("alternative_2", ""),
        "alternative_3": test_row.get("alternative_3", ""),
        "household_size": float(gt_row["household_size"]),
        "housing_type": _clean_text(gt_row.get("housing_type", "")),
        "utility_budget": float(gt_row.get("utility_budget", 0) or 0),
    }
    if decision_type == "HVAC":
        base.update({
            "square_footage": float(gt_row["square_footage"]),
            "outdoor_temp": float(gt_row["outdoor_temp"]),
        })
    elif decision_type == "Shower":
        base.update({"outdoor_temp": float(gt_row["outdoor_temp"])})
    base.update(params)
    return base


def score_scenario(decision_type: str, scenario: Dict) -> Optional[List[Dict]]:
    """Run the reference calculator. Returns per-alternative criterion scores, or
    None if the calculator raises (recorded as a failure, never defaulted).

    The three calculators do not share a return shape, so both are handled:
      HVAC / Appliance: {alt_label: {"<criterion>_score": v, ...}}
      Shower:           {"alternatives": [{"alternative": l,
                                           "transformed_values": {crit: v}}]}
    Verified against all three calculators rather than assumed.
    """
    calc = CALCULATORS[decision_type]()
    try:
        # The calculators print per-alternative progress; silence it so the
        # ablation's own output stays readable across ~1,700 scoring calls.
        with contextlib.redirect_stdout(io.StringIO()):
            result = calc.calculate_scenario_scores(scenario)
    except Exception:
        return None
    if not isinstance(result, dict):
        return None

    rows = []
    if "alternatives" in result and isinstance(result["alternatives"], list):
        for item in result["alternatives"]:
            if not isinstance(item, dict):
                return None
            vals = item.get("transformed_values", item)
            row = {"alternative": _clean_text(item.get("alternative"))}
            for c in CRITERIA:
                row[c] = vals.get(c, vals.get(f"{c}_score", SENTINEL_FLOAT))
            rows.append(row)
    else:
        for alt_label, scores in result.items():
            if not isinstance(scores, dict):
                continue
            row = {"alternative": _clean_text(alt_label)}
            for c in CRITERIA:
                row[c] = scores.get(f"{c}_score", scores.get(c, SENTINEL_FLOAT))
            rows.append(row)
    return rows or None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def scenario_metrics(arm_scored: List[Dict], ref_scored: List[Dict]) -> Optional[Dict]:
    """Kendall tau / Top-1 / MAE for one scenario, arm vs reference."""
    if arm_scored is None or ref_scored is None:
        return None
    if any(is_sentinel(a[c]) for a in arm_scored for c in CRITERIA):
        return None
    if any(is_sentinel(a[c]) for a in ref_scored for c in CRITERIA):
        return None

    ref_by_alt = {a["alternative"]: a for a in ref_scored}
    common = [a["alternative"] for a in arm_scored if a["alternative"] in ref_by_alt]
    if len(common) < 2:
        return None

    arm_r = apply_mavt_ranking([a for a in arm_scored if a["alternative"] in ref_by_alt])
    ref_r = apply_mavt_ranking([ref_by_alt[a] for a in common])

    arm_rank = {alt: rk for alt, rk in zip(
        [a["alternative"] for a in arm_scored if a["alternative"] in ref_by_alt], arm_r["ranks"])}
    ref_rank = {alt: rk for alt, rk in zip(common, ref_r["ranks"])}

    a_vec = [arm_rank[c] for c in common]
    r_vec = [ref_rank[c] for c in common]
    if len(set(a_vec)) < 2 or len(set(r_vec)) < 2:
        tau = np.nan
    else:
        tau = kendalltau(a_vec, r_vec).correlation

    top1 = 1.0 if (arm_r["ranked_alternatives"] and ref_r["ranked_alternatives"]
                   and arm_r["ranked_alternatives"][0] == ref_r["ranked_alternatives"][0]) else 0.0

    errs = [abs(float(a[c]) - float(ref_by_alt[a["alternative"]][c]))
            for a in arm_scored if a["alternative"] in ref_by_alt for c in CRITERIA]

    return {"kendall_tau": tau, "top1": top1, "mae": float(np.mean(errs)) if errs else np.nan}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def extracted_params(row: pd.Series, decision_type: str) -> Optional[Dict[str, object]]:
    groups = HIDDEN_PARAMS[decision_type]
    if str(row.get("extraction_failed", "")).strip().lower() in {"true", "1", "yes"}:
        return None
    out = {}
    for p in groups["numeric"]:
        v = _to_float(row.get(f"extracted_{p}"))
        if pd.isna(v) or is_sentinel(v):
            return None
        out[p] = v
    for p in groups["categorical"]:
        v = _clean_text(row.get(f"extracted_{p}"))
        if not v or is_sentinel(v):
            return None
        out[p] = v
    return out


def true_params(gt_row: pd.Series, decision_type: str) -> Dict[str, object]:
    groups = HIDDEN_PARAMS[decision_type]
    out = {}
    for p in groups["numeric"]:
        out[p] = _to_float(gt_row.get(p))
    for p in groups["categorical"]:
        out[p] = _clean_text(gt_row.get(p))
    return out


def run(args) -> pd.DataFrame:
    test_df = load_test_scenarios()
    gt_cache = {d: load_ground_truth(d) for d in SCENARIO_FILES}
    defaults = compute_defaults()

    print("Corpus-median default parameters (the 'no inference' arm):")
    for d, params in defaults.items():
        print(f"  {d}: " + ", ".join(f"{k}={v}" for k, v in params.items()))
    print()

    records = []
    for model_key in args.models:
        folder = PROJECT_ROOT / MODEL_SPECS[model_key]["output_folder"]
        results_path = folder / "LLM-Parameterized_Reference_Scoring_results.xlsx"
        if not results_path.exists():
            print(f"SKIP {model_key}: {results_path.name} not found")
            continue
        res = read_table_clean(results_path)
        # One row per scenario; the file repeats scenarios per alternative.
        res = res.drop_duplicates(subset=["scenario_id"])
        by_sid = {int(r["scenario_id"]): r for _, r in res.iterrows()}
        print(f"{model_key}: {len(by_sid)} scenarios in results file")

        rev_runs = load_order_arm(model_key, "reversed")
        ctrl_runs = load_order_arm(model_key, "control")
        shipped_runs = {}
        for p in _shipped_run_paths(model_key):
            tag = "shippedrun_" + p.stem.rsplit("_", 1)[-1]
            sr = read_table_clean(p).drop_duplicates(subset=["scenario_id"])
            shipped_runs[tag] = {int(r["scenario_id"]): r for _, r in sr.iterrows()}

        if not rev_runs:
            print(f"  (no order-reversed arm collected; run with --collect "
                  f"--models {model_key} to add it)")
        else:
            print(f"  order arms: reversed={len(rev_runs)} run(s), "
                  f"control={len(ctrl_runs)} run(s), "
                  f"shipped per-run={len(shipped_runs)}")

        matched = unmatched = 0
        for _, test_row in test_df.iterrows():
            sid = int(test_row["scenario_id"])
            dtype = _clean_text(test_row.get("decision_type"))
            if dtype not in HIDDEN_PARAMS:
                continue
            gt_row = match_ground_truth(test_row, gt_cache[dtype], dtype)
            if gt_row is None:
                unmatched += 1
                continue
            matched += 1

            ref_scored = score_scenario(dtype, build_scenario(
                dtype, test_row, gt_row, true_params(gt_row, dtype)))

            # (arm_id, source_run, params). The reversed arm contributes one
            # entry per collected run, so the headline row averages over its
            # runs instead of resting on whichever run happened to be first.
            arm_entries = [
                ("extracted", "", extracted_params(by_sid[sid], dtype)
                 if sid in by_sid else None),
                ("default_params", "", defaults[dtype]),
            ]
            for arm_id, runs in (("extracted_per_run", shipped_runs),
                                 ("order_control", ctrl_runs),
                                 ("order_reversed", rev_runs)):
                for tag in sorted(runs):
                    arm_entries.append(
                        (arm_id, tag,
                         extracted_params(runs[tag][sid], dtype)
                         if sid in runs[tag] else None))

            for arm_id, source_run, p in arm_entries:
                if p is None:
                    records.append({"model": model_key, "arm": arm_id,
                                    "source_run": source_run, "decision_type": dtype,
                                    "scenario_id": sid, "kendall_tau": np.nan,
                                    "top1": np.nan, "mae": np.nan, "failed": True})
                    continue
                scored = score_scenario(dtype, build_scenario(dtype, test_row, gt_row, p))
                m = scenario_metrics(scored, ref_scored)
                rec = {"model": model_key, "arm": arm_id, "source_run": source_run,
                       "decision_type": dtype, "scenario_id": sid, "failed": m is None}
                rec.update(m or {"kendall_tau": np.nan, "top1": np.nan, "mae": np.nan})
                records.append(rec)
        print(f"  matched {matched}/{matched + unmatched} scenarios"
              + (f" ({unmatched} unmatched)" if unmatched else ""))

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Alternative-order arm: paired analysis against the shipped run-to-run ceiling
# ---------------------------------------------------------------------------

def _shipped_run_paths(model_key: str) -> List[Path]:
    folder = PROJECT_ROOT / MODEL_SPECS[model_key]["output_folder"]
    return sorted(folder.glob("LLM-Parameterized_Reference_Scoring_results_run_*.xlsx"))


def _params_by_sid(df: pd.DataFrame, test_df: pd.DataFrame) -> Dict[int, object]:
    """Extracted parameter dict per scenario, or None where extraction failed."""
    dtype_by_sid = {int(r["scenario_id"]): _clean_text(r.get("decision_type"))
                    for _, r in test_df.iterrows()}
    df = df.drop_duplicates(subset=["scenario_id"])
    out = {}
    for _, r in df.iterrows():
        sid = int(r["scenario_id"])
        dtype = dtype_by_sid.get(sid)
        out[sid] = extracted_params(r, dtype) if dtype in HIDDEN_PARAMS else None
    return out


def _param_signature(params) -> Optional[Tuple]:
    if params is None:
        return None
    return tuple(sorted((k, str(v)) for k, v in params.items()))


def _mcnemar_exact(ref_correct: Dict[int, float], alt_correct: Dict[int, float]):
    """Discordant counts and the exact binomial p, ref against alt.

    Reported for completeness only. It is badly underpowered here: the shipped
    runs disagree on top-1 correctness for roughly 5-15 of 195 scenarios, and a
    two-sided binomial on b+c=5 cannot reach 0.05 at any split. A null from this
    test is uninformative and must not be reported as evidence of no effect --
    use the permutation test below for that.
    """
    sids = [s for s in ref_correct if s in alt_correct
            and ref_correct[s] is not None and alt_correct[s] is not None]
    b = sum(1 for s in sids if ref_correct[s] == 1.0 and alt_correct[s] == 0.0)
    c = sum(1 for s in sids if ref_correct[s] == 0.0 and alt_correct[s] == 1.0)
    p = 1.0 if (b + c) == 0 else binomtest(b, b + c, 0.5).pvalue
    return len(sids), b, c, float(p)


def _agreement(a_by_sid: Dict[int, object], b_by_sid: Dict[int, object]) -> float:
    sids = [s for s in a_by_sid
            if a_by_sid[s] is not None and b_by_sid.get(s) is not None]
    return float(np.mean([a_by_sid[s] == b_by_sid[s] for s in sids])) if sids else np.nan


def _exchangeability_test(per_tag: Dict[str, Dict[int, object]],
                          rev_tags: List[str], shipped_tags: List[str]):
    """Exact label-permutation test on run-level agreement.

    Under the null that alternative order does nothing, a reversed run is just
    another run: which runs carry the 'reversed' label is arbitrary. So relabel
    every way -- C(n, k) assignments for k reversed runs among n total -- and
    ask how often the observed separation is matched or beaten. The shipped
    collection is 5 reversed against 8 in the shipped order (5 original plus 3
    contemporaneous controls), so the primary pooled basis has C(13,5) = 1287
    relabelings.

    Statistic: mean within-group agreement minus mean between-group agreement.
    Large and positive means runs agree with their own group more than across
    groups, which is what an ordering effect would produce.

    This replaces per-pair McNemar as the headline test for three reasons. It
    uses all 195 scenarios rather than the 5-15 discordant ones, so it is not
    power-starved. It handles the dependence between comparisons that share a
    run, instead of presenting one correlated signal as several confirmations.
    And it needs no distributional assumption. The floor is p = 1/C(n, k),
    which on the shipped pooled basis is 1/1287 = 0.00078 and bounds how strong
    a claim this design can support. The count is derived from the data at run
    time and recorded in the `*_n_relabelings` columns, so it stays right if
    the run counts change.
    """
    tags = list(shipped_tags) + list(rev_tags)
    k = len(rev_tags)
    if k == 0 or len(shipped_tags) == 0:
        return np.nan, np.nan, 0

    ag = {}
    for i, a in enumerate(tags):
        for b in tags[i + 1:]:
            ag[(a, b)] = ag[(b, a)] = _agreement(per_tag[a], per_tag[b])

    def stat(group):
        within = [ag[(a, b)] for i, a in enumerate(tags) for b in tags[i + 1:]
                  if (a in group) == (b in group) and not np.isnan(ag[(a, b)])]
        between = [ag[(a, b)] for i, a in enumerate(tags) for b in tags[i + 1:]
                   if (a in group) != (b in group) and not np.isnan(ag[(a, b)])]
        if not within or not between:
            return np.nan
        return float(np.mean(within) - np.mean(between))

    observed = stat(frozenset(rev_tags))
    null = [stat(frozenset(c)) for c in itertools.combinations(tags, k)]
    null = [v for v in null if not np.isnan(v)]
    if not null or np.isnan(observed):
        return observed, np.nan, len(null)
    p = sum(1 for v in null if v >= observed) / len(null)
    return observed, float(p), len(null)


def order_reversal_analysis(models: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compare the reversed-order arm against each shipped run, with the
    shipped-vs-shipped pairs supplying the noise ceiling.

    Every source is scored through the same calculator with the alternatives in
    canonical order, so the stable-sort tie-break in apply_mavt_ranking cannot
    manufacture a difference between arms.
    """
    test_df = load_test_scenarios()
    gt_cache = {d: load_ground_truth(d) for d in SCENARIO_FILES}

    pair_rows, summary_rows = [], []
    for model_key in models:
        rev_paths = order_arm_run_paths(model_key, "reversed")
        if not rev_paths:
            print(f"SKIP {model_key}: no order-reversed arm collected")
            continue
        ctrl_paths = order_arm_run_paths(model_key, "control")
        run_paths = _shipped_run_paths(model_key)
        if not run_paths:
            print(f"SKIP {model_key}: no shipped per-run A_H files")
            continue

        sources = OrderedDict()
        for p in run_paths:
            tag = "shipped_" + p.stem.rsplit("_", 1)[-1]
            sources[tag] = _params_by_sid(read_table_clean(p), test_df)
        for p in ctrl_paths:
            tag = "control_" + p.stem.rsplit("_", 1)[-1]
            sources[tag] = _params_by_sid(read_table_clean(p), test_df)
        for p in rev_paths:
            tag = "reversed_" + p.stem.rsplit("_", 1)[-1]
            sources[tag] = _params_by_sid(read_table_clean(p), test_df)

        # Score every source once.
        choice = {tag: {} for tag in sources}
        correct = {tag: {} for tag in sources}
        signature = {tag: {} for tag in sources}
        for _, test_row in test_df.iterrows():
            sid = int(test_row["scenario_id"])
            dtype = _clean_text(test_row.get("decision_type"))
            if dtype not in HIDDEN_PARAMS:
                continue
            gt_row = match_ground_truth(test_row, gt_cache[dtype], dtype)
            if gt_row is None:
                continue
            ref_scored = score_scenario(dtype, build_scenario(
                dtype, test_row, gt_row, true_params(gt_row, dtype)))
            if ref_scored is None:
                continue
            ref_top1 = apply_mavt_ranking(ref_scored)["ranked_alternatives"]
            ref_top1 = ref_top1[0] if ref_top1 else None

            for tag, by_sid in sources.items():
                params = by_sid.get(sid)
                signature[tag][sid] = _param_signature(params)
                if params is None:
                    choice[tag][sid] = None
                    correct[tag][sid] = None
                    continue
                scored = score_scenario(dtype, build_scenario(
                    dtype, test_row, gt_row, params))
                if scored is None or any(is_sentinel(a[c])
                                         for a in scored for c in CRITERIA):
                    choice[tag][sid] = None
                    correct[tag][sid] = None
                    continue
                ranked = apply_mavt_ranking(scored)["ranked_alternatives"]
                top1 = ranked[0] if ranked else None
                choice[tag][sid] = top1
                correct[tag][sid] = (
                    None if top1 is None or ref_top1 is None
                    else (1.0 if top1 == ref_top1 else 0.0))

        shipped_tags = [t for t in sources if t.startswith("shipped_")]
        ctrl_tags = [t for t in sources if t.startswith("control_")]
        rev_tags = [t for t in sources if t.startswith("reversed_")]
        # Three families. within_shipped and within_reversed are each arm's own
        # run-to-run noise; between is the contrast of interest. It only means
        # something if it sits outside BOTH noise bands.
        # within_* families are each group's own run-to-run noise. Keeping
        # within_control separate from within_shipped is what exposes a session
        # effect: if today's control runs agree with each other more than the
        # older shipped runs do, elevated self-consistency in the reversed arm
        # is the session, not the manipulation.
        pairs = ([("within_shipped", a, b) for i, a in enumerate(shipped_tags)
                  for b in shipped_tags[i + 1:]]
                 + [("within_control", a, b) for i, a in enumerate(ctrl_tags)
                    for b in ctrl_tags[i + 1:]]
                 + [("within_reversed", a, b) for i, a in enumerate(rev_tags)
                    for b in rev_tags[i + 1:]]
                 + [("control_vs_shipped", a, b)
                    for a in ctrl_tags for b in shipped_tags]
                 + [("reversed_vs_control", a, b)
                    for a in rev_tags for b in ctrl_tags]
                 + [("between", a, b) for a in rev_tags for b in shipped_tags])

        for family, a, b in pairs:
            sids = [s for s in choice[a]
                    if choice[a][s] is not None and choice[b].get(s) is not None]
            agree = np.mean([choice[a][s] == choice[b][s] for s in sids]) if sids else np.nan
            psids = [s for s in signature[a]
                     if signature[a][s] is not None and signature[b].get(s) is not None]
            pagree = (np.mean([signature[a][s] == signature[b][s] for s in psids])
                      if psids else np.nan)
            n, bc, cc, p = _mcnemar_exact(correct[b], correct[a])
            pair_rows.append({
                "model": model_key, "family": family, "arm_a": a, "arm_b": b,
                "n_paired": len(sids),
                "top1_choice_agreement": agree,
                "param_identity_rate": pagree,
                "n_mcnemar": n, "b_shipped_right": bc, "c_other_right": cc,
                "mcnemar_exact_p": p,
            })

        pdf = pd.DataFrame([r for r in pair_rows if r["model"] == model_key])
        ship = pdf[pdf["family"] == "within_shipped"]
        wrev = pdf[pdf["family"] == "within_reversed"]
        btw = pdf[pdf["family"] == "between"]

        # The between-family agreement is "different" only if it falls below
        # both within-family bands. Comparing it against the shipped band alone
        # would credit reversal for noise the reversed arm has anyway.
        noise_floor = min([v for v in [ship["top1_choice_agreement"].min(),
                                       wrev["top1_choice_agreement"].min()]
                           if not pd.isna(v)] or [np.nan])

        # Three bases, all reported, because each answers a different objection.
        #
        #   control : reversed vs the same-session control. Session held fixed,
        #             so an effect here cannot be provider drift. Only C(8,5) =
        #             56 relabelings, so its floor is p = 0.018.
        #   shipped : reversed vs the older shipped runs. C(10,5) = 252
        #             relabelings, but cross-session, so drift and ordering are
        #             confounded.
        #   pooled  : reversed vs shipped AND control together. Both are the
        #             shipped alternative order -- session is a nuisance factor,
        #             not the manipulation -- so pooling them is grouping by
        #             condition, not a data-dependent choice. C(13,5) = 1287
        #             relabelings, floor p = 0.00078. Pooling inflates the
        #             within-reference spread, which shrinks the separation
        #             statistic, so this is the conservative direction.
        #
        # `pooled` is primary when a control exists; without one only the
        # confounded `shipped` basis is available and that is said plainly.
        bases = {"shipped": shipped_tags}
        if ctrl_tags:
            bases["control"] = ctrl_tags
            bases["pooled"] = shipped_tags + ctrl_tags
        basis = "pooled" if ctrl_tags else "shipped"

        per_basis = {}
        for name, tags in bases.items():
            c_sep, c_p, c_n = _exchangeability_test(choice, rev_tags, tags)
            p_sep, p_p, _ = _exchangeability_test(signature, rev_tags, tags)
            per_basis[name] = (c_sep, c_p, p_sep, p_p, c_n)

        choice_sep, choice_p, param_sep, param_p, n_perm = per_basis[basis]

        # Drift, measured directly: same prompt, different session.
        drift_choice = (np.mean([_agreement(choice[c], choice[s])
                                 for c in ctrl_tags for s in shipped_tags])
                        if ctrl_tags else np.nan)
        drift_param = (np.mean([_agreement(signature[c], signature[s])
                                for c in ctrl_tags for s in shipped_tags])
                       if ctrl_tags else np.nan)

        summary_rows.append({
            "model": model_key,
            # Headline test. See _exchangeability_test: this is the one that
            # uses all 195 scenarios and respects the dependence between
            # comparisons sharing a run.
            "perm_basis": basis,
            "perm_choice_separation": choice_sep,
            "perm_choice_p": choice_p,
            "perm_param_separation": param_sep,
            "perm_param_p": param_p,
            "perm_n_relabelings": n_perm,
            "n_control_runs": len(ctrl_tags),
            # Drift diagnostic. Same prompt, different session. Read against
            # within_shipped_*: if they match, the shipped and control runs are
            # interchangeable and the cross-session basis is uncompromised.
            "drift_control_vs_shipped_choice": drift_choice,
            "drift_control_vs_shipped_param": drift_param,
            **{f"{name}_{k}": v
               for name, vals in per_basis.items()
               for k, v in zip(("choice_sep", "choice_p", "param_sep",
                                "param_p", "n_relabelings"), vals)},
            "n_shipped_runs": len(shipped_tags),
            "n_reversed_runs": len(rev_tags),
            "within_shipped_choice_agreement_mean": ship["top1_choice_agreement"].mean(),
            "within_shipped_choice_agreement_min": ship["top1_choice_agreement"].min(),
            "within_reversed_choice_agreement_mean": wrev["top1_choice_agreement"].mean(),
            "within_reversed_choice_agreement_min": wrev["top1_choice_agreement"].min(),
            "between_choice_agreement_mean": btw["top1_choice_agreement"].mean(),
            "between_choice_agreement_min": btw["top1_choice_agreement"].min(),
            "between_at_or_above_noise_floor": bool(
                btw["top1_choice_agreement"].mean() >= noise_floor),
            "within_shipped_param_identity_mean": ship["param_identity_rate"].mean(),
            "within_reversed_param_identity_mean": wrev["param_identity_rate"].mean(),
            "between_param_identity_mean": btw["param_identity_rate"].mean(),
            "between_mcnemar_p_min": btw["mcnemar_exact_p"].min(),
            "between_mcnemar_p_max": btw["mcnemar_exact_p"].max(),
            "between_n_pairs_p_below_05": int((btw["mcnemar_exact_p"] < 0.05).sum()),
            "between_n_pairs": len(btw),
            "between_net_correct_gain": (btw["c_other_right"] - btw["b_shipped_right"]).mean(),
        })

    summary = pd.DataFrame(summary_rows)

    # Holm across the whole permutation family. The primary-basis test is run
    # twice per model, once on the choice statistic and once on the parameter
    # statistic, so four models give eight tests competing for one alpha
    # budget. Reporting the raw p-values alone would leave the correction to
    # the reader; the supplement quotes the adjusted values, so they are
    # computed here rather than by hand.
    if not summary.empty:
        fam = [(i, c) for c in ("perm_choice_p", "perm_param_p")
               for i in summary.index if pd.notna(summary.at[i, c])]
        m = len(fam)
        summary["perm_choice_p_holm"] = np.nan
        summary["perm_param_p_holm"] = np.nan
        running = 0.0
        for step, (i, c) in enumerate(
                sorted(fam, key=lambda ic: summary.at[ic[0], ic[1]])):
            running = max(running, min(summary.at[i, c] * (m - step), 1.0))
            summary.at[i, c + "_holm"] = running

    return pd.DataFrame(pair_rows), summary


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, arm), g in df.groupby(["model", "arm"], sort=False):
        ok = g[~g["failed"]]
        # The reversed arm contributes several runs, so per-run counts are
        # reported rather than a row count that silently triples.
        n_runs = max(1, g["source_run"].nunique()) if "source_run" in g else 1
        rows.append({
            "model": model,
            "arm": arm,
            "label": ARM_SPECS[arm]["label"],
            "n_runs": n_runs,
            "n_scenarios": len(g) // n_runs,
            "n_scored": len(ok),
            "success_rate": len(ok) / len(g) if len(g) else np.nan,
            "kendall_tau": ok["kendall_tau"].mean(),
            "top1_accuracy": ok["top1"].mean(),
            "mae": ok["mae"].mean(),
        })
    out = pd.DataFrame(rows)
    arm_order = {a: i for i, a in enumerate(ARM_SPECS)}
    return (out.assign(_a=out["arm"].map(arm_order))
               .sort_values(["model", "_a"]).drop(columns=["_a"]))


def parse_args():
    p = argparse.ArgumentParser(
        description="AH parameter-provenance ablation (extracted vs default). "
                    "Makes zero API calls.")
    p.add_argument("--models", nargs="+",
                   default=list(MODEL_SPECS.keys()),
                   choices=list(MODEL_SPECS.keys()),
                   help="Model keys whose extracted parameters to evaluate. Defaults to all "
                        "four, which is the set the paper reports; this script makes no API "
                        "calls, so there is no cost reason to narrow it. Passing a subset "
                        "OVERWRITES the analysis workbooks with that subset, so a partial "
                        "run silently drops the omitted models from the shipped results.")
    p.add_argument("--collect", action="store_true",
                   help="Collect the alternative-order arm before analysing. This is "
                        "the only mode that calls the API: one extraction per scenario "
                        "per run per model (195 x runs each). Resumable.")
    p.add_argument("--collect-only", action="store_true",
                   help="Collect the order arm and stop, without running the analysis.")
    p.add_argument("--order-arms", nargs="+", default=["reversed"],
                   choices=list(ORDER_ARMS),
                   help="Which order arms to collect. 'control' re-sends the "
                        "shipped order in the same session, which is what makes "
                        "a reversed-vs-shipped gap attributable to ordering "
                        "rather than to provider drift between sessions.")
    p.add_argument("--order-run-start", type=int, default=1,
                   help="First run index to collect. Use this to extend an arm "
                        "without touching runs already collected: re-running a "
                        "completed index would retry its failed scenarios and "
                        "mutate data that has already been analysed.")
    p.add_argument("--order-runs", type=int, default=DEFAULT_ORDER_RUNS,
                   help=f"Repeat runs of the reversed arm (default "
                        f"{DEFAULT_ORDER_RUNS}). More than one is what gives the arm "
                        f"its own variance, so the comparison against the five shipped "
                        f"runs is distribution against distribution.")
    p.add_argument("--output-dir", default=str(PROJECT_ROOT / "Analysis" / "Hybrid_Ablation"))
    p.add_argument("--output", default=str(PROJECT_ROOT / "hybrid_ablation_results.md"))
    return p.parse_args()


def main():
    args = parse_args()

    if args.collect or args.collect_only:
        for model_key in args.models:
            for arm in args.order_arms:
                # Not `run`: that name is the module-level analysis function,
                # and binding it here would make it local to main().
                for run_idx in range(args.order_run_start, args.order_runs + 1):
                    print(f"\n=== Collecting order-{arm} extraction: "
                          f"{model_key} run {run_idx}/{args.order_runs} ===")
                    collect_order_arm(model_key, run=run_idx, arm=arm)
        if args.collect_only:
            return

    df = run(args)
    if df.empty:
        print("No records produced.")
        return
    summary = summarize(df)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_dir / "hybrid_ablation_summary.xlsx") as xl:
        summary.to_excel(xl, sheet_name="summary", index=False)
        df.to_excel(xl, sheet_name="per_scenario", index=False)

    print("\n=== AH parameter-provenance ablation ===")
    cols = ["model", "arm", "n_scored", "success_rate", "kendall_tau", "top1_accuracy", "mae"]
    print(summary[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # Hand-rolled markdown: pandas.to_markdown needs `tabulate`, which is not a
    # declared dependency of this repo.
    def _md(df: pd.DataFrame) -> str:
        hdr = list(df.columns)
        out = ["| " + " | ".join(hdr) + " |",
               "| " + " | ".join("---" for _ in hdr) + " |"]
        for _, r in df.iterrows():
            cells = [f"{r[h]:.4f}" if isinstance(r[h], float) else str(r[h]) for h in hdr]
            out.append("| " + " | ".join(cells) + " |")
        return "\n".join(out)

    lines = ["# AH Parameter-Provenance Ablation", "",
             "Arms: extracted (actual) / order_reversed / default (floor).",
             "", _md(summary[cols])]

    pairs, order_summary = order_reversal_analysis(args.models)
    if not order_summary.empty:
        with pd.ExcelWriter(out_dir / "hybrid_order_reversal.xlsx") as xl:
            order_summary.to_excel(xl, sheet_name="summary", index=False)
            pairs.to_excel(xl, sheet_name="pairwise", index=False)

        print("\n\n=== Alternative-order arm: exact label-permutation test ===")
        print("Under the null that ordering does nothing, a reversed run is just "
              "another run. Relabel all C(8,3)=56 ways and ask how often the "
              "observed within-minus-between separation is matched. Separation "
              "near zero means the reversed runs are indistinguishable from more "
              "shipped runs. Floor is p=0.018, so that is the strongest claim "
              "this design supports.")
        show = ["model", "n_reversed_runs", "perm_choice_separation", "perm_choice_p",
                "perm_param_separation", "perm_param_p", "perm_n_relabelings"]
        print(order_summary[show].to_string(index=False,
                                            float_format=lambda v: f"{v:.4f}"))

        n_sig = int((order_summary["perm_choice_p"] < 0.05).sum())
        n_sig_p = int((order_summary["perm_param_p"] < 0.05).sum())
        print(f"\n  Top-1 choice: separation significant in "
              f"{n_sig}/{len(order_summary)} models.")
        print(f"  Extracted parameters: separation significant in "
              f"{n_sig_p}/{len(order_summary)} models.")

        print("\n--- Descriptive agreement bands (context, not tests) ---")
        desc = ["model", "within_shipped_choice_agreement_mean",
                "within_reversed_choice_agreement_mean",
                "between_choice_agreement_mean",
                "within_shipped_param_identity_mean",
                "within_reversed_param_identity_mean",
                "between_param_identity_mean"]
        print(order_summary[desc].to_string(index=False,
                                            float_format=lambda v: f"{v:.4f}"))
        print("\n  Per-pair McNemar columns are in the workbook but are "
              "underpowered here (5-15 discordant pairs of 195) and must not be "
              "read as evidence of no effect.")

        _n_ship = int(order_summary["n_shipped_runs"].iloc[0])
        _n_ctrl = int(order_summary["n_control_runs"].iloc[0])
        _n_rev = int(order_summary["n_reversed_runs"].iloc[0])
        _n_relab = int(order_summary["perm_n_relabelings"].iloc[0])
        lines += ["", "## Alternative-order arm", "",
                  f"Exact label-permutation test, pooled basis, over the "
                  f"{_n_ship + _n_ctrl + _n_rev} runs ({_n_ship} shipped, {_n_ctrl} "
                  f"control, {_n_rev} reversed; shipped+control form the reference "
                  f"group). Separation is mean within-group agreement minus mean "
                  f"between-group agreement; p is the fraction of the "
                  f"{_n_relab} relabelings matching or beating it. Floor p = "
                  f"{1 / _n_relab:.5f}.", "",
                  _md(order_summary[show]), "",
                  "Descriptive agreement bands:", "",
                  _md(order_summary[desc])]

    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {args.output} and {out_dir / 'hybrid_ablation_summary.xlsx'}")


if __name__ == "__main__":
    main()
