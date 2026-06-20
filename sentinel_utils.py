"""Shared sentinel-filtering utilities for all MCDA architectures.

The sentinel value 1928 marks a failed/invalid score.  All three of these
are treated as sentinel regardless of how they arrive from xlsx/JSON:
    - numeric int   1928
    - numeric float 1928.0
    - string        "1928"

Non-numeric strings (e.g. "N/A", "error") coerce to NaN, which the callers
should treat as a failure-safe missing value rather than a valid score.
"""

SENTINEL_VALUE = 1928
SENTINEL_FLOAT = 1928.0
CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]


def coerce_score(value):
    """Coerce a raw score value to float, returning NaN for non-numeric garbage.

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

    for col in df.select_dtypes(include=[object]).columns:
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


def format_embedding_text(decision_type: str, fields) -> str:
    """Build the similarity-embedding document for a scenario.

    Single source of truth shared by BuildRAG (index side, reads RAG sheets) and
    Example-Guided_LLM scoring.py (query side, reads TestScenarios) so the embedded string
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

