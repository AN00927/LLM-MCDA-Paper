import argparse
import json
import logging
import math
import os
import shutil
import sys
import tempfile
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import (
    CRITERION_WEIGHTS,
    MAX_RETRIES,
    MAX_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
    RETRY_BASE_DELAY,
    TEMPERATURE,
    get_model_id,
    get_output_folder,
    get_reasoning_payload,
    MODEL_SPECS,
)
import importlib.util

from sentinel_utils import (
    appliance_age_to_band_label,
    format_embedding_text,
    gpm_to_flow_rate_label,
    house_age_to_band_label,
    read_table_clean,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
OUTPUT_DIR = PROJECT_ROOT / get_output_folder()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CRITERIA = ["energy_cost", "environmental", "comfort", "practicality"]
SENTINEL = 1928.0
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ALTERNATE_EMBEDDING_MODEL = "sentence-transformers/paraphrase-MiniLM-L3-v2"
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}

from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

DECISION_TYPES = ["HVAC", "Appliance", "Shower"]
RAG_FILES = OrderedDict([
    ("HVAC", "HVACRagScenarios.xlsx"),
    ("Appliance", "ApplianceRAGScenarios.xlsx"),
    ("Shower", "ShowerRAGScenarios.xlsx"),
])

ABLATION_SPECS = OrderedDict([
    ("control_k3", {
        "label": "Control k=3 standard",
        "k": 3,
        "retrieval": "similarity",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "include_hidden_params": True,
        "include_scores": True,
        "include_ranks": True,
        "llm": True,
    }),
    ("random_exemplars_k3", {
        "label": "Random exemplars k=3",
        "k": 3,
        "retrieval": "random",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "include_hidden_params": True,
        "include_scores": True,
        "include_ranks": True,
        "llm": True,
    }),
    ("descriptions_no_scores_ranks", {
        "label": "Descriptions without scores or ranks",
        "k": 3,
        "retrieval": "similarity",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "include_hidden_params": True,
        "include_scores": False,
        "include_ranks": False,
        "llm": True,
    }),
    ("exemplars_no_hidden_params", {
        "label": "Exemplars without hidden parameters",
        "k": 3,
        "retrieval": "similarity",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "include_hidden_params": False,
        "include_scores": True,
        "include_ranks": True,
        "llm": True,
    }),
    ("retrieval_k1", {
        "label": "Retrieval k=1",
        "k": 1,
        "retrieval": "similarity",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "include_hidden_params": True,
        "include_scores": True,
        "include_ranks": True,
        "llm": True,
    }),
    ("retrieval_k5", {
        "label": "Retrieval k=5",
        "k": 5,
        "retrieval": "similarity",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "include_hidden_params": True,
        "include_scores": True,
        "include_ranks": True,
        "llm": True,
    }),
    ("alternate_embedding_k3", {
        "label": f"Alternate embedding k=3 ({ALTERNATE_EMBEDDING_MODEL})",
        "k": 3,
        "retrieval": "similarity",
        "embedding_model": ALTERNATE_EMBEDDING_MODEL,
        "include_hidden_params": True,
        "include_scores": True,
        "include_ranks": True,
        "llm": True,
    }),
    ("nearest_neighbor_k3", {
        "label": "Nearest-neighbor prediction k=3",
        "k": 3,
        "retrieval": "similarity",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "include_hidden_params": True,
        "include_scores": True,
        "include_ranks": True,
        "llm": False,
    }),
])


def _clean_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _to_float(value) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    if not math.isfinite(value):
        return np.nan
    return value


def _load_chromadb():
    import chromadb
    return chromadb


def _load_sentence_transformer_model(model_name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name)


def _load_scipy_rank_metrics():
    from scipy.stats import kendalltau, spearmanr
    return kendalltau, spearmanr


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES or status_code >= 520


def parse_sample_size(value: str) -> Optional[int]:
    if value.strip().lower() == "all":
        return None
    try:
        n = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--sample-size must be an integer or 'all'") from exc
    if n <= 0:
        raise argparse.ArgumentTypeError("--sample-size must be positive or 'all'")
    return n


def load_source_df(decision_type: str) -> pd.DataFrame:
    path = SCENARIO_DIR / RAG_FILES[decision_type]
    df = read_table_clean(path)
    if decision_type == "HVAC":
        df["alternative_num"] = df.groupby("scenario_id").cumcount() + 1
    return df


