# S1 apply log

Applied against the current `paper/paper_draft_v2.tex`, `paper/supplementary.tex`,
`paper/cas-refs.bib`, `README.md`, `requirements.txt`. Most S1 items had already been
applied by the earlier, stopped S1 agent; this pass verified each one (old string
absent / new string present) and applied the remainder. No git commands were run.

`Analysis/pass5/audit_old_strings.py` is written against `paper/pass5/PASS5_PROPOSAL.md`'s
own markup and its file set does not include `requirements.txt`; it was read but not run,
since it would not parse `PASS6_PROPOSAL.md`'s per-item blocks correctly. Verification was
done by direct `grep`/`Read` of the current files against each item's quoted old/new text.

| Item | Status | File:line after edit | Old -> new (short) |
|---|---|---|---|
| A3.1 | already applied | paper_draft_v2.tex:1058 | GPM "multiplies against duration" -> "proportional to GPM times duration" mechanism clause |
| A3.3 (README L144) | applied now | README.md:145 | "multiplies each alternative's own duration and so does not cancel" -> "rescales every duration's cost and water use by the same factor..." |
| A3.3 (README L149) | applied now | README.md:150 | "multiplies against each alternative's own duration..." -> "scales every duration's cost and water use by one factor... (0.23-0.27 per run)" |
| A7.1 | already applied | paper_draft_v2.tex:404 | dropped trailing "...so averaging several scoring runs might likewise improve MCDA scores." |
| A8.1 | already applied | paper_draft_v2.tex:320 | "only on calculations with a single correct value" -> "tasks whose correct answer does not depend on anyone's preferences..." with 6 citations |
| A8.2 (optional) | already applied | paper_draft_v2.tex:408 | tool-augmentation examples sentence added |
| A8.3 | already applied | paper_draft_v2.tex:476 | added Jakeman/Bennett sentence |
| A8.4 (BibTeX) | already applied | cas-refs.bib:768-855 | 8 new entries (gao2023pal ... bennett2013characterising) present, no duplicate keys |
| A11.1 | already applied | paper_draft_v2.tex:615 | HVAC/Shower cost-emissions co-movement mechanism rewritten |
| A11.3 | already applied | paper_draft_v2.tex:1095 | "because PJM's marginal emissions intensity..." -> "because the three alternatives...share one time of use..." |
| B12 | already applied | paper_draft_v2.tex:524 | "Indoor Temp (alt.)" col changed --- -> A |
| B13 | already applied | paper_draft_v2.tex:496 | withheld-parameter list expanded to 10 fields; cross-checked against `HIDDEN_PARAMS` in `run_hybrid_ablation_experiments.py` (HVAC: r_value/seer/hvac_age/occupancy_context; Appliance: kwh_per_cycle/appliance/baseline_time; Shower: gpm/tank_size/water_heater_temp) — matches exactly |
| B14 | already applied | paper_draft_v2.tex:519,522,575 | House Age row -> ---; new HVAC Age row added; footnote b corrected |
| B15 | already applied | paper_draft_v2.tex:741 | states k=1 explicitly, notes control retrieves three |
| B16 | already applied | paper_draft_v2.tex:1049 | "comes close on two of the three" -> "matches or beats...for two of the four models on two of the three decision types" |
| B18 | already applied | paper_draft_v2.tex:322-328,838 | RQ1/RQ2 -> single Proposition + RQ |
| B19 | already applied | paper_draft_v2.tex:1084 | "argue that such independent agreement is evidence" -> "read the convergence of several research groups on clinical calculation as evidence" |
| B20 | already applied | paper_draft_v2.tex:1078 | "Where that literature predicts compressed scores," clause deleted |
| B21 | already applied | paper_draft_v2.tex:607 | "Cost is also the criterion households estimate worst" -> "Households also misjudge the energy use that drives cost" |
| B22 | already applied | paper_draft_v2.tex:369 | "by representing them as fuzzy numbers...\cite{zadeh1965}" -> "with fuzzy sets \cite{zadeh1965} rather than..." |
| B23 | already applied | paper_draft_v2.tex:1070 | "must perform in a single forward pass" -> "must perform within one response, with at most a low-effort reasoning trace" |
| B25 | applied now (1 remaining location) | paper_draft_v2.tex:583 | "...\cite{merec2021} in Supplementary Material S2..." -> "...in Table S2.2..." (all other 25 pointer locations already resolved to specific table/figure numbers or correctly left as "keep" text-section pointers, verified individually) |
| B42 | already applied | cas-refs.bib:214 | paetz2012 author list corrected |
| B50 | already applied | paper_draft_v2.tex:621 | "give their full derivations in S1" -> "give their monthly-cost conversions, rate tables and parameter bands in S1" |
| B57 | already applied | supplementary.tex:1343 | dangling "per the main text's timestamp convention" phrase removed |
| B58 | already applied | supplementary.tex:142 | alpha-sweep `horizontal sep=1.6cm` -> `1.5cm` |
| B59 | already applied | supplementary.tex:656 | `\texorpdfstring{...}{A_H}` -> `{A\_H}` |
| B61 | already applied | supplementary.tex:176,202,974 | `xurl` added; model IDs and RAG-ablation path use `\nolinkurl{...}` |
| B62 | skipped: excluded by task instructions | paper_draft_v2.tex:22-23,30-31,349 | co-author TODOs / `todonotes` package left in place (handoff Section 7: strip only before submission) |
| B64 | already applied | paper_draft_v2.tex:346 | PA emissions figure caption now cites `padep_ghg2026`; entry present in cas-refs.bib |
| B65 | skipped: no concrete edit given | cas-refs.bib | item lists 14 uncited entries with "delete for tidiness, or leave them" and no old/new string; left as-is |
| B66 | already applied | cas-refs.bib:442,461 | `pages` added to lewis2020 and wei2022cot |
| B67 | skipped: no concrete edit given | paper_draft_v2.tex:87,242 | item offers "delete both `\newcommand` blocks, or leave them" with no old/new string and explicitly notes output is unchanged either way; left as-is |
| B68 | applied now | README.md:3-4 | "**Author:** Ahaan Nigam / **Institution:**... / **Collaborator:** River Huang..." -> "**Authors:** Ahaan Nigam; River Huang (Paul Scherrer Institut, Switzerland)" + Institution line kept; "## Citation / Collaborator" heading was already "## Citation" |
| B69 | already applied | README.md:34 | `git clone <repository-url>` -> real GitHub URL |
| B73 | already applied | README.md:444,450 | "Three ablation suites"/"All three" -> "Four"/"All four"; CLAUDE.md pointer dropped |
| B74 | applied now | README.md:11,13 | old single-question sentence -> Proposition + Research question, copying the paper's post-B18 wording (main text L322-328) |
| B75 | applied now | requirements.txt:2,13-14 | added `matplotlib==3.11.0`; added `torch==2.11.0` (note: this sandbox's `.venv` currently has torch 2.14.0 installed and no matplotlib package at all — the proposal's versions were taken from the author's machine; applied as specified per the proposal rather than improvised, flagging the discrepancy here) |
| B78 | skipped: file not found | paper/PAPER_STATUS.md | file does not exist in this checkout (`find`/`ls paper` confirm no `PAPER_STATUS.md`); nothing to edit |

## Compile check

`pdflatex` is not installed in this environment (`pdflatex: command not found`), so no
baseline or post-edit diagnostic compile could be run, for either `paper_draft_v2.tex` or
`supplementary.tex`. No build artifacts were created, so none needed removal. Per
`CLAUDE.md`, the Overleaf-compiled PDF is the source of truth regardless; the author should
compile in Overleaf to confirm no new undefined references/citations.

## Summary

- Applied now: 5 (A3.3 — two locations in README, one item; B25; B68; B74; B75)
- Already applied (verified, no change made): 29
- Skipped: 4 (B62 — excluded by task instructions; B65, B67 — no concrete old/new string given, informational/optional only; B78 — target file does not exist)
- Old string not found (distinct from "skipped: no edit given"): none
- Total S1 items covered: 38
