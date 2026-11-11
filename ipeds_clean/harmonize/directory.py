"""Harmonized institution directory: one row per unitid x year.

Harmonized fields
  control   1 public, 2 private nonprofit, 3 private for-profit
  level     1 four-year or above, 2 two-year, 3 less-than-two-year
  sector    1-9, standard IPEDS sector = (control, level) grid; 0 admin unit
  degree_granting  bool
  stabbr, fips, region (BEA/OBE region 0-9), instnm, city, hbcu, tribal

Year-specific derivations (column `derivation` records which were used):
  1980 (HEGIS ic1980): no for-profit control code. control from `control` +
       `affil` (affil 25 "Organized as profit making" -> for-profit; affil 1x
       state/local -> public). level from `type` (university/other 4-yr/4-yr
       branch -> 4-yr; 2-yr and 2-yr branches -> 2-yr; "none of the above" ->
       from hloffer). HEGIS covered only institutions of higher education, so
       degree_granting = hloffer in {03..08}. fips from stabbr.
  1990 (ic90hd + ic90abce): control/iclevel/sector as reported (0 = admin unit
       -> NA). degree_granting = offers associate's or higher (ic90abce level3,
       5, 7, 9, 10).
  2000 (fa2000hd), 2010/2020 (hd*): reported control, iclevel, sector, deggrant.

Institutions that report 1980 completions but are missing from ic1980 (about 3%)
get attributes from the 1990 directory, flagged derivation="filled_from_1990".
"""
from __future__ import annotations

import pandas as pd

from .. import load

STATE_FIPS = None  # built lazily from 1990+ files


def _fips_lookup() -> dict[str, int]:
    d = pd.concat([load(y, t, ["stabbr", "fips"]) for y, t in
                   [(1990, "ic90hd"), (2000, "fa2000hd"), (2010, "hd2010"), (2020, "hd2020")]])
    d = d.dropna().drop_duplicates()
    return d.groupby("stabbr")["fips"].agg(lambda s: s.mode().iloc[0]).to_dict()


def _sector(control: pd.Series, level: pd.Series) -> pd.Series:
    s = (level - 1) * 3 + control
    return s.where(control.notna() & level.notna()).astype("Int64")


def _na_neg(s: pd.Series) -> pd.Series:
    s = s.astype("Int64")
    return s.mask(s < 0)


def _hegis(year: int, table: str) -> pd.DataFrame:
    """1980, 1984, 1985: HEGIS coding (control 0/1/2 + affil; level from iclevel/type/hloffer)."""
    d = load(year, table)
    num = lambda c: pd.to_numeric(d[c], errors="coerce") if c in d else pd.Series(pd.NA, index=d.index)
    affil = d["affil"].astype("string").str.zfill(2).fillna("")
    public = (affil.str.startswith("1") & ~affil.eq("10")).astype(bool)
    forprofit = affil.eq("25").astype(bool)
    ctrl = pd.Series(pd.NA, index=d.index, dtype="Int64")
    c = num("control").fillna(-9).astype(int)
    ctrl[c.eq(1)] = 1
    ctrl[c.eq(2)] = 2
    ctrl[c.eq(2) & forprofit] = 3
    combo = c.eq(0)
    ctrl[combo & public] = 1
    ctrl[combo & ~public] = 2
    ctrl[combo & forprofit] = 3

    hl = d["hloffer"].astype("string").str.lstrip("0").fillna("")   # HEGIS: 3 = 1-<4 yrs, 4 = bacc, ... 8 = doctorate
    typ = num("type")
    lvl = typ.map({1: 1, 2: 1, 4: 1, 3: 2, 5: 2, 6: 2}).astype("Int64")
    if "iclevel" in d:
        lvl = num("iclevel").map({1: 1, 2: 2}).astype("Int64").fillna(lvl)
    none = lvl.isna()
    lvl[none & hl.isin(["4", "5", "6", "7", "8"])] = 1
    lvl[none & hl.eq("3")] = 2
    return pd.DataFrame({
        "year": year, "unitid": d["unitid"], "instnm": d["instnm"], "city": d["city"],
        "stabbr": d["stabbr"], "fips": d["stabbr"].map(_fips_lookup()).astype("Int64"),
        "region": pd.to_numeric(d["obereg"], errors="coerce").astype("Int64"),
        "control": ctrl, "level": lvl,
        "degree_granting": hl.isin(["3", "4", "5", "6", "7", "8"]).astype("boolean"),
        "hbcu": pd.NA, "tribal": pd.NA,
        "derivation": "HEGIS: control from control+affil; level from iclevel/type/hloffer; degree_granting from hloffer",
    })


