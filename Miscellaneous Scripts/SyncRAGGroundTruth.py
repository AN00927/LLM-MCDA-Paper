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
    # alternative is a numeric setpoint for HVAC (e.g. '75') but a time string
    # for Appliance (e.g. '2:00 AM') — safe to try numeric first, fall back.
    if col_name == "alternative":
        try:
            f = float(str(value).strip())
            return str(int(f)) if f == int(f) else f"{f:.10g}"
        except ValueError:
            return _norm_str(value)
    return _norm_str(value)


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def _validate_domain(
    dtype: str,
    rag_df: pd.DataFrame,
    gt_df: pd.DataFrame,
    descriptor_cols: list[str],
    rag_path: Path,
    gt_path: Path,
) -> list[str]:
    """Return a list of error strings (empty = all good).

    Checks performed (all before any write):
      1. scenario_id column present in both files
      2. Every RAG scenario_id exists in GT
      3. Every RAG scenario_id has exactly 3 rows in GT
      4. No GT scenario_id appears MORE than 3 times (sanity)
      5. For each (scenario_id, alternative) pair: all descriptor columns
         match between the RAG row and the GT row (normalised comparison)
    """
    errors: list[str] = []

    # -- 1. Column presence ---------------------------------------------------
    for col in ["scenario_id"] + descriptor_cols:
        if col not in rag_df.columns:
            errors.append(f"{dtype}: RAG file missing expected column '{col}' ({rag_path.name})")
        if col not in gt_df.columns:
            errors.append(f"{dtype}: GT file missing expected column '{col}' ({gt_path.name})")
    if errors:
        return errors  # Can't proceed without the key columns

    # -- Coerce scenario_id to int in both -----------------------------------
    try:
        rag_df = rag_df.copy()
        gt_df = gt_df.copy()
        rag_df["scenario_id"] = pd.to_numeric(rag_df["scenario_id"], errors="raise").astype(int)
        gt_df["scenario_id"] = pd.to_numeric(gt_df["scenario_id"], errors="raise").astype(int)
    except Exception as exc:
        errors.append(f"{dtype}: scenario_id is not numeric — {exc}")
        return errors

    rag_ids = sorted(rag_df["scenario_id"].unique())
    gt_ids_set = set(gt_df["scenario_id"].unique())

    # -- 2. All RAG scenario_ids present in GT --------------------------------
    missing_in_gt = [sid for sid in rag_ids if sid not in gt_ids_set]
    if missing_in_gt:
        errors.append(
            f"{dtype}: {len(missing_in_gt)} RAG scenario_id(s) not found in GT: {missing_in_gt}"
        )

    # -- 3 & 4. Row counts per scenario_id in GT ------------------------------
    gt_counts = gt_df["scenario_id"].value_counts()
    wrong_count = {
        sid: int(gt_counts[sid])
        for sid in rag_ids
        if sid in gt_counts.index and gt_counts[sid] != 3
    }
    if wrong_count:
        errors.append(
            f"{dtype}: GT has wrong row count (expected 3 per scenario_id) for: {wrong_count}"
        )
    gt_excess = {
        sid: int(cnt)
        for sid, cnt in gt_counts.items()
        if sid not in set(rag_ids) and cnt != 3
    }
    # (We only flag excess outside RAG if they have the wrong count — the GT
    # may legitimately contain test scenarios too, so just check count==3.)

    if errors:
        return errors  # Don't run descriptor check if structural issues exist

    # -- 5. Descriptor column match per (scenario_id, alternative) pair ------
    # Build a GT lookup: (scenario_id, norm_alternative) -> row dict
    gt_lookup: dict[tuple[int, str], dict] = {}
    for _, row in gt_df.iterrows():
        sid = int(row["scenario_id"])
        alt_key = _col_norm("alternative", row.get("alternative", ""))
        pair = (sid, alt_key)
        if pair in gt_lookup:
            errors.append(
                f"{dtype}: GT has duplicate (scenario_id={sid}, alternative={row.get('alternative')!r}) — "
                "cannot match unambiguously"
            )
        else:
            gt_lookup[pair] = row.to_dict()

    if errors:
        return errors

    mismatches: list[str] = []
    for _, rag_row in rag_df.iterrows():
        sid = int(rag_row["scenario_id"])
        alt_key = _col_norm("alternative", rag_row.get("alternative", ""))
        pair = (sid, alt_key)

        if pair not in gt_lookup:
            mismatches.append(
                f"  scenario_id={sid}, alternative={rag_row.get('alternative')!r}: "
                "no matching (scenario_id, alternative) pair in GT"
            )
            continue

        gt_row = gt_lookup[pair]
        for col in descriptor_cols:
            rag_val = _col_norm(col, rag_row.get(col, ""))
            gt_val = _col_norm(col, gt_row.get(col, ""))
            if rag_val != gt_val:
                mismatches.append(
                    f"  scenario_id={sid}, alternative={rag_row.get('alternative')!r}, "
                    f"col='{col}': RAG={rag_row.get(col)!r} vs GT={gt_row.get(col)!r}"
                )

    if mismatches:
        errors.append(
            f"{dtype}: descriptor mismatch(es) between RAG and GT "
            f"({len(mismatches)} row(s)):\n" + "\n".join(mismatches[:30])
            + ("\n  ... (truncated)" if len(mismatches) > 30 else "")
        )

    return errors


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

    # ---- Full pre-write validation ------------------------------------------
    errors = _validate_domain(dtype, rag_df, gt_df, descriptor_cols, rag_path, gt_path)
    if errors:
        raise ValueError(
            f"\n{'='*60}\n"
            f"Validation FAILED for {dtype} — no files were written.\n"
            f"{'='*60}\n"
            + "\n".join(errors)
        )

    # ---- Build the refreshed dataframe from GT rows -------------------------
    rag_df_typed = rag_df.copy()
    gt_df_typed = gt_df.copy()
    rag_df_typed["scenario_id"] = pd.to_numeric(rag_df_typed["scenario_id"], errors="raise").astype(int)
    gt_df_typed["scenario_id"] = pd.to_numeric(gt_df_typed["scenario_id"], errors="raise").astype(int)

    rag_ids = set(rag_df_typed["scenario_id"].unique())
    refreshed_df = (
        gt_df_typed[gt_df_typed["scenario_id"].isin(rag_ids)]
        .copy()
        .sort_values(["scenario_id"])
        .reset_index(drop=True)
    )

    # ---- Final sanity: row count must be exactly scenario_count × 3 ---------
    expected_rows = len(rag_ids) * 3
    if len(refreshed_df) != expected_rows:
        raise RuntimeError(
            f"{dtype}: refreshed dataframe has {len(refreshed_df)} rows "
            f"but expected {expected_rows} ({len(rag_ids)} scenarios × 3 alternatives). "
            "Aborting before write."
        )

    # ---- scenario_id set must be unchanged ----------------------------------
    refreshed_ids = set(refreshed_df["scenario_id"].unique())
    if refreshed_ids != rag_ids:
        added = refreshed_ids - rag_ids
        dropped = rag_ids - refreshed_ids
        raise RuntimeError(
            f"{dtype}: scenario_id set changed after filtering GT. "
            f"Added: {sorted(added)}, Dropped: {sorted(dropped)}"
        )

    if not dry_run:
        write_xlsx(refreshed_df, rag_path)

    return {
        "scenarios_synced": len(rag_ids),
        "rows_written": len(refreshed_df),
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
