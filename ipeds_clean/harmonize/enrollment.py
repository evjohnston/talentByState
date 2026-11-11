"""Harmonized Fall Enrollment: unitid x year x level x attendance x race x sex.

Source: ef1980_a, ef90_a, ef2000a, ef2010a, ef2020a (the "A" part: race x sex x
level x attendance). Each survey line is mapped to an additive cell:

  level        ug | grad | first_prof | level_unknown (grand-total-only reporters,
               mainly 1986-1989)
  attendance   ft | pt

Line/efalevel mapping (sums of lines where the form split a category):

            ug_ft     grad_ft         fp_ft   ug_pt      grad_pt        fp_pt   first-time ft/pt
  1980      1 + 8     11 + 9          10      15 + 22    25 + 23        24      2 / 16
  1990      8         11 + 12 + 13    9 + 10  22         25 + 26 + 27   23 + 24 1 / 15
  2000      8         11              9       22         25             23      1 / 15
  2010/20   el 22     el 32           --      el 42      el 52          --      el 24 / el 44
  (1980 lines 8/9 and 22/23 are "unclassified" students at the undergraduate /
   postbaccalaureate level; NCES counts them with undergrad / graduate.)
  From 2010 first-professional students are reported as graduate students, so
  first_prof is absent and `grad` includes them. For a consistent series use
  grad + first_prof ("postbacc").

Race (harmonized, comparable categories):
  nonres, black, aian, api, hisp, white, two_more (2010+ only), unknown
  * api = Asian + Native Hawaiian/Other Pacific Islander from 2010.
  * 1980 has no "unknown" item: unknown = reported total - sum of race detail
    (the residual, usually 0).
  * 1990: unknowns were pre-allocated to races by NCES (efrace13/14 are the
    "original unknown" memo, excluded), so 1990 has no unknown category and
    the race counts include allocated students.
  * 2010+ categories follow the 1997 OMB standard (Hispanic of any race; two or
    more races available), so breaks at 2010 are definitional, not real.

The first-time undergraduate counts (degree-seeking first-time freshmen) are a
SUBSET of ug and are written to a separate file so cells stay additive.
"""
from __future__ import annotations

import pandas as pd

from .. import load

OLD_RACE = {  # 1980-2007 efraceNN columns: (race, sex)
    "nonres": ("efrace01", "efrace02"), "black": ("efrace03", "efrace04"),
    "aian": ("efrace05", "efrace06"), "api": ("efrace07", "efrace08"),
    "hisp": ("efrace09", "efrace10"), "white": ("efrace11", "efrace12"),
    "unknown": ("efrace13", "efrace14"), "_total": ("efrace15", "efrace16"),
}
DV_RACE = {  # 2008-2009 transition: NCES-derived old+new categories
    "nonres": ["efnral"], "black": ["dvefbk"], "aian": ["dvefai"], "api": ["dvefap"],
    "hisp": ["dvefhs"], "white": ["dvefwh"], "two_more": ["ef2mor"], "unknown": ["efunkn"],
    "_total": ["eftotl"],
}
NEW_RACE = {  # 2010+ columns
    "nonres": ["efnral"], "black": ["efbkaa"], "aian": ["efaian"],
    "api": ["efasia", "efnhpi"], "hisp": ["efhisp"], "white": ["efwhit"],
    "two_more": ["ef2mor"], "unknown": ["efunkn"], "_total": ["eftotl"],
}
RACES = ["nonres", "black", "aian", "api", "hisp", "white", "two_more", "unknown", "not_collected"]

# ---- line / efalevel layouts -------------------------------------------------
# HEGIS lines (1980, 1984, 1985). ~20% of institutions reported the unclassified
# total (7 / 21) without the undergrad/postbacc split (8+9 / 22+23). Following
# NCES, unsplit unclassified students count as undergraduates:
# ug = 1 + 7 - 9, grad = 11 + 9 (negative key = subtract).
L_HEGIS = {("ug", "ft"): [1, 7, -9], ("grad", "ft"): [11, 9], ("first_prof", "ft"): [10],
           ("ug", "pt"): [15, 21, -23], ("grad", "pt"): [25, 23], ("first_prof", "pt"): [24]}
