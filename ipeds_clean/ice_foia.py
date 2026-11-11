"""ICE SEVIS FOIA releases: Optional Practical Training (OPT), STEM OPT and F-1 public high-school students by state.

    python -m ipeds_clean.ice_foia      # cache the workbooks (first run), then rebuild data/ice_foia/*.csv

Source: record-level Excel extracts from the Student and Exchange Visitor Information System (SEVIS) released by
U.S. Immigration and Customs Enforcement (ICE) under FOIA, saved in sources/ice_sevis_foia/. Student identifiers
are withheld, so no file can be linked to another or de-duplicated by person. What each file is:

* StudentExchangeVisa2003-2012.xlsx, sheet SEV_STUDENT (the only sheet). One row per practical-training
  employment record of an F-1 student: school, level of education, major title(s), actual employment start and
  end dates, and the employer's CITY and STATE_CODE (EMP_ID is redacted "(b)(7)(e)" on every row). STATE_CODE
  is the employer's location: a school's records spread over many states (Lamar University, TX: 866 TX, 275 NJ,
  128 CA ...). Durations cluster at 12 months (post-completion OPT), with 17-month (2008-2016) and 24-month
  (2016-) records that look like STEM extensions, so the file mixes regular OPT and STEM OPT employment and
  cannot separate them. Despite the name, start dates run 1998-2018: 2003-2016 are full years, 2017 runs to
  about July (extract date), pre-2003 and 2018 are stray rows and are dropped. THE FILE IS TRUNCATED: it has
  exactly 1,048,575 data rows, Excel's sheet limit, and its rows are not in any date or school order, so the
  missing rows are an unknown, probably arbitrary, slice; every count is a lower bound (roughly two-thirds of
  the records ICE holds, judging from published OPT totals for 2004-2016 of about 1.5 million). Shares (in-state
  retention, level and field mix) are less affected than levels if the cut is arbitrary. Employer location is
  blank on 98% of records starting before 2007 (the SEVIS employer address fields were not used yet), 71% in
  2007, 43% in 2008, falling to 14% in 2016 (38% in partial 2017), so state measures by employer start in
  2008. There are 66,466 exact duplicate rows (after date parsing), which may be different students (same
  school, major, level and dates); all rows are kept. A student with several employers has several records,
  so counts are employment records, not people.
* OPTSTEMInception-2014.xlsx (sheet CSVFile_2014-11-20T11_21_23) and OPTSTEM1-11-20143-31-2017.xlsx (sheet
  STEM-OPT). One row per STEM OPT extension request: school, employer name, program (major) title and its CIP
  code (PRIMARY_PROG_SUBJECT_CODE), request status, requested employment start/end (EMP_START/END_DATE: a
  17-month window until May 2016, 24 months after), and in the second file the USCIS approval (EAD) dates and
  actual employment dates. Neither file has any location column (no employer or school address) and neither
  has the level of education. The inception file runs from the program's start (April 2008) to its extract on
  2014-11-20; the second covers requested start dates 2014-01-11 to 2017-03-31. They overlap for 2014. The
  "(1)" copy of the second file (now in sources/_duplicates_to_delete/) is byte-identical. 49% of the second
  file's employer names are blank, almost all for starts after mid-2016 (the 24-month rule moved employer
  details to the Form I-983), and 11% of its rows are exact duplicates, nearly all with blank employer, so
  likely different students; all are kept. Excel turned a few inception-file employer names into dates; those
  are treated as blank.
* PrimarySecondaryPublic-YYYY-YYYY.xlsx (2004-05 to 2016-17). One row per F-1 student at a public secondary
  school in that school year: school, school code, state (full name), country of citizenship, and the
  I-20 cost and funding estimate (months, tuition and fees, living expenses, funding sources).
* PrimarySecondaryPublictoHigherEducation.xlsx / ...toPrivate.xlsx. One row per SEVIS transfer of an F-1
  student out of a public secondary school, to a college or university / to a private K-12 school, with both
  schools' names, codes, states and types, January 2015 to August/September 2017.

Geography. Employer state (OPT) comes from STATE_CODE. School state is not in any file: it is looked up by
matching SCHOOL_NAME to the IPEDS institution directory (data/ipeds/harmonized/directory.parquet, 1998 on):
exact normalized name, then the name before a dash/comma/parenthesis, then a unique-state prefix match (system
names like "University of Michigan" -> MI), then a state name inside the school name; SCHOOL_FIX (hand-checked) overrides all of these. A
name IPEDS uses in several states (DeVry University, Concordia University, University of St. Thomas ...) is left
without a state ("ambiguous"). About 97% of records get a school state; the lookup is written to school_states.csv for
review. School-system names (e.g. "The City University of New York") are placed in the system's state.
Two-letter postal codes for the 50 states + DC; territories keep their codes (PR, GU, VI ...) and are kept in
"US" totals; "US" is every record.

Year. OPT: the calendar year of ACTUAL_EMP_START_DATE (the only date in that file; when the employment began).
STEM OPT: the calendar year of EMP_START_DATE (the requested start of the STEM extension, present in both
files; in the 2014-2017 file it equals the USCIS validity start and the actual start for >75% of records).
Inception file rows are used for start dates before 2014-01-11, the 2014-2017 file from that date on. 2008
(program began April 2008) and 2017 (to March 31) are partial years for STEM OPT; 2017 to about July for OPT.
High school: the fall year of the school year (2016 = 2016-17). Transfers: calendar year of DATE_OF_TRANSFER.

Retention (OPT, by school state S): opt_stay_in_state / opt_starts_school_emp_known = the share of OPT
employment records of students from schools in S whose employer is also in S, among records with a known
employer state. Records with a blank employer state are left out of both parts, so retention assumes they are
like the others. The US value is the share of all known-employer records with employer state = school state.
opt_employer_to_school = employment starts at employers in S / starts by students of schools in S (known
employer state): above 1 means the state's employers take in more OPT workers than its colleges send out.

Fields: 2-digit CIP families as in ipeds_clean.states (FIELDS, STEM_CIP2): cs 11, eng 14+15, math 27, bio 26,
phys 40, health 51, business 52; stem = 03, 04, 11, 14, 15, 26, 27, 40. OPT majors are titles only, mapped to
CIP through the NCES 2000/2010/2020 title lists (99.9% of records). Levels (OPT only): bach, master, doc,
assoc, other (certificate, language, secondary ...).

Outputs (data/ice_foia/):
  opt_state.csv          year, state, geo, measure, level, field, value (level/field "all" = every record)
                         OPT (employment-start year): opt_starts_school, opt_starts_school_emp_known,
                         opt_emp_state_coverage, opt_stay_in_state, opt_retention, opt_starts_employer,
                         opt_employer_to_school; STEM OPT (requested-start year, by school state, level
                         "all"): stem_opt_requests, stem_opt_approved, stem_opt_denied, stem_opt_employer_named
  opt_state_wide.csv     one row per year-state; columns measure, measure__<level>, measure__<field>;
                         flags opt_partial_year, opt_emp_state_reliable (year >= 2008), stem_opt_partial_year
  opt_employers_top.csv  top 10 employers of approved STEM OPT requests by school state and year (and US),
                         2008-2016 (employer names largely blank after mid-2016); employer = where the student
                         works, but the state is the school's
  hs_f1_state.csv        year, school_year, state, geo, measure, value: hs_f1_students, hs_f1_schools,
                         hs_f1_median_tuition, hs_f1_median_months, hs_f1_share_china, hs_f1_countries;
                         hs_to_college_out, hs_to_college_in_state_share, hs_to_college_in, hs_to_private_out
  school_states.csv      school name -> state lookup with method and record counts
  files.csv              every file: sheet, rows, record definition, years, use, duplicates
  checks.csv             truncation, coverage by year, file overlap, state sums vs US
Intermediate (cache/ice_foia/): one parquet per workbook (or workbook group), rebuilt when a source is newer.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .dol import STATE_MAP, STATES as STATE_NAMES, TERR as TERR_NAMES

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "ice_sevis_foia"
OUT = ROOT / "data" / "ice_foia"
RAW = ROOT / "cache" / "ice_foia"
IPEDS_DIR = ROOT / "data" / "ipeds" / "harmonized" / "directory.parquet"
CIP_REF = ROOT / "reference" / "cip"
STATES = set(STATE_NAMES)
TERR = set(TERR_NAMES) | {"UM"}
EXCEL_MAX_ROWS = 1_048_575
OPT_FILE = "StudentExchangeVisa2003-2012.xlsx"
STEM_OLD, STEM_NEW = "OPTSTEMInception-2014.xlsx", "OPTSTEM1-11-20143-31-2017.xlsx"
STEM_SPLIT = pd.Timestamp("2014-01-11")      # first requested start date in the 2014-2017 file
OPT_YEARS = range(2003, 2018)
OPT_PARTIAL, STEM_PARTIAL = {2017}, {2008, 2017}
EMP_RELIABLE_FROM = 2008
# same groupings as ipeds_clean.states (copied so this module does not import the plotting stack)
STEM_CIP2 = ["03", "04", "11", "14", "15", "26", "27", "40"]
FIELDS = {"cs": ["11"], "eng": ["14", "15"], "math": ["27"], "bio": ["26"], "phys": ["40"],
          "health": ["51"], "business": ["52"]}
LEVELS = {"BACHELOR'S": "bach", "MASTER'S": "master", "DOCTORATE": "doc", "ASSOCIATE": "assoc"}
TITLE_FIX = {"nursing registered nurse training rn asn bsn msn": "51",
             "pharmacy pharmd usa pharmd bs bpharm canada": "51"}
# hand-checked school -> state for names the IPEDS lookup misses or gets wrong (by record count)
SCHOOL_FIX = {
    "NYU Tandon School of Engineering": "NY", "NYU Polytechnic School of Engineering": "NY",
    "UCLA-Extension": "CA", "University of Notre Dame du Lac": "IN", "Herguan University": "CA",
    "ASU-Thunderbird School of Global Management": "AZ", "University of Puerto Rico": "PR",
    "Johns Hopkins University Schl of Advanced Intl Studies": "DC", "UCI Division of Continuing Education": "CA",
    "St. Mary's Univ. of San Antonio, TX": "TX", "The Lee Strasberg Theatre and Film Institute": "NY",
    "Kapi`olani Community College": "HI", "American College of Commerce & Technology": "VA",
    "San Diego Univ. for Integrative Studies": "CA", "Santa Barbara City College District": "CA",
    "The Fletcher School of Law and Diplomacy": "MA", "Keck Graduate Institute of Applied Life Sciences": "CA",
    "Lone Star College System District": "TX", "International Center of Photography": "NY",
    "Tufts University School of Medicine and Dentistry": "MA", "Peralta Community College District": "CA",
    "College of Saint Benedict/Saint John's University": "MN", "MiraCosta Community College District": "CA",
    "UC Davis Extension, International Programs": "CA", "Johns Hopkins University Peabody Institute": "MD",
    "Ashland University and Ashland Center for English Studies": "OH", "HB Studio": "NY",
    "World Learning/SIT Graduate Institute": "VT", "Westchester Community College": "NY",
    "Southern States University San Diego": "CA", "The Boston Conservatory at Berklee": "MA",
    "Minneapolis Community and Tech. College": "MN", "Stella Adler Studio of Acting": "NY",
    "Kutztown University of PA": "PA", "OLIVET UNIVERSITY": "CA", "Washington University of Virginia": "VA",
    "Desert Community College District": "CA", "Neighborhood Playhouse School of the Theatre": "NY",
    "Embry-Riddle Aeronautical University - Prescott, AZ": "AZ",
    "The Art Institute of CA @ LA (f/k/a The Art Institute of LA)": "CA",
    "International American University": "CA", "El Paso Community College District": "TX",
    "Whittier College and Whittier Law School": "CA", "MassBay Community College": "MA",
    "Hobart and William Smith Colleges": "NY", "Pima County Community College District": "AZ",
    "East Los Angeles Community College": "CA", "College of Medicine, Mayo Clinic": "MN",
    "Miami International University of Art & Design": "FL",
}


# ---------------------------------------------------------------- reading + cache

def _cached(name: str, sources: list[Path], reader) -> pd.DataFrame:
    p = RAW / f"{name}.parquet"
    if p.exists() and p.stat().st_mtime >= max(s.stat().st_mtime for s in sources):
        return pd.read_parquet(p)
    RAW.mkdir(parents=True, exist_ok=True)
    d = reader()
    d.to_parquet(p, index=False)
    return d


def _date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def read_opt() -> pd.DataFrame:
    def r():
        d = pd.read_excel(SRC / OPT_FILE, sheet_name="SEV_STUDENT", engine="calamine", dtype=str)
        for c in ["ACTUAL_EMP_START_DATE", "ACTUAL_EMP_END_DATE"]:
            d[c] = _date(d[c])
        return d.drop(columns="EMP_ID")
    return _cached("opt_2003_2017", [SRC / OPT_FILE], r)


def read_stem() -> pd.DataFrame:
    def r():
        out = []
        for f in [STEM_OLD, STEM_NEW]:
            d = pd.read_excel(SRC / f, engine="calamine", dtype=object)
            d["EMPLR_NAME"] = d.EMPLR_NAME.where(d.EMPLR_NAME.map(lambda v: isinstance(v, str)))
            for c in [c for c in d if c.endswith("_DATE")]:
                d[c] = _date(d[c])
            d["PRIMARY_PROG_SUBJECT_CODE"] = pd.to_numeric(d.PRIMARY_PROG_SUBJECT_CODE, errors="coerce") \
                .map(lambda v: f"{v:07.4f}" if pd.notna(v) else None)
            for c in ["SCHOOL_NAME", "EMPLR_NAME", "PROG_CLASS_DESC", "STUDENT_REQ_STATUS_DESC"]:
                d[c] = d[c].astype("string")
            out.append(d.assign(file=f))
        return pd.concat(out, ignore_index=True).drop(columns=["STUDENT_REQ_STATUS_CODE", "EMPMNT_TYPE_DESC"])
    return _cached("stem_opt", [SRC / STEM_OLD, SRC / STEM_NEW], r)


def _hs_files() -> list[Path]:
    return sorted(SRC.glob("PrimarySecondaryPublic-*.xlsx"))


def read_hs() -> tuple[pd.DataFrame, pd.DataFrame]:
    def r1():
        return pd.concat([pd.read_excel(f, engine="calamine").assign(file=f.name, year=int(f.stem[-9:-5]))
                          for f in _hs_files()], ignore_index=True)
    tf = [SRC / "PrimarySecondaryPublictoHigherEducation.xlsx", SRC / "PrimarySecondaryPublictoPrivate.xlsx"]

    def r2():
        d = pd.concat([pd.read_excel(f, engine="calamine").assign(file=f.name) for f in tf], ignore_index=True)
        d["DATE_OF_TRANSFER"] = _date(d.DATE_OF_TRANSFER)
        return d
    return _cached("hs_f1", _hs_files(), r1), _cached("hs_transfers", tf, r2)


# ---------------------------------------------------------------- lookups

def _norm(s: str) -> str:
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(the|at|of|in|campus|main|inc|for)\b", " ", s)
    abbr = {"suny": "state university new york", "ny": "new york", "univ": "university", "schl": "school",
            "st": "saint"}
    return " ".join(abbr.get(w, w) for w in s.split())


def _stem_name(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s)
    return re.split(r"\s*(?:--|-| / |:|,)\s*", s)[0]


def school_states(names: pd.Series) -> pd.DataFrame:
    """SCHOOL_NAME -> two-letter state, with how it was found. `names` = record counts indexed by name."""
    ip = pd.read_parquet(IPEDS_DIR, columns=["year", "instnm", "stabbr"])
    ip = ip[(ip.year >= 1998) & ip.stabbr.isin(list(STATES | TERR))]
    ip["k"] = ip.instnm.astype(str).map(_norm)
    grp = ip.groupby("k").stabbr.agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
    exact = grp.dropna().to_dict()
    in_name = {_norm(v): k for k, v in STATE_NAMES.items()}

    def look(n: str):
        if n in SCHOOL_FIX:
            return SCHOOL_FIX[n], "manual"
        for k, how in ((_norm(n), "exact"), (_norm(_stem_name(n)), "stripped")):
            if k in exact:
                return exact[k], how
        k = _norm(_stem_name(n))
        if _norm(n) in grp.index or k in grp.index:   # an IPEDS name shared by schools in several states
            return None, "ambiguous"
        pref = set(grp[grp.index.str.startswith(k + " ")].dropna())
        if len(pref) == 1:
            return pref.pop(), "prefix"
        hits = {st for sn, st in in_name.items() if re.search(rf"\b{sn}\b", _norm(n))}
        if len(hits) == 1:
            return hits.pop(), "state_in_name"
        return None, "unmatched"
    rows = [(n, c, *look(n)) for n, c in names.items()]
    return pd.DataFrame(rows, columns=["school_name", "records", "state", "method"])


def title_cip2() -> dict[str, str]:
    """Normalized CIP title (2000, 2010, 2020 editions) -> 2-digit family."""
    unx = lambda s: s.astype(str).str.replace(r'^="?|"$', "", regex=True).str.strip()  # noqa: E731
    a = pd.read_csv(CIP_REF / "Crosswalk2000to2010.csv", dtype=str, encoding="cp1252")
    b = pd.read_csv(CIP_REF / "CIPCode2020.csv", dtype=str, encoding="cp1252")
    t = pd.concat([pd.DataFrame({"code": unx(a.CIPCode2000), "title": a.CIPTitle2000}),
                   pd.DataFrame({"code": unx(a.CIPCode2010), "title": a.CIPTitle2010}),
                   pd.DataFrame({"code": unx(b.CIPCode), "title": b.CIPTitle})])
    t = t[t.code.str.len() == 7]
    t["k"] = t.title.map(_tkey)
    return {**t.groupby("k").code.agg(lambda s: s.str[:2].mode().iloc[0]).to_dict(), **TITLE_FIX}


def _tkey(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower().replace("(new)", "")).strip()


def field_of(cip2: pd.Series) -> pd.DataFrame:
    """Boolean frame: one column per field group (plus stem)."""
    out = {f: cip2.isin(v) for f, v in FIELDS.items()}
    out["stem"] = cip2.isin(STEM_CIP2)
    return pd.DataFrame(out)


def geo_of(state: pd.Series) -> pd.Series:
    return np.where(state == "US", "national", np.where(state.isin(list(STATES)), "state", "territory"))


# ---------------------------------------------------------------- measures

def _expand(d: pd.DataFrame, levels: bool) -> pd.DataFrame:
    """Stack the records once per (level, field) cut they belong to: (all, all), (level, all), (all, field),
    (level, field)."""
    flds = field_of(d.cip2)
    parts = []
    lv = [("all", pd.Series(True, index=d.index))]
    if levels:
        lv += [(k, d.level == k) for k in ["bach", "master", "doc", "assoc", "other"]]
    fl = [("all", pd.Series(True, index=d.index))] + [(f, flds[f]) for f in ["stem", *FIELDS]]
    for ln, lm in lv:
        for fn, fm in fl:
            parts.append(d[lm & fm].assign(level=ln, field=fn))
    return pd.concat(parts, ignore_index=True)


def opt_measures(opt: pd.DataFrame) -> pd.DataFrame:
    d = _expand(opt, levels=True)
    k = ["year", "level", "field"]
    known = d.emp_state.notna()
    d["known"], d["stay"] = known, known & (d.emp_state == d.school_state)
    sch = d[d.school_state.notna()].groupby(k + ["school_state"]).agg(
        opt_starts_school=("known", "size"), opt_starts_school_emp_known=("known", "sum"),
        opt_stay_in_state=("stay", "sum"))
    sch.index = sch.index.rename("state", level="school_state")
    us = d.groupby(k).agg(opt_starts_school=("known", "size"), opt_starts_school_emp_known=("known", "sum"),
                          opt_stay_in_state=("stay", "sum"))
    us["state"] = "US"
    us = us.set_index("state", append=True)
    emp = d[known].groupby(k + ["emp_state"]).size().rename("opt_starts_employer")
    emp.index = emp.index.rename("state", level="emp_state")
    us_emp = d[known].groupby(k).size().rename("opt_starts_employer").to_frame().assign(state="US") \
        .set_index("state", append=True).opt_starts_employer
    m = pd.concat([sch, us]).join(pd.concat([emp, us_emp]), how="outer").fillna(0)
    m["opt_emp_state_coverage"] = m.opt_starts_school_emp_known / m.opt_starts_school
    m["opt_retention"] = m.opt_stay_in_state / m.opt_starts_school_emp_known.replace(0, np.nan)
    m["opt_employer_to_school"] = m.opt_starts_employer / m.opt_starts_school_emp_known.replace(0, np.nan)
    m = m.reset_index()
    return m[m.year.isin(OPT_YEARS)]


def stem_measures(stem: pd.DataFrame) -> pd.DataFrame:
    d = _expand(stem, levels=False)
    k = ["year", "level", "field"]
    d["approved"] = d.status == "APPROVED"
    d["denied"] = d.status == "DENIED"
    d["named"] = d.approved & d.employer.notna()
    agg = dict(stem_opt_requests=("approved", "size"), stem_opt_approved=("approved", "sum"),
               stem_opt_denied=("denied", "sum"), stem_opt_employer_named=("named", "sum"))
    a = d[d.school_state.notna()].groupby(k + ["school_state"]).agg(**agg)
    a.index = a.index.rename("state", level="school_state")
    u = d.groupby(k).agg(**agg).assign(state="US").set_index("state", append=True)
    return pd.concat([a, u]).reset_index()


def _clean_employer(s: pd.Series) -> pd.Series:
    e = s.str.upper().str.replace(r"\s*[\(\[][^\)\]]*\d[^\)\]]*[\)\]]\s*$", "", regex=True)  # "(8/26/13)" stamps
    e = e.str.replace(r"[^A-Z0-9& ]+", " ", regex=True).str.split().str.join(" ")
    suf = r"(\s+(INC|INCORPORATED|LLC|L L C|LLP|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LP|PC|PLLC|USA|US|NA))+$"
    return e.str.replace(suf, "", regex=True).str.strip().replace("", pd.NA)


def top_employers(stem: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    d = stem[(stem.status == "APPROVED") & stem.year.between(2008, 2016)].copy()
    d["key"] = _clean_employer(d.employer.astype("string"))
    named = d[d.key.notna()]
    disp = named.groupby("key").employer.agg(lambda s: s.mode().iloc[0])
    both = pd.concat([named, named.assign(school_state="US")])
    both = both[both.school_state.notna()]
    c = both.groupby(["year", "school_state", "key"]).size().rename("stem_opt_approved").reset_index()
    tot = both.groupby(["year", "school_state"]).size().rename("approved_with_employer")
    allap = pd.concat([d, d.assign(school_state="US")]).groupby(["year", "school_state"]).size().rename("approved")
    c = c.sort_values(["year", "school_state", "stem_opt_approved", "key"], ascending=[True, True, False, True])
    c["rank"] = c.groupby(["year", "school_state"]).cumcount() + 1
    c = c[c["rank"] <= n].join(tot, on=["year", "school_state"]).join(allap, on=["year", "school_state"])
    c["share_of_named"] = c.stem_opt_approved / c.approved_with_employer
    c["employer"] = c.key.map(disp)
    c = c.rename(columns={"school_state": "state", "key": "employer_key"})
    return c[["year", "state", "rank", "employer", "employer_key", "stem_opt_approved", "share_of_named",
              "approved_with_employer", "approved"]]


def hs_measures(hs: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    hs = hs.assign(state=hs.STATE_DESC.str.upper().str.strip().map(STATE_MAP))
    rows = []
    for geo_us in (False, True):
        h = hs.assign(state="US") if geo_us else hs[hs.state.notna()]
        g = h.groupby(["year", "state"])
        m = pd.DataFrame({"hs_f1_students": g.size(), "hs_f1_schools": g.SCHOOL_CODE.nunique(),
                          "hs_f1_median_tuition": g.TUITION_AND_FEES.median(),
                          "hs_f1_median_months": g.ESTIMATED_AVERAGE_COST_LENGTH.median(),
                          "hs_f1_share_china": g.COC.apply(lambda s: (s == "CHINA").mean()),
                          "hs_f1_countries": g.COC.nunique()})
        rows.append(m.reset_index().melt(id_vars=["year", "state"], var_name="measure"))
    hsl = pd.concat(rows)
    hsl.insert(1, "school_year", hsl.year.map(lambda y: f"{y}-{str(y + 1)[-2:]}"))
    tr = tr.assign(year=tr.DATE_OF_TRANSFER.dt.year,
                   out_st=tr.TRANSOUT_SCHOOL_STATE.str.upper().str.strip().map(STATE_MAP),
                   in_st=tr.TRANSIN_SCHOOL_STATE.str.upper().str.strip().map(STATE_MAP))
    tr["same"] = tr.out_st == tr.in_st
    col = tr[tr.file.str.contains("HigherEducation")]
    prv = tr[tr.file.str.contains("Private")]
    t = []
    for us in (False, True):
        c = col.assign(out_st="US", in_st="US") if us else col
        p = prv.assign(out_st="US") if us else prv
        o = c[c.out_st.notna()].groupby(["year", "out_st"])
        t += [o.size().rename("hs_to_college_out"), o.same.mean().rename("hs_to_college_in_state_share")]
        t.append(c[c.in_st.notna()].groupby(["year", "in_st"]).size().rename("hs_to_college_in")
                 .rename_axis(["year", "out_st"]))
        t.append(p[p.out_st.notna()].groupby(["year", "out_st"]).size().rename("hs_to_private_out"))
    tl = pd.concat([s.reset_index().rename(columns={"out_st": "state", s.name: "value"}).assign(measure=s.name)
                    for s in t])
    tl["school_year"] = ""
    out = pd.concat([hsl, tl[["year", "school_year", "state", "measure", "value"]]], ignore_index=True)
    out = out.dropna(subset=["year"]).astype({"year": int})
    out.insert(3, "geo", geo_of(out.state))
    return out.sort_values(["measure", "year", "state"])


# ---------------------------------------------------------------- build

def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def build() -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    opt_raw, stem_raw = read_opt(), read_stem()
    hs, tr = read_hs()
    names = pd.concat([opt_raw.SCHOOL_NAME, stem_raw.SCHOOL_NAME.astype(str)]).value_counts()
    ss = school_states(names)
    ss.to_csv(OUT / "school_states.csv", index=False)
    smap = ss.dropna(subset=["state"]).set_index("school_name").state

    cip = title_cip2()
    opt = pd.DataFrame({
        "year": opt_raw.ACTUAL_EMP_START_DATE.dt.year, "school_state": opt_raw.SCHOOL_NAME.map(smap),
        "emp_state": opt_raw.STATE_CODE.str.strip().str.upper().map(STATE_MAP),
        "level": opt_raw.LEVEL_OF_EDUCATION.map(LEVELS).fillna("other"),
        "cip2": opt_raw.TITLE_OF_MAJOR_1.map(_tkey).map(cip)})
    keep = ((stem_raw.file == STEM_OLD) & (stem_raw.EMP_START_DATE < STEM_SPLIT)) | \
           ((stem_raw.file == STEM_NEW) & (stem_raw.EMP_START_DATE >= STEM_SPLIT))
    s = stem_raw[keep]
    stem = pd.DataFrame({"year": s.EMP_START_DATE.dt.year, "school_state": s.SCHOOL_NAME.astype(str).map(smap),
                         "status": s.STUDENT_REQ_STATUS_DESC, "employer": s.EMPLR_NAME,
                         "cip2": s.PRIMARY_PROG_SUBJECT_CODE.str[:2]})
    stem = stem[stem.year.between(2008, 2017)]

    om, sm = opt_measures(opt), stem_measures(stem)
    long = pd.concat([om.melt(id_vars=["year", "state", "level", "field"], var_name="measure"),
                      sm.melt(id_vars=["year", "state", "level", "field"], var_name="measure")], ignore_index=True)
    long = long.dropna(subset=["value"]).astype({"year": int})
    long.insert(2, "geo", geo_of(long.state))
    long = long[["year", "state", "geo", "measure", "level", "field", "value"]] \
        .sort_values(["measure", "level", "field", "year", "state"])
    long.to_csv(OUT / "opt_state.csv", index=False)

    marg = long[(long.level == "all") | (long.field == "all")].copy()
    marg["col"] = np.where((marg.level == "all") & (marg.field == "all"), marg.measure,
                           np.where(marg.level == "all", marg.measure + "__" + marg.field,
                                    marg.measure + "__" + marg.level))
    w = marg.pivot_table(index=["year", "state", "geo"], columns="col", values="value").reset_index()
    w.columns.name = None
    w["opt_partial_year"] = w.year.isin(OPT_PARTIAL).astype(int)
    w["opt_emp_state_reliable"] = (w.year >= EMP_RELIABLE_FROM).astype(int)
    w["stem_opt_partial_year"] = w.year.isin(STEM_PARTIAL).astype(int)
    first = ["year", "state", "geo", "opt_starts_school", "opt_starts_employer", "opt_retention",
             "opt_emp_state_coverage", "stem_opt_approved", "opt_partial_year", "opt_emp_state_reliable",
             "stem_opt_partial_year"]
    w = w[first + sorted(c for c in w if c not in first)]
    w.to_csv(OUT / "opt_state_wide.csv", index=False)

    top_employers(stem).to_csv(OUT / "opt_employers_top.csv", index=False)
    hs_measures(hs, tr).to_csv(OUT / "hs_f1_state.csv", index=False)

    # ---- files.csv
    files = []
    dup_dir = ROOT / "sources" / "_duplicates_to_delete"
    copies = {p.name.split("__", 1)[-1].replace(" (1)", ""): p for p in dup_dir.glob("ice_sevis_foia__*")} if dup_dir.exists() else {}
    defs = {OPT_FILE: ("practical-training (OPT) employment record", "ACTUAL_EMP_START_DATE year",
                       "opt_* measures"),
            STEM_OLD: ("STEM OPT extension request", "EMP_START_DATE year", "stem_opt_* for starts < 2014-01-11"),
            STEM_NEW: ("STEM OPT extension request", "EMP_START_DATE year", "stem_opt_* for starts >= 2014-01-11"),
            "toHigherEducation": ("transfer: public high school -> college", "DATE_OF_TRANSFER year",
                                  "hs_to_college_*"),
            "toPrivate": ("transfer: public high school -> private K-12", "DATE_OF_TRANSFER year",
                          "hs_to_private_out")}
    raw_by = {OPT_FILE: opt_raw, STEM_OLD: stem_raw[stem_raw.file == STEM_OLD],
              STEM_NEW: stem_raw[stem_raw.file == STEM_NEW]}
    for p in sorted(SRC.glob("*.xlsx")):
        key = next((k for k in defs if k in p.name), None)
        if p.name in raw_by:
            r = raw_by[p.name]
            ycol = "ACTUAL_EMP_START_DATE" if p.name == OPT_FILE else "EMP_START_DATE"
            rows, dups = len(r), int(r.drop(columns=[c for c in ["file"] if c in r]).duplicated().sum())
            yrs = r[ycol].dt.year
        elif key:
            r = tr[tr.file == p.name]
            rows, dups, yrs = len(r), int(r.duplicated().sum()), r.DATE_OF_TRANSFER.dt.year
        else:
            r = hs[hs.file == p.name]
            rows, dups, yrs = len(r), int(r.drop(columns="file").duplicated().sum()), r.year
        rec, ydef, use = defs.get(key, ("F-1 student at a public secondary school", "school year in file name",
                                        "hs_f1_*"))
        files.append({"file": p.name, "rows": rows, "record": rec, "year_from": ydef,
                      "years": f"{int(yrs.min())}-{int(yrs.max())}", "used_for": use, "exact_duplicate_rows": dups,
                      "at_excel_row_limit": int(rows == EXCEL_MAX_ROWS),
                      "identical_copy": (str(copies[p.name].relative_to(ROOT)) if p.name in copies
                                         and _md5(copies[p.name]) == _md5(p) else "")})
    pd.DataFrame(files).to_csv(OUT / "files.csv", index=False)

    # ---- checks.csv
    ch = []
    add = lambda check, year, value, note="": ch.append(  # noqa: E731
        {"check": check, "year": year, "value": value, "note": note})
    add("OPT file rows (= Excel row limit => truncated)", "", len(opt_raw), f"limit {EXCEL_MAX_ROWS:,}")
    for y, g in opt.groupby("year"):
        add("OPT records by employment start year", int(y), len(g), "dropped" if y not in OPT_YEARS else "")
        add("OPT employer state known (share)", int(y), round(g.emp_state.notna().mean(), 4))
        add("OPT school state found (share)", int(y), round(g.school_state.notna().mean(), 4))
        add("OPT major mapped to CIP (share)", int(y), round(g.cip2.notna().mean(), 4))
    add("OPT employer STATE_CODE not a US state/territory (rows)", "",
        int((opt_raw.STATE_CODE.notna() & opt.emp_state.isna()).sum()))
    for y, g in stem.groupby("year"):
        add("STEM OPT requests by requested start year", int(y), len(g))
        add("STEM OPT approved", int(y), int((g.status == "APPROVED").sum()))
        add("STEM OPT approved with employer name (share)", int(y),
            round(g[g.status == "APPROVED"].employer.notna().mean(), 4))
        add("STEM OPT school state found (share)", int(y), round(g.school_state.notna().mean(), 4))
    ov = stem_raw[(stem_raw.EMP_START_DATE >= STEM_SPLIT) & (stem_raw.EMP_START_DATE < "2014-11-21")
                  & (stem_raw.STUDENT_REQ_STATUS_DESC == "APPROVED")]
    for f, g in ov.groupby("file"):
        add(f"STEM OPT approved, starts 2014-01-11..2014-11-20, in {f}", 2014, len(g),
            "overlap window; the later file is used")
    for name, m in (("opt_starts_school", om), ("opt_starts_employer", om), ("stem_opt_approved", sm)):
        a = m[(m.level == "all") & (m.field == "all")]
        for y, g in a.groupby("year"):
            st, us = g[g.state != "US"][name].sum(), g[g.state == "US"][name].sum()
            add(f"{name}: states+territories / US", int(y), round(st / us, 4) if us else np.nan,
                "below 1 = records with no state")
    add("schools matched to a state (share of names)", "", round(ss.state.notna().mean(), 4))
    for meth, g in ss.groupby("method"):
        add(f"school-state method: {meth} (share of records)", "", round(g.records.sum() / ss.records.sum(), 4))
    c = pd.DataFrame(ch)
    c.to_csv(OUT / "checks.csv", index=False)
    print(pd.DataFrame(files).to_string(index=False))
    return w


if __name__ == "__main__":
    build()
