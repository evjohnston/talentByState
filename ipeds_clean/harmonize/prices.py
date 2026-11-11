"""Published prices (sticker tuition & fees, room and board, books): unitid x academic year.

`ay` = the fall year of the academic year (1980 -> 1980-81). The 2000/2010/2020
files also report the three prior years' undergraduate prices, so the series has
these academic years:
    1980, 1990, 1998-2000, 2007-2010, 2017-2020
`survey_year` says which file a row came from; `current` marks the file's own year.

Columns (nominal dollars, full-time students, academic year)
  ug_tf_in_district   undergraduate tuition + required fees, in-district (publics; 1990+)
  ug_tf_in_state      in-state (privates: their single price)
  ug_tf_out_state     out-of-state
  grad_tf_in_state, grad_tf_out_state   (current year only)
  room_board          typical room + board charge (room + board; or combined charge)
  room_board_coa      on-campus room & board in the cost-of-attendance block (2000+ only)
  books               books and supplies (1990 = "expenses, books and supplies"; 2000+)

Definitions differ slightly over time:
  * 1980 HEGIS reports "tuition" by control (private: one price; public: in/out of
    state). Whether required fees are included is not stated in the dictionary.
  * 1990: "tuition and required fees for full-time, full-year students".
  * 2000+: published tuition and fees for full-time FIRST-TIME undergraduates
    (chg*ay*). Grad = average tuition + required fees (tuition6+fee6, tuition7+fee7).
  * 2020-21 prices were set during COVID; use 2019-20 (also in the 2020 file) as
    the pre-pandemic point if needed.
"""
from __future__ import annotations

import pandas as pd

from .. import load

COLS = ["ug_tf_in_district", "ug_tf_in_state", "ug_tf_out_state", "grad_tf_in_state",
        "grad_tf_out_state", "room_board", "room_board_coa", "books", "ug_tf_program"]


def _f(s):
    return pd.Series(s).astype("Float64")


def _rb(room, board, combined=None):
    rb = _f(room).add(_f(board), fill_value=0).where(_f(room).notna() | _f(board).notna())
    if combined is not None:
        rb = rb.fillna(_f(combined))
    return rb


def _hegis(year: int, ctrl: pd.Series) -> pd.DataFrame:
    """1980, 1984, 1985: tuition by control (private: one price; public: in/out of state)."""
    d = load(year, f"ic{year}")
    public = d.unitid.map(ctrl).eq(1).fillna(False).values
    g = lambda c: _f(d[c]) if c in d else pd.Series(pd.NA, index=d.index, dtype="Float64")
    priv = g("prtfu")
    return pd.DataFrame({
        "unitid": d.unitid, "ay": year, "survey_year": year, "current": True, "ug_tf_in_district": pd.NA,
        "ug_tf_in_state": g("pbtfui").where(public, priv), "ug_tf_out_state": g("pbtfuo").where(public, priv),
        "grad_tf_in_state": g("pbtfgi").where(public, g("prtfg")),
        "grad_tf_out_state": g("pbtfgo").where(public, g("prtfg")),
        "room_board": _rb(g("roomamt"), g("boardamt")), "room_board_coa": pd.NA, "books": pd.NA,
        "ug_tf_program": pd.NA,
    })


# 1986-1997: (tuition table, room/board table, column map). 1986 numbers its items differently.
EARLY = {1986: ("ic1986_a", "ic1986_a"), 1987: ("ic1987_b", "ic1987_b"), 1988: ("ic1988_a", "ic1988_b"),
         1989: ("ic1989_b", "ic1989_b"), 1990: ("ic90d", "ic90d"), 1991: ("ic1991_d", "ic1991_d"),
         1992: ("ic1992_b", "ic1992_b"), 1993: ("ic1993_b", "ic1993_b"), 1994: ("ic1994_b", "ic1994_b"),
         1995: ("ic9596_b", "ic9596_b"), 1996: ("ic9697_b", "ic9697_b"), 1997: ("ic9798_d", "ic9798_d")}


def _early(year: int) -> pd.DataFrame:
    tt, rt = EARLY[year]
    d = load(year, tt)
    r = load(year, rt, None) if rt != tt else d
    g = lambda df, c: _f(df[c]) if c in df else pd.Series(pd.NA, index=df.index, dtype="Float64")
    if year == 1986:   # tuition1/2 = UG in/out of state, tuition4/5 = grad in/out of state
        cols = {"ug_tf_in_district": None, "ug_tf_in_state": "tuition1", "ug_tf_out_state": "tuition2",
                "grad_tf_in_state": "tuition4", "grad_tf_out_state": "tuition5"}
    else:              # tuition1/2/3 = UG in-district/in-state/out-of-state, 5/6/7 = grad
        cols = {"ug_tf_in_district": "tuition1", "ug_tf_in_state": "tuition2", "ug_tf_out_state": "tuition3",
                "grad_tf_in_state": "tuition6", "grad_tf_out_state": "tuition7"}
    out = pd.DataFrame({"unitid": d.unitid, "ay": year, "survey_year": year, "current": True})
    for k, c in cols.items():
        out[k] = g(d, c) if c else pd.NA
    rb = r[["unitid"]].assign(room_board=_rb(g(r, "roomamt"), g(r, "boardamt")).values,
                              books=g(r, "avgamt1").values)
    out = out.merge(rb, on="unitid", how="left") if rt != tt else out.assign(room_board=rb.room_board.values,
                                                                           books=rb.books.values)
    return out.assign(room_board_coa=pd.NA, ug_tf_program=pd.NA)


