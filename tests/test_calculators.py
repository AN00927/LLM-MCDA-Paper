"""Deterministic-calculator tests.

The regression tests regenerate each ground-truth workbook from its scenario
workbook and compare it with the frozen copy in ``workbooks/ground_truth/``, so
any change to a calculator constant or formula that moves the reference scores
fails here.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from calculators.ApplianceGroundTruthCalculator import process_appliance_scenarios
from calculators.HVACGroundTruthCalculator import process_hvac_scenarios
from calculators.ShowerGroundTruthCalculator import (
    ShowerGroundTruthCalculator,
    process_shower_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "workbooks" / "scenarios"
GROUND_TRUTH = ROOT / "workbooks" / "ground_truth"
SCORE_COLS = [
    "energy_cost_score",
    "environmental_score",
    "comfort_score",
    "practicality_score",
]


def _assert_matches_frozen(regenerated: pd.DataFrame, frozen_path: Path) -> None:
    frozen = pd.read_excel(frozen_path)
    assert len(regenerated) == len(frozen)
    for col in SCORE_COLS:
        np.testing.assert_allclose(
            regenerated[col].astype(float).to_numpy(),
            frozen[col].astype(float).to_numpy(),
            atol=1e-9,
            err_msg=col,
        )
    np.testing.assert_allclose(
        regenerated["mavt_score"].astype(float).to_numpy(),
        frozen["mavt_score"].astype(float).to_numpy(),
        atol=1e-4,
        err_msg="mavt_score",
    )
    assert (
        regenerated["rank"].astype(int).tolist() == frozen["rank"].astype(int).tolist()
    )


@pytest.mark.parametrize(
    "process, scenario_file, truth_file",
    [
        (process_hvac_scenarios, "HVACScenarios.xlsx", "ground_truth_hvac.xlsx"),
        (process_appliance_scenarios, "ApplianceScenarios.xlsx", "ground_truth_appliance.xlsx"),
        (process_shower_scenarios, "ShowerScenarios.xlsx", "ground_truth_shower.xlsx"),
    ],
    ids=["hvac", "appliance", "shower"],
)
def test_calculator_reproduces_frozen_ground_truth(
    tmp_path, capsys, process, scenario_file, truth_file
):
    out = tmp_path / truth_file
    regenerated = process(str(SCENARIOS / scenario_file), str(out))
    capsys.readouterr()  # the calculators print per-scenario progress
    _assert_matches_frozen(regenerated, GROUND_TRUTH / truth_file)


def test_frozen_scores_are_unit_interval_and_ranks_are_permutations():
    for name in ("hvac", "appliance", "shower"):
        df = pd.read_excel(GROUND_TRUTH / f"ground_truth_{name}.xlsx")
        assert df[SCORE_COLS].min().min() >= 0.0
        assert df[SCORE_COLS].max().max() <= 1.0
        for _, sc in df.groupby("scenario_id"):
            assert sorted(sc["rank"].astype(int)) == list(range(1, len(sc) + 1))


def test_shower_mains_water_temperature_endpoints_and_midpoint():
    calc = ShowerGroundTruthCalculator()
    assert calc.determine_inlet_temp(20) == pytest.approx(calc.INLET_TEMP_WINTER)
    assert calc.determine_inlet_temp(32) == pytest.approx(calc.INLET_TEMP_WINTER)
    assert calc.determine_inlet_temp(90) == pytest.approx(calc.INLET_TEMP_SUMMER)
    mid = calc.determine_inlet_temp(53.5)
    assert mid == pytest.approx((calc.INLET_TEMP_WINTER + calc.INLET_TEMP_SUMMER) / 2)
    assert calc.TARGET_SHOWER_TEMP == 105.0


def test_shower_energy_scales_linearly_with_duration():
    calc = ShowerGroundTruthCalculator()
    inlet = calc.determine_inlet_temp(40)
    short = calc.calculate_shower_energy(5, 2.0, 120, inlet)
    long = calc.calculate_shower_energy(10, 2.0, 120, inlet)
    assert long == pytest.approx(2 * short)
