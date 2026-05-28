"""Shared sentinel-filtering utilities for all MCDA architectures.

The sentinel value 1928 marks a failed/invalid score.  All three of these
are treated as sentinel regardless of how they arrive from CSV/JSON:
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


def parse_utility_budget(budget_value) -> float:
    """Parse utility budget values that may include currency symbols/commas.

    Returns a non-negative float (0.0 on missing/unparseable).
    """
    import pandas as pd
    import re

    if budget_value is None:
        return 0.0

    # Handle already-numeric values
    try:
        if isinstance(budget_value, (int, float)):
            return max(0.0, float(budget_value))
    except Exception:
        pass

    if pd.isna(budget_value):
        return 0.0

    s = str(budget_value).strip()
    # Remove currency symbols, spaces, and thousands separators
    cleaned = re.sub(r"[^0-9.\-]", "", s)
    if cleaned == "":
        return 0.0
    try:
        return max(0.0, float(cleaned))
    except ValueError:
        return 0.0

