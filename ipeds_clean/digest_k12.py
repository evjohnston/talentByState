"""State measures from the Digest of Education Statistics (NCES): every edition saved as HTML in reference/digest/
plus the Excel tables in sources/nces_digest_tables/.

    python -m ipeds_clean.digest_k12      # -> data/digest_k12/*.csv, data/digest_state/*.csv

The Digest parser (ipeds_clean.digest) parses only IPEDS-sourced tables into data/ipeds/digest/. This module
reuses its HTML parser for K-12 state tables (Common Core of Data, EDFacts, IDEA, NEA salary estimates), adds an
Excel parser for the tabn*.xls[x] downloads, and reads the IPEDS migration tables (309.xx) from
data/ipeds/digest/values.parquet.

Sources per measure (SPECS): the 2013+ table numbers (e.g. 211.60) in every edition folder (.asp and .html
copies), the 1995-2012 editions' tables whose title matches the spec's regex (old sequential numbers), and the
Excel copies. Each edition prints only selected years and revises earlier ones; for every state and year the
latest edition is kept (ordered by edition, then the "This table was prepared <month year>" date), and the
edition and file are recorded. Projected columns (219.20 graduates, 203.xx enrollment) become a separate
"_proj" measure from the one edition that projects furthest ahead, kept after each state's last actual year.
Every Excel file turned out to have an HTML copy of the same edition, so the Excel copies back up the HTML parse
(HTML is kept on ties).

Years are the spring of the school year (2022-23 -> 2023); fall counts keep the fall year (fall 2023 -> 2023);
a single-year table (309.xx, 219.50) takes its year from the title. Dollar measures use each edition's
unadjusted (current) dollars, deflated here to constant REAL_BASE dollars with the project's CPI-U
(crosswalks/deflators.csv, academic-year index), so they line up with the IPEDS dollars.

Outputs
  data/digest_k12/k12_state.csv        year, state, measure, value, edition, file   (K-12 measures)
  data/digest_k12/k12_state_wide.csv   one row per state-year, one column per measure (SPECS keys; dollar measures
                                       also as *_nominal; *_proj for projections)
  data/digest_k12/files_excel.csv      inventory of sources/nces_digest_tables/: table, title, edition,
                                       prepared, latest data year, md5, duplicate_of, html_copy, used, why
  data/digest_state/postsec_state.csv  + _wide.csv: first-time-student residence and migration (309.10-309.30)
Exact duplicate Excel files (same table, same content) are moved to sources/_duplicates_to_delete/
nces_digest_tables/ (logged in sources/new_data_moves.csv).
"""
from __future__ import annotations

import functools
import hashlib
import importlib
import re
import shutil
from pathlib import Path

import pandas as pd

from .config import DATA, REF, SOURCES
from .states_explorer import NAMES

D = importlib.import_module("ipeds_clean.digest")
OUT = DATA / "digest_k12"
OUT_PS = DATA / "digest_state"
XLS = SOURCES / "nces_digest_tables"
DUPS = SOURCES / "_duplicates_to_delete" / "nces_digest_tables"
MOVES = SOURCES / "new_data_moves.csv"
SOURCE = "Data from NCES, Digest of Education Statistics"
NAME2ST = {v: k for k, v in NAMES.items()}
MONTH = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
DROP_COL = re.compile(r"percent change|rank|change,|change in|difference", re.I)