def _meta_val(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value.item() if hasattr(value, "item") else value
    return str(value)


def build_scenario_metadata(decision_type: str, first_row, group: pd.DataFrame) -> Dict:
    md = {
        "decision_type": decision_type,
        "scenario_id": f"{decision_type.lower()}_{first_row['scenario_id']}",
        "question": _meta_val(first_row.get("question")),
        "location": _meta_val(first_row.get("location")),
        "household_size": _meta_val(first_row.get("household_size")),
        "housing_type": _meta_val(first_row.get("housing_type")),
        "utility_budget": _meta_val(first_row.get("utility_budget")),
    }
    if decision_type == "HVAC":
        md.update({
            "square_footage": _meta_val(first_row.get("square_footage")),
            "insulation": _meta_val(first_row.get("insulation")),
            "outdoor_temp": _meta_val(first_row.get("outdoor_temp")),
            "house_age": house_age_to_band_label(first_row.get("house_age")),
            "r_value": _meta_val(first_row.get("r_value")),
            "seer": _meta_val(first_row.get("seer")),
            "hvac_age": _meta_val(first_row.get("hvac_age")),
        })
    elif decision_type == "Appliance":
        md.update({
            "appliance": _meta_val(first_row.get("appliance")),
            "appliance_age": appliance_age_to_band_label(first_row.get("appliance_age")),
            "kwh_per_cycle": _meta_val(first_row.get("kwh_per_cycle")),
        })
    elif decision_type == "Shower":
        flow_rate = first_row.get("flow_rate")
        if flow_rate is None or str(flow_rate).strip() in ("", "nan", "N/A", "<NA>"):
            flow_rate = gpm_to_flow_rate_label(first_row.get("gpm", 0))
        md.update({
            "outdoor_temp": _meta_val(first_row.get("outdoor_temp")),
            "gpm": _meta_val(first_row.get("gpm")),
            "flow_rate": flow_rate,
            "tank_size": _meta_val(first_row.get("tank_size")),
            "water_heater_temp": _meta_val(first_row.get("water_heater_temp")),
        })
    for i, (_, row) in enumerate(group.iterrows(), 1):
        if decision_type == "Shower":
            name = f"{int(round(float(row['duration_min'])))} min"
        else:
            name = str(row["alternative"])
        md[f"alt{i}"] = name
        md[f"alt{i}_energy_cost"] = float(row["energy_cost_score"])
        md[f"alt{i}_environmental"] = float(row["environmental_score"])
        md[f"alt{i}_comfort"] = float(row["comfort_score"])
        md[f"alt{i}_practicality"] = float(row["practicality_score"])
        md[f"alt{i}_mavt"] = float(row["mavt_score"])
        md[f"alt{i}_rank"] = int(round(float(row["rank"])))
    return md


def load_source_groups() -> Dict[str, List[Dict]]:
    loaders = {
        "HVAC": lambda csv_dir: load_source_df("HVAC"),
        "Appliance": lambda csv_dir: load_source_df("Appliance"),
        "Shower": lambda csv_dir: load_source_df("Shower"),
    }
    groups_by_type = {}
    for decision_type, filename in RAG_FILES.items():
        df = loaders[decision_type](str(SCENARIO_DIR))
        groups = []
        for source_position, (scenario_id, group) in enumerate(df.groupby("scenario_id", sort=False), 1):
            first_row = group.iloc[0].to_dict()
            alternatives = []
            for _, row in group.iterrows():
                alt_dict = {
                    "alternative": _clean_text(row.get("alternative")),
                    "energy_cost": _to_float(row.get("energy_cost_score")),
                    "environmental": _to_float(row.get("environmental_score")),
                    "comfort": _to_float(row.get("comfort_score")),
                    "practicality": _to_float(row.get("practicality_score")),
                    "mavt_score": _to_float(row.get("mavt_score")),
                    "rank": int(round(float(row.get("rank")))),
                }
                if "duration_min" in row:
                    alt_dict["duration_min"] = _to_float(row.get("duration_min"))
                alternatives.append(alt_dict)
            metadata_group = pd.DataFrame([
                {
                    "alternative": alt["alternative"],
                    "energy_cost_score": alt["energy_cost"],
                    "environmental_score": alt["environmental"],
                    "comfort_score": alt["comfort"],
                    "practicality_score": alt["practicality"],
                    "mavt_score": alt["mavt_score"],
                    "rank": alt["rank"],
                    **({"duration_min": alt["duration_min"]} if "duration_min" in alt else {})
                }
                for alt in alternatives
            ])
            metadata = dict(first_row)
            metadata.update({
                "decision_type": decision_type,
                "source_scenario_id": scenario_id,
                "source_position": source_position,
                "filename": filename,
                "alternatives": alternatives,
            })
            groups.append(metadata)
        groups_by_type[decision_type] = groups
    return groups_by_type


def stratified_sample(groups_by_type: Dict[str, List[Dict]], sample_size: Optional[int], seed: int) -> List[Dict]:
    rng = np.random.default_rng(seed)
    sampled = []
    if sample_size is None:
        for decision_type in DECISION_TYPES:
            sampled.extend(groups_by_type[decision_type])
        return sampled
    groups = {dtype: list(groups_by_type[dtype]) for dtype in DECISION_TYPES}
    counts = {dtype: len(groups[dtype]) for dtype in DECISION_TYPES}
    base = sample_size // len(DECISION_TYPES)
    remainder = sample_size % len(DECISION_TYPES)
    allocations = {dtype: min(base, counts[dtype]) for dtype in DECISION_TYPES}
    ordered = sorted(DECISION_TYPES, key=lambda dtype: counts[dtype], reverse=True)
    for dtype in ordered:
        if remainder <= 0:
            break
        if allocations[dtype] < counts[dtype]:
            allocations[dtype] += 1
            remainder -= 1
    for dtype in DECISION_TYPES:
        n = min(allocations[dtype], counts[dtype])
        if n <= 0:
            continue
        indices = rng.choice(counts[dtype], size=n, replace=False)
        sampled.extend([groups[dtype][int(i)] for i in sorted(indices)])
    return sampled


def build_collection(embedding_model_name: str, temp_root: Path) -> Tuple[str, object, object, Dict[str, List[Dict]]]:
    chromadb = _load_chromadb()
    temp_path = tempfile.mkdtemp(prefix=f"rag_ablation_{embedding_model_name.replace('/', '_').replace('-', '_')}_", dir=str(temp_root))
    client = chromadb.PersistentClient(path=temp_path)
    collection = client.create_collection(
        name="rag_ablation_collection",
        metadata={
            "description": "Temporary RAG ablation collection",
            "embedding_model": embedding_model_name,
        },
    )
    model = _load_sentence_transformer_model(embedding_model_name)
    groups_by_type = load_source_groups()
    for decision_type in DECISION_TYPES:
        for scenario in groups_by_type[decision_type]:
            first_row = {k: v for k, v in scenario.items() if k != "alternatives"}
            document = format_embedding_text(decision_type, first_row)
            embedding = model.encode(document).tolist()
            metadata_group = pd.DataFrame([
                {
                    "alternative": alt["alternative"],
                    "energy_cost_score": alt["energy_cost"],
                    "environmental_score": alt["environmental"],
                    "comfort_score": alt["comfort"],
                    "practicality_score": alt["practicality"],
                    "mavt_score": alt["mavt_score"],
                    "rank": alt["rank"],
                    **({"duration_min": alt["duration_min"]} if "duration_min" in alt else {})
                }
                for alt in scenario["alternatives"]
            ])
            metadata = build_scenario_metadata(decision_type, pd.Series(first_row), metadata_group)
            metadata["source_scenario_id"] = int(scenario["source_scenario_id"])
            metadata["source_position"] = int(scenario["source_position"])
            metadata["filename"] = scenario["filename"]
            collection.add(
                ids=[metadata["scenario_id"]],
                embeddings=[embedding],
                documents=[document],
                metadatas=[metadata],
            )
    return temp_path, collection, model, groups_by_type


def _fmt_num(value, ndigits: int = 1) -> str:
    value = _to_float(value)
    if pd.isna(value):
        return "N/A"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{ndigits}f}"


