import os
import sys
import json
import csv
import requests
import time
from typing import Dict, List, Tuple
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import CRITERION_WEIGHTS, get_model_id, get_output_folder
from sentinel_utils import has_sentinel_scores

TEST_SCENARIOS_CSV = PROJECT_ROOT / "Scenario Files" / "TestScenarios.csv"
OUTPUT_DIR = PROJECT_ROOT / get_output_folder()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables!")

MODEL_ID = get_model_id()
TEMPERATURE = 0.3

CHROMA_DB_PATH = PROJECT_ROOT / 'chroma_rag_db'
COLLECTION_NAME = 'mcda_scenarios'
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
RETRIEVE_K = 3 

MAX_RETRIES = 5
RETRY_DELAY = 2
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}

OUTPUT_CSV = OUTPUT_DIR / "RAGResults.csv"
OUTPUT_DIAGNOSTICS = OUTPUT_DIR / "RAGDiagnostics.json"

RAG_FAILURE_COUNTER_KEYS = [
    "failed_malformed_json",
    "failed_missing_score",
    "failed_out_of_bounds",
    "failed_invalid_score_type",
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

print("Loading ChromaDB and embedding model")
try:
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    chroma_collection = chroma_client.get_collection(COLLECTION_NAME)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"OK Loaded RAG database: {chroma_collection.count()} scenarios available")
except Exception as e:
    print(f" WARNING: Could not load RAG database: {e}")
    print("  Make sure to run Miscellaneous Files/BuildRAG.py first.")
    chroma_collection = None
    embedding_model = None


def query_openrouter(messages: List[Dict], model: str = MODEL_ID,
                     temperature: float = TEMPERATURE) -> Tuple[str, Dict]:
    """
    Returns:
        (response_text, diagnostics_dict)
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
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
                    print(f"  Transient API error (attempt {attempt}): {response.status_code}")
                else:
                    print(f"  API error (attempt {attempt}): {response.status_code}")

                if not retry_forever and attempt >= MAX_RETRIES:
                    break

                time.sleep(min(RETRY_DELAY * (2 ** min(attempt - 1, 5)), 60))
                continue

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            print(f"  Request failed (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_DELAY * (2 ** min(attempt - 1, 5)), 60))
            continue

        except ValueError as e:
            last_error = f"Invalid API JSON envelope: {e}"
            print(f"  Invalid API JSON envelope (attempt {attempt}): {e}")
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_DELAY * (2 ** min(attempt - 1, 5)), 60))
            continue

    # Only reachable when finite retries are exhausted.
    raise Exception(f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}")

def build_system_prompt() -> str:
    """
    Build system prompt for MCDA scoring.
    """
    return """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
    You consistently utilize all information given in the scenario context. You must take into account all factors and how they may affect all 4 criteria.
Your task is to score alternatives on four criteria:
1. Energy Cost (0-10): Lower energy costs = higher score
2. Environmental Impact (0-10): Lower emissions = higher score
3. Comfort (0-10): Higher user comfort = higher score
4. Practicality (0-10): Easier to implement/maintain = higher score

Scoring guidelines:
- Use the full 0-10 scale
- Consider tradeoffs between criteria
- Base scores on engineering principles, behavioral research, and practical constraints
- Be consistent across similar scenarios

