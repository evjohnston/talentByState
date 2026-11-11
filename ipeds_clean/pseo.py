"""Census Post-Secondary Employment Outcomes (PSEO): do a state's graduates stay and work there, and what do they earn?

    python -m ipeds_clean.pseo            # rebuild every output (re-uses cache/pseo/ if present)
    python -m ipeds_clean.pseo refresh    # re-read the source files first

Source: U.S. Census Bureau, LEHD Post-Secondary Employment Outcomes, sources/census_pseo/. Each release
folder (R2019Q2 ... R2026Q2, plus latest_release) holds per-state subfolders and an all/ folder that stacks
every state; earlier_releases/ has the 2018 pilot files (CO, MI, TX, WI; a different layout). Only the newest
release is used for the outputs: latest_release, which is byte-identical to R2026Q2 (schema V4.14.1, files
pseopu_*_20260715_1529, graduation years 2001-2021). Older releases are earlier vintages of the same series;
they are used only for coverage history (states and institutions per release) and for one revision check
against R2025Q4. Nothing is summed across releases.

Files read (latest_release/all/):
  pseoe_all.csv.gz   earnings: p25/p50/p75 annual earnings 1, 5 and 10 years after graduation, the count of
                     graduates with earnings (yN_grads_earn) and the IPEDS completions count (yN_ipeds_count)
  pseof_all.csv.gz   flows: graduates employed (yN_grads_emp), employed in the institution's state
                     (yN_grads_emp_instate) and not employed (yN_grads_nme), nationally and by the Census
                     division of the job; by industry too (not used here)
  pseo_all_institutions.csv, pseo_all_partners.txt   participating institutions (OPEID) and data partners
Rows used are the state rollups (inst_level S: every participating institution in the state, the
"institution" field is the state FIPS code), all industries, by degree level x (all fields | 2-digit CIP)
x graduation cohort. Bachelor's cohorts are 3 graduation years (2001 = 2001-2003, ..., 2019 = 2019-2021);
other degrees 5 (2001, 2006, 2011, 2016 = 2016-2020); "all" = PSEO's pooled all-cohorts rows. Latest cohorts
with data: bachelor's y1 2019, y5 2016, y10 2010; other degrees y1 2016, y5 2011, y10 2006.

Scope: PSEO covers only graduates of participating institutions (state systems that signed data
agreements), 37 states + DC in this release (plus Western Governors University, an online institution
published under "US" and excluded from the state rows here). A state row therefore means "graduates of the
participating institutions in that state", not all of the state's graduates; coverage.csv gives the share
of the state's IPEDS completions those institutions account for. Employment is from LEHD (UI-covered jobs
in all states) plus federal employment; graduates are tracked wherever in the US they work.

Measures (pseo_state.csv; years_after 1, 5, 10):
  grads_emp, grads_emp_instate, grads_nme   counts from the flows file
  share_instate          grads_emp_instate / grads_emp: share of employed graduates working in the state of
                         their institution (retention); 1 - share_instate work in another state
  employment_rate        grads_emp / (grads_emp + grads_nme)
  share_instate_of_grads grads_emp_instate / (grads_emp + grads_nme)
  p25/p50/p75_earnings   PSEO's published percentiles of annual earnings (inflation-adjusted by Census to a
                         common recent dollar year; the files do not say which), grads_earn, ipeds_count
  Rows that are not a published rollup are summed from published cells: STEM / non_stem fields (2-digit
  CIP; STEM = states.STEM_CIP2 = 03, 04, 11, 14, 15, 26, 27, 40), the combined "doctoral" level (doc_res +
  doc_prof) and "US" (sum of the participating states). Their measures are counts and share_instate over
  published cells only, p50_earnings_wmean (mean of the cells' published medians weighted by grads_earn; not
  a true median), and earnings_published_share / flows_published_share (share of the group's IPEDS count in
  cells whose value is published). Counts in these rows are therefore lower bounds when the share < 1.
Suppression: a value is used only when its status flag is 1. Status 5 (suppressed: too few graduates or
Census disclosure rules) and -1 (not available: the cohort has not reached that year, or no such data) are
left missing, never zero. ipeds_count is used wherever a number is present (its flags are 1-4).

Destinations (pseo_destinations.csv): PSEO publishes the place of work only by Census division (9), not by
state, so origin-state -> destination-state shares are not available. Per origin state, cohort, degree,
field, years_after: in_state; home_division_other (other states in the origin's own division =
division count - in-state count); each other division; suppressed (graduates in cells whose division
counts are suppressed). Shares are of grads_emp and sum to 1.

Outputs (data/pseo/):
  pseo_state.csv          state, grad_cohort, cohort_years, degree_level, field, years_after, measure, value
  pseo_state_wide.csv     one row per state x cohort x degree x field x years_after; latest = 1 marks the most
                          recent cohort with data in any state for that degree and years_after (bach y1:
                          2019), latest_for_state = 1 the state's own most recent (MA, MI, OK, ME have no
                          2019 bachelor's cohort, so their latest y1 is 2016)
  pseo_destinations.csv   origin_state, grad_cohort, cohort_years, degree_level, field, years_after,
                          destination, division, grads_emp, share
  coverage.csv            per release x state: participating institutions; for the latest release also the
                          partners, Census's own coverage estimate (2015), and the share of the state's IPEDS
                          completions (2019-2021, first majors) at institutions matched to PSEO by OPEID
  files.csv               every file under sources/census_pseo/: release, version line, bytes, whether used
  checks.csv              internal consistency and cross-source checks
Intermediate (cache/pseo/): pseoe_<release>.parquet (the whole earnings file, typed) and
pseof_<release>.parquet (flows rows for state and institution rollups, all industries, plus state x
industry rows), written the first time the gz files are read; institution_unitid.parquet, the PSEO OPEID ->
IPEDS unitid match used for coverage (8-digit OPEID, else 6-digit OPEID in the same state).
"""
from __future__ import annotations

