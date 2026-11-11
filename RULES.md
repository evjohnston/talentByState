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

## Secrets

API keys live in `.env` (`CENSUS_API_KEY`, `COLLEGE_SCORECARD_API_KEY`), which git ignores. Read them in code;
never print, log or commit their values.

## Outputs

- Serve the HTML locally (`cd data/states && python -m http.server 8765`); never publish it elsewhere.
- Every figure carries its own source line ("Data from ...").
- After a rebuild, check: no browser errors, no NaN/undefined text, all PDF fonts embedded, and even page counts
  for print PDFs.
