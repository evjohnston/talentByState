"""Full-time instructional faculty: counts and salary outlays, all available years.

Grain: unitid x year x rank x contract x sex
  n_faculty, salary_outlay, n_tenured (where collected),
  outlay_eq9 = salary outlay equated to a 9-month basis (see below)
Average salary = salary_outlay / n_faculty; equated 9-month = outlay_eq9 / n_faculty
(use `equated_9month()` to aggregate correctly).

  rank      prof, assoc, asst, instr, lect, norank   (total rows dropped; used for QA)
  contract  9_10   9/10-month contracts  (1980-85: "9-month")
            11_12  11/12-month contracts (1980-85: "12-month")
            9_12   2012-2015 only: counts are by contract month but outlays are
                   reported only as a 9-12-month total, so contract can't be split
  sex       men, women
  Less-than-9-month faculty (reported separately in some years) are excluded.

Equated 9-month (NCES convention):
  9_10 outlay as is, 11_12 outlay x 9/11 (= 0.8182)
  2012-2015: average weighted monthly salary x 9 x n (exactly NCES's method)
  2016+:     NCES's own equated outlays (saeq9o*)

Layouts (year -> source)
  1980        sal1980_a   arank 1-6 (9-month) / 8-13 (12-month); numm salm tenm numw salw tenw
  1984-85     sal19xx_a   same, keyed by `line`; saa1-6
  1987-1998   wide files, one row per institution; columns located by dictionary label
              "<rank> <men|women> <9/10|11/12>[-]month, <tenured|total|salary outlays>"
  1999        sal1999_a   contract x arank rows (+ tenuredm/w)
  2001        sal2001_a_s contract x arank, where arank encodes sex (1-6 men, 8-13 women)
  2002-2011   sal20xx_a   contract x arank rows; tenure from sal20xx_faculty (2006-2011;
              not collected 2001-02 to 2004-05)
  2012-2024   sal20xx_is  rank rows with contract-month columns; no tenure
  2000, 1986, 1988 -- no salary file published by IPEDS
"""
from __future__ import annotations

import re

import pandas as pd

from .. import load, tables, variables

RANKS = ["prof", "assoc", "asst", "instr", "lect", "norank"]
KEY = ["year", "unitid", "rank", "contract", "sex"]
EQ9 = {"9_10": 1.0, "11_12": 9 / 11}


def _f(s) -> pd.Series:
    return pd.Series(s).astype("Float64").fillna(0)


def _rank_rows(d, rank_col, men, women):
    """1980-85 layout: rank code 1-6 = 9-month, 8-13 = 12-month."""
    a = pd.to_numeric(d[rank_col], errors="coerce")
    rank = a.map({**{i: RANKS[i - 1] for i in range(1, 7)}, **{i: RANKS[i - 8] for i in range(8, 14)}})
    contract = a.map(lambda x: "9_10" if 1 <= x <= 6 else ("11_12" if 8 <= x <= 13 else None))
    out = []
    for sex, (n, s, t) in (("men", men), ("women", women)):
        out.append(pd.DataFrame({"unitid": d.unitid, "rank": rank, "contract": contract, "sex": sex,
                                 "n_faculty": _f(d[n]), "salary_outlay": _f(d[s]), "n_tenured": _f(d[t])}))
    return pd.concat(out).dropna(subset=["rank", "contract"])


_R = {"professors": "prof", "associate professors": "assoc", "assistant professors": "asst",
      "instructors": "instr", "lecturers": "lect", "no academic rank": "norank"}
_M = {"total": "n_faculty", "salary outlays": "salary_outlay", "tenured": "n_tenured"}
_PAT = re.compile(r"^(professors|associate professors|assistant professors|instructors|lecturers|"
                  r"no academic rank)\s+(men|women)\s+(9/10|11/12)\s*-?\s*month,?\s*(.*)$", re.I)


def _wide(year, table):
    d = load(year, table)
    v = variables()
    v = v[(v.year == year) & (v.table == table)]
    spec = []
    for var, lab in zip(v.varname, v.label):
        m = _PAT.match(str(lab).strip())
        if m and m.group(4).strip().lower() in _M and var in d:
            spec.append((var, _R[m.group(1).lower()], m.group(2).lower(),
                         "9_10" if m.group(3) == "9/10" else "11_12", _M[m.group(4).strip().lower()]))
    spec = pd.DataFrame(spec, columns=["var", "rank", "sex", "contract", "measure"])
    long = d.melt(id_vars="unitid", value_vars=list(spec["var"]), var_name="var", value_name="v")
    long = long.merge(spec, on="var")
    long["v"] = long["v"].astype("Float64").fillna(0)
    return long.pivot_table(index=["unitid", "rank", "contract", "sex"], columns="measure",
                            values="v", aggfunc="sum").reset_index()


