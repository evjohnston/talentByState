"""USAspending.gov: federal grant and contract obligations by state (place of performance) and fiscal year, with an
R&D-focused subset.

    python -m ipeds_clean.usaspending          # -> data/usaspending/*.csv (API responses cached in cache/usaspending/)

Source: the public USAspending API (no key), queried one request at a time with a pause between requests; every
JSON response is cached in cache/usaspending/ and reused on later runs (delete the folder to refresh).
  POST /api/v2/search/spending_by_geography/  scope=place_of_performance, geo_layer=state, one fiscal year
       (Oct 1 - Sep 30) per request: transaction obligations whose action date falls in the year, summed by the
       state where the work is performed.
  POST /api/v2/search/spending_over_time/     group=fiscal_year, same filters: the national total (all places,
       including foreign and unknown place of performance), used as "US" and for the state-sum check.
The API's searchable data start at FY2008 (2007-10-01). FY2026 closed on 2026-09-30; late reporting (DOD contract
data are published with a 90-day lag) will still add to it, so treat FY2026 as provisional.

Measures (value = obligations in USD; negative de-obligations are netted in)
  grants_all       award types 02-05 (block, formula, project grants, cooperative agreements), all agencies
  contracts_all    award types A-D (BPA calls, purchase orders, delivery orders, definitive contracts), all agencies
  R&D subset:
  grants_nsf       grants 02-05 awarded by the National Science Foundation (toptier agency)
  grants_nih       grants 02-05 awarded by the National Institutes of Health (HHS subtier agency)
  grants_nasa      grants 02-05 awarded by NASA (toptier agency)
  grants_doe_sc    grants 02-05 under Assistance Listing 81.049, DOE Office of Science Financial Assistance Program
  grants_rd4       derived: grants_nsf + grants_nih + grants_nasa + grants_doe_sc (no overlap between the four)
  contracts_rd     contracts A-D whose Product/Service Code is in the "Research and Development" group (PSC
                   codes starting with "A")
  rd_subset        derived: grants_rd4 + contracts_rd
The grant subset is research-agency grants, not an R&D classification: NIH and NSF grants are nearly all
research and training, NASA and DOE Office of Science grants mostly so. R&D grants from other agencies (DOD, USDA,
DOE outside the Office of Science, ...) are not in it; R&D contracts from every agency are.

Not used: the two files in sources/usaspending/ (inventoried in files.csv). usaspending-db-subset_20261106.zip is
a 5 GB PostgreSQL pg_dump directory (toc.dat + *.dat.gz) that needs a Postgres restore; FY2027_All_Contracts_Full
is one month of FY2027 contract transactions, outside the FY2008-2026 window and contracts only.

Outputs (data/usaspending/):
  usaspending_state.csv       fiscal_year, state, measure, value, note, endpoint, cache_file, quality
  usaspending_state_wide.csv  one row per state-year, one column per measure (rows flagged incomplete left out)

Incomplete as retrieved (2026-11-10, re-pulled 2026-11-11 with no change), flagged quality=incomplete:
* FY2026 grants: the API returns $311B of grant obligations nationally (FY2025: $1,245B). By awarding agency
  (completeness.csv) HHS has $1.7B against $826B (only CMS, $1.4B; no NIH, ACF, HRSA, CDC), DOE 9%, Commerce 9%,
  EPA 22%, while Transportation, Agriculture, Education, DHS and DOD are at 88-99%; NSF is at 73%, NASA 76%,
  DOE Office of Science 75%. So all grant measures (and grants_rd4, 18% of FY2025, and rd_subset) for FY2026 are
  incomplete and kept out. FY2026 contracts look complete ($802B vs $814B) but are still provisional.
* FY2008 NIH: the state query returns one state (ME, $1.8M) and the national query $11.2B (FY2009: $26.1B);
  NIH's FY2008 awards are evidently not coded to the NIH subtier, so grants_nih, grants_rd4 and rd_subset for
  FY2008 are incomplete.
  files.csv                   the two downloaded files (not used) and every cached API response (used)
  coverage.csv                measure x fiscal_year: states (50 + DC), territories, US present
  checks.csv                  state sums vs national totals, R&D shares, US continuity, comparison with FFS
  pulls.csv                   re-pulled years (REPULL): earlier vs current pull by measure and state (+ sum51)
  completeness.csv            FY2026 vs FY2025 grant obligations by awarding agency and HHS subagency
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "usaspending"
CACHE = ROOT / "cache" / "usaspending"
OUT = ROOT / "data" / "usaspending"
API = "https://api.usaspending.gov/api/v2/search/"
YEARS = range(2008, 2027)
PAUSE = 0.8
# Re-pulls: fiscal years refetched on a later date. The cache name carries the date (geo_<m>_<fy>_r<date>), so the
# earlier responses stay in cache/usaspending/ for comparison (pulls.csv). The national spending_over_time series is
# refetched with the latest date too and used for every year.
REPULL = {2025: "20261111", 2026: "20261111"}
OVERTIME_TAG = max(REPULL.values(), default="")

STATES51 = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
            "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
            "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"}
TERR = {"PR", "GU", "VI", "AS", "MP", "FM", "MH", "PW", "UM"}
GRANTS = ["02", "03", "04", "05"]
CONTRACTS = ["A", "B", "C", "D"]
MEASURES = {
    "grants_all": {"award_type_codes": GRANTS},
    "contracts_all": {"award_type_codes": CONTRACTS},
    "grants_nsf": {"award_type_codes": GRANTS,
                   "agencies": [{"type": "awarding", "tier": "toptier", "name": "National Science Foundation"}]},
    "grants_nih": {"award_type_codes": GRANTS,
                   "agencies": [{"type": "awarding", "tier": "subtier", "name": "National Institutes of Health"}]},
    "grants_nasa": {"award_type_codes": GRANTS,
                    "agencies": [{"type": "awarding", "tier": "toptier",
                                  "name": "National Aeronautics and Space Administration"}]},
    "grants_doe_sc": {"award_type_codes": GRANTS, "program_numbers": ["81.049"]},
    "contracts_rd": {"award_type_codes": CONTRACTS, "psc_codes": {"require": [["Research and Development"]]}},
}
DERIVED = {"grants_rd4": ["grants_nsf", "grants_nih", "grants_nasa", "grants_doe_sc"],
           "rd_subset": ["grants_nsf", "grants_nih", "grants_nasa", "grants_doe_sc", "contracts_rd"]}
ORDER = ["grants_all", "contracts_all", "grants_nsf", "grants_nih", "grants_nasa", "grants_doe_sc", "grants_rd4",
         "contracts_rd", "rd_subset"]


# ---------------------------------------------------------------- API with cache
def post(endpoint: str, body: dict, name: str, tag: str = "") -> tuple[dict, Path]:
    """Cached POST; tag (a retrieval date) gives a re-pull its own cache file."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(json.dumps([endpoint, body], sort_keys=True).encode()).hexdigest()[:10]
    path = CACHE / f"{name}_{key}{'_r' + tag if tag else ''}.json"
    if path.exists():
        return json.loads(path.read_text()), path
    data = json.dumps(body).encode()
    for attempt in range(5):
        try:
            out = json.loads(http_post(API + endpoint, data))
            break
        except Exception as e:                     # rate limit / timeout: back off and retry
            wait = 5 * 2 ** attempt
            print(f"  ! {name}: {e}; retry in {wait}s")
            time.sleep(wait)
    else:
        raise RuntimeError(f"USAspending request failed: {name}")
    out["_request"] = {"endpoint": endpoint, "body": body,
                       "retrieved": time.strftime("%Y-%m-%d %H:%M:%S")}
    path.write_text(json.dumps(out))
    time.sleep(PAUSE)
    return out, path


