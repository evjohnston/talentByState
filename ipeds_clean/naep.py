"""NAEP (The Nation's Report Card) scores by state, from the NAEP Data Service API (no key).

    python -m ipeds_clean.naep           # discover years, download every result, write data/naep/*.csv
    python -m ipeds_clean.naep --refresh # ignore the cached responses in cache/naep/

API: https://www.nationsreportcard.gov/DataService/GetAdhocData.aspx (docs: /api_documentation.aspx).
Scope: every subject, grade and scale (composite and subscales) of the main NAEP assessments, every
assessment year, all students (variable TOTAL), for the nation (NT), national public schools (NP), the 50
states and DC; plus the national Long-Term Trend assessment (mathematics and reading, ages 9/13/17).
Statistics: mean, standard deviation, the 10/25/50/75/90th percentiles and the achievement levels (cumulative
and discrete), each with its standard error. Achievement levels exist only for composite/overall scales.

How the download works: the API rejects a call if any year in it is not an assessment year or if the years
span two frameworks, so each subject x grade x scale x year x sample is first probed with one cheap national
call, then fetched with one call per statistic covering every jurisdiction (about 7,000 calls including probes, about 4,400 with data; 6 at a time
the first run takes two to three hours, after which every response is cached in cache/naep/raw/). Samples: R2 =
accommodations not permitted (1990-2000), R3 = accommodations permitted (1996 on); NAEP reports trends on R3
from 1996/1998 and both are kept. State results exist only where states took part: mathematics and reading
in grades 4 and 8 (1990/1992 on; every state since 2003), science (1996-2015), writing (1998-2007),
vocabulary (2009, 2011, 2013) and grade 12 mathematics and reading for the pilot states (2009, 2013). Civics, U.S.
history, geography, economics, music, visual arts and TEL are national only.

Outputs (data/naep/):
  naep_long.csv   program, subject, grade, scale, year, sample, jurisdiction, state, stattype, value, se, error_flag
  naep_wide.csv   main NAEP, one row per jurisdiction x subject x grade x scale x year x sample, a column per statistic
  naep_ltt.csv    Long-Term Trend (national), same columns as naep_long.csv
  coverage.csv    states with a displayable mean, by subject x grade x scale x year x sample
  calls.csv       every API call made, with its status
Rows the API marks as not displayable (no data, reporting standard not met, national-only subject) are dropped.
NCES warns that published values can be revised, so rerun with --refresh before relying on a new release.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "naep"
RAW = ROOT / "cache" / "naep"
URL = "https://www.nationsreportcard.gov/DataService/GetAdhocData.aspx"
SOURCE = "Data from NCES, National Assessment of Educational Progress"

STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
          "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
          "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
JURIS = ["NT", "NP"] + STATES
JNAME = {"NT": "US", "NP": "US public"}

# subject: (name, {composite/overall scale: [subscales]}) -- from the API documentation
SUBJECTS = {
    "MAT": ("Mathematics", {"MRPCM": ["MRPS1", "MRPS2", "MRPS3", "MRPS4", "MRPS5"],
                            "MWPCM": ["MWPS1", "MWPS2", "MWPS3", "MWPS4"]}),
    "RED": ("Reading", {"RRPCM": ["RRPS1", "RRPS2", "RRPS3", "RRPS4"]}),
    "SCI": ("Science", {"SRPCM": ["SRPS1", "SRPS2", "SRPS3"], "SRPUV": []}),
    "WRI": ("Writing", {"WRIRP": []}),
    "VOC": ("Vocabulary", {"VOCRP": []}),
    "CIV": ("Civics", {"CIVRP": []}),
    "HIS": ("U.S. history", {"HRPCM": ["HRPS1", "HRPS2", "HRPS3", "HRPS4"]}),
    "GEO": ("Geography", {"GRPCM": ["GRPS1", "GRPS2", "GRPS3"]}),
    "ECN": ("Economics", {"ERPCM": ["ERPS1", "ERPS2", "ERPS3"]}),
    "MUS": ("Music", {"MUSRP": []}),
    "VIS": ("Visual arts", {"VISRP": []}),
    "TEL": ("Technology and engineering literacy", {"TRPUN": ["TRPP1", "TRPP2", "TRPP3"]}),
}
SCALES = {
    "MRPCM": "Mathematics composite (1990 framework)", "MRPS1": "Number properties and operations",
    "MRPS2": "Measurement", "MRPS3": "Geometry", "MRPS4": "Data analysis, statistics, and probability",
    "MRPS5": "Algebra", "MWPCM": "Mathematics composite (grade 12, 2005 framework)",
    "MWPS1": "Number properties and operations", "MWPS2": "Measurement and geometry",
    "MWPS3": "Data analysis, statistics, and probability", "MWPS4": "Algebra",
    "RRPCM": "Reading composite", "RRPS1": "Literary experience", "RRPS2": "Gain information",
    "RRPS3": "Perform a task", "RRPS4": "Gain and use information",
    "SRPCM": "Science composite (1996 framework)", "SRPS1": "Physical science", "SRPS2": "Earth science",
    "SRPS3": "Life science", "SRPUV": "Science overall (2009 framework)", "WRIRP": "Writing",
    "VOCRP": "Meaning vocabulary", "CIVRP": "Civics", "HRPCM": "U.S. history composite", "HRPS1": "Democracy",
    "HRPS2": "Cultures", "HRPS3": "Technology", "HRPS4": "World role", "GRPCM": "Geography composite",
    "GRPS1": "Space and place", "GRPS2": "Environment and society", "GRPS3": "Spatial dynamics",
    "ERPCM": "Economics composite", "ERPS1": "Market", "ERPS2": "National", "ERPS3": "International",
    "MUSRP": "Music", "VISRP": "Visual arts", "TRPUN": "TEL overall",
    "TRPP1": "Communicating and collaborating", "TRPP2": "Developing solutions and achieving goals",
    "TRPP3": "Understanding technological principles",
    "MRPSCT": "Long-Term Trend mathematics", "RRPSCT": "Long-Term Trend reading"}
STATS = {"MN:MN": "mean", "SD:SD": "sd", "PC:P1": "p10", "PC:P2": "p25", "PC:P5": "p50", "PC:P7": "p75",
         "PC:P9": "p90", "ALC:BB": "below_basic", "ALC:AB": "at_or_above_basic",
         "ALC:AP": "at_or_above_proficient", "ALC:AD": "advanced", "ALD:BA": "at_basic", "ALD:PR": "at_proficient",
         "ALD:AD": "at_advanced"}
SCORE_STATS = [k for k in STATS if not k.startswith("AL")]
GRADES = {1: 4, 2: 8, 3: 12}
NDE_YEARS = [f"{y}R2" for y in range(1990, 2003)] + [f"{y}R3" for y in range(1996, 2027)]
LTT_YEARS = [f"{y}R1" for y in range(1969, 2005)] + [f"{y}R3" for y in range(2004, 2027)]
LTT = {"MAT": "MRPSCT", "RED": "RRPSCT"}

_calls: list[dict] = []


def _path(params: dict) -> Path:
    key = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return RAW / "raw" / (hashlib.sha1(key.encode()).hexdigest() + ".json")


def call(params: dict, refresh: bool = False) -> list | None:
    """One API call, cached on disk. Returns the result list, or None if the API rejected the call."""
    path = _path(params)
    if path.exists() and not refresh:
        body = path.read_text()
    else:
        q = urllib.parse.urlencode({"type": "data", "variable": "TOTAL", **params}, safe=":,")
        req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "talentByState-pipeline"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    body = r.read().decode("utf-8", "replace")
                break
            except urllib.error.HTTPError as e:
                if e.code < 500:              # 400 = the API's "no such year/scale" answer: cache it
                    body = e.read().decode("utf-8", "replace")
                    break
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
            except Exception:  # noqa: BLE001 -- timeouts: back off and retry
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    try:
        d = json.loads(body, strict=False)
        ok = d.get("status") == 200 and isinstance(d.get("result"), list)
    except json.JSONDecodeError:            # error bodies carry unescaped stack traces
        d, ok = None, False
    _calls.append({**params, "ok": ok})
    return d["result"] if ok else None


def discover(refresh: bool) -> list[dict]:
    """Every (program, subject, cohort, scale, yearSample) with national data."""
    probes = []
    for s, (_, scales) in SUBJECTS.items():
        for scale in scales:
            for c in GRADES:
                probes += [dict(subject=s, cohort=c, subscale=scale, Year=y) for y in NDE_YEARS]
    for s, scale in LTT.items():
        for c in GRADES:
            probes += [dict(Program="LTT", subject=s, cohort=c, subscale=scale, Year=y) for y in LTT_YEARS]

    def ok(p):
        return p if call({**p, "jurisdiction": "NT", "stattype": "MN:MN"}, refresh) else None

    with ThreadPoolExecutor(6) as ex:
        found = [p for p in ex.map(ok, probes) if p]
    # main NAEP: subscales are tried in every year their composite exists
    out = []
    for p in found:
        out.append(p)
        if p.get("Program") != "LTT":
            out += [{**p, "subscale": sub} for sub in SUBJECTS[p["subject"]][1][p["subscale"]]]
    return out


COMPOSITES = {scale for _, scales in SUBJECTS.values() for scale in scales}


def tasks(p: dict) -> list[dict]:
    """The calls for one subject x grade x scale x year: one per statistic, every jurisdiction at once.
    (One call with all 14 statistics x 53 jurisdictions takes minutes on the server; one statistic, seconds.)"""
    base = {**p, "jurisdiction": "NT" if p.get("Program") == "LTT" else ",".join(JURIS), "ShowDetails": "true"}
    full = {**base, "stattype": ",".join(STATS)}
    if _path(full).exists():               # cached by an earlier version that asked for everything at once
        return [full]
    stats = STATS if p["subscale"] in COMPOSITES and p.get("Program") != "LTT" else SCORE_STATS
    return [{**base, "stattype": st} for st in stats]


def tidy(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[df.isStatDisplayable == 1]
    df = pd.DataFrame({
        "program": df.get("program", "NDE"),
        "subject": df.subject, "subject_name": df.subject.map(lambda s: SUBJECTS.get(s, (s,))[0]),
        "grade": df.Cohort.map(GRADES), "cohort_label": df.CohortLabel,
        "scale": df.scale, "scale_name": df.scale.map(SCALES),
        "year": df.year, "sample": df["sample"],
        "jurisdiction": df.jurisdiction, "state": df.jurisdiction.map(lambda j: JNAME.get(j, j)),
        "stattype": df.stattype, "stat": df.stattype.map(STATS),
        "value": df.value, "se": df.get("stdError"), "error_flag": df.errorFlag})
    df.loc[df.se < 0, "se"] = None
    return df.drop_duplicates()


def build(refresh: bool = False) -> None:
    combos = discover(refresh)
    print(len(combos), "subject x grade x scale x year combinations", flush=True)
    jobs = [(p, t) for p in combos for t in tasks(p)]
    print(len(jobs), "calls", flush=True)
    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(lambda j: (j[0], call(j[1], refresh) or []), jobs))
    OUT.mkdir(parents=True, exist_ok=True)
    main = [r for p, rs in results if p.get("Program") != "LTT" for r in rs]
    ltt = [r for p, rs in results if p.get("Program") == "LTT" for r in rs]
    m = tidy(main).assign(program="NDE")
    m = m.sort_values(["subject", "grade", "scale", "year", "sample", "jurisdiction", "stattype"])
    m.to_csv(OUT / "naep_long.csv", index=False)
    lt = tidy(ltt).assign(program="LTT")
    lt["grade"] = None                     # LTT reports by age: cohort_label says "Age 9" etc.
    lt.sort_values(["subject", "cohort_label", "year", "sample", "stattype"]).to_csv(OUT / "naep_ltt.csv", index=False)
    idx = ["jurisdiction", "state", "subject", "subject_name", "grade", "scale", "scale_name", "year", "sample"]
    w = m.pivot_table(index=idx, columns="stat", values="value", aggfunc="first")
    se = m.pivot_table(index=idx, columns="stat", values="se", aggfunc="first").add_suffix("_se")
    cols = [STATS[k] for k in STATS if STATS[k] in w]
    w = w[cols].join(se[[c + "_se" for c in cols if c + "_se" in se]]).reset_index()
    w.to_csv(OUT / "naep_wide.csv", index=False)
    cov = (m[(m.stat == "mean") & m.jurisdiction.isin(STATES)]
           .groupby(["subject_name", "grade", "scale", "year", "sample"]).jurisdiction.nunique()
           .rename("states").reset_index())
    cov.to_csv(OUT / "coverage.csv", index=False)
    pd.DataFrame(_calls).to_csv(OUT / "calls.csv", index=False)
    print(f"main: {len(m):,} rows, LTT: {len(lt):,} rows", flush=True)


if __name__ == "__main__":
    build(refresh="--refresh" in sys.argv)