# IPEDS lines 1-29 (1986-1998, 2000, 2001; 2000/01 report only the subtotal lines,
# which the same mapping picks up).
L_IPEDS = {("ug", "ft"): [8], ("grad", "ft"): [11, 12, 13], ("first_prof", "ft"): [9, 10],
           ("ug", "pt"): [22], ("grad", "pt"): [25, 26, 27], ("first_prof", "pt"): [23, 24]}
# efalevel codes (1999, 2002-2009 with first-professional; 2010+ without)
EL_FP = {("ug", "ft"): [22], ("grad", "ft"): [32], ("first_prof", "ft"): [36],
         ("ug", "pt"): [42], ("grad", "pt"): [52], ("first_prof", "pt"): [56]}
EL = {("ug", "ft"): [22], ("grad", "ft"): [32], ("ug", "pt"): [42], ("grad", "pt"): [52]}


def layout(year: int) -> dict:
    """Everything that varies by year: table, key column, cells, race scheme."""
    if year in (1980, 1984, 1985):
        cells, ft, gt, key = L_HEGIS, {"ft": [2], "pt": [16]}, 29, "line"
    elif year <= 2001 and year != 1999:
        cells, ft, gt, key = L_IPEDS, {"ft": [1], "pt": [15]}, 29, "line"
    elif year <= 2009:
        cells, ft, gt, key = EL_FP, {"ft": [24], "pt": [44]}, 1, "efalevel"
    else:
        cells, ft, gt, key = EL, {"ft": [24], "pt": [44]}, 1, "efalevel"
    if year in (1985, 1987, 1989):
        race = "totals_only"       # race/ethnicity collected in even years only
    elif year in (1980, 1984, 1986, 1988):
        race = "old_no_unknown"    # no unknown item: unknown = total - detail
    elif 1990 <= year <= 1993:
        race = "old_allocated"     # unknowns pre-allocated; 13/14 = memo
    elif 1994 <= year <= 1997:
        race = "old_balance"       # _anr file: unknown = 13/14 + balance columns
    elif year <= 2007:
        race = "old"
    elif year <= 2009:
        race = "derived"
    else:
        race = "new"
    return {"cells": cells, "first_time": ft, "grand_total": gt, "key": key, "race": race}


def table_for(year: int) -> str | None:
    """The race x sex x level 'A' table: *_anr (1994-1999) else ef{yyyy}a / ef{yyyy}_a."""
    import re
    from .. import tables
    t = tables()
    names = set(t.loc[(t.year == year) & (t.component == "EF"), "table"])
    for pat in (r"ef\d+_anr", r"ef\d{2,4}_?a", r"ef\d{4}"):
        hit = sorted(n for n in names if re.fullmatch(pat, n))
        if hit:
            return hit[0]
    return None


def _long(year: int) -> pd.DataFrame:
    """unitid x key x race x sex long frame for one year."""
    L = layout(year)
    d = load(year, table_for(year))
    key = L["key"]
    d = d[d[key].notna()]
    keyv = pd.to_numeric(d[key], errors="coerce")
    out = []

    def add(race, sex, v):
        out.append(pd.DataFrame({"unitid": d.unitid.values, "key": keyv.values, "race": race,
                                 "sex": sex, "n": pd.Series(v).astype("Float64").fillna(0).values}))

    if L["race"] in ("new", "derived"):
        scheme = NEW_RACE if L["race"] == "new" else DV_RACE
        for race, stems in scheme.items():
            for sex, suf in (("men", "m"), ("women", "w")):
                cols = [f"{st}{suf}" for st in stems if f"{st}{suf}" in d]
                if cols:
                    add(race, sex, sum(d[c].astype("Float64").fillna(0) for c in cols))
    else:
        for race, (m, w) in OLD_RACE.items():
            if L["race"] == "totals_only" and race != "_total":
                continue
            if race == "unknown" and L["race"] == "old_allocated":
                continue
            for sex, col in (("men", m), ("women", w)):
                if col not in d:
                    continue
                v = d[col].astype("Float64").fillna(0)
                if race == "unknown" and L["race"] == "old_balance":
                    bal = next((b for b in ([f"bal_{sex[0]}", "balmen" if sex == "men" else "balwomen"]) if b in d), None)
                    if bal:
                        v = v + d[bal].astype("Float64").fillna(0)
                add(race, sex, v)
        if L["race"] == "totals_only":
            for sex, col in (("men", "efrace15"), ("women", "efrace16")):
                add("not_collected", sex, d[col])
    x = pd.concat(out, ignore_index=True)
    x = x.groupby(["unitid", "key", "race", "sex"], as_index=False)["n"].sum()
    if L["race"] == "old_no_unknown":  # residual "unknown" = reported total - detail
        piv = x.pivot_table(index=["unitid", "key", "sex"], columns="race", values="n", aggfunc="sum").fillna(0)
        resid = piv["_total"] - piv[[r for r in piv.columns if r != "_total"]].sum(axis=1)
        u = resid.rename("n").reset_index().assign(race="unknown")
        x = pd.concat([x, u], ignore_index=True)
    return x