def _hidden_param_lines(decision_type: str, md: Dict) -> List[str]:
    if decision_type == "HVAC":
        return [
            f"- R-Value: {_fmt_num(md.get('r_value'))}",
            f"- SEER: {_fmt_num(md.get('seer'))}",
            f"- HVAC Age: {_fmt_num(md.get('hvac_age'), 0)} years",
        ]
    if decision_type == "Appliance":
        return [
            f"- Appliance: {_clean_text(md.get('appliance'))}",
            f"- kWh per Cycle: {_fmt_num(md.get('kwh_per_cycle'))}",
        ]
    if decision_type == "Shower":
        return [
            f"- GPM: {_fmt_num(md.get('gpm'))}",
            f"- Tank Size: {_fmt_num(md.get('tank_size'), 0)} gal",
            f"- Water Heater Temp: {_fmt_num(md.get('water_heater_temp'), 0)} deg F",
        ]
    return []


def _base_param_lines(decision_type: str, md: Dict) -> List[str]:
    if decision_type == "HVAC":
        return [
            f"- Location: {_clean_text(md.get('location'))}",
            f"- Outdoor Temp: {_fmt_num(md.get('outdoor_temp'), 0)} deg F",
            f"- Square Footage: {_fmt_num(md.get('square_footage'), 0)} sqft",
            f"- Insulation: {_clean_text(md.get('insulation'))}",
            f"- Household Size: {_fmt_num(md.get('household_size'), 0)} occupants",
            f"- Housing Type: {_clean_text(md.get('housing_type'))}",
            f"- House Age: {_clean_text(md.get('house_age'))}",
            f"- Utility Budget: ${_fmt_num(md.get('utility_budget'), 0)}/month",
        ]
    if decision_type == "Appliance":
        return [
            f"- Location: {_clean_text(md.get('location'))}",
            f"- Appliance Age Range: {_clean_text(md.get('appliance_age'))}",
            f"- Household Size: {_fmt_num(md.get('household_size'), 0)} occupants",
            f"- Housing Type: {_clean_text(md.get('housing_type'))}",
            f"- Utility Budget: ${_fmt_num(md.get('utility_budget'), 0)}/month",
        ]
    if decision_type == "Shower":
        return [
            f"- Location: {_clean_text(md.get('location'))}",
            f"- Outdoor Temp: {_fmt_num(md.get('outdoor_temp'), 0)} deg F",
            f"- Flow Rate: {_clean_text(md.get('flow_rate'))}",
            f"- Household Size: {_fmt_num(md.get('household_size'), 0)} occupants",
            f"- Housing Type: {_clean_text(md.get('housing_type'))}",
            f"- Utility Budget: ${_fmt_num(md.get('utility_budget'), 0)}/month",
        ]
    return []


def format_target_prompt(scenario: Dict, alternative: str) -> str:
    decision_type = scenario["decision_type"]
    prompt = f'Score this alternative: "{alternative}"\n\n'
    prompt += f'For the decision: "{scenario.get("question", "N/A")}"\n\n'
    prompt += "SCENARIO CONTEXT:\n"
    prompt += "\n".join(_base_param_lines(decision_type, scenario))
    prompt += "\n\nProvide scores (0-1) for all 4 criteria.\n"
    prompt += "Consider how this specific alternative performs given the scenario context.\n"
    return prompt


def build_system_prompt() -> str:
    return """You are an expert household decision analyst specializing in Multi-Criteria Decision Analysis (MCDA).
You consistently utilize all information given in the scenario context. Score alternatives on four criteria using the inclusive 0-1 scale (0.0 <= score <= 1.0):
1. Energy Cost: Lower energy costs = higher score
2. Environmental Impact: Lower emissions = higher score
3. Comfort: Higher user comfort = higher score
4. Practicality: Easier to implement/maintain = higher score

Return ONLY: {"energy_cost": X, "environmental": X, "comfort": X, "practicality": X} where each X is between 0.0 and 1.0."""


