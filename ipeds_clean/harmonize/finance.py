"""Harmonized institutional finance: one row per unitid x fiscal year, nominal dollars.

Five accounting regimes appear in these files (column `form`):
  fund       1980, 1990 (all institutions), 2000 public (F1): pre-GASB34/35 fund
             accounting. Tuition is GROSS; institutional aid is an expenditure
             ("scholarships"); plant O&M is its own function; no depreciation.
  fasb       2000, 2010, 2020 private nonprofit (+ a few publics in 2010/2020): F2.
             Tuition NET of discounts/allowances; O&M and depreciation are
             allocated into the functions; investment return includes gains.
  gasb       2010, 2020 public (F1A): tuition NET; O&M allocated into functions
             (2010 also reports the allocation, so it can be backed out); Pell and
             other student grants are NONoperating revenue.
  forprofit  2000, 2010, 2020 for-profit (F3): tuition net; several functions
             only reported combined (2000/2010).

Concepts (the column set is identical for every row; NA = not collected):
  Revenues  tuition_gross, tuition_net, tuition_allowance, fed_approp, state_approp,
            local_approp, fed_grants, state_grants, local_grants, private_gifts_grants,
            investment, auxiliary, hospital, total_revenue
            + always-available combos: fed_total, state_local_total
  Expenses  instruction, research, public_service, academic_support, student_services,
            institutional_support, plant_om, scholarships_gross (fund only),
            net_grant_aid (fasb/forprofit/gasb net scholarship expense), auxiliary_exp,
            hospital_exp, total_expenses, instruction_salaries,
            instruction_excl_alloc (instruction without allocated O&M/depreciation/
            interest: = instruction for fund rows; computed for 2010 gasb/fasb)
            + always-available combos: research_public_service, support_total
  Other     aid_institutional (fund: institutionally funded scholarships)

Comparability rules of thumb
  * Cross-regime: use tuition_gross, fed_total, state_local_total, support_total,
    research_public_service, instruction_excl_alloc. Even these are approximate.
  * total_revenue / total_expenses are as reported and NOT comparable across
    regimes (fund totals include transfers; FASB includes investment gains;
    GASB/FASB expenses include depreciation).
  * Deflate with `deflate()`; default index is CPI-U (crosswalks/deflators.csv),
    replace with HEPI if available.
Mapping lives in MAP below (one dict per (year, table)); each concept is a list
of source columns summed, a leading "-" subtracts.
"""
from __future__ import annotations

import pandas as pd

from .. import load
from ..config import XWALK

CONCEPTS_REV = ["tuition_gross", "tuition_net", "tuition_allowance", "fed_approp", "state_approp",
                "local_approp", "fed_grants", "state_grants", "local_grants", "private_gifts_grants",
                "investment", "auxiliary", "hospital", "total_revenue"]
CONCEPTS_EXP = ["instruction", "research", "public_service", "academic_support", "student_services",
                "institutional_support", "plant_om", "scholarships_gross", "net_grant_aid",
                "auxiliary_exp", "hospital_exp", "total_expenses", "instruction_salaries",
                "instruction_excl_alloc"]
EXTRA = ["aid_institutional", "fed_total", "state_local_total", "research_public_service", "support_total"]

