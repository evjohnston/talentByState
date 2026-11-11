"""College Scorecard (U.S. Department of Education): earnings, debt and completion, rolled up to states.

    python -m ipeds_clean.scorecard            # -> data/scorecard/*.csv (latest release)
    python -m ipeds_clean.scorecard history    # -> institutions_history.csv, scorecard_state_years.csv, cohort_map.csv
    python -m ipeds_clean.scorecard --refresh  # refetch from the API

Source: the College Scorecard API (api.data.gov/ed/collegescorecard/v1/schools), key COLLEGE_SCORECARD_API_KEY in
the project's .env. Variable names and cohort definitions come from reference/college_scorecard/
CollegeScorecardDataDictionary.xlsx (sheets Institution_Data_Dictionary, FieldOfStudy_Data_Dictionary,
Most_Recent_Inst_Cohort_Map). The "latest" (most recent) data, where each measure's cohort differs:
  earnings 10 years after entry   Treasury, AY2011-12 + AY2012-13 entrants, measured CY2022-23, 2024 dollars
  earnings 1 year after completion  AY2020-21 + AY2021-22 completers, measured CY2022-23, 2024 dollars
  median debt of completers       NSLDS FY2024-25 pooled
  completion rate (4-year, 150%)  fall 2019 entering cohort
  program earnings (field of study) 1 and 5 years after completion, by 4-digit CIP and credential level
Earnings cover federal-aid recipients who are working and not enrolled; they are not all graduates.

History: the API also serves fields keyed by data-file year (<year>.earnings..., MERGED<year>_<year+1>_PP), for
earnings 10 years after entry (2007, 2009, 2011-14, 2020, 2022 files; e.g. 2022 = AY2011-13 entrants measured
CY2022-23, converted to 2024 dollars with the CPI-U from each file's dollar year), completer debt (1997-2024; 2024 =
NSLDS FY2024-25), 4-year completion (1997-2025; year Y = fall Y-6 entrants), Pell share (2008-2025; Y = AY Y-1 to Y)
and undergraduate enrollment (1996-2024 except 2000; Y = fall Y). cohort_map.csv has the dictionary text per year
(Institution_Cohort_Map). The API serves only institutions in the current file, so closed institutions are missing
from the early years. The same weights as the latest roll-ups (enrollment weights fall back to the institution's
previous year when the file has no enrollment, as in 2000 and 2025). About 190 requests of 60 fields, cached.

State roll-ups (institutions located in the state; Title IV institutions only):
  inst_earn10_median        median of institution medians, weighted by the number of students measured
  inst_earn1_median         same, earnings 1 year after completion
  inst_debt_median          median completer debt, weighted by undergraduate enrollment
  inst_completion_4yr       4-year-institution completion rate, weighted by undergraduate enrollment
  inst_pell_share           Pell share of undergraduates, weighted by enrollment
  prog_earn1_<lvl>_<grp>    program median earnings 1 year after completion, weighted by graduates measured, for
  prog_earn5_<lvl>_<grp>    lvl = bach, master, doc (research/professional, credential 6-7) and grp = stem, nonstem, all
  prog_stem_premium1_bach   STEM minus non-STEM bachelor's earnings, 1 year after completion
Weighted medians of medians are approximations of the state median, the usual practice with Scorecard data.
STEM = 2-digit CIP 03, 04, 11, 14, 15, 26, 27, 40 (the project's definition).

Outputs (data/scorecard/):
  institutions.csv        one row per institution: unitid, name, state, sector and the latest measures
  programs.csv            one row per institution x 4-digit CIP x credential with earnings and counts
  scorecard_state_wide.csv  the state roll-ups above (state, measure columns; US = all institutions)
  scorecard_state.csv     long form
  checks.csv              coverage: institutions and graduates measured per state
  institutions_history.csv  unitid x year: earn10 (file dollars), earn10_2024, earn10_n, debt, c150_4, pell, ugds
  scorecard_state_years.csv year x state: the inst_* roll-ups above plus inst_ugds (sum), with institution counts
  cohort_map.csv          year x measure: what each year's value measures (from the data dictionary)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from .config import CACHE, DATA, ROOT

OUT = DATA / "scorecard"
CACHE_DIR = CACHE / "scorecard"
URL = "https://api.data.gov/ed/collegescorecard/v1/schools"
SOURCE = "Data from U.S. Department of Education, College Scorecard"
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
             "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
STEM2 = {"03", "04", "11", "14", "15", "26", "27", "40"}
LEVELS = {3: "bach", 5: "master", 6: "doc", 7: "doc"}          # credential levels: 3 bachelor's, 5 master's, 6 doctoral, 7 first-professional
INST_FIELDS = {
    "id": "unitid", "school.name": "name", "school.state": "state", "school.ownership": "control",
    "school.degrees_awarded.predominant": "preddeg", "school.degrees_awarded.highest": "highdeg",
    "latest.student.size": "ugds", "latest.student.grad_students": "grads",
    "latest.earnings.10_yrs_after_entry.median": "earn10", "latest.earnings.10_yrs_after_entry.working_not_enrolled.overall": "earn10_n",
    "latest.earnings.6_yrs_after_entry.median": "earn6",
    "latest.earnings.1_yr_after_completion.median": "earn1", "latest.earnings.4_yrs_after_completion.median": "earn4",
    "latest.aid.median_debt.completers.overall": "debt", "latest.aid.pell_grant_rate": "pell",
    "latest.completion.completion_rate_4yr_150nt": "c150_4", "latest.completion.completion_rate_less_than_4yr_150nt": "c150_l4",
    "latest.student.demographics.race_ethnicity.non_resident_alien": "ug_nonresident"}
PROG = "latest.programs.cip_4_digit"
PROG_FIELDS = ["code", "credential.level", "counts.ipeds_awards2", "earnings.1_yr.overall_median_earnings",
               "earnings.1_yr.working_not_enrolled.overall_count", "earnings.5_yr.overall_median_earnings",
               "earnings.5_yr.working_not_enrolled.overall_count"]


def key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        k, _, v = line.partition("=")
        if k.strip() == "COLLEGE_SCORECARD_API_KEY":
            return v.strip().strip('"').strip("'")
    raise SystemExit("COLLEGE_SCORECARD_API_KEY is not set in .env")


def pages(kind: str, fields: list[str], refresh: bool = False) -> list[dict]:
    """Every school, 100 per page, cached as JSON in cache/scorecard/<kind>_<page>.json."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out, page, total, k = [], 0, None, None
    while total is None or page * 100 < total:
        f = CACHE_DIR / f"{kind}_{page:03d}.json"
        if f.exists() and not refresh:
            d = json.loads(f.read_text())
        else:
            k = k or key()
            q = urllib.parse.urlencode({"fields": ",".join(fields), "per_page": 100, "page": page, "api_key": k})
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "talentByState-pipeline"}), timeout=180) as r:
                        d = json.loads(r.read())
                    break
                except Exception:  # noqa: BLE001 -- rate limits and timeouts: back off
                    if attempt == 4:
                        raise
                    time.sleep(10 * (attempt + 1))
            f.write_text(json.dumps(d))
            time.sleep(0.3)
        total = d["metadata"]["total"]
        out += d["results"]
        page += 1
    return out


