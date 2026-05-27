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


def read_csv_clean(path, dtype: dict = None, time_columns: list = None, keep_str_cols: list = None):
    """
    Robust CSV reader that attempts common encodings and normalizes column names

    - path: file path or pathlib.Path
    - dtype: optional dict passed to pd.read_csv to enforce dtypes (e.g. {'Baseline Time': str})
    - time_columns: list of column names that should be read/treated as string times
    - keep_str_cols: list of columns to coerce to string and strip whitespace

    Returns a pandas.DataFrame with trimmed column names and string columns stripped.
    """
    import pandas as pd
    from pathlib import Path

    encodings = [
        "utf-8-sig",  # preferred for Excel compatibility
        "utf-8",
        "cp1252",
    ]

    p = Path(path)
    last_err = None
    for enc in encodings:
        try:
            if dtype is None:
                df = pd.read_csv(p, encoding=enc)
            else:
                # enforce dtype for selected columns; others inferred
                df = pd.read_csv(p, encoding=enc, dtype=dtype)
            last_err = None
            break
        except UnicodeDecodeError as e:
            last_err = e
            continue
        except Exception as e:
            # If parse errors occur with a forced dtype, retry without dtype
            last_err = e
            try:
                df = pd.read_csv(p, encoding=enc)
                last_err = None
                break
            except Exception:
                continue

    if last_err is not None:
        raise last_err

    # Normalize column names and strip surrounding whitespace
    df.columns = [str(c).strip() for c in df.columns]

    # Coerce requested columns to string and strip whitespace
    strcols = set((keep_str_cols or []) + (time_columns or []))
    for col in strcols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Also strip all object (string) columns by default to remove stray spaces/BOMs
    for col in df.select_dtypes(include=[object]).columns:
        # avoid re-casting columns explicitly requested to remain as something else
        if col in strcols:
            continue
        df[col] = df[col].astype(str).str.strip()

    return df


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