_FUND_HEGIS = {  # 1980, 1984-1986 (HEGIS item numbering)
    "tuition_gross": ["a01"], "fed_approp": ["a02"], "state_approp": ["a03"], "local_approp": ["a04"],
    "fed_grants": ["a05", "a06"], "state_grants": ["a07", "a08"], "local_grants": ["a09", "a10"],
    "private_gifts_grants": ["a11", "a12"], "investment": ["a13", "a14"], "auxiliary": ["a16"],
    "hospital": ["a17"], "total_revenue": ["a20"],
    "instruction": ["b01"], "research": ["b02"], "public_service": ["b03"],
    "academic_support": ["b04", "b05"],  # HEGIS reports libraries (b05) outside academic support
    "student_services": ["b06"], "institutional_support": ["b07"], "plant_om": ["b08"],
    "scholarships_gross": ["b09", "b10"], "auxiliary_exp": ["b14"], "hospital_exp": ["b16"],
    "total_expenses": ["b19"], "instruction_excl_alloc": ["b01"],
}
_FUND_3D = {  # 1987-1996 (all institutions) and public F1 1997-2003 (3-digit item numbering)
    "tuition_gross": ["a013"], "fed_approp": ["a023"], "state_approp": ["a043"], "local_approp": ["a053"],
    "fed_grants": ["a063"], "state_grants": ["a073"], "local_grants": ["a083"],
    "private_gifts_grants": ["a093"], "investment": ["a103"], "auxiliary": ["a123"], "hospital": ["a133"],
    "total_revenue": ["a163"],
    "instruction": ["b013"], "research": ["b023"], "public_service": ["b033"], "academic_support": ["b043"],
    "student_services": ["b063"], "institutional_support": ["b073"], "plant_om": ["b083"],
    "scholarships_gross": ["b093"], "auxiliary_exp": ["b133"], "hospital_exp": ["b163"],
    "total_expenses": ["b223"], "instruction_salaries": ["b014"], "instruction_excl_alloc": ["b013"],
    "aid_institutional": ["e063"],
}
_FASB_97 = {  # 1997 F2 (first FASB form for private nonprofits)
    "tuition_net": ["fa01_1"], "tuition_allowance": ["faa08"], "fed_approp": ["fa02_1"],
    "state_approp": ["fa04_1"], "local_approp": ["fa05_1"], "fed_grants": ["fa06_1"],
    "state_grants": ["fa07_1"], "local_grants": ["fa08_1"], "private_gifts_grants": ["fa910_1"],
    "investment": ["fa11_1"], "auxiliary": ["fa13_1"], "hospital": ["fa14_16"],  # hospital+indep+other combined
    "total_revenue": ["fa17_1"],
    "instruction": ["fb01_1"], "research": ["fb02_1"], "public_service": ["fb03_1"],
    "academic_support": ["fb04_1"], "student_services": ["fb05_1"], "institutional_support": ["fb06_1"],
    "auxiliary_exp": ["fb07_1"], "net_grant_aid": ["fb08_1"], "plant_om": ["fb11_1"],
    "total_expenses": ["fb12_1"],
}
_FASB_98 = {  # 1998-1999 F2
    "tuition_net": ["f2a01_1"], "tuition_allowance": ["f2aa08"], "fed_approp": ["f2a02_1"],
    "state_approp": ["f2a04_1"], "local_approp": ["f2a05_1"], "fed_grants": ["f2a06_1"],
    "state_grants": ["f2a07_1"], "local_grants": ["f2a08_1"], "private_gifts_grants": ["f2a09_1", "f2a10_1"],
    "investment": ["f2a11_1"], "auxiliary": ["f2a13_1"], "hospital": ["f2a14_1"], "total_revenue": ["f2a17_1"],
    "instruction": ["f2b01_1"], "research": ["f2b02_1"], "public_service": ["f2b03_1"],
    "academic_support": ["f2b04_1"], "student_services": ["f2b05_1"], "institutional_support": ["f2b06_1"],
    "auxiliary_exp": ["f2b07_1"], "net_grant_aid": ["f2b08_1"], "hospital_exp": ["f2b09_1"],
    "total_expenses": ["f2b12_1"], "instruction_salaries": ["f2b01_2"],
}
_FASB = {  # 2000+ F2. Total expenses moved from f2e121 (2000-01) to f2e131 (2002+).
    "tuition_net": ["f2d01"], "tuition_allowance": ["f2c08"], "fed_approp": ["f2d02"], "state_approp": ["f2d03"],
    "local_approp": ["f2d04"], "fed_grants": ["f2d05"], "state_grants": ["f2d06"], "local_grants": ["f2d07"],
    "private_gifts_grants": ["f2d08"], "investment": ["f2d10"], "auxiliary": ["f2d12"], "hospital": ["f2d13"],
    "total_revenue": ["f2d16"],
    "instruction": ["f2e011"], "research": ["f2e021"], "public_service": ["f2e031"],
    "academic_support": ["f2e041"], "student_services": ["f2e051"], "institutional_support": ["f2e061"],
    "net_grant_aid": ["f2e081"], "auxiliary_exp": ["f2e071"], "hospital_exp": ["f2e091"],
    "instruction_salaries": ["f2e012"],
}
_GASB = {  # 2002+ F1A. Local/private operating grants were one line (f1b04) before 2008.
    "tuition_net": ["f1b01"], "tuition_allowance": ["f1e08"], "fed_approp": ["f1b10"], "state_approp": ["f1b11"],
    "local_approp": ["f1b12"],
    "fed_grants": ["f1b02", "f1b13"], "state_grants": ["f1b03", "f1b14"], "local_grants": ["f1b04a", "f1b15"],
    "private_gifts_grants": ["f1b04b|f1b04", "f1b16"], "investment": ["f1b17"], "auxiliary": ["f1b05"],
    "hospital": ["f1b06"], "total_revenue": ["f1d01|f1b25"],
    "instruction": ["f1c011"], "research": ["f1c021"], "public_service": ["f1c031"],
    "academic_support": ["f1c051"], "student_services": ["f1c061"], "institutional_support": ["f1c071"],
    "net_grant_aid": ["f1c101"], "auxiliary_exp": ["f1c111"], "hospital_exp": ["f1c121"],
    "total_expenses": ["f1c191"], "instruction_salaries": ["f1c012"],
}
_FP_98 = {  # 1998-1999 F3
    "tuition_net": ["f3a01"], "tuition_allowance": ["f3aa06"], "fed_total": ["f3a02"],
    "state_local_total": ["f3a04"], "private_gifts_grants": ["f3a05"], "investment": ["f3a06"],
    "auxiliary": ["f3a08"], "total_revenue": ["f3a10"],
    "instruction": ["f3b01_1"], "research": ["f3b02_1"], "public_service": ["f3b03_1"],
    "academic_support": ["f3b04_1"], "student_services": ["f3b05_1"], "institutional_support": ["f3b06_1"],
    "auxiliary_exp": ["f3b07_1"], "net_grant_aid": ["f3b08_1"], "total_expenses": ["f3b10_1"],
    "instruction_salaries": ["f3b01_2"],
}
_FP_0013 = {  # 2000-2013 F3 (several functions reported combined)
    "tuition_net": ["f3d01"], "tuition_allowance": ["f3c06"], "fed_total": ["f3d02"],
    "state_local_total": ["f3d03"], "private_gifts_grants": ["f3d04"], "investment": ["f3d05"],
    "auxiliary": ["f3d07"], "total_revenue": ["f3d09"],
    "instruction": ["f3e01"], "research_public_service": ["f3e02"], "support_total": ["f3e03"],
    "auxiliary_exp": ["f3e04"], "net_grant_aid": ["f3e05"], "total_expenses": ["f3e07"],
}
_FP_14 = {  # 2014+ F3 (full functional detail)
    "tuition_net": ["f3d01"], "tuition_allowance": ["f3c06"], "fed_approp": ["f3d02a"],
    "fed_grants": ["f3d02b"], "fed_total": ["f3d02"], "state_approp": ["f3d03a"], "state_grants": ["f3d03b"],
    "state_local_total": ["f3d03"], "private_gifts_grants": ["f3d04"], "investment": ["f3d05"],
    "auxiliary": ["f3d07"], "hospital": ["f3d12"], "total_revenue": ["f3d09"],
    "instruction": ["f3e011"], "research": ["f3e02a1"], "public_service": ["f3e02b1"],
    "academic_support": ["f3e03a1"], "student_services": ["f3e03b1"],
    "institutional_support": ["f3e03c1"], "auxiliary_exp": ["f3e041"], "net_grant_aid": ["f3e051"],
    "hospital_exp": ["f3e101"], "total_expenses": ["f3e071"], "instruction_salaries": ["f3e012"],
}


