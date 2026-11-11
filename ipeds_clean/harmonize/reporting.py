"""Who reported for whom, response/imputation status, and mergers.

reporting.parquet  year x unitid x component
  component   c (completions), ef (fall enrollment), e12 (12-month enrollment), f (finance),
              gr, gr2 (graduation rates 150% / 200%), sfa, hr (human resources; also s, sa, eap
              in 1987-2004), adm, al (libraries), om (outcome measures), ic
  prch        1 parent record (includes data of children)
              2 child record (data reported with the parent)
              3 partial child (reports part of the data; rest with parent)
              4 child, data included with a non-postsecondary entity
              5 partial child, rest with a non-postsecondary entity
              6 partial parent/child (finance, 2020s)
  parent_unitid   unitid of the reporting parent (idx_* / unitidx)
  status      1 respondent, 2 partial respondent imputed, 4 nonrespondent imputed,
              5 nonrespondent not imputed  (1986-97 rstatus 3 -> 5)
  imputed     status in (2, 4)
  imp_method  1 carry forward, 2 nearest neighbor, 4 mixed (2000+)

  Sources: 1986-1997 component header files (*_ic, *_hdr: parchild, unitidx, rstatus);
  1998-2003 directory headers (prch_*, idx_*, stat_*, imp_*); 2004+ flags files.

entities.parquet  unitid -> successor_unitid for institutions merged into another
  (directory `newid`, followed through chains), with the last year the unitid appears.

Helpers
  rollup_children(df, component, value_cols): add each child's values into its parent
  consistent_entity(df, value_cols): re-key merged institutions to their final successor
"""
from __future__ import annotations

import re

import pandas as pd

from .. import load, tables

_PREFIX = {"c": "c", "ef": "ef", "f": "f", "s": "hr", "sal": "sa", "ic": "ic", "res": "ef_res"}


def _num(s):
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def build() -> pd.DataFrame:
    t = tables()
    rows = []
    for year, tab in zip(t.year, t.table):
        year = int(year)
        if year < 1986:
            continue
        try:
            v = load(year, tab, None)
        except Exception:
            continue
        cols = set(v.columns)
        if "parchild" in cols and year <= 1997:
            m = re.match(r"^([a-z]+?)(\d|_)", tab)
            comp = _PREFIX.get(m.group(1) if m else "", None)
            if comp is None:
                continue
            st = _num(v["rstatus"]) if "rstatus" in cols else pd.Series(pd.NA, index=v.index, dtype="Int64")
            rows.append(pd.DataFrame({"year": year, "unitid": v.unitid, "component": comp,
                                      "prch": _num(v["parchild"]),
                                      "parent_unitid": _num(v["unitidx"]) if "unitidx" in cols else pd.NA,
                                      "status": st.replace({3: 5}), "imp_method": pd.NA, "source": tab}))
        prch_cols = [c for c in cols if c.startswith("prch_")]
        if prch_cols and (tab.startswith(("flags", "hd", "fa")) or tab.endswith(("_hd", "hdac"))):
            for pc in prch_cols:
                comp = pc[5:]
                g = lambda k: _num(v[f"{k}_{comp}"]) if f"{k}_{comp}" in cols else pd.Series(pd.NA, index=v.index, dtype="Int64")
                rows.append(pd.DataFrame({"year": year, "unitid": v.unitid, "component": comp,
                                          "prch": _num(v[pc]), "parent_unitid": g("idx"),
                                          "status": g("stat"), "imp_method": g("imp"), "source": tab}))
    x = pd.concat(rows, ignore_index=True)
    for c in ["prch", "parent_unitid", "status", "imp_method"]:
        x[c] = pd.to_numeric(x[c], errors="coerce").astype("Int64")
        x[c] = x[c].mask(x[c] < 0)          # -2 not applicable, -9 not active
    x["component"] = x.component.replace({"s": "hr", "eap": "hr"}).where(~x.year.ge(2005) | ~x.component.isin(["s", "sa", "eap"]), "hr")
    # one row per year x unitid x component (flags preferred over headers)
    x["_pri"] = x.source.str.startswith("flags").astype(int)
    x = x.sort_values("_pri", ascending=False).drop_duplicates(["year", "unitid", "component"]).drop(columns="_pri")
    x["imputed"] = x.status.isin([2, 4]).astype("boolean").where(x.status.notna())
    x["parent_unitid"] = x.parent_unitid.where(x.parent_unitid != x.unitid)
    return x.sort_values(["year", "unitid", "component"]).reset_index(drop=True)


def entities(directory: pd.DataFrame) -> pd.DataFrame:
    """unitid -> final successor via directory `newid` (merged institutions)."""
    m = directory.dropna(subset=["newid"])
    m = m[m.newid != m.unitid]
    first = m.sort_values("year").drop_duplicates("unitid")[["unitid", "newid", "year"]]
    succ = dict(zip(first.unitid, first.newid))

    def final(u, seen=()):
        n = succ.get(u)
        return u if n is None or n in seen or len(seen) > 20 else final(n, seen + (u,))

    last = directory.groupby("unitid").year.max()
    out = pd.DataFrame({"unitid": list(succ)})
    out["successor_unitid"] = out.unitid.map(lambda u: final(u)).astype("Int64")
    out["newid_first_seen"] = out.unitid.map(dict(zip(first.unitid, first.year))).astype("Int64")
    out["last_year_present"] = out.unitid.map(last).astype("Int64")
    out["chain_length"] = out.unitid.map(lambda u: len(_chain(u, succ)))
    return out.sort_values("unitid").reset_index(drop=True)


def _chain(u, succ):
    seen = [u]
    while succ.get(seen[-1]) is not None and succ[seen[-1]] not in seen and len(seen) < 20:
        seen.append(succ[seen[-1]])
    return seen[1:]


def rollup_children(df: pd.DataFrame, reporting: pd.DataFrame, component: str,
                    value_cols: list[str], keys: list[str] | None = None) -> pd.DataFrame:
    """Re-key child records (prch 2/3) to their parent and sum value_cols.

    Use when comparing institutions whose reporting structure changes over time: the parent
    then always represents parent + children. `keys` are the other grouping columns."""
    keys = keys or []
    r = reporting[(reporting.component == component) & reporting.prch.isin([2, 3]) & reporting.parent_unitid.notna()]
    m = dict(zip(zip(r.year, r.unitid), r.parent_unitid))
    out = df.copy()
    out["unitid"] = [m.get((y, u), u) for y, u in zip(out.year, out.unitid)]
    return out.groupby(["year", "unitid"] + keys, as_index=False, observed=True)[value_cols].sum(min_count=1)


def consistent_entity(df: pd.DataFrame, entities_df: pd.DataFrame, value_cols: list[str],
                      keys: list[str] | None = None) -> pd.DataFrame:
    """Re-key merged institutions to their final successor in every year and sum value_cols,
    so a merger doesn't look like a jump in the successor's series."""
    keys = keys or []
    m = dict(zip(entities_df.unitid, entities_df.successor_unitid))
    out = df.copy()
    out["unitid"] = out.unitid.map(lambda u: m.get(u, u)).astype("Int64")
    return out.groupby(["year", "unitid"] + keys, as_index=False, observed=True)[value_cols].sum(min_count=1)
