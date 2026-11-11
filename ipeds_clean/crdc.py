"""Civil Rights Data Collection (CRDC, U.S. Department of Education, Office for Civil Rights): high-school access to
STEM courses, Advanced Placement and dual enrollment by state, plus gifted and talented and SAT/ACT participation.

    python -m ipeds_clean.crdc              # cache any new survey years, then rebuild every output
    python -m ipeds_clean.crdc 2023-24      # the survey years named only (outputs then hold just those)

Source: the public-use CRDC zips saved in sources/ed_crdc/ (school-level files; the data are OCR's), one per
survey: 2009-10, 2011-12, 2013-14, 2015-16, 2017-18, 2020-21, 2021-22 and 2023-24 (the *.html files are saved
web-page shells with no data). Layouts:
  2009-10, 2011-12   one Excel file per table ("Pt 1-...", "Pt 2-..."), columns {M|F}_{race}_{5|7}_{item}
                     (M_TOT_7_CALCULUS_ENR ...). They are renamed here to the 2013-14 names following the 2011-12 ->
                     2013-14 crosswalk in appendix C of the 2013-14 user's manual (M_TOT_7_CALCULUS_ENR ->
                     TOT_MATHENR_CALC_M, NUM_CLASS_CALCULUS -> SCH_MATHCLASSES_CALC, G9 -> SCH_GRADE_G09, PROVIDE_AP
                     -> SCH_APENR_IND, NUM_AP_COURSES -> SCH_APCOURSES, GTE_PROGRAM -> SCH_GT_IND ...). Grade and
                     status flags are 1/0; "-" marks the race-category set a district did not use (2009-10 districts
                     reported 5 or 7 categories; the total is whichever set is filled; race detail is kept for 2011-12
                     only, since 2009-10's 5-category Asian includes Pacific Islanders); "‡" = suppressed by OCR (kept
                     as reserve code -11); blank = not asked. JJ: 2011-12 "Z" (long-term secure facility, the later
                     years' JJ) is excluded, "X" (other JJ) is not; 2009-10 "X" is excluded. AP-subject and IB
                     indicators did not exist: a school is Yes when it reports students, No when it reports 0.
  2013-14            one Excel file per module, already in the modern names (geometry SCH_GEOMCLASSES_GS0712 /
                     TOT_GEOMENR_GS0712_* renamed to SCH_MATHCLASSES_GEOM / TOT_MATHENR_GEOM_*).
  2015-16            one wide school CSV (TOT_GEOM_* renamed TOT_MATHENR_GEOM_*).
  2017-18 onward     one CSV per module, joined here on COMBOKEY (LEAID + school ID).
Survey design: 2009-10 was a stratified sample of about 7,000 districts and 72,000 schools (every district with
more than 3,000 students, every district in states with fewer than 25 districts, and a rolling sample of the
rest). OCR weighted it for its published state estimates, but the public-use file has no weights, so the
2009-10 school-level sums here cover the sampled schools only (source column says so); shares and rates are
unweighted ratios over the sampled schools and lean toward large districts. crdc_tables.py parses OCR's weighted
2009-10 state estimates, and combine() takes 2009-10 counts from them. Every later year is a universe (2011-12:
99.2% of schools responded). Puerto Rico (in the files from 2017-18) is dropped (state = postal code for the 50
states + DC; "US" = their sum). year = the spring of the school year (2015-16 -> 2016); school_year keeps the label.

High school: a school with students enrolled in each of grades 10, 11 and 12 (SCH_GRADE_G10..G12 all "Yes" in
School Characteristics; so 9-12 and 10-12 schools, which are common in Utah, both count), excluding justice facilities (JJ, or SCH_JUST in 2023-24). Schools with
only ungraded students are not counted. n_schools_any_9_12 (any of grades 9-12) is given for reference. All
counts and shares below are over these high schools, which include alternative, special-education and (2021-22
on, flagged) virtual schools; share_reghs_offer_* repeats each offering share over "regular" high schools
(none of those three flags; n_reghs).
Enrollment denominators are each school's total enrollment (TOT_ENR, all grades it serves, so a 7-12 school's grades 7-8 are in it).

Measures (per course c = calc, advm (advanced mathematics), alg2 (Algebra II), geom (geometry), phys, chem, biol,
csci (computer science, from 2020-21), dsci (data science classes, 2023-24 only)):
  n_hs_valid_c / n_hs_offer_c / share_hs_offer_c   high schools with a usable answer / with at least one class
                                                   (SCH_*CLASSES_c > 0) / the ratio
  share_students_access_c                           share of high-school students in a school offering c
  enr_c, enr_c_m, enr_c_f, enr_c_per100, enr_c_female_share, and by race for calc, phys, csci
AP (any AP course; AP math; AP science; AP computer science from 2020-21): schools with any students enrolled
(SCH_AP*ENR_IND = Yes), share, student access, students enrolled (counted once per subject group, not per
course), mean number of distinct AP courses (SCH_APCOURSES, among schools with AP; values above 40 are dropped as
errors, which matters only in 2009-10), by sex and race. Dual enrollment (from 2013-14; SCH_DUAL_IND; counts from
2015-16, TOT_DUAL, renamed TOT_DUALENR later) and the IB Diploma Programme indicator likewise. SAT/ACT takers
(enr_satact*: students in grades 11-12 who took either test during the year, high schools, no indicator).
Gifted and talented over every school, all grades (n_sch_gt, share_sch_gt, enr_gt, enr_all, enr_gt_per100_all).
Race/ethnicity (CRDC codes): HI Hispanic, AM American Indian/Alaska Native, AS Asian, HP Native Hawaiian/Pacific
Islander, BL Black, WH White, TR two or more races; enr_hs_<race> gives the denominators.
Definition changes across years: 2009-10/2011-12 course classes and enrollments were asked of schools with any of
grades 7-12 (later: classes for high-school students), counted on one fall day; geometry covers grades 7-12 through
2013-14 (grade-8 geometry is reported separately from 2015-16); the advanced-mathematics rate dips in 2015-16
(15.8 -> 13.7 per 100 nationally) with no definition change in the documentation; AP math includes AP Precalculus from 2023-24 (first offered then; enr_apmath_per100 jumps ~25%);
the AP indicator in 2009-10/2011-12 is "students enrolled in AP courses" (PROVIDE_AP), as later.

Reserve codes: negative numbers are not counts. 2013-14: -2 small cell, -5 missing, -9 not applicable. 2015-16: -2
small cell (privacy), -5 action plan, -6 force certified, -7 system error, -8 EDFacts missing, -9 not
applicable/skipped. 2017-18: -3 skip-logic failure, -5, -6, -8, -9, -11 suppressed. 2020-21: -3, -4 missing
optional, -5, -6, -8, -9, -11, -13 skipped for virtual-only schools (COVID directional indicators). 2021-22: -3, -4,
-5, -6, -9, -12 suppressed for privacy, -13. 2023-24: -3 processing error, -5, -6, -7 indeterminable, -9, -10
suppressed under Executive Order 14168 (the nonbinary "_X" columns), -11 data quality, -13. Every reserve
code is treated as missing: a high school with a reserve code for a course is left out of that course's
n_hs_valid (and from the numerator), and a count with a reserve code adds nothing to a sum (sums are over
schools with a value; coverage.csv counts each code per field), except that a school not offering the
course/program (0 classes, or indicator No) counts 0 enrolled when its counts are skipped (-9 or blank). Rates per
100 (enr_*_per100) divide by the enrollment of schools whose count is known. Enrollment totals are TOT_*_M + TOT_*_F
(+ TOT_*_X where not reserved; 2021-22 reports X for enrollment; in 2023-24 the X columns are reserved -10).
Public-use counts are privacy-protected: 2015-16 values are rounded with small cells as -2; from 2017-18 counts are
perturbed (small random +/-1 changes), so small-state counts are approximate.

Outputs (data/crdc/):
  crdc_state.csv              year, school_year, state, source, measure, value     (state "US" = 50 states + DC)
  crdc_state_school_wide.csv  one row per state-year, school-level files only
  crdc_state_wide.csv         every year (combine(): school-level rows; 2009-10 counts from OCR's estimates; years
                              with no school-level file from OCR's published tables, see crdc_tables.py), `source`
  files.csv                   every file in sources/ed_crdc/ (state_tables/ has its own, data/crdc_tables/files.csv)
  coverage.csv                per year x field: source file, schools with a value, high schools with each reserve code
  checks.csv                  national high-school counts and course shares by year; sex sums vs totals; national
                              trends with changes over 5 points (shares) or 25% (rates) marked REVIEW
Intermediate (cache/crdc/): school_{year}_v2.parquet, the needed columns of every school (as text).
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE, DATA, SOURCES

SRC = SOURCES / "ed_crdc"
OUT = DATA / "crdc"
RAW = CACHE / "crdc"
STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
          "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
          "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
RACES = ["HI", "AM", "AS", "HP", "BL", "WH", "TR"]
SEXES = ["M", "F", "X"]
YEARS = ["2009-10", "2011-12", "2013-14", "2015-16", "2017-18", "2020-21", "2021-22", "2023-24"]
ZIPS = {sy: f"{sy}-crdc-data.zip" for sy in YEARS}
# file layout: legacy = 2009-10/2011-12 Excel files with M_/F_ race-sex columns (renamed here to the 2013-14
# names, following the 2011-12 -> 2013-14 crosswalk in appendix C of the 2013-14 user's manual); xlsx = 2013-14
# Excel files already in the modern names; wide = one school CSV (2015-16); csv = one CSV per module.
LAYOUT = {"2009-10": "legacy", "2011-12": "legacy", "2013-14": "xlsx", "2015-16": "wide"}
# survey design: 2009-10 is a stratified sample of about 7,000 districts (72,000 schools); OCR's weights are
# not in the public-use file, so school-level sums cover the sampled (responding) schools only
DESIGN = {"2009-10": "sample"}
CACHE_VERSION = "v2"     # bump when KEEP or the renames change (old caches are then ignored)
# module CSVs read from the per-module years (matched on the file name, any folder)
MODULES = ["School Characteristics", "Enrollment", "Advanced Mathematics", "Calculus", "Physics", "Chemistry",
           "Biology", "Computer Science", "Data Science", "Advanced Placement", "Dual Enrollment",
           "International Baccalaureate", "Algebra II", "Geometry", "Gifted and Talented", "SAT and ACT"]
# Excel files read in 2009-10 and 2011-12 (regex on the file name; first match each) and in 2013-14
LEGACY_FILES = [r"School Characteristics\.xlsx", r"Classes in Math", r"Overall Enrol", r"enrolled in Advanced Math",
                r"enrolled in Algebra II", r"enrolled in Biology", r"enrolled in Calculus", r"enrolled in Chemistry",
                r"enrolled in Geometry", r"Gifted-Talented", r"IB (Diploma )?Programme", r"enrolled in Physics",
                r"at least one AP course", r"taking AP Mathematics", r"taking AP Science", r"SAT or ACT"]
XLSX_FILES = [r"^01 School Char", r"^03 Enrollment", r"^04-1 Gifted", r"^04-2 Dual", r"^05-2 Geometry",
              r"^05-3 Other Math", r"^05-4 Biology", r"^05-5 Chemistry", r"^05-6 Physics", r"^06 Advanced Placement",
              r"^07-1 SAT"]
# course key -> (classes column, enrollment stem, race detail?)
COURSES = {"calc": ("SCH_MATHCLASSES_CALC", "MATHENR_CALC", True),
           "advm": ("SCH_MATHCLASSES_ADVM", "MATHENR_ADVM", False),
           "alg2": ("SCH_MATHCLASSES_ALG2", "MATHENR_ALG2", False),
           "geom": ("SCH_MATHCLASSES_GEOM", "MATHENR_GEOM", False),
           "phys": ("SCH_SCICLASSES_PHYS", "SCIENR_PHYS", True),
           "chem": ("SCH_SCICLASSES_CHEM", "SCIENR_CHEM", False),
           "biol": ("SCH_SCICLASSES_BIOL", "SCIENR_BIOL", False),
           "csci": ("SCH_COMPCLASSES_CSCI", "COMPENR_CSCI", True),
           "dsci": ("SCH_DATACLASSES_DSCI", "DATAENR_DSCI", False)}
# program key -> (indicator column, total stem(s), race stem)
PROGRAMS = {"ap": ("SCH_APENR_IND", ["APENR"], "APENR"),
            "apmath": ("SCH_APMATHENR_IND", ["APMATHENR"], "APMATHENR"),
            "apsci": ("SCH_APSCIENR_IND", ["APSCIENR"], "APSCIENR"),
            "apcs": ("SCH_APCOMPENR_IND", ["APCOMPENR"], "APCOMPENR"),
            "dual": ("SCH_DUAL_IND", ["DUAL", "DUALENR"], "DUALENR"),
            "ib": ("SCH_IBENR_IND", [], None)}
KEEP = re.compile(
    r"^(LEA_STATE|COMBOKEY|JJ|SCH_JUST|SCH_VIRT_IND|SCH_GRADE_G(09|10|11|12)|SCH_GRADE_UG|SCH_UGDETAIL_HS"
    r"|SCH_STATUS_(SPED|ALT|CHARTER|MAGNET)|SCH_APCOURSES|SCH_IBENR_IND"
    r"|TOT_ENR_[MFX]|SCH_ENR_(HI|AM|AS|HP|BL|WH|TR)_[MFX]"
    r"|SCH_(MATH|SCI|COMP|DATA)CLASSES_(CALC|ADVM|ALG2|GEOM|PHYS|CHEM|BIOL|CSCI|DSCI)"
    r"|TOT_(MATH|SCI|COMP|DATA)ENR_(CALC|ADVM|ALG2|GEOM|PHYS|CHEM|BIOL|CSCI|DSCI)_[MFX]"
    r"|SCH_GT_IND|TOT_GTENR_[MFX]|TOT_SATACT_[MFX]|SCH_IBENR_IND|TOT_IBENR_[MFX]"
    r"|SCH_(MATHENR_CALC|SCIENR_PHYS|COMPENR_CSCI)_(HI|AM|AS|HP|BL|WH|TR)_[MFX]"
    r"|SCH_AP(ENR|MATHENR|SCIENR|COMPENR)_IND|TOT_AP(ENR|MATHENR|SCIENR|COMPENR)_[MFX]"
    r"|SCH_AP(ENR|MATHENR|SCIENR|COMPENR)_(HI|AM|AS|HP|BL|WH|TR)_[MFX]"
    r"|SCH_DUAL_IND|TOT_DUAL(ENR)?_[MFX]|SCH_DUALENR_(HI|AM|AS|HP|BL|WH|TR)_[MFX])$")


# 2023-24 public file carries no "No" for the AP and IB indicators: high schools answering No appear as -9
# (their AP counts are -9 too; the Yes share matches earlier years), so -9 is read as No there.
NEG9_IS_NO = {"2023-24": True}


def year_of(sy: str) -> int:
    return int(sy[:4]) + 1


# ---------------------------------------------------------------- inventory

def inventory() -> pd.DataFrame:
    rows = []
    for p in sorted(SRC.iterdir()):
        if p.is_dir():   # state_tables/ is inventoried by crdc_tables.py (data/crdc_tables/files.csv)
            continue
        f = p.name
        m = re.search(r"(20\d\d)-(20\d\d|\d\d)", f)
        sy = f"{m.group(1)}-{m.group(2)[-2:]}" if m else None
        kind, used, note = "documentation", False, "documentation (inventory only)"
        if f in ZIPS.values():
            kind, used = "data", True
            note = ("used (a sample of districts; no weights in the file)" if DESIGN.get(sy) == "sample" else "used")
        elif f.endswith(".html"):
            kind, note = "web page", "saved web-page shell (no data)"
        elif f.endswith((".xlsx", ".xls")) and "Appendix" in f:
            kind = "appendix workbook"
        rows.append({"file": f, "school_year": sy, "kind": kind, "bytes": p.stat().st_size,
                     "mb": round(p.stat().st_size / 1e6, 1), "used": used, "note": note})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- reading and caching

def _std_name(c: str) -> str:
    """Later-year spellings of the same item -> one name (2013-14 and 2015-16 geometry)."""
    c = c.strip()
    c = re.sub(r"^SCH_GEOMCLASSES_GS0712$", "SCH_MATHCLASSES_GEOM", c)
    c = re.sub(r"^TOT_GEOMENR_GS0712_([MF])$", r"TOT_MATHENR_GEOM_\1", c)
    c = re.sub(r"^TOT_GEOM_([MFX])$", r"TOT_MATHENR_GEOM_\1", c)
    return c


def _read_csv(z: zipfile.ZipFile, member: str) -> pd.DataFrame:
    with z.open(member) as fh:
        head = pd.read_csv(fh, nrows=0, encoding="latin-1").columns
    cols = [c for c in head if KEEP.match(_std_name(c))]
    parts = []
    with z.open(member) as fh:
        for ch in pd.read_csv(fh, usecols=cols, dtype=str, encoding="latin-1", keep_default_na=False,
                              chunksize=20_000):
            parts.append(ch.astype("string[pyarrow]"))   # far smaller than object strings
    df = pd.concat(parts, ignore_index=True)
    df.columns = [_std_name(c) for c in df.columns]
    return df


# 2009-10 / 2011-12 item stems (M_TOT_7_CALCULUS_ENR ...) -> the 2013-14 stems (TOT_MATHENR_CALC_M ...)
LEGACY_STEMS = {"ENROL": "ENR", "MATH_ENR": "MATHENR_ADVM", "ALGEBRA2_ENR": "MATHENR_ALG2",
                "GEOMETRY_ENR": "MATHENR_GEOM", "CALCULUS_ENR": "MATHENR_CALC", "BIOLOGY_ENR": "SCIENR_BIOL",
                "CHEMISTRY_ENR": "SCIENR_CHEM", "PHYSICS_ENR": "SCIENR_PHYS", "ONE_AP": "APENR",
                "MATH_AP": "APMATHENR", "SCIENCE_AP": "APSCIENR", "IB_DIPLOMA_ENR": "IBENR", "GT": "GTENR",
                "SAT_ACT": "SATACT"}
LEGACY_RACE = {"HIS": "HI", "AME": "AM", "ASI": "AS", "HI_PAC": "HP", "BLA": "BL", "WHI": "WH", "2_OR_MORE": "TR"}
LEGACY_SCH = {"G9": "SCH_GRADE_G09", "G10": "SCH_GRADE_G10", "G11": "SCH_GRADE_G11", "G12": "SCH_GRADE_G12",
              "UG": "SCH_GRADE_UG", "SP_ED": "SCH_STATUS_SPED", "ALT_SCH": "SCH_STATUS_ALT",
              "CHARTER_SCH": "SCH_STATUS_CHARTER", "MG_SCH": "SCH_STATUS_MAGNET", "PROVIDE_AP": "SCH_APENR_IND",
              "GTE_PROGRAM": "SCH_GT_IND"}
LEGACY_CLASSES = {"NUM_CLASS_GEOMETRY": "SCH_MATHCLASSES_GEOM", "NUM_CLASS_ALG2": "SCH_MATHCLASSES_ALG2",
                  "NUM_CLASS_MATH": "SCH_MATHCLASSES_ADVM", "NUM_CLASS_CALCULUS": "SCH_MATHCLASSES_CALC",
                  "NUM_CLASS_BIOLOGY": "SCH_SCICLASSES_BIOL", "NUM_CLASS_PHYSICS": "SCH_SCICLASSES_PHYS",
                  "NUM_CLASS_CHEMISTRY": "SCH_SCICLASSES_CHEM", "NUM_AP_COURSES": "SCH_APCOURSES"}
LEGACY_CELL = re.compile(r"^([MF])_(AME|ASI|HIS|BLA|WHI|HI_PAC|2_OR_MORE|TOT)_([57])_(.+)$")


def _legacy_values(s: pd.Series) -> pd.Series:
    """2009-10/2011-12 cells: '-' = the other race-category set (blank here), '‡' = suppressed by OCR for data
    quality (-11 here, as in later years), blank = item not asked (left blank)."""
    s = s.fillna("").astype(str).str.strip()
    return s.mask(s == "-", "").mask(s == "‡", "-11")


def _legacy_frame(d: pd.DataFrame, sy: str) -> pd.DataFrame:
    """One 2009-10/2011-12 file -> the 2013-14 column names (as text). Totals: the 5-category (2009-10 only)
    and 7-category race sets are alternatives for a school, so the total is whichever is filled. Race detail
    is kept for 2011-12 only (in 2009-10 most districts reported 5 categories, Asian including Pacific
    Islander, so race detail is not comparable)."""
    out = {"LEA_STATE": d.LEA_STATE.astype(str).str.strip(), "COMBOKEY": d.COMBOKEY.astype(str).str.strip()}
    if "JJ" in d:   # 2011-12: Z = long-term secure facility (the later-year JJ), X = other; 2009-10: X
        jj = d.JJ.fillna("").astype(str).str.strip().str.upper()
        out["JJ"] = np.where(jj == ("Z" if sy == "2011-12" else "X"), "Yes", "No")
    tot: dict[str, list] = {}
    for c in d.columns:
        if c in LEGACY_SCH:
            v = _legacy_values(d[c])
            out[LEGACY_SCH[c]] = v.replace({"1": "Yes", "0": "No"})
        elif c in LEGACY_CLASSES:
            out[LEGACY_CLASSES[c]] = _legacy_values(d[c])
        elif m := LEGACY_CELL.match(c):
            sex, rc, cat, stem = m.groups()
            new = LEGACY_STEMS.get(stem)
            if new is None:
                continue
            if rc == "TOT":
                tot.setdefault(f"TOT_{new}_{sex}", []).append(_legacy_values(d[c]))
            elif cat == "7" and sy != "2009-10":
                out[f"SCH_{new}_{LEGACY_RACE[rc]}_{sex}"] = _legacy_values(d[c])
    for k, vs in tot.items():
        v = vs[0]
        for w in vs[1:]:
            v = v.mask(v == "", w)
        out[k] = v
    return pd.DataFrame(out)


def _derive_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """2009-10/2011-12 have no AP-subject or IB indicators: Yes when the school reports students, No when 0."""
    for ind, stem in [("SCH_APMATHENR_IND", "APMATHENR"), ("SCH_APSCIENR_IND", "APSCIENR"), ("SCH_IBENR_IND", "IBENR")]:
        if ind in df or f"TOT_{stem}_M" not in df:
            continue
        n = num(df[f"TOT_{stem}_M"]).add(num(df[f"TOT_{stem}_F"]), fill_value=0)
        n = n.where(num(df[f"TOT_{stem}_M"]).notna() | num(df[f"TOT_{stem}_F"]).notna())
        n = n.astype("Float64").to_numpy(dtype=float, na_value=np.nan)
        df[ind] = pd.Series(np.where(n > 0, "Yes", np.where(n == 0, "No", "")), index=df.index).astype(
            "string[pyarrow]")
    return df


def _read_xlsx(z: zipfile.ZipFile, member: str, sy: str) -> pd.DataFrame:
    with z.open(member) as fh:
        d = pd.read_excel(io.BytesIO(fh.read()), sheet_name=0, dtype=str, engine="calamine")
    d.columns = [str(c).strip() for c in d.columns]
    if LAYOUT[sy] == "legacy":
        d = _legacy_frame(d, sy)
    else:
        d.columns = [_std_name(c) for c in d.columns]
        d = d[[c for c in d.columns if KEEP.match(c)]]
    d = d[[c for c in d.columns if KEEP.match(c)]]
    return d.fillna("").astype("string[pyarrow]")


def _merge(df: pd.DataFrame | None, d: pd.DataFrame) -> pd.DataFrame:
    d = d.drop_duplicates("COMBOKEY")
    if df is None:
        return d
    new = [c for c in d.columns if c not in df.columns or c == "COMBOKEY"]
    return df.merge(d[new], on="COMBOKEY", how="outer")


def read_year(sy: str) -> tuple[pd.DataFrame, list[dict]]:
    """All needed columns for every school in one survey year, one row per COMBOKEY, plus the column map."""
    z = zipfile.ZipFile(SRC / ZIPS[sy])
    layout = LAYOUT.get(sy, "csv")
    cmap, df = [], None
    if layout in ("legacy", "xlsx"):
        names = [n for n in z.namelist() if n.lower().endswith(".xlsx") and "/LEA/" not in n
                 and not Path(n).name.startswith(("~$", "$")) and z.getinfo(n).file_size > 1000
                 and "EDFACTS" not in n.upper()]
        for pat in (LEGACY_FILES if layout == "legacy" else XLSX_FILES):
            hit = [n for n in names if re.search(pat, Path(n).name, re.I)]
            if not hit:
                print(f"  ({sy}: no file matching {pat})", flush=True)
                continue
            print(f"  reading {Path(hit[0]).name}", flush=True)
            d = _read_xlsx(z, hit[0], sy)
            cmap += [{"school_year": sy, "file": hit[0], "column": c} for c in d.columns
                     if c not in ("LEA_STATE", "COMBOKEY", "JJ") or df is None]
            df = _merge(df, d)
        return (_derive_indicators(df) if layout == "legacy" else df), cmap
    names = [i.filename for i in z.infolist() if i.filename.lower().endswith(".csv")]
    if layout == "wide":
        member = next(n for n in names if n.endswith("School Data.csv"))
        print(f"  reading {member}", flush=True)
        df = _read_csv(z, member)
        cmap = [{"school_year": sy, "file": member, "column": c} for c in df.columns]
        return df, cmap
    for mod in MODULES:
        hit = [n for n in names if Path(n).name == f"{mod}.csv" and "/LEA/" not in n and not n.startswith("LEA/")]
        if not hit:
            continue
        print(f"  reading {hit[0]}", flush=True)
        d = _read_csv(z, hit[0])
        cmap += [{"school_year": sy, "file": hit[0], "column": c} for c in d.columns
                 if c not in ("LEA_STATE", "COMBOKEY", "JJ", "SCH_JUST") or mod == "School Characteristics"]
        df = _merge(df, d)
    return df, cmap


def cached(sy: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    p, cp = RAW / f"school_{sy}_{CACHE_VERSION}.parquet", RAW / f"columns_{sy}_{CACHE_VERSION}.parquet"
    if p.exists() and cp.exists():
        return pd.read_parquet(p), pd.read_parquet(cp)
    df, cmap = read_year(sy)
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    cm = pd.DataFrame(cmap)
    cm.to_parquet(cp, index=False)
    return df, cm



# ---------------------------------------------------------------- cleaning

def num(s: pd.Series) -> pd.Series:
    """Counts: reserve codes (negative) and blanks -> NaN."""
    v = pd.to_numeric(s, errors="coerce").astype("float64")   # plain floats (no pd.NA from pyarrow strings)
    return v.where(v >= 0)


def yes(s: pd.Series) -> pd.Series:
    """Yes/No indicator -> 1.0/0.0; reserve codes and blanks -> NaN."""
    u = s.fillna("").astype(str).str.strip().str.upper()
    return u.map({"YES": 1.0, "NO": 0.0}).astype("float64")


def reserve_counts(s: pd.Series) -> dict:
    v = pd.to_numeric(s, errors="coerce").astype("float64")
    return {int(k): int(n) for k, n in v[v < 0].value_counts().items()}


def _sum_sex(df: pd.DataFrame, stem: str, prefix: str = "TOT") -> dict[str, pd.Series]:
    """{'m','f','x','all'} counts for TOT_{stem}_M/F/X (all = M + F + X; NaN only if M and F are both missing)."""
    out = {}
    for s in SEXES:
        c = f"{prefix}_{stem}_{s}"
        out[s.lower()] = num(df[c]) if c in df else pd.Series(np.nan, index=df.index)
    a = pd.concat([out["m"], out["f"], out["x"]], axis=1)
    out["all"] = a.sum(axis=1, min_count=1).where(out["m"].notna() | out["f"].notna())
    return out


def _race(df: pd.DataFrame, stem: str) -> dict[str, pd.Series]:
    r = {}
    for rc in RACES:
        cols = [f"SCH_{stem}_{rc}_{s}" for s in SEXES if f"SCH_{stem}_{rc}_{s}" in df]
        if cols:
            r[rc] = pd.concat([num(df[c]) for c in cols], axis=1).sum(axis=1, min_count=1)
    return r


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["state"] = df.LEA_STATE.str.strip().str.upper()
    jj = df.SCH_JUST if "SCH_JUST" in df else df.get("JJ", pd.Series("", index=df.index))
    df["is_jj"] = yes(jj).fillna(0).astype(bool)
    g = pd.concat([yes(df[f"SCH_GRADE_G{k}"]) for k in ["09", "10", "11", "12"]], axis=1)
    df["any_9_12"] = g.eq(1).any(axis=1)
    df["hs"] = g.iloc[:, 1:].eq(1).all(axis=1) & ~df.is_jj      # grades 10-12: 10-12 high schools (common in Utah) count
    df["enr"] = _sum_sex(df, "ENR")["all"]
    return df


# ---------------------------------------------------------------- measures

def _share(n, d):
    return n / d if d else np.nan


def measures(g: pd.DataFrame, all_rows: pd.DataFrame, sy: str) -> dict:
    """g: one geography's high schools (prepared); all_rows: every school in that geography."""
    r = {"n_schools_all": len(all_rows), "n_schools_any_9_12": int(all_rows.any_9_12.sum()),
         "n_jj_with_9_12_excluded": int((all_rows.is_jj & all_rows.any_9_12).sum()),
         "n_hs": len(g), "enr_hs": g.enr.sum(min_count=1)}
    for nm, col in [("charter", "SCH_STATUS_CHARTER"), ("alt", "SCH_STATUS_ALT"), ("sped", "SCH_STATUS_SPED"),
                    ("magnet", "SCH_STATUS_MAGNET"), ("virtual", "SCH_VIRT_IND")]:
        if col in g:
            r[f"n_hs_{nm}"] = yes(g[col]).sum()
    e = _sum_sex(g, "ENR")
    r["enr_hs_m"], r["enr_hs_f"] = e["m"].sum(min_count=1), e["f"].sum(min_count=1)
    for rc, v in _race(g, "ENR").items():
        r[f"enr_hs_{rc.lower()}"] = v.sum(min_count=1)

    reg = pd.Series(True, index=g.index)
    for col in ["SCH_STATUS_ALT", "SCH_STATUS_SPED", "SCH_VIRT_IND"]:
        if col in g:
            reg &= yes(g[col]) != 1
    r["n_reghs"] = int(reg.sum())

    def access(flag: pd.Series, key: str):
        ok = flag.notna()
        r[f"n_hs_valid_{key}"] = int(ok.sum())
        r[f"n_hs_offer_{key}"] = int((flag == 1).sum())
        r[f"share_hs_offer_{key}"] = _share((flag == 1).sum(), ok.sum())
        w = g.enr.where(ok & g.enr.notna())
        r[f"share_students_access_{key}"] = _share(w[flag == 1].sum(), w.sum())
        rf = flag[reg & ok]   # regular high schools: not alternative, special-education or virtual
        r[f"share_reghs_offer_{key}"] = _share((rf == 1).sum(), len(rf))

    def enrolled(key: str, stems: list[str], race_stem: str | None, by_race: bool, flag: pd.Series):
        """Counts; a school that does not offer the course/program (flag 0) counts as 0 even if skipped (-9)."""
        stem = next((s for s in stems if f"TOT_{s}_M" in g), None)
        if stem is None:
            return
        no = flag == 0
        s = {k: v.mask(no & v.isna(), 0.0) for k, v in _sum_sex(g, stem).items()}
        both = s["all"].notna() & g.enr.notna()
        r[f"enr_{key}"] = s["all"].sum(min_count=1)
        r[f"enr_{key}_m"], r[f"enr_{key}_f"] = s["m"].sum(min_count=1), s["f"].sum(min_count=1)
        r[f"enr_{key}_per100"] = _share(s["all"][both].sum() * 100, g.enr[both].sum())
        r[f"enr_{key}_female_share"] = _share(s["f"].sum(), s["m"].sum() + s["f"].sum())
        mf = s["m"].notna() & e["m"].notna()
        r[f"enr_{key}_per100_m"] = _share(s["m"][mf].sum() * 100, e["m"][mf].sum())
        ff = s["f"].notna() & e["f"].notna()
        r[f"enr_{key}_per100_f"] = _share(s["f"][ff].sum() * 100, e["f"][ff].sum())
        if by_race and race_stem:
            for rc, v in _race(g, race_stem).items():
                r[f"enr_{key}_{rc.lower()}"] = v.mask(no & v.isna(), 0.0).sum(min_count=1)

    for key, (ccol, stem, by_race) in COURSES.items():
        if ccol not in g:
            continue
        f = (num(g[ccol]) > 0).astype(float).where(num(g[ccol]).notna())
        access(f, key)
        enrolled(key, [stem], stem, by_race, f)
    ap = None
    for key, (icol, stems, rstem) in PROGRAMS.items():
        if icol not in g:
            continue
        f = yes(g[icol])
        if NEG9_IS_NO.get(sy) and key != "dual":   # 2023-24 public file: no "No" values; -9 stands for No
            f = f.mask(pd.to_numeric(g[icol], errors="coerce").astype("float64") == -9, 0.0)
        if key == "ap":
            ap = f
        elif key.startswith("ap") and ap is not None:   # subject question asked only of schools with AP
            f = f.where(ap != 0, 0.0)
        access(f, key)
        enrolled(key, stems, rstem, True, f)
    if "SCH_APCOURSES" in g:
        n = num(g.SCH_APCOURSES)
        has = ap == 1
        # at most ~40 distinct AP courses exist; larger values (2009-10 has some in the thousands) are errors
        r["ap_courses_mean"] = n[has & (n > 0) & (n <= 40)].mean()
    # SAT or ACT takers (students in grades 11-12 who took either test during the school year; no indicator)
    enrolled("satact", ["SATACT"], None, False, pd.Series(np.nan, index=g.index))
    # gifted and talented: every school (all grades), not only high schools
    if "TOT_GTENR_M" in all_rows:
        a = all_rows
        gt = yes(a.SCH_GT_IND) if "SCH_GT_IND" in a else pd.Series(np.nan, index=a.index)
        s = _sum_sex(a, "GTENR")
        s = {k: v.mask((gt == 0) & v.isna(), 0.0) for k, v in s.items()}
        r["n_sch_valid_gt"], r["n_sch_gt"] = int(gt.notna().sum()), int((gt == 1).sum())
        r["share_sch_gt"] = _share((gt == 1).sum(), gt.notna().sum())
        r["enr_all"] = a.enr.sum(min_count=1)
        r["enr_gt"], r["enr_gt_m"], r["enr_gt_f"] = (s[k].sum(min_count=1) for k in ("all", "m", "f"))
        both = s["all"].notna() & a.enr.notna()
        r["enr_gt_per100_all"] = _share(s["all"][both].sum() * 100, a.enr[both].sum())
        r["enr_gt_female_share"] = _share(s["f"].sum(), s["m"].sum() + s["f"].sum())
    return r