def _long_rows(year, table, fac_table=None):
    """1999, 2002-2011: contract (1 = 9/10, 2 = 11/12) x arank (1-6) rows."""
    d = load(year, table)
    d = d[d.contract.isin([1, 2]) & d.arank.between(1, 6)]
    out = []
    for sex, s in (("men", "m"), ("women", "w")):
        a = pd.DataFrame({"unitid": d.unitid, "arank": d.arank, "contract": d.contract, "sex": sex,
                          "n_faculty": _f(d[f"empcnt{s}"]), "salary_outlay": _f(d[f"outlay{s}"])})
        if f"tenured{s}" in d:
            a["n_tenured"] = _f(d[f"tenured{s}"])
        elif fac_table:
            t = load(year, fac_table)
            t = t[t.contract.isin([1, 2]) & t.arank.between(1, 6)]
            b = pd.DataFrame({"unitid": t.unitid, "arank": t.arank, "contract": t.contract, "sex": sex,
                              "n_tenured": _f(t[f"tenure{s}"])})
            a = a.merge(b, on=["unitid", "arank", "contract", "sex"], how="left")
        else:
            a["n_tenured"] = pd.NA
        out.append(a)
    x = pd.concat(out)
    x["rank"] = x.arank.map(lambda i: RANKS[int(i) - 1])
    x["contract"] = x.contract.map({1: "9_10", 2: "11_12"})
    return x.drop(columns="arank")


def _y2001(table):
    d = load(2001, table)
    d = d[d.contract.isin([1, 2])]
    a = d.arank
    sex = a.map(lambda i: "men" if 1 <= i <= 6 else ("women" if 8 <= i <= 13 else None))
    rank = a.map(lambda i: RANKS[i - 1] if 1 <= i <= 6 else (RANKS[i - 8] if 8 <= i <= 13 else None))
    x = pd.DataFrame({"unitid": d.unitid, "rank": rank, "sex": sex,
                      "contract": d.contract.map({1: "9_10", 2: "11_12"}),
                      "n_faculty": _f(d.empcount), "salary_outlay": _f(d.outlays), "n_tenured": pd.NA})
    return x.dropna(subset=["rank", "sex"])


def _is(year, table):
    d = load(year, table)
    d = d[d.arank.between(1, 6)]
    rank = d.arank.map(lambda i: RANKS[int(i) - 1]).values
    out = []
    for sex, s in (("men", "m"), ("women", "w")):
        if f"sa09mo{s}" in d:   # 2016+: outlays by contract month
            for contract, months in (("9_10", ("09", "10")), ("11_12", ("11", "12"))):
                n = sum(_f(d[f"sa{m}mc{s}"]).values for m in months)
                o = sum(_f(d[f"sa{m}mo{s}"]).values for m in months)
                out.append(pd.DataFrame({"unitid": d.unitid.values, "rank": rank, "contract": contract,
                                         "sex": sex, "n_faculty": n, "salary_outlay": o,
                                         "outlay_eq9": o * EQ9[contract], "n_tenured": pd.NA}))
        else:                   # 2012-2015: outlays only as 9-12 month total
            n = sum(_f(d[f"sa{m}mc{s}"]).values for m in ("09", "10", "11", "12"))
            out.append(pd.DataFrame({"unitid": d.unitid.values, "rank": rank, "contract": "9_12", "sex": sex,
                                     "n_faculty": n, "salary_outlay": _f(d[f"saoutl{s}"]).values,
                                     "outlay_eq9": (_f(d[f"saavmn{s}"]) * 9).values * n, "n_tenured": pd.NA}))
    x = pd.concat(out)
    # 2016+: prefer NCES's own equated outlays, allocated to contract rows
    if "saeq9om" in d:
        eq = pd.concat([pd.DataFrame({"unitid": d.unitid.values, "rank": rank, "sex": "men",
                                      "nces_eq9": _f(d.saeq9om).values}),
                        pd.DataFrame({"unitid": d.unitid.values, "rank": rank, "sex": "women",
                                      "nces_eq9": _f(d.saeq9ow).values})])
        tot = x.groupby(["unitid", "rank", "sex"])["outlay_eq9"].transform("sum")
        x = x.merge(eq, on=["unitid", "rank", "sex"], how="left")
        share = (x.outlay_eq9 / tot.values).where(tot.values > 0, 0)
        x["outlay_eq9"] = (x["nces_eq9"] * share).fillna(x.outlay_eq9)
        x = x.drop(columns="nces_eq9")
    return x


