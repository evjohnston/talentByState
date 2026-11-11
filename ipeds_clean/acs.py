"""American Community Survey (Census Bureau): the foreign-born population and STEM workforce by state.

    python -m ipeds_clean.acs                 # tables for every year in YEARS + PUMS for PUMS_YEARS
    python -m ipeds_clean.acs tables          # published detailed tables only
    python -m ipeds_clean.acs pums 2023 2024  # PUMS for the years named

Two sources, both ACS 1-year (2020 is skipped: the Bureau released only experimental 1-year estimates). Detailed
tables run 2014-2025; PUMS 2014-2024 (as of 2026-11-11 the 2025 1-year PUMS is on neither www2.census.gov nor the
API's 2025/acs/acs1/pums; add 2025 to PUMS_YEARS when it is):

* Detailed tables, from the Census API (api.census.gov, needs a free key in $CENSUS_API_KEY, or as CENSUS_API_KEY=... in the
  project's .env, or in a .census_key file; sign up at https://api.census.gov/data/key_signup.html). Without a
  key the keyless table-based summary files on www2.census.gov are used instead, which only exist for
  2021 on. Variable labels always come from the API's metadata, which needs no key.
    B05002  place of birth by nativity and citizenship status
    B05006  place of birth for the foreign-born population (country detail)
    B06009  place of birth by educational attainment (25+)
* Public Use Microdata Sample (person file, www2.census.gov, no key): workers in STEM occupations by
  nativity, citizenship, degree, country of birth and year of entry. STEM occupations are SOC 15 (computer
  and mathematical), 17 (architecture and engineering), 19 (life, physical and social science) plus the
  three STEM manager codes 11-3021, 11-9041, 11-9121. Workers are the employed (civilian or armed forces)
  and are counted where they live, not where they work. Margins of error use the 80 replicate weights.

Outputs (data/acs/):
  tables_long.csv         year, state, table, variable, label, estimate, moe
  table_measures.csv      year, state, measure, value                (shares derived from the tables)
  pums_stem.csv           year, state, group, measure, value, moe90, n
  pums_stem_wide.csv      the 'all' group of pums_stem.csv, one row per state-year
  files_tables.csv        where each year came from
Intermediate (cache/acs/): api/{year}_{table}_{state|us}.json, the raw API responses (delete one to refetch it);
pums_stem_{year}.parquet, the STEM-worker records kept from each year's
person file, and pums_workers.csv, all-worker totals by state and nativity. The 600 MB person-file zips are
downloaded to a temporary folder and deleted once read.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "acs"
RAW = ROOT / "cache" / "acs"
YEARS = [y for y in range(2014, 2026) if y != 2020]   # detailed tables (2025 1-year released Sept 2026)
PUMS_YEARS = [y for y in YEARS if y <= 2024]           # 2025 1-year PUMS not yet on www2 or the API (checked 2026-11-11)
TABLES = ["B05002", "B05006", "B06009"]
API = "https://api.census.gov/data/{y}/acs/acs1"
SF = "https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/data/1YRData/acsdt1y{y}-{t}.dat"
PUMS = "https://www2.census.gov/programs-surveys/acs/data/pums/{y}/1-Year/csv_pus.zip"
SOURCE = "Data from U.S. Census Bureau, American Community Survey 1-year"

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
        "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
        "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
        "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
        "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
        "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
        "54": "WV", "55": "WI", "56": "WY"}


def api_keys() -> list[str]:
    """Every Census key available, in order: $CENSUS_API_KEY, then each CENSUS_API_KEY* line in the project's .env
    (one key is enough; extra CENSUS_API_KEY_<suffix> lines are tried as fallbacks), then .census_key."""
    keys = [os.environ.get("CENSUS_API_KEY", "").strip()]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip().upper().startswith("CENSUS_API_KEY"):
                keys.append(v.strip().strip('"').strip("'"))
    f = ROOT / ".census_key"
    if f.exists():
        keys.append(f.read_text().strip())
    return list(dict.fromkeys(k for k in keys if k))


_KEY: list = []


def api_key() -> str | None:
    """The first key the API accepts (checked once per run with a one-cell request); None if none works."""
    if _KEY:
        return _KEY[0]
    for k in api_keys():
        try:
            _get(f"{API.format(y=2019)}?get=NAME&for=state:06&key={k}")
            _KEY.append(k)
            return k
        except PermissionError:
            continue
    _KEY.append(None)
    return None


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "talentByState-pipeline"})
    with urllib.request.urlopen(req, timeout=300) as r:
        if "missing_key" in r.geturl() or "invalid_key" in r.geturl():
            raise PermissionError(f"Census API refused the request ({r.geturl()})")
        return r.read()


# ---------------------------------------------------------------- detailed tables

def labels(year: int, table: str) -> dict[str, str]:
    d = json.loads(_get(f"{API.format(y=year)}/groups/{table}.json"))["variables"]
    return {k[:-1]: v["label"].replace("Estimate!!", "").replace(":", "") for k, v in d.items() if k.endswith("E")}


def _tidy(df: pd.DataFrame, year: int, table: str) -> pd.DataFrame:
    """df: one row per geography with GEO_ID and {table}_{line}E / _{line}M columns."""
    df = df[df.GEO_ID.str.match(r"^(0100000US|0400000US\d\d)$")].copy()
    df["state"] = df.GEO_ID.str[-2:].map(FIPS).where(df.GEO_ID.str.startswith("04"), "US")
    df = df.dropna(subset=["state"])           # drops Puerto Rico
    est = [c for c in df if c.startswith(table) and c.endswith("E")]
    long = df.melt(id_vars="state", value_vars=est, var_name="variable", value_name="estimate")
    long["variable"] = long.variable.str[:-1]
    moe = df.melt(id_vars="state", value_vars=[c[:-1] + "M" for c in est], var_name="variable", value_name="moe")
    moe["variable"] = moe.variable.str[:-1]
    long = long.merge(moe, on=["state", "variable"])
    lab = labels(year, table)
    long["label"] = long.variable.map(lab)
    for c in ["estimate", "moe"]:
        long[c] = pd.to_numeric(long[c], errors="coerce")
    long.loc[long.moe < 0, "moe"] = np.nan    # Census annotation codes (-555555555 etc.)
    long.insert(0, "table", table)
    long.insert(0, "year", year)
    return long[["year", "state", "table", "variable", "label", "estimate", "moe"]]


def fetch_table(year: int, table: str, key: str | None) -> tuple[pd.DataFrame, str]:
    """From the API when a working key is set; otherwise (or if the API refuses the key) the keyless summary file."""
    note = ""
    if key:
        try:
            frames = []
            for geo in ["state:*", "us:1"]:
                f = RAW / "api" / f"{year}_{table}_{geo.split(':')[0]}.json"   # raw response cache (no key in it)
                if f.exists():
                    rows = json.loads(f.read_text())
                else:
                    rows = json.loads(_get(f"{API.format(y=year)}?get=group({table})&for={geo}&key={key}"))
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text(json.dumps(rows))
                frames.append(pd.DataFrame(rows[1:], columns=rows[0]))
            return _tidy(pd.concat(frames), year, table), "api"
        except PermissionError as e:           # invalid or not-yet-activated key
            note = f" (API refused the key: {'invalid key' if 'invalid' in str(e) else 'missing key'})"
    df = pd.read_csv(io.BytesIO(_get(SF.format(y=year, t=table.lower()))), sep="|", dtype=str)
    # summary-file names are B05002_E001 / B05002_M001; rename to the API's B05002_001E / B05002_001M
    df = df.rename(columns=lambda c: f"{c[:6]}_{c[-3:]}{c[7]}" if c[:6] == table else c)
    return _tidy(df, year, table), "summary file" + note


def build_tables() -> pd.DataFrame:
    key = api_key()
    frames, log = [], []
    for y in YEARS:
        for t in TABLES:
            try:
                df, how = fetch_table(y, t, key)
                frames.append(df)
                log.append((y, t, how, len(df)))
            except Exception as e:  # noqa: BLE001 -- record and keep going (e.g. no keyless file before 2021)
                log.append((y, t, f"missing: {type(e).__name__}", 0))
            print(y, t, log[-1][2], flush=True)
    long = pd.concat(frames, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT / "tables_long.csv", index=False)
    pd.DataFrame(log, columns=["year", "table", "source", "rows"]).to_csv(OUT / "files_tables.csv", index=False)
    table_measures(long).to_csv(OUT / "table_measures.csv", index=False)
    return long


def table_measures(long: pd.DataFrame) -> pd.DataFrame:
    """Shares by state-year, found by label so that renumbered lines across vintages still match.
    Country detail (B05006) is not published in 1-year data for about 20 small states."""
    # 2023+ labels write "Foreign-born"; earlier vintages "Foreign born"
    long = long.assign(label=long.label.str.replace("Foreign-born", "Foreign born", regex=False))
    def pick(t, lab):
        s = long[(long.table == t) & (long.label == lab)]
        return s.set_index(["year", "state"]).estimate

    pop = pick("B05002", "Total")
    fb = pick("B05002", "Total!!Foreign born")
    nat = pick("B05002", "Total!!Foreign born!!Naturalized U.S. citizen")
    noncit = pick("B05002", "Total!!Foreign born!!Not a U.S. citizen")
    fb_b = pick("B05006", "Total")
    india = pick("B05006", "Total!!Asia!!South Central Asia!!India")
    china = long[(long.table == "B05006") & long.label.str.contains(r"Eastern Asia!!China.*excluding Hong Kong", na=False)]
    china = china.set_index(["year", "state"]).estimate
    ed = long[long.table == "B06009"]
    adults = pick("B06009", "Total")
    ba = ed[ed.label.isin(["Total!!Bachelor's degree", "Total!!Graduate or professional degree"])].groupby(["year", "state"]).estimate.sum()
    fb_ad = pick("B06009", "Total!!Foreign born")
    fb_ba = ed[ed.label.isin(["Total!!Foreign born!!Bachelor's degree", "Total!!Foreign born!!Graduate or professional degree"])].groupby(["year", "state"]).estimate.sum()
    fb_grad = pick("B06009", "Total!!Foreign born!!Graduate or professional degree")
    grad = pick("B06009", "Total!!Graduate or professional degree")
    m = {
        "acs_fb_share": fb / pop,                       # foreign-born share of residents
        "acs_noncit_share": noncit / pop,               # noncitizen share of residents
        "acs_naturalized_share_of_fb": nat / fb,
        "acs_fb_india_share": india / fb_b,             # share of the foreign-born born in India
        "acs_fb_china_share": china / fb_b,             # ... born in China (excl. Hong Kong, Taiwan)
        "acs_ba_plus_share": ba / adults,               # bachelor's or higher, 25+
        "acs_fb_ba_plus_share": fb_ba / fb_ad,          # same, foreign-born 25+
        "acs_fb_share_of_grad": fb_grad / grad,         # foreign-born share of graduate-degree holders
    }
    out = pd.concat({k: v for k, v in m.items()}, names=["measure"]).rename("value").reset_index()
    return out[["year", "state", "measure", "value"]].dropna()


# ---------------------------------------------------------------- PUMS

STEM_MGR = {"113021", "119041", "119121"}
GROUPS = {"computer_math": "15", "engineering": "17", "science": "19"}
REP = [f"PWGTP{i}" for i in range(1, 81)]
KEEP = ["PWGTP", "AGEP", "CIT", "SCHL", "NATIVITY", "POBP", "YOEP", "SOCP", "ESR"]


def stem_group(socp: pd.Series) -> pd.Series:
    s = socp.fillna("").str.strip()
    g = pd.Series(None, index=s.index, dtype=object)
    for name, pre in GROUPS.items():
        g[s.str.startswith(pre)] = name
    g[s.isin(STEM_MGR)] = "stem_managers"
    return g


def extract_pums(year: int) -> pd.DataFrame:
    """Download one year's person file, keep employed STEM workers, save totals for all workers."""
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"pums_stem_{year}.parquet"
    if out.exists():
        return pd.read_parquet(out)
    stem, workers = [], []
    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / "pus.zip"
        print(year, "downloading", flush=True)
        req = urllib.request.Request(PUMS.format(y=year), headers={"User-Agent": "talentByState-pipeline"})
        with urllib.request.urlopen(req, timeout=600) as r, open(zpath, "wb") as f:
            while chunk := r.read(1 << 22):
                f.write(chunk)
        with zipfile.ZipFile(zpath) as z:
            for name in [n for n in z.namelist() if n.lower().endswith(".csv")]:
                with z.open(name) as fh:
                    head = pd.read_csv(z.open(name), nrows=0).columns
                    up = {c: c.upper() for c in head}          # 2014-2016 spell replicate weights pwgtp1..
                    st = "STATE" if "STATE" in up.values() else "ST"
                    want = {st, *KEEP, *REP}
                    cols = [c for c in head if up[c] in want]
                    dt = {c: str for c in cols if up[c] in (st, "SOCP", "POBP")}
                    for ch in pd.read_csv(fh, usecols=cols, dtype=dt, chunksize=500_000, low_memory=False):
                        ch = ch.rename(columns=up)
                        ch = ch[ch.ESR.isin([1, 2, 4, 5])].rename(columns={st: "fips"})
                        ch["fips"] = ch.fips.str.zfill(2)
                        workers.append(ch.groupby(["fips", "NATIVITY"]).agg(w=("PWGTP", "sum"), n=("PWGTP", "size")).reset_index())
                        ch["group"] = stem_group(ch.SOCP)
                        stem.append(ch[ch.group.notna()])
                print(year, name, "read", flush=True)
    df = pd.concat(stem, ignore_index=True)
    df["state"] = df.pop("fips").map(FIPS)
    df.insert(0, "year", year)
    df.to_parquet(out, index=False)
    w = pd.concat(workers).groupby(["fips", "NATIVITY"]).sum().reset_index()
    w["state"] = w.pop("fips").map(FIPS)
    w.insert(0, "year", year)
    wf = RAW / "pums_workers.csv"
    old = pd.read_csv(wf) if wf.exists() else pd.DataFrame()
    pd.concat([old[old.year != year] if len(old) else old, w]).to_csv(wf, index=False)
    return df


