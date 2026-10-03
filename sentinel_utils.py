"""Compatibility alias for :mod:`llm_mcda.common.sentinel_utils`."""
import sys as _sys
from pathlib import Path as _Path

_SOURCE_ROOT = str(_Path(__file__).resolve().parent / "src")
if _SOURCE_ROOT in _sys.path:
    _sys.path.remove(_SOURCE_ROOT)
_sys.path.insert(0, _SOURCE_ROOT)

from llm_mcda.common import sentinel_utils as _implementation

# Keep legacy imports on the canonical module object, including private helpers
# that older scripts import directly and module-level monkeypatches.
_sys.modules[__name__] = _implementation
