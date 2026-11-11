"""Civil Rights Data Collection (CRDC): the state-level tables OCR published, parsed into tidy files, so the
state series reach back before the school-level files (ipeds_clean/crdc.py) and the 2009-10 sample year gets
OCR's weighted state estimates.

    python -m ipeds_clean.crdc_tables          # inventory (and move exact duplicates), parse, harmonize, combine

Source: sources/ed_crdc/state_tables/ (860 files saved from OCR's web tools, 2026-11; the data are OCR's):
  2000-, 2004-, 2006-<state>-projection.xls   OCR Elementary and Secondary School Survey (2000) and CRDC (2004,
                                              2006) "Projected Values" for a state (sheets Page 1-3: items by sex x
                                              race/disability/LEP, Number and %). Survey year Y is taken as the
                                              Y-(Y+1) school year (fall membership), so year = Y + 1.
  2009-10-Estimations-<State>.xls             2009-10 "Estimated Values" from OCR's weighted district sample; cells
                                              such as "238343 (*)" (relative SE > 0.30), "(!)", "‡" (suppressed,
                                              SE > 50%), "†" (differs from other published sources), "--".
  <ST>.xls, <ST> (n).xls, <ST>-AP-and-IB.xlsx one state's tables by topic (mostly 2011-12; the title row gives the
                                              school year).
  <Topic>.xlsx / <Topic> (n).xlsx             "by state" tables (all states in rows; sheets Total/Male/Female(/
                                              Nonbinary)), 2011-12 to 2021-22; the (n) copies are other school years
                                              or exact duplicates.
  archives/CRDCArchive-*.zip                  OCR's CRDC archive exports, one survey year each (1970, 1980, 1990,
                                              1998): district records with the sampling weight DISTWGHT; state values
                                              are weighted sums (DISTWGHT x value over districts reporting the item; no
                                              nonresponse imputation, so national membership runs ~4-6% below NCES).
                                              The 1998 export has no weights: long file only, not harmonized.
  Overall Enrollment_export_*.xlsx            a national export from OCR's data tool (no year in the file).

Only 5 files were byte-identical to another (4 copies of sources/ed_crdc/ appendix workbooks and one "(n)"
table); one more holds the same data as another file in different bytes (kept, its rows dropped). Most "(n)"
copies are other school years of the same table. Exact duplicates (same md5) are moved to sources/_duplicates_to_delete/crdc_state_tables/ (logged in
sources/new_data_moves.csv); the copy kept is the one without a "(n)" suffix, else the shortest name.

Outputs (data/crdc_tables/):
  files.csv          every file: md5, duplicate_of, school_year(s), first table title, kind, used / why not
  crdc_tables_long.csv   state, school_year, year (spring), table, item, group (column group: race, disability,
                     EL, total, course...), sex, value, pct, flag (OCR's markers), source_file, sheet
                     (state "US" = OCR's national row; "US_PR" = "50 states, DC and Puerto Rico")
  crdc_tables_wide.csv   one row per state-year: measures harmonized to crdc.py's names where the definition matches
                     (counts of students, all grades/schools in the state): enr_all (membership), enr_gt (gifted and
                     talented), enr_ap (at least one AP course), enr_apmath, enr_apsci, enr_apcs, enr_ib, enr_calc,
                     enr_advm, enr_alg2, enr_geom, enr_biol, enr_chem, enr_phys, enr_csci, enr_satact, each with _m/_f,
                     and enr_gt_per100_all (gifted per 100 students). US = sum of the 50 states + DC.
                     Discipline, harassment, retention, LEP, disability and staffing tables are in the long file only.
  checks.csv         published state totals vs the school-level sums (crdc.py), conflicting duplicate values, and
                     national series by year
Then crdc.combine() rebuilds data/crdc/crdc_state_wide.csv (every year; `source` column).
"""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import sys
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA, ROOT, SOURCES

SRC = SOURCES / "ed_crdc" / "state_tables"
DUP = SOURCES / "_duplicates_to_delete" / "crdc_state_tables"
MOVES = SOURCES / "new_data_moves.csv"
OUT = DATA / "crdc_tables"

NAMES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
         "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
         "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
         "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
         "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
         "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
         "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
         "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
         "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
         "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR"}
KEY = {re.sub(r"[^a-z]", "", k.lower()): v for k, v in NAMES.items()}
KEY.update({"dc": "DC", "nation": "US", "unitedstates": "US", "national": "US", "us": "US",
            "50statesdistrictofcolumbiaandpuertorico": "US_PR"})
