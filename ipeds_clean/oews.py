"""BLS Occupational Employment and Wage Statistics (OEWS, called OES before 2021): STEM jobs and wages by state.

    python -m ipeds_clean.oews              # cache any new workbooks, then rebuild every output
    python -m ipeds_clean.oews 2023 2024    # the years named only (outputs then hold just those years)

Source: the BLS OEWS zips saved in sources/bls_oews/ (oes{yy}st/nat for 1997-2002, oesm{yy}st/nat from
2003, plus November panels oesn03*/oesn04* and metro, industry and all-area files, which are inventoried but
not used). One estimate per year from the state file (50 states + DC; Guam, Puerto Rico and the Virgin
Islands are dropped) and the national file (state "US"). OEWS counts wage and salary jobs where they are
located (place of work), excluding the self-employed and farm owners; it is an establishment survey whose
estimates pool six semiannual panels over three years, so year-over-year changes are not designed as a time
series (BLS's own caution).

Years: 1999-2025. 1997 and 1998 use the old 5-digit OES occupation codes (e.g. 22126 electrical and
electronic engineers), which do not map cleanly to SOC, so they are inventoried only. Reference period: May
of each year from 2003; the 1999-2001 files are the annual (fourth-quarter) survey and 2002 is the November
2002 panel (BLS archive labelling; not stated in the files). The November 2003 and November 2004 panels are
skipped in favour of May.

STEM: SOC major groups 15 (computer & mathematical), 17 (architecture & engineering) and 19 (life, physical
& social science) plus 11-3021, 11-9041 and 11-9121, the definition in acs.py and dol.py. STEM employment is
the published major-group totals plus the three manager occupations (all six codes are unchanged across SOC
vintages, so the total is consistent even where detailed codes change). If exactly one of the 22 major groups
is suppressed and the all-occupations total is published, that group is recovered as the total minus the
other 21 (flagged). A suppressed manager occupation is left out of the total (flag; 57 state-years lack
11-9121, mostly small states). stem_a_mean is the employment-weighted mean of the six parts' mean wages,
which equals the true STEM mean. A STEM median cannot be computed from published data: stem_a_median_approx
is the employment-weighted median of the detailed STEM occupations' medians (top-coded medians enter as
"above everything"); treat it as an approximation. 1999-2000 have no all-occupations row: emp_total is the
sum of the 22 major groups (missing if any is suppressed) and all-occupation wages are missing.
Per 1,000 jobs and location quotients: published (jobs_1000 from 2009, loc_q from 2010) for single
occupations and major groups; for STEM they are computed here (stem_per_1000, stem_lq = state STEM share /
national-file STEM share), for every year. checks.csv shows the same formula reproduces BLS's SOC-15 values.

SOC vintages (soc_vintage column): 1999-2009 2000 SOC; 2010-2011 hybrid 2000/2010; 2012-2018 2010 SOC;
2019-2020 hybrid 2010/2018; 2021-2025 2018 SOC. Key occupations (KEY below; codes per year in
coverage.csv) follow the code changes. Breaks: software developers = 15-1031 + 15-1032 (computer software
engineers) to 2009, 15-1132 + 15-1133 2010-2018, 15-1256 2019-2020 (includes software QA analysts and
testers, so it jumps), 15-1252 from 2021 (QA/testers split out); a median is given only when one code
covers the group (2019 on), other years carry per-code medians in oews_occ_state.csv and an employment-
weighted mean. Computer & information research scientists 15-1011 / 15-1111 / 15-1221; information
security analysts start 2012 (combined with web developers in 2010-2011); data scientists start 2021.
Biological scientists sum 19-1021, 19-1022, 19-1023, 19-1029; the "all other" residual 19-1029 is not
published before 2004, so that group (and the detailed-occupation coverage) is lower before then.

Suppression: "**" employment not released, "*" wage not available, "#" wage at or above the top code (the
threshold per the files: $70/hr ($145,600/yr) 1999-2005, $80 by 2008, $90 by 2012, $100 ($208,000) by 2016,
$115 ($239,200) by 2023), "***" wage withdrawn
for reporting errors (1999 airline pilots, flight attendants), "~" fewer than 0.5% of establishments. All
become missing values; the meaning is kept in the flag column (long file) and *_flag columns (occupation
file). Key-occupation groups with some codes suppressed get a partial sum, flagged "partial".

Outputs (data/oews/):
  oews_state.csv        year, state, measure, value, flag, soc_vintage   (state "US" = national file)
  oews_state_wide.csv   one row per state-year: totals, STEM measures, SOC 15/17/19, key-occupation
                        employment and mean/median wages
  oews_occ_state.csv    one row per state-year-code for the key occupations: employment, RSE, jobs per
                        1,000, location quotient, mean and percentile annual wages, flags
  files.csv             every file in sources/bls_oews/: year, panel, kind, reference period, used or why not
  coverage.csv          per year: reference period, SOC vintage, states, suppressed rows, which fields
                        exist, the codes used for each key occupation
  checks.csv            state sums vs national file, computed vs published jobs-per-1,000 and LQ for
                        SOC 15, national STEM employment by year
  columns.csv           which source column fed each field, per file
Intermediate (cache/oews/): {zip stem}.parquet, the mapped columns of each workbook as text. Python's
zipfile rejects the CRC of oes97st.zip (unzip -t accepts it), so `unzip -p` is used as a fallback.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE, DATA, SOURCES

SRC = SOURCES / "bls_oews"
OUT = DATA / "oews"
RAW = CACHE / "oews"

# canonical field: source names (normalized: lower case, spaces -> "_"); first hit wins
FIELDS = {
    "area": ["area"],
    "st": ["st", "prim_state"],
    "occ_code": ["occ_code"],
    "occ_title": ["occ_title", "occ_titl"],
    "group": ["group", "occ_group", "o_group"],
    "tot_emp": ["tot_emp"],
    "emp_prse": ["emp_prse"],
    "jobs_1000": ["jobs_1000"],
    "loc_q": ["loc_q", "loc_quotient"],
    "h_mean": ["h_mean"],
    "a_mean": ["a_mean"],
    "mean_prse": ["mean_prse"],
    "h_median": ["h_median"],
    "a_pct10": ["a_pct10", "a_wpct10"],
    "a_pct25": ["a_pct25", "a_wpct25"],
    "a_median": ["a_median"],
    "a_pct75": ["a_pct75", "a_wpct75"],
    "a_pct90": ["a_pct90", "a_wpct90"],
    "annual": ["annual"],
    "hourly": ["hourly"],
}
NAME_RE = re.compile(r"^oes(m|n)?(\d{2})(st|nat|ma|in3|in4|all)\.zip$")


def _norm(c) -> str:
    return re.sub(r"\s+", "_", str(c).strip().lower())


def _year(yy: str) -> int:
    y = int(yy)
    return y + (1900 if y >= 90 else 2000)


def _zip_bytes(path: Path, member: str) -> bytes:
    """Python's zipfile rejects the CRC of a few 1990s zips that `unzip -t` accepts; fall back to unzip -p."""
    try:
        with zipfile.ZipFile(path) as z:
            return z.read(member)
    except zipfile.BadZipFile:
        return subprocess.run(["unzip", "-p", str(path), member], capture_output=True, check=True).stdout


