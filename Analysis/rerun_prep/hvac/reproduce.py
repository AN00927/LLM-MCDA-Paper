"""Step 1 regression gate: the unmodified calculators reproduce the shipped reference.

Checks, for HVAC and Shower:
  1. the frozen copies in hvac/shipped/ are byte-identical to Ground Truth Calculators/
     (skipped with a note once the new calculators are installed there);
  2. running the frozen copy over the master sheet reproduces Ground Truth/*.xlsx
     cell for cell (all scores, mavt, rank, raw columns; test and RAG scenarios);
  3. every RAG score column in Scenario Files/*Rag*.xlsx equals the matching GT row;
  4. the Shower copy in calc_new/ (comment edits + continuous budget penalty, which no
     Shower alternative reaches) also reproduces its xlsx.

Usage: python Analysis/rerun_prep/hvac/reproduce.py
Exit code 0 only if every check passes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd  # noqa: E402
import common as C  # noqa: E402


def main() -> int:
    ok = True
    for name in ("HVACGroundTruthCalculator.py", "ShowerGroundTruthCalculator.py"):
        same = C.sha256(C.FROZEN_DIR / name) == C.sha256(C.SHIPPED_CALC_DIR / name)
        print(f"[{'PASS' if same else 'NOTE'}] frozen {name} "
              f"{'==' if same else '!='} Ground Truth Calculators/{name}")

    hv = C.load_module(C.FROZEN_DIR / "HVACGroundTruthCalculator.py", "hvac_frozen")
    gt = pd.read_excel(C.HVAC_GT)
    run = C.run_hvac(hv)
    mm = C.compare_frames(gt, run)
    bad = {k: v for k, v in mm.items() if v}
    ok &= not bad
    rag_sids, _ = C.rag_signatures(gt, C.HVAC_RAG, "HVAC")
    print(f"[{'PASS' if not bad else 'FAIL'}] HVAC frozen copy vs ground_truth_hvac.xlsx: "
          f"{len(gt)} rows, {len(gt.columns)} cols, mismatches={bad or 0} "
          f"(test scenarios {105 - len(rag_sids)}, RAG scenarios {len(rag_sids)})")
    rg = C.check_rag_scores(run, C.HVAC_RAG, "HVAC")
    rbad = {k: v for k, v in rg["mismatch"].items() if v}
    ok &= (not rbad) and rg["matched"] == rg["rag_rows"]
    print(f"[{'PASS' if not rbad and rg['matched'] == rg['rag_rows'] else 'FAIL'}] HVAC RAG score "
          f"columns: {rg['matched']}/{rg['rag_rows']} rows matched, mismatches={rbad or 0}")

    for label, path in (("frozen", C.FROZEN_DIR), ("calc_new", C.NEW_DIR)):
        sh = C.load_module(path / "ShowerGroundTruthCalculator.py", f"shower_{label}")
        sgt = pd.read_excel(C.SHOWER_GT)
        srun = C.run_shower(sh)
        smm = {k: v for k, v in C.compare_frames(sgt, srun).items() if v}
        ok &= not smm
        print(f"[{'PASS' if not smm else 'FAIL'}] Shower {label} copy vs ground_truth_shower.xlsx: "
              f"{len(sgt)} rows, mismatches={smm or 0}")
        srg = C.check_rag_scores(srun, C.SHOWER_RAG, "Shower")
        sbad = {k: v for k, v in srg["mismatch"].items() if v}
        ok &= (not sbad) and srg["matched"] == srg["rag_rows"]
        print(f"[{'PASS' if not sbad and srg['matched'] == srg['rag_rows'] else 'FAIL'}] Shower "
              f"{label} RAG score columns: {srg['matched']}/{srg['rag_rows']} matched, "
              f"mismatches={sbad or 0}")

        # Shower bounds: 5th-95th percentiles over the 80 master scenarios (test + RAG
        # pooled), rounded to the shipped precision, must equal the literals in the class.
        if label == "calc_new":
            import numpy as np
            p = lambda s, q: float(np.percentile(s.astype(float), q))
            c5, c95 = p(srun["raw_cost"], 5), p(srun["raw_cost"], 95)
            w5, w95 = p(srun["raw_water_gallons"], 5), p(srun["raw_water_gallons"], 95)
            same = (round(c5, 2), round(c95, 2), round(w5, 1), round(w95, 1)) == (0.14, 1.14, 6.0, 45.0)
            ok &= same
            print(f"[{'PASS' if same else 'FAIL'}] Shower bounds recomputed: cost p5={c5:.4f} "
                  f"p95={c95:.4f} (class 0.14/1.14); water p5={w5:.2f} p95={w95:.2f} (class 6.0/45.0)")

    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
