# Debugging Task: Add Logging to All Three Architectures

## Goal
Add logging to output whatever the model is returning at each step (thinking, reasoning, content) to diagnose why Qwen model gets stuck.

## Architectures to Update
1. **Direct_LLM_Scoring.py** - `query_openrouter` and `score_alternative`
2. **Example-Guided_LLM_Scoring.py** - `query_openrouter` and `score_alternative_with_rag`
3. **LLM-Parameterized_Reference_Scoring.py** - `query_openrouter` and `extract_all_with_ai`

## Changes Needed
- [x] Add DEBUG level logging to `query_openrouter` in all three files to log:
  - Full response content (including thinking/reasoning if present)
  - Response structure
  - Token usage details
- [x] Add DEBUG logging in scoring functions to show what the model returns
- [x] Add DEBUG logging in extraction function for LLM-Parameterized_Reference_Scoring
- [x] Ensure logging level can be controlled (INFO for normal, DEBUG for verbose)

## How to Use
Set environment variable `DEBUG_API=true` to enable debug logging:
```bash
DEBUG_API=true python Architectures/Direct_LLM_Scoring.py
```
Or for other architectures:
```bash
DEBUG_API=true python Architectures/Example-Guided_LLM_Scoring.py
DEBUG_API=true python Architectures/LLM-Parameterized_Reference_Scoring.py