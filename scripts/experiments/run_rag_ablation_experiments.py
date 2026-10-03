import argparse
import hashlib
import json
import logging
import math
import os
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
for _import_root in (_BOOTSTRAP_ROOT / "src", _BOOTSTRAP_ROOT):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from llm_mcda.common.paths import (
    RUN_OUTPUT_DIR_ENV,
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_directory,
    require_safe_output_path,
)
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import numpy as np
import pandas as pd

from llm_mcda.common.model_config import (
    CRITERION_WEIGHTS,
    MAX_RETRIES,
    MAX_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
    RETRY_BASE_DELAY,
    TEMPERATURE,
    _is_transient_http_status,
    get_model_id,
    get_reasoning_payload,
    MODEL_SPECS,
)

from llm_mcda.common.sentinel_utils import (
    CRITERIA,
    FAILED_API_BAD_REQUEST,
    FAILED_TRUNCATED,
    SENTINEL_FLOAT,
    RawCallLog,
    RunAbort,
    build_openrouter_payload,
    call_log_fields,
    openrouter_chat,
    response_meta,
    appliance_age_to_band_label,
    apply_mavt_ranking,
    format_embedding_text,
    gpm_to_flow_rate_label,
    house_age_to_band_label,
    read_table_clean,
)

from scripts.archive.legacy.CreateRepresentativeSample import (
    stratified_sample_by_features as stratified_sample,
)
SCENARIO_DIR = PROJECT_ROOT / "workbooks/scenarios"

SENTINEL = SENTINEL_FLOAT
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ALTERNATE_EMBEDDING_MODEL = "sentence-transformers/paraphrase-MiniLM-L3-v2"

from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://local.app/llm-mcda")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM-MCDA-Paper")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Per-call raw archive, same mechanism as the architectures (sentinel_utils.RawCallLog).
# Disabled unless .start() is called. LLM scoring runs on a thread pool, so the
# file write is serialised by this lock rather than relying on .set_scenario(),
# which is not thread-safe.
RAW_LOG = RawCallLog()
_raw_log_lock = threading.Lock()

# Set when any worker hits a RunAbort (HTTP 401/402/403, or the shared
# consecutive-failure breaker in sentinel_utils.openrouter_chat). Workers check
# it before each call and the pool cancels queued scenarios, so an
# out-of-credit run stops paying at once; the unit is never checkpointed.
_ABORT = threading.Event()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Parse-error codes for a call with no usable completion (lower-case, like the
# rest of this script's codes).
ERR_API_EXHAUSTED = "failed_api_exhausted"
ERR_API_BAD_REQUEST = "failed_api_bad_request"
ERR_TRUNCATED = "failed_truncated"
ERR_EMPTY = "failed_empty_response"


class RagCallFailed(RuntimeError):
    """A call that ended without a completion (retries exhausted, or a
    400/404/422 on its one retry). The message starts with the failure code;
    `attempt_errors` and `diagnostics` carry the per-attempt record."""

    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics
        self.attempt_errors = diagnostics.get("attempt_errors")

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
    if value == SENTINEL:
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
                "source_scenario_id": f"{decision_type.lower()}_{scenario_id}",
                "source_scenario_numeric": scenario_id,
                "source_position": source_position,
                "filename": filename,
                "alternatives": alternatives,
            })
            groups.append(metadata)
        groups_by_type[decision_type] = groups
    return groups_by_type



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
            metadata["source_scenario_id"] = scenario["source_scenario_id"]
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


# Kept under its old name for any caller; the fields are sentinel_utils'.
_response_meta = response_meta


def _call_diagnostics(call: Dict, model_id: str) -> Dict:
    """This script's per-call diagnostics from an openrouter_chat result."""
    return {
        "prompt_tokens": call.get("prompt_tokens", 0),
        "completion_tokens": call.get("completion_tokens", 0),
        "total_tokens": call.get("total_tokens", 0),
        "latency_ms": call.get("latency_ms", 0.0),
        "model": model_id,
        "failure_type": call.get("failure_type"),
        **call_log_fields(call),
    }


