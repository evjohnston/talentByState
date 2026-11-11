"""Graduation Rate Survey (150% of normal time), every year 1997-2024.

The GRS began in 1997, so there is no 1980 or 1990 equivalent.

Grain: unitid x year x cohort x measure x race x sex -> n (student counts).
Rates are computed from counts (completers / adjusted cohort) so they can be
aggregated correctly; `rates()` does that.

  cohort   ba4   bachelor's-seeking subcohort at 4-year institutions
           oth4  other degree/certificate-seeking subcohort at 4-year institutions
           c2yr  degree/certificate-seeking cohort at 2-year institutions
           lt2   degree/certificate-seeking cohort at less-than-2-year institutions:
                 main file grtype 35-39 through 2003 (race x sex detail); separate
                 gr{yyyy}_l2 files from 2004 (totals only: race = not_collected, sex = all)
                 Combine c2yr + lt2 for all less-than-4-year institutions.
  cohort_year  entering fall: 4-year cohorts 1994 / 2004 / 2014,
               less-than-4-year cohorts 1997 / 2007 / 2017

  measure  revised, exclusions, adj_cohort,
           comp150          completers of any award within 150% of normal time
           comp150_bach     ba4: completers of a bachelor's within 150% (6 years)
           comp_bach_4yr, comp_bach_5yr   ba4: within 4 / 5 years (2010+ only)
           comp100          lt4: completers within 100% of normal time (2010+ only)
           transfer_out, still_enrolled

grtype -> (cohort, measure). Codes are stable 2000-2020 except 35-39, which in
2000 meant "<2-year institutions" and from 2010 mean 100%-time completers.

Race: 1997-2007 grrace01-14 (old categories); 2008-2010 NCES-derived dvgr* (old+new
merged, transition years) + grnral, gr2mor, grunkn; 2011+ new categories, api = Asian+NHPI.
cohort_year = survey year - 6 (4-year cohorts) or - 3 (less-than-4-year).
"""
from __future__ import annotations

import pandas as pd

from .. import load

RACES = ["nonres", "black", "aian", "api", "hisp", "white", "two_more", "unknown", "not_collected"]

GRTYPE = {
    6: ("ba4", "revised"), 7: ("ba4", "exclusions"), 8: ("ba4", "adj_cohort"),
    9: ("ba4", "comp150"), 12: ("ba4", "comp150_bach"),
    13: ("ba4", "comp_bach_4yr"), 14: ("ba4", "comp_bach_5yr"),
    16: ("ba4", "transfer_out"), 17: ("ba4", "still_enrolled"),
    18: ("oth4", "revised"), 19: ("oth4", "exclusions"), 20: ("oth4", "adj_cohort"),
    21: ("oth4", "comp150"), 25: ("oth4", "transfer_out"), 26: ("oth4", "still_enrolled"),
    27: ("c2yr", "revised"), 28: ("c2yr", "exclusions"), 29: ("c2yr", "adj_cohort"),
    30: ("c2yr", "comp150"), 33: ("c2yr", "transfer_out"), 34: ("c2yr", "still_enrolled"),
}
# Through 2008, grtype 35-39 = the separate less-than-2-year institution cohort;
# from 2009 they are 100%-of-normal-time completers of the 2-year cohort.
GRTYPE_OLD = dict(GRTYPE)
GRTYPE_OLD.update({35: ("lt2", "revised"), 36: ("lt2", "exclusions"), 37: ("lt2", "adj_cohort"),
                   38: ("lt2", "comp150"), 39: ("lt2", "transfer_out")})
GRTYPE_NEW = {**GRTYPE, 35: ("c2yr", "comp100")}
# Less-than-2-year institutions: in the main file (grtype 35-39) through 2003; from
# 2004 only in the separate gr{yyyy}_l2 files, which have totals only (no race/sex).
L2_LINES = {"line_10": "revised", "line_45": "exclusions", "line_50": "adj_cohort",
            "line_11": "comp150", "line_30": "transfer_out", "line_55": "comp100"}
GRTYPE_2000 = GRTYPE_OLD  # backwards-compatible name


def cohort_year(year: int) -> dict:
    """4-year cohorts entered 6 years before the survey; less-than-4-year cohorts 3 years before."""
    return {"ba4": year - 6, "oth4": year - 6, "c2yr": year - 3, "lt2": year - 3}


def years() -> list[int]:
    import re
    from .. import tables
    t = tables()
    return sorted(int(y) for y, n in zip(t.year, t.table) if re.fullmatch(r"gr\d{4}", n))

OLD = {"nonres": (1, 2), "black": (3, 4), "aian": (5, 6), "api": (7, 8),
       "hisp": (9, 10), "white": (11, 12), "unknown": (13, 14)}
NEW_DV = {"nonres": ["grnral"], "black": ["dvgrbk"], "aian": ["dvgrai"], "api": ["dvgrap"],
           "hisp": ["dvgrhs"], "white": ["dvgrwh"], "two_more": ["gr2mor"], "unknown": ["grunkn"]}
NEW_2011 = {"nonres": ["grnral"], "black": ["grbkaa"], "aian": ["graian"], "api": ["grasia", "grnhpi"],
            "hisp": ["grhisp"], "white": ["grwhit"], "two_more": ["gr2mor"], "unknown": ["grunkn"]}