import hashlib
import re
import sys

import numpy as np
import pandas as pd

from .config import CACHE, DATA, SOURCES
from .states import ABBR, STEM_CIP2

SRC = SOURCES / "census_pseo"
REL = SRC / "latest_release"
OUT = DATA / "pseo"
RAW = CACHE / "pseo"
SOURCE = "Data from U.S. Census Bureau, LEHD Post-Secondary Employment Outcomes"
REVISION_RELEASE = "R2025Q4"
IPEDS_YEARS = (2019, 2021)          # IPEDS completion years lined up with the latest bachelor's cohort
YEARS = [1, 5, 10]

DEGREE = {"01": "cert_lt1", "02": "cert_1_2", "03": "assoc", "04": "cert_2_4", "05": "bach", "06": "pb_cert",
          "07": "master", "08": "pm_cert", "17": "doc_res", "18": "doc_prof", "19": "doc_other"}
COMBINED = {"doc_res": "doctoral", "doc_prof": "doctoral", "doc_other": "doctoral"}
DIVISION = {1: "New England", 2: "Middle Atlantic", 3: "East North Central", 4: "West North Central",
            5: "South Atlantic", 6: "East South Central", 7: "West South Central", 8: "Mountain", 9: "Pacific"}
STATE_DIV = {**dict.fromkeys("CT ME MA NH RI VT".split(), 1), **dict.fromkeys("NJ NY PA".split(), 2),
             **dict.fromkeys("IL IN MI OH WI".split(), 3), **dict.fromkeys("IA KS MN MO NE ND SD".split(), 4),
             **dict.fromkeys("DE DC FL GA MD NC SC VA WV".split(), 5), **dict.fromkeys("AL KY MS TN".split(), 6),
             **dict.fromkeys("AR LA OK TX".split(), 7), **dict.fromkeys("AZ CO ID MT NV NM UT WY".split(), 8),
             **dict.fromkeys("AK CA HI OR WA".split(), 9)}
# flows aggregation levels kept in the cache: state & institution rollups x {national, division} x all
# industries, and state x national x NAICS sector
FLOW_AGGS = {26, 28, 32, 34, 38, 40, 44, 46, 122, 124, 128, 130, 74, 76, 80, 82}
KEY = ["state", "grad_cohort", "cohort_years", "degree_level"]


# ---------------------------------------------------------------- reading

def release_version(folder=REL) -> str:
    """'2026Q2' from the version file of a release folder."""
    for p in [folder / "all" / "version_pseo.txt", folder / "us" / "version_pseo.txt"]:
        if p.exists():
            m = re.search(r"\s(\d{4}Q\d)\s", p.read_text(encoding="utf-8-sig"))
            if m:
                return m.group(1)
    return folder.name.lstrip("R")


def _typed(d: pd.DataFrame) -> pd.DataFrame:
    for c in d:
        if c.startswith("status_"):
            d[c] = pd.to_numeric(d[c], errors="coerce").astype("Int8")
        elif c.startswith("y") and c[1:3].rstrip("_").isdigit():
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d["agg_level_pseo"] = d["agg_level_pseo"].astype(int)
    return d


