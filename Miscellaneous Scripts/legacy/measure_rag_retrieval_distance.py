"""C2: Measure Test->RAG retrieval distances in the exact units the production
query path uses (L2 on unnormalized all-MiniLM-L6-v2 embeddings).

Replicates, field-for-field:
  - Index side:  Miscellaneous Scripts/build_rag_index.py (embed path, lines ~224-235 /
    252-263 / 279-290): read_table_clean(RAG sheet) -> group by scenario_id ->
    first_row -> format_embedding_text(decision_type, first_row) ->
    embedding_model.encode(text) (bare, no normalize_embeddings).
  - Query side:  Architectures/Example-Guided_LLM_Scoring.py (lines 309-327):
    read_table_clean(TestScenarios.xlsx, keep_str_cols=[alt cols]) ->
    row.to_dict() -> format_embedding_text(decision_type, scenario) ->
    embedding_model.encode(text) (bare, no normalize_embeddings).
  - Candidate pool: production queries filter where={"decision_type": X}
    (Example-Guided_LLM_Scoring.py line 338), so nearest-neighbour search is
    restricted to the same decision type's corpus entries, exactly like here.
  - Distance unit: Chroma's default hnsw space is L2 (build_rag_index.py line 204 has
    no hnsw:space key). True L2 = np.linalg.norm(q - c), the same convention as
    the ablation harness (Miscellaneous Scripts/run_rag_ablation_experiments.py line 623).

No API calls. All data on disk. New file; nothing existing is modified.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentinel_utils import format_embedding_text, read_table_clean

SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
TEST_SCENARIOS = SCENARIO_DIR / "TestScenarios.xlsx"
RAG_FILES = {
    "HVAC": "HVACRagScenarios.xlsx",
    "Appliance": "ApplianceRAGScenarios.xlsx",
    "Shower": "ShowerRAGScenarios.xlsx",
}
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OUT_XLSX = PROJECT_ROOT / "Analysis" / "TestRAG_distances.xlsx"
OUT_JSON = PROJECT_ROOT / "Analysis" / "TestRAG_distances.json"


def build_corpus(model):
    """One embedding per RAG scenario, exactly as build_rag_index.py does."""
    corpus = []  # list of dicts: decision_type, scenario_id, text, embedding
    for dtype, fname in RAG_FILES.items():
        df = read_table_clean(SCENARIO_DIR / fname)
        for scenario_id, group in df.groupby("scenario_id"):
            first_row = group.iloc[0]
            text = format_embedding_text(dtype, first_row)
            emb = model.encode(text)  # bare encode: no normalize_embeddings
            corpus.append({
                "decision_type": dtype,
                "scenario_id": f"{dtype.lower()}_{scenario_id}",
                "text": text,
                "embedding": emb,
            })
    return corpus


def load_test_scenarios():
    """Query-side dicts, exactly as Example-Guided_LLM_Scoring.py lines 764-776."""
    df = read_table_clean(
        TEST_SCENARIOS,
        keep_str_cols=["alternative_1", "alternative_2", "alternative_3"],
    )
    return df, [row.to_dict() for _, row in df.iterrows()]


def l2(a, b):
    return float(np.linalg.norm(a - b))


def main():
    print("Loading embedding model (all-MiniLM-L6-v2, unnormalized encode)...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Embedding RAG corpus (90 scenarios)...")
    corpus = build_corpus(model)
    by_type = {}
    for c in corpus:
        by_type.setdefault(c["decision_type"], []).append(c)

    print("Embedding Test scenarios (195)...")
    test_df, scenarios = load_test_scenarios()
    # Build the query text the same way the production code does.
    test_rows = []
    for i, scenario in enumerate(scenarios):
        dtype = scenario.get("decision_type", "HVAC")
        try:
            text = format_embedding_text(dtype, scenario)
        except ValueError:
            text = scenario.get("question", "")
        emb = model.encode(text)
        test_rows.append({
            "idx": i,
            "decision_type": dtype,
            "text": text,
            "embedding": emb,
        })

    # RAG->RAG leave-one-out nearest-neighbour L2 (same-type only), the pairing
    # the old "0.05" claim was measured on.
    loo_nn = []
    for c in corpus:
        same_type = [o for o in by_type[c["decision_type"]] if o["scenario_id"] != c["scenario_id"]]
        loo_nn.append(min(l2(c["embedding"], o["embedding"]) for o in same_type))

    rows = []
    for tr in test_rows:
        dtype = tr["decision_type"]
        same_type = by_type[dtype]
        d = np.array([l2(tr["embedding"], c["embedding"]) for c in same_type])
        nn_idx = int(np.argmin(d))
        d_all = np.array([l2(tr["embedding"], c["embedding"]) for c in corpus])
        rows.append({
            "idx": tr["idx"],
            "decision_type": dtype,
            "question": scenarios[tr["idx"]].get("question", ""),
            "nn_distance": float(d[nn_idx]),
            "nn_corpus_id": same_type[nn_idx]["scenario_id"],
            "random_mean_same_type": float(d.mean()),
            "random_mean_all_corpus": float(d_all.mean()),
            "min_same_type": float(d.min()),
            "max_same_type": float(d.max()),
        })

    out = pd.DataFrame(rows)
    out.to_excel(OUT_XLSX, index=False)

    def summ(vals, label):
        v = np.array(vals, dtype=float)
        return {"label": label, "n": int(len(v)), "min": float(v.min()),
                "median": float(np.median(v)), "max": float(v.max()),
                "mean": float(v.mean())}

    nn_all = out["nn_distance"].values
    rand_all = out["random_mean_same_type"].values
    rand_all_corpus = out["random_mean_all_corpus"].values
    summary = {
        "test_rag_nn": summ(nn_all, "Test->RAG nearest neighbour L2 (all 195)"),
        "test_rag_random_mean": summ(rand_all, "Test->RAG random corpus entry L2 mean, same-type pool (all 195)"),
        "test_rag_random_mean_all_corpus": summ(rand_all_corpus, "Test->RAG random corpus entry L2 mean, all 90 entries (all 195)"),
        "rag_rag_loo": summ(loo_nn, "RAG->RAG leave-one-out NN L2 (90 corpus scenarios)"),
        "per_type": {},
    }
    for dtype in ("HVAC", "Appliance", "Shower"):
        sub = out[out["decision_type"] == dtype]
        summary["per_type"][dtype] = {
            "n": int(len(sub)),
            "nn": summ(sub["nn_distance"].values, f"{dtype} NN"),
            "random_mean": summ(sub["random_mean_same_type"].values, f"{dtype} random"),
        }

    # Verdict logic: if NN median is within ~10-20% of the random mean, or the
    # NN median sits far above the RAG->RAG LOO median, retrieval discriminates
    # little for test queries.
    nn_med = float(np.median(nn_all))
    rand_mean = float(np.mean(rand_all))
    rand_mean_all = float(np.mean(rand_all_corpus))
    loo_med = float(np.median(loo_nn))
    ratio = nn_med / rand_mean
    verdict = (
        "NEARLY NON-DISCRIMINATING"
        if ratio >= 0.9
        else "WEAKLY DISCRIMINATING"
        if ratio >= 0.8
        else "DISCRIMINATING"
    )
    summary["verdict"] = {
        "nn_median": nn_med,
        "random_mean": rand_mean,
        "random_mean_all_corpus": rand_mean_all,
        "ratio_nn_to_random": ratio,
        "rag_rag_loo_median": loo_med,
        "ratio_nn_to_loo": nn_med / loo_med if loo_med > 0 else float("nan"),
        "verdict": verdict,
        "rule": "NN median / random mean >= 0.9 -> near-random (little discrimination)",
    }

    with open(OUT_JSON, "w") as f:
        json.dump(summary, f, indent=2)

    print("=" * 70)
    print("C2 RETRIEVAL DISTANCE MEASUREMENT (L2, unnormalized all-MiniLM-L6-v2)")
    print("=" * 70)
    for key in ("test_rag_nn", "test_rag_random_mean", "test_rag_random_mean_all_corpus", "rag_rag_loo"):
        s = summary[key]
        print(f"\n{s['label']}:")
        print(f"  n      = {s['n']}")
        print(f"  min    = {s['min']:.4f}")
        print(f"  median = {s['median']:.4f}")
        print(f"  mean   = {s['mean']:.4f}")
        print(f"  max    = {s['max']:.4f}")
    print("\nPer decision type (Test->RAG):")
    for dtype, d in summary["per_type"].items():
        print(f"  {dtype:<10} n={d['n']:>3}  NN median={d['nn']['median']:.4f} "
              f"NN min={d['nn']['min']:.4f} NN max={d['nn']['max']:.4f} "
              f"random mean={d['random_mean']['mean']:.4f}")
    v = summary["verdict"]
    print(f"\nVERDICT: {v['verdict']}")
    print(f"  NN median / random mean = {v['ratio_nn_to_random']:.3f} "
          f"({nn_med:.4f} vs {rand_mean:.4f})")
    print(f"  NN median / RAG->RAG LOO median = {v['ratio_nn_to_loo']:.2f} "
          f"({nn_med:.4f} vs {loo_med:.4f})")
    print(f"\nWrote {OUT_XLSX}")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
