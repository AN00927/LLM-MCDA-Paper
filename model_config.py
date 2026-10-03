"""Compatibility alias for :mod:`llm_mcda.common.model_config`."""
import sys as _sys
from pathlib import Path as _Path

_SOURCE_ROOT = str(_Path(__file__).resolve().parent / "src")
if _SOURCE_ROOT in _sys.path:
    _sys.path.remove(_SOURCE_ROOT)
_sys.path.insert(0, _SOURCE_ROOT)

from llm_mcda.common import model_config as _implementation

# Use one module object so legacy imports and the package API share mutable
# configuration and monkeypatches exactly.
_sys.modules[__name__] = _implementation
