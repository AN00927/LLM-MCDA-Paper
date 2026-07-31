import hashlib
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
import sys

RAG_FILES = {
    'HVAC': {

        'ground_truth': 'HVACRagScenarios.xlsx'
    },
    'Appliance': {
        'ground_truth': 'ApplianceRAGScenarios.xlsx'
    },
    'Shower': {
        'ground_truth': 'ShowerRAGScenarios.xlsx'
    }
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
CHROMA_DB_PATH = PROJECT_ROOT / "chroma_rag_db"
COLLECTION_NAME = 'mcda_scenarios'
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from sentinel_utils import (
    read_table_clean,
    format_embedding_text,
    house_age_to_band_label,
    gpm_to_flow_rate_label,
    appliance_age_to_band_label,
)

# Bump this any time the metadata field set OR the embedding string changes —
# the source-file hash only catches RAG sheet edits, not changes to how we
# embed/render them, so a code-only change must bump this to force a rebuild.
# v3: "show everything" — full homeowner + engineering params and per-alt
#     mavt/rank in metadata; embedding expanded (budget + age/flow labels).
# v4: appliance_age banded (3-yr early / 5-yr later) in both the embedding and
#     the display metadata, mirroring house_age.
RAG_SCHEMA_VERSION = 4


def compute_source_table_hash(csv_dir: Path = SCENARIO_DIR) -> str:
    """SHA-256 of the concatenated bytes of the three RAG source files."""
    h = hashlib.sha256()
    for decision_type in ('HVAC', 'Appliance', 'Shower'):
        path = Path(csv_dir) / RAG_FILES[decision_type]['ground_truth']
        # Stable order: tag with filename so reordering files changes the hash.
        h.update(decision_type.encode('utf-8'))
        h.update(b'|')
        h.update(path.name.encode('utf-8'))
        h.update(b'|')
        with open(path, 'rb') as f:
            h.update(f.read())
        h.update(b'|')
    return h.hexdigest()


def load_hvac_data(csv_dir: str) -> pd.DataFrame:
    """Load HVAC data (single file contains everything)."""
    gt_path = Path(csv_dir) / RAG_FILES['HVAC']['ground_truth']
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from sentinel_utils import read_table_clean
    df = read_table_clean(gt_path)
    df['alternative_num'] = df.groupby('scenario_id').cumcount() + 1
    return df


def load_appliance_data(csv_dir: str) -> pd.DataFrame:
    """Load Appliance data (GT file contains everything)."""
    gt_path = Path(csv_dir) / RAG_FILES['Appliance']['ground_truth']
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from sentinel_utils import read_table_clean
    df = read_table_clean(gt_path)
    return df


def load_shower_data(csv_dir: str) -> pd.DataFrame:
    """Load Shower data (scenario file contains everything)."""
    scenarios_path = Path(csv_dir) / RAG_FILES['Shower']['ground_truth']
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from sentinel_utils import read_table_clean
    df = read_table_clean(scenarios_path)
    return df


def format_scenario_text(row, decision_type: str) -> str:
    """Embedding document for a scenario (delegates to the shared builder so the
    index side stays byte-identical to Eample-Guided_LLM_Scoring.py's query side)."""
    return format_embedding_text(decision_type, row)


def _meta_val(v):
    """Coerce a cell to a Chroma-legal metadata scalar (str/int/float/bool).

    None / NaN / pandas-NA become '' so a missing field is visibly blank rather
    than crashing collection.add (which rejects None)."""
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except (TypeError, ValueError):
        pass
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v.item() if hasattr(v, 'item') else v
    return str(v)


def build_scenario_metadata(decision_type: str, first_row, group) -> dict:
    """Full "show everything" metadata for one scenario.

    Stores every homeowner + engineering parameter the LLM may see (excluding the
    literal raw_* physical quantities) plus, per alternative, the 4 criterion
    scores AND the mavt aggregate + rank. house_age is stored as a band label so
    the rendered exemplar mirrors the target-scenario block. Used only for display
    at query time; embedding/similarity comes from format_scenario_text.
    """
    md = {
        'decision_type': decision_type,
        'scenario_id': f"{decision_type.lower()}_{first_row['scenario_id']}",
        'question': _meta_val(first_row.get('question')),
        'location': _meta_val(first_row.get('location')),
        'household_size': _meta_val(first_row.get('household_size')),
        'housing_type': _meta_val(first_row.get('housing_type')),
        'utility_budget': _meta_val(first_row.get('utility_budget')),
    }

    if decision_type == 'HVAC':
        md.update({
            'square_footage': _meta_val(first_row.get('square_footage')),
            'insulation': _meta_val(first_row.get('insulation')),
            'outdoor_temp': _meta_val(first_row.get('outdoor_temp')),
            'house_age': house_age_to_band_label(first_row.get('house_age')),
            'r_value': _meta_val(first_row.get('r_value')),
            'seer': _meta_val(first_row.get('seer')),
            'hvac_age': _meta_val(first_row.get('hvac_age')),
        })
    elif decision_type == 'Appliance':
        md.update({
            'appliance': _meta_val(first_row.get('appliance')),
            # Banded for display so the exemplar mirrors the (banded) target
            # block; mirrors how house_age is stored as a label.
            'appliance_age': appliance_age_to_band_label(first_row.get('appliance_age')),
            'kwh_per_cycle': _meta_val(first_row.get('kwh_per_cycle')),
        })
    elif decision_type == 'Shower':
        fr = first_row.get('flow_rate')
        if fr is None or str(fr).strip() in ('', 'nan', 'N/A', '<NA>'):
            fr = gpm_to_flow_rate_label(first_row.get('gpm', 0))
        md.update({
            'outdoor_temp': _meta_val(first_row.get('outdoor_temp')),
            'gpm': _meta_val(first_row.get('gpm')),
            'flow_rate': fr,
            'tank_size': _meta_val(first_row.get('tank_size')),
            'water_heater_temp': _meta_val(first_row.get('water_heater_temp')),
        })

    for i, (_, r) in enumerate(group.iterrows(), 1):
        if decision_type == 'Shower':
            name = f"{int(round(float(r['duration_min'])))} min"
        else:
            name = str(r['alternative'])
        md[f'alt{i}'] = name
        md[f'alt{i}_energy_cost'] = float(r['energy_cost_score'])
        md[f'alt{i}_environmental'] = float(r['environmental_score'])
        md[f'alt{i}_comfort'] = float(r['comfort_score'])
        md[f'alt{i}_practicality'] = float(r['practicality_score'])
        md[f'alt{i}_mavt'] = float(r['mavt_score'])
        md[f'alt{i}_rank'] = int(round(float(r['rank'])))
    return md


def build_rag_database(csv_dir=SCENARIO_DIR):
    """Build ChromaDB vector database from RAG scenario files."""
    print("BUILDING RAG DATABASE")

    # Initialize embedding model
    print(f"\nLoading embedding mo del: {EMBEDDING_MODEL}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"Model loaded (embedding dim: {embedding_model.get_sentence_embedding_dimension()})")

    # Initialize ChromaDB
    print(f"\nInitializing ChromaDB at: {CHROMA_DB_PATH}")
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))

    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection: {COLLECTION_NAME}")
    except:
        pass

    source_hash = compute_source_table_hash(csv_dir)
    print(f"Source SHA-256: {source_hash}")
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "MCDA scenarios with ground truth scores",
            "source_table_sha256": source_hash,
            "schema_version": RAG_SCHEMA_VERSION,
        }
    )
    print(f"Created collection: {COLLECTION_NAME}")

    total_scenarios = 0

    # HVAC
    
    print(f"Processing HVAC scenarios")
    
    try:
        hvac_df = load_hvac_data(csv_dir)
        print(f"Loaded {len(hvac_df)} HVAC scenario-alternative combinations")

        for scenario_id, group in hvac_df.groupby('scenario_id'):
            first_row = group.iloc[0]
            scenario_text = format_scenario_text(first_row, 'HVAC')
            embedding = embedding_model.encode(scenario_text).tolist()
            metadata = build_scenario_metadata('HVAC', first_row, group)

            collection.add(
                ids=[metadata['scenario_id']],
                embeddings=[embedding],
                documents=[scenario_text],
                metadatas=[metadata]
            )

        unique_scenarios = len(hvac_df['scenario_id'].unique())
        print(f"Added {unique_scenarios} HVAC scenarios to database")
        total_scenarios += unique_scenarios

    except Exception as e:
        print(f" Error processing HVAC scenarios: {e}")

    # Appliance
    
    print(f"Processing Appliance scenarios")

    try:
        appliance_df = load_appliance_data(csv_dir)
        print(f"Loaded {len(appliance_df)} Appliance scenario-alternative combinations")

        for scenario_id, group in appliance_df.groupby('scenario_id'):
            first_row = group.iloc[0]
            scenario_text = format_scenario_text(first_row, 'Appliance')
            embedding = embedding_model.encode(scenario_text).tolist()
            metadata = build_scenario_metadata('Appliance', first_row, group)

            collection.add(
                ids=[metadata['scenario_id']],
                embeddings=[embedding],
                documents=[scenario_text],
                metadatas=[metadata]
            )

        unique_scenarios = len(appliance_df['scenario_id'].unique())
        print(f"Added {unique_scenarios} Appliance scenarios to database")
        total_scenarios += unique_scenarios

    except Exception as e:
        print(f" Error processing Appliance scenarios: {e}")

    # Shower
    
    print(f"Processing Shower scenarios")
    
    try:
        shower_df = load_shower_data(csv_dir)
        print(f"Loaded {len(shower_df)} Shower scenario-alternative combinations")
        for scenario_id, group in shower_df.groupby('scenario_id'):
            first_row = group.iloc[0]
            scenario_text = format_scenario_text(first_row, 'Shower')
            embedding = embedding_model.encode(scenario_text).tolist()
            metadata = build_scenario_metadata('Shower', first_row, group)

            collection.add(
                ids=[metadata['scenario_id']],
                embeddings=[embedding],
                documents=[scenario_text],
                metadatas=[metadata]
            )

        unique_scenarios = len(shower_df['scenario_id'].unique())
        print(f"added {unique_scenarios} Shower scenarios to database")
        total_scenarios += unique_scenarios

    except Exception as e:
        print(f" Error processing Shower scenarios: {e}")

    # Summary
    
    print(f"DATABASE BUILD COMPLETE")
    print(f"Total scenarios: {total_scenarios}")
    print(f"Database location: {CHROMA_DB_PATH}")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"\nTo use in Eample-Guided_LLM_Scoring.py.py:")
    print(f"  client = chromadb.PersistentClient(path='{CHROMA_DB_PATH}')")
    print(f"  collection = client.get_collection('{COLLECTION_NAME}')")


