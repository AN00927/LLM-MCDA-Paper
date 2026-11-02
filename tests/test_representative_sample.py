"""Tests for the feature-stratified scenario sampler used by the RAG ablations."""
from scripts.experiments.representative_sample import (
    DECISION_TYPES,
    stratified_sample_by_features,
)


def _groups():
    hvac = [
        {"id": f"h{i}", "outdoor_temp": t, "insulation": ins}
        for i, (t, ins) in enumerate(
            [(20, "Good"), (40, "Good"), (60, "Poor"), (90, "Poor"), (25, "Poor"), (85, "Good")] * 3
        )
    ]
    appliance = [
        {"id": f"a{i}", "appliance": app, "appliance_age": age}
        for i, (app, age) in enumerate(
            [("washing_machine", 2), ("dryer", 6), ("dishwasher", 12), ("dryer", 20)] * 4
        )
    ]
    shower = [{"id": f"s{i}", "gpm": g} for i, g in enumerate([1.5, 2.2, 2.7, 3.2] * 4)]
    return {"HVAC": hvac, "Appliance": appliance, "Shower": shower}


def test_full_pool_returned_when_sample_size_is_none_or_large():
    groups = _groups()
    total = sum(len(v) for v in groups.values())
    assert len(stratified_sample_by_features(groups, None, seed=0)) == total
    assert len(stratified_sample_by_features(groups, total + 10, seed=0)) == total


def test_sample_has_requested_size_and_every_decision_type():
    sample = stratified_sample_by_features(_groups(), 12, seed=1)
    assert len(sample) == 12
    ids = [s["id"] for s in sample]
    assert len(set(ids)) == 12
    assert {i[0] for i in ids} == {"h", "a", "s"}
    assert len(DECISION_TYPES) == 3


def test_sample_is_reproducible_for_a_seed_and_differs_across_seeds():
    a = stratified_sample_by_features(_groups(), 12, seed=7)
    b = stratified_sample_by_features(_groups(), 12, seed=7)
    c = stratified_sample_by_features(_groups(), 12, seed=8)
    assert [s["id"] for s in a] == [s["id"] for s in b]
    assert [s["id"] for s in a] != [s["id"] for s in c]


def test_every_shower_flow_stratum_is_covered_when_quota_allows():
    sample = stratified_sample_by_features(_groups(), 12, seed=3)
    gpms = {s["gpm"] for s in sample if s["id"].startswith("s")}
    bands = {"low" if g < 2.0 else "ml" if g < 2.5 else "mh" if g < 3.0 else "high" for g in gpms}
    assert bands == {"low", "ml", "mh", "high"}