# measure: tables (2013+ numbers), pre-2013 title regex, column regex, options
#   year="title": the table covers one year, named in its title    proj: split "Projected" columns off
#   dollars: deflate to REAL_BASE                                     col_not: columns to leave out
#   fall_to_spring: a "fall 2012" column is school year 2012-13 (-> 2013), to match school-year columns
SPECS = {
    "k12_ppe": dict(tables=["236.65"], col=r"^(unadjusted|current dollars)", dollars=True,
                    title=r"^current expenditures? per pupil in fall enrollment in public elementary and secondary schools, by state"),
    "k12_acgr": dict(tables=["219.46"], col=r"^total,? acgr for all students"),
    "k12_afgr": dict(tables=["219.35"], col=r"\d{4}",
                     title=r"^averaged freshman graduation rates? for public secondary schools, by state"),
    "k12_afgr_by_group": dict(measure="k12_afgr", tables=["219.40", "219.41"], year="title",
                              col=r"^total, male and female \| total$|^averaged freshman graduation rate( \(afgr\))? \| total$"),
    "k12_teacher_salary": dict(tables=["211.60"], col=r"^(current dollars|unadjusted)", dollars=True,
                               title=r"^estimated average annual salary of teachers in public elementary ?and ?secondary schools, by state"),
    "k12_enroll": dict(tables=["203.20"], col=r".", col_not=r"kinder|grade", proj=True,
                       title=r"^enrollment in public elementary and secondary schools, by (region, |level and )?state"),
    "k12_enroll_pk8": dict(tables=["203.25"], col=r".", proj=True),
    "k12_enroll_9_12": dict(tables=["203.30"], col=r".", proj=True),
    "k12_hs_grads": dict(tables=["219.20"], col=r".", proj=True, title=r"^public high school graduates, by (region, )?state"),
    "k12_frpl_pct": dict(tables=["204.10"], col=r"^percent",
                         title=r"^number and percentage of public school students eligible for free or reduced-price lunch, by state"),
    "k12_el_pct": dict(tables=["204.20"], col=r"^percent|as a percent", fall_to_spring=True,
                       title=r"^number and percentage of public school students participating in programs for english language learners, by state"),
    "k12_idea_pct": dict(tables=["204.70"], col=r"^3- to 21-year-olds served \| as a percent of public school enroll"),
    "k12_teachers": dict(tables=["208.40"], col=r"\bteachers\b",
                         title=r"^teachers, enrollment, and pupil/teacher ratios in public elementary and secondary schools, by state"),
    "k12_pupil_teacher": dict(tables=["208.40"], col=r"pupil/ ?teacher ratio",
                              title=r"^teachers, enrollment, and pupil/teacher ratios in public elementary and secondary schools, by state"),
    "k12_charter_enroll_pct": dict(tables=["216.90"], col=r"charter school enrollment as a percent",
                                   title=r"^public elementary and secondary charter schools and enrollment, by state"),
    "k12_dropout_event": dict(tables=["219.50"], col=r"event dropout rate\), by race/ethnicity \| total$", year="title"),
}

