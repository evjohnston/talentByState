"""Carnegie Classification of Institutions of Higher Education, keyed to IPEDS unitid.

    python -m ipeds_clean.harmonize.carnegie

Sources (sources/carnegie/)
  longitudinal/Longitudinal-Public-Data-File-1973-2021.xlsx   every edition 1973-2021, with the
      publisher's own cross-edition harmonization (NewVal, Group)
  2018/, 2021/   edition public files (adds the program, profile and size/setting classifications)
  2025/          2025 public file: the new Institutional Classification, Research Activity
                 Designation and Student Access and Earnings classification (codes only)

Outputs (data/ipeds/harmonized/)
  carnegie.parquet    one row per unitid x cc_year (1973 1976 1987 1994 2000 2005 2010 2015 2018
                      2021 2025)
      unitid          unitid the institution reported under in that edition (R_UNITID if
                      given, else C_UNITID); unitid_current = most recent unitid
      status          classified | did_not_exist | not_classified | stopout | merged | closed
      basic_code, basic_label        edition's own basic classification
      common_code     publisher's cross-edition value (NewVal; 15 R1-tier ... 40 two-year ...)
      group, group_label   0 not in, 1 Doctoral, 2 Master's, 3 Bachelor's, 4 Bacc/Assoc,
                      5 Associate's, 6 Special focus 2-yr, 7 Special focus 4-yr, 8 Tribal/other
      research_tier   R1 | R2 | doctoral_other | none   (from common_code 15/16/17; 2025 from the
                      Research Activity Designation: 1 R1, 2 R2)
      group_approx_2025  True for 2025 rows, where group is mapped from the new Institutional
                      Classification (Doctorate/Master's/Baccalaureate/Associate/Special Focus
                      wording) and is NOT the same construct as earlier basic classifications
  carnegie_detail.parquet   unitid x cc_year (2018, 2021, 2025): every classification code in the
                      edition files (ipug, ipgrad, enrprofile, ugprofile, sizeset, ic2025, ...)
  carnegie_labels.csv  value labels for carnegie_detail

Not brought in: College Scorecard and NSF HERD fields bundled in the 2025 files (earnings, net
price, debt, outcome measures, R&D spending, MSI flags sourced from Scorecard).

Use carnegie_asof(panel_df) to attach the most recent edition at or before each panel year.
"""
from __future__ import annotations

import re

import pandas as pd

from ..config import OUT, ROOT

SRC = ROOT / "sources" / "carnegie"
HARM = OUT / "harmonized"
LONG = SRC / "longitudinal" / "Longitudinal-Public-Data-File-1973-2021.xlsx"

GROUPS = {0: "Not in classification", 1: "Doctoral", 2: "Master's", 3: "Bachelor's", 4: "Bacc/Assoc",
          5: "Associate's", 6: "Special focus: 2-year", 7: "Special focus: 4-year", 8: "Tribal/other"}
STATUS = {-1: "did_not_exist", -2: "not_classified", -3: "stopout", -4: "merged", -5: "closed",
          -6: "merged"}

# classification columns kept from the 2018 / 2021 / 2025 edition files (codes, not inputs)
DETAIL = re.compile(r"^(basic\d{4}|cc\d{4}|ipug\d{4}|ipgrad\d{4}|enrprofile\d{4}|ugprofile\d{4}|"
                    r"sizeset\d{4}|cce\d{4}|ic2025(size|alf)?|research2025|saec2025|apm|gpm|"
                    r"setting2025|highest_degree_2025|landgrnt|landgrant|medical|rpu|cce|lpp|"
                    r"womens|womenonly|selindex|actcat|docresflag|locale|control)$", re.I)


def _longitudinal() -> pd.DataFrame:
    cols = ["C_UNITID", "R_UNITID", "YEAR", "INSTNM", "RecentName", "STATE", "CONTROL", "LEVEL",
            "VALUE", "NewVal", "CatLabel", "Group", "GrpLabel", "MergeInto_Link", "EmergeFrom_Link"]
    x = pd.read_excel(LONG, sheet_name="CCData", usecols=cols, engine="openpyxl")
    x = x.dropna(subset=["C_UNITID"])
    num = lambda s: pd.to_numeric(s, errors="coerce").astype("Int64")
    out = pd.DataFrame({
        "unitid": num(x.R_UNITID).fillna(num(x.C_UNITID)),
        "unitid_current": num(x.C_UNITID),
        "cc_year": num(x.YEAR),
        "instnm": x.INSTNM.fillna(x.RecentName),
        "stabbr": x.STATE, "control": num(x.CONTROL), "level": num(x.LEVEL),
        "basic_code": num(x.VALUE), "basic_label": x.CatLabel.astype("string").str.strip(),
        "common_code": pd.to_numeric(x.NewVal, errors="coerce"),
        "group": num(x.Group), "merge_into": num(x.MergeInto_Link), "emerge_from": num(x.EmergeFrom_Link),
        "source": "longitudinal"})
    return out


def _research_tier(common: pd.Series) -> pd.Series:
    return pd.Series(pd.NA, index=common.index, dtype="string").mask(common == 15, "R1") \
        .mask(common == 16, "R2").mask(common.isin([17, 17.5]), "doctoral_other") \
        .fillna("none").where(common.notna())


