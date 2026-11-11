"""NSF/NCSES Survey of Earned Doctorates (SED): research doctorates by state, field and citizenship; stay rates.

    python -m ipeds_clean.sed            # -> data/sed/*.csv and a printed sanity-check report

Source: the SED published data tables in sources/nsf_sed/, one folder (1994-2004, .xls; 1996 is Lotus 1-2-3
.wks saved as .xls, read by a small reader here) or zip (2005-2025 releases, .xls/.xlsx) per download. Zips are
read in place (nested zips too). Folder and zip names do not give the doctorate year (nsf09311.zip is 2006,
nsf11321.zip holds 2007 and 2008, tab07305.zip is 2005, data_tables.zip is 2017, nsf2X3XX zips are 2018-2025,
nsf15326.zip is not SED at all), so each file's year is read from its title: the last year named in it
("...: 2016", "...: 2015-25"). Tables are found by title, not number. The state is that of the doctorate-granting
institution, and the year is the academic year ending in it (July-June).

What is used
* State tables (sed_state.csv, state rows): 1994-2001 "Institutions conferring S&E doctorates / Doctorates
  awarded, by State, institution, and major field" (state subtotal rows; 1994-95 print the fields in two
  vertical halves, both read); 2003-2008 "Doctorates awarded, by state, institution, and major field";
  2009-2020 "Doctorate-granting institutions, by state/location and major S&E [and non-S&E] fields" (two
  tables per year, state rows); 2021-2025 Table 7-10 "Research doctorate recipients, by state or location of
  doctorate institution and broad field". The US row is the table's all-institutions / United States row
  (it includes Puerto Rico); PR is kept as state "PR". 2002's state table (Table 6) is in sources/nsf_sed/2002/
  (added later), so every year 1994-2025 has state values.
* Citizenship (state "US" only; no SED table crosses state by citizenship): the trend tables "Doctorate(s)
  awarded / recipients, by (sex,) citizenship status, and major field" (2003-2008 releases) and "by citizenship
  status and major field" / Table 1-7 (2012-2025 releases). Each year's value comes from the release for that
  year, or else the earliest later release (1994-2002 from the 2003 release, 2009-2011 from 2012). Measures
  doctorates_uspr, doctorates_temp_visa, doctorates_temp_visa_share (% of all recipients in the same table,
  which includes citizenship unknown).
* Postgraduation commitments (state "US"): own-year "Definite postgraduation plans/commitments of doctorate
  recipients, by citizenship status and major field" (1996-2020; 1994-95 layout not parsed, the 2005 download
  has only the percentage table, 2009-2011 publish percentages only) and Tables 6-1/6-2/6-3 (2021-2025): recipients
  with definite commitments, of whom in the U.S. / abroad, for all, U.S. citizens + permanent residents and
  temporary visa holders. stay_rate_* = 100 * definite commitments in the U.S. / all definite commitments
  (NSF's basis; unknown location stays in the denominator). The digest figures "Stay rate of temporary visa
  holders with definite U.S. commitments, by S&E / non-S&E fields" (2009-2012 releases, 1989-2012) fill
  temp_visa_stay_rate for the years before 2001 and are checked against the computed rate where both exist.
* sed_us.csv (national, by country): "Doctorate recipients with temporary visas intending to stay in the
  United States after doctorate receipt, by country of citizenship" (2009-2025 releases, 7 years each; number of
  temporary visa recipients and % intending to stay, i.e. who said they plan to stay, whatever their
  commitment), and the selected-years "Postgraduation location of doctorate recipients with temporary visas"
  (2009-2011) / Table 2-4 (2021-2025) by citizenship.
* National trend Table 1-1 / "Doctorate recipients from U.S. colleges and universities: 1958-" is used only
  for checks.

Not used, and why, is listed per file in files.csv. Tables by sex, race, age, debt, funding, time to degree,
institution rankings (no state column) and the 2009-2020 "by state, broad field and sex" tables (the
institution tables above give the same states without the sex split or D suppression) are not used.

Outputs (data/sed/):
  sed_state.csv       year, state, measure, field, value, source_file, table_title, note, container
  sed_state_wide.csv  one row per state-year, columns <measure>__<field> for the headline fields
  sed_us.csv          state ("US"), year, geo, geo_level, measure, field, value, release, source_file, ...
  files.csv           every file: container, file, md5, detected_year, table_title, kind, used, why_not_used
  coverage.csv        measure x field x year: states (50 + DC) covered, territories, US present
  checks.csv          state sums vs US, US continuity, cross-table and cross-release agreement, share ranges

Fields (codes as published or summed from published parts; "derived" in note when summed):
  all, se, non_se; life_sci (agricultural + biological/biomedical + health), ag, bio, health, ag_bio;
  phys_earth (physical sciences + geosciences), phys_sci, earth; math_cs, math, cs; phys_math_cs (the
  2009-2014 "physical sciences", which includes math and computer sciences); psych_soc, psych, soc;
  engineering; multidisc (2021+); education; humanities_arts, humanities, arts; other_non_se (non-S&E other
  than education and humanities/arts, business included), business, other_excl_business (2021+);
  se_excl_health (S&E without health sciences, for comparing across the 2009 break).

Series breaks and caveats
* 1994-2008 tables put health sciences in non-S&E; from 2009 health is in S&E (life sciences). "se" jumps in
  2009 for this reason: compare se_excl_health across 2008/2009. State tables before 2009 have no health column.
* 2009-2014 "physical sciences" includes mathematics and computer sciences and "social sciences" includes
  psychology; from 2015 the broad fields are those listed above. 2009-2014 "Humanities" vs 2015+ "Humanities
  and arts" is a label change in the tables (composition of the arts not stated in the xls notes).
* 2021: new field taxonomy (aligned with the NCSES Taxonomy of Disciplines; multidisciplinary/interdisciplinary
  sciences becomes its own field, business shown separately) and the tables say "research doctorate
  recipients". Later releases revise earlier years onto "historical/trend" fields, so values for a given year
  differ slightly between releases (2020 all fields: 55,283 in the 2020 release, 55,224 in 2021, 55,200 in
  2025). Values here are from the release for that year where one exists.
* Through 2020 the tables say "doctorates" / "doctorate recipients"; from 2021 "research doctorate recipients".
  The SED covers research doctorates throughout (professional degrees such as MD/JD are out of scope); the xls
  notes do not document a change in inclusion rules, and the releases' own trend tables carry one continuous
  series. 1994-2000 state tables were S&E tables with non-S&E and grand-total columns.
* The 2000 and 2001 state subtotals sum to 0.5-0.9% less than the published all-institutions total (the
  subtotals equal their institution rows; the gap is in the source). Other years agree within 0.5%.
* temporary visa holders: 1994-2003 tables say "non-U.S. citizens with temporary visas". Citizenship unknown
  (about 2,000-3,500 a year to 2008) is in "all" but in neither group, so the share is a lower bound.
* D = suppressed cells are missing. Nothing is imputed; years without a table are absent.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import struct
import warnings
import zipfile
from collections import Counter, defaultdict

import pandas as pd

from .config import ROOT, SOURCES

SRC = SOURCES / "nsf_sed"
OUT = ROOT / "data" / "sed"

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
        "American Samoa": "AS", "Northern Mariana Islands": "MP"}
CODE = {**{v.lower(): k for k, v in NAMES.items()}, **{k.lower(): v for k, v in TERR.items()}}
US_RE = re.compile(r"^(total, )?all (u\.s\. )?institutions$|^united states$|^all states$")
YEARS_RE = re.compile(r"((?:19|20)\d\d)(?:\s*[–—-]\s*(\d{2,4})(?!\d))?")
HEADLINE = ["all", "se", "non_se", "life_sci", "phys_earth", "math_cs", "psych_soc", "engineering",
            "education", "humanities_arts", "other_non_se", "se_excl_health"]
FOOT_WORDS = {"total", "other", "sciences", "fields", "recipients", "engineering", "s&e", "humanities",
              "statesa", "states", "institutions", "china", "india", "korea", "taiwan", "resident", "holder",
              "nec", "life", "education", "rank", "hong kong", "commitments", "plans"}


# ---------------------------------------------------------------- reading
def sources():
    """(container, member, bytes) for every file in sources/nsf_sed/; zips (and zips inside them) read in place."""
    def walk(container, prefix, z):
        for n in sorted(z.namelist()):
            if n.endswith("/") or "__MACOSX" in n:
                continue
            b = z.read(n)
            if n.lower().endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(b)) as inner:
                    yield from walk(container, prefix + n + "/", inner)
            else:
                yield container, prefix + n, b
    for p in sorted(SRC.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if not f.name.startswith("."):
                    yield p.name, f.name, f.read_bytes()
        elif p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                yield from walk(p.name, "", z)


def read_wks(b: bytes) -> pd.DataFrame | None:
    """Lotus 1-2-3 release 1 worksheet (.wks): integer, number, label and formula-value cells."""
    cells = {}
    i = 0
    while i + 4 <= len(b):
        op, ln = struct.unpack_from("<HH", b, i)
        d = b[i + 4:i + 4 + ln]
        i += 4 + ln
        if op == 1:
            break
        if op in (0x0D, 0x0E, 0x0F, 0x10) and ln >= 5:
            col, row = struct.unpack_from("<HH", d, 1)
            if op == 0x0D:
                v = struct.unpack_from("<h", d, 5)[0]
            elif op in (0x0E, 0x10):
                v = struct.unpack_from("<d", d, 5)[0]
            else:
                s = d[5:].split(b"\0")[0].decode("latin-1")
                v = s[1:] if s[:1] in ("'", '"', "^", "\\") else s
            cells[(row, col)] = v
    if not cells:
        return None
    df = pd.DataFrame(index=range(max(r for r, _ in cells) + 1), columns=range(max(c for _, c in cells) + 1),
                      dtype=object)
    for (r, c), v in cells.items():
        df.iat[r, c] = v
    return df


def first_sheet(b: bytes) -> pd.DataFrame | None:
    if b[:6] == b"\x00\x00\x02\x00\x04\x04":
        return read_wks(b)
    for eng, kw in (("calamine", {}), ("xlrd", {"logfile": open(os.devnull, "w")})):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return pd.read_excel(io.BytesIO(b), header=None, sheet_name=0, engine=eng, engine_kwargs=kw)
        except Exception:
            pass
    return None


def text(v) -> str:
    if isinstance(v, str):
        return " ".join(v.split())
    if isinstance(v, (int, float)) and not pd.isna(v):
        return str(int(v)) if v == int(v) else str(v)
    return ""


def title_of(df: pd.DataFrame) -> str:
    parts = []
    for v in df.iloc[:8, 0]:
        s = text(v)
        if not s or re.fullmatch(r"[-|: ]+|\(.*\)|page \d.*", s, re.I):
            continue
        parts.append(s)
        if re.search(r":\s*(selected years,\s*)?(19|20)\d\d", s, re.I) or len(parts) == 4:
            break
    t = " ".join(parts)
    t = re.sub(r"^(table|figure)\s+[\w-]+\.?\s*\|?\s*", lambda m: m.group(0).strip() + " ", t, flags=re.I)
    return t[:300]


def year_of(title: str) -> int | None:
    m = YEARS_RE.findall(re.sub(r"\b(19|20)\d\d Carnegie", "", title))
    if not m:
        return None
    start, end = m[-1]
    return int(start) if not end else int(start[:4 - len(end)] + end)


def num(v):
    if isinstance(v, str):
        v = v.replace(",", "").strip()
    v = pd.to_numeric(v, errors="coerce")
    return None if pd.isna(v) else float(v)


def norm(s: str) -> str:
    """Lowercase label/header with hyphenation, footnote letters/digits and pipes removed."""
    s = re.sub(r"[|:]", " ", s)
    s = re.sub(r"-{2,}", " ", s)
    s = " ".join(s.split())
    s = re.sub(r"(\w)- (\w)", r"\1\2", s).lower()
    s = re.sub(r"(?<=[a-z&)])\d+\b|(?<=[a-z,]) \d$", "", s)
    words = []
    for w in s.split():
        core = w.rstrip(",")
        if len(core) > 2 and core[-1] in "abcdefgh" and core[:-1] in FOOT_WORDS:
            w = core[:-1] + w[len(core):]
        words.append(w)
    return " ".join(words).strip(" ,")


def state_code(s: str) -> str | None:
    s = norm(s)
    s = re.sub(r", total$", "", s)
    if s in CODE:
        return CODE[s]
    # footnote letter glued on ("Puerto Ricob")
    if s[:-1] in CODE and s[-1] in "abcdefgh":
        return CODE[s[:-1]]
    return None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:50]


# ---------------------------------------------------------------- field codes
def field_code(h: str, tyear: int, kind: str) -> str | None:
    """Field code for a column header (state tables) or row label (national tables); tyear = table's year."""
    t = norm(h)
    t = re.sub(r"^(science|non-science and engineering) (?!and )", "", t)
    t = re.sub(r"^(\w+) \1\b", r"\1", t)                           # "engineering engineering"
    t = re.sub(r" \(.*\)$", "", t)
    f = re.fullmatch
    if f(r"(grand total, )?all fields|grand total|all doctorate recipients|all recipients|total", t):
        return "all"
    if f(r"total s&e|all s&e|science and engineering(, total| total)?|s&e", t):
        return "se"
    if f(r"(non-? ?s&e|nons&e|non-science and engineering)(,? total)?", t):
        return "non_se"
    if f(r"life sciences( total)?", t):
        return "life_sci"
    if f(r"(biological (&|and) agricultural|agricultural and biological) sciences( total)?", t):
        return "ag_bio"
    if f(r"agricultural( sciences)?((,| and|/) ?natural resources)?", t):
        return "ag"
    if f(r"biological( sciences)?((,| and|/) ?biomedical sciences)?|biological and biomedical", t):
        return "bio"
    if f(r"health( sciences)?", t):
        return "health"
    if f(r"physical sciences and earth sciences( total)?", t):
        return "phys_earth"
    if f(r"physical sciences(,? total)?", t):
        return "phys_math_cs" if 2009 <= tyear <= 2014 else "phys_sci"
    if f(r"(earth|geosciences)\b.*", t):
        return "earth"
    if f(r"mathematics and computer sciences( total)?", t):
        return "math_cs"
    if f(r"mathematics( and statistics)?", t):
        return "math"
    if f(r"computer (and information )?sciences", t):
        return "cs"
    if f(r"psychology and social sciences( total)?", t):
        return "psych_soc"
    if f(r"psychology", t):
        return "psych"
    if f(r"social sciences(,? total)?", t):
        return "psych_soc" if 2009 <= tyear <= 2014 else "soc"
    if f(r"engineering(,? total)?", t):
        return "engineering"
    if f(r"multidisciplinary.*", t):
        return "multidisc"
    if f(r"education(,? total)?", t):
        return "education"
    if f(r"humanities and arts( total)?", t):
        return "humanities_arts"
    if f(r"humanities(,? total)?", t):
        return "humanities"
    if f(r"visual and performing arts", t):
        return "arts"
    if f(r"business( management and administration| and management)?", t):
        return "business"
    if f(r"other non-s&e fields.*|other total|professional/other/unknown", t):
        return "other_non_se"
    if f(r"other non-science and engineering|other", t):
        if tyear >= 2021:
            return "other_excl_business"
        return "other_non_se" if kind != "state" else None
    return None


