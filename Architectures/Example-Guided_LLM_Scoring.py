import os
import sys
import json
import hashlib
import logging
import requests
import time
from typing import Dict, List, Tuple
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import (
    CRITERION_WEIGHTS,
    TIE_BREAK_PRIORITY,
    get_model_id,
    get_output_folder_for_model_id,
    get_reasoning_payload,
    N_RUNS,
    TEMPERATURE,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_BASE_DELAY,
    MAX_RETRY_BACKOFF,
    EXTRACTION_INVALID_JSON,
    FAILED_MISSING_SCORE,
    FAILED_OUT_OF_BOUNDS,
    FAILED_INVALID_SCORE_TYPE,
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN,
)
from sentinel_utils import (
    _atomic_write_json,
    _atomic_write_xlsx,
    _is_complete_run_file,
    format_embedding_text,
    has_sentinel_scores,
    read_table_clean,
    SENTINEL_VALUE,
    SENTINEL_FLOAT,
)

TEST_SCENARIOS = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# Allow debug level to be controlled via environment variable
DEBUG_API = os.getenv("DEBUG_API", "false").lower() == "true"
DEBUG_LEVEL = logging.DEBUG if DEBUG_API else logging.INFO

logging.basicConfig(
    level=DEBUG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables!")

MODEL_ID = get_model_id()
REASONING_PAYLOAD = get_reasoning_payload()

API_CONFIG = {
    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    "model": MODEL_ID,
    "temperature": TEMPERATURE,
    "reasoning": REASONING_PAYLOAD,
}
logger.info(f"Reasoning payload: {API_CONFIG['reasoning']}")

# Log startup config
if DEBUG_API:
    logger.debug(f"DEBUG_API mode enabled - will log full API responses")
    logger.debug(f"Model: {MODEL_ID}")
    logger.debug(f"Temperature: {TEMPERATURE}")
    logger.debug(f"Max retries: {MAX_RETRIES}")
    logger.debug(f"Request timeout: {REQUEST_TIMEOUT}s")

CHROMA_DB_PATH = PROJECT_ROOT / 'chroma_rag_db'
COLLECTION_NAME = 'mcda_scenarios'
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
RETRIEVE_K = 1

EXPECTED_RAG_SCHEMA_VERSION = 4
RAG_SOURCE_FILES = [
    ("HVAC", "HVACRagScenarios.xlsx"),
    ("Appliance", "ApplianceRAGScenarios.xlsx"),
    ("Shower", "ShowerRAGScenarios.xlsx"),
]


def _compute_expected_source_hash() -> str:
    """Recompute the hash BuildRAG.compute_source_table_hash would produce now."""
    h = hashlib.sha256()
    for decision_type, filename in RAG_SOURCE_FILES:
        path = PROJECT_ROOT / "Scenario Files" / filename
        h.update(decision_type.encode('utf-8'))
        h.update(b'|')
        h.update(path.name.encode('utf-8'))
        h.update(b'|')
        with open(path, 'rb') as f:
            h.update(f.read())
        h.update(b'|')
    return h.hexdigest()

TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}



RAG_FAILURE_COUNTER_KEYS = [
    EXTRACTION_INVALID_JSON,
    FAILED_MISSING_SCORE,
    FAILED_OUT_OF_BOUNDS,
    FAILED_INVALID_SCORE_TYPE,
    FAILED_API_EXHAUSTED,
    FAILED_UNKNOWN
]


def _init_failure_counters() -> Dict[str, int]:
    return {key: 0 for key in RAG_FAILURE_COUNTER_KEYS}


def _increment_failure_counters(counters: Dict[str, int], failure_types: List[str], increment: int = 1) -> None:
    for failure_type in set(failure_types):
        if failure_type in counters:
            counters[failure_type] += increment


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520

chroma_collection = None
embedding_model = None


def init_rag_resources() -> None:
    """Initialize ChromaDB client and embedding model for a single run."""
    global chroma_collection, embedding_model
    logger.info("Loading ChromaDB and embedding model")
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    chroma_collection = chroma_client.get_collection(COLLECTION_NAME)

    coll_meta = chroma_collection.metadata or {}
    stored_hash = coll_meta.get("source_table_sha256")
    stored_version = coll_meta.get("schema_version")
    expected_hash = _compute_expected_source_hash()

    if stored_version != EXPECTED_RAG_SCHEMA_VERSION:
        raise RuntimeError(
            f"RAG schema version mismatch: collection has "
            f"schema_version={stored_version!r}, runtime expects "
            f"{EXPECTED_RAG_SCHEMA_VERSION}. Re-run BuildRAG.py."
        )
    if stored_hash != expected_hash:
        raise RuntimeError(
            f"RAG source hash mismatch — Chroma collection is stale.\n"
            f"  collection source_table_sha256: {stored_hash}\n"
            f"  current source_table_sha256:    {expected_hash}\n"
            f"Re-run Miscellaneous Scripts/BuildRAG.py to refresh."
        )

    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"OK Loaded RAG database: {chroma_collection.count()} scenarios available "
          f"(schema v{stored_version}, hash {stored_hash[:12]}...)")