def http_post(url: str, data: bytes) -> bytes:
    """urllib first; if the local Python cannot verify the TLS chain (e.g. behind an intercepting proxy whose CA
    is only in the system keychain), fall back to the system curl."""
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json",
                                                          "User-Agent": "talentByState research"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
    r = subprocess.run(["curl", "-sS", "--fail", "-m", "180", "-X", "POST", url, "-H",
                        "Content-Type: application/json", "--data-binary", "@-"], input=data, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[:300])
    return r.stdout


def fy_period(fy: int) -> list[dict]:
    return [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}]


# ---------------------------------------------------------------- build
def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, used, prev = [], [], []
    for m, flt in MEASURES.items():
        body = {"group": "fiscal_year", "filters": {**flt, "time_period": [
            {"start_date": f"{YEARS[0] - 1}-10-01", "end_date": f"{YEARS[-1]}-09-30"}]}}
        d, p = post("spending_over_time/", body, f"overtime_{m}", OVERTIME_TAG)
        used.append(p)
        for r in d["results"]:
            fy = int(r["time_period"]["fiscal_year"])
            if fy in YEARS:
                rows.append(dict(fiscal_year=fy, state="US", measure=m, value=r["aggregated_amount"],
                                 note="national total, all places of performance (spending_over_time)",
                                 endpoint="spending_over_time", cache_file=p.name))
        for fy in YEARS:
            body = {"scope": "place_of_performance", "geo_layer": "state",
                    "filters": {**flt, "time_period": fy_period(fy)}}
            if fy in REPULL:      # keep the earlier pull for the comparison
                d0, p0 = post("spending_by_geography/", body, f"geo_{m}_{fy}")
                prev.append((m, fy, p0, d0))
            d, p = post("spending_by_geography/", body, f"geo_{m}_{fy}", REPULL.get(fy, ""))
            used.append(p)
            for r in d["results"]:
                code = r.get("shape_code")
                if not code:
                    continue
                rows.append(dict(fiscal_year=fy, state=code, measure=m, value=r["aggregated_amount"], note="",
                                 endpoint="spending_by_geography", cache_file=p.name))
        print(f"  {m}: done")
    df = pd.DataFrame(rows)
    pulls(df, prev)
    completeness()
    # derived sums
    piv = df.pivot_table(index=["fiscal_year", "state"], columns="measure", values="value", aggfunc="first")
    add = []
    for name, parts in DERIVED.items():
        s = piv[parts].sum(axis=1, min_count=1).dropna()
        add.append(pd.DataFrame({"value": s, "measure": name, "note": "derived: " + " + ".join(parts),
                                 "endpoint": "", "cache_file": ""}).reset_index())
    df = pd.concat([df] + add, ignore_index=True)
    df.loc[df.fiscal_year == YEARS[-1], "note"] = (df.loc[df.fiscal_year == YEARS[-1], "note"] +
                                                   "; FY2026 provisional (late reporting)").str.strip("; ")
    # incomplete series as retrieved (see docstring): flagged in the long file, left out of the wide file
    grant_like = [m for m in ORDER if m.startswith("grants") or m == "rd_subset"]
    bad = ((df.fiscal_year == 2026) & df.measure.isin(grant_like)) | \
          ((df.fiscal_year == 2008) & df.measure.isin(["grants_nih", "grants_rd4", "rd_subset"]))
    df["quality"] = ""
    df.loc[bad, "quality"] = "incomplete"
    df["order"] = df.measure.map({m: i for i, m in enumerate(ORDER)})
    df = df.sort_values(["fiscal_year", "state", "order"]).drop(columns="order")
    df.to_csv(OUT / "usaspending_state.csv", index=False)
    wide = df[df.quality == ""].pivot_table(index=["fiscal_year", "state"], columns="measure", values="value", aggfunc="first")
    wide[[m for m in ORDER if m in wide]].reset_index().to_csv(OUT / "usaspending_state_wide.csv", index=False)

    files = []
    for p in sorted(SRC.iterdir()):
        if p.name.startswith("."):
            continue
        rec = dict(file=f"sources/usaspending/{p.name}", bytes=p.stat().st_size, md5="", contents="", used="no")
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
                rec["contents"] = f"{len(names)} members, e.g. " + "; ".join(names[:3])
        except Exception as e:
            rec["contents"] = f"not readable as zip: {e}"
        if "db-subset" in p.name:
            rec["md5"] = "not computed (5 GB)"
            rec["why_not_used"] = ("PostgreSQL pg_dump directory format (toc.dat + numbered .dat.gz table dumps) "
                                   "of a subset database; needs pg_restore into Postgres. The public API gives the "
                                   "same award data by state and year.")
        elif "FY2027" in p.name:
            h = hashlib.md5()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            rec["md5"] = h.hexdigest()
            rec["why_not_used"] = ("one month (Oct 2026) of FY2027 contract transactions only; outside the "
                                   "FY2008-2026 window and no grants")
        else:
            rec["why_not_used"] = "not part of this build"
        files.append(rec)
    for p in sorted(set(used)):
        req = json.loads(p.read_text()).get("_request", {})
        files.append(dict(file=f"cache/usaspending/{p.name}", bytes=p.stat().st_size, md5="",
                          contents=f"API {req.get('endpoint', '')} retrieved {req.get('retrieved', '')}: "
                                   + json.dumps(req.get("body", {}).get("filters", {}))[:300],
                          used="yes", why_not_used=""))
    pd.DataFrame(files).to_csv(OUT / "files.csv", index=False)

    cov = df.groupby(["measure", "fiscal_year"]).state.agg(
        n_states=lambda s: s.isin(STATES51).sum(),
        territories=lambda s: " ".join(sorted(set(s) & TERR)),
        other_codes=lambda s: " ".join(sorted(set(s) - STATES51 - TERR - {"US"})),
        us=lambda s: "yes" if (s == "US").any() else "no").reset_index()
    cov.to_csv(OUT / "coverage.csv", index=False)
    checks(df)