def data_member(path: Path) -> str:
    """The data workbook inside a zip: the largest .xls/.xlsx that is not field_descriptions or an Excel lock file."""
    with zipfile.ZipFile(path) as z:
        cands = [i for i in z.infolist() if i.filename.lower().endswith((".xls", ".xlsx"))
                 and "field_desc" not in i.filename.lower() and "/~$" not in "/" + i.filename]
    return max(cands, key=lambda i: i.file_size).filename


def read_zip(path: Path) -> tuple[pd.DataFrame, dict, str, int]:
    """Read one state/national workbook (all rows, mapped columns, as text). Returns df, column map, member, header row."""
    import python_calamine as pc
    member = data_member(path)
    wb = pc.CalamineWorkbook.from_filelike(io.BytesIO(_zip_bytes(path, member)))
    rows = wb.get_sheet_by_index(0).to_python()
    hdr = next(i for i, r in enumerate(rows[:80]) if "occ_code" in [_norm(c) for c in r])
    head = [_norm(c) for c in rows[hdr]]
    idx, used = {}, {}
    for k, cands in FIELDS.items():
        for c in cands:
            if c in head:
                idx[k], used[k] = head.index(c), c
                break

    def txt(v):
        if v is None:
            return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()

    body = [r for r in rows[hdr + 1:] if len(r) > idx["occ_code"] and txt(r[idx["occ_code"]])]
    df = pd.DataFrame({k: [txt(r[i]) if i < len(r) else "" for r in body] for k, i in idx.items()})
    return df, used, member, hdr