def build_year(sy: str) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    raw, cmap = cached(sy)
    df = prepare(raw)
    pr = int((df.state == "PR").sum())
    df = df[df.state.isin(STATES)]
    hs = df[df.hs]
    rows = []
    for st in STATES + ["US"]:
        a = df if st == "US" else df[df.state == st]
        g = hs if st == "US" else hs[hs.state == st]
        for k, v in measures(g, a, sy).items():
            rows.append((st, k, v))
    long = pd.DataFrame(rows, columns=["state", "measure", "value"])
    long.insert(0, "school_year", sy)
    long.insert(0, "year", year_of(sy))
    # coverage: per field, schools with a usable value and reserve codes among high schools
    src = dict(zip(cmap.column, cmap.file))
    cov = []
    for c in raw.columns:
        if c in ("LEA_STATE", "COMBOKEY"):
            continue
        rc = reserve_counts(hs[c]) if c in hs else {}
        v = hs[c].fillna("").str.strip()
        cov.append({"school_year": sy, "field": c, "source_file": src.get(c, ""),
                    "hs_nonblank": int((v != "").sum()), "hs_reserve_total": sum(rc.values()),
                    **{f"hs_code_{k}": n for k, n in sorted(rc.items())}})
    us = long[long.state == "US"].set_index("measure").value
    chk = [{"school_year": sy, "check": "Puerto Rico schools dropped", "value": pr, "note": ""},
           {"school_year": sy, "check": "US schools (50 states + DC)", "value": us["n_schools_all"], "note": ""},
           {"school_year": sy, "check": "US high schools (grades 9-12, not JJ)", "value": us["n_hs"], "note": ""}]
    for k in list(COURSES) + list(PROGRAMS):
        if f"share_hs_offer_{k}" in us:
            chk.append({"school_year": sy, "check": f"US share of high schools offering {k}",
                        "value": us[f"share_hs_offer_{k}"],
                        "note": "calculus: about half of high schools nationally" if k == "calc" else ""})
    for k in ["enr_hs", "enr_ap", "enr_calc"]:
        if f"{k}_m" in us:
            chk.append({"school_year": sy, "check": f"US {k}: M + F + X vs total, difference",
                        "value": us[k] - us[f"{k}_m"] - us[f"{k}_f"],
                        "note": "nonzero = X (nonbinary) counts, or schools with only one sex reserved"})
    return long, cov, chk