def completeness(fy: int = YEARS[-1]) -> pd.DataFrame:
    """completeness.csv: grant obligations by awarding agency (and HHS subagency), fy vs fy-1, as currently served
    (POST spending_by_category/awarding_agency|awarding_subagency, cached with the re-pull date)."""
    tag = REPULL.get(fy, "")
    out = []
    for kind, extra in (("awarding_agency", {}), ("awarding_subagency", {"agencies": [
            {"type": "awarding", "tier": "toptier", "name": "Department of Health and Human Services"}]})):
        for y in (fy - 1, fy):
            body = {"category": kind, "limit": 100, "page": 1,
                    "filters": {"award_type_codes": GRANTS, "time_period": fy_period(y), **extra}}
            d, _ = post(f"spending_by_category/{kind}/", body, f"cat_grants_{kind}_{y}", tag)
            out += [dict(level=kind, agency=r["name"], fiscal_year=y, value=r["amount"]) for r in d["results"]]
    c = pd.DataFrame(out).pivot_table(index=["level", "agency"], columns="fiscal_year", values="value").reset_index()
    c.columns = ["level", "agency", f"fy{fy - 1}", f"fy{fy}"]
    c["pct_of_prior"] = (100 * c[f"fy{fy}"] / c[f"fy{fy - 1}"]).round(1)
    c = c.sort_values(["level", f"fy{fy - 1}"], ascending=[True, False])
    c.to_csv(OUT / "completeness.csv", index=False)
    return c


