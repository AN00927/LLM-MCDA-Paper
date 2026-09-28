"""Shared sentinel-filtering utilities for all MCDA architectures.

The sentinel value 1928 marks a failed/invalid score.  All three of these
are treated as sentinel regardless of how they arrive from xlsx/JSON:
    - numeric int   1928
    - numeric float 1928.0
    - string        "1928"

Non-numeric strings (e.g. "N/A", "error") coerce to NaN, which the callers
should treat as a failure-safe missing value rather than a valid score.
"""

import threading

SENTINEL_VALUE = 1928
SENTINEL_FLOAT = 1928.0
CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]

# Decimals kept on a weighted MAVT sum before alternatives are ranked. Criterion
# scores are stored at 2 dp and the weights at 2 dp, so an exact sum never needs
# more than 4; the extra digits only strip floating-point noise. Without the
# rounding, two alternatives that tie exactly (e.g. 0.5175 and 0.5175) can differ
# in the 16th digit depending on summation order, and the noise, not
# TIE_BREAK_PRIORITY, decides which ranks first.
MAVT_ROUND_DECIMALS = 10

# Failure codes added for the 2026-09 rerun. They live here, next to the
# sentinel, rather than in model_config (which is the author's run-config file).
# A response that stopped on finish_reason == "length" was cut off by
# MAX_OUTPUT_TOKENS (or a provider cap); its partial text is never scored.
FAILED_TRUNCATED = "FAILED_TRUNCATED"
# A_E found no exemplar (Chroma error, uninitialised index, or zero matches).
# Scoring without examples would silently turn A_E into A_D for that call.
FAILED_RAG_RETRIEVAL = "FAILED_RAG_RETRIEVAL"
# The request itself was rejected (400/404/422) on its one retry. Kept apart
# from FAILED_API_EXHAUSTED so a bad parameter is not read as an outage.
FAILED_API_BAD_REQUEST = "FAILED_API_BAD_REQUEST"

# Output cap sent as max_tokens on every architecture call. Reasoning tokens
# count against it on most providers. Chosen from the historical per-call
# evidence in Analysis/rerun_prep/arch_new/token_evidence.csv: no shipped-prompt
# call on any model came near it (largest per-scenario SUM of three A_D calls:
# 2,501; largest A_H call: 247; largest run-mean per call: 601), and it sits
# inside every model's max output (gpt-oss 32,768; Gemini 65,536; the smallest
# gpt-oss endpoint, SiliconFlow, caps at 8,192).
MAX_OUTPUT_TOKENS = 8192

# Provider routing sent with every call when the model's MODEL_SPECS entry has
# no "provider" key. require_parameters stops OpenRouter routing to an endpoint
# that would silently drop temperature / reasoning / max_tokens.
DEFAULT_PROVIDER_PREFS = {"require_parameters": True}

# 401 bad key, 402 out of credit, 403 forbidden: every later call fails the same
# way, so the process stops instead of saving a run full of sentinels.
FATAL_HTTP_STATUS_CODES = {401, 402, 403}
# A malformed or unroutable request is retried once (a routing blip can return
# 404 "no endpoints"), then the call fails as FAILED_API_BAD_REQUEST.
BAD_REQUEST_STATUS_CODES = {400, 404, 422}
BAD_REQUEST_MAX_ATTEMPTS = 2
# Calls in a row that end in an API-level failure (retries exhausted or a bad
# request) before the process aborts. A config error such as an unsupported
# reasoning effort fails every call; without this the run is saved as complete.
# 0 disables the breaker.
MAX_CONSECUTIVE_API_FAILURES = 5
# A_E calls in a row with no exemplar before the process aborts (RunAbort).
# Retrieval never fails for a model-specific reason, so a streak means the
# index or the query is broken. 0 disables.
MAX_CONSECUTIVE_RETRIEVAL_FAILURES = 5


def coerce_score(value):
    """Coerce a raw score value to float, returning NaN for non-numeric or unparseable values.

    1928 / 1928.0 / "1928" are all treated as the sentinel (not NaN) so that
    callers can still distinguish "failed run" from "genuinely missing data".
    """
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return float("nan")


def is_sentinel(value) -> bool:
    """Return True if *value* is the failure sentinel in any of its three forms."""
    coerced = coerce_score(value)
    import math
    if math.isnan(coerced):
        return False
    return coerced == SENTINEL_FLOAT