DERIVE = [  # target, parts (all must be present), sign of each part, applies to table years
    ("ag_bio", ["ag", "bio"], None),
    ("life_sci", ["ag", "bio", "health"], (2009, 9999)),
    ("phys_earth", ["phys_sci", "earth"], None),
    ("phys_earth", ["phys_math_cs", "-math", "-cs"], None),
    ("math_cs", ["math", "cs"], None),
    ("psych_soc", ["psych", "soc"], None),
    ("humanities_arts", ["humanities", "arts"], None),
    ("other_non_se", ["business", "other_excl_business"], None),
    ("se", ["life_sci", "phys_earth", "math_cs", "psych_soc", "engineering", "multidisc"], (2021, 9999)),
    ("se", ["life_sci", "phys_earth", "math_cs", "psych_soc", "engineering"], (2015, 2020)),
    ("se", ["life_sci", "phys_math_cs", "psych_soc", "engineering"], (2009, 2014)),
    ("non_se", ["education", "humanities_arts", "other_non_se"], (2015, 9999)),
    ("non_se", ["education", "humanities", "other_non_se"], (2009, 2014)),
    ("se_excl_health", ["se", "-health"], (2009, 9999)),
    ("se_excl_health", ["se"], (0, 2008)),
]


def derive_fields(vals: dict, tyear: int) -> dict:
    """{field: value} -> {field: (value, note)} for derivable fields not already present."""
    out = {}
    for target, parts, yrs in DERIVE:
        if target in vals or target in out or (yrs and not yrs[0] <= tyear <= yrs[1]):
            continue
        have = {**vals, **{k: v for k, (v, _) in out.items()}}
        names = [p.lstrip("-") for p in parts]
        if all(n in have and have[n] is not None for n in names):
            v = sum(-have[p[1:]] if p.startswith("-") else have[p] for p in parts)
            out[target] = (v, "derived: " + " ".join(("- " + p[1:]) if p.startswith("-") else ("+ " + p)
                                                     for p in parts).lstrip("+ "))
    return out


