"""Deprecated shim: MEREC weights now lives in weight_analysis.

Use `python -m llm_mcda.common.weighting.weight_analysis --method merec --output-dir DIR`.
Running this file directly keeps its legacy behavior (same default destination).
"""
import sys
import warnings
from pathlib import Path

# Make the checkout's src layout importable when this script is run directly.
for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "src" / "llm_mcda").is_dir():
        if str(_candidate / "src") not in sys.path:
            sys.path.insert(0, str(_candidate / "src"))
        break

from llm_mcda.common.weighting import weight_analysis as _impl


def main():
    warnings.warn(
        "merec_weights.py is deprecated; use llm_mcda.common.weighting.weight_analysis --method merec",
        DeprecationWarning,
        stacklevel=2,
    )
    _impl.run_merec(_impl.LEGACY_METHODOLOGY_DIR)


if __name__ == "__main__":
    main()