def _cells(x: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    rows = []
    for (level, att), keys in mapping.items():
        sign = {abs(k): (-1 if k < 0 else 1) for k in keys}
        s = x[x.key.isin(sign) & (x.race != "_total")].copy()
        s["n"] = s["n"] * s["key"].map(sign)
        g = s.groupby(["unitid", "race", "sex"], as_index=False)["n"].sum()
        rows.append(g.assign(level=level, attendance=att))
    return pd.concat(rows, ignore_index=True)


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (enrollment, first_time, qa)."""
    enr, ft, qa = [], [], []
    from ..config import YEARS
    for year in YEARS:
        if table_for(year) is None:
            continue
        L = layout(year)
        x = _long(year)
        e = _cells(x, L["cells"]).assign(year=year)
        # Institutions that reported only the grand total (no level/attendance lines;
        # ~1,200 small schools in 1986-87, ~300 in 1989): keep their students in a
        # flagged level_unknown cell so totals stay complete.
        total_only = set(x.loc[x.key == L["grand_total"], "unitid"]) - set(e.loc[e.n != 0, "unitid"])
        g = x[(x.key == L["grand_total"]) & (x.race != "_total") & x.unitid.isin(total_only)]
        resid = g.groupby(["unitid", "race", "sex"], as_index=False)["n"].sum()
        resid = resid[resid.n != 0]
        if len(resid):
            e = pd.concat([e, resid.assign(level="level_unknown", attendance="unknown", year=year)],
                          ignore_index=True)
        f = _cells(x, {("ug_first_time", a): k for a, k in L["first_time"].items()}).assign(year=year)
        enr.append(e)
        ft.append(f)
        # QA: additive cells vs the reported grand total, per institution
        gt = x[(x.key == L["grand_total"]) & (x.race == "_total")].groupby("unitid")["n"].sum()
        cs = e.groupby("unitid")["n"].sum()
        c = pd.DataFrame({"cells": cs, "grand_total": gt}).fillna(0)
        rt = x[x.race == "_total"].groupby(["unitid", "key"])["n"].sum()
        rd = x[x.race != "_total"].groupby(["unitid", "key"])["n"].sum()
        qa.append({"year": year, "table": table_for(year), "race_scheme": L["race"], "institutions": len(c),
                   "sum_cells": c.cells.sum(), "sum_grand_total": c.grand_total.sum(),
                   "inst_cells_eq_total": float((c.cells - c.grand_total).abs().le(0.5).mean()),
                   "race_detail_eq_total": float((rt - rd.reindex(rt.index).fillna(0)).abs().le(0.5).mean())})
    order = ["year", "unitid", "level", "attendance", "race", "sex", "n"]
    enr = pd.concat(enr, ignore_index=True)[order]
    ft = pd.concat(ft, ignore_index=True)[order]
    for d in (enr, ft):
        d["race"] = pd.Categorical(d["race"], RACES)
        d["n"] = d["n"].astype("Float64")
    enr = enr[enr.n.ne(0)].reset_index(drop=True)   # drop structural zeros
    ft = ft[ft.n.ne(0)].reset_index(drop=True)
    return enr, ft, pd.DataFrame(qa)
