#!/usr/bin/env python3
"""
emit_collection_window.py -- the collection window of every run artifact, from
the UTC timestamps the runs record, falling back to filesystem times only for
files that carry none.

Sources, in order of preference, per artifact
---------------------------------------------
  diagnostics JSON  `collected_utc_start` / `collected_utc_end` (the rerun's
                    architectures), else `collected_utc` (run start only)
  per-run xlsx      the `collected_utc` column (min and max over its rows)
  raw JSONL         every record's `collected_utc` (min and max); one record
                    per API call, so this is the tightest window
  mtime             filesystem modification time, only for an artifact with no
                    internal timestamp (the pre-rerun shipped runs)

Every row says which source it used (`time_source`). An mtime is NOT a
collection time: copying, restoring or re-saving a file rewrites it without any
data changing, and in this repository the shipped runs' mtimes are all within
seconds of each other (a bulk checkout). For those files the script also
records the author date of the last git commit that touched the artifact (one
read-only `git log`), still only an upper bound.

Covered: each model's main runs (the three architectures), the A_D position-bias
arm (`position_bias/`), the A_H order arms (`hybrid_order_reversal/`), the
listwise A_D arm (`listwise_direct/`), the prompt-ablation cells
(`Output Files <model>/prompt_ablation/cell_*_<model>_run_NN_raw.jsonl`) and the RAG
ablation (`Combined Metrics/rag_ablation_results_raw.jsonl`, one log for
all models, split here by each record's `model` id).

Outputs
-------
  local-only collection_window.csv     one row per artifact:
      model, architecture, run, artifact, filename, start_utc_iso,
      end_utc_iso, time_source, mtime_utc_iso, last_commit_utc_iso,
      last_commit_sha, last_commit_subject
  local-only collection_window_summary.csv one row per (model, architecture):
      earliest start, latest end, span in hours, sources used, and how many
      artifacts fell back to mtime

Usage:
    python scripts/paper_pipeline/emit_collection_window.py [--out-dir DIR]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from common.paths import repository_root
PROJECT_ROOT = repository_root(start=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
IMPORT_ROOT = PROJECT_ROOT
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))

from common.paths import repository_path  # noqa: E402
from common.model_config import MODEL_SPECS, get_model_artifact_subdir

PAPER_DIR = repository_path("Combined Metrics")

ARCHITECTURES = [
    "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring",
]


def _iso_utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value):
    """datetime (UTC) from an ISO string, or None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _run_number(path):
    stem = path.stem
    if stem.endswith("_raw"):
        stem = stem[: -len("_raw")]
    if "_run_" not in stem:
        return None
    tail = stem.split("_run_")[-1]
    return int(tail) if tail.isdigit() else None


def window_from_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        diag = json.load(fh)
    start = _parse_iso(diag.get("collected_utc_start"))
    end = _parse_iso(diag.get("collected_utc_end"))
    if start is not None:
        return start, end or start, ("diagnostics_json:collected_utc_start/_end"
                                     if end is not None else
                                     "diagnostics_json:collected_utc_start")
    start = _parse_iso(diag.get("collected_utc"))
    if start is not None:
        return start, start, "diagnostics_json:collected_utc (start only)"
    return None, None, None


def window_from_xlsx(path):
    try:
        df = pd.read_excel(path)
    except Exception:
        return None, None, None
    if "collected_utc" not in df.columns:
        return None, None, None
    times = [t for t in (_parse_iso(v) for v in df["collected_utc"]) if t is not None]
    if not times:
        return None, None, None
    return min(times), max(times), "xlsx:collected_utc"


def window_from_jsonl(path):
    times = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                t = _parse_iso(json.loads(line).get("collected_utc"))
            except (ValueError, AttributeError):
                continue
            if t is not None:
                times.append(t)
    if not times:
        return None, None, None
    return min(times), max(times), "raw_jsonl:collected_utc"


READERS = {"diagnostics_json": window_from_json, "results_xlsx": window_from_xlsx,
           "raw_jsonl": window_from_jsonl}


