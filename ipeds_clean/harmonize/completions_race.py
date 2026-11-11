"""Completions by race/ethnicity: unitid x year x award_level x cip2020_2 x race x sex.

Coverage: 1985, 1987, 1989-2025. (1980, 1984, 1986, 1988 carry totals by sex only;
race was collected in odd years until 1989.) 1985-1994: 2-digit race files, allocated
to CIP-2020 families as described for 1990 below; 1995+: 6-digit files.
Field detail is the 2-digit CIP-2020 family because 1990 race data exist only at
2-digit CIP-85.

Per year
  2000  c2000_a, 6-digit CIP-1990, crace01-14 (old categories incl. unknown)
  2010  c2010_a, 6-digit CIP-2010. Transition year: institutions could report old
        or new categories. Uses NCES's derived dvc* variables (old+new combined)
        for black/aian/api/hisp/white, plus cnral, c2mor, cunkn.
  2020  c2020_a, new categories; api = Asian + NHPI.
  1990  c8990re: 2-digit CIP-85 families (xx.0000) plus ~10 separately listed
        6-digit first-professional codes (18.1001 medicine, 22.0101 law, ...).
        `bal_m/bal_w` = total minus race detail (race not reported) -> unknown.
        CIP-85 families don't map 1:1 to CIP-2020 families (06/07 -> 52,
        17/18 -> 51, part of 02 -> 26 ...), so each institution's race counts
        for family F are allocated across CIP-2020 families using THAT
        institution's own 6-digit distribution for F at that award level
        (c8990cip through the CIP chain); national distribution as fallback.
        Counts are therefore fractional for 1990 (`alloc` column says how).

First majors only; grand-total rows dropped; where reported totals exceed the
field detail, residual rows with cip2020_2 = NA keep level totals complete.
"""
from __future__ import annotations

import pandas as pd

from .. import load
from .cip_chain import build_chain
from .completions import AWLEVEL_MAP

RACES = ["nonres", "black", "aian", "api", "hisp", "white", "two_more", "unknown"]
OLD = {"nonres": (1, 2), "black": (3, 4), "aian": (5, 6), "api": (7, 8),
       "hisp": (9, 10), "white": (11, 12), "unknown": (13, 14)}
NEW_DV = {"nonres": ["cnral"], "black": ["dvcbk"], "aian": ["dvcai"], "api": ["dvcap"],
          "hisp": ["dvchs"], "white": ["dvcwh"], "two_more": ["c2mor"], "unknown": ["cunkn"]}   # 2008-2010
NEW_2011 = {"nonres": ["cnral"], "black": ["cbkaa"], "aian": ["caian"], "api": ["casia", "cnhpi"],
            "hisp": ["chisp"], "white": ["cwhit"], "two_more": ["c2mor"], "unknown": ["cunkn"]}
KEY = ["year", "unitid", "award_level", "cip2020_2", "race", "sex"]


def _melt(d: pd.DataFrame, year: int, id_cols: list[str]) -> pd.DataFrame:
    """Race x sex long rows. unknown = crace13/14 + balance (race not reported) where
    present; files with neither (1985, 1987, 1989) get unknown = total - race detail."""
    parts = []
    f = lambda c: d[c].astype("Float64").fillna(0) if c in d else 0
    if year >= 2008:
        scheme = NEW_DV if year <= 2010 else NEW_2011
        for race, stems in scheme.items():
            for sex, suf in (("men", "m"), ("women", "w")):
                v = sum(f(f"{st}{suf}") for st in stems)
                parts.append(d[id_cols].assign(race=race, sex=sex, n=v))
    else:
        for sex, (tot, bal) in (("men", ("crace15", ("bal_m", "balmen"))), ("women", ("crace16", ("bal_w", "balwomen")))):
            known = 0
            for race, (m, w) in OLD.items():
                if race == "unknown":
                    continue
                v = f(f"crace{(m if sex == 'men' else w):02d}")
                known = known + v
                parts.append(d[id_cols].assign(race=race, sex=sex, n=v))
            i = 13 if sex == "men" else 14
            if f"crace{i}" in d or any(b in d for b in bal):
                unk = f(f"crace{i}") + sum(f(b) for b in bal)
            else:
                unk = f(tot) - known
            parts.append(d[id_cols].assign(race="unknown", sex=sex, n=unk))
    return pd.concat(parts, ignore_index=True)


def _six_digit_year(year: int, table: str, vintage: str) -> tuple[pd.DataFrame, dict]:
    d = load(year, table)
    if "majornum" in d:
        d = d[d.majornum.eq(1)]
    d = d.assign(award_level=[AWLEVEL_MAP[(year, table)].get(a) for a in d.awlevel])
    tot = d[d.cipcode.str.startswith("99")]
    det = d[~d.cipcode.str.startswith("99")]
    chain, _ = build_chain(vintage, det.cipcode.unique())
    chain = chain.assign(cip2020_2=chain.cip2020.astype("string").str[:2])
    m = det.merge(chain[["orig_code", "cip2020_2", "share"]], left_on="cipcode", right_on="orig_code")
    long = _melt(m, year, ["unitid", "award_level", "cip2020_2", "share"])
    long["n"] = long["n"] * long["share"]
    long = long.assign(year=year, alloc="direct")
    resid = _residual(tot, long, year)
    return pd.concat([long, resid], ignore_index=True), {}


