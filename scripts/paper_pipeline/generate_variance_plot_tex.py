#!/usr/bin/env python3
"""Assemble the complete Run-to-Run Variance subsection as a self-contained .tex file.

Thin shim: the implementation lives in generate_pgfplots.py.
Equivalent: python generate_pgfplots.py --figure variance
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_pgfplots import (  # noqa: E402,F401
    main,
    generate_boxplot_block,
    generate_violin_block,
    require_local_per_run_csvs,
    METRICS,
    MODELS,
    BOX_MINIPAGE_TPL,
    VIOLIN_MINIPAGE_TPL,
    build_box_figure,
    build_violin_figure,
    OUTPUT_DIR,
    OUTPUT_FILE,
)

if __name__ == "__main__":
    main(["--figure", "variance"])
