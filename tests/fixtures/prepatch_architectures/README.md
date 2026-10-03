# Pre-patch architecture fixtures

These source snapshots preserve the three architecture implementations immediately before the Phase I installation patch. They support offline regression comparisons in `tests/test_arch_patch.py`; the test no longer reads arbitrary Git commits, so it remains valid after a history rewrite.

Captured from the parent of the historical `Phase I: install calculators, apply scenario fixes, refresh GT/RAG, code changes a-d` change.

Content checksums:
- `Direct_LLM_Scoring.py`: 39029 bytes, SHA-256 `8e5bb54ca18e1c7858bc0dfab6c667e4b171dae485fabaed2f322d967bfbd95c`
- `Example-Guided_LLM_Scoring.py`: 53708 bytes, SHA-256 `882d3c6a8046ba046cf8634e4a39b5d69c0486ff188c54da4db86baeaa0e2109`
- `LLM-Parameterized_Reference_Scoring.py`: 61809 bytes, SHA-256 `3cbac0b721fc5239a3b0ee5f832b5aa219b7bc520eea11eea5cf175f53ce8838`