def wmedian(v: pd.Series, w: pd.Series) -> float:
    """Weighted median (weights = graduates or students measured)."""
    m = v.notna() & w.notna() & (w > 0)
    if not m.any():
        return np.nan
    v, w = v[m].to_numpy(float), w[m].to_numpy(float)
    o = np.argsort(v)
    c = np.cumsum(w[o])
    return float(v[o][np.searchsorted(c, c[-1] / 2)])


def wmean(v: pd.Series, w: pd.Series) -> float:
    m = v.notna() & w.notna() & (w > 0)
    return float((v[m] * w[m]).sum() / w[m].sum()) if m.any() else np.nan


# ---------------------------------------------------------------- history (year-keyed fields)
# The API keys each value by the year of the merged data file it comes from (<year> = MERGED<year>_<year+1>_PP.csv),
# not by cohort; what each file's value measures is in the dictionary's Institution_Cohort_Map sheet.
HIST_YEARS = range(1996, 2026)
HIST_FIELDS = {"earnings.10_yrs_after_entry.median": "earn10",
               "earnings.10_yrs_after_entry.working_not_enrolled.overall": "earn10_n",
               "aid.median_debt.completers.overall": "debt", "completion.completion_rate_4yr_150nt": "c150_4",
               "aid.pell_grant_rate": "pell", "student.size": "ugds"}
