import os
import json
import csv
import requests
import time
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

try:
    from HVACGroundTruthCalculator import (
        HVACGroundTruthCalculator
    )
except ModuleNotFoundError:
    print("couldnt get HVAC ground truth calculator")

try:
    from ApplianceGroundTruthCalculator import (
        ApplianceGroundTruthCalculator
    )
except ModuleNotFoundError:
    print("couldnt get appliance  ground truth calculator")


try:
    from ShowerGroundTruthCalculator import (
        ShowerGroundTruthCalculator
    )
except ModuleNotFoundError:
    print("couldnt get shower ground truth calculator")


load_dotenv()
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables!")

MODEL_ID = "mistralai/mistral-small-3.2"
TEMPERATURE = 0.3
CRITERION_WEIGHTS = {
    'energy_cost': 0.35,
    'environmental': 0.30,
    'comfort': 0.20,
    'practicality': 0.15
}

MAX_RETRIES = 3
RETRY_DELAY = 2
EXTRACTION_MAX_RETRIES = 1
OUTPUT_CSV = '/mnt/user-data/outputs/hybrid_results.csv'
OUTPUT_DIAGNOSTICS = '/mnt/user-data/outputs/hybrid_diagnostics.json'

UNIFIED_EXTRACTION_PROMPT = """[PLACEHOLDER ]

You are a household decision expert. Analyze this scenario and extract ALL required information in a single response.

SCENARIO:
{scenario_text}

QUESTION: {question}

YOUR TASK:
1. Classify the decision type (HVAC, Appliance, or Shower)
2. Extract the specific parameters needed for that decision type
3. Select the appropriate ground truth calculator

Return ONLY valid JSON with this structure:

For HVAC decisions:
{{
  "decision_type": "HVAC",
  "calculator": "HVACGroundTruthCalculator",
  "parameters": {{
    "r_value": <number>,
    "hvac_age": <number>,
    "seer": <number>,
    "alternatives": ["XF", "XF", "XF"]
  }}
}}

For Appliance decisions:
{{
  "decision_type": "Appliance",
  "calculator": "ApplianceGroundTruthCalculator",
  "parameters": {{
    "appliance_type": "Dishwasher|Washer|Dryer",
    "kwh_per_cycle": <number>,
    "appliance_age": <number>,
    "alternatives": ["Run at Xpm", "Run at Xpm", "Run at Xpm"]
  }}
}}

For Shower decisions:
{{
  "decision_type": "Shower",
  "calculator": "ShowerGroundTruthCalculator",
  "parameters": {{
    "gpm": <number>,
    "water_heater_type": "Electric|Gas",
    "tank_size": <number>,
    "water_heater_temp": <number>,
    "alternatives": [<number>, <number>, <number>]
  }}
}}

Return ONLY the JSON, no explanation.
"""

