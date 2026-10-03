#!/usr/bin/env python3
"""Generate the fig:grouped_bars figure (Overall performance by model) as a matplotlib vector PDF.

Thin shim: the implementation lives in generate_pgfplots.py.
Equivalent: python generate_pgfplots.py --figure grouped_bars
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_pgfplots import (  # noqa: E402,F401
    main,
    DATA,
    OUTPUT_PATH,
    PANEL_ORDER,
    GROUPED_BAR_MODELS as MODELS,
)

if __name__ == "__main__":
    main(["--figure", "grouped_bars"])