def cached(fname: str) -> pd.DataFrame:
    """cache/oews/{zip stem}.parquet: the mapped columns of that zip's workbook, as text (written on first read)."""
    p = RAW / (Path(fname).stem + ".parquet")
    if p.exists():
        return pd.read_parquet(p)
    print(f"  reading {fname}", flush=True)
    df, used, member, hdr = read_zip(SRC / fname)
    df.attrs = {}
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    m = pd.DataFrame([{"file": fname, "member": member, "header_row": hdr, "field": k, "source_column": v}
                      for k, v in used.items()])
    cp = RAW / "columns.parquet"
    if cp.exists():
        old = pd.read_parquet(cp)
        m = pd.concat([old[old.file != fname], m], ignore_index=True)
    m.to_parquet(cp, index=False)
    return df


# ---------------------------------------------------------------- constants

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
        "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
        "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
        "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
        "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
        "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
        "54": "WV", "55": "WI", "56": "WY"}
TERR_FIPS = {"66": "GU", "72": "PR", "78": "VI"}
FIRST_SOC_YEAR = 1999     # 1997-1998 files use the old 5-digit OES occupation taxonomy
STEM_MAJORS = ["15-0000", "17-0000", "19-0000"]
STEM_MGRS = ["11-3021", "11-9041", "11-9121"]   # same codes in the 2000, 2010 and 2018 SOC


def soc_vintage(y: int) -> str:
    return ("2000 SOC" if y <= 2009 else "2000/2010 SOC hybrid" if y <= 2011 else "2010 SOC" if y <= 2018
            else "2010/2018 SOC hybrid" if y <= 2020 else "2018 SOC")


def ref_period(y: int, panel: str = "m") -> str:
    if panel == "n":
        return f"November {y}"
    return f"{y} annual survey (Q4)" if y <= 2001 else "November 2002" if y == 2002 else f"May {y}"


# Key occupations. key -> (label, [(first year, last year, [codes])]); codes summed when more than one.
KEY = {
    "software_dev": ("Software developers", [
        (1999, 2009, ["15-1031", "15-1032"]),     # computer software engineers, applications + systems software
        (2010, 2018, ["15-1132", "15-1133"]),     # software developers, applications + systems software
        (2019, 2020, ["15-1256"]),                # hybrid: software developers AND software QA analysts/testers
        (2021, 2100, ["15-1252"])]),              # software developers (QA/testers split out as 15-1253)
    "comp_research_sci": ("Computer & information research scientists", [
        (1999, 2009, ["15-1011"]), (2010, 2018, ["15-1111"]), (2019, 2100, ["15-1221"])]),
    "comp_systems_analyst": ("Computer systems analysts", [
        (1999, 2009, ["15-1051"]), (2010, 2018, ["15-1121"]), (2019, 2100, ["15-1211"])]),
    "info_security_analyst": ("Information security analysts", [
        (2012, 2018, ["15-1122"]), (2019, 2100, ["15-1212"])]),
    "data_scientist": ("Data scientists", [(2021, 2100, ["15-2051"])]),
    "statistician": ("Statisticians", [(1999, 2100, ["15-2041"])]),
    "electrical_eng": ("Electrical engineers", [(1999, 2100, ["17-2071"])]),
    "electronics_eng": ("Electronics engineers, except computer", [(1999, 2100, ["17-2072"])]),
    "mechanical_eng": ("Mechanical engineers", [(1999, 2100, ["17-2141"])]),
    "civil_eng": ("Civil engineers", [(1999, 2100, ["17-2051"])]),
    "aerospace_eng": ("Aerospace engineers", [(1999, 2100, ["17-2011"])]),
    "chemical_eng": ("Chemical engineers", [(1999, 2100, ["17-2041"])]),
    "industrial_eng": ("Industrial engineers", [(1999, 2100, ["17-2112"])]),
    "comp_hardware_eng": ("Computer hardware engineers", [(1999, 2100, ["17-2061"])]),
    "biological_sci": ("Biological scientists (biochemists & biophysicists, microbiologists, zoologists, all other)", [
        (1999, 2100, ["19-1021", "19-1022", "19-1023", "19-1029"])]),
    "medical_sci": ("Medical scientists, except epidemiologists", [(1999, 2100, ["19-1042"])]),
    "chemist": ("Chemists", [(1999, 2100, ["19-2031"])]),
    "physicist": ("Physicists", [(1999, 2100, ["19-2012"])]),
    "cis_manager": ("Computer & information systems managers", [(1999, 2100, ["11-3021"])]),
    "eng_manager": ("Architectural & engineering managers", [(1999, 2100, ["11-9041"])]),
    "natsci_manager": ("Natural sciences managers", [(1999, 2100, ["11-9121"])]),
}
NUM = ["tot_emp", "emp_prse", "jobs_1000", "loc_q", "h_mean", "a_mean", "mean_prse", "h_median",
       "a_pct10", "a_pct25", "a_median", "a_pct75", "a_pct90"]
