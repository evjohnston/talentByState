"""Official CPI-U from the BLS Public Data API v2 -> crosswalks/deflators.csv.

    python -m ipeds_clean.bls            # rebuild crosswalks/deflators.csv from BLS

Series CUUR0000SA0: CPI-U, U.S. city average, all items, not seasonally adjusted, 1982-84=100.
Monthly values are pulled and averaged here, giving two indexes per year:
  index     calendar-year average (Jan-Dec of `year`)          <- default used by deflate()
  index_fy  July (year-1) to June (year) average, matching the IPEDS fiscal year that ends in
            `year` (FY2020 = July 2019-June 2020) and the academic year that ends in `year`
Only complete periods (12 months) are written.

A registration key is optional: set the environment variable BLS_API_KEY to use one. Without a
key, BLS allows 10 years per request and 25 requests per day; this script uses 5 requests.
This is used only to deflate IPEDS dollar amounts; no other BLS data enter the project.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import date

import pandas as pd

from .config import XWALK

URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
SERIES = "CUUR0000SA0"
OUT = XWALK / "deflators.csv"


def fetch_monthly(start: int = 1978, end: int | None = None, series: str = SERIES) -> pd.DataFrame:
    end = end or date.today().year
    key = os.environ.get("BLS_API_KEY")
    span = 20 if key else 10
    rows = []
    for y0 in range(start, end + 1, span):
        body = {"seriesid": [series], "startyear": str(y0), "endyear": str(min(y0 + span - 1, end))}
        if key:
            body["registrationkey"] = key
        req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
        if res.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS request {body['startyear']}-{body['endyear']} failed: {res.get('message')}")
        for s in res["Results"]["series"]:
            for d in s["data"]:
                # "-" = not published (e.g. October 2025, federal shutdown); that year is then
                # incomplete and left out of the annual averages
                if d["period"].startswith("M") and d["period"] != "M13" and d["value"] not in ("-", ""):
                    rows.append({"year": int(d["year"]), "month": int(d["period"][1:]),
                                 "value": float(d["value"]),
                                 "preliminary": any(f.get("code") == "P" for f in d.get("footnotes", []) if f)})
    m = pd.DataFrame(rows).drop_duplicates(["year", "month"]).sort_values(["year", "month"])
    return m.reset_index(drop=True)


def annual(m: pd.DataFrame) -> pd.DataFrame:
    cal = m.groupby("year").value.agg(["mean", "size"])
    cal = cal[cal["size"] == 12]["mean"]
    fy_year = m.year + (m.month >= 7).astype(int)          # Jul-Dec count toward the next FY
    fy = m.groupby(fy_year).value.agg(["mean", "size"])
    fy = fy[fy["size"] == 12]["mean"]
    out = pd.DataFrame({"index": cal.round(3), "index_fy": fy.round(3)})
    out.index.name = "year"
    return out.reset_index().dropna(subset=["index", "index_fy"], how="all")


def write(df: pd.DataFrame) -> None:
    header = (
        "# Price index used by ipeds_clean.harmonize.finance.deflate().\n"
        f"# Source: BLS Public Data API v2, series {SERIES} (CPI-U, U.S. city average, all items,\n"
        "# NSA, 1982-84=100), monthly values averaged by ipeds_clean.bls on "
        f"{date.today().isoformat()}.\n"
        "# index    = calendar-year average (default)\n"
        "# index_fy = July(year-1)-June(year) average, matching the IPEDS fiscal/academic year ending in `year`\n"
        "# Rebuild with: python -m ipeds_clean.bls\n")
    OUT.write_text(header + df.to_csv(index=False))


if __name__ == "__main__":
    old = pd.read_csv(OUT, comment="#") if OUT.exists() else None
    a = annual(fetch_monthly())
    if old is not None and "index" in old:
        cmp = old[["year", "index"]].merge(a[["year", "index"]], on="year", suffixes=("_old", "_bls"))
        cmp["diff"] = (cmp.index_bls - cmp.index_old).round(3)
        bad = cmp[cmp["diff"].abs() > 0.05]
        print(f"compared {len(cmp)} years with the previous file; {len(bad)} differ by > 0.05")
        if len(bad):
            print(bad.to_string(index=False))
    write(a)
    print(f"wrote {OUT} ({a.year.min()}-{a.year.max()}, {len(a)} years)")
