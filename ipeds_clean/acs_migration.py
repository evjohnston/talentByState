"""Migration of college graduates between states: ACS geographical mobility by educational attainment.

    python -m ipeds_clean.acs_migration       # -> data/acs_migration/*.csv

Sources (U.S. Census Bureau, American Community Survey; population 25 and over):
* B07009  mobility in the past year by educational attainment, for the CURRENT residence: who moved INTO the
          state from another state, and from abroad.
* B07409  the same, for the residence ONE YEAR AGO: who moved OUT of the state to another state.
The tables were downloaded from data.census.gov as CSVs into sources/census_acs_migration/ (1-year 2010-2025,
5-year 2010-2024 for B07009; 2018 on for B07409). The 1-year B07409 for 2010-2017 is not in the download and is
fetched from the Census API (key from .env; see acs.py) and cached in cache/acs_migration/. There are no 2020
1-year estimates.

Measures (state x year; 1-year estimates, with the 5-year series kept separately as a smoother check):
  in_<ed>, out_<ed>, net_<ed>          movers from / to other states, and the difference, for ed = ba (bachelor's),
                                        grad (graduate or professional), ba_plus (both)
  abroad_<ed>                           arrivals from abroad (B07009 only; there is no outflow abroad in the ACS)
  net_ba_plus_per_1000                  net domestic migration of bachelor's-or-higher adults per 1,000 such residents
  in_rate_ba_plus, out_rate_ba_plus     movers in / out as a share of bachelor's-plus residents (%)
Margins of error are kept in migration_long.csv (90%). Net flows of small states are often within the margin.

Outputs (data/acs_migration/):
  migration_long.csv    year, survey (1y|5y), table, state, line, estimate, moe, source
  migration_state_wide.csv  the measures above, one row per state-year (1-year)
  migration_state_5y.csv    the same from the 5-year tables (year = last year of the period)
  files.csv             every source file, its table, survey, year and whether it was used
  checks.csv            states' summed in- and out-flows by year (equal: each mover leaves one state, enters another)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .acs import API, FIPS, _get, api_key, labels
from .config import CACHE, DATA, SOURCES

SRC = SOURCES / "census_acs_migration"
OUT = DATA / "acs_migration"
CACHE_DIR = CACHE / "acs_migration"
SOURCE = "Data from U.S. Census Bureau, American Community Survey"
NAME2ST = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
           "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
           "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
           "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
           "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
           "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
           "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
           "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
           "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "United States": "US", "Puerto Rico": "PR"}
ED = {"Bachelor's degree": "ba", "Graduate or professional degree": "grad"}
FILE_RE = re.compile(r"ACSDT(?P<s>[15])Y(?P<y>\d{4})\.(?P<t>B07[04]09)")


def _num(x) -> float | None:
    s = str(x).replace(",", "").replace("±", "").strip()
    try:
        return float(s)
    except ValueError:
        return None                    # "*****", "N", "-" (Census annotation codes)


def _paths(raw: list[str]) -> list[str]:
    """Indented row labels ('Total:', '    Same house:', '        Bachelor's degree') -> 'Same house: > Bachelor's degree'."""
    out, stack = [], []
    for lab in raw:
        depth = (len(lab) - len(lab.lstrip("\xa0 "))) // 4
        name = lab.strip()
        stack = stack[:depth] + [name]
        out.append(" > ".join(stack[1:]) if depth else name)
    return out


def read_csv(path: Path) -> pd.DataFrame:
    m = FILE_RE.match(path.name)
    d = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    d["line"] = _paths(d.iloc[:, 0].fillna("").tolist())
    rows = []
    for col in d.columns[1:-1]:
        name, _, kind = col.partition("!!")
        st = NAME2ST.get(name)
        if not st or kind not in ("Estimate", "Margin of Error"):
            continue
        for line, v in zip(d.line, d[col]):
            rows.append((st, line, kind, _num(v)))
    x = pd.DataFrame(rows, columns=["state", "line", "kind", "v"]).pivot_table(index=["state", "line"], columns="kind", values="v", aggfunc="first")
    x = x.rename(columns={"Estimate": "estimate", "Margin of Error": "moe"}).reset_index()
    x.insert(0, "table", m["t"])
    x.insert(0, "survey", f"{m['s']}y")
    x.insert(0, "year", int(m["y"]))
    x["source"] = path.name
    return x


def fetch_api(year: int, table: str) -> pd.DataFrame:
    """1-year table from the Census API, lines labelled like the data.census.gov CSVs."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / f"{table}_{year}_1y.json"
    if not f.exists():
        rows = []
        for geo in ("state:*", "us:1"):
            rows += json.loads(_get(f"{API.format(y=year)}?get=group({table})&for={geo}&key={api_key()}"))[(0 if not rows else 1):]
        f.write_text(json.dumps(rows))
    rows = json.loads(f.read_text())
    d = pd.DataFrame(rows[1:], columns=rows[0])
    d["state"] = d.GEO_ID.str[-2:].map(FIPS).where(d.GEO_ID.str.startswith("04"), "US")
    d = d.dropna(subset=["state"])
    lab = labels(year, table)                     # 'Total living in area 1 year ago!!Moved to different state!!Bachelor's degree'
    out = []
    for var, label in lab.items():
        if var + "E" not in d:
            continue
        parts = label.split("!!")
        kids = parts[1:]                          # CSV style: every level but the last ends in ":"
        line = " > ".join(p.strip() + (":" if i < len(kids) - 1 else "") for i, p in enumerate(kids)) if kids else parts[0] + ":"
        out.append(pd.DataFrame({"state": d.state, "line": line, "estimate": pd.to_numeric(d[var + "E"], errors="coerce"),
                                 "moe": pd.to_numeric(d.get(var + "M"), errors="coerce")}))
    x = pd.concat(out)
    x.loc[x.moe < 0, "moe"] = None
    x.insert(0, "table", table)
    x.insert(0, "survey", "1y")
    x.insert(0, "year", year)
    x["source"] = "Census API"
    return x


def measures(long: pd.DataFrame) -> pd.DataFrame:
    """State x year measures from one survey's long rows."""
    def pick(table, prefix, ed):
        s = long[(long.table == table) & (long.line == f"{prefix} > {ed}")]
        return s.set_index(["year", "state"]).estimate
    tot = lambda table, ed: pick(table, {"B07009": "Total:", "B07409": "Total living in area 1 year ago:"}[table].rstrip(":"), ed) \
        if False else long[(long.table == table) & (long.line == ed)].set_index(["year", "state"]).estimate
    m = {}
    for lab, ed in ED.items():
        m[f"in_{ed}"] = pick("B07009", "Moved from different state:", lab)
        m[f"abroad_{ed}"] = pick("B07009", "Moved from abroad:", lab)
        m[f"out_{ed}"] = pick("B07409", "Moved to different state:", lab)
        m[f"res_{ed}"] = tot("B07009", lab)
    w = pd.DataFrame(m)
    for k in ("in", "abroad", "out", "res"):
        w[f"{k}_ba_plus"] = w[f"{k}_ba"] + w[f"{k}_grad"]
    for ed in ("ba", "grad", "ba_plus"):
        w[f"net_{ed}"] = w[f"in_{ed}"] - w[f"out_{ed}"]
    w["net_ba_plus_per_1000"] = 1000 * w.net_ba_plus / w.res_ba_plus
    w["in_rate_ba_plus"] = 100 * w.in_ba_plus / w.res_ba_plus
    w["out_rate_ba_plus"] = 100 * w.out_ba_plus / w.res_ba_plus
    w.loc[w.index.get_level_values("state") == "US", [c for c in w if c.startswith(("in_", "out_", "net_"))]] = None  # no interstate flow for the nation
    return w.reset_index()


def build() -> pd.DataFrame:
    files, frames = [], []
    for p in sorted(SRC.glob("*.csv")):
        m = FILE_RE.match(p.name)
        if not m:
            files.append({"file": p.name, "used": "no", "why": "not a B07009/B07409 export"})
            continue
        frames.append(read_csv(p))
        files.append({"file": p.name, "table": m["t"], "survey": f"{m['s']}y", "year": int(m["y"]), "used": "yes", "why": ""})
    long = pd.concat(frames, ignore_index=True)
    have = set(zip(long.survey, long.table, long.year))
    for y in range(2010, 2018):
        if ("1y", "B07409", y) not in have:
            frames.append(fetch_api(y, "B07409"))
            files.append({"file": f"Census API B07409 {y} 1-year", "table": "B07409", "survey": "1y", "year": y, "used": "yes",
                          "why": "not in the download; fetched from the API"})
    long = pd.concat(frames, ignore_index=True)
    long["line"] = long.line.str.replace(r"\s+", " ", regex=True).str.replace(r":(?= >)", ":", regex=True)
    OUT.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT / "migration_long.csv", index=False)
    pd.DataFrame(files).to_csv(OUT / "files.csv", index=False)
    w1 = measures(long[long.survey == "1y"])
    w5 = measures(long[long.survey == "5y"])
    w1.to_csv(OUT / "migration_state_wide.csv", index=False)
    # check: every interstate mover leaves one state and enters another, so states' in- and out-flows match
    ck = w1[w1.state != "US"].groupby("year")[["in_ba_plus", "out_ba_plus", "net_ba_plus"]].sum().reset_index()
    ck.to_csv(OUT / "checks.csv", index=False)
    w5.to_csv(OUT / "migration_state_5y.csv", index=False)
    return w1


if __name__ == "__main__":
    w = build()
    x = w[w.year == w.year.max()].set_index("state")
    print(x.loc[["CA", "TX", "NY", "FL", "WA", "WV"], ["in_ba_plus", "out_ba_plus", "net_ba_plus", "net_ba_plus_per_1000", "abroad_ba_plus"]].round(1))
    print(w.groupby("year").net_ba_plus.apply(lambda s: s.dropna().sum()).round(0).to_dict(), "(states' net should sum to ~0)")