Return ONLY a JSON object with four numeric scores (0-10). There should be no other text in your response, even for reasoning:
{"energy_cost": X, "environmental": X, "comfort": X, "practicality": X}"""


def format_scenario_text_for_retrieval(scenario: Dict) -> Tuple[str, str]:
    """
    Convert scenario to text for RAG retrieval.
    Returns:
        (scenario_text, decision_type)
    """
    # Read decision type from CSV (not keyword detection)
    decision_type = scenario.get('Decision Type', 'HVAC')

    if decision_type == 'HVAC':
        scenario_text = (
            f"{scenario.get('Outdoor Temp', 'N/A')}°F outdoor, "
            f"{scenario.get('Insulation', 'N/A')} insulation, "
            f"{scenario.get('Square Footage', 'N/A')} sqft, "
            f"{scenario.get('Household Size', 'N/A')} occupants, "
            f"{scenario.get('Housing Type', 'N/A')}"
        )
    elif decision_type == 'Appliance':
        scenario_text = (
            f"{scenario.get('Question', 'N/A')}, "
            f"{scenario.get('Household Size', 'N/A')} occupants, "
            f"{scenario.get('Housing Type', 'N/A')}, "
            f"appliance age range: {scenario.get('Appliance Age', 'N/A')}, "
            f"budget ${scenario.get('Utility Budget', 'N/A')}/month"
        )
    elif decision_type == 'Shower':
        scenario_text = (
            f"{scenario.get('Flow rate', 'N/A')} showerhead, "
            f"{scenario.get('Outdoor Temp', 'N/A')}°F outdoor, "
            f"{scenario.get('Household Size', 'N/A')} occupants, "
            f"{scenario.get('Housing Type', 'N/A')}, "
            f"budget ${scenario.get('Utility Budget', 'N/A')}/month"
        )
    else:
        scenario_text = scenario.get('Question', f'Unknown decision type: {decision_type}')
        print(f"   Warning: Unknown decision type '{decision_type}'")

    return scenario_text, decision_type

def retrieve_similar_scenarios(scenario: Dict, k: int = RETRIEVE_K) -> List[Dict]:
    """
    Retrieve k most similar scenarios from RAG database.

    Args:
        scenario: Current test scenario dict
        k: Number of similar scenarios to retrieve

    Returns:
        List of dicts with retrieved scenario info and scores
    """
    if chroma_collection is None or embedding_model is None:
        print("   RAG database not available, skipping retrieval")
        return []

    # Convert scenario to text
    scenario_text, decision_type = format_scenario_text_for_retrieval(scenario)

    # Generate embedding
    query_embedding = embedding_model.encode(scenario_text).tolist()

    # Retrieve from database (filtered by decision type)
    try:
        results = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where={"decision_type": decision_type}
        )
    except Exception as e:
        print(f"   Retrieval error: {e}")
        return []

    retrieved = []
    if results['ids'] and len(results['ids'][0]) > 0:
        for doc_id, doc_text, metadata in zip(
                results['ids'][0],
                results['documents'][0],
                results['metadatas'][0]
        ):
            retrieved.append({
                'id': doc_id,
                'text': doc_text,
                'decision_type': metadata.get('decision_type', 'Unknown'),
                'question': metadata.get('question', 'N/A'),
                'alternatives': [
                    {
                        'name': metadata.get('alt1', 'N/A'),
                        'scores': {
                            'energy_cost': metadata.get('alt1_energy_cost', 0.0),
                            'environmental': metadata.get('alt1_environmental', 0.0),
                            'comfort': metadata.get('alt1_comfort', 0.0),
                            'practicality': metadata.get('alt1_practicality', 0.0)
                        }
                    },
                    {
                        'name': metadata.get('alt2', 'N/A'),
                        'scores': {
                            'energy_cost': metadata.get('alt2_energy_cost', 0.0),
                            'environmental': metadata.get('alt2_environmental', 0.0),
                            'comfort': metadata.get('alt2_comfort', 0.0),
                            'practicality': metadata.get('alt2_practicality', 0.0)
                        }
                    },
                    {
                        'name': metadata.get('alt3', 'N/A'),
                        'scores': {
                            'energy_cost': metadata.get('alt3_energy_cost', 0.0),
                            'environmental': metadata.get('alt3_environmental', 0.0),
                            'comfort': metadata.get('alt3_comfort', 0.0),
                            'practicality': metadata.get('alt3_practicality', 0.0)
                        }
                    }
                ]
            })

    return retrieved


def format_rag_context(retrieved_scenarios: List[Dict]) -> str:
    """
    Format retrieved scenarios as context for LLM prompt.

    Args:
        retrieved_scenarios: List of retrieved scenario dicts

    Returns:
        Formatted context string
    """
    if not retrieved_scenarios:
        return ""

    context = "RELEVANT SIMILAR SCENARIOS WITH EXPERT SCORES:\n\n"

    for i, scenario in enumerate(retrieved_scenarios, 1):
        context += f"Example {i}: {scenario['text']}\n"
        context += f"  Question: {scenario['question']}\n"

        for alt in scenario['alternatives']:
            scores = alt['scores']
            context += (
                f"  * {alt['name']}: "
                f"Energy Cost: {scores['energy_cost']:.1f}/10, "
                f"Environmental: {scores['environmental']:.1f}/10, "
                f"Comfort: {scores['comfort']:.1f}/10, "
                f"Practicality: {scores['practicality']:.1f}/10\n"
            )
        context += "\n"

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
            f"- Outdoor Temp: {scenario.get('Outdoor Temp', 'N/A')}°F\n"
            f"- Square Footage: {scenario.get('Square Footage', 'N/A')} sqft\n"
            f"- Insulation: {scenario.get('Insulation', 'N/A')}\n"
            f"- Household Size: {scenario.get('Household Size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
            f"- House Age: {scenario.get('House Age', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"
        )

    elif decision_type == 'Appliance':
        prompt += (
            f"- Household Size: {scenario.get('Household Size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"
            f"- Appliance Age Range: {scenario.get('Appliance Age', 'N/A')} years\n"
        )

    elif decision_type == 'Shower':
        prompt += (
            f"- Outdoor Temp: {scenario.get('Outdoor Temp', 'N/A')}°F\n"
            f"- Household Size: {scenario.get('Household Size', 'N/A')} occupants\n"
            f"- Housing Type: {scenario.get('Housing Type', 'N/A')}\n"
            f"- Flow Rate: {scenario.get('Flow rate', 'N/A')}\n"
            f"- Utility Budget: ${scenario.get('Utility Budget', 'N/A')}/month\n"
        )

    prompt += "\nProvide scores (0-10) for all 4 criteria using the calibrations in the system prompt.\n"
    prompt += "Consider how this specific alternative performs given the scenario context.\n"

    return prompt

def parse_llm_scores(response_text: str) -> Tuple[Dict[str, float], List[str]]:
    """
    Parse JSON scores from LLM response.
    """
    try:
        # Strip markdown code fences if present (Claude sometimes wraps JSON in ```json ... ```)
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        scores = json.loads(text)

        validated_scores = {}
        validation_failed = False
        validation_failure_types = set()
        for criterion in ['energy_cost', 'environmental', 'comfort', 'practicality']:
            if criterion not in scores:
                print(f"   Missing score for {criterion}; using sentinel 1928")
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
                    print(f"   Out-of-range score for {criterion}: {raw_value}; using sentinel 1928")
                    validated_scores[criterion] = 1928
                    validation_failed = True
                    validation_failure_types.add('failed_out_of_bounds')
            else:
                print(f"   Invalid score type for {criterion}: {raw_score}; using sentinel 1928")
                validated_scores[criterion] = 1928
                validation_failed = True
                validation_failure_types.add('failed_invalid_score_type')

        if validation_failed:
            validated_scores['_failed'] = True
            return validated_scores, sorted(validation_failure_types) if validation_failure_types else ['failed_unknown']

        return validated_scores, []
    except (json.JSONDecodeError, ValueError) as e:
        print("   Could not parse scores; failed")
        failed_scores = {
            'energy_cost': 1928,
            'environmental': 1928,
            'comfort': 1928,
            'practicality': 1928,
            '_failed': True
        }
        return failed_scores, ['failed_malformed_json']


def score_alternative_with_rag(scenario: Dict, alternative: str) -> Tuple[Dict, Dict]:
    """
    Score an alternative using RAG-Enhanced approach.

    Returns:
        (scores_dict, diagnostics_dict)
    """
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
        print(f"   Scoring failed for alternative '{alternative}': {e}")
        scores = {
            'energy_cost': 1928,
            'environmental': 1928,
            'comfort': 1928,
            'practicality': 1928
        }
        diagnostics = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'latency_ms': 0.0,
            'model': MODEL_ID,
            'success': False,
            'error': str(e),
            'failure_types': ['failed_unknown']
        }

    # Add RAG metadata to diagnostics
    diagnostics['rag_retrieved_count'] = len(retrieved)
    diagnostics['rag_context_length'] = len(rag_context)

    return scores, diagnostics


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    """
    Apply MAVT weighted sum to rank alternatives.

    Args:
        alternatives_scores: List of dicts with 'alternative' and 'scores'

    Returns:
        Dict with ranked alternatives and weighted scores
    """
    weighted_scores = []

    for alt_data in alternatives_scores:
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
        weighted_scores.append({
            'alternative': alt_data['alternative'],
            'weighted_score': weighted_sum,
            'raw_scores': scores
        })
    ranked = sorted(weighted_scores, key=lambda x: x['weighted_score'], reverse=True)

    return {
        'ranked_alternatives': [r['alternative'] for r in ranked],
        'weighted_scores': [r['weighted_score'] for r in ranked],
        'details': ranked
    }


def run_scenario(scenario: Dict) -> Dict:
    """
    Run RAG-Enhanced scoring on all alternatives in a scenario.

    Returns:
        Dict with scores and ranking results
    """
    print(f"SCENARIO: {scenario.get('Question', 'N/A')}")

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
        print(f"\nScoring: {alternative}")

        scores, diagnostics = score_alternative_with_rag(scenario, alternative)
        total_diagnostics['api_calls'] += 1
        total_diagnostics['total_tokens_input'] += diagnostics.get('prompt_tokens', 0)
        total_diagnostics['total_tokens_output'] += diagnostics.get('completion_tokens', 0)
        total_diagnostics['total_latency_ms'] += diagnostics.get('latency_ms', 0.0)

        if scores.get('_failed'):
            print(f" FAILED -- skipping alternative")
            failure_types = diagnostics.get('failure_types')
            if failure_types:
                total_diagnostics['failed_calls'] += 1
                _increment_failure_counters(total_diagnostics, failure_types)
            elif failure_types is None:
                total_diagnostics['failed_calls'] += 1
                _increment_failure_counters(total_diagnostics, ['failed_unknown'])
            alternatives_scores.append({
                'alternative': alternative,
                'scores': {'energy_cost': None, 'environmental': None, 'comfort': None, 'practicality': None},
                'failed': True
            })
            continue

        print(f"  Scores: Energy={scores['energy_cost']:.1f}, "
              f"Env={scores['environmental']:.1f}, "
              f"Comfort={scores['comfort']:.1f}, "
              f"Pract={scores['practicality']:.1f}")
        print(f"  Retrieved {diagnostics.get('rag_retrieved_count', 0)} similar scenarios")

        alternatives_scores.append({
            'alternative': alternative,
            'scores': scores
        })

        if diagnostics.get('success', False):
            total_diagnostics['successful_calls'] += 1
        else:
            failure_types = diagnostics.get('failure_types')
            if failure_types:
                total_diagnostics['failed_calls'] += 1
                _increment_failure_counters(total_diagnostics, failure_types)
            elif failure_types is None:
                total_diagnostics['failed_calls'] += 1
                _increment_failure_counters(total_diagnostics, ['failed_unknown'])

    total_diagnostics['scenario_failed'] = total_diagnostics['failed_calls'] > 0
    ranking_result = apply_mavt_ranking(alternatives_scores)

    print(f"\nRANKING:")
    for i, (alt, score) in enumerate(zip(
            ranking_result['ranked_alternatives'],
            ranking_result['weighted_scores']
    ), 1):
        print(f"  {i}. {alt} (weighted score: {score:.2f})")

    return {
        'scenario': scenario.get('Question', 'N/A'),
        'alternatives_scores': alternatives_scores,
        'ranking_result': ranking_result,
        'diagnostics': total_diagnostics
    }


def run_test_set(test_csv_path: str, output_csv_path: str,
                 output_diagnostics_path: str) -> Dict:
    """
    Run RAG-Enhanced on full test set.

    Args:
        test_csv_path: Path to test scenarios CSV
        output_csv_path: Path to save results CSV
        output_diagnostics_path: Path to save diagnostics JSON

    Returns:
        Summary statistics dict
    """
    import csv as csv_module

    test_csv_path = Path(test_csv_path)
    output_csv_path = Path(output_csv_path)
    output_diagnostics_path = Path(output_diagnostics_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_diagnostics_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"RAG-ENHANCED MCDA ARCHITECTURE - TEST SET")

    print(f"Loading test scenarios from: {test_csv_path}")

    scenarios = []
    with open(test_csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv_module.DictReader(f)
        first_row = next(reader)

        # Validate required columns
        required_cols = ['Question', 'Decision Type', 'Alternative 1', 'Alternative 2', 'Alternative 3']
        missing_cols = [col for col in required_cols if col not in first_row]

        if missing_cols:
            raise ValueError(f" Missing required columns: {missing_cols}")

        scenarios.append(first_row)
        scenarios.extend(list(reader))

    print(f"OK Loaded {len(scenarios)} test scenarios")
    print(f"  Decision types: {set([s.get('Decision Type', 'UNKNOWN') for s in scenarios])}\n")

    # Process all scenarios
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
        print(f"\n[{i + 1}/{len(scenarios)}] Processing: {scenario.get('Question', 'N/A')[:60]}...")

        try:
            result = run_scenario(scenario)
        except Exception as e:
            print(f"  Scenario crashed and was marked failed: {e}")
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
                    'weighted_scores': []
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

        # Aggregate diagnostics
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
    # Save results to CSV
    print(f"\nSaving results to: {output_csv_path}")

    with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            'scenario_id', 'question', 'location', 'decision_type', 'outdoor_temp', 'appliance_age', 'flow_rate',
            'alternative', 'energy_cost', 'environmental', 'comfort', 'practicality',
            'rank', 'weighted_score'
        ]
        writer = csv_module.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for scenario_id, result in enumerate(all_results, 1):
            question = result['scenario']
            decision_type = scenarios[scenario_id - 1].get('Decision Type', 'UNKNOWN')
            location = scenarios[scenario_id - 1].get('Location', 'N/A')
            outdoor_temp = scenarios[scenario_id - 1].get('Outdoor Temp', '')
            appliance_age = scenarios[scenario_id - 1].get('Appliance Age', '')
            flow_rate = scenarios[scenario_id - 1].get('Flow rate', '')
            scenario_failed = result.get('diagnostics', {}).get('scenario_failed', False)

            # Get ranking details
            ranked_alts = result['ranking_result']['ranked_alternatives']
            weighted_scores = result['ranking_result']['weighted_scores']
            rank_lookup = {alt: idx + 1 for idx, alt in enumerate(ranked_alts)}
            score_lookup = {alt: weighted_scores[idx] for idx, alt in enumerate(ranked_alts)}

            # Write each alternative
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
                    # Failed alternatives may not exist in ranked_alts.
                    rank = rank_lookup.get(alternative, 1928)
                    weighted_score = score_lookup.get(alternative, 1928)

                writer.writerow({
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

    print(f"OK Results saved to: {output_csv_path}")

    # Save diagnostics
    print(f"Saving diagnostics to: {output_diagnostics_path}")

    with open(output_diagnostics_path, 'w', encoding='utf-8-sig') as f:
        json.dump(cumulative_diagnostics, f, indent=2)

    print(f"OK Diagnostics saved to: {output_diagnostics_path}")

    print(f"RAG-ENHANCED TEST COMPLETE")
    print(f"Total scenarios: {cumulative_diagnostics['total_scenarios']}")
    print(f"Total API calls: {cumulative_diagnostics['total_api_calls']}")
    print(f"Successful calls: {cumulative_diagnostics['successful_calls']}")
    print(f"Failed calls: {cumulative_diagnostics['failed_calls']}")
    print(f"Total tokens (input): {cumulative_diagnostics['total_tokens_input']}")
    print(f"Total tokens (output): {cumulative_diagnostics['total_tokens_output']}")
    print(f"Average latency: {cumulative_diagnostics['avg_latency_ms']:.0f} ms")
    print(f"Success rate: {cumulative_diagnostics['success_rate']:.1%}")

    return cumulative_diagnostics

if __name__ == "__main__":
    import sys

    test_csv = TEST_SCENARIOS_CSV

    if not test_csv.exists():
        print(f"Test scenarios file not found: {test_csv}")
        print("Please upload your test scenarios CSV first.")
        sys.exit(1)

    if chroma_collection is None:
        print(f"RAG database not available.")
        print("Please run Miscellaneous Files/BuildRAG.py first to create the RAG database.")
        sys.exit(1)

    # Run test set
    run_test_set(
        test_csv_path=str(test_csv),
        output_csv_path=str(OUTPUT_CSV),
        output_diagnostics_path=str(OUTPUT_DIAGNOSTICS)
    )