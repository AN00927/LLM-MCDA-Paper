"""Shared sentinel-filtering utilities for all MCDA architectures."""

SENTINEL_VALUE = 1928
CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]


def has_sentinel_scores(scores: dict, criteria: list = CRITERIA,
                        sentinel: int = SENTINEL_VALUE) -> bool:
    """Return True if any criterion score equals the sentinel value."""
    return any(scores.get(c) == sentinel for c in criteria)
