#!/usr/bin/env python3
"""Generate hardcoded pgfplots violin polygon commands from per-run data.

Thin shim: the implementation lives in generate_pgfplots.py.
Equivalent: python generate_pgfplots.py --figure violin
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_pgfplots import (  # noqa: E402,F401
    main,
    require_local_per_run_csvs as _require_local_per_run_csvs,
    compute_violin_polygon,
    generate_violin_block,
    VIOLIN_ARCH_MAP as ARCH_MAP,
    N_GRID,
    MAX_HALF_WIDTH,
    DATA_DIR,
    PER_RUN_MODELS,
)

if __name__ == "__main__":
    main(["--figure", "violin"])