def pulls(df: pd.DataFrame, prev: list) -> None:
    """pulls.csv: each re-pulled fiscal year, earlier vs current pull, by measure, state and US (51-state sum)."""
    out = []
    for m, fy, p0, d0 in prev:
        old = {r["shape_code"]: r["aggregated_amount"] for r in d0["results"] if r.get("shape_code")}
        new = df[(df.measure == m) & (df.fiscal_year == fy) & (df.endpoint == "spending_by_geography")].set_index("state").value
        when0 = d0.get("_request", {}).get("retrieved", "")
        for st in sorted(set(old) | set(new.index)):
            out.append(dict(fiscal_year=fy, measure=m, state=st, earlier=old.get(st), current=new.get(st),
                            earlier_retrieved=when0, current_tag=REPULL[fy]))
    if not out:
        return
    p = pd.DataFrame(out)
    s51 = p[p.state.isin(STATES51)].groupby(["fiscal_year", "measure"])[["earlier", "current"]].sum().reset_index()
    p = pd.concat([p, s51.assign(state="sum51", earlier_retrieved=p.earlier_retrieved.iat[0],
                                 current_tag=p.current_tag.iat[0])], ignore_index=True)
    p["change_pct"] = (100 * (p.current / p.earlier - 1)).round(2)
    p.to_csv(OUT / "pulls.csv", index=False)