def trend_checks(long: pd.DataFrame) -> list[dict]:
    """National series across years: each year's value and its change from the previous survey; changes larger
    than 5 points (shares, x100) or 25% (rates per 100) are flagged for review."""
    us = long[long.state == "US"].pivot_table(index="school_year", columns="measure", values="value")
    out = []
    keys = [f"share_hs_offer_{k}" for k in list(COURSES) + list(PROGRAMS)] + \
           [f"enr_{k}_per100" for k in list(COURSES) + ["ap", "apmath", "apsci", "apcs", "dual", "satact"]] + \
           ["share_sch_gt", "enr_gt_per100_all"]
    for k in keys:
        if k not in us:
            continue
        s = us[k].dropna()
        prev = None
        for sy, v in s.items():
            share = k.startswith("share")
            d = None if prev is None else ((v - prev) * 100 if share else (v / prev - 1) * 100 if prev else None)
            big = d is not None and abs(d) > (5 if share else 25)
            out.append({"school_year": sy, "check": f"trend US {k}", "value": v * 100 if share else v,
                        "note": ("" if d is None else f"change vs previous survey {d:+.1f} "
                                 f"{'points' if share else '%'}") + (" - REVIEW" if big else "")
                                + (" (2009-10: unweighted sample)" if DESIGN.get(sy) == "sample" else "")})
            prev = v
    return out