def format_rag_context(retrieved: List[Dict], spec: Dict) -> str:
    if not retrieved:
        return ""
    include_scores = spec.get("include_scores", True)
    include_ranks = spec.get("include_ranks", True)
    include_hidden_params = spec.get("include_hidden_params", True)
    context = "RELEVANT SIMILAR SCENARIOS WITH EXPERT SCORES:\n\n"
    for i, item in enumerate(retrieved, 1):
        md = item["metadata"]
        decision_type = md.get("decision_type", "Unknown")
        context += f"Example {i}:\n"
        context += f"  Question: {md.get('question', 'N/A')}\n"
        context += "\n".join(f"  {line}" for line in _base_param_lines(decision_type, md))
        if include_hidden_params:
            context += "\n"
            context += "\n".join(f"  {line}" for line in _hidden_param_lines(decision_type, md))
        if include_scores:
            context += "\n  Expert scores:\n"
            for j in range(1, 4):
                alt = md.get(f"alt{j}")
                if alt in (None, "", "N/A"):
                    continue
                scores = {c: md.get(f"alt{j}_{c}") for c in CRITERIA}
                if any(scores[c] in (None, "") for c in CRITERIA):
                    continue
                context += (
                    f"  * {alt}: "
                    f"Energy Cost: {_fmt_num(scores['energy_cost'])}/1, "
                    f"Environmental: {_fmt_num(scores['environmental'])}/1, "
                    f"Comfort: {_fmt_num(scores['comfort'])}/1, "
                    f"Practicality: {_fmt_num(scores['practicality'])}/1"
                )
                if include_ranks:
                    context += f" | MAVT: {_fmt_num(md.get(f'alt{j}_mavt'), 2)}, Rank: {_fmt_num(md.get(f'alt{j}_rank'), 0)}"
                context += "\n"
        context += "\n"
    context += "Use these examples as reference, but score based on the specific scenario above.\n"
    return context


def query_openrouter(messages: List[Dict], model_id: str) -> Tuple[str, Dict]:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found. Use --ablations nearest-neighbor for an offline-only run.")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE,
    }
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": TEMPERATURE,
    }
    model_key = None
    for k, spec in MODEL_SPECS.items():
        if spec["openrouter_id"] == model_id:
            model_key = k
            break
    reasoning_payload = get_reasoning_payload(model_key) if model_key else get_reasoning_payload()
    if reasoning_payload is not None:
        payload["reasoning"] = reasoning_payload
    last_error = None
    response = None
    attempt = 0
    retry_forever = MAX_RETRIES <= 0
    while True:
        attempt += 1
        try:
            start = time.time()
            response = None
            import requests
            response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            latency_ms = (time.time() - start) * 1000
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                return content, {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "latency_ms": latency_ms,
                    "model": model_id,
                }
            last_error = f"Status {response.status_code}: {response.text}"
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            if _is_transient_http_status(response.status_code):
                logging.info("Transient API error on attempt %s: %s", attempt, response.status_code)
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
        except Exception as exc:
            last_error = str(exc)
            logging.info("Request failed on attempt %s: %s", attempt, exc)
            if not retry_forever and attempt >= MAX_RETRIES:
                break
            time.sleep(min(RETRY_BASE_DELAY * (2 ** min(attempt - 1, 5)), MAX_RETRY_BACKOFF))
    raise RuntimeError(f"failed_api_exhausted: Failed after {MAX_RETRIES} attempts. Last error: {last_error}")


def retrieve_similar(collection, model, scenario: Dict, k: int) -> List[Dict]:
    if k <= 0:
        return []
    target_source_id = int(scenario["source_scenario_id"])
    decision_type = scenario["decision_type"]
    query_text = format_embedding_text(decision_type, scenario)
    query_embedding = model.encode(query_text).tolist()
    retrieved = []
    candidate_k = min(max(k + 10, 20), collection.count())
    max_candidate_k = max(collection.count(), 1)
    while len(retrieved) < k and candidate_k <= max_candidate_k:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_k,
            where={"decision_type": decision_type},
        )
        if not results.get("ids") or not results["ids"][0]:
            break
        for doc_id, doc_text, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            metadata_source_id = metadata.get("source_scenario_id", doc_id)
            try:
                metadata_source_id = int(metadata_source_id)
            except (TypeError, ValueError):
                metadata_source_id = -1
            if metadata_source_id == target_source_id:
                continue
            if metadata.get("decision_type") != decision_type:
                continue
            retrieved.append({
                "id": doc_id,
                "text": doc_text,
                "metadata": metadata,
                "distance": float(distance),
            })
            if len(retrieved) >= k:
                break
        if len(retrieved) >= k:
            break
        candidate_k = min(candidate_k * 2, max_candidate_k)
    return retrieved[:k]


