"""Student financial aid for full-time, first-time degree/certificate-seeking undergraduates.

One row per unitid x survey year, 2000-2024. The SFA file in each folder describes the
PRIOR academic year (sfa9900s -> 1999-2000 ... sfa2324 -> 2023-24); `aid_ay` = fall
year of that aid year (= survey year - 1). Pell / any-grant / federal-loan items start
in 2008-2009; all-undergraduate items in 2009.

For each aid type: _n (students receiving), _avg (average among recipients),
_total (dollars; 2000 has no totals in the file, so _total = _n * _avg there).
  any_aid      any financial aid (n only)
  fed_grant    federal grants (Pell + other federal)
  pell         Pell grants                        (2010, 2020 only)
  state_grant  state/local grants
  inst_grant   institutional grants
  any_grant    federal+state+local+institutional  (2010, 2020 only)
  loan         all student loans (federal + other)
  fed_loan     federal student loans              (2010, 2020 only)
`cohort_ftft` is the fall cohort, or the full-year cohort for program reporters
(`cohort_basis`). Plus all-undergraduate Pell and federal-loan counts for 2010/2020 (ug_pell_*, ug_fed_loan_*).

2000 -> 2010 caveat: the 2008 HEOA expanded the SFA component (Pell and loan
detail, all-undergraduate items, net price), so only the five aid types present
in all three years are strictly comparable; definitions of "first-time" cohort
and "received" vs "awarded" (2020 wording) are otherwise unchanged in intent.
"""
from __future__ import annotations

import pandas as pd

from .. import load

TYPES = {"fed_grant": "fgrnt", "pell": "pgrnt", "state_grant": "sgrnt", "inst_grant": "igrnt",
         "any_grant": "agrnt", "loan": "loan", "fed_loan": "floan"}


def _f(d, c):
    return d[c].astype("Float64") if c in d else pd.Series(pd.NA, index=d.index, dtype="Float64")


def _one(year: int, table: str, aid_ay: int) -> pd.DataFrame:
    d = load(year, table)
    # Academic-year reporters use a fall cohort (scfa1n); program reporters (mostly
    # for-profit / <2-year) use a full-year cohort (scfy1n). Use whichever exists.
    fall, full = _f(d, "scfa1n"), _f(d, "scfy1n")
    use_fall = fall.notna() & fall.gt(0)
    out = pd.DataFrame({"year": year, "aid_ay": aid_ay, "unitid": d.unitid,
                        "cohort_ftft": fall.where(use_fall, full),
                        "cohort_basis": pd.Series(["fall" if f else "full_year" for f in use_fall],
                                                  index=d.index).where(fall.notna() | full.notna()),
                        "any_aid_n": _f(d, "anyaidn")})
    for name, stem in TYPES.items():
        n, a, t = _f(d, f"{stem}_n"), _f(d, f"{stem}_a"), _f(d, f"{stem}_t")
        out[f"{name}_n"], out[f"{name}_avg"] = n, a
        out[f"{name}_total"] = t if f"{stem}_t" in d else (n * a)
    out["ug_all_n"] = _f(d, "scugrad")
    for name, stem in (("ug_pell", "upgrnt"), ("ug_fed_loan", "ufloan")):
        out[f"{name}_n"], out[f"{name}_avg"], out[f"{name}_total"] = (_f(d, f"{stem}n"), _f(d, f"{stem}a"),
                                                                     _f(d, f"{stem}t"))
    # keep the reported percentages for QA
    out["_any_aid_p"] = _f(d, "anyaidp")
    out["_fed_grant_p"] = _f(d, "fgrnt_p")
    return out


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    import re
    from .. import tables
    t = tables()
    src = sorted((int(y), n) for y, n in zip(t.year, t.table) if re.fullmatch(r"sfa\d{4}s?", n))
    x = pd.concat([_one(y, n, y - 1) for y, n in src], ignore_index=True)
    qa = []
    for y, g in x.groupby("year"):
        ok = g.cohort_ftft > 0
        p = (g.any_aid_n / g.cohort_ftft * 100)[ok]
        qa.append({"year": y, "institutions": len(g),
                   "recipients_le_cohort": float((g.any_aid_n <= g.cohort_ftft)[ok & g.any_aid_n.notna()].mean()),
                   "any_aid_pct_matches_reported (+-1pt)": float(((p - g._any_aid_p[ok]).abs() <= 1).dropna().mean()),
                   "fed_grant_pct_matches (+-1pt)": float((((g.fed_grant_n / g.cohort_ftft * 100)[ok]
                                                           - g._fed_grant_p[ok]).abs() <= 1).dropna().mean())})
    x = x.drop(columns=[c for c in x if c.startswith("_")])
    return x.sort_values(["unitid", "year"]).reset_index(drop=True), pd.DataFrame(qa)