def checks(df):
    out = []
    w = df.pivot_table(index=["fiscal_year", "state"], columns="measure", values="value", aggfunc="first")
    for (fy, m), g in df.groupby(["fiscal_year", "measure"]):
        us = g.loc[g.state == "US", "value"]
        if us.empty or not us.iat[0]:
            continue
        s51, sall = g[g.state.isin(STATES51)].value.sum(), g[g.state != "US"].value.sum()
        out.append(dict(check="state_sum_vs_national", fiscal_year=fy, state="US", measure=m, us=us.iat[0],
                        sum_51=s51, sum_with_territories=sall, diff_pct=round(100 * (sall / us.iat[0] - 1), 3),
                        flag="" if abs(sall / us.iat[0] - 1) < 0.05 else "state sum differs > 5%"))
    for (fy, st), r in w.iterrows():
        if st in STATES51 | {"US"}:
            for num, den in (("grants_rd4", "grants_all"), ("contracts_rd", "contracts_all")):
                if pd.notna(r.get(num)) and r.get(den):
                    out.append(dict(check=f"share_{num}_of_{den}", fiscal_year=fy, state=st, measure=num,
                                    us=r[den], sum_51=r[num], diff_pct=round(100 * r[num] / r[den], 2)))
    us = w.xs("US", level="state")
    for m in ORDER:
        if m in us:
            s = us[m].dropna()
            for fy, v, ch in zip(s.index, s.values, s.pct_change().values * 100):
                out.append(dict(check="us_continuity", fiscal_year=fy, state="US", measure=m, us=v,
                                diff_pct=None if pd.isna(ch) else round(ch, 2),
                                flag="jump" if pd.notna(ch) and abs(ch) > 25 else ""))
    # informational: NSF grants (USAspending, place of performance) vs NSF R&D obligations by state (NSF FFS)
    ffs = ROOT / "data" / "ffs" / "ffs_state.csv"
    if ffs.exists():
        f = pd.read_csv(ffs)
        f = f[(f.measure == "rd_oblig") & (f.category.isin(["ag_nsf", "ag_nasa", "all"]))]
        f = f.pivot_table(index=["fiscal_year", "state"], columns="category", values="value", aggfunc="first") * 1000
        for (fy, st), r in w.iterrows():
            if (fy, st) in f.index and st in STATES51:
                for a, b in (("grants_nsf", "ag_nsf"), ("rd_subset", "all")):
                    if pd.notna(r.get(a)) and pd.notna(f.loc[(fy, st)].get(b)) and f.loc[(fy, st)][b]:
                        out.append(dict(check=f"vs_ffs_{b}", fiscal_year=fy, state=st, measure=a,
                                        us=f.loc[(fy, st)][b], sum_51=r[a],
                                        diff_pct=round(100 * (r[a] / f.loc[(fy, st)][b] - 1), 2)))
    ck = pd.DataFrame(out)
    ck["flag"] = ck.flag.fillna("") if "flag" in ck else ""
    ck.to_csv(OUT / "checks.csv", index=False)

    pd.set_option("display.width", 220)
    s = ck[ck.check == "state_sum_vs_national"]
    print(f"state sum vs national: {len(s)} rows; 51-state share of national, median by measure:")
    print((100 * s.sum_51 / s.us).groupby(s.measure).median().round(2).to_string())
    print("\nUS totals ($B):")
    print((us[[m for m in ORDER if m in us]] / 1e9).round(2).to_string())
    for c in ("vs_ffs_ag_nsf", "vs_ffs_all"):
        x = ck[ck.check == c]
        if len(x):
            print(f"\n{c}: {len(x)} state-years, median diff {x.diff_pct.median():.1f}%")


if __name__ == "__main__":
    build()