def main(years: list[str] | None = None):
    inv = inventory()
    years = years or list(ZIPS)
    longs, covs, chks = [], [], []
    for sy in years:
        print(f"CRDC {sy}", flush=True)
        long, cov, chk = build_year(sy)
        longs.append(long)
        covs += cov
        chks += chk
    long = pd.concat(longs, ignore_index=True)
    long.insert(3, "source", long.school_year.map(lambda sy: SOURCE_SAMPLE if DESIGN.get(sy) == "sample"
                                                   else SOURCE_SCHOOL))
    chks += trend_checks(long)
    OUT.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT / "crdc_state.csv", index=False)
    w = long.pivot_table(index=["year", "school_year", "state", "source"], columns="measure", values="value",
                         sort=False)
    order = [m for m in dict.fromkeys(long.measure) if m in w.columns]
    w[order].reset_index().to_csv(OUT / "crdc_state_school_wide.csv", index=False)
    pd.DataFrame(covs).to_csv(OUT / "coverage.csv", index=False)
    pd.DataFrame(chks).to_csv(OUT / "checks.csv", index=False)
    inv.to_csv(OUT / "files.csv", index=False)
    combine()
    return long


# ---------------------------------------------------------------- combined state-year file

SOURCE_SCHOOL = "school-level file (universe)"
SOURCE_SAMPLE = "school-level file (2009-10 district sample, unweighted: responding schools only)"
SOURCE_EST = "OCR published state estimates"