DICT_VARS = {"earn10": "MD_EARN_WNE_P10", "debt": "GRAD_DEBT_MDN", "c150_4": "C150_4", "pell": "PCTPELL", "ugds": "UGDS"}


def cohort_map() -> pd.DataFrame:
    """year (file start year) x measure -> the dictionary's cohort/measure text."""
    c = pd.read_excel(ROOT / "reference" / "college_scorecard" / "CollegeScorecardDataDictionary.xlsx",
                      sheet_name="Institution_Cohort_Map", engine="openpyxl").set_index("variable")
    rows = [{"year": int(col[6:10]), "measure": m, "cohort": c.at[v, col]}
            for m, v in DICT_VARS.items() for col in c.columns if pd.notna(c.at[v, col])]
    return pd.DataFrame(rows)


def history(refresh: bool = False) -> pd.DataFrame:
    """Institution x year (unitid, state, year, earn10, earn10_n, debt, c150_4, pell, ugds), every year with a value.
    Ten years of fields per request (60 fields), 100 schools per page: about 190 requests, cached as hist<y0>_<page>.json."""
    frames = []
    for y0 in range(HIST_YEARS[0], HIST_YEARS[-1] + 1, 10):
        ys = [y for y in HIST_YEARS if y0 <= y < y0 + 10]
        raw = pages(f"hist{y0}", ["id", "school.state"] + [f"{y}.{f}" for y in ys for f in HIST_FIELDS], refresh)
        for y in ys:
            d = pd.DataFrame([{"unitid": r["id"], "state": r["school.state"], "year": y,
                               **{v: r.get(f"{y}.{f}") for f, v in HIST_FIELDS.items()}} for r in raw])
            frames.append(d.dropna(subset=list(HIST_FIELDS.values()), how="all"))
    return pd.concat(frames, ignore_index=True)


def build_history(refresh: bool = False) -> pd.DataFrame:
    """State x year roll-ups of the year-keyed measures (same weighted medians/means as the latest roll-ups).
    Earnings are converted to 2024 dollars from each file's dollar year (CPI-U, calendar year); debt is nominal."""
    from .harmonize.finance import deflators
    h = history(refresh)
    cm = cohort_map()
    dollar = (cm[cm.measure == "earn10"].set_index("year").cohort.str.extract(r"(\d{4}) dollars")[0].astype(float))
    cpi = deflators("index")
    h["earn10_2024"] = h.earn10 * h.year.map(lambda y: cpi[2024] / cpi[int(dollar[y])] if y in dollar.index else np.nan)
    # enrollment weight: the same file's undergraduate count, else the nearest earlier file's (2000 and 2025 have none)
    h = h.sort_values(["unitid", "year"])
    h["w_ug"] = h.groupby("unitid").ugds.ffill()
    h.to_csv(OUT / "institutions_history.csv", index=False)
    rows = []
    for (y, st), g in pd.concat([h[h.state.isin(STATES)], h[h.state.isin(STATES)].assign(state="US")]).groupby(["year", "state"]):
        rows.append({"year": y, "state": st, "inst_n": g.ugds.notna().sum(),
                     "inst_earn10_median": wmedian(g.earn10_2024, g.earn10_n),
                     "inst_debt_median": wmedian(g.debt, g.w_ug),
                     "inst_completion_4yr": 100 * wmean(g.c150_4, g.w_ug),
                     "inst_pell_share": 100 * wmean(g.pell, g.w_ug),
                     "inst_ugds": g.ugds.sum(min_count=1),
                     "n_earn10": g.earn10.notna().sum(), "n_debt": g.debt.notna().sum(),
                     "n_c150_4": g.c150_4.notna().sum(), "n_pell": g.pell.notna().sum()})
    w = pd.DataFrame(rows)
    w.to_csv(OUT / "scorecard_state_years.csv", index=False)
    cm.pivot(index="year", columns="measure", values="cohort").reset_index().to_csv(OUT / "cohort_map.csv", index=False)
    return w


