"""Paths and constants for the IPEDS cleaning pipeline."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Every raw download, as received, lives under sources/{publisher_dataset}/ (read-only inputs).
# Regenerable API responses and microdata extracts live under cache/ (safe to delete; rebuilt on demand).
SOURCES = ROOT / "sources"
CACHE = ROOT / "cache"
# All IPEDS/HEGIS downloads live in sources/ipeds/{year}/. Zips sit either directly
# in the year folder or in a raw/ subfolder (the original decade folders).
RAW_ROOT = SOURCES / "ipeds"
YEARS = sorted(int(p.name) for p in RAW_ROOT.iterdir() if p.is_dir() and p.name.isdigit())
DECADE_YEARS = [1980, 1990, 2000, 2010, 2020]

# Downloaded reference material (read-only): official NCES CIP files and survey forms.
REF = ROOT / "reference"
CIP_REF = REF / "cip"                    # CIP.XLS, Crosswalk2000to2010.csv, Crosswalk2010to2020.csv, ...
FORMS_SRC = REF / "survey_forms"         # archived IPEDS survey form/instruction zips
# Project-maintained inputs (edit these): hand-reviewed CIP overrides, price index.
XWALK = ROOT / "crosswalks"

DATA = ROOT / "data"        # everything the pipeline writes; one folder per source, plus states/ (the products)
OUT = DATA / "ipeds"        # IPEDS outputs: clean/, meta/, harmonized/, digest/, forms_text/, urban/
CLEAN_DIR = OUT / "clean"   # data/ipeds/clean/{year}/{table}.parquet
META_DIR = OUT / "meta"     # catalogs + QA reports

# Survey component, matched against the table name in order (first match wins).
# fa2000hd must be matched before the generic finance pattern.
COMPONENTS: list[tuple[str, str]] = [
    (r"^flags", "FLAGS"),        # response status / imputation flags
    (r"^drv", "DRV"),            # NCES derived variables (2021+)
    (r"^dfr", "DFR"),            # data feedback report
    (r"^res\d", "EF"),           # residence of first-time students (EF part C, 1980s)
    (r"^ip\d", "IC"),            # institutional prices (1999)
    (r"^pub_", "OTHER"),
    (r"^(hd|ic\d+hd|fa\d+hd)", "HD"),  # institutional directory / header
    (r"^ic", "IC"),              # institutional characteristics
    (r"^adm", "ADM"),            # admissions
    (r"^effy", "E12"),           # 12-month enrollment
    (r"^efia", "EFIA"),          # 12-month instructional activity
    (r"^ef", "EF"),              # fall enrollment
    (r"^c", "C"),                # completions
    (r"^sfav?", "SFA"),          # student financial aid
    (r"^gr", "GR"),              # graduation rates
    (r"^om", "OM"),              # outcome measures
    (r"^sal", "SAL"),            # faculty salaries
    (r"^eap", "EAP"),            # employees by assigned position
    (r"^s\d", "S"),              # fall staff
    (r"^al", "AL"),              # academic libraries
    (r"^f", "F"),                # finance
]

# Columns that are identifiers/codes: always kept as strings (leading zeros,
# CIP decimals like "01.0100", etc.), regardless of dictionary type.
FORCE_STRING = {
    "cipcode", "opeid", "zip", "ein", "duns", "gentele", "fice", "ueis",
    "webaddr", "adminurl", "faidurl", "applurl", "npricurl", "veturl",
    "athurl", "disaurl", "ialias",
}

# Tokens treated as missing on read (in addition to empty strings).
NA_TOKENS = ["", ".", " ", "NA", "N/A"]


def component_for(table: str) -> str:
    for pat, comp in COMPONENTS:
        if re.match(pat, table):
            return comp
    return "OTHER"


def generic_name(table: str) -> str:
    """Strip the year token so tables can be lined up across decades.

    ef1980_a -> efa, ef90_a -> efa, ef2010a -> efa, f9900_f1 -> ff1,
    f0910_f1a -> ff1a, gr200_10 -> gr200, c8990cip -> ccip.
    """
    if table.startswith("gr200_"):
        return "gr200"
    m = re.match(r"^([a-z]+?)(19\d\d|20\d\d|\d{4}|\d{2})(.*)$", table)
    if not m:
        return table
    return (m.group(1) + m.group(3)).replace("_", "")
