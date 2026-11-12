# Talent by State: the U.S. STEM talent pipeline, state by state

State-level data on every stage of the talent pipeline, built for state policymakers alongside the 2026
US Talent Report. The project has three products in `data/states/`: the State Talent Sheet, the web profiles
and the PDF profiles. They draw on these sources:

| Pipeline stage | Source | Code | Outputs |
|---|---|---|---|
| K-12 preparation | NCES, NAEP | `naep.py` | `data/naep/` |
| College enrollment, degrees, prices, outcomes | NCES, IPEDS (1980–2025) | `python -m ipeds_clean`, `harmonize/` | `data/ipeds/` |
| International students by country | DHS, SEVIS by the Numbers | `sevis.py` | `data/sevis/` |
| Graduate students and postdocs | NSF NCSES, GSS | `gss.py` | `data/gss/` |
| Doctorates | NSF NCSES, SED | `sed.py` | `data/sed/` |
| H-1B jobs and green cards | DOL OFLC (LCA, PERM); USCIS H-1B Employer Data Hub | `dol.py`, `h1b.py` | `data/dol/`, `data/h1b/` |
| STEM workforce | Census, American Community Survey | `acs.py` | `data/acs/` |
| Innovation | USPTO, PatentsView | `patents.py` | `data/patents/` |

Each source has its own section below. The IPEDS pipeline comes first, because it is the largest.

**Live site:** [www.emersonjohnston.org/talentByState](https://www.emersonjohnston.org/talentByState/) (GitHub
Pages): the profiles index, each state's profile, the State Talent Sheet (`sheet.html`) and the PDF downloads.
`python -m ipeds_clean.deploy_pages` publishes `data/states/` to the `gh-pages` branch, which holds only the
built site and is replaced by one fresh commit on each deploy (so the ~500 MB of pages and PDFs never enter the
code history). Deploy only after a rebuild has passed its checks; `--dry` builds the site folder without pushing.

**Repository and data integrity.** Git (github.com/evjohnston/talentByState) tracks the code, templates, docs,
crosswalks and small reference files. The inputs (`sources/`, `reference/digest/`, `reference/survey_forms/`, about
34 GB), the rebuildable outputs (`data/`), `cache/` and `.env` are not tracked.
- **Inputs:** `manifests/sources_manifest.csv` (tracked) records every input file's size and MD5.
  `python -m ipeds_clean.manifest` reports missing, new or changed inputs; after adding or moving files on
  purpose, run it with `--update` and commit the manifest. Input files are only ever moved, never edited, and
  every move is logged in `sources/new_data_moves.csv`.
- **Commits:** `.githooks/pre-commit` (enabled with `git config core.hooksPath .githooks`) blocks a commit that
  removes README headings or drops more than 40 README lines, stages `.env`, or adds a file over 50 MB.
- **Working rules** for editing (exact, unique-match edits; one writer per shared file) are in `RULES.md`.

## IPEDS / HEGIS 1980–2025: cleaned tables and harmonized annual panels

