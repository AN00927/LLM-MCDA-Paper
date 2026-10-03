#!/usr/bin/env python3
"""Generate hardcoded pgfplots boxplot commands from per-run CSV data.

Thin shim: the implementation lives in generate_pgfplots.py.
Equivalent: python generate_pgfplots.py --figure boxplot
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_pgfplots import (  # noqa: E402,F401
    main,
    require_local_per_run_csvs,
    generate_boxplot_block,
    BOX_ARCH_MAP as ARCH_MAP,
    DATA_DIR,
    PER_RUN_MODELS,
)

if __name__ == "__main__":
    main(["--figure", "boxplot"])