def _ipeds_early(year: int, table: str, awarded: set) -> pd.DataFrame:
    """1986-1999 IC header files: control 1-3, iclevel 1-3 (0/-1 = no response), no deggrant item.

    degree_granting = highest offering is an associate's or higher (hloffer 3, 5-9) OR the
    institution awarded associate's-or-higher degrees that year (Completions). hloffer 4
    (a 2-<4-year certificate) ranks above the associate's in this coding, so hloffer
    alone cannot settle those cases.
    """
    d = load(year, table).drop_duplicates("unitid")
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype("Int64") if c in d else pd.Series(pd.NA, index=d.index, dtype="Int64")
    ctrl = num("control").where(lambda s: s.between(1, 3))
    lvl = num("iclevel").where(lambda s: s.between(1, 3))
    hl = num("hloffer")
    deg = (hl.isin([3, 5, 6, 7, 8, 9]).fillna(False) | d["unitid"].isin(awarded)).astype("boolean")
    yn = lambda c: num(c).map({1: True, 2: False}).astype("boolean") if c in d else pd.NA
    return pd.DataFrame({
        "year": year, "unitid": d["unitid"], "instnm": d["instnm"], "city": d["city"],
        "stabbr": d["stabbr"], "fips": _na_neg(num("fips")) if "fips" in d else d["stabbr"].map(_fips_lookup()).astype("Int64"),
        "region": _na_neg(num("obereg")), "control": ctrl, "level": lvl, "degree_granting": deg,
        "hbcu": yn("hbcu"), "tribal": yn("tribal"),
        "newid": _na_neg(num("newid")) if "newid" in d else pd.NA,
        "opeid": d["opeid"] if "opeid" in d else pd.NA,
        "derivation": "1986-1999: degree_granting = hloffer associate+ or awarded associate+ degrees",
    })


def _hd(year: int, table: str) -> pd.DataFrame:
    d = load(year, table)
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype("Int64")
    return pd.DataFrame({
        "year": year, "unitid": d["unitid"], "instnm": d["instnm"], "city": d["city"],
        "stabbr": d["stabbr"], "fips": _na_neg(num("fips")), "region": _na_neg(num("obereg")),
        "control": _na_neg(num("control")), "level": _na_neg(num("iclevel")),
        "degree_granting": num("deggrant").map({1: True, 2: False, 3: False, 4: False}).astype("boolean"),
        "hbcu": num("hbcu").map({1: True, 2: False}).astype("boolean"),
        "tribal": num("tribal").map({1: True, 2: False}).astype("boolean"),
        "newid": _na_neg(num("newid")) if "newid" in d else pd.NA,
        "opeid": d["opeid"] if "opeid" in d else pd.NA,
        "derivation": "reported",
    })


# year -> directory table (1986-1999 header files vary in name)
EARLY = {1986: "ic1986_a", 1987: "ic1987_a", 1988: "ic1988_a", 1989: "ic1989_a", 1990: "ic90hd",
         1991: "ic1991_hdr", 1992: "ic1992_a", 1993: "ic1993_a", 1994: "ic1994_a", 1995: "ic9596_a",
         1996: "ic9697_a", 1997: "ic9798_hdr", 1998: "ic98hdac", 1999: "ic99_hd"}