def query_openrouter(messages: List[Dict], model: str = MODEL_ID,
                     temperature: float = TEMPERATURE) -> Tuple[Dict, Dict]:
    """
    Query OpenRouter API with retry logic.
    EXACT COPY from pure_prompting.py and rag_enhanced.py
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

    for attempt in range(MAX_RETRIES):
        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            latency = time.time() - start_time

            if response.status_code == 200:
                data = response.json()

                usage = data.get('usage', {})
                diagnostics = {
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                    'latency_seconds': latency,
                    'model': model
                }

                return data, diagnostics
            else:
                print(f"  API error (attempt {attempt + 1}/{MAX_RETRIES}): {response.status_code}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)

        except Exception as e:
            print(f"  Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    raise Exception(f"Failed to get response after {MAX_RETRIES} attempts")


# Decision type detection and calculator selection now handled in unified extraction
# No separate functions needed


def format_scenario_for_extraction(scenario: Dict) -> str:
    """
    Convert scenario dict to natural language text for extraction prompt.
    """
    lines = []
    for key, value in scenario.items():
        if key not in ['Question']:  # Don't repeat question in details
            lines.append(f"- {key}: {value}")
    return '\n'.join(lines)


def extract_all_with_ai(scenario: Dict) -> Tuple[Optional[Dict], Dict]:
    """
    UNIFIED AI EXTRACTION - Single call extracts everything:
    1. Decision type classification
    2. Parameters for that decision type
    3. Calculator selection

    NO FALLBACKS - Returns None on failure.

    Returns:
        (extraction_result_dict, diagnostics)

        extraction_result_dict structure:
        {
            'decision_type': 'HVAC'|'Appliance'|'Shower',
            'calculator': 'HVACGroundTruthCalculator'|...,
            'parameters': {...}  # Decision-type specific
        }
    """
    scenario_text = format_scenario_for_extraction(scenario)
    question = scenario.get('Question', '')

    prompt = UNIFIED_EXTRACTION_PROMPT.format(
        scenario_text=scenario_text,
        question=question
    )

    messages = [{"role": "user", "content": prompt}]

    extraction_diagnostics = {
        'attempts': 0,
        'success': False,
        'extraction_error': None
    }

    for attempt in range(EXTRACTION_MAX_RETRIES + 1):
        extraction_diagnostics['attempts'] += 1

        try:
            response, api_diagnostics = query_openrouter(messages)
            response_text = response['choices'][0]['message']['content']
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

            if json_match:
                extracted = json.loads(json_match.group())

                required_top_level = ['decision_type', 'calculator', 'parameters']
                if all(k in extracted for k in required_top_level):

                    if extracted['decision_type'] not in ['HVAC', 'Appliance', 'Shower']:
                        print(f" iinvalid decision_type: {extracted['decision_type']}")
                        extraction_diagnostics['extraction_error'] = "Invalid decision_type"
                        continue

                    valid_calculators = ['HVACGroundTruthCalculator', 'ApplianceGroundTruthCalculator',
                                         'ShowerGroundTruthCalculator']
                    if extracted['calculator'] not in valid_calculators:
                        print(f" invalid calculator: {extracted['calculator']}")
                        extraction_diagnostics['extraction_error'] = "Invalid calculator"
                        continue

                    params = extracted['parameters']
                    decision_type = extracted['decision_type']

                    if decision_type == 'HVAC':
                        required_params = ['r_value', 'hvac_age', 'seer', 'alternatives']
                    elif decision_type == 'Appliance':
                        required_params = ['appliance_type', 'kwh_per_cycle', 'appliance_age', 'alternatives']
                    elif decision_type == 'Shower':
                        required_params = ['gpm', 'water_heater_type', 'tank_size', 'water_heater_temp', 'alternatives']

                    if all(k in params for k in required_params):
                        extraction_diagnostics['success'] = True
                        extraction_diagnostics.update(api_diagnostics)
                        return extracted, extraction_diagnostics
                    else:
                        print(f"Missing required parameters for {decision_type}")
                        extraction_diagnostics['extraction_error'] = f"Missing parameters: {required_params}"
                        continue

            print(f"Extraction attempt {attempt + 1} failed to parse JSON")
            extraction_diagnostics['extraction_error'] = "Invalid JSON format"

        except Exception as e:
            print(f"Extraction attempt {attempt + 1} error: {e}")
            extraction_diagnostics['extraction_error'] = str(e)

    print("  extraction fail")
    return None, extraction_diagnostics

def score_with_ground_truth(extracted_result: Dict, scenario: Dict) -> List[Dict]:
    """
    Feed extracted parameters to AI-selected ground truth calculator.
    Calculator was already chosen by AI in extraction step.

    Args:
        extracted_result: Output from extract_all_with_ai()
            {
                'decision_type': 'HVAC',
                'calculator': 'HVACGroundTruthCalculator',
                'parameters': {...}
            }
        scenario: Original scenario dict

    Returns:
        List of alternatives with scores
    """
    gt_scenario = {**scenario, **extracted_result['parameters']}

    # Add alternatives as separate keys (required by GT calculators)
    alternatives = extracted_result['parameters'].get('alternatives', [])
    for i, alt in enumerate(alternatives[:3], 1):
        gt_scenario[f'Alternative {i}'] = alt

    # Use AI-selected calculator
    calculator_name = extracted_result['calculator']
    print(f"  Using AI-selected calculator: {calculator_name}")

    if calculator_name == 'HVACGroundTruthCalculator':
        result = HVACGroundTruthCalculator.calculate_scenario_scores(gt_scenario)
    elif calculator_name == 'ApplianceGroundTruthCalculator':
        result = ApplianceGroundTruthCalculator.calculate_scenario_scores(gt_scenario)
    elif calculator_name == 'ShowerGroundTruthCalculator':
        result = ShowerGroundTruthCalculator.calculate_scenario_scores(gt_scenario)
    else:
        raise ValueError(f"Unknown calculator: {calculator_name}")

    # Extract scores from result
    alternatives_scores = []
    for alt_data in result['alternatives']:
        alternatives_scores.append({
            'alternative': alt_data['alternative'],
            'scores': alt_data['transformed_values']
        })

    return alternatives_scores


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    """
    Apply MAVT weighted sum to rank alternatives.
    EXACT COPY from pure_prompting.py and rag_enhanced.py
    """
    weighted_scores = []

    for alt_data in alternatives_scores:
        scores = alt_data['scores']
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

    # Sort by weighted score (descending)
    ranked = sorted(weighted_scores, key=lambda x: x['weighted_score'], reverse=True)

    return {
        'ranked_alternatives': [r['alternative'] for r in ranked],
        'weighted_scores': [r['weighted_score'] for r in ranked],
        'details': ranked
    }

def run_scenario(scenario: Dict) -> Dict:
    """
    Run Hybrid approach on a single scenario.

    Process:
    1. SINGLE AI CALL extracts: decision type + parameters + calculator selection
    2. If extraction fails → output zeros and mark as failed
    3. Feed to ground truth calculator (AI-selected)
    4. Apply MAVT ranking

    Returns:
        Dict with results and diagnostics
    """
    print(f"\n{'=' * 70}")
    print(f"SCENARIO: {scenario.get('Question', 'N/A')}")
    print(f"{'=' * 70}")

    # Step 1: SINGLE AI CALL - extract everything
    print(f"AI extracting all information (decision type + parameters + calculator)...")

    extraction_result, extraction_diag = extract_all_with_ai(scenario)

    # Step 2: Check if extraction failed
    if extraction_result is None:
        print(f" EXTRACTION FAILEd. Outputting zero scores")

        # Create zero-score alternatives
        zero_alternatives = []
        for i in range(1, 4):
            zero_alternatives.append({
                'alternative': f'Alternative {i} (extraction failed)',
                'scores': {
                    'energy_cost': 0.0,
                    'environmental': 0.0,
                    'comfort': 0.0,
                    'practicality': 0.0
                }
            })

        ranking_result = apply_mavt_ranking(zero_alternatives)

        return {
            'scenario': scenario.get('Question', 'N/A'),
            'decision_type': 'UNKNOWN',
            'calculator': 'NONE',
            'extraction_failed': True,
            'extracted_result': None,
            'alternatives_scores': zero_alternatives,
            'ranking_result': ranking_result,
            'extraction_diagnostics': extraction_diag
        }

    decision_type = extraction_result['decision_type']
    calculator = extraction_result['calculator']
    parameters = extraction_result['parameters']

    print(f"  ✓ Extraction succeeded")
    print(f"  Decision type: {decision_type}")
    print(f"  Calculator: {calculator}")
    print(f"  Parameters: {parameters}")
    print(f"Calculating ground truth scores")

    try:
        alternatives_scores = score_with_ground_truth(extraction_result, scenario)

        for alt_data in alternatives_scores:
            scores = alt_data['scores']
            print(f"  {alt_data['alternative']}: "
                  f"Energy={scores['energy_cost']:.1f}, "
                  f"Env={scores['environmental']:.1f}, "
                  f"Comfort={scores['comfort']:.1f}, "
                  f"Pract={scores['practicality']:.1f}")

    except Exception as e:
        print(f" hround truth calculation failed: {e}")

        # Output zeros on GT calculation failure
        zero_alternatives = []
        for i, alt in enumerate(parameters.get('alternatives', ['Alt1', 'Alt2', 'Alt3'])[:3], 1):
            zero_alternatives.append({
                'alternative': str(alt),
                'scores': {
                    'energy_cost': 0.0,
                    'environmental': 0.0,
                    'comfort': 0.0,
                    'practicality': 0.0
                }
            })

        ranking_result = apply_mavt_ranking(zero_alternatives)

        return {
            'scenario': scenario.get('Question', 'N/A'),
            'decision_type': decision_type,
            'calculator': calculator,
            'extraction_failed': False,
            'gt_calculation_failed': True,
            'extracted_result': extraction_result,
            'alternatives_scores': zero_alternatives,
            'ranking_result': ranking_result,
            'error': str(e),
            'extraction_diagnostics': extraction_diag
        }

    # Step 4: Apply MAVT ranking
    ranking_result = apply_mavt_ranking(alternatives_scores)

    print(f"\nRANKING:")
    for i, (alt, score) in enumerate(zip(
            ranking_result['ranked_alternatives'],
            ranking_result['weighted_scores']
    ), 1):
        print(f"  {i}. {alt} (weighted score: {score:.2f})")

    return {
        'scenario': scenario.get('Question', 'N/A'),
        'decision_type': decision_type,
        'calculator': calculator,
        'extraction_failed': False,
        'gt_calculation_failed': False,
        'extracted_result': extraction_result,
        'alternatives_scores': alternatives_scores,
        'ranking_result': ranking_result,
        'extraction_diagnostics': extraction_diag
    }

#as for the RAG optimized, we have to code the actually test set running