def _modern(year: int, ay_table: str, ic_table: str | None, py_table: str | None, offsets: dict[str, int]) -> pd.DataFrame:
    """offsets: column suffix -> academic year (e.g. {'3': 2010, '2': 2009, ...})."""
    a = load(year, ay_table)
    if ic_table:
        m = load(year, ic_table)
        m = m[[c for c in ("unitid", "roomamt", "boardamt", "rmbrdamt") if c in m]]
        a = a.merge(m, on="unitid", how="left")
    rows = []
    g = lambda df, c: _f(df[c]) if c in df else pd.Series(pd.NA, index=df.index, dtype="Float64")
    for suf, ay in offsets.items():
        cur = ay == year
        rows.append(pd.DataFrame({
            "unitid": a.unitid, "ay": ay, "survey_year": year, "current": cur,
            "ug_tf_in_district": g(a, f"chg1ay{suf}"), "ug_tf_in_state": g(a, f"chg2ay{suf}"),
            "ug_tf_out_state": g(a, f"chg3ay{suf}"),
            "grad_tf_in_state": (g(a, "tuition6").add(g(a, "fee6"), fill_value=0).where(g(a, "tuition6").notna())
                                 if cur else pd.NA),
            "grad_tf_out_state": (g(a, "tuition7").add(g(a, "fee7"), fill_value=0).where(g(a, "tuition7").notna())
                                  if cur else pd.NA),
            "room_board": _rb(g(a, "roomamt"), g(a, "boardamt"), g(a, "rmbrdamt")) if cur else pd.NA,
            "room_board_coa": g(a, f"chg5ay{suf}"), "books": g(a, f"chg4ay{suf}"), "ug_tf_program": pd.NA,
        }))
    out = pd.concat(rows, ignore_index=True)
    if py_table:   # program reporters (mostly <2-year): price of the largest program
        p = load(year, py_table)
        prow = []
        for suf, ay in offsets.items():
            if f"chg1py{suf}" in p:
                prow.append(pd.DataFrame({"unitid": p.unitid, "ay": ay, "survey_year": year, "current": ay == year,
                                          "ug_tf_program": g(p, f"chg1py{suf}"), "books": g(p, f"chg4py{suf}"),
                                          "room_board_coa": g(p, f"chg5py{suf}")}))
        if prow:
            out = pd.concat([out] + prow, ignore_index=True)
    return out


def _offsets(year: int, table: str) -> dict[str, int]:
    """Which ay-suffixes a file carries: 0-3 from 2009, 1-3 before (ay3 = the survey year)."""
    from .. import variables
    v = variables()
    names = set(v[(v.year == year) & (v.table == table)].varname)
    return {str(k): year - (3 - k) for k in range(4)
            if any(n.endswith(f"ay{k}") or n.endswith(f"py{k}") for n in names)}


def build(directory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    from .. import tables
    t = tables()
    have = set(zip(t.year, t.table))
    parts = []
    for year in sorted({int(y) for y in t.year}):
        if year in (1980, 1984, 1985):
            ctrl = directory[directory.year == year].set_index("unitid")["control"]
            parts.append(_hegis(year, ctrl))
        elif year in EARLY:
            parts.append(_early(year))
        elif year == 1999 and (1999, "ip1999ay") in have:
            parts.append(_modern(1999, "ip1999ay", None, "ip1999py" if (1999, "ip1999py") in have else None,
                                 {"1": 1997, "2": 1998, "3": 1999}))
        elif (year, f"ic{year}_ay") in have:
            ay = f"ic{year}_ay"
            parts.append(_modern(year, ay, f"ic{year}" if (year, f"ic{year}") in have else None,
                                 f"ic{year}_py" if (year, f"ic{year}_py") in have else None, _offsets(year, ay)))
    x = pd.concat(parts, ignore_index=True)
    # One value per unitid x academic year x price: prefer the file whose own year it is,
    # else the most recent file that reports it (later files carry revised prior years).
    x["_pref"] = x.current.astype(int) * 10000 + x.survey_year
    x = x.sort_values("_pref", ascending=False)
    x = x.groupby(["unitid", "ay"], as_index=False).first()   # first non-null per column
    x = x.drop(columns="_pref")
    for c in COLS:
        x[c] = x[c].astype("Float64")
    x = x[x[COLS].notna().any(axis=1)]
    x = x[["unitid", "ay", "survey_year", "current"] + COLS].sort_values(["unitid", "ay"]).reset_index(drop=True)

    # QA: overlapping academic years reported in two files should agree
    #   (none overlap here, but 2000/2010/2020 prior-year columns vs. their own
    #   current-year column of the previous survey are not available, so instead
    #   check internal sanity: out-of-state >= in-state >= in-district for publics)
    pub = x.merge(directory[["year", "unitid", "control"]].rename(columns={"year": "survey_year"}),
                  on=["survey_year", "unitid"], how="left")
    pub = pub[pub.control.eq(1)]
    qa = pd.DataFrame([{
        "check": "public: out_state >= in_state", "share": float((pub.ug_tf_out_state >= pub.ug_tf_in_state).mean())},
        {"check": "public: in_state >= in_district (1990+)",
         "share": float((pub.ug_tf_in_state >= pub.ug_tf_in_district).dropna().mean())},
        {"check": "rows with any negative price", "share": float((x[COLS] < 0).any(axis=1).mean())},
    ])
    return x, qa