# ---------------------------------------------------------------- classify
def classify(title: str) -> str | None:
    t = title.lower()
    if re.search(r"percentage distribution|distribution of", t):
        return None
    if re.search(r"state(/| or )location|by state,", t):
        if "ranked" in t:
            return "state_rank"
        if re.search(r"and sex|, sex", t) and "institution" not in t.split("by")[0] and "broad field" in t \
                and "institution and" not in t:
            return "state_sex"
        if re.search(r"institution|broad field of doctorate", t):
            return "state"
    if "intending to stay" in t or "intention to stay" in t:
        return "stay_country"
    if re.search(r"postgraduation location of doctorate recipients with temporary visas.*selected years", t):
        return "pg_location"
    if re.search(r"table 2-4 .*postgraduation (location and )?plans of research doctorate recipients with "
                 r"definite commitments, by sex, citizenship", t):
        return "pg_location"
    if re.search(r"stay rate of temporary visa holders", t):
        return "digest_stay"
    if re.search(r"(definite )?postgraduation (plans|commitments) of doctorate recipients,? by citizenship", t) \
            or re.search(r"postgraduation plans of science and engineering \(s&e\) doctorate recipients, by "
                         r"citizenship", t) \
            or re.search(r"table 6-[123] .*research doctorate recipients with definite postgraduation "
                         r"commitments, by major field", t):
        if "percentage" not in t and "distribution" not in t:
            return "commit"
    if re.search(r"doctorates? (awarded|recipients),? by (sex, )?citizenship status(, sex)?,? and major field", t) \
            or re.search(r"by (historical|trend) major field of doctorate and citizenship status", t):
        return "cit_field"
    if re.search(r"(research )?doctorate recipients from u\.s\. colleges and universities: 1958", t):
        return "trend_total"
    return None


# ---------------------------------------------------------------- parsers
def header_text(df, rows, j) -> str:
    return " ".join(text(df.iat[i, j]) for i in rows if text(df.iat[i, j]) and
                    not re.fullmatch(r"[-|: ]+|page \d+ of \d+", text(df.iat[i, j]), re.I))