WTS = ["PWGTP"] + REP


def _sums(df: pd.DataFrame, x: pd.Series) -> pd.DataFrame:
    """Weighted sums of x (full + 80 replicate weights) and unweighted n by year x state x group, with the
    'all' group and the US rolled up from the same sums."""
    W = pd.DataFrame(df[WTS].to_numpy(dtype=float) * x.to_numpy(dtype=float)[:, None], columns=WTS, index=df.index)
    W["n"] = x.to_numpy() != 0
    S = W.join(df[["year", "state", "group"]]).groupby(["year", "state", "group"]).sum()
    S = pd.concat([S, S.groupby(["year", "group"]).sum().assign(state="US").set_index("state", append=True)
                   .reorder_levels(["year", "state", "group"])])
    return pd.concat([S, S.groupby(["year", "state"]).sum().assign(group="all").set_index("group", append=True)])


def _se(T: pd.DataFrame) -> pd.Series:
    return np.sqrt(4 / 80 * (T[REP].sub(T.PWGTP, axis=0) ** 2).sum(axis=1))


def _count(df, x):
    S = _sums(df, x)
    return pd.DataFrame({"value": S.PWGTP, "moe90": 1.645 * _se(S), "n": S.n})


def _ratio(df, num, den):
    """Weighted share num/den with a replicate-weight 90% MOE; n is the unweighted count of den records."""
    N, D = _sums(df, num), _sums(df, den)
    R = N[WTS] / D[WTS].replace(0, np.nan)
    return pd.DataFrame({"value": R.PWGTP, "moe90": 1.645 * _se(R), "n": D.n})