def query_openrouter(messages: List[Dict], model_id: str) -> Tuple[str, Dict]:
    """POST through the architectures' shared client,
    sentinel_utils.openrouter_chat: same payload builder (max_tokens
    MAX_OUTPUT_TOKENS, the MODEL_SPECS provider pin for model_id), same retry
    policy from model_config, same failure rules.

    Returns (content, diagnostics). A truncated reply (finish_reason length)
    returns its partial text with diagnostics["failure_type"] ==
    FAILED_TRUNCATED; the caller must not parse it. Raises RagCallFailed when
    retries are exhausted or a 400/404/422 repeats, and OpenRouterFatalError
    (a RunAbort) on 401/402/403 or the consecutive-failure breaker.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found. Use --ablations nearest_neighbor_k3 for an offline-only run.")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_APP_TITLE,
    }
    model_key = None
    for k, spec in MODEL_SPECS.items():
        if spec["openrouter_id"] == model_id:
            model_key = k
            break
    reasoning_payload = get_reasoning_payload(model_key) if model_key else get_reasoning_payload()
    payload = build_openrouter_payload(model_id, messages, TEMPERATURE, reasoning_payload)
    # logger=None: one console line per call would flood an 8-worker run; every
    # attempt is kept in the raw jsonl instead.
    call = openrouter_chat(
        payload, headers,
        endpoint=OPENROUTER_URL,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
        is_transient=_is_transient_http_status,
        base_delay=RETRY_BASE_DELAY,
        max_backoff=MAX_RETRY_BACKOFF,
        logger=None,
    )
    diagnostics = _call_diagnostics(call, model_id)
    failure_type = call.get("failure_type")
    if failure_type and failure_type != FAILED_TRUNCATED:
        code = ERR_API_BAD_REQUEST if failure_type == FAILED_API_BAD_REQUEST else ERR_API_EXHAUSTED
        errors = call.get("attempt_errors") or []
        last = errors[-1].get("detail") if errors else None
        raise RagCallFailed(
            f"{code}: failed after {call.get('attempts')} attempt(s). Last error: {last}",
            diagnostics)
    if failure_type == FAILED_TRUNCATED:
        logging.warning("truncated reply (finish_reason=%s) from %s; call fails as %s",
                        call.get("finish_reason"), model_id, ERR_TRUNCATED)
    return call.get("content"), diagnostics


def retrieve_similar(collection, model, scenario: Dict, k: int) -> List[Dict]:
    if k <= 0:
        return []
    target_source_id = scenario["source_scenario_id"]
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
            metadata_source_id = str(metadata.get("source_scenario_id", doc_id))
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
    """Superseded by apply_mavt_ranking at both call sites (B60): this breaks
    weighted_score ties by list position, not TIE_BREAK_PRIORITY. Left in place,
    unused, rather than deleted, since it is not the change B60 asked for."""
    ranks = [SENTINEL] * len(scores)
    valid_idx = [idx for idx, value in enumerate(scores) if value != SENTINEL and np.isfinite(value)]
    if not valid_idx:
        return ranks
    order = sorted(valid_idx, key=lambda idx: scores[idx], reverse=True)
    for rank, idx in enumerate(order, 1):
        ranks[int(idx)] = rank
    return ranks


NN_FALLBACKS = ("tie", "nearest", "unscored")


def canonical_alternative(value, decision_type: str):
    """One comparable key for an alternative label, used on BOTH sides of the
    nearest-neighbour match. The three callers spell the same alternative
    differently: the index metadata stores Shower as "8 min", the test-set NN
    passes 8.0 and the RAG ablation passes "8"; HVAC comes as 72 or "72".
    Returns:
      HVAC      -> int setpoint (72), or "off" (plus "_<n>" if a number follows)
      Appliance -> minutes after midnight (int), from "2:00 PM" / "2pm" / "14:00"
      Shower    -> duration in minutes (float), from 8, "8", "8.0", "8 min"
    Anything unparseable comes back as the stripped upper-case string, so it
    can still match itself exactly."""
    import re
    text = _clean_text(value)
    if decision_type == "Shower":
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        return float(m.group(1)) if m else text.upper()
    if decision_type == "HVAC":
        low = text.lower()
        if "off" in low:
            m = re.search(r"(\d+(?:\.\d+)?)", low)
            return f"off_{m.group(1)}" if m else "off"
        try:
            return int(round(float(text)))
        except ValueError:
            return text.upper()
    if decision_type == "Appliance":
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?\s*[Mm]", text)
        if m:
            hour, minute = int(m.group(1)) % 12, int(m.group(2) or 0)
            if m.group(3).lower() == "p":
                hour += 12
            return hour * 60 + minute
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
        if m:
            return int(m.group(1)) * 60 + int(m.group(2))
        return text.upper()
    return text


def _alternative_distance(a, b, decision_type: str) -> Optional[float]:
    """Distance between two canonical keys in the alternative's own unit:
    setpoint degrees (HVAC), clock minutes on a 24 h circle (Appliance),
    shower minutes (Shower). None if either side has no numeric value (HVAC
    "off")."""
    if isinstance(a, str) or isinstance(b, str):
        return None
    d = abs(float(a) - float(b))
    if decision_type == "Appliance":
        d = min(d, 1440.0 - d)
    return d


def nearest_neighbor_prediction(scenario: Dict, retrieved: List[Dict], fallback: str = "tie") -> Dict:
    """Copy-only prediction: each target alternative gets the mean criterion
    scores of the retrieved exemplars' alternatives with the same label, both
    labels compared through `canonical_alternative`.

    `fallback` decides a target alternative that no exemplar shares:
      tie      -- mean over every retrieved alternative (the original rule; if
                  all three targets miss, all three tie and the tie-break,
                  finally list order, decides)
      nearest  -- mean over the exemplar alternatives nearest in value
                  (`_alternative_distance`); a target with no numeric value
                  (HVAC "Off") or no numeric exemplar falls back to `tie`
      unscored -- if NO target alternative matches (the case where `tie`
                  gives three identical predictions), the scenario is unscored:
                  every alternative gets the sentinel, so it drops out of the
                  means like any failed prediction. A partial miss keeps the
                  `tie` rule for the missing alternative."""
    if fallback not in NN_FALLBACKS:
        raise ValueError(f"fallback must be one of {NN_FALLBACKS}, got {fallback!r}")
    decision_type = scenario["decision_type"]
    exemplar_alts = []  # (canonical key, {criterion: value}) for every retrieved alternative
    for item in retrieved:
        md = item["metadata"]
        for j in range(1, 4):
            label = md.get(f"alt{j}")
            if label in (None, ""):
                continue
            scores = {c: _to_float(md.get(f"alt{j}_{c}")) for c in CRITERIA}
            exemplar_alts.append((canonical_alternative(label, decision_type), scores))

    def _collect(keys_ok):
        values = {c: [] for c in CRITERIA}
        for key, scores in exemplar_alts:
            if keys_ok(key):
                for criterion in CRITERIA:
                    if not pd.isna(scores[criterion]):
                        values[criterion].append(scores[criterion])
        return values

    predictions = []
    unmatched = 0
    for target_alt in scenario["alternatives"]:
        alt_name = target_alt["alternative"]
        target_key = canonical_alternative(alt_name, decision_type)
        criterion_values = _collect(lambda key: key == target_key)
        if all(not values for values in criterion_values.values()):
            unmatched += 1
            if fallback == "nearest":
                dists = [_alternative_distance(target_key, key, decision_type) for key, _ in exemplar_alts]
                finite = [d for d in dists if d is not None]
                if finite:
                    best = min(finite)
                    criterion_values = {c: [] for c in CRITERIA}
                    for (_, scores), d in zip(exemplar_alts, dists):
                        if d is not None and d <= best + 1e-9:
                            for criterion in CRITERIA:
                                if not pd.isna(scores[criterion]):
                                    criterion_values[criterion].append(scores[criterion])
            if all(not values for values in criterion_values.values()):
                criterion_values = _collect(lambda key: True)
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
    if fallback == "unscored" and predictions and unmatched == len(predictions):
        for pred in predictions:
            pred["scores"] = {c: SENTINEL for c in CRITERIA}
            pred["weighted_score"] = SENTINEL
            pred["failed"] = True
            pred["error"] = "nn_unscored: no alternative shares a label with any retrieved exemplar"
    # Tie-broken via apply_mavt_ranking's deterministic TIE_BREAK_PRIORITY sort
    # key (B60), not rank_from_scores's positional stable-sort tie-break.
    mavt_input = [{"alternative": p["alternative"], **p["scores"]} for p in predictions]
    ranks = apply_mavt_ranking(mavt_input)["ranks"]
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
        if _ABORT.is_set():
            raise RunAbort("aborted: another worker hit a fatal OpenRouter error")
        diagnostics["api_calls"] += 1

        def _record(response_text, call_diag, api_success, error=None, parse_error=None):
            with _raw_log_lock:
                RAW_LOG.record(
                    scenario_id=scenario.get("source_scenario_id"),
                    decision_type=scenario.get("decision_type", ""),
                    ablation=spec.get("label"),
                    k=spec.get("k"),
                    retrieval_mode=spec.get("retrieval"),
                    retrieved_ids=[r.get("id") for r in retrieved],
                    retrieved_distances=[r.get("distance") for r in retrieved],
                    alternative=alt["alternative"],
                    model=model_id,
                    system_prompt_sha256=hashlib.sha256(messages[0]["content"].encode("utf-8")).hexdigest(),
                    prompt=user_prompt,
                    prompt_sha256=hashlib.sha256(user_prompt.encode("utf-8")).hexdigest(),
                    response=response_text or "",
                    prompt_tokens=call_diag.get("prompt_tokens", 0),
                    completion_tokens=call_diag.get("completion_tokens", 0),
                    latency_ms=call_diag.get("latency_ms", 0),
                    failure_type=call_diag.get("failure_type"),
                    error=error,
                    **call_log_fields(call_diag),
                    api_success=api_success,
                    parse_error=parse_error,
                )

        try:
            try:
                response_text, call_diag = query_openrouter(messages, model_id)
            except RunAbort as abort:
                # 401/402/403 or the breaker: archive the failing call, stop
                # every worker, and let the abort propagate (never caught below).
                _record("", _call_diagnostics(getattr(abort, "diagnostics", {}) or {}, model_id),
                        False, error=str(abort))
                _ABORT.set()
                raise
            except Exception as call_exc:
                # query_openrouter raises (rather than returning a diagnostics
                # dict) once MAX_RETRIES is exhausted or a bad request repeats,
                # so the ordinary record below is never reached for that call.
                # Log it here instead, with every attempt's error.
                _record("", getattr(call_exc, "diagnostics", None) or {}, False, error=str(call_exc))
                raise
            diagnostics["prompt_tokens"] += call_diag.get("prompt_tokens", 0) or 0
            diagnostics["completion_tokens"] += call_diag.get("completion_tokens", 0) or 0
            diagnostics["total_tokens"] += call_diag.get("total_tokens", 0) or 0
            diagnostics["latency_ms"] += call_diag.get("latency_ms", 0.0) or 0.0
            if call_diag.get("failure_type") == FAILED_TRUNCATED:
                scores, error = None, ERR_TRUNCATED   # partial text logged, never parsed
            elif not (response_text or "").strip():
                scores, error = None, ERR_EMPTY       # content null / "" / whitespace
            else:
                try:
                    scores, error = parse_scores(response_text)
                except Exception as parse_exc:
                    scores, error = None, f"failed_parse_exception: {parse_exc}"
            _record(response_text, call_diag, True, parse_error=error)
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
    # Tie-broken via apply_mavt_ranking's deterministic TIE_BREAK_PRIORITY sort
    # key (B60), not rank_from_scores's positional stable-sort tie-break.
    mavt_input = [{"alternative": p["alternative"], **p["scores"]} for p in predictions]
    ranks = apply_mavt_ranking(mavt_input)["ranks"]
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
            _, spearmanr = _load_scipy_rank_metrics()
            rho = float(spearmanr(pred_scores, gt_scores).statistic)
        except Exception:
            rho = np.nan
    else:
        rho = np.nan

    # Tau uses the tie-broken ranks, not raw scores (B60): both sides already
    # carry the TIE_BREAK_PRIORITY tie-break -- gt_by_alt[alt]["rank"] from the
    # ground truth's own apply_mavt_ranking output, pred_by_alt[alt]["rank"] from
    # this file's apply_mavt_ranking call above -- so tau is never tau_b on ties.
    rank_common = [alt for alt in common if pred_by_alt[alt]["rank"] != SENTINEL]
    gt_ranks = [gt_by_alt[alt]["rank"] for alt in rank_common]
    pred_ranks = [pred_by_alt[alt]["rank"] for alt in rank_common]
    if len(pred_ranks) >= 2 and len(set(pred_ranks)) > 1 and len(set(gt_ranks)) > 1:
        try:
            kendalltau, _ = _load_scipy_rank_metrics()
            tau = float(kendalltau(pred_ranks, gt_ranks).statistic)
        except Exception:
            tau = np.nan
    else:
        tau = np.nan
    # Top-1 / Top-2 also come from the tie-broken ranks (rank == 1, rank <= 2),
    # so an exact score tie is decided by TIE_BREAK_PRIORITY, as for tau,
    # rather than by input order in a sort on the raw sums.
    gt_top1 = next((alt for alt in common if gt_by_alt[alt]["rank"] == 1), "")
    pred_top1 = next((alt for alt in rank_common if pred_by_alt[alt]["rank"] == 1), "")
    pred_top2 = {alt for alt in rank_common if pred_by_alt[alt]["rank"] <= 2}
    # Accuracy rule (author decision, 2026-09-27): a scenario whose prediction
    # failed or is unscored -- ANY alternative failed (API failure, truncation,
    # parse error, the copy-only 'unscored' fallback) or carries no valid rank --
    # counts as WRONG for Top-1 and Top-2, and stays in the denominator, which
    # is every scenario in the arm. Before, a partial failure could still score
    # a hit from the surviving alternatives. Tau / MAE are not accuracy metrics
    # and are unchanged.
    scenario_failed = (
        not predictions
        or any(pred.get("failed") for pred in predictions)
        or len(rank_common) < len(common)
        or not common
    )
    return {
        "score_mae": score_mae,
        "score_rmse": score_rmse,
        "kendall_tau": tau,
        "spearman_rho": rho,
        "top1_correct": (not scenario_failed) and bool(gt_top1 and pred_top1 and gt_top1 == pred_top1),
        "top2_correct": (not scenario_failed) and bool(gt_top1 and gt_top1 in pred_top2),
        "gt_top1": gt_top1,
        "pred_top1": pred_top1,
        "scenario_failed": bool(scenario_failed),
    }


# Failure rule (S4, author decisions 2026-09-29), the same one the main suite
# applies (evaluate_architecture_metrics.FAILED_SCENARIO_*): a failed scenario
# stays in every denominator; Top-1/Top-2 wrong (already so in scenario_metrics),
# tau and rho 0 (chance), and the MAVT-score MAE/RMSE at the chance-level error
# of a uniform-random score on the 0-1 scale, E|U - t| = (t^2 + (1-t)^2)/2 and
# E(U - t)^2 = (t^3 + (1-t)^3)/3, from the scenario's reference MAVT scores t.
FAILED_SCENARIO_TAU = 0.0
FAILED_SCENARIO_RHO = 0.0


def apply_failure_rule(scen: pd.DataFrame, rows_df: pd.DataFrame) -> pd.DataFrame:
    """Fill the failed scenarios of the one-row-per-scenario frame `scen` under
    the failure rule, using the per-alternative reference MAVT scores in
    `rows_df`. Rows written before the rule (NaN tau/MAE) are fixed here, so
    --recompute-significance-only applies it to already-collected data."""
    if "scenario_failed" not in scen or not scen["scenario_failed"].astype(bool).any():
        return scen
    keys = ["model_key", "ablation_id", "ablation_label", "decision_type", "source_scenario_id"]
    t = pd.to_numeric(rows_df["gt_mavt_score"], errors="coerce")
    chance = (rows_df.assign(_abs=(t ** 2 + (1 - t) ** 2) / 2,
                             _sq=(t ** 3 + (1 - t) ** 3) / 3)
              .groupby(keys, dropna=False)[["_abs", "_sq"]].mean())
    scen = scen.copy()
    failed = scen["scenario_failed"].astype(bool)
    idx = pd.MultiIndex.from_frame(scen.loc[failed, keys])
    scen.loc[failed, "kendall_tau"] = FAILED_SCENARIO_TAU
    scen.loc[failed, "spearman_rho"] = FAILED_SCENARIO_RHO
    scen.loc[failed, "score_mae"] = chance["_abs"].reindex(idx).values
    scen.loc[failed, "score_rmse"] = np.sqrt(chance["_sq"].reindex(idx).values)
    return scen


def scenario_level_df(rows_df: pd.DataFrame) -> pd.DataFrame:
    scen = rows_df.drop_duplicates(["model_key", "ablation_id", "ablation_label", "decision_type", "source_scenario_id"]).copy()
    return apply_failure_rule(scen, rows_df)


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
            # Failed scenarios stay in every denominator (failure rule, S4):
            # wrong for Top-1/Top-2, chance level for tau, rho and MAE.
            "n_failed_scenarios": (int(group["scenario_failed"].astype(bool).sum())
                                   if "scenario_failed" in group else np.nan),
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
            "n_failed_scenarios": (int(group["scenario_failed"].astype(bool).sum())
                                   if "scenario_failed" in group else np.nan),
        }
        for col in metric_cols:
            summary[col] = float(pd.to_numeric(group[col], errors="coerce").mean()) if col in group else np.nan
        summaries.append(summary)
    return pd.DataFrame(summaries)


def cliff_delta(x, y):
    """Compute Cliff's delta effect size between two paired samples.

    Cliff's delta is a non-parametric effect size measure that quantifies
    the degree of difference between two groups.  It ranges from -1 to +1:

        |delta| < 0.147  = negligible
        |delta| < 0.33   = small
        |delta| < 0.474  = medium
        |delta| >= 0.474  = large

    Non-finite values (NaN, inf) are removed before computation.  Returns
    (nan, "") if either array is empty after filtering.

    Args:
        x: array-like of scores for group 1.
        y: array-like of scores for group 2.

    Returns:
        Tuple of (delta, interpretation) where *delta* is a float in [-1, 1]
        and *interpretation* is one of "negligible", "small", "medium", "large",
        or (nan, "") when insufficient data is available.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return float('nan'), ""
    concordant = sum(np.sum(xi > y) for xi in x)
    discordant = sum(np.sum(xi < y) for xi in x)
    delta = (concordant - discordant) / (n_x * n_y)
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        interpretation = "negligible"
    elif abs_delta < 0.33:
        interpretation = "small"
    elif abs_delta < 0.474:
        interpretation = "medium"
    else:
        interpretation = "large"
    return delta, interpretation


