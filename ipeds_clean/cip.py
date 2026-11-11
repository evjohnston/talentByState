"""CIP code helpers and the 2010 -> 2020 crosswalk.

CIP formats seen in the raw files:
  1980  "01020"   HEGIS-era 5-digit, no decimal (2-digit family + 3)
  1990+ "06.0402" standard xx.xxxx
The NCES crosswalk csv is an Excel export with codes written as ="01.0101".
"""
from __future__ import annotations

import re

import pandas as pd

from .config import CIP_REF


def _unexcel(s: pd.Series) -> pd.Series:
    return s.astype("string").str.replace(r'^="?|"$', "", regex=True).str.strip()


def cip_level(code: pd.Series) -> pd.Series:
    """2, 4 or 6 digit level of a standard xx[.xx[xx]] code."""
    digits = code.astype("string").str.replace(".", "", regex=False).str.len()
    return digits.map({2: 2, 4: 4, 6: 6}).astype("Int64")


def cip2(code: pd.Series) -> pd.Series:
    """2-digit CIP family from any of the formats above."""
    c = code.astype("string").str.strip()
    return c.str.extract(r"^(\d{2})", expand=False)


def load_crosswalk_2010_2020(path=None) -> pd.DataFrame:
    path = path or CIP_REF / "2010to2020-Crosswalk.csv"
    raw = pd.read_csv(path, dtype=str, encoding="cp1252", keep_default_na=False)
    xw = pd.DataFrame({
        "cip2010": _unexcel(raw["Original code"]).replace("", pd.NA),
        "title2010": raw["Original title"].str.strip().replace("", pd.NA),
        "action": raw["Action"].str.strip(),
        "text_change": raw["Text change"].str.strip().eq("Yes"),
        "cip2020": _unexcel(raw["Current code"]).replace("", pd.NA),
        "title2020": raw["Current title"].str.strip().replace("", pd.NA),
    })
    ref = xw["cip2010"].fillna(xw["cip2020"])
    xw["level"] = cip_level(ref)
    # Many-to-one / one-to-many indicators, useful when allocating counts.
    six = xw[xw["level"] == 6]
    n_targets = six.dropna(subset=["cip2010"]).groupby("cip2010")["cip2020"].nunique()
    xw["n_targets_from_2010"] = xw["cip2010"].map(n_targets).astype("Int64")
    return xw
