"""NSF/NCSES Survey of Graduate Students and Postdoctorates in S&E (GSS): state and national counts.

    python -m ipeds_clean.gss            # -> data/gss/*.csv and a printed sanity-check report

Source: the GSS published data tables in sources/nsf_gss/, one folder (1994-2004, .xls) or zip (2005-2025, .xls/.xlsx)
per download. Zips are read in place. The folder name is the year the file was downloaded under, which is not
always the survey (fall) year, so every file's survey year is read from its table title (the last year named in
it, e.g. "...: 2016" or "...: 1975-2024"); files whose title names no year get the most common year of their
folder. Tables are found by title, not by number, because the numbering changes nearly every year.

What is used
* State tables (1994, 1996-2016): "Graduate students in science / in engineering in all institutions, by
  (region,) state, institution, citizenship ..." and, from 2010, the same for postdoctoral appointees. The state
  subtotal rows are kept (institution rows are not), plus the "all institutions" row as state "US" and Puerto
  Rico / Guam / Virgin Islands as PR / GU / VI where listed. 1994 also has science+engineering+health by state
  (Table E-1, with the health column), SEH by citizenship (E-4) and the science and engineering broad fields
  (E-2, E-3). No state table covers full-time or first-time students, nonfaculty researchers (NFRs), or health
  outside 1994.
* National trend tables (2017+ releases): Table 1-1 (grad students, postdocs, NFRs by science / engineering /
  health), 1-3a-d or 1-7 (citizenship), and the own-year "broad fields, by degree program, citizenship"
  table (2-4 / 2-9; the only field-level citizenship source in the 2024 release). They give the "US" rows
  only for measure-years the state tables do not cover (1995, 2017-2024, NFRs, health, pre-2010 postdocs). The
  value comes from the release for that survey year, or else the earliest later release (2019 has no release
  here and comes from the 2020 one). "2007new"/"2014new"/"2017new" rows are used, not the "old" ones.
  These tables are also used to check the state-table US totals; values for a given year agree exactly across
  all the 2017-2024 releases here.

Not used, and why, is listed per file in files.csv. From 2017 the published tables have no state detail, and the
institution ranking tables give no state for each institution, so they cannot be aggregated to states. 1995 has
no state table (and its one Lotus 1-2-3 file, an institution ranking, cannot be read).

Outputs (data/gss/):
  gss_state.csv       survey_year, state, measure, field, value, note, source_folder, source_file, table_title
  gss_state_wide.csv  one row per state-year, columns <measure>__<field> for the headline fields
  files.csv           every file: folder, file, md5, survey_year, table_title, used, why_not_used
  coverage.csv        measure x field x survey_year: states (50 + DC) covered, territories, US present
  checks.csv          state sums vs US total, US continuity, state-table US vs national trend tables

Measures: grad_total, grad_temp_visa, grad_temp_visa_share (%), postdoc_total, postdoc_temp_visa,
postdoc_temp_visa_share (%), nfr_total (US only). Fields: science, engineering, all_se (science + engineering;
summed by us where the source gives them separately), health, se_and_health, and in 1994 broad science and
engineering fields (sci_*, eng_*).

Caveats
* Temporary visa holders: from 1998 the tables say "students with temporary visas"; 1994-97 tables say
  "Non-U.S. citizens". NSF's own trend tables treat the earlier column as temporary visa holders (1996 SEH:
  102,974 "non-U.S. citizens" vs 102,984 temporary visa holders in the 2024 trend table), so one measure is used.
* Series breaks noted by NSF: 2007 (fields reclassified, new fields, survey redesign; state tables are on the
  "2007new" basis); 2008 (stricter exclusion of practitioner programs in psychology and other health); 2010
  (postdoc/NFR section expanded: part of the jump over 2009 is better reporting; 2010-11 postdocs reimputed in
  2012); 2014 (frame update added 151 institutions, mostly master's-granting; 2014 state tables are on the new
  frame); 2017 (redesign: taxonomy aligned to the NCSES Taxonomy of Disciplines, some fields reclassified or
  dropped, master's vs doctoral reported separately; compare at broad-field level only). "Science" includes
  psychology and the social sciences throughout; health is separate.
* The "all institutions" (US) total includes institutions in Puerto Rico and other outlying areas, and from 2010
  imputed data for nonresponding institutions that are not listed (they are in the state subtotals).
* State tables count students where the institution is, not where they come from.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import warnings
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "nsf_gss"
OUT = ROOT / "data" / "gss"

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
CODE = {**{v: k for k, v in NAMES.items()}, **TERR}
ALL_RE = re.compile(r"^(total, )?all institutions[a-z]?$", re.I)
YEAR_END = re.compile(r"((?:19|20)\d\d)(?:\s*[–-]\s*(\d{2,4}))?(?:\s*\(selected\s*(?:years)?\)?)?\s*$")
HEADLINE = ["all_se", "se_and_health", "science", "engineering", "health"]


# ---------------------------------------------------------------- reading
def sources():
    """(folder, file, bytes) for every file in sources/nsf_gss/, zips read in place, one at a time."""
    for p in sorted(SRC.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if not f.name.startswith("."):
                    yield p.name, f.name, f.read_bytes()
        elif p.suffix == ".zip":
            with zipfile.ZipFile(p) as z:
                for n in sorted(z.namelist()):
                    if not n.endswith("/"):
                        try:
                            yield p.name, n, z.read(n)
                        except zipfile.BadZipFile:              # one damaged member (a PDF) in 2007.zip
                            yield p.name, n, None


def first_sheet(b: bytes) -> pd.DataFrame | None:
    for eng, kw in (("calamine", {}), ("xlrd", {"logfile": open(os.devnull, "w")})):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return pd.read_excel(io.BytesIO(b), header=None, sheet_name=0, engine=eng, engine_kwargs=kw)
        except Exception:
            pass
    return None


def title_of(df: pd.DataFrame) -> str:
    parts = []
    for v in df.iloc[:6, 0]:
        s = " ".join(str(v).split()) if isinstance(v, str) else ""
        if not s or s.startswith("--") or re.fullmatch(r"\(.*\)", s):
            continue
        parts.append(s)
        if YEAR_END.search(s) or len(parts) == 4:
            break
    return " ".join(parts)[:300]


def raw_title(b: bytes) -> str:
    """Printable text at the top of a file no reader understands (the 1995 Lotus 1-2-3 sheet)."""
    runs = re.findall(rb"[\x20-\x7e]{8,}", b[:4000])
    lines = [r.decode().strip(" '") for r in runs if not r.strip(b" '-")[:1] == b""][:3]
    return " ".join(lines)[:300]


def year_of(title: str) -> int | None:
    m = YEAR_END.search(title)
    if not m:
        return None
    start, end = m.group(1), m.group(2)
    if not end:
        return int(start)
    return int(start[:4 - len(end)] + end)


def num(v):
    v = pd.to_numeric(v, errors="coerce")
    return None if pd.isna(v) else float(v)


def label(v) -> str:
    if isinstance(v, (int, float)) and not pd.isna(v):
        return str(int(v)) if v == int(v) else str(v)
    return " ".join(str(v).split()) if isinstance(v, str) else ""


def state_code(s: str) -> str | None:
    for name, code in CODE.items():
        if s == name or (s.startswith(name) and re.fullmatch(r"[a-z,]{1,3}", s[len(name):])):
            return code
    return None


def slug(s: str) -> str:
    s = re.sub(r"[^a-z]+", "_", re.sub(r"-\s+", "", s.lower())).strip("_")
    return s[:40]


# ---------------------------------------------------------------- classify and parse
def classify(title: str) -> str | None:
    t = title.lower()
    if re.search(r"by (geographic division, |region, )?state,", t) and "students" in t or "postdoc" in t and "state," in t:
        return "state"
    if re.search(r"graduate students, postdoctoral appointees, and doctorate-holding nonfaculty researchers in "
                 r"science, engineering, and health: 1975", t):
        return "trend_counts"
    if re.search(r"citizenship of graduate students and postdoctoral appointees in .*: 1980", t):
        return "trend_cit"
    if "broad fields, by degree program, citizenship" in t:
        return "fields_cit"
    return None


def subject(title: str) -> str:
    head = title.lower().split(" in all institutions")[0].split(" in doctorate")[0]
    head = head.split("citizenship of graduate students and postdoctoral appointees in")[-1]
    if "health" in head and "engineering" in head:
        return "se_and_health"
    for f in ("engineering", "health"):
        if f in head:
            return f
    return "science"


def parse_state(df: pd.DataFrame, title: str) -> list[dict]:
    t = title.lower()
    pop = "postdoc" if "postdoc" in t else "grad"
    field = subject(title)
    labs = df[0].map(label)
    r0 = next(i for i, s in labs.items() if ALL_RE.match(s))
    hdr = [" ".join(re.sub(r"[|\-]{2,}|\|", " ", str(x)) for x in df.iloc[1:r0, j] if pd.notna(x)).lower()
           for j in range(df.shape[1])]
    numeric = [j for j in range(1, df.shape[1]) if num(df.iat[r0, j]) is not None]
    if "area of study" in t:                     # 1994 E-1: SEH, S&E, science, engineering, health
        cols = dict(zip(numeric, ["se_and_health", "all_se", "science", "engineering", "health"]))
        cols = {j: ("grad_total", f) for j, f in cols.items()}
    elif "major field" in t:                     # 1994 E-2/E-3: broad fields within science or engineering
        pre = "sci_" if field == "science" else "eng_"
        cols = {numeric[0]: ("grad_total", field)}
        cols |= {j: ("grad_total", pre + slug(hdr[j])) for j in numeric[1:]}
    else:
        temp = [j for j in numeric if re.search(r"temporary|non-u\.\s?s\.", hdr[j])]
        cols = {numeric[0]: (f"{pop}_total", field)}
        if temp:
            cols[temp[-1]] = (f"{pop}_temp_visa", field)
    out, seen = [], set()
    for i in range(r0, len(df)):
        code = "US" if i == r0 else state_code(labs[i])
        if not code:
            continue
        if code in seen:
            print(f"  ! {title[:60]}: {labs[i]} appears twice, second kept out")
            continue
        seen.add(code)
        for j, (m, f) in cols.items():
            v = num(df.iat[i, j])
            if v is not None:
                out.append(dict(state=code, measure=m, field=f, value=v))
    return out


def parse_trend(df: pd.DataFrame, kind: str, title: str) -> list[dict]:
    labs = df[0].map(label)
    hr = labs[labs == "Year"].index[0]
    first = next(i for i in range(hr + 1, len(df)) if re.match(r"^\d{4}", labs[i]))
    grp = df.iloc[hr].ffill()
    sub = df.iloc[hr + 1].ffill() if first > hr + 1 else grp
    unit = df.iloc[hr + 2] if first > hr + 2 else pd.Series([None] * df.shape[1])
    pops = {"graduate students": "grad", "postdoctoral appointees": "postdoc",
            "doctorate-holding nonfaculty researchers": "nfr"}
    field = subject(title)
    cols = {}
    for j in range(1, df.shape[1]):
        pop, s = pops.get(label(grp[j]).lower()), label(sub[j]).lower()
        if not pop or label(unit[j]).lower() == "percent":
            continue
        if kind == "trend_counts":
            f = {"all fields": "se_and_health", "science": "science", "engineering": "engineering",
                 "health": "health"}.get(s)
            if f:
                cols[j] = (f"{pop}_total", f)
        elif s == "total":
            cols[j] = (f"{pop}_total", field)
        elif s.startswith("temporary visa"):
            cols[j] = (f"{pop}_temp_visa", field)
    out = []
    for i in range(first, len(df)):
        m = re.match(r"^(\d{4})(old|new)?", labs[i])
        if not m:
            if labs[i]:
                break
            continue
        if m.group(2) == "old" or int(m.group(1)) < 1994:
            continue
        for j, (meas, f) in cols.items():
            v = num(df.iat[i, j])
            if v is not None:
                out.append(dict(year=int(m.group(1)), state="US", measure=meas, field=f, value=v))
    return out


def parse_fields_cit(df: pd.DataFrame, year: int) -> list[dict]:
    """Own-year broad field x citizenship table: totals and temporary visa holders for S, E, H and SEH."""
    labs = df[0].map(label)
    top = next(i for i, s in labs.items() if s.startswith("All graduate students"))
    hdr = [" ".join(str(x) for x in df.iloc[1:top, j] if pd.notna(x)).lower() for j in range(df.shape[1])]
    temp = next(j for j in range(1, df.shape[1]) if "temporary visa" in hdr[j])
    want = {"All graduate students": "se_and_health", "Science": "science", "Engineering": "engineering",
            "Health": "health"}
    out = []
    for i in range(top, len(df)):
        f = want.pop(labs[i], None)
        if f:
            out += [dict(year=year, state="US", measure=m, field=f, value=num(df.iat[i, j]))
                    for m, j in (("grad_total", 1), ("grad_temp_visa", temp)) if num(df.iat[i, j]) is not None]
        if not want:
            break
    return out


# ---------------------------------------------------------------- build
def derive(df: pd.DataFrame) -> pd.DataFrame:
    """all_se = science + engineering where not published, then temporary-visa shares."""
    key = ["survey_year", "state", "measure"]
    w = df[df.field.isin(["science", "engineering"])].pivot_table(index=key, columns="field", values="value",
                                                                  aggfunc="first")
    # a state missing from a postdoc engineering table has no engineering postdocs listed: count it as 0
    pd_states = w.index.get_level_values("measure").str.startswith("postdoc") & (w.index.get_level_values("state") != "US")
    w.loc[pd_states, "engineering"] = w.loc[pd_states, "engineering"].fillna(0)
    w = w.dropna()
    have = set(map(tuple, df.loc[df.field == "all_se", key].values))
    srcs = df[df.field.isin(["science", "engineering"])].groupby(key).agg(
        source_folder=("source_folder", lambda s: "+".join(sorted(set(s)))),
        source_file=("source_file", lambda s: "+".join(sorted(set(s)))))
    add = (w.science + w.engineering).rename("value").reset_index()
    add = add[[tuple(r) not in have for r in add[key].values]].merge(srcs.reset_index(), on=key)
    add = add.assign(field="all_se", note="derived: science + engineering", table_title="")
    df = pd.concat([df, add], ignore_index=True)
    rows = []
    for pop in ("grad", "postdoc"):
        t = df[df.measure == f"{pop}_total"].set_index(["survey_year", "state", "field"])
        v = df[df.measure == f"{pop}_temp_visa"].set_index(["survey_year", "state", "field"])
        j = t[["value"]].merge(v[["value", "source_folder", "source_file"]], left_index=True, right_index=True,
                              suffixes=("", "_v"))
        j = j[j.value > 0]
        rows.append(pd.DataFrame({"value": (100 * j.value_v / j.value).round(2), "measure": f"{pop}_temp_visa_share",
                                  "note": "derived: 100 * temp_visa / total", "table_title": "",
                                  "source_folder": j.source_folder, "source_file": j.source_file}).reset_index())
    return pd.concat([df, *rows], ignore_index=True)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    files, state_rows, nat_rows = [], [], []
    md5s = {}
    for folder, name, b in sources():
        md5 = hashlib.md5(b).hexdigest() if b is not None else ""
        md5s[(folder, name)] = md5
        rec = dict(folder=folder, file=name, md5=md5, title_year=None, table_title="", used="no", why_not_used="")
        files.append(rec)
        if b is None:
            rec["why_not_used"] = "damaged inside the zip (bad CRC); PDF copy of the tables"
            continue
        if not name.lower().endswith((".xls", ".xlsx")):
            rec["why_not_used"] = ("PDF copy of the published tables" if name.lower().endswith(".pdf")
                                   else "index of table titles" if name.endswith(".txt") else "not a data table")
            continue
        df = first_sheet(b)
        if df is None:
            rec["table_title"] = raw_title(b)
            rec["title_year"] = year_of(re.sub(r"[-' ]+$", "", rec["table_title"]))
            rec["why_not_used"] = "unreadable format (Lotus 1-2-3 worksheet); institution ranking, no state detail"
            continue
        title, kind = title_of(df), classify(title_of(df))
        year = year_of(title)
        rec.update(table_title=title, title_year=year, kind=kind)
        base = dict(source_folder=folder, source_file=name, table_title=title, note="")
        if kind == "state":
            state_rows += [dict(survey_year=year, **x, **base) for x in parse_state(df, title)]
        elif kind in ("trend_counts", "trend_cit") and year >= 2017:   # a trend table's end year is its release
            nat_rows += [dict(release=year, **x, **base) for x in parse_trend(df, kind, title)]
        elif kind == "fields_cit" and year >= 2017:
            nat_rows += [dict(release=year, **x, **base) for x in parse_fields_cit(df, year)]
        else:
            continue
        rec["used"] = "yes"
    # survey year: the title's own year, else the most common title year in the folder
    mode = {f: Counter(r["title_year"] for r in files if r["folder"] == f and r["title_year"]).most_common(1)
            for f in {r["folder"] for r in files}}
    for r in files:
        r["survey_year"] = r["title_year"] or (mode[r["folder"]][0][0] if mode[r["folder"]] else None)
    state_years = {r["survey_year"] for r in files if r.get("kind") == "state"}
    for r in files:
        if r["used"] == "no" and not r["why_not_used"]:
            t, kind = r["table_title"].lower(), r.get("kind")
            r["why_not_used"] = (
                "institution ranking with no state column; cannot be aggregated to states" if "rank" in t else
                "national trend table; state tables used for this year" if kind else
                "national table on a topic not tabulated by state" if r["survey_year"] in state_years else
                "national table; no state detail published for this year")
    for r in files:                               # browser duplicate downloads
        m = re.match(r"(.*) \(1\)(\.\w+)$", r["file"])
        if m:
            orig = md5s.get((r["folder"], m.group(1) + m.group(2)))
            r["duplicate_check"] = ("no un-suffixed copy; this is the only copy" if orig is None else
                                    "identical to " + m.group(1) + m.group(2) if orig == r["md5"] else
                                    "DIFFERS from " + m.group(1) + m.group(2))

    st = pd.DataFrame(state_rows)
    st = st.drop_duplicates(["survey_year", "state", "measure", "field"])    # 1994 E-1 and E-4 share SEH totals
    nat = pd.DataFrame(nat_rows).rename(columns={"year": "survey_year"})
    nat["lag"] = nat.release - nat.survey_year
    nat = nat[nat.lag >= 0].sort_values(["lag", "source_file"])
    have = set(map(tuple, st.loc[st.state == "US", ["survey_year", "measure", "field"]].values))
    fill = nat.drop_duplicates(["survey_year", "measure", "field"])
    fill = fill[[tuple(x) not in have for x in fill[["survey_year", "measure", "field"]].values]]
    fill = fill.assign(note=lambda d: d.lag.map(lambda l: "national trend table" + (
        f", from a release {l} year(s) later" if l else "")))
    long = derive(pd.concat([st, fill.drop(columns=["release", "lag"])], ignore_index=True))
    long["survey_year"] = long.survey_year.astype(int)
    long = long.sort_values(["survey_year", "state", "measure", "field"])
    cols = ["survey_year", "state", "measure", "field", "value", "note", "source_folder", "source_file",
            "table_title"]
    long[cols].to_csv(OUT / "gss_state.csv", index=False)

    h = long[long.field.isin(HEADLINE)]
    wide = h.pivot_table(index=["survey_year", "state"], columns=["measure", "field"], values="value", aggfunc="first")
    wide.columns = [f"{m}__{f}" for m, f in wide.columns]
    order = [f"{m}__{f}" for f in HEADLINE for m in ("grad_total", "grad_temp_visa", "grad_temp_visa_share",
             "postdoc_total", "postdoc_temp_visa", "postdoc_temp_visa_share", "nfr_total")]
    wide[[c for c in order if c in wide]].reset_index().to_csv(OUT / "gss_state_wide.csv", index=False)

    fl = pd.DataFrame(files)
    fl = fl[["folder", "file", "md5", "survey_year", "table_title", "used", "why_not_used", "duplicate_check"]]
    fl.to_csv(OUT / "files.csv", index=False)

    cov = long.groupby(["measure", "field", "survey_year"]).state.agg(
        n_states=lambda s: s.isin(STATES51).sum(),
        territories=lambda s: " ".join(sorted(set(s) & set(TERR.values()))),
        us=lambda s: "yes" if (s == "US").any() else "no").reset_index()
    cov["source"] = cov.n_states.map(lambda n: "state tables" if n else "national only")
    cov.to_csv(OUT / "coverage.csv", index=False)
    checks(long, st, nat, fl)


# ---------------------------------------------------------------- sanity checks
def checks(long, st, nat, fl):
    out = []
    # 1. state subtotals vs the published all-institutions total, same table
    for (y, m, f, src), g in st.groupby(["survey_year", "measure", "field", "source_file"]):
        us = g.loc[g.state == "US", "value"]
        if us.empty:
            continue
        s51, sall = g[g.state.isin(STATES51)].value.sum(), g[g.state != "US"].value.sum()
        out.append(dict(check="state_sum_vs_us", survey_year=y, measure=m, field=f, source=src, us=us.iat[0],
                        sum_51=s51, sum_with_territories=sall, diff_pct=round(100 * (sall / us.iat[0] - 1), 3)))
    # 2. state-table US totals vs the national trend tables (latest release)
    latest = nat.sort_values("release").drop_duplicates(["survey_year", "measure", "field"], keep="last")
    j = st[st.state == "US"].merge(latest, on=["survey_year", "measure", "field"], suffixes=("", "_trend"))
    for r in j.itertuples():
        out.append(dict(check="us_state_table_vs_trend", survey_year=r.survey_year, measure=r.measure,
                        field=r.field, source=f"{r.source_file} vs {r.source_file_trend}", us=r.value,
                        trend=r.value_trend, diff_pct=round(100 * (r.value / r.value_trend - 1), 3)))
    # 3. US continuity and temporary-visa shares
    us = long[(long.state == "US")].pivot_table(index="survey_year", columns=["measure", "field"], values="value",
                                                 aggfunc="first")
    for m, f in [("grad_total", "all_se"), ("grad_temp_visa", "all_se"), ("grad_total", "se_and_health"),
                 ("postdoc_total", "all_se"), ("postdoc_total", "se_and_health")]:
        if (m, f) not in us:
            continue
        s = us[(m, f)].dropna()
        for y, v, ch in zip(s.index, s.values, s.pct_change().values * 100):
            out.append(dict(check="us_continuity", survey_year=y, measure=m, field=f, us=v,
                            diff_pct=None if pd.isna(ch) else round(ch, 2), flag="jump" if abs(ch) > 12 else ""))
    for f in ("all_se", "se_and_health"):
        if ("grad_temp_visa_share", f) in us:
            for y, v in us[("grad_temp_visa_share", f)].dropna().items():
                out.append(dict(check="us_temp_visa_share", survey_year=y, measure="grad_temp_visa_share", field=f,
                                us=v, flag="" if (y < 2005 or 25 <= v <= 45) else "outside 25-45%"))
    ck = pd.DataFrame(out)
    ck.to_csv(OUT / "checks.csv", index=False)

    pd.set_option("display.width", 200)
    print(f"files: {len(fl)}, used {(fl.used == 'yes').sum()}; survey years by folder:")
    print(fl[fl.survey_year.notna()].groupby("folder").survey_year.agg(lambda s: s.mode().iat[0]).to_string())
    s = ck[ck.check == "state_sum_vs_us"]
    print(f"\nstate sums vs US total: {len(s)} table-measures, max |diff| {s.diff_pct.abs().max():.3f}% "
          f"(51 only: median {(100 * (s.sum_51 / s.us - 1)).median():.2f}%)")
    print(s[s.diff_pct.abs() > 0.5].to_string() if (s.diff_pct.abs() > 0.5).any() else "  all within 0.5%")
    t = ck[ck.check == "us_state_table_vs_trend"]
    print(f"\nstate-table US vs national trend tables: {len(t)} pairs, |diff| > 1%:")
    print(t[t.diff_pct.abs() > 1][["survey_year", "measure", "field", "us", "trend", "diff_pct"]].to_string())
    c = ck[ck.check == "us_continuity"]
    print("\nUS continuity jumps (>12% year to year):")
    print(c[c.flag != ""][["survey_year", "measure", "field", "us", "diff_pct"]].to_string())
    print("\nUS temporary-visa share of grad students (%):")
    print(us.filter(like="grad_temp_visa_share").round(1).to_string())


if __name__ == "__main__":
    build()