def _edition_file(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(data, labels) for a 2018/2021/2025 edition public file."""
    if year == 2018:
        f, ds, ls = SRC / "2018" / "CCIHE2018-PublicDataFile.xlsx", "Data", "Labels"
    elif year == 2021:
        f, ds, ls = SRC / "2021" / "CCIHE2021-PublicData.xlsx", "Data", "Values"
    else:
        f, ds, ls = SRC / "2025" / "2025-Public-Data-File.xlsx", "data", "values"
    d = pd.read_excel(f, sheet_name=ds)
    d.columns = [str(c).strip().lower() for c in d.columns]
    lab = pd.read_excel(f, sheet_name=ls)
    lab = lab.iloc[:, :3] if year != 2018 else lab.iloc[:, [0, 1, 2]]
    lab.columns = ["variable", "code", "label"]
    lab["variable"] = lab.variable.ffill().astype(str).str.strip().str.lower()
    lab = lab.dropna(subset=["code"])
    lab["cc_year"] = year
    return d, lab


def _group_2025(name: pd.Series) -> pd.Series:
    n = name.fillna("").str.lower()
    g = pd.Series(pd.NA, index=name.index, dtype="Int64")
    g = g.mask(n.str.contains("doctorate"), 1).mask(n.str.contains("master"), 2)
    g = g.mask(n.str.contains(r"associate/baccalaureate"), 4)
    g = g.mask(n.str.contains("baccalaureate") & g.isna(), 3).mask(n.str.contains("associate") & g.isna(), 5)
    return g.mask(n.str.startswith("special focus"), 7)


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lo = _longitudinal()
    lo["status"] = lo.basic_code.map(STATUS).fillna("classified").where(lo.basic_code.notna())
    lo.loc[lo.basic_code.notna() & (lo.basic_code >= 0), "status"] = "classified"
    lo["research_tier"] = _research_tier(lo.common_code)
    lo["group_approx_2025"] = False

    details, labels = [], []
    for yr in (2018, 2021, 2025):
        d, lab = _edition_file(yr)
        keep = ["unitid"] + [c for c in d.columns if DETAIL.match(c) and c != "unitid"]
        det = d[keep].copy()
        det.insert(1, "cc_year", yr)
        details.append(det)
        labels.append(lab[lab.variable.isin(keep)])
        if yr == 2025:
            n = d.get("ic2025name", pd.Series(index=d.index, dtype="string"))
            res = pd.to_numeric(d.get("research2025"), errors="coerce")
            row = pd.DataFrame({
                "unitid": pd.to_numeric(d.unitid, errors="coerce").astype("Int64"),
                "unitid_current": pd.to_numeric(d.unitid, errors="coerce").astype("Int64"),
                "cc_year": 2025, "instnm": d.get("instnm"), "stabbr": d.get("stabbr"),
                "control": pd.to_numeric(d.get("control"), errors="coerce").astype("Int64"),
                "level": pd.NA, "basic_code": pd.to_numeric(d.get("ic2025"), errors="coerce").astype("Int64"),
                "basic_label": n.astype("string"), "common_code": pd.NA,
                "group": _group_2025(n), "merge_into": pd.NA, "emerge_from": pd.NA,
                "source": "2025 public file", "status": "classified",
                "research_tier": pd.Series(res.map({1: "R1", 2: "R2"}), dtype="string").fillna("none"),
                "group_approx_2025": True})
            lo = pd.concat([lo, row], ignore_index=True)
    lo["group"] = pd.to_numeric(lo.group, errors="coerce").astype("Int64")
    lo["group_label"] = lo.group.map(GROUPS)
    lo = lo.sort_values(["unitid", "cc_year"]).drop_duplicates(["unitid", "cc_year"], keep="first")
    det = pd.concat(details, ignore_index=True)
    det["unitid"] = pd.to_numeric(det.unitid, errors="coerce").astype("Int64")
    for c in det.columns[2:]:
        det[c] = pd.to_numeric(det[c], errors="coerce")
    labs = pd.concat(labels, ignore_index=True)
    return lo.reset_index(drop=True), det, labs


def carnegie_asof(df: pd.DataFrame, year_col: str = "year", cc: pd.DataFrame | None = None,
                  cols: tuple[str, ...] = ("cc_year", "group", "group_label", "research_tier", "basic_label")) -> pd.DataFrame:
    """Attach the latest Carnegie edition published at or before each row's year
    (classified rows only). Rows before 1973 get nothing."""
    cc = cc if cc is not None else pd.read_parquet(HARM / "carnegie.parquet")
    cc = cc[cc.status == "classified"][["unitid", *cols]].dropna(subset=["cc_year"])
    cc = cc.assign(cc_year=cc.cc_year.astype("int64")).sort_values("cc_year")
    left = df.assign(_y=df[year_col].astype("int64")).sort_values("_y")
    out = pd.merge_asof(left, cc, left_on="_y", right_on="cc_year", by="unitid", direction="backward")
    return out.drop(columns="_y").sort_index()


if __name__ == "__main__":
    HARM.mkdir(parents=True, exist_ok=True)
    lo, det, labs = build()
    lo.to_parquet(HARM / "carnegie.parquet", index=False)
    det.to_parquet(HARM / "carnegie_detail.parquet", index=False)
    labs.to_csv(HARM / "carnegie_labels.csv", index=False)
    cl = lo[lo.status == "classified"]
    print(f"carnegie: {len(lo):,} rows, {lo.unitid.nunique():,} unitids; classified by edition:")
    print(cl.groupby("cc_year").size().to_dict())
    print("research tier by edition:")
    print(pd.crosstab(cl.cc_year, cl.research_tier).to_string())
    d = pd.read_parquet(HARM / "directory.parquet", columns=["year", "unitid"])
    link = cl.merge(d.drop_duplicates("unitid"), on="unitid", how="left", indicator=True)
    print("classified unitids found in the IPEDS directory:",
          link.groupby("cc_year")["_merge"].apply(lambda s: f"{(s == 'both').mean():.1%}").to_dict())
    print(f"carnegie_detail: {det.shape}, labels {len(labs)}")