def query_openrouter(messages: List[Dict], model: str = None,
                     temperature: float = None) -> Tuple[str, Dict]:
    if model is None:
        model = API_CONFIG["model"]
    if temperature is None:
        temperature = API_CONFIG["temperature"]
    url = API_CONFIG["endpoint"]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    reasoning_payload = API_CONFIG["reasoning"]
    if reasoning_payload is not None:
        payload["reasoning"] = reasoning_payload

    last_error = None
    response = None

    attempt = 0
    retry_forever = MAX_RETRIES <= 0

    while True:
        attempt += 1
        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                
                # DEBUG: Log full response structure (always log reasoning/thinking data)
                logger.debug(f"=== API RESPONSE (attempt {attempt}) ===")
                logger.debug(f"Full response keys: {list(data.keys())}")
                logger.debug(f"Usage: {data.get('usage', {})}")
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    logger.debug(f"Choice keys: {list(choice.keys())}")
                    if "message" in choice:
                        msg = choice["message"]
                        logger.debug(f"Message keys: {list(msg.keys())}")
                        logger.debug(f"Message role: {msg.get('role')}")
                        logger.debug(f"Message content (first 500 chars): {msg.get('content', '')[:500]}")
                        # Check for reasoning/thinking fields
                        for key in msg.keys():
                            if key not in ['role', 'content']:
                                logger.debug(f"Message extra field '{key}': {msg.get(key)}")

                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                usage = data.get('usage', {})
                reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                finish_reason = data.get("choices", [{}])[0].get("finish_reason", "?")
                # Always-on progress log: shows pipeline is alive + catches surprise reasoning
                logger.info(
                    f"  [call ok] attempt={attempt} latency={latency_ms/1000:.1f}s "
                    f"prompt={usage.get('prompt_tokens', 0)} "
                    f"completion={usage.get('completion_tokens', 0)} "
                    f"reasoning_tokens={reasoning_tokens} "
                    f"finish={finish_reason}"
                )
                if reasoning_tokens > 0:
                    logger.warning(
                        f"  [WARN] reasoning_tokens={reasoning_tokens} > 0 "
                        f"-- reasoning was not disabled for this provider/model."
                    )

                diagnostics = {
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                    'latency_ms': latency_ms,
                    'model': model
                }

                if DEBUG_API:
                    logger.debug(f"Returning content (len={len(content)}): {content[:200]}...")

                return content, diagnostics
            else:
                last_error = f"Status {response.status_code}: {response.text}"
                if _is_transient_http_status(response.status_code):
                    logger.info(f"  Transient API error (attempt {attempt}): {response.status_code}")
                else:
                    logger.info(f"  API error (attempt {attempt}): {response.status_code}")

                if not retry_forever and attempt >= MAX_RETRIES:
                    break

                time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
                continue

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            logger.info(f"  Request failed (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
            continue

        except ValueError as e:
            last_error = f"Invalid API JSON envelope: {e}"
            logger.info(f"  Invalid API JSON envelope (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
            continue

    # Retries exhausted — raise so caller can map to failed_api_exhausted.
    raise Exception(f"{FAILED_API_EXHAUSTED}: Failed after {MAX_RETRIES} attempts. Last error: {last_error}")

def build_system_prompt() -> str:
    """Build system prompt.

    Calibration anchors are intentionally omitted because RAG already
    supplies scored in-context examples.
    """
    return """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
    You consistently utilize all information given in the scenario context. Score alternatives on four criteria using the inclusive 0-1 scale (0.0 <= score <= 1.0):
1. Energy Cost: Lower energy costs = higher score
2. Environmental Impact: Lower emissions = higher score
3. Comfort: Higher user comfort = higher score
4. Practicality: Easier to implement/maintain = higher score


Return ONLY: {"energy_cost": X, "environmental": X, "comfort": X, "practicality": X} where each X is between 0.0 and 1.0. You must distinguish between the criteria: do not assign the same score to all 4 criteria for an alternative unless performance is actually identical across them.
"""


def format_scenario_text_for_retrieval(scenario: Dict) -> Tuple[str, str]:
    """Build the query-side embedding string (mirrors the index side field-for-field
    via the shared sentinel_utils.format_embedding_text)."""
    decision_type = scenario.get('decision_type', 'HVAC')
    try:
        scenario_text = format_embedding_text(decision_type, scenario)
    except ValueError:
        scenario_text = scenario.get('question', f'Unknown decision type: {decision_type}')
        logger.info(f"   Warning: Unknown decision type '{decision_type}'")
    return scenario_text, decision_type

def retrieve_similar_scenarios(scenario: Dict, k: int = RETRIEVE_K) -> List[Dict]:
    if chroma_collection is None or embedding_model is None:
        logger.info("   RAG database not available, skipping retrieval")
        return []

    # Turn the scenario into plain text
    scenario_text, decision_type = format_scenario_text_for_retrieval(scenario)

    # Make the embedding
    query_embedding = embedding_model.encode(scenario_text).tolist()

    # Pull matches from the database, filtered by decision type. Narrow the
    # catch to the failure modes Chroma's query can realistically raise (bad
    # embedding dim / malformed filter -> ValueError; backend/sqlite issues ->
    # RuntimeError; missing keys in the result envelope -> KeyError) rather than
    # masking unrelated bugs behind a bare Exception.
    try:
        results = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where={"decision_type": decision_type}
        )
    except (ValueError, RuntimeError, KeyError) as e:
        logger.warning(f"   Retrieval query failed ({type(e).__name__}): {e}")
        return []

    retrieved = []
    if results['ids'] and len(results['ids'][0]) > 0:
        for doc_id, doc_text, metadata in zip(
                results['ids'][0],
                results['documents'][0],
                results['metadatas'][0]
        ):
            # Carry the full "show everything" metadata through; format_rag_context
            # renders the homeowner+engineering block and per-alt scores from it.
            retrieved.append({
                'id': doc_id,
                'text': doc_text,
                'decision_type': metadata.get('decision_type', 'Unknown'),
                'metadata': metadata,
            })

    return retrieved


def _fmt_num(v, nd=1):
    """Format a metadata value as a fixed-decimal number, or pass text through."""
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def _exemplar_param_lines(decision_type: str, md: Dict) -> List[str]:
    """Render the homeowner + engineering parameter block for one exemplar,
    mirroring the target-scenario block in build_user_prompt_with_rag and adding
    the engineering values withheld from the homeowner-facing input."""
    g = lambda k: md.get(k, 'N/A')
    if decision_type == 'HVAC':
        return [
            f"- Location: {g('location')}",
            f"- Outdoor Temp: {g('outdoor_temp')} deg F",
            f"- Square Footage: {g('square_footage')} sqft",
            f"- Insulation: {g('insulation')}",
            f"- Household Size: {g('household_size')} occupants",
            f"- Housing Type: {g('housing_type')}",
            f"- House Age: {g('house_age')}",
            f"- R-Value: {g('r_value')}",
            f"- SEER: {g('seer')}",
            f"- HVAC Age: {g('hvac_age')} years",
            f"- Utility Budget: ${g('utility_budget')}/month",
        ]
    if decision_type == 'Appliance':
        return [
            f"- Location: {g('location')}",
            f"- Household Size: {g('household_size')} occupants",
            f"- Housing Type: {g('housing_type')}",
            f"- Appliance: {g('appliance')}",
            f"- Appliance Age Range: {g('appliance_age')}",
            f"- kWh per Cycle: {g('kwh_per_cycle')}",
            f"- Utility Budget: ${g('utility_budget')}/month",
        ]
    if decision_type == 'Shower':
        return [
            f"- Location: {g('location')}",
            f"- Outdoor Temp: {g('outdoor_temp')} deg F",
            f"- Household Size: {g('household_size')} occupants",
            f"- Housing Type: {g('housing_type')}",
            f"- Flow Rate: {g('flow_rate')}",
            f"- GPM: {g('gpm')}",
            f"- Tank Size: {g('tank_size')} gal",
            f"- Water Heater Temp: {g('water_heater_temp')} deg F",
            f"- Utility Budget: ${g('utility_budget')}/month",
        ]
    return [f"- Location: {g('location')}"]


def format_rag_context(retrieved_scenarios: List[Dict]) -> str:
    """Render each retrieved exemplar as a full worked example: the complete
    homeowner + engineering parameter block, then every alternative with its 4
    criterion scores plus the MAVT aggregate and rank."""
    if not retrieved_scenarios:
        return ""

    context = "RELEVANT SIMILAR SCENARIOS WITH EXPERT SCORES:\n\n"
    skipped_alts = 0
    criteria = ('energy_cost', 'environmental', 'comfort', 'practicality')

    for i, scenario in enumerate(retrieved_scenarios, 1):
        md = scenario.get('metadata', {})
        decision_type = scenario.get('decision_type', md.get('decision_type', 'HVAC'))
        context += f"Example {i}:\n"
        context += f"  Question: {md.get('question', 'N/A')}\n"
        for line in _exemplar_param_lines(decision_type, md):
            context += f"  {line}\n"
        context += "  Expert scores:\n"

        for j in range(1, 4):
            name = md.get(f'alt{j}')
            if name in (None, '', 'N/A'):
                continue
            scores = {c: md.get(f'alt{j}_{c}') for c in criteria}
            if any(scores[c] is None or scores[c] == '' for c in criteria):
                skipped_alts += 1
                continue
            mavt = md.get(f'alt{j}_mavt')
            rank = md.get(f'alt{j}_rank')
            context += (
                f"  * {name}: "
                f"Energy Cost: {_fmt_num(scores['energy_cost'])}/1, "
                f"Environmental: {_fmt_num(scores['environmental'])}/1, "
                f"Comfort: {_fmt_num(scores['comfort'])}/1, "
                f"Practicality: {_fmt_num(scores['practicality'])}/1 "
                f"| MAVT: {_fmt_num(mavt, 2)}, Rank: {_fmt_num(rank, 0)}\n"
            )
        context += "\n"

    if skipped_alts > 0:
        logger.info(f"   WARNING: skipped {skipped_alts} retrieved alternative(s) with missing scores. "
              f"Likely RAG metadata schema drift — re-run BuildRAG.")

    context += "Use these examples as reference, but score based on the specific scenario above.\n"    
    return context

def build_user_prompt_with_rag(scenario: Dict, alternative: str, rag_context: str) -> str:
    # Get other alternatives in the scenario to show the LLM the comparative set
    all_alts = [
        scenario.get("alternative_1", ""),
        scenario.get("alternative_2", ""),
        scenario.get("alternative_3", "")
    ]
    other_alts = [str(a) for a in all_alts if a not in (None, "", "N/A") and str(a) != str(alternative)]
    
    prompt = f'Score this alternative: "{alternative}"\n'
    prompt += f'Other alternatives available for this decision: {other_alts}\n\n'
    prompt += f'For the decision: "{scenario.get("question", "N/A")}"\n\n'
    prompt += "SCENARIO CONTEXT:\n"
    prompt += f"- Location: {scenario.get('location', 'N/A')}\n"

    decision_type = scenario.get('decision_type', 'HVAC')

    if decision_type == 'HVAC':
        prompt += (
            f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
            f"- Square Footage: {scenario.get('square_footage', 'N/A')} sqft\n"
            f"- Insulation: {scenario.get('insulation', 'N/A')}\n"
            f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
            f"- House Age: {scenario.get('house_age', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"
        )

    elif decision_type == 'Appliance':
        prompt += (
            f"- Appliance Age Range: {scenario.get('appliance_age', 'N/A')}\n"
            f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"
        )

    elif decision_type == 'Shower':
        prompt += (
            f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
            f"- Flow Rate: {scenario.get('flow_rate', 'N/A')}\n"
            f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('housing_type', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('utility_budget', 'N/A')}/month\n"
        )

    prompt += "\nProvide scores (0-1) for all 4 criteria.\n"
    prompt += "Consider how this specific alternative performs given the scenario context.\n\n"
    
    # RAG context goes after the prompt
    if rag_context:
        prompt += rag_context

    return prompt

def score_alternative_with_rag(scenario: Dict, alternative: str) -> Tuple[Dict, Dict]:
    """Retrieve exemplars, build the RAG prompt, query the model, and parse +
    validate the returned scores — all in one function (mirrors Direct_LLM_Prompting's
    score_alternative).

    retrieved/rag_context are locals here so the RAG diagnostics at the end
    always reference real values (previously they were inlined into the prompt
    call and the diagnostics referenced undefined names, crashing every call).
    """
    retrieved = retrieve_similar_scenarios(scenario, k=RETRIEVE_K)
    rag_context = format_rag_context(retrieved)

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt_with_rag(scenario, alternative, rag_context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    sentinel_scores = {
        'energy_cost': SENTINEL_VALUE, 'environmental': SENTINEL_VALUE,
        'comfort': SENTINEL_VALUE, 'practicality': SENTINEL_VALUE, '_failed': True,
    }

    try:
        response_text, diagnostics = query_openrouter(messages)
        
        # DEBUG: Log the raw scoring response (always log reasoning/thinking data)
        logger.debug(f"=== SCORING RESPONSE for '{alternative}' ===")
        logger.debug(f"Raw response (first 1000 chars): {response_text[:1000]}")
        logger.debug(f"Response length: {len(response_text)} chars")
    except Exception as e:
        logger.info(f"   Scoring failed for alternative '{alternative}': {e}")
        # Distinguish API/network exhaustion from genuine code/parse errors.
        error_text = str(e).lower()
        failure_type = FAILED_API_EXHAUSTED if FAILED_API_EXHAUSTED.lower() in error_text else FAILED_UNKNOWN
        diagnostics = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'latency_ms': 0.0,
            'model': API_CONFIG['model'],
            'success': False,
            'error': str(e),
            'failure_types': [failure_type],
            'rag_retrieved_count': len(retrieved),
            'rag_context_length': len(rag_context),
        }
        return dict(sentinel_scores), diagnostics

    # Parse + validate the model's JSON in-line (single source of truth).
    validation_failed = False
    validation_failure_types = set()
    scores: Dict[str, float] = {}
    try:
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.info("   Could not parse scores; failed")
        diagnostics['success'] = False
        diagnostics['failure_types'] = [EXTRACTION_INVALID_JSON]
        diagnostics['rag_retrieved_count'] = len(retrieved)
        diagnostics['rag_context_length'] = len(rag_context)
        return dict(sentinel_scores), diagnostics

    for criterion in ['energy_cost', 'environmental', 'comfort', 'practicality']:
        if criterion not in parsed:
            logger.info(f"   Missing score for {criterion}; using sentinel {SENTINEL_VALUE}")
            scores[criterion] = SENTINEL_VALUE
            validation_failed = True
            validation_failure_types.add(FAILED_MISSING_SCORE)
            continue

        raw_score = parsed[criterion]
        if isinstance(raw_score, (int, float)):
            raw_value = float(raw_score)
            if 0.0 <= raw_value <= 1.0:
                scores[criterion] = raw_value
            else:
                logger.info(f"   Out-of-range score for {criterion}: {raw_value}; using sentinel {SENTINEL_VALUE}")
                scores[criterion] = SENTINEL_VALUE
                validation_failed = True
                validation_failure_types.add(FAILED_OUT_OF_BOUNDS)
        else:
            logger.info(f"   Invalid score type for {criterion}: {raw_score}; using sentinel {SENTINEL_VALUE}")
            scores[criterion] = SENTINEL_VALUE
            validation_failed = True
            validation_failure_types.add(FAILED_INVALID_SCORE_TYPE)

    if validation_failed:
        scores['_failed'] = True
        diagnostics['success'] = False
        diagnostics['failure_types'] = sorted(validation_failure_types) if validation_failure_types else [FAILED_UNKNOWN]
    else:
        diagnostics['success'] = True
        diagnostics['failure_types'] = []

    diagnostics['rag_retrieved_count'] = len(retrieved)
    diagnostics['rag_context_length'] = len(rag_context)
    return scores, diagnostics


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    alternatives = [ad['alternative'] for ad in alternatives_scores]

    valid_pairs = []  # (input_idx, weighted_sum)
    for idx, alt_data in enumerate(alternatives_scores):
        if alt_data.get('failed'):
            continue
        scores = alt_data['scores']
        if has_sentinel_scores(scores):
            continue
        weighted_sum = (
                CRITERION_WEIGHTS['energy_cost'] * scores['energy_cost'] +
                CRITERION_WEIGHTS['environmental'] * scores['environmental'] +
                CRITERION_WEIGHTS['comfort'] * scores['comfort'] +
                CRITERION_WEIGHTS['practicality'] * scores['practicality']
        )
        valid_pairs.append((idx, weighted_sum))

    if not valid_pairs:
        return {
            'ranked_alternatives': [],
            'ranks': [SENTINEL_VALUE] * len(alternatives),
            'weighted_scores': [SENTINEL_FLOAT] * len(alternatives)
        }

    # Deterministic tiebreaking based on TIE_BREAK_PRIORITY
    def sort_key(pair):
        idx, ws = pair
        scores = alternatives_scores[idx]['scores']
        return (ws,) + tuple(scores.get(crit, 0.0) for crit in TIE_BREAK_PRIORITY)

    valid_pairs_sorted = sorted(valid_pairs, key=sort_key, reverse=True)
    ranked_alternatives = [alternatives[idx] for idx, _ in valid_pairs_sorted]

    # Keep the indices lined up with the original alternatives
    ranks = [SENTINEL_VALUE] * len(alternatives)
    weighted_scores = [SENTINEL_FLOAT] * len(alternatives)
    for rank_position, (input_idx, ws) in enumerate(valid_pairs_sorted):
        ranks[input_idx] = rank_position + 1
        weighted_scores[input_idx] = ws

    return {
        'ranked_alternatives': ranked_alternatives,
        'ranks': ranks,
        'weighted_scores': weighted_scores
    }


def run_scenario(scenario: Dict) -> Dict:
    logger.info(f"SCENARIO: {scenario.get('question', 'N/A')}")

    alternatives_scores = []
    total_diagnostics = {
        'api_calls': 0,
        'total_tokens_input': 0,
        'total_tokens_output': 0,
        'total_latency_ms': 0.0,
        'successful_calls': 0,
        'failed_calls': 0,
        **_init_failure_counters()
    }
    for i in range(1, 4):
        alt_key = f'alternative_{i}'
        if alt_key not in scenario:
            continue

        alternative = scenario[alt_key]
        logger.info(f"\nScoring: {alternative}")

        scores, diagnostics = score_alternative_with_rag(scenario, alternative)
        total_diagnostics['api_calls'] += 1
        total_diagnostics['total_tokens_input'] += diagnostics.get('prompt_tokens', 0)
        total_diagnostics['total_tokens_output'] += diagnostics.get('completion_tokens', 0)
        total_diagnostics['total_latency_ms'] += diagnostics.get('latency_ms', 0.0)

        if scores.get('_failed'):
            logger.info(f" FAILED -- skipping alternative")
            failure_types = diagnostics.get('failure_types') or [FAILED_UNKNOWN]
            total_diagnostics['failed_calls'] += 1
            _increment_failure_counters(total_diagnostics, failure_types)
            alternatives_scores.append({
                'alternative': alternative,
                'scores': {'energy_cost': None, 'environmental': None, 'comfort': None, 'practicality': None},
                'failed': True
            })
            continue

        logger.info(f"  Scores: Energy={scores['energy_cost']:.2f}, "
              f"Env={scores['environmental']:.2f}, "
              f"Comfort={scores['comfort']:.2f}, "
              f"Pract={scores['practicality']:.2f}")
        logger.info(f"  Retrieved {diagnostics.get('rag_retrieved_count', 0)} similar scenarios")

        alternatives_scores.append({
            'alternative': alternative,
            'scores': scores
        })

        if diagnostics.get('success', False):
            total_diagnostics['successful_calls'] += 1
        else:
            failure_types = diagnostics.get('failure_types') or [FAILED_UNKNOWN]
            total_diagnostics['failed_calls'] += 1
            _increment_failure_counters(total_diagnostics, failure_types)

    total_diagnostics['scenario_failed'] = total_diagnostics['failed_calls'] > 0
    ranking_result = apply_mavt_ranking(alternatives_scores)

    logger.info(f"\nRANKING:")
    alt_names = [ad['alternative'] for ad in alternatives_scores]
    for i, alt in enumerate(ranking_result['ranked_alternatives'], 1):
        ws = ranking_result['weighted_scores'][alt_names.index(alt)]
        logger.info(f"  {i}. {alt} (weighted score: {ws:.2f})")

    return {
        'scenario': scenario.get('question', 'N/A'),
        'alternatives_scores': alternatives_scores,
        'ranking_result': ranking_result,
        'diagnostics': total_diagnostics
    }


RAG_RESULT_FIELDNAMES = [
    'scenario_id', 'question', 'location', 'decision_type',
    'outdoor_temp', 'appliance_age', 'flow_rate', 'alternative',
    'energy_cost', 'environmental', 'comfort', 'practicality',
    'rank', 'weighted_score',
]


def run_test_set(test_path: str, output_path: str,
                 output_diagnostics_path: str) -> Dict:
    """Run a single benchmark pass. Caller must have initialized RAG resources."""
    test_csv_path = Path(test_path)
    output_csv_path = Path(output_path)
    output_diagnostics_path = Path(output_diagnostics_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_diagnostics_path.parent.mkdir(parents=True, exist_ok=True)

    if chroma_collection is None or embedding_model is None:
        raise RuntimeError("RAG database not initialized; init_rag_resources() must be called before run_test_set.")

    logger.info(f"EXAMPLE-GUIDED LLM SCORING ARCHITECTURE - TEST SET")

    logger.info(f"Loading test scenarios from: {test_csv_path}")

    scenarios = []
    df = read_table_clean(
        test_csv_path,
        keep_str_cols=["alternative_1", "alternative_2", "alternative_3"],
    )
    required_cols = ['question', 'decision_type', 'alternative_1', 'alternative_2', 'alternative_3']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f" Missing required columns: {missing_cols}")

    for _, row in df.iterrows():
        scenarios.append(row.to_dict())

    logger.info(f"OK Loaded {len(scenarios)} test scenarios")
    logger.info(f"  Decision types: {set([s.get('decision_type', 'UNKNOWN') for s in scenarios])}\n")

    # Run through all scenarios
    all_results = []
    cumulative_diagnostics = {
        'total_scenarios': len(scenarios),
        'total_api_calls': 0,
        'total_latency_ms': 0.0,
        'total_tokens_input': 0,
        'total_tokens_output': 0,
        'successful_calls': 0,
        'failed_calls': 0,
        'successful_scenarios': 0,
        'failed_scenarios': 0,
        **_init_failure_counters()
    }
    for i, scenario in enumerate(scenarios):
        logger.info(f"\n[{i + 1}/{len(scenarios)}] Processing: {scenario.get('question', 'N/A')[:60]}...")

        try:
            result = run_scenario(scenario)
        except Exception as e:
            logger.info(f"  Scenario crashed and was marked failed: {e}")
            fallback_alternatives = [
                scenario.get('alternative_1', ''),
                scenario.get('alternative_2', ''),
                scenario.get('alternative_3', '')
            ]
            result = {
                'scenario': scenario.get('question', 'N/A'),
                'alternatives_scores': [
                    {
                        'alternative': alt,
                        'scores': {
                            'energy_cost': None,
                            'environmental': None,
                            'comfort': None,
                            'practicality': None
                        },
                        'failed': True
                    }
                    for alt in fallback_alternatives
                ],
                'ranking_result': {
                    'ranked_alternatives': [],
                    'ranks': [SENTINEL_VALUE, SENTINEL_VALUE, SENTINEL_VALUE],
                    'weighted_scores': [SENTINEL_FLOAT, SENTINEL_FLOAT, SENTINEL_FLOAT]
                },
                'diagnostics': {
                    'api_calls': 0,
                    'total_tokens_input': 0,
                    'total_tokens_output': 0,
                    'total_latency_ms': 0.0,
                    'successful_calls': 0,
                    'failed_calls': len(fallback_alternatives),
                    'scenario_failed': True,
                    'scenario_error': str(e),
                    **_init_failure_counters()
                }
            }

        all_results.append(result)

        # Roll the diagnostics up together
        diag = result['diagnostics']
        cumulative_diagnostics['total_api_calls'] += diag['api_calls']
        cumulative_diagnostics['total_tokens_input'] += diag['total_tokens_input']
        cumulative_diagnostics['total_tokens_output'] += diag['total_tokens_output']
        cumulative_diagnostics['total_latency_ms'] += diag['total_latency_ms']
        cumulative_diagnostics['successful_calls'] += diag['successful_calls']
        cumulative_diagnostics['failed_calls'] += diag['failed_calls']
        for counter_key in RAG_FAILURE_COUNTER_KEYS:
            cumulative_diagnostics[counter_key] += diag.get(counter_key, 0)
        if diag.get('scenario_failed', False):
            cumulative_diagnostics['failed_scenarios'] += 1
        else:
            cumulative_diagnostics['successful_scenarios'] += 1

    cumulative_diagnostics['avg_latency_ms'] = (
        cumulative_diagnostics['total_latency_ms'] /
        max(cumulative_diagnostics['total_api_calls'], 1)
    )
    cumulative_diagnostics['success_rate'] = (
            cumulative_diagnostics['successful_scenarios'] /
            max(cumulative_diagnostics['total_scenarios'], 1)
    )
    # Write the results to the output file
    logger.info(f"\nSaving results to: {output_csv_path}")

    # Build rows then write to Excel
    rows = []
    for scenario_id, result in enumerate(all_results, 1):
        question = result['scenario']
        decision_type = scenarios[scenario_id - 1].get('decision_type', 'UNKNOWN')
        location = scenarios[scenario_id - 1].get('location', 'N/A')
        outdoor_temp = scenarios[scenario_id - 1].get('outdoor_temp', '')
        appliance_age = scenarios[scenario_id - 1].get('appliance_age', '')
        flow_rate = scenarios[scenario_id - 1].get('flow_rate', '')
        scenario_failed = result.get('diagnostics', {}).get('scenario_failed', False)

        ranks = result['ranking_result']['ranks']
        weighted_scores = result['ranking_result']['weighted_scores']

        for alt_idx, alt_data in enumerate(result['alternatives_scores']):
            alternative = alt_data['alternative']
            scores = alt_data['scores']

            if scenario_failed:
                energy_cost = SENTINEL_VALUE
                environmental = SENTINEL_VALUE
                comfort = SENTINEL_VALUE
                practicality = SENTINEL_VALUE
                rank = SENTINEL_VALUE
                weighted_score = SENTINEL_FLOAT
            else:
                energy_cost = scores['energy_cost']
                environmental = scores['environmental']
                comfort = scores['comfort']
                practicality = scores['practicality']
                rank = ranks[alt_idx]
                weighted_score = weighted_scores[alt_idx]

            rows.append({
                'scenario_id': scenario_id,
                'question': question,
                'location': location,
                'decision_type': decision_type,
                'outdoor_temp': outdoor_temp,
                'appliance_age': appliance_age,
                'flow_rate': flow_rate,
                'alternative': alternative,
                'energy_cost': energy_cost,
                'environmental': environmental,
                'comfort': comfort,
                'practicality': practicality,
                'rank': rank,
                'weighted_score': weighted_score
            })

    _atomic_write_xlsx(pd.DataFrame(rows, columns=RAG_RESULT_FIELDNAMES), output_csv_path)
    logger.info(f"OK Results saved to: {output_csv_path}")

    _atomic_write_json(cumulative_diagnostics, output_diagnostics_path)
    logger.info(f"OK Diagnostics saved to: {output_diagnostics_path}")

    logger.info(f"EXAMPLE-GUIDED LLM SCORING TEST COMPLETE")
    logger.info(f"Total scenarios: {cumulative_diagnostics['total_scenarios']}")
    logger.info(f"Total API calls: {cumulative_diagnostics['total_api_calls']}")
    logger.info(f"Successful calls: {cumulative_diagnostics['successful_calls']}")
    logger.info(f"Failed calls: {cumulative_diagnostics['failed_calls']}")
    logger.info(f"Total tokens (input): {cumulative_diagnostics['total_tokens_input']}")
    logger.info(f"Total tokens (output): {cumulative_diagnostics['total_tokens_output']}")
    logger.info(f"Average latency: {cumulative_diagnostics['avg_latency_ms']:.0f} ms")
    logger.info(f"Success rate: {cumulative_diagnostics['success_rate']:.1%}")

    return cumulative_diagnostics

def run_multi_and_aggregate(test_csv_path: str, base_output_csv: str,
                            base_diagnostics_path: str) -> None:
    """Run the benchmark N_RUNS times and average the per-run xlsx outputs.

    Resume-aware: a per-run xlsx that already exists, has size > 0, has no
    leftover .tmp sibling, and reads as a non-empty DataFrame is treated as
    a completed run and skipped. Any other state triggers a re-run.

    RAG resources (Chroma collection + embedding model) are initialized once
    up-front. If they are still healthy across runs, no re-init happens. If a
    later run finds them in a missing state (e.g. a transient error nuked the
    globals), `_ensure_rag_initialized` lazily reloads them before launching.
    """
    base = Path(base_output_csv)
    base_diag = Path(base_diagnostics_path)
    run_paths = []
    skipped_runs = []

    if chroma_collection is None or embedding_model is None:
        init_rag_resources()

    for run_idx in range(1, N_RUNS + 1):
        run_path = base.with_name(f"{base.stem}_run_{run_idx:02d}{base.suffix}")
        diag_path = base_diag.with_name(f"{base_diag.stem}_run_{run_idx:02d}{base_diag.suffix}")
        if _is_complete_run_file(run_path):
            logger.info(f"--- Run {run_idx}/{N_RUNS}: resuming from {run_path.name} ---")
            run_paths.append(run_path)
            skipped_runs.append(run_idx)
            continue
        if chroma_collection is None or embedding_model is None:
            init_rag_resources()
        logger.info(f"--- Run {run_idx}/{N_RUNS} -> {run_path.name} ---")
        try:
            run_test_set(str(test_csv_path), str(run_path), str(diag_path))
            run_paths.append(run_path)
        except Exception as e:
            logger.info(f"ERROR: Run {run_idx} failed and will be excluded from aggregation: {e}")

    if skipped_runs:
        logger.info(f"Resumed {len(skipped_runs)} existing run(s): {skipped_runs}")

    n_runs = len(run_paths)
    if n_runs == 0:
        logger.info("ERROR: All runs failed. No aggregation possible.")
        return
    if n_runs < N_RUNS:
        logger.info(
            f"WARNING: Only {n_runs}/{N_RUNS} runs completed. "
            f"Aggregating over {n_runs} runs."
        )
    logger.info(f"{n_runs}/{N_RUNS} runs complete. Aggregating scores...")

    valid_run_paths = []
    run_dfs = []
    for p in run_paths:
        try:
            run_dfs.append(read_table_clean(p))
            valid_run_paths.append(p)
        except Exception as e:
            logger.info(f"WARNING: Could not read {p.name}, skipping from aggregation: {e}")
    if len(run_dfs) == 0:
        logger.info("ERROR: No run files could be read. Aggregation aborted.")
        return
    n_readable = len(run_dfs)
    if n_readable < n_runs:
        logger.info(f"WARNING: Aggregating over {n_readable}/{n_runs} readable runs.")
    combined = pd.concat(run_dfs, ignore_index=True)
    combined = combined.drop(columns=["rank", "weighted_score"], errors="ignore")

    CRITERIA_COLS = ["energy_cost", "environmental", "comfort", "practicality"]

    for c in CRITERIA_COLS:
        combined[c] = pd.to_numeric(combined[c], errors="coerce")
        # Treat exact sentinel float as a failed row
        combined.loc[combined[c] == SENTINEL_FLOAT, c] = np.nan

    GROUP_KEYS = ["scenario_id", "alternative"]
    META_COLS = [
        "decision_type", "question", "location",
        "outdoor_temp", "appliance_age", "flow_rate",
    ]

    # Count how many runs contributed a non-NaN value per (scenario, alternative)
    n_valid_runs = combined.groupby(GROUP_KEYS)[CRITERIA_COLS[0]].apply(
        lambda s: s.notna().sum()
    ).reset_index(name="n_successful_runs")

    avg_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].mean()
    std_criteria = combined.groupby(GROUP_KEYS, as_index=False)[CRITERIA_COLS].std()
    avg_meta = combined.groupby(GROUP_KEYS, as_index=False)[META_COLS].first()

    avg = avg_criteria.merge(avg_meta, on=GROUP_KEYS)
    avg = avg.merge(n_valid_runs, on=GROUP_KEYS)
    avg["n_runs"] = n_readable
    avg["n_failed_runs"] = avg["n_runs"] - avg["n_successful_runs"]

    std_criteria = std_criteria.rename(columns={c: f"{c}_std" for c in CRITERIA_COLS})
    stats_df = avg.merge(std_criteria, on=GROUP_KEYS)

    if n_readable == 1:
        logger.info("WARNING: Only 1 run aggregated — std columns will be NaN (undefined for N=1).")
        for c in CRITERIA_COLS:
            col = f"{c}_std"
            if col in stats_df.columns:
                stats_df[col] = "N/A (N=1)"

    # Put 1928 back anywhere every run failed for that alternative
    for c in CRITERIA_COLS:
        avg[c] = avg[c].fillna(SENTINEL_FLOAT)

    # Re-rank each scenario using the averaged scores
    avg["rank"] = int(SENTINEL_VALUE)
    avg["weighted_score"] = float(SENTINEL_FLOAT)

    for sid in avg["scenario_id"].unique():
        sc_mask = avg["scenario_id"] == sid
        sc = avg[sc_mask]
        valid_idx = sc.index[~sc[CRITERIA_COLS].eq(SENTINEL_FLOAT).any(axis=1)]
        if len(valid_idx) > 0:
            ws = (
                avg.loc[valid_idx, "energy_cost"] * CRITERION_WEIGHTS["energy_cost"] +
                avg.loc[valid_idx, "environmental"] * CRITERION_WEIGHTS["environmental"] +
                avg.loc[valid_idx, "comfort"] * CRITERION_WEIGHTS["comfort"] +
                avg.loc[valid_idx, "practicality"] * CRITERION_WEIGHTS["practicality"]
            )
            avg.loc[valid_idx, "weighted_score"] = ws
            sub = avg.loc[valid_idx].copy()
            sub["weighted_score"] = ws
            sort_cols = ["weighted_score"] + TIE_BREAK_PRIORITY
            # Stable sort descending on all sorting columns
            sub_sorted = sub.sort_values(sort_cols, ascending=[False] * len(sort_cols), kind="mergesort")
            avg.loc[sub_sorted.index, "rank"] = list(range(1, len(sub_sorted) + 1))

    col_order = [
        "scenario_id", "question", "location", "decision_type", "outdoor_temp",
        "appliance_age", "flow_rate", "alternative",
        "energy_cost", "environmental", "comfort", "practicality",
        "rank", "weighted_score",
        "n_runs", "n_successful_runs", "n_failed_runs",
    ]
    _atomic_write_xlsx(avg.reindex(columns=col_order), base_output_csv)
    logger.info(f"Averaged results ({n_readable} runs) saved to {base_output_csv}")

    stats_path = base.with_name(f"{base.stem}_stats{base.suffix}")
    _atomic_write_xlsx(stats_df, stats_path)
    logger.info(f"Score statistics saved to {stats_path}")


def main():
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found in environment variables!")
    if not TEST_SCENARIOS.exists():
        raise FileNotFoundError(f"Test scenarios file not found: {TEST_SCENARIOS}")

    logger.info("Starting Example-Guided LLM Scoring Architecture Test...")
    logger.info(f"Model: {API_CONFIG['model']}")
    logger.info(f"Temperature: {API_CONFIG['temperature']}")

    output_dir = PROJECT_ROOT / get_output_folder_for_model_id(API_CONFIG["model"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "Example-Guided_LLM_Scoring_results.xlsx"
    output_diagnostics = output_dir / "Example-Guided_LLM_Scoring_results_diagnostics.json"

    run_multi_and_aggregate(
        test_csv_path=str(TEST_SCENARIOS),
        base_output_csv=str(output_csv),
        base_diagnostics_path=str(output_diagnostics),
    )


if __name__ == "__main__":
    main()