def parse_state(df: pd.DataFrame, year: int, kind: str) -> list[dict]:
    """State x field cells of a state(-institution) table, all column groups and vertical page halves."""
    nr, nc = df.shape
    labcols = [c for c in range(nc) if any(re.match(r"^state( and|/| or)", text(df.iat[i, c]), re.I)
                                            or re.search(r"\bstate or location( and institution)?$",
                                                         text(df.iat[i, c]), re.I)
                                            for i in range(min(nr, 30)))]
    out = []
    for k, c in enumerate(labcols):
        cend = labcols[k + 1] if k + 1 < len(labcols) else nc
        labs = [text(df.iat[i, c]) for i in range(nr)]
        anchors = [i for i in range(nr) if US_RE.match(norm(labs[i]))]
        if not anchors:                                   # rank tables: no US row
            anchors = [next(i for i in range(nr) if state_code(labs[i]))]
        for a, r0 in enumerate(anchors):
            r1 = anchors[a + 1] if a + 1 < len(anchors) else nr
            top = max(0, (anchors[a - 1] + 1) if a else 0, r0 - 25)
            top = max([top] + [i for i in range(top, r0) if re.match(r"^(table|figure)\b", labs[i], re.I)])
            cols = {}
            for j in range(c + 1, cend):
                h = header_text(df, range(top + (1 if re.match(r"^(table|figure)", labs[top], re.I) else 0), r0),
                                j)
                fc = field_code(h, year, "state")
                if fc and fc not in cols.values():
                    cols[j] = fc
            seen = set()
            for i in range(r0, r1):
                code = "US" if US_RE.match(norm(labs[i])) else state_code(labs[i])
                if not code:
                    continue
                if code in seen:
                    print(f"  ! {year} {labs[i]} twice in one section; second kept out")
                    continue
                seen.add(code)
                for j, fc in cols.items():
                    v = num(df.iat[i, j])
                    if v is not None:
                        out.append(dict(state=code, field=fc, value=v))
    return out


def year_header(df: pd.DataFrame):
    """(row, {col: year}) of the first row with >= 3 four-digit year cells."""
    for i in range(min(len(df), 40)):
        ys = {}
        for j in range(1, df.shape[1]):
            s = text(df.iat[i, j])
            if re.fullmatch(r"(19|20)\d\d(\.0)?", s):
                ys[j] = int(float(s))
        if len(ys) >= 3:
            return i, ys
    return None, {}


BLOCKS = [(r"\b(men|women|male|female)\b", None), (r"citizenship unknown|unknown citizenship", None),
          (r"permanent visa", None), (r"^u\.s\. citizens?(, all fields)?$", None),
          (r"^non-u\.s\. citizens?(, all fields)?$", None),
          (r"u\.s\. citizens? (or|and) permanent residents?", "uspr"), (r"temporary visa", "temp"),
          (r"^(total|all fields|all doctorate recipients|all recipients)$", "all")]


def block_of(label: str):
    t = norm(label)
    for pat, b in BLOCKS:
        if re.search(pat, t):
            return True, b
    return False, None


def parse_cit_field(df: pd.DataFrame, release: int) -> list[dict]:
    hr, ys = year_header(df)
    if hr is None:
        return []
    out, block, seen = [], "all", set()
    for i in range(hr + 1, len(df)):
        lab = text(df.iat[i, 0])
        if not lab or re.match(r"^(table|field of study|characteristic|citizenship status)", lab, re.I):
            continue
        is_block, b = block_of(lab)
        if is_block and not (b == "all" and block == "all" and "all" in seen):
            block = b
            if b:
                seen.discard((b, "all"))
            fc = "all"
        else:
            fc = field_code(re.sub(r",? all fields$", "", lab), release, "national")
        if not block or not fc or (block, fc) in seen:
            continue
        seen.add((block, fc))
        for j, y in ys.items():
            v = num(df.iat[i, j])
            if v is not None:
                out.append(dict(year=y, block=block, field=fc, value=v))
    return out


def parse_commit(df: pd.DataFrame, year: int, title: str) -> list[dict]:
    t = title.lower()
    first = next((i for i in range(3, len(df)) if text(df.iat[i, 0]) and num(df.iat[i, 1]) is not None), None)
    if first is None:
        return []
    cols = {}
    for j in range(1, df.shape[1]):
        h = header_text(df, range(1, first), j).lower()
        m = ("abroad" if "abroad" in h else "us" if re.search(r"(united states|u\.s\.) total|total (in )?u\.s\.", h)
             else "definite" if re.search(r"definite (plans|commitments)", h) and "location" not in h
             else "all_recipients" if re.search(r"all (doctorate )?recipients", h) else None)
        if m and m not in cols.values():
            cols[j] = m
    if "us" not in cols.values():                      # "In the United States" group, first column is its total
        for j in range(1, df.shape[1]):
            if re.search(r"united states", header_text(df, range(1, first), j).lower()) and j not in cols:
                cols[j] = "us"
                break
    fixed = ("temp" if "temporary visa holder research" in t else "uspr" if "u.s. citizen and permanent" in t
             else "all" if re.search(r"table 6-1 ", t) else None)
    out, block, seen = [], fixed or "all", set()
    for i in range(first, len(df)):
        lab = text(df.iat[i, 0])
        if not lab:                                    # 1994-2002: block labels sit in the second column
            alt = text(df.iat[i, 1]) if df.shape[1] > 1 else ""
            if fixed or not alt or num(df.iat[i, 1]) is not None or not block_of(alt)[0]:
                continue
            lab = alt
            block = block_of(alt)[1]
            continue
        is_block, b = (False, None) if fixed else block_of(lab)
        if is_block:
            block, fc = b, "all"
        elif re.match(r"^(all |temporary visa holder doctorate recipients reporting)", lab, re.I):
            fc = "all"
        else:
            fc = field_code(lab, year, "national")
        if not block or not fc or (block, fc) in seen:
            continue
        seen.add((block, fc))
        for j, m in cols.items():
            v = num(df.iat[i, j])
            if v is not None:
                out.append(dict(block=block, field=fc, measure=m, value=v))
    return out


def parse_digest_stay(df: pd.DataFrame, release: int) -> list[dict]:
    hr, ys = year_header(df)
    out = []
    for i in range(hr + 1, len(df)):
        lab = text(df.iat[i, 0])
        fc = field_code(lab, release, "national")
        if lab and not fc:
            fc = "other_non_se" if norm(lab) == "other" else None
        if fc:
            out += [dict(year=y, field=fc, value=num(df.iat[i, j])) for j, y in ys.items()
                    if num(df.iat[i, j]) is not None]
    return out


REGIONS = r"(africa|asia|east/south asia|east asia and south asia|west asia|europe|middle east|" \
          r"north/south america|north america and south america|pacifica/australia|pacifica and australia|" \
          r"australia-oceania|oceania|unknown region|region unknown)"


