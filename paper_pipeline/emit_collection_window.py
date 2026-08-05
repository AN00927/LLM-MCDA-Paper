#!/usr/bin/env python3
"""
emit_collection_window.py -- recover approximate collection times for the
shipped benchmark runs from the filesystem.

IMPORTANT CAVEAT
----------------
These timestamps are filesystem modification times (`st_mtime`), NOT wall-clock
collection timestamps recorded inside the artifacts. No shipped run output
carries an internal UTC timestamp (see the "Every run must record a UTC
collection timestamp" note in CLAUDE.md); this script reconstructs the closest
available proxy after the fact.

An mtime is therefore an upper bound on when the run finished, and it is only
that if nothing has touched the file since. Copying, moving across
filesystems, restoring from backup, or re-saving a workbook all rewrite mtime
without any data changing. Treat the output as "these files were last written
around here", suitable for establishing that arms of an experiment are roughly
contemporaneous, and NOT as provenance strong enough to rule out provider
drift on its own. New runs should record a real UTC timestamp in the per-run
xlsx and the raw JSONL rather than relying on this.

In this repository the mtimes turned out to be uninformative: every run
artifact carries the same mtime to within a few seconds, which is the
signature of a bulk checkout or copy rather than of the runs themselves. The
script therefore also records, for each artifact, the author date of the most
recent git commit that touched it. That is a stronger proxy here -- the runs
were committed shortly after collection -- though it is still an upper bound
and still external to the artifact.

Outputs
-------
  paper/collection_window.csv          one row per artifact:
      model, architecture, run, artifact, mtime_utc_iso,
      last_commit_utc_iso, last_commit_sha, last_commit_subject
  paper/collection_window_summary.csv  one row per (model, architecture):
      min and max mtime and commit date, artifact count, span in hours

Usage:
    python paper_pipeline/emit_collection_window.py
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_SPECS

PAPER_DIR = PROJECT_ROOT / "paper"
OUT_ROWS = PAPER_DIR / "collection_window.csv"
OUT_SUMMARY = PAPER_DIR / "collection_window_summary.csv"

ARCHITECTURES = [
    "Direct_LLM_Scoring",
    "Example-Guided_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring",
]


def _iso_utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _run_number(path):
    stem = path.stem
    if "_run_" not in stem:
        return None
    tail = stem.split("_run_")[-1]
    return int(tail) if tail.isdigit() else None


def last_commit_index():
    """Map repo-relative path -> (author_date_iso, sha, subject) for its last commit.

    One read-only `git log` walk over the output folders. Read-only: this
    script never writes to the repository.
    """
    folders = [spec["output_folder"] for spec in MODEL_SPECS.values()]
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
    commits = last_commit_index()
    rows = []
    for model_key, spec in MODEL_SPECS.items():
        folder = PROJECT_ROOT / spec["output_folder"]
        if not folder.exists():
            print(f"  [SKIP] {model_key}: {folder} does not exist")
            continue
        for arch in ARCHITECTURES:
            patterns = [
                (f"{arch}_results_run_*.xlsx", "results_xlsx"),
                (f"{arch}_results_diagnostics_run_*.json", "diagnostics_json"),
            ]
            for pattern, kind in patterns:
                for path in sorted(folder.glob(pattern)):
                    run = _run_number(path)
                    if run is None:
                        continue
                    rel = path.relative_to(PROJECT_ROOT).as_posix()
                    cdate, csha, csubj = commits.get(rel, ("", "", ""))
                    rows.append({
                        "model": model_key,
                        "architecture": arch,
                        "run": run,
                        "artifact": kind,
                        "filename": path.name,
                        "mtime_utc_iso": _iso_utc(path.stat().st_mtime),
                        "last_commit_utc_iso": cdate,
                        "last_commit_sha": csha,
                        "last_commit_subject": csubj,
                        "mtime_epoch": path.stat().st_mtime,
                    })

    if not rows:
        print("ERROR: no run artifacts found")
        return

    df = pd.DataFrame(rows).sort_values(
        ["model", "architecture", "run", "artifact"], kind="mergesort"
    ).reset_index(drop=True)

    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    df.drop(columns=["mtime_epoch"]).to_csv(OUT_ROWS, index=False)
    print(f"[OK] wrote {OUT_ROWS} ({len(df)} artifacts)")

    summary = df.groupby(["model", "architecture"]).agg(
        n_artifacts=("filename", "count"),
        n_runs=("run", "nunique"),
        min_mtime_utc_iso=("mtime_epoch", lambda s: _iso_utc(s.min())),
        max_mtime_utc_iso=("mtime_epoch", lambda s: _iso_utc(s.max())),
        span_hours=("mtime_epoch", lambda s: round((s.max() - s.min()) / 3600.0, 2)),
        min_commit_utc_iso=("last_commit_utc_iso", lambda s: min(x for x in s if x) if any(s) else ""),
        max_commit_utc_iso=("last_commit_utc_iso", lambda s: max(x for x in s if x) if any(s) else ""),
    ).reset_index()
    summary.to_csv(OUT_SUMMARY, index=False)
    print(f"[OK] wrote {OUT_SUMMARY} ({len(summary)} rows)")

    print("\nApproximate collection window per (model, architecture) "
          "-- filesystem mtime, not an internal timestamp:")
    print(summary.to_string(index=False))

    print(f"\nOverall span: {_iso_utc(df['mtime_epoch'].min())} "
          f"to {_iso_utc(df['mtime_epoch'].max())}")


if __name__ == "__main__":
    main()
