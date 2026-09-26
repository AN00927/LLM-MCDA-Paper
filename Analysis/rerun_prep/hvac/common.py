"""Shared helpers for the HVAC / Shower reference-calculator rerun-prep harness.

Nothing here writes to Ground Truth/, Scenario Files/ or chroma_rag_db/. Calculator
runs go through each module's own process_*_scenarios() (so the xlsx-writing code path
is the one that produced the shipped files), with the output sent to a temporary
directory and read straight back.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RERUN_PREP = PROJECT_ROOT / "Analysis" / "rerun_prep"
HVAC_DIR = RERUN_PREP / "hvac"
OUT_DIR = HVAC_DIR / "out"

SCENARIO_DIR = PROJECT_ROOT / "Scenario Files"
GROUND_TRUTH_DIR = PROJECT_ROOT / "Ground Truth"
SHIPPED_CALC_DIR = PROJECT_ROOT / "Ground Truth Calculators"

# Frozen byte-identical copies of the calculators as shipped on 2026-09-25. They stay
# the "before" side of every comparison after the installed files are replaced.
FROZEN_DIR = HVAC_DIR / "shipped"
NEW_DIR = RERUN_PREP / "calc_new"

HVAC_MASTER = SCENARIO_DIR / "HVACScenarios.xlsx"
HVAC_RAG = SCENARIO_DIR / "HVACRagScenarios.xlsx"
HVAC_GT = GROUND_TRUTH_DIR / "ground_truth_hvac.xlsx"
SHOWER_MASTER = SCENARIO_DIR / "ShowerScenarios.xlsx"
SHOWER_RAG = SCENARIO_DIR / "ShowerRAGScenarios.xlsx"
SHOWER_GT = GROUND_TRUTH_DIR / "ground_truth_shower.xlsx"

SCORE_COLS = ["energy_cost_score", "environmental_score", "comfort_score",
              "practicality_score", "mavt_score", "rank"]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SYNC = None


def sync_module():
    """The repo's sync_rag_ground_truth_scores module (for its descriptor matching)."""
    global _SYNC
    if _SYNC is None:
        _SYNC = load_module(PROJECT_ROOT / "Miscellaneous Scripts" / "core-automation"
                            / "sync_rag_ground_truth_scores.py", "sync_rag_gt_scores")
    return _SYNC


def run_hvac(module, cls=None, master: Path = HVAC_MASTER) -> pd.DataFrame:
    """Run module.process_hvac_scenarios with calculator class `cls` (default: the
    module's own class) into a temp file and read it back."""
    return _run(module, "HVACGroundTruthCalculator", "process_hvac_scenarios", cls, master)


def run_shower(module, cls=None, master: Path = SHOWER_MASTER) -> pd.DataFrame:
    return _run(module, "ShowerGroundTruthCalculator", "process_shower_scenarios", cls, master)


def _run(module, cls_name, fn_name, cls, master):
    orig = getattr(module, cls_name)
    if cls is not None:
        setattr(module, cls_name, cls)
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "gt.xlsx"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                getattr(module, fn_name)(str(master), str(out))
            return pd.read_excel(out)
    finally:
        setattr(module, cls_name, orig)


# sentinel_utils.apply_mavt_ranking now rounds the weighted sum to 10 dp before ranking
# (MAVT_ROUND_DECIMALS, added 2026-09-25 by the P3 tie-break work), so a stored mavt_score
# can differ from a fresh one by float noise (~1e-16). mavt_score is compared to 1e-9;
# every other column, rank included, must match exactly.
FLOAT_TOL_COLS = {"mavt_score": 1e-9}


def compare_frames(a: pd.DataFrame, b: pd.DataFrame, cols=None) -> dict:
    """Exact cell comparison (NaN == NaN), except FLOAT_TOL_COLS. Returns {col: n_mismatch}."""
    if a.shape[0] != b.shape[0]:
        return {"__rows__": abs(a.shape[0] - b.shape[0])}
    cols = cols or [c for c in a.columns if c in b.columns]
    res = {}
    for c in cols:
        x, y = a[c].reset_index(drop=True), b[c].reset_index(drop=True)
        both_nan = x.isna() & y.isna()
        eq = (x == y) | both_nan
        if c in FLOAT_TOL_COLS:
            eq = eq | ((pd.to_numeric(x, errors="coerce") - pd.to_numeric(y, errors="coerce")).abs()
                       <= FLOAT_TOL_COLS[c])
        res[c] = int((~eq).sum())
    return res


def rag_signatures(gt: pd.DataFrame, rag_path: Path, dtype: str) -> tuple[set, dict]:
    """Match RAG rows to GT rows by the sync script's descriptor signature.
    Returns (set of GT scenario_ids that are RAG, {gt_row_index: rag_row_index})."""
    sync = sync_module()
    cols = sync.CONFIG[dtype]["descriptor_cols"]
    rag = pd.read_excel(rag_path, dtype=object, engine="openpyxl").fillna("")
    gt_obj = gt.astype(object).where(gt.notna(), "")

    def sig(row):
        return tuple(sync._col_norm(c, row.get(c, "")) for c in cols)

    rag_lookup = {sig(r): i for i, r in rag.iterrows()}
    matches = {}
    for i, r in gt_obj.iterrows():
        j = rag_lookup.get(sig(r))
        if j is not None:
            matches[i] = j
    rag_sids = set(int(gt.loc[i, "scenario_id"]) for i in matches)
    return rag_sids, matches