def retrieve_random(model, scenario: Dict, candidates: List[Dict], k: int, rng: np.random.Generator) -> List[Dict]:
    if k <= 0 or not candidates:
        return []
    target_id = scenario["scenario_id"]
    decision_type = scenario["decision_type"]
    eligible = [c for c in candidates if c["decision_type"] == decision_type and c["scenario_id"] != target_id]
    if not eligible:
        return []
    n = min(k, len(eligible))
    selected = list(rng.choice(len(eligible), size=n, replace=False))
    query_text = format_embedding_text(decision_type, scenario)
    query_embedding = model.encode(query_text)
    retrieved = []
    for idx in selected:
        candidate = eligible[int(idx)]
        doc_text = format_embedding_text(decision_type, candidate)
        candidate_embedding = model.encode(doc_text)
        distance = float(np.linalg.norm(query_embedding - candidate_embedding))
        retrieved.append({
            "id": candidate["scenario_id"],
            "text": doc_text,
            "metadata": candidate,
            "distance": distance,
        })
    return retrieved


def parse_scores(response_text: str) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
    text = response_text.strip()
    try:
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
    except Exception as exc:
        return None, f"failed_malformed_json: {exc}"
    scores = {}
    for criterion in CRITERIA:
        if criterion not in parsed:
            return None, f"failed_missing_score:{criterion}"
        raw = parsed[criterion]
        if not isinstance(raw, (int, float)):
            return None, "failed_invalid_score_type"
        value = float(raw)
        if not (0.0 <= value <= 1.0):
            return None, "failed_out_of_bounds"
        scores[criterion] = value
    return scores, None


def weighted_score(scores: Dict[str, float]) -> float:
    return sum(CRITERION_WEIGHTS[c] * scores[c] for c in CRITERIA)


def rank_from_scores(scores: List[float]) -> List[int]:
    ranks = [SENTINEL] * len(scores)
    valid_idx = [idx for idx, value in enumerate(scores) if value != SENTINEL and np.isfinite(value)]
    if not valid_idx:
        return ranks
    order = sorted(valid_idx, key=lambda idx: scores[idx], reverse=True)
    for rank, idx in enumerate(order, 1):
        ranks[int(idx)] = rank
    return ranks


def nearest_neighbor_prediction(scenario: Dict, retrieved: List[Dict]) -> Dict:
    predictions = []
    for target_alt in scenario["alternatives"]:
        alt_name = target_alt["alternative"]
        criterion_values = {c: [] for c in CRITERIA}
        for item in retrieved:
            md = item["metadata"]
            for j in range(1, 4):
                if md.get(f"alt{j}") == alt_name:
                    for criterion in CRITERIA:
                        value = _to_float(md.get(f"alt{j}_{criterion}"))
                        if not pd.isna(value):
                            criterion_values[criterion].append(value)
        if all(not values for values in criterion_values.values()):
            for item in retrieved:
                md = item["metadata"]
                for j in range(1, 4):
                    for criterion in CRITERIA:
                        value = _to_float(md.get(f"alt{j}_{criterion}"))
                        if not pd.isna(value):
                            criterion_values[criterion].append(value)
        pred_scores = {
            criterion: float(np.mean(values)) if values else SENTINEL
            for criterion, values in criterion_values.items()
        }
        predictions.append({
            "alternative": alt_name,
            "scores": pred_scores,
            "weighted_score": weighted_score(pred_scores) if all(pred_scores[c] != SENTINEL for c in CRITERIA) else SENTINEL,
            "failed": False,
        })
    ranks = rank_from_scores([p["weighted_score"] for p in predictions])
    for pred, rank in zip(predictions, ranks):
        pred["rank"] = rank
    return {
        "predictions": predictions,
        "diagnostics": {
            "api_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "latency_ms": 0.0,
        },
    }


def llm_prediction(scenario: Dict, spec: Dict, retrieved: List[Dict], model_id: str) -> Dict:
    predictions = []
    diagnostics = {
        "api_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": 0.0,
    }
    rag_context = format_rag_context(retrieved, spec)
    for alt in scenario["alternatives"]:
        user_prompt = rag_context + format_target_prompt(scenario, alt["alternative"])
        messages = [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]
        diagnostics["api_calls"] += 1
        try:
            response_text, call_diag = query_openrouter(messages, model_id)
            diagnostics["prompt_tokens"] += call_diag.get("prompt_tokens", 0)
            diagnostics["completion_tokens"] += call_diag.get("completion_tokens", 0)
            diagnostics["total_tokens"] += call_diag.get("total_tokens", 0)
            diagnostics["latency_ms"] += call_diag.get("latency_ms", 0.0)
            scores, error = parse_scores(response_text)
            if error:
                raise RuntimeError(error)
            predictions.append({
                "alternative": alt["alternative"],
                "scores": scores,
                "weighted_score": weighted_score(scores),
                "failed": False,
            })
            diagnostics["successful_calls"] += 1
        except Exception as exc:
            logging.info("LLM scoring failed for %s / %s: %s", scenario["question"], alt["alternative"], exc)
            predictions.append({
                "alternative": alt["alternative"],
                "scores": {c: SENTINEL for c in CRITERIA},
                "weighted_score": SENTINEL,
                "failed": True,
                "error": str(exc),
            })
            diagnostics["failed_calls"] += 1
    ranks = rank_from_scores([p["weighted_score"] for p in predictions])
    for pred, rank in zip(predictions, ranks):
        pred["rank"] = rank
    return {"predictions": predictions, "diagnostics": diagnostics}