def build(refresh: bool = False) -> pd.DataFrame:
    inst = pd.DataFrame(pages("inst", list(INST_FIELDS), refresh)).rename(columns=INST_FIELDS)
    raw = pages("prog", ["id", "school.state"] + [f"{PROG}.{f}" for f in PROG_FIELDS], refresh)
    rows = []
    for r in raw:
        for p in r.get(PROG) or []:
            g = lambda path: (lambda o: o)(  # noqa: E731
                __import__("functools").reduce(lambda o, k: (o or {}).get(k), path.split("."), p))
            rows.append({"unitid": r["id"], "state": r["school.state"], "cip4": p.get("code"), "level": g("credential.level"),
                         "awards": g("counts.ipeds_awards2"), "earn1": g("earnings.1_yr.overall_median_earnings"),
                         "earn1_n": g("earnings.1_yr.working_not_enrolled.overall_count"),
                         "earn5": g("earnings.5_yr.overall_median_earnings"), "earn5_n": g("earnings.5_yr.working_not_enrolled.overall_count")})
    prog = pd.DataFrame(rows)
    prog["stem"] = prog.cip4.astype(str).str[:2].isin(STEM2)
    OUT.mkdir(parents=True, exist_ok=True)
    inst.to_csv(OUT / "institutions.csv", index=False)
    prog.to_csv(OUT / "programs.csv", index=False)

    out = {}
    for st in sorted(STATES) + ["US"]:
        i = inst if st == "US" else inst[inst.state == st]
        p = prog if st == "US" else prog[prog.state == st]
        if st == "US":
            i, p = i[i.state.isin(STATES)], p[p.state.isin(STATES)]
        m = {"inst_n": len(i), "inst_earn10_median": wmedian(i.earn10, i.earn10_n), "inst_earn1_median": wmedian(i.earn1, i.ugds),
             "inst_debt_median": wmedian(i.debt, i.ugds), "inst_completion_4yr": 100 * wmean(i.c150_4, i.ugds),
             "inst_pell_share": 100 * wmean(i.pell, i.ugds)}
        for lvl in ("bach", "master", "doc"):
            q = p[p.level.map(LEVELS) == lvl]
            for grp, qq in (("all", q), ("stem", q[q.stem]), ("nonstem", q[~q.stem])):
                m[f"prog_earn1_{lvl}_{grp}"] = wmedian(qq.earn1, qq.earn1_n)
                m[f"prog_earn5_{lvl}_{grp}"] = wmedian(qq.earn5, qq.earn5_n)
                m[f"prog_n1_{lvl}_{grp}"] = qq.earn1_n.where(qq.earn1.notna()).sum()
        m["prog_stem_premium1_bach"] = m["prog_earn1_bach_stem"] - m["prog_earn1_bach_nonstem"]
        out[st] = m
    w = pd.DataFrame(out).T.rename_axis("state").reset_index()
    w.to_csv(OUT / "scorecard_state_wide.csv", index=False)
    w.melt(id_vars="state", var_name="measure").dropna().to_csv(OUT / "scorecard_state.csv", index=False)
    ck = w[["state", "inst_n", "prog_n1_bach_all", "prog_n1_master_all"]].copy()
    ck["inst_with_earn10"] = ck.state.map(lambda s: (inst if s == "US" else inst[inst.state == s]).earn10.notna().sum())
    ck.to_csv(OUT / "checks.csv", index=False)
    return w


if __name__ == "__main__":
    if "history" in sys.argv:
        hw = build_history(refresh="--refresh" in sys.argv)
        print(hw[hw.state == "US"].set_index("year").drop(columns="state").round(1).to_string())
        sys.exit()
    w = build(refresh="--refresh" in sys.argv).set_index("state")
    print(w.loc[["US", "CA", "TX", "MA", "MS"], ["inst_n", "inst_earn10_median", "inst_debt_median", "prog_earn1_bach_stem",
                                                 "prog_earn1_bach_nonstem", "prog_earn5_bach_all", "prog_earn1_master_stem"]].round(0))
