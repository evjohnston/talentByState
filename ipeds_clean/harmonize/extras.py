"""Additional harmonized panels.

  admissions        2001-2024  applicants / admits / enrolled (by sex, FT/PT), SAT/ACT percentiles
                               (ic{yyyy} through 2013, adm{yyyy} from 2014)
  retention         2003-2024  FT/PT retention rates and cohorts, student-to-faculty ratio (ef{yyyy}d)
  fte               1980-2024  fall FTE (FT + PT/3, from the enrollment panel) for every year, plus
                               12-month instructional activity and NCES-reported FTE (efia, 2002+)
  enrollment_12mo   2002-2024  unduplicated 12-month headcount by level x race x sex (effy)
  enrollment_age    odd years  fall enrollment by age group x FT/PT x sex (ef{yyyy}b), where the
                               layout is parseable (line labels or efbage codes)
  residence         even years first-time students by state of residence when admitted (ef{yyyy}c)
  outcome_measures  2015-2024  stacked as published (cohort category x outcome variables)
  gr200             2008-2024  graduation within 200% of normal time (stacked)
  gr_pell           2016-2024  graduation rates by Pell / Subsidized Stafford receipt (stacked)
  completers        2012-2024  unduplicated completers by race x sex (c_b) and by award level x age (c_c)
  distance_ed       2012-2024  fall enrollment by distance-education status (ef_dist)
  libraries         2014-2024  academic libraries (stacked)

"Stacked" = all years concatenated with a year column; variable names are stable over these
short spans, and every variable's label per year is written to extras_variables.csv.
"""
from __future__ import annotations

import re

import pandas as pd

from .. import labels, load, tables, variables


def _t():
    t = tables()
    return sorted(zip(t.year.astype(int), t.table))


def _f(d, c):
    return d[c].astype("Float64") if c in d else pd.Series(pd.NA, index=d.index, dtype="Float64")


def _stack(pattern: str, keep_strings: tuple = ()) -> pd.DataFrame:
    parts = []
    for y, n in _t():
        if re.fullmatch(pattern, n):
            d = load(y, n)
            d = d[[c for c in d.columns if not c.startswith("x") or c in keep_strings]]
            parts.append(d.assign(year=y, source_table=n))
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True)
    lead = ["year", "unitid"]
    return x[lead + [c for c in x.columns if c not in lead]]


# ---------------------------------------------------------------- admissions
ADM_COLS = ["applcn", "applcnm", "applcnw", "admssn", "admssnm", "admssnw", "enrlt", "enrlm", "enrlw",
            "enrlft", "enrlftm", "enrlftw", "enrlpt", "enrlptm", "enrlptw",
            "satnum", "satpct", "actnum", "actpct", "satvr25", "satvr75", "satmt25", "satmt75",
            "actcm25", "actcm75", "acten25", "acten75", "actmt25", "actmt75"]


def admissions() -> pd.DataFrame:
    parts = []
    for y, n in _t():
        if (y <= 2013 and n == f"ic{y}") or n == f"adm{y}":
            d = load(y, n)
            if "applcnm" not in d and "applcn" not in d:
                continue
            out = pd.DataFrame({"year": y, "unitid": d.unitid})
            for c in ADM_COLS:
                out[c] = _f(d, c)
            for tot, (m, w) in {"applcn": ("applcnm", "applcnw"), "admssn": ("admssnm", "admssnw"),
                                "enrlft": ("enrlftm", "enrlftw"), "enrlpt": ("enrlptm", "enrlptw")}.items():
                out[tot] = out[tot].fillna(out[m].add(out[w], fill_value=0).where(out[m].notna() | out[w].notna()))
            out["enrlt"] = out.enrlt.fillna(out.enrlft.add(out.enrlpt, fill_value=0).where(out.enrlft.notna() | out.enrlpt.notna()))
            out["source_table"] = n
            parts.append(out)
    x = pd.concat(parts, ignore_index=True)
    x = x[x[["applcn", "admssn", "enrlt"]].notna().any(axis=1)]
    x["admit_rate"] = (x.admssn / x.applcn).where(x.applcn > 0)
    x["yield_rate"] = (x.enrlt / x.admssn).where(x.admssn > 0)
    return x.reset_index(drop=True)