def matched_pairs_rank_biserial(x, y):
    """Matched-pairs rank-biserial correlation, the effect size that belongs to
    the Wilcoxon signed-rank test (S3): (sum of positive ranks - sum of
    negative ranks) / total rank sum, over the non-zero paired differences,
    ranked by |d| with midranks. In [-1, 1]; positive means x > y. Returns
    (r, n_nonzero); r is 0.0 when every difference is zero.

    Cliff's delta (cliff_delta above) compares every x with every y, ignoring
    the pairing, so next to a paired test it can read "negligible" for a large
    paired effect. It is kept as a descriptive column only."""
    from scipy.stats import rankdata
    d = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    d = d[np.isfinite(d) & (d != 0)]
    if len(d) == 0:
        return 0.0, 0
    r = rankdata(np.abs(d))
    return float((r[d > 0].sum() - r[d < 0].sum()) / r.sum()), int(len(d))


def rank_biserial_interpretation(r):
    """Magnitude label for a rank-biserial correlation (|r| < 0.1 negligible,
    < 0.3 small, < 0.5 medium, else large), the correlation thresholds the
    main-suite significance script uses."""
    a = abs(r)
    if a < 0.1:
        return "negligible"
    if a < 0.3:
        return "small"
    if a < 0.5:
        return "medium"
    return "large"


def friedman_test_per_metric(scenario_df: pd.DataFrame, metric_cols: List[str],
                             config_col: str = 'ablation_id',
                             scenario_col: str = 'source_scenario_id') -> pd.DataFrame:
    """Perform Friedman tests for each metric across ablation configurations.

    The Friedman test is a non-parametric alternative to a repeated-measures
    ANOVA.  It tests whether there are statistically significant differences
    between two or more related groups (here: ablation configurations evaluated
    on the same set of scenarios).

    A significant result (p < 0.05) indicates that at least one configuration
    differs from the others for that metric.  Use post-hoc pairwise tests to
    determine which specific pairs differ.

    Args:
        scenario_df: DataFrame with one row per (config, scenario) combination.
        metric_cols: list of column names to test.
        config_col: column identifying the ablation configuration.
        scenario_col: column identifying the scenario.

    Returns:
        DataFrame with columns: metric, chi2, p_value, df, n_scenarios, n_configs.
    """
    from scipy.stats import friedmanchisquare

    results = []
    for metric in metric_cols:
        if metric not in scenario_df.columns:
            continue
        pivoted = scenario_df.pivot_table(
            index=scenario_col, columns=config_col, values=metric, aggfunc='first'
        )
        pivoted = pivoted.dropna()
        k = pivoted.shape[1]
        n = pivoted.shape[0]
        if k < 3 or n < 2:
            continue
        try:
            stat, p_value = friedmanchisquare(
                *[pivoted[col].values for col in pivoted.columns]
            )
        except Exception:
            continue
        results.append({
            'metric': metric,
            'chi2': float(stat),
            'p_value': float(p_value),
            'df': k - 1,
            'n_scenarios': n,
            'n_configs': k,
        })
    return pd.DataFrame(results)


def holm_correct(p_values, alpha: float = 0.05):
    """Holm-Bonferroni step-down correction for an arbitrary family of p-values.

    This is the single implementation of the Holm procedure used everywhere in
    the codebase that needs to correct more than one p-value drawn from the
    same family of hypotheses -- both the pairwise post-hoc tables (via
    `posthoc_wilcoxon_holm` below) and the cross-stratum Friedman omnibus
    tables in `run_rag_ablation_experiments.py`, `test_prompt_ablation_significance.py`, and
    `test_hybrid_ablation_significance.py`. Centralising it means a correction fix
    only has to happen once.

    Holm controls the family-wise error rate: sort p-values ascending, test
    the smallest against alpha/m, the next against alpha/(m-1), and so on;
    once one comparison fails to reject, every larger p-value in the family
    is also not rejected (step-down monotonicity), regardless of whether its
    own per-step threshold would have been cleared in isolation.

    Args:
        p_values: array-like of raw p-values (NaNs allowed; excluded from the
            family and returned as NaN).
        alpha: family-wise significance level (default 0.05).

    Returns:
        (p_holm, significant_holm): two numpy arrays, same length and order as
        the input, with NaN preserved wherever the input was NaN.
    """
    p_arr = np.asarray(p_values, dtype=float)
    n = len(p_arr)
    p_holm = np.full(n, np.nan)
    significant_holm = np.zeros(n, dtype=bool)

    valid_mask = ~np.isnan(p_arr)
    valid_idx = np.where(valid_mask)[0]
    m = len(valid_idx)
    if m == 0:
        return p_holm, significant_holm

    # Order the valid p-values ascending; ties keep their original relative
    # order (stable sort), which only affects which of two identical
    # p-values is nominally "first" and has no effect on the resulting
    # p_holm values or significance calls.
    order = valid_idx[np.argsort(p_arr[valid_idx], kind="stable")]

    sig_in_rank_order = np.zeros(m, dtype=bool)
    for rank in range(m):
        idx = order[rank]
        raw_p = p_arr[idx]
        multiplier = m - rank
        p_holm[idx] = min(raw_p * multiplier, 1.0)
        threshold = alpha / multiplier
        sig_in_rank_order[rank] = raw_p < threshold

    # Enforce Holm step-down monotonicity: once the sequential procedure
    # encounters a non-rejection, all remaining (larger) p-values in the
    # family must also be treated as not rejected, regardless of whether
    # their individual p-value clears their own threshold. Without this pass
    # significance calls can have a False followed by a True at a larger
    # p-value, which violates the family-wise error rate guarantee.
    for rank in range(1, m):
        if not sig_in_rank_order[rank - 1]:
            sig_in_rank_order[rank] = False

    for rank in range(m):
        significant_holm[order[rank]] = sig_in_rank_order[rank]

    return p_holm, significant_holm


