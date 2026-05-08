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