# Inventory: why each Excel table is or is not used (tables not listed: "single-year/descriptive table; skipped").
SKIP = {
    "101.40": "Census population estimates; take from Census directly",
    "102.40": "Census/ACS child poverty; not an education measure",
    "104.80": "ACS attainment, 2 years only", "104.85": "ACS attainment, one year", "104.88": "ACS attainment, one year",
    "202.25": "ACS pre-K enrollment, one year",
    "203.40": "one fall, by grade", "203.45": "one fall, by grade", "203.70": "race/ethnicity shares, 3 years",
    "203.72": "one fall, by locale", "203.80": "average daily attendance (enrollment used instead)",
    "203.90": "attendance and school-year length, 2007-08",
    "204.06": "Title I schools, one year", "204.07": "Title I schools, one year", "204.09": "private-school Title I",
    "204.25": "EL services, few years", "204.28": "EL proficiency attainment, few years",
    "204.75c": "homeless students", "204.75d": "homeless students",
    "204.90": "gifted and talented: CRDC gives a longer series (crdc_gt_per100)",
    "205.80": "private schools (PSS): biennial, few years",
    "208.30": "teachers by level (208.40 totals used)", "209.30": "teacher degrees/experience, 2011-12 SASS",
    "211.70": "BLS OEWS teacher wages, 3 years; use OEWS directly",
    "213.20": "staff by assignment, one year", "213.30": "staff by assignment, one year",
    "213.40": "staff totals (teachers and pupil/teacher ratio used)", "213.50": "pupil/staff ratios (pupil/teacher used)",
    "213.75": "BLS OEWS, 3 years", "214.30": "number of agencies",
    "216.43": "schools by size, one year", "216.44": "schools by size, one year", "216.70": "school counts by type",
    "216.75": "average school size, one year", "216.90a": "one year", "216.90b": "one year", "216.90c": "one year",
    "216.90d": "one year",
    "219.30": "national only", "219.32": "graduates by sex and race, one year", "219.33": "graduates by sex and race, one year",
    "219.85a": "ACS status dropout", "219.85b": "ACS status dropout", "219.87": "status dropout, 2000",
    "221.50": "NAEP: data/naep (API) covers", "221.65": "NAEP: data/naep covers", "221.70": "NAEP: data/naep covers",
    "221.72": "NAEP: data/naep covers", "222.70": "NAEP: data/naep covers", "222.75": "NAEP: data/naep covers",
    "223.23": "NAEP: data/naep covers",
    "226.40": "SAT: participation set by state testing policy; few years", "226.60": "ACT: 2 years, participation set by policy",
    "228.50": "YRBS school safety", "230.62": "YRBS bullying", "230.82": "HSLS one cohort",
    "236.25": "total current expenditures (per-pupil 236.65 used)", "236.30": "expenditures by function, one year",
    "236.40": "expenditures by function, one year", "236.50": "instruction expenditures, 2 years",
    "236.70": "per pupil in average daily attendance (per pupil in fall enrollment used)",
    "236.75": "per pupil by function, one year", "236.80": "per pupil by function, one year",
    "302.70": "ACS enrollment rate of 18-24, few years",
    "304.10": "IPEDS: the state panel has fall enrollment 1980+", "304.15": "IPEDS covers", "304.20": "IPEDS covers",
    "304.21": "IPEDS covers", "304.22": "IPEDS covers", "304.30": "IPEDS covers", "304.35": "IPEDS covers",
    "304.40": "IPEDS covers", "304.45": "IPEDS covers", "304.50": "IPEDS covers", "304.60": "IPEDS covers",
    "304.70": "IPEDS covers", "304.80": "IPEDS covers", "305.20": "IPEDS covers", "306.60": "IPEDS covers",
    "306.65": "IPEDS covers", "307.20": "IPEDS covers", "307.30": "IPEDS covers", "308.10": "IPEDS covers",
    "308.20": "IPEDS covers", "310.20": "by country of origin, not by state",
    "314.50": "IPEDS covers", "314.55": "IPEDS covers", "314.65": "IPEDS covers", "316.30": "IPEDS covers (faculty_salary)",
    "316.40": "IPEDS covers", "316.50": "IPEDS covers", "316.60": "IPEDS covers", "316.81": "IPEDS covers",
    "317.20": "IPEDS covers", "317.30": "IPEDS covers", "319.10": "IPEDS covers", "319.20": "IPEDS covers",
    "319.30": "IPEDS covers", "319.40": "IPEDS covers",
    "330.20": "IPEDS covers (tuition_pub4_instate, 1980+)", "333.20": "IPEDS finance covers", "333.25": "IPEDS finance covers",
    "333.30": "IPEDS covers (approp_per_fte, 1985+)", "334.20": "IPEDS finance covers", "334.70": "IPEDS finance covers",
    "401.60": "ED appropriations for one fiscal year; program mix changes by year",
    "701.30": "school libraries, 2011-12",
}
MIGRATION = {"309.10": "all", "309.20": "hs", "309.30": "4yr"}


# --------------------------------------------------------------------------- labels

def _state(label: str) -> str | None:
    s = re.sub(r"[\d\\/,*†‡]+$", "", str(label)).replace("…", "").strip(" .")
    s = re.sub(r"\s+", " ", s)
    return NAME2ST.get(s)


