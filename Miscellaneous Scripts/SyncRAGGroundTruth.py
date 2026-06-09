"""SyncRAGGroundTruth.py

Refreshes the score columns in each RAG scenario file from the latest ground
truth files WITHOUT changing which scenario_ids are assigned to RAG.

Run this after re-running any Ground Truth Calculator to propagate updated
scores into the RAG corpus (then re-run BuildRAG.py to rebuild ChromaDB).

Workflow:
    1. python "Ground Truth Calculators/<Domain>GroundTruthCalculator.py"
    2. python "Miscellaneous Scripts/SyncRAGGroundTruth.py"
    3. python "Miscellaneous Scripts/BuildRAG.py"

Matching is intentionally strict: before overwriting anything the script
verifies that every descriptor column (question/description, location,
alternatives, physical parameters) in the existing RAG file matches the
corresponding ground truth row for the same (scenario_id, alternative) pair.
Any mismatch aborts the entire run so that no file is touched.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"


# Score columns that are allowed to differ (these are what we refresh).
SCORE_COLS = {
    "energy_cost_score",
    "environmental_score",
    "comfort_score",
    "practicality_score",
    "mavt_score",
    "rank",
    "raw_kwh",
    "raw_cost",
    "raw_emissions",
    "raw_water_gallons",
}

# Per-domain config ----------------------------------------------------------
# descriptor_cols: columns that MUST match between RAG and GT for the same
#                  (scenario_id, alternative) pair before we trust the refresh.
#                  These are the scenario parameters — not the computed scores.
CONFIG = {
    "HVAC": {
        "rag_file": "HVACRagScenarios.xlsx",
        "gt_file": "ground_truth_hvac.xlsx",
        "descriptor_cols": [
            "question",
            "location",
            "square_footage",
            "insulation",
            "household_size",
            "utility_budget",
            "housing_type",
            "outdoor_temp",
            "house_age",
            "alternative",
        ],
    },
    "Appliance": {
        "rag_file": "ApplianceRAGScenarios.xlsx",
        "gt_file": "ground_truth_appliance.xlsx",
        "descriptor_cols": [
            "question",
            "location",
            "utility_budget",
            "appliance",
            "appliance_age",
            "housing_type",
            "household_size",
            "kwh_per_cycle",
            "alternative",
        ],
    },
    "Shower": {
        "rag_file": "ShowerRAGScenarios.xlsx",
        "gt_file": "ground_truth_shower.xlsx",
        "descriptor_cols": [
            "question",
            "location",
            "household_size",
            "gpm",
            "utility_budget",
            "housing_type",
            "outdoor_temp",
            "alternative",
            "duration_min",
        ],
    },
}


# ---------------------------------------------------------------------------
# I/O helpers (identical to RoundScenarioCounts.py)
# ---------------------------------------------------------------------------

def read_xlsx(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, dtype=object, engine="openpyxl").fillna("")


def write_xlsx(df: pd.DataFrame, path: Path) -> None:
    df = df.copy()
    numeric_cols = SCORE_COLS - {"rank"}
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "rank" in df.columns:
        df["rank"] = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False, engine="openpyxl")


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm_str(value: object) -> str:
    """Collapse whitespace, strip, lowercase, drop non-ASCII lookalike chars."""
    s = str(value).strip()
    # Replace common unicode look-alikes that can sneak in via Excel copy-paste
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _norm_numeric(value: object) -> str:
    """Normalise numeric-ish values to a canonical string for comparison.

    Treats '' / None as '', and converts floats with a trailing .0 to ints so
    that '75.0' and '75' compare equal (common after Excel round-trips).
    """
    s = str(value).strip()
    if s in ("", "nan", "None"):
        return ""
    try:
        f = float(s)
        # If it is a whole number represent it without decimal for comparison.
        return str(int(f)) if f == int(f) else f"{f:.10g}"
    except ValueError:
        return _norm_str(s)


def _col_norm(col_name: str, value: object) -> str:
    """Pick the right normaliser for a column based on its name."""
    numeric_indicators = {
        "square_footage", "household_size", "utility_budget", "outdoor_temp",
        "house_age", "kwh_per_cycle", "gpm", "duration_min",
        "appliance_age",
    }
    if col_name in numeric_indicators:
        return _norm_numeric(value)
    # alternative is a numeric setpoint for HVAC (e.g. '75') but a clock time for
    # Appliance. Appliance times can appear in shorthand ('6pm') or canonical
    # ('6:00 PM') form across RAG vs GT, so normalise any am/pm time to 24h HH:MM
    # before comparing — otherwise '6pm' != '6:00 pm' would spuriously mismatch.
    if col_name == "alternative":
        s = str(value).strip()
        try:
            f = float(s)
            return str(int(f)) if f == int(f) else f"{f:.10g}"
        except ValueError:
            pass
        m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*([ap])m', s, re.IGNORECASE)
        if m:
            hh = int(m.group(1)) % 12
            if m.group(3).lower() == 'p':
                hh += 12
            return f"{hh:02d}:{int(m.group(2) or 0):02d}"
        return _norm_str(value)
    return _norm_str(value)



# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def sync_domain(
    dtype: str,
    cfg: dict,
    *,
    dry_run: bool = False,
) -> dict:
    rag_path = SCENARIO_DIR / cfg["rag_file"]
    gt_path = GROUND_TRUTH_DIR / cfg["gt_file"]

    if not rag_path.exists():
        raise FileNotFoundError(f"RAG file not found: {rag_path}")
    if not gt_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {gt_path}")

    rag_df = read_xlsx(rag_path)
    gt_df = read_xlsx(gt_path)

    descriptor_cols = cfg["descriptor_cols"]

    # ---- Column-presence check ----------------------------------------------
    missing = [c for c in descriptor_cols if c not in rag_df.columns or c not in gt_df.columns]
    if missing:
        raise ValueError(
            f"\n{'='*60}\nValidation FAILED for {dtype} — no files were written.\n"
            f"{'='*60}\n{dtype}: descriptor column(s) missing from RAG or GT: {missing}"
        )

    # ---- Match RAG rows to GT rows by DESCRIPTOR SIGNATURE, not scenario_id --
    # The RAG sheets carry their own sequential scenario_id (1..N per type) which
    # no longer corresponds to the master-row index used in the GT files, so a
    # scenario_id join is impossible. The descriptor columns (params + per-alt
    # alternative/duration) uniquely identify a scenario-alternative and MUST
    # already agree between the two files, so they are the correct join key.
    # Only the SCORE_COLS are copied across; every other RAG column is preserved
    # (writing the GT frame wholesale would drop RAG-only "show everything"
    # columns such as flow_rate / tank_size / water_heater_temp).
    def _signature(row) -> tuple:
        return tuple(_col_norm(c, row.get(c, "")) for c in descriptor_cols)

    gt_lookup: dict[tuple, dict] = {}
    for _, row in gt_df.iterrows():
        sig = _signature(row)
        if sig in gt_lookup:
            raise RuntimeError(
                f"{dtype}: GT has duplicate descriptor signature {sig} — "
                "cannot match unambiguously. Aborting before write."
            )
        gt_lookup[sig] = row.to_dict()

    score_cols = [c for c in SCORE_COLS if c in gt_df.columns and c in rag_df.columns]

    updated = rag_df.copy()
    unmatched: list[str] = []
    for idx, rag_row in updated.iterrows():
        gt_row = gt_lookup.get(_signature(rag_row))
        if gt_row is None:
            unmatched.append(
                f"  scenario_id={rag_row.get('scenario_id')!r}, "
                f"alternative={rag_row.get('alternative')!r}: no GT row with matching descriptors"
            )
            continue
        for col in score_cols:
            updated.at[idx, col] = gt_row[col]

    if unmatched:
        raise ValueError(
            f"\n{'='*60}\nValidation FAILED for {dtype} — no files were written.\n"
            f"{'='*60}\n{dtype}: {len(unmatched)} RAG row(s) had no descriptor match in GT:\n"
            + "\n".join(unmatched[:30])
            + ("\n  ... (truncated)" if len(unmatched) > 30 else "")
        )

    if not dry_run:
        write_xlsx(updated, rag_path)

    return {
        "scenarios_synced": rag_df["scenario_id"].nunique(),
        "rows_written": len(updated),
        "score_cols_refreshed": score_cols,
        "dry_run": dry_run,
    }


def main(dry_run: bool = False) -> None:
    print(f"{'DRY RUN — ' if dry_run else ''}Syncing RAG scenario files from ground truth...\n")

    all_passed = True
    results = {}

    for dtype, cfg in CONFIG.items():
        try:
            result = sync_domain(dtype, cfg, dry_run=dry_run)
            status = "DRY RUN" if dry_run else "WRITTEN"
            print(
                f"  [{status}] {dtype}: {result['scenarios_synced']} scenarios, "
                f"{result['rows_written']} rows"
            )
            results[dtype] = result
        except (ValueError, RuntimeError, FileNotFoundError) as exc:
            print(f"  [ERROR] {dtype}:\n{exc}\n", file=sys.stderr)
            all_passed = False

    print()
    if not all_passed:
        print("One or more domains failed. No partial writes were made for failed domains.")
        sys.exit(1)
    elif dry_run:
        print("Dry run complete — all validations passed. Run without --dry-run to write.")
    else:
        print("Sync complete. Run BuildRAG.py next to rebuild the ChromaDB vector store.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