def specs() -> list[tuple[int, list[str], str, dict]]:
    """(year, source tables, form, mapping) for every finance file available.

    Multi-part fund files (1987, 1989-1996: _a revenues, _b expenditures, _e
    scholarships) are merged on unitid.
    """
    import re
    from .. import tables
    t = tables()
    t = t[t.component == "F"]
    out = []
    for year, g in t.groupby("year"):
        names = set(g.table)
        year = int(year)
        parts = sorted(n for n in names if re.search(r"_[abe]$", n) and not re.search(r"_f\d", n))
        single = [n for n in names if re.fullmatch(r"f(19\d\d|\d{4})", n)]
        if year in (1980, 1984, 1985, 1986):
            out.append((year, single, "fund", _FUND_HEGIS))
        elif single:                                    # 1988
            out.append((year, single, "fund", _FUND_3D))
        elif parts:                                     # 1987, 1989-1996
            out.append((year, parts, "fund", _FUND_3D))
        for n in sorted(names):
            if re.fullmatch(r"f\d{4}_?f1", n):            # public fund-accounting F1, 1997-2003
                out.append((year, [n], "fund", _FUND_3D))
            elif re.fullmatch(r"f\d{4}_?f2", n):
                m = _FASB_97 if year == 1997 else _FASB_98 if year <= 1999 else dict(_FASB)
                if year >= 2000:
                    # f2e121 = total expenses only in 2000-2001; from 2002 it is "Other expenses"
                    m["total_expenses"] = ["f2e121"] if year <= 2001 else ["f2e131"]
                    if 2002 <= year <= 2015:   # functions report allocated O&M / depreciation / interest
                        m["instruction_excl_alloc"] = ["f2e011", "-f2e014", "-f2e015", "-f2e016"]
                out.append((year, [n], "fasb", m))
            elif re.fullmatch(r"f\d{4}_?f3", n):
                m = _FP_98 if year <= 1999 else _FP_0013 if year <= 2013 else dict(_FP_14)
                if year in (2014, 2015):
                    m["instruction_excl_alloc"] = ["f3e011", "-f3e014", "-f3e015", "-f3e016"]
                out.append((year, [n], "forprofit", m))
            elif re.fullmatch(r"f\d{4}_f1a", n):
                m = dict(_GASB)
                # O&M is a separate function through 2007; 2008-2009 were a phase-in year pair
                # with "aligned" (O&M allocated, f1c016 etc.) and "unaligned" (O&M still a
                # function, f1c081) forms -- confirmed in the 2008/2009 survey forms. Map
                # plant_om wherever the separate line exists; unaligned filers have no
                # allocation, so their instruction already excludes O&M.
                if year <= 2009:
                    m["plant_om"] = ["f1c081"]
                if year <= 2007:
                    m["instruction_excl_alloc"] = ["f1c011", "-f1c014", "-f1c017"]
                elif year <= 2015:
                    m["instruction_excl_alloc"] = ["f1c011", "-f1c014", "-f1c016", "-f1c017"]
                out.append((year, [n], "gasb", m))
    return out