def read_flows(path, aggs=FLOW_AGGS, chunksize=1_000_000) -> pd.DataFrame:
    """Stream a pseof file, keeping the given aggregation levels."""
    keep = []
    for ch in pd.read_csv(path, dtype=str, chunksize=chunksize, encoding="utf-8-sig"):
        keep.append(ch[ch.agg_level_pseo.astype(int).isin(aggs)])
    return _typed(pd.concat(keep, ignore_index=True))


def load(refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    rel = release_version()
    RAW.mkdir(parents=True, exist_ok=True)
    pe, pf = RAW / f"pseoe_{rel}.parquet", RAW / f"pseof_{rel}.parquet"
    if refresh or not pe.exists():
        _typed(pd.read_csv(REL / "all" / "pseoe_all.csv.gz", dtype=str, encoding="utf-8-sig")).to_parquet(pe)
    if refresh or not pf.exists():
        read_flows(REL / "all" / "pseof_all.csv.gz").to_parquet(pf)
    return pd.read_parquet(pe), pd.read_parquet(pf)


# ---------------------------------------------------------------- cells

def _base(d: pd.DataFrame) -> pd.DataFrame:
    """State rollup rows -> state, cohort, degree, cip keys."""
    d = d[d.inst_level == "S"].copy()
    d["state"] = d.institution.astype(int).map(ABBR)
    d["grad_cohort"] = d.grad_cohort.replace({"0000": "all"})
    d["cohort_years"] = d.grad_cohort_years.astype(int)
    d["degree_level"] = d.degree_level.map(DEGREE)
    return d


def cells(e: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    """One row per state x cohort x degree x cip cell x years_after with earnings and national flows."""
    ids = KEY + ["cip_level", "cipcode"]
    e = _base(e[e.agg_level_pseo.isin([26, 28, 32, 34])])
    f = _base(f[f.agg_level_pseo.isin([26, 28, 32, 34])])
    out = []
    for y in YEARS:
        a = e[ids].copy()
        a["years_after"] = y
        ok = e[f"status_y{y}_earnings"].eq(1)
        for p in ["p25", "p50", "p75"]:
            a[f"{p}_earnings"] = e[f"y{y}_{p}_earnings"].where(ok)
        a["grads_earn"] = e[f"y{y}_grads_earn"].where(e[f"status_y{y}_grads_earn"].eq(1))
        a["earn_ok"] = ok & a.grads_earn.notna()
        a["ipeds_count"] = e[f"y{y}_ipeds_count"]
        b = f[ids].copy()
        b["years_after"] = y
        b["grads_emp"] = f[f"y{y}_grads_emp"].where(f[f"status_y{y}_grads_emp"].eq(1))
        b["grads_emp_instate"] = f[f"y{y}_grads_emp_instate"].where(f[f"status_y{y}_grads_emp_instate"].eq(1))
        b["grads_nme"] = f[f"y{y}_grads_nme"].where(f[f"status_y{y}_grads_nme"].eq(1))
        out.append(a.merge(b, on=ids + ["years_after"], how="outer"))
    c = pd.concat(out, ignore_index=True)
    c["earn_ok"] = c.earn_ok.fillna(False).astype(bool)
    c["flow_ok"] = c.grads_emp.notna() & c.grads_emp_instate.notna()
    c["field"] = np.where(c.cip_level == "A", "all", np.where(c.cipcode.isin(STEM_CIP2), "stem", "non_stem"))
    return c


def direct(c: pd.DataFrame) -> pd.DataFrame:
    """Published rollups: state x single degree x all fields."""
    d = c[(c.cip_level == "A")].copy()
    d["share_instate"] = d.grads_emp_instate / d.grads_emp
    tot = d.grads_emp + d.grads_nme
    d["employment_rate"] = d.grads_emp / tot
    d["share_instate_of_grads"] = d.grads_emp_instate / tot
    cols = ["grads_emp", "grads_emp_instate", "grads_nme", "share_instate", "employment_rate",
            "share_instate_of_grads", "p25_earnings", "p50_earnings", "p75_earnings", "grads_earn", "ipeds_count"]
    return d[KEY + ["field", "years_after"] + cols]


def _expand(c: pd.DataFrame) -> pd.DataFrame:
    """Memberships of each cell in the groups that are summed: fields, combined doctoral, US."""
    parts = []
    cip2 = c[c.cip_level == "2"]
    allf = c[c.cip_level == "A"]
    comb = lambda d: d[d.degree_level.isin(COMBINED)].assign(degree_level=lambda x: x.degree_level.map(COMBINED))  # noqa: E731
    for d in [cip2, comb(cip2), comb(allf)]:
        parts += [d, d.assign(state="US")]
    parts.append(allf.assign(state="US"))
    return pd.concat(parts, ignore_index=True)


def summed(c: pd.DataFrame) -> pd.DataFrame:
    x = _expand(c)
    x["w"] = x.grads_earn.where(x.earn_ok)
    x["wp50"] = x.p50_earnings.where(x.earn_ok) * x.w
    x["ipeds_earn"] = x.ipeds_count.where(x.earn_ok)
    x["ipeds_flow"] = x.ipeds_count.where(x.flow_ok)
    x["emp"] = x.grads_emp.where(x.flow_ok)
    x["inst"] = x.grads_emp_instate.where(x.flow_ok)
    g = x.groupby(KEY + ["field", "years_after"])[["w", "wp50", "ipeds_count", "ipeds_earn", "ipeds_flow",
                                                   "emp", "inst"]].sum(min_count=1)
    s = pd.DataFrame(index=g.index)
    s["grads_emp"] = g.emp
    s["grads_emp_instate"] = g.inst
    s["share_instate"] = g.inst / g.emp
    s["flows_published_share"] = g.ipeds_flow.fillna(0) / g.ipeds_count
    s["p50_earnings_wmean"] = g.wp50 / g.w
    s["grads_earn"] = g.w
    s["ipeds_count"] = g.ipeds_count
    s["earnings_published_share"] = g.ipeds_earn.fillna(0) / g.ipeds_count
    return s.reset_index()


def state_long(c: pd.DataFrame) -> pd.DataFrame:
    w = pd.concat([direct(c), summed(c)], ignore_index=True)
    long = w.melt(id_vars=KEY + ["field", "years_after"], var_name="measure").dropna(subset=["value"])
    return long[["state", "grad_cohort", "cohort_years", "degree_level", "field", "years_after", "measure", "value"]]


def wide(long: pd.DataFrame) -> pd.DataFrame:
    idx = KEY + ["field", "years_after"]
    w = long.pivot_table(index=idx, columns="measure", values="value", aggfunc="first").reset_index()
    w.columns.name = None
    # latest: the most recent cohort with a share_instate or median for that degree, cohort length and year
    has = w[w.grad_cohort != "all"]
    has = has[has[["share_instate", "p50_earnings", "p50_earnings_wmean"]].notna().any(axis=1)]
    k = ["degree_level", "cohort_years", "years_after"]
    latest = has[has.state != "US"].groupby(k).grad_cohort.max().rename("latest_cohort")
    w = w.merge(latest.reset_index(), on=k, how="left")
    w["latest"] = (w.grad_cohort == w.latest_cohort).astype(int)
    mine = has.groupby(["state", "field"] + k).grad_cohort.max().rename("_mine")
    w = w.merge(mine.reset_index(), on=["state", "field"] + k, how="left")
    w["latest_for_state"] = (w.grad_cohort == w._mine).astype(int)
    order = ["grads_emp", "grads_emp_instate", "share_instate", "grads_nme", "employment_rate",
             "share_instate_of_grads", "flows_published_share", "p25_earnings", "p50_earnings", "p75_earnings",
             "p50_earnings_wmean", "grads_earn", "ipeds_count", "earnings_published_share"]
    return w[idx + ["latest", "latest_for_state"] + [c for c in order if c in w]].sort_values(idx)


# ---------------------------------------------------------------- destinations

def destinations(f: pd.DataFrame) -> pd.DataFrame:
    ids = KEY + ["cip_level", "cipcode"]
    n = _base(f[f.agg_level_pseo.isin([26, 28, 32, 34])])
    dv = _base(f[f.agg_level_pseo.isin([122, 124, 128, 130])])
    dv["division"] = dv.geography.astype(int)
    out = []
    for y in YEARS:
        a = n[ids].copy()
        a["years_after"] = y
        a["denom"] = n[f"y{y}_grads_emp"].where(n[f"status_y{y}_grads_emp"].eq(1))
        b = dv[ids + ["division"]].copy()
        b["years_after"] = y
        b["emp"] = dv[f"y{y}_grads_emp"].where(dv[f"status_y{y}_grads_emp"].eq(1))
        b["inst"] = dv[f"y{y}_grads_emp_instate"].where(dv[f"status_y{y}_grads_emp_instate"].eq(1))
        a = a[a.denom.notna()]
        out.append((a, b.merge(a[ids + ["years_after"]], on=ids + ["years_after"])))   # only cells with a total
    a = pd.concat([o[0] for o in out], ignore_index=True)
    b = pd.concat([o[1] for o in out], ignore_index=True)
    grp = []
    for d, cols in [(a, ["denom"]), (b, ["emp", "inst"])]:
        d = d.assign(field=np.where(d.cip_level == "A", "all", np.where(d.cipcode.isin(STEM_CIP2), "stem", "non_stem")))
        comb = d[d.degree_level.isin(COMBINED)].assign(degree_level=lambda x: x.degree_level.map(COMBINED))
        d = pd.concat([d[d.cip_level == "A"], d[d.cip_level == "2"], comb[comb.cip_level == "A"],
                       comb[comb.cip_level == "2"]])
        # single-degree all-field rows come straight from the rollup; others are summed from cells
        grp.append(d)
    key = KEY + ["field", "years_after"]
    den = grp[0].groupby(key).denom.sum().rename("denom")
    by = grp[1].groupby(key + ["division"])[["emp", "inst"]].sum(min_count=1).reset_index()
    by["home"] = by.state.map(STATE_DIV)
    rows = []
    home = by[by.division == by.home]
    rows.append(home.assign(destination="in_state", grads_emp=home.inst))
    rows.append(home.assign(destination="home_division_other", grads_emp=home.emp - home.inst))
    other = by[by.division != by.home]
    rows.append(other.assign(destination=other.division.map(DIVISION), grads_emp=other.emp))
    r = pd.concat(rows, ignore_index=True)
    r = r.merge(den.reset_index(), on=key)
    pub = r.groupby(key).grads_emp.sum().rename("pub")
    sup = den.reset_index().merge(pub.reset_index(), on=key, how="left").fillna({"pub": 0})
    sup = sup.assign(destination="suppressed", division=np.nan, grads_emp=sup.denom - sup.pub)
    r = pd.concat([r, sup], ignore_index=True)
    r["share"] = r.grads_emp / r.denom
    r = r[r.grads_emp.notna()].rename(columns={"state": "origin_state"})
    r["division"] = r.division.astype("Int64")
    cols = ["origin_state", "grad_cohort", "cohort_years", "degree_level", "field", "years_after", "destination",
            "division", "grads_emp", "share"]
    order = {"in_state": 0, "home_division_other": 1, "suppressed": 99}
    r["_o"] = r.destination.map(order).fillna(2 + r.division.fillna(0))
    return r.sort_values(cols[:6] + ["_o"])[cols]


# ---------------------------------------------------------------- coverage

def partners(path) -> pd.DataFrame:
    rows = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = [x.strip() for x in block.splitlines() if x.strip()]
        fips, _, name = lines[0].partition(" ")
        pct = re.match(r"(\d+)% of statewide graduates covered \((\d{4}) estimate\)", lines[1]) if len(lines) > 1 else None
        rows.append({"state": ABBR.get(int(fips), "US"), "state_name": name,
                     "census_coverage_pct": int(pct.group(1)) if pct else np.nan,
                     "census_coverage_year": int(pct.group(2)) if pct else np.nan,
                     "partners": "; ".join(lines[2:] if pct else lines[1:])})
    return pd.DataFrame(rows)


def _releases():
    return sorted([p for p in SRC.iterdir() if p.is_dir() and re.match(r"R\d{4}Q\d$", p.name)])


def coverage(e: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coverage by release x state, and the institution match table for the latest release."""
    hist = []
    for r in _releases():
        inst_f = r / "all" / "pseo_all_institutions.csv"
        if inst_f.exists():
            i = pd.read_csv(inst_f, dtype=str, encoding="utf-8-sig")
            n = i.groupby("institution_state").institution.nunique()
        else:   # R2019Q2, R2020Q3: no institution list; states from the version file
            txt = (r / "all" / "version_pseo.txt").read_text(encoding="utf-8-sig")
            n = pd.Series(np.nan, index=sorted(set(re.findall(r"PSEO[EF] ([A-Z]{2}) ", txt))))
        hist.append(pd.DataFrame({"release": r.name, "state": n.index, "pseo_institutions": n.values}))
    hist = pd.concat(hist, ignore_index=True)
    first = hist.groupby("state").release.min().rename("first_release")

    inst = pd.read_csv(REL / "all" / "pseo_all_institutions.csv", dtype=str, encoding="utf-8-sig")
    d = pd.read_parquet(DATA / "ipeds" / "harmonized" / "directory.parquet", columns=["year", "unitid", "stabbr", "opeid"])
    d = d[d.opeid.notna() & (d.opeid.str.len() == 8)]
    by8 = d.drop_duplicates(["opeid", "unitid"])[["opeid", "unitid"]]
    m8 = inst.merge(by8, left_on="institution", right_on="opeid", how="inner").assign(match="opeid8")
    rest = inst[~inst.institution.isin(m8.institution)].assign(op6=lambda x: x.institution.str[:6])
    d6 = d.assign(op6=d.opeid.str[:6]).drop_duplicates(["op6", "unitid", "stabbr"])[["op6", "unitid", "stabbr"]]
    m6 = rest.merge(d6, left_on=["op6", "institution_state"], right_on=["op6", "stabbr"]).assign(match="opeid6_same_state")
    match = pd.concat([m8, m6], ignore_index=True)[["institution", "label", "institution_state", "unitid", "match"]]
    match = match.drop_duplicates(["institution", "unitid"])

    c = pd.read_parquet(DATA / "ipeds" / "harmonized" / "completions.parquet", columns=["year", "unitid", "award_level", "total"],
                        filters=[("year", ">=", IPEDS_YEARS[0]), ("year", "<=", IPEDS_YEARS[1])])
    c["lvl"] = c.award_level.astype(str).map({"bach": "bach", "master": "master", "doc_res": "doctoral",
                                             "doc_prof": "doctoral"})
    st = d[d.year.between(*IPEDS_YEARS)].drop_duplicates(["year", "unitid"])[["year", "unitid", "stabbr"]]
    c = c.dropna(subset=["lvl"]).merge(st, on=["year", "unitid"], how="left")
    c["covered"] = c.unitid.isin(match.unitid)
    tot = c.pivot_table(index="stabbr", columns="lvl", values="total", aggfunc="sum")
    cov = c[c.covered].pivot_table(index="stabbr", columns="lvl", values="total", aggfunc="sum")

    rel = REL.resolve()
    latest_name = next((r.name for r in _releases() if release_version(r) == release_version(rel)), REL.name)
    p = partners(REL / "all" / "pseo_all_partners.txt")
    cur = hist[hist.release == latest_name].drop(columns="release")
    cur = cur.merge(p, on="state", how="outer").merge(first.reset_index(), on="state", how="left")
    cur["ipeds_matched_institutions"] = cur.state.map(match.groupby("institution_state").institution.nunique())
    cur["ipeds_unitids"] = cur.state.map(match.groupby("institution_state").unitid.nunique())
    for lvl in ["bach", "master", "doctoral"]:
        cur[f"ipeds_{lvl}_state"] = cur.state.map(tot[lvl])
        cur[f"ipeds_{lvl}_covered"] = cur.state.map(cov[lvl]).where(cur[f"ipeds_{lvl}_state"].isna(), cur.state.map(cov[lvl]).fillna(0))
        cur[f"ipeds_{lvl}_share"] = cur[f"ipeds_{lvl}_covered"] / cur[f"ipeds_{lvl}_state"]
    # PSEO's own IPEDS count for the latest bachelor's cohort (graduation years 2019-2021)
    s = _base(e[e.agg_level_pseo.eq(32)])
    s = s[(s.degree_level == "bach") & (s.grad_cohort == "2019")].groupby("state").y1_ipeds_count.sum(min_count=1)
    cur["pseo_bach_2019_ipeds_count"] = cur.state.map(s)
    cur["pseo_bach_2019_share_of_ipeds"] = cur.pseo_bach_2019_ipeds_count / cur.ipeds_bach_state
    cur.insert(0, "release", latest_name)
    hist = hist[hist.release != latest_name]
    allcov = pd.concat([cur, hist], ignore_index=True).sort_values(["release", "state"], ascending=[False, True])
    return allcov, match


# ---------------------------------------------------------------- files, checks

def _kind(name: str) -> str:
    for pat, k in [(r"^pseoe_", "earnings"), (r"^pseof_", "flows"), (r"_institutions\.csv$", "institutions"),
                   (r"_partners\.txt$", "partners"), (r"\.xlsx$", "workbook"), (r"^version_pseo", "version"),
                   (r"^graduate_earnings", "pilot earnings (2018)"), (r"schema", "schema")]:
        if re.search(pat, name, re.I):
            return k
    return "other"


def files(latest_name: str) -> pd.DataFrame:
    rows = []
    for p in sorted(SRC.rglob("*")):
        if not p.is_file() or p.name == ".DS_Store":
            continue
        parts = p.relative_to(SRC).parts
        release, sub = parts[0], (parts[1] if len(parts) > 2 else "")
        k = _kind(p.name)
        vf = p.parent / "version_pseo.txt"
        ver = ""
        if vf.exists() and k in ("earnings", "flows"):
            tag = "PSEOE" if k == "earnings" else "PSEOF"
            lines = [x.strip() for x in vf.read_text(encoding="utf-8-sig").splitlines() if x.startswith(tag + " ")]
            ver = lines[0] if lines else ""
            if sub == "all" and lines:     # stacked file: schema + release, and how many states it stacks
                m = re.search(r"(V\S+ \d{4}Q\d)", lines[0])
                ver = f"{tag} all {m.group(1) if m else ''} ({len(lines)} state files)"
        if release == "latest_release" and sub == "all" and k in ("earnings", "flows", "institutions", "partners"):
            used = "primary"
        elif release == "latest_release" or release == latest_name:
            used = "not used: per-state subset or copy of the primary all/ files" if release == "latest_release" \
                else "not used: identical copy of latest_release"
        elif sub == "all" and k == "institutions":
            used = "coverage history"
        elif release == REVISION_RELEASE and sub == "all" and k in ("earnings", "flows"):
            used = "revision check"
        elif sub == "all" and k == "version" and release.startswith("R"):
            used = "coverage history" if not (p.parent / "pseo_all_institutions.csv").exists() else "not used"
        else:
            used = "not used: earlier vintage"
        rows.append({"release": release, "folder": sub, "file": p.name, "kind": k, "bytes": p.stat().st_size,
                     "version": ver, "used": used})
    return pd.DataFrame(rows)


def _md5(p) -> str:
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def checks(e, f, c, dest, cov) -> pd.DataFrame:
    out = []
    add = lambda check, value, ok, note="": out.append({"check": check, "value": value, "ok": bool(ok), "note": note})  # noqa: E731
    latest_name = cov.release.iloc[0]
    same = all(_md5(REL / "all" / n) == _md5(SRC / latest_name / "all" / n) for n in ["pseoe_all.csv.gz", "pseof_all.csv.gz"])
    add("latest_release identical to newest R folder", latest_name, same, "md5 of pseoe_all and pseof_all")

    # division counts sum to the national count (single-degree, all-field rollups, all division cells published)
    n = _base(f[f.agg_level_pseo.isin([26, 32])])
    dv = _base(f[f.agg_level_pseo.isin([122, 128])])
    worst, home_bad = 0.0, 0
    for y in YEARS:
        ok = dv[f"status_y{y}_grads_emp"].eq(1)
        g = dv.assign(v=dv[f"y{y}_grads_emp"].where(ok), bad=~ok).groupby(KEY).agg(v=("v", "sum"), bad=("bad", "sum"))
        t = n.set_index(KEY)[f"y{y}_grads_emp"].where(n.set_index(KEY)[f"status_y{y}_grads_emp"].eq(1))
        j = g.join(t.rename("t")).dropna()
        j = j[j.bad == 0]
        worst = max(worst, float((j.v - j.t).abs().max()) if len(j) else 0.0)
        hi = dv[dv[f"y{y}_grads_emp_instate"] > 0]
        home_bad += int((hi.geography.astype(int) != hi.state.map(STATE_DIV)).sum())
    add("sum of division grads_emp = national grads_emp (max abs diff)", worst, worst == 0)
    add("in-state employment only in the state's own Census division (rows violating)", home_bad, home_bad == 0)

    d = direct(c)
    add("grads_emp_instate <= grads_emp (rows violating)", int((d.grads_emp_instate > d.grads_emp).sum()),
        (d.grads_emp_instate > d.grads_emp).sum() == 0)
    r = d.dropna(subset=["grads_emp", "grads_nme", "ipeds_count"])
    r = r[r.ipeds_count > 0]
    ratio = (r.grads_emp + r.grads_nme) / r.ipeds_count
    add("(grads_emp + grads_nme) / ipeds_count, median over state rollups", round(float(ratio.median()), 4),
        abs(ratio.median() - 1) < 0.05, f"p5 {ratio.quantile(.05):.3f}, p95 {ratio.quantile(.95):.3f}")
    s = dest.groupby(["origin_state", "grad_cohort", "cohort_years", "degree_level", "field", "years_after"]).share.sum()
    add("destination shares sum to 1 (max abs deviation)", float((s - 1).abs().max()), (s - 1).abs().max() < 1e-9)

    # suppression extent
    for y in YEARS:
        st = _base(e[e.agg_level_pseo.isin([32, 34])])[f"status_y{y}_earnings"].value_counts().to_dict()
        add(f"earnings status flags, state cells, y{y}", str({int(k): int(v) for k, v in st.items()}), True,
            "1 published, 5 suppressed, -1 not available")
        st = _base(f[f.agg_level_pseo.isin([32, 34])])[f"status_y{y}_grads_emp"].value_counts().to_dict()
        add(f"flows status flags, state cells, y{y}", str({int(k): int(v) for k, v in st.items()}), True)
    sm = summed(c)
    for fld in ["stem", "non_stem"]:
        x = sm[(sm.field == fld) & (sm.degree_level == "bach") & (sm.state != "US") & (sm.years_after == 1) &
               (sm.grad_cohort == "2019")]
        add(f"bach 2019 y1 {fld}: median flows_published_share across states", round(float(x.flows_published_share.median()), 4),
            True, f"min {x.flows_published_share.min():.3f}")
        add(f"bach 2019 y1 {fld}: median earnings_published_share across states",
            round(float(x.earnings_published_share.median()), 4), True, f"min {x.earnings_published_share.min():.3f}")
    # stem + non_stem published grads_emp vs the all-field rollup
    a = d[(d.degree_level == "bach") & (d.grad_cohort == "2019") & (d.years_after == 1)].set_index("state").grads_emp
    b = sm[(sm.degree_level == "bach") & (sm.grad_cohort == "2019") & (sm.years_after == 1) & (sm.state != "US")]
    b = b.groupby("state").grads_emp.sum()
    q = (b / a).dropna()
    add("bach 2019 y1: (stem + non_stem published grads_emp) / all-field grads_emp, min across states",
        round(float(q.min()), 4), q.max() <= 1.000001, f"median {q.median():.4f}")

    # PSEO's IPEDS count vs IPEDS completions at matched institutions
    cur = cov[cov.release == latest_name]
    x = cur.dropna(subset=["pseo_bach_2019_ipeds_count", "ipeds_bach_covered"])
    x = x[x.state != "US"]
    rr = x.pseo_bach_2019_ipeds_count / x.ipeds_bach_covered
    add("PSEO y1_ipeds_count (bach 2019-21) / IPEDS bach completions 2019-21 at matched institutions, median",
        round(float(rr.median()), 4), abs(rr.median() - 1) < 0.1,
        "; ".join(f"{s}:{v:.2f}" for s, v in zip(x.state, rr) if abs(v - 1) > 0.1))
    x = cur.dropna(subset=["census_coverage_pct", "ipeds_bach_share"])
    add("Census 2015 coverage estimate vs IPEDS bach share 2019-21 (corr)",
        round(float(np.corrcoef(x.census_coverage_pct, x.ipeds_bach_share)[0, 1]), 3), True)

    # revisions vs the previous release
    prev = SRC / REVISION_RELEASE / "all"
    if (prev / "pseof_all.csv.gz").exists():
        pf = read_flows(prev / "pseof_all.csv.gz", aggs={32})
        pe = _typed(pd.read_csv(prev / "pseoe_all.csv.gz", dtype=str, encoding="utf-8-sig"))
        pc = cells(pe, pf)
        old = direct(pc)
        k = KEY + ["field", "years_after"]
        j = d.merge(old, on=k, suffixes=("", "_old"))
        j = j[(j.degree_level == "bach") & (j.grad_cohort == "2016") & (j.years_after == 1)]
        ds = (j.share_instate - j.share_instate_old).abs()
        dp = (j.p50_earnings / j.p50_earnings_old - 1).abs()
        add(f"revision vs {REVISION_RELEASE}: bach 2016 y1 share_instate, max abs change", round(float(ds.max()), 4),
            True, f"{len(j)} states in both; median {ds.median():.4f}")
        add(f"revision vs {REVISION_RELEASE}: bach 2016 y1 p50_earnings, max relative change", round(float(dp.max()), 4),
            True, f"median {dp.median():.4f}; a median of 0 means the same dollar year in both releases")
    return pd.DataFrame(out)


# ---------------------------------------------------------------- build

def build(refresh: bool = False):
    e, f = load(refresh)
    c = cells(e, f)
    long = state_long(c)
    w = wide(long)
    dest = destinations(f)
    cov, match = coverage(e)
    OUT.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT / "pseo_state.csv", index=False)
    w.to_csv(OUT / "pseo_state_wide.csv", index=False)
    dest.to_csv(OUT / "pseo_destinations.csv", index=False)
    cov.to_csv(OUT / "coverage.csv", index=False)
    match.to_parquet(RAW / "institution_unitid.parquet", index=False)
    fl = files(cov.release.iloc[0])
    fl.to_csv(OUT / "files.csv", index=False)
    ch = checks(e, f, c, dest, cov)
    ch.to_csv(OUT / "checks.csv", index=False)
    print(ch.to_string(index=False))
    show = w[(w.latest == 1) & (w.degree_level == "bach") & (w.field == "all") & (w.years_after.isin([1, 5]))]
    print(show.pivot_table(index="state", columns="years_after", values=["share_instate", "p50_earnings"]).round(3).to_string())
    return w


if __name__ == "__main__":
    build(refresh="refresh" in sys.argv[1:])
