"""NAFSA International Student Economic Value: international students, dollars and jobs by state.

    python -m ipeds_clean.nafsa      # -> data/nafsa/*.csv and a printed check report

Source: NAFSA: Association of International Educators, "Benefits from International Students" one-page national
summaries (the International Student Economic Value Tool, analysis by JB International from 2024-25). Each is a
single page with a 51-row table (50 states + DC): international students, U.S. dollars contributed, jobs created
or supported, and a national total. Seven academic years, 2018-19 to 2024-25:

  sources/nafsa_econ_value/isev-2019.pdf             2018-19
  sources/nafsa_econ_value/isev-2020.pdf             2019-20
  sources/nafsa_econ_value/isev_EconValue2020_2021.pdf   2020-21 (InDesign file dated 11-9-2021)
  sources/nafsa_econ_value/EconValue-2022.pdf        2021-22
  sources/nafsa_econ_value/EconValue-2023_final.pdf  2022-23
  sources/nafsa_econ_value/EconValue2024 (1).pdf     2023-24   (browser-suffixed name; no un-suffixed copy exists)
  sources/nafsa_econ_value/EconValue2025_v01_11-12-2025 (1).pdf   2024-25 (same; dated 11-12-2025)
The academic year is read from the footnote ("...analysis for 2021-2022 Academic Year"),
not the file name (EconValue-2022 is 2021-22).

Measures: intl_students, econ_contribution_usd (printed rounded to $0.1 million or $0.1 billion; the rounding
half-width is kept as econ_contribution_rounding), jobs_supported. The one-page summaries print no components
(tuition and fees, living expenses, dependents, institutional support): those exist only in NAFSA's online tool
and state pages, which are not in sources/. They are recorded as not available rather than estimated.

Enrollment is Open Doors (same academic year; equal to the Open Doors state sheets, see ipeds_clean.open_doors
checks); the national Total includes Puerto Rico and the U.S. Virgin Islands (2024-25 also the Northern Mariana
Islands), which are not listed, so the Total ("US" rows) exceeds the 51-row sum for students (by about 0.05%).
Jobs are only computed for the 51 (the territories are not in Commerce's jobs data), so jobs sum to the Total
within rounding. Whether dollars and jobs exclude students on OPT is not stated on these pages; the NAFSA/JB
Fall 2025 snapshot (sources/iie_open_doors) says its dollars and jobs (which equal these totals for 2023-24 and
2024-25) exclude OPT students, while the student count includes them. The jobs multiplier changed over time
("three jobs per seven students" in 2018-19, "three per eight" 2019-20, "one per three" from 2020-21), and the
2024-25 analysis added Peterson's and Common Data Set inputs, so dollars and jobs are not strictly comparable
across years; state jumps above 30% are listed in checks.csv.

Outputs (data/nafsa/):
  nafsa_state.csv       academic_year, year (fall), state, measure, category, value, source_file, page, note
  nafsa_state_wide.csv  one row per state x academic year (US = the printed national total)
  files.csv             every file read (and the NAFSA files elsewhere), md5, academic year, duplicate notes
  checks.csv            51-row sums vs printed totals, headline vs table total, year-over-year jumps

Verified against the Open Doors state sheets (ipeds_clean.open_doors checks.csv, vs_nafsa_*): for 2021-22 to
2024-25 every state's enrollment equals the Open Doors count and every dollar figure equals the sheet's
unrounded "Estimated International Student Expenditure" within the printed rounding, except Michigan 2021-22
dollars (NAFSA $695.5M vs Open Doors $965,457,224, a likely transposition) and Mississippi 2024-25 students
(3,444 vs 3,445). These are noted on the rows (SUSPECT below), not changed.
  pdf_tables/           every pdfplumber table per page (raw grid), for audit
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from .gss import NAMES
from .open_doors import dump_tables, md5

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "nafsa_econ_value"
EXTRA = []   # isev-2019/2020.pdf (NAFSA summaries first filed with the SEVIS reports) now sit in SRC
OUT = ROOT / "data" / "nafsa"
CODE = {v: k for k, v in NAMES.items()}
ROW = re.compile(r"(" + "|".join(sorted(map(re.escape, NAMES.values()), key=len, reverse=True)) + "|Total|TOTAL)"
                 r" ([\d][\d,.]*) \$\s?([\d.,]+)\s?(million|billion) ([\d,]+)")

# values that disagree with the Open Doors state sheet for the same year (which prints NAFSA's figure unrounded);
# kept as printed here, flagged in the note
SUSPECT = {("2021-22", "MI", "econ_contribution_usd"):
           "SUSPECT: Open Doors 2022 Michigan sheet prints $965,457,224 for the same NAFSA estimate; $695.5 million "
           "looks like a digit transposition (965 -> 695). Use $965.5 million.",
           ("2024-25", "MS", "intl_students"): "Open Doors 2025 Mississippi sheet prints 3,445 (off by one)"}


def money(x: str, unit: str) -> tuple[float, float]:
    """'5.4','billion' -> (5.4e9, 0.05e9): value and half-width of the printed rounding."""
    mult = 1e9 if unit == "billion" else 1e6
    dec = len(x.split(".")[1]) if "." in x else 0
    return float(x.replace(",", "")) * mult, 0.5 * 10 ** -dec * mult


def count(x: str) -> tuple[float, str | None]:
    """'2.211' (a typo for 2,211 in the 2024-25 Nevada row) -> 2211 with a note."""
    if re.fullmatch(r"\d{1,3}\.\d{3}", x):
        return float(x.replace(".", "")), f"printed '{x}'; read as {x.replace('.', ',')} (period for comma)"
    return float(x.replace(",", "")), None


def parse(path: Path):
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, OUT / "pdf_tables")
        pg = pdf.pages[0]
        t = pg.extract_text()
        npages = len(pdf.pages)
    m = re.search(r"(20\d\d)\s*-\s*(20\d\d)\s*Academic\s*Year", t.replace("\n", " "))
    ay = f"{m.group(1)}-{m.group(2)[2:]}"
    rows = []
    for line in t.split("\n"):
        for r in ROW.finditer(line):
            name, s, d, unit, j = r.groups()
            st = "US" if name.lower() == "total" else CODE[name]
            n, note = count(s)
            usd, rnd = money(d, unit)
            base = dict(academic_year=ay, year=int(ay[:4]), state=st, source_file=path.name, page=1)
            rows += [dict(base, measure="intl_students", value=n, note=note),
                     dict(base, measure="econ_contribution_usd", value=usd,
                          note=f"printed ${d} {unit}"),
                     dict(base, measure="econ_contribution_rounding", value=rnd,
                          note="half-width of the printed rounding"),
                     dict(base, measure="jobs_supported", value=float(j.replace(",", "")), note=None)]
    # headline figures printed outside the table
    flat = re.sub(r"\s+", " ", t)
    head = {}
    hj = re.search(r"Number of Jobs Created or Supported ([\d,]{6,})", flat) or \
        re.search(r"support\s*([\d,]{6,})\b", flat)      # 2020-21: "support 306,308 Michigan ... jobs*"
    if hj:
        head["headline_jobs"] = float(hj.group(1).replace(",", ""))
    hd = re.search(r"Total Contribution(?: [A-Z][\w ]*?)? \$([\d.]+) billion", flat) or \
        re.search(r"contribute\s*(?:nearly )?\$?\s*([\d.]+) billion", flat)
    if hd:
        head["headline_usd"] = float(hd.group(1)) * 1e9
    return ay, rows, head, npages


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, files, heads = [], [], {}
    paths = sorted(SRC.glob("*.pdf")) + EXTRA
    sums = {p.name: md5(p) for p in paths}
    for p in paths:
        ay, r, head, n = parse(p)
        rows += r
        heads[ay] = head
        base = re.sub(r" \(\d\)(?=\.pdf$)", "", p.name)
        dup = ""
        if base != p.name:
            dup = ("identical to " + base if sums.get(base) == sums[p.name] else
                   "DIFFERS from " + base if base in sums else "browser-suffixed name; no un-suffixed copy in folder")
        files.append(dict(folder=str(p.parent.relative_to(ROOT)), file=p.name, md5=sums[p.name], pages=n,
                          academic_year=ay, states=sum(1 for x in r if x["measure"] == "intl_students"
                                                       and x["state"] != "US"),
                          used="yes", why="state table (students, dollars, jobs) and national total",
                          duplicate_check=dup,
                          not_available="components (tuition, living expenses) not printed on this summary"))
    long = pd.DataFrame(rows)
    for (ay, st, m), note in SUSPECT.items():
        k = (long.academic_year == ay) & (long.state == st) & (long.measure == m)
        long.loc[k, "note"] = long.loc[k, "note"].fillna("").str.cat([note] * k.sum(), sep="; ").str.strip("; ")
    dups = long.duplicated(["academic_year", "state", "measure"], keep=False)
    assert not dups.any(), long[dups]
    long = long.sort_values(["academic_year", "state", "measure"])
    cols = ["academic_year", "year", "state", "measure", "value", "note", "source_file", "page"]
    long.assign(category=None)[cols[:4] + ["category"] + cols[4:]].to_csv(OUT / "nafsa_state.csv", index=False)
    wide = long.pivot_table(index=["academic_year", "year", "state"], columns="measure", values="value",
                            aggfunc="first").reset_index()
    wide = wide[["academic_year", "year", "state", "intl_students", "econ_contribution_usd",
                 "econ_contribution_rounding", "jobs_supported"]]
    src = long.drop_duplicates("academic_year").set_index("academic_year").source_file
    wide["source_file"] = wide.academic_year.map(src)
    wide.to_csv(OUT / "nafsa_state_wide.csv", index=False)
    pd.DataFrame(files).to_csv(OUT / "files.csv", index=False)
    checks(wide, heads)


def checks(wide, heads):
    out = []
    st51 = set(NAMES)
    for ay, g in wide.groupby("academic_year"):
        s = g[g.state.isin(st51)]
        us = g[g.state == "US"].iloc[0]
        out.append(dict(check="states_listed", academic_year=ay, value=len(s), flag="" if len(s) == 51 else "missing"))
        for m in ("intl_students", "econ_contribution_usd", "jobs_supported"):
            tot = s[m].sum()
            tol = s.econ_contribution_rounding.sum() if m == "econ_contribution_usd" else 0
            d = tot - us[m]
            flag = ""
            if m == "jobs_supported" and abs(d) > 5:
                flag = "jobs: 51-row sum != printed total"
            elif m == "jobs_supported" and d:
                flag = "rounding (|diff| <= 5 jobs)"
            if m == "intl_students" and not (0 <= -d <= 0.01 * us[m]):
                flag = "students: total minus 51 rows outside 0-1% (territories)"
            if m == "econ_contribution_usd" and abs(d) > tol + us.econ_contribution_rounding:
                flag = "dollars: 51-row sum differs from total beyond printed rounding (territories?)"
            out.append(dict(check="sum51_vs_total", academic_year=ay, measure=m, value=tot, computed=us[m],
                            diff=d, diff_pct=round(100 * d / us[m], 3), detail=f"rounding allowance {tol:,.0f}"
                            if tol else "", flag=flag))
        h = heads.get(ay, {})
        for k, m in (("headline_jobs", "jobs_supported"), ("headline_usd", "econ_contribution_usd")):
            if k in h:
                out.append(dict(check="headline_vs_table_total", academic_year=ay, measure=m, value=h[k],
                                computed=us[m], flag="" if abs(h[k] - us[m]) <= 0.051e9 else "differs"))
    w = wide.sort_values("year").set_index(["state", "year"])
    for (st, y), r in w.iterrows():
        if (st, y - 1) in w.index:
            p = w.loc[(st, y - 1)]
            for m in ("intl_students", "econ_contribution_usd"):
                ch = 100 * (r[m] / p[m] - 1)
                if abs(ch) > 30:
                    out.append(dict(check="yoy_jump_gt_30pct", academic_year=r.academic_year, state=st, measure=m,
                                    value=r[m], computed=p[m], diff_pct=round(ch, 1), flag="check"))
    ck = pd.DataFrame(out)
    ck.to_csv(OUT / "checks.csv", index=False)
    pd.set_option("display.width", 200)
    print(ck.to_string())
    print(wide[wide.state.isin(["CA", "TX", "US"])].to_string())


if __name__ == "__main__":
    build()
