---
name: pdf-qa
description: QA-check the State Talent Profile PDFs in this repo after any change to ipeds_clean/templates/state_pdf.html, ipeds_clean/state_pdf.py, a data module that feeds the profiles (sevis, external, states_explorer, state_profile), or the profile data itself. Runs the layout, overflow, figure-numbering, NaN, stat-box-vs-table, font and even-page checks, and renders the paired and rail spreads to PNG for a visual look. Use it before every commit or deploy that touches the PDFs, whenever the user asks to check, verify, QA, proof or review the PDFs or profiles, and after rebuilding them with state_pdf, even if the user only says "rebuild" or "does it look right".
---

# PDF QA for the State Talent Profiles

The profiles are built by rendering `ipeds_clean/templates/state_pdf.html` in Chrome, one per state, as a digital
PDF (spreads) and a print PDF (single pages). Layout is fitted in the browser at build time, so a problem in one
state rarely shows in another: a long state name, a missing measure or a small state's thin data can push a
box past its edge. This skill checks the rendered result, not the code.

## Run the checks

```bash
uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py                # six sample states, layout only (~15 s)
uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py --png          # + rebuild their PDFs, fonts, page counts, PNGs
uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py --all          # all 51 states, layout only (~4 min)
uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py CA NY --pdf    # named states, with the PDF checks
```

The sample (CA, TX, WY, DC, VT, RI) spans the largest and smallest states, DC (no state government, unusual
data) and small New England states, which is where layouts break. Use `--all` before a deploy or after a change
to fitting logic; the sample is enough while iterating. The script exits 1 if anything is flagged, and the
docstring at the top of `scripts/pdf_qa.py` says what each check means.

What it catches, and why each matters:
- **Overflow, vertical and sideways.** Paired-spread prose is set in two columns; when it is too long it spills
  into a third column off to the right, which a height check never sees. This happened once and went unnoticed
  until checked by width, so a clean result here means both directions were checked.
- **Stat box vs table.** Every number in a crimson stat box or rail that comes from a measure carries
  `data-m="<measure>"`; the check compares it with that measure's latest value as By the Numbers prints it. A
  mismatch means the box and the table read different sources or months (the SEVIS 2025 count once did).
  When you add a stat built by hand (`{v, l, c}`), add `m:` if it stands for a measure, so it is checked too.
- **Figure numbers** in reading order, rails included (a final pass renumbers `.fig .ft em` and `.prail .fno`).
- **Margins, NaN/undefined, browser errors**, and with `--pdf`: fonts embedded, no Type3, even print page count.

## Look at the pages

Checks pass does not mean the pages read well. After `--png`, open the PNGs in `cache/pdf_qa/<ST>/` (one per
paired or rail spread) and look at a few for at least the largest and smallest sample state. Look for: a stat
box crowding the prose, prose cut to one paragraph, a chart squeezed short, labels colliding, a heading at its
smallest size. These are judgment calls the script cannot make; report them with the sheet number.

## Report

Give the user, in this order: the pass/flag line per state, each flagged issue with the state and what to fix,
then anything you saw in the PNGs. Say plainly when everything passed and which states and checks were run
(sample or all, with or without `--pdf`). The project's RULES.md asks for these checks after every rebuild and
before `python -m ipeds_clean.deploy_pages`; a failing check blocks the deploy.