def _residual(tot: pd.DataFrame, long: pd.DataFrame, year: int) -> pd.DataFrame:
    """Reported (99-row) race totals minus field detail, per unitid x level x race x sex."""
    t = _melt(tot, year, ["unitid", "award_level"]).groupby(["unitid", "award_level", "race", "sex"])["n"].sum()
    s = long.groupby(["unitid", "award_level", "race", "sex"])["n"].sum()
    g = (t - s.reindex(t.index).fillna(0))
    g = g[g > 0.5].rename("n").reset_index()
    return g.assign(year=year, cip2020_2=pd.NA, alloc="residual_unallocated")


def _two_digit(year: int, re_table: str, cip_table: str, vintage: str) -> pd.DataFrame:
    """1985, 1987, 1989-1994: race only at 2-digit CIP; allocate to CIP-2020 families."""
    from .cip_chain import norm_cip80
    norm = (lambda s: s.map(norm_cip80).astype("string")) if vintage == "CIP80" else (lambda s: s)
    re_ = load(year, re_table)
    re_["cipcode"] = norm(re_["cipcode"])
    re_ = re_.assign(award_level=[AWLEVEL_MAP[(year, cip_table)].get(a) for a in re_.awlevel])
    tot = re_[re_.cipcode.str.startswith("99")]
    det = re_[~re_.cipcode.str.startswith("99")]
    listed = set(c for c in det.cipcode.unique() if not c.endswith(".0000"))

    # allocation key for each 6-digit c8990cip code: itself if separately listed in
    # c8990re, else its family "FF.0000"
    cip = load(year, cip_table)
    cip["cipcode"] = norm(cip["cipcode"])
    cip = cip[~cip.cipcode.str.startswith("99")]
    chain, _ = build_chain(vintage, cip.cipcode.unique())
    chain = chain.assign(cip2020_2=chain.cip2020.astype("string").str[:2])
    cip = cip.merge(chain[["orig_code", "cip2020_2", "share"]], left_on="cipcode", right_on="orig_code")
    cip["w"] = (cip.crace15.fillna(0) + cip.crace16.fillna(0)) * cip.share
    cip["re_code"] = cip.cipcode.where(cip.cipcode.isin(listed), cip.cipcode.str[:2] + ".0000")
    # 95.0000 (undesignated) has no family
    cip["cip2020_2"] = cip.cip2020_2.where(~cip.cipcode.str.startswith("95"), pd.NA)

    inst = cip.groupby(["unitid", "awlevel", "re_code", "cip2020_2"], dropna=False)["w"].sum()
    inst = (inst / inst.groupby(level=[0, 1, 2]).transform("sum")).rename("p").reset_index()
    nat = cip.groupby(["awlevel", "re_code", "cip2020_2"], dropna=False)["w"].sum()
    nat = (nat / nat.groupby(level=[0, 1]).transform("sum")).rename("p").reset_index()
    fam = cip.groupby(["re_code", "cip2020_2"], dropna=False)["w"].sum()
    fam = (fam / fam.groupby(level=0).transform("sum")).rename("p").reset_index()

    det = det.rename(columns={"cipcode": "re_code"})
    a = det.merge(inst, on=["unitid", "awlevel", "re_code"], how="inner").assign(alloc="institution")
    rest = det[~det.set_index(["unitid", "awlevel", "re_code"]).index.isin(
        a.set_index(["unitid", "awlevel", "re_code"]).index)]
    b = rest.merge(nat, on=["awlevel", "re_code"], how="inner").assign(alloc="national_by_level")
    rest2 = rest[~rest.set_index(["awlevel", "re_code"]).index.isin(nat.set_index(["awlevel", "re_code"]).index)]
    c = rest2.merge(fam, on="re_code", how="left").assign(alloc="national_any_level")
    c["p"] = c["p"].fillna(1.0)
    m = pd.concat([a, b, c], ignore_index=True)
    long = _melt(m, year, ["unitid", "award_level", "cip2020_2", "p", "alloc"])
    long["n"] = long["n"] * long["p"]
    long = long.drop(columns="p").assign(year=year)
    resid = _residual(tot, long, year)
    return pd.concat([long, resid], ignore_index=True)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    import re
    from .. import tables
    from .completions import sources, vintage_for
    t = tables()
    names = set(zip(t.year, t.table))
    parts = []
    for year, table, vin in sources():
        if year >= 1995:                                   # 6-digit files carry race
            parts.append(_six_digit_year(year, table, vin)[0])
        else:
            re_t = next((n for (y, n) in names if y == year and re.fullmatch(r"c(\d{4}_re|8990re)", n)), None)
            if re_t:
                parts.append(_two_digit(year, re_t, table, vin))
    x = pd.concat(parts, ignore_index=True)
    x = (x.groupby(KEY + ["alloc"], dropna=False, observed=True)["n"].sum().reset_index())
    x = x[x.n.abs() > 1e-9]
    x["race"] = pd.Categorical(x.race, RACES)
    x["n"] = x["n"].astype("Float64")
    # QA vs harmonized completions totals by year x level
    from . import completions as C  # noqa: F401  (panel built separately; compared in __main__)
    qa = x.groupby(["year", "award_level"], observed=True)["n"].sum().rename("race_file_total").reset_index()
    return x.sort_values(KEY).reset_index(drop=True), qa