def _spring(a: int, b: str) -> int:
    return int(b) if len(b) == 4 else (a // 100) * 100 + int(b) + (100 if int(b) < a % 100 else 0)


def _year(col: str) -> int | None:
    """Spring year from a column label: '1999-2000' -> 2000, '2011- 12' -> 2012, 'Fall 2014' -> 2014. The last
    header level is read first ('Teachers | Fall 2000'), then the levels above ('Fall 2020 | Teachers')."""
    for part in reversed(col.split("|")):
        y = _year1(part)
        if y:
            return y
    return None


def _year1(tail: str) -> int | None:
    m = re.search(r"((?:19|20)\d{2})\s*[-–]\s*(\d{2,4})", tail)
    if m:
        return _spring(int(m.group(1)), m.group(2))
    m = re.search(r"((?:19|20)\d{2})(\d{2})\b", tail)        # 2008 edition: "199091" (dash lost)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return _spring(int(m.group(1)), m.group(2))
    m = re.search(r"(?:Fall\s+)?((?:19|20)\d{2})", tail)
    return int(m.group(1)) if m else None


def _clean_col(c: str) -> str:
    """Drop the dashed rules of the 1995-2003 text tables: '---- | Current dollars ----' -> 'Current dollars'."""
    parts = [re.sub(r"-{3,}", "", p).strip() for p in str(c).split("|")]
    return " | ".join(p for p in parts if p)


def _title_year(title: str) -> int | None:
    """The (last) year a single-year title names: 'by state: Fall 2022' -> 2022, ': 2020-21' -> 2021."""
    tail = str(title).split(":")[-1]
    ys = [_spring(int(a), b) for a, b in re.findall(r"((?:19|20)\d{2})\s*[-–]\s*(\d{2,4})", tail)]
    ys += [int(a) for a in re.findall(r"(?<![-–\d])((?:19|20)\d{2})(?![-–\d])", tail)]
    return max(ys) if ys else None


def _prepared(text: str) -> int:
    """'This table was prepared August 2017' -> 201708 (0 if absent)."""
    m = re.search(r"prepared\s+([A-Z][a-z]+)\.?,?\s+((?:19|20)\d{2})", text)
    return int(m.group(2)) * 100 + MONTH.get(m.group(1).lower(), 0) if m else 0


# --------------------------------------------------------------------------- Excel tables

def _cell(v) -> str:
    return "" if pd.isna(v) else re.sub(r"\s+", " ", str(v)).strip()


@functools.lru_cache(maxsize=None)
def _read_excel(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, header=None, engine="calamine", dtype=object)


def excel_meta(path: Path) -> dict:
    """Title, prepared date and source note of a tabn*.xls[x] file."""
    d = _read_excel(path)
    cells = [_cell(v) for v in d.iloc[:, 0]]
    title = next((c for c in cells if c.startswith("Table")), cells[0] if cells else "")
    i = cells.index(title) if title in cells else 0
    if i + 1 < len(cells) and cells[i + 1] and not d.iloc[i + 1, 1:].notna().any() and not title.rstrip().endswith(("]", ")")) \
            and re.search(r"[a-z,]$", title.split(":")[-1].strip()):
        title += " " + cells[i + 1]       # a title wrapped onto the next row
    text = " ".join(c for c in cells if c)
    title = re.sub(r"^Table\s+[\d.]+[a-z]?\.\s*", "", title)
    return {"title": title, "prepared": _prepared(text),
            "source": next((c for c in cells if c.startswith("SOURCE")), "")[:600]}


def parse_excel(path: Path) -> pd.DataFrame:
    """A Digest Excel table -> row_label, row_path, col, col_label, value (like digest.parse_file).

    The row of printed column numbers (1, 2, 3, ...) anchors the parse: header rows above it are stacked
    into col_label (upper rows filled right across merged cells), rows below are data until the notes.
    Footnote-marker columns (no number, or a repeated number) are dropped."""
    d = _read_excel(path)
    num = None
    for r in range(min(len(d), 30)):
        v = d.iloc[r]
        if str(v.iloc[0]).strip() in ("1", "1.0"):
            nums = pd.to_numeric(v.iloc[1:], errors="coerce").dropna()
            if len(nums) and nums.iloc[0] == 2:
                num = r
                break
    if num is None:
        return pd.DataFrame()
    first = next(r for r in range(num) if _cell(d.iloc[r, 0]).startswith("Table") or r == 0)
    head = d.iloc[first + 1:num].copy()
    if len(head) > 1:
        head.iloc[:-1] = head.iloc[:-1].T.ffill().T   # fill spanning labels right (upper rows only)
    cols, last = [], None
    for j in range(1, d.shape[1]):
        n = pd.to_numeric(d.iat[num, j], errors="coerce")
        if pd.isna(n) or n == last:
            continue
        last = n
        lab = " | ".join(dict.fromkeys(_cell(x) for x in head.iloc[:, j] if _cell(x)))
        lab = re.sub(r"\\\d+\\|\\[a-z]\\", "", lab).strip()
        cols.append((j, int(n), lab))
    rows, section = [], ""
    for r in range(num + 1, len(d)):
        lab = _cell(d.iat[r, 0])
        if re.match(r"^(NOTE|SOURCE|\\\d|---|—|#|†|‡|!|\*|\d\\)", lab):
            break
        if not lab:
            continue
        vals = [(j, n, c, d.iat[r, j]) for j, n, c in cols]
        if all(pd.isna(v) or _cell(v) == "" for *_, v in vals):
            section = lab.strip(" .:")
            continue
        for j, n, c, v in vals:
            if isinstance(v, (int, float)) and not pd.isna(v):
                x, raw = float(v), str(v)
            else:
                raw = _cell(v)
                x, _ = D.parse_value(re.sub(r"\\\d+\\", "", raw)) if raw else (None, "")
            rows.append({"row": r, "row_label": lab, "row_path": f"{section} > {lab}" if section else lab,
                         "col": n, "col_label": c, "value": x, "value_raw": raw})
    return pd.DataFrame(rows)


def _table_of(name: str) -> str:
    m = re.match(r"tabn(\d{3}\.\d{2}[a-z]?)", name)
    return m.group(1) if m else ""


def _content_key(path: Path) -> str:
    v = parse_excel(path)
    if v.empty:
        return hashlib.md5(_read_excel(path).to_csv(index=False).encode()).hexdigest()
    v = v.assign(row_label=v.row_label.str.replace(r"[.\s]+$", "", regex=True).str.strip(), value=v.value.round(4))
    s = v[["row_label", "col_label", "value"]].to_csv(index=False)
    return hashlib.md5(s.encode()).hexdigest()


def _html_prepared() -> pd.DataFrame:
    """(table, edition, prepared, file) for every 2013+ HTML table file (prepared date read from the page)."""
    rows = []
    for f in sorted((REF / "digest").glob("20*/dt*_*.*")):
        m = re.match(r"dt(\d{2})_(\d{3}\.\d{2}[a-z]?)$", f.stem)
        if not m or f.suffix not in (".asp", ".html"):
            continue
        rows.append({"table": m.group(2), "edition": int(f.parent.name), "file": f})
    return pd.DataFrame(rows)


@functools.lru_cache(maxsize=None)
def _page(path: Path) -> str:
    return path.read_text(errors="ignore")


def inventory(move: bool = True) -> pd.DataFrame:
    """Catalog sources/nces_digest_tables/ (and the copies already moved aside) -> files_excel.csv."""
    files = sorted(XLS.glob("tabn*.xls*")) + sorted(DUPS.glob("tabn*.xls*"))
    html = _html_prepared()
    cat = _catalog().assign(path=lambda c: c.file.map(lambda f: REF / "digest" / f))
    html["title"] = html.file.map(dict(zip(cat.path, cat.title))).fillna("")
    rows = []
    for f in files:
        t = _table_of(f.name)
        meta = excel_meta(f)
        ed, basis, copy = None, "", ""
        h = html[html.table == t]
        h = h[[bool(meta["prepared"]) and _prepared(_page(f)) == meta["prepared"] for f in h.file]]
        if len(h):     # several editions can reprint one table (same prepared date): prefer the same data year
            same = h[h.title.map(_title_year) == _title_year(meta["title"])]
            r = (same if len(same) else h).iloc[-1 if len(same) else 0]
            eds = sorted((same if len(same) else h).edition)
            basis = "same prepared date as the HTML copy" + (f" (reprinted unchanged in editions {eds[0]}-{eds[-1]}; latest given)" if len(eds) > 1 else "")
            ed, copy = r.edition, str(r.file.relative_to(REF.parent))
        if ed is None and meta["prepared"]:
            y, mth = divmod(meta["prepared"], 100)
            ed, basis = (y - 1 if mth <= 3 else y), "inferred from the prepared date (Jan-Mar -> previous edition)"
        span = re.findall(r"((?:19|20)\d{2})(?:\s*[-–]\s*(\d{2,4}))?", meta["title"].split(":")[-1])
        latest = max((_spring(int(a), b) if b else int(a)) for a, b in span) if span else None
        rows.append({"file": f.name, "folder": str(f.parent.relative_to(SOURCES)), "table": t, "title": meta["title"],
                     "edition": ed, "edition_basis": basis, "prepared": meta["prepared"] or None,
                     "latest_data_year": latest, "md5": hashlib.md5(f.read_bytes()).hexdigest(),
                     "content": _content_key(f), "html_copy": copy})
    inv = pd.DataFrame(rows)
    # exact duplicates: same table and same parsed content (keep the plainest name: no " (n)", .xlsx over .xls)
    inv["_rank"] = (inv.folder.str.contains("_duplicates").astype(int) * 100 + inv.file.str.contains(r" \(\d+\)").astype(int) * 10
                    + inv.file.str.endswith(".xls").astype(int))
    inv["_n"] = pd.to_numeric(inv.file.str.extract(r"\((\d+)\)")[0], errors="coerce").fillna(-1)
    inv = inv.sort_values(["table", "content", "_rank", "_n"])
    keep = inv.groupby(["table", "content"]).file.transform("first")
    inv["duplicate_of"] = keep.where(keep != inv.file, "")
    used_tables = {t: m for m, s in SPECS.items() for t in s["tables"]}
    used_tables.update({t: f"fresh_*_{u} (data/digest_state)" for t, u in MIGRATION.items()})

    def why(r):
        if r.duplicate_of:
            return "no", f"exact duplicate of {r.duplicate_of}"
        ms = sorted({s.get("measure", m) for m, s in SPECS.items() if r.table in s["tables"]}) or ([used_tables[r.table]] if r.table in used_tables else [])
        if ms:
            how = "same edition as " + r.html_copy.split("/")[-1] + " (HTML kept on ties)" if r.html_copy else "edition not in reference/digest"
            return "yes", ", ".join(ms) + "; " + how
        base = re.sub(r"[a-z]$", "", r.table)
        return "no", SKIP.get(r.table) or SKIP.get(base) or "single-year or descriptive table"
    inv[["used", "why"]] = inv.apply(lambda r: pd.Series(why(r)), axis=1)
    if move:
        DUPS.mkdir(parents=True, exist_ok=True)
        log = []
        for r in inv[(inv.duplicate_of != "") & ~inv.folder.str.contains("_duplicates")].itertuples():
            src, dst = XLS / r.file, DUPS / r.file
            shutil.move(str(src), str(dst))
            log.append(("moved", str(src.relative_to(SOURCES.parent)), str(dst.relative_to(SOURCES.parent))))
            inv.loc[inv.file == r.file, "folder"] = str(DUPS.relative_to(SOURCES))
        if log:
            with MOVES.open("a") as fh:
                fh.writelines(f"{a},{b},{c}\n" for a, b, c in log)
    inv = inv.drop(columns=["_rank", "_n", "content"]).sort_values(["table", "edition", "file"])
    OUT.mkdir(parents=True, exist_ok=True)
    inv.to_csv(OUT / "files_excel.csv", index=False)
    return inv


# --------------------------------------------------------------------------- sources per measure

@functools.lru_cache(maxsize=None)
def _catalog() -> pd.DataFrame:
    return pd.read_csv(DATA / "ipeds" / "digest" / "catalog.csv")


def _sources(spec: dict) -> list[dict]:
    """Every file holding the spec's table: {path, kind, edition, prepared, title}."""
    out, cat = [], _catalog()
    titles = dict(zip(cat.file, cat.title))
    for t in spec["tables"]:
        by_ed: dict[int, Path] = {}
        for f in sorted((REF / "digest").glob(f"20*/dt*_{t}.*")):
            if "__" in f.stem or f.suffix not in (".asp", ".html") or f.stem.split("_", 1)[1] != t:
                continue
            ed = int(f.parent.name)
            if ed not in by_ed or f.suffix == ".html":
                by_ed[ed] = f
        for ed, f in by_ed.items():
            rel = f"{ed}/{f.name}"
            title = titles.get(rel) or titles.get(rel.replace(".html", ".asp"), "")
            out.append({"path": f, "kind": "html", "edition": ed, "prepared": _prepared(_page(f)), "title": title})
    if spec.get("title"):
        x = cat[(cat.edition < 2013) & cat.title.str.contains(spec["title"].replace("(", "(?:"), case=False, regex=True, na=False)]
        for r in x.itertuples():
            f = REF / "digest" / r.file
            out.append({"path": f, "kind": "html", "edition": int(r.edition), "prepared": _prepared(_page(f)), "title": r.title})
    inv = OUT / "files_excel.csv"
    if inv.exists():
        x = pd.read_csv(inv, keep_default_na=False)
        x = x[x.table.isin(spec["tables"]) & (x.duplicate_of == "") & ~x.folder.str.contains("_duplicates")]
        for r in x.itertuples():
            out.append({"path": XLS / r.file, "kind": "excel", "edition": int(r.edition or 0),
                        "prepared": int(r.prepared or 0), "title": r.title})
    return out


@functools.lru_cache(maxsize=None)
def _parsed(path: Path) -> pd.DataFrame:
    try:
        v = parse_excel(path) if path.suffix.startswith(".xls") else D.parse_file(path)
    except Exception:  # noqa: BLE001 -- a malformed page: skip it, the other editions remain
        return pd.DataFrame()
    return v


def parse_spec(key: str) -> pd.DataFrame:
    """One spec's values from every source file (all editions; not yet reduced to the latest)."""
    spec = SPECS[key]
    measure = spec.get("measure", key)
    keep = re.compile(spec["col"], re.I)
    drop = re.compile(spec["col_not"], re.I) if spec.get("col_not") else None
    rows = []
    for s in _sources(spec):
        v = _parsed(s["path"])
        if v.empty:
            continue
        v = v.assign(col_label=v.col_label.fillna("").map(_clean_col))
        lab = v.col_label
        v = v[lab.map(lambda c: bool(keep.search(c)) and not DROP_COL.search(c) and not (drop and drop.search(c)))]
        if v.empty:
            continue
        if spec.get("year") == "title":
            y = _title_year(s["title"])
            v = v.assign(year=y)
        else:
            v = v.assign(year=v.col_label.map(_year))
            if spec.get("fall_to_spring"):
                v = v.assign(year=v.year + ~v.col_label.str.contains(r"\d{4}\s*[-–]\s*\d{2}"))
        v = v.assign(state=v.row_label.map(_state)).dropna(subset=["state", "year", "value"])
        proj = v.col_label.str.contains("project", case=False) if spec.get("proj") else pd.Series(False, index=v.index)
        v = v.assign(measure=measure + proj.map({True: "_proj", False: ""}))
        v = v.drop_duplicates(["state", "year", "measure"], keep="first")    # a table printed twice on one page
        rows.append(v.assign(edition=s["edition"], prepared=s["prepared"], rank=int(s["kind"] == "html"),
                             file=s["path"].name)[["year", "state", "measure", "value", "edition", "prepared", "rank", "file"]])
    cols = ["year", "state", "measure", "value", "edition", "prepared", "rank", "file"]
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=cols)