def parse_stay_country(df: pd.DataFrame) -> list[dict]:
    hr = next(i for i in range(min(len(df), 20)) if sum(bool(re.fullmatch(r"(19|20)\d\d(\.0)?", text(x)))
                                                        for x in df.iloc[i, 1:]) >= 3)
    ys = {}
    for j in range(1, df.shape[1]):
        s = text(df.iat[hr, j])
        if re.fullmatch(r"(19|20)\d\d(\.0)?", s):
            ys[j] = int(float(s))
    sub = hr + 1
    out, region = [], None
    for i in range(sub + 1, len(df)):
        lab = text(df.iat[i, 0])
        if not lab or re.match(r"^(d = |na = |note|source|- =|\W)", lab, re.I) or len(lab) > 60:
            continue
        if lab[-1:] in "abcdefgh" and lab[:-1].lower() in FOOT_WORDS:      # "Chinaa": footnote letter
            lab = lab[:-1]
        nl = norm(lab)
        if nl.startswith("all temporary visa"):
            level, geo = "all", "All temporary visa holders"
        elif re.fullmatch(REGIONS, nl):
            level, geo, region = "region", lab, lab
        else:
            level = "country"
            geo = f"Other ({region})" if nl.startswith("other") and region else lab
        for j, y in ys.items():
            n, p = num(df.iat[i, j]), num(df.iat[i, j + 1]) if j + 1 < df.shape[1] else None
            if n is not None:
                out.append(dict(year=y, geo=geo, geo_level=level, region=region if level == "country" else "",
                                measure="temp_visa_doctorates", value=n))
            if p is not None:
                out.append(dict(year=y, geo=geo, geo_level=level, region=region if level == "country" else "",
                                measure="pct_intending_to_stay", value=p))
    pct = [r["value"] for r in out if r["measure"] == "pct_intending_to_stay"]
    if pct and max(pct) <= 1.0:                          # 2015-2016 releases store proportions
        for r in out:
            if r["measure"] == "pct_intending_to_stay":
                r["value"] = round(100 * r["value"], 1)
                r["note"] = "published as a proportion; x 100"
    return out


def parse_pg_location(df: pd.DataFrame, title: str) -> list[dict]:
    t = title.lower()
    out = []
    if "with temporary visas" in t:                    # 2009-2011: one row per selected year
        cols = {}
        for j in range(1, df.shape[1]):
            h = header_text(df, range(1, 4), j).lower()
            m = ("definite_commitments" if "all reporting" in h else "pct_us" if "u.s. location" in h else
                 "pct_abroad" if "foreign" in h else "pct_unknown" if "unknown" in h else None)
            if m:
                cols[j] = m
        for i in range(len(df)):
            s = text(df.iat[i, 0])
            if re.fullmatch(r"(19|20)\d\d", s):
                out += [dict(year=int(s), block="temp", measure=m, value=num(df.iat[i, j]))
                        for j, m in cols.items() if num(df.iat[i, j]) is not None]
        return out
    hdr = {j: header_text(df, range(3, 6), j).lower() for j in range(1, df.shape[1])}
    cols = {j: b for j, b in ((j, "all" if re.match(r"^total", h) else "uspr" if re.search(
        r"u\.s\. citizen or permanent resident$", h) else "temp" if re.search(r"temporary visa holder$", h)
        else None) for j, h in hdr.items()) if b}
    section, where = None, ""
    for i in range(6, len(df)):
        s = text(df.iat[i, 0])
        if re.fullmatch(r"(19|20)\d\d", s) and section:
            out += [dict(year=int(s), block=b, measure=section, value=num(df.iat[i, j]))
                    for j, b in cols.items() if num(df.iat[i, j]) is not None]
        elif s:
            n = norm(s)
            if "in the united states" in n:
                where, section = "us_", "pct_us"
            elif "abroad" in n:
                where, section = "abroad_", "pct_abroad_or_unknown"
            elif "all definite commitments" in n:
                where, section = "", "definite_commitments"
            elif "reported type of plan" in n:
                section = "reported_plan_type"
            else:
                section = "pct_" + where + slug(re.sub(r"\(.*?\)\s*[a-h]?$|\(.*?\)", "", n))
    return out


def parse_trend_total(df: pd.DataFrame) -> list[dict]:
    out = []
    for i in range(len(df)):
        s = text(df.iat[i, 0])
        if re.fullmatch(r"(19|20)\d\d", s) and num(df.iat[i, 1]) is not None:
            out.append(dict(year=int(s), value=num(df.iat[i, 1])))
    return out