Every file the IPEDS Data Center publishes for **1980 and 1984–2025** (1981–83 don't exist) is
cleaned table by table, then harmonized into institution-level panels that line up across
45 years of survey changes. There are also reporting-structure and merger tables.

```bash
.venv/bin/python -m ipeds_clean              # stage 1: clean all 1,213 tables (~15 min)
.venv/bin/python -m ipeds_clean --years 1999 --tables sal1999_a   # re-clean one table; merges into the catalog
.venv/bin/python -m ipeds_clean.harmonize    # stage 2: build the panels (~2 min)
```

```python
import ipeds_clean as ic
d  = ic.directory()                       # unitid x year attributes
c  = ic.completions()                     # awards by CIP-2020 x level x sex
x  = c.merge(d, on=["year", "unitid"], how="left")
f  = ic.finance(real_base_year=2020)      # constant dollars
ic.load(2010, "ef2010a")                  # any cleaned source table
```

The venv lives in `.venv.nosync/` (iCloud skips `*.nosync`); `.venv` is a symlink to it.

## Folder layout

```
sources/                   every raw download, as received (read-only; never edited)
  ipeds/{year}/            IPEDS Data Center downloads
  carnegie/                Carnegie Classification: longitudinal/ (1973-2021), 2018/, 2021/, 2025/, docs/
  delta_cost/              Delta Cost Project 1987-2012 CSV zip; docs/ (dictionary, mapping, PDFs)
  dhs_sevis/               DHS "SEVIS by the Numbers" monthly pages (.html; .mhtml copies)
  nsf_gss/                 NSF/NCSES Survey of Graduate Students and Postdoctorates tables, by download year
  nsf_sed/                 NSF/NCSES Survey of Earned Doctorates tables, by download/release
  dol_oflc/                DOL Office of Foreign Labor Certification disclosure files (LCA, PERM, PW, H-2A/B, CW-1)
  uscis_h1b/               USCIS H-1B Employer Data Hub exports, one file (.xlsx or .csv) per fiscal year
  uspto_patents/           PatentsView annualized patent files, one zip per grant year
  dhs_yearbook/            DHS Yearbook of Immigration Statistics (PDFs FY1996-2022, Excel FY2023-24;
                           excel/: the yearbooks' Excel table zips FY1996-2021 and tables8-11newadj)
  dhs_sevis/annual_reports/  SEVIS by the Numbers reports (2017 biannual, CY2018-24), OPT, F-1 to H-1B,
                             high-school F-1 and China/Hong Kong FOIA tables (PDF)
  ice_sevis_foia/          ICE SEVIS FOIA record-level releases (OPT, STEM OPT, public high-school F-1)
  iie_open_doors/          IIE Open Doors state fact sheets and snapshot reports (PDF)
  nafsa_econ_value/        NAFSA international student economic value reports (PDF)
  state_bridgeusa_j1/      State Department BridgeUSA J-1 counts
  census_acs_migration/    ACS B07009/B07409 exports from data.census.gov
  census_pseo/             Census PSEO releases R2019Q2-R2026Q2 (per-state and stacked files)
  bls_oews/                BLS OEWS state, national, metro and industry zips, 1997-2025
  ed_crdc/                 Civil Rights Data Collection zips, documentation, state_tables/ (OCR's published tables)
  nsf_herd/, nsf_ffs/      NSF Higher Education R&D and Federal Funds for R&D table zips
  usaspending/             USAspending database subset (pg_dump, not used) and FY2027 contracts extract
cache/                     regenerable downloads and extracts (safe to delete; rebuilt on demand, slowly)
  acs/                     ACS PUMS STEM-worker extracts per year (the 600 MB person files are not kept)
  naep/raw/                NAEP Data Service API responses (~7,000 calls; refetching takes hours)
  dol/                     needed columns of each OFLC workbook, as parquet (first read ~25 min)
reference/                 downloaded documentation, read-only
  digest/{edition}/        Digest of Education Statistics tables, 1995-2025 (one file per table;
                           menu/index pages in _pages/). No tables exist for the 2004 edition.
  cip/                     official NCES CIP files the CIP chain reads:
                           CIP.XLS (HEGIS/CIP-85/CIP-90/CIP-2000), Crosswalk2000to2010.csv,
                           Crosswalk2010to2020.csv, 2010to2020-Crosswalk.csv, CIPCode2020.csv
    nces_web_pages/        saved NCES crosswalk pages (HEGIS/CIP-85/CIP-90), for reading only
  cip_soc/                 CIP-SOC crosswalks (not used by the pipeline)
  survey_forms/            archived IPEDS survey forms and instructions, 1994–2025 (283 zips)
  state_attributes/        state GDP, population, partisanship, census region (peer presets)
  fonts/, logo/            embedded in the HTML pages
crosswalks/                project-maintained inputs, edit these:
  cip_overrides.csv        hand-reviewed CIP mappings that win over the official crosswalks
  deflators.csv            BLS CPI-U (rebuilt by python -m ipeds_clean.bls)
data/                      everything the pipeline writes (safe to delete and rebuild), one folder per source
  ipeds/                   IPEDS outputs
    clean/{year}/          stage 1: one parquet per source table
    meta/                  catalogs (tables, variables, value labels) and cleaning QA
    harmonized/            stage 2: panels + qa_*.csv
    forms_text/            text extracted from reference/survey_forms
    digest/                parsed Digest tables: catalog.csv, values.parquet, series.csv
    urban/                 Urban Institute IPEDS files for cross-checking (python -m ipeds_clean.urban)
  sevis/                   DHS SEVIS tables and checks             (python -m ipeds_clean.sevis)
  acs/                     Census ACS tables and STEM-workforce measures (python -m ipeds_clean.acs)
  naep/                    NAEP scores by state, subject, grade, year (python -m ipeds_clean.naep)
  gss/                     NSF GSS grad students and postdocs by state (python -m ipeds_clean.gss)
  sed/                     NSF SED doctorates by state                (python -m ipeds_clean.sed)
  h1b/                     USCIS H-1B approvals by employer state     (python -m ipeds_clean.h1b)
  dol/                     DOL LCA worksites and PERM by state        (python -m ipeds_clean.dol)
  patents/                 USPTO patents by assignee state            (python -m ipeds_clean.patents)
  digest_k12/, crdc/       K-12 spending, graduation rates, graduates, teachers, course access
  digest_state/            Digest residence and migration of first-time college students
  ice_foia/, j1/           OPT retention and STEM OPT; J-1 exchange visitors
  pseo/, scorecard/, acs_migration/   graduates' in-state employment, earnings, and migration of degree holders
  dhs_yearbook/, oews/     green cards and naturalizations; STEM jobs and wages
  states/                  the products, built from every source: state panel, maps, the State Talent Sheet,
                           the web profiles and the PDF profiles
ipeds_clean/               the code (the package keeps its original name); every path is set in
                           ipeds_clean/config.py (SOURCES, CACHE, DATA, OUT = data/ipeds, ...)
.env                       API keys, not committed: CENSUS_API_KEY (and any CENSUS_API_KEY_* backups; the ACS
                           module uses the first key the Census API accepts)
```

Build order: `python -m ipeds_clean` (clean) → `python -m ipeds_clean.digest` (parse Digest, ~5 min)
→ `python -m ipeds_clean.harmonize` (panels, then Carnegie, Delta Cost and the Digest benchmarks
when their inputs exist).

## Coverage

| panel | years | grain |
|---|---|---|
| `directory` | 1980, 1984–2025 | unitid × year: control, level, sector, state, degree-granting… |
| `enrollment` | 1980, 1984–2024 | unitid × year × level × FT/PT × race × sex |
| `enrollment_first_time` | 1980, 1984–2024 | first-time degree-seeking undergrads (subset of ug) |
| `completions` | 1980, 1984–2025 | unitid × year × award level × CIP-2020 × sex |
| `completions_race` | 1985, 1987, 1989–2025 | unitid × year × award level × 2-digit CIP-2020 × race × sex |
| `finance` | 1980, 1984–2024 | unitid × fiscal year, ~30 revenue/expense concepts |
| `faculty_salaries` | 39 years, 1980–2024 | unitid × year × rank × contract × sex |
| `prices` | academic years 1980, 1984–2023 | unitid × academic year: tuition & fees, room & board, books |
| `grad_rates` | 1997–2024 | unitid × year × cohort × measure × race × sex |
| `student_aid` | 2000–2024 (aid years 1999–2023) | unitid × year, aid to first-time full-time undergrads |
| `reporting` | 1986–2025 | unitid × year × component: parent/child role, parent unitid, response status, imputed |
| `entities` | – | merged unitid → final successor (1,056 institutions) |
| `fte` | 1980–2025 | fall FTE (FT + PT/3) every year; 12-month credit/contact hours and NCES FTE (2002+) |
| `enrollment_12mo` | 2002–2025 | unduplicated 12-month headcount × level × race × sex |
| `enrollment_age` | 1987, odd years 1991–99, 2000–2024 | fall enrollment × level × FT/PT × age group × sex |
| `residence` | 1986, 1988, even years 1992–98, 2000–2024 | first-time students × state of residence |
| `admissions` | 2001–2024 | applicants / admits / enrolled by sex and FT/PT; SAT/ACT 25th/75th percentiles |
| `retention` | 2002–2024 | FT/PT retention rates and cohorts; student-to-faculty ratio |
| `staff` | 2001–2024 | all staff and instructional staff by tenure status, FT/PT |
| `outcome_measures`, `gr200`, `gr_pell`, `completers_race`, `completers_age`, `distance_ed`, `libraries` | 2008–2024 (varies) | stacked as published; labels in `extras_variables.csv` |

Missing by design: race in completions for 1980/84/86/88 and enrollment race in 1985/87/89
(race collected in alternate years then); faculty salaries in 1986, 1988 and 2000 (no IPEDS file);
graduation rates before 1997 and student aid before 2000 (the surveys didn't exist).

All panels link to the directory for 100% of institution-years. `directory.derivation` shows how
each row was obtained (`reported`, `filled_from_<year>` for 7,011 institution-years borrowed from
the nearest year, `private_lt2yr_sample` for 4,370 pre-1993 CN-form sample schools).

---

# Stage 1: cleaning (`data/ipeds/clean/`, `data/ipeds/meta/`)

**Source.** `sources/ipeds/{year}/*.zip` (decade folders keep theirs in `sources/ipeds/{year}/raw/`).
Stata/SAS/SPSS program and Stata-format zips were removed; only the CSV data zips and `_Dict`
zips are read. Duplicate downloads are verified byte-identical and read once. Where a zip has a
revised `*_rv.csv`, the revised file is used.

**Per table** ([ipeds_clean/clean.py](ipeds_clean/clean.py)):
- UTF-8 with cp1252 fallback; lowercase column names; whitespace stripped; `""`/`"."` → missing.
- Ragged rows are allowed only if the extra fields are empty (verified per file; otherwise the table fails loudly).
- Types: `unitid` Int64; codes/IDs (`cipcode`, `opeid`, `zip`, …) and dictionary type A → string; imputation flags `x*` → string; the rest Int64/Float64.
- **Negative missing-data codes** (-1/-2/-3/-9): kept in *categorical* variables (labelled in `value_labels.csv`); set to missing in *continuous* ones; never touched in Finance (real negative dollars). Logged in `data/ipeds/meta/sentinel_codes.csv`.
- Dictionaries: HTML (1980–~2008) and xls/xlsx parsed into `variables.csv` / `value_labels.csv`. An empty dictionary export (sal1999_a) falls back to type inference.

**QA against NCES's published dictionary statistics** (`qa_stats.csv`), 42,945 variable checks:

| status | n | meaning |
|---|---|---|
| match_raw | 37,588 | n/sum/min/max/mean match |
| match_blank_as_zero_mean | 5,213 | old HTML dictionaries average blanks as 0; min/max match |
| mismatch_dict_stats_predate_revision | 72 | stats describe the original file; the revised one is loaded |
| skipped_kept_as_string | 44 | ID columns kept as text on purpose |
| MISMATCH | 28 | three tables (f0506_f1a_f, f0809_f1a, hd2009); not investigated further |

**Failures** (`failures.csv`): 7 tables have unquoted commas in free text (the 1995–96 `_ic` response-status
files, `ic2005mission`, `pub_financialaid`). None feeds a harmonized panel.

---

# Stage 2: harmonized panels (`data/ipeds/harmonized/`)

Common conventions:
- **Join** on `unitid` + `year` (prices: `ay` = academic year's fall).
- **Race** (where collected): `nonres, black, aian, api, hisp, white, two_more, unknown`, plus
  `not_collected` where a year only has totals. `api` = Asian + NHPI from 2008–11. `two_more`
  exists only from the 1997-OMB transition (2008–2011 depending on survey), so race series have a
  definitional break there; transition years use NCES's derived old+new (`dv*`) variables.
- **Blank = 0 inside a reported row** (old files leave zeros blank; the dictionaries' own means
  treat blanks as 0). Ignoring this silently dropped 106k 1990 awards before it was fixed.
- **Residual rows** keep totals complete where institutions reported only totals
  (`cip_method = residual_unallocated`, `level = level_unknown`); they are never assigned a field or level.

## Directory

`control` 1 public / 2 private nonprofit / 3 for-profit; `level` 1 four-year+ / 2 two-year /
3 less-than-two-year; `sector` 1–9; `degree_granting`; `stabbr`, `fips`, `region`, `hbcu`, `tribal`,
`opeid`, `newid` (mergers), `n_years`, `sample_weight` (pre-1993 CN sample schools, 1991 only), `derivation`,
`title_iv` (participates in federal student aid: 1996–97 `opeind` 1–2, 1998+ `opeflag` 1–3; NA before 1996).
The Digest's postsecondary universe from 1996 is `degree_granting & title_iv & fips <= 56`.

| years | source | notes |
|---|---|---|
| 1980, 1984, 1985 | HEGIS `ic{year}` | no for-profit code: derived from `affil = 25` ("organized as profit making"); level from iclevel/type/hloffer |
| 1986–1999 | IC header files (`ic1986_a` … `ic99_hd`) | no degree-granting item: = highest offering associate's+ **or** awarded associate's+ that year |
| 2000–2025 | `fa{year}hd`, `hd{year}` | as reported |

Universe breaks: HEGIS (1980–85) covered only institutions of higher education, with branches
folded into parents; IPEDS from 1986 adds less-than-2-year and non-degree schools; before 1993
private less-than-2-year schools were **sampled** (CN form), so their national counts need
`sample_weight`; from 2002 the universe narrows largely to Title IV institutions (for-profit
<2-year drops from ~3,200 to ~1,750). Filter on `degree_granting` for a HEGIS-like universe.

## Completions

**Field of study → CIP-2020** through every CIP revision ([cip_chain.py](ipeds_clean/harmonize/cip_chain.py)).
Vintages were verified per year (each file matches its edition's code list at 99–100%):

| files | code system | chain |
|---|---|---|
| 1980 | HEGIS (1970 taxonomy; `"01020"` = HEGIS 0102) | HEGIS → CIP90 → CIP2K → CIP10 → CIP20 |
| 1984–1986 | CIP-1980, undotted, leading zero dropped (`10102` = 01.0102) | CIP80 → CIP85 → CIP90 → … |
| 1987–1991 | CIP-1985 | CIP85 → CIP90 → … |
| 1992–2002 | CIP-1990 | CIP90 → CIP2K → … |
| 2003–2009 | CIP-2000 | CIP2K → CIP10 → CIP20 |
| 2010–2019 | CIP-2010 | CIP10 → CIP20 |
| 2020+ | CIP-2020 | – |

Rules per step (recorded in `cip_method`; full path per code in `cip_chain.csv`): `override`
([crosswalks/cip_overrides.csv](crosswalks/cip_overrides.csv), hand-reviewed, **edit to change a mapping**) →
`official` NCES crosswalk → `report_under` (parsed "Deleted, report under …") → `same_code` →
`title_match` / `sibling` (all listed in `cip_chain_review.csv`) → `no_field`. There is no official
CIP80→85 crosswalk; CIP-85 was a light update, so 1984–86 resolve ~97% by identical codes.

Share of awards mapped officially: 2010–2025 100%; 1992–2009 98–99%; 1987–91 81–87% (+7–9% same-code);
1980 90% (+9% override). `95.0000` "Undesignated field" (up to 5.5% of awards in 1989) stays `no_field`.
**Use `cip2020_2` or `cip2020_4` for long series**: older editions were coarser, so new 6-digit
programs show zero in early years by construction.

**Award levels:** one code map for 1984+ (validated against every year's labels), HEGIS map for 1980.
`cert_1_4` exists only in 1984–86 (code 2 = "1 but less than 4 years"); combine `cert_1_2 + cert_2_4`
for a consistent series. `doc_prof` = first-professional (≤2009) / doctor's professional practice (2010+).
When the first-professional level was retired, NCES moved divinity and rabbinical degrees (M.Div.,
M.H.L./Rav) to master's; the panel applies the same rule to pre-2010 first-professional awards in
theology (CIP 39 → `master`; `awlevel_orig` = 10 still shows the reported level). With it, doctor's and
master's totals match the Digest (table 318.10) to a median 0.2–0.3% across 1980–2022.

First majors only (second majors start 2001). Residual rows: 1987 (72k awards, 386 institutions
that reported only level totals), 1992–93 (~1%), 1984–86 (<0.3%).

## Fall enrollment

`level`: `ug`, `grad`, `first_prof` (through 2008, partly in 2008 during the phase-in; from fall 2009 first-professional is inside `grad`, so use
grad + first_prof = postbaccalaureate for a consistent series), `level_unknown` (grand-total-only
reporters: 274k students in 1986, 315k in 1987, 151k in 1989). `attendance`: `ft`, `pt`.

| years | layout | race |
|---|---|---|
| 1980, 1984, 1985 | HEGIS lines; unsplit "unclassified" students counted as undergraduates (NCES convention) | 1985 totals only |
| 1986–1998, 2000–01 | IPEDS lines 1–29 | 1987/89 totals only; 1986/88 no unknown item (unknown = total − detail) |
| 1990–1993 | | unknowns **pre-allocated** to races by NCES (efrace13/14 = memo, excluded) |
| 1994–1998 | `*_anr` files (as reported; `*_ark` = allocated version, not used) | unknown = 13/14 + balance |
| 1999, 2002–2009 | `efalevel` codes | old categories; 2008–09 NCES-derived |
| 2010–2024 | `efalevel` | new categories (2022+ also report gender-unknown counts as a memo; men + women = total) |

QA: for **100% of institutions in every year**, cells sum to the reported grand total and race detail sums to totals.
Totals: 12.2M (1980) → 15.5M (1999) → 21.9M (2010 peak) → 20.4M (2024), all institutions.

## Completions by race

2-digit CIP-2020 families. 1985, 1987, 1989–1994 come from 2-digit race files: each institution's
race counts for an old family are split across CIP-2020 families in proportion to that institution's
own 6-digit awards (`alloc = institution`; national split as fallback), so those years are fractional.
1995+ come straight from the 6-digit files. Totals equal the completions panel exactly except
1991–94, where the 2-digit race files are 0.1–2.6% below the 6-digit files at source.

## Finance

One row per institution × fiscal year (nominal $; `ic.finance(real_base_year=2020)` deflates with
[crosswalks/deflators.csv](crosswalks/deflators.csv): official BLS CPI-U, series CUUR0000SA0, pulled
by `python -m ipeds_clean.bls`. The default `index` is the calendar-year average of the year the fiscal
year ends in; `ic.finance(2020, index="index_fy")` uses the July–June average, which matches the IPEDS
fiscal year exactly. Calendar 2025 is missing because BLS published no October 2025 CPI (federal
shutdown), so use `index_fy` to deflate FY2025. Concepts are resolved per year from form families in `finance.specs()`; every
resolved item and its label per year is in `qa_finance_item_labels.csv`.

| `form` | who / when | tuition | plant O&M, depreciation | comparable instruction |
|---|---|---|---|---|
| `fund` | all 1980–1996; public F1 1997–2003 | **gross** | O&M its own function | = instruction |
| `fasb` | private nonprofit 1997+ | net + allowance | 1997 separate unless the institution allocated it; allocated from 1998 | 2002–2015 (allocation backed out) |
| `gasb` | public F1A 2002+ | net + allowance | O&M separate ≤2007; 2008–09 phase-in (`form_variant` aligned = allocated, unaligned = separate); allocated 2010+ | 2002–2015 |
| `forprofit` | 1998+ | net + allowance | allocated | 2014–2015 |

Most comparable across regimes: `tuition_gross`, `fed_total`, `state_local_total`, `state_approp`,
`research_public_service`, `support_total`, `instruction_excl_alloc`. **Not comparable across regimes:**
`total_revenue` / `total_expenses` (fund totals include transfers; FASB revenue includes investment
gains; GASB/FASB expenses include depreciation). The label audit caught one real trap: private
nonprofit `f2e121` means total expenses only in 2000–01 and "Other expenses" from 2002.

## Faculty salaries

Full-time instructional faculty: `n_faculty`, `salary_outlay`, `outlay_eq9` (equated 9-month),
`n_tenured` by rank × contract (`9_10`, `11_12`; `9_12` in 2012–15, when outlays aren't split by
contract) × sex. `salaries.equated_9month(df, by=[...])` aggregates correctly.
QA: counts equal institution-reported totals in every year with a total row, and our equated average
equals NCES's own (1999, 2002–2011) to the dollar. All-ranks equated average: $22.1k (1980) →
$55.0k (1999) → $73.3k (2010) → $99.8k (2024). Breaks: 2012 (salary worksheet limited to full-time
**non-medical** instructional staff, per the 2012 HR instructions; −$1.3k step); tenure not collected 2001–05 and absent from the salary files from 2012.

## Graduation rates

Counts from the Graduation Rate Survey; compute rates with `grad_rates.rates(df, by=["year"], cohort="ba4", num="comp150_bach")`.
Cohorts: `ba4` bachelor's-seeking at 4-year; `oth4` other degree-seeking at 4-year; `c2yr` 2-year
institutions; `lt2` less-than-2-year institutions (main file through 2003 with race × sex; separate
`_l2` files from 2004, totals only: `race = not_collected`, `sex = all`). `cohort_year` = survey year − 6
(4-year) or − 3. `grtype` 35–39 changed meaning in 2009 (year-specific mapping).
Results: bachelor's 6-year rate 52.5% (1991 entrants) → 64.4% (2018); 2-year 31–36%, rising to 43% by 2024;
less-than-2-year 65–71%. QA: race sums = totals and 4-year totals = ba4 + oth4 for 100% of institutions.

## Published prices

By academic year (`ay`): undergraduate tuition + fees in-district / in-state / out-of-state, graduate,
`room_board` (typical room + board, consistent all years), `room_board_coa` (2000+), `books`,
`ug_tf_program` (price of the largest program for program reporters, mostly <2-year). Later files
repeat prior years; one value per unitid × ay is kept, preferring the file whose own year it is.
Definitions shift: 1980–85 "tuition" by control; 1986–1997 tuition + required fees; 1997+ published
price for first-time full-time students. Median public 4-year in-state: $745 (1980) → $3,160 (2000) →
$8,568 (2023). Public 2-year medians run high in 1987–88 (table coverage, not adjusted).

## Student aid

First-time full-time undergraduates; each survey year describes the prior aid year (`aid_ay`).
Number receiving / average / total for any aid, federal, state/local and institutional grants, and
loans (all years); Pell, any-grant and federal loans from 2008–09; all-undergraduate items from 2009.
`cohort_ftft` uses the fall cohort, or the full-year cohort for program reporters (`cohort_basis`).
QA: recipients ≤ cohort for 100%, shares match the reported percentages for >99% in every year.

## Reporting structure and mergers

Before comparing institutions over time, decide how to treat **parent/child reporting** and **mergers**.

- **`reporting`**: one row per institution × year × component (`c`, `ef`, `e12`, `f`, `gr`, `gr2`, `sfa`, `hr`, `adm`, `al`, `om`, …).
  - `prch`: 1 parent (includes children's data), 2 child (reported with the parent), 3 partial child, 4/5 child reporting with a non-postsecondary entity, 6 partial parent/child.
  - `parent_unitid`, `status` (1 respondent, 2 partial-imputed, 4 nonrespondent-imputed, 5 nonrespondent-not-imputed), `imputed`, `imp_method` (1 carry-forward, 2 nearest-neighbor).
  - Sources: 1986–97 component header files, 1998–2003 directory headers, 2004+ `flags` files. 34,485 child records point to a parent.
  - Imputation is rare (0.1–2.4% of institution-years by component since 2000). Drop `imputed` rows for strict analyses.
- **`entities`**: 1,056 unitids merged into another institution (directory `newid`, followed through 115 multi-step chains to the final successor).
- **Helpers** in `ipeds_clean.harmonize.reporting`, both preserving totals exactly:
  - `rollup_children(df, reporting, component, value_cols)` sums children into parents, so a parent always represents parent + branches (finance: 220k → 208k institution-years).
  - `consistent_entity(df, entities, value_cols)` re-keys merged institutions to their successor in every year, so mergers don't look like growth.

```python
from ipeds_clean.harmonize.reporting import rollup_children, consistent_entity
fin = rollup_children(ic.finance(), ic.panel("reporting"), "f", ["total_expenses", "instruction"])
enr = consistent_entity(ic.enrollment(), ic.panel("entities"), ["n"], keys=["level", "attendance"])
```

## Additional panels

Load any of them with `ic.panel("<name>")`. Code: [ipeds_clean/harmonize/extras.py](ipeds_clean/harmonize/extras.py).

- **`fte`**: `fall_fte_*` = FT + PT/3 (the standard approximation) for every year from the enrollment panel, plus the
  12-month instructional-activity file from 2002: credit/contact hours and NCES-reported or -estimated FTE (2008+).
  Fall FTE runs from 8.9M (1980) to 16.5M (2010).
- **`enrollment_12mo`**: unduplicated annual headcount by level × race × sex (race schemes as in the fall panel;
  2008–10 use NCES's derived `dvey*` columns). It matches institution-reported totals in the check years.
- **`enrollment_age`**: age groups (under 18 … 65+, unknown) × FT/PT × sex × level. Three layouts are mapped from labels.
  **Age is required only in odd years:** odd-year (and 2000–03) totals equal fall enrollment exactly, while even years from 2004
  cover 74–98% of students, and 1991–97 cover 87–97%.
- **`residence`**: first-time students by state of residence when admitted (`first_time`, `recent_hs_grads`).
  **Required in even years** (about 3M students); odd years are optional (about 2.2M).
- **`admissions`**: 2001–2013 from the IC file, 2014+ from ADM. Totals are built from men + women where only those exist,
  plus `admit_rate` and `yield_rate`. Applicants grow from 5.0M to 14.8M over 2001–2024 against 1.4–1.7M enrolled.
- **`retention`**: full- and part-time retention rates and cohorts (rates from 2003), `stufacr` student-to-faculty ratio.
  Median FT retention runs 70–75%.
- **`staff`**: all staff and instructional staff (tenured / tenure-track / not on track / without faculty status), FT and PT.
  The series is continuous across the 2012 category change; FT instructional staff grow from 616k (2002) to 767k (2024), with tenured
  flat at about 300k and non-tenure-track rising from 191k to 321k. **2001 covers fewer institutions** (4,750 vs 6,498;
  on common institutions it is within 4% of 2002).
- **Stacked as published:** `outcome_measures` (2015+), `gr200` (2008+), `gr_pell` (2016+), `completers_race` and
  `completers_age` (2012+), `distance_ed` (2012+), `libraries` (2014+). Variable names are stable within these spans;
  labels and first/last years per variable are in `extras_variables.csv`.

Not harmonized (single or few years, or superseded): pre-2001 staff (`s1987`–`s99`, which use different occupational
schemes), `ef*cp` (enrollment by selected majors), institutional characteristics beyond the directory fields (mission,
services, calendar), the 2021+ `drv*` derived-variable files (they duplicate source items), and the cost-of-attendance
files new in 2024.

## Verified against the IPEDS survey forms (1994–2025)

`reference/survey_forms/` holds the archived form and instruction packages (283 zips, 926 PDFs).
`python -m ipeds_clean.forms` extracts their text to `data/ipeds/forms_text/`, and
`ipeds_clean.forms.search(pattern, component=..., years=...)` searches them. Checked against the instructions:

| inferred rule | instructions say | result |
|---|---|---|
| Age reported in odd years, residence in even years | "Enrollment by age is required in odd-numbered years, and enrollment by residence of first-time undergraduates is required in even-numbered years" (1999, 2007, 2020+) | confirmed |
| First-professional replaced by doctor's research / professional practice / other | Required "beginning with the 2009-10 collection year" (Completions and Fall Enrollment) | confirmed; enrollment change is fall **2009**, not 2010 (README corrected) |
| Completions CIP edition per year | 2002–03: "1990 CIP or CIP2000" (institutions chose); 2009–10: "required to use the 2010 CIP"; 2019–20: "Use the 2020 CIP codes" | confirmed; the 2003 choice also produced 14 temporary `xx.xx88` conversion codes, now hand-mapped |
| Second majors start 2001 | 2000–01 form adds "CIP Data Second Majors" | confirmed |
| FASB: O&M allocated to functions | 1997: separate only if not allocated in the statements; 1998: "should be allocated among all functional categories" | confirmed, with 1997 mixed (README corrected) |
| GASB: O&M separate through 2007 | 2008–09 offered both "aligned" (O&M allocated) and "unaligned" forms; all institutions aligned from 2010 | **fixed**: `plant_om` now mapped for 2008–09 unaligned filers ($13.5B / $11.6B, previously 0) and `form_variant` added |
| GASB: Pell in federal nonoperating grants | "Federal nonoperating grants is expected to be greater than or equal to the amount reported for Pell grants" (2011+) | consistent; `fed_grants` sums operating + nonoperating, so placement doesn't matter |
| SFA: full-year cohort for program reporters | separate "full-year cohort (program reporters)" screens | confirmed |
| Salaries: equated 9-month | "the system will calculate the Equated 9 months" from 9/10/11/12-month outlays | consistent (our formula reproduces NCES's equated averages to the dollar) |
| Salaries: 2012 universe | 2012 salary worksheet: "full-time, non-medical, instructional staff" | explains the 2012 step (README corrected) |

---

## External reference material (checking only)

The project analyzes IPEDS. Carnegie and Delta Cost (above) are IPEDS-derived and keyed to `unitid`;
two further outside sources are pulled only for checking, and neither feeds a panel:

- **BLS CPI-U** (`python -m ipeds_clean.bls`): the price index in `crosswalks/deflators.csv`, used
  only to express IPEDS dollars in constant dollars.
- **Urban Institute Education Data Portal, IPEDS files only** (`python -m ipeds_clean.urban`):
  Urban's re-release of the same NCES surveys, saved to `data/ipeds/urban/` with `manifest.csv` and the
  codebooks. It is used to cross-check the panels. The set covers the single-file endpoints for
  directory, finance, prices, admissions, retention, FTE, residence, graduation rates (150%, 200%,
  Pell), outcome measures, completers, libraries, instructional salaries and student aid. It also
  has enrollment by race and completions by 6-digit CIP for 1990, 2000, 2010, 2020 and 2023, and
  enrollment by age for 2000, 2010, 2020 and 2023. None of the portal's non-IPEDS sources are
  fetched. Cite as: [dataset names], Education Data Portal (Version 0.27.0), Urban Institute,
  accessed <date>, https://educationdata.urban.org/documentation/, ODC Attribution License.

## Digest of Education Statistics tables

`python -m ipeds_clean.digest` reads every table in `reference/digest/` (14,050 tables, 30 editions,
1995–2025). It catalogs them all and parses the 4,606 whose source note cites IPEDS or HEGIS. 4,552
parse; the 54 that don't are ranked lists, such as the "120 largest campuses", with no numbered columns.

- `data/ipeds/digest/catalog.csv`: every table, with edition, table_id, title, source note, `ipeds`, format,
  parse status, `series_id`, `link_score` and `link_via`.
- `data/ipeds/digest/values.parquet` (3.9M cells): each cell has its `row_path` (section > subsection >
  label, e.g. `Current dollars > Male > 2010-11`) and `col_label` (stacked headers, e.g.
  `Control of institution | Private | For-profit`). It also has `year_first`/`year_last` parsed from
  year rows, `value`, `value_raw` and `flag`: `na` (—), `dagger` (†), `zero` (#), `rsnm` (‡),
  `caution` (!) or `se` (a standard error in parentheses).
- **Linked across editions:** 2013+ tables keep their number ("303.10"). Older tables (old sequential
  numbers) are matched one-to-one by title to the next edition, back to 1995. 1,797 of the 2,719
  older IPEDS tables are linked; the rest were discontinued or redesigned. `series.csv` lists each
  series with its editions and old numbers. The core series run 1995–2024 unbroken: 303.10 enrollment,
  304.10 by state, 316.10 salaries, 317.10 institutions, 318.10 degrees, 330.10 tuition.

```python
ic.digest("303.10", latest=True)   # one value per row/column: newest edition after the data year
ic.digest_catalog().query("ipeds and title.str.contains('tuition')", engine="python")
```

**Benchmarks against the panels** (`qa_digest.csv`, built by the harmonize run). These compare
national totals in the Digest's universe: degree-granting, 50 states + DC, and Title IV from 1996.
Institution counts include only institutions reporting fall enrollment, directly or through a parent,
as the Digest does. Salaries use 9/10-month contracts, which is what table 316.10 reports.

| measure | median gap | years within 1% |
|---|---|---|
| fall enrollment: total / FT / PT / sex / public | 0.0–0.2% | 80–95% |
| bachelor's, master's, doctor's degrees | 0.0–0.3% | 82–92% |
| average faculty salary (all ranks / professors) | 0.0% (to the dollar from 2005) | 91–97% |
| degree-granting institutions (total, public 4-yr) | 0.1–0.2% | 56–77% |

Known gaps, which are about the universe, not errors:
- **1986–1995:** the Digest counted accredited "institutions of higher education". IPEDS has no
  consistent flag for that, so panel for-profit counts and enrollment run 20–100% higher, and
  associate's degrees 3–6% higher.
- **2000–2010:** associate's degrees run ~2% above the Digest. The cause hasn't been found.

## Carnegie Classification

`carnegie.parquet` has one row per unitid × edition (1973, 1976, 1987, 1994, 2000, 2005, 2010, 2015,
2018, 2021, 2025), from the publisher's longitudinal file plus the 2025 public file.

- `basic_code` and `basic_label` are each edition's own basic classification.
- `common_code` and `group` (Doctoral / Master's / Bachelor's / Bacc-Assoc / Associate's / Special
  focus / Tribal) are the publisher's cross-edition harmonization.
- `research_tier` is R1 / R2 / doctoral_other. R1 and R2 counts match the published ones (2021: 146
  R1, 133 R2; 2025: 187 / 139).
- `status` records did_not_exist / merged / closed / not_classified.
- **2025 is a new system.** It has an Institutional Classification and a Research Activity Designation
  but no basic classification, so its `group` is mapped from the new category names and flagged
  `group_approx_2025`.

`carnegie_detail.parquet` holds every other classification code in the 2018/2021/2025 files (program,
enrollment-profile, size and setting, 2025 size and award level), with labels in
`carnegie_labels.csv`. The College Scorecard and NSF research-spending fields bundled in the 2025
file were not brought in. 99.6–100% of classified unitids from 1987 on are in the IPEDS directory
(1973–76: 94–99%).

```python
ic.carnegie(ic.directory())   # each institution-year gets the latest edition at or before that year
```

## Delta Cost Project (1987–2012)

`delta_cost.parquet` holds all 974 published variables (215,613 unitid × years). `year` =
`academicyear` = fiscal year end, the same as `finance.parquet`. Labels and definitions are in
`delta_cost_variables.csv`.

- **Grouped rows:** rows with `isgrouped = 1` carry Delta's combined parent + child finances (`groupid`
  > 0). Use `isgrouped == 0` to match single institutions.
- **Missing codes:** set to NA only where the dictionary defines them. Imputation flags (`I*` columns)
  keep −1/−2 as categories.
- **Linkage:** every Delta row with data links to the IPEDS directory. The unmatched 5.8% are empty
  placeholder rows.
- **Check against the finance panel** (`qa_delta_cost.csv`, ungrouped institution-years):
  - tuition, state and federal appropriations agree within 1% for 98.5–99.4%;
  - total expenses for 96% and total revenue for 90%;
  - instruction, research and student services for 67–75% only. Delta re-maps functional expenses
    (see `docs/IPEDS_DCP_Database_Mapping_File_87_12.xls`), so use Delta's versions when you want
    its adjustment.

## DHS SEVIS by the Numbers (2014–2026)

The one non-IPEDS student source. DHS/ICE (Study in the States) publishes a "SEVIS Data Mapping Tool Data"
page each month. The pages are saved in `sources/dhs_sevis/`: 72 all-student months (April 2014 – October 2026) and
66 STEM months (September 2015 – October 2026). Monthly from 2023, a few months a year before that.

```bash
.venv/bin/python -m ipeds_clean.sevis           # parse every page -> data/sevis/ + validation report
.venv/bin/python -m ipeds_clean.sevis --check   # compare with IPEDS nonresident fall enrollment
```

**Two layouts.**
- **All active F-1/M-1 students** (no `stem` in the file name): one row per country of citizenship. Each row
  has the total, male/female, counts by education level, and one column per state or territory. State and
  level are never crossed.
- **Active STEM students** (`-stem-`): one row per state × education level × country × sex. STEM is DHS's
  STEM Designated Degree Program List, not the IPEDS CIP families used elsewhere in this project.

SEVIS counts are a snapshot of active records in the month named, not an academic-year count. The PDF reports
in `sources/dhs_sevis/annual_reports/` are read by a different module (`sevis_reports`, below).

**Outputs (`data/sevis/`):**

| file | contents |
|---|---|
| `all_country.parquet` | month × country: continent, region, total, male, female, counts by level |
| `all_state_country.parquet` | month × state × country: all active students (long form of the state columns) |
| `stem.parquet` | month × state × level × country × sex: active STEM students |
| `country_map.csv` | the 116 raw spellings that are mapped to another name (renames, scanning typos such as "AHD" for "AND") |
| `files.csv` | one row per page: row counts, sums checked against the total, saved copies, `flag` |
| `ipeds_check.csv`, `national_levels.csv` | the `--check` comparison (below) |

**Saved copies.** A page can also be saved as a browser single-file archive (`.mhtml`) named like the
`.html` page. The parser uses the `.html` page, falls back to the `.mhtml` copy if the `.html` has no
table, and records in `files.csv` whether the copies agree. The one copy so far,
`july-2018-sevis-data-mapping-tool-data.mhtml`, is identical to its `.html` page.

**Pages flagged and left out of every snapshot** (`files.csv`, `flag`):
- **July 2018 STEM:** the page has no data table.
- **November 2023, all students:** repeats the May 2023 table cell for cell.
- **September 2020, September 2022 and November 2022 STEM:** partial. Each totals 21–23% of the all-student
  count, against 50–57% in the surrounding months.

**Other checks.**
- The state columns and the level columns sum to the total exactly in 60 of the 72 all-student pages and
  within 0.5% in the other 12.
- Male + female matches the total within 0.5%, except July 2014 (+0.9%).

**How the pages are used.**
- **Yearly snapshot:** one fall snapshot per year, the September–December page closest to November (lines
  up with the IPEDS fall census). 2019 has no fall page and is blank. 2023 uses October, because the November
  2023 page is a repeat. STEM has no usable fall 2022 page, so STEM 2022 is blank too.
- **States:** the state columns include Guam, Puerto Rico, the Virgin Islands and the Northern Mariana Islands.
  The sheet uses the 50 states and DC, and its U.S. value is their sum.
- **State Talent Sheet:** 10 rows in "International students by country (SEVIS)" (`sevis.SHEET_MEASURES`,
  `sevis.sheet_panel`):
  - totals, and each state's share of the U.S. total;
  - the shares from India and China, and the share from the top two countries;
  - the number of countries represented;
  - STEM totals, STEM master's and doctoral counts, and the India share of STEM master's students (blank
    where a state has fewer than 30 STEM master's students).
- **State profiles:** the latest month, from `sevis.state_payloads`: top countries, trend, and STEM by level.
- **Source line:** every SEVIS figure reads "Data from DHS, SEVIS by the Numbers".

**Not comparable across the two layouts.** In some states the STEM pages count nearly as many students as
the all-student pages, or more: New Jersey 133% in November 2025, Washington 93%, Texas 88%. The two layouts
are not drawn on the same basis, so no STEM share of all students is computed.

**Check against IPEDS** (`--check`, 50 states + DC, fall snapshot vs IPEDS fall nonresident headcount).
The two count different populations:
- SEVIS counts F-1/M-1 visa holders at every level, primary school through doctorate, plus language and
  flight schools.
- IPEDS counts students on any temporary visa at degree-granting Title IV institutions.

| fall | SEVIS month | SEVIS | IPEDS nonres | ratio | SEVIS master's + doctoral ÷ IPEDS graduate | SEVIS associate + bachelor's ÷ IPEDS undergraduate |
|---|---|---|---|---|---|---|
| 2014 | Oct | 1,110,721 | 916,401 | 1.21 | 1.13 | 0.85 |
| 2016 | Nov | 1,227,214 | 997,022 | 1.23 | 1.23 | 0.87 |
| 2018 | Dec | 1,173,504 | 989,827 | 1.19 | 1.25 | 0.84 |
| 2020 | Dec | 872,790 | 848,326 | 1.03 | 1.12 | 0.77 |
| 2021 | Oct | 963,394 | 883,368 | 1.09 | 1.12 | 0.84 |
| 2022 | Nov | 1,095,144 | 965,288 | 1.13 | 1.12 | 0.89 |
| 2023 | Oct | 1,221,681 | 1,020,841 | 1.20 | 1.22 | 0.90 |
| 2024 | Nov | 1,281,400 | 1,046,139 | 1.22 | 1.32 | 0.86 |

The by-level ratios are national and include the territories; the other columns are 50 states + DC.

- **The totals move together.** Both fall from 2018 to 2020 and recover by 2024.
- **Graduate level:** SEVIS runs above IPEDS. This fits SEVIS keeping students on post-completion OPT as
  active records under their degree level. IPEDS counts only students who are enrolled.
- **Undergraduate level:** SEVIS runs below IPEDS, because IPEDS nonresidents include other visa types.
- **By state** (fall 2024): the median ratio is 1.17. The lowest are HI 0.77, AK 0.78 and IN 0.84; the
  highest are WA 1.47, UT 1.49, CT 1.53, ME 1.56 and NH 1.58. Read a high ratio as a state with many
  non-degree, language or OPT records, not as an IPEDS error.
- **Not yet compared:** the harmonized IPEDS enrollment panel ends in fall 2024, so 2025 and 2026 have no
  IPEDS check.

## Census American Community Survey (2014–2025)

The workforce end of the pipeline: who works in STEM in each state, and how many of them were born abroad.
ACS 1-year estimates. Code in `ipeds_clean/acs.py`; nothing is kept in `sources/`, because both parts are
downloaded from the Census Bureau on each run.
- **Detailed tables:** 2014–2019 and 2021–2025.
- **Microdata (PUMS):** 2014–2019 and 2021–2024. As of 2026-11-11 the 2025 1-year PUMS is on neither
  www2.census.gov nor the API; add 2025 to `acs.PUMS_YEARS` when it is.
- **No 2020:** the Bureau released only experimental 1-year data that year.

```bash
.venv/bin/python -m ipeds_clean.acs                # detailed tables + microdata, every year
.venv/bin/python -m ipeds_clean.acs tables         # detailed tables only
.venv/bin/python -m ipeds_clean.acs pums 2024      # microdata for the years named
```

**Detailed tables.**
- **What they are:** the published estimates and margins of error for three tables, for each state, DC and
  the US (Puerto Rico is dropped):
  - B05002: nativity and citizenship.
  - B05006: country of birth of the foreign-born.
  - B06009: educational attainment (25 and over) by place of birth.
- **Where they come from:**
  - **With a key:** the Census API (`api.census.gov`), which covers every year. The key is free from
    https://api.census.gov/data/key_signup.html. Put it in `$CENSUS_API_KEY`, as `CENSUS_API_KEY=...` in the
    project's `.env` (extra `CENSUS_API_KEY_*` lines are tried as fallbacks), or in a `.census_key` file.
    The module uses the first key the API accepts. Raw responses are cached in `cache/acs/api/`; delete one
    to refetch it.
  - **Without a key:** the keyless table-based summary files on www2.census.gov. These start in 2021, so
    2014–2019 stay empty until a key is added.
  - `data/acs/files_tables.csv` records which source each year came from. Every year in the current build
    came from the API.
- **Matching lines across years:** lines are matched by label, because B05006 renumbers its countries
  between vintages and 2023 changed "Foreign born" to "Foreign-born".
- **Small states:** the Census does not publish B05006 country detail in 1-year data for about 20 small
  states (the India share exists for 28–33 states a year).

**Microdata (PUMS).**
- **Source:** the national person file for each year, from www2.census.gov. No key is needed.
- **How it's processed:** each year's zip (about 600 MB) is downloaded to a temporary folder, read, then
  deleted. The STEM-worker records are kept in `cache/acs/pums_stem_{year}.parquet` (10–15 MB each), and
  all-worker totals by state and nativity in `cache/acs/pums_workers.csv`.
- **STEM occupations** (the same definition as the DOL and OEWS rows):
  - SOC 15: computer and mathematical.
  - SOC 17: architecture and engineering.
  - SOC 19: life, physical and social science.
  - The STEM manager codes 11-3021, 11-9041 and 11-9121.
- **Workers:** the employed, civilian or armed forces, counted in the state where they live, not where they
  work.
- **Margins of error:** 90% margins come from the 80 replicate weights. `n` is the number of sample records
  behind the denominator.
- **Small states are thin.** Wyoming has 107–153 STEM-worker records a year and 0–10 foreign-born ones.
  Read the country and doctorate shares only where `n` is in the hundreds.

**Outputs (`data/acs/`):**
- `tables_long.csv`: year, state, table, variable, label, estimate, moe.
- `table_measures.csv`: foreign-born and noncitizen shares of residents; the naturalized share of the
  foreign-born; India and China shares of the foreign-born; bachelor's-or-higher shares for all adults and
  for foreign-born adults; the foreign-born share of graduate-degree holders.
- `pums_stem.csv`: year × state × occupation group (`all`, `computer_math`, `engineering`, `science`,
  `stem_managers`) × measure, with value, moe90 and n.
- `pums_stem_wide.csv`: the `all` group, one row per state-year, with `n_stem_records` and
  `n_fb_stem_records`.
- `files_tables.csv`: where each table-year came from.

**Microdata measures:**

| Measure | What it is |
|---|---|
| `stem_workers` | workers in STEM occupations |
| `stem_share_of_workers` | STEM workers as a share of all workers |
| `stem_fb_share` | foreign-born share of STEM workers |
| `stem_naturalized_share` | naturalized citizens as a share of STEM workers |
| `stem_noncit_share` | noncitizens as a share of STEM workers (green-card holders and temporary visas together; the ACS does not separate them) |
| `stem_fb_recent_share` | STEM workers who are foreign-born and arrived in the last 10 years |
| `stem_grad_fb_share` | foreign-born share of STEM workers with a master's, professional degree or doctorate |
| `stem_phd_fb_share` | foreign-born share of STEM workers with a doctorate |
| `stem_grad_share_fb` | share of foreign-born STEM workers who hold a graduate degree |
| `stem_grad_share_native` | share of US-born STEM workers who hold a graduate degree |
| `stem_fb_india_share` | share of foreign-born STEM workers born in India |
| `stem_fb_china_share` | share of foreign-born STEM workers born in mainland China (not Hong Kong or Taiwan) |

**US figures, 2014 → 2024:**
- **STEM workers:** 8.8 million → 13.7 million (5.9% → 8.1% of workers).
- **Foreign-born share of STEM workers:** 21.6% → 24.0%. Noncitizens: 9.9% → 11.3%.
- **Among STEM workers with a graduate degree:** 37.8% → 40.9% foreign-born.
- **Among STEM workers with a doctorate:** 43.7% → 46.6% foreign-born.
- **India:** 28–30% of foreign-born STEM workers every year; China 10–11%.
- **All residents (detailed tables):** 13.3% foreign-born in 2014, 14.8% in 2024 and 14.7% in 2025. The
  foreign-born share of graduate-degree holders rose from 18.1% to 21.5% (2014 → 2025).

**How states compare:**
- **Foreign-born share of STEM workers, 2024:** highest in New Jersey 41.5%, California 39.7%, Washington
  33.9% and Texas 31.0%; lowest in Montana 2.4% and West Virginia 2.8%.
- **Foreign-born share of residents, 2025:** highest in California 27.2%, New Jersey 24.9% and New York 23.4%;
  lowest in West Virginia 2.3%.

**In the sheet and profiles** (`external.acs`): ten rows, eight from the microdata and the foreign-born shares
of residents and of graduate-degree holders from the tables. Microdata shares resting on fewer than 100 sample
records are blank. In 2024 that blanks the doctorate share in 31 states and the shares of foreign-born STEM
workers (such as India's) in 21.

**Caveats:**
- **The 2018 occupation codes:** part of the rise in STEM workers comes in 2018, when the ACS moved to the
  2018 SOC codes.
- **Not comparable with IPEDS or SEVIS:** the ACS counts residents and workers, not students, so its
  numbers do not line up with those two sources.

## NAEP, The Nation's Report Card (1990–2024)

K-12 achievement by state, from the NAEP Data Service API, which needs no key. Code in
`ipeds_clean/naep.py`; the API responses are cached in `cache/naep/raw/` (there is no `sources/` folder).

```bash
.venv/bin/python -m ipeds_clean.naep             # rebuild data/naep/ from the cache (seconds)
.venv/bin/python -m ipeds_clean.naep --refresh   # refetch every response (hours)
```

**What's covered:** every subject, grade, scale (composite and subscales) and assessment year of the main
NAEP, for all students:
- for the nation (`US`), national public schools (`US public`), the 50 states and DC;
- plus the national Long-Term Trend assessment: reading 1971–2025 and mathematics 1978–2025, at ages 9, 13
  and 17.

**Statistics:** each comes with its standard error.
- the mean and standard deviation;
- the 10th, 25th, 50th, 75th and 90th percentiles;
- the achievement levels, both cumulative and discrete (these exist only for composite and overall scales).

**How the download works.** The API rejects a call if any year in it is not an assessment year, or if the
years span two frameworks. So the module:
1. probes each subject × grade × scale × year × sample with one small national call;
2. fetches every valid combination with one call per statistic, covering every jurisdiction at once.

A single call that asks for all statistics and jurisdictions together takes minutes on the server, so the
calls are split up. `calls.csv` lists 7,069 calls, probes included, of which 4,415 returned data. Six run at
a time; the first run takes two to three hours.

**Samples:**
- **R2** (1990–2000) does not permit testing accommodations; **R3** (1996 on) does. Both are kept.
- In years with both, the sheet and profiles use R3.

**State coverage** (`coverage.csv`, composite scales):

| Subject | Grade | Years with state results | States |
|---|---|---|---|
| Mathematics | 4 | 1992–2024 | every state since 2003 |
| Mathematics | 8 | 1990–2024 | every state since 2003 |
| Reading | 4 | 1992–2024 | every state since 2003 |
| Reading | 8 | 1998–2024 | every state since 2003 |
| Science | 4 | 2000, 2005, 2009, 2015 | up to 46 |
| Science | 8 | 1996–2015 | up to 51 (2011) |
| Writing | 4 | 2002 | 44 |
| Writing | 8 | 1998, 2002, 2007 | up to 45 |
| Vocabulary | 4 and 8 | 2009, 2011, 2013 | 51 |
| Mathematics, reading, vocabulary | 12 | 2009 and 2013 | 13 pilot states |

Civics, U.S. history, geography, economics, music, visual arts and TEL are national only. (The module
docstring gives vocabulary as 2011–2015; the cached API responses give 2009, 2011 and 2013.)

**In the sheet and profiles** (`external.naep`):
- **Measures:** grade 4 and 8 mathematics and reading averages; at or above Proficient in all four; at
  Advanced and the 90th percentile for grade 8 mathematics; grade 8 science on the 2009 framework (2009, 2011,
  2015).
- **States vs U.S.:** states are public-school results, so the U.S. comparison is national public schools.
- **Changes:** scores change in points.
- **Lines:** chart lines may span gaps of up to five years, because NAEP is assessed every two to four years.

**Outputs (`data/naep/`):**
- `naep_long.csv`: one row per jurisdiction × subject × grade × scale × year × sample × statistic, with
  value, standard error and error flag. Rows the API marks as not displayable are dropped.
- `naep_wide.csv`: one row per jurisdiction × subject × grade × scale × year × sample, with a column per
  statistic and its `_se`.
- `naep_ltt.csv`: Long-Term Trend, national.
- `coverage.csv`: states with a displayable mean, by subject × grade × scale × year × sample.
- `calls.csv`: every API call, with its status.

NCES can revise published values, so rerun with `--refresh` before relying on a new release.

## NSF/NCSES Survey of Graduate Students and Postdoctorates (GSS)

Graduate students and postdocs in science and engineering, by the state of the institution, with
temporary-visa holders counted separately. Code in `ipeds_clean/gss.py`; the published tables are in
`sources/nsf_gss/`, one folder per download for 1994–2004 (.xls) and one zip for 2005–2025 (.xls/.xlsx).
Zips are read in place.

```bash
.venv/bin/python -m ipeds_clean.gss        # -> data/gss/  (~3 s)
```

**Folder names are download labels, not survey years.** Each file's survey year is read from its table
title, and tables are found by title, because NSF renumbers them nearly every year. Four zips hold a
different year than their name:
- `2025.zip` (nsf23312) is fall 2021.
- `2023.zip` (nsf24319) is 2022.
- `2022.zip` (nsf25317) is 2023.
- `2021.zip` (nsf26307) is 2024.

**Coverage.**
- **Graduate students by state:** total and temporary-visa counts, for S&E, science and engineering, in 1994
  and 1996–2016.
  - 1994 also has health, S&E plus health, and broad fields.
  - In 1994 the state temporary-visa count exists only for S&E plus health.
- **Postdocs by state:** total and temporary-visa counts, 2010–2016.
- **From 2017 on:** NSF publishes no state detail, and its institution tables don't name a state, so
  2017–2024 and 1995 are national only.
  - US values come from the national trend tables, from the release for that year or the earliest later one.
  - There is no 2019 download; that year's US values come from the 2020 release.
  - Nonfaculty researchers (`nfr_total`) are national only in every year.
- **Territories:** Puerto Rico, Guam and the Virgin Islands are separate rows. The US total includes them, so
  the 50 states plus DC run 0–1.1% below the US total (median 0.2%).

**Series breaks, from NSF's table notes:**
- **2007:** fields were reclassified.
- **2008:** practitioner programs were excluded more strictly.
- **2010:** the postdoc section was expanded, so part of the jump over 2009 is better reporting.
- **2014:** the survey frame added 151 institutions, mostly master's-granting.
- **2017:** a redesign to the NCSES field taxonomy. US S&E graduate students go from 620,489 in 2016 to
  581,149 in 2017 on the new basis, and NSF advises comparing only broad fields across it.

"Science" includes psychology and the social sciences throughout; health is separate.

**Temporary visa before 1998.** The 1994–1997 tables say "Non-U.S. citizens". NSF's own trend tables treat
that column as temporary-visa holders (1996 S&E plus health: 102,974 vs 102,984), and so does this parser.

**Checks** (`data/gss/checks.csv`):
- The state rows plus territories add up to the US row exactly, for every table.
- The state tables' US rows agree exactly with the national trend tables in most years, and within 1.5%
  otherwise, except 2011 engineering postdocs on temporary visas (2.8%).
- Year-over-year jumps over 15% are flagged: temporary-visa S&E graduate students in 2014 (+16%, the frame
  change), 2021 (+16%) and 2022 (+22%).

**US figures:**
- **S&E graduate students:** 433,152 in 1994, 620,489 in 2016, 740,379 in 2024.
- **Temporary-visa share of S&E graduate students:**
  - about 30% in 2001–2012,
  - 36–39% in 2014–2017,
  - 32.6% in 2020,
  - 40–42% in 2022–2024.
- **S&E postdocs:** 25,787 in 1994 and 49,247 in 2024. More than half are on temporary visas in every year
  through 2023.

**In the sheet and profiles** (`external.gss`): S&E graduate students and postdocs, the temporary-visa count
and share, and the temporary-visa share of engineering graduate students. The state series end in 2016; the
US line continues to 2024.

**Outputs (`data/gss/`):**
- `gss_state.csv` (long) and `gss_state_wide.csv`: counts and shares by survey year, state and field.
- `coverage.csv`: which measures exist by year and how many states.
- `files.csv`: all 2,212 files, with the detected survey year, table title, and whether each was used (99 are)
  and why not.
- `checks.csv`

**Unreadable files:**
- `1995/sel34.xls` is a Lotus 1-2-3 sheet that can't be read (an institution ranking, no state detail).
- The `tables.pdf` in `2011.zip` is damaged (bad CRC); it is a PDF copy of the tables.
- The 32 files with " (1)" in their names have no un-suffixed twin, so they are the only copies.

## NSF/NCSES Survey of Earned Doctorates (SED, 1994–2025)

Research doctorates by the state of the institution that awarded them. Code in `ipeds_clean/sed.py`; the
tables are in `sources/nsf_sed/`, one folder per year for 1994–2004 (.xls; 1996 is a Lotus 1-2-3 sheet read by
a small reader in the module) and one zip per release for 2005–2025. Zips, nested ones included, are read in
place.

```bash
.venv/bin/python -m ipeds_clean.sed        # -> data/sed/  (~5 s)
```

**Coverage:**
- **States:** all 50 plus DC, with Puerto Rico kept separately.
- **Years:** every year 1994–2025, by the academic year (July–June) ending in it. The module docstring says
  the 2002 state table is missing; `sources/nsf_sed/2002/tab6.xls` is now in place and used.
- **Fields every year:** all fields, S&E, non-S&E, engineering, physical and earth sciences, math and computer
  sciences, psychology and social sciences, and S&E excluding health.
- **Fields from 2009 on:** life sciences, health, education, humanities (humanities and arts from 2015), and
  other non-S&E fields. Multidisciplinary sciences are a separate field from 2021.
- **Suppressed cells** (D) are missing. Nothing is imputed.

**What NSF does not publish by state.** No SED table crosses state with citizenship or postgraduation plans,
so temporary-visa doctorates and stay rates exist only for the nation (state `US`):
- Temporary-visa share of S&E doctorates: 34–38% since 2015 (35.6% in 2025). Citizenship unknown (about
  2,000–3,500 a year to 2008) counts in the total, so the share is a lower bound.
- Temporary-visa doctorate recipients with definite plans who are staying in the U.S.: 61% in 1996, 77% in
  2006, 82% in 2025. 1989–1995 come from NSF's digest figures, which also check the computed rates.
- `sed_us.csv` has intent to stay by country of citizenship for 2003–2025 (2025: China 78.7% of 6,545
  temporary-visa recipients, India 86.2% of 2,715).

**Folder names are download labels.** Each file's year is read from its table title. For example:
- `tab07305.zip` is 2005, `nsf09311.zip` is 2006 and `nsf11321.zip` is 2007–2008.
- `data_tables.zip` is 2017, and the `nsf2xxxx` zips cover 2018–2025.
- `nsf15326.zip` is NSF's IPEDS-based "S&E Degrees 1966–2012", not SED, and is not used.

**Series breaks:**
- **2009:** health moved into S&E (life sciences). The parser adds an `se_excl_health` field so S&E can be
  compared across the break; the sheet uses it.
- **2009–2014:** physical sciences include math and computer science, and social sciences include psychology.
  The narrower fields are derived from the sub-columns (`note` says "derived").
- **2015:** "Humanities" became "Humanities and arts".
- **2021:** a new field taxonomy, and the tables say "research doctorate recipients". Later releases revise
  earlier years slightly, by up to about 2% (2020 all fields: 55,283 in the 2020 release, 55,200 in 2025).
  Values here are from each year's own release.

**Checks** (`data/sed/checks.csv`):
- State rows add up to the US row exactly in most years and within 0.3% otherwise, except 2000–2001, which
  are 0.3–0.5% short in the source (up to 0.9% in some fields).
- All fields equal S&E plus non-S&E in every year.
- US totals match NSF's latest national trend table within 0.4%.

**US totals:**
- **Research doctorates:** 41,011 in 1994, 55,006 in 2015, 52,250 in 2021 (the COVID dip) and 59,015 in 2025.
- **Largest states, 2025:** California 6,983, Texas 4,497, New York 4,436, Massachusetts 3,260.

**In the sheet and profiles** (`external.sed`): research doctorates (all, S&E excluding health, engineering,
math and computer science), each state's share of U.S. doctorates, and the S&E share.

**Outputs (`data/sed/`):**
- `sed_state.csv`, `sed_state_wide.csv`, `sed_us.csv`
- `files.csv`, `coverage.csv`, `checks.csv`

## USCIS H-1B Employer Data Hub (FY2009–2026)

Approved and denied H-1B petitions, by employer, from USCIS. Code in `ipeds_clean/h1b.py`; the source files
are in `sources/uscis_h1b/`, one export per fiscal year.

```bash
.venv/bin/python -m ipeds_clean.h1b        # -> data/h1b/
```

**What a row is.** Each row is one petitioning employer × city × ZIP, with counts of petitions decided in
that fiscal year. Only first decisions count; appeals and revocations are not reflected.

**Initial and continuing approvals.**
- **Initial approvals** are the closest measure of new H-1B workers: cap-lottery winners plus cap-exempt
  hires such as universities.
- **Continuing approvals** are extensions, employer changes and amendments for people already in H-1B
  status.

**One layout for every year.** Each row has six petition types, each approved or denied: new employment,
continuation, change with same employer, new concurrent, change of employer, amended. FY2009–2023 were
re-exported from the current Data Hub tool (`h1b_employer_information_fy{year}.xlsx` or `.csv`); FY2024–2026
(`h1b_datahubexport-{year}.csv`) were already in that layout. The six types are kept separately too.

**How initial and continuing are counted.** USCIS's own definition: "initial" is new employment plus new
concurrent employment, and everything else (continuation, change with same employer, change of employer,
amended) is "continuing". With that split the hub reproduces USCIS's *Characteristics of H-1B Specialty
Occupation Workers* reports (Appendix D, Table 1b of the FY2020, FY2021, FY2022 and FY2024 editions; Table 2
of the FY2025 edition) to within 0.2% in every year they cover:

| FY | Report, initial / continuing | Hub, initial / continuing |
|---|---|---|
| 2016 | 105,090 / 252,121 | 105,066 / 252,071 |
| 2017 | 96,167 / 277,225 | 96,123 / 277,175 |
| 2018 | 87,894 / 247,067 | 87,871 / 247,035 |
| 2019 | 132,986 / 256,392 | 132,978 / 256,375 |
| 2020 | 122,886 / 303,824 | 122,894 / 303,821 |
| 2021 | 123,414 / 283,657 | 123,406 / 283,635 |
| 2022 | 132,429 / 309,614 | 132,659 / 309,748 |
| 2023 | 118,948 / 267,370 | 118,952 / 267,383 |
| 2024 | 141,205 / 258,190 | 141,206 / 258,193 |
| 2025 | 114,806 / 291,542 | 114,804 / 291,543 |

FY2009–2015 have no report on this definition (editions before FY2020 split initial and continuing from a
different form question), and FY2026 has no report yet.

**Old layout, superseded.** The earlier hub's exports (initial and continuing columns only) agreed with the
re-exports to within 0.1% nationally for FY2009–2020, but the FY2021–22 ones ran 5–18% above USCIS's reports
(FY2021 initial 141k vs 123k; Massachusetts, Connecticut and New Jersey 33–37% high), and the FY2023 one was
incomplete at the source (33k rows, 38k initial approvals). They are in `sources/_duplicates_to_delete/`
(FY2009–2022 under `uscis_h1b_old_layout/`) and listed in `files.csv` as superseded (`used = no`). No
`incomplete_export` flags remain on the files in use.

**Withheld names.** A few rows a year (under 50) have a blank employer name. They count in state and U.S.
totals but not as employers.

**State is the employer's, not the worker's.** The state is wherever the petitioner filed from, which is
often headquarters. All of Amazon's petitions, for example, come from Virginia (HQ2), not Washington. Use
DOL's LCA worksite data for where the jobs are.

**Outputs (`data/h1b/`):**
- `h1b_state_wide.csv` and the long-form `h1b_state.csv`:
  - initial and continuing approvals and denials,
  - the initial denial rate,
  - the number of employers with at least one initial approval,
  - the sector mix of initial approvals (professional/scientific/technical, education, health, information,
    manufacturing, finance),
  - the top five employers' share of the state's initial approvals.
- `h1b_top_employers.csv`: the ten employers with the most initial approvals in each state and year.
- `files.csv`: rows and national totals per file.

**FY2025 figures:**
- **US:** 115k initial approvals and 292k continuing.
- **States with the most initial approvals:** California 21.6k, Texas 12.6k, New York 11.4k, New Jersey
  7.7k, Virginia 7.6k.

## DOL foreign labor certification: LCA and PERM (FY2008–2026)

Department of Labor, Office of Foreign Labor Certification (OFLC) disclosure data. Code in
`ipeds_clean/dol.py`; the source files are in `sources/dol_oflc/`.

```bash
.venv/bin/python -m ipeds_clean.dol        # ~30 s from the cache in cache/dol/ (first read ~25 min)
.venv/bin/python -m ipeds_clean.dol lca    # or perm
```

**The two programs:**
- **LCA (Labor Condition Applications):** the employer's filing that comes before an H-1B, H-1B1 or E-3
  petition. Each application lists the worksite, occupation and offered wage.
- **PERM (permanent labor certification):** the employer step of most employment-based green cards.

**State is the worksite, the first listed.** This is the main difference from the USCIS hub, which uses the
employer's address. For FY2024 H-1B positions:
- Washington: 74k by worksite, 104k by employer address.
- New Jersey: 33k by worksite, 76k by employer address.

The employer-state version is kept as `*_emp_state`.

**What counts as certified:**
- **LCA:** CERTIFIED plus CERTIFIED-WITHDRAWN, because those applications were approved and could support a
  petition. Certified-only counts are kept as `*_certonly`. OFLC's Selected Statistics PDFs record status at
  each quarter's close, so they fall between the two:
  - Applications: the main count runs 0.5–4.8% above the PDFs.
  - Positions: 0.5–3% above.
- **PERM:** CERTIFIED plus CERTIFIED-EXPIRED. This matches the PDFs exactly for FY2017–2023 and FY2026,
  including the top-state counts. FY2024 is 42 cases low and FY2025 0.25% low.
- **Full comparison:** `data/dol/checks.csv`.

**Quarterly files.** From FY2020, most quarterly files hold only that quarter's decisions, but some repeat
earlier quarters:
- FY2021 Q3 repeats Q1–Q2.
- FY2023 Q2 repeats Q1.
- The FY2026 file is year-to-date.

Cases are de-duplicated by case number, keeping the latest file. After that, total LCA decisions match the
PDFs exactly (FY2024: 561,037).

**FY2026 is partial.** It runs through Q3 (June 2026) and has `partial = 1` in the wide files.

**Gaps by year:**
- **FY2008 and part of FY2009 (LCA):** the old eFile system uses DOT occupation codes, not SOC, so the STEM
  and occupation measures start in FY2009.
- **FY2010 (LCA):** no visa-class column, so the H-1B-only measures are blank. The all-visa `lca_*` measures
  cover it.
- **H-1B-dependent employer flag:** FY2015 on only.
- **PERM new form (FY2024 new-form file, FY2025, FY2026):** it drops country of citizenship, class of
  admission and education. Those measures end with FY2024 and cover only old-form cases that year. About
  4% of new-form cases have no worksite state and are counted in the US total only.
- **Column mapping:** column names change across vintages; `data/dol/columns.csv` maps them.

**Measures.**
- **LCA:**
  - Certified applications and positions, for all visa classes and for H-1B only.
  - Positions by SOC major group.
  - STEM positions and share, using the same STEM occupation definition as the ACS module.
  - Median annualized offered wage.
  - The share of positions at H-1B-dependent employers.
- **PERM:**
  - Certified cases.
  - The STEM share.
  - India, China and other citizenship, with shares.
  - The worker's education and the job's required education (master's, doctorate).
  - The worker's class of admission (F-1, H-1B, L-1, not in the US).
  - Median offered wage.

**FY2024 figures:**
- **H-1B (US):** 795,657 certified positions on 534,037 applications. 80% of positions are STEM, and the
  median offered wage is $112,882.
- **Top H-1B worksite states:** California 186k, Texas 114k, Washington 74k, New York 61k, Illinois 35k.
- **PERM (US):** 101,994 certified. India accounts for 47% of FY2024 cases on the old form and 52% in FY2023.
- **F-1 to green card:** 8.7% of FY2024 PERM certifications were for workers in F-1 student status, up from
  3.6% in FY2015. H-1B holders were 66%.

**Outputs (`data/dol/`):**
- `lca_state.csv`, `lca_state_wide.csv`
- `perm_state.csv`, `perm_state_wide.csv`
- `files.csv`: every file in `sources/dol_oflc/`, used or not and why. PW, H-2A, H-2B, CW-1, the state PDFs and the
  multi-worksite appendices are listed but not parsed.
- `columns.csv`, `checks.csv`

## USPTO patents, PatentsView (grant years 1976–2025)

Granted patents by the state of the patent owner (the assignee). Code in `ipeds_clean/patents.py`; the source
files are in `sources/uspto_patents/`. They are the PatentsView annualized files built from the 12/31/2025 release, and
the variable definitions are in `data_dictionary_PVANNUAL.xlsx`.

```bash
.venv/bin/python -m ipeds_clean.patents    # -> data/patents/  (~20 s)
```

**What a state's count means.** Rows are patent × assignee, and the location is the assignee's. So a state's
count is patents owned by organizations or people located there, not patents by inventors who live there.
Two counts are kept:
- `patents` (whole count): a patent with owners in two states counts once in each.
- `patents_frac` (fractional count): each patent is split evenly across its owners, so the states add up to
  the US total.

**What's left out:**
- Patents with no assignee (about 5%, mostly individual inventors who kept the patent) have no location.
- `year_missing.zip`, patents with no grant year.

**Years:** every grant year from 1976 to 2025 is present. 1994 and 2019 arrived later, from the `misc data` download.

**Technology fields** use the patent's first WIPO technology field, and the profiles group them:
- **Digital:** computer technology, digital communication, telecommunications, basic communication processes,
  IT methods, audio-visual.
- **Semiconductors:** semiconductors, micro- and nano-technology.
- **Life sciences:** biotechnology, pharmaceuticals, medical technology, analysis of biological materials,
  organic fine chemistry.
- **Energy and environment:** electrical machinery and energy, environmental technology, engines.
- `patents_state_field.csv` has all 35 fields, so the groups can be redefined.

**Outputs (`data/patents/`):** `patents_state_wide.csv` and the long-form `patents_state.csv` have, by state
and grant year:
- patents, as both whole and fractional counts,
- the number of distinct assignees,
- mean team size,
- the share of patents with a woman inventor, and women's share of inventors,
- the share of patents owned by individuals,
- the share in each technology group,
- the state's share of US-assignee patents.

**2025 figures:**
- **US assignees:** 135.6k patents.
- **Largest states:**
  - California: 43.1k, 32% of the US.
  - Texas: 11.0k.
  - New York: 7.8k.
  - Massachusetts: 6.3k.
- **Technology mix:**
  - Digital: 62% of California's patents and 71% of Washington's.
  - Life sciences: 45% of Massachusetts'.
  - Energy and engines: 15% of Michigan's.

## More pipeline sources (added November 2026)

Each source below has its own module. `python -m ipeds_clean.<module>` rebuilds its folder in `data/`, and each folder
includes `files.csv` (every input file, used or not) and `checks.csv`. The raw files are in `sources/`; how the
`New Data` download was sorted is logged in `sources/new_data_moves.csv`. Byte-identical duplicates are in
`sources/_duplicates_to_delete/`. Saved web-page shells (`.htm`, `.html`, `.asp` pages with no data) are in
`sources/_web_pages/`.

**K-12 preparation**
- **Digest of Education Statistics, state tables** (`digest_k12`, NCES; `python -m ipeds_clean.digest_k12`). Every
  edition 1995–2025: the 2013+ table numbers in `reference/digest/{edition}/` (`.asp` and `.html` copies), the
  1995–2012 equivalents found by title in the Digest catalog, and the Excel downloads in
  `sources/nces_digest_tables/`. For each state and year the latest edition that prints it is kept (by edition, then
  the "prepared" date; `edition` and `file` are recorded). Projected columns become a separate `_proj` measure from
  the one edition that projects furthest, after each state's last actual year. Years are the spring of the school
  year; fall counts keep the fall year. Dollars are deflated to 2024 dollars with the project's CPI-U.
  - `data/digest_k12/k12_state.csv` (+ `_wide`): per-pupil current spending (236.65, 1970–2021), ACGR (219.46,
    2011–2019 and 2022; the Digest prints 2019-20 and 2020-21 only by student group), AFGR (219.35, 219.40–41,
    1991–2013, 2019, 2023–24), teacher salary (211.60, 1970, 1980, 1990, 1992–2022), enrollment (203.20, fall
    1980–2024; PK-8 203.25 and 9–12 203.30 from 1990), public high school graduates (219.20, 1970–2024, projected to
    2032), free or reduced-price lunch share (204.10, 2001–2023), English-learner share (204.20, 2001–2022; before
    2010-11 partly students in EL programs), IDEA share (204.70, 2012–2023), teachers and pupil/teacher ratio (208.40,
    fall 1991–2022), charter enrollment share (216.90, 2000–2023), event dropout rate (219.50, 4 years).
  - `data/digest_state/postsec_state.csv` (+ `_wide`): first-time students' residence and migration (309.10 all,
    309.20 recent high school graduates, 309.30 the same in 4-year colleges; falls 1992–2022, read from
    `data/ipeds/digest/values.parquet`): enrolled in the state, residents enrolled anywhere, stayers, out- and
    in-migrants, net, `leave_share` (residents enrolled out of state / residents enrolled anywhere) and
    `instate_share` (matches the IPEDS `instate_share_ft`).
  - `data/digest_k12/files_excel.csv`: every Excel file with its table, title, edition (matched to the HTML copy with
    the same prepared date), latest data year, md5, `duplicate_of`, `html_copy` and used/why. Every Excel file has an
    HTML copy of the same edition in `reference/digest/`, so the Excel copies back up the HTML parse. Exact
    duplicates (same table and content) were moved to `sources/_duplicates_to_delete/nces_digest_tables/`.
  - Skipped (reason in `files_excel.csv`): NAEP tables (data/naep covers them), ACS and Census tables, BLS OEWS
    teacher wages, single-year descriptive tables, and the postsecondary tables IPEDS already gives the state panel.

- **Civil Rights Data Collection** (`crdc`, `crdc_tables`, U.S. Department of Education, Office for Civil Rights).
  School-level files for 2009-10, 2011-12, 2013-14, 2015-16, 2017-18, 2020-21, 2021-22 and 2023-24
  (`python -m ipeds_clean.crdc`). OCR's published state tables add 2000-01, 2004-05 and 2006-07 (projections),
  2009-10 (weighted estimates) and 1970-71, 1980-81 and 1990-91 (archive district files, weighted sums)
  (`python -m ipeds_clean.crdc_tables`, which also rebuilds the combined file).
  - **Measures:** the share of public high schools (students in each of grades 10–12, so 10–12 schools count) offering calculus, advanced
    math, Algebra II, geometry, physics, chemistry, biology, computer science (2020-21 on), AP (overall, math,
    science, computer science), dual enrollment (2013-14 on) and IB; enrollments per 100 students; SAT/ACT takers;
    gifted and talented students per 100 students (all schools).
  - **`data/crdc/crdc_state_wide.csv`** has every year, with a `source` column: school-level files where they are
    a universe; for 2009-10 counts from OCR's estimates and shares/rates from the sampled schools (the sheet and profiles leave 2009-10 out); published tables
    only for years with no school-level file (mostly counts, gifted per 100, AP math/science enrollment).
  - **2009-10 was a sample** of about 7,000 districts. The public file has no weights, so its school-level shares
    lean toward large districts (AP offering reads about 6 points higher than 2011-12).
  - **Data handling:** reserve codes are treated as missing. 2009-10/2011-12 column names are mapped to the 2013-14
    names using OCR's crosswalk. In 2023-24, -9 is read as "No" for AP and IB, because that file has no "No" values.
  - **Definition changes:** AP math includes AP Precalculus from 2023-24. Geometry covers grades 7–12 through
    2013-14. 2009-10 race detail is not kept (most districts reported 5 categories). Pre-2009 surveys were
    district samples, and their survey year Y is read as school year Y–(Y+1).
  - **State tables:** `data/crdc_tables/` holds `files.csv` (md5, duplicates, what each file is), the tidy
    `crdc_tables_long.csv` (every table, including discipline and harassment), `crdc_tables_wide.csv` and
    `checks.csv`. Exact duplicates were moved to `sources/_duplicates_to_delete/crdc_state_tables/`.

**International students and their first jobs**
- **ICE SEVIS FOIA releases** (`ice_foia`): OPT employment records 1998–2018, STEM OPT extension requests
  2008–2017, and F-1 students in public high schools 2004-05 to 2016-17.
  - **The OPT file is cut off.** It stops at Excel's 1,048,575-row limit, so counts are lower bounds, and only the
    shares are reliable.
  - **Retention:** the share of OPT records whose employer is in the school's state. Employer state is mostly
    missing before 2008.
  - **STEM OPT files:** they have no location columns, so they are counted by the school's state.
  - **School states:** these come from matching school names to the IPEDS directory (`school_states.csv`, 98.5%
    matched).
- **J-1 exchange visitors** (`j1`, State Department BridgeUSA): participants by site-of-activity state and program
  start year, 2015–2025, all categories combined. The national category and country tables flag the "talent"
  categories.

**Graduates: do they stay, and what do they earn?**
- **Census Post-Secondary Employment Outcomes** (`pseo`): release R2026Q2, statewide rows for 37 states plus DC.
  - **Measures:** the share of each graduating cohort employed in the institution's state 1, 5 and 10 years out,
    by degree and STEM vs not, plus median earnings.
  - **Destinations:** PSEO reports only "in state" vs Census division, not the destination state
    (`pseo_destinations.csv` is state → division).
  - **Coverage:** coverage of each state's bachelor's degrees is in `coverage.csv`. It is near full in MD, NM, VA,
    SC, NJ, IN and TX, and partial in NY, MA, PA, MI and DC.
- **College Scorecard** (`scorecard`, API key `COLLEGE_SCORECARD_API_KEY` in `.env`; dictionary in
  `reference/college_scorecard/`).
  - **Contents:** the latest release for 6,118 institutions and 215,000 programs. It gives median earnings
    10 years after entry and 1 year after completion, median completer debt, completion and Pell shares, and
    program earnings 1 and 5 years out by level and STEM vs not.
  - **History** (`python -m ipeds_clean.scorecard history`): the API's year-keyed fields for earnings 10 years
    after entry, completer debt, 4-year completion, Pell share and undergraduate enrollment, every year with
    values (`scorecard_state_years.csv`). The year is the data file's (`MERGED<year>_<year+1>`), not the cohort.
    `cohort_map.csv` gives what each year measures (2025 completion = fall 2019 entrants; 2024 debt = FY2024–25
    completers). The sheet labels each year that way. Only institutions in the current file are served, so the
    early years leave out closed institutions.
  - **State values:** these are medians of institution or program medians, weighted by the number of students
    measured.
- **ACS migration by education** (`acs_migration`): tables B07009 (residence now) and B07409 (residence a year ago),
  from the `data.census.gov` downloads plus the Census API for 2010–2017 B07409.
  - **Measures:** bachelor's-plus and graduate-degree adults moving in from and out to other states, the net
  (and per 1,000 residents), and arrivals from abroad, 2010–2025.
  - **Check:** states' summed inflows equal their outflows every year.

**Green cards and citizenship**
- **DHS Yearbook of Immigration Statistics** (`dhs_yearbook`): a PDF yearbook for every year FY1996–2022 (INS
  1996–2002, DHS 2003–22; tables extracted to `data/dhs_yearbook/pdf_tables/` for audit), Excel tables for
  FY2023–24, and in `sources/dhs_yearbook/excel/` the yearbooks' own Excel tables (zips for FY1996 and
  FY1998–2021 incl. the supplemental tables, FY2020–22 workbooks, `tables8-11newadj` FY2006–2023). Excel is used
  wherever a release has it (exact cells); the PDF is the fallback. Each fiscal year uses its latest edition;
  `release_fy` and `source_file` record which. Every file, zip member and sheet is listed in `files.csv` and
  `excel_files.csv` (used / why not).
  - **Measures:**
    - new green-card holders by state of residence, FY1988–2024 (no gaps);
    - refugees and asylees granted green cards by state, FY1987–2001;
    - naturalizations by state, FY1986–2024 (no gaps);
    - I-94 admissions by destination state, FY1996 and FY1998–2024: principal classes (F-1/M-1, J-1, L-1, H-1/2/3,
      TN, ...) in FY1996–2004 and DHS broad groups (students and exchange visitors, temporary workers) in FY2005–24;
    - every class of admission by state (H-1B, F-1, J-1, L-1, O-1, TN, ...) for FY2002 (Table 611) and FY2005–20,
      FY2022–24 (Nonimmigrant Supplemental Table 3); sheet measures `dhs_i94_h1b`, `dhs_i94_f1`, `dhs_i94_j1`
      and their shares of U.S. admissions, plus L-1 and O-1 shares;
    - national LPRs by class and country (new arrivals vs adjustments FY2006–24).
  - **What's not available:** no yearbook table (PDF, Excel or supplemental) splits green cards by state and class
    of admission; the LPR supplemental tables are state × country of birth, metro areas and orphan adoptions. So
    employment-based green cards are national only. No class-by-state I-94 table exists here for FY1997, FY2003–04
    (beyond the INS principal classes) or FY2021 (no FY2021 nonimmigrant supplement in the folder).
  - **I-94 counting:** admissions count entries, not people. DHS counted land admissions more completely from
    FY2010 and Canadian air/sea admissions from FY2013–14, and COVID-19 cut FY2020–22, so compare counts only within
    FY2010–12, FY2014–19 and FY2022 on; the sheet's shares of U.S. admissions are comparable across years.
  - **Checks:** every PDF has a usable text layer (none scanned). Excel and PDF agree cell for cell except FY2004
    Table 28 (326 admissions shifted between temporary and NAFTA workers in the Excel; Excel used) and a few single
    cells (`excel_vs_pdf.csv`). The class-by-state tables' U.S. H-1B, F-1, J-1, L-1, O-1 and TN equal the national
    tables, and the supplemental state × country-of-birth totals equal Tables 4 and 22 except FY2003–04.
    Two zip members are truncated and unreadable (LPR2001 `Table6.xls`, NATZ2000 `Table48.xls`; national tables).
  - **Data notes:** FY2023–24 values are rounded to the nearest 10. Editions revise FY1996–2007 noticeably (e.g.
    "Other" territories); `checks.csv` lists every disagreement between editions.

**International students' economic value**
- **IIE Open Doors state fact sheets** (`open_doors`): editions 2020–2026 (international students
  2019/20–2025/26; study abroad 2017/18–2024/25). The 2020 sheets' pages sum to Open Doors' national total
  (1,075,496).
  - **Measures:** international students hosted, % change and rank, estimated spending, top places of origin
    (shares), top host institutions, U.S. students studying abroad, and State Department program counts.
  - **The 2026 edition** (`OD26_State-Sheets_All-States.pdf`) was received pre-release; the embargo has lifted
    and it is used like the other editions.
  - **Fall 2026 NAFSA/JB outlook** (`Fall_2026_..._NAFSA_JBI.pdf`): national projections only, no state
    figures. Inventoried in `files.csv`, not parsed.
  - **Unrelated paper:** two copies of a research paper that had been downloaded with these files
    (`In_the_Moment_and_Over_Time*.pdf`) are now in `sources/_not_data/`.
- **NAFSA International Student Economic Value** (`nafsa`): academic years 2018-19 to 2024-25 (2020-21 from
  `isev_EconValue2020_2021.pdf`: 914,095 students, $28.4B, 306,308 jobs; the state rows sum to the total),
  giving students, economic contribution (printed rounded) and jobs supported. Michigan's 2021-22 figure is
  corrected from NAFSA's misprinted $695.5M to $965.5M.
- **SEVIS by the Numbers reports** (`sevis_reports`): annual reports for every calendar year 2018–2024, plus the
  June 2017 biannual report (a May 5, 2017 snapshot, kept as `active_students` and never mixed with the
  calendar-year `records`).
  - **What they don't have:** a full 50-state table. No report has one, in text or in an image. What exists are
    regional top-3 tables, state figures quoted in the text, SEVP-certified school counts, and an image of the
    top five states. That image is read by OCR with the macOS Vision framework (cached in `ocr_raw.csv`), and a
    count is kept only when it agrees with its printed share.
  - **National series:** OPT, STEM OPT and CPT (CY2017–24; Jan 1/Aug 1 OPT counts 2012–17); F-1 to H-1B
    change-of-status approvals, FY2012–17 (all, and from STEM OPT; national only); STEM students and share (May
    2017); China and Hong Kong students by school level (2012). Every extracted table is in `pdf_tables/`.

**Research funding**
- **NSF Higher Education R&D Survey** (`herd`): FY2010–2024, plus FY2003–09 totals from the predecessor
  survey.
  - **Measures:** university R&D by state, by source, field and federal agency, plus personnel.
  - **Built by summing institutions:** federal-by-agency by state (and FY2024 source and field) are summed from
    the institution rankings, and they match the state totals exactly.
  - **Revisions:** each year uses its own release, and the FY2024 release's revised series is kept as
    `rd_exp_rev`.
- **NSF Survey of Federal Funds for R&D** (`ffs`): R&D and R&D-plant obligations by state of performance,
  FY1985–2024. By agency and by performer, FY2004–24. Each year takes the latest volume that reports it;
  `all_own_volume` matches that volume's breakdowns. There is a break at FY2021, when coverage widens and FFRDCs
  move under intramural.
- **USAspending** (`usaspending`, public API, cached in `cache/usaspending/`): FY2008–2026 by place of
  performance.
  - **Measures:** all grants and all contracts, plus an R&D subset: NSF, NIH, NASA and DOE Science grants, and
    contracts with an R&D product/service code.
  - **Incomplete years:** FY2026 grants are incomplete and left out of the sheet. A re-pull on 2026-11-11
    (`REPULL` in the module; `pulls.csv` compares it with the 2026-11-10 pull) left them unchanged: $311B against
    FY2025's $1,245B, with HHS (including all of NIH) almost absent and NSF at 73% (`completeness.csv`, by
    agency). FY2026 contracts ($802B vs $814B) are kept, as provisional. The re-pull revised contract totals for
    every year down 1–2%; grants did not change.
  - **The two downloaded files are not used:** the 5 GB database subset needs a Postgres restore, and the FY2027
    file has one month of contracts.

**STEM jobs**
- **BLS Occupational Employment and Wage Statistics** (`oews`), 1999–2025:
  - **Measures:** STEM jobs (same occupation codes as the ACS and DOL rows), STEM share, location quotient, mean
    wage, an approximate median, and key occupations including software developers.
  - **Occupation codes:** the occupation classification changes in 2010, 2012, 2019 and 2021, and `coverage.csv`
    lists the codes used each year. 1997–98 use pre-SOC codes and are not used.
  - **Checks:** state sums match the national file to within 0.1%.

## State-by-state measures and maps

`python -m ipeds_clean.states` builds `data/states/state_panel.csv` (long: state × year × measure,
plus `state = "US"` national rows), `state_table_{2010,2023}.csv` (one row per state) and the maps in
`data/states/figures/png/` (300 dpi) and `data/states/figures/svg/` (vector).

**Geography and universe:** states are where the institution is located. The universe is
degree-granting institutions in the 50 states + DC, Title IV from 1996. Dollars are in constant 2024
dollars (CPI-U). Measures are built from pooled counts and dollars, so they are proper state
aggregates, not averages of institution rates.

| measure | years | note |
|---|---|---|
| `enroll_total`, `share_public`, `share_forprofit`, `share_parttime`, `share_grad` | 1980–2024 | fall headcount |
| `share_online_only` | 2012–2024 | exclusively distance education |
| `bach_per_100_ug` | 1985–2025 | bachelor's awarded ÷ prior-fall undergraduates |
| `tuition_pub4_instate` | 1980–2023 | sticker price, undergraduate-enrollment-weighted |
| `approp_per_fte`, `tuition_reliance_pub` | 1985/2001–2024 | public institutions; FY t over fall t−1 FTE. Colorado's College Opportunity Fund stipends are recorded as tuition |
| `grad_rate_bach6`, `grad_rate_2yr` | 1997–2024 | survey year; cohorts entered 6 / 3 years earlier |
| `faculty_salary` | 1980–2024 | 9/10-month contracts, as in Digest 316.10 |
| `instate_share_ft`, `net_migration_ft` | 1986–2024 | from residence of first-time students |

**International talent and field mix** (follows the 2026 US Talent Report, chapters 1–2):
- **Measures, by level** (`bach`, `master`, `doc` = research doctorates):
  - `intl_share_{level}` and `intl_share_stem_{level}`: international (US nonresident) share of degrees.
  - `intl_share_{cs,eng,math,phys,bio}_{master,doc}`: international share by field, for fields with
    at least 30 awards.
  - `stem_share_{level}` and `field_share_{cs,eng,math,bio,phys,health,business}_{level}`: the field
    concentration of each state's degrees.
- **Measures, not by level:**
  - `share_of_us_intl_stem_master` and `intl_stem_master_count`: where international STEM master's
    graduates are trained.
  - `stem_master_per_doc`.
  - `intl_share_enroll_{ug,grad}`: fall enrollment.
  - `foreign_share_ft`: first-time students whose home is abroad.
- **STEM definition:** CIP-2020 families 03, 04, 11, 14, 15, 26, 27, 40 (`states.STEM_CIP2`).
- **Check against the report:** national values reproduce its Table 1.01 international shares within
  0.8 pp in 1995 and 2025. STEM shares of all degrees run about 1 pp low, because the report flags
  STEM at the 6-digit level. Doctorate shares differ because the report uses the SED.
- **Online universities:** institutions that enroll mostly online students nationwide (WGU in UT, UMGC
  in MD, SNHU in NH) dominate their states' field and international measures.

Maps are saved as 300-dpi PNG plus SVG. The maps are tile grids, one equal square per state, so DC and Rhode Island weigh the same as Texas:

```python
from ipeds_clean import states
sp = states.panel()
states.tile_map(sp, "approp_per_fte", 2024)              # level, single-hue scale
states.change_map(sp, "enroll_total", 2010, 2023)        # % change (points for % measures), red/blue
states.map_grid(sp, "share_online_only", [2012, 2016, 2020, 2023])   # small multiples, shared scale
states.wide(sp, 2023)                                    # the table behind any map
```

Color scales clip at the 5th and 95th percentiles; the clipped ends are marked ≤ / ≥.

### Outside sources in the sheet and profiles

`ipeds_clean/external.py` reads each outside source's CSVs and reshapes them for the State Talent Sheet,
the web profiles and the PDF profiles:
- One function per source sets its measures, titles, units, notes and source line.
- `states_explorer.full_panel()` combines them with the IPEDS panel and SEVIS. The sheet, the profiles and
  the PDFs all use it.
- A source whose outputs are missing is skipped.

| Rail group | Measures |
|---|---|
| K-12 preparation (NAEP) | grade 4 and 8 math and reading scores; Proficient and Advanced shares; 90th-percentile score; grade 8 science |
| Graduate students & postdocs (NSF GSS) | S&E graduate students and postdocs, total and temporary-visa (states 1994–2016) |
| Doctorates (NSF SED) | research doctorates (all, S&E, engineering, math and CS); share of U.S. doctorates; S&E share |
| H-1B jobs & green cards (DOL) | certified H-1B positions by worksite; STEM share; median wage; H-1B-dependent share; PERM certifications; India, F-1, graduate-degree and STEM shares |
| H-1B petitions by employer (USCIS) | new and continuing approvals; denial rate; sector mix; top-five concentration |
| Workforce: foreign-born STEM workers (ACS) | STEM workers; foreign-born shares (all, graduate degree, doctorate, recent arrivals, India); noncitizen share; foreign-born share of residents and of graduate-degree holders |
| Patents (USPTO) | patents (fractional); share of U.S.; digital, life-science and semiconductor shares; women's share of inventors |
| K-12 preparation (NCES Digest, CRDC) | per-pupil spending; graduation rates (ACGR, AFGR); teacher salary; enrollment; high schools offering calculus, physics, chemistry, Algebra II, computer science, AP, dual enrollment; AP, calculus, physics and SAT/ACT per 100; gifted per 100 |
| Do graduates stay? (Census PSEO) | bachelor's, STEM, master's and doctoral graduates working in the state 1, 5 and 10 years out; median earnings |
| Graduate migration (ACS) | net domestic migration of bachelor's-plus and graduate-degree adults (count, per 1,000); in and out rates; arrivals from abroad |
| Graduate earnings & debt (College Scorecard) | earnings 1 and 10 years out; STEM and non-STEM bachelor's earnings and premium; master's STEM earnings; debt; completion; Pell share |
| OPT: international graduates' first jobs (ICE) | OPT retention overall, bachelor's, master's, STEM; employer-to-school ratio; STEM OPT approvals |
| Exchange visitors (J-1) | J-1 participants by state |
| Green cards & citizenship (DHS) | new green-card holders; naturalizations; share of U.S.; student and exchange admissions share (FY2005–24) and F-1/M-1 share (FY1996–2004); temporary-worker admissions share (FY2005–24); H-1B and F-1 admissions (FY2023–24) |
| STEM jobs & wages (BLS OEWS) | STEM jobs, share, location quotient, mean and approximate median wage; software developers; all-occupation wage |
| International students' economic value (IIE, NAFSA) | international students hosted; study abroad; economic contribution; jobs supported |
| Research funding (NSF HERD, Federal Funds, USAspending) | university R&D (total, share of U.S., federal/business/state shares, math & CS, engineering, personnel); federal R&D obligations (total, universities, DOD, HHS); research grants and R&D contracts |

**Rules shared by every source:**
- **Every value is kept,** for every year a state has it, so a state missing a year is blank only in that
  year.
- **Latest year:** a measure's latest year is the last year any state reports it. National-only years (GSS
  after 2016) stay in the trend charts.
- **Measures no state reports** (SED citizenship, for example) are left out of the sheet and are described
  in the notes.
- **The U.S. line:** profile charts draw it only where it is comparable with a state (shares, scores and
  wages). For counts and "share of U.S." measures, the U.S. value is given in the note.
- **NAEP lines** may span gaps of up to five years, because NAEP is assessed every two to four years.
- **Score changes** are in points.

**Where they appear:**
- **Web profiles:** five sections (K-12 preparation, graduate research, H-1B jobs and green cards, STEM
  workforce, patents), with charts for the state and its comparison states and each state's top H-1B
  employers.
- **PDF profiles:** two-page spreads in the same order. They cover K-12 preparation, graduate research, do
  graduates stay?, research funding, H-1B jobs and green cards (two spreads), STEM workforce, and patents.
- **Web profiles:** the "Do graduates stay?" section (PSEO, OPT, migration, College Scorecard) and research
  funding in the graduate-research section. Single-release measures (College Scorecard earnings 1 year out and program earnings) are drawn as bars
  comparing the state, its comparison states and the U.S.

### Interactive HTML pages (local)

```
python -m ipeds_clean.states_explorer          # data/states/sheet.html: the State Talent Sheet (explorer.html redirects)
python -m ipeds_clean.state_profile CA         # data/states/profiles/CA.html (+ profiles/data/CA.json)
python -m ipeds_clean.state_profile --all      # all 50 states + DC, and profiles/index.html
python -m ipeds_clean.international           # data/states/international.html
cd data/states && python -m http.server 8765   # then open http://localhost:8765/sheet.html
```

**State Talent Sheet** (`sheet.html`): pick a state and up to seven competitor states (defaults to the
four closest in enrollment; "Nearby" uses the map neighbours). Every measure is a row and every state a
column, with the U.S. last. Each cell shows a value, rank, sparkline and change since the base year;
switch cells to "Change since base year" or "Rank". Choose base and latest years and the degree level.
Click a row to open its comparison panel: a trend for the chosen states against the U.S., all 51
states ranked (Play replays the ranking year by year), a map, and a scatter against any other measure.
Clicking a state in a chart adds or removes it. Export CSV saves the visible sheet. Rows marked (SEVIS) come from DHS SEVIS by the Numbers (see the SEVIS section): their
year label names the snapshot month, their panel carries a DHS source line, and they skip the IPEDS
provisional mark and the online-university flag. The **Flows** view
draws three animated Sankey diagrams for any chosen state: degrees by level, then domestic or
international graduates, then field; where first-time students come from; and where the state's
residents enroll. Its data (`flows`, `pipeline`) comes from `state_profile.flows_all` / `pipeline_all`.

**Peer sets.** "Compared with" opens a menu of suggested competitor sets; editing the chips by
hand makes the set "Custom", and changing the state reapplies the chosen set. Built by
`ipeds_clean/peers.py` (`python -m ipeds_clean.peers` rebuilds the attribute table):

| set | how states are chosen | source |
|---|---|---|
| Similar enrollment | 4 closest in fall enrollment | IPEDS |
| Biggest student exchange | most first-time students sent and received | IPEDS residence |
| Similar international reliance | closest on intl share of grad students and STEM master's | IPEDS |
| Similar STEM focus | closest on STEM share of bachelor's and master's | IPEDS |
| Similar public funding | closest on appropriations per FTE and public 4-year tuition | IPEDS |
| Leaders in international STEM talent | top 4 by international STEM master's | IPEDS |
| Same region | same Census division (topped up from the region) | Census Bureau |
| Similar economy size | 4 closest in 2024 GDP | BEA via FRED (`<ST>NGSP`) |
| Similar output per person | 4 closest in 2024 GDP per resident | BEA + Census via FRED (`<ST>POP`) |
| Similar 2024 presidential vote | 4 closest 2024 R−D margin | MIT Election Lab, 2024-elections-official |

The outside attributes (`reference/state_attributes/state_attributes.csv`, raw downloads in
`reference/state_attributes/raw/`) are used only to choose comparison states; they are never shown
or analysed as measures.

**Institution detail** (in every profile): an "Every institution" table (search, sort) in the Institutions
section, and every institution bar or bubble is clickable. Each opens a side panel with directory and Carnegie
data, enrollment and international shares, admissions, price, aid, retention and graduation, degrees by level
(international and STEM), largest fields, trends, faculty and finance. Data: `python -m ipeds_clean.inst_detail`
writes `profiles/data/inst/<ST>.json`.

**Printable State Talent Profile:** a booklet in the style of the 2026 US Talent Report, in two formats.

| Format | File | Pages | Use |
|---|---|---|---|
| Digital | `profiles/pdf/<ST>.pdf` | an 8.5×11 cover, 17×11 two-page spreads (pages 2–3, 4–5, …), then 11×8.5 landscape By the Numbers pages | reading on screen |
| Print | `profiles/pdf/<ST>_print.pdf` | every page 8.5×11 | printing as a booklet |

**Contents.** At a glance, International dependence, STEM, Where students come from, Migration, then the
outside sources (K-12 preparation, Graduate research, H-1B jobs and green cards, STEM workforce, Patents).
These are followed by Competitors, Fields, Students and money, Outcomes and faculty, Institutions with data
notes, and By the Numbers. Layouts are measured so nothing overruns a page, and small states get extra
figures where there is room.

**Single-page figures** (facing pages, rather than one chart across the spread) carry exactly one figure or
one table each, in one layout: the figure or table fills the top 65% of the live area (inside the 1-inch
margins) and the text the bottom 35%. The text has "About this figure", which says what the figure shows and
how its measure is defined, and "The numbers", a list of values with their change from the previous report
and since 2015, the U.S. figure and the state's rank. It reports the data; it does not interpret it. Charts
are drawn to fill their 65%, and table rows are spaced to fill it; where the text runs long, its last items are
dropped, then its type steps down, until it fits its 35%.

**By the Numbers** is a table on landscape pages, grouped by topic in pipeline order, not by source: K-12
preparation; enrollment and institutions; degrees and fields of study; international students; graduate
education and research; college costs and outcomes; where students and graduates go; work visas and green
cards; STEM workforce and innovation. Each topic starts with its own header row; a topic cut by a page break
repeats its header, marked "continued", on the next page, and no page ends on a header with no rows under it.
- **Columns:** measure, 2015 value, latest value (superscripts give each year observed), change since 2015,
  latest U.S. value, U.S. change since 2015, the state's rank, and a source number. The measure column is wide
  enough that nearly every name fits on one line.
- **Rows left out** because another row already says the same thing: NAEP grade 8 math advanced share and
  90th percentile; the averaged freshman graduation rate (ACGR kept); Scorecard enrollment, 4-year completion
  rate and STEM earnings premium (IPEDS enrollment and graduation rate kept; the premium is the difference of
  two rows shown); SED's S&E share of doctorates (IPEDS STEM share kept); Open Doors' international student
  count (SEVIS kept); DHS H-1B, F-1 and J-1 admission counts (their shares kept) and the INS F-1/M-1 share
  (ends 2004); the USAspending total (grants and contracts kept); the 4-year out-of-state share (all-college
  share kept); the net migration count (per-1,000 rate kept); BLS's approximate STEM median wage and STEM share
  of jobs (mean wage and the ACS share kept). They stay in the State Talent Sheet and the CSVs.
- **Sources** follow the tables on one page: every data source as a Chicago-style bibliography entry,
  alphabetical, numbered [1], [2], … in the order the source column uses.

**The print version** is made from the digital PDF, in order for double-sided printing on 8.5×11 sheets:

| PDF page | Content | Sheet |
|---|---|---|
| 1 | cover | sheet 1, front |
| 2 | "This page intentionally left blank." | sheet 1, back |
| 3–4 | folios 2 and 3 | sheet 2, front and back |
| 5–6 | folios 4 and 5 | sheet 3 |
| … | … | … |

- Each spread is cut at the gutter into its left and right pages. The printed folios and the table of
  contents are unchanged.
- The landscape By the Numbers pages are turned a quarter turn onto 8.5×11 pages, top of the table toward
  the left edge, so every page of the booklet is the same size; turn the booklet to read them.
- If the page count is odd, a final "intentionally left blank" page completes the last sheet.
- A page with nothing on it, such as a page with no figure for a small state, also carries the
  "intentionally left blank" line, in both formats.
- Print double-sided, flipping on the long edge.
- The two halves of each spread share one copy of its content, so a print PDF is no larger than the digital
  one.

**Fonts are fully embedded, so the PDFs pass print-shop preflight checks** such as Vistaprint's "non-embedded
fonts" check.
- **Why Type3 appeared:** the template's Montserrat and EB Garamond are variable fonts. Chrome writes text set
  in a variable font as Type3, which print services treat as non-embedded.
- **The fix:** `state_pdf.py` makes a static TrueType instance of each weight used (Montserrat 300–900, EB
  Garamond 400–800), caches them in `cache/fonts/`, and embeds those. Each instance has its own name, such as
  `Montserrat-Bold`.
- **Change arrows:** the ▲ ▼ arrows in By the Numbers are drawn as small SVG triangles. Montserrat has no
  such glyphs, and the system-font fallback would also print as Type3.
- **Checking it:** every font in all 102 PDFs is an embedded TrueType subset.

**Viewer and downloads.**
- "View PDF" on each profile opens `profiles/viewer.html#<ST>`. There, a Digital | Print switch picks the
  format to view, download, or download for all states.
- `viewer.html?format=print#TX` opens on the print version.
- The zips are `pdf/State_Talent_Profiles_all_states.zip` (digital) and
  `pdf/State_Talent_Profiles_all_states_print.zip` (print). The profiles index links to both.

**Building it.** `python -m ipeds_clean.state_pdf --all` (or give state codes) rebuilds both formats, the
viewer and both zips. The layout is HTML/CSS (`ipeds_clean/templates/state_pdf.html`). Playwright prints it
with the installed Chrome, and pypdf merges the pages and makes the print split.

**International Talent** (`international.html`, `python -m ipeds_clean.international`): the national
view. Animated Sankeys from abroad to the states (first-time students whose home is outside the U.S.)
and from degree level to field to state (international graduates); a map and ranking on five
international measures; growth by state since 2015; concentration in the leading states; national
trends; and the top 25 institutions for international STEM master's and doctorates. IPEDS does not
record country of citizenship, so origin countries are not shown. All pages share a tab bar
(Sheet · State Talent Profile · International Talent).

**State profiles** (`profiles/<ST>.html`): one state, every data point, read against the same
competitor set (shared with the sheet through the URL and browser storage). An at-a-glance table
compares key measures; every time-series chart overlays the competitors, fetched from
`profiles/data/<ST>.json`, so competitor lines need the local server. Sections cover institutions,
students, international talent, STEM talent, international × STEM (including a degree-pipeline
Sankey), fields, money, outcomes, faculty, migration (arrival and departure Sankeys), all 61 measures
as a rank heatmap, and an animated all-state bubble chart.

Both pages are self-contained files with data and fonts embedded (IBM Plex Sans in
`reference/fonts/`). The design system is `ipeds_clean/templates/kit.css`, the Sankey component is
`ipeds_clean/templates/sankey.js`, and the earlier "manual" templates are kept in
`ipeds_clean/templates/old_manual/`.

Two collection gaps are handled in the panel: race/ethnicity was not collected in 1985, 1987 and
1989 (those years are blank, not 0%), and residence of first-time students is voluntary in odd years
from 2001, so odd years with under 80% of the neighbouring years' reporters are dropped
(`states.residence_years`).

## What would still improve this

1. **Delta Cost after 2012**: the public file ends in 2012, so `instruction_excl_alloc` still has no
   comparable adjustment for 2016+.
2. **HEGIS/IPEDS forms before 1994** (not in the IPEDS archive) to confirm the remaining inferred 1980s definitions: 1980–85 tuition and fees, and unclassified students.