FLAGS = {"**": "employment not released", "*": "wage not available", "#": "wage top-coded",
         "***": "wage removed (reporting errors)", "~": "under 0.5% of establishments reporting"}


def key_codes(key: str, y: int) -> list[str]:
    return next((c for a, b, c in KEY[key][1] if a <= y <= b), [])


# ---------------------------------------------------------------- inventory

def inventory() -> pd.DataFrame:
    rows = []
    for p in sorted(SRC.iterdir()):
        m = NAME_RE.match(p.name)
        r = {"file": p.name, "bytes": p.stat().st_size, "year": None, "panel": "", "kind": "", "used": False}
        if not m:
            r["note"] = "not an OEWS zip"
        else:
            y, kind, panel = _year(m.group(2)), m.group(3), m.group(1) or ""
            r.update(year=y, kind=kind, panel={"m": "May", "n": "November", "": "annual"}[panel],
                     reference_period=ref_period(y, panel or "m"))
            if kind not in ("st", "nat"):
                r["note"] = {"ma": "metropolitan/nonmetropolitan areas", "in3": "national industry (3-digit)",
                             "in4": "national industry (4-digit)", "all": "all-area combined file"}[kind] + \
                    ": out of scope (inventory only)"
            elif panel == "n":
                r["note"] = "November panel; the May panel of the same year is the one used"
            elif y < FIRST_SOC_YEAR:
                r["note"] = "old 5-digit OES occupation codes (pre-SOC); STEM definition cannot be applied; not used"
            else:
                r.update(used=True, note="used")
        rows.append(r)
    return pd.DataFrame(rows).astype({"year": "Int64"})


# ---------------------------------------------------------------- cleaning

def clean(df: pd.DataFrame, national: bool) -> pd.DataFrame:
    """Numbers parsed; each suppression symbol kept in a <col>_flag column; state postal code attached."""
    df = df.copy()
    if national:
        df["state"] = "US"
    else:
        a = df.area.str.replace(r"\.0$", "", regex=True).str.zfill(2)
        df["state"] = a.map(FIPS)
        df["territory"] = a.map(TERR_FIPS)
    for c in NUM:
        if c not in df:
            df[c] = ""
        v = df[c].fillna("").str.strip()
        df[c] = pd.to_numeric(v.str.replace(",", ""), errors="coerce")
        df[c + "_flag"] = v.where(v.isin(list(FLAGS)), "")
    df["group"] = df.group.fillna("").str.strip().str.lower()
    df["occ_code"] = df.occ_code.str.strip()
    return df


