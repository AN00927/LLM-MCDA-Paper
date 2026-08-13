#!/usr/bin/env python3
"""
map_floats_to_artifacts.py - P0.2 of the EMS revision plan.

The paper uses NO \\input{}: every table is literal LaTeX, hand-pasted after
inspecting a pipeline artifact (see run_paper_pipeline.py:10-15). The repo's own
hand-paste map covers only 4 floats. This builds the complete one.

For each float in both .tex files it records: label, kind, line range, caption
head, how many extracted numbers it contains, and whether any \\ref{} points at
it. The PRODUCER column is filled in by hand in the plan's ledger - this script
establishes the inventory those entries attach to.

Usage:
    python paper_pipeline/map_floats_to_artifacts.py
"""

import csv
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = PROJECT_ROOT / "paper"
OUT_DIR = PROJECT_ROOT / "Analysis"
NUMBERS_CSV = OUT_DIR / "numbers_baseline.csv"

TEX_FILES = [
    ("main", PAPER_DIR / "paper_draft_working.tex"),
    ("supp", PAPER_DIR / "supplementary_material.tex"),
]

BEGIN_RE = re.compile(r"\\begin\{(table|figure)(\*?)\}")
END_RE = re.compile(r"\\end\{(table|figure)\*?\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
CAPTION_RE = re.compile(r"\\caption\{")
REF_RE = re.compile(r"\\(?:ref|autoref|cref|Cref)\{([^}]*)\}")
COMMENT_RE = re.compile(r"(?<!\\)%.*$")


def strip_comment(line):
    return COMMENT_RE.sub("", line)


def balanced_caption(text, start):
    """Extract the caption argument starting at the brace after \\caption."""
    i = text.find("{", start)
    if i < 0:
        return ""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
    return text[i + 1:i + 200]


def scan(kind, path):
    floats, refs = [], Counter()
    if not path.exists():
        return floats, refs

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    open_stack = []

    for idx, raw in enumerate(lines, start=1):
        line = strip_comment(raw)
        for m in REF_RE.finditer(line):
            refs[m.group(1)] += 1

        bm = BEGIN_RE.search(line)
        if bm:
            open_stack.append({
                "file": kind, "kind": bm.group(1) + bm.group(2),
                "start": idx, "label": "", "caption": "",
            })
            continue

        if open_stack:
            cur = open_stack[-1]
            if not cur["label"]:
                lm = LABEL_RE.search(line)
                if lm:
                    cur["label"] = lm.group(1)
            if not cur["caption"] and CAPTION_RE.search(line):
                # caption may span lines; join a window and brace-match
                window = "\n".join(lines[idx - 1: idx + 12])
                cap = balanced_caption(window, CAPTION_RE.search(window).start())
                cap = re.sub(r"\s+", " ", cap).strip()
                cur["caption"] = cap[:180]

        if END_RE.search(line) and open_stack:
            cur = open_stack.pop()
            cur["end"] = idx
            floats.append(cur)

    # Unclosed floats are a LaTeX error worth surfacing.
    for cur in open_stack:
        cur["end"] = -1
        cur["caption"] = "[UNCLOSED FLOAT]" + cur["caption"]
        floats.append(cur)

    return floats, refs


def main():
    OUT_DIR.mkdir(exist_ok=True)

    all_floats, all_refs = [], Counter()
    for kind, path in TEX_FILES:
        f, r = scan(kind, path)
        print(f"{path.name}: {len(f)} floats, {sum(r.values())} refs")
        all_floats.extend(f)
        all_refs.update(r)

    # numbers per float label, from the P0.1 inventory
    nums = Counter()
    if NUMBERS_CSV.exists():
        with NUMBERS_CSV.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["float_label"]:
                    nums[row["float_label"]] += 1
    else:
        print("  WARNING: numbers_baseline.csv missing; run extract_baseline_numbers.py")

    labelled = [f for f in all_floats if f["label"]]
    unlabelled = [f for f in all_floats if not f["label"]]

    rows = []
    for f in sorted(labelled, key=lambda x: (x["file"] != "main", x["start"])):
        rows.append({
            "file": f["file"], "label": f["label"], "kind": f["kind"],
            "start": f["start"], "end": f["end"],
            "n_numbers": nums.get(f["label"], 0),
            "n_refs": all_refs.get(f["label"], 0),
            "caption": f["caption"],
        })

    csv_path = OUT_DIR / "float_artifact_map.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "file", "label", "kind", "start", "end", "n_numbers", "n_refs",
            "producer", "artifact", "caption"])
        w.writeheader()
        for r in rows:
            r.setdefault("producer", "")
            r.setdefault("artifact", "")
            w.writerow(r)

    md = ["# Float -> artifact map (P0.2)", "",
          "Complete inventory of floats in both `.tex` files. The paper uses no",
          "`\\input{}`, so each of these was hand-pasted from a pipeline artifact;",
          "`producer`/`artifact` are filled in the plan ledger.", "",
          f"- Floats with labels: **{len(labelled)}**",
          f"- Floats WITHOUT labels: **{len(unlabelled)}**",
          f"- Distinct labels referenced by `\\ref{{}}`: {len(all_refs)}", ""]

    orphan_floats = [r for r in rows if r["n_refs"] == 0]
    dangling = sorted(set(all_refs) - {f["label"] for f in labelled})

    md += ["## Floats never referenced by `\\ref{}`", ""]
    if orphan_floats:
        md += ["| File | Label | Line |", "|---|---|---|"]
        for r in orphan_floats:
            md.append(f"| {r['file']} | `{r['label']}` | {r['start']} |")
    else:
        md.append("None.")

    md += ["", "## `\\ref{}` targets with no float label in either file", "",
           "*(May legitimately point at sections, equations, or appendices.)*", ""]
    md.append(", ".join(f"`{d}`" for d in dangling) if dangling else "None.")

    md += ["", "## Full inventory", "",
           "| File | Label | Kind | Lines | Numbers | Refs | Caption |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        cap = r["caption"][:90].replace("|", "\\|")
        md.append(f"| {r['file']} | `{r['label']}` | {r['kind']} "
                  f"| {r['start']}-{r['end']} | {r['n_numbers']} | {r['n_refs']} | {cap} |")

    if unlabelled:
        md += ["", "## Unlabelled floats (cannot be cross-referenced)", "",
               "| File | Kind | Lines |", "|---|---|---|"]
        for f in sorted(unlabelled, key=lambda x: (x["file"] != "main", x["start"])):
            md.append(f"| {f['file']} | {f['kind']} | {f['start']}-{f['end']} |")

    md_path = OUT_DIR / "float_artifact_map.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("")
    print(f"  Labelled floats:   {len(labelled)}")
    print(f"  Unlabelled floats: {len(unlabelled)}")
    print(f"  Never referenced:  {len(orphan_floats)}")
    print(f"  Dangling refs:     {len(dangling)}")
    print(f"  Wrote {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"  Wrote {md_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