def scenario_metrics(predictions: List[Dict], scenario: Dict) -> Dict:
    gt_by_alt = {alt["alternative"]: alt for alt in scenario["alternatives"]}
    pred_by_alt = {pred["alternative"]: pred for pred in predictions}
    common = [alt for alt in gt_by_alt if alt in pred_by_alt]
    gt_scores = np.array([gt_by_alt[alt]["mavt_score"] for alt in common], dtype=float)
    pred_scores = np.array([pred_by_alt[alt]["weighted_score"] for alt in common], dtype=float)
    valid = np.isfinite(gt_scores) & np.isfinite(pred_scores) & (pred_scores != SENTINEL)
    gt_scores = gt_scores[valid]
    pred_scores = pred_scores[valid]
    score_diff = pred_scores - gt_scores if len(pred_scores) else np.array([])
    if len(score_diff):
        score_mae = float(np.mean(np.abs(score_diff)))
        score_rmse = float(np.sqrt(np.mean(score_diff ** 2)))
    else:
        score_mae = np.nan
        score_rmse = np.nan
    if len(pred_scores) >= 2 and np.nanstd(pred_scores) > 0 and np.nanstd(gt_scores) > 0:
        try:
            kendalltau, spearmanr = _load_scipy_rank_metrics()
            tau = float(kendalltau(pred_scores, gt_scores).statistic)
            rho = float(spearmanr(pred_scores, gt_scores).statistic)
        except Exception:
            tau = np.nan
            rho = np.nan
    else:
        tau = np.nan
        rho = np.nan
    gt_top1 = sorted(common, key=lambda alt: gt_by_alt[alt]["mavt_score"], reverse=True)[0] if common else ""
    ranked_common = [alt for alt in common if pred_by_alt[alt]["weighted_score"] != SENTINEL]
    pred_order = sorted(ranked_common, key=lambda alt: pred_by_alt[alt]["weighted_score"], reverse=True) if ranked_common else []
    pred_top1 = pred_order[0] if pred_order else ""
    pred_top2 = set(pred_order[:2])
    return {
        "score_mae": score_mae,
        "score_rmse": score_rmse,
        "kendall_tau": tau,
        "spearman_rho": rho,
        "top1_correct": bool(gt_top1 and pred_top1 and gt_top1 == pred_top1),
        "top2_correct": bool(gt_top1 and gt_top1 in pred_top2),
        "gt_top1": gt_top1,
        "pred_top1": pred_top1,
    }


def scenario_level_df(rows_df: pd.DataFrame) -> pd.DataFrame:
    return rows_df.drop_duplicates(["model_key", "ablation_id", "ablation_label", "decision_type", "source_scenario_id"]).copy()


def summarize_rows(rows: List[Dict]) -> pd.DataFrame:
    df = scenario_level_df(pd.DataFrame(rows))
    metric_cols = [
        "score_mae", "score_rmse", "kendall_tau", "spearman_rho",
        "top1_accuracy", "top2_accuracy", "mean_retrieval_distance",
        "retrieval_count", "api_calls", "successful_calls", "failed_calls",
        "success_rate",
    ]
    summaries = []
    for (model_key, ablation_id, ablation_label), group in df.groupby(["model_key", "ablation_id", "ablation_label"], dropna=False):
        summary = {
            "model_key": model_key,
            "ablation_id": ablation_id,
            "ablation_label": ablation_label,
            "n_scenarios": int(group["source_scenario_id"].nunique()),
        }
        for col in metric_cols:
            if col not in group:
                summary[col] = np.nan
            elif col in {"api_calls", "successful_calls", "failed_calls", "retrieval_count"}:
                summary[col] = float(group[col].sum())
            elif col == "success_rate":
                denom = group["api_calls"].sum()
                summary[col] = float(group["successful_calls"].sum() / denom) if denom else np.nan
            else:
                summary[col] = float(pd.to_numeric(group[col], errors="coerce").mean())
        summaries.append(summary)
    return pd.DataFrame(summaries)


def summarize_by_decision_type(rows: List[Dict]) -> pd.DataFrame:
    df = scenario_level_df(pd.DataFrame(rows))
    metric_cols = ["score_mae", "score_rmse", "kendall_tau", "spearman_rho", "top1_accuracy", "top2_accuracy"]
    summaries = []
    for (model_key, ablation_id, ablation_label, decision_type), group in df.groupby(["model_key", "ablation_id", "ablation_label", "decision_type"], dropna=False):
        summary = {
            "model_key": model_key,
            "ablation_id": ablation_id,
            "ablation_label": ablation_label,
            "decision_type": decision_type,
            "n_scenarios": int(group["source_scenario_id"].nunique()),
        }
        for col in metric_cols:
            summary[col] = float(pd.to_numeric(group[col], errors="coerce").mean()) if col in group else np.nan
        summaries.append(summary)
    return pd.DataFrame(summaries)