def load_year(y: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pre = "oes" if y <= 2002 else "oesm"
    st, nat = f"{pre}{y % 100:02d}st.zip", f"{pre}{y % 100:02d}nat.zip"
    s = clean(cached(st), national=False)
    n = clean(cached(nat), national=True)
    info = {"territory_rows_dropped": int(s.territory.notna().sum())}
    s = s[s.state.notna()]
    return s, n, info


# ---------------------------------------------------------------- measures

def _wmedian(vals: pd.Series, w: pd.Series) -> float:
    """Weighted median; top-coded values enter as +inf (rank only), so a median landing on one is missing."""
    o = vals.sort_values()
    cw = w[o.index].cumsum()
    v = o[cw >= cw.iloc[-1] / 2].iloc[0]
    return float(v) if np.isfinite(v) else np.nan


def measures(df: pd.DataFrame, y: int) -> tuple[list[tuple], list[dict]]:
    """Long rows (state, measure, value, flag) and key-occupation detail rows for one geography's records."""
    st = df.state.iloc[0]
    by = df.drop_duplicates("occ_code").set_index("occ_code")
    out, occ = [], []

    def cell(code, col):
        if code not in by.index:
            return np.nan, "not published"
        return by.at[code, col], FLAGS.get(by.at[code, col + "_flag"], "")

    # all occupations
    tot, f = cell("00-0000", "tot_emp")
    if np.isnan(tot) and f == "not published":   # 1999-2000: no all-occupations row; sum the 22 major groups
        maj = df[df.group == "major"]
        tot = maj.tot_emp.sum() if maj.tot_emp.notna().all() else np.nan
        f = "sum of major groups (no all-occupations row)"
    out.append((st, "emp_total", tot, f))
    for col in ["a_mean", "a_median"]:
        v, f = cell("00-0000", col)
        out.append((st, f"{col}_total", v, f))

    # STEM = SOC 15, 17, 19 major groups + three STEM manager occupations
    parts = STEM_MAJORS + STEM_MGRS
    emp = {c: cell(c, "tot_emp")[0] for c in parts}
    resid = ""
    maj = df[(df.group == "major") & (df.occ_code != "00-0000")].drop_duplicates("occ_code")
    if maj.tot_emp.isna().sum() == 1 and not np.isnan(tot) and "00-0000" in by.index:
        c = maj.occ_code[maj.tot_emp.isna()].iloc[0]   # the one suppressed major group = total - the other 21
        if c in STEM_MAJORS:
            emp[c] = tot - maj.tot_emp.sum()
            resid = f"{c} derived as total minus the other major groups"
    supp = [c for c in parts if np.isnan(emp[c])]
    stem = np.nansum(list(emp.values())) if not any(np.isnan(emp[c]) for c in STEM_MAJORS) else np.nan
    out += [(st, "stem_emp", stem, "; ".join(x for x in [("missing " + " ".join(supp)) if supp else "", resid] if x)),
            (st, "stem_parts_suppressed", len(supp), " ".join(supp)),
            (st, "stem_share", stem / tot if tot else np.nan, ""),
            (st, "stem_per_1000", stem / tot * 1000 if tot else np.nan, "computed")]
    am = {c: cell(c, "a_mean")[0] for c in parts}
    ok = [c for c in parts if not np.isnan(emp[c]) and not np.isnan(am[c])]
    wsum = sum(emp[c] for c in ok)
    out.append((st, "stem_a_mean", sum(emp[c] * am[c] for c in ok) / wsum if wsum else np.nan,
                "" if len(ok) == len(parts) else f"{len(parts) - len(ok)} of 6 parts without mean wage"))
    det = df[(df.group.isin(["", "detailed"])) & ~df.occ_code.str.endswith("0000")
             & (df.occ_code.str[:2].isin(["15", "17", "19"]) | df.occ_code.isin(STEM_MGRS))]
    d = det[det.tot_emp.notna()]
    med = d.a_median.where(d.a_median_flag != "#", np.inf)
    d2 = d[med.notna()]
    out += [(st, "stem_emp_detailed_published", d.tot_emp.sum(), "sum of detailed STEM occupations with employment"),
            (st, "stem_detailed_coverage", d.tot_emp.sum() / stem if stem else np.nan, ""),
            (st, "stem_a_median_approx", _wmedian(med[d2.index], d2.tot_emp) if len(d2) else np.nan,
             "employment-weighted median of detailed-occupation medians (not a true median)")]
    for c in STEM_MAJORS + STEM_MGRS:
        k = "soc" + c[:2] if c.endswith("0000") else "mgr" + c.replace("-", "")
        for col, nm in [("tot_emp", "emp"), ("jobs_1000", "jobs_1000"), ("loc_q", "loc_q"),
                        ("a_mean", "a_mean"), ("a_median", "a_median")]:
            v, f = cell(c, col)
            out.append((st, f"{nm}_{k}", v, f))
        v = emp[c]
        out.append((st, f"share_{k}", v / tot if tot else np.nan, ""))

    # key occupations
    for key in KEY:
        codes = key_codes(key, y)
        if not codes:
            continue
        rows = by.reindex([c for c in codes if c in by.index])
        for c, r in rows.iterrows():
            occ.append({"state": st, "key": key, "occ_code": c, "occ_title": r.occ_title,
                        **{k: r[k] for k in NUM if k not in ("h_mean", "h_median")},
                        **{k + "_flag": FLAGS.get(r[k + "_flag"], "") for k in ["tot_emp", "a_mean", "a_median"]}})
        if rows.empty:
            out.append((st, f"emp_{key}", np.nan, "not published"))
            continue
        e = rows.tot_emp
        miss = [c for c in rows.index if np.isnan(e[c])] + [c for c in codes if c not in by.index]
        out.append((st, f"emp_{key}", e.sum() if not miss else (e.sum() if e.notna().any() else np.nan),
                    ("partial: missing " + " ".join(miss)) if miss and e.notna().any() else
                    ("employment not released" if miss else "")))
        ok = rows[e.notna() & rows.a_mean.notna()]
        out.append((st, f"a_mean_{key}", (ok.tot_emp * ok.a_mean).sum() / ok.tot_emp.sum() if len(ok) else np.nan,
                    "" if len(ok) == len(codes) else ("emp-weighted over published codes" if len(ok) else
                                                      FLAGS.get(rows.a_mean_flag.iloc[0], "not available"))))
        if len(codes) == 1:
            for col in ["a_median", "a_pct10", "a_pct90", "jobs_1000", "loc_q"]:
                v, f = cell(codes[0], col)
                out.append((st, f"{col}_{key}", v, f))
    return out, occ


def build_year(y: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    s, n, info = load_year(y)
    longs, occs = [], []
    for _, g in list(s.groupby("state")) + [("US", n)]:
        o, k = measures(g, y)
        longs += o
        occs += k
    long = pd.DataFrame(longs, columns=["state", "measure", "value", "flag"])
    # STEM location quotient: state STEM share / national STEM share (national file)
    sh = long[long.measure == "stem_share"].set_index("state").value
    lq = (sh / sh["US"]).rename("value").reset_index().assign(measure="stem_lq", flag="computed vs national file")
    long = pd.concat([long, lq], ignore_index=True)
    long.insert(0, "year", y)
    occ = pd.DataFrame(occs)
    occ.insert(0, "year", y)
    info.update({"states": s.state.nunique(), "rows_state_file": len(s), "rows_national_file": len(n),
                 "emp_suppressed_state_rows": int((s.tot_emp_flag == "**").sum()),
                 "has_jobs_1000": bool(s.jobs_1000.notna().any()), "has_loc_q": bool(s.loc_q.notna().any()),
                 "checks": _checks(y, s, n, long)})
    return long, occ, info


def _checks(y, s, n, long) -> list[dict]:
    v = long.set_index(["state", "measure"]).value
    st_states = long.state.unique()
    r = []
    for m in ["emp_total", "stem_emp", "emp_soc15", "emp_soc17", "emp_soc19"]:
        sm = v[[(x, m) for x in st_states if x != "US" and (x, m) in v.index]].sum()
        r.append({"year": y, "check": f"sum of states vs national file: {m}", "ours": sm, "reference": v.get(("US", m)),
                  "diff_pct": (sm / v.get(("US", m)) - 1) * 100,
                  "note": "states exclude territories and unallocated; state estimates are benchmarked separately"})
    tot = s[s.occ_code == "00-0000"].set_index("state").tot_emp
    c = s[s.occ_code == "15-0000"].set_index("state")
    if c.jobs_1000.notna().any() and len(tot):
        calc = c.tot_emp / tot * 1000
        dd = (calc - c.jobs_1000).abs()
        r.append({"year": y, "check": "SOC 15 jobs per 1,000: computed vs published, max abs diff", "ours": dd.max(),
                  "reference": 0, "diff_pct": np.nan, "note": ""})
    if c.loc_q.notna().any() and len(tot):
        us = n.set_index("occ_code").tot_emp
        calc = (c.tot_emp / tot) / (us["15-0000"] / us["00-0000"])
        dd = (calc - c.loc_q).abs()
        r.append({"year": y, "check": "SOC 15 location quotient: computed vs published, max abs diff", "ours": dd.max(),
                  "reference": 0, "diff_pct": np.nan, "note": "published LQs are rounded to 2 decimals"})
    return r


# ---------------------------------------------------------------- build

WIDE = ["emp_total", "a_mean_total", "a_median_total", "stem_emp", "stem_share", "stem_per_1000", "stem_lq",
        "stem_a_mean", "stem_a_median_approx", "stem_parts_suppressed", "stem_detailed_coverage",
        "emp_soc15", "emp_soc17", "emp_soc19", "a_mean_soc15", "a_mean_soc17", "a_mean_soc19",
        "a_median_soc15", "a_median_soc17", "a_median_soc19", "loc_q_soc15", "loc_q_soc17", "loc_q_soc19",
        "jobs_1000_soc15", "jobs_1000_soc17", "jobs_1000_soc19"]


def main(years: list[int] | None = None):
    inv = inventory()
    years = years or sorted(int(y) for y in inv[inv.used].year.unique())
    longs, occs, cov, chk = [], [], [], []
    for y in years:
        print(f"OEWS {y}", flush=True)
        long, occ, info = build_year(y)
        longs.append(long)
        occs.append(occ)
        chk += info.pop("checks")
        cov.append({"year": y, "reference_period": ref_period(y), "soc_vintage": soc_vintage(y), **info,
                    **{f"codes_{k}": " ".join(key_codes(k, y)) for k in KEY}})
    long = pd.concat(longs, ignore_index=True)
    long["soc_vintage"] = long.year.map(soc_vintage)
    OUT.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT / "oews_state.csv", index=False)
    w = long.pivot_table(index=["year", "state"], columns="measure", values="value").reset_index()
    keycols = [c for c in w if any(c == f"{p}_{k}" for k in KEY for p in ["emp", "a_mean", "a_median"])]
    w = w[["year", "state"] + [c for c in WIDE if c in w] + keycols]
    w.insert(2, "soc_vintage", w.year.map(soc_vintage))
    w.insert(3, "reference_period", w.year.map(ref_period))
    w.to_csv(OUT / "oews_state_wide.csv", index=False)
    occ = pd.concat(occs, ignore_index=True)
    occ.insert(3, "key_label", occ.key.map(lambda k: KEY[k][0]))
    occ.insert(1, "soc_vintage", occ.year.map(soc_vintage))
    occ.to_csv(OUT / "oews_occ_state.csv", index=False)
    pd.DataFrame(cov).to_csv(OUT / "coverage.csv", index=False)
    c = pd.DataFrame(chk)
    us = long[(long.state == "US") & (long.measure == "stem_emp")]
    c = pd.concat([c, pd.DataFrame({"year": us.year, "check": "national STEM employment (national file)",
                                    "ours": us.value, "reference": np.nan, "diff_pct": np.nan,
                                    "note": "expect about 10 million in 2023 (SOC 15+17+19 + 3 managers)"})])
    c.sort_values(["check", "year"]).to_csv(OUT / "checks.csv", index=False)
    inv.to_csv(OUT / "files.csv", index=False)
    cp = RAW / "columns.parquet"
    if cp.exists():
        pd.read_parquet(cp).sort_values(["file", "field"]).to_csv(OUT / "columns.csv", index=False)
    return long


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or None)
