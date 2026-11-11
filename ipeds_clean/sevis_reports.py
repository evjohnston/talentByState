"""DHS/ICE SEVP "SEVIS by the Numbers" annual reports and related SEVP PDFs: state and national tables.

    python -m ipeds_clean.sevis_reports      # -> data/sevis_reports/*.csv and a printed check report

Sources (sources/dhs_sevis/annual_reports/):
* SEVIS by the Numbers annual reports for calendar years 2018-2024 (*-sevis-btn.pdf, every year). Counts are
  F-1 and M-1 SEVIS records active at any time in the calendar year, so a state's figure is larger than any
  monthly snapshot from the SEVIS mapping tool (ipeds_clean.sevis; checks.csv compares them). Students who move
  between states in a year may be counted twice.
* 17_0623_hsi_sevp-0617-biannual-sevis-btn.pdf: the June 2017 biannual report, a snapshot of active F and M
  records on May 5, 2017 vs May 2016 (the CY2018 report says the two bases cannot be compared). Kept as measure
  active_students (never mixed with records): CA, NY, TX (figure call-outs), NE, NV, ID (prose, both years),
  absolute changes for 8 states, % growth for the 13 states named as their region's fastest growing,
  SEVP-certified schools for CA, NY, FL, TX; national F and M total, J-1, STEM students (513,611; 43%),
  region shares. These match the mapping tool's May 2017 counts within 0.4% (checks.csv), except Idaho, printed
  2,752 where the sentence's own "14 percent drop from 4,363" and the mapping tool give 3,752 (corrected to
  3,752, noted). The report gives 8,774 SEVP-certified schools on one page and 8,744 on another (both kept).
* ApprovedforF-1toH1-Bvisa2012-2017.pdf (FOUO, released by SEVP): F-1 students approved for change of status to
  H-1B by fiscal year 2012-2017, all and those on STEM OPT; page 2 counts STEM OPT authorizations with an
  employment start date of Jan 1 / Aug 1 (FY2017 Aug blank in source). National only.
* mainland-china-hong-kong-students-studying-in-us.pdf: FOIA 12-11907 summary (May 3, 2012): active F-1 and M-1
  students from China and Hong Kong by level (primary, high school, post-high school). National only.
* CountOfF-1StudentsOnOPT2012-2017.pdf: one table (marked "For Official Use Only", released by SEVP): F-1 students
  on post-completion OPT and STEM OPT on January 1 and August 1, 2012-2017. National only.
* f-1high-school-students-entering-us-2007-2011.pdf: ICE FOIA 12-12727 response (2012), one row per
  year x country of citizenship x school state x public school (Y/N) for F-1 high-school students entering the
  U.S., 2007-2011. Despite its summary ("number and country of origin"), the table has no count column and no
  row repeats, so each row only says that at least one student from that country entered a public / private
  high school in that state that year. Page 1 is a scanned image: its 34 rows were transcribed by hand from the
  image (flagged source="page 1 image, transcribed"); pages 2-175 are text.
* isev-2019.pdf, isev-2020.pdf are NAFSA economic value summaries (2018-19, 2019-20) filed here; they are parsed
  by ipeds_clean.nafsa and listed in files.csv as not used here.

What the annual reports contain at state level, and what is extracted:
* "the three <region> states that saw the greatest percentage change" tables: state, % change, absolute change,
  calendar-year total records (3 states per region, plus territories) -> measures records, records_change,
  records_pct_change (category = "region top-3 change table").
* State totals quoted in the prose ("Texas hosted 102,380 student records") -> records (category = "text").
* Top 10 states by number of SEVP-certified schools -> sevp_certified_schools.
* Region totals and shares ("28.3% (461,192) in the Northeast") -> sevis_reports_us.csv.
Report quirks found by checks.csv: the CY2018 tables compute "% change" on the current-year total, not the prior
year (NJ -3,086 / 56,194 = -5.5%); CY2018 prints North Dakota as 3,308 where its own row and the CY2019 report imply
3,038 (kept, flagged SUSPECT); the CY2019 text says Florida "hosted 85,969 student records in 2018" in a 2019
paragraph (read as 2019, noted). Lists' captions in sevis_reports_lists.csv are taken from the sentence above each
table and are heuristic: several consecutive lists can share one caption, so use header and page too.
* Rows of the change tables whose state name is interleaved with the next heading in the text layer ("INnetwer
  Jnearsteioy nal Students in the South+ 17.7% ..." = New Jersey) are recovered by de-interleaving against the
  region headings (CY2022 NJ, KY; CY2023 NH, TN); the % change check confirms them.
* The top-5 states figure ("Above are the U.S. states that hosted the largest number ...") is an image. It is
  read by OCR with the macOS Vision framework through the system `swift` (no package installed); the raw OCR
  lines are cached in ocr_raw.csv, so later builds need no OCR. A count is kept (category "figure (OCR)",
  lowest priority) only if the state label reads cleanly and the count agrees with its printed share given the
  other counts in the figure; the share is kept as records_share_pct (the base of these shares is about 3% below
  the region sum and is not stated). All OCR counts that overlap a text/table value match it exactly except
  CY2018 Massachusetts: the figure prints 101,515, the text 100,515 (text kept; checks.csv). The CY2021 figure
  gave no readable blocks; CY2022 and CY2024 counts are partly unreadable (shares kept).
There is no complete 50-state table in any of these files (no figure or map shows every state), no OPT or STEM
OPT by state of employment, no F-1 to H-1B by state, and no top schools by state: school, employer and major
rankings are national and carry no state; they go to sevis_reports_lists.csv as printed.

National tables (sevis_reports_us.csv; year_basis = calendar year, fiscal year, May snapshot or point in time):
OPT, STEM OPT and CPT students with an EAD who reported an employer (from the report text, with the prior-year
figure each report quotes; CY2017-2024, the CY2023 report itself gives only STEM OPT participants), 2012-2017
OPT counts on Jan 1 / Aug 1 from the FOUO table, F-1 to H-1B approvals FY2012-2017, SEVP-certified schools,
higher-education records by degree level, region totals. Reports revise prior years: the CY2022 report gives
115,651 OPT for 2021 while the CY2021 report gave 105,970; both are kept with their source (checks.csv). The
CY2024 report gives STEM OPT as 95,384 (work authorizations) in the OPT section and 165,524 ("participating")
in the executive summary; both are kept with notes.

SEVIS cross-check (checks.csv vs_sevis_monthly): calendar-year records / the largest monthly active count from the
mapping tool (data/sevis/all_state_country.parquet, same year, else nearest) is 1.2-1.4 for most states (median
about 1.3), as expected for an any-time-in-year count against a point-in-time count. Outliers: New Jersey 2.1-2.3
(2018, 2024), Kentucky 0.42-0.45 (2018-19), Missouri 0.90 (2024); those states' monthly and annual figures are not
on the same footing and should not be mixed.

Outputs (data/sevis_reports/):
  sevis_reports_state.csv       year (calendar; 2016-17 = May snapshots), state, measure, category (table, text,
                                figure (OCR), May snapshot), value, note, source_file, page
  sevis_reports_state_wide.csv  one row per state-year: records (table, else text, else OCR), change, % change,
                                records_share_pct, active_students (May snapshots), SEVP-certified schools;
                                F-1 high-school country counts (2007-2011)
  sevis_reports_us.csv          national / regional measures by year
  sevis_reports_lists.csv       national ranked lists (top countries, schools, employers, sponsors) as printed
  hs_f1_rows.csv                the FOIA rows: year, country, state, public_school, source
  ocr_raw.csv                   cached OCR lines of the top-states figure pages (file, page, x, y, conf, text)
  files.csv, checks.csv, pdf_tables/ (every pdfplumber table, one CSV per page)
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from .gss import NAMES
from .open_doors import dump_tables, md5, num

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "dhs_sevis" / "annual_reports"
OUT = ROOT / "data" / "sevis_reports"
SEVIS = ROOT / "data" / "sevis" / "all_state_country.parquet"
TERR = {"Virgin Islands of the U.S.": "VI", "Puerto Rico": "PR", "Guam": "GU", "Virgin Islands": "VI", "U.S. Virgin Islands": "VI",
        "American Samoa": "AS", "Northern Mariana Islands": "MP", "Federated States of Micronesia": "FM",
        "Federated State of Micronesia": "FM", "Micronesia": "FM", "Marshall Islands": "MH", "Palau": "PW"}
CODE = {**{v.upper(): k for k, v in NAMES.items()}, **{k.upper(): v for k, v in TERR.items()}}
STATE_ALT = "|".join(sorted(map(re.escape, [*NAMES.values(), *TERR]), key=len, reverse=True))
CHANGE = re.compile(r"^(.*?)\s*([+-]?\d+(?:\.\d+)?%)\s+([+-]?[\d,]+)\s+([\d,]+)$")
PROSE = re.compile(r"(?<![A-Za-z])(" + STATE_ALT + r"),? (?:which |was home to |also )?(?:hosted|had) ([\d,]+\d)"
                   r"(?: (?:[A-Za-z0-9\-]+ ){0,4}?(?:students?|records))")
PROSE2 = re.compile(r"(" + STATE_ALT + r") (?:remain(?:s|ed) the most popular state for [a-z ]+, hosting ([\d,]+\d)|"
                    r"hosted the largest percentage \([\d.]+%\) of [a-z ]+ records \(([\d,]+\d)\))")
# printed values that contradict the same report's own arithmetic or the next report; kept, flagged in the note
SUSPECT = {(2018, "ND", "records"): "SUSPECT: printed 3,308, but the row's -85 / -2.8% and the CY2019 report "
                                    "(2,788, -250, -8.2%) both imply 3,038 (digit transposition)"}
HEADER = re.compile(r"SEVIS by the Numbers|Exchange Visitor Program \(SEVP\)|^=====PAGE|^\d{1,2}$|^\d+F$")
# page 1 of the FOIA file is a scanned image; rows transcribed from it by hand (year, country, state, public)
HS_PAGE1 = """AFGHANISTAN|VIRGINIA|N;ALBANIA|CALIFORNIA|N;ALBANIA|CONNECTICUT|N;ALBANIA|ILLINOIS|N;ALBANIA|MASSACHUSETTS|N;
ANGOLA|ARIZONA|Y;ANGOLA|FLORIDA|N;ANGOLA|MASSACHUSETTS|N;ANGOLA|TEXAS|N;ANTIGUA AND BARBUDA|COLORADO|N;
ARGENTINA|ARKANSAS|N;ARGENTINA|FLORIDA|N;ARGENTINA|MASSACHUSETTS|N;ARGENTINA|MINNESOTA|N;ARGENTINA|NEW YORK|N;
ARGENTINA|OHIO|N;ARGENTINA|TEXAS|N;ARGENTINA|VERMONT|N;ARMENIA|MARYLAND|N;ARMENIA|MICHIGAN|N;AUSTRALIA|ARIZONA|Y;
AUSTRALIA|CALIFORNIA|N;AUSTRALIA|COLORADO|N;AUSTRALIA|CONNECTICUT|N;AUSTRALIA|DISTRICT OF COLUMBIA|N;
AUSTRALIA|FLORIDA|N;AUSTRALIA|IOWA|Y;AUSTRALIA|KANSAS|N;AUSTRALIA|MARYLAND|N;AUSTRALIA|MASSACHUSETTS|N;
AUSTRALIA|NEW JERSEY|N;AUSTRALIA|NEW MEXICO|N;AUSTRALIA|NEW YORK|N;AUSTRALIA|NORTH CAROLINA|N"""
STATE_SECTION = re.compile(r"Students Across the United States")
END_SECTION = re.compile(r"J-1 exchange visitors must be|Exchange Visitors\s*$", re.M)


def code(name: str) -> str | None:
    return CODE.get(re.sub(r"\s+", " ", name).strip().upper())


def flat(s: str) -> str:
    """Join lines, drop bullet glyphs, normalize spaces."""
    s = re.sub(r"(?m)^\s*[−•\-]\s*$", " ", s)
    s = re.sub(r"\s[−•]\s", " ", s.replace("\n", " "))
    s = re.sub(r"\s+-\s+(?=[A-Z])", " ", s)
    return re.sub(r"\s+", " ", s)


# ---------------------------------------------------------------- annual reports
def report(path: Path):
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, OUT / "pdf_tables")
        pages = [(pg.extract_text() or "") for pg in pdf.pages]
        lists = ranked_lists(pdf, path.name)
    year = int(re.search(r"(20\d\d) SEVIS by the Numbers", re.sub(r"(\d) (\d)", r"\1\2", pages[0]
                                                                     .replace("S EVIS", "SEVIS"))).group(1))
    st, us = [], []

    def S(state, measure, value, category, page, note=None):
        st.append(dict(year=year, state=state, measure=measure, category=category, value=value, note=note,
                       source_file=path.name, page=page))

    def U(measure, value, page, category=None, note=None, y=year):
        us.append(dict(year=y, state="US", measure=measure, category=category, value=value, note=note,
                       report_year=year, source_file=path.name, page=page))

    # overview page before the section heading; in CY2020 and CY2023 the heading is garbled in the text layer,
    # so fall back to the caption of the top-states figure
    start = next((i for i, t in enumerate(pages) if STATE_SECTION.search(t)), None)
    if start is None:
        start = next(i for i, t in enumerate(pages) if re.search(r"Above are the U\.S\. states that hosted", t))
    start -= 1
    end = next((i for i, t in enumerate(pages) if i > start and END_SECTION.search(t)), len(pages))
    # 1. region top-3 change tables (state section only: country tables share the layout, and Georgia is both)
    for i in range(start, end):
        lines = pages[i].split("\n")
        for k, line in enumerate(lines):
            g = None if CHANGE.match(line.strip()) and code(CHANGE.match(line.strip()).group(1) or "") \
                else garbled_change(line)
            if g:
                note = "region top-3 % change table (state name interleaved with a heading in the text layer)"
                S(g[0], "records", g[3], "table", i + 1, note)
                S(g[0], "records_change", g[2], "table", i + 1, note)
                S(g[0], "records_pct_change", g[1], "table", i + 1, note)
                continue
            m = CHANGE.match(line.strip())
            if not m:
                continue
            name = m.group(1)
            c = code(name) if name else None
            if c is None and k > 0:
                c = code(lines[k - 1] + " " + name)
            if c is None and k + 1 < len(lines):
                c = code((lines[k - 1] if k else "") + " " + name + " " + lines[k + 1])
            if c is None:
                continue
            note = "region top-3 % change table"
            S(c, "records", num(m.group(4)), "table", i + 1, note)
            S(c, "records_change", num(m.group(3)), "table", i + 1, note)
            S(c, "records_pct_change", num(m.group(2)), "table", i + 1, note)
    # 2. prose: "<State> hosted N ... records" anywhere in the report
    for i, t in enumerate(pages):
        for m in PROSE.finditer(flat(t)):
            c = code(m.group(1))
            if re.search(r"states,? and (the )?$", flat(t)[max(0, m.start() - 25): m.start()]):
                continue                    # "Sixteen Southern states and the District of Columbia hosted <region>"
            note = "quoted in text"
            ctx = flat(t)[m.start(): m.end() + 40]
            yr = re.search(r"in (?:calendar year )?(20\d\d)", ctx)
            if yr and int(yr.group(1)) != year:
                note += f" (sentence says {yr.group(1)}; read as {year}, the report year)"
            S(c, "records", num(m.group(2)), "text", i + 1, note)
        for m in PROSE2.finditer(flat(t)):
            S(code(m.group(1)), "records", num(m.group(2) or m.group(3)), "text", i + 1, "quoted in text")
    # 3. SEVP-certified schools, top 10 states
    alltext = [(i + 1, l) for i, t in enumerate(pages) for l in t.split("\n")]
    on, got = False, 0
    for pg, l in alltext:
        if re.search(r"School Count\s*$", l):
            on = True
            continue
        if not on or HEADER.search(l.strip()):
            continue
        m = re.match(r"^(" + STATE_ALT + r") ([\d,]+)$", l.strip())
        if m:
            S(code(m.group(1)), "sevp_certified_schools", num(m.group(2)), "table", pg,
              "top 10 states by SEVP-certified schools")
            got += 1
        elif got:
            break
    # 4. national: regions, degree levels, OPT / STEM OPT / CPT
    for i, t in enumerate(pages):
        f = flat(t)
        for m in re.finditer(r"([\d.]+)% \(([\d,]+)\) (?:in the )?(Northeast|South|West|Midwest|"
                             r"non-continental U\.S\. territories|U\.S\. territories)", f):
            U("region_records", num(m.group(2)), i + 1, category=m.group(3).replace("non-continental ", ""))
            U("region_share_pct", float(m.group(1)), i + 1, category=m.group(3).replace("non-continental ", ""))
        for m in re.finditer(r"([\d.]+)% \(([\d,]+)\) ?(Associate|Bachelor’s|Master’s|Doctoral)", f):
            U("higher_ed_records", num(m.group(2)), i + 1, category=m.group(3).replace("’", "'"))
        for kind, pat in (("opt_working", r"pre- and post-completion (?:optional practical training \()?OPT\)?"),
                          ("stem_opt_working", r"(?:science, technology, engineering and mathematics \(STEM\) OPT|"
                                               r"STEM OPT)"),
                          ("cpt_working", r"(?:curricular practical training \()?CPT\)?")):
            for m in re.finditer(r"([\d,]{6,}) " + pat + r" students (?:with both an (?:EAD|employment authorization"
                                 r" document \(EAD\)) and )?who reported working for an employer in (?:calendar "
                                 r"year )?(20\d\d), compared to ([\d,]+) in (?:calendar year )?(20\d\d)", f):
                U(kind, num(m.group(1)), i + 1, y=int(m.group(2)), note="with EAD and a reported employer")
                U(kind, num(m.group(3)), i + 1, y=int(m.group(4)),
                  note=f"prior-year figure quoted in the CY{year} report")
            for m in re.finditer(r"there were ([\d,]+) pre- and post-completion OPT students with both an EAD and who "
                                 r"reported working for an employer, ([\d,]+) STEM OPT students with both an EAD and "
                                 r"who reported working for an employer, and ([\d,]+) CPT", f) if kind == "opt_working" \
                    else []:
                for k2, v in zip(("opt_working", "stem_opt_working", "cpt_working"), m.groups()):
                    U(k2, num(v), i + 1, note="with EAD and a reported employer (OPT section)")
        m = re.search(r"a total of ([\d,]+) foreign students obtained work authorization through OPT, while a separate "
                      r"population of ([\d,]+) foreign students obtained work authorization through STEM OPT, and "
                      r"([\d,]+) foreign students obtained work authorization through CPT", f)
        if m:
            for k2, v in zip(("opt_working", "stem_opt_authorized", "cpt_working"), m.groups()):
                U(k2, num(v), i + 1, note="work authorizations, duplicates not removed (OPT section)")
        for m in re.finditer(r"In calendar year (20\d\d), ([\d,]+) SEVP-certified schools were eligible to enroll "
                             r"international students, an? (?:decrease|increase) of [\d,]+ schools from (?:calendar year )?"
                             r"(20\d\d) \(([\d,]+) schools\)", f):
            U("sevp_certified_schools", num(m.group(2)), i + 1, y=int(m.group(1)), note="eligible to enroll")
            U("sevp_certified_schools", num(m.group(4)), i + 1, y=int(m.group(3)),
              note=f"prior-year figure quoted in the CY{year} report")
        m = re.search(r"unique foreign student SEVIS records with work authorization through a form of practical "
                      r"training was ([\d,]+)", f)
        if m:
            U("practical_training_unique", num(m.group(1)), i + 1, note="OPT + STEM OPT + CPT, deduplicated")
        m = re.search(r"with ([\d,]+) foreign students participating in STEM OPT in (20\d\d)", f) or re.search(
            r"There was a total of ([\d,]+) international students participating in science, technology, "
            r"engineering, and mathematics \(STEM\) OPT in (20\d\d)", f)
        if m:
            U("stem_opt_participating", num(m.group(1)), i + 1, y=int(m.group(2)),
              note="executive summary; differs from the OPT section's STEM OPT authorizations")
        m = re.search(r"There were ([\d,]+) pre- and post-completion optional practical training \(OPT\) students with "
                      r"both an employment authorization document \(EAD\) and who reported working for an employer "
                      r"in (?:calendar year )?(20\d\d), compared to ([\d,]+) in (?:calendar year )?(20\d\d)", f)
        if m and not any(r["measure"] == "opt_working" and r["year"] == int(m.group(2)) for r in us):
            U("opt_working", num(m.group(1)), i + 1, y=int(m.group(2)), note="with EAD and a reported employer")
            U("opt_working", num(m.group(3)), i + 1, y=int(m.group(4)),
              note=f"prior-year figure quoted in the CY{year} report")
    for r in lists:
        r["year"] = year
    return year, st, us, lists, len(pages)


def ranked_lists(pdf, fname):
    """Two-column 'name | count' tables (countries, schools, employers, sponsors) with a caption guessed from the
    nearest 'top N ...' sentence above the table; continuation tables inherit the previous caption."""
    out, caption, header = [], None, None
    for i, pg in enumerate(pdf.pages, 1):
        for tb in pg.find_tables():
            grid = tb.extract()
            if not grid or len(grid[0]) < 2:
                continue
            vals = [num((r[-1] or "").strip()) for r in grid]
            if sum(v is not None for v in vals) < max(2, 0.6 * len(grid)):
                continue
            above = (pg.crop((0, max(0, tb.bbox[1] - 110), pg.width, tb.bbox[1])).extract_text() or "")
            fa = flat(above)
            cut = [m.start() for m in re.finditer(r"Below are|The chart below|The top \d+|Visit the", fa)]
            sent = [fa[cut[-1]:]] if cut else []
            first_numeric = vals[0] is not None
            if sent and not (first_numeric and caption and not re.search(r"\btop \d+|Below", sent[-1])):
                caption = sent[-1].strip()
                header = None
            if not first_numeric:
                header = " | ".join(" ".join((c or "").split()) for c in grid[0])
            rank = sum(1 for r in out if r["caption"] == caption and r["header"] == header)
            for row, v in zip(grid, vals):
                if v is None:
                    continue
                name = " ".join(" ".join((c or "").split()) for c in row[:-1] if c).strip()
                rank += 1
                out.append(dict(caption=caption, header=header, rank=rank, name=name, value=v, source_file=fname,
                                page=i))
    return out



# ---------------------------------------------------------------- garbled change-table rows
REGION_HEAD = ["International Students in the " + r for r in ("Northeast", "South", "Midwest", "West")]


def _interleaves(s: str, a: str, b: str) -> bool:
    """True if s is an interleaving of a and b (case-sensitive, spaces removed beforehand)."""
    if len(s) != len(a) + len(b):
        return False
    ok = [[False] * (len(b) + 1) for _ in range(len(a) + 1)]
    ok[0][0] = True
    for i in range(len(a) + 1):
        for j in range(len(b) + 1):
            if i and ok[i - 1][j] and a[i - 1] == s[i + j - 1]:
                ok[i][j] = True
            if j and ok[i][j - 1] and b[j - 1] == s[i + j - 1]:
                ok[i][j] = True
    return ok[-1][-1]


def garbled_change(line: str):
    """A change-table row whose state name is interleaved in the text layer with the next region's heading,
    e.g. 'INnetwer Jnearsteioy nal Students in the South+ 17.7% +8,050 53,618' (New Jersey). Returns
    (state, pct, change, total) or None. The heading's last letters can also land inside the percent
    ('Midwe+s1t3 .8%')."""
    m = re.match(r"^(.*?)\s*([+-][\d,]+) ([\d,]+)$", line.strip())
    if not m or "%" not in m.group(1):
        return None
    pre = m.group(1)
    k = max(pre.rfind("+"), pre.rfind("-"))
    if k < 0 or not pre.rstrip().endswith("%"):
        return None
    pct_part = pre[k:]
    pct = re.sub(r"[^\d.]", "", pct_part)
    name = (pre[:k] + re.sub(r"[^A-Za-z]", "", pct_part)).replace(" ", "")
    for st_name in [*NAMES.values(), *TERR]:
        for h in REGION_HEAD:
            if _interleaves(name, st_name.replace(" ", ""), h.replace(" ", "")):
                return code(st_name), float(pre[k] + pct), num(m.group(2)), num(m.group(3))
    return None


# ---------------------------------------------------------------- June 2017 biannual report (May snapshot)
UPPER_STATES = sorted((n.upper() for n in NAMES.values()), key=len, reverse=True)
BI_SUSPECT = {("ID", 2017): (3752, "corrected from the printed 2,752: the same sentence's 14 percent drop from 4,363 "
                                    "and the SEVIS mapping tool both give 3,752")}


def biannual(path: Path):
    """SEVIS by the Numbers, June 2017 (biannual): a snapshot of active records on May 5, 2017, compared with
    May 2016. Not comparable with the calendar-year (any time in the year) counts of the annual reports."""
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, OUT / "pdf_tables")
        pages = [(pg.extract_text() or "") for pg in pdf.pages]
        words14 = pdf.pages[13].extract_words()
    st, us = [], []
    snap = "active F and M student records on May 5, 2017 (biannual snapshot, not a calendar-year count)"

    def S(state, measure, value, page, note, year=2017):
        st.append(dict(year=year, state=state, measure=measure, category="May snapshot", value=value,
                       note=note, source_file=path.name, page=page))

    def U(measure, value, page, note, category=None, year=2017):
        us.append(dict(year=year, state="US", measure=measure, category=category, value=value, note=note,
                       report_year=2017, source_file=path.name, page=page, year_basis="May snapshot"))

    states_alt = "|".join(map(re.escape, UPPER_STATES))
    for i, t in enumerate(pages):
        lines = [l.strip() for l in t.split("\n")]
        # figure call-outs: "200,809 / STUDENTS IN / ... / CALIFORNIA", "635 / SCHOOLS IN / NEW YORK"
        for k, l in enumerate(lines):
            if l in UPPER_STATES:
                for j in (k - 1, k - 2):
                    lab = next((x for x in ("STUDENTS IN", "SCHOOLS IN") if j > 0 and lines[j].endswith(x)), None)
                    if lab:
                        n = next((re.search(r"([\d,]{3,})$", lines[x]) for x in range(j - 1, max(-1, j - 4), -1)
                                  if re.search(r"([\d,]{3,})$", lines[x])), None)
                        if n:
                            meas = "active_students" if lab == "STUDENTS IN" else "sevp_certified_schools"
                            S(code(l), meas, num(n.group(1)), i + 1, "figure call-out; " + (
                                snap if meas == "active_students" else "SEVP-certified schools, May 2017"))
                        break
        # top proportional growth per region: a line ending in state names, the next ending in as many percents
        for k in range(len(lines) - 1):
            m = re.search(r"((?:(?:" + states_alt + r")\s*)+)$", lines[k])
            p2 = next((x for x in (re.search(r"((?:\d+(?:\.\d+)?% ?)+)$", l2) for l2 in lines[k + 1:k + 3]) if x),
                      None)
            if not m or not p2:
                continue
            names = re.findall(states_alt, m.group(1))
            pcts = re.findall(r"(\d+(?:\.\d+)?)%", p2.group(1))
            if len(names) == len(pcts) >= 2:
                for n_, v in zip(names, pcts):
                    S(code(n_), "active_students_pct_change", float(v), i + 1,
                      "May 2016 to May 2017; listed among the region's largest proportional growth")
        # prose with the figure labels (upper-case state names, bare percents) that the text layer mixes in removed
        f = flat("\n".join(re.sub(r"\s*(?:(?:" + states_alt + r")\s*)+$|\s*(?:\d+% ?)+$", "", l) for l in lines))
        alt = STATE_ALT
        for m in re.finditer(r"(" + alt + r")[^()]{0,120}?\((?:[+-]?\d+ percent, )?from ([\d,]+) students to "
                             r"([\d,]+) students\)", f):
            c = code(m.group(1))
            S(c, "active_students", num(m.group(2)), i + 1, "quoted in text; May 2016 snapshot", year=2016)
            S(c, "active_students", num(m.group(3)), i + 1, "quoted in text; " + snap)
        for m in re.finditer(r"((?:" + alt + r")(?:, (?:" + alt + r"))*,? and (?:" + alt + r"))[^()]{0,160}?"
                             r"\(((?:[+-][\d,]+ students,? (?:and )?)+)respectively\)", f):
            names = re.findall(alt, m.group(1))
            vals = re.findall(r"([+-][\d,]+) students", m.group(2))
            if len(names) == len(vals):
                for n_, v in zip(names, vals):
                    S(code(n_), "active_students_change", num(v), i + 1, "quoted in text; May 2016 to May 2017")
        for m in re.finditer(r"(" + alt + r") (?:saw|experienced) the largest (?:increase|decrease) in (?:the number "
                             r"of )?international students[^()]{0,60}?\(([+-][\d,]+) students\)", f):
            S(code(m.group(1)), "active_students_change", num(m.group(2)), i + 1,
              "quoted in text; May 2016 to May 2017")
        # national (raw text: the call-outs pair numbers with percents)
        f = flat(t)
        for pat, meas, note in (
                (r"([\d,]{7,}) 8,\d{3} ACTIVE F & M STUDENTS", "active_f_m_students", snap),
                (r"([\d,]{6,}) \d+% J-1 EXCHANGE VISITORS", "j1_exchange_visitors", "active J-1, May 5, 2017"),
                (r"As of May 5, 2017, there are ([\d,]+) SEVP-certified schools", "sevp_certified_schools",
                 "Schools section text"),
                (r"[\d,]{7,} ([\d,]+) ACTIVE F & M STUDENTS SEVP-CERTIFIED SCHOOLS", "sevp_certified_schools",
                 "Trends page call-out (the Schools section says 8,744)")):
            for m in re.finditer(pat, f):
                U(meas, num(m.group(1)), i + 1, note)
        m = re.search(r"(\d+) percent of international students come .{0,40}?to the United States to enroll in science, "
                      r"technology, engineering and mathematics \(STEM\)", f)
        if m:
            U("stem_share_pct", float(m.group(1)), i + 1, "share of F and M students in STEM programs, May 2017")
        m = re.search(r"enrolled in STEM programs \(from ([\d,]+) to ([\d, ]+\d)\)", f)
        if m:
            U("stem_students", num(m.group(1)), i + 1, "F and M students in STEM programs, May 2016", year=2016)
            U("stem_students", num(m.group(2).replace(" ", "")), i + 1, "F and M students in STEM programs, May 2017")
    # region shares (figure 8): each percent sits just above its region label; match by position
    pcts = [w for w in words14 if re.fullmatch(r"\d+\.\d%", w["text"])]
    for lab, cat in (("NORTHEAST", "Northeast"), ("MIDWEST", "Midwest"), ("WEST", "West"), ("SOUTH", "South"),
                     ("TERRITORIES", "U.S. states & territories outside the continent (incl. AK, HI)")):
        w = next((w for w in words14 if w["text"] == lab), None)
        if w is None:
            continue
        cands = [p for p in pcts if p["top"] < w["top"] + 10]
        if lab == "TERRITORIES":
            cands = [p for p in pcts if abs(p["top"] - w["top"]) < 15]
        best = min(cands, key=lambda p: abs(p["x0"] - w["x0"]) + abs(p["top"] - w["top"]), default=None)
        if best:
            U("region_share_pct", float(best["text"].rstrip("%")), 14, snap, category=cat)
    for (c, y), (fix, note) in BI_SUSPECT.items():
        for r in st:
            if r["state"] == c and r["year"] == y and r["measure"] == "active_students":
                r["value"] = fix
                r["note"] = (r["note"] + "; " if r["note"] else "") + note
    return st, us, len(pages)


# ---------------------------------------------------------------- small SEVP FOIA / FOUO tables
def h1b_table(path: Path):
    """ApprovedforF-1toH1-Bvisa2012-2017.pdf: F-1 students approved for a change of status to H-1B, fiscal
    years 2012-2017, national; page 2: STEM OPT authorizations with an employment start date of Jan 1 / Aug 1."""
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, OUT / "pdf_tables")
        t = [pg.extract_text() or "" for pg in pdf.pages]
    rows = []
    ys = [int(y) for y in re.findall(r"20\d\d", re.search(r"Description ((?:20\d\d ?)+)", t[0]).group(1))]

    def R(y, meas, v, page, note):
        rows.append(dict(year=y, state="US", measure=meas, category=None, value=v, note=note, report_year=None,
                         source_file=path.name, page=page, year_basis="fiscal year"))
    for lab, meas in (("Approved for F-1 to H1-B visa for students with STEM-OPT", "f1_to_h1b_approved_stem_opt"),
                      ("Approved for F-1 to H1-B visa", "f1_to_h1b_approved")):
        m = re.search(r"^" + re.escape(lab) + r" ((?:[\d,]+ ?)+)$", t[0], re.M)
        for y, v in zip(ys, m.group(1).split()):
            R(y, meas, num(v), 1, "F-1 students approved for change of status to H-1B (FOUO table released by "
                                  "SEVP)" + ("; subset who were on STEM OPT" if "stem" in meas else ""))
    for m in re.finditer(r"^(20\d\d) (\d+)(?: (\d+))?$", t[1], re.M):
        R(int(m.group(1)), "stem_opt_start_jan1", num(m.group(2)), 2,
          "STEM OPT authorizations with an actual employment start date of January 1")
        if m.group(3):
            R(int(m.group(1)), "stem_opt_start_aug1", num(m.group(3)), 2,
              "STEM OPT authorizations with an actual employment start date of August 1")
    return rows


def china_hk_table(path: Path):
    """mainland-china-hong-kong-students-studying-in-us.pdf: FOIA 12-11907 summary (submitted May 3, 2012):
    active F-1 / M-1 students from China and Hong Kong by school level. National, one date."""
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, OUT / "pdf_tables")
        t = pdf.pages[0].extract_text() or ""
    rows = []
    for m in re.finditer(r"^(China|Hong Kong) ([FM]-1) ((?:[\d,]+ ?)+)$", t, re.M):
        vals = [num(v) for v in m.group(3).split()]
        cats = ["primary", "high_school", "post_high_school", "total"] if len(vals) == 4 else \
            ["post_high_school", "total"] if len(vals) == 2 else ["total"] * len(vals)
        for c, v in zip(cats, vals):
            rows.append(dict(year=2012, state="US", measure="active_students_china_hk", value=v,
                             category=f"{m.group(1)} {m.group(2)} {c}", report_year=None, source_file=path.name,
                             page=1, year_basis="snapshot (FOIA summary of May 3, 2012)",
                             note="active students by school level; M-1 students are post-high-school"))
    for m in re.finditer(r"^Students: (China|Hong Kong) ([\d,]+)$", t, re.M):
        rows.append(dict(year=2012, state="US", measure="active_students_china_hk", value=num(m.group(2)),
                         category=f"{m.group(1)} F-1 and M-1 total", report_year=None, source_file=path.name, page=1,
                         year_basis="snapshot (FOIA summary of May 3, 2012)", note="active students"))
    return rows


# ---------------------------------------------------------------- OCR of the top-states figure (images)
# The figure "Above are the U.S. states that hosted the largest number of F-1 and M-1 student records" is an
# image with the top five states' share and count. It is read with the macOS Vision framework through the
# system `swift` (no extra install); raw OCR lines are cached in ocr_raw.csv so the build does not need OCR again.
OCR_CACHE = OUT / "ocr_raw.csv"
TOP_FIG = re.compile(r"(?:Above|Below) are the U\.S\.\s+states that hosted the largest number")
SWIFT_OCR = """import Foundation
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    for o in (req.results ?? []) {
        let b = o.boundingBox
        if let t = o.topCandidates(1).first {
            print(path + "\\t" + String(format: "%.4f\\t%.4f\\t%.2f\\t", b.minX, 1 - b.maxY, t.confidence) + t.string)
        }
    }
}
"""


def ocr_raw(files: list[Path]) -> pd.DataFrame | None:
    """Raw OCR lines (file, page, x, y, conf, text) of the top-states figure pages; cached."""
    if OCR_CACHE.exists():
        d = pd.read_csv(OCR_CACHE)
        if set(f.name for f in files) <= set(d.file):
            return d
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("swift"):
        print("OCR skipped: no cache and no swift (macOS Vision) available")
        return None
    import pypdfium2 as pdfium
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "ocr.swift").write_text(SWIFT_OCR)
        imgs = {}
        for f in files:
            doc = pdfium.PdfDocument(str(f))
            hits = [i for i in range(len(doc)) if TOP_FIG.search(doc[i].get_textpage().get_text_range())]
            for i in sorted({j for h in hits[:1] for j in (h, h + 1) if j < len(doc)}):
                png = tmp / f"{len(imgs)}.png"
                doc[i].render(scale=4).to_pil().save(png)
                imgs[str(png)] = (f.name, i + 1)
            doc.close()
        out = subprocess.run(["swift", str(tmp / "ocr.swift"), *imgs], capture_output=True, text=True,
                             check=True).stdout
    for line in out.splitlines():
        path, x, y, conf, text = line.split("\t", 4)
        fname, page = imgs[path]
        rows.append(dict(file=fname, page=page, x=float(x), y=float(y), conf=float(conf), text=text))
    d = pd.DataFrame(rows)
    d.to_csv(OCR_CACHE, index=False)
    return d


def ocr_top_states(raw: pd.DataFrame, years: dict):
    """Blocks of '<pct>%' / 'STUDENT RECORDS' / 'IN <STATE>' / '(<count>)' -> state rows. The printed shares are
    not on the regions' total (CY2018: California 302,073 is 18.9% of the 1,597,961 region sum but printed 19.5%),
    so the counts are checked against each other: each count and its rounded share bound the base
    (count / (share +- half a unit)); a count is kept only when its bounds overlap the common bounds of at least
    two other counts in the same figure. Otherwise only the share is kept, when the state name is read cleanly."""
    import difflib
    upper = {n.upper(): k for k, n in NAMES.items()}
    out = []
    for (fname, page), g in raw.groupby(["file", "page"], sort=False):
        year = years.get(fname)
        blocks, cur = [], None
        for r in g.itertuples():
            t = r.text.strip()
            if re.fullmatch(r"\d{1,2}(?:\.\d{1,2})?%", t):
                cur = dict(pct=t[:-1], state=None, score=0, count=None, conf=r.conf)
                blocks.append(cur)
            elif cur is not None and cur["state"] is None and re.match(r"^I\s?N\s?\S", t) and "RECORD" not in t:
                name = re.sub(r"^I\s?N\s?", "", t).upper()
                best = difflib.get_close_matches(name, list(upper), n=1, cutoff=0.5)
                if best:
                    cur.update(state=upper[best[0]], score=difflib.SequenceMatcher(None, name, best[0]).ratio())
            elif cur is not None and cur["count"] is None and re.fullmatch(r"\([\d,.]+\)", t):
                cur["count"] = num(t[1:-1].replace(".", ","))
                cur["conf"] = min(cur["conf"], r.conf)
        def bounds(b):
            h = 0.05 if "." in b["pct"] else 0.5
            return 100 * b["count"] / (float(b["pct"]) + h), 100 * b["count"] / (float(b["pct"]) - h)
        withc = [b for b in blocks if b["count"] and float(b["pct"]) > 0.5]
        for b in blocks:
            # the state label must be read nearly cleanly ('INSORIDE' for Florida scores 0.6 against Oregon)
            if not b["state"] or year is None or b["score"] < 0.8:
                continue
            pct = float(b["pct"])
            ok, base = False, None
            others = [bounds(o) for o in withc if o is not b]
            if b in withc and len(others) >= 2:
                lo, hi = max(o[0] for o in others), min(o[1] for o in others)
                blo, bhi = bounds(b)
                ok = lo <= hi and blo <= hi and bhi >= lo
                base = (max(lo, blo) + min(hi, bhi)) / 2
            row = dict(year=year, state=b["state"], category="figure (OCR)", source_file=fname, page=page)
            if ok:
                out.append(dict(row, measure="records", value=b["count"],
                                note=f"OCR of image figure (conf {b['conf']:.2f}); consistent with its printed "
                                     f"share {pct}% (implied base {base:,.0f})"))
            out.append(dict(row, measure="records_share_pct", value=pct,
                            note="OCR of image figure: share of all F-1 and M-1 records" +
                                 ("" if ok else "; count unreadable or inconsistent, not kept")))
    return out

# ---------------------------------------------------------------- other files
def opt_table(path: Path):
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, OUT / "pdf_tables")
        t = pdf.pages[0].extract_text()
    rows = []
    names = ["opt_post_completion_jan1", "stem_opt_jan1", "opt_total_jan1",
             "opt_post_completion_aug1", "stem_opt_aug1", "opt_total_aug1"]
    for m in re.finditer(r"^(20\d\d) " + " ".join([r"([\d,]+)"] * 6) + r"$", t, re.M):
        for k, v in zip(names, m.groups()[1:]):
            rows.append(dict(year=int(m.group(1)), state="US", measure=k, category=None, value=num(v),
                             note="F-1 students on OPT on Jan 1 / Aug 1 (FOUO table)", report_year=None,
                             source_file=path.name, page=1))
    return rows


def hs_rows(path: Path):
    rows = [dict(year=2007, country=c, state_name=s, public_school=p, source="page 1 image, transcribed")
            for c, s, p in (x.strip().split("|") for x in HS_PAGE1.replace("\n", "").split(";"))]
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, OUT / "pdf_tables")
        for i, pg in enumerate(pdf.pages[1:], 2):
            for l in (pg.extract_text() or "").split("\n"):
                m = re.match(r"^(20\d\d) (.+?) (" + STATE_ALT.upper().replace("\\ ", " ") + r"|"
                             + STATE_ALT + r") ([YN])$", l.strip(), re.I)
                if m:
                    rows.append(dict(year=int(m.group(1)), country=m.group(2), state_name=m.group(3),
                                     public_school=m.group(4), source=f"page {i}"))
                elif l.strip():
                    rows.append(dict(year=None, country=l, state_name=None, public_school=None,
                                     source=f"page {i} UNPARSED"))
        n = len(pdf.pages)
    d = pd.DataFrame(rows)
    d["state"] = d.state_name.map(lambda s: code(s) if isinstance(s, str) else None)
    return d, n


# ---------------------------------------------------------------- build
def build():
    OUT.mkdir(parents=True, exist_ok=True)
    st, us, lists, files = [], [], [], []
    hs = None
    for p in sorted(SRC.glob("*.pdf")):
        f = dict(file=p.name, md5=md5(p), pages=None, year=None, used="yes", why="", note="")
        if "biannual" in p.name:
            s, u, n = biannual(p)
            st += s
            us += u
            f.update(pages=n, year="2017 (May 5 snapshot)",
                     why="biannual report June 2017: active students on May 5, 2017 vs May 2016 for the states "
                         "quoted (call-outs, prose, top-growth lists), schools by state (4), national STEM, regions",
                     note="snapshot counts, not calendar-year records: kept as measure active_students, never "
                          "mixed with records")
        elif p.name.endswith("sevis-btn.pdf"):
            y, s, u, l, n = report(p)
            st += s
            us += u
            lists += l
            f.update(pages=n, year=y, why=f"annual report CY{y}: state change tables, state totals quoted in text, "
                                          f"top-10 states by schools, national OPT/levels/regions, ranked lists",
                     note="top-5 states figure is an image: read by OCR (validated), see ocr_raw.csv")
        elif p.name.startswith("CountOfF-1StudentsOnOPT"):
            u = opt_table(p)
            us += u
            f.update(pages=1, year="2012-2017", why="national OPT / STEM OPT counts on Jan 1 and Aug 1",
                     note="marked UNCLASSIFIED // FOR OFFICIAL USE ONLY (FOUO)")
        elif p.name.startswith("ApprovedforF-1toH1-B"):
            us += h1b_table(p)
            f.update(pages=2, year="FY2012-2017", why="national F-1 to H-1B change-of-status approvals (all, and on "
                                                       "STEM OPT); STEM OPT start-date counts",
                     note="marked UNCLASSIFIED // FOR OFFICIAL USE ONLY (FOUO); no state breakdown")
        elif p.name.startswith("mainland-china-hong-kong"):
            us += china_hk_table(p)
            f.update(pages=1, year="2012 (May snapshot)", why="FOIA 12-11907: active China / Hong Kong F-1 and M-1 "
                                                              "students by school level",
                     note="national only; no state breakdown")
        elif p.name.startswith("f-1high-school"):
            hs, n = hs_rows(p)
            f.update(pages=n, year="2007-2011", why="FOIA 12-12727: year x country x state x public school rows",
                     note="no counts in the table; page 1 is an image, its 34 rows transcribed by hand")
        elif p.name.startswith("isev-"):
            f.update(used="no", why="NAFSA economic value summary, not SEVIS data: parsed by ipeds_clean.nafsa")
            with pdfplumber.open(p) as pdf:
                f["pages"] = len(pdf.pages)
        else:
            f.update(used="no", why="not recognized")
        files.append(f)

    # top-5 states figure (image): OCR, each count validated against its printed share
    btn = sorted(p for p in SRC.glob("*sevis-btn.pdf") if "biannual" not in p.name)
    raw = ocr_raw(btn)
    if raw is not None:
        years = {f["file"]: f["year"] for f in files if f["file"] in {p.name for p in btn}}
        st += ocr_top_states(raw, years)

    long = pd.DataFrame(st)
    # one value per state-year-measure: table beats text beats OCR; duplicates collapse
    long["prio"] = long.category.map({"table": 0, "text": 1, "figure (OCR)": 2})
    conflicts = long.groupby(["year", "state", "measure"]).value.nunique()
    conflicts = conflicts[conflicts > 1]
    long = long.sort_values(["year", "state", "measure", "prio", "page"]).drop_duplicates(
        ["year", "state", "measure", "category", "value"]).drop(columns="prio")
    # F-1 high-school country counts
    if hs is not None:
        h = hs[hs.state.notna()]
        hsm = []
        for (y, s), g in h.groupby(["year", "state"]):
            hsm += [dict(year=int(y), state=s, measure="hs_f1_countries", category="any school",
                         value=g.country.nunique()),
                    dict(year=int(y), state=s, measure="hs_f1_countries", category="public",
                         value=g[g.public_school == "Y"].country.nunique()),
                    dict(year=int(y), state=s, measure="hs_f1_countries", category="private",
                         value=g[g.public_school == "N"].country.nunique())]
        hsm = pd.DataFrame(hsm).assign(note="distinct countries of citizenship with >=1 F-1 high-school entrant "
                                            "(FOIA table has no counts)",
                                       source_file="f-1high-school-students-entering-us-2007-2011.pdf", page=None)
        long = pd.concat([long, hsm], ignore_index=True)
        hs.to_csv(OUT / "hs_f1_rows.csv", index=False)
    cols = ["year", "state", "measure", "category", "value", "note", "source_file", "page"]
    for (y, st_, m), note in SUSPECT.items():
        k = (long.year == y) & (long.state == st_) & (long.measure == m)
        long.loc[k, "note"] = long.loc[k, "note"].fillna("") + "; " + note
    long = long[cols].sort_values(["year", "state", "measure", "category"])
    long.to_csv(OUT / "sevis_reports_state.csv", index=False)

    best = long.copy()
    best["prio"] = best.category.map({"table": 0, "text": 1, "figure (OCR)": 2}).fillna(3)
    best = best.sort_values("prio")
    w1 = best[best.measure != "hs_f1_countries"].drop_duplicates(["year", "state", "measure"]) \
        .pivot_table(index=["year", "state"], columns="measure", values="value", aggfunc="first")
    w2 = long[long.measure == "hs_f1_countries"].pivot_table(index=["year", "state"], columns="category",
                                                             values="value", aggfunc="first")
    w2.columns = [f"hs_f1_countries_{c.replace(' ', '_')}" for c in w2.columns]
    wide = w1.join(w2, how="outer").reset_index()
    wide.to_csv(OUT / "sevis_reports_state_wide.csv", index=False)

    usd = pd.DataFrame(us)
    usd["year_basis"] = usd.get("year_basis", pd.Series(index=usd.index, dtype=object)).fillna("calendar year")
    usd.loc[usd.note.str.contains("Jan 1 / Aug 1", na=False), "year_basis"] = \
        "point in time (Jan 1 / Aug 1)"
    usd = usd.drop_duplicates(["year", "measure", "category", "value", "report_year", "year_basis"])
    usd = usd.sort_values(["measure", "year", "report_year"])
    usd.to_csv(OUT / "sevis_reports_us.csv", index=False)
    pd.DataFrame(lists)[["year", "caption", "header", "rank", "name", "value", "source_file", "page"]] \
        .to_csv(OUT / "sevis_reports_lists.csv", index=False)
    pd.DataFrame(files).to_csv(OUT / "files.csv", index=False)
    checks(long, usd, wide, conflicts, hs)


def checks(long, usd, wide, conflicts, hs):
    out = []
    for (y, s, m), n in conflicts.items():
        v = long[(long.year == y) & (long.state == s) & (long.measure == m)]
        out.append(dict(check="state_value_conflict", year=y, state=s, measure=m, value=None,
                        detail="; ".join(f"{r.category} p{r.page}: {r.value:g}" for r in v.itertuples()),
                        flag="table and text disagree"))
    # regions sum vs implied national total from state shares quoted in text ("14.6% ... (237,763)")
    reg = usd[usd.measure == "region_records"].groupby("year").value.sum()
    for y, tot in reg.items():
        out.append(dict(check="regions_sum", year=y, state="US", measure="records", value=tot,
                        detail="sum of the four regions + territories"))
    # change table: total - change = prior year; compare with the prior report's value where present
    w = wide.set_index(["year", "state"])
    for (y, s), r in w.iterrows():
        if pd.notna(r.get("records_change")) and pd.notna(r.get("records")):
            prev = r.records - r.records_change
            calc = 100 * r.records_change / prev if prev else None
            calc_cur = 100 * r.records_change / r.records if r.records else None
            ok = calc is None or abs(calc - r.records_pct_change) < 0.15
            ok_cur = calc_cur is not None and abs(calc_cur - r.records_pct_change) < 0.15
            out.append(dict(check="pct_change_consistent", year=y, state=s, measure="records_pct_change",
                            value=r.records_pct_change, computed=round(calc, 2) if calc is not None else None,
                            detail="" if ok else "matches change / current-year total" if ok_cur else "",
                            flag="" if ok else "base is current year, not prior" if ok_cur else "differs"))
            if (y - 1, s) in w.index and pd.notna(w.loc[(y - 1, s)].get("records")):
                p = w.loc[(y - 1, s)].records
                out.append(dict(check="prior_year_vs_prior_report", year=y, state=s, measure="records",
                                value=prev, computed=p, diff=prev - p,
                                flag="" if abs(prev - p) <= 0.01 * p else "prior report differs >1%"))
    # OPT: same year quoted by two reports
    o = usd[usd.measure.str.contains("opt|cpt", regex=True)]
    for (y, m), g in o.groupby(["year", "measure"]):
        if g.value.nunique() > 1:
            out.append(dict(check="national_value_revised", year=y, state="US", measure=m,
                            detail="; ".join(f"CY{r.report_year} report: {r.value:,.0f}" for r in g.itertuples()),
                            flag="revised"))
    # SEVIS mapping-tool monthly snapshots (ipeds_clean.sevis) vs calendar-year record counts
    if SEVIS.exists():
        sv = pd.read_parquet(SEVIS, columns=["month", "state", "n"])
        sv = sv.groupby(["month", "state"]).n.sum().reset_index()
        sv["year"] = sv.month.dt.year
        rec = wide[wide.records.notna()][["year", "state", "records"]]
        for r in rec.itertuples():
            g = sv[(sv.year == r.year) & (sv.state == r.state)]
            if g.empty:
                near = sv[sv.state == r.state].assign(d=lambda x: (x.year - r.year).abs()).sort_values("d")
                if near.empty:
                    continue
                g = near[near.d == near.d.iloc[0]]
            out.append(dict(check="vs_sevis_monthly", year=r.year, state=r.state, measure="records", value=r.records,
                            computed=g.n.max(), diff=round(r.records / g.n.max(), 3),
                            detail=f"ratio = CY records / max monthly active ({len(g)} month(s): "
                                   f"{g.month.min():%Y-%m}..{g.month.max():%Y-%m}; mean {g.n.mean():,.0f})"))
        # May snapshots (June 2017 biannual) vs the mapping tool's month nearest May of the same year
        if "active_students" in wide:
            for r in wide[wide.active_students.notna()][["year", "state", "active_students"]].itertuples():
                g = sv[(sv.state == r.state) & (sv.year == r.year)]
                if g.empty:
                    continue
                g = g.iloc[[(g.month.dt.month - 5).abs().argmin()]]
                out.append(dict(check="snapshot_vs_sevis_monthly", year=r.year, state=r.state, measure="active_students",
                                value=r.active_students, computed=g.n.iloc[0],
                                diff=round(r.active_students / g.n.iloc[0], 3),
                                detail=f"ratio = May snapshot (report) / mapping tool {g.month.iloc[0]:%Y-%m}",
                                flag="" if abs(r.active_students / g.n.iloc[0] - 1) < 0.1 else "differs >10%"))
    if hs is not None:
        out.append(dict(check="hs_rows", value=len(hs), detail=f"unparsed lines: {(hs.state.isna()).sum()}; "
                                                              f"duplicate rows: {hs.duplicated().sum()}",
                        flag="" if hs.state.notna().all() else "unparsed"))
    ck = pd.DataFrame(out)
    ck.to_csv(OUT / "checks.csv", index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 160)
    print(ck[ck.flag.fillna("") != ""].to_string())
    v = ck[ck.check == "vs_sevis_monthly"]
    print("\nCY records / max monthly active snapshot, by year:")
    print(v.groupby("year")["diff"].describe().to_string())
    print(ck[ck.check == "regions_sum"].to_string())


if __name__ == "__main__":
    build()