def has_sentinel_scores(scores: dict, criteria: list = CRITERIA) -> bool:
    """Return True if any criterion score in *scores* equals the sentinel value.

    Handles int, float, and string representations of 1928.
    """
    return any(is_sentinel(scores.get(c)) for c in criteria)


def coerce_score_series(series):
    """Apply coerce_score element-wise to a pandas Series, returning a float Series.

    Equivalent to pd.to_numeric(series, errors='coerce') but also converts
    the string "1928" to the sentinel float so sentinel detection still works.
    """
    import pandas as pd
    return series.apply(coerce_score)


def read_table_clean(path, dtype: dict = None, time_columns: list = None, keep_str_cols: list = None):
    """
    Read a CSV or XLSX file and normalize column names/strings.

    - path: file path or pathlib.Path
    - dtype: optional dict passed to pandas for dtype enforcement
    - time_columns: list of column names that should be treated as string times
    - keep_str_cols: list of columns to coerce to string and strip whitespace

    Returns a pandas.DataFrame with trimmed column names and string columns stripped.
    """
    import pandas as pd
    from pathlib import Path

    p = Path(path)

    strcols = set((keep_str_cols or []) + (time_columns or []))

    def _to_str(value):
        if value is None:
            return ""
        if isinstance(value, float) and pd.isna(value):
            return ""
        return str(value).strip()

    converters = {col: _to_str for col in strcols} if strcols else None

    if p.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        df = pd.read_excel(p, dtype=dtype, converters=converters, engine="openpyxl")
    else:
        encodings = ["utf-8-sig", "utf-8", "cp1252"]
        last_err = None
        for enc in encodings:
            try:
                if dtype is None:
                    df = pd.read_csv(p, encoding=enc)
                else:
                    df = pd.read_csv(p, encoding=enc, dtype=dtype)
                last_err = None
                break
            except UnicodeDecodeError as e:
                last_err = e
                continue
            except Exception as e:
                last_err = e
                try:
                    df = pd.read_csv(p, encoding=enc)
                    last_err = None
                    break
                except Exception:
                    continue

        if last_err is not None:
            raise last_err

    df.columns = [str(c).strip() for c in df.columns]

    for col in strcols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    for col in df.select_dtypes(include=["object", "string"]).columns:
        if col in strcols:
            continue
        df[col] = df[col].astype(str).str.strip()

    # Excel stores 1800 as 1800.0; downcast integer-valued floats so prompts
    # and downstream string formatting render "1800" instead of "1800.0".
    for col in df.select_dtypes(include=["float"]).columns:
        if col in strcols:
            continue
        series = df[col]
        non_null = series.dropna()
        if len(non_null) == 0:
            continue
        if (non_null == non_null.astype("int64")).all():
            df[col] = series.astype("Int64")

    return df


def _atomic_write_xlsx(df, path) -> None:
    """Write df to xlsx atomically: stage to .tmp, fsync, rename onto path.

    Prevents a crash mid-write from leaving a half-written file that resume
    logic would later treat as a complete run.
    """
    import os
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    df.to_excel(tmp, index=False, engine="openpyxl")
    os.replace(tmp, p)


def _atomic_write_json(obj, path) -> None:
    """Write obj to JSON atomically (same staging strategy as _atomic_write_xlsx)."""
    import json
    import os
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, p)


def _is_complete_run_file(path) -> bool:
    """Return True iff *path* is a readable xlsx with at least one data row.

    Used by resume logic to validate that an existing per-run output came from
    a successful previous launch (vs. a crashed-mid-write file).
    """
    from pathlib import Path
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return False
    if p.with_suffix(p.suffix + ".tmp").exists():
        # A leftover .tmp means the previous write didn't finish.
        return False
    try:
        df = read_table_clean(p)
    except Exception:
        return False
    return len(df) > 0


# Column every per-run xlsx written since the 2026-09 rerun carries. An older
# file lacks it and must never be resumed as if it came from this collection.
RUN_FILE_FORMAT_COLUMN = "collected_utc"