def posthoc_wilcoxon_holm(scenario_df: pd.DataFrame, metric: str,
                           config_col: str = 'ablation_id',
                           scenario_col: str = 'source_scenario_id',
                           alpha: float = 0.05) -> pd.DataFrame:
    """Perform pairwise Wilcoxon signed-rank tests with Holm-Bonferroni correction.

    After a significant Friedman test, this function determines which specific
    pairs of configurations differ significantly.  Each pair is tested with the
    Wilcoxon signed-rank test, and p-values are corrected for multiple
    comparisons using the Holm-Bonferroni sequential procedure.  Effect sizes
    are reported as Cliff's delta with magnitude interpretation.

    Args:
        scenario_df: DataFrame with one row per (config, scenario) combination.
        metric: the metric column to compare.
        config_col: column identifying the ablation configuration.
        scenario_col: column identifying the scenario.
        alpha: significance level (default 0.05).

    Returns:
        DataFrame with columns: config_i, config_j, statistic, p_value,
        p_holm, significant_holm, cliff_delta, cliff_delta_interpretation,
        n_pairs.
    """
    from scipy.stats import wilcoxon

    pivoted = scenario_df.pivot_table(
        index=scenario_col, columns=config_col, values=metric, aggfunc='first'
    )
    pivoted = pivoted.dropna()
    configs = list(pivoted.columns)

    pairs = []
    for i in range(len(configs)):
        for j in range(i + 1, len(configs)):
            ci, cj = configs[i], configs[j]
            vi = pivoted[ci].values.astype(float)
            vj = pivoted[cj].values.astype(float)
            n_pairs = len(vi)
            if n_pairs < 5:
                continue
            try:
                stat, p_val = wilcoxon(vi, vj, alternative='two-sided')
            except ValueError:
                continue
            delta, delta_interp = cliff_delta(vi, vj)   # unpaired, descriptive only
            rb, n_nonzero = matched_pairs_rank_biserial(vi, vj)
            pairs.append({
                'config_i': ci,
                'config_j': cj,
                'statistic': float(stat),
                'p_value': float(p_val),
                'rank_biserial': rb,
                'rank_biserial_interpretation': rank_biserial_interpretation(rb),
                'n_nonzero': n_nonzero,
                'cliff_delta': delta,
                'cliff_delta_interpretation': delta_interp,
                'n_pairs': n_pairs,
            })

    if not pairs:
        return pd.DataFrame(columns=[
            'config_i', 'config_j', 'statistic', 'p_value', 'p_holm',
            'significant_holm', 'rank_biserial', 'rank_biserial_interpretation',
            'n_nonzero', 'cliff_delta', 'cliff_delta_interpretation', 'n_pairs',
        ])

    pairs_df = pd.DataFrame(pairs).sort_values('p_value').reset_index(drop=True)
    p_holm, significant_holm = holm_correct(pairs_df['p_value'].values, alpha=alpha)

    pairs_df['p_holm'] = p_holm
    pairs_df['significant_holm'] = significant_holm
    return pairs_df


def derive_bootstrap_seed(seed: int, stratum_key, config_id, metric: str) -> int:
    """Deterministic 64-bit seed for one (stratum, config, metric) bootstrap.

    The key is hashed with SHA-256 rather than Python's built-in `hash()`,
    which is randomised per process for strings and would therefore make the
    draw irreproducible across runs -- the exact failure this function exists
    to prevent.
    """
    key = "|".join(str(part) for part in (seed, stratum_key, config_id, metric))
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")


def bootstrap_ci_per_config(scenario_df: pd.DataFrame, metric: str,
                            config_col: str = 'ablation_id',
                            n_bootstrap: int = 10000,
                            seed: int = 42,
                            stratum_key=None) -> pd.DataFrame:
    """Compute bootstrap 95% confidence intervals for each configuration's mean.

    For each ablation configuration the function resamples the scenario-level
    metric values with replacement to construct a 95 % confidence interval for
    the mean.  The percentile method is used for CI construction.

    Seeding is per (stratum, config, metric), not per call. A single
    `default_rng(seed)` consumed across the config loop makes each config's
    draw depend on how many configs preceded it, so the same data bootstrapped
    inside a seven-config loop and inside a one-config loop returns different
    intervals -- pure Monte Carlo jitter that a reader cannot distinguish from
    a real change. This was observed on `nearest_neighbor_k3`, whose CI moved
    from [-0.175, 0.172] to [-0.167, 0.178] on completely unchanged data.
    Deriving each config's seed from a hash of its own key makes the draw
    reproducible AND keeps configs drawing independent resample sequences
    rather than all replaying one shared stream. Callers that bootstrap
    several strata separately must pass `stratum_key`, otherwise the same
    config in two strata would resample on identical indices.

    Neither the number of replicates nor the CI method is affected.

    Args:
        scenario_df: DataFrame with one row per (config, scenario) combination.
        metric: the metric column to bootstrap.
        config_col: column identifying the ablation configuration.
        n_bootstrap: number of bootstrap resamples (default 10 000).
        seed: base seed, hashed together with the stratum/config/metric key.
        stratum_key: identifier of the stratum this frame belongs to (e.g. a
            model key, or an (architecture, model) pair). None is valid for
            single-stratum callers.

    Returns:
        DataFrame with columns: ablation_id, ablation_label, point_estimate,
        ci_lower, ci_upper, metric.
    """
    results = []

    for config_id, group in scenario_df.groupby(config_col):
        values = group[metric].dropna().values.astype(float)
        if len(values) < 2:
            continue
        rng = np.random.default_rng(
            derive_bootstrap_seed(seed, stratum_key, config_id, metric))
        point_estimate = float(np.mean(values))
        boot_means = np.empty(n_bootstrap)
        for b in range(n_bootstrap):
            sample = rng.choice(values, size=len(values), replace=True)
            boot_means[b] = np.mean(sample)
        ci_lower = float(np.percentile(boot_means, 2.5))
        ci_upper = float(np.percentile(boot_means, 97.5))
        label = group['ablation_label'].iloc[0] if 'ablation_label' in group.columns else config_id
        results.append({
            'ablation_id': config_id,
            'ablation_label': label,
            'point_estimate': point_estimate,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'metric': metric,
        })

    return pd.DataFrame(results)


# 2 (2026-09-27): calls go through sentinel_utils.openrouter_chat (max_tokens,
# provider pin, truncation / empty content fail) and Top-1 / Top-2 count a
# failed scenario as wrong. A format-1 checkpoint was collected under the old
# rules and is refused rather than resumed into a new collection.
CHECKPOINT_FORMAT = 2