STATES51 = [v for v in NAMES.values() if v != "PR"]
SEX = {"male": "M", "m": "M", "female": "F", "f": "F", "total": "T", "t": "T", "nonbinary": "X"}
VALUE_HDR = {"number", "estimation"}
PCT_HDR = {"percent", "%"}


def state_code(s: str) -> str | None:
    return KEY.get(re.sub(r"[^a-z0-9]", "", str(s).lower()))


def clean_label(s) -> str:
    s = re.sub(r"\s+", " ", str(s).replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[A-Za-z\)])[¹²³⁴\d]+$", "", s).strip()   # footnote markers ("Membership¹", "mathematics1")


# ---------------------------------------------------------------- inventory and duplicates

def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _keep_rank(name: str) -> tuple:
    return (bool(re.search(r" \(\d+\)\.\w+$", name)), len(name), name)


def dedupe(move: bool = True) -> pd.DataFrame:
    """md5 of every file under state_tables/ (and of copies already moved out); exact duplicates are moved."""
    rows = []
    for p in sorted(SRC.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rows.append({"file": str(p.relative_to(SRC)), "md5": md5(p), "bytes": p.stat().st_size,
                         "location": "state_tables"})
    for p in sorted(DUP.glob("*")) if DUP.exists() else []:
        if p.is_file():
            rows.append({"file": p.name, "md5": md5(p), "bytes": p.stat().st_size, "location": "moved"})
    df = pd.DataFrame(rows)
    # files elsewhere in sources/ed_crdc/ that a state_tables file duplicates (e.g. the appendix workbook)
    parent = {md5(p): f"../{p.name}" for p in (SOURCES / "ed_crdc").glob("*.xlsx")}
    df["duplicate_of"] = ""
    for h, g in df.groupby("md5"):
        here = g[g.location == "state_tables"]
        if h in parent:
            keep = parent[h]
        elif len(here):
            keep = min(here.file, key=_keep_rank)
        else:
            keep = min(g.file, key=_keep_rank)
        df.loc[g.index[g.file != keep], "duplicate_of"] = keep
    if move:
        moves = []
        for i, r in df[(df.duplicate_of != "") & (df.location == "state_tables")].iterrows():
            src = SRC / r.file
            DUP.mkdir(parents=True, exist_ok=True)
            dst = DUP / src.name
            k = 1
            while dst.exists():
                dst = DUP / f"{src.stem}__{k}{src.suffix}"
                k += 1
            shutil.move(str(src), str(dst))
            moves.append({"action": "moved", "from": str(src.relative_to(ROOT)), "to": str(dst.relative_to(ROOT))})
            df.loc[i, ["file", "location"]] = [dst.name, "moved"]
        if moves:
            log = pd.DataFrame(moves)
            log.to_csv(MOVES, mode="a", header=not MOVES.exists(), index=False)
            print(f"  moved {len(moves)} exact duplicates to {DUP.relative_to(ROOT)}", flush=True)
    return df


# ---------------------------------------------------------------- cell values

NUM = re.compile(r"^\s*(-?[\d,]*\.?\d+(?:[eE]-?\d+)?)\s*(.*?)\s*$")


def parse_cell(s) -> tuple[float, str]:
    """'238343 (*)' -> (238343, '(*)'); '‡' -> (nan, '‡'); '1-3' -> (nan, '1-3'); '' -> (nan, '')."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return np.nan, ""
    t = str(s).replace("\xa0", " ").strip()
    if not t:
        return np.nan, ""
    if re.fullmatch(r"\d+\s*-\s*\d+", t) or t.startswith(("≤", "<", ">")):
        return np.nan, t
    m = NUM.match(t)
    if m:
        try:
            return float(m.group(1).replace(",", "")), m.group(2)
        except ValueError:
            pass
    return np.nan, t


def _is_valueish(s) -> bool:
    v, f = parse_cell(s)
    return not np.isnan(v) or f in {"‡", "†", "--", "-", ".", "#", "§", "*", "1-3", "≤3"} or bool(
        re.fullmatch(r"\d+\s*-\s*\d+|[≤<]\s*\d+", f))


# ---------------------------------------------------------------- generic OCR table parser

def read_grid(x: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    g = pd.read_excel(x, sheet, header=None, dtype=str)
    return g.fillna("").map(lambda v: str(v).replace("\xa0", " ").strip()) if len(g) else g


def title_of(g: pd.DataFrame) -> str:
    texts = [v for v in g.head(6).values.ravel() if isinstance(v, str) and len(v) > 3 and not _is_valueish(v)]
    return " ".join(texts[:2]) if texts and texts[0][:4].isdigit() else (texts[0] if texts else "")


def school_year_of(text: str, fname: str) -> str | None:
    m = re.search(r"School Year (\d{4})\s*[-–]\s*(\d{2,4})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)[-2:]}"
    m = re.match(r"(20\d\d)-(?:\w+-projection)", fname)
    if m:
        y = int(m.group(1))
        return f"{y}-{(y + 1) % 100:02d}"
    if fname.startswith("2009-10-Estimations"):
        return "2009-10"
    m = re.search(r"(\d{4})\s*[-–]\s*(\d{2,4})", text)
    return f"{m.group(1)}-{m.group(2)[-2:]}" if m else None


def parse_sheet(g: pd.DataFrame, file_state: str | None, sheet_sex: str | None) -> list[dict]:
    """Rows of a sheet laid out like OCR's published tables: label columns (state, item, sex) on the left, then
    column groups each with a Number (or Estimation) column, an optional flag column and a Percent/% column;
    header blocks may repeat down the sheet (one per printed page)."""
    out = []
    if g.empty:
        return out
    hdr_rows = [i for i in range(len(g)) if sum(v.lower() in VALUE_HDR for v in g.iloc[i]) >= 2]
    bare = False
    if not hdr_rows:   # tables with one value column per group and no Number row: header = row above the data
        first = next((i for i in range(len(g)) if any(state_code(v) for v in g.iloc[i])
                      and sum(not np.isnan(parse_cell(v)[0]) for v in g.iloc[i]) >= 1), None)
        if first is None or first < 1:
            return out
        hdr_rows, bare = [first - 1], True
    for bi, h in enumerate(hdr_rows):
        end = hdr_rows[bi + 1] - 2 if bi + 1 < len(hdr_rows) else len(g)
        hdr = [v.lower() if v.lower() in VALUE_HDR | PCT_HDR else "" for v in g.iloc[h]] if bare else \
            [v.lower() for v in g.iloc[h]]
        above = [g.iloc[r] for r in range(max(0, h - 3), h + (1 if bare else 0))]
        ncol = g.shape[1]

        def label_at(c):
            for r in reversed(above):
                v = r.iloc[c]
                if v and len(v) < 200 and v.lower() not in VALUE_HDR | PCT_HDR and \
                        (not _is_valueish(v) or re.fullmatch(r"\d{3}", v)):   # "504"
                    return v
            return ""

        data = g.iloc[h + 1:end]
        first_val = min([c for c in range(ncol) if hdr[c] in VALUE_HDR] or [ncol])
        # value columns: Number/Estimation, plus labelled single columns (Number of Schools, Total Students...)
        cols = {}

        def numeric_col(c):
            v = [x for x in data.iloc[:, c] if x]
            return bool(v) and sum(_is_valueish(x) for x in v) >= 0.8 * len(v)

        for c in range(ncol):
            left = [k for k in cols if k < c]
            k = max(left) if left else None
            if hdr[c] in VALUE_HDR:
                cols[c] = {"group": label_at(c), "pct": None, "flag": None}
            elif hdr[c] in PCT_HDR:
                if k is not None and cols[k]["pct"] is None and c - k <= 2 and not (label_at(c) and c - k == 1
                                                                                    and label_at(c) != label_at(k)):
                    cols[k]["pct"] = c
                elif numeric_col(c):   # a column OCR headed "Percent" that holds counts, or a standalone percent
                    cols[c] = {"group": label_at(c) or "Percent", "pct": None, "flag": None}
            elif not hdr[c] and label_at(c) and numeric_col(c):   # Total Students, Number of Schools
                cols[c] = {"group": label_at(c), "pct": None, "flag": None}
            elif not hdr[c] and k is not None and c - k == 1 and not label_at(c):
                cols[k]["flag"] = c
        # label columns: everything left of the first value column
        first = min(cols) if cols else ncol
        labcols = [c for c in range(first) if c not in cols]
        role = {}
        valrows = data[data.apply(lambda r: any(_is_valueish(r.iloc[c]) for c in cols), axis=1)] if cols else data
        for c in labcols:
            v = [x for x in valrows.iloc[:, c] if x]
            if not v:
                continue
            hl = (label_at(c) or g.iloc[h, c]).lower()
            if hl in ("sex", "gender") or sum(x.lower() in SEX for x in v) >= 0.6 * len(v):
                role[c] = "sex"
            elif sum(state_code(x) is not None for x in v) >= 0.6 * len(v):
                role[c] = "state"
            elif (label_at(c) or g.iloc[h, c]) and (label_at(c) or g.iloc[h, c]).lower() not in ("state",):
                role[c] = "item"
        sexc = next((c for c, r in role.items() if r == "sex"), None)
        statec = next((c for c, r in role.items() if r == "state"), None)
        itemc = [c for c, r in role.items() if r == "item"]
        rows = []
        pending = None
        for i in range(len(data)):
            r = data.iloc[i]
            vals = {c: r.iloc[c] for c in cols}
            has_val = any(_is_valueish(v) for v in vals.values())
            labels = {c: r.iloc[c] for c in role}
            if has_val and not any(labels.values()) and i + 1 < len(data):
                nxt = data.iloc[i + 1]
                if any(nxt.iloc[c] for c in role) and not any(_is_valueish(nxt.iloc[c]) for c in cols):
                    pending = r     # values printed one row above their labels (2000 "Membership")
                    continue
            if pending is not None and not has_val:
                r = pd.concat([r.iloc[:first], pending.iloc[first:]])
                has_val, pending = True, None
            if not has_val:
                continue
            rows.append(r)
        if not rows:
            continue
        # items: OCR prints an item's label on one row of its Male/Female/Total block
        blocks, b, prev_sex, prev_state, seen = [], -1, None, None, set()
        for r in rows:
            sx = SEX.get(r.iloc[sexc].lower()) if sexc is not None else None
            st = r.iloc[statec] if statec is not None else None
            if b < 0 or prev_sex == "T" or (sx and sx in seen) or (sx is None and sexc is not None) or \
                    (st is not None and st != prev_state and st) or (sexc is None):
                b += 1
                seen = set()
            blocks.append(b)
            seen.add(sx)
            prev_sex, prev_state = sx, (st or prev_state)
        item_of = {}
        for r, bb in zip(rows, blocks):
            lab = " ".join(clean_label(r.iloc[c]) for c in itemc if r.iloc[c])
            if lab and bb not in item_of:
                item_of[bb] = lab
        state_of, last_state = {}, file_state
        for r, bb in zip(rows, blocks):
            if statec is not None and r.iloc[statec]:
                last_state = state_code(r.iloc[statec])
            state_of.setdefault(bb, last_state)
        for r, bb in zip(rows, blocks):
            sx = SEX.get(r.iloc[sexc].lower()) if sexc is not None and r.iloc[sexc] else (sheet_sex or "T")
            st = state_code(r.iloc[statec]) if statec is not None and r.iloc[statec] else state_of.get(bb)
            for c, spec in cols.items():
                v, fl = parse_cell(r.iloc[c])
                if np.isnan(v) and not fl:
                    continue
                pct, pfl = parse_cell(r.iloc[spec["pct"]]) if spec["pct"] is not None else (np.nan, "")
                fl2 = r.iloc[spec["flag"]] if spec["flag"] is not None else ""
                out.append({"state": st, "item": item_of.get(bb, ""), "group": clean_label(spec["group"]) or "Total",
                            "sex": sx, "value": v, "pct": pct,
                            "flag": " ".join(x for x in (fl, fl2, pfl and f"pct:{pfl}") if x)})
    return out


def sheet_sex(sheet: str, title: str) -> str | None:
    s = sheet.strip().lower()
    if s in ("total", "male", "female", "nonbinary"):
        return SEX[s]
    t = title.lower()
    for w, k in [("nonbinary students", "X"), ("female students", "F"), (" male students", "M")]:
        if w in t:
            return k
    return None


def kind_of(f: str) -> str:
    n = Path(f).name
    if n.endswith("-projection.xls"):
        return "projection"
    if n.startswith("2009-10-Estimations"):
        return "estimation"
    if n.startswith("CRDCArchive"):
        return "archive"
    if n.startswith("Overall Enrollment_export"):
        return "export"
    if "Appendix" in n:
        return "documentation"
    if re.match(r"^[A-Z]{2}(-AP-and-IB| \(\d+\))?\.xlsx?$|^[A-Z]{2}-Enrollment-by-[Ss]tate", n):
        return "state topic table"
    return "by-state table"


def parse_excel(p: Path) -> tuple[list[dict], dict]:
    rows, meta = [], {"titles": [], "years": set()}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        x = pd.ExcelFile(p, engine="calamine")
        name = p.name
        fstate = None
        m = re.match(r"^(20\d\d)-(\w+)-projection", name) or re.match(r"^2009-10-Estimations-(\w+)", name)
        if m:
            fstate = state_code(m.groups()[-1])
        m = re.match(r"^([A-Z]{2})[ .-]", name)
        if fstate is None and m:
            fstate = m.group(1)
        years = {}
        for sh in x.sheet_names:
            g = read_grid(x, sh)
            if g.empty:
                continue
            t = title_of(g)
            sy = school_year_of(" ".join(g.head(6).values.ravel()), name)
            years[sh] = sy
            if t:
                meta["titles"].append(t)
            st = fstate
            m = re.search(r"(?:State of|Values for) ([A-Za-z .]+?)\s*$", " ".join(v for v in g.head(5).values.ravel() if v))
            if m and state_code(m.group(1)):
                st = state_code(m.group(1))
            for r in parse_sheet(g, st, sheet_sex(sh, t)):
                r.update({"school_year": sy, "table": t, "sheet": sh})
                rows.append(r)
        known = [y for y in years.values() if y]
        for r in rows:   # a sheet without a year takes the file's
            if r["school_year"] is None and known:
                r["school_year"] = known[0]
        meta["years"] = {r["school_year"] for r in rows if r["school_year"]}
    return rows, meta


def parse_export(p: Path) -> list[dict]:
    """Overall Enrollment_export: Group x National / National Female / Male / Nonbinary (no year given)."""
    d = pd.read_excel(p, engine="calamine", dtype=str)
    out = []
    for _, r in d.iterrows():
        for c in d.columns[1:]:
            v, fl = parse_cell(r[c])
            sx = {"National": "T", "National Female": "F", "National Male": "M", "National Nonbinary": "X"}.get(c, c)
            out.append({"state": "US_PR", "item": "Overall enrollment", "group": clean_label(r.iloc[0]), "sex": sx,
                        "value": v, "pct": np.nan, "flag": fl, "school_year": None,
                        "table": "Overall Enrollment (OCR data tool export)", "sheet": "data"})
    return out


# ---------------------------------------------------------------- CRDC archive (district time series 1968-1998)

ARCH_RACE = {"AI": "American Indian/Alaska Native", "AS": "Asian/Pacific Islander", "BL": "Black", "HI": "Hispanic",
             "WH": "White", "TR": "Total", "TM": "Total Male", "TF": "Total Female", "DS": "Disabled", "LE": "LEP"}


def parse_archive(p: Path) -> tuple[list[dict], dict]:
    """Weighted state sums of every numeric item (DISTWGHT x value over districts reporting it)."""
    z = zipfile.ZipFile(p)
    defs = pd.read_csv(io.BytesIO(z.read("Definitions.csv")), dtype=str)
    title = dict(zip(defs["Variable Name"], defs["Variable Title"]))
    module = dict(zip(defs["Variable Name"], defs["Sub-Module Name"]))
    frames = []
    for n in sorted(n for n in z.namelist() if n.startswith("DataTS")):
        d = pd.read_csv(io.BytesIO(z.read(n)), dtype=str, low_memory=False)
        d.columns = [c.strip() for c in d.columns]
        frames.append(d)
    d = frames[0]
    for e in frames[1:]:
        new = [c for c in e.columns if c not in d.columns or c in ("DISCODE", "Year_")]
        d = d.merge(e[new], on=["DISCODE", "Year_"], how="outer")
    skip = {"DISCODE", "DISSTAT", "Year_", "DISCITY", "DISCNTY", "DISCODE1", "DISNAME", "DISSTAT1", "DISSTRT",
            "DISZIP", "DISTWGHT", "DISTSUB"}
    weighted = "DISTWGHT" in d
    w = pd.to_numeric(d.DISTWGHT, errors="coerce").fillna(1.0) if weighted else pd.Series(1.0, index=d.index)
    how = "weighted district sums" if weighted else "unweighted sums of sampled districts (no weights in file)"
    st = d.DISSTAT.str.strip().str.upper()
    yr = pd.to_numeric(d.Year_, errors="coerce").astype("Int64")
    rows = []
    for c in d.columns:
        if c in skip:
            continue
        v = pd.to_numeric(d[c].str.strip(), errors="coerce")
        if v.notna().sum() == 0:
            continue
        tmp = pd.DataFrame({"state": st, "y": yr, "wv": v * w, "w": w.where(v.notna()), "n": v.notna()})
        agg = tmp.groupby(["state", "y"]).agg(value=("wv", "sum"), wsum=("w", "sum"), n=("n", "sum"))
        agg = agg[agg.n > 0]
        tot = tmp.groupby(["state", "y"]).w.size()
        m = re.match(r"^(.*)_([A-Z]{2})$", c)
        grp, sx = (ARCH_RACE.get(m.group(2), m.group(2)), "T") if m else ("Total", "T")
        if m and m.group(2) in ("TM", "TF"):
            grp, sx = "Total", m.group(2)[1]
        for (s, y), a in agg.iterrows():
            rows.append({"state": s, "school_year": f"{int(y)}-{(int(y) + 1) % 100:02d}", "item": title.get(c, c),
                         "group": grp, "sex": sx, "value": a.value, "pct": np.nan,
                         "flag": f"districts reporting {int(a.n)} of {int(tot.get((s, y), 0))}",
                         "table": f"CRDC archive, {how}: {module.get(c, '')} ({c})", "sheet": "DataTS"})
    return rows, {"titles": ["CRDC archive district time series (weighted sums)"],
                  "years": {r["school_year"] for r in rows}}


# ---------------------------------------------------------------- harmonization

# (measure key, regex on "table | item" text (lowercase), regex that excludes)
STUDENTS_EXCL = r"teacher|classes|offering|passed|passing|taking ap tests|exam|did not take|retained|retention|" \
                r"certified|counsel|single.sex|failing|percentage of (public |high |middle )?schools|schools with"
HARM = [
    ("calc", r"calculus", r"ap |advanced placement"),
    ("advm", r"advanced math", r"ap |advanced placement"),
    ("alg2", r"algebra ii\b", r"ap "),
    ("geom", r"geometry", r"in grade 8|grade 7 or 8|middle"),
    ("biol", r"\bbiology\b", r"ap |advanced placement"),
    ("chem", r"\bchemistry\b", r"ap |advanced placement"),
    ("phys", r"\bphysics\b", r"ap |advanced placement"),
    ("csci", r"computer science", r"ap |advanced placement"),
    ("apcs", r"(ap|advanced placement) comp", r""),
    ("apmath", r"(ap|advanced placement) math", r""),
    ("apsci", r"(ap|advanced placement) science", r""),
    ("ap", r"at least one (ap|advanced placement)|^.*enrolled in ap\b|advanced placement enrollment$|"
           r"students enrolled in advanced placement courses|^enrolled in ap$", r"math|science|comp|foreign|other"),
    ("ib", r"international baccalaureate|ib diploma|\bib\b", r""),
    ("gt", r"gifted", r"program(s)?$|offering"),
    ("satact", r"sat or act|act or sat|sat and act|sat/act", r""),
    ("all", r"(^|\| )membership\b|school (fe|non)?(male |binary )?students overall",
     r"prek|pre-k|preschool|early childhood"),
]
RACE7 = {"american indian or alaska native": "am", "asian": "as", "hispanic or latino of any race": "hi",
         "black or african american": "bl", "white": "wh", "native hawaiian or other pacific islander": "hp",
         "two or more races": "tr"}


def harmonize(long: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long published rows -> (state-year measures, the rows used, with their measure)."""
    d = long[long.kind.isin(["projection", "estimation", "state topic table", "by-state table", "archive"])].copy()
    d = d[d.state.notna() & d.school_year.notna()]
    text = (d.table.fillna("") + " | " + d.item.fillna("")).str.lower()
    d["key"] = None
    for key, pat, excl in HARM:
        hit = d.key.isna() & text.str.contains(pat, regex=True)
        if excl:
            hit &= ~text.str.contains(excl, regex=True)
        if key != "satact":
            hit &= ~text.str.contains(STUDENTS_EXCL, regex=True)
        # archive items carry their own names ("Gifted/Talented: Total", "AP Math: ...")
        d.loc[hit, "key"] = key
    arch = d.kind == "archive"
    arch_map = {r"\(GIFT_": "gt", r"\(APMTH_": "apmath", r"\(APSCI_": "apsci", r"\(APCMP_": "apcs",
                r"\(MEM_": "all"}
    d.loc[arch, "key"] = None
    arch &= ~d.table.str.contains("unweighted")   # 1998 file has no weights: long file only
    for pat, key in arch_map.items():
        d.loc[arch & d.table.str.contains(pat, regex=True), "key"] = key   # noqa
    d = d[d.key.notna()]
    g = d.group.str.lower().str.replace(r"\s+", " ", regex=True)
    total = g.isin(["total", "total students", "number of students", ""]) | g.str.startswith("total")
    total &= ~g.str.contains("school")
    rows = []
    for (st, sy), x in d.groupby(["state", "school_year"]):
        rec = {"state": st, "school_year": sy}
        used = []
        for key in x.key.unique():
            k = x[x.key == key]
            kt = k[total.loc[k.index]]
            stem = "all" if key == "all" else key
            for sx, suf in [("T", ""), ("M", "_m"), ("F", "_f")]:
                v = kt[kt.sex == sx].value.dropna()
                if len(v):
                    rec[f"enr_{stem}{suf}"] = v.iloc[0]
                    used.append(kt[kt.sex == sx].index[0])
            if "enr_" + stem not in rec and f"enr_{stem}_m" in rec and f"enr_{stem}_f" in rec:
                rec[f"enr_{stem}"] = rec[f"enr_{stem}_m"] + rec[f"enr_{stem}_f"]
            if key in ("calc", "phys", "csci", "ap", "apmath", "apsci", "apcs") and sy >= "2011-12":   # 7 races
                kr = k[(k.sex == "T") & g.loc[k.index].isin(RACE7)]
                for _, r in kr.drop_duplicates("group").iterrows():
                    rec[f"enr_{stem}_{RACE7[r.group.lower()]}"] = r.value
        rows.append(rec)
        d.loc[used, "used_as"] = "x"
    w = pd.DataFrame(rows)
    if w.empty:
        return w, d
    if "enr_gt" in w and "enr_all" in w:
        w["enr_gt_per100_all"] = w.enr_gt * 100 / w.enr_all
    return w, d


def us_sum(w: pd.DataFrame) -> pd.DataFrame:
    """US = 50 states + DC where all 51 report; OCR's national rows (US, US_PR) are kept as published_us_*."""
    out = []
    num = [c for c in w.columns if c.startswith("enr_") and "per100" not in c]
    for sy, x in w.groupby("school_year"):
        s = x[x.state.isin(STATES51)]
        rec = {"state": "US", "school_year": sy}
        for c in num:
            v = s[c].dropna()
            if len(v) == 51:
                rec[c] = v.sum()
        if "enr_gt" in rec and "enr_all" in rec:
            rec["enr_gt_per100_all"] = rec["enr_gt"] * 100 / rec["enr_all"]
        out.append(rec)
    keep = w[w.state.isin(STATES51)]
    return pd.concat([keep, pd.DataFrame(out)], ignore_index=True)


SOURCE_OF = {"projection": "OCR published state projections", "estimation": "OCR published state estimates",
             "archive": "OCR CRDC archive (weighted district sums)",
             "state topic table": "OCR published state tables", "by-state table": "OCR published state tables"}


# ---------------------------------------------------------------- main

def main(move: bool = True):
    OUT.mkdir(parents=True, exist_ok=True)
    print("CRDC state tables: md5 inventory", flush=True)
    inv = dedupe(move)
    longs, meta = [], {}
    keep = inv[(inv.duplicate_of == "") & (inv.location == "state_tables")]
    for f in keep.file:
        p = SRC / f
        k = kind_of(f)
        try:
            if k == "archive":
                rows, m = parse_archive(p)
            elif k == "export":
                rows, m = parse_export(p), {"titles": ["Overall Enrollment (OCR data tool export)"], "years": set()}
            elif k == "documentation":
                rows, m = [], {"titles": [], "years": set(), "why": "documentation (also in sources/ed_crdc/)"}
            else:
                rows, m = parse_excel(p)
        except Exception as e:   # noqa: BLE001 - recorded in files.csv
            rows, m = [], {"titles": [], "years": set(), "why": f"could not parse: {type(e).__name__}: {e}"[:200]}
        for r in rows:
            r["source_file"], r["kind"] = f, k
        longs += rows
        sig = hashlib.md5(pd.DataFrame(rows)[["state", "school_year", "table", "item", "group", "sex", "value", "pct"]]
                          .astype(str).sort_values(["state", "table", "item", "group", "sex"]).to_csv(index=False)
                          .encode()).hexdigest() if rows else None
        m["content"] = sig
        meta[f] = (k, m, len(rows))
    # same parsed content in files that are not byte-identical (re-downloads): noted, not moved
    first_with = {}
    for f in sorted(meta, key=_keep_rank):
        sig = meta[f][1].get("content")
        if sig and sig in first_with:
            meta[f][1]["same_data_as"] = first_with[sig]
        elif sig:
            first_with[sig] = f
    long = pd.DataFrame(longs)
    long = long[long.state.notna() | (long.kind == "export")]
    long["year"] = long.school_year.map(lambda s: int(s[:4]) + 1 if isinstance(s, str) else np.nan)
    cols = ["state", "school_year", "year", "table", "item", "group", "sex", "value", "pct", "flag", "source_file",
            "sheet", "kind"]
    long = long[cols]
    # identical rows from different (non-identical) files: keep one, record conflicts
    key = ["state", "school_year", "table", "item", "group", "sex"]
    conf = long.groupby(key, dropna=False).value.agg(["nunique", "count"])
    conflicts = conf[conf["nunique"] > 1]
    long = long.drop_duplicates(key + ["value", "pct"])
    long.to_csv(OUT / "crdc_tables_long.csv", index=False)

    w, used = harmonize(long)
    used_files = set(used[used.get("used_as") == "x"].source_file) if "used_as" in used else set()
    if not w.empty:
        w = us_sum(w)
        w["year"] = w.school_year.map(lambda s: int(s[:4]) + 1)
        kinds = used.groupby("school_year").kind.agg(lambda s: sorted(set(s)))
        w["source"] = w.school_year.map(lambda sy: "; ".join(SOURCE_OF[k] for k in kinds.get(sy, [])))
        lead = ["year", "school_year", "state", "source"]
        order = ["enr_all", "enr_all_m", "enr_all_f", "enr_gt", "enr_gt_m", "enr_gt_f", "enr_gt_per100_all"]
        rest = sorted(c for c in w.columns if c not in lead + order)
        w = w[lead + [c for c in order if c in w] + rest].sort_values(["year", "state"])
        w.to_csv(OUT / "crdc_tables_wide.csv", index=False)

    # files.csv
    fr = []
    for _, r in inv.iterrows():
        k = kind_of(r.file)
        if r.duplicate_of:
            fr.append({**r[["file", "md5", "bytes", "location", "duplicate_of"]], "same_data_as": "", "kind": k,
                       "school_year": "",
                       "title": "", "rows": 0, "used": False, "why": f"exact duplicate of {r.duplicate_of}"})
            continue
        kk, m, n = meta.get(r.file, (k, {"titles": [], "years": set()}, 0))
        yrs = ", ".join(sorted(y for y in m["years"] if y))
        why = m.get("why") or ("harmonized measures in crdc_tables_wide.csv" if r.file in used_files else
                               "long file only (no harmonized measure)" if n else "no table rows found")
        if kk == "export":
            why = "long file only; national, no school year in the file"
        same = m.get("same_data_as", "")
        if same:
            why = f"same data as {same} (different bytes, so not moved); rows dropped as duplicates"
        fr.append({**r[["file", "md5", "bytes", "location", "duplicate_of"]], "same_data_as": same, "kind": kk,
                   "school_year": yrs, "title": (m["titles"][0] if m["titles"] else "")[:300], "rows": n,
                   "used": n > 0 and not same, "why": why})
    files = pd.DataFrame(fr)
    files.to_csv(OUT / "files.csv", index=False)

    # checks
    chk = [{"check": "files", "school_year": "", "state": "", "value": len(files), "note": "files inventoried"},
           {"check": "exact duplicates", "school_year": "", "state": "", "value": int((files.duplicate_of != "").sum()),
            "note": f"moved to {DUP.relative_to(ROOT)}"},
           {"check": "same parsed data, different bytes", "school_year": "", "state": "",
            "value": int((files.same_data_as.fillna("") != "").sum()), "note": "re-downloads; kept in place"},
           {"check": "conflicting values for one key", "school_year": "", "state": "", "value": len(conflicts),
            "note": "same state/year/table/item/group/sex with different values in different files"}]
    sch = DATA / "crdc" / "crdc_state_school_wide.csv"
    if sch.exists() and not w.empty:
        s = pd.read_csv(sch)
        for m_ in ["enr_calc", "enr_phys", "enr_chem", "enr_ap", "enr_apmath", "enr_gt", "enr_all", "enr_satact"]:
            if m_ not in w or m_ not in s:
                continue
            j = w[["school_year", "state", m_]].merge(s[["school_year", "state", m_]], on=["school_year", "state"],
                                                      suffixes=("_pub", "_sch")).dropna()
            for sy, x in j.groupby("school_year"):
                us = x[x.state == "US"]
                ratio = (x[f"{m_}_sch"] / x[f"{m_}_pub"]).replace([np.inf, -np.inf], np.nan)
                chk.append({"check": f"school-level / published {m_}", "school_year": sy, "state": "US",
                            "value": float(us[f"{m_}_sch"].iloc[0] / us[f"{m_}_pub"].iloc[0]) if len(us) else np.nan,
                            "note": f"states: median {ratio.median():.3f}, min {ratio.min():.3f}, max {ratio.max():.3f}"
                                    " (school-level enr_* other than gifted/all counts high schools only)"})
        for m_ in ["enr_all", "enr_gt", "enr_ap", "enr_apmath", "enr_apsci", "enr_calc", "enr_phys", "enr_gt_per100_all"]:
            if m_ in w:
                for _, r in w[w.state == "US"].dropna(subset=[m_]).iterrows():
                    chk.append({"check": f"published US {m_}", "school_year": r.school_year, "state": "US",
                                "value": r[m_], "note": r.source})
    pd.DataFrame(chk).to_csv(OUT / "checks.csv", index=False)
    if len(conflicts):
        conflicts.reset_index().to_csv(OUT / "conflicts.csv", index=False)
    from . import crdc
    crdc.combine()
    print(f"  {len(files)} files, {int((files.duplicate_of != '').sum())} duplicates, {len(long):,} long rows, "
          f"{len(w)} state-years", flush=True)
    return long, w


if __name__ == "__main__":
    main(move="--no-move" not in sys.argv)
