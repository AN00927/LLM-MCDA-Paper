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

from model_config import CRITERION_WEIGHTS, get_model_id, get_output_folder, N_RUNS
from sentinel_utils import (
    _atomic_write_json,
    _atomic_write_xlsx,
    _is_complete_run_file,
    has_sentinel_scores,
    read_table_clean,
)

TEST_SCENARIOS = PROJECT_ROOT / "Scenario Files" / "TestScenarios.xlsx"
OUTPUT_DIR = PROJECT_ROOT / get_output_folder()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables!")

MODEL_ID = get_model_id()
TEMPERATURE = 0.3

CHROMA_DB_PATH = PROJECT_ROOT / 'chroma_rag_db'
COLLECTION_NAME = 'mcda_scenarios'
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
RETRIEVE_K = 3

# Must match BuildRAG.RAG_SCHEMA_VERSION. Bump in lockstep when metadata fields change.
EXPECTED_RAG_SCHEMA_VERSION = 2
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

MAX_RETRIES = 5
RETRY_DELAY = 2
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}

OUTPUT_CSV = OUTPUT_DIR / "rag_results.xlsx"
OUTPUT_DIAGNOSTICS = OUTPUT_DIR / "rag_results_diagnostics.json"

RAG_FAILURE_COUNTER_KEYS = [
    "failed_malformed_json",
    "failed_missing_score",
    "failed_out_of_bounds",
    "failed_invalid_score_type",
    "failed_api_exhausted",
    "failed_unknown"
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


def query_openrouter(messages: List[Dict], model: str = MODEL_ID,
                     temperature: float = TEMPERATURE) -> Tuple[str, Dict]:
    """Query openrouter."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }

    last_error = None
    response = None

    attempt = 0
    retry_forever = MAX_RETRIES <= 0

    while True:
        attempt += 1
        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            latency = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                usage = data.get('usage', {})
                diagnostics = {
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                    'latency_ms': latency *1000,
                    'model': model
                }

                return content, diagnostics
            else:
                last_error = f"Status {response.status_code}: {response.text}"
                if _is_transient_http_status(response.status_code):
                    logger.info(f"  Transient API error (attempt {attempt}): {response.status_code}")
                else:
                    logger.info(f"  API error (attempt {attempt}): {response.status_code}")

                if not retry_forever and attempt >= MAX_RETRIES:
                    break

                time.sleep(min(RETRY_DELAY * (2 ** min(attempt - 1, 5)), 60))
                continue

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            logger.info(f"  Request failed (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_DELAY * (2 ** min(attempt - 1, 5)), 60))
            continue

        except ValueError as e:
            last_error = f"Invalid API JSON envelope: {e}"
            logger.info(f"  Invalid API JSON envelope (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_DELAY * (2 ** min(attempt - 1, 5)), 60))
            continue

    # Retries exhausted — raise so caller can map to failed_api_exhausted.
    raise Exception(f"failed_api_exhausted: Failed after {MAX_RETRIES} attempts. Last error: {last_error}")

def build_system_prompt() -> str:
    """Build system prompt.

    Numeric calibration anchors are intentionally omitted because RAG already
    supplies scored in-context examples.
    """
    return """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
    You consistently utilize all information given in the scenario context. You must take into account all factors and how they may affect all 4 criteria.
Your task is to score alternatives on four criteria:
1. Energy Cost (0-10): Lower energy costs = higher score
2. Environmental Impact (0-10): Lower emissions = higher score
3. Comfort (0-10): Higher user comfort = higher score
4. Practicality (0-10): Easier to implement/maintain = higher score

Scoring guidelines:
- Use the inclusive 0-10 scale (0.0 <= score <= 10.0; do not exceed 10.0 or go below 0.0)
- Consider tradeoffs between criteria
- Base scores on engineering principles, behavioral research, and practical constraints
- Be consistent across similar scenarios

Return ONLY a JSON object with four numeric scores (0-10). There should be no other text in your response, even for reasoning:
{"energy_cost": X, "environmental": X, "comfort": X, "practicality": X}"""


def format_scenario_text_for_retrieval(scenario: Dict) -> Tuple[str, str]:
    """Format scenario text for retrieval."""
    decision_type = scenario.get('Decision Type', 'HVAC')

    if decision_type == 'HVAC':
        scenario_text = (
            f"{scenario.get('outdoor_temp', 'N/A')} deg F outdoor, "
            f"{scenario.get('Insulation', 'N/A')} insulation, "
            f"{scenario.get('square_footage', 'N/A')} sqft, "
            f"{scenario.get('household_size', 'N/A')} occupants, "
            f"{scenario.get('Housing Type', 'N/A')}"
        )
    elif decision_type == 'Appliance':
        scenario_text = (
            f"{scenario.get('Question', 'N/A')}, "
            f"{scenario.get('household_size', 'N/A')} occupants, "
            f"{scenario.get('Housing Type', 'N/A')}, "
            f"appliance age range: {scenario.get('Appliance Age', 'N/A')}, "
            f"budget ${scenario.get('Utility Budget', 'N/A')}/month"
        )
    elif decision_type == 'Shower':
        scenario_text = (
            f"{scenario.get('Flow rate', 'N/A')} showerhead, "
            f"{scenario.get('outdoor_temp', 'N/A')} deg F outdoor, "
            f"{scenario.get('household_size', 'N/A')} occupants, "
            f"{scenario.get('Housing Type', 'N/A')}, "
            f"budget ${scenario.get('Utility Budget', 'N/A')}/month"
        )
    else:
        scenario_text = scenario.get('Question', f'Unknown decision type: {decision_type}')
        logger.info(f"   Warning: Unknown decision type '{decision_type}'")

    return scenario_text, decision_type

def retrieve_similar_scenarios(scenario: Dict, k: int = RETRIEVE_K) -> List[Dict]:
    """Retrieve similar scenarios."""
    if chroma_collection is None or embedding_model is None:
        logger.info("   RAG database not available, skipping retrieval")
        return []

    # Turn the scenario into plain text
    scenario_text, decision_type = format_scenario_text_for_retrieval(scenario)

    # Make the embedding
    query_embedding = embedding_model.encode(scenario_text).tolist()

    # Pull matches from the database, filtered by decision type
    try:
        results = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where={"decision_type": decision_type}
        )
    except Exception as e:
        logger.info(f"   Retrieval error: {e}")
        return []

    retrieved = []
    if results['ids'] and len(results['ids'][0]) > 0:
        for doc_id, doc_text, metadata in zip(
                results['ids'][0],
                results['documents'][0],
                results['metadatas'][0]
        ):
            # B4 fix: default to None (not 0.0) so missing metadata is visible
            # rather than silently anchoring the LLM at zero.
            retrieved.append({
                'id': doc_id,
                'text': doc_text,
                'decision_type': metadata.get('decision_type', 'Unknown'),
                'question': metadata.get('question', 'N/A'),
                'alternatives': [
                    {
                        'name': metadata.get('alt1', 'N/A'),
                        'scores': {
                            'energy_cost': metadata.get('alt1_energy_cost'),
                            'environmental': metadata.get('alt1_environmental'),
                            'comfort': metadata.get('alt1_comfort'),
                            'practicality': metadata.get('alt1_practicality')
                        }
                    },
                    {
                        'name': metadata.get('alt2', 'N/A'),
                        'scores': {
                            'energy_cost': metadata.get('alt2_energy_cost'),
                            'environmental': metadata.get('alt2_environmental'),
                            'comfort': metadata.get('alt2_comfort'),
                            'practicality': metadata.get('alt2_practicality')
                        }
                    },
                    {
                        'name': metadata.get('alt3', 'N/A'),
                        'scores': {
                            'energy_cost': metadata.get('alt3_energy_cost'),
                            'environmental': metadata.get('alt3_environmental'),
                            'comfort': metadata.get('alt3_comfort'),
                            'practicality': metadata.get('alt3_practicality')
                        }
                    }
                ]
            })

    return retrieved


def format_rag_context(retrieved_scenarios: List[Dict]) -> str:
    """Format rag context."""
    if not retrieved_scenarios:
        return ""

    context = "RELEVANT SIMILAR SCENARIOS WITH EXPERT SCORES:\n\n"
    skipped_alts = 0

    for i, scenario in enumerate(retrieved_scenarios, 1):
        context += f"Example {i}: {scenario['text']}\n"
        context += f"  Question: {scenario['question']}\n"

        for alt in scenario['alternatives']:
            scores = alt['scores']
            # B4 fix: skip alternatives where any criterion score is missing
            # (None) — formatting them would either crash on :.1f or silently
            # anchor the LLM at 0.0. Indicates RAG schema drift.
            if any(scores.get(c) is None for c in ('energy_cost', 'environmental', 'comfort', 'practicality')):
                skipped_alts += 1
                continue
            context += (
                f"  * {alt['name']}: "
                f"Energy Cost: {scores['energy_cost']:.1f}/10, "
                f"Environmental: {scores['environmental']:.1f}/10, "
                f"Comfort: {scores['comfort']:.1f}/10, "
                f"Practicality: {scores['practicality']:.1f}/10\n"
            )
        context += "\n"

    if skipped_alts > 0:
        logger.info(f"   WARNING: skipped {skipped_alts} retrieved alternative(s) with missing scores. "
              f"Likely RAG metadata schema drift — re-run BuildRAG.")

    context += "Use these examples as reference, but score based on the specific scenario below.\n"
    context += "Just because a reference scenario has an extreme value does not mean that the scenario you are analyzing has the same characteristics.\n"

    return context

def build_user_prompt_with_rag(scenario: Dict, alternative: str, rag_context: str) -> str:
    prompt = rag_context
    prompt += f'Score this alternative: "{alternative}"\n\n'
    prompt += f'For the decision: "{scenario.get("Question", "N/A")}"\n\n'
    prompt += "SCENARIO CONTEXT:\n"
    prompt += f"- Location: {scenario.get('Location', 'N/A')}\n"

    decision_type = scenario.get('Decision Type', 'HVAC')

    if decision_type == 'HVAC':
        prompt += (
            f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
            f"- Square Footage: {scenario.get('square_footage', 'N/A')} sqft\n"
            f"- Insulation: {scenario.get('Insulation', 'N/A')}\n"
            f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
            f"- House Age: {scenario.get('hvac_age', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"
        )

    elif decision_type == 'Appliance':
        prompt += (
            f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"
            f"- Appliance Age Range: {scenario.get('Appliance Age', 'N/A')} years\n"
        )

    elif decision_type == 'Shower':
        prompt += (
            f"- Outdoor Temp: {scenario.get('outdoor_temp', 'N/A')} deg F\n"
            f"- Household Size: {scenario.get('household_size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
            f"- Flow Rate: {scenario.get('Flow rate', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"
        )

    prompt += "\nProvide scores (0-10) for all 4 criteria using the calibrations in the system prompt.\n"
    prompt += "Consider how this specific alternative performs given the scenario context.\n"

    return prompt

def parse_llm_scores(response_text: str) -> Tuple[Dict[str, float], List[str]]:
    """Parse llm scores."""
    try:
        # Claude sometimes wraps JSON in code fences, so let's peel that off
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        scores = json.loads(text)

        validated_scores = {}
        validation_failed = False
        validation_failure_types = set()
        for criterion in ['energy_cost', 'environmental', 'comfort', 'practicality']:
            if criterion not in scores:
                logger.info(f"   Missing score for {criterion}; using sentinel 1928")
                validated_scores[criterion] = 1928
                validation_failed = True
                validation_failure_types.add('failed_missing_score')
                continue

            raw_score = scores[criterion]

            if isinstance(raw_score, (int, float)):
                raw_value = float(raw_score)
                if 0.0 <= raw_value <= 10.0:
                    validated_scores[criterion] = raw_value
                else:
                    logger.info(f"   Out-of-range score for {criterion}: {raw_value}; using sentinel 1928")
                    validated_scores[criterion] = 1928
                    validation_failed = True
                    validation_failure_types.add('failed_out_of_bounds')
            else:
                logger.info(f"   Invalid score type for {criterion}: {raw_score}; using sentinel 1928")
                validated_scores[criterion] = 1928
                validation_failed = True
                validation_failure_types.add('failed_invalid_score_type')

        if validation_failed:
            validated_scores['_failed'] = True
            return validated_scores, sorted(validation_failure_types) if validation_failure_types else ['failed_unknown']

        return validated_scores, []
    except (json.JSONDecodeError, ValueError) as e:
        logger.info("   Could not parse scores; failed")
        failed_scores = {
            'energy_cost': 1928,
            'environmental': 1928,
            'comfort': 1928,
            'practicality': 1928,
            '_failed': True
        }
        return failed_scores, ['failed_malformed_json']


def score_alternative_with_rag(scenario: Dict, alternative: str) -> Tuple[Dict, Dict]:
    """Score alternative with rag."""
    retrieved = retrieve_similar_scenarios(scenario, k=RETRIEVE_K)

    rag_context = format_rag_context(retrieved)

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt_with_rag(scenario, alternative, rag_context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response_text, diagnostics = query_openrouter(messages)

        scores, failure_types = parse_llm_scores(response_text)
        diagnostics['success'] = not scores.get('_failed', False)
        diagnostics['failure_types'] = failure_types if scores.get('_failed', False) else []
    except Exception as e:
        logger.info(f"   Scoring failed for alternative '{alternative}': {e}")
        scores = {
            'energy_cost': 1928,
            'environmental': 1928,
            'comfort': 1928,
            'practicality': 1928
        }
        # Distinguish API/network exhaustion from genuine code/parse errors.
        error_text = str(e).lower()
        if 'failed_api_exhausted' in error_text:
            failure_type = 'failed_api_exhausted'
        else:
            failure_type = 'failed_unknown'
        diagnostics = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'latency_ms': 0.0,
            'model': MODEL_ID,
            'success': False,
            'error': str(e),
            'failure_types': [failure_type]
        }

    # Add the RAG bits to diagnostics
    diagnostics['rag_retrieved_count'] = len(retrieved)
    diagnostics['rag_context_length'] = len(rag_context)

    return scores, diagnostics


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    """Apply mavt ranking."""
    alternatives = [ad['alternative'] for ad in alternatives_scores]
    n = len(alternatives)

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
            'ranks': [1928] * n,
            'weighted_scores': [1928] * n
        }

    valid_pairs_sorted = sorted(valid_pairs, key=lambda x: x[1], reverse=True)
    ranked_alternatives = [alternatives[idx] for idx, _ in valid_pairs_sorted]

    # Keep the indices lined up with the original alternatives
    ranks = [1928] * n
    weighted_scores = [1928] * n
    for rank_position, (input_idx, ws) in enumerate(valid_pairs_sorted):
        ranks[input_idx] = rank_position + 1
        weighted_scores[input_idx] = ws

    return {
        'ranked_alternatives': ranked_alternatives,
        'ranks': ranks,
        'weighted_scores': weighted_scores
    }


def run_scenario(scenario: Dict) -> Dict:
    """Run scenario."""
    logger.info(f"SCENARIO: {scenario.get('Question', 'N/A')}")

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
        alt_key = f'Alternative {i}'
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
            failure_types = diagnostics.get('failure_types') or ['failed_unknown']
            total_diagnostics['failed_calls'] += 1
            _increment_failure_counters(total_diagnostics, failure_types)
            alternatives_scores.append({
                'alternative': alternative,
                'scores': {'energy_cost': None, 'environmental': None, 'comfort': None, 'practicality': None},
                'failed': True
            })
            continue

        logger.info(f"  Scores: Energy={scores['energy_cost']:.1f}, "
              f"Env={scores['environmental']:.1f}, "
              f"Comfort={scores['comfort']:.1f}, "
              f"Pract={scores['practicality']:.1f}")
        logger.info(f"  Retrieved {diagnostics.get('rag_retrieved_count', 0)} similar scenarios")

        alternatives_scores.append({
            'alternative': alternative,
            'scores': scores
        })

        if diagnostics.get('success', False):
            total_diagnostics['successful_calls'] += 1
        else:
            failure_types = diagnostics.get('failure_types') or ['failed_unknown']
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
        'scenario': scenario.get('Question', 'N/A'),
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


def _ensure_rag_initialized() -> None:
    """Init RAG resources once for the multi-run pass; reload if a prior init was lost."""
    if chroma_collection is None or embedding_model is None:
        init_rag_resources()


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

    logger.info(f"RAG-ENHANCED MCDA ARCHITECTURE - TEST SET")

    logger.info(f"Loading test scenarios from: {test_csv_path}")

    scenarios = []
    df = read_table_clean(
        test_csv_path,
        keep_str_cols=["Alternative 1", "Alternative 2", "Alternative 3"],
    )
    required_cols = ['Question', 'Decision Type', 'Alternative 1', 'Alternative 2', 'Alternative 3']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f" Missing required columns: {missing_cols}")

    for _, row in df.iterrows():
        scenarios.append(row.to_dict())

    logger.info(f"OK Loaded {len(scenarios)} test scenarios")
    logger.info(f"  Decision types: {set([s.get('Decision Type', 'UNKNOWN') for s in scenarios])}\n")

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
        logger.info(f"\n[{i + 1}/{len(scenarios)}] Processing: {scenario.get('Question', 'N/A')[:60]}...")

        try:
            result = run_scenario(scenario)
        except Exception as e:
            logger.info(f"  Scenario crashed and was marked failed: {e}")
            fallback_alternatives = [
                scenario.get('Alternative 1', ''),
                scenario.get('Alternative 2', ''),
                scenario.get('Alternative 3', '')
            ]
            result = {
                'scenario': scenario.get('Question', 'N/A'),
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
                    'ranks': [1928, 1928, 1928],
                    'weighted_scores': [1928, 1928, 1928]
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
        decision_type = scenarios[scenario_id - 1].get('Decision Type', 'UNKNOWN')
        location = scenarios[scenario_id - 1].get('Location', 'N/A')
        outdoor_temp = scenarios[scenario_id - 1].get('outdoor_temp', '')
        appliance_age = scenarios[scenario_id - 1].get('Appliance Age', '')
        flow_rate = scenarios[scenario_id - 1].get('Flow rate', '')
        scenario_failed = result.get('diagnostics', {}).get('scenario_failed', False)

        ranks = result['ranking_result']['ranks']
        weighted_scores = result['ranking_result']['weighted_scores']

        for alt_idx, alt_data in enumerate(result['alternatives_scores']):
            alternative = alt_data['alternative']
            scores = alt_data['scores']

            if scenario_failed:
                energy_cost = 1928
                environmental = 1928
                comfort = 1928
                practicality = 1928
                rank = 1928
                weighted_score = 1928
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

    logger.info(f"RAG-ENHANCED TEST COMPLETE")
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

    _ensure_rag_initialized()

    for run_idx in range(1, N_RUNS + 1):
        run_path = base.with_name(f"{base.stem}_run_{run_idx:02d}{base.suffix}")
        diag_path = base_diag.with_name(f"{base_diag.stem}_run_{run_idx:02d}{base_diag.suffix}")
        if _is_complete_run_file(run_path):
            logger.info(f"--- Run {run_idx}/{N_RUNS}: resuming from {run_path.name} ---")
            run_paths.append(run_path)
            skipped_runs.append(run_idx)
            continue
        _ensure_rag_initialized()
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
    SENTINEL = 1928.0

    # Use pd.to_numeric handles string "1928" and malformed values
    for c in CRITERIA_COLS:
        combined[c] = pd.to_numeric(combined[c], errors="coerce")
        # Treat exact sentinel float as a failed row
        combined.loc[combined[c] == SENTINEL, c] = np.nan

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

    # When N=1, pandas std returns NaN — annotate clearly in the stats output
    if n_readable == 1:
        logger.info("WARNING: Only 1 run aggregated — std columns will be NaN (undefined for N=1).")
        for c in CRITERIA_COLS:
            col = f"{c}_std"
            if col in stats_df.columns:
                stats_df[col] = "N/A (N=1)"

    # Put 1928 back anywhere every run failed for that alternative
    for c in CRITERIA_COLS:
        avg[c] = avg[c].fillna(SENTINEL)

    # Re-rank each scenario using the averaged scores
    avg["rank"] = int(SENTINEL)
    avg["weighted_score"] = float(SENTINEL)

    for sid in avg["scenario_id"].unique():
        sc_mask = avg["scenario_id"] == sid
        sc = avg[sc_mask]
        valid_idx = sc.index[~sc[CRITERIA_COLS].eq(SENTINEL).any(axis=1)]
        if len(valid_idx) > 0:
            ws = (
                avg.loc[valid_idx, "energy_cost"] * CRITERION_WEIGHTS["energy_cost"] +
                avg.loc[valid_idx, "environmental"] * CRITERION_WEIGHTS["environmental"] +
                avg.loc[valid_idx, "comfort"] * CRITERION_WEIGHTS["comfort"] +
                avg.loc[valid_idx, "practicality"] * CRITERION_WEIGHTS["practicality"]
            )
            avg.loc[valid_idx, "weighted_score"] = ws
            avg.loc[valid_idx, "rank"] = ws.rank(ascending=False, method="min").astype(int)

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

    run_multi_and_aggregate(
        test_csv_path=str(TEST_SCENARIOS),
        base_output_csv=str(OUTPUT_CSV),
        base_diagnostics_path=str(OUTPUT_DIAGNOSTICS),
    )


if __name__ == "__main__":
    main()
