"""USCIS H-1B Employer Data Hub: H-1B petition decisions by employer, rolled up to states.

    python -m ipeds_clean.h1b      # -> data/h1b/*.csv

Source: USCIS H-1B Employer Data Hub exports, one file per fiscal year in sources/uscis_h1b/. Each row is one
employer (petitioner) x city x ZIP with counts of approved and denied I-129 petitions decided in that fiscal
year (first decisions only; appeals and revocations are not reflected). Every year is in the current hub
layout: six petition types, each approved/denied: New Employment, Continuation, Change with Same Employer,
New Concurrent, Change of Employer, Amended (the answer to Form I-129 Part 2, Question 2).

  FY2009-2023  h1b_employer_information_fy{fy}.xlsx / .csv, re-exported from the current hub tool on
               2026-11-11 (.xlsx, or UTF-16 tab-separated .csv for FY2018-20 and FY2023)
  FY2024-2026  h1b_datahubexport-{fy}.csv (UTF-16 tab-separated, already in the current layout)

Initial = New Employment + New Concurrent; Continuing = Continuation + Change with Same Employer + Change of
Employer + Amended. This is USCIS's definition in the "Characteristics of H-1B Specialty Occupation Workers"
reports from the FY2020 edition on ("initial" and "continuing" defined from Part 2, Question 2; earlier
editions used Question 4 and are not comparable). The six types are also kept separately. Check against
the reports' Appendix D, Table 1b (approvals, initial / continuing):
      FY    report                     hub
      2016  105,090 / 252,121 (a)      105,066 / 252,071
      2017   96,167 / 277,225 (a,b)     96,123 / 277,175
      2018   87,894 / 247,067 (a,b,c)   87,871 / 247,035
      2019  132,986 / 256,392 (a,b,c)  132,978 / 256,375
      2020  122,886 / 303,824 (a-d)    122,894 / 303,821
      2021  123,414 / 283,657 (b-d)    123,406 / 283,635
      2022  132,429 / 309,614 (c,d)    132,659 / 309,748
      2023  118,948 / 267,370 (d)      118,952 / 267,383
      2024  141,205 / 258,190 (d)      141,206 / 258,193
      2025  114,806 / 291,542 (e)      114,804 / 291,543
  (a) FY2020 report, (b) FY2021, (c) FY2022, (d) FY2024, (e) FY2025 report (Table 2, April 2026).
  Every year is within 0.2% of USCIS's own count. FY2009-2015 have no report on this definition; their
  hub totals are within about 0.1% of the old-layout exports, which matched the hub for FY2016-20 too.
  FY2026 has no report yet.

Old layout (superseded): the earlier hub's exports (h1b_datahubexport-{fy}.csv, UTF-8, Initial / Continuing
columns only). For FY2009-2020 they agree with the re-exports to within 0.1% nationally and about 1% in any
state (employer names are spelled differently in a few percent of rows). The FY2021-22 old exports ran
5-18% above USCIS's reports (FY2021 141k initial vs 123k; MA, CT, NJ 33-37% high) and the FY2023 one was
incomplete at the source (33,332 rows, 38k initial approvals). All are replaced by the re-exports, moved to
sources/_duplicates_to_delete/ (FY2009-2022 under uscis_h1b_old_layout/), and listed in files.csv with
used = no. With the re-exports the series is on one method from FY2009 to FY2026.

Some rows have a blank employer name (USCIS withholds names of individual petitioners; under 50 rows a
year). They count in state and US totals but not as employers (employer counts, top-five share, top lists).

State is the petitioner's (employer's) state on the petition, which is often headquarters, not where the
worker works; DOL's LCA data (ipeds_clean.dol) has the worksite. "Initial" approvals are the closest
measure of new H-1B workers (cap-subject lottery winners plus cap-exempt hires such as universities);
continuing approvals are extensions, transfers and amendments of people already in H-1B status.

Outputs (data/h1b/):
  h1b_state.csv        fiscal_year, state, measure, value     (US = all rows, incl. those without a state)
  h1b_state_wide.csv   the same, one row per state-year
  h1b_top_employers.csv  the 10 employers with the most initial approvals in each state-year
  files.csv            rows and national totals per file, with a flag for incomplete exports, plus the
                       superseded old-layout files (used = no)
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .open_doors import md5

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "uscis_h1b"
OUT = ROOT / "data" / "h1b"
SOURCE = "Data from USCIS, H-1B Employer Data Hub"
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
             "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
NEW_TYPES = ["New Employment", "Continuation", "Change with Same Employer", "New Concurrent",
             "Change of Employer", "Amended"]
SECTORS = {"54": "prof_sci_tech", "61": "education", "62": "health", "51": "information",
           "31": "manufacturing", "32": "manufacturing", "33": "manufacturing", "52": "finance"}
INITIAL_TYPES = ["New Employment", "New Concurrent"]        # USCIS: "New employment" or "New concurrent employment"
# a file whose initial approvals fall below this share of the median year is flagged as an incomplete export
INCOMPLETE = 0.5
DUPES = ROOT / "sources" / "_duplicates_to_delete"
OLD_DIRS = [SRC, DUPES, DUPES / "uscis_h1b_old_layout"]
# old-layout exports replaced by re-exports from the current hub tool: file -> (incomplete at the source?, note)
SUPERSEDED = {"h1b_datahubexport-2023.csv":
              (True, "superseded by h1b_employer_information_fy2023.csv (re-export from the current Data Hub tool, "
                     "2026-11-11): the old export was incomplete at the source (33,332 rows, 38,315 initial approvals); "
                     "every Tax ID in it is in the new file. Moved to sources/_duplicates_to_delete/.")}
for _fy in range(2009, 2023):
    SUPERSEDED[f"h1b_datahubexport-{_fy}.csv"] = (False, (
        f"old Data Hub layout (initial/continuing only), superseded by h1b_employer_information_fy{_fy} (re-export "
        "from the current Data Hub tool, 2026-11-11), which reproduces USCIS's Characteristics of H-1B counts"
        + (". The old export ran 5-18% above them" if _fy in (2021, 2022) else "; national totals within 0.1%")
        + ". Moved to sources/_duplicates_to_delete/uscis_h1b_old_layout/."))
# what files.csv recorded for superseded files that have since been deleted from _duplicates_to_delete
GONE = {"h1b_datahubexport-2023.csv": dict(fiscal_year=2023, rows=33332, initial_approved=38315,
                                           continuing_approved=138635, no_state=0.07785311412456498,
                                           md5="d3acafd446a0cb0b6b59eb00582cdcb9")}


def sources() -> dict[int, Path]:
    """Fiscal year -> export. A re-export (h1b_employer_information_fy{fy}.csv/.xlsx) replaces the old file."""
    out = {int(p.stem.split("-")[-1]): p for p in SRC.glob("h1b_datahubexport-*.csv")}
    for p in SRC.glob("h1b_employer_information_fy*"):
        if p.suffix in (".csv", ".xlsx"):
            out[int(re.search(r"fy(\d{4})", p.stem).group(1))] = p
    return dict(sorted(out.items()))


def read(fy: int, path: Path) -> pd.DataFrame:
    if path.suffix == ".xlsx":
        d = pd.read_excel(path, dtype=str, engine="openpyxl")
    else:
        utf16 = path.read_bytes()[:2] in (b"\xff\xfe", b"\xfe\xff")
        d = pd.read_csv(path, encoding="utf-16" if utf16 else "utf-8", sep="\t" if utf16 else ",", dtype=str)
    d.columns = d.columns.str.strip()
    if "Fiscal Year" in d:
        assert set(d["Fiscal Year"].str.strip()) == {str(fy)}, (path.name, d["Fiscal Year"].unique()[:5])
    num = lambda c: pd.to_numeric(d[c].str.replace(",", ""), errors="coerce").fillna(0)  # noqa: E731
    pick = lambda *names: next(c for c in d if c in names)  # noqa: E731
    out = pd.DataFrame({
        "fiscal_year": fy,
        "employer": d[pick("Employer", "Employer (Petitioner) Name")].fillna("").str.strip().str.upper(),
        "state": d[pick("State", "Petitioner State")].fillna("").str.strip().str.upper(),
        "city": d[pick("City", "Petitioner City")].fillna("").str.strip().str.upper(),
        "naics2": d[pick("NAICS", "Industry (NAICS) Code")].fillna("").str.strip().str[:2],
    })
    if "New Employment Approval" in d:
        for t in NEW_TYPES:
            key = t.lower().replace(" ", "_")
            out[f"{key}_approved"], out[f"{key}_denied"] = num(f"{t} Approval"), num(f"{t} Denial")
        ini = [t.lower().replace(" ", "_") for t in INITIAL_TYPES]
        rest = [t.lower().replace(" ", "_") for t in NEW_TYPES if t not in INITIAL_TYPES]
        out["initial_approved"] = out[[f"{k}_approved" for k in ini]].sum(axis=1)
        out["initial_denied"] = out[[f"{k}_denied" for k in ini]].sum(axis=1)
        out["continuing_approved"] = out[[f"{k}_approved" for k in rest]].sum(axis=1)
        out["continuing_denied"] = out[[f"{k}_denied" for k in rest]].sum(axis=1)
    else:
        out["initial_approved"] = num(pick("Initial Approvals", "Initial Approval"))
        out["initial_denied"] = num(pick("Initial Denials", "Initial Denial"))
        out["continuing_approved"] = num(pick("Continuing Approvals", "Continuing Approval"))
        out["continuing_denied"] = num(pick("Continuing Denials", "Continuing Denial"))
    return out


def measures(d: pd.DataFrame) -> pd.DataFrame:
    d = pd.concat([d[d.state.isin(STATES)], d.assign(state="US")])
    g = d.groupby(["fiscal_year", "state"])
    m = g[["initial_approved", "initial_denied", "continuing_approved", "continuing_denied"]].sum()
    m["total_approved"] = m.initial_approved + m.continuing_approved
    m["initial_denial_rate"] = m.initial_denied / (m.initial_approved + m.initial_denied)
    named = d[d.employer != ""]                                  # blank = name withheld by USCIS
    m["employers_with_initial"] = named[named.initial_approved > 0].groupby(["fiscal_year", "state"]).employer.nunique()
    sec = d.assign(sector=d.naics2.map(SECTORS).fillna("other")).pivot_table(
        index=["fiscal_year", "state"], columns="sector", values="initial_approved", aggfunc="sum")
    m = m.join(sec.div(m.initial_approved, axis=0).add_prefix("initial_share_"))
    emp = named.groupby(["fiscal_year", "state", "employer"]).initial_approved.sum().reset_index()
    top5 = (emp.sort_values("initial_approved", ascending=False).groupby(["fiscal_year", "state"]).head(5)
            .groupby(["fiscal_year", "state"]).initial_approved.sum())
    m["initial_share_top5_employers"] = top5 / m.initial_approved
    new_cols = [c for c in d if c.endswith("_approved") and c.split("_approved")[0] in
                [t.lower().replace(" ", "_") for t in NEW_TYPES]]
    if new_cols:
        m = m.join(d.groupby(["fiscal_year", "state"])[new_cols].sum(min_count=1))
    return m.reset_index()


def build() -> pd.DataFrame:
    src = sources()
    d = pd.concat([read(y, p) for y, p in src.items()], ignore_index=True)
    files = d.groupby("fiscal_year").agg(rows=("employer", "size"), initial_approved=("initial_approved", "sum"),
                                         continuing_approved=("continuing_approved", "sum"),
                                         no_state=("state", lambda s: (~s.isin(STATES)).mean())).reset_index()
    files["incomplete_export"] = files.initial_approved < INCOMPLETE * files.initial_approved.median()
    files["source_file"] = files.fiscal_year.map({y: p.name for y, p in src.items()})
    files["used"], files["note"] = "yes", ""
    old = []
    for name, (incomplete, note) in SUPERSEDED.items():
        if name in {p.name for p in src.values()}:
            continue
        p = next((q / name for q in OLD_DIRS if (q / name).exists()), None)
        if p is None:
            if name in GONE:                                     # file deleted since; keep its recorded row
                g = dict(GONE[name])
                h = g.pop("md5")
                old.append(dict(g, incomplete_export=incomplete, source_file=name, used="no",
                                note=f"{note} md5 {h} (file since deleted)"))
            continue
        o = read(int(name.split("-")[-1].split(".")[0]), p)
        old.append(dict(fiscal_year=o.fiscal_year.iloc[0], rows=len(o), initial_approved=o.initial_approved.sum(),
                        continuing_approved=o.continuing_approved.sum(), no_state=(~o.state.isin(STATES)).mean(),
                        incomplete_export=incomplete, source_file=name, used="no",
                        note=f"{note} md5 {md5(p)}"))
    if old:
        files = pd.concat([files, pd.DataFrame(old)], ignore_index=True).sort_values(["fiscal_year", "used"],
                                                                                    ascending=[True, False])
    OUT.mkdir(parents=True, exist_ok=True)
    files.to_csv(OUT / "files.csv", index=False)
    used = files[files.used == "yes"]
    w = measures(d)
    w["incomplete_export"] = w.fiscal_year.isin(used.fiscal_year[used.incomplete_export])
    w.to_csv(OUT / "h1b_state_wide.csv", index=False)
    w.drop(columns="incomplete_export").melt(id_vars=["fiscal_year", "state"], var_name="measure").dropna() \
        .to_csv(OUT / "h1b_state.csv", index=False)
    top = (d[d.state.isin(STATES) & (d.employer != "")].groupby(["fiscal_year", "state", "employer"])
           [["initial_approved", "continuing_approved"]].sum().reset_index()
           .sort_values(["fiscal_year", "state", "initial_approved"], ascending=[True, True, False])
           .groupby(["fiscal_year", "state"]).head(10))
    top.to_csv(OUT / "h1b_top_employers.csv", index=False)
    print(files.to_string(index=False))
    return w


if __name__ == "__main__":
    build()
