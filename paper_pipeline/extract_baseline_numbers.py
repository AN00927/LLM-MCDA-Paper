#!/usr/bin/env python3
"""
extract_baseline_numbers.py - P0.1 baseline snapshot for the EMS revision.

Scans paper_draft_working.tex and supplementary_material.tex for every numeric
claim, tags each with its file, line, enclosing section, and enclosing float
label, and writes a reproducible baseline to Analysis/.

This is the diff target for P7.2: after the revision, re-run and compare, so
every number that moved is explained by a ledger entry and every number that did
not move is confirmed unaffected.

The paper uses NO \\input{} - all tables are literal LaTeX (see
run_paper_pipeline.py) - so this file scan is the only complete inventory of
printed numbers that exists.

Usage:
    python paper_pipeline/extract_baseline_numbers.py
    python paper_pipeline/extract_baseline_numbers.py --tag post_revision
"""

import argparse
import csv
import re
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = PROJECT_ROOT / "paper"
OUT_DIR = PROJECT_ROOT / "Analysis"

TEX_FILES = [
    ("main", PAPER_DIR / "paper_draft_working.tex"),
    ("supp", PAPER_DIR / "supplementary_material.tex"),
]

# Numeric patterns worth tracking. Order matters: more specific first, and a
# span already claimed by an earlier pattern is not re-matched.
PATTERNS = OrderedDict([
    # [0.165, 0.186] or [-0.172, 0.175]
    ("ci", re.compile(r"\[\s*-?\d*\.\d+\s*,\s*-?\d*\.\d+\s*\]")),
    # p = 0.0092, p_Holm = 0.0448, p < 0.001, 8.83e-17
    ("pvalue", re.compile(r"p[_\{\}A-Za-z]*\s*(?:=|<|>|\\leq|\\geq|\\le|\\ge)\s*-?\d*\.?\d+(?:e-?\d+)?",
                          re.IGNORECASE)),
    # 0.880--0.923, 89.7--93.1, 5th--95th
    ("range", re.compile(r"-?\d+\.?\d*\s*-{2,3}\s*-?\d+\.?\d*")),
    # 91.6%, 33.4\%
    ("percent", re.compile(r"-?\d+\.?\d*\s*\\?%")),
    # scientific notation not already caught
    ("scientific", re.compile(r"\b\d+\.?\d*e-?\d+\b")),
    # bare decimals: 0.897, 1.041, -0.147
    ("decimal", re.compile(r"(?<![\w.])-?\d+\.\d+(?![\w.])")),
    # bare integers >= 2 digits (skip 0/1 and single digits: mostly LaTeX args)
    ("integer", re.compile(r"(?<![\w.\-])\d{2,}(?![\w.])")),
])

SECTION_RE = re.compile(r"\\(sub)*section\*?\{([^}]*)\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
FLOAT_BEGIN_RE = re.compile(r"\\begin\{(table|figure|threeparttable)\*?\}")
FLOAT_END_RE = re.compile(r"\\end\{(table|figure)\*?\}")
COMMENT_RE = re.compile(r"(?<!\\)%.*$")

# Lines that are pure LaTeX plumbing - their numbers are layout, not claims.
PLUMBING_RE = re.compile(
    r"\\(usepackage|documentclass|geometry|setlength|renewcommand|newcommand"
    r"|includegraphics|vspace|hspace|arraystretch|columnwidth|textwidth"
    r"|floatpagefraction|textfraction|topfraction|bottomfraction|cline)"
)


def strip_comment(line: str) -> str:
    return COMMENT_RE.sub("", line)


def scan_file(kind: str, path: Path):
    """Yield one record per numeric claim found."""
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping")
        return

    section = ""
    subsection = ""
    float_label = ""
    float_depth = 0
    pending_float = False

    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw)
        if not line.strip():
            continue

        m = SECTION_RE.search(line)
        if m:
            if m.group(1):
                subsection = m.group(2)
            else:
                section = m.group(2)
                subsection = ""

        if FLOAT_BEGIN_RE.search(line):
            float_depth += 1
            pending_float = True
        if pending_float:
            lm = LABEL_RE.search(line)
            if lm:
                float_label = lm.group(1)
                pending_float = False
        if FLOAT_END_RE.search(line):
            float_depth = max(0, float_depth - 1)
            if float_depth == 0:
                float_label = ""
                pending_float = False

        if PLUMBING_RE.search(line):
            continue

        claimed = []  # (start, end) spans already consumed

        def overlaps(a, b):
            return any(not (b <= s or a >= e) for s, e in claimed)

        for kind_name, pat in PATTERNS.items():
            for match in pat.finditer(line):
                s, e = match.span()
                if overlaps(s, e):
                    continue
                claimed.append((s, e))
                ctx = line.strip()
                if len(ctx) > 200:
                    lo = max(0, s - 90)
                    hi = min(len(line), e + 90)
                    ctx = ("..." if lo > 0 else "") + line[lo:hi].strip() + \
                          ("..." if hi < len(line) else "")
                yield {
                    "file": kind,
                    "line": lineno,
                    "type": kind_name,
                    "value": match.group(0).strip(),
                    "section": section,
                    "subsection": subsection,
                    "float_label": float_label,
                    "in_float": "yes" if float_depth > 0 else "no",
                    "context": ctx,
                }


def main():
    parser = argparse.ArgumentParser(
        description="Extract every printed number from the paper .tex files.")
    parser.add_argument("--tag", default="baseline",
                        help="Label for the output files (default: baseline)")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records = []
    for kind, path in TEX_FILES:
        print(f"Scanning {path.name} ...")
        found = list(scan_file(kind, path))
        print(f"  {len(found)} numeric claims")
        records.extend(found)

    csv_path = OUT_DIR / f"numbers_{args.tag}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "file", "line", "type", "value", "section", "subsection",
            "float_label", "in_float", "context"])
        writer.writeheader()
        writer.writerows(records)

    by_type = Counter(r["type"] for r in records)
    by_file = Counter(r["file"] for r in records)
    by_float = Counter(r["float_label"] for r in records if r["float_label"])
    in_float = sum(1 for r in records if r["in_float"] == "yes")

    md = [
        f"# Printed-number inventory ({args.tag})",
        "",
        f"Generated {stamp} by `paper_pipeline/extract_baseline_numbers.py`.",
        "",
        "Diff target for P7.2. The paper uses no `\\input{}` - every table is",
        "literal LaTeX - so this is the only complete inventory of printed",
        "numbers that exists.",
        "",
        f"- **Total numeric claims:** {len(records)}",
        f"- **In floats:** {in_float}  |  **In prose:** {len(records) - in_float}",
        "",
        "## By file",
        "",
        "| File | Claims |",
        "|---|---|",
    ]
    for k, v in by_file.most_common():
        md.append(f"| {k} | {v} |")

    md += ["", "## By type", "", "| Type | Claims |", "|---|---|"]
    for k, v in by_type.most_common():
        md.append(f"| {k} | {v} |")

    md += ["", "## By float (top 30)", "", "| Label | Claims |", "|---|---|"]
    for k, v in by_float.most_common(30):
        md.append(f"| `{k}` | {v} |")

    md += ["", "## Floats with no numbers (check: orphaned or image-only)", ""]
    md.append("See the CSV; floats absent from the table above contain no")
    md.append("extracted numerics.")
    md.append("")

    md_path = OUT_DIR / f"numbers_{args.tag}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    print("")
    print(f"  Total numeric claims: {len(records)}")
    print(f"  In floats: {in_float}   In prose: {len(records) - in_float}")
    print(f"  Wrote {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"  Wrote {md_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