def check_rag_scores(gt: pd.DataFrame, rag_path: Path, dtype: str) -> dict:
    """Compare every RAG score column with the matching GT row (exact after the sync
    script's numeric write: RAG stores the GT value)."""
    rag = pd.read_excel(rag_path)
    _, matches = rag_signatures(gt, rag_path, dtype)
    sync = sync_module()
    cols = [c for c in sync.SCORE_COLS if c in gt.columns and c in rag.columns]
    mism = {c: 0 for c in cols}
    for gi, ri in matches.items():
        for c in cols:
            g, r = gt.loc[gi, c], rag.loc[ri, c]
            tol = FLOAT_TOL_COLS.get(c)
            close = tol is not None and not (pd.isna(g) or pd.isna(r)) and abs(float(g) - float(r)) <= tol
            if not ((pd.isna(g) and pd.isna(r)) or g == r or close):
                mism[c] += 1
    return {"rag_rows": len(rag), "matched": len(matches), "mismatch": mism}


def orderings(df: pd.DataFrame) -> dict:
    """{scenario_id: tuple of alternatives, best first} from the rank column."""
    out = {}
    for sid, g in df.groupby("scenario_id"):
        g = g.sort_values("rank")
        out[int(sid)] = tuple(str(a) for a in g["alternative"])
    return out


def ranking_changes(base: pd.DataFrame, new: pd.DataFrame, rag_sids: set) -> dict:
    ob, on = orderings(base), orderings(new)
    res = {"test": {"n": 0, "winner": 0, "full": 0, "winner_ids": [], "full_ids": []},
           "rag": {"n": 0, "winner": 0, "full": 0, "winner_ids": [], "full_ids": []}}
    for sid in ob:
        k = "rag" if sid in rag_sids else "test"
        res[k]["n"] += 1
        if ob[sid][0] != on[sid][0]:
            res[k]["winner"] += 1
            res[k]["winner_ids"].append(sid)
        if ob[sid] != on[sid]:
            res[k]["full"] += 1
            res[k]["full_ids"].append(sid)
    return res


def _fmt(v, nd):
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


EXEMPLAR_CELLS = [("energy_cost_score", 1), ("environmental_score", 1), ("comfort_score", 1),
                  ("practicality_score", 1), ("mavt_score", 2), ("rank", 0)]


def exemplar_changes(base: pd.DataFrame, new: pd.DataFrame, rag_sids: set) -> dict:
    """Exemplar-visible RAG score cells as Example-Guided_LLM_Scoring renders them
    (criteria 1 dp, MAVT 2 dp, rank 0 dp). Rows are aligned by (scenario_id, alternative)."""
    key = ["scenario_id", "alternative"]
    b = base[base["scenario_id"].isin(rag_sids)].set_index(key)
    n = new[new["scenario_id"].isin(rag_sids)].set_index(key)
    cells = changed = 0
    rows_changed, scen_changed = set(), set()
    per_col = {c: 0 for c, _ in EXEMPLAR_CELLS}
    for idx in b.index:
        for c, nd in EXEMPLAR_CELLS:
            cells += 1
            if _fmt(b.loc[idx, c], nd) != _fmt(n.loc[idx, c], nd):
                changed += 1
                per_col[c] += 1
                rows_changed.add(idx)
                scen_changed.add(idx[0])
    return {"cells": cells, "changed": changed, "rows_changed": len(rows_changed),
            "rows": len(b), "scenarios_changed": len(scen_changed),
            "scenarios": len(set(i[0] for i in b.index)), "per_col": per_col}


def cost_percentile_bounds(costs, factor_off=0.976, factor_peak=1.041, rate=0.19) -> dict:
    """5th-95th percentile of the nonzero (active) per-alternative cost, and the HVAC
    Environmental bounds derived from those kWh at the PJM off-peak / peak factors."""
    c = np.asarray([x for x in costs if x > 0], dtype=float)
    p5, p95 = float(np.percentile(c, 5)), float(np.percentile(c, 95))
    kwh5, kwh95 = p5 / rate, p95 / rate
    return {"n_active": int(c.size), "cost_p5": p5, "cost_p95": p95,
            "kwh_p5": kwh5, "kwh_p95": kwh95,
            "env_min": kwh5 * factor_off, "env_max": kwh95 * factor_peak,
            "cost_min_r": round(p5, 2), "cost_max_r": round(p95, 2),
            "env_min_r": round(kwh5 * factor_off, 2), "env_max_r": round(kwh95 * factor_peak, 2)}
