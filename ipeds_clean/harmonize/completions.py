"""Harmonized Completions panel: unitid x year x award level x CIP-2020, by sex.

Rules
  * Source tables: the 6-digit detail file of every year (see `sources()`); the
    *_2dig files are exact aggregates. 1980 = c1980_4ormore_cip + c1980subba_cip.
  * Grand-total rows (cipcode 99*) are dropped from the panel and used for QA.
  * 2010/2020: first majors only (majornum == 1). Second majors were not
    collected before 2001, so including them would break the series.
  * Counts mapped through a one-to-many CIP link are multiplied by `share`
    (rare; only "report under X, Y" cases), so they can be fractional.
  * Where an institution's reported grand total (99 row) exceeds the sum of its
    field rows, a residual row is added (cip_method = residual_unallocated,
    cip2020 = NA) so level totals match what institutions reported. This only
    matters for 1990: the public 1989-90 6-digit file is ~3% short of the
    institutions' own totals (2,170 unitid x level cells; never the reverse).
  * Pre-2010 first-professional degrees in theology (CIP 39: M.Div., rabbinical) are
    counted as master's, as NCES did when the first-professional level was retired; all
    other first-professional degrees are doc_prof. awlevel_orig keeps the reported level.
  * Awards with no assignable field (HEGIS 90xx intermediate degrees,
    "undesignated field" 95.xxxx) keep cip2020 = NA and cip_method = no_field.
    They stay in the panel so level totals are complete.
"""
from __future__ import annotations

import pandas as pd

from .. import load
from .cip_chain import build_chain, norm_cip80

def vintage_for(year: int) -> str:
    """CIP edition used by each Completions file (verified against code lists)."""
    if year <= 1980:
        return "HEGIS"
    if year <= 1986:
        return "CIP80"
    if year <= 1991:
        return "CIP85"
    if year <= 2002:
        return "CIP90"
    if year <= 2009:
        return "CIP2K"
    if year <= 2019:
        return "CIP10"
    return "CIP20"


def sources() -> list[tuple[int, str, str]]:
    """(year, table, vintage) for the 6-digit detail file(s) of every available year.

    1980 c1980_4ormore_cip + c1980subba_cip; 1984-1994 c{yyyy}_cip / c8990cip;
    1995+ c{yy}{yy}_a / c{yyyy}_a. The *_2dig, *_re, *_b, *_c, *dep files are
    aggregates or other dimensions and are not used here.
    """
    import re
    from .. import tables
    t = tables()
    t = t[t.component == "C"]
    out = []
    for y, tab in zip(t.year, t.table):
        if (y == 1980 and tab in ("c1980_4ormore_cip", "c1980subba_cip")) or \
                re.fullmatch(r"c(\d{4})_cip|c8990cip|c\d{4}_a", tab):
            out.append((int(y), tab, vintage_for(int(y))))
    return sorted(out)


# Harmonized award levels. Order = display order.
AWARD_LEVELS = {
    "cert_lt1":  "Certificate, less than 1 year",
    "cert_1_2":  "Certificate, 1 to less than 2 years",
    "cert_1_4":  "Certificate, 1 to less than 4 years (1984-1986 only; = cert_1_2 + cert_2_4 later)",
    "assoc":     "Associate's degree",
    "cert_2_4":  "Certificate, 2 to less than 4 years",
    "bach":      "Bachelor's degree",
    "pb_cert":   "Postbaccalaureate certificate",
    "master":    "Master's degree",
    "pm_cert":   "Post-master's certificate (incl. 1980 intermediate degrees, 2000 first-professional certificates)",
    "doc_res":   "Doctor's degree, research/scholarship and other",
    "doc_prof":  "First-professional degree / Doctor's degree, professional practice",
}

# Award-level codes are stable from 1984 on (1-11 through the 2000s; 17-19 replace
# 9-11 from 2008-2010; 20-21 split "<1 year" from 2020). Only the 1980 HEGIS files
# use their own scheme. `check_awlevels()` verifies this against every year's labels.
STD_AWLEVEL = {1: "cert_lt1", 2: "cert_1_2", 3: "assoc", 4: "cert_2_4", 5: "bach", 6: "pb_cert",
               7: "master", 8: "pm_cert", 9: "doc_res", 10: "doc_prof", 11: "pm_cert",
               17: "doc_res", 18: "doc_prof", 19: "doc_res", 20: "cert_lt1", 21: "cert_lt1"}


class _AwMap(dict):
    """(year, table) -> {code: level}; any table not listed uses STD_AWLEVEL."""
    def __missing__(self, key):
        return STD_AWLEVEL