def run_file_state(path) -> str:
    """Classify a per-run xlsx for resume logic.

    "missing"    -- absent, empty, mid-write (.tmp sibling) or unreadable: run it.
    "complete"   -- readable, has rows and a collected_utc column: skip it.
    "old_format" -- readable with rows but no collected_utc: a pre-rerun file.
                    Callers refuse to run rather than overwrite it, so old data
                    is neither mixed into nor silently replaced by the rerun.
    """
    from pathlib import Path
    p = Path(path)
    if not _is_complete_run_file(p):
        return "missing"
    try:
        import pandas as pd
        cols = [str(c).strip() for c in pd.read_excel(p, nrows=0, engine="openpyxl").columns]
    except Exception:
        return "missing"
    return "complete" if RUN_FILE_FORMAT_COLUMN in cols else "old_format"


def log_run_event(path, message: str) -> None:
    """Append one UTC-stamped line to a run's event log (resume skips, run
    start/end, aborts). Never raises; the console log is not kept on disk."""
    from datetime import datetime, timezone
    from pathlib import Path
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
    except Exception:
        pass


class RawCallLog:
    """Append-as-you-go JSONL archive of every raw model call in a benchmark run.

    One JSON object per API call, flushed immediately, so a run that dies partway
    still leaves on disk every call it had already paid for. The per-run xlsx and
    the diagnostics json both record aggregates only; without this the raw model
    text is unrecoverable and any later question about *what the model actually
    said* costs a re-collection.

    Field names match the order-arm jsonl written by
    Miscellaneous Scripts/run_hybrid_ablation_experiments.py (scenario_id, run,
    decision_type, prompt, prompt_sha256, response, prompt_tokens,
    completion_tokens, latency_ms) so both sources can be read by one parser.

    Disabled unless start() is called. Importing an architecture module and
    driving run_scenario yourself -- which the ablation and position-bias scripts
    do -- archives nothing and behaves exactly as it did before.

    Append-only, read last-write-wins by scenario_id, same as the order arm. A
    crashed run is restarted from the first scenario, so its second pass appends
    a fresh set of records rather than overwriting; every record carries its own
    collected_utc, so the passes stay distinguishable.
    """

    def __init__(self):
        self.path = None
        self.run = None
        self.scenario_id = None
        self._warned = False

    def start(self, path, run=None) -> None:
        """Begin archiving to *path*. run is parsed from a `_run_NN` filename
        when not given explicitly."""
        import re
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.path = p
        if run is None:
            m = re.search(r"_run_(\d+)", p.stem)
            run = int(m.group(1)) if m else None
        self.run = run
        self.scenario_id = None
        self._warned = False

    def stop(self) -> None:
        self.path = None
        self.run = None
        self.scenario_id = None

    def set_scenario(self, scenario_id) -> None:
        self.scenario_id = scenario_id

    def record(self, **fields) -> None:
        """Append one call record. Never raises: an archiving fault must not
        take down a run that is spending money."""
        if self.path is None:
            return
        import json
        from datetime import datetime, timezone
        try:
            rec = {
                "collected_utc": datetime.now(timezone.utc).isoformat(),
                "run": self.run,
                "scenario_id": self.scenario_id,
            }
            rec.update(fields)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                f.flush()
        except Exception as exc:
            if not self._warned:
                self._warned = True
                print(f"[WARN] raw call log write failed ({exc}); "
                      f"continuing without archiving")


# ---------------------------------------------------------------------------
# Shared OpenRouter call policy (all three architectures)
# ---------------------------------------------------------------------------

class RunAbort(BaseException):
    """Stop the whole process: a condition that would fail every later call,
    so continuing would only save a run full of sentinels as complete.

    Derives from BaseException on purpose. The architectures and the scripts
    that drive them (position bias, hybrid order arm) wrap each scenario in
    `except Exception` and write sentinels for a crash; an abort must fall
    through all of those.
    """


