"""Discover source files in {year}/raw/*.zip.

The raw folders contain repeated browser downloads ("FLAGS2010 (3).zip").
Those are byte-identical, so we dedupe by content hash and keep one copy.
When a data zip contains both foo.csv and foo_rv.csv, the revised file wins.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path

from .config import RAW_ROOT, ROOT, YEARS, component_for, generic_name


@dataclass
class Source:
    year: int
    table: str            # canonical lowercase name, e.g. "ef2010a"
    generic: str          # year-stripped name, e.g. "efa"
    component: str        # survey component, e.g. "EF"
    data_zip: str         # path relative to ROOT
    data_member: str      # csv inside the zip
    revised: bool         # True if *_rv.csv was used
    dict_zip: str | None
    dict_member: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _canonical_zip_stem(p: Path) -> str:
    # "FLAGS2010 (3).zip" -> "FLAGS2010"
    return re.sub(r"\s*\(\d+\)$", "", p.stem)


def discover(years: list[int] = YEARS) -> list[Source]:
    sources: list[Source] = []
    for year in years:
        raw = RAW_ROOT / str(year) / "raw"
        if not raw.exists():
            raw = RAW_ROOT / str(year)
        if not raw.exists():
            continue
        # canonical stem -> first zip path (duplicates verified identical)
        uniq: dict[str, Path] = {}
        for z in sorted(raw.glob("*.zip"), key=lambda p: (len(p.name), p.name)):
            stem = _canonical_zip_stem(z)
            if stem in uniq:
                if _md5(z) != _md5(uniq[stem]):
                    raise RuntimeError(f"{z} differs from {uniq[stem]}; resolve manually")
                continue
            uniq[stem] = z

        for stem, z in sorted(uniq.items()):
            if stem.upper().endswith("_DICT"):
                continue
            with zipfile.ZipFile(z) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csvs:
                continue
            rv = [n for n in csvs if n.lower().endswith("_rv.csv")]
            member = rv[0] if rv else csvs[0]
            table = stem.lower()

            dz = uniq.get(stem + "_Dict") or uniq.get(stem + "_DICT")
            dmember = None
            if dz is not None:
                with zipfile.ZipFile(dz) as zf:
                    cands = [n for n in zf.namelist()
                             if n.lower().endswith((".html", ".htm", ".xls", ".xlsx"))]
                dmember = cands[0] if cands else None

            sources.append(Source(
                year=year, table=table, generic=generic_name(table),
                component=component_for(table),
                data_zip=str(z.relative_to(ROOT)), data_member=member,
                revised=bool(rv),
                dict_zip=str(dz.relative_to(ROOT)) if dz else None,
                dict_member=dmember,
            ))
    return sources