# ---------------------------------------------------------------- retention
RET_COLS = ["grcohrt", "ugentern", "pgrcohrt", "rrftct", "rrftex", "rrftin", "rrftcta", "ret_nmf", "ret_pcf",
            "rrptct", "rrptex", "rrptin", "rrptcta", "ret_nmp", "ret_pcp", "stufacr"]


def retention() -> pd.DataFrame:
    parts = []
    for y, n in _t():
        if n == f"ef{y}d":
            d = load(y, n)
            out = pd.DataFrame({"year": y, "unitid": d.unitid})
            for c in RET_COLS:
                out[c] = _f(d, c)
            parts.append(out)
    x = pd.concat(parts, ignore_index=True)
    return x[x[RET_COLS].notna().any(axis=1)].reset_index(drop=True)


# ---------------------------------------------------------------- FTE
def fte(enrollment: pd.DataFrame) -> pd.DataFrame:
    """Fall FTE = FT + PT/3 (the standard NCES approximation) for every year, plus the 12-month
    instructional-activity file (efia, 2002+): credit/contact hours and NCES-reported FTE."""
    e = enrollment.copy()
    e["lvl"] = e.level.map({"ug": "ug", "grad": "grad", "first_prof": "grad", "level_unknown": "unknown"})
    p = e.pivot_table(index=["year", "unitid"], columns=["lvl", "attendance"], values="n", aggfunc="sum").fillna(0)
    g = lambda lv, at: p[(lv, at)] if (lv, at) in p.columns else 0
    out = pd.DataFrame({"fall_fte_ug": g("ug", "ft") + g("ug", "pt") / 3,
                        "fall_fte_grad": g("grad", "ft") + g("grad", "pt") / 3}).reset_index()
    out["fall_fte_total"] = out.fall_fte_ug + out.fall_fte_grad
    ia = []
    for y, n in _t():
        if n == f"efia{y}":
            d = load(y, n)
            r = pd.DataFrame({"year": y, "unitid": d.unitid})
            for c, new in [("cdactua", "credit_hours_ug"), ("cnactua", "contact_hours_ug"), ("cdactga", "credit_hours_grad"),
                           ("fteug", "fte12_ug_reported"), ("ftegd", "fte12_grad_reported"), ("ftedpp", "fte12_docprof_reported"),
                           ("efteug", "fte12_ug_estimated"), ("eftegd", "fte12_grad_estimated")]:
                r[new] = _f(d, c)
            ia.append(r)
    if ia:
        out = out.merge(pd.concat(ia, ignore_index=True), on=["year", "unitid"], how="outer")
    for c in out.columns:
        if c not in ("year", "unitid"):
            out[c] = out[c].astype("Float64")
    return out.sort_values(["unitid", "year"]).reset_index(drop=True)


# ---------------------------------------------------------------- 12-month enrollment
_RACE_OLD = {"nonres": (1, 2), "black": (3, 4), "aian": (5, 6), "api": (7, 8), "hisp": (9, 10),
             "white": (11, 12), "unknown": (13, 14)}
_RACE_NEW = {"nonres": ["nral"], "black": ["bkaa"], "aian": ["aian"], "api": ["asia", "nhpi"],
             "hisp": ["hisp"], "white": ["whit"], "two_more": ["2mor"], "unknown": ["unkn"]}
_RACE_DV = {"nonres": ["nral"], "black": ["bk"], "aian": ["ai"], "api": ["ap"], "hisp": ["hs"],
            "white": ["wh"], "two_more": ["2mor"], "unknown": ["unkn"]}


