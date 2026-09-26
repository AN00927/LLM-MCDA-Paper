"""Tests for the Shower reference calculator (P1-HVAC: comments + continuous budget penalty).

File under test: SHOWER_CALC_PATH (env var, absolute or relative to the repo root), else
Analysis/rerun_prep/calc_new/ShowerGroundTruthCalculator.py.
"""
import importlib.util
import math
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CALC_PATH = PROJECT_ROOT / "Analysis" / "rerun_prep" / "calc_new" / "ShowerGroundTruthCalculator.py"
CALC_PATH = Path(os.environ.get("SHOWER_CALC_PATH", DEFAULT_CALC_PATH))
if not CALC_PATH.is_absolute():
    CALC_PATH = PROJECT_ROOT / CALC_PATH
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_spec = importlib.util.spec_from_file_location("shower_calc_under_test", str(CALC_PATH))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SHOWER = _mod.ShowerGroundTruthCalculator


@pytest.fixture
def calc():
    return SHOWER()


def test_budget_penalty_continuous_above_1_5(calc):
    bp = calc.calculate_budget_penalty
    assert bp(10, 0) == 1.0
    assert bp(70, 100) == 1.0
    assert bp(100, 100) == pytest.approx(0.5)
    assert bp(150, 100) == pytest.approx(0.5 * math.exp(-1.5))
    assert bp(200, 100) == pytest.approx(0.5 * math.exp(-3.0))
    vals = [bp(u, 100) for u in range(80, 300, 5)]
    assert all(v > 0 for v in vals)
    assert all(b < a for a, b in zip(vals, vals[1:]))


def test_values_unchanged(calc):
    assert calc.ELECTRICITY_RATE_PA == 0.19
    assert calc.ELECTRIC_HEATER_EFFICIENCY == 0.92
    assert calc.TARGET_SHOWER_TEMP == 105.0
    assert (calc.INLET_TEMP_WINTER, calc.INLET_TEMP_SUMMER) == (45, 65)
    assert calc.apply_value_function(0.14, calc.VF_ENERGY_COST, "energy_cost") == pytest.approx(1.0)
    assert calc.apply_value_function(1.14, calc.VF_ENERGY_COST, "energy_cost") == pytest.approx(0.0)
    assert calc.apply_value_function(6.0, calc.VF_ENVIRONMENTAL, "environmental") == pytest.approx(1.0)
    assert calc.apply_value_function(45.0, calc.VF_ENVIRONMENTAL, "environmental") == pytest.approx(0.0)