def sources() -> list[tuple[int, str]]:
    t = tables()
    t = t[t.component == "SAL"]
    return sorted((int(y), n) for y, n in zip(t.year, t.table))


def _year(year: int) -> pd.DataFrame | None:
    names = {n for y, n in sources() if y == year}
    pick = lambda pat: next((n for n in sorted(names) if re.fullmatch(pat, n)), None)
    if year == 1980:
        return _rank_rows(load(1980, "sal1980_a"), "arank", ("numm", "salm", "tenm"), ("numw", "salw", "tenw"))
    if year in (1984, 1985):
        t = pick(r"sal\d{4}_a")
        return _rank_rows(load(year, t), "line", ("saa1", "saa2", "saa3"), ("saa4", "saa5", "saa6"))
    if 1987 <= year <= 1998:
        t = pick(r"sal\d{2,4}_a(_1)?")
        return _wide(year, t) if t else None
    if year == 2001:
        return _y2001(pick(r"sal2001_a(_s)?"))
    if year == 1999 or 2002 <= year <= 2011:
        return _long_rows(year, pick(r"sal\d{4}_a"), pick(r"sal\d{4}_faculty"))
    if year >= 2012:
        t = pick(r"sal\d{4}_is")
        return _is(year, t) if t else None
    return None


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    parts = []
    for year in sorted({y for y, _ in sources()}):
        x = _year(year)
        if x is not None and len(x):
            parts.append(x.assign(year=year))
    x = pd.concat(parts, ignore_index=True)
    for c in ["n_faculty", "salary_outlay", "n_tenured", "outlay_eq9"]:
        if c not in x:
            x[c] = pd.NA
        x[c] = x[c].astype("Float64")
    eq = x.contract.map(EQ9).astype("Float64")
    x["outlay_eq9"] = x.outlay_eq9.fillna(x.salary_outlay * eq)
    x = x[(x.n_faculty > 0) | (x.salary_outlay > 0)]
    x["rank"] = pd.Categorical(x["rank"], RANKS)
    x = x[KEY + ["n_faculty", "salary_outlay", "outlay_eq9", "n_tenured"]].sort_values(KEY).reset_index(drop=True)
    return x, _qa(x)


def equated_9month(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Average salary equated to a 9-month basis, grouped by `by`."""
    g = df.groupby(by, observed=True).agg(n_faculty=("n_faculty", "sum"), outlay_eq9=("outlay_eq9", "sum"))
    g["avg_salary_eq9"] = g.outlay_eq9 / g.n_faculty
    return g.reset_index()


def _qa(x: pd.DataFrame) -> pd.DataFrame:
    """Harmonized counts vs institution-reported total rows; NCES equated averages vs ours."""
    rows = []
    hy = x.groupby("year").n_faculty.sum()
    for year, t in sources():
        try:
            d = load(year, t)
        except Exception:
            continue
        rep = None
        if t == "sal1980_a" or (year in (1984, 1985) and t.endswith("_a")):
            k = "arank" if year == 1980 else "line"
            tot = d[pd.to_numeric(d[k], errors="coerce").isin([7, 14])]
            m, w = ("numm", "numw") if year == 1980 else ("saa1", "saa4")
            rep = float(tot[m].fillna(0).sum() + tot[w].fillna(0).sum())
        elif "empcntt" in d and "contract" in d and t.endswith("_a"):
            rep = float(d[d.contract.isin([1, 2]) & (d.arank == 7)].empcntt.fillna(0).sum())
        elif t == "sal2001_a_s":
            rep = float(d[d.contract.isin([1, 2]) & (d.arank == 15)].empcount.fillna(0).sum())
        elif "satotlt" in d and t.endswith("_is"):
            rep = float(d[d.arank == 7].satotlt.fillna(0).sum())
        if rep is not None:
            rows.append({"year": year, "table": t, "reported_total": rep, "harmonized": float(hy.get(year, 0))})
        if "contract" in d and "outlayt" in d and t.endswith("_a") and (d.contract == 4).any():
            eq = d[(d.contract == 4) & (d.arank == 7)]
            ours = equated_9month(x[x.year == year], ["year"])
            if len(ours) and eq.empcntt.sum() > 0:
                rows.append({"year": year, "table": t + " (NCES equated avg vs ours)",
                             "reported_total": float(eq.outlayt.sum() / eq.empcntt.sum()),
                             "harmonized": float(ours.avg_salary_eq9.iloc[0])})
    q = pd.DataFrame(rows)
    q["ratio"] = q.harmonized / q.reported_total
    return q