def enrollment_12mo() -> pd.DataFrame:
    parts = []
    for y, n in _t():
        if n != f"effy{y}":
            continue
        d = load(y, n)
        lv = pd.to_numeric(d.effylev, errors="coerce")
        keep = lv.isin([2, 3, 4])
        if "effyalev" in d:   # 2023+: detailed rows exist too; keep level totals only
            keep &= pd.to_numeric(d.effyalev, errors="coerce").isin([2, 12])
        d = d[keep]
        level = pd.to_numeric(d.effylev, errors="coerce").map({2: "ug", 3: "first_prof", 4: "grad"})
        rows = []
        cols = set(d.columns)
        for sex, (i, suf) in (("men", (0, "m")), ("women", (1, "w"))):
            if "fyrace15" in cols:            # 2002-2007 old categories
                for race, pair in _RACE_OLD.items():
                    rows.append((race, sex, _f(d, f"fyrace{pair[i]:02d}")))
            else:
                dv = any(c.startswith(("dvey", "dvefy", "dvfy")) for c in cols)
                for race, stems in (_RACE_DV if dv else _RACE_NEW).items():
                    cand = []
                    for st in stems:
                        for pre in (["dvey", "dvefy", "dvfy", "efy"] if dv else ["efy"]):
                            c = f"{pre}{st}{suf}"
                            if c in cols:
                                cand.append(c)
                                break
                    if cand:
                        rows.append((race, sex, sum(_f(d, c).fillna(0) for c in cand)))
        for race, sex, v in rows:
            parts.append(pd.DataFrame({"year": y, "unitid": d.unitid.values, "level": level.values,
                                       "race": race, "sex": sex, "n": v.fillna(0).values}))
    x = pd.concat(parts, ignore_index=True)
    x = x.groupby(["year", "unitid", "level", "race", "sex"], as_index=False)["n"].sum()
    return x[x.n != 0].reset_index(drop=True)


# ---------------------------------------------------------------- age
_AGE_ORDER = ["under18", "18_19", "20_21", "22_24", "25_29", "30_34", "35_39", "40_49", "50_64", "65plus", "unknown"]
_AGE_PAT = [(r"under 18", "under18"), (r"18.?19", "18_19"), (r"20.?21", "20_21"), (r"22.?24", "22_24"),
            (r"25.?29", "25_29"), (r"30.?34", "30_34"), (r"35.?39", "35_39"), (r"40.?49", "40_49"),
            (r"50.?64", "50_64"), (r"65", "65plus"), (r"unknown", "unknown")]


def _age_group(label: str) -> str | None:
    l = str(label).lower()
    if "total" in l:
        return None
    return next((g for p, g in _AGE_PAT if re.search(p, l)), None)


def _level_of(label) -> str | None:
    l = str(label).lower()
    if "total" in l or "all students" in l:
        return None
    if "first" in l and "prof" in l:
        return "first_prof"
    if "undergrad" in l:
        return "ug"
    if "grad" in l:
        return "grad"
    return None