def latest(d: pd.DataFrame) -> pd.DataFrame:
    """Per state-year-measure, the latest edition (edition, prepared date; HTML before Excel on ties)."""
    d = d.assign(year=d.year.astype(int)).sort_values(["edition", "prepared", "rank"])
    p = d[d.measure.str.endswith("_proj")]
    if len(p):   # projections: one vintage (the edition projecting furthest ahead, latest on ties), after the actuals
        reach = p.groupby(["measure", "file"]).agg(y=("year", "max"), e=("edition", "max"), r=("rank", "max")).reset_index()
        last = reach.sort_values(["y", "e", "r"]).drop_duplicates("measure", keep="last").set_index("measure").file
        p = p[p.file == p.measure.map(last)]
        act = d[~d.measure.str.endswith("_proj")].groupby(["measure", "state"]).year.max()
        top = pd.Series(list(zip(p.measure.str.removesuffix("_proj"), p.state)), index=p.index).map(act)
        p = p[top.isna() | (p.year > top)]           # projected years after the state's last actual year
    d = d[~d.measure.str.endswith("_proj")].drop_duplicates(["year", "state", "measure"], keep="last")
    return pd.concat([d, p], ignore_index=True)[["year", "state", "measure", "value", "edition", "file"]]


def build_k12() -> pd.DataFrame:
    from .harmonize.finance import deflators
    from .states import REAL_BASE
    f = deflators("index_fy")            # academic-year (July-June) CPI-U, indexed by the year the school year ends
    d = latest(pd.concat([parse_spec(k) for k in SPECS], ignore_index=True))
    real = []
    for m, spec in SPECS.items():
        if spec.get("dollars") and "measure" not in spec:
            x = d[d.measure == m].copy()
            d.loc[d.measure == m, "measure"] = m + "_nominal"
            x["value"] = x.value * f.get(REAL_BASE) / x.year.map(f)
            real.append(x.dropna(subset=["value"]))
    d = pd.concat([d] + real, ignore_index=True).sort_values(["measure", "state", "year"])
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT / "k12_state.csv", index=False)
    w = d.pivot_table(index=["year", "state"], columns="measure", values="value").reset_index()
    w.to_csv(OUT / "k12_state_wide.csv", index=False)
    return w