def _source(year: int, tabs: list[str]) -> pd.DataFrame:
    d = load(year, tabs[0])
    for t in tabs[1:]:
        e = load(year, t)
        e = e[[c for c in e.columns if c == "unitid" or c not in d.columns]]
        d = d.merge(e, on="unitid", how="outer")
    return d


def _sum(d: pd.DataFrame, cols: list[str]) -> pd.Series | None:
    """Sum the listed items ("a|b" = first present; "-x" subtracts). None if no item exists."""
    parts = []
    for c in cols:
        sign = -1 if c.startswith("-") else 1
        alts = [a for a in c.lstrip("-").split("|") if a in d]
        if not alts:
            continue
        parts.append(d[alts[0]].astype("Float64") * sign)
    if not parts:
        return None
    df = pd.concat(parts, axis=1)
    # NA only if every component is NA (a blank component inside a reported row is 0)
    return df.sum(axis=1, min_count=1).astype("Float64")


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, qa = [], []
    missing = []
    for year, tabs, form, m in specs():
        d = _source(year, tabs)
        out = pd.DataFrame({"year": year, "unitid": d.unitid, "form": form, "source_table": "+".join(tabs)})
        # 2008-2009 GASB phase-in: which form version did the institution file?
        if form == "gasb" and year in (2008, 2009):
            om_function = d["f1c081"].astype("Float64").fillna(0).ne(0) if "f1c081" in d else False
            out["form_variant"] = pd.Series("aligned", index=d.index).where(~om_function, "unaligned").values
        for concept, cols in m.items():
            v = _sum(d, cols)
            if v is None:   # item not on this year's form
                missing.append({"year": year, "tables": "+".join(tabs), "concept": concept, "items": " ".join(cols)})
                continue
            # Within a reported finance row, a blank item the form collects is 0
            # (e.g. a private college leaves "state appropriations" empty). Items the
            # form does not collect stay NA.
            out[concept] = v.fillna(0).values
        rows.append(out)
    qa.append({"check": "concepts whose items are absent on that year's form (left NA)",
               "share_match": float(len(missing))})
    pd.DataFrame(missing).to_csv(_missing_path(), index=False)
    x = pd.concat(rows, ignore_index=True)
    for c in CONCEPTS_REV + CONCEPTS_EXP + EXTRA:
        if c not in x:
            x[c] = pd.NA
        x[c] = x[c].astype("Float64")
    # derived, filled only where not reported directly
    net = x.form.ne("fund")
    x.loc[net, "tuition_gross"] = x.loc[net, "tuition_net"] + x.loc[net, "tuition_allowance"].fillna(0)
    add = lambda *cs: pd.concat([x[c] for c in cs], axis=1).sum(axis=1, min_count=1)
    x["fed_total"] = x.fed_total.fillna(add("fed_approp", "fed_grants"))
    x["state_local_total"] = x.state_local_total.fillna(add("state_approp", "state_grants", "local_approp", "local_grants"))
    x["research_public_service"] = x.research_public_service.fillna(add("research", "public_service"))
    x["support_total"] = x.support_total.fillna(add("academic_support", "student_services", "institutional_support"))
    if "form_variant" not in x:
        x["form_variant"] = pd.NA
    cols = ["year", "unitid", "form", "form_variant", "source_table"] + CONCEPTS_REV + ["fed_total", "state_local_total"] + \
        CONCEPTS_EXP + ["research_public_service", "support_total", "aid_institutional"]
    x = x[cols].sort_values(["unitid", "year"]).reset_index(drop=True)

    # QA: components vs reported totals (fund E&G identity and revenue identity)
    f80 = load(1980, "f1980")
    qa.append({"check": "1980 sum a01..a19 == a20 (revenues)",
               "share_match": float(((f80[[f"a{i:02d}" for i in range(1, 20)]].fillna(0).sum(axis=1)
                                      - f80.a20.fillna(0)).abs() < 2).mean())})
    qa.append({"check": "1980 sum b01..b11 excl b05 == b12 (E&G)",
               "share_match": float(((f80[[f"b{i:02d}" for i in range(1, 12) if i != 5]].fillna(0).sum(axis=1)
                                      - f80.b12.fillna(0)).abs() < 2).mean())})
    g = load(2010, "f0910_f1a")
    qa.append({"check": "2010 GASB: instruction excl. alloc <= instruction",
               "share_match": float((x[(x.year == 2010) & (x.form == "gasb")].eval(
                   "instruction_excl_alloc <= instruction + 1")).mean())})
    qa.append({"check": "2010 GASB tuition_gross == f1b01 + f1e08",
               "share_match": float(((g.f1b01.fillna(0) + g.f1e08.fillna(0)).values ==
                                     x[(x.year == 2010) & (x.form == "gasb")].sort_values("unitid")
                                     .set_index("unitid").reindex(g.unitid).tuition_gross.fillna(0).values).mean())})
    return x, pd.DataFrame(qa)


def _missing_path():
    from ..config import OUT
    (OUT / "harmonized").mkdir(parents=True, exist_ok=True)
    return OUT / "harmonized" / "qa_finance_missing_items.csv"


def deflators(index: str = "index") -> pd.Series:
    """BLS CPI-U by year from crosswalks/deflators.csv (rebuilt by `python -m ipeds_clean.bls`).

    index="index"     calendar-year average of the year the fiscal year ends in (default)
    index="index_fy"  July-June average matching the IPEDS fiscal year exactly"""
    d = pd.read_csv(XWALK / "deflators.csv", comment="#")
    return d.set_index("year")[index].dropna()


def deflate(df: pd.DataFrame, base_year: int = 2020, cols: list[str] | None = None,
            index: str = "index") -> pd.DataFrame:
    """Return a copy with money columns in constant `base_year` dollars (years with no index -> NaN)."""
    idx = deflators(index)
    cols = cols or [c for c in CONCEPTS_REV + CONCEPTS_EXP + EXTRA if c in df]
    f = df.year.map(idx[base_year] / idx).astype(float)
    out = df.copy()
    for c in cols:
        out[c] = out[c] * f
    return out