def artifact_specs(folder):
    """(architecture label, directory, glob, artifact kind) for one model folder."""
    specs = []
    for arch in ARCHITECTURES:
        specs += [
            (arch, folder, f"{arch}_results_run_*.xlsx", "results_xlsx"),
            (arch, folder, f"{arch}_results_diagnostics_run_*.json", "diagnostics_json"),
            (arch, folder, f"{arch}_results_run_*_raw.jsonl", "raw_jsonl"),
        ]
    pb = folder / "position_bias"
    specs += [
        ("Direct_LLM_Scoring[position_bias_reversed]", pb, "Direct_LLM_Scoring_reversed_run_*.xlsx", "results_xlsx"),
        ("Direct_LLM_Scoring[position_bias_reversed]", pb, "Direct_LLM_Scoring_reversed_run_*_raw.jsonl", "raw_jsonl"),
    ]
    ho = folder / "hybrid_order_reversal"
    for arm in ("reversed", "control"):
        specs += [
            (f"AH_order_{arm}", ho, f"AH_extraction_order_{arm}_run_*.xlsx", "results_xlsx"),
            (f"AH_order_{arm}", ho, f"AH_extraction_order_{arm}_run_*_raw.jsonl", "raw_jsonl"),
        ]
    lw = folder / "listwise_direct"
    specs += [
        ("AD_listwise", lw, "AD_listwise_run_*.xlsx", "results_xlsx"),
        ("AD_listwise", lw, "AD_listwise_run_*_raw.jsonl", "raw_jsonl"),
    ]
    return specs


PROMPT_ABLATION_DIRS = [
    repository_path(get_model_artifact_subdir(mk, "prompt_ablation")) for mk in MODEL_SPECS
]
RAG_ABLATION_LOG = repository_path("Combined Metrics","rag_ablation_results_raw.jsonl")


def rag_log_windows(path=RAG_ABLATION_LOG):
    """{openrouter model id: (first, last) collected_utc} over the RAG
    ablation's shared raw log; {} if it does not exist."""
    times = {}
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            t = _parse_iso(rec.get("collected_utc"))
            if t is not None:
                times.setdefault(rec.get("model"), []).append(t)
    return {m: (min(ts), max(ts)) for m, ts in times.items()}


def _row(model_key, arch, run, kind, path, start, end, source, commits):
    rel = path.relative_to(PROJECT_ROOT).as_posix()
    cdate, csha, csubj = commits.get(rel, ("", "", ""))
    mtime = path.stat().st_mtime
    return {
        "model": model_key, "architecture": arch, "run": run, "artifact": kind,
        "filename": path.name,
        "start_utc_iso": start.isoformat(timespec="seconds"),
        "end_utc_iso": end.isoformat(timespec="seconds"),
        "time_source": source, "mtime_utc_iso": _iso_utc(mtime),
        "last_commit_utc_iso": cdate, "last_commit_sha": csha,
        "last_commit_subject": csubj,
        "_start": start.timestamp(), "_end": end.timestamp(),
    }


def ablation_rows(commits):
    """Rows for the two ablations kept outside the model folders. Only
    recorded timestamps are used: an artifact with none is skipped, never
    dated by its mtime."""
    rows = []
    rag = rag_log_windows()
    for model_key, spec in MODEL_SPECS.items():
        for path in sorted(p for d in PROMPT_ABLATION_DIRS for p in d.glob(f"cell_*_{model_key}_run_*_raw.jsonl")):
            start, end, source = window_from_jsonl(path)
            if start is not None:
                rows.append(_row(model_key, "prompt_ablation:" + path.name.split(f"_{model_key}_run_")[0],
                                 _run_number(path),
                                 "raw_jsonl", path, start, end, source, commits))
        if spec["openrouter_id"] in rag:
            start, end = rag[spec["openrouter_id"]]
            rows.append(_row(model_key, "rag_ablation", 1, "raw_jsonl", RAG_ABLATION_LOG,
                             start, end, "raw_jsonl:collected_utc", commits))
    return rows


