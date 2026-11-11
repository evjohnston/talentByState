"""NSF/NCSES Higher Education R&D Survey (HERD): R&D expenditures and R&D personnel by state and fiscal year.

    python -m ipeds_clean.herd           # -> data/herd/*.csv and a printed sanity-check report

Source: the HERD published data-table zips in sources/nsf_herd/, one zip per survey year (FY2010 = nsf12330,
FY2011 = nsf13325, FY2012-17 = herd20YYtables, FY2018 = herd18-dt-tables, FY2019-24 = nsf21314 ... nsf26304).
Zips are read in place. Every file's fiscal year is read from its table title (the last year named in it,
"...: FY 2023" or "...: FYs 2010-23"); a zip's survey (release) year is the most common title year in it.
Tables are found by title, not by number, because the numbering changes nearly every year.

What is used (per release)
* State trend tables ("R&D expenditures, by (geographic division and) state: FYs ...", and the same "in science
  and engineering fields"): rd_exp/all and rd_exp/fld_se for every year in the table. In 2010 the only
  multi-year state source is the "by state, institutional control, and institution: FY 2003-10" table (its
  state rows carry state totals); 2024 (nsf26304, only 27 tables) has the standard-form "by state: FYs
  2010-24" table.
* Own-year "by state and source of funds" (2013+), "by geographic division, state, and source of funds"
  (2012) or "by state, institutional control, institution, and source of funds" (2010-11): rd_exp by source.
* Own-year "by state, institutional control, institution, and R&D field" (2011-23): rd_exp by broad field.
  State rows carry the state totals; where a state row is blank the institution rows under it are summed.
  FY2010 (no state x field table) and FY2024 (no state x field or state x source table) come from the
  ranking tables aggregated to states (below); basis says so.
* "Headcount (and FTEs) of R&D personnel ..., by state, institutional control, and institution" (2010-19,
  2022-24): summed over institutions (state rows are blank; US = sum of states and territories where the
  table has no US row). FY2020-21 releases have national totals only. Standard-form institutions only.
* "... at institutions in both survey populations / the standard form and short form survey populations, by
  state, ..." (2012+): rd_exp_both_pop/all, the state total including short-form (< $1M) institutions.
* Institution ranking tables have no state column. Each ranked institution is given the state it is listed
  under in the same release's state x institution tables (matched on the institution name), then summed:
  - "ranked by all federal R&D expenditures, by federal agency" -> rd_exp_federal by agency (all years);
  - "ranked by all R&D expenditures, by source of funds / by R&D field" -> used for the rank-vs-state check,
    and for FY2024 source and field by state (no state table on those in the 2024 release). These sums cover
    standard-form institutions only (ranking tables list no short-form institutions).

Selection: a value comes from the release for its own fiscal year; years a release does not cover
themselves (FY2003-09) come from the earliest later release that has them. Revisions in later releases are
reported in checks.csv (own-year vs latest release).

Outputs (data/herd/):
  herd_state.csv       fiscal_year, state, measure, category, value, unit, basis, note, release_year,
                       source_zip, source_file, table_title
  herd_state_wide.csv  one row per state-year, columns <measure>__<category>
  files.csv            every file in every zip: zip, file, md5, title_year, release_year, table_title, kind,
                       used, why_not_used
  coverage.csv         measure x category x fiscal_year: states (50 + DC), territories, US present, basis
  checks.csv           state sums vs US row, components vs totals, rank-table aggregation vs state tables,
                       revisions, US continuity

Measures (dollars in thousands unless unit says otherwise)
  rd_exp           category all; src_federal, src_state_local, src_institution, src_business, src_nonprofit,
                   src_other; fld_cs, fld_geo, fld_life, fld_math, fld_math_cs, fld_phys, fld_psych,
                   fld_social, fld_sci_nec, fld_eng, fld_se, fld_non_se
  rd_exp_rev       all: the latest release's revised standard-form series (FY2010-24 from the FY2024 release);
                   rd_exp/all keeps each year's own-release value (consistent with its source / field detail)
  rd_exp_both_pop  all (standard + short-form populations)
  rd_exp_federal   all, ag_dod, ag_doe, ag_hhs, ag_nasa, ag_nsf, ag_usda, ag_other (from ranking tables)
  personnel_hc     all, pi, other, postdoc (2010-15), researchers, technicians, support (2022+)
  personnel_fte    all, researchers, technicians, support (2022+)

Caveats
* FY2010 is the first HERD year; it replaced the Survey of R&D Expenditures at Universities and Colleges
  (Academic R&D Expenditures Survey). FY2003-09 values here are as republished in the HERD releases but are
  pre-redesign: HERD added non-S&E fields' detail, broadened institution funds (unrecovered indirect costs,
  cost sharing), and changed the population, so there is a level break at 2010.
* From FY2012 institutions with < $1M R&D answer a short form; state tables (except the "both populations"
  one) cover the standard-form population. The "United States" row includes Puerto Rico, Guam, and the U.S.
  Virgin Islands, which are kept as PR, GU, VI.
* Fields: through FY2015 (and in 2010-12 state tables) mathematics and computer sciences are combined or
  separately listed depending on the table ("Math and computer sciences" -> fld_math_cs); from FY2016 the
  taxonomy was revised (geosciences, atmospheric & ocean sciences replaces environmental sciences;
  computer and information sciences; mathematics and statistics). fld_math_cs is derived where both parts
  are published, for continuity.
* Personnel: headcounts of PIs, other personnel and postdocs (FY2010-19; postdocs only through FY2015);
  FY2020 redesign to researchers / R&D technicians / R&D support staff with headcounts and FTEs. Postdocs
  are part of "researchers" from FY2020 and no longer shown separately. No state table in FY2020-21.
  FY2010-11 tables leave nonreporting institutions blank (not imputed), so those state sums undercount
  (Wyoming: U. Wyoming blank, so WY is missing; US = 772,329 in FY2010 vs 916,822 in FY2012).
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import warnings
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "nsf_herd"
OUT = ROOT / "data" / "herd"

NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
STATES51 = set(NAMES)
TERR = {"Puerto Rico": "PR", "Guam": "GU", "Virgin Islands": "VI", "U.S. Virgin Islands": "VI",
        "American Samoa": "AS", "Northern Mariana Islands": "MP", "Federated States of Micronesia": "FM",
        "Marshall Islands": "MH", "Palau": "PW"}
CODE = {**{v: k for k, v in NAMES.items()}, **TERR}
US_RE = re.compile(r"^(united states|all institutions|total, all institutions)[a-z]?$", re.I)
CONTROL_RE = re.compile(r"^(public|private)( institutions)?[a-z]?$", re.I)
YEAR_END = re.compile(r"((?:19|20)\d\d)(?:\s*[–-]\s*(\d{2,4}))?\s*[.;]?\s*$")
FOOT_RE = re.compile(r"^(NOTES?\b|SOURCES?\b|Notes?:|Sources?:|[a-z]{1,3} ?= |[a-z] [A-Z(])")
DIVISIONS = {"new england", "middle atlantic", "east north central", "west north central", "south atlantic",
             "east south central", "west south central", "mountain", "pacific", "outlying areas",
             "pacific and outlying areas", "other", "u.s. territories", "territories"}
UNIT = {"personnel_hc": "persons", "personnel_fte": "fte"}
HEADLINE = [("rd_exp", "all"), ("rd_exp_rev", "all"), ("rd_exp", "src_federal"), ("rd_exp", "src_state_local"),
            ("rd_exp", "src_institution"), ("rd_exp", "src_business"), ("rd_exp", "src_nonprofit"),
            ("rd_exp", "src_other"), ("rd_exp", "fld_se"), ("rd_exp", "fld_non_se"), ("rd_exp", "fld_cs"),
            ("rd_exp", "fld_math"), ("rd_exp", "fld_math_cs"), ("rd_exp", "fld_eng"), ("rd_exp", "fld_life"),
            ("rd_exp", "fld_phys"), ("rd_exp", "fld_geo"), ("rd_exp", "fld_psych"), ("rd_exp", "fld_social"),
            ("rd_exp", "fld_sci_nec"), ("rd_exp_both_pop", "all"), ("rd_exp_federal", "all"),
            ("rd_exp_federal", "ag_hhs"), ("rd_exp_federal", "ag_nsf"), ("rd_exp_federal", "ag_dod"),
            ("rd_exp_federal", "ag_doe"), ("rd_exp_federal", "ag_nasa"), ("rd_exp_federal", "ag_usda"),
            ("rd_exp_federal", "ag_other"), ("personnel_hc", "all"), ("personnel_hc", "pi"),
            ("personnel_hc", "other"), ("personnel_hc", "postdoc"), ("personnel_hc", "researchers"),
            ("personnel_hc", "technicians"), ("personnel_hc", "support"), ("personnel_fte", "all"),
            ("personnel_fte", "researchers")]


# ---------------------------------------------------------------- reading
def sources():
    """(zip, file, bytes) for every file in sources/nsf_herd/*.zip, read in place, one at a time."""
    for p in sorted(SRC.glob("*.zip")):
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                if not n.endswith("/"):
                    yield p.name, n, z.read(n)


def first_sheet(b: bytes) -> pd.DataFrame | None:
    for eng, kw in (("calamine", {}), ("xlrd", {"logfile": open(os.devnull, "w")})):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return pd.read_excel(io.BytesIO(b), header=None, sheet_name=0, engine=eng, engine_kwargs=kw)
        except Exception:
            pass
    return None


def clean(v) -> str:
    if isinstance(v, (int, float)) and not pd.isna(v):
        return str(int(v)) if v == int(v) else str(v)
    return " ".join(str(v).replace("\xa0", " ").split()) if isinstance(v, str) else ""


def title_of(df: pd.DataFrame) -> str:
    parts = []
    for v in df.iloc[:5, 0]:
        s = clean(v)
        if not s or s.startswith("("):
            continue
        parts.append(s)
        if YEAR_END.search(s) or len(parts) == 3:
            break
    t = " ".join(parts)
    return re.sub(r"^(Table [A-Z]?-?\d+)\.?\s*\|?\s*", r"\1. ", t, flags=re.I)[:300]


def year_of(title: str) -> int | None:
    m = YEAR_END.search(title.split(" | ")[0])
    if not m:
        return None
    start, end = m.group(1), m.group(2)
    return int(start) if not end else int(start[:4 - len(end)] + end)


def num(v):
    if isinstance(v, str):
        v = v.replace(",", "").strip()
    v = pd.to_numeric(v, errors="coerce")
    return None if pd.isna(v) else float(v)


def state_code(s: str) -> str | None:
    for name, code in CODE.items():
        if s == name or (s.startswith(name) and re.fullmatch(r"[a-z,*]{1,3}", s[len(name):])):
            return code
    return None


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def name_keys(s: str) -> list[str]:
    """Match keys for an institution name; the second drops a footnote letter glued to the end ('U.b')."""
    keys = [norm_name(s)]
    m = re.match(r"^(.*[.)A-Z])[a-z]{1,2}$", s)
    if m:
        keys.append(norm_name(m.group(1)))
    return keys


def lookup(m: dict, name: str) -> str | None:
    """State for a ranked institution: exact name, then footnote letter(s) dropped, then a unique-state prefix
    match (names cut off by a line wrap, or a combined entry such as "U. Maryland" for its campuses)."""
    key = norm_name(name)
    for k in name_keys(name) + [key[:-1], key[:-2]]:
        if k in m:
            return m[k]
    for k in (key, key[:-1], key[:-2]):
        if len(k) >= 8:
            hits = {v for kk, v in m.items() if kk.startswith(k)}
            if len(hits) == 1:
                return hits.pop()
    hits = {v for kk, v in m.items() if len(kk) >= 12 and key.startswith(kk)}
    return hits.pop() if len(hits) == 1 else None


# ---------------------------------------------------------------- table grid
def grid(df: pd.DataFrame):
    """Split a published table into (label columns, data columns with header text, body start row)."""
    lab = df.map(clean)
    start = None
    for i in range(1, min(len(df), 40)):
        for j in range(min(3, df.shape[1])):
            s = lab.iat[i, j]
            if s and (US_RE.match(s) or state_code(s)):
                start = i
                break
        if start is not None:
            break
    if start is None:
        return None
    body = df.iloc[start:]
    hdr_rows = lab.iloc[1:start].copy()
    data = []
    for j in range(1, df.shape[1]):
        share = body.iloc[:, j].map(lambda v: num(v) is not None).mean()
        if share >= 0.15:
            data.append(j)
    if not data:
        return None
    first = data[0]
    # forward-fill each header row across the data columns (merged group headings)
    hdr = {}
    filled = hdr_rows.iloc[:, first:].replace("", None).T.ffill().T.fillna("")
    for j in data:
        hdr[j] = " ".join(x for x in filled[j] if x).lower()
    data = [j for j in data if "rank" not in hdr[j]]
    return list(range(first)), data, hdr, start, lab


def rows_of(df: pd.DataFrame, inst: bool, rank: bool = False):
    """Yield (kind, state, name, {col: value}) for the body rows: kind in us / state / inst."""
    g = grid(df)
    if g is None:
        return None
    labcols, data, hdr, start, lab = g
    cur = None
    out = []
    for i in range(start, len(df)):
        cells = [(j, lab.iat[i, j]) for j in labcols if lab.iat[i, j]]
        vals = {j: num(df.iat[i, j]) for j in data}
        if not cells:
            continue
        j0, s0 = cells[0]
        right_j, right = cells[-1]
        if US_RE.match(s0) and len(cells) == 1:
            out.append(("us", "US", s0, vals))
            continue
        code = state_code(s0) if (j0 == 0 or len(cells) == 1 or not inst) else None
        if code and (len(cells) == 1 or not inst):
            cur = code
            out.append(("state", code, s0, vals))
            continue
        if code:                                  # state, control and first institution on one row
            cur = code
        if not inst:
            continue
        if FOOT_RE.match(right):
            break
        if CONTROL_RE.match(right) or right.lower() in DIVISIONS or (cur is None and not rank):
            continue
        if rank and out and out[-1][0] == "inst" and all(v is None for v in out[-1][3].values()):
            out[-1] = ("inst", cur, out[-1][2] + " " + right, vals)      # name wrapped onto a second line
            continue
        out.append(("inst", cur, right, vals))
    return out, data, hdr


# ---------------------------------------------------------------- classify
EXCLUDE = re.compile(r"medical school|clinical trial|subrecipient|passed through|received from|imputed|"
                     r"historically black|hispanic|foreign|equipment|in the short form survey population|"
                     r"short form institutions|public institutions|private institutions")


def classify(t: str) -> str | None:
    t = t.lower()
    if EXCLUDE.search(t):
        return None
    if "personnel" in t and "by state" in t:
        return "personnel"
    if "ranked" in t:
        if re.search(r"^table \S+ federally financed higher education r&d expenditures(?: at institutions in the "
                     r"standard form survey population)?, ranked by all federal r&d expenditures, by federal agency", t):
            return "rank_agency"
        if re.search(r"^table \S+ higher education r&d expenditures at higher education institutions in the "
                     r"standard form and short form survey populations, ranked by all r&d expenditures, by source", t):
            return "rank_source_both"
        if re.search(r"^table \S+ higher education r&d expenditures(?: at institutions in the "
                     r"standard form survey population)?, ranked by all r&d expenditures, by source of funds", t):
            return "rank_source"
        if re.search(r"^table \S+ higher education r&d expenditures(?: at institutions in the standard form survey "
                     r"population)?, ranked by all r&d expenditures, by r&d field", t):
            return "rank_field"
        return None
    if "by state" not in t and "and state" not in t:
        return None
    if "federally financed" in t or "nonfederally" in t:
        return None
    if re.search(r"in both (the )?.*survey|standard form and short form survey populations", t):
        return "both_pop"
    if "science and engineering fields" in t:
        return "trend_se"
    if "source of funds" in t:
        return "source"
    if "r&d field" in t:
        return "field"
    if re.search(r"by (geographic division and )?state(, institutional control, and institution)?: fys? ", t) or \
            re.search(r"standard form survey population, by state: fys", t):
        return "trend_total"
    return None


# ---------------------------------------------------------------- column maps
def year_cols(data, hdr):
    out = {}
    for j in data:
        ys = re.findall(r"\b((?:19|20)\d\d)\b", hdr[j])
        if len(ys) == 1 and not re.search(r"[a-z]", re.sub(r"\b(fy|fys)\b", "", hdr[j])):
            out[j] = int(ys[0])
    return out


SRC_MAP = [("all r&d", "all"), ("total", "all"), ("federal", "src_federal"), ("state and local", "src_state_local"),
           ("institution", "src_institution"), ("business", "src_business"), ("industry", "src_business"),
           ("nonprofit", "src_nonprofit"), ("all other", "src_other")]
FLD_MAP = [("all r&d", "all"), ("non-s&e", "fld_non_se"), ("all s&e", "fld_se"), ("math and computer", "fld_math_cs"),
           ("computer", "fld_cs"), ("environmental", "fld_geo"), ("geosciences", "fld_geo"), ("life", "fld_life"),
           ("math", "fld_math"), ("physical", "fld_phys"), ("psychology", "fld_psych"), ("social", "fld_social"),
           ("nec", "fld_sci_nec"), ("engineering", "fld_eng")]
AG_MAP = [("all federal", "all"), ("dod", "ag_dod"), ("doe", "ag_doe"), ("hhs", "ag_hhs"), ("nasa", "ag_nasa"),
          ("nsf", "ag_nsf"), ("usda", "ag_usda"), ("other", "ag_other")]


def keyword_cols(data, hdr, mapping):
    out, used = {}, set()
    for j in data:
        h = hdr[j].replace("\n", " ")
        for kw, cat in mapping:
            if kw in h:
                if cat not in used:
                    out[j] = cat
                    used.add(cat)
                break
    return out


def personnel_cols(data, hdr, year):
    out = {}
    for j in data:
        h = hdr[j]
        ys = [int(y) for y in re.findall(r"\b(20\d\d)\b", h)]
        if ys and ys[-1] != year:
            continue
        meas = "personnel_fte" if "fte" in h else "personnel_hc"
        rest = re.sub(r"\b20\d\d\b", "", h)
        cat = ("postdoc" if "postdoc" in rest else "pi" if "principal" in rest else "other" if "other personnel" in rest
               else "researchers" if "researcher" in rest else "technicians" if "technician" in rest
               else "support" if "support" in rest else "all")
        if (meas, cat) not in out.values():
            out[j] = (meas, cat)
    return out


# ---------------------------------------------------------------- parse one table
def parse(df, kind, year):
    """Returns (state rows [dict], institution rows [dict]) for a classified table."""
    inst_tbl = kind in ("source", "field", "personnel", "both_pop", "trend_total") or kind.startswith("rank")
    res = rows_of(df, inst=inst_tbl, rank=kind.startswith("rank"))
    if res is None:
        return [], []
    rows, data, hdr = res
    if kind in ("trend_total", "trend_se"):
        cmap = {j: (y, "rd_exp", "all" if kind == "trend_total" else "fld_se") for j, y in year_cols(data, hdr).items()}
    elif kind == "both_pop":
        cmap = {data[0]: (year, "rd_exp_both_pop", "all")}
    elif kind in ("source", "rank_source"):
        cmap = {j: (year, "rd_exp", c) for j, c in keyword_cols(data, hdr, SRC_MAP).items()}
    elif kind in ("field", "rank_field"):
        cmap = {j: (year, "rd_exp", c) for j, c in keyword_cols(data, hdr, FLD_MAP).items()}
    elif kind == "rank_agency":
        cmap = {j: (year, "rd_exp_federal", c) for j, c in keyword_cols(data, hdr, AG_MAP).items()}
    elif kind == "personnel":
        cmap = {j: (year, m, c) for j, (m, c) in personnel_cols(data, hdr, year).items()}
    else:
        return [], []
    st, inst = [], []
    for k, code, name, vals in rows:
        if k == "inst":
            inst.append(dict(state=code, name=name, vals={cmap[j]: vals[j] for j in cmap}))
        else:
            for j, (y, m, c) in cmap.items():
                if vals.get(j) is not None:
                    st.append(dict(fiscal_year=y, state=code, measure=m, category=c, value=vals[j]))
    if kind.startswith("rank") or kind == "trend_total":
        return st, inst                  # rank: US row only (institutions mapped to states later); multi-year
                                         # institution tables: state rows only
    # states whose own row is blank: sum the institutions listed under them
    have = {(r["state"], r["fiscal_year"], r["measure"], r["category"]) for r in st}
    sums = defaultdict(float)
    count = Counter()
    for r in inst:
        for key, v in r["vals"].items():
            if v is not None:
                sums[(r["state"],) + key] += v
                count[(r["state"],) + key] += 1
    for (code, y, m, c), v in sums.items():
        if (code, y, m, c) not in have:
            st.append(dict(fiscal_year=y, state=code, measure=m, category=c, value=v,
                           note=f"sum of {count[(code, y, m, c)]} institutions listed under the state"))
    # tables without a US row: the US value is the sum of states and territories
    if kind in ("both_pop", "personnel"):
        tot = defaultdict(float)
        for r in st:
            tot[(r["fiscal_year"], r["measure"], r["category"])] += r["value"]
        has_us = {(r["fiscal_year"], r["measure"], r["category"]) for r in st if r["state"] == "US"}
        st += [dict(fiscal_year=y, state="US", measure=m, category=c, value=v,
                    note="derived: sum of states and territories (table has no US row)")
               for (y, m, c), v in tot.items() if (y, m, c) not in has_us]
    return st, inst


# ---------------------------------------------------------------- build
def build():
    OUT.mkdir(parents=True, exist_ok=True)
    files, md5s = [], {}
    tables = []                                    # (zip, file, title, kind, title_year, df)
    for zp, name, b in sources():
        rec = dict(zip=zp, file=name, md5=hashlib.md5(b).hexdigest(), title_year=None, table_title="",
                   kind="", used="no", why_not_used="")
        files.append(rec)
        low = name.lower()
        if not low.endswith((".xls", ".xlsx")):
            rec["why_not_used"] = ("PDF copy of a published table" if low.endswith(".pdf") and "tab" in low else
                                   "technical notes (PDF)" if "tech_notes" in low else
                                   "erratum (PDF); corrected table is in the zip" if "erratum" in low else
                                   "PDF of all tables" if low.endswith(".pdf") else
                                   "index of table titles" if low.endswith(".txt") else "not a data table")
            continue
        df = first_sheet(b)
        if df is None:
            rec["why_not_used"] = "unreadable"
            continue
        title = title_of(df)
        kind = classify(title)
        rec.update(table_title=title, title_year=year_of(title), kind=kind or "")
        if kind:
            tables.append((zp, name, title, kind, rec["title_year"], df, rec))
    release = {z: Counter(r["title_year"] for r in files if r["zip"] == z and r["title_year"]).most_common(1)[0][0]
               for z in {r["zip"] for r in files}}
    for r in files:
        r["release_year"] = release[r["zip"]]

    state_rows, inst_by_rel, rank = [], defaultdict(dict), []
    for zp, name, title, kind, ty, df, rec in tables:
        year = release[zp]
        if kind not in ("trend_total", "trend_se") and ty != year:
            rec["why_not_used"] = f"title year {ty} is not the release year {year}"
            continue
        st, inst = parse(df, kind, year)
        base = dict(release_year=year, source_zip=zp, source_file=name.split("/")[-1], table_title=title, kind=kind)
        for r in inst:                                   # institution -> state map for this release
            if not kind.startswith("rank"):
                for k in name_keys(r["name"]):
                    inst_by_rel[year].setdefault(k, r["state"])
        if kind.startswith("rank"):
            rank.append((year, kind, inst, st, base, rec))
            continue
        if st:
            rec["used"] = "yes"
            state_rows += [{**base, "note": "", **x} for x in st]
        else:
            rec["why_not_used"] = "classified but no state rows parsed"

    # ranking tables -> states through the institution names
    match_log = []
    for year, kind, inst, us, base, rec in rank:
        m = inst_by_rel.get(year, {})
        agg, miss, tot_all, tot_miss = defaultdict(float), [], 0.0, 0.0
        for r in inst:
            code = lookup(m, r["name"])
            first = next(iter(r["vals"].values()), None) or 0.0
            tot_all += first
            if code is None:
                miss.append(r["name"])
                tot_miss += first
                continue
            for (y, meas, cat), v in r["vals"].items():
                if v is not None:
                    agg[(code, y, meas, cat)] += v
        match_log.append(dict(release_year=year, kind=kind, source=base["source_file"], institutions=len(inst),
                              unmatched=len(miss), unmatched_share_pct=round(100 * tot_miss / tot_all, 3) if tot_all else None,
                              unmatched_examples="; ".join(miss[:6])))
        rec["used"] = "yes" if kind == "rank_agency" or (kind != "rank_agency" and year == 2024) else "check only"
        note = (f"sum over ranked institutions mapped to states by name ({len(inst) - len(miss)} of {len(inst)} "
                f"matched); standard-form institutions only")
        rk = [dict(fiscal_year=y, state=c, measure=meas, category=cat, value=v, note=note, **base)
              for (c, y, meas, cat), v in agg.items()]
        rk += [{**base, "note": "ranking-table total", **x} for x in us]
        for r in rk:
            r["kind"] = kind
        state_rows += rk

    df = pd.DataFrame(state_rows)
    df["lag"] = df.release_year - df.fiscal_year
    df = df[df.lag >= 0]
    # priority: state tables before ranking aggregates; own year (lag 0) first, then the earliest later release
    pri = {"source": 0, "field": 0, "personnel": 0, "both_pop": 0, "trend_total": 1, "trend_se": 1,
           "rank_agency": 2, "rank_source": 3, "rank_field": 3, "rank_source_both": 9}
    df["pri"] = df.kind.map(pri)
    df = df.sort_values(["lag", "pri", "source_file"])
    key = ["fiscal_year", "state", "measure", "category"]
    best = df[df.pri < 9].drop_duplicates(key).copy()
    # ranking sums only stand in where no state table gives the measure for that year (FY2024 source / field)
    stated = set(map(tuple, best.loc[best.pri < 2, ["fiscal_year", "measure", "category"]].values))
    keep = pd.Series([tuple(x) not in stated for x in best[["fiscal_year", "measure", "category"]].values],
                     index=best.index)
    best = best[(best.pri < 3) | keep]
    # the latest release's revised state series (trend table), kept as its own measure for time series use
    tr = df[(df.kind == "trend_total") & (df.measure == "rd_exp") & (df.category == "all") & (df.fiscal_year >= 2010)]
    tr = tr[tr.release_year == tr.release_year.max()].drop_duplicates(key).assign(
        measure="rd_exp_rev", note="as revised in the latest release")
    best = derive(pd.concat([best, tr], ignore_index=True))
    best["unit"] = best.measure.map(UNIT).fillna("usd_thousands")
    best["basis"] = best.apply(basis, axis=1)
    best.loc[best.fiscal_year < 2010, "note"] = (best.loc[best.fiscal_year < 2010, "note"].fillna("") +
                                                 "; pre-HERD (Academic R&D Expenditures Survey) as republished").str.strip("; ")
    best.loc[best.lag > 0, "note"] = (best.loc[best.lag > 0, "note"].fillna("") + best.loc[best.lag > 0, "lag"].map(
        lambda l: f"; from a release {int(l)} year(s) later")).str.strip("; ")
    best = best.sort_values(key)
    cols = ["fiscal_year", "state", "measure", "category", "value", "unit", "basis", "note", "release_year",
            "source_zip", "source_file", "table_title"]
    best[cols].to_csv(OUT / "herd_state.csv", index=False)

    wide = best.pivot_table(index=["fiscal_year", "state"], columns=["measure", "category"], values="value",
                            aggfunc="first")
    order = [c for c in HEADLINE if c in wide.columns]
    wide = wide[order]
    wide.columns = [f"{m}__{c}" for m, c in wide.columns]
    wide.reset_index().to_csv(OUT / "herd_state_wide.csv", index=False)

    fl = pd.DataFrame(files)
    fl["base"] = fl.file.str.split("/").str[-1]
    in_best = set(map(tuple, best[["source_zip", "source_file"]].drop_duplicates().values))
    hit = pd.Series([(z, f) in in_best for z, f in fl[["zip", "base"]].values], index=fl.index)
    parsed = fl.used != "no"
    fl.loc[parsed & hit, "used"] = "yes"
    fl.loc[parsed & ~hit, "used"] = "check only"
    fl.loc[parsed & ~hit, "why_not_used"] = "parsed for checks.csv; values superseded by another table or release"
    fl.loc[(fl.used == "no") & (fl.why_not_used == ""), "why_not_used"] = fl[(fl.used == "no") & (fl.why_not_used == "")].apply(
        why_not, axis=1)
    fl = fl[["zip", "file", "md5", "title_year", "release_year", "table_title", "kind", "used", "why_not_used"]]
    fl.to_csv(OUT / "files.csv", index=False)

    cov = best.groupby(["measure", "category", "fiscal_year"]).agg(
        n_states=("state", lambda s: s.isin(STATES51).sum()),
        territories=("state", lambda s: " ".join(sorted(set(s) & set(TERR.values())))),
        us=("state", lambda s: "yes" if (s == "US").any() else "no"),
        basis=("basis", lambda s: "; ".join(sorted(set(s)))),
        source=("source_file", lambda s: " ".join(sorted(set(s))))).reset_index()
    cov.to_csv(OUT / "coverage.csv", index=False)
    checks(best, df, pd.DataFrame(match_log), fl)


def basis(r):
    if r.kind.startswith("rank"):
        return "ranking-table institutions aggregated to states (standard form)" if r.state != "US" else "ranking-table total"
    if r.measure == "rd_exp_both_pop":
        return "standard + short form populations"
    if r.fiscal_year < 2010:
        return "pre-HERD (Academic R&D Expenditures Survey)"
    if r.fiscal_year < 2012:
        return "HERD (single population)"
    return "HERD standard form population"


def why_not(r):
    t = r.table_title.lower()
    if r.kind:
        return "superseded / duplicate of a table already used"
    if "ranked" in t:
        return "institution ranking on a topic not aggregated to states"
    if "by state" in t:
        return "state x institution table on a topic not kept (medical school, clinical trials, subrecipients, short form)"
    return "national table; no state detail"


def derive(best):
    """fld_se = all - non-S&E where not published; fld_math_cs = math + cs where both are published."""
    key = ["fiscal_year", "state"]
    rd = best[best.measure == "rd_exp"].pivot_table(index=key, columns="category", values="value", aggfunc="first")
    src = best[best.measure == "rd_exp"].drop_duplicates(key).set_index(key)[
        ["release_year", "source_zip", "source_file", "kind", "lag", "pri"]]
    add = []
    if {"all", "fld_non_se"} <= set(rd.columns):
        s = (rd["all"] - rd["fld_non_se"]).dropna()
        have = rd["fld_se"].dropna().index if "fld_se" in rd else []
        s = s[~s.index.isin(have)]
        add.append(pd.DataFrame({"value": s, "category": "fld_se", "note": "derived: all - non-S&E"}))
    if {"fld_math", "fld_cs"} <= set(rd.columns):
        s = (rd["fld_math"] + rd["fld_cs"]).dropna()
        have = rd["fld_math_cs"].dropna().index if "fld_math_cs" in rd else []
        s = s[~s.index.isin(have)]
        add.append(pd.DataFrame({"value": s, "category": "fld_math_cs", "note": "derived: math + computer sciences"}))
    if not add:
        return best
    a = pd.concat(add).join(src).reset_index().assign(measure="rd_exp", table_title="")
    return pd.concat([best, a], ignore_index=True)


# ---------------------------------------------------------------- sanity checks
def checks(best, alldf, match, fl):
    out = []
    # 1. state rows (51 and with territories) vs the US row of the same table
    for (y, m, c, z, src), g in alldf.groupby(["fiscal_year", "measure", "category", "source_zip", "source_file"]):
        us = g.loc[(g.state == "US") & ~g.note.fillna("").str.startswith("derived"), "value"]
        if us.empty or not us.iat[0]:
            continue
        s51, sall = g[g.state.isin(STATES51)].value.sum(), g[g.state != "US"].value.sum()
        out.append(dict(check="state_sum_vs_us", fiscal_year=y, measure=m, category=c, source=f"{z}/{src}",
                        us=us.iat[0], sum_51=s51, sum_with_territories=sall,
                        diff_pct=round(100 * (sall / us.iat[0] - 1), 3)))
    # 2. components vs totals in the selected data
    w = best.pivot_table(index=["fiscal_year", "state"], columns=["measure", "category"], values="value", aggfunc="first")
    def comp(name, meas, parts, total):
        cols = [(meas, p) for p in parts if (meas, p) in w]
        if (meas, total) not in w or not cols:
            return
        s = w[cols].sum(axis=1, min_count=1)
        t = w[(meas, total)]
        for (y, st), a, b in zip(w.index, s, t):
            if pd.notna(a) and pd.notna(b) and b:
                out.append(dict(check=name, fiscal_year=y, state=st, measure=meas, category=total, us=b, sum_51=a,
                                diff_pct=round(100 * (a / b - 1), 3)))
    comp("sources_vs_total", "rd_exp", ["src_federal", "src_state_local", "src_institution", "src_business",
                                        "src_nonprofit", "src_other"], "all")
    comp("agencies_vs_federal_total", "rd_exp_federal", ["ag_dod", "ag_doe", "ag_hhs", "ag_nasa", "ag_nsf",
                                                         "ag_usda", "ag_other"], "all")
    for (y, st), r in w.iterrows():
        f = [("rd_exp", c) for c in ("fld_cs", "fld_math", "fld_math_cs", "fld_geo", "fld_life", "fld_phys",
                                      "fld_psych", "fld_social", "fld_sci_nec", "fld_eng", "fld_non_se") if ("rd_exp", c) in w]
        vals = {c: r[(m, c)] for m, c in f if pd.notna(r[(m, c)])}
        if "fld_math_cs" in vals and ("fld_math" in vals or "fld_cs" in vals):
            vals.pop("fld_math_cs")
        if vals and pd.notna(r.get(("rd_exp", "all"))) and r[("rd_exp", "all")]:
            a = sum(vals.values())
            out.append(dict(check="fields_vs_total", fiscal_year=y, state=st, measure="rd_exp", category="all",
                            us=r[("rd_exp", "all")], sum_51=a, diff_pct=round(100 * (a / r[("rd_exp", "all")] - 1), 3)))
    # 3. ranking-table federal total aggregated to states vs the state table's federal source
    if ("rd_exp_federal", "all") in w and ("rd_exp", "src_federal") in w:
        for (y, st), a, b in zip(w.index, w[("rd_exp_federal", "all")], w[("rd_exp", "src_federal")]):
            if pd.notna(a) and pd.notna(b) and b:
                out.append(dict(check="rank_federal_vs_state_federal", fiscal_year=y, state=st, measure="rd_exp_federal",
                                category="all", us=b, sum_51=a, diff_pct=round(100 * (a / b - 1), 3)))
    # 4. ranking-table all-R&D totals aggregated to states vs state-table totals (same release)
    rk = alldf[(alldf.kind == "rank_source") & (alldf.category == "all") & (alldf.lag == 0)]
    stt = best[(best.measure == "rd_exp") & (best.category == "all")].set_index(["fiscal_year", "state"]).value
    for r in rk.itertuples():
        b = stt.get((r.fiscal_year, r.state))
        if b:
            out.append(dict(check="rank_total_vs_state_total", fiscal_year=r.fiscal_year, state=r.state,
                            measure="rd_exp", category="all", source=r.source_file, us=b, sum_51=r.value,
                            diff_pct=round(100 * (r.value / b - 1), 3)))
    # 5. revisions: selected (own-year) value vs the latest release that has the same state-year total
    tr = alldf[(alldf.measure == "rd_exp") & (alldf.category == "all") & alldf.kind.isin(["trend_total", "source"])]
    latest = tr.sort_values("release_year").drop_duplicates(["fiscal_year", "state"], keep="last").set_index(
        ["fiscal_year", "state"])
    for (y, st), v in stt.items():
        if (y, st) in latest.index:
            l = latest.loc[(y, st)]
            if l.release_year != best.loc[(best.fiscal_year == y) & (best.state == st) & (best.measure == "rd_exp") &
                                          (best.category == "all"), "release_year"].iat[0]:
                out.append(dict(check="revision_latest_release", fiscal_year=y, state=st, measure="rd_exp",
                                category="all", source=l.source_file, us=v, sum_51=l.value,
                                diff_pct=round(100 * (l.value / v - 1), 3)))
    # 6. US continuity
    us = w.xs("US", level="state") if "US" in w.index.get_level_values("state") else None
    if us is not None:
        for mc in [("rd_exp", "all"), ("rd_exp", "src_federal"), ("rd_exp_federal", "all"), ("personnel_hc", "all")]:
            if mc in us:
                s = us[mc].dropna()
                for y, v, ch in zip(s.index, s.values, s.pct_change().values * 100):
                    out.append(dict(check="us_continuity", fiscal_year=y, state="US", measure=mc[0], category=mc[1],
                                    us=v, diff_pct=None if pd.isna(ch) else round(ch, 2),
                                    flag="jump" if pd.notna(ch) and abs(ch) > 12 else ""))
    ck = pd.DataFrame(out)
    ck["flag"] = ck.get("flag", pd.Series(index=ck.index, dtype=object)).fillna("")
    ck.loc[(ck.check != "us_continuity") & (ck.diff_pct.abs() > 1), "flag"] = "> 1%"
    ck = pd.concat([ck, match.assign(check="rank_name_match")], ignore_index=True)
    ck.to_csv(OUT / "checks.csv", index=False)
    report(best, ck, fl)


def report(best, ck, fl):
    pd.set_option("display.width", 220)
    print(f"files: {len(fl)}, used {(fl.used == 'yes').sum()}, check only {(fl.used == 'check only').sum()}")
    print(fl[fl.used != "no"].groupby(["zip"]).release_year.first().to_string())
    for c in ("state_sum_vs_us", "sources_vs_total", "fields_vs_total", "agencies_vs_federal_total",
              "rank_federal_vs_state_federal", "rank_total_vs_state_total", "revision_latest_release"):
        s = ck[ck.check == c]
        if len(s):
            print(f"\n{c}: {len(s)} rows, median diff {s.diff_pct.median():.3f}%, |diff|>1%: "
                  f"{(s.diff_pct.abs() > 1).sum()}  max |diff| {s.diff_pct.abs().max():.2f}%")
    print("\nrank name matching:")
    print(ck[ck.check == "rank_name_match"][["release_year", "kind", "institutions", "unmatched",
                                             "unmatched_share_pct"]].to_string(index=False))
    us = best[(best.state == "US") & (best.measure == "rd_exp") & (best.category == "all")]
    print("\nUS rd_exp/all ($B):", " ".join(f"{int(y)}:{v / 1e6:.1f}" for y, v in zip(us.fiscal_year, us.value)))
    cov = best[best.state.isin(STATES51)].groupby(["measure", "category"]).fiscal_year.agg(
        lambda s: f"{int(s.min())}-{int(s.max())} ({s.nunique()} yrs)")
    print("\ncoverage (50+DC):\n" + cov.to_string())


if __name__ == "__main__":
    build()