def enrollment_age() -> pd.DataFrame:
    """Fall enrollment by age. Layouts:
    1987-1997  line = FT/PT x age group; columns efage01.. = level x sex (by label)
    2000-2001  line = FT/PT x age group; efage01/02 = men/women; lstudy = level
    1999, 2002+ efbage = age group; efage01-04 = FT men/women, PT men/women; lstudy = level
    'All students' / total rows and columns are dropped so cells are additive."""
    v = variables()
    parts = []
    for y, n in _t():
        if not re.fullmatch(rf"ef{y}b|ef\d{{2}}_b|ef{y}_b", n):
            continue
        d = load(y, n)
        vl = v[(v.year == y) & (v.table == n)]
        vlab = dict(zip(vl.varname, vl.label))
        if "efbage" in d:
            lab = labels(y, n, "efbage")
            grp = d.efbage.astype("string").map({k: _age_group(val) for k, val in lab.items()})
            lv = d.lstudy.astype("string").map({k: _level_of(val) for k, val in labels(y, n, "lstudy").items()})
            for att, sex, c in [("ft", "men", "efage01"), ("ft", "women", "efage02"),
                                ("pt", "men", "efage03"), ("pt", "women", "efage04")]:
                parts.append(pd.DataFrame({"year": y, "unitid": d.unitid, "level": lv, "age_group": grp,
                                           "attendance": att, "sex": sex, "n": _f(d, c)}))
            continue
        if "line" not in d:
            continue
        lab = labels(y, n, "line")
        key = d.line.astype("string").str.strip()
        att = key.map({k: ("ft" if re.search(r"full", str(val), re.I) else "pt" if re.search(r"part", str(val), re.I)
                           else None) for k, val in lab.items()})
        grp = key.map({k: _age_group(val) for k, val in lab.items()})
        if "lstudy" in d and labels(y, n, "lstudy") and "efage03" not in d:   # 2000-2001
            lv = d.lstudy.astype("string").map({k: _level_of(val) for k, val in labels(y, n, "lstudy").items()})
            for sex, c in (("men", "efage01"), ("women", "efage02")):
                parts.append(pd.DataFrame({"year": y, "unitid": d.unitid, "level": lv, "age_group": grp,
                                           "attendance": att, "sex": sex, "n": _f(d, c)}))
        else:                                                                 # 1987-1997
            for c in [c for c in d.columns if re.fullmatch(r"efage\d\d", c)]:
                l = str(vlab.get(c, ""))
                lv = _level_of(l)
                if lv is None:
                    continue
                sex = "women" if "women" in l.lower() else "men" if "men" in l.lower() else None
                parts.append(pd.DataFrame({"year": y, "unitid": d.unitid, "level": lv, "age_group": grp,
                                           "attendance": att, "sex": sex, "n": _f(d, c)}))
    x = pd.concat(parts, ignore_index=True)
    x = x.dropna(subset=["age_group", "attendance", "level", "sex"])
    x["age_group"] = pd.Categorical(x.age_group, _AGE_ORDER, ordered=True)
    x = x.groupby(["year", "unitid", "level", "attendance", "age_group", "sex"], as_index=False, observed=True)["n"].sum()
    return x[x.n.fillna(0) != 0].reset_index(drop=True)


# ---------------------------------------------------------------- residence
def residence() -> pd.DataFrame:
    parts = []
    for y, n in _t():
        if not re.fullmatch(rf"ef{y}c|ef\d{{2}}_c|ef{y}_c", n):
            continue
        d = load(y, n)
        key = "efcstate" if "efcstate" in d else "line" if "line" in d else None
        if key is None or "efres01" not in d:
            continue
        lab = labels(y, n, key)
        code = pd.to_numeric(d[key], errors="coerce")
        parts.append(pd.DataFrame({"year": y, "unitid": d.unitid, "state_code": code.astype("Int64"),
                                   "state": d[key].astype("string").str.strip().map(lab),
                                   "first_time": _f(d, "efres01"), "recent_hs_grads": _f(d, "efres02")}))
    x = pd.concat(parts, ignore_index=True)
    # drop the total rows (99 = all students, 58 = US total) so rows are additive by state
    tot = x.state.astype("string").str.contains("total", case=False, na=False)
    return x[~tot].reset_index(drop=True)


# ---------------------------------------------------------------- stacked components
def outcome_measures():
    return _stack(r"om\d{4}")


def gr200():
    return _stack(r"gr200_\d{2}")


def gr_pell():
    return _stack(r"gr\d{4}_pell_ssl")


def completers():
    b, c = _stack(r"c\d{4}_b"), _stack(r"c\d{4}_c")
    return b[b.year >= 2012].reset_index(drop=True), c[c.year >= 2012].reset_index(drop=True)


def distance_ed():
    return _stack(r"ef\d{4}a_dist")


def libraries():
    return _stack(r"al\d{4}")


def variable_catalog(names: list[str]) -> pd.DataFrame:
    """Labels per year for the stacked panels' variables (extras_variables.csv)."""
    v = variables()
    pats = {"outcome_measures": r"om\d{4}", "gr200": r"gr200_\d{2}", "gr_pell": r"gr\d{4}_pell_ssl",
            "completers_race": r"c\d{4}_b", "completers_age": r"c\d{4}_c", "distance_ed": r"ef\d{4}a_dist",
            "libraries": r"al\d{4}"}
    rows = []
    for nm in names:
        m = v[v.table.str.fullmatch(pats[nm])]
        g = m.groupby("varname").agg(first_year=("year", "min"), last_year=("year", "max"),
                                     label=("label", "last")).reset_index()
        rows.append(g.assign(panel=nm))
    return pd.concat(rows, ignore_index=True)[["panel", "varname", "label", "first_year", "last_year"]]


