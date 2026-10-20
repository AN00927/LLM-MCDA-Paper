"""Deprecated shim: entropy weights now lives in weight_analysis.

Use `python -m common.weighting.weight_analysis --method entropy --output-dir DIR`.
Running this file directly keeps its legacy behavior (same default destination).
"""
import sys
import warnings
from pathlib import Path

# Make the checkout root importable when this script is run directly.
for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "common").is_dir():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from common.weighting import weight_analysis as _impl


def main():
    warnings.warn(
        "EntropyWeights.py is deprecated; use common.weighting.weight_analysis --method entropy",
        DeprecationWarning,
        stacklevel=2,
    )
    _impl.run_entropy(_impl.LEGACY_METHODOLOGY_DIR)


if __name__ == "__main__":
    main()
