import os
import sys
import json
import requests
import time
import importlib.util
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import CRITERION_WEIGHTS, get_model_id, get_output_folder

TEST_SCENARIOS_CSV = PROJECT_ROOT / "Scenario Files" / "TestScenarios.csv"
OUTPUT_DIR = PROJECT_ROOT / get_output_folder()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GROUND_TRUTH_CALCULATORS_DIR = PROJECT_ROOT / "Ground Truth Calculators"

def _load_calculator_class(module_filename: str, class_name: str):
    module_path = GROUND_TRUTH_CALCULATORS_DIR / module_filename
    spec = importlib.util.spec_from_file_location(class_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


HVACGroundTruthCalculator = None
ApplianceGroundTruthCalculator = None
ShowerGroundTruthCalculator = None

try:
    HVACGroundTruthCalculator = _load_calculator_class(
        "HVACGroundTruthCalculator.py", "HVACGroundTruthCalculator"
    )
except Exception:
    print("couldnt get HVAC ground truth calculator")

try:
    ApplianceGroundTruthCalculator = _load_calculator_class(
        "ApplianceGroundTruthCalculator.py", "ApplianceGroundTruthCalculator"
    )
except Exception:
    print("couldnt get appliance  ground truth calculator")

try:
    ShowerGroundTruthCalculator = _load_calculator_class(
        "ShowerGroundTruthCalculator.py", "ShowerGroundTruthCalculator"
    )
except Exception:
    print("couldnt get shower ground truth calculator")


load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables!")

MODEL_ID = get_model_id()
TEMPERATURE = 0.3

MAX_RETRIES = 3
RETRY_DELAY = 2
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
OUTPUT_CSV = OUTPUT_DIR / "hybrid_results.csv"
OUTPUT_DIAGNOSTICS = OUTPUT_DIR / "hybrid_diagnostics.json"


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520


UNIFIED_EXTRACTION_PROMPT = """You are a household decision expert. Analyze this scenario and extract ALL required information in a single response.

SCENARIO:
{scenario_text}

QUESTION: {question}

YOUR TASK:
1. Read the Decision Type from the scenario (HVAC, Appliance, or Shower)
2. Extract the specific parameters needed for that decision type
3. No field should be left blank; if a value is not apparent, it is mandatory to reasonably estimate it based off of available information
3. Select the appropriate ground truth calculator
4. Format alternatives exactly as shown below

Return ONLY valid JSON with this structure:

For HVAC decisions:
{{
  "decision_type": "HVAC",
  "calculator": "HVACGroundTruthCalculator",
  "parameters": {{
    "Location": "<city, state>",
    "square_footage": <number>,
    "Insulation": "<Poor/Medium/Good>",
    "r_value": <number>,
    "household_size": <number>,
    "outdoor_temp": <number>,
    "seer": <number>,
    "hvac_age": <number>,
    "Household Type": "<Apartment/Single-family/Townhouse>",
    "utility_budget": <number>
    "Occupancy Context": "occupied_all_day|unoccupied_<hours>|occupied_sleep",
    "alternatives": ["<temp>", "<temp>", "<temp>"]
  }}
}}

For Appliance decisions:
{{
  "decision_type": "Appliance",
  "calculator": "ApplianceGroundTruthCalculator",
  "parameters": {{
    "Location": "<city, state>",
    "Appliance": "Dishwasher|Washer|Dryer",
    "kwh/cycle": <number>,
    "Appliance Age/Type": "<age> OR <type>",
    "Baseline Time": "<time like 7pm, 8am, 9am>",
    "Peak Rate": <number>,
    "Off-Peak Rate": <number>,
    "Occupants": <number>,
    "Housing Type": "<Apartment/Single-family/Townhouse>",
    "utility_budget": <number>,
    "alternatives": ["<time>", "<time>", "<time>"]
  }}
}}

For Shower decisions:
{{
  "decision_type": "Shower",
  "calculator": "ShowerGroundTruthCalculator",
  "parameters": {{
    "Location": "<city, state>",
    "GPM": <number>,
    "Tank Size": <number>,
    "Water Heater Temp": <number>,
    "outdoor_temp": <number>,
    "Occupants": <number>,
    "Housing Type": "<Apartment/Single-family/Townhouse>",
    "utility_budget": <number>,
    "alternatives": ["<minutes>", "<minutes>", "<minutes>"]
  }}
}}

CRITICAL: Alternative formats must match exactly:
- HVAC: "72", "76", "80" (No suffix)
- Appliance: "7pm", "10pm", "2am" 
- Shower: "5", "10", "15" (No suffix)

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
                if _is_transient_http_status(response.status_code):
                    print(f"  Transient API error (attempt {attempt + 1}/{MAX_RETRIES}): {response.status_code}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                else:
                    print(f"  Non-retryable API error: {response.status_code}")
                break

        except requests.exceptions.RequestException as e:
            print(f"  Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            break

        except ValueError as e:
            print(f"  Invalid API JSON envelope (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            break

    raise Exception(f"Failed to get response after {MAX_RETRIES} attempts")



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
    attempt = 0
    extraction_diagnostics['attempts'] = 1

    try:
        response, api_diagnostics = query_openrouter(messages)
        extraction_diagnostics.update({
            'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
            'completion_tokens': api_diagnostics.get('completion_tokens', 0),
            'latency_ms': api_diagnostics.get('latency_seconds', 0) * 1000
        })
        response_text = response['choices'][0]['message']['content']
        stripped_response = response_text.strip()
        strict_json_only = stripped_response.startswith('{') and stripped_response.endswith('}')
        if not strict_json_only:
            print(f"Extraction attempt {attempt + 1} failed: non-JSON wrapper text detected")
            extraction_diagnostics['extraction_error'] = "Non-JSON wrapper text detected"
            return None, extraction_diagnostics

        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

        if not json_match:
            print(f"Extraction attempt {attempt + 1} failed to parse JSON")
            extraction_diagnostics['extraction_error'] = "Invalid JSON format"
            extraction_diagnostics.update({
                'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
                'completion_tokens': api_diagnostics.get('completion_tokens', 0),
                'latency_ms': api_diagnostics.get('latency_seconds', 0) * 1000
            })
            return None, extraction_diagnostics

        try:
            extracted = json.loads(json_match.group())
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Extraction attempt {attempt + 1} failed to parse JSON: {e}")
            extraction_diagnostics['extraction_error'] = "Invalid JSON format"
            extraction_diagnostics.update({
                'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
                'completion_tokens': api_diagnostics.get('completion_tokens', 0),
                'latency_ms': api_diagnostics.get('latency_seconds', 0) * 1000
            })
            return None, extraction_diagnostics

        required_top_level = ['decision_type', 'calculator', 'parameters']
        if all(k in extracted for k in required_top_level):

            if extracted['decision_type'] not in ['HVAC', 'Appliance', 'Shower']:
                print(f" iinvalid decision_type: {extracted['decision_type']}")
                extraction_diagnostics['extraction_error'] = "Invalid decision_type"
                return None, extraction_diagnostics

            valid_calculators = ['HVACGroundTruthCalculator', 'ApplianceGroundTruthCalculator',
                                 'ShowerGroundTruthCalculator']
            if extracted['calculator'] not in valid_calculators:
                print(f" invalid calculator: {extracted['calculator']}")
                extraction_diagnostics['extraction_error'] = "Invalid calculator"
                return None, extraction_diagnostics

            params = extracted['parameters']
            decision_type = extracted['decision_type']

            if decision_type == 'HVAC':
                required_params = ['Location', 'square_footage', 'Insulation', 'r_value',
                                   'seer', 'hvac_age', 'outdoor_temp', 'alternatives']
            elif decision_type == 'Appliance':
                required_params = ['Location', 'Appliance', 'kwh/cycle', 'Appliance Age/Type',
                                   'Baseline Time', 'Peak Rate', 'Off-Peak Rate', 'alternatives']
            elif decision_type == 'Shower':
                required_params = ['Location', 'GPM', 'Tank Size',
                                   'Water Heater Temp', 'outdoor_temp', 'alternatives']
            if all(k in params for k in required_params):
                extraction_diagnostics['success'] = True
                extraction_diagnostics.update({
                    'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
                    'completion_tokens': api_diagnostics.get('completion_tokens', 0),
                    'latency_ms': api_diagnostics.get('latency_seconds', 0) * 1000
                })
                return extracted, extraction_diagnostics

            print(f"Missing required parameters for {decision_type}")
            extraction_diagnostics['extraction_error'] = f"Missing parameters: {required_params}"
            return None, extraction_diagnostics

        print(f"Extraction attempt {attempt + 1} failed to parse JSON")
        extraction_diagnostics['extraction_error'] = "Invalid JSON format"
        extraction_diagnostics.update({
            'prompt_tokens': api_diagnostics.get('prompt_tokens', 0),
            'completion_tokens': api_diagnostics.get('completion_tokens', 0),
            'latency_ms': api_diagnostics.get('latency_seconds', 0) * 1000
        })
        return None, extraction_diagnostics

    except Exception as e:
        print(f"Extraction attempt {attempt + 1} error: {e}")
        extraction_diagnostics['extraction_error'] = str(e)
        return None, extraction_diagnostics

def score_with_ground_truth(extracted_result: Dict, scenario: Dict) -> List[Dict]:
    gt_scenario = {**scenario, **extracted_result['parameters']}

    if 'utility_budget' in gt_scenario:
        gt_scenario['Utility Budget'] = gt_scenario['utility_budget']
    alternatives = extracted_result['parameters'].get('alternatives', [])
    for i, alt in enumerate(alternatives[:3], 1):
        gt_scenario[f'Alternative {i}'] = alt
    for key in ['Utility Budget', 'Occupants', 'Peak Rate', 'Off-Peak Rate', 'kwh/cycle']:
        if key in gt_scenario and isinstance(gt_scenario[key], str):
            try:
                gt_scenario[key] = float(gt_scenario[key])
            except (ValueError, TypeError):
                gt_scenario[key] = 0.0

    calculator_name = extracted_result['calculator']
    print(f"  Using AI-selected calculator: {calculator_name}")
    
    if calculator_name == 'HVACGroundTruthCalculator':
        calc = HVACGroundTruthCalculator()
        result = calc.calculate_scenario_scores(gt_scenario)
    elif calculator_name == 'ApplianceGroundTruthCalculator':
        calc = ApplianceGroundTruthCalculator()
        result = calc.calculate_scenario_scores(gt_scenario)
    elif calculator_name == 'ShowerGroundTruthCalculator':
        calc = ShowerGroundTruthCalculator()
        result = calc.calculate_scenario_scores(gt_scenario)
    else:
        raise ValueError(f"Unknown calculator: {calculator_name}")
    alternatives_scores = []
    if calculator_name == 'ShowerGroundTruthCalculator':
        for alt_data in result['alternatives']:
            alternatives_scores.append({
                'alternative': str(alt_data['alternative']),
                'scores': {
                    'energy_cost': alt_data['transformed_values']['energy_cost'],
                    'environmental': alt_data['transformed_values']['environmental'],
                    'comfort': alt_data['transformed_values']['comfort'],
                    'practicality': alt_data['transformed_values']['practicality']
                }
            })
    else:  # HVAC and Appliance — identical return structure
        for alt_key, alt_data in result.items():
            alternatives_scores.append({
                'alternative': str(alt_key),
                'scores': {
                    'energy_cost': alt_data['energy_cost_score'],
                    'environmental': alt_data['environmental_score'],
                    'comfort': alt_data['comfort_score'],
                    'practicality': alt_data['practicality_score']
                }
            })
    return alternatives_scores


def apply_mavt_ranking(alternatives_scores: List[Dict]) -> Dict:
    """
    Apply MAVT weighted sum to rank alternatives.
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
  
    print(f"SCENARIO: {scenario.get('Question', 'N/A')}")
   
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
            'gt_calculation_failed': False,
            'scenario_failed': True,
            'extracted_result': None,
            'alternatives_scores': zero_alternatives,
            'ranking_result': ranking_result,
            'extraction_diagnostics': extraction_diag
        }

    decision_type = extraction_result['decision_type']
    calculator = extraction_result['calculator']
    parameters = extraction_result['parameters']

    print(f"   Extraction succeeded")
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
            'scenario_failed': True,
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
        'scenario_failed': False,
        'extracted_result': extraction_result,
        'alternatives_scores': alternatives_scores,
        'ranking_result': ranking_result,
        'extraction_diagnostics': extraction_diag
    }