def combine() -> pd.DataFrame:
    """crdc_state_wide.csv: every year. School-level rows where a universe file exists; for 2009-10 (sample)
    the counts come from OCR's published (weighted) state estimates where crdc_tables.py harmonized one, and
    shares and rates stay the school-level sample's (ratios need no weights when one state's schools share a
    weight; they are unweighted across sampling strata); years with no school-level file (OCR projections
    2000-2006) come from the published tables only."""
    sch = pd.read_csv(OUT / "crdc_state_school_wide.csv")
    tp = DATA / "crdc_tables" / "crdc_tables_wide.csv"
    if not tp.exists():
        sch.to_csv(OUT / "crdc_state_wide.csv", index=False)
        return sch
    est = pd.read_csv(tp)
    est = est[est.state.isin(STATES + ["US"])]
    rows = [sch[sch.school_year.map(lambda sy: DESIGN.get(sy) != "sample")]]
    have = set(sch.school_year)
    # 2009-10: sample shares/rates + published counts
    for sy in [y for y in have if DESIGN.get(y) == "sample"]:
        s = sch[sch.school_year == sy].set_index("state")
        e = est[est.school_year == sy].set_index("state")
        counts = [c for c in s.columns if re.match(r"^(n_|enr_)", c) and not re.search(r"(per100|share)", c)]
        s[counts] = np.nan    # sample sums are not state totals
        common = [c for c in e.columns if c in s.columns and c in counts]
        s.loc[s.index.intersection(e.index), common] = e.loc[s.index.intersection(e.index), common]
        s["source"] = (f"{SOURCE_EST} (counts); " + SOURCE_SAMPLE.replace("school-level file", "school-level")
                       + " (shares and rates)")
        rows.append(s.reset_index())
    # years with no school-level file
    other = est[~est.school_year.isin(have)].copy()
    other["source"] = other.get("source", SOURCE_EST)
    rows.append(other)
    w = pd.concat(rows, ignore_index=True, sort=False)
    lead = ["year", "school_year", "state", "source"]
    w = w[lead + [c for c in w.columns if c not in lead]].sort_values(["year", "state"])
    w.to_csv(OUT / "crdc_state_wide.csv", index=False)
    return w


if __name__ == "__main__":
    main(sys.argv[1:] or None)