def _json_default(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def source_files_sha256() -> Dict[str, str]:
    """SHA-256 of each RAG source sheet, so a checkpoint written before a data
    change is never resumed into a collection over the changed data."""
    return {
        name: hashlib.sha256((SCENARIO_DIR / name).read_bytes()).hexdigest()
        for name in RAG_FILES.values()
    }


def checkpoint_path(checkpoint_dir: Path, ablation_id: str, model_key: str) -> Path:
    return Path(checkpoint_dir) / f"{ablation_id}__{model_key}.json"


def _checkpoint_header(ablation_id: str, spec: Dict, model_key: str, model_id: str,
                       sample: List[Dict], run_meta: Dict) -> Dict:
    """Everything that must be equal for a saved unit to be reused."""
    return {
        "format": CHECKPOINT_FORMAT,
        "ablation_id": ablation_id,
        "spec": {k: v for k, v in spec.items() if k != "label"},
        "model_key": model_key,
        "model_id": model_id,
        "seed": run_meta.get("seed"),
        "sample_size": run_meta.get("sample_size"),
        "source_sha256": run_meta.get("source_sha256"),
        "nn_fallback": None if spec["llm"] else run_meta.get("nn_fallback", "tie"),
        "source_scenario_ids": [s["source_scenario_id"] for s in sample],
    }


def load_checkpoint(path: Path, expected_header: Dict) -> Optional[Dict]:
    """Return the saved unit, None if there is none. Raises if the file exists
    but was written for a different configuration, since silently re-running
    it would mix two collections and silently reusing it would be worse."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    header = saved.get("header", {})
    diffs = sorted(k for k in expected_header if header.get(k) != expected_header[k])
    if diffs:
        raise RuntimeError(
            f"Checkpoint {path} was written for a different configuration "
            f"(differs in: {', '.join(diffs)}). Move it aside before rerunning.")
    return saved


def write_checkpoint(path: Path, header: Dict, rows: List[Dict], unit_meta: Dict,
                     tmp_path: Optional[Path] = None) -> None:
    """Atomic write (tmp + os.replace). Called from the main thread only, after
    the unit's thread pool has been joined, so no two writers ever race."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tmp_path or path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"header": header, "unit": unit_meta, "rows": rows}, f, default=_json_default)
    os.replace(tmp, path)


def build_result_rows(sample: List[Dict], specs: OrderedDict, collections: Dict[str, Tuple], rng: np.random.Generator, model_keys: Optional[List[str]] = None, workers: int = 1, checkpoint_dir: Optional[Path] = None, run_meta: Optional[Dict] = None, checkpoint_paths=None, checkpoint_tmp_paths=None) -> List[Dict]:
    """Run every (ablation x model x scenario) cell and flatten to per-alternative rows.

    Checkpointing (`checkpoint_dir`): each (ablation, model) unit is saved to
    `<checkpoint_dir>/<ablation_id>__<model_key>.json` as soon as it finishes,
    and a restart skips every unit whose checkpoint exists. The returned rows
    are always read back from the checkpoints, so the final workbook is exactly
    their union. A skipped unit still re-runs its (local, cheap) retrieval:
    this keeps the random arm's shared `rng` on the same draw sequence as an
    uninterrupted run, and the recomputed exemplar ids must equal the saved
    ones or the run stops. A unit in which every API call failed (e.g. out of
    credit) is not saved and stops the run, so it is retried on restart rather
    than resumed as a unit of sentinels.

    Two phases per (ablation, model). Retrieval runs serially because Chroma
    collections and SentenceTransformer models are not documented thread-safe,
    and because `retrieve_random` draws from a shared `rng` -- parallel draws
    would make the `--seed` unreproducible. Retrieval is CPU-local and cheap.

    LLM scoring is then dispatched across `workers` threads. Only the network
    wait is parallelised, which is where all the wall clock actually goes. Each
    worker calls `query_openrouter` independently, so `MAX_RETRIES`, the backoff
    schedule, and the per-call `latency_ms` measurement are untouched: latency is
    still measured around a single successful POST, not around queue time.
    """
    run_meta = run_meta or {}
    nn_fallback = run_meta.get("nn_fallback", "tie")
    rows = []
    for ablation_id, spec in specs.items():
        temp_path, collection, model, groups_by_type = collections[spec["embedding_model"]]
        logging.info("Running ablation: %s", ablation_id)

        if spec["llm"]:
            selected = model_keys if model_keys else list(MODEL_SPECS.keys())
            eval_models = [(k, MODEL_SPECS[k]["openrouter_id"]) for k in selected]
        else:
            eval_models = [("offline", "none")]

        for model_key, model_id in eval_models:
            if spec["llm"]:
                logging.info("  Evaluating model: %s (%s)", model_key, model_id)
            else:
                logging.info("  Evaluating offline NN prediction (fallback=%s)", nn_fallback)

            ckpt_path = None
            saved = None
            header = None
            if checkpoint_dir is not None:
                ckpt_path = (checkpoint_paths or {}).get(
                    (ablation_id, model_key),
                    checkpoint_path(checkpoint_dir, ablation_id, model_key),
                )
                header = _checkpoint_header(ablation_id, spec, model_key, model_id, sample, run_meta)
                saved = load_checkpoint(ckpt_path, header)

            # Serial retrieval, preserving rng draw order.
            retrieved_by_scenario = []
            for scenario in sample:
                decision_type = scenario["decision_type"]
                candidates = groups_by_type[decision_type]
                if spec["retrieval"] == "none":
                    retrieved = []
                elif spec["retrieval"] == "random":
                    retrieved = retrieve_random(model, scenario, candidates, spec["k"], rng)
                else:
                    retrieved = retrieve_similar(collection, model, scenario, spec["k"])
                retrieved_by_scenario.append(retrieved)

            if saved is not None:
                expected_ids = {
                    s["source_scenario_id"]: json.dumps([str(item.get("id")) for item in r])
                    for s, r in zip(sample, retrieved_by_scenario)
                }
                for row in saved["rows"]:
                    if row["retrieved_ids"] != expected_ids.get(row["source_scenario_id"]):
                        raise RuntimeError(
                            f"Checkpoint {ckpt_path}: saved exemplars for {row['source_scenario_id']} "
                            f"differ from this run's retrieval; move the checkpoint aside.")
                logging.info("    resumed from checkpoint %s (%s rows)", ckpt_path.name, len(saved["rows"]))
                rows.extend(saved["rows"])
                continue

            unit_start_utc = datetime.now(timezone.utc).isoformat()
            unit_rows = []

            # Parallel only for LLM arms with workers > 1.
            n_workers = max(1, int(workers)) if spec["llm"] else 1
            if n_workers > 1:
                results = [None] * len(sample)
                pool = ThreadPoolExecutor(max_workers=n_workers)
                try:
                    futures = {
                        pool.submit(llm_prediction, scenario, spec,
                                    retrieved_by_scenario[i], model_id): i
                        for i, scenario in enumerate(sample)
                    }
                    done = 0
                    for future in as_completed(futures):
                        i = futures[future]
                        results[i] = future.result()
                        done += 1
                        if done % 25 == 0 or done == len(sample):
                            logging.info("    %s/%s scenarios scored", done, len(sample))
                except BaseException as exc:
                    # RunAbort (401/402/403 or the failure breaker), a crash, or
                    # Ctrl-C: drop the queued scenarios; on an abort also stop
                    # every running worker at its next call. The unit is not
                    # checkpointed and no workbook is written, so a rerun
                    # re-collects it.
                    if not isinstance(exc, Exception):
                        _ABORT.set()
                    pool.shutdown(wait=True, cancel_futures=True)
                    raise
                pool.shutdown(wait=True)
            else:
                results = []
                for i, scenario in enumerate(sample):
                    if spec["llm"]:
                        results.append(llm_prediction(scenario, spec, retrieved_by_scenario[i], model_id))
                    else:
                        results.append(nearest_neighbor_prediction(scenario, retrieved_by_scenario[i],
                                                                   fallback=nn_fallback))
            unit_end_utc = datetime.now(timezone.utc).isoformat()

            for scenario, retrieved, result in zip(sample, retrieved_by_scenario, results):
                decision_type = scenario["decision_type"]
                predictions = result["predictions"]
                diag = result["diagnostics"]
                metrics = scenario_metrics(predictions, scenario)
                mean_distance = float(np.mean([item["distance"] for item in retrieved])) if retrieved else np.nan
                for pred in predictions:
                    unit_rows.append({
                        "model_key": model_key,
                        "model_id": model_id,
                        "ablation_id": ablation_id,
                        "ablation_label": spec["label"],
                        "sample_seed": scenario.get("source_scenario_numeric", scenario.get("source_position", 0)),
                        "decision_type": decision_type,
                        "source_scenario_id": scenario["source_scenario_id"],
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
                        "retrieved_ids": json.dumps([str(item.get("id")) for item in retrieved]),
                        "retrieved_distances": json.dumps([item.get("distance") for item in retrieved]),
                        "score_mae": metrics["score_mae"],
                        "score_rmse": metrics["score_rmse"],
                        "kendall_tau": metrics["kendall_tau"],
                        "spearman_rho": metrics["spearman_rho"],
                        "top1_correct": metrics["top1_correct"],
                        "top2_correct": metrics["top2_correct"],
                        "gt_top1": metrics["gt_top1"],
                        "pred_top1": metrics["pred_top1"],
                        "scenario_failed": bool(metrics["scenario_failed"]),
                        "api_calls": int(diag.get("api_calls", 0)),
                        "successful_calls": int(diag.get("successful_calls", 0)),
                        "failed_calls": int(diag.get("failed_calls", 0)),
                        "prompt_tokens": int(diag.get("prompt_tokens", 0)),
                        "completion_tokens": int(diag.get("completion_tokens", 0)),
                        "total_tokens": int(diag.get("total_tokens", 0)),
                        "latency_ms": float(diag.get("latency_ms", 0.0)),
                        "error": pred.get("error", ""),
                        "nn_fallback": "" if spec["llm"] else nn_fallback,
                        "collected_utc": unit_start_utc,
                        "collected_utc_end": unit_end_utc,
                    })

            if checkpoint_dir is None:
                rows.extend(unit_rows)
                continue
            n_calls = sum(int(r["diagnostics"].get("api_calls", 0)) for r in results)
            n_failed = sum(int(r["diagnostics"].get("failed_calls", 0)) for r in results)
            if spec["llm"] and n_calls and n_failed == n_calls:
                raise RuntimeError(
                    f"Every one of the {n_calls} API calls failed for {ablation_id} / {model_key}; "
                    f"the unit is not checkpointed. Check credit and the raw log, then rerun: "
                    f"completed units resume from {checkpoint_dir}.")
            write_checkpoint(ckpt_path, header, unit_rows, {
                "collected_utc_start": unit_start_utc,
                "collected_utc_end": unit_end_utc,
                "api_calls": n_calls,
                "failed_calls": n_failed,
            }, tmp_path=(checkpoint_tmp_paths or {}).get((ablation_id, model_key)))
            # Read back, so the final workbook is assembled from the checkpoints.
            rows.extend(load_checkpoint(ckpt_path, header)["rows"])
    return rows


def _atomic_write_xlsx(df: pd.DataFrame, path: Path, tmp_path: Optional[Path] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tmp_path or path.with_suffix(path.suffix + ".tmp")
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


def write_report(output_path: Path, sample_size: Optional[int], seed: int, specs: OrderedDict, summary_df: pd.DataFrame, dtype_summary_df: pd.DataFrame, rows_df: pd.DataFrame, plot_paths: List[Path], friedman_results: Optional[pd.DataFrame] = None, posthoc_df: Optional[pd.DataFrame] = None, bootstrap_df: Optional[pd.DataFrame] = None) -> None:
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

    if friedman_results is not None and not friedman_results.empty:
        sections.append("## Friedman Tests (non-parametric omnibus, per model)\n\n"
                        "Chi-squared statistic for each metric across all ablation configurations, "
                        "run separately within each model. Holm-Bonferroni is applied once across "
                        "the whole (model x metric) family; read `p_holm`, not `p_value`.\n\n"
                        + _format_md_table(friedman_results, float_cols=["chi2", "p_value"]))
    if posthoc_df is not None and not posthoc_df.empty:
        sections.append("## Post-hoc Pairwise Wilcoxon Tests (Holm-corrected, within model)\n\n"
                        "Pairwise differences within each model, computed only for (model, metric) "
                        "cells whose Friedman omnibus survived the family correction above, and "
                        "Holm-corrected within their own (model x metric) family.\n\n"
                        + _format_md_table(posthoc_df, float_cols=["statistic", "p_value", "p_holm", "cliff_delta"]))
    if bootstrap_df is not None and not bootstrap_df.empty:
        sections.append("## Bootstrap 95% Confidence Intervals (per model)\n\n"
                        "Percentile-method 95% CIs for each configuration's mean metric value, "
                        "computed within each model rather than pooled across models.\n\n"
                        + _format_md_table(bootstrap_df, float_cols=["point_estimate", "ci_lower", "ci_upper"]))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# RAG Ablation Study\n\n")
        for section in sections:
            f.write(section + "\n\n")


def _resolved_path_key(path: Path) -> str:
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def _validate_report_destination(output_dir: Path, report_path: Path, input_paths=()) -> None:
    if report_path.suffix.casefold() != ".md":
        raise UnsafeOutputPathError(
            f"--output must name a Markdown report ending in .md: {report_path}"
        )

    generated_paths = [
        output_dir / "rag_ablation_results.xlsx",
        output_dir / "rag_ablation_summary.xlsx",
        output_dir / "rag_ablation_summary_by_decision_type.xlsx",
        output_dir / "rag_ablation_friedman_tests.xlsx",
        output_dir / "rag_ablation_posthoc_tests.xlsx",
        output_dir / "rag_ablation_bootstrap_ci.xlsx",
        output_dir / "rag_ablation_results_raw.jsonl",
        *(output_dir / "checkpoints" / f"{ablation_id}__{model_key}.json"
          for ablation_id in ABLATION_SPECS for model_key in MODEL_SPECS),
    ]
    report_key = _resolved_path_key(report_path)
    for generated_path in generated_paths:
        if report_key == _resolved_path_key(generated_path):
            raise UnsafeOutputPathError(
                f"--output collides with a generated RAG ablation artifact: {generated_path}"
            )
    for input_path in input_paths:
        if report_key == _resolved_path_key(input_path):
            raise UnsafeOutputPathError(
                f"--output would overwrite a RAG ablation input: {input_path}"
            )


def resolve_output_paths(output_dir_value, report_output_value):
    """Resolve all writer destinations before the command creates anything."""
    if output_dir_value is None and report_output_value is None:
        raise UnsafeOutputPathError(
            f"An explicit --output-dir (or {RUN_OUTPUT_DIR_ENV}) or a safe --output report path is required."
        )

    if output_dir_value is None:
        report_path = require_safe_output_path(
            report_output_value,
            option="--output",
            root=PROJECT_ROOT,
        )
        output_dir = report_path.parent
    else:
        output_dir = require_safe_output_directory(
            output_dir_value,
            option="--output-dir",
            root=PROJECT_ROOT,
        )
        report_value = report_output_value or output_dir / "rag_ablation_results.md"
        report_path = require_safe_output_path(
            report_value,
            option="--output",
            root=PROJECT_ROOT,
        )
    _validate_report_destination(output_dir, report_path)
    return output_dir, report_path


def validate_recompute_directories(input_dir: Path, output_dir: Path) -> Tuple[Path, Path]:
    """Resolve recompute input/output dirs and require disjoint trees."""
    resolved_input = Path(input_dir).expanduser().resolve()
    resolved_output = Path(output_dir).expanduser().resolve()
    input_key = os.path.normcase(os.path.normpath(str(resolved_input)))
    output_key = os.path.normcase(os.path.normpath(str(resolved_output)))
    try:
        common = os.path.commonpath((input_key, output_key))
    except ValueError:
        common = None
    if common in {input_key, output_key}:
        raise UnsafeOutputPathError(
            "For --recompute-significance-only, --input-dir and --output-dir must "
            "be disjoint directories after resolving symlinks. "
            f"Input: {resolved_input}; output: {resolved_output}. Choose separate trees."
        )
    return resolved_input, resolved_output


def _require_disjoint_from_input(path: Path, input_dir: Path, *, option: str) -> Path:
    """Reject resolved output targets that touch a read-only input tree."""
    resolved_path = Path(path).expanduser().resolve()
    resolved_input = Path(input_dir).expanduser().resolve()
    path_key = os.path.normcase(os.path.normpath(str(resolved_path)))
    input_key = os.path.normcase(os.path.normpath(str(resolved_input)))
    try:
        common = os.path.commonpath((path_key, input_key))
    except ValueError:
        common = None
    if common in {path_key, input_key}:
        raise UnsafeOutputPathError(
            f"{option} resolves into or overlaps the read-only input tree "
            f"{resolved_input}: {resolved_path}. Choose a separate output destination."
        )
    return resolved_path


def _validate_report_outside_input(report_path: Path, input_dir: Path) -> Path:
    """Reports must not be written anywhere inside the source directory."""
    resolved_report = Path(report_path).expanduser().resolve()
    resolved_input = Path(input_dir).expanduser().resolve()
    report_key = os.path.normcase(os.path.normpath(str(resolved_report)))
    input_key = os.path.normcase(os.path.normpath(str(resolved_input)))
    try:
        common = os.path.commonpath((report_key, input_key))
    except ValueError:
        common = None
    if common == input_key:
        raise UnsafeOutputPathError(
            f"--output report must be outside the read-only --input-dir tree: "
            f"{resolved_input}. Resolved report: {resolved_report}"
        )
    return resolved_report


def _preflight_output_paths(output_dir: Path, report_path: Path, input_dir: Path,
                            *, full_run: bool, checkpoint_keys=()) -> Dict:
    """Resolve and validate every destination before reading source data.

    All paths are passed through the shared frozen-path validators, which
    resolve existing symlinks/junctions. Outputs are additionally kept
    disjoint from the read-only source tree. Atomic temporary siblings are
    preflighted too and returned for use by the writers.
    """
    output_dir = require_safe_output_directory(
        output_dir, option="--output-dir", root=PROJECT_ROOT
    )
    output_dir = _require_disjoint_from_input(
        output_dir, input_dir, option="--output-dir"
    )
    report_path = require_safe_output_path(
        report_path, option="--output", root=PROJECT_ROOT
    )
    if report_path.suffix.casefold() != ".md":
        raise UnsafeOutputPathError(
            f"--output must name a Markdown report ending in .md: {report_path}"
        )
    report_path = _validate_report_outside_input(report_path, input_dir)

    result = {"output_dir": output_dir, "report": report_path}
    directories = {}
    if full_run:
        directories["temp_dir"] = output_dir / ".rag_ablation_temp"
        if checkpoint_keys is not None:
            directories["checkpoint_dir"] = output_dir / "checkpoints"
    for name, value in directories.items():
        safe_dir = require_safe_output_directory(
            value, option=f"{name} output directory", root=PROJECT_ROOT
        )
        result[name] = _require_disjoint_from_input(
            safe_dir, input_dir, option=f"{name} output directory"
        )

    file_values = {}
    if full_run:
        file_values.update({
            "results": output_dir / "rag_ablation_results.xlsx",
            "summary": output_dir / "rag_ablation_summary.xlsx",
            "dtype_summary": output_dir / "rag_ablation_summary_by_decision_type.xlsx",
            "friedman": output_dir / "rag_ablation_friedman_tests.xlsx",
            "posthoc": output_dir / "rag_ablation_posthoc_tests.xlsx",
            "bootstrap": output_dir / "rag_ablation_bootstrap_ci.xlsx",
            "raw_log": output_dir / "rag_ablation_results_raw.jsonl",
        })
        for ablation_id, model_key in checkpoint_keys or ():
            file_values[f"checkpoint:{ablation_id}:{model_key}"] = (
                result["checkpoint_dir"] / f"{ablation_id}__{model_key}.json"
            )
    else:
        file_values.update({
            "summary": output_dir / "rag_ablation_summary.xlsx",
            "dtype_summary": output_dir / "rag_ablation_summary_by_decision_type.xlsx",
            "friedman": output_dir / "rag_ablation_friedman_tests.xlsx",
            "posthoc": output_dir / "rag_ablation_posthoc_tests.xlsx",
            "bootstrap": output_dir / "rag_ablation_bootstrap_ci.xlsx",
        })

    file_values["report"] = report_path
    safe_files = {}
    temp_files = {}
    all_targets = {}
    for name, value in file_values.items():
        safe_path = require_safe_output_path(
            value, option=("--output" if name == "report" else f"{name} output"),
            root=PROJECT_ROOT,
        )
        safe_path = _require_disjoint_from_input(
            safe_path, input_dir,
            option=("--output" if name == "report" else f"{name} output"),
        )
        key = _resolved_path_key(safe_path)
        if key in all_targets:
            raise UnsafeOutputPathError(
                f"Output paths collide after resolving symlinks: {name} and "
                f"{all_targets[key]} both target {safe_path}."
            )
        all_targets[key] = name
        safe_files[name] = safe_path
        if safe_path.suffix.casefold() == ".xlsx":
            tmp_value = safe_path.with_suffix(safe_path.suffix + ".tmp")
            tmp_path = require_safe_output_path(
                tmp_value, option=f"temporary {name} output", root=PROJECT_ROOT
            )
            tmp_path = _require_disjoint_from_input(
                tmp_path, input_dir, option=f"temporary {name} output"
            )
            tmp_key = _resolved_path_key(tmp_path)
            if tmp_key in all_targets:
                raise UnsafeOutputPathError(
                    f"Temporary output for {name} collides after resolving symlinks "
                    f"with {all_targets[tmp_key]}: {tmp_path}"
                )
            all_targets[tmp_key] = f"temporary {name}"
            temp_files[name] = tmp_path

    # Checkpoint JSON files also use atomic .tmp siblings.
    checkpoint_paths = {}
    checkpoint_tmp_paths = {}
    for ablation_id, model_key in checkpoint_keys or ():
        name = f"checkpoint:{ablation_id}:{model_key}"
        path = safe_files[name]
        tmp_path = require_safe_output_path(
            path.with_suffix(path.suffix + ".tmp"),
            option=f"temporary checkpoint {ablation_id}/{model_key} output",
            root=PROJECT_ROOT,
        )
        tmp_path = _require_disjoint_from_input(
            tmp_path, input_dir,
            option=f"temporary checkpoint {ablation_id}/{model_key} output",
        )
        tmp_key = _resolved_path_key(tmp_path)
        if tmp_key in all_targets:
            raise UnsafeOutputPathError(
                f"Temporary checkpoint output collides after resolving symlinks "
                f"with {all_targets[tmp_key]}: {tmp_path}"
            )
        all_targets[tmp_key] = f"temporary {name}"
        checkpoint_paths[(ablation_id, model_key)] = path
        checkpoint_tmp_paths[(ablation_id, model_key)] = tmp_path

    result["files"] = safe_files
    result["temporary_files"] = temp_files
    result["checkpoint_paths"] = checkpoint_paths
    result["checkpoint_tmp_paths"] = checkpoint_tmp_paths
    return result


def run(args) -> Dict:
    output_dir, report_path = resolve_output_paths(
        getattr(args, "output_dir", None),
        getattr(args, "output", None),
    )
    sample_size = parse_sample_size(args.sample_size)
    ablation_ids = set(args.ablations)
    specs = OrderedDict((k, v) for k, v in ABLATION_SPECS.items() if k in ablation_ids)
    if not specs:
        raise ValueError("No ablations selected")

    selected_model_keys = getattr(args, "models", None) or list(MODEL_SPECS.keys())
    checkpoint_keys = None
    if not getattr(args, "no_checkpoint", False):
        checkpoint_keys = []
        for ablation_id, spec in specs.items():
            model_keys = selected_model_keys if spec["llm"] else ["offline"]
            checkpoint_keys.extend((ablation_id, model_key) for model_key in model_keys)
    output_paths = _preflight_output_paths(
        output_dir,
        report_path,
        SCENARIO_DIR,
        full_run=True,
        checkpoint_keys=checkpoint_keys,
    )
    output_dir = output_paths["output_dir"]
    report_path = output_paths["report"]
    if any(spec["llm"] for spec in specs.values()) and not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found. Use --ablations nearest-neighbor for an offline-only run.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    groups_by_type = load_source_groups()
    sample = stratified_sample(groups_by_type, sample_size, args.seed)
    logging.info("Loaded %s source scenarios; sampled %s", sum(len(v) for v in groups_by_type.values()), len(sample))

    temp_root = output_paths["temp_dir"]
    temp_root.mkdir(parents=True, exist_ok=True)
    embedding_models = sorted({spec["embedding_model"] for spec in specs.values()})
    collections = {}
    for embedding_model_name in embedding_models:
        logging.info("Building temporary Chroma collection with %s", embedding_model_name)
        collections[embedding_model_name] = build_collection(embedding_model_name, temp_root)

    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    collected_utc = datetime.now(timezone.utc).isoformat()
    run_meta = {
        "seed": args.seed,
        "sample_size": sample_size,
        "source_sha256": source_files_sha256(),
        "nn_fallback": getattr(args, "nn_fallback", "tie"),
    }
    checkpoint_dir = output_paths.get("checkpoint_dir")
    RAW_LOG.start(output_paths["files"]["raw_log"])
    try:
        rows = build_result_rows(sample, specs, collections, rng, getattr(args, "models", None),
                                 workers=getattr(args, "workers", 1),
                                 checkpoint_dir=checkpoint_dir, run_meta=run_meta,
                                 checkpoint_paths=output_paths["checkpoint_paths"],
                                 checkpoint_tmp_paths=output_paths["checkpoint_tmp_paths"])
    finally:
        RAW_LOG.stop()
    rows_df = pd.DataFrame(rows)
    # Each (ablation, model) unit carries its own collection window; the run
    # start fills in only if a row somehow has none.
    if "collected_utc" not in rows_df:
        rows_df["collected_utc"] = collected_utc
    rows_df["collected_utc"] = rows_df["collected_utc"].fillna(collected_utc)
    rows_df["top1_accuracy"] = rows_df["top1_correct"].astype(float)
    rows_df["top2_accuracy"] = rows_df["top2_correct"].astype(float)
    rows_df["success_rate"] = np.where(rows_df["api_calls"] > 0, rows_df["successful_calls"] / rows_df["api_calls"], np.nan)

    results_path = output_paths["files"]["results"]
    summary_path = output_paths["files"]["summary"]
    dtype_summary_path = output_paths["files"]["dtype_summary"]
    _atomic_write_xlsx(rows_df, results_path, output_paths["temporary_files"]["results"])
    summary_df = summarize_rows(rows_df)
    dtype_summary_df = summarize_by_decision_type(rows_df)
    _atomic_write_xlsx(summary_df, summary_path, output_paths["temporary_files"]["summary"])
    _atomic_write_xlsx(dtype_summary_df, dtype_summary_path, output_paths["temporary_files"]["dtype_summary"])

    scenario_df = scenario_level_df(rows_df)
    stat_metrics = ['kendall_tau', 'score_mae', 'score_rmse', 'top1_accuracy']

    friedman_results, posthoc_df, bootstrap_df, paths = run_significance_suite(
        scenario_df, stat_metrics, output_dir, output_paths=output_paths)

    write_report(report_path, sample_size, args.seed, specs, summary_df, dtype_summary_df, rows_df, [],
                 friedman_results=friedman_results, posthoc_df=posthoc_df, bootstrap_df=bootstrap_df)

    print("\nRAG ABLATION COMPLETE")
    print(f"Sample size: {'all' if sample_size is None else sample_size}")
    print(f"Scenarios: {rows_df['source_scenario_id'].nunique()}")
    print(f"Rows: {len(rows_df)}")
    print(_format_md_table(summary_df, float_cols=[c for c in summary_df.columns if c not in {"model_key", "ablation_id", "ablation_label", "n_scenarios"}]))
    print(f"\nResults saved to: {results_path}")
    print(f"Report saved to: {report_path}")
    print(f"Friedman tests saved to: {paths['friedman_path']}")
    print(f"Post-hoc tests saved to: {paths['posthoc_path']}")
    print(f"Bootstrap CIs saved to: {paths['bootstrap_path']}")
    if not friedman_results.empty:
        sig = friedman_results[friedman_results['significant_holm']]
        if not sig.empty:
            print(f"\nSignificant Friedman results (Holm-corrected across the "
                  f"{friedman_results['p_value'].notna().sum()}-test family, p_holm < 0.05):")
            print(_format_md_table(sig))

    return {
        "rows": rows_df,
        "summary": summary_df,
        "by_decision_type": dtype_summary_df,
        "results_path": results_path,
        "report_path": report_path,
    }


def run_significance_suite(scenario_df: pd.DataFrame, stat_metrics: List[str],
                            output_dir: Path, model_col: str = 'model_key',
                            output_paths: Optional[Dict] = None):
    """Friedman -> Holm-corrected family -> gated post-hoc -> bootstrap CI pipeline.

    This is the single significance-testing entry point for the RAG ablation,
    factored out of `run()` so it can be re-invoked directly against an
    existing `rag_ablation_results.xlsx` (via `--recompute-significance-only`)
    without repeating the retrieval/LLM-querying work above it.

    Everything here is stratified by model. There is no architecture
    dimension in this ablation -- every retrieval config is A_E -- so
    `model_col` alone defines a stratum, exactly as (architecture, model)
    defines one in `test_prompt_ablation_significance.py`. Stratification is
    not cosmetic: `friedman_test_per_metric` pivots to (scenario x config)
    with `aggfunc='first'`, so running it over a multi-model frame silently
    keeps one arbitrary model's value per cell and discards the rest,
    reporting a single-model result under a whole-study label. Per-model
    strata also keep model effects out of the config comparison, and honour
    the project-wide rule that no reported metric is a cross-model pool.

    Two correction layers are applied, matching the convention used
    throughout the rest of the paper's significance testing
    (`significance_testing.py`) and mirrored identically in
    `test_prompt_ablation_significance.py` and `test_hybrid_ablation_significance.py`:

    1. Cross-stratum family correction on the Friedman omnibus tests
       themselves. One Friedman test is run per (model, metric) pair -- with
       four evaluated models and the four metrics in `stat_metrics` that is
       a 16-test family, and the `offline` nearest-neighbour pseudo-model is
       skipped because a single config cannot support an omnibus test.
       Reporting all of those omnibus p-values side by side and gating each
       independently at nominal alpha=0.05 inflates the family-wise
       false-positive rate across the set, the same way reporting 40+
       uncorrected pairwise tests would. Holm-Bonferroni is applied ONCE
       across the whole cross-stratum Friedman table before it is used for
       anything downstream, and `p_holm` / `significant_holm` are the columns
       that should be read and cited, not the raw `p_value` column (kept for
       transparency/audit only).
    2. Post-hoc pairwise Wilcoxon+Holm within the stratum, but only for
       (model, metric) cells whose Friedman omnibus is significant AFTER the
       family correction above (`significant_holm`, not raw
       `p_value < 0.05`). Each surviving cell's pairwise tests are Holm-
       corrected within their own (model x metric) family. Running post-hoc
       comparisons for a cell whose omnibus did not survive correction would
       test pairwise differences the omnibus test itself could not support
       finding.

    Bootstrap CIs are computed per config WITHIN each model and left ungated
    regardless of Friedman outcome: a bootstrap CI describes one
    configuration's own sampling uncertainty, not a pairwise comparison, so
    it is not a multiple-comparisons question in the same sense and gating it
    on the omnibus would withhold a purely descriptive quantity from
    configurations that otherwise didn't reach significance.

    Every output frame carries a `model_key` column so no row is ambiguous
    about which stratum produced it.
    """
    strata = []
    friedman_rows = []
    for model_key, stratum in scenario_df.groupby(model_col, dropna=False):
        # A stratum needs >= 3 configs for a Friedman omnibus. The `offline`
        # nearest-neighbour pseudo-model has exactly one, so it drops out of
        # the omnibus/post-hoc layers but still gets descriptive bootstrap CIs.
        if stratum['ablation_id'].nunique() >= 3:
            strata.append((model_key, stratum))
            fr = friedman_test_per_metric(stratum, stat_metrics)
            for _, r in fr.iterrows():
                friedman_rows.append({model_col: model_key, **r.to_dict()})

    friedman_results = pd.DataFrame(friedman_rows)
    if not friedman_results.empty:
        p_holm, significant_holm = holm_correct(friedman_results['p_value'].values)
        friedman_results['p_holm'] = p_holm
        friedman_results['significant_holm'] = significant_holm
    else:
        friedman_results = pd.DataFrame(columns=[
            model_col, 'metric', 'chi2', 'p_value', 'df', 'n_scenarios', 'n_configs',
            'p_holm', 'significant_holm',
        ])
    files = (output_paths or {}).get("files", {})
    temporary_files = (output_paths or {}).get("temporary_files", {})
    friedman_path = files.get("friedman", output_dir / "rag_ablation_friedman_tests.xlsx")
    _atomic_write_xlsx(friedman_results, friedman_path, temporary_files.get("friedman"))

    posthoc_parts = []
    for model_key, stratum in strata:
        sig_metrics = set(friedman_results.loc[
            (friedman_results[model_col] == model_key) & (friedman_results['significant_holm']),
            'metric',
        ])
        for metric in stat_metrics:
            if metric not in sig_metrics:
                continue
            ph = posthoc_wilcoxon_holm(stratum, metric)
            if ph.empty:
                continue
            ph.insert(0, 'metric', metric)
            ph.insert(0, model_col, model_key)
            posthoc_parts.append(ph)
    posthoc_df = pd.concat(posthoc_parts, ignore_index=True) if posthoc_parts else pd.DataFrame()
    posthoc_path = files.get("posthoc", output_dir / "rag_ablation_posthoc_tests.xlsx")
    _atomic_write_xlsx(posthoc_df, posthoc_path, temporary_files.get("posthoc"))

    bootstrap_parts = []
    for model_key, stratum in scenario_df.groupby(model_col, dropna=False):
        for metric in ['kendall_tau', 'score_mae', 'top1_accuracy']:
            bc = bootstrap_ci_per_config(stratum, metric, stratum_key=model_key)
            if bc.empty:
                continue
            bc.insert(0, model_col, model_key)
            bootstrap_parts.append(bc)
    bootstrap_df = pd.concat(bootstrap_parts, ignore_index=True) if bootstrap_parts else pd.DataFrame()
    bootstrap_path = files.get("bootstrap", output_dir / "rag_ablation_bootstrap_ci.xlsx")
    _atomic_write_xlsx(bootstrap_df, bootstrap_path, temporary_files.get("bootstrap"))

    paths = {
        "friedman_path": friedman_path,
        "posthoc_path": posthoc_path,
        "bootstrap_path": bootstrap_path,
    }
    return friedman_results, posthoc_df, bootstrap_df, paths


def recompute_significance_only(source_dir: Path, output_dir: Path, report_path: Path):
    """Recompute the Friedman/post-hoc/bootstrap suite from a saved results file.

    Loads `source_dir/rag_ablation_results.xlsx` (already-collected
    scenario-level rows from a prior full run) and writes refreshed outputs
    to a separate safe output directory, making zero API calls. Use this after
    a change to the significance-testing code itself
    (e.g. adding the Holm family correction) when the underlying scenario
    data has not changed and re-querying the models would be pure cost with
    no new information.
    """
    output_dir, report_path = resolve_output_paths(output_dir, report_path)
    try:
        source_dir, output_dir = validate_recompute_directories(source_dir, output_dir)
    except UnsafeOutputPathError as exc:
        raise SystemExit(str(exc)) from exc
    results_path = source_dir / "rag_ablation_results.xlsx"
    try:
        _validate_report_outside_input(report_path, source_dir)
        _validate_report_destination(output_dir, report_path, input_paths=[results_path])
        output_paths = _preflight_output_paths(
            output_dir, report_path, source_dir, full_run=False
        )
    except UnsafeOutputPathError as exc:
        raise SystemExit(str(exc)) from exc
    output_dir = output_paths["output_dir"]
    report_path = output_paths["report"]
    if not results_path.exists():
        raise SystemExit(f"Missing {results_path}. Run a full ablation first.")
    rows_df = pd.read_excel(results_path)
    scenario_df = scenario_level_df(rows_df)
    stat_metrics = ['kendall_tau', 'score_mae', 'score_rmse', 'top1_accuracy']

    friedman_results, posthoc_df, bootstrap_df, paths = run_significance_suite(
        scenario_df, stat_metrics, output_dir, output_paths=output_paths)

    # Summaries are recomputed from the loaded rows rather than read back off
    # disk: a stale summary written by an earlier, smaller run would otherwise
    # be republished into the report alongside freshly recomputed statistics.
    summary_path = output_paths["files"]["summary"]
    dtype_summary_path = output_paths["files"]["dtype_summary"]
    summary_df = summarize_rows(rows_df)
    dtype_summary_df = summarize_by_decision_type(rows_df)
    _atomic_write_xlsx(summary_df, summary_path, output_paths["temporary_files"]["summary"])
    _atomic_write_xlsx(dtype_summary_df, dtype_summary_path, output_paths["temporary_files"]["dtype_summary"])

    write_report(report_path, None, None, OrderedDict(), summary_df, dtype_summary_df, rows_df, [],
                 friedman_results=friedman_results, posthoc_df=posthoc_df, bootstrap_df=bootstrap_df)

    print("RAG ABLATION SIGNIFICANCE RECOMPUTE COMPLETE (no API calls made)")
    print(f"Rows loaded: {len(rows_df)}")
    print(f"Models: {', '.join(sorted(str(m) for m in rows_df['model_key'].unique()))}")
    print(f"Summary saved to: {summary_path}")
    print(f"Decision-type summary saved to: {dtype_summary_path}")
    print(f"Friedman tests saved to: {paths['friedman_path']}")
    print(f"Post-hoc tests saved to: {paths['posthoc_path']}")
    print(f"Bootstrap CIs saved to: {paths['bootstrap_path']}")
    if not friedman_results.empty:
        print(f"\n=== FRIEDMAN (per model; Holm-corrected across the full "
              f"{int(friedman_results['p_value'].notna().sum())}-test family) ===")
        show = friedman_results[['model_key', 'metric', 'chi2', 'p_value', 'p_holm', 'significant_holm', 'df', 'n_scenarios', 'n_configs']]
        print(show.to_string(index=False))
        sig = friedman_results[friedman_results['significant_holm']]
        if not sig.empty:
            print(f"\nSignificant Friedman results (Holm-corrected, p_holm < 0.05):")
            print(_format_md_table(sig))
    return {
        "friedman_results": friedman_results,
        "posthoc_df": posthoc_df,
        "bootstrap_df": bootstrap_df,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run RAG retrieval and exemplar ablations.")
    parser.add_argument(
        "--sample-size",
        default="all",
        help="Number of source scenarios to sample, stratified by decision type. Default 'all' "
             "runs the complete 90-scenario RAG source set. Pass an integer for a stratified subset.",
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(MODEL_SPECS.keys()),
        choices=list(MODEL_SPECS.keys()),
        help="Model keys to evaluate. Defaults to all four, which is the set the paper "
             "reports, so a default run reproduces the shipped ablation. Gemini costs "
             "roughly 50x the output price of the other three; pass the other three keys "
             "explicitly to skip it, at the cost of no longer matching the paper.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrent scenario-scoring threads. Retrieval stays serial and "
             "deterministic; only the OpenRouter calls are parallelised. Set 1 to "
             "run fully serially.",
    )
    parser.add_argument(
        "--ablations",
        nargs="+",
        default=list(ABLATION_SPECS.keys()),
        choices=list(ABLATION_SPECS.keys()),
        help="Ablation IDs to run. Default: all ablations.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get(RUN_OUTPUT_DIR_ENV),
        help=f"Explicit safe output directory (or set {RUN_OUTPUT_DIR_ENV}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional safe Markdown report output path. If --output-dir is omitted, "
            "the report's parent directory is also used for Excel outputs."
        ),
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help=(
            "Read-only directory containing a prior rag_ablation_results.xlsx; "
            "required with --recompute-significance-only."
        ),
    )
    parser.add_argument(
        "--nn-fallback",
        choices=list(NN_FALLBACKS),
        default="tie",
        help="Copy-only (nearest_neighbor_k3) rule for a target alternative that no "
             "retrieved exemplar shares: 'tie' = mean over all retrieved alternatives "
             "(original rule; an all-miss scenario is decided by the tie-break), "
             "'nearest' = the exemplar alternatives nearest in value, 'unscored' = "
             "a scenario with no label match at all gets the sentinel and drops out "
             "of the means.",
    )
    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Do not write or resume per-(ablation, model) checkpoints under "
             "<output-dir>/checkpoints/. By default each finished unit is saved "
             "there and a restart skips it.",
    )
    parser.add_argument(
        "--recompute-significance-only",
        action="store_true",
        help="Skip retrieval and all API calls; reload the existing "
             "rag_ablation_results.xlsx in --input-dir and rerun only the "
             "Friedman/post-hoc/bootstrap significance suite. Use this after "
             "a change to the significance-testing code (e.g. correction "
             "policy) when the underlying scenario data has not changed.",
    )
    args = parser.parse_args()
    if args.recompute_significance_only:
        if not args.input_dir:
            parser.error("--input-dir is required with --recompute-significance-only.")
        try:
            output_dir, report_path = resolve_output_paths(args.output_dir, args.output)
            input_dir, output_dir = validate_recompute_directories(
                Path(args.input_dir), output_dir
            )
            _validate_report_outside_input(report_path, input_dir)
        except UnsafeOutputPathError as exc:
            parser.error(str(exc))
        args.input_dir = input_dir
        args.output_dir = output_dir
        args.output = report_path
    return args


if __name__ == "__main__":
    args = parse_args()
    try:
        output_dir, report_path = resolve_output_paths(args.output_dir, args.output)
    except UnsafeOutputPathError as exc:
        raise SystemExit(str(exc)) from exc
    if args.recompute_significance_only:
        recompute_significance_only(Path(args.input_dir), output_dir, report_path)
    else:
        args.output_dir = output_dir
        args.output = report_path
        try:
            run(args)
        except UnsafeOutputPathError as exc:
            raise SystemExit(str(exc)) from exc