def test_retrieval(test_scenario_text: str, decision_type: str, k: int = 3):
    """
    Test retrieval from built database.

    Args:
        test_scenario_text: Text description of test scenario
        decision_type: 'HVAC', 'Appliance', or 'Shower'
        k: Number of similar scenarios to retrieve
    """
    
    print(f"TESTING RETRIEVAL")
    print(f"Query: {test_scenario_text}")
    print(f"Decision type filter: {decision_type}")
    print(f"Retrieving top-{k} similar scenarios...\n")

    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    collection = client.get_collection(COLLECTION_NAME)

    embedding_model = SentenceTransformer(EMBEDDING_MODEL)

    query_embedding = embedding_model.encode(test_scenario_text).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where={"decision_type": decision_type}
    )

    if results['ids'] and len(results['ids'][0]) > 0:
        for i, (doc_id, doc_text, metadata) in enumerate(zip(
                results['ids'][0],
                results['documents'][0],
                results['metadatas'][0]
        )):
            print(f"Result {i + 1}: {doc_id}")
            print(f"  Text: {doc_text}")
            print(f"  Question: {metadata.get('question', 'N/A')}")
            print(f"  Alternative 1 ({metadata.get('alt1', 'N/A')}):")
            print(f"    Energy: {metadata.get('alt1_energy_cost', 0):.2f}, "
                  f"Env: {metadata.get('alt1_environmental', 0):.2f}, "
                  f"Comfort: {metadata.get('alt1_comfort', 0):.2f}, "
                  f"Pract: {metadata.get('alt1_practicality', 0):.2f}")
            print()
    else:
        print("No results foun")


def run_demo_retrieval_cases():
    test_cases = [
        (
            "dishwasher, 1.4 kWh/cycle, 4 occupants, Townhouse, peak $0.18/kWh, off-peak $0.08/kWh",
            "Appliance",
            "Scenario 9: I want to run my dishwasher this afternoon (around 2 PM). When should I start it?"
        ),
        (
            "dishwasher, 1.4 kWh/cycle, 3 occupants, Townhouse, peak $0.18/kWh, off-peak $0.09/kWh",
            "Appliance",
            "Scenario 10: Planning to clean up from lunch around 2 PM. When's the best time for the dishwasher?"
        ),
        (
            "dishwasher, 0.98 kWh/cycle, 4 occupants, Single-family, peak $0.17/kWh, off-peak $0.09/kWh",
            "Appliance",
            "Scenario 11: When should I do dishes today?"
        ),
    ]

    for scenario_text, decision_type, label in test_cases:
        print(f"\n{label}")
        test_retrieval(scenario_text, decision_type, k=3)


if __name__ == "__main__":
    build_rag_database()
    if len(sys.argv) > 1 and sys.argv[1] == "--demo-retrieval":
        run_demo_retrieval_cases()