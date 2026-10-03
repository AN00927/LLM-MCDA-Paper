#!/usr/bin/env python3
"""Deprecated shim: weight diagnostics now live in weight_analysis.

Use `python -m llm_mcda.common.weighting.weight_analysis --method diagnostics
--output-dir DIR [--scope full|test]`. Running this file directly keeps its
legacy behavior and CLI (`--scope`, same default destinations).
"""
import argparse
import sys
import warnings
from pathlib import Path

# Make the checkout's src layout importable when this script is run directly.
for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "src" / "llm_mcda").is_dir():
        sys.path.insert(0, str(_candidate / "src"))
        break
else:
    raise RuntimeError("Cannot locate the repository src/llm_mcda package")

from llm_mcda.common.paths import UnsafeOutputPathError
from llm_mcda.common.weighting import weight_analysis as _impl


def main():
    parser = argparse.ArgumentParser(description="Weight discrimination diagnostics")
    parser.add_argument("--scope", choices=["full", "test"], default="full",
                        help="full = 285-scenario corpus the value functions are "
                             "calibrated on (default); test = 195 evaluated scenarios")
    args = parser.parse_args()
    warnings.warn(
        "WeightDiagnostics.py is deprecated; use "
        "llm_mcda.common.weighting.weight_analysis --method diagnostics",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        _impl.run_diagnostics(_impl.LEGACY_METHODOLOGY_DIR, _impl.LEGACY_DIAG_CSV_DIR, args.scope)
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