class OpenRouterFatalError(RunAbort):
    """Stop the whole process: bad key (401), no credit (402), forbidden (403),
    or MAX_CONSECUTIVE_API_FAILURES calls in a row without a usable completion.
    An out-of-credit run must never be saved as a complete run of sentinels.
    `diagnostics` holds the failing call's record for the raw log.
    """

    def __init__(self, message, diagnostics=None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class OpenRouterCallFailed(Exception):
    """One call ended without a completion (retries exhausted, or a bad request
    after its one retry). A_E and A_H raise it from query_openrouter; the text
    starts with the failure code so older string checks still classify it."""

    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics
        self.failure_type = diagnostics.get("failure_type")


def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def response_meta(data) -> dict:
    """Per-call provenance from an OpenRouter 200 body, for the raw log: the
    generation id (lets cost/provider be re-queried via /api/v1/generation),
    the serving provider and resolved model (both vary call to call under
    :floor routing), finish_reason (a 'length' stop is a truncation), the full
    usage block (reasoning tokens, cost) and any separate reasoning text.
    Same fields as the helper in the prompt/RAG ablation scripts."""
    if not isinstance(data, dict):
        data = {}
    choices = data.get("choices")
    choice = (choices[0] if isinstance(choices, list) and choices else {}) or {}
    if not isinstance(choice, dict):
        choice = {}
    message = choice.get("message") or {}
    if not isinstance(message, dict):
        message = {}
    return {
        "response_id": data.get("id"),
        "response_model": data.get("model"),
        "provider": data.get("provider"),
        "system_fingerprint": data.get("system_fingerprint"),
        "finish_reason": choice.get("finish_reason"),
        "native_finish_reason": choice.get("native_finish_reason"),
        "usage": data.get("usage"),
        "reasoning": message.get("reasoning"),
        "body_error": data.get("error") or choice.get("error"),
    }


def message_content(data) -> str:
    """The completion text, never None: `content: null` (reasoning-only
    replies) becomes "", and a list of content parts is joined."""
    choices = data.get("choices") if isinstance(data, dict) else None
    choice = (choices[0] if isinstance(choices, list) and choices else {}) or {}
    message = (choice.get("message") if isinstance(choice, dict) else None) or {}
    content = message.get("content") if isinstance(message, dict) else None
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return content if isinstance(content, str) else str(content)


def provider_prefs_for_model(model_id: str) -> dict:
    """MODEL_SPECS[<key whose openrouter_id is model_id>]["provider"], else
    DEFAULT_PROVIDER_PREFS. Looked up by the id actually sent, so scripts that
    repoint API_CONFIG["model"] (position bias, order arm) get that model's
    routing, not MODEL_KEY's."""
    import copy
    from model_config import MODEL_SPECS
    for spec in MODEL_SPECS.values():
        if spec.get("openrouter_id") == model_id:
            return copy.deepcopy(spec.get("provider", DEFAULT_PROVIDER_PREFS))
    return copy.deepcopy(DEFAULT_PROVIDER_PREFS)


def build_openrouter_payload(model: str, messages, temperature, reasoning=None,
                             max_tokens=None) -> dict:
    """Chat-completions payload shared by the three architectures: model,
    messages, temperature, reasoning (if any), max_tokens and provider routing.
    Usage accounting is not requested: OpenRouter now returns the full usage
    block (cost, reasoning tokens) on every response and documents
    `usage: {include: true}` as deprecated with no effect.

    *max_tokens* defaults to None, which sends MAX_OUTPUT_TOKENS (8192) exactly
    as before -- every architecture and the RAG/hybrid ablation scripts call
    this with two positional args and get that unchanged behaviour. Passing an
    explicit value overrides it; the prompt ablation's cot_scaffold arm is the
    only caller that does, with its per-model raised cap."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if reasoning is not None:
        payload["reasoning"] = reasoning
    payload["max_tokens"] = MAX_OUTPUT_TOKENS if max_tokens is None else max_tokens
    payload["provider"] = provider_prefs_for_model(model)
    return payload


def request_params(payload: dict) -> dict:
    """The payload minus the messages, for the raw log."""
    import copy
    return {k: copy.deepcopy(v) for k, v in payload.items() if k != "messages"}


def _body_problem(data):
    """Why a 200 body holds no usable completion, or None if it does."""
    import json
    if not isinstance(data, dict):
        return "response body is not a JSON object"
    if data.get("error"):
        return "error body: " + json.dumps(data.get("error"), default=str)[:500]
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return "no choices in response"
    choice = choices[0]
    if not isinstance(choice, dict):
        return "choices[0] is not an object"
    if choice.get("error") or choice.get("finish_reason") == "error":
        return "choice error: " + json.dumps(choice.get("error"), default=str)[:500]
    return None


_TRUNCATION_NATIVE_REASONS = {"length", "max_tokens", "max_output_tokens"}

# Calls in a row without a usable completion, across the whole process. Read
# and written from every ThreadPoolExecutor worker in the prompt/RAG/hybrid
# ablations, so every increment, reset and threshold check goes through
# _consecutive_api_failures_lock (below) rather than the bare
# read-modify-write `+= 1`, which is not atomic under the GIL across
# bytecode boundaries and can under-count or double-trip the breaker with
# several workers failing at once.
_consecutive_api_failures = 0
_consecutive_api_failures_lock = threading.Lock()


def openrouter_chat(payload: dict, headers: dict, *, endpoint: str, max_retries: int,
                    timeout, is_transient, base_delay, max_backoff, logger=None) -> dict:
    """POST one chat completion under the shared retry policy.

    Transient HTTP errors, network errors, an unparseable envelope, and a 200
    whose body is an error or has no choices are retried with capped
    exponential backoff up to max_retries attempts. 400/404/422 get one retry.
    401/402/403 raise OpenRouterFatalError at once. latency_ms is the round
    trip of the successful POST only.

    Returns a dict with: ok, content, failure_type (None, FAILED_TRUNCATED,
    FAILED_API_EXHAUSTED or FAILED_API_BAD_REQUEST), truncated, attempts,
    retries, latency_ms, prompt/completion/total/reasoning tokens, cost,
    request_params, attempt_errors and the response_meta fields. A truncated
    call keeps its (partial) content but is not ok.
    """
    import time
    import requests
    from model_config import FAILED_API_EXHAUSTED
    global _consecutive_api_failures

    out = {
        "ok": False,
        "content": None,
        "failure_type": None,
        "truncated": False,
        "attempts": 0,
        "retries": 0,
        "latency_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cost": None,
        "request_params": request_params(payload),
        "attempt_errors": [],
        **response_meta({}),
    }

    def _note(attempt, status, kind, detail, level="warning"):
        out["attempt_errors"].append({
            "attempt": attempt, "utc": utc_now(), "status": status,
            "kind": kind, "detail": str(detail)[:500],
        })
        if logger is not None:
            getattr(logger, level)(f"  API {kind} (attempt {attempt}, status {status}): {str(detail)[:300]}")

    def _count_failure_and_maybe_abort():
        global _consecutive_api_failures
        # The increment and the threshold check happen under the same lock
        # acquisition so two workers failing at once can't both read the
        # pre-increment value: each sees its own post-increment count, and
        # exactly one call trips the breaker at the configured threshold.
        with _consecutive_api_failures_lock:
            _consecutive_api_failures += 1
            count = _consecutive_api_failures
        if MAX_CONSECUTIVE_API_FAILURES > 0 and count >= MAX_CONSECUTIVE_API_FAILURES:
            last = out["attempt_errors"][-1] if out["attempt_errors"] else {"detail": out["failure_type"]}
            raise OpenRouterFatalError(
                f"ABORT: {count} consecutive OpenRouter calls ended without a "
                f"usable completion (last: {out['failure_type']}, {last.get('detail')}). Check the "
                f"model id, reasoning effort, provider routing and max_tokens before resuming.",
                out,
            )

    attempt = 0
    bad_request_attempts = 0
    retry_forever = max_retries <= 0

    while True:
        attempt += 1
        out["attempts"] = attempt
        status = None
        try:
            start_time = time.time()
            response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            latency_ms = (time.time() - start_time) * 1000
            status = response.status_code

            if status == 200:
                data = response.json()
                problem = _body_problem(data)
                if problem is None:
                    usage = data.get("usage") or {}
                    out.update(response_meta(data))
                    out["content"] = message_content(data)
                    out["latency_ms"] = latency_ms
                    out["retries"] = attempt - 1
                    out["prompt_tokens"] = usage.get("prompt_tokens", 0) or 0
                    out["completion_tokens"] = usage.get("completion_tokens", 0) or 0
                    out["total_tokens"] = usage.get("total_tokens", 0) or 0
                    out["reasoning_tokens"] = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0
                    out["cost"] = usage.get("cost")
                    native = str(out.get("native_finish_reason") or "").lower()
                    out["truncated"] = (out.get("finish_reason") == "length"
                                        or native in _TRUNCATION_NATIVE_REASONS)
                    if logger is not None:
                        logger.info(
                            f"  [call ok] attempt={attempt} latency={latency_ms/1000:.1f}s "
                            f"prompt={out['prompt_tokens']} "
                            f"completion={out['completion_tokens']} "
                            f"reasoning_tokens={out['reasoning_tokens']} "
                            f"finish={out.get('finish_reason')} provider={out.get('provider')}"
                        )
                        if out["reasoning_tokens"] > 0:
                            logger.warning(
                                f"  [WARN] reasoning_tokens={out['reasoning_tokens']} > 0 "
                                f"-- reasoning was not disabled for this provider/model."
                            )
                    if out["truncated"]:
                        out["failure_type"] = FAILED_TRUNCATED
                        if logger is not None:
                            logger.warning(f"  [WARN] truncated at max_tokens={payload.get('max_tokens')} "
                                           f"(finish={out.get('finish_reason')}); call fails as {FAILED_TRUNCATED}")
                        _count_failure_and_maybe_abort()
                        return out
                    out["ok"] = True
                    with _consecutive_api_failures_lock:
                        _consecutive_api_failures = 0
                    return out
                # A 200 that carries an error or no choices is retried like a
                # transient error; its id/provider are kept for the log.
                meta = response_meta(data)
                _note(attempt, status, "error_in_200_body",
                      f"{problem} (id={meta.get('response_id')}, provider={meta.get('provider')})")
            elif status in FATAL_HTTP_STATUS_CODES:
                _note(attempt, status, "fatal_http", response.text, level="error")
                out["failure_type"] = f"FATAL_HTTP_{status}"
                reason = {401: "invalid API key", 402: "insufficient credit",
                          403: "forbidden"}.get(status, "")
                raise OpenRouterFatalError(
                    f"ABORT: OpenRouter returned HTTP {status} ({reason}). "
                    f"Every later call would fail the same way, so the run stops here and nothing is "
                    f"saved as complete. Body: {response.text[:300]}",
                    out,
                )
            elif status in BAD_REQUEST_STATUS_CODES:
                bad_request_attempts += 1
                _note(attempt, status, "bad_request", response.text, level="error")
                if bad_request_attempts >= BAD_REQUEST_MAX_ATTEMPTS:
                    out["failure_type"] = FAILED_API_BAD_REQUEST
                    break
            else:
                kind = "transient_http" if is_transient(status) else "http_error"
                _note(attempt, status, kind, response.text)

        except requests.exceptions.RequestException as e:
            _note(attempt, status, type(e).__name__, e)
        except ValueError as e:
            _note(attempt, status, "invalid_json_envelope", e)

        if not retry_forever and attempt >= max_retries:
            out["failure_type"] = FAILED_API_EXHAUSTED
            break

        time.sleep(min(base_delay * (2 ** min(attempt - 1, 5)), max_backoff))

    out["retries"] = attempt
    _count_failure_and_maybe_abort()
    return out


def call_log_fields(call: dict) -> dict:
    """The per-call fields every architecture writes to its raw log."""
    call = call or {}
    keys = ("request_params", "attempts", "retries", "attempt_errors", "response_id",
            "response_model", "provider", "system_fingerprint", "finish_reason",
            "native_finish_reason", "usage", "reasoning", "body_error", "truncated",
            "reasoning_tokens", "cost")
    return {k: call.get(k) for k in keys}


def cost_of(call: dict):
    """usage.cost as a float, or None when the response carried none."""
    try:
        c = (call or {}).get("cost")
        return None if c is None else float(c)
    except (TypeError, ValueError):
        return None


def init_usage_totals() -> dict:
    """Run-level sums of what OpenRouter billed, for the diagnostics JSON.
    calls_with_cost says how many calls the cost total covers."""
    return {"total_cost_usd": 0.0, "total_tokens_reasoning": 0, "calls_with_cost": 0}


def add_call_usage(totals: dict, call: dict) -> None:
    """Add one call's usage.cost and reasoning tokens to *totals*."""
    call = call or {}
    c = cost_of(call)
    if c is not None:
        totals["total_cost_usd"] += c
        totals["calls_with_cost"] += 1
    totals["total_tokens_reasoning"] += int(call.get("reasoning_tokens") or 0)


def merge_usage_totals(dst: dict, src: dict) -> None:
    for k, v in init_usage_totals().items():
        dst[k] = dst.get(k, v) + (src or {}).get(k, v)


def house_age_to_band_label(years) -> str:
    """Canonical building-age range label for a numeric age in years.

    5-year bands up to 20 years (1-5/6-10/11-15/16-20), then 10-year bands
    (21-30, 31-40, ... 101-110, ...). Single source of truth shared by the
    scenario rebuild, BuildRAG embedding, and RAG retrieval embedding so the
    label can never drift between index and query sides.

    Returns the input unchanged (as str) if it is non-numeric.
    """
    try:
        y = int(round(float(years)))
    except (TypeError, ValueError):
        return str(years)
    if y <= 5:
        return "1-5 years"
    if y <= 10:
        return "6-10 years"
    if y <= 15:
        return "11-15 years"
    if y <= 20:
        return "16-20 years"
    lo = ((y - 1) // 10) * 10 + 1
    return f"{lo}-{lo + 9} years"


def appliance_age_to_band_label(years) -> str:
    """Canonical appliance-age range label for a numeric age in years.

    Finer 3-year bands through the first 12 years (1-3 / 4-6 / 7-9 / 10-12),
    where appliance efficiency degrades fastest, then 5-year bands beyond that
    (13-17, 18-22, 23-27, ...). Single source of truth shared by the
    TestScenarios rebuild, BuildRAG embedding/metadata, and RAG retrieval
    embedding so the label can never drift between index and query sides
    (mirrors house_age_to_band_label). Returns the input unchanged (as str)
    if it is non-numeric.
    """
    try:
        y = int(round(float(years)))
    except (TypeError, ValueError):
        return str(years)
    if y < 1:
        y = 1
    if y <= 12:
        lo = ((y - 1) // 3) * 3 + 1
        return f"{lo}-{lo + 2} years"
    lo = ((y - 13) // 5) * 5 + 13
    return f"{lo}-{lo + 4} years"


def gpm_to_flow_rate_label(gpm) -> str:
    """Canonical showerhead flow-rate label for a numeric GPM value.

    low_flow (<= 2.0) / standard (<= 3.0) / high_flow (> 3.0). Single source
    of truth shared by the scenario rebuild, BuildRAG embedding, and RAG
    retrieval embedding. Returns the input unchanged (as str) if non-numeric.
    """
    try:
        val = float(gpm)
    except (TypeError, ValueError):
        return str(gpm)
    if val <= 2.0:
        return "low_flow"
    if val <= 3.0:
        return "standard"
    return "high_flow"


def extract_json_object(text, keys):
    """The JSON object in a model reply, or None. Shared by A_D, A_E and the
    prompt ablation so every scoring arm parses replies by one rule (author
    decision 2026-09-27).

    A ```json fence is unwrapped. The whole reply is parsed first; if that fails,
    the last flat {...} span that holds any of *keys* is used, so a reply with
    prose around the object (or a reasoning scaffold before it) still parses.
    """
    import json
    import re
    if not text:
        return None
    body = str(text).strip()
    if body.startswith("```"):
        parts = body.split("```")
        if len(parts) >= 2:
            body = parts[1]
            if body.lower().startswith("json"):
                body = body[4:]
            body = body.strip()
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    for match in reversed(list(re.finditer(r"\{[^{}]*\}", body, re.DOTALL))):
        try:
            candidate = json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(candidate, dict) and any(k in candidate for k in keys):
            return candidate
    return None


def is_numeric_score(value) -> bool:
    """A real number, not a bool (bool is an int subclass in Python)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def apply_mavt_ranking(alternatives_scores):
    """MAVT ranking for flat-dict alternatives (GT calculators and Direct arch).

    Each element of *alternatives_scores* must be a dict with an ``"alternative"``
    key and the four criterion scores as top-level keys.  Elements whose scores
    contain the sentinel value (1928) are excluded from ranking and receive
    SENTINEL_VALUE rank / SENTINEL_FLOAT weighted_score in the output.

    Returns a dict with keys:
        ``ranked_alternatives`` — list of alternative labels, best first
        ``ranks``              — parallel list of 1-based int ranks (or SENTINEL_VALUE)
        ``weighted_scores``    — parallel list of weighted sums (or SENTINEL_FLOAT)
    """
    from model_config import CRITERION_WEIGHTS, TIE_BREAK_PRIORITY
    import math

    alternatives = [a["alternative"] for a in alternatives_scores]

    valid_pairs = []  # (input_idx, weighted_sum)
    for idx, alt in enumerate(alternatives_scores):
        if has_sentinel_scores(alt):
            continue
        try:
            ws = (
                CRITERION_WEIGHTS["energy_cost"]   * float(alt["energy_cost"]) +
                CRITERION_WEIGHTS["environmental"] * float(alt["environmental"]) +
                CRITERION_WEIGHTS["comfort"]       * float(alt["comfort"]) +
                CRITERION_WEIGHTS["practicality"]  * float(alt["practicality"])
            )
        except (KeyError, TypeError, ValueError):
            continue
        if math.isnan(ws):
            continue
        # Round so exact ties are equal and reach TIE_BREAK_PRIORITY.
        valid_pairs.append((idx, round(ws, MAVT_ROUND_DECIMALS)))

    if not valid_pairs:
        return {
            "ranked_alternatives": [],
            "ranks": [SENTINEL_VALUE] * len(alternatives),
            "weighted_scores": [SENTINEL_FLOAT] * len(alternatives),
        }

    def _sort_key(pair):
        idx, ws = pair
        alt = alternatives_scores[idx]
        return (ws,) + tuple(float(alt.get(c, 0.0)) for c in TIE_BREAK_PRIORITY)

    valid_pairs_sorted = sorted(valid_pairs, key=_sort_key, reverse=True)
    ranked_alternatives = [alternatives[idx] for idx, _ in valid_pairs_sorted]

    ranks = [SENTINEL_VALUE] * len(alternatives)
    weighted_scores = [SENTINEL_FLOAT] * len(alternatives)
    for rank_position, (input_idx, ws) in enumerate(valid_pairs_sorted):
        ranks[input_idx] = rank_position + 1
        weighted_scores[input_idx] = ws

    return {
        "ranked_alternatives": ranked_alternatives,
        "ranks": ranks,
        "weighted_scores": weighted_scores,
    }


def find_file_in_paths(filename: str, search_dirs) -> str:
    """Return the first path under *search_dirs* where *filename* exists.

    Raises ``FileNotFoundError`` if the file is not found in any directory.
    Used by the objective-weight analysis scripts (MERCECWeights, ImpliedWeights)
    to locate ground-truth xlsx files regardless of the working directory.
    """
    import os
    for d in search_dirs:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"Cannot find '{filename}' in {list(search_dirs)}. "
        f"Run from repo root or set SEARCH_DIRS explicitly."
    )


def format_embedding_text(decision_type: str, fields) -> str:
    """Build the similarity-embedding document for a scenario.

    Single source of truth shared by BuildRAG (index side, reads RAG sheets) and
    Eample-Guided_LLM_Scoring.py (query side, reads TestScenarios) so the embedded string
    is byte-identical field-for-field on both sides — retrieval quality depends on
    the query and index strings being produced by the *same* function.

    Encodes only the score-driving homeowner-facing parameters (no free-text
    location; Appliance keeps its question because it carries the baseline time).
    *fields* may be a dict or a pandas Series (anything with .get).
      - house_age is normalised to a band label (idempotent if already a label)
      - flow_rate uses the stored label, falling back to a gpm-derived label
    """
    def g(key, default="N/A"):
        v = fields.get(key, default)
        return default if v is None else v

    if decision_type == "HVAC":
        house_age = house_age_to_band_label(fields.get("house_age"))
        return (
            f"{g('outdoor_temp')} deg F outdoor, {g('insulation')} insulation, "
            f"{g('square_footage')} sqft, {g('household_size')} occupants, "
            f"{g('housing_type')}, house age {house_age}, budget ${g('utility_budget')}/month"
        )
    if decision_type == "Appliance":
        # No separate appliance-type token: TestScenarios (query side) has no
        # 'appliance' column, and the question text already names the appliance
        # ("run the dryer"). Adding it would be 'N/A' on the query side and break
        # query/index parity.
        # appliance_age is banded here so the query side (TestScenarios stores
        # the band label) and the index side (ApplianceRAGScenarios stores raw
        # years) converge to the same token — idempotent on an existing label.
        appliance_age = appliance_age_to_band_label(fields.get("appliance_age"))
        return (
            f"{g('question')}, appliance age {appliance_age}, "
            f"{g('household_size')} occupants, {g('housing_type')}, "
            f"budget ${g('utility_budget')}/month"
        )
    if decision_type == "Shower":
        fr = fields.get("flow_rate")
        if fr is None or str(fr).strip() in ("", "nan", "N/A", "<NA>"):
            fr = gpm_to_flow_rate_label(fields.get("gpm", 0))
        return (
            f"{fr} showerhead, {g('outdoor_temp')} deg F outdoor, "
            f"{g('household_size')} occupants, {g('housing_type')}, "
            f"budget ${g('utility_budget')}/month"
        )
    raise ValueError(f"Unknown decision type: {decision_type}")