_CIP80_LEVELS = {1: "cert_lt1", 2: "cert_1_4", 3: "assoc", 5: "bach", 7: "master", 9: "doc_res", 10: "doc_prof"}
AWLEVEL_MAP = _AwMap({
    # 1984-86: code 2 = "at least 1 but less than 4 academic years" (1986 label says
    # "at least 2"; counts follow 1984-85, so treated as the same category).
    (1984, "c1984_cip"): _CIP80_LEVELS, (1985, "c1985_cip"): _CIP80_LEVELS, (1986, "c1986_cip"): _CIP80_LEVELS,
    (1980, "c1980subba_cip"): {1: "cert_1_2", 2: "assoc", 3: "assoc", 4: "cert_2_4", 5: "cert_2_4"},
    (1980, "c1980_4ormore_cip"): {5: "bach", 7: "master", 8: "pm_cert", 9: "doc_res", 10: "doc_prof"},
})

_LEVEL_PATTERNS = [  # label regex -> level, first match wins (used only for QA)
    (r"first.?professional.*certificate|post.?master|intermediate|specialist", "pm_cert"),
    (r"professional practice|first.?professional", "doc_prof"),
    (r"doctor", "doc_res"),
    (r"master", "master"),
    (r"post.?baccalaureate", "pb_cert"),
    (r"bachelor", "bach"),
    (r"associate", "assoc"),
    (r"(at least|)\s*2\b.*less than 4|two.*less than four|2 but less than 4", "cert_2_4"),
    (r"(at least|)\s*1\b.*less than 2|one.*less than two|1 but less than 2", "cert_1_2"),
    (r"less than (one|1)|less than 12 weeks|12 weeks", "cert_lt1"),
]


def check_awlevels() -> pd.DataFrame:
    """Compare STD_AWLEVEL against every year's dictionary label for each awlevel code."""
    import re
    from ..config import META_DIR
    v = pd.read_csv(META_DIR / "value_labels.csv", dtype={"code": str})
    v = v[(v.varname == "awlevel") & v.table.isin([t for _, t, _ in sources()])]
    rows = []
    for (y, t), g in v.groupby(["year", "table"]):
        amap = AWLEVEL_MAP[(int(y), t)]
        for code, lab in zip(g.code, g.label):
            try:
                c = int(float(code))
            except ValueError:
                continue
            guess = next((lvl for pat, lvl in _LEVEL_PATTERNS if re.search(pat, str(lab).lower())), None)
            rows.append({"year": y, "table": t, "code": c, "label": lab,
                         "mapped": amap.get(c), "label_suggests": guess,
                         "agree": amap.get(c) == guess})
    return pd.DataFrame(rows)


