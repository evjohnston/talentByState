"""Department of Labor, Office of Foreign Labor Certification (OFLC): LCA and PERM disclosure data by state.

    python -m ipeds_clean.dol            # cache any new workbooks, then rebuild every output
    python -m ipeds_clean.dol lca        # one program only (lca or perm)

Source: the OFLC public disclosure workbooks saved in sources/dol_oflc/ (the data are
DOL's). Two programs, both counted by the fiscal year of the OFLC decision (Oct 1 - Sep 30, the year the file
is labelled with) and by the state of the (primary, first-listed) worksite:

* LCA, Labor Condition Applications for H-1B, H-1B1 (Chile, Singapore) and E-3 (Australia) workers, FY2008-
  FY2026. An LCA is the employer's attestation step before a USCIS petition; one LCA can cover several
  worker positions and is not a visa. FY2008 and part of FY2009 come from the old eFile system (H-1B_Case_
  Data_*), the rest of FY2009 on from iCERT/FLAG. From FY2020 OFLC publishes one file per quarter. Most hold
  only that quarter's decisions, but not all: the FY2021 Q3 file repeats every Q1 and Q2 case (it is Q1-Q3
  cumulative), the FY2023 Q2 file repeats Q1, a few FY2025 Q1 cases recur later, and the only FY2026 file
  (Q3) is year-to-date. So cases are de-duplicated by case number within each year, keeping the row from
  the latest file (latest status); after that, total determinations match the Selected Statistics exactly
  (e.g. FY2021 528,902; FY2024 561,037). FY2010's file has no visa-class column, so H-1B-only measures are
  missing that year (all-class lca_* measures exist). The FY2009 iCERT file repeats 7,256 rows verbatim.
  Worksite is the first worksite on the form (the LCA_Worksites files listing extra sites are not used). Employer state is kept as a second geography because the
  USCIS H-1B Employer Data Hub places petitions at the employer's address.
* PERM, permanent labor certification (ETA-9089), the employer step of most employment-based green cards,
  FY2008-FY2026. FY2024 has two files (old 9089 form and the new form introduced in June 2023); both are
  used. The new form drops the worker's citizenship, class of admission and education, so those measures end
  in FY2024 (old-form cases only that year) and the new-form FY2024 file has no SOC code.

Certified: LCA status CERTIFIED or CERTIFIED-WITHDRAWN (certified, so it could support a petition; the
employer withdrew it later, usually when the job ended). *_certonly measures count CERTIFIED alone. OFLC's
Selected Statistics count status as of each quarter's close, so their "certified" sits between the two (our
cert + certified-withdrawn positions run 1-3% above, CERTIFIED-only positions about 1-1.5% below; see
checks.csv). PERM certified = CERTIFIED or CERTIFIED-EXPIRED (*_certonly = CERTIFIED alone), which matches
the Selected Statistics to the case for FY2017-FY2023 and FY2026. The eFile years mark withdrawal in a
separate flag.
STEM occupations: SOC major groups 15, 17, 19 plus 11-3021, 11-9041, 11-9121 (the definition in acs.py).
FY2008 eFile LCAs carry 3-digit DOT occupation codes rather than SOC, so STEM and SOC measures start FY2009
(iCERT cases only for FY2009). Wages: the lower bound of the offered wage, annualized by its unit (hour x2080,
week x52, bi-weekly x26, month x12, year x1); annual values outside $10k-$2m are treated as entry errors and
left out of medians. Where a vintage has no offered-wage unit (LCA FY2010, PERM FY2013) the prevailing-wage
unit is used. Medians are of applications, not positions.
State codes: two-letter postal codes for the 50 states and DC; territories keep their codes (PR, GU, VI, MP,
AS, FM, MH, PW); full names and stray spellings are mapped; anything else is dropped from the state rows but
counted in "US", which is every certified case.

Outputs (data/dol/):
  lca_state.csv, perm_state.csv            fiscal_year, state, measure, value  (state "US" = national)
  lca_state_wide.csv, perm_state_wide.csv  one row per state-year; partial = 1 for FY2026 (through Q3, June)
  files.csv                                every file in sources/dol_oflc/: program, fiscal year, used or why not,
                                           rows read, rows after de-duplication
  columns.csv                              which source column fed each field, per file
  checks.csv                               national and top-state totals vs the Selected Statistics PDFs
Intermediate (cache/dol/): {program}_{fy}.parquet, the needed columns of that year's workbook(s) with
a `file` column, written the first time a workbook is read.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "dol_oflc"
OUT = ROOT / "data" / "dol"
RAW = ROOT / "cache" / "dol"
PARTIAL_FY = 2026   # FY2026 files run through Q3 (decisions to June 30, 2026)

# canonical field: candidate source names, normalized (upper case, non-alphanumerics -> "_"); first hit wins
FIELDS = {
    "lca": {
        "case": ["CASE_NUMBER", "LCA_CASE_NUMBER", "CASE_NO"],
        "status": ["CASE_STATUS", "STATUS", "APPROVAL_STATUS"],
        "withdrawn": ["WITHDRAWN"],
        "visa": ["VISA_CLASS", "PROGRAM", "PROGRAM_DESIGNATION"],
        "workers": ["TOTAL_WORKER_POSITIONS", "TOTAL_WORKERS", "NBR_IMMIGRANTS"],
        "soc": ["SOC_CODE", "LCA_CASE_SOC_CODE", "OCCUPATIONAL_CODE", "JOB_CODE"],
        "work_state": ["WORKSITE_STATE", "WORKSITE_STATE_1", "LCA_CASE_WORKLOC1_STATE", "WORK_LOCATION_STATE1",
                       "STATE_1"],
        "emp_state": ["EMPLOYER_STATE", "LCA_CASE_EMPLOYER_STATE", "STATE"],
        "wage": ["WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_FROM_1", "WAGE_RATE_OF_PAY", "LCA_CASE_WAGE_RATE_FROM",
                 "WAGE_RATE_1"],
        "wage_unit": ["WAGE_UNIT_OF_PAY", "WAGE_UNIT_OF_PAY_1", "LCA_CASE_WAGE_RATE_UNIT", "RATE_PER_1",
                      "PW_UNIT_1"],
        "dependent": ["H_1B_DEPENDENT", "H1B_DEPENDENT"],
    },
    "perm": {
        "case": ["CASE_NUMBER", "CASE_NO"],
        "status": ["CASE_STATUS"],
        "soc": ["PW_SOC_CODE", "PWD_SOC_CODE"],
        "work_state": ["JOB_INFO_WORK_STATE", "WORKSITE_STATE", "PRIMARY_WORKSITE_STATE"],
        "emp_state": ["EMPLOYER_STATE", "EMPLOYER_STATE_PROVINCE", "EMP_STATE"],
        "citizenship": ["COUNTRY_OF_CITIZENSHIP", "COUNTRY_OF_CITZENSHIP"],
        "admission": ["CLASS_OF_ADMISSION"],
        "educ_req": ["JOB_INFO_EDUCATION", "MINIMUM_EDUCATION"],
        "educ_fw": ["FOREIGN_WORKER_INFO_EDUCATION", "FOREIGN_WORKER_EDUCATION"],
        "wage": ["WAGE_OFFER_FROM_9089", "WAGE_OFFERED_FROM_9089", "WAGE_OFFER_FROM", "JOB_OPP_WAGE_FROM"],
        "wage_unit": ["WAGE_OFFER_UNIT_OF_PAY_9089", "WAGE_OFFERED_UNIT_OF_PAY_9089", "WAGE_OFFER_UNIT_OF_PAY",
                      "JOB_OPP_WAGE_PER", "PW_UNIT_OF_PAY_9089"],
    },
}
LCA_RE = re.compile(r"^(H-1B_Case_Data_FY|Icert_ LCA_ FY|H-1B_FY|H-1B_iCert_LCA_FY|LCA_FY|H-1B_Disclosure_Data_FY|"
                    r"LCA_Disclosure_Data_FY)(\d{2,4})(_Q(\d))?[^/]*\.xlsx$")
PERM_RE = re.compile(r"^PERM_(Disclosure_Data_)?(New_Form_)?FY(\d{2,4})(_Q\d|_EOY)?\.xlsx$")

STATES = {"AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS", "CA": "CALIFORNIA",
          "CO": "COLORADO", "CT": "CONNECTICUT", "DE": "DELAWARE", "DC": "DISTRICT OF COLUMBIA", "FL": "FLORIDA",
          "GA": "GEORGIA", "HI": "HAWAII", "ID": "IDAHO", "IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA",
          "KS": "KANSAS", "KY": "KENTUCKY", "LA": "LOUISIANA", "ME": "MAINE", "MD": "MARYLAND",
          "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA", "MS": "MISSISSIPPI", "MO": "MISSOURI",
          "MT": "MONTANA", "NE": "NEBRASKA", "NV": "NEVADA", "NH": "NEW HAMPSHIRE", "NJ": "NEW JERSEY",
          "NM": "NEW MEXICO", "NY": "NEW YORK", "NC": "NORTH CAROLINA", "ND": "NORTH DAKOTA", "OH": "OHIO",
          "OK": "OKLAHOMA", "OR": "OREGON", "PA": "PENNSYLVANIA", "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA",
          "SD": "SOUTH DAKOTA", "TN": "TENNESSEE", "TX": "TEXAS", "UT": "UTAH", "VT": "VERMONT", "VA": "VIRGINIA",
          "WA": "WASHINGTON", "WV": "WEST VIRGINIA", "WI": "WISCONSIN", "WY": "WYOMING"}
TERR = {"PR": "PUERTO RICO", "GU": "GUAM", "VI": "VIRGIN ISLANDS", "MP": "NORTHERN MARIANA ISLANDS",
        "AS": "AMERICAN SAMOA", "FM": "FEDERATED STATES OF MICRONESIA", "MH": "MARSHALL ISLANDS", "PW": "PALAU"}
STATE_MAP = {**{v: k for k, v in {**STATES, **TERR}.items()}, **{k: k for k in {**STATES, **TERR}},
             "WASHINGTON DC": "DC", "WASHINGTON D C": "DC", "D C": "DC", "US VIRGIN ISLANDS": "VI",
             "U S VIRGIN ISLANDS": "VI", "VIRGIN ISLANDS US": "VI", "MARIANA ISLANDS": "MP",
             "NORTHERN MARIANA ISLANDS CNMI": "MP", "CNMI": "MP", "MICRONESIA": "FM", "SAIPAN": "MP"}
STEM_MGR = {"113021", "119041", "119121"}
SOC2 = {"11": "Management", "13": "Business & financial", "15": "Computer & mathematical",
        "17": "Architecture & engineering", "19": "Life, physical & social science", "21": "Community & social service",
        "23": "Legal", "25": "Education", "27": "Arts, media", "29": "Healthcare practitioners",
        "31": "Healthcare support", "33": "Protective service", "35": "Food preparation", "37": "Building & grounds",
        "39": "Personal care", "41": "Sales", "43": "Office & admin support", "45": "Farming, fishing, forestry",
        "47": "Construction & extraction", "49": "Installation & repair", "51": "Production",
        "53": "Transportation", "55": "Military"}
ANNUAL = {"Y": 1, "A": 1, "H": 2080, "W": 52, "B": 26, "M": 12}


def _norm(c) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(c).upper()).strip("_")


# ---------------------------------------------------------------- inventory

def inventory() -> pd.DataFrame:
    """Classify every file in sources/dol_oflc/ (program, fiscal year, whether it is a data file this module reads)."""
    rows = []
    for p in sorted(SRC.iterdir()):
        f, prog, fy, q, use, why = p.name, "", None, None, False, ""
        m, n = (None if re.search("Appendix|Worksite", f) else LCA_RE.match(f)), PERM_RE.match(f)
        if m:
            prog, fy, q, use = "lca", int(m.group(2)), m.group(4), True
        elif n:
            prog, fy, use = "perm", int(n.group(3)), True
        else:
            u = f.upper()
            prog = next((k for k in ["H-2A", "H2A", "H-2B", "H2B", "CW", "PW", "PERM", "LCA", "H-1B", "H1B"]
                         if u.startswith(k)), "")
            prog = {"H2A": "H-2A", "H2B": "H-2B", "H1B": "lca", "H-1B": "lca", "LCA": "lca", "PERM": "perm",
                    "CW": "CW-1"}.get(prog, prog) or ("state pdf" if re.fullmatch(r"[A-Z]{2}\.pdf", f) else "other")
            y = re.search(r"FY_?\s?(\d{4}|\d{2})(?!\d)", f) or re.search(r"(20\d\d)", f)
            fy = int(y.group(1)) if y else None
            why = ("LCA worksite/appendix companion file (first worksite is in the main file)" if prog == "lca"
                   and f.endswith(".xlsx") else "record layout" if "layout" in f.lower() or f.endswith((".doc", ".docx", ".rtf"))
                   else ("Selected Statistics PDF, used for checks.csv" if prog in ("lca", "perm") else
                         "Selected Statistics PDF, out of scope") if "selected" in f.lower()
                   else "out of scope (inventory only)")
        if fy is not None and fy < 100:
            fy += 2000
        rows.append({"file": f, "program": prog, "fiscal_year": fy, "quarter": q, "used": use, "note": why,
                     "bytes": p.stat().st_size})
    return pd.DataFrame(rows).astype({"fiscal_year": "Int64"})


# ---------------------------------------------------------------- reading and caching

def read_workbook(path: Path, program: str) -> tuple[pd.DataFrame, dict]:
    """Stream one workbook with python-calamine, keeping only the mapped columns (as text)."""
    import python_calamine as pc
    wb = pc.CalamineWorkbook.from_path(str(path))
    sheets = [wb.get_sheet_by_index(i) for i in range(len(wb.sheet_names))]
    sh = max(sheets, key=lambda s: s.height)           # data sheet; others are blank or notes
    it = sh.iter_rows()
    head = [_norm(c) for c in next(it)]
    idx, used = {}, {}
    for k, cands in FIELDS[program].items():
        for c in cands:
            if c in head:
                idx[k], used[k] = head.index(c), c
                break
    cols = {k: [] for k in idx}
    for r in it:
        if not r[idx["case"]]:
            continue
        for k, i in idx.items():
            v = r[i]
            cols[k].append("" if v is None else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)))
    wb.close()
    return pd.DataFrame(cols), used


def cached(program: str, fy: int, files: list[str], colmap: list) -> pd.DataFrame:
    p = RAW / f"{program}_{fy}.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        if set(df.file.unique()) == set(files):
            m = pd.read_parquet(RAW / "columns.parquet") if (RAW / "columns.parquet").exists() else None
            if m is not None:
                colmap.extend(m[m.file.isin(files)].to_dict("records"))
            return df
    parts = []
    for f in files:
        print(f"  reading {f}", flush=True)
        d, used = read_workbook(SRC / f, program)
        parts.append(d.assign(file=f))
        colmap.extend({"program": program, "fiscal_year": fy, "file": f, "field": k, "source_column": v}
                      for k, v in used.items())
    df = pd.concat(parts, ignore_index=True)
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    m = pd.DataFrame([r for r in colmap if r["file"] in files])
    cp = RAW / "columns.parquet"
    if cp.exists():
        old = pd.read_parquet(cp)
        m = pd.concat([old[~old.file.isin(files)], m], ignore_index=True)
    m.to_parquet(cp, index=False)
    return df


# ---------------------------------------------------------------- cleaning

def state(s: pd.Series) -> pd.Series:
    k = s.fillna("").str.upper().str.replace(r"[^A-Z ]", " ", regex=True).str.split().str.join(" ")
    return k.map(STATE_MAP)


def soc6(s: pd.Series) -> pd.Series:
    d = s.fillna("").str.replace(r"\D", "", regex=True)
    return d.str[:6].where((d.str.len() >= 6) & d.str[:2].isin(list(SOC2)))   # not a SOC major group -> missing


def annual_wage(w: pd.Series, unit: pd.Series) -> pd.Series:
    num = pd.to_numeric(w.fillna("").str.replace(r"[$,\s]", "", regex=True).str.extract(r"(\d+(?:\.\d+)?)")[0],
                        errors="coerce")
    mult = unit.fillna("").str.strip().str.upper().str[:1].map(ANNUAL)
    a = num * mult
    return a.where(a.between(10_000, 2_000_000))


def status(s: pd.Series) -> pd.Series:
    return s.fillna("").str.upper().str.replace(r"\s*-\s*", "-", regex=True).str.strip()


def dedupe(df: pd.DataFrame, files: list[str]) -> pd.DataFrame:
    """One row per case number, keeping the row from the latest file of the year."""
    order = {f: i for i, f in enumerate(files)}
    df = df.assign(_o=df.file.map(order), case=df.case.str.strip().str.upper())
    return df.sort_values("_o").drop_duplicates("case", keep="last").drop(columns="_o")


def _prep(df: pd.DataFrame, program: str) -> pd.DataFrame:
    df["st"] = status(df.status)
    if program == "lca":
        if "withdrawn" in df:   # eFile: certified + withdrawal flag
            w = df.withdrawn.str.upper().str.startswith("Y")
            df.loc[df.st.eq("CERTIFIED") & w, "st"] = "CERTIFIED-WITHDRAWN"
        df["cert"] = df.st.isin(["CERTIFIED", "CERTIFIED-WITHDRAWN"])
        df["certonly"] = df.st.eq("CERTIFIED")
        v = df.get("visa", pd.Series("", index=df.index)).fillna("").str.upper().str.strip()
        df["h1b"] = v.isin(["H-1B", "H1B", "R", "H-1B VISA"]) if "visa" in df else np.nan
        df["n"] = pd.to_numeric(df.workers, errors="coerce").fillna(1).clip(lower=1)
        df["dep"] = df.dependent.str.upper().str[:1].map({"Y": 1.0, "N": 0.0}) if "dependent" in df else np.nan
    else:
        df["cert"] = df.st.isin(["CERTIFIED", "CERTIFIED-EXPIRED"])
        df["certonly"] = df.st.eq("CERTIFIED")
        df["n"] = 1.0
    df["state"] = state(df.work_state) if "work_state" in df else np.nan
    df["emp"] = state(df.emp_state) if "emp_state" in df else np.nan
    df["soc"] = soc6(df.soc) if "soc" in df else np.nan
    if program == "lca" and df.file.str.startswith("H-1B_Case_Data").any():   # eFile: DOT codes, not SOC
        df.loc[df.file.str.startswith("H-1B_Case_Data"), "soc"] = np.nan
    df["stem"] = (df.soc.str[:2].isin(["15", "17", "19"]) | df.soc.isin(STEM_MGR)).where(df.soc.notna())
    df["wage_a"] = annual_wage(df.wage, df.wage_unit) if "wage" in df and "wage_unit" in df else np.nan
    return df


# ---------------------------------------------------------------- measures

def _agg(df: pd.DataFrame, geo: str, fn) -> pd.DataFrame:
    """Apply fn to each state group and to the national total; returns long rows (state, measure, value)."""
    out = []
    for st, g in list(df.groupby(geo)) + [("US", df)]:
        for k, v in fn(g).items():
            out.append((st, k, v))
    return pd.DataFrame(out, columns=["state", "measure", "value"])


def _share(num, den):
    return num / den if den else np.nan


def lca_measures(df: pd.DataFrame) -> pd.DataFrame:
    c = df[df.cert]
    has_visa = df.h1b.notna().all() and df.h1b.dtype == bool

    def f(g):
        hg = g[g.h1b] if has_visa else g.iloc[0:0]
        r = {"lca_apps": len(g), "lca_positions": g.n.sum(),
             "lca_apps_certonly": int(g.certonly.sum()), "lca_positions_certonly": g.n[g.certonly].sum(),
             "lca_median_wage": g.wage_a.median()}
        a = g[g.stem.notna()]
        if len(a):
            r["lca_stem_share"] = _share(a.n[a.stem.astype(bool)].sum(), a.n.sum())
        if has_visa:
            s = hg[hg.stem.notna()]
            d = hg[hg.dep.notna()] if hg.dep.notna().any() else None
            r.update({"h1b_apps": len(hg), "h1b_positions": hg.n.sum(),
                      "h1b_apps_certonly": int(hg.certonly.sum()), "h1b_positions_certonly": hg.n[hg.certonly].sum(),
                      "h1b_stem_positions": s.n[s.stem.astype(bool)].sum() if len(s) else np.nan,
                      "h1b_stem_share": _share(s.n[s.stem.astype(bool)].sum(), s.n.sum()) if len(s) else np.nan,
                      "h1b_median_wage": hg.wage_a.median(),
                      "h1b_dependent_share": _share(d.n[d.dep == 1].sum(), d.n.sum()) if d is not None else np.nan})
            if len(s):
                for k, v in s.groupby(s.soc.str[:2]).n.sum().items():
                    r[f"h1b_positions_soc{k}"] = v
        return r

    work = _agg(c, "state", f)

    def e(g):
        r = {"lca_positions_emp_state": g.n.sum(), "lca_apps_emp_state": len(g)}
        if has_visa:
            hg = g[g.h1b]
            r.update({"h1b_positions_emp_state": hg.n.sum(), "h1b_apps_emp_state": len(hg)})
        return r

    emp = _agg(c, "emp", e)
    emp = emp[emp.state != "US"]
    return pd.concat([work, emp], ignore_index=True)


def perm_measures(df: pd.DataFrame) -> pd.DataFrame:
    c = df[df.cert]
    cit = c.citizenship.fillna("").str.upper().str.strip() if "citizenship" in c else None
    adm = c.admission.fillna("").str.upper().str.replace(r"[^A-Z0-9]", "", regex=True) if "admission" in c else None
    er = c.educ_req.fillna("").str.upper() if "educ_req" in c else None
    ef = c.educ_fw.fillna("").str.upper() if "educ_fw" in c else None

    def f(g):
        i = g.index
        r = {"perm_cert": len(g), "perm_cert_certonly": int(g.certonly.sum()), "perm_median_wage": g.wage_a.median()}
        s = g[g.stem.notna()]
        if len(s):
            r.update({"perm_stem": int(s.stem.astype(bool).sum()), "perm_stem_share": s.stem.astype(bool).mean()})
        if cit is not None:
            x = cit[i]
            known = (x != "").sum()
            if known:
                for k, m in {"india": x.eq("INDIA"), "china": x.isin(["CHINA", "PEOPLES REPUBLIC OF CHINA"])}.items():
                    r[f"perm_{k}"], r[f"perm_{k}_share"] = int(m.sum()), m.sum() / known
                r["perm_other_country"] = int(known - r["perm_india"] - r["perm_china"])
        if adm is not None:
            x = adm[i]
            known = (x != "").sum()
            if known:
                for k, m in {"h1b": x.isin(["H1B", "H1B1"]), "f1": x.eq("F1"), "l1": x.isin(["L1", "L1A", "L1B"]),
                             "notinus": x.isin(["NOTINUSA", "NOTINUS", "NA", "NONE"])}.items():
                    r[f"perm_adm_{k}"], r[f"perm_adm_{k}_share"] = int(m.sum()), m.sum() / known
                r["perm_adm_other"] = int(known - sum(r[f"perm_adm_{k}"] for k in ["h1b", "f1", "l1", "notinus"]))
        for nm, x in [("req", er), ("fw", ef)]:
            if x is not None:
                x = x[i]
                known = (x != "").sum()
                if known:
                    ms, dr = x.str.startswith("MASTER"), x.str.startswith("DOCTOR")
                    r.update({f"perm_{nm}_masters": int(ms.sum()), f"perm_{nm}_doctorate": int(dr.sum()),
                              f"perm_{nm}_grad_share": (ms | dr).sum() / known})
        return r

    work = _agg(c, "state", f)
    emp = _agg(c, "emp", lambda g: {"perm_cert_emp_state": len(g)})
    return pd.concat([work, emp[emp.state != "US"]], ignore_index=True)


# ---------------------------------------------------------------- build

def build(program: str, inv: pd.DataFrame, colmap: list) -> pd.DataFrame:
    sub = inv[(inv.program == program) & inv.used].sort_values(["fiscal_year", "quarter", "file"], na_position="first")
    longs = []
    for fy, g in sub.groupby("fiscal_year"):
        fy = int(fy)
        files = list(g.file)
        if program == "lca" and fy == 2009:   # eFile first (Oct 2008 - Apr 2009), then iCERT
            files = sorted(files, key=lambda f: not f.startswith("H-1B_Case"))
        print(f"{program} FY{fy}", flush=True)
        raw = cached(program, fy, files, colmap)
        for f, n in raw.file.value_counts().items():
            inv.loc[inv.file == f, "rows_read"] = n
        df = dedupe(raw, files)
        for f, n in df.file.value_counts().items():
            inv.loc[inv.file == f, "rows_after_dedupe"] = n
        inv.loc[inv.file.isin(files), "dup_cases_in_year"] = len(raw) - len(df)
        df = _prep(df, program)
        st = df.st.value_counts()
        for s_, n in st.items():
            longs.append(pd.DataFrame({"state": ["US"], "measure": [f"status_{s_.lower().replace('-', '_') or 'blank'}"],
                                       "value": [n], "fiscal_year": [fy]}))
        m = (lca_measures if program == "lca" else perm_measures)(df).assign(fiscal_year=fy)
        longs.append(m)
        del raw, df
    out = pd.concat(longs, ignore_index=True)[["fiscal_year", "state", "measure", "value"]]
    out = out.sort_values(["fiscal_year", "state", "measure"]).reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / f"{program}_state.csv", index=False)
    w = out[~out.measure.str.startswith("status_")].pivot_table(index=["fiscal_year", "state"], columns="measure",
                                                                 values="value").reset_index()
    if program == "lca":
        sc = [c for c in w if c.startswith("h1b_positions_soc")]
        if sc:
            top = w[sc].fillna(-1).idxmax(axis=1).where(w[sc].notna().any(axis=1))
            w["top_soc_group"] = top.str[-2:]
            w["top_soc_group_name"] = w.top_soc_group.map(SOC2)
            w["top_soc_group_share"] = w[sc].max(axis=1) / w[sc].sum(axis=1)
    w.insert(2, "partial", (w.fiscal_year == PARTIAL_FY).astype(int))
    w.insert(3, "geo", np.where(w.state == "US", "national", np.where(w.state.isin(list(STATES)), "state", "territory")))
    w.to_csv(OUT / f"{program}_state_wide.csv", index=False)
    return out


# ---------------------------------------------------------------- checks vs Selected Statistics PDFs

def _pdf_text(p: Path) -> str:
    try:
        import pypdf
    except ImportError:
        return ""
    return "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(str(p)).pages)


def checks() -> pd.DataFrame:
    rows = []
    names = {v.title(): k for k, v in STATES.items()}
    for p in sorted(SRC.glob("*Selected*Statistics*.pdf")):
        prog = "lca" if p.name.startswith(("LCA", "H-1B")) else "perm" if p.name.startswith("PERM") else None
        if not prog or not (OUT / f"{prog}_state.csv").exists():
            continue
        fy = int(re.search(r"FY_?(\d{4})", p.name).group(1))
        t = re.sub(r"[ \t]+", " ", _pdf_text(p))
        ours = pd.read_csv(OUT / f"{prog}_state.csv")
        ours = ours[ours.fiscal_year == fy].set_index(["state", "measure"]).value
        num = lambda s: float(s.replace(",", ""))
        pdf = {}
        if prog == "lca":
            m = re.search(r"-\s*Certified\s+([\d,]+)", t)
            if m: pdf[("US", "lca_apps")] = num(m.group(1))
            m = re.search(r"Positions\s*Certified\s+([\d,]+)", t)
            if m: pdf[("US", "lca_positions")] = num(m.group(1))
            key = "lca_positions"
        else:
            m = re.search(r"Certified\s+([\d,]+)", t)
            if m: pdf[("US", "perm_cert")] = num(m.group(1))
            key = "perm_cert"
        sec = t[t.find("States"):] if "States" in t else ""
        for nm, code in names.items():
            m = re.search(rf"\n{nm}\s+([\d,]{{4,}})\s+[\d.]+%", "\n" + sec)
            if m:
                pdf[(code, key)] = num(m.group(1))
        for (st, ms), v in pdf.items():
            o, oc = ours.get((st, ms), np.nan), ours.get((st, ms + "_certonly"), np.nan)
            rows.append({"program": prog, "fiscal_year": fy, "pdf": p.name, "state": st, "measure": ms,
                         "pdf_value": v, "ours": o, "diff_pct": (o - v) / v * 100 if v else np.nan,
                         "ours_certonly": oc, "diff_pct_certonly": (oc - v) / v * 100 if v else np.nan})
    c = pd.DataFrame(rows)
    c.to_csv(OUT / "checks.csv", index=False)
    return c


def main(programs: list[str]):
    inv = inventory()
    inv["rows_read"] = np.nan
    inv["rows_after_dedupe"] = np.nan
    inv["dup_cases_in_year"] = np.nan
    colmap: list = []
    for p in programs:
        build(p, inv, colmap)
    OUT.mkdir(parents=True, exist_ok=True)
    fp = OUT / "files.csv"
    if fp.exists() and len(programs) < 2:   # keep the other program's counts
        old = pd.read_csv(fp).set_index("file")
        for c in ["rows_read", "rows_after_dedupe", "dup_cases_in_year"]:
            keep = ~inv.program.isin(programs)
            inv.loc[keep, c] = inv.loc[keep, "file"].map(old[c])
    inv.loc[inv.used, "note"] = np.where(inv.loc[inv.used, "rows_read"].notna(), "used", "not read")
    inv.to_csv(fp, index=False)
    cm = pd.read_parquet(RAW / "columns.parquet")
    cm.astype({"fiscal_year": int}).sort_values(["program", "fiscal_year", "file", "field"]).to_csv(OUT / "columns.csv", index=False)
    print(checks().to_string())


if __name__ == "__main__":
    main(sys.argv[1:] or ["lca", "perm"])
