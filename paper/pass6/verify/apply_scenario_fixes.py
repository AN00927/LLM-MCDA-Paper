#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apply the typo/grammar/cell-type fixes staged in scenario_fixes.json to the
THREE MASTER scenario workbooks (Scenario Files/HVACScenarios.xlsx,
ApplianceScenarios.xlsx, ShowerScenarios.xlsx).

Safety:
  - Default mode is --dry-run: prints what WOULD change, writes nothing.
  - --apply actually writes. A timestamped backup of every master file
    touched is written to Scenario Files/Backups/ BEFORE any cell is
    modified (backup happens even in dry-run's "would do" preview, but the
    file copy itself is only made under --apply).
  - Before writing any cell, the CURRENT value is asserted to equal the
    fix's "old" value; a mismatch aborts that fix (does not touch the
    cell) and is reported, so a fix that is stale (someone already edited
    the cell, or two staged fixes touch the same cell) never silently
    clobbers something else.
  - Each cell's number_format is preserved exactly as it was before the
    write (Text "@" stays "@", General stays General, etc.) -- this script
    only ever changes .value, never .number_format, except that a "type"
    fix converting a text cell to a numeric Python type keeps whatever
    number_format the cell already had (per-cell, not reformatted to "0").
  - Rows whose kind == "other" are SKIPPED unless --include-other is passed
    (these are question-vs-field contradictions flagged for author review,
    not mechanical typo/type corrections).

Usage:
    python apply_scenario_fixes.py                # dry-run (default)
    python apply_scenario_fixes.py --dry-run
    python apply_scenario_fixes.py --apply
    python apply_scenario_fixes.py --apply --include-other
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FIXES_JSON = os.path.join(HERE, "scenario_fixes.json")
BACKUP_DIR = os.path.join(REPO_ROOT, "Scenario Files", "Backups")


def load_fixes():
    with open(FIXES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_path(rel_file):
    """rel_file is like 'Scenario Files/HVACScenarios.xlsx' (repo-relative)."""
    return os.path.join(REPO_ROOT, *rel_file.split("/"))


def values_equal(cell_value, expected):
    """Loose equality: numeric-string vs number, str vs str, etc.

    A fix's 'old' in scenario_fixes.json may be a Python str/int/float. We
    compare the cell's CURRENT value against it, allowing '80' == 80 and
    3 == 3.0 style numeric-string/numeric equivalence, but never allowing a
    silent semantic change (e.g. '80' matching 81 is still a mismatch).
    """
    if cell_value == expected:
        return True
    # numeric-string vs number (e.g. cell is '80', fix expects int 80 as
    # the OLD value would never happen in our fixes, but guard anyway)
    try:
        return float(cell_value) == float(expected)
    except (TypeError, ValueError):
        return False


def backup_file(path, do_copy):
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem, ext = os.path.splitext(os.path.basename(path))
    dest = os.path.join(BACKUP_DIR, f"{stem}_BACKUP_{ts}{ext}")
    if do_copy:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        shutil.copy2(path, dest)
        if not os.path.exists(dest) or os.path.getsize(dest) == 0:
            raise RuntimeError(f"Backup failed or empty for {path} -> aborting")
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Actually write changes (default is dry-run).")
    ap.add_argument("--dry-run", action="store_true", help="Explicit dry-run (default behavior; kept for clarity).")
    ap.add_argument("--include-other", action="store_true",
                     help="Also apply kind=='other' rows (question-vs-field contradictions). "
                          "Off by default -- those need author sign-off on which side to change.")
    args = ap.parse_args()

    do_apply = args.apply and not args.dry_run
    mode = "APPLY" if do_apply else "DRY-RUN"

    fixes = load_fixes()
    print(f"[mode] {mode}  ({len(fixes)} staged fixes loaded from {FIXES_JSON})")

    by_file = {}
    for fx in fixes:
        by_file.setdefault(fx["file"], []).append(fx)

    total_applied = 0
    total_skipped_other = 0
    total_mismatch = 0
    total_would_apply = 0

    for rel_file, file_fixes in by_file.items():
        abs_path = resolve_path(rel_file)
        if not os.path.exists(abs_path):
            print(f"[ERROR] master file not found, skipping all its fixes: {abs_path}")
            continue

        print(f"\n=== {rel_file}  ({len(file_fixes)} staged fixes) ===")

        wb = openpyxl.load_workbook(abs_path)
        sheet_name = file_fixes[0]["sheet"]
        ws = wb[sheet_name]
        hdr = [c.value for c in ws[1]]
        try:
            col_idx = {h: i + 1 for i, h in enumerate(hdr)}
        except TypeError:
            print(f"[ERROR] could not read header row for {rel_file}")
            continue

        file_needs_backup = False
        actions = []  # (fx, status, detail)

        for fx in file_fixes:
            kind = fx.get("kind")
            if kind == "other" and not args.include_other:
                total_skipped_other += 1
                actions.append((fx, "SKIP(other)", "kind=='other'; pass --include-other to apply"))
                continue

            col = fx["column_header"]
            r0 = fx["row_index_0based_data"]
            excel_row = r0 + 2  # header is row 1, data starts row 2
            if col not in col_idx:
                total_mismatch += 1
                actions.append((fx, "MISMATCH", f"column '{col}' not found in {rel_file} header"))
                continue
            cell = ws.cell(excel_row, col_idx[col])
            current = cell.value
            expected_old = fx["old"]

            if not values_equal(current, expected_old):
                total_mismatch += 1
                actions.append((fx, "MISMATCH",
                                 f"current value {current!r} != expected old {expected_old!r} "
                                 f"(row {r0}, col {col}) -- fix NOT applied"))
                continue

            new_val = fx["new"]
            preserved_fmt = cell.number_format

            if do_apply:
                file_needs_backup = True
                actions.append((fx, "WILL_APPLY", f"row {r0} {col}: {current!r} -> {new_val!r} (fmt kept: {preserved_fmt!r})"))
            else:
                total_would_apply += 1
                actions.append((fx, "WOULD_APPLY", f"row {r0} {col}: {current!r} -> {new_val!r} (fmt kept: {preserved_fmt!r})"))

        # backup + write pass (only in --apply mode, only if at least one real change)
        if do_apply and file_needs_backup:
            dest = backup_file(abs_path, do_copy=True)
            print(f"  [backup] {dest}")
            for fx, status, detail in actions:
                if status != "WILL_APPLY":
                    continue
                col = fx["column_header"]
                r0 = fx["row_index_0based_data"]
                excel_row = r0 + 2
                cell = ws.cell(excel_row, col_idx[col])
                cell.value = fx["new"]  # number_format left untouched -> preserved
                total_applied += 1
            wb.save(abs_path)
            print(f"  [saved] {abs_path}")
        elif do_apply:
            print("  [no changes to apply in this file]")

        for fx, status, detail in actions:
            print(f"  [{status:12}] #{fx.get('source_md_id','?'):>3} {detail}")

    print("\n==================== SUMMARY ====================")
    print(f"  mode:                 {mode}")
    print(f"  total staged fixes:   {len(fixes)}")
    print(f"  skipped (kind=other): {total_skipped_other}  (use --include-other to include)")
    print(f"  mismatched (aborted): {total_mismatch}")
    if do_apply:
        print(f"  applied:              {total_applied}")
    else:
        print(f"  would apply:          {total_would_apply}")
        print("  (nothing written -- pass --apply to actually modify the master workbooks)")


if __name__ == "__main__":
    sys.exit(main())