def build(completions: pd.DataFrame | None = None) -> pd.DataFrame:
    """completions: the harmonized completions panel (for 1980 fill-ins and 1986-99 degree_granting)."""
    import re
    from .. import tables
    t = tables()
    have = set(zip(t.year, t.table))
    awarded = {}
    if completions is not None:
        deg = completions[completions.award_level.isin(
            ["assoc", "bach", "master", "pm_cert", "doc_res", "doc_prof"]) & (completions.total > 0)]
        awarded = deg.groupby("year").unitid.agg(set).to_dict()
    parts = []
    for year in sorted({int(y) for y in t.year}):
        if year in (1980, 1984, 1985):
            parts.append(_hegis(year, f"ic{year}"))
        elif year in EARLY and (year, EARLY[year]) in have:
            parts.append(_ipeds_early(year, EARLY[year], awarded.get(year, set())))
        else:
            hd = next((n for n in (f"fa{year}hd", f"hd{year}") if (year, n) in have), None)
            if hd:
                parts.append(_hd(year, hd))
    d = pd.concat(parts, ignore_index=True)
    if completions is not None:   # completions reporters missing from that year's directory
        c80 = set(completions.loc[completions.year == 1980, "unitid"])
        missing = c80 - set(d.loc[d.year == 1980, "unitid"])
        fill = d[(d.year == 1984) & d.unitid.isin(missing)].copy()
        fill["year"], fill["derivation"] = 1980, "filled_from_1984"
        d = pd.concat([d, fill], ignore_index=True)
    d["sector"] = _sector(d["control"], d["level"])
    for c in ["hbcu", "tribal"]:
        d[c] = d[c].astype("boolean")
    d["newid"] = pd.to_numeric(d["newid"], errors="coerce").astype("Int64")
    d["opeid"] = d["opeid"].astype("string")
    d["n_years"] = d.groupby("unitid")["year"].transform("nunique")
    cols = ["year", "unitid", "instnm", "city", "stabbr", "fips", "region", "control", "level",
            "sector", "degree_granting", "hbcu", "tribal", "opeid", "newid", "n_years", "derivation"]
    return d[cols].sort_values(["unitid", "year"]).reset_index(drop=True)


def add_title_iv(d: pd.DataFrame) -> pd.DataFrame:
    """title_iv: institution participates in federal Title IV student aid programs.

    1996-97 opeind in {1 eligible, 2 branch/system office of an eligible institution};
    1998+   opeflag in {1 eligible, 2 branch campus of a participant, 3 deferment only}.
    NA before 1996 (no indicator collected). The Digest of Education Statistics restricts
    most postsecondary totals to Title IV degree-granting institutions from 1996 on."""
    from .. import load
    v = pd.read_csv(__import__("ipeds_clean.config", fromlist=["META_DIR"]).META_DIR / "variables.csv",
                    usecols=["year", "table", "varname"])
    v = v[v.varname.str.lower().isin(["opeind", "opeflag"])]
    parts = []
    for year, g in v.groupby("year"):
        tabs = sorted(g.table.unique(), key=lambda t: (not t.startswith(("hd", "fa")), "hd" not in t, t))
        for tab in tabs:
            var = g.loc[g.table == tab, "varname"].iloc[0]
            x = load(int(year), tab, ["unitid", var])
            code = pd.to_numeric(x[var], errors="coerce")
            ok = {1, 2} if var.lower() == "opeind" else {1, 2, 3}
            parts.append(pd.DataFrame({"year": int(year), "unitid": x.unitid,
                                       "title_iv": code.isin(ok).astype("boolean").where(code.notna())}))
            break
    t4 = pd.concat(parts).drop_duplicates(["year", "unitid"])
    out = d.drop(columns="title_iv", errors="ignore").merge(t4, on=["year", "unitid"], how="left")
    return out


