"""IPEDS survey forms and instructions (reference/survey_forms/*.zip, 1994-2025): text index + search.

    python -m ipeds_clean.forms            # extract text of every PDF -> data/ipeds/forms_text/
    from ipeds_clean.forms import search
    search(r"Pell", component="finance", years=range(2002, 2010))

Zips are named "<collection year>-<component>.zip" as downloaded from the IPEDS
"Annual Survey Forms Packages - Archived" page. The collection year is the year the
survey opened (e.g. the "2010" Finance package collects fiscal year 2009-10 data, which
this project files under year 2010 for finance; Fall Enrollment "2010" = fall 2010).
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from .config import FORMS_SRC, OUT

SRC = FORMS_SRC
TXT = OUT / "forms_text"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _extract(job):
    zpath, member, out = job
    out = Path(out)
    if out.exists() and out.stat().st_size > 0:
        return str(out), "cached", 0
    try:
        from pypdf import PdfReader
        raw = zipfile.ZipFile(zpath).read(member)
        r = PdfReader(io.BytesIO(raw))
        text = "\n\n".join(f"[page {i + 1}]\n" + (p.extract_text() or "") for i, p in enumerate(r.pages))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        return str(out), "ok", len(r.pages)
    except Exception as e:  # scanned or malformed PDFs
        return str(out), f"error: {repr(e)[:120]}", 0


def jobs():
    for z in sorted(SRC.glob("*.zip")):
        m = re.match(r"^(\d{4})-(.+)\.zip$", z.name)
        if not m:
            continue
        year, comp = m.group(1), _slug(m.group(2))
        for member in zipfile.ZipFile(z).namelist():
            if member.lower().endswith(".pdf"):
                yield str(z), member, str(TXT / year / comp / (Path(member).stem + ".txt"))


def build(workers: int = 6) -> pd.DataFrame:
    js = list(jobs())
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        for i, (out, status, pages) in enumerate(ex.map(_extract, js, chunksize=4), 1):
            rows.append({"file": out, "status": status, "pages": pages})
            if i % 100 == 0:
                print(f"{i}/{len(js)}", flush=True)
    idx = pd.DataFrame(rows)
    idx["year"] = idx.file.str.extract(r"forms_text/(\d{4})/")[0].astype(int)
    idx["component"] = idx.file.str.extract(r"forms_text/\d{4}/([^/]+)/")[0]
    idx["chars"] = [Path(f).stat().st_size if Path(f).exists() else 0 for f in idx.file]
    idx.to_csv(TXT / "index.csv", index=False)
    return idx


def search(pattern: str, component: str | None = None, years=None, context: int = 160,
           max_hits: int = 50) -> pd.DataFrame:
    """Regex search over extracted form text. Returns year, component, file, page, snippet."""
    idx = pd.read_csv(TXT / "index.csv")
    if component:
        idx = idx[idx.component.str.contains(_slug(component))]
    if years is not None:
        idx = idx[idx.year.isin(list(years))]
    rx = re.compile(pattern, re.I)
    hits = []
    for f, y, c in zip(idx.file, idx.year, idx.component):
        p = Path(f)
        if not p.exists():
            continue
        text = p.read_text(errors="ignore")
        for m in rx.finditer(text):
            page = text.count("[page ", 0, m.start())
            s = re.sub(r"\s+", " ", text[max(0, m.start() - context): m.end() + context])
            hits.append({"year": y, "component": c, "file": p.name, "page": page, "snippet": s})
            if len(hits) >= max_hits:
                return pd.DataFrame(hits)
    return pd.DataFrame(hits)


if __name__ == "__main__":
    idx = build(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
    print(idx.status.str.split(":").str[0].value_counts().to_dict(), "pages:", int(idx.pages.sum()))
