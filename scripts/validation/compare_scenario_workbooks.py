#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cell-by-cell comparison of the four derived scenario files in two directories
(TestScenarios.xlsx and the three RAG sheets). Used as the reproduction gate for
scripts/collection/scenarios/build_scenario_workbooks.py and to diff the Phase I dry run.

For every sheet it compares the sheet names, the used range, and for every cell
in the union of both ranges: the value, the Python type of the value, the
number_format and the openpyxl data_type. Every differing cell is printed.

Usage:
    python compare_scenario_workbooks.py DIR_A DIR_B [--csv OUT.csv]
Exit code 0 = identical, 1 = differences found.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import openpyxl

# Make the checkout's src layout importable when this script is run directly.
for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "src" / "llm_mcda").is_dir():
        sys.path.insert(0, str(_candidate / "src"))
        break
else:
    raise RuntimeError("Cannot locate the repository src/llm_mcda package")

from llm_mcda.common.paths import (
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_path,
)

PROJECT_ROOT = repository_root(start=__file__)

FILES = ["TestScenarios.xlsx", "HVACRagScenarios.xlsx",
         "ApplianceRAGScenarios.xlsx", "ShowerRAGScenarios.xlsx"]


def cell_sig(c):
    return (c.value, type(c.value).__name__, c.number_format, c.data_type)


def compare(dir_a, dir_b):
    """Returns list of dicts, one per difference."""
    diffs = []
    for f in FILES:
        wa = openpyxl.load_workbook(os.path.join(dir_a, f))
        wb = openpyxl.load_workbook(os.path.join(dir_b, f))
        if wa.sheetnames != wb.sheetnames:
            diffs.append({"file": f, "cell": "-", "header": "-", "what": "sheetnames",
                          "a": wa.sheetnames, "b": wb.sheetnames})
        a, b = wa.worksheets[0], wb.worksheets[0]
        if (a.max_row, a.max_column) != (b.max_row, b.max_column):
            diffs.append({"file": f, "cell": "-", "header": "-", "what": "dimensions",
                          "a": a.dimensions, "b": b.dimensions})
        hdr = {c.column: c.value for c in a[1]}
        for r in range(1, max(a.max_row, b.max_row) + 1):
            for col in range(1, max(a.max_column, b.max_column) + 1):
                ca, cb = a.cell(r, col), b.cell(r, col)
                sa, sb = cell_sig(ca), cell_sig(cb)
                if sa != sb:
                    what = [n for n, x, y in zip(("value", "type", "number_format", "data_type"),
                                                 sa, sb) if x != y]
                    diffs.append({"file": f, "cell": ca.coordinate, "header": hdr.get(col),
                                  "what": "+".join(what), "a": sa, "b": sb})
    return diffs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dir_a")
    ap.add_argument("dir_b")
    ap.add_argument("--csv", default=None, help="also write the differences to this CSV")
    args = ap.parse_args(argv)
    if args.csv:
        try:
            args.csv = str(require_safe_output_path(
                args.csv, option="--csv", root=PROJECT_ROOT
            ))
        except UnsafeOutputPathError as exc:
            ap.error(str(exc))
    diffs = compare(args.dir_a, args.dir_b)
    per_file = {f: sum(1 for d in diffs if d["file"] == f) for f in FILES}
    for f in FILES:
        print(f"{f:28s} {per_file[f]:4d} differing cell(s)")
    for d in diffs:
        print(f"  {d['file']} {d['cell']} [{d['header']}] {d['what']}: "
              f"{ascii(d['a'])} -> {ascii(d['b'])}")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["file", "cell", "header", "what", "a", "b"])
            w.writeheader()
            w.writerows(diffs)
    print("IDENTICAL" if not diffs else f"DIFFERENT ({len(diffs)} cell(s))")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