LABELS = {
    "control": {1: "Public", 2: "Private nonprofit", 3: "Private for-profit"},
    "level": {1: "Four-year or above", 2: "Two-year", 3: "Less-than-two-year"},
    "sector": {1: "Public 4-year+", 2: "Private nonprofit 4-year+", 3: "Private for-profit 4-year+",
               4: "Public 2-year", 5: "Private nonprofit 2-year", 6: "Private for-profit 2-year",
               7: "Public <2-year", 8: "Private nonprofit <2-year", 9: "Private for-profit <2-year"},
}


def fill_missing(d: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """Add directory rows for (year, unitid) pairs that appear in a data panel but not in that
    year's directory file, copying the nearest year's record (ties -> earlier year).
    The copied row keeps its attributes and gets derivation = 'filled_from_<year>'."""
    pairs = pairs[["year", "unitid"]].drop_duplicates()
    have = d[["year", "unitid"]].assign(_h=1)
    miss = pairs.merge(have, how="left").query("_h.isna()")[["year", "unitid"]]
    if miss.empty:
        return d
    cand = miss.merge(d.rename(columns={"year": "src_year"}), on="unitid", how="inner")
    cand["dist"] = (cand.src_year - cand.year).abs() * 2 + (cand.src_year > cand.year)
    best = cand.sort_values("dist").drop_duplicates(["year", "unitid"])
    best = best.assign(derivation="filled_from_" + best.src_year.astype(str)).drop(columns=["src_year", "dist"])
    out = pd.concat([d, best[d.columns]], ignore_index=True)
    out["n_years"] = out.groupby("unitid")["year"].transform("nunique")
    return out.sort_values(["unitid", "year"]).reset_index(drop=True)


def add_cn_sample(d: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """Before 1993 NCES surveyed only a SAMPLE of private less-than-2-year institutions, on
    the short "CN" form. Those sample members (unitids ~262000-362999) report Completions /
    Fall Enrollment / Staff but never appear in any directory file. Add them as level = 3
    (less-than-2-year), control unknown (private; nonprofit vs for-profit not recorded),
    with the published sampling weight where available (ef1991_hdr.smplwt)."""
    from .. import load, tables
    pairs = pairs[["year", "unitid"]].drop_duplicates()
    have = d[["year", "unitid"]].assign(_h=1)
    miss = pairs.merge(have, how="left").query("_h.isna() and year < 1993")[["year", "unitid"]]
    if miss.empty:
        return d
    t = tables()
    w = {}
    for y, n in zip(t.year, t.table):
        if y < 1993 and n.endswith(("_hdr", "_ic")):
            try:
                x = load(int(y), n)
            except Exception:
                continue
            if "formrt" in x and "smplwt" in x:
                cn = x[x.formrt.astype("string").eq("CN")]
                w.update({(int(y), u): v for u, v in zip(cn.unitid, cn.smplwt)})
    cn = miss.year.between(1986, 1992)
    rows = miss.assign(control=pd.NA, level=pd.Series(3, index=miss.index).where(cn),
                       degree_granting=pd.Series(False, index=miss.index).where(cn),
                       derivation=pd.Series("no_directory_record", index=miss.index).where(
                           ~cn, "private_lt2yr_sample (CN form; no directory record)"))
    rows["sample_weight"] = [w.get((y, u)) for y, u in zip(rows.year, rows.unitid)]
    out = pd.concat([d, rows], ignore_index=True)
    out["sample_weight"] = pd.to_numeric(out.get("sample_weight"), errors="coerce").astype("Float64")
    out["level"] = out["level"].astype("Int64")
    out["control"] = out["control"].astype("Int64")
    out["degree_granting"] = out["degree_granting"].astype("boolean")
    out["n_years"] = out.groupby("unitid")["year"].transform("nunique")
    return out.sort_values(["unitid", "year"]).reset_index(drop=True)