# ---------------------------------------------------------------- staff (EAP)
STAFF_CATS = ["all_staff", "instr_total", "instr_tenured", "instr_tenure_track", "instr_not_tenure_track",
              "instr_no_faculty_status"]


def staff() -> pd.DataFrame:
    """Employees by assigned position, 2001-2024: all staff and instructional staff by tenure
    status, full-time / part-time (medical-school staff included).

    2001       eap2001: typecd (1/2 FT, 3/4 PT) x functcd (1+2 = instruction, 12 = total) x fstat1-5 columns
    2002-2011  eap: functcd (10 all, 23 all instruction) x fstat (0 all, 2 tenured, 3 on track,
               4 not on track, 5 without faculty status) x ftpt (2 FT, 3 PT), value eaptot
    2012-2024  eap: eapcat 10000 all staff; 21000/21020/21030/21040/21050 instructional staff
               total/tenured/on track/not on track/without faculty status; eapft / eappt
    'instr_*' = primarily instruction + instruction combined with research/public service (2001-11)
    or the 'Instructional staff' categories (2012+); a definitional break at 2012 is expected."""
    out = []
    for y, n in _t():
        if n != f"eap{y}":
            continue
        d = load(y, n)
        if y == 2001:
            d = d.assign(ftpt=d.typecd.map({1: "ft", 2: "ft", 3: "pt", 4: "pt"}))
            tot = d[d.functcd == 12]
            ins = d[d.functcd.isin([1, 2])]
            for att in ("ft", "pt"):
                t_, i_ = tot[tot.ftpt == att], ins[ins.ftpt == att]
                g = lambda df, c: df.groupby("unitid")[c].sum(min_count=1)
                vals = {"all_staff": g(t_, "fstat5") if att == "ft" else g(t_, "fstat5"),
                        "instr_tenured": g(i_, "fstat1"), "instr_tenure_track": g(i_, "fstat2"),
                        "instr_not_tenure_track": g(i_, "fstat3"), "instr_no_faculty_status": g(i_, "fstat4")}
                vals["instr_total"] = sum(vals[k].fillna(0) for k in ["instr_tenured", "instr_tenure_track",
                                                                      "instr_not_tenure_track", "instr_no_faculty_status"])
                for cat, s in vals.items():
                    out.append(pd.DataFrame({"year": y, "unitid": s.index, "category": cat, "attendance": att,
                                             "n": s.values}))
        elif y <= 2011:
            m = {(10, 0): "all_staff", (23, 0): "instr_total", (23, 2): "instr_tenured", (23, 3): "instr_tenure_track",
                 (23, 4): "instr_not_tenure_track", (23, 5): "instr_no_faculty_status"}
            d = d[d.ftpt.isin([2, 3])]
            d = d.assign(category=[m.get((f, s)) for f, s in zip(d.functcd, d.fstat)]).dropna(subset=["category"])
            out.append(pd.DataFrame({"year": y, "unitid": d.unitid, "category": d.category,
                                     "attendance": d.ftpt.map({2: "ft", 3: "pt"}), "n": _f(d, "eaptot")}))
        else:
            m = {10000: "all_staff", 21000: "instr_total", 21020: "instr_tenured", 21030: "instr_tenure_track",
                 21040: "instr_not_tenure_track", 21050: "instr_no_faculty_status"}
            d = d[d.eapcat.isin(m)]
            for att, c in (("ft", "eapft"), ("pt", "eappt")):
                out.append(pd.DataFrame({"year": y, "unitid": d.unitid, "category": d.eapcat.map(m),
                                         "attendance": att, "n": _f(d, c)}))
    x = pd.concat(out, ignore_index=True)
    x["n"] = x.n.astype("Float64")
    x = x.groupby(["year", "unitid", "category", "attendance"], as_index=False)["n"].sum(min_count=1)
    x["category"] = pd.Categorical(x.category, STAFF_CATS)
    return x.dropna(subset=["n"]).reset_index(drop=True)