PUMS_MEASURES = {  # name: (title, how)
    "stem_workers": "Workers in STEM occupations",
    "stem_fb_share": "Foreign-born share of STEM workers",
    "stem_naturalized_share": "Naturalized-citizen share of STEM workers",
    "stem_noncit_share": "Noncitizen share of STEM workers (green-card holders and temporary visas)",
    "stem_fb_recent_share": "Share of STEM workers who are foreign-born and arrived in the last 10 years",
    "stem_grad_fb_share": "Foreign-born share of STEM workers with a graduate degree",
    "stem_phd_fb_share": "Foreign-born share of STEM workers with a doctorate",
    "stem_grad_share_fb": "Share of foreign-born STEM workers with a graduate degree",
    "stem_grad_share_native": "Share of US-born STEM workers with a graduate degree",
    "stem_fb_india_share": "Share of foreign-born STEM workers born in India",
    "stem_fb_china_share": "Share of foreign-born STEM workers born in China (excl. Hong Kong, Taiwan)",
    "stem_share_of_workers": "STEM workers as a share of all workers",
}


def pums_measures(df: pd.DataFrame) -> pd.DataFrame:
    for c in ["AGEP", "CIT", "SCHL", "NATIVITY", "YOEP", "ESR"]:   # some vintages store blanks as text
        df[c] = pd.to_numeric(df[c], errors="coerce")
    one = pd.Series(1, index=df.index)
    fb = (df.NATIVITY == 2).astype(int)
    grad = df.SCHL.ge(22).astype(int)              # master's, professional, doctorate
    phd = df.SCHL.eq(24).astype(int)
    recent = (fb.astype(bool) & (df.year - df.YOEP < 10)).astype(int)
    pob = df.POBP.astype(str).str.lstrip("0")
    parts = {
        "stem_workers": _count(df, one),
        "stem_fb_share": _ratio(df, fb, one),
        "stem_naturalized_share": _ratio(df, (df.CIT == 4).astype(int), one),
        "stem_noncit_share": _ratio(df, (df.CIT == 5).astype(int), one),
        "stem_fb_recent_share": _ratio(df, recent, one),
        "stem_grad_fb_share": _ratio(df, fb * grad, grad),
        "stem_phd_fb_share": _ratio(df, fb * phd, phd),
        "stem_grad_share_fb": _ratio(df, fb * grad, fb),
        "stem_grad_share_native": _ratio(df, (1 - fb) * grad, 1 - fb),
        "stem_fb_india_share": _ratio(df, fb * pob.eq("210"), fb),
        "stem_fb_china_share": _ratio(df, fb * pob.eq("207"), fb),
    }
    out = pd.concat(parts, names=["measure"]).reset_index()
    wf = RAW / "pums_workers.csv"
    if wf.exists():
        w = pd.read_csv(wf)
        w = pd.concat([w, w.assign(state="US")]).groupby(["year", "state"]).w.sum()
        sw = out[(out.measure == "stem_workers") & (out.group == "all")].set_index(["year", "state"]).value
        share = (sw / w).dropna().rename("value").reset_index().assign(measure="stem_share_of_workers", group="all")
        out = pd.concat([out, share], ignore_index=True)
    return out[["year", "state", "group", "measure", "value", "moe90", "n"]].sort_values(["measure", "group", "state", "year"])


def build_pums(years: list[int]) -> pd.DataFrame:
    for y in years:
        extract_pums(y)
    df = pd.concat([pd.read_parquet(p) for p in sorted(RAW.glob("pums_stem_*.parquet"))], ignore_index=True)
    m = pums_measures(df)
    OUT.mkdir(parents=True, exist_ok=True)
    m.to_csv(OUT / "pums_stem.csv", index=False)
    a = m[m.group == "all"]
    wide = a.pivot_table(index=["year", "state"], columns="measure", values="value").reset_index()
    nn = a[a.measure == "stem_workers"].set_index(["year", "state"]).n.rename("n_stem_records")
    nf = a[a.measure == "stem_grad_share_fb"].set_index(["year", "state"]).n.rename("n_fb_stem_records")
    wide = wide.join(nn, on=["year", "state"]).join(nf, on=["year", "state"])
    wide.to_csv(OUT / "pums_stem_wide.csv", index=False)
    return m


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "tables":
        build_tables()
    if not args or args[0] == "pums":
        build_pums([int(a) for a in args[1:]] or PUMS_YEARS)