def last_commit_index():
    """Map repo-relative path -> (author_date_iso, sha, subject) for its last commit.

    One read-only `git log` walk over the output folders. Read-only: this
    script never writes to the repository.
    """
    folders = [spec["output_folder"] for spec in MODEL_SPECS.values()
               if (PROJECT_ROOT / spec["output_folder"]).exists()]
    if not folders:
        return {}
    cmd = ["git", "log", "--name-only", "--date=iso-strict",
           "--format=@@@|%H|%aI|%s", "--"] + folders
    try:
        out = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True,
                             text=True, check=True, encoding="utf-8",
                             errors="replace").stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  [WARN] git log unavailable ({exc}); commit dates omitted")
        return {}

    index = {}
    sha = date = subject = None
    for line in out.splitlines():
        if line.startswith("@@@|"):
            _, sha, date, subject = line.split("|", 3)
        elif line.strip() and sha is not None:
            index.setdefault(line.strip(), (date, sha[:8], subject))
    return index


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out-dir", default=str(PAPER_DIR),
                    help="Where collection_window*.csv go (default: local-only paper artifacts)")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_rows = out_dir / "collection_window.csv"
    out_summary = out_dir / "collection_window_summary.csv"

    commits = last_commit_index()
    rows = []
    for model_key, spec in MODEL_SPECS.items():
        folder = PROJECT_ROOT / spec["output_folder"]
        if not folder.exists():
            print(f"  [SKIP] {model_key}: {folder} does not exist")
            continue
        for arch, directory, pattern, kind in artifact_specs(folder):
            if not directory.exists():
                continue
            for path in sorted(directory.glob(pattern)):
                if kind == "results_xlsx" and path.stem.endswith("_raw"):
                    continue
                run = _run_number(path)
                if run is None:
                    continue
                start, end, source = READERS[kind](path)
                mtime = path.stat().st_mtime
                if start is None:
                    start = end = datetime.fromtimestamp(mtime, tz=timezone.utc)
                    source = "mtime"
                rel = path.relative_to(PROJECT_ROOT).as_posix()
                cdate, csha, csubj = commits.get(rel, ("", "", ""))
                rows.append({
                    "model": model_key,
                    "architecture": arch,
                    "run": run,
                    "artifact": kind,
                    "filename": path.name,
                    "start_utc_iso": start.isoformat(timespec="seconds"),
                    "end_utc_iso": end.isoformat(timespec="seconds"),
                    "time_source": source,
                    "mtime_utc_iso": _iso_utc(mtime),
                    "last_commit_utc_iso": cdate,
                    "last_commit_sha": csha,
                    "last_commit_subject": csubj,
                    "_start": start.timestamp(),
                    "_end": end.timestamp(),
                })

    rows += ablation_rows(commits)

    if not rows:
        print("ERROR: no run artifacts found")
        return

    df = pd.DataFrame(rows).sort_values(
        ["model", "architecture", "run", "artifact"], kind="mergesort"
    ).reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    df.drop(columns=["_start", "_end"]).to_csv(out_rows, index=False)
    print(f"[OK] wrote {out_rows} ({len(df)} artifacts)")

    summary = df.groupby(["model", "architecture"]).agg(
        n_artifacts=("filename", "count"),
        n_runs=("run", "nunique"),
        start_utc_iso=("_start", lambda s: _iso_utc(s.min())),
        end_utc_iso=("_end", lambda s: _iso_utc(s.max())),
        time_sources=("time_source", lambda s: "; ".join(sorted(set(s)))),
        n_mtime_fallback=("time_source", lambda s: int((s == "mtime").sum())),
        min_commit_utc_iso=("last_commit_utc_iso", lambda s: min(x for x in s if x) if any(s) else ""),
        max_commit_utc_iso=("last_commit_utc_iso", lambda s: max(x for x in s if x) if any(s) else ""),
    ).reset_index()
    bounds = df.groupby(["model", "architecture"]).agg(lo=("_start", "min"), hi=("_end", "max")).reset_index()
    summary = summary.merge(bounds, on=["model", "architecture"])
    summary.insert(summary.columns.get_loc("end_utc_iso") + 1, "span_hours",
                   ((summary.pop("hi") - summary.pop("lo")) / 3600.0).round(2))
    summary.to_csv(out_summary, index=False)
    print(f"[OK] wrote {out_summary} ({len(summary)} rows)")

    print("\nCollection window per (model, architecture); time_sources says whether "
          "it is a recorded UTC timestamp or an mtime fallback:")
    print(summary.drop(columns=["min_commit_utc_iso", "max_commit_utc_iso"]).to_string(index=False))

    internal = df[df["time_source"] != "mtime"]
    n_fallback = int((df["time_source"] == "mtime").sum())
    if len(internal):
        print(f"\nOverall span from recorded timestamps ({len(internal)} artifacts): "
              f"{_iso_utc(internal['_start'].min())} to {_iso_utc(internal['_end'].max())}")
    if n_fallback:
        print(f"{n_fallback} artifact(s) carry no recorded timestamp and use the file mtime "
              f"(an upper bound on when the file was last written, not a collection time).")


if __name__ == "__main__":
    main()