# --------------------------------------------------------------------------- residence and migration (309.xx)

def build_migration() -> pd.DataFrame:
    """First-time students' residence and migration by state, every edition (IPEDS residence data, biennial
    until 2008): counts, the share of a state's residents who enroll out of state, and net migration.
    Universes: all first-time students (309.10), recent high school graduates (309.20), recent high school
    graduates in 4-year institutions (309.30). Year = the fall named in the title."""
    v = pd.read_parquet(DATA / "ipeds" / "digest" / "values.parquet",
                        columns=["edition", "table_id", "row_label", "col", "col_label", "value"])
    cat = _catalog()
    cat = cat[cat.title.str.contains(r"^residence and migration of all (freshmen|first-time|new undergraduate)", case=False, na=False)]
    cat = cat.assign(univ=cat.title.map(lambda t: "4yr" if re.search(r"4-year", t) else
                                        "hs" if re.search(r"high school in the (past|previous) 12 months", t) else "all"),
                     year=cat.title.map(_title_year))
    cat["table_id"] = cat.table_id.astype(str)
    v["table_id"] = v.table_id.astype(str)
    v = v.merge(cat[["edition", "table_id", "file", "univ", "year"]], on=["edition", "table_id"])
    v = v.assign(state=v.row_label.map(_state)).dropna(subset=["state", "value"])
    lab = v.col_label.fillna("").str.replace(r"(\w)- (\w)", r"\1\2", regex=True).str.replace("jurisdiction", "state")
    ratio = lab.str.contains("ratio", case=False)
    kind = pd.Series(None, index=v.index, dtype=object)
    kind[lab.str.contains(r"located in the state", case=False)] = "enrolled"
    kind[lab.str.contains(r"any state", case=False) & ~ratio] = "residents"
    kind[lab.str.contains(r"home state", case=False) & ~ratio] = "stay"
    kind[lab.str.contains(r"^migration of students \| out", case=False)] = "out"
    kind[lab.str.contains(r"^migration of students \| into", case=False)] = "in"
    v = v.assign(kind=kind).dropna(subset=["kind"])
    v = v.sort_values("edition").drop_duplicates(["univ", "year", "state", "kind"], keep="last")
    w = v.pivot_table(index=["univ", "year", "state"], columns="kind", values="value").reset_index()
    w["net"] = w["in"] - w.out
    w["leave_share"] = 100 * (w.residents - w.stay) / w.residents
    w["instate_share"] = 100 * w.stay / w.enrolled
    src = v.groupby(["univ", "year", "state"]).agg(edition=("edition", "max"), file=("file", "first")).reset_index()
    long = w.melt(id_vars=["univ", "year", "state"], var_name="kind", value_name="value").dropna(subset=["value"])
    long = long.merge(src, on=["univ", "year", "state"])
    long["measure"] = "fresh_" + long.kind + "_" + long.univ
    long = long[["year", "state", "measure", "value", "edition", "file"]].sort_values(["measure", "state", "year"])
    OUT_PS.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT_PS / "postsec_state.csv", index=False)
    wide = long.pivot_table(index=["year", "state"], columns="measure", values="value").reset_index()
    wide.to_csv(OUT_PS / "postsec_state_wide.csv", index=False)
    return wide


def build() -> pd.DataFrame:
    inventory()
    build_migration()
    return build_k12()


if __name__ == "__main__":
    w = build()
    long = pd.read_csv(OUT / "k12_state.csv")
    for m, g in long[long.state != "US"].groupby("measure"):
        ys = sorted(g.year.unique())
        print(f"{m:28s} {ys[0]}-{ys[-1]} {len(ys):3d} years, {g.state.nunique()} states")
