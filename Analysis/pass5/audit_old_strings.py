"""Audit every old -> new "old" string in paper/pass5/PASS5_PROPOSAL.md.

For each old string: find the target file it names, count exact occurrences,
report the actual line number(s) of each occurrence, and compare them with the
line number(s) the proposal states. Also report pairs of old strings whose
matched spans overlap in the same file (candidate combined edits).

Read-only on every file. print() output is ASCII only (Windows cp1252).

Usage: python Analysis/pass5/audit_old_strings.py [--csv OUT.csv]
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "paper" / "pass5" / "PASS5_PROPOSAL.md"

FILES = {
    "main": ROOT / "paper" / "paper_draft_v2.tex",
    "supp": ROOT / "paper" / "supplementary.tex",
    "readme": ROOT / "README.md",
    "req": ROOT / "requirements.txt",
    "bib": ROOT / "paper" / "cas-refs.bib",
    "claude": ROOT / "CLAUDE.md",
    "status": ROOT / "paper" / "PAPER_STATUS.md",
    "hvac": ROOT / "Ground Truth Calculators" / "HVACGroundTruthCalculator.py",
    "shower": ROOT / "Ground Truth Calculators" / "ShowerGroundTruthCalculator.py",
    "appl": ROOT / "Ground Truth Calculators" / "ApplianceGroundTruthCalculator.py",
}

PATH_TO_KEY = [
    ("paper_draft_v2.tex", "main"),
    ("supplementary.tex", "supp"),
    ("README.md", "readme"),
    ("requirements.txt", "req"),
    ("cas-refs.bib", "bib"),
    ("CLAUDE.md", "claude"),
    ("PAPER_STATUS.md", "status"),
    ("HVACGroundTruthCalculator.py", "hvac"),
    ("ShowerGroundTruthCalculator.py", "shower"),
    ("ApplianceGroundTruthCalculator.py", "appl"),
]


# Part A insertion points: (item, file key, stated line, anchor text in the file)
ANCHORS = [
    ("A2.4", "main", 788, "    Fixed default & 70.3 & $0.0$ & 0.614 & $0.000$ \\\\"),
    ("A2.6", "main", 810, "The fixed default succeeds where one criterion decides"),
    ("A2.11", "supp", 1334, "\\subsection{Alternative-Ordering Ablation: Full Statistics}"),
    ("A2-ko", "main", 1071, "which is what Practicality measures."),
    ("A4.4", "main", 1094, "We also assume electric resistance water heating in every Shower scenario."),
    ("A4.5", "supp", 329, "The user prompt includes the other alternatives as reference so that the model doesn't assign the same scores to all alternatives."),
    ("A4.6", "main", 998, "falls below $\\mathcal{A}_{\\text{D}}$ with DeepSeek ($\\tau = 0.167$)."),
    ("A4.8", "supp", 1237, "so no prompt perturbation reverses the architecture ordering for a fixed model."),
    ("A6.2", "supp", 204, "\\subsection{Notation}"),
    ("A7.2", "supp", 980, "Run-to-Run Variance"),
    ("A7.3", "main", 837, "exclude zero for every architecture difference."),
    ("A9.3", "supp", 201, "We report API costs at OpenRouter's published prices as of August 1, 2026."),
    ("A10.1", "main", 726, "The calculator applies weekday summer rates year-round and models no weekend, holiday, or seasonal shift in the peak window."),
    ("A10.2", "supp", 765, "cuts its per-cycle cost by 49--76\\% across these five time-of-use utilities."),
    ("A11-ko", "main", 1101, "would address the PJM specificity noted in Section~\\ref{sec:limitations}."),
]


def asc(s):
    return s.encode("ascii", "replace").decode("ascii")


def load_texts():
    return {k: p.read_text(encoding="utf-8") for k, p in FILES.items()}


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def find_all(text, needle):
    out, start = [], 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1


# ---------------------------------------------------------------- Part A --
PART_A_LOC = re.compile(r"\b(main|S|README)\s+L(\d+)(?:\s*[-–]\s*L?(\d+))?")
PART_A_EXTRA_L = re.compile(r"(?<![A-Za-z])L(\d+)(?:\s*[-–]\s*L?(\d+))?")
KEYMAP_A = {"main": "main", "S": "supp", "README": "readme"}


def parse_locs_a(s, default_key=None):
    """Return (key, set_of_lines) from a Part A heading/bullet fragment."""
    key, lines = default_key, set()
    for m in PART_A_LOC.finditer(s):
        if key is None or key == default_key:
            key = KEYMAP_A[m.group(1)]
        a = int(m.group(2))
        b = int(m.group(3)) if m.group(3) else a
        lines.update(range(a, b + 1))
    for m in PART_A_EXTRA_L.finditer(s):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if b - a < 40:
            lines.update(range(a, b + 1))
    return key, lines


def extract_inline_old(line):
    """Return list of old strings on one Part A line."""
    olds = []
    # form 1: "old: `...`" possibly followed by "-> new:"; A9.1 nests backticks
    for m in re.finditer(r"\bold:\s*`", line):
        start = m.end()
        # the old ends at the backtick before " -> new" / " ->" or at line end
        arrow = line.find("` -> new", start)
        if arrow < 0:
            arrow = line.find("` ->", start)
        if arrow >= 0:
            olds.append(line[start:arrow])
        else:
            end = line.rfind("`")
            if end > start:
                olds.append(line[start:end])
    if olds:
        return olds
    # form 2: "- `X` -> `Y`" (A1.2 row swaps, A2.8, A2.12 README L150)
    m = re.search(r"`([^`]+)`\s*->\s*`", line)
    if m and "new:" not in line[: m.start()]:
        olds.append(m.group(1))
    return olds


def parse_part_a(md_lines, a_start, a_end):
    items = []
    ctx_item, ctx_key, ctx_lines = None, None, set()
    sub_key, sub_lines = None, set()
    i = a_start
    while i < a_end:
        line = md_lines[i]
        h = re.match(r"\*\*(A\d+\.\d+)[^*]*\*\*", line)
        top = re.match(r"^## (A\d+)\.", line)
        if top:
            ctx_item, ctx_key, ctx_lines = top.group(1), None, set()
        if h:
            ctx_item = h.group(1)
            k, ls = parse_locs_a(line)
            ctx_key = k or "main"
            ctx_lines = ls
            if "S1" in line or "S2" in line or ", S," in line or " S L" in line:
                if k is None:
                    ctx_key = "supp"
        # bullet-level location overrides (A3.3 README L144, A5 swaps, knock-ons)
        bullet_key, bullet_lines = None, set()
        if re.match(r"^- ", line):
            sub_key, sub_lines = None, set()
        msub = re.match(r"^- (?:Caption, )?(main|S|README) L(\d+)", line)
        if msub and "old" not in line:
            sub_key, sub_lines = parse_locs_a(line)
        if re.match(r"^\s+- old:", line) and sub_key:
            bullet_key, bullet_lines = sub_key, sub_lines
        mb = re.match(r"\s*-\s*(?:\*\*)?(main|S|README)\s+L(\d+)", line)
        if mb:
            bullet_key, bullet_lines = parse_locs_a(line)
        if re.match(r"^\s*-\s*(?:Main |main )?L\d+", line):
            bullet_key = "main"
            bullet_lines = parse_locs_a(line)[1]
        mb2 = re.match(r"\s*-\s*(L\d+) (old|new):", line)
        if mb2:
            bullet_key = ctx_key
            bullet_lines = {int(mb2.group(1)[1:])}
        # multi-line latex old block: "- old:" then ```latex
        if re.match(r"\s*-\s*old:\s*$", line) and i + 1 < a_end and md_lines[i + 1].startswith("```"):
            j = i + 2
            block = []
            while not md_lines[j].startswith("```"):
                block.append(md_lines[j])
                j += 1
            items.append(dict(item=ctx_item, key=ctx_key, stated=set(ctx_lines),
                              old="\n".join(block), src_line=i + 1))
            i = j + 1
            continue
        if "old" in line or "->" in line:
            for old in extract_inline_old(line):
                if old.strip() in ("", "latex"):
                    continue
                key = bullet_key or ctx_key or "main"
                stated = bullet_lines or ctx_lines
                # knock-on "old `x` -> new `y`" (no colon)
                items.append(dict(item=ctx_item, key=key, stated=set(stated),
                                  old=old, src_line=i + 1))
            m3 = re.search(r"\bold `([^`]+)` -> new `", line)
            if m3 and not re.search(r"\bold:\s*`", line):
                key = bullet_key or ctx_key or "main"
                k2, ls2 = parse_locs_a(line)
                items.append(dict(item=ctx_item, key=k2 or key,
                                  stated=ls2 or set(ctx_lines), old=m3.group(1),
                                  src_line=i + 1))
        i += 1
    # de-duplicate identical (src_line, old)
    seen, out = set(), []
    for it in items:
        sig = (it["src_line"], it["old"])
        if sig not in seen:
            seen.add(sig)
            out.append(it)
    return out


# ---------------------------------------------------------------- Part B --
WHERE_TOKEN = re.compile(
    r"(paper_draft_v2\.tex|supplementary\.tex|README\.md|requirements\.txt|cas-refs\.bib|"
    r"CLAUDE\.md|PAPER_STATUS\.md|HVACGroundTruthCalculator\.py|ShowerGroundTruthCalculator\.py|"
    r"ApplianceGroundTruthCalculator\.py|\bmain|\bsupp|\bREADME|\bbib|HVAC calc|Shower calc|Appliance calc)"
    r"|:(\d+)(?:-(\d+))?"
)
ALIAS = {"main": "main", "supp": "supp", "README": "readme", "bib": "bib",
         "HVAC calc": "hvac", "Shower calc": "shower", "Appliance calc": "appl"}


def key_for_path(p):
    for name, k in PATH_TO_KEY:
        if name in p:
            return k
    return ALIAS.get(p)


def parse_where(s):
    stated = {}
    cur = None
    for m in WHERE_TOKEN.finditer(s):
        if m.group(1):
            cur = key_for_path(m.group(1))
        elif cur is not None:
            a = int(m.group(2))
            b = int(m.group(3)) if m.group(3) else a
            stated.setdefault(cur, set()).update(range(a, b + 1))
    return stated


def parse_part_b(md_lines, b_start, b_end):
    items = []
    ctx_item, where = None, {}
    local = set()
    i = b_start
    while i < b_end:
        line = md_lines[i]
        m = re.match(r"^### (B\d+)\.", line)
        if m:
            ctx_item, where, local = m.group(1), {}, set()
        if line.startswith("- **Where:**"):
            buf = line
            j = i + 1
            while j < b_end and md_lines[j].startswith("  ") and not md_lines[j].lstrip().startswith("- **"):
                buf += " " + md_lines[j].strip()
                j += 1
            where = parse_where(buf)
        mloc = re.match(r"^(HVAC|Shower|Appliance), lines? (\d+)(?:(?:-| and )(\d+))?", line)
        if mloc:
            a = int(mloc.group(2))
            b = int(mloc.group(3)) if mloc.group(3) else a
            local = set(range(a, b + 1)) | {a, b}
        mo = re.match(r"^```old (.+)$", line)
        if mo:
            path = mo.group(1).strip()
            key = key_for_path(path)
            j = i + 1
            block = []
            while not md_lines[j].startswith("```"):
                block.append(md_lines[j])
                j += 1
            stated = set(local) if (local and key in ("hvac", "shower", "appl")) else set(where.get(key, set()))
            items.append(dict(item=ctx_item, key=key, stated=stated,
                              old="\n".join(block), src_line=i + 1))
            i = j + 1
            continue
        i += 1
    return items


def main():
    md = PROPOSAL.read_text(encoding="utf-8")
    md_lines = md.split("\n")
    a_start = next(i for i, l in enumerate(md_lines) if l.startswith("# Pass 5 proposal, Part A"))
    b_start = next(i for i, l in enumerate(md_lines) if l.startswith("# Pass 5 proposal, Part B"))
    b_end = next(i for i, l in enumerate(md_lines) if l.startswith("# Not proposed"))
    texts = load_texts()

    items = parse_part_a(md_lines, a_start, b_start) + parse_part_b(md_lines, b_start, b_end)

    rows, spans = [], []
    n_ok = n_zero = n_multi = n_line = n_dep = 0
    for it in items:
        text = texts.get(it["key"])
        if text is None:
            status, actual = "NO-FILE", []
        else:
            hits = find_all(text, it["old"])
            actual = [line_of(text, h) for h in hits]
            for h in hits:
                spans.append((it["key"], h, h + len(it["old"]), it["item"], it["src_line"]))
            if len(hits) == 0 and md.count(it["old"][:60]) > 1:
                # the old string is another item's new text (a dependent edit)
                status = "AFTER-OTHER-EDIT"
                n_dep += 1
            elif len(hits) == 0:
                status = "NOT-FOUND"
                n_zero += 1
            elif len(hits) > 1:
                status = "MULTI"
                n_multi += 1
            else:
                last = actual[0] + it["old"].count("\n")
                if not it["stated"]:
                    status = "OK-NOLINE"
                    n_ok += 1
                elif any(l in it["stated"] for l in range(actual[0], last + 1)):
                    status = "OK"
                    n_ok += 1
                else:
                    status = "LINE-MISMATCH"
                    n_line += 1
        rows.append(dict(item=it["item"], proposal_line=it["src_line"], file=it["key"],
                         stated=",".join(str(x) for x in sorted(it["stated"])[:6]) +
                         ("..." if len(it["stated"]) > 6 else ""),
                         actual=",".join(str(a) for a in actual), status=status,
                         old=it["old"][:90].replace("\n", " | ")))

    for r in rows:
        if r["status"] not in ("OK",):
            print(asc("%-6s pl%-5s %-7s stated=%-14s actual=%-10s %-13s %s" % (
                r["item"], r["proposal_line"], r["file"], r["stated"], r["actual"],
                r["status"], r["old"])))
    print("TOTAL old strings: %d" % len(rows))
    print("found once at stated line (or no line stated): %d" % n_ok)
    print("line mismatch: %d   not found: %d   multiple: %d   found only in another item's new text: %d"
          % (n_line, n_zero, n_multi, n_dep))

    # overlapping spans in the same file (candidate combined edits)
    print("\nOVERLAPPING OLD SPANS (same file):")
    spans.sort()
    for a in range(len(spans)):
        for b in range(a + 1, len(spans)):
            ka, sa, ea, ia, pa = spans[a]
            kb, sb, eb, ib, pb = spans[b]
            if kb != ka or sb >= ea:
                continue
            if ia == ib and pa == pb:
                continue
            print(asc("  %s: %s (pl%d) overlaps %s (pl%d) at file line %d" % (
                ka, ia, pa, ib, pb, line_of(texts[ka], sb))))

    # different items whose old strings sit on the same physical line (same paragraph)
    print("\nDIFFERENT ITEMS EDITING THE SAME FILE LINE (non-overlapping spans):")
    by_line = {}
    for k, s, e, item, pl in spans:
        text = texts[k]
        for ln in range(line_of(text, s), line_of(text, e) + 1):
            by_line.setdefault((k, ln), set()).add(item)
    for (k, ln), its in sorted(by_line.items()):
        if len(its) > 1:
            print("  %s:%d  %s" % (k, ln, ", ".join(sorted(its))))

    # insertion anchors: text the proposal says to insert before/after
    print("\nINSERTION ANCHORS:")
    for item, k, stated, anchor in ANCHORS:
        hits = find_all(texts[k], anchor)
        lines = [line_of(texts[k], h) for h in hits]
        st = "OK" if len(hits) == 1 and lines[0] == stated else "CHECK"
        print(asc("  %-6s %-6s stated=%-5d actual=%-12s %s  %s" % (
            item, k, stated, ",".join(map(str, lines)), st, anchor[:60])))

    if "--csv" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--csv") + 1])
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("wrote %s" % asc(str(out)))


if __name__ == "__main__":
    main()