def build_result_rows(sample: List[Dict], specs: OrderedDict, collections: Dict[str, Tuple], rng: np.random.Generator) -> List[Dict]:
    rows = []
    for ablation_id, spec in specs.items():
        temp_path, collection, model, groups_by_type = collections[spec["embedding_model"]]
        logging.info("Running ablation: %s", ablation_id)
        
        # Determine models to evaluate for this ablation
        if spec["llm"]:
            # Evaluate all models defined in MODEL_SPECS
            eval_models = [(k, info["openrouter_id"]) for k, info in MODEL_SPECS.items()]
        else:
            # Offline evaluations do not use LLMs, so we run them once
            eval_models = [("offline", "none")]
            
        for model_key, model_id in eval_models:
            if spec["llm"]:
                logging.info("  Evaluating model: %s (%s)", model_key, model_id)
            else:
                logging.info("  Evaluating offline NN prediction")
                
            for scenario in sample:
                decision_type = scenario["decision_type"]
                candidates = groups_by_type[decision_type]
                if spec["retrieval"] == "none":
                    retrieved = []
                elif spec["retrieval"] == "random":
                    retrieved = retrieve_random(model, scenario, candidates, spec["k"], rng)
                else:
                    retrieved = retrieve_similar(collection, model, scenario, spec["k"])
                    
                if spec["llm"]:
                    result = llm_prediction(scenario, spec, retrieved, model_id)
                else:
                    result = nearest_neighbor_prediction(scenario, retrieved)
                    
                predictions = result["predictions"]
                diag = result["diagnostics"]
                metrics = scenario_metrics(predictions, scenario)
                mean_distance = float(np.mean([item["distance"] for item in retrieved])) if retrieved else np.nan
                for pred in predictions:
                    rows.append({
                        "model_key": model_key,
                        "ablation_id": ablation_id,
                        "ablation_label": spec["label"],
                        "sample_seed": int(scenario["source_scenario_id"]),
                        "decision_type": decision_type,
                        "source_scenario_id": int(scenario["source_scenario_id"]),
                        "source_position": int(scenario["source_position"]),
                        "question": scenario.get("question", ""),
                        "location": scenario.get("location", ""),
                        "retrieval_mode": spec["retrieval"],
                        "embedding_model": spec["embedding_model"],
                        "k": int(spec["k"]),
                        "include_hidden_params": bool(spec["include_hidden_params"]),
                        "include_scores": bool(spec["include_scores"]),
                        "include_ranks": bool(spec["include_ranks"]),
                        "llm": bool(spec["llm"]),
                        "alternative": pred["alternative"],
                        "pred_energy_cost": pred["scores"].get("energy_cost", SENTINEL),
                        "pred_environmental": pred["scores"].get("environmental", SENTINEL),
                        "pred_comfort": pred["scores"].get("comfort", SENTINEL),
                        "pred_practicality": pred["scores"].get("practicality", SENTINEL),
                        "pred_weighted_score": pred["weighted_score"],
                        "pred_rank": pred["rank"],
                        "gt_mavt_score": next((alt["mavt_score"] for alt in scenario["alternatives"] if alt["alternative"] == pred["alternative"]), np.nan),
                        "gt_rank": next((alt["rank"] for alt in scenario["alternatives"] if alt["alternative"] == pred["alternative"]), SENTINEL),
                        "mean_retrieval_distance": mean_distance,
                        "retrieval_count": len(retrieved),
                        "score_mae": metrics["score_mae"],
                        "score_rmse": metrics["score_rmse"],
                        "kendall_tau": metrics["kendall_tau"],
                        "spearman_rho": metrics["spearman_rho"],
                        "top1_correct": metrics["top1_correct"],
                        "top2_correct": metrics["top2_correct"],
                        "gt_top1": metrics["gt_top1"],
                        "pred_top1": metrics["pred_top1"],
                        "api_calls": int(diag.get("api_calls", 0)),
                        "successful_calls": int(diag.get("successful_calls", 0)),
                        "failed_calls": int(diag.get("failed_calls", 0)),
                        "prompt_tokens": int(diag.get("prompt_tokens", 0)),
                        "completion_tokens": int(diag.get("completion_tokens", 0)),
                        "total_tokens": int(diag.get("total_tokens", 0)),
                        "latency_ms": float(diag.get("latency_ms", 0.0)),
                        "error": pred.get("error", ""),
                    })
    return rows