# ---------------------------------------------------------------- build
def pick(df: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    """For multi-year tables: the release for that year, else the earliest later release."""
    df = df.assign(lag=df.release - df.year)
    df = df[df.lag >= 0].sort_values(["lag", "source_file"])
    return df.drop_duplicates(key)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    files, state_rows, cit_rows, commit_rows, stay_rows, pg_rows, digest_rows, trend_rows, rank_rows = \
        [], [], [], [], [], [], [], [], []
    md5s = {}
    for container, name, b in sources():
        md5 = hashlib.md5(b).hexdigest()
        md5s[(container, name)] = md5
        rec = dict(container=container, file=name, md5=md5, detected_year=None, table_title="", kind="",
                   used="no", why_not_used="")
        files.append(rec)
        low = name.lower()
        if not low.endswith((".xls", ".xlsx")):
            rec["why_not_used"] = ("PDF copy of the published tables or technical notes" if low.endswith(".pdf")
                                   else "index of table titles" if low.endswith(".txt") else "not a data table")
            continue
        df = first_sheet(b)
        if df is None or df.empty:
            rec["why_not_used"] = "unreadable file"
            continue
        title = title_of(df)
        year = year_of(title)
        kind = classify(title) or ""
        rec.update(table_title=title, detected_year=year, kind=kind)
        base = dict(container=container, source_file=name, table_title=title)
        if not year:
            rec["why_not_used"] = "no year in title (list of tables)"
            continue
        if "1966" in title and "degrees awarded" in title.lower():
            rec["why_not_used"] = "NSF 'Science and Engineering Degrees: 1966-2012' (IPEDS-based), not SED"
            continue
        try:
            if kind == "state":
                rows = parse_state(df, year, kind)
                state_rows += [dict(year=year, **r, **base) for r in rows]
            elif kind == "state_rank":
                rows = parse_state(df, year, kind)
                rank_rows += [dict(year=year, **r, **base) for r in rows if r["field"] == "all"]
                rec["why_not_used"] = "ranking table; used only to check the state totals"
                continue
            elif kind == "cit_field":
                rows = parse_cit_field(df, year)
                if not any(r["block"] == "temp" for r in rows):
                    rec["why_not_used"] = "citizenship blocks not recognized (layout not parsed)"
                    continue
                cit_rows += [dict(release=year, **r, **base) for r in rows]
            elif kind == "commit":
                rows = parse_commit(df, year, title)
                if not rows or not re.search(r"table 6-[12] ", title.lower()) and \
                        not any(r["block"] == "temp" for r in rows):
                    rec["why_not_used"] = "citizenship blocks not recognized (layout not parsed)"
                    continue
                commit_rows += [dict(year=year, **r, **base) for r in rows]
            elif kind == "stay_country":
                rows = parse_stay_country(df)
                stay_rows += [dict(release=year, **r, **base) for r in rows]
            elif kind == "pg_location":
                rows = parse_pg_location(df, title)
                pg_rows += [dict(release=year, **r, **base) for r in rows]
            elif kind == "digest_stay":
                rows = parse_digest_stay(df, year)
                digest_rows += [dict(release=year, **r, **base) for r in rows]
            elif kind == "trend_total":
                rows = parse_trend_total(df)
                trend_rows += [dict(release=year, **r, **base) for r in rows]
                rec["why_not_used"] = "national trend total; used only for checks"
                continue
            else:
                continue
        except Exception as e:                           # keep going; the file is reported
            rec["why_not_used"] = f"parse error: {type(e).__name__}: {e}"[:200]
            continue
        if rows:
            rec["used"] = "yes"
        else:
            rec["why_not_used"] = "no rows recognized"

    # ---- state tables
    st = pd.DataFrame(state_rows)
    st["note"] = ""
    dup = st.groupby(["year", "state", "field"]).value.nunique()
    if (dup > 1).any():
        print("  ! state/field values differ between the two tables of a year:\n", dup[dup > 1].head())
    st = st.drop_duplicates(["year", "state", "field"])           # "all fields" appears in both 2009-20 tables
    years_by_container = st.groupby("year").container.agg(lambda s: sorted(set(s)))
    der = []
    for (y, s), g in st.groupby(["year", "state"]):
        vals = dict(zip(g.field, g.value))
        src = g.iloc[0]
        for f, (v, note) in derive_fields(vals, y).items():
            der.append(dict(year=y, state=s, field=f, value=v, note=note, container=src.container,
                            source_file="+".join(sorted(set(g.source_file))), table_title=""))
    st = pd.concat([st, pd.DataFrame(der)], ignore_index=True).assign(measure="doctorates")

    # ---- citizenship (US)
    cit = pick(pd.DataFrame(cit_rows), ["year", "block", "field"])
    cder = []
    for (y, b), g in cit.groupby(["year", "block"]):
        vals = dict(zip(g.field, g.value))
        rel = int(g.release.iloc[0])
        for f, (v, note) in derive_fields(vals, rel).items():
            cder.append(dict(year=y, block=b, field=f, value=v, note=note, release=rel,
                             container=g.container.iloc[0], source_file=g.source_file.iloc[0],
                             table_title=g.table_title.iloc[0]))
    cit = pd.concat([cit.assign(note=""), pd.DataFrame(cder)], ignore_index=True)
    cit["note"] = cit.apply(lambda r: ("; ".join(x for x in [r.note, f"from the {r.release} release" if
                                                              r.release != r.year else ""] if x)), axis=1)
    us_rows = []
    measure = {"uspr": "doctorates_uspr", "temp": "doctorates_temp_visa"}
    for r in cit.itertuples():
        if r.block in measure:
            us_rows.append(dict(year=r.year, state="US", measure=measure[r.block], field=r.field, value=r.value,
                                note=r.note, container=r.container, source_file=r.source_file,
                                table_title=r.table_title))
    tot = cit[cit.block == "all"].set_index(["year", "field"])
    tv = cit[cit.block == "temp"].set_index(["year", "field"])
    j = tv[["value", "container", "source_file", "table_title"]].join(
        tot[["value"]].rename(columns={"value": "value_all"}), how="inner")
    for (y, f), r in j[j.value_all > 0].iterrows():
        us_rows.append(dict(year=y, state="US", measure="doctorates_temp_visa_share", field=f,
                            value=round(100 * r.value / r.value_all, 2), container=r.container,
                            source_file=r.source_file, table_title=r.table_title,
                            note="derived: 100 * temp visa / all recipients in the same table"))
    # national "doctorates" for years without a state table
    have = set(map(tuple, st.loc[st.state == "US", ["year", "field"]].values))
    for (y, f), r in tot.iterrows():
        if (y, f) not in have:
            us_rows.append(dict(year=y, state="US", measure="doctorates", field=f, value=r.value,
                                container=r.container, source_file=r.source_file, table_title=r.table_title,
                                note="national citizenship trend table (no state table this year)"
                                     + (f"; from the {r.release} release" if r.release != y else "")))

    # ---- postgraduation commitments (US, own-year tables) + digest stay rates
    cm = pd.DataFrame(commit_rows).drop_duplicates(["year", "block", "field", "measure"]).assign(note="")
    cmd = []
    for (y, b, m), g in cm.groupby(["year", "block", "measure"]):
        for f, (v, note) in derive_fields(dict(zip(g.field, g.value)), y).items():
            if f != "se_excl_health":
                cmd.append(dict(year=y, block=b, measure=m, field=f, value=v, note=note,
                                container=g.container.iat[0], source_file=g.source_file.iat[0],
                                table_title=g.table_title.iat[0]))
    cm = pd.concat([cm, pd.DataFrame(cmd)], ignore_index=True)
    suffix = {"all": "", "uspr": "_uspr", "temp": "_temp_visa"}
    names = {"definite": "definite_commitments", "us": "definite_commitments_us",
             "abroad": "definite_commitments_abroad"}
    for r in cm[cm.measure.isin(list(names))].itertuples():
        us_rows.append(dict(year=r.year, state="US", measure=names[r.measure] + suffix[r.block], field=r.field,
                            value=r.value, container=r.container, source_file=r.source_file,
                            table_title=r.table_title, note=r.note))
    w = cm.pivot_table(index=["year", "block", "field"], columns="measure", values="value", aggfunc="first")
    src = cm.drop_duplicates(["year", "block", "field"]).set_index(["year", "block", "field"])
    if {"us", "definite"} <= set(w.columns):
        for (y, b, f), r in w.dropna(subset=["us", "definite"]).iterrows():
            if r.definite > 0:
                s = src.loc[(y, b, f)]
                us_rows.append(dict(year=y, state="US", measure="stay_rate" + suffix[b], field=f,
                                    value=round(100 * r.us / r.definite, 2), container=s.container,
                                    source_file=s.source_file, table_title=s.table_title,
                                    note="derived: 100 * definite commitments in the U.S. / all definite "
                                         "commitments"))
    dg = pick(pd.DataFrame(digest_rows), ["year", "field"]) if digest_rows else pd.DataFrame()
    have_sr = {(r["year"], r["field"]) for r in us_rows if r["measure"] == "stay_rate_temp_visa"}
    for r in dg.itertuples():
        if (r.year, r.field) not in have_sr:
            us_rows.append(dict(year=r.year, state="US", measure="stay_rate_temp_visa", field=r.field,
                                value=r.value, container=r.container, source_file=r.source_file,
                                table_title=r.table_title, note="digest figure data" +
                                (f"; from the {r.release} release" if r.release != r.year else "")))

    long = pd.concat([st, pd.DataFrame(us_rows)], ignore_index=True)
    long["year"] = long.year.astype(int)
    long["note"] = long.note.fillna("")
    long = long.sort_values(["year", "state", "measure", "field"])
    cols = ["year", "state", "measure", "field", "value", "source_file", "table_title", "note", "container"]
    long[cols].to_csv(OUT / "sed_state.csv", index=False)

    h = long[long.field.isin(HEADLINE)]
    wide = h.pivot_table(index=["year", "state"], columns=["measure", "field"], values="value", aggfunc="first")
    wide.columns = [f"{m}__{f}" for m, f in wide.columns]
    order = [f"{m}__{f}" for m in ("doctorates", "doctorates_temp_visa", "doctorates_temp_visa_share",
                                   "doctorates_uspr", "definite_commitments_temp_visa",
                                   "definite_commitments_us_temp_visa", "stay_rate_temp_visa", "stay_rate_uspr",
                                   "stay_rate") for f in HEADLINE]
    wide[[c for c in order if c in wide]].reset_index().to_csv(OUT / "sed_state_wide.csv", index=False)

    # ---- national by-country / selected-years tables
    sc = pd.DataFrame(stay_rows)
    labels = set(sc.geo)
    sc["geo"] = sc.geo.map(lambda g: g[:-1] if g[-1:] in "abcdefgh" and g[:-1] in labels else g)
    sc_all = sc.copy()
    sc = pick(sc, ["year", "geo", "measure"]).assign(field="all")
    pg = pd.DataFrame(pg_rows)
    pg_all = pg.copy()
    pg = pick(pg, ["year", "block", "measure"]).assign(field="all", geo_level="all")
    pg["geo"] = pg.block.map({"all": "All doctorate recipients", "uspr": "U.S. citizens and permanent residents",
                              "temp": "Temporary visa holders"})
    pg["measure"] = "pg_" + pg.measure
    us = pd.concat([sc, pg.drop(columns="block")], ignore_index=True)
    us["state"] = "US"
    if "note" not in us:
        us["note"] = ""
    us["note"] = [("; ".join(x for x in [n if isinstance(n, str) else "",
                                         f"from the {rel} release" if rel != y else ""] if x))
                  for n, rel, y in zip(us.note, us.release, us.year)]
    us = us.sort_values(["measure", "geo_level", "geo", "year"])
    us[["state", "year", "geo", "geo_level", "region", "measure", "field", "value", "release", "source_file",
        "table_title", "note", "container"]].to_csv(OUT / "sed_us.csv", index=False)

    # ---- files
    for r in files:
        if r["used"] == "no" and not r["why_not_used"]:
            t = r["table_title"].lower()
            r["why_not_used"] = (
                "state table by sex (D-suppressed); the state x institution field tables are used instead"
                if r["kind"] == "state_sex" else
                "institution ranking/list with no state column; cannot be aggregated to states"
                if re.search(r"top \d+|ranked|institutions? (granting|with the largest)", t) else
                "percentage distribution (counts table of the same year used)" if "distribution" in t else
                "topic not needed (sex, race/ethnicity, age, debt, support, time to degree, field detail)")
        m = re.match(r"(.*) \(1\)(\.\w+)$", r["file"])
        r["duplicate_check"] = ""
        if m:
            orig = md5s.get((r["container"], m.group(1) + m.group(2)))
            r["duplicate_check"] = ("no un-suffixed copy; this is the only copy" if orig is None else
                                    "identical to " + m.group(1) + m.group(2) if orig == r["md5"] else
                                    "DIFFERS from " + m.group(1) + m.group(2))
    fl = pd.DataFrame(files)
    fl = fl[["container", "file", "md5", "detected_year", "table_title", "kind", "used", "why_not_used",
             "duplicate_check"]]
    fl.to_csv(OUT / "files.csv", index=False)

    cov = long.groupby(["measure", "field", "year"]).state.agg(
        n_states=lambda s: s.isin(STATES51).sum(),
        territories=lambda s: " ".join(sorted(set(s) & set(TERR.values()))),
        us=lambda s: "yes" if (s == "US").any() else "no").reset_index()
    cov["source"] = cov.n_states.map(lambda n: "state tables" if n else "national only")
    cov.to_csv(OUT / "coverage.csv", index=False)
    checks(long, st, pd.DataFrame(rank_rows), pd.DataFrame(trend_rows), pd.DataFrame(cit_rows), sc_all, pg_all,
           pd.DataFrame(digest_rows), fl, years_by_container)


# ---------------------------------------------------------------- sanity checks
def checks(long, st, rank, trend, cit_all, sc_all, pg_all, dg_all, fl, years_by_container):
    out = []
    pub = st[~st.note.fillna("").str.startswith("derived")]
    # 1. state sums vs the published US row, same table
    for (y, f, src), g in pub.groupby(["year", "field", "source_file"]):
        us = g.loc[g.state == "US", "value"]
        if us.empty:
            continue
        s51, sall = g[g.state.isin(STATES51)].value.sum(), g[g.state != "US"].value.sum()
        out.append(dict(check="state_sum_vs_us", year=y, measure="doctorates", field=f, source=src, us=us.iat[0],
                        value=sall, sum_51=s51, diff_pct=round(100 * (sall / us.iat[0] - 1), 3),
                        n_states=g.state.isin(STATES51).sum()))
    # 2. all = se + non_se in the state tables (published or derived)
    w = st.pivot_table(index=["year", "state"], columns="field", values="value", aggfunc="first")
    if {"all", "se", "non_se"} <= set(w.columns):
        d = (w.se + w.non_se - w["all"]).dropna()
        for y, g in d.groupby(level=0):
            out.append(dict(check="all_eq_se_plus_non_se", year=y, measure="doctorates", field="all",
                            n_states=len(g), value=g.abs().max(),
                            flag="" if g.abs().max() <= 2 else "mismatch"))
    # 3. state table vs the ranking table total
    if not rank.empty:
        j = st[st.field == "all"].merge(rank, on=["year", "state"], suffixes=("", "_rank"))
        for y, g in j.groupby("year"):
            dd = (g.value - g.value_rank).abs()
            out.append(dict(check="state_vs_rank_table", year=y, measure="doctorates", field="all",
                            n_states=len(g), value=dd.max(), source=g.source_file_rank.iat[0],
                            flag="" if dd.max() == 0 else "differs"))
    # 4. US totals: state table vs citizenship trend table vs Table 1-1 (latest release)
    us = long[(long.state == "US") & (long.measure == "doctorates") & (long.field == "all")].set_index("year")
    lt = trend.sort_values("release").drop_duplicates("year", keep="last").set_index("year")
    own = trend[trend.release == trend.year].set_index("year")
    call = cit_all[(cit_all.block == "all") & (cit_all.field == "all")]
    cown = call[call.release == call.year].set_index("year")
    for y, r in us.iterrows():
        rec = dict(check="us_total_cross_table", year=y, measure="doctorates", field="all", us=r.value,
                   source=r.source_file)
        if y in lt.index:
            rec.update(trend_latest=lt.value[y], trend_latest_release=lt.release[y])
        if y in own.index:
            rec["trend_same_release"] = own.value[y]
        if y in cown.index:
            rec["cit_table_same_release"] = cown.value[y]
        if "trend_latest" in rec:
            rec["diff_pct"] = round(100 * (r.value / rec["trend_latest"] - 1), 3)
        rec["flag"] = "" if y < 2015 or 52000 <= r.value <= 58500 else "outside 52,000-58,500"
        out.append(rec)
    # 5. US continuity
    piv = long[long.state == "US"].pivot_table(index="year", columns=["measure", "field"], values="value",
                                               aggfunc="first")
    for m, f in [("doctorates", "all"), ("doctorates", "se"), ("doctorates", "se_excl_health"),
                 ("doctorates_temp_visa", "all"), ("doctorates_temp_visa", "se")]:
        if (m, f) not in piv:
            continue
        s = piv[(m, f)].dropna()
        for y, v, ch, gap in zip(s.index, s.values, s.pct_change().values * 100, s.index.to_series().diff()):
            out.append(dict(check="us_continuity", year=y, measure=m, field=f, us=v,
                            diff_pct=None if pd.isna(ch) else round(ch, 2),
                            flag=("gap before" if gap and gap > 1 else "") +
                                 (" jump" if not pd.isna(ch) and abs(ch) > 8 else "")))
    # 6. temporary visa share of S&E
    for f in ("se", "all", "engineering", "math_cs"):
        if ("doctorates_temp_visa_share", f) in piv:
            for y, v in piv[("doctorates_temp_visa_share", f)].dropna().items():
                out.append(dict(check="us_temp_visa_share", year=y, measure="doctorates_temp_visa_share", field=f,
                                us=v, flag="" if (f != "se" or y < 2015 or 33 <= v <= 42) else "outside 33-42%"))
    # 7. the same year in several releases (multi-year tables)
    for name, df, key in [("cit_field", cit_all, ["year", "block", "field"]),
                          ("stay_country", sc_all, ["year", "geo", "measure"]),
                          ("pg_location", pg_all, ["year", "block", "measure"]),
                          ("digest_stay", dg_all, ["year", "field"])]:
        if df.empty:
            continue
        sub = df if name != "cit_field" else df[df.field.isin(["all", "se", "non_se", "engineering"])]
        g = sub.groupby(key).agg(n=("release", "nunique"), lo=("value", "min"), hi=("value", "max"),
                                 releases=("release", lambda s: " ".join(map(str, sorted(set(s))))))
        g = g[g.n > 1]
        for k, r in g.iterrows():
            k = dict(zip(key, k if isinstance(k, tuple) else (k,)))
            if name == "stay_country" and k["geo"] != "All temporary visa holders" and \
                    k["geo"] not in ("China", "India", "South Korea", "Korea, South", "Taiwan"):
                continue
            out.append(dict(check=f"release_agreement_{name}", year=k["year"],
                            measure=k.get("measure", k.get("block", "")), field=k.get("field", k.get("geo", "")),
                            value=r.hi - r.lo, source=r.releases,
                            diff_pct=round(100 * (r.hi / r.lo - 1), 3) if r.lo else None,
                            flag="" if r.hi == r.lo else "revised"))
    # 8. computed stay rate vs digest figure
    sr = long[(long.measure == "stay_rate_temp_visa") & (~long.note.str.startswith("digest"))]
    if not dg_all.empty:
        dl = dg_all.sort_values("release").drop_duplicates(["year", "field"], keep="last")
        j = sr.merge(dl, on=["year", "field"], suffixes=("", "_dg"))
        for r in j.itertuples():
            out.append(dict(check="stay_rate_vs_digest", year=r.year, measure="stay_rate_temp_visa", field=r.field,
                            us=r.value, value=r.value_dg, diff_pct=round(r.value - r.value_dg, 2),
                            source=f"{r.source_file} vs {r.source_file_dg}",
                            flag="" if abs(r.value - r.value_dg) <= 1.5 else "differs"))
    # 9. one container per state-table year
    for y, cs in years_by_container.items():
        out.append(dict(check="state_table_releases", year=y, measure="doctorates", field="all",
                        source=" + ".join(cs), flag="" if len(cs) == 1 else "several releases"))
    ck = pd.DataFrame(out)
    ck.to_csv(OUT / "checks.csv", index=False)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    print(f"files: {len(fl)}, used {(fl.used == 'yes').sum()}")
    used = fl[fl.used == "yes"]
    print(used.groupby("container").detected_year.agg(lambda s: f"{int(s.min())}-{int(s.max())}").to_string())
    s = ck[ck.check == "state_sum_vs_us"]
    print(f"\nstate sums vs US row: {len(s)} table-fields, max |diff| {s.diff_pct.abs().max():.3f}%")
    print(s[s.diff_pct.abs() > 0.5][["year", "field", "source", "us", "value", "diff_pct"]].to_string()
          if (s.diff_pct.abs() > 0.5).any() else "  all within 0.5%")
    for c in ("all_eq_se_plus_non_se", "state_vs_rank_table", "stay_rate_vs_digest", "state_table_releases"):
        x = ck[(ck.check == c) & (ck.flag.fillna("") != "")]
        print(f"\n{c}: {(ck.check == c).sum()} rows, {len(x)} flagged")
        if len(x):
            print(x[["year", "field", "us", "value", "source", "flag"]].head(20).to_string())
    t = ck[ck.check == "us_total_cross_table"]
    print("\nUS total doctorates (state table) vs national tables:")
    print(t[["year", "us", "cit_table_same_release", "trend_same_release", "trend_latest", "diff_pct", "flag"]]
          .to_string(index=False))
    c = ck[(ck.check == "us_continuity") & (ck.flag.fillna("") != "")]
    print("\nUS continuity flags (>8% change or gap):")
    print(c[["year", "measure", "field", "us", "diff_pct", "flag"]].to_string(index=False))
    v = ck[ck.check == "us_temp_visa_share"].pivot_table(index="year", columns="field", values="us")
    print("\nUS temporary-visa share of doctorates (%):")
    print(v.round(1).to_string())
    r = ck[ck.check.str.startswith("release_agreement") & (ck.flag == "revised")]
    print(f"\nsame year in several releases: {(ck.check.str.startswith('release_agreement')).sum()} comparisons, "
          f"{len(r)} revised; largest:")
    print(r.reindex(r.diff_pct.abs().sort_values(ascending=False).index).head(10)[
        ["check", "year", "measure", "field", "value", "diff_pct", "source"]].to_string(index=False))


if __name__ == "__main__":
    build()