def _year(year: int) -> tuple[pd.DataFrame, dict]:
    d = load(year, f"gr{year}")
    d["grtype"] = pd.to_numeric(d["grtype"], errors="coerce")   # stored as text in some years (2002)
    gmap = GRTYPE_OLD if year <= 2008 else GRTYPE_NEW
    old_race = year <= 2007
    scheme = NEW_DV if year <= 2010 else NEW_2011
    d = d[d.grtype.isin(gmap)].copy()
    d["cohort"] = d.grtype.map(lambda g: gmap[g][0])
    d["measure"] = d.grtype.map(lambda g: gmap[g][1])
    parts = []
    for sex, suf in (("men", "m"), ("women", "w")):
        if old_race:
            for race, (m, w) in OLD.items():
                col = f"grrace{(m if sex == 'men' else w):02d}"
                parts.append(d[["unitid", "cohort", "measure"]].assign(race=race, sex=sex,
                                                                      n=d[col].astype("Float64").fillna(0)))
            total = d.grrace15 if sex == "men" else d.grrace16
        else:
            for race, stems in scheme.items():
                cols = [f"{st}{suf}" for st in stems if f"{st}{suf}" in d]
                if not cols:
                    continue
                v = sum(d[c].astype("Float64").fillna(0) for c in cols)
                parts.append(d[["unitid", "cohort", "measure"]].assign(race=race, sex=sex, n=v))
            total = d[f"grtotl{suf}"]
        parts.append(d[["unitid", "cohort", "measure"]].assign(race="_total", sex=sex,
                                                              n=total.astype("Float64").fillna(0)))
    x = pd.concat(parts, ignore_index=True)
    x = x.groupby(["unitid", "cohort", "measure", "race", "sex"], as_index=False)["n"].sum()
    t = x[x.race == "_total"].set_index(["unitid", "cohort", "measure", "sex"])["n"]
    r = x[x.race != "_total"].groupby(["unitid", "cohort", "measure", "sex"])["n"].sum()
    ok = (t - r.reindex(t.index).fillna(0)).abs().le(0.5)
    qa = {"year": year, "rows": len(d), "race_sum_eq_total": float(ok.mean()) if len(ok) else float("nan")}
    x = x[x.race != "_total"].assign(year=year)
    if not (x.cohort == "lt2").any():   # 2004+: less-than-2-year institutions from the L2 file
        l2 = _l2(year)
        if l2 is not None:
            x = pd.concat([x, l2], ignore_index=True)
    x["cohort_year"] = x.cohort.map(cohort_year(year))
    return x, qa


def _l2(year: int) -> pd.DataFrame | None:
    from .. import tables
    t = tables()
    if not ((t.year == year) & (t.table == f"gr{year}_l2")).any():
        return None
    d = load(year, f"gr{year}_l2")
    parts = [pd.DataFrame({"unitid": d.unitid, "cohort": "lt2", "measure": m, "race": "not_collected",
                           "sex": "all", "n": d[c].astype("Float64").fillna(0)})
             for c, m in L2_LINES.items() if c in d]
    return pd.concat(parts, ignore_index=True).assign(year=year) if parts else None


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    out, qa = [], []
    for y in years():
        x, q = _year(y)
        out.append(x)
        qa.append(q)
    x = pd.concat(out, ignore_index=True)
    x = x[x.n != 0]
    x["race"] = pd.Categorical(x.race, RACES)
    x["n"] = x.n.astype("Float64")
    cols = ["year", "unitid", "cohort", "cohort_year", "measure", "race", "sex", "n"]
    x = x[cols].sort_values(cols[:-1]).reset_index(drop=True)
    qa = pd.DataFrame(qa)
    # QA: 4-year total cohort (grtype 2 / 3) == ba4 + oth4 subcohorts, per institution.
    # (The gr200 files can't be used: they follow an earlier cohort, e.g. 2002 in 2010.)
    chk = []
    for y in years():
        d = load(y, f"gr{y}")
        d["grtype"] = pd.to_numeric(d["grtype"], errors="coerce")
        tc = "grrace24" if y <= 2007 else "grtotlt"
        for g_all, measure in ((2, "adj_cohort"), (3, "comp150")):
            a = d[d.grtype == g_all].groupby("unitid")[tc].sum()
            b = x[(x.year == y) & x.cohort.isin(["ba4", "oth4"]) & (x.measure == measure)].groupby("unitid")["n"].sum()
            chk.append({"year": y, "check": f"4yr total {measure} == ba4+oth4",
                        "match": float((a - b.reindex(a.index).fillna(0)).abs().le(0.5).mean()) if len(a) else float("nan")})
    qa = qa.merge(pd.DataFrame(chk), on="year", how="left")
    return x, qa


def rates(df: pd.DataFrame, by: list[str], cohort: str = "ba4", num: str = "comp150_bach") -> pd.DataFrame:
    """Completers / adjusted cohort, aggregated over `by` (e.g. ['year'] or ['year','race'])."""
    d = df[df.cohort == cohort]
    g = d.pivot_table(index=by, columns="measure", values="n", aggfunc="sum", observed=True)
    out = pd.DataFrame({"adj_cohort": g.get("adj_cohort"), "completers": g.get(num)}).fillna(0)
    out["rate"] = out.completers / out.adj_cohort
    return out.reset_index()
