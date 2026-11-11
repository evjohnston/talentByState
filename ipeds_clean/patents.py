"""USPTO granted patents by state of the assignee, from the PatentsView annualized files.

    python -m ipeds_clean.patents     # -> data/patents/*.csv

Source: PatentsView (USPTO) annualized patent data, one zip per grant year in sources/uspto_patents/ ({year}.zip, plus
year_missing.zip for patents without a grant year), built from the 12/31/2025 PatentsView release; variable
definitions in sources/uspto_patents/data_dictionary_PVANNUAL.xlsx. Rows are patent x assignee; the location fields
are the disambiguated assignee's location, so a state's count is patents owned by organizations (or people)
located in the state, not patents by inventors living there.

Counting:
* patents        whole count: a patent with assignees in two states counts once in each
* patents_frac   fractional count: each patent split evenly across its assignees (US states sum to the
                 US-assignee total)
* US row         patents with at least one US assignee; world totals are in files.csv
Patents with no assignee (about 5%, mostly individual inventors who kept their patent) have no location and
are left out, as are patents without a grant year (year_missing.csv). Technology fields are the WIPO
35-field classification of the patent's first listed field.

Outputs (data/patents/):
  patents_state.csv        grant_year, state, measure, value
  patents_state_wide.csv   one row per state-year
  patents_state_field.csv  grant_year, state, wipo_sector, wipo_field, patents, patents_frac
  files.csv                rows, patents and US-assignee patents per file; grant years with no file
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "uspto_patents"
OUT = ROOT / "data" / "patents"
SOURCE = "Data from USPTO, PatentsView"
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
             "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
COLS = ["patent_number", "grant_year", "assignee", "assignee_ind", "country", "state", "d_assignee",
        "first_wipo_field_title", "first_wipo_sector_title", "team_size", "men_inventors", "women_inventors"]
# WIPO fields grouped for the profiles (the full field detail is in patents_state_field.csv)
GROUPS = {
    "digital": ["Computer technology", "Digital communication", "Telecommunications", "Basic communication processes",
                "IT methods for management", "Audio-visual technology"],
    "semiconductors": ["Semiconductors", "Micro-structural and nano-technology"],
    "life_sciences": ["Biotechnology", "Pharmaceuticals", "Medical technology", "Analysis of biological materials",
                      "Organic fine chemistry"],
    "energy_environment": ["Electrical machinery, apparatus, energy", "Environmental technology",
                           "Engines, pumps, turbines"],
}


def read(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        d = pd.read_csv(z.open(z.namelist()[0]), usecols=COLS, dtype=str, low_memory=False)
    for c in ["team_size", "men_inventors", "women_inventors", "assignee_ind", "d_assignee"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["n_assignees"] = d.groupby("patent_number").patent_number.transform("size")
    return d


def year_measures(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    us = d[(d.country == "US") & d.state.isin(STATES)].copy()
    us["w"] = 1 / us.n_assignees
    us_all = d[d.country == "US"].assign(state="US", w=lambda x: 1 / x.n_assignees)
    rows = pd.concat([us, us_all])
    # one row per patent x state (whole counts); weights add up when a patent has two assignees in the state
    ps = rows.groupby(["state", "patent_number"]).agg(
        w=("w", "sum"), field=("first_wipo_field_title", "first"), sector=("first_wipo_sector_title", "first"),
        team=("team_size", "first"), men=("men_inventors", "first"), women=("women_inventors", "first"),
        ind=("assignee_ind", "max")).reset_index()
    g = ps.groupby("state")
    m = pd.DataFrame({"patents": g.size(), "patents_frac": g.w.sum(),
                      "assignees": rows.groupby("state").assignee.nunique(),
                      "mean_team_size": g.team.mean(),
                      "share_with_woman_inventor": g.women.apply(lambda s: (s > 0).mean()),
                      "women_share_of_inventors": g.women.sum() / (g.men.sum() + g.women.sum()),
                      "share_individual_assignee": g.ind.mean()})
    for name, fields in GROUPS.items():
        m[f"share_{name}"] = ps[ps.field.isin(fields)].groupby("state").size().reindex(m.index).fillna(0) / m.patents
    m["share_of_us_frac"] = m.patents_frac / m.loc["US", "patents_frac"]
    fld = ps.groupby(["state", "sector", "field"]).agg(patents=("w", "size"), patents_frac=("w", "sum")).reset_index()
    return m.reset_index(), fld


def build() -> None:
    files, wide, fields = [], [], []
    for path in sorted(SRC.glob("*.zip")):
        d = read(path)
        rec = {"file": path.name, "rows": len(d), "patents": d.patent_number.nunique(),
               "patents_us_assignee": d[d.country == "US"].patent_number.nunique(),
               "patents_no_assignee": d[d.d_assignee == 0].patent_number.nunique()}
        files.append(rec)
        if not path.stem.isdigit():
            continue
        y = int(path.stem)
        m, f = year_measures(d)
        wide.append(m.assign(grant_year=y))
        fields.append(f.assign(grant_year=y))
        print(y, rec["patents"], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    fl = pd.DataFrame(files)
    years = [int(f[:-4]) for f in fl.file if f[:-4].isdigit()]
    missing = [y for y in range(min(years), max(years) + 1) if y not in years]
    fl = pd.concat([fl, pd.DataFrame({"file": [f"{y}.zip (not downloaded)" for y in missing]})])
    fl.to_csv(OUT / "files.csv", index=False)
    w = pd.concat(wide)
    w = w[["grant_year", "state"] + [c for c in w if c not in ("grant_year", "state")]]
    w.to_csv(OUT / "patents_state_wide.csv", index=False)
    w.melt(id_vars=["grant_year", "state"], var_name="measure").dropna().to_csv(OUT / "patents_state.csv", index=False)
    f = pd.concat(fields)
    f[["grant_year", "state", "sector", "field", "patents", "patents_frac"]].rename(
        columns={"sector": "wipo_sector", "field": "wipo_field"}).to_csv(OUT / "patents_state_field.csv", index=False)
    print("grant years with no file:", missing)


if __name__ == "__main__":
    build()