def run_test_set(test_csv_path: str, output_csv_path: str,
                 output_diagnostics_path: str) -> Dict:
    """
    Run Hybrid approach on full test set.

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


    print(f"Loading test scenarios from: {test_csv_path}")

    scenarios = []
    with open(test_csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv_module.DictReader(f)
        first_row = next(reader)

        # Validate required columns
        required_cols = ['Question', 'Decision Type']
        missing_cols = [col for col in required_cols if col not in first_row]

        if missing_cols:
            raise ValueError(f" Missing required columns: {missing_cols}")

        scenarios.append(first_row)
        scenarios.extend(list(reader))

    print(f" Loaded {len(scenarios)} test scenarios")
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
        'failed_scenarios': 0
    }
    for i, scenario in enumerate(scenarios):
        print(f"\n[{i + 1}/{len(scenarios)}] Processing: {scenario.get('Question', 'N/A')[:60]}...")

        try:
            result = run_scenario(scenario)
        except Exception as e:
            print(f" Scenario crashed and was marked failed: {e}")
            fallback_alternatives = [
                scenario.get('Alternative 1', 'Alt1'),
                scenario.get('Alternative 2', 'Alt2'),
                scenario.get('Alternative 3', 'Alt3')
            ]
            result = {
                'scenario': scenario.get('Question', 'N/A'),
                'decision_type': scenario.get('Decision Type', 'UNKNOWN'),
                'calculator': 'NONE',
                'extraction_failed': True,
                'gt_calculation_failed': False,
                'scenario_failed': True,
                'alternatives_scores': [
                    {
                        'alternative': str(alt),
                        'scores': {
                            'energy_cost': 0.0,
                            'environmental': 0.0,
                            'comfort': 0.0,
                            'practicality': 0.0
                        }
                    }
                    for alt in fallback_alternatives
                ],
                'ranking_result': {
                    'ranked_alternatives': [str(alt) for alt in fallback_alternatives],
                    'weighted_scores': [0.0, 0.0, 0.0]
                },
                'extraction_diagnostics': {
                    'attempts': 0,
                    'success': False,
                    'extraction_error': str(e),
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'latency_ms': 0.0
                }
            }

        all_results.append(result)

        ext_diag = result.get('extraction_diagnostics', {})
        attempts = ext_diag.get('attempts', 0)
        try:
            attempts = int(attempts)
        except (TypeError, ValueError):
            attempts = 0
        cumulative_diagnostics['total_api_calls'] += max(attempts, 0)

        cumulative_diagnostics['total_tokens_input'] += ext_diag.get('prompt_tokens', 0)
        cumulative_diagnostics['total_tokens_output'] += ext_diag.get('completion_tokens', 0)
        cumulative_diagnostics['total_latency_ms'] += ext_diag.get('latency_ms', 0.0)

        if result.get('scenario_failed', False):
            cumulative_diagnostics['failed_calls'] += 1
            cumulative_diagnostics['failed_scenarios'] += 1
        else:
            cumulative_diagnostics['successful_calls'] += 1
            cumulative_diagnostics['successful_scenarios'] += 1
    cumulative_diagnostics['avg_latency_ms'] = (
            cumulative_diagnostics['total_latency_ms'] /
            max(cumulative_diagnostics['total_api_calls'], 1)
    )
    cumulative_diagnostics['success_rate'] = (
            cumulative_diagnostics['successful_scenarios'] /
            max(cumulative_diagnostics['total_scenarios'], 1)
    )
    print(f"\nSaving results to: {output_csv_path}")

    with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            'scenario_id', 'question', 'location', 'decision_type', 'outdoor_temp', 'appliance_age', 'flow_rate',
            'calculator', 'extraction_failed', 'gt_calculation_failed',
            'alternative', 'energy_cost', 'environmental', 'comfort', 'practicality',
            'rank', 'weighted_score'
        ]
        writer = csv_module.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for scenario_id, result in enumerate(all_results, 1):
            question = result['scenario']
            decision_type = result['decision_type']
            calculator = result['calculator']
            extraction_failed = result.get('extraction_failed', False)
            gt_calc_failed = result.get('gt_calculation_failed', False)
            scenario_failed = result.get('scenario_failed', False)

            location = scenarios[scenario_id - 1].get('Location', 'N/A')
            outdoor_temp = scenarios[scenario_id - 1].get('Outdoor Temp', '')
            appliance_age = scenarios[scenario_id - 1].get('Appliance Age', '')
            flow_rate = scenarios[scenario_id - 1].get('Flow rate', '')

            # Get ranking details
            ranked_alts = result['ranking_result']['ranked_alternatives']
            weighted_scores = result['ranking_result']['weighted_scores']

            # Write each alternative
            for alt_idx, alt_data in enumerate(result['alternatives_scores']):
                alternative = alt_data['alternative']
                scores = alt_data['scores']

                if scenario_failed:
                    energy_cost = 9999
                    environmental = 9999
                    comfort = 9999
                    practicality = 9999
                    rank = 9999
                    weighted_score = 9999
                else:
                    energy_cost = scores['energy_cost']
                    environmental = scores['environmental']
                    comfort = scores['comfort']
                    practicality = scores['practicality']
                    # Find rank (1-based)
                    rank = ranked_alts.index(alternative) + 1
                    weighted_score = weighted_scores[ranked_alts.index(alternative)]

                writer.writerow({
                    'scenario_id': scenario_id,
                    'question': question,
                    'location': location,
                    'decision_type': decision_type,
                    'outdoor_temp': outdoor_temp,
                    'appliance_age': appliance_age,
                    'flow_rate': flow_rate,
                    'calculator': calculator,
                    'extraction_failed': extraction_failed,
                    'gt_calculation_failed': gt_calc_failed,
                    'alternative': alternative,
                    'energy_cost': energy_cost,
                    'environmental': environmental,
                    'comfort': comfort,
                    'practicality': practicality,
                    'rank': rank,
                    'weighted_score': weighted_score
                })

    print(f" Results saved to: {output_csv_path}")

    # Save diagnostics
    print(f"Saving diagnostics to: {output_diagnostics_path}")

    with open(output_diagnostics_path, 'w', encoding='utf-8-sig') as f:
        json.dump(cumulative_diagnostics, f, indent=2)

    print(f" Diagnostics saved to: {output_diagnostics_path}")


    print(f"HYBRID TEST COMPLETE")
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
    test_csv = TEST_SCENARIOS_CSV

    if not test_csv.exists():
        print(f" ERROR: Test scenarios file not found: {test_csv}")
        print("Please upload your test scenarios CSV first.")
        sys.exit(1)

    if (HVACGroundTruthCalculator is None or
            ApplianceGroundTruthCalculator is None or
            ShowerGroundTruthCalculator is None):
        print(" ERROR: Could not load one or more ground truth calculators.")
        print("Please ensure HVACGroundTruthCalculator.py, ApplianceGroundTruthCalculator.py, and ShowerGroundTruthCalculator.py are in the Ground Truth Calculators folder.")
        sys.exit(1)
    else:
        print(" Ground truth calculators loaded")

    run_test_set(
        test_csv_path=str(test_csv),
        output_csv_path=str(OUTPUT_CSV),
        output_diagnostics_path=str(OUTPUT_DIAGNOSTICS)
    )