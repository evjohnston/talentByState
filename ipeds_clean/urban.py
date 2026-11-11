"""Urban Institute Education Data Portal: IPEDS bulk CSVs, used ONLY to cross-check our panels.

    python -m ipeds_clean.urban            # download the validation set -> data/ipeds/urban/
    python -m ipeds_clean.urban --list     # show what would be downloaded

Scope: only the portal's college-university IPEDS files (its re-release of the same NCES
surveys). Nothing from the portal's non-IPEDS sources (Scorecard, FSA, NACUBO, ...) is fetched,
and nothing downloaded here feeds the harmonized panels; it is comparison material.

Files come from https://educationdata.urban.org/csv/ipeds/<file>, listed by the portal's
download catalog (api/v1/api-downloads/). Codebooks for every IPEDS endpoint are fetched.
Very large per-year series (enrollment by race, completions by 6-digit CIP) are sampled in
SAMPLE_YEARS rather than pulled for all 40 years. Re-running skips files already complete.
Cite as: [dataset names], Education Data Portal (Version 0.27.0), Urban Institute, accessed
<date>, https://educationdata.urban.org/documentation/, made available under the ODC
Attribution License.
"""
from __future__ import annotations

import html
import json
import sys
import urllib.request

import pandas as pd

from .config import OUT

CATALOG = "https://educationdata.urban.org/api/v1/api-downloads/"
BASE = "https://educationdata.urban.org/csv/ipeds/"
DEST = OUT / "urban"

# single-file endpoints that correspond to a harmonized panel
FULL = [
    "colleges_ipeds_directory.csv",             # directory
    "colleges_ipeds_finance.csv",               # finance
    "colleges_ipeds_ay_tuition_fees.csv",       # prices
    "colleges_ipeds_admissions-enrollment.csv", # admissions
    "colleges_ipeds_fall-retention.csv",        # retention
    "colleges_ipeds_enrollment-fte.csv",        # fte
    "colleges_ipeds_fall-res.csv",              # residence
    "colleges_ipeds_grad-rates.csv",            # grad_rates
    "colleges_ipeds_grad-rates-200pct.csv",     # gr200
    "colleges_ipeds_grad-rates-pell.csv",       # gr_pell
    "colleges_ipeds_outcome-measures.csv",      # outcome_measures
    "colleges_ipeds_completers.csv",            # completers
    "colleges_ipeds_academic_libraries.csv",    # libraries
    "colleges_ipeds_salaries_is.csv",           # faculty_salaries
    "colleges_ipeds_sfa_grants_and_net_price.csv",  # student_aid
    "colleges_ipeds_sfa_ftft.csv",              # student_aid
]
# per-year files, sampled
SAMPLE_YEARS = [1990, 2000, 2010, 2020, 2023]
PER_YEAR = ["colleges_ipeds_fall-enrollment-race_{y}.csv",     # enrollment
            "colleges_ipeds_completions-6digcip_{y}.csv",      # completions
            "colleges_ipeds_fall-enrollment-age_{y}.csv"]      # enrollment_age (odd/even rules)


def catalog() -> pd.DataFrame:
    """Portal download catalog; the JSON API is often slow, so the last good copy is cached
    in data/ipeds/urban/catalog.json and used when the live request fails."""
    cache = DEST / "catalog.json"
    try:
        with urllib.request.urlopen(CATALOG, timeout=180) as r:
            raw = r.read()
        DEST.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
    except OSError as e:
        if not cache.exists():
            raise
        print(f"catalog API unavailable ({e!r:.80}); using cached {cache.name}")
        raw = cache.read_bytes()
    c = pd.DataFrame(json.loads(raw)["results"])
    c = c[(c.file_dir == "ipeds") & (c.hide == 0)].drop_duplicates("file_name")
    c["file_label"] = c.file_label.map(html.unescape)
    return c


def manifest(c: pd.DataFrame) -> pd.DataFrame:
    want = set(FULL) | {p.format(y=y) for p in PER_YEAR for y in SAMPLE_YEARS}
    m = c[c.file_name.isin(want) | c.file_name.str.startswith("codebook_")].copy()
    missing = want - set(m.file_name)
    if missing:
        print("not in the catalog (skipped):", sorted(missing))
    return m[["file_name", "file_label", "file_size"]].reset_index(drop=True)


def _remote_size(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        n = r.headers.get("Content-Length")
    return int(n) if n else None


def download(m: pd.DataFrame) -> pd.DataFrame:
    DEST.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, f in enumerate(m.file_name, 1):
        url, out = BASE + f, DEST / f
        size = _remote_size(url)
        if out.exists() and size and out.stat().st_size == size:
            rows.append({"file_name": f, "bytes": size, "status": "cached"})
            continue
        tmp = out.with_suffix(out.suffix + ".part")
        with urllib.request.urlopen(url, timeout=600) as r, open(tmp, "wb") as fh:
            while chunk := r.read(1 << 20):
                fh.write(chunk)
        ok = size is None or tmp.stat().st_size == size
        tmp.replace(out) if ok else None
        rows.append({"file_name": f, "bytes": out.stat().st_size if ok else None,
                     "status": "ok" if ok else "size mismatch"})
        print(f"[{i}/{len(m)}] {f} {rows[-1]['status']}", flush=True)
    log = m.merge(pd.DataFrame(rows), on="file_name")
    log["accessed"] = pd.Timestamp.today().date().isoformat()
    log.to_csv(DEST / "manifest.csv", index=False)
    return log


if __name__ == "__main__":
    m = manifest(catalog())
    if "--list" in sys.argv:
        print(m.to_string(index=False))
    else:
        log = download(m)
        print(log.status.value_counts().to_dict(), f"{log.bytes.sum() / 1e9:.2f} GB in {DEST}")