def _read(year: int, table: str, vintage: str) -> pd.DataFrame:
    d = load(year, table)
    if "ctotalm" in d:
        men, women = d["ctotalm"], d["ctotalw"]
    else:
        men, women = d["crace15"], d["crace16"]
    out = pd.DataFrame({
        "year": year, "unitid": d["unitid"], "source_table": table, "cip_vintage": vintage,
        "cip_orig": (d["cipcode"].str[:4] if vintage == "HEGIS" else
                     d["cipcode"].map(norm_cip80).astype("string") if vintage == "CIP80" else d["cipcode"]),
        "cip_orig_full": d["cipcode"],
        "awlevel_orig": d["awlevel"].astype("Int64"),
        "majornum": d["majornum"] if "majornum" in d else 1,
        # Within a reported row a blank sex count means zero (1980-2000 files leave
        # zeros blank; the dictionaries' own means treat blanks as 0). Without
        # fillna, men + women is NA whenever one side is blank and awards vanish.
        "men": men.astype("Float64").fillna(0), "women": women.astype("Float64").fillna(0),
    })
    out["total"] = out["men"] + out["women"]
    return out


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (panel, chain, review, qa)."""
    frames, chains, reviews, qa = [], [], [], []
    by_vintage: dict[str, list[pd.DataFrame]] = {}
    from .cip_chain import vintages
    V = vintages()
    PREV = {"CIP85": "CIP80", "CIP90": "CIP85", "CIP2K": "CIP90", "CIP10": "CIP2K", "CIP20": "CIP10"}
    for year, table, vin in sources():
        r = _read(year, table, vin)
        # Transition years let institutions choose the old or new CIP (e.g. 2002-03 data:
        # "1990 CIP or CIP2000", per the 2003 Completions form). Codes valid only in the
        # previous edition are routed through that edition's chain.
        prev = PREV.get(vin)
        if prev:
            old = ~r.cip_orig.isin(set(V[vin].titles)) & r.cip_orig.isin(set(V[prev].titles)) & \
                  ~r.cip_orig.str.startswith(("99", "95"))
            if old.any():
                r.loc[old, "cip_vintage"] = prev
                by_vintage.setdefault(prev, []).append(r[old])
                r = r[~old]
        by_vintage.setdefault(vin, []).append(r)

    for vin, parts in by_vintage.items():
        raw = pd.concat(parts, ignore_index=True)
        is_total = raw["cip_orig"].str.startswith("99")
        first = raw["majornum"].eq(1)
        detail = raw[~is_total & first].copy()
        totals = raw[is_total & first]

        chain, review = build_chain(vin, detail["cip_orig"].unique())
        chains.append(chain)
        if len(review):
            reviews.append(review.assign(vintage=vin))

        m = detail.merge(chain[["orig_code", "cip2020", "share", "method", "path"]],
                         left_on="cip_orig", right_on="orig_code", how="left", validate="many_to_many")
        for c in ["men", "women", "total"]:
            m[c] = m[c] * m["share"]
        m["award_level"] = [AWLEVEL_MAP[(y, t)].get(a) for y, t, a in
                            zip(m["year"], m["source_table"], m["awlevel_orig"])]
        m = m.rename(columns={"method": "cip_method", "share": "cip_share", "path": "cip_path"})

        # residual rows: reported total - field detail, per unitid x level
        key = ["year", "unitid", "source_table", "cip_vintage", "awlevel_orig"]
        det = detail.groupby(key)[["men", "women", "total"]].sum()
        rep = totals.groupby(key)[["men", "women", "total"]].sum()
        gap = (rep - det.reindex(rep.index).fillna(0))
        gap = gap[gap["total"] > 0].reset_index()
        if len(gap):
            gap = gap.assign(cip_orig_full=pd.NA, cip2020=pd.NA, cip_share=1.0,
                             cip_method="residual_unallocated", cip_path=pd.NA)
            gap["award_level"] = [AWLEVEL_MAP[(y, t)].get(a) for y, t, a in
                                  zip(gap["year"], gap["source_table"], gap["awlevel_orig"])]
            m = pd.concat([m, gap], ignore_index=True)
        frames.append(m)

        # QA 1: totals preserved through the chain, by year x original award level
        a = detail.groupby(["year", "source_table", "awlevel_orig"])["total"].sum()
        b = m[m.cip_method != "residual_unallocated"].groupby(["year", "source_table", "awlevel_orig"])["total"].sum()
        r = m[m.cip_method == "residual_unallocated"].groupby(["year", "source_table", "awlevel_orig"])["total"].sum()
        # QA 2: detail rows sum to the institution-reported grand total rows
        t = totals.groupby(["year", "source_table", "awlevel_orig"])["total"].sum()
        q = pd.DataFrame({"raw_detail": a, "harmonized": b, "residual_added": r,
                          "reported_99_total": t}).fillna({"residual_added": 0}).reset_index()
        qa.append(q)

    panel = pd.concat(frames, ignore_index=True)
    cip = panel["cip2020"].astype("string")
    panel["cip2020_4"] = cip.str[:5]
    panel["cip2020_2"] = cip.str[:2]
    # NCES reclassification when the first-professional level was retired (2010): divinity and
    # rabbinical first-professional degrees (M.Div., M.H.L./Rav) became master's, the rest
    # doctor's-professional practice. Apply it to pre-2010 first-professional awards (original
    # level 10) in theology (CIP 39) so the series matches 2010+ reporting and the Digest.
    fp_div = (pd.to_numeric(panel["awlevel_orig"], errors="coerce").eq(10).fillna(False).astype(bool)
              & panel["award_level"].eq("doc_prof").fillna(False).astype(bool)
              & panel["cip2020_2"].eq("39").fillna(False).astype(bool))
    panel.loc[fp_div, "award_level"] = "master"
    panel["award_level"] = pd.Categorical(panel["award_level"], categories=list(AWARD_LEVELS), ordered=True)
    cols = ["year", "unitid", "award_level", "cip2020", "cip2020_4", "cip2020_2",
            "men", "women", "total",
            "cip_orig_full", "cip_vintage", "cip_method", "cip_share", "awlevel_orig", "source_table"]
    panel = panel[cols].sort_values(["year", "unitid", "award_level", "cip2020"]).reset_index(drop=True)
    qa = pd.concat(qa, ignore_index=True)
    qa["award_level"] = [AWLEVEL_MAP[(y, t)].get(a) for y, t, a in zip(qa.year, qa.source_table, qa.awlevel_orig)]
    return panel, pd.concat(chains, ignore_index=True), pd.concat(reviews, ignore_index=True), qa