def _atomic_write_xlsx(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_excel(tmp, index=False, engine="openpyxl")
    os.replace(tmp, path)


def _format_md_table(df: pd.DataFrame, float_cols=None, max_rows: Optional[int] = None) -> str:
    float_cols = set(float_cols or [])
    if df is None or df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows).copy()
    rendered = df.copy()
    for col in rendered.columns:
        if col in float_cols:
            rendered[col] = rendered[col].map(lambda v: "N/A" if pd.isna(v) else f"{float(v):.4f}")
        else:
            rendered[col] = rendered[col].map(lambda v: "" if pd.isna(v) else str(v))
    headers = list(rendered.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def make_plots(summary_df: pd.DataFrame, output_dir: Path) -> List[Path]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    if summary_df.empty:
        return []
    plot_paths = []
    ordered = summary_df.sort_values(["model_key", "ablation_id"])
    for metric, filename, ylabel in [
        ("top1_accuracy", "rag_ablation_top1_accuracy.png", "Top-1 accuracy"),
        ("score_mae", "rag_ablation_score_mae.png", "Score MAE"),
        ("mean_retrieval_distance", "rag_ablation_retrieval_distance.png", "Mean retrieval distance"),
    ]:
        if metric not in ordered.columns or ordered[metric].isna().all():
            continue
        labels = (ordered["model_key"].astype(str) + " - " + ordered["ablation_label"].astype(str)).tolist()
        values = ordered[metric].astype(float).tolist()
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(range(len(labels)), values, color="#4C78A8")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(f"RAG ablation: {ylabel}")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        path = output_dir / filename
        fig.savefig(path, dpi=180)
        plt.close(fig)
        plot_paths.append(path)
    return plot_paths


def write_report(output_path: Path, sample_size: Optional[int], seed: int, specs: OrderedDict, summary_df: pd.DataFrame, dtype_summary_df: pd.DataFrame, rows_df: pd.DataFrame, plot_paths: List[Path]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sections = []
    sections.append("## Overview\n\n" + "\n".join([
        f"- Sample size: {'all' if sample_size is None else sample_size}",
        f"- Random seed: {seed}",
        f"- Scenarios evaluated: {rows_df['source_scenario_id'].nunique() if not rows_df.empty else 0}",
        f"- Result rows: {len(rows_df)}",
        f"- Output plots: {', '.join('`' + str(p) + '`' for p in plot_paths) if plot_paths else 'None'}",
    ]))

    config_rows = []
    for ablation_id, spec in specs.items():
        config_rows.append({
            "ablation_id": ablation_id,
            "label": spec["label"],
            "k": spec["k"],
            "retrieval": spec["retrieval"],
            "embedding_model": spec["embedding_model"],
            "include_hidden_params": spec["include_hidden_params"],
            "include_scores": spec["include_scores"],
            "include_ranks": spec["include_ranks"],
            "llm": spec["llm"],
        })
    sections.append("## Ablation Configurations\n\n" + _format_md_table(pd.DataFrame(config_rows)))
    sections.append("## Overall Summary\n\n" + _format_md_table(
        summary_df,
        float_cols=[c for c in summary_df.columns if c not in {"model_key", "ablation_id", "ablation_label", "n_scenarios"}],
    ))
    sections.append("## Summary by Decision Type\n\n" + _format_md_table(
        dtype_summary_df,
        float_cols=[c for c in dtype_summary_df.columns if c not in {"model_key", "ablation_id", "ablation_label", "decision_type", "n_scenarios"}],
    ))
    worst = rows_df.sort_values("score_mae", ascending=False).head(20) if not rows_df.empty else pd.DataFrame()
    sections.append("## Highest Score-MAE Cases\n\n" + _format_md_table(
        worst[[
            "model_key", "ablation_id", "decision_type", "source_scenario_id", "question", "alternative",
            "score_mae", "kendall_tau", "gt_top1", "pred_top1", "error",
        ]] if not worst.empty else worst,
        float_cols=["score_mae", "kendall_tau"],
    ))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# RAG Ablation Study\n\n")
        for section in sections:
            f.write(section + "\n\n")


def run(args) -> Dict:
    sample_size = parse_sample_size(args.sample_size)
    ablation_ids = set(args.ablations)
    specs = OrderedDict((k, v) for k, v in ABLATION_SPECS.items() if k in ablation_ids)
    if not specs:
        raise ValueError("No ablations selected")
    if any(spec["llm"] for spec in specs.values()) and not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found. Use --ablations nearest-neighbor for an offline-only run.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    groups_by_type = load_source_groups()
    sample = stratified_sample(groups_by_type, sample_size, args.seed)
    logging.info("Loaded %s source scenarios; sampled %s", sum(len(v) for v in groups_by_type.values()), len(sample))

    temp_root = PROJECT_ROOT / ".rag_ablation_temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    embedding_models = sorted({spec["embedding_model"] for spec in specs.values()})
    collections = {}
    for embedding_model_name in embedding_models:
        logging.info("Building temporary Chroma collection with %s", embedding_model_name)
        collections[embedding_model_name] = build_collection(embedding_model_name, temp_root)

    rng = np.random.default_rng(args.seed)
    rows = build_result_rows(sample, specs, collections, rng)
    rows_df = pd.DataFrame(rows)
    rows_df["top1_accuracy"] = rows_df["top1_correct"].astype(float)
    rows_df["top2_accuracy"] = rows_df["top2_correct"].astype(float)
    rows_df["success_rate"] = np.where(rows_df["api_calls"] > 0, rows_df["successful_calls"] / rows_df["api_calls"], np.nan)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "rag_ablation_results.xlsx"
    summary_path = output_dir / "rag_ablation_summary.xlsx"
    dtype_summary_path = output_dir / "rag_ablation_summary_by_decision_type.xlsx"
    report_path = Path(args.output)
    _atomic_write_xlsx(rows_df, results_path)
    summary_df = summarize_rows(rows)
    dtype_summary_df = summarize_by_decision_type(rows)
    _atomic_write_xlsx(summary_df, summary_path)
    _atomic_write_xlsx(dtype_summary_df, dtype_summary_path)
    plot_paths = make_plots(summary_df, output_dir)
    write_report(report_path, sample_size, args.seed, specs, summary_df, dtype_summary_df, rows_df, plot_paths)

    print("\nRAG ABLATION COMPLETE")
    print(f"Sample size: {'all' if sample_size is None else sample_size}")
    print(f"Scenarios: {rows_df['source_scenario_id'].nunique()}")
    print(f"Rows: {len(rows_df)}")
    print(_format_md_table(summary_df, float_cols=[c for c in summary_df.columns if c not in {"model_key", "ablation_id", "ablation_label", "n_scenarios"}]))
    print(f"\nResults saved to: {results_path}")
    print(f"Report saved to: {report_path}")

    return {
        "rows": rows_df,
        "summary": summary_df,
        "by_decision_type": dtype_summary_df,
        "results_path": results_path,
        "report_path": report_path,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run RAG retrieval and exemplar ablations.")
    parser.add_argument(
        "--sample-size",
        default="15",
        help="Number of source scenarios to sample, stratified by decision type. Use 'all' for the full RAG source set.",
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument(
        "--ablations",
        nargs="+",
        default=list(ABLATION_SPECS.keys()),
        choices=list(ABLATION_SPECS.keys()),
        help="Ablation IDs to run. Default: all ablations.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Directory for Excel outputs and plots.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "rag_ablation_results.md"),
        help="Markdown report output path.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
