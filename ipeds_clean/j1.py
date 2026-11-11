"""State Department BridgeUSA (J-1 Exchange Visitor Program): participants by site-of-activity state.

    python -m ipeds_clean.j1      # -> data/j1/*.csv

Source: sources/state_bridgeusa_j1/J1-data.xlsx, a U.S. Department of State (BridgeUSA) workbook of J-1
exchange visitor counts by Program Begin Date Year, 2015-2025. Three pivot sheets, each with a two-row header
(a "Program Begin Date Year" banner, then the years and "Grand Total"):

* "Category Counts"          15 J-1 categories x year (national only)
* "Country of Citizenship"   ~240 countries/areas x year (national only)
* "Site of Activity State"   primary site of activity: 50 states + DC, territories (AS, FM, GU, MH, MP, PR,
                             PW, UM, VI) and "N/A (Seeking, exempt, on travel)" x year. No category split.

A participant is counted in the year their program began (a new J-1 program record), not as a stock of people
present; a long program (professor, research scholar, college student) appears once, in its start year.
The state sheet has no category dimension, so state counts are dominated by Summer Work Travel, camp
counselors and au pairs (about half the national total); the "talent" categories (students, scholars,
professors, interns, trainees, physicians, teachers, specialists) exist only nationally. Blank cells are 0.
2020-2021 collapse with COVID travel limits. The workbook does not say when it was extracted, so 2025 may be
incomplete (it is 9% below 2024).

Outputs (data/j1/):
  j1_state.csv         year, state, geo, measure, value  (participants, share_of_us; "US" = Grand Total,
                       which includes territories and "UNASSIGNED" = N/A: seeking, exempt, on travel)
  j1_state_wide.csv    one row per state (incl. US, territories, UNASSIGNED), one participants column per year
  j1_category_us.csv   year, category, participants, share_of_total, talent (1 = a category with a degree,
                       research, teaching or work-training purpose)
  j1_country_us.csv    year, country, participants, share_of_total, rank
  files.csv            sheets read, rows, years
  checks.csv           sheet row sums vs each sheet's Grand Total, and across sheets
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "state_bridgeusa_j1" / "J1-data.xlsx"
OUT = ROOT / "data" / "j1"
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
             "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
TERR = {"PR", "GU", "VI", "MP", "AS", "FM", "MH", "PW", "UM"}
TALENT = {"ALIEN PHYSICIAN", "INTERN", "PROFESSOR", "RESEARCH SCHOLAR", "SHORT-TERM SCHOLAR", "SPECIALIST",
          "STUDENT COLLEGE UNIVERSITY", "TEACHER", "TRAINEE"}


def sheet(name: str) -> pd.DataFrame:
    """A pivot sheet as long (key, year, value) plus its Grand Total row/column."""
    raw = pd.read_excel(SRC, sheet_name=name, engine="calamine", header=None)
    hdr = raw.iloc[1].tolist()
    d = raw.iloc[2:].copy()
    d.columns = ["key"] + [int(h) if isinstance(h, (int, float)) else str(h).strip() for h in hdr[1:]]
    d["key"] = d["key"].astype(str).str.strip()
    years = [c for c in d.columns if isinstance(c, int)]
    d[years + ["Grand Total"]] = d[years + ["Grand Total"]].apply(pd.to_numeric, errors="coerce").fillna(0)
    return d, years


def build() -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    files, checks, tables = [], [], {}
    for name in ["Category Counts", "Country of Citizenship", "Site of Activity State"]:
        d, years = sheet(name)
        total = d[d.key == "Grand Total"].iloc[0]
        body = d[d.key != "Grand Total"]
        tables[name] = (body, total, years)
        files.append({"file": SRC.name, "sheet": name, "rows": len(body), "years": f"{years[0]}-{years[-1]}",
                      "used": "yes"})
        for y in years + ["Grand Total"]:
            checks.append({"check": f"{name}: rows sum to Grand Total", "year": y, "expected": total[y],
                           "actual": body[y].sum(), "diff": body[y].sum() - total[y]})
    cat, cat_tot, years = tables["Category Counts"]
    st, st_tot, _ = tables["Site of Activity State"]
    co, co_tot, _ = tables["Country of Citizenship"]
    for y in years:
        checks.append({"check": "State sheet Grand Total = Category Grand Total", "year": y,
                       "expected": cat_tot[y], "actual": st_tot[y], "diff": st_tot[y] - cat_tot[y]})
        checks.append({"check": "Country sheet Grand Total = Category Grand Total", "year": y,
                       "expected": cat_tot[y], "actual": co_tot[y], "diff": co_tot[y] - cat_tot[y]})

    st = st.assign(state=st.key.where(st.key.isin(STATES | TERR), "UNASSIGNED"))
    long = st.melt(id_vars="state", value_vars=years, var_name="year", value_name="participants")
    us = pd.DataFrame({"state": "US", "year": years, "participants": [cat_tot[y] for y in years]})
    long = pd.concat([long, us], ignore_index=True)
    long["share_of_us"] = long.participants / long.year.map(dict(zip(us.year, us.participants)))
    long.insert(2, "geo", long.state.map(lambda s: "national" if s == "US" else "state" if s in STATES
                                          else "territory" if s in TERR else "unassigned"))
    long = long.sort_values(["year", "state"])
    long.melt(id_vars=["year", "state", "geo"], var_name="measure").to_csv(OUT / "j1_state.csv", index=False)
    w = long.pivot_table(index=["state", "geo"], columns="year", values="participants").reset_index()
    w.columns = [f"participants_{c}" if isinstance(c, int) else c for c in w.columns]
    w.to_csv(OUT / "j1_state_wide.csv", index=False)

    c = cat.melt(id_vars="key", value_vars=years, var_name="year", value_name="participants") \
        .rename(columns={"key": "category"})
    c["share_of_total"] = c.participants / c.year.map(lambda y: cat_tot[y])
    c["talent"] = c.category.isin(TALENT).astype(int)
    c.sort_values(["year", "participants"], ascending=[True, False]).to_csv(OUT / "j1_category_us.csv", index=False)
    k = co.melt(id_vars="key", value_vars=years, var_name="year", value_name="participants") \
        .rename(columns={"key": "country"})
    k["share_of_total"] = k.participants / k.year.map(lambda y: co_tot[y])
    k["rank"] = k.groupby("year").participants.rank(ascending=False, method="min").astype(int)
    k.sort_values(["year", "rank"]).to_csv(OUT / "j1_country_us.csv", index=False)
    pd.DataFrame(files).to_csv(OUT / "files.csv", index=False)
    ch = pd.DataFrame(checks)
    ch.to_csv(OUT / "checks.csv", index=False)
    print(ch[ch["diff"] != 0].to_string(index=False))
    return long


if __name__ == "__main__":
    build()
