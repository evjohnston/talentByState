# Working rules for this project

State talent-pipeline data for state policymakers: a Python/pandas pipeline (`ipeds_clean/`) that turns the
inputs in `sources/` into CSVs in `data/` and the State Talent Sheet, web profiles and PDFs in `data/states/`.
README.md documents every source; read the relevant section before changing a module.

## Data integrity

- **`sources/` is read-only.** Never edit, overwrite or delete an input file. Files may only be *moved* (for
  example into `sources/_duplicates_to_delete/`), and every move is logged in `sources/new_data_moves.csv`
  (action, from, to). The user deletes files; agents do not.
- **Check the inputs before a rebuild**: `python -m ipeds_clean.manifest` compares `sources/`,
  `reference/digest/` and `reference/survey_forms/` with `manifests/sources_manifest.csv` (size and MD5).
  After adding or moving inputs on purpose, run `python -m ipeds_clean.manifest --update` and commit the manifest.
- **`data/` and `cache/` are rebuilt by code.** Fix the module, not the output file.
- **Commit the PDF profiles with every commit.** `data/states/profiles/pdf/*.pdf` is the one tracked part of
  `data/` (the zips are not); rebuild the PDFs first when a change affects them, so each commit carries current PDFs.
- Corrections to published numbers (for example a misprint) go in the module, with the printed value, the
  corrected value and the reason in the output's note column and the docstring.

## Editing files

- **Use exact, unique-match edits** (the Edit tool) for code and docs. Do not rewrite or splice files with
  Python or sed replacements anchored on text that may appear more than once; check that an anchor is unique
  before any scripted change.
- **One writer per shared file.** Parallel agents must not edit README.md, `ipeds_clean/external.py`,
  `ipeds_clean/states_explorer.py` or the templates at the same time. A subagent puts proposed README text in
  its report; the main session applies it.
- **Commit before and after each batch of work** (`git add -A && git commit`), so any bad edit can be undone with
  git. The pre-commit hook (`.githooks/pre-commit`) blocks commits that drop README sections or many lines,
  stage `.env`, or add files over 50 MB.
- Commit messages describe the change; no tool or assistant attribution lines.

## Finding your way

- **Start from the knowledge graph** in `graphify-out/` (built by graphify; not committed). `GRAPH_REPORT.md`
  lists the communities (one per source module, template or doc topic), the most connected code and the
  cross-file links; `graph.html` is the clickable map. Ask it before grepping:
  `graphify query "how does the PDF fit a figure to 65% of the page?"`, `graphify explain "full_panel"`,
  `graphify path "external.py" "state_pdf.html"`.
- **Keep it current**: after code changes run `graphify update .` (code only, free, keeps community names).
  After README, DESIGN or template changes, run `/graphify . --update` in Claude Code to re-read the changed docs.
  `.graphifyignore` keeps `sources/`, `data/`, `cache/`, `reference/`, `archive/` and the PDFs out of the graph.
- `archive/` holds retired code (old templates, the spread mockups). Nothing imports it; don't build on it.

## Secrets

API keys live in `.env` (`CENSUS_API_KEY`, `COLLEGE_SCORECARD_API_KEY`), which git ignores. Read them in code;
never print, log or commit their values.

## Outputs

- Preview the HTML locally (`cd data/states && python -m http.server 8765`). The only public copy is the GitHub
  Pages site (https://www.emersonjohnston.org/talentByState/), published with `python -m ipeds_clean.deploy_pages`
  after the checks below pass; publish nowhere else.
- Every figure carries its own source line ("Data from ...").
- After a rebuild, check: no browser errors, no NaN/undefined text, all PDF fonts embedded, and even page counts
  for print PDFs.
