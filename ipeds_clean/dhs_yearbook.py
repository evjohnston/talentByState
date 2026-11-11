"""DHS Yearbook of Immigration Statistics: green cards, naturalizations and I-94 admissions by state.

    python -m ipeds_clean.dhs_yearbook      # -> data/dhs_yearbook/*.csv and data/dhs_yearbook/pdf_tables/*.csv

Source: sources/dhs_yearbook/. Full-yearbook PDFs for every year 1996-2022 (INS Statistical Yearbook 1996-2002;
DHS/OIS Yearbook 2003-2022) and the OHSS Excel table workbooks for FY2023 and FY2024 (lawful
permanent residents, naturalizations, nonimmigrants, refugees, asylees, enforcement, and the FY2024 new-arrival /
adjustment split of Tables 8-11), plus the yearbook data dictionary. sources/dhs_yearbook/excel/ holds the
yearbooks' own Excel tables (189 files): zips per release and topic for FY1996 and FY1998-2021 (no FY1997; LPR,
NATZ, NI, RFA, ENF and their "Supp" zips, which repeat the supplemental tables of the main zips), the FY2020-22
workbooks, and the "tables8-11newadj" workbooks FY2006-2023. Zip members are read in memory (calamine; xlrd for
the BIFF4 tables of the 1996 zip); two members are truncated and unreadable (LPR2001 Table6.xls, NATZ2000
Table48.xls, both national). File names are not reliable, so each PDF's fiscal year is read from its Table 1 title
("... FISCAL YEARS 1820 TO 2016" / "1820-1998") and each workbook's or zip's from the latest year in its titles.
Excel is preferred: where a release has the same table in Excel and PDF (by release, table kind and LPR type),
the Excel cells are used and the PDF values are kept only for the comparison (excel_vs_pdf.csv, checks.csv).
Tables are found by title, not number: page text (pypdfium2) is
searched for the title at the top of a page, then those pages are read with pdfplumber (extract_text) and each
line is split into a row label (before the dot leaders) and value tokens. Every PDF table used is written as the
raw extracted grid to pdf_tables/{fy}_table{nn}.csv (page, panel, label as printed, one column per printed column).

What is used (state = 2-letter postal code for the 50 states + DC; "US" = the table's Total row; territories as
PR, GU, VI, MP (Northern Mariana Is.), AS, MH where listed; OTHER (residual territories / armed forces posts, as the
table footnotes define it), ARMED_FORCES, UNKNOWN, OTHER_OR_UNKNOWN kept as their own rows):
* lpr / total: "Persons obtaining lawful (legal) permanent resident status by state or territory of residence"
  (Table 4, 2005+; 10 years per release) and "Immigrants admitted by state of intended residence" (1996-98 T18,
  1999-2001 T17, 2002 T13, 2003-04 T11; 9-10 years each). FY1988-2024, no gaps.
* lpr / refugees_asylees: "Refugees and asylees granted (lawful) permanent resident status by state of residence"
  (1996-98 T36, 1999-2001 T34; the 2002+ yearbooks have no such table). FY1987-2001. This is the only state x
  class-of-admission LPR table in any of these files: no yearbook here (PDF, Excel or supplemental) tabulates
  employment-, family- or diversity-based LPRs by state. The LPR supplemental tables are state x country of birth
  (Supp. 1, FY2002-03 and FY2005-21; FY2004 has none), CBSA x country / region of birth (2-3) and orphan
  adoptions (4-5); only Supp. 1's all-countries row is read, to cross-check Table 4. Same for naturalizations
  (Supp. 1 state x country of birth, FY2002-21, checked against Table 22).
* naturalized / total: "Persons naturalized by state (or territory) of residence" (Table 22 2005-2023, Table 23
  FY2024 workbook; 1996-97 T49, 1998 T50, 1999 T48, 2000 T51, 2001 T50, 2002 T36, 2003-04 T33). FY1987-2024.
* i94_admissions by class: "Nonimmigrant admissions (I-94 only) by selected category of admission and state or
  territory of destination" (Table 30, 2008-2023; Table 31 FY2024) gives total plus broad groups (visa_waiver,
  tourists_business_other, students_exchange_visitors = F/J/M incl. dependants, temp_workers_families = H, L, O, P,
  E, TN, etc. incl. dependants, diplomats_representatives, all_other, unknown); the FY2005-06 "Table 31 ... by
  category of admission and state of destination" has the same eight columns. The INS-era tables "Nonimmigrants
  admitted by selected class of admission and state of intended residence/destination" (1996-97 T43, 1998 T43,
  1999-2001 T41, 2002 T30, 2003-04 T28) give principal classes: f1_m1 (students), j1 (exchange visitors), l1
  (intracompany transferees), h1_h2_h3 (temporary workers and trainees; H-1B is not split out), tn (NAFTA), etc.;
  their column headers are hand-mapped per release and page (COLS_OLD) and verified by summing classes to "All
  classes" (exact for every state row, FY1996-2004; the Excel versions' column headings are mapped to the same
  codes by keyword, INS_NI). Every class x state (h1b, f1, j1, l1, o1, tn, h1b1, e3, ...; principals and
  dependants as separate classes): FY2002 Table 611 (Excel only; "Nonimmigrants admitted by state of destination
  and class of admission"; its j1 / l1 / tn give way to Table 30's) and Nonimmigrant Supplemental Table 3,
  FY2005-2020 and FY2022-24 (the NI2003-04 supplements have country tables only, and no FY2021 supplement is
  here). Single fiscal years, taken from the table title: 1996, 1998-2024. FY1997 does not exist: the 1997
  yearbook's Table 43 is titled FISCAL YEAR 1996 and
  is the FY1996 table reprinted cell for cell (INS published no FY1997 nonimmigrant detail; later national tables
  also skip 1997), kept as the latest FY1996 release.
* National (dhs_us.csv): LPRs by type (total / adjustment / new_arrival) and major class (Table 6, 10 years per
  release, FY1996-2024; employment_total and employment_1st..5th preferences, family, immediate relatives,
  diversity, refugees, asylees, ...); LPRs by broad class x region / country of birth (Table 10, one year per
  release; FY2006-24 also split into new arrivals / adjustments from the "tables8-11newadj" workbooks); I-94
  admissions by detailed class (Table 25 / FY2024 Table 26, 10 years per release, e.g. h1b, f1, j1, l1, tn;
  FY1996, 1998-2024; the FY2005-06 releases' Table 26 is I-94 only and its "unknown" / temporary-worker groups
  are cut differently from the 2007+ releases, see checks.csv). The INS-era (1996-2004) national tables are not
  used: their titles and layouts differ and the 2005-2007 releases cover those years.

Not used, and why, is listed per file in files.csv and per sheet in excel_files.csv (refugee and asylee
workbooks: national by nationality only, no state; enforcement: no state; data dictionary: reference only). Also not used from used PDFs: LPRs / naturalized
/ nonimmigrants by country of birth x state (old T16-17, T44, T51), asylum cases filed by asylum office (claims,
not grants), CBSA tables, and the country rows of the supplemental state x country-of-birth tables.

Releases: multi-year tables are repeated in later yearbooks, often revised. Every release's value is kept in
dhs_releases.csv; dhs_state.csv / dhs_us.csv keep one value per key: the latest release, except that the OHSS
FY2023-24 workbooks round every cell to the nearest 10, so where the latest unrounded (PDF) release agrees with the
rounded one within 5 the unrounded value is kept (same data, more precision); a larger difference is a revision
and the latest release wins. release_fy, source_file, table and rounded say where each value came from;
checks.csv lists every cross-release disagreement beyond rounding.

Outputs (data/dhs_yearbook/):
  dhs_state.csv        fiscal_year, state, measure, class, value, note, rounded, release_fy, source_file, table,
                       table_title
  dhs_state_wide.csv   one row per state-year: lpr_total, lpr_refugees_asylees, naturalized, i94_total,
                       i94_students_exchange, i94_temp_workers_families, i94_f1_m1, i94_j1, i94_l1,
                       i94_h1_h2_h3, i94_tn, i94_h1b, i94_f1, i94_o1 (blank where the source has no such table)
  dhs_us.csv           national-only tables: fiscal_year, measure, breakdown (major_class = Table 6,
                       broad_class_by_country_of_birth = Table 10, class = Table 25), type, class, country,
                       geo_level, value, note, rounded, release_fy, source_file, table, table_title
  dhs_releases.csv     every value from every release (state and US tables), before choosing one
  files.csv            every input file (PDFs, workbooks, excel/ zips): md5, fiscal year from contents, tables
                       used, used, why_not_used, duplicate
  excel_files.csv      every sheet of every workbook and zip member: container, member, sheet, md5, fiscal_year,
                       table, title, kind, used, use / why_not_used, duplicate_of (identical copies)
  excel_vs_pdf.csv     every cell where the Excel and PDF versions of a table differ or exist in only one
  coverage.csv         measure x class x fiscal_year: states (of 50 + DC), territories, US present, releases used
  checks.csv           state sums vs US totals; class sums vs totals; cross-release disagreements; state-table US
                       totals vs national tables; employment-based in Table 10 vs Table 6; Supp 3 vs Table 30;
                       Excel vs PDF (summary per release-table, one row per differing cell); supplemental
                       state x country-of-birth totals vs Tables 4 / 22; Table 611 vs Table 30; the class x state
                       tables' U.S. H-1B / F-1 / J-1 / L-1 / O-1 / TN vs the national class table
  pdf_tables/          the raw extracted PDF grids

Values: "-" (represents zero) is 0; "D" (disclosure standards not met), "X" (not applicable) and "NA" are blank
with the code in `note`. Nothing is imputed.

Caveats and series breaks
* LPRs: "immigrants admitted" (INS, to FY2003) and "persons obtaining LPR status" (DHS) are the same flow: new
  arrivals plus adjustments of status. FY1989-91 include IRCA legalization (2.7 million); FY2020-21 are depressed
  by COVID-19 consular closures; FY2023-24 rose sharply. LPR state is the state of residence (INS: intended
  residence) on the application.
* Naturalizations FY1994-2003: INS reported large "Other or unknown"/"Unknown" counts (e.g. 111,133 in FY1996, and
  some states such as Alaska, Arkansas, Wisconsin show near-zero values in some years) because part of the data
  came from systems without state of residence; state values in those years are undercounts.
* I-94 admissions count arrival events, not people (a student who travels home twice is counted three times), and
  most short-term land admissions from Canada and Mexico are excluded. State of destination is self-reported and
  not required; DHS cautions it may not be the final destination, and "Unknown" is large (9.9 million of 76.8
  million in FY2016). The INS-era (1996-2003) tables are "state of intended residence/destination" from the
  Nonimmigrant Information System and include classes that later moved; broad groups are not identical to the
  DHS Table 30 groups, so only the totals and principal classes (j1, l1, tn) line up across the break. FY2001 has
  business and pleasure visitors combined (b1_b2), as does FY2000. No FY1997 nonimmigrant state data exist (see
  above). FY1996-2004 have principal classes but not the DHS broad groups, and FY2005-2022 have the broad groups
  but not j1 / l1 / tn / f1 / h1b by state; the groups are not derived from the classes here.
* I-94 series breaks flagged by DHS: from FY2010 admissions "greatly exceed" earlier years "due to a more
  complete count of land admissions" (national F-1 admissions 0.9 million in FY2009, 1.5 million in FY2010), and
  FY2013-14 rise again from a more complete count of Canadian air and sea admissions. FY2020-22 are depressed by
  COVID-19 travel restrictions. Compare levels only within FY2010-2012, FY2014-2019 and FY2022 on.
* Country names in Table 10 are as printed and change between releases (e.g. "China, People's Republic" vs
  "China"); they are not harmonized.
* OHSS workbooks (FY2023-24) are rounded to the nearest 10, so their state sums need not equal the total. A
  sheet counts as rounded when 98%+ of its cells of 10 or more are multiples of 10 (notes saying "rounding" are not
  a test).
* Excel vs PDF: identical except FY2004 Table 28 (Excel moves 326 admissions in 43 states between temporary
  workers and NAFTA workers; the PDF's TN total matches the national table, the Excel's does not; Excel is used),
  single cells off by 1-2 in FY1994 / FY2001 / FY2003 LPR and naturalization totals, and FY2003 Montana
  naturalizations (blank in the PDF text, 75 / 81 in Excel). The PDFs' Table 10 country names were sometimes
  garbled by wrapped headings; the Excel names replace them.
* Class x state I-94 tables: the Supp. 3 classes sum to Table 30's state totals except FY2005 (Supp. 3 is 0.4%
  lower), FY2007 (Supp. 3 counts Guam in "Other") and FY2008 (Guam 4,769 lower). Their U.S. H-1B, F-1, J-1, L-1,
  O-1 and TN equal the national Table 25 in every release; Table 611's FY2002 TN is 334 above it. The I-94
  counting breaks above apply to every class; shares of U.S. admissions are the comparable form.
* PDF text layers: all 40 PDFs have a usable text layer (no scanned tables; the image-only pages are covers,
  section dividers and charts). Quirks handled: footnote markers between header years ("1998 1 1999"), dots in
  place of spaces in the FY2006 yearbook ("New.York"), kerning gaps in 1998 ("1 ,611"), one typo in FY2005
  Table 26 ("1.010,756"). Printed state rows sum exactly to the printed totals in every release-table except
  1999 T17 (FY1994) and 2003 T11 (FY2003), off by 1 in the source, and 1998 T43, where Rhode Island's last cell is
  blank in print.
* Revisions between editions are large for FY1996-2007: the 2005-2007 yearbooks report "Other" (territories and
  armed forces posts) of 5-8 thousand LPRs a year where the 2008+ editions report about 1 thousand, and revised
  FY1996-2001 totals and naturalizations down by 0.5-4 thousand; the latest edition is used (checks.csv lists
  every disagreement).
* FY2024 series break in the broad I-94 groups: the FY2024 workbook moves treaty traders and investors (E1-E3 and
  dependants) out of "temporary workers and families" into their own column (treaty_traders_investors in Table
  31) and revises Table 26 back to FY2015 on that basis (about 0.4-0.5 million fewer per year; checks.csv). The
  FY2008-2023 state values of temp_workers_families include E classes; FY2024 does not.
* Table 6 "Other" and some small classes were re-cut over time (from the FY2017 release, classes such as
  victims of crimes, Iraqi/Afghan employees and cancellation of removal are shown separately and "Other" shrinks);
  the latest release's classes are used for each year, so compare "other" with care.
"""
from __future__ import annotations

import hashlib
import re
import warnings
import zipfile
from pathlib import Path

import pandas as pd

from .config import DATA, SOURCES

SRC = SOURCES / "dhs_yearbook"
OUT = DATA / "dhs_yearbook"
GRID = OUT / "pdf_tables"

NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
STATES51 = set(NAMES)
TERR = {"puerto rico": "PR", "guam": "GU", "u.s. virgin islands": "VI", "virgin islands": "VI",
        "northern mariana islands": "MP", "northern mariana is.": "MP", "northern mariana is": "MP",
        "american samoa": "AS", "marshall islands": "MH", "federated states of micronesia": "FM", "palau": "PW",
        "american somoa": "AS", "u. s. virgin islands": "VI", "federated states of micro": "FM"}   # Excel spellings
OTHER = {"total": "US", "other": "OTHER", "unknown": "UNKNOWN", "other or unknown": "OTHER_OR_UNKNOWN",
         "armed services posts": "ARMED_FORCES", "armed forces posts": "ARMED_FORCES", "all states": "US"}
CODE = {**{v.lower(): k for k, v in NAMES.items()}, **TERR, **OTHER, "dist. of columbia": "DC"}
TERR_CODES = sorted(set(TERR.values()))

# Title patterns (matched against upper-cased, whitespace-collapsed text). Order matters: the detailed
# class x state supplemental table must be tested before the national class table.
SPECS = [
    ("lpr_state", r"(?:PERSONS OBTAINING (?:LEGAL|LAWFUL) PERMANENT RESIDENT STATUS|IMMIGRANTS ADMITTED) BY STATE "
                  r"(?:OR TERRITORY )?OF (?:INTENDED )?RESIDENCE\W*FISCAL YEARS"),
    ("natz_state", r"PERSONS NATURALIZED BY STATE (?:OR TERRITORY )?OF RESIDENCE\W*FISCAL YEARS"),
    ("refasy_state", r"REFUGEES AND ASYLEES GRANTED (?:LAWFUL )?PERMANENT RESIDENT STATUS BY STATE OF RESIDENCE"),
    # FY2005-06 Table 31 drops "SELECTED"; a bare "BY CLASS OF ADMISSION AND STATE" is the detailed table
    ("ni_state", r"NONIMMIGRANT(?:S ADMITTED| ADMISSIONS)(?: \(I-94 ONLY\))? BY (?:SELECTED (?:CLASS|CATEGORY)|CATEGORY) "
                 r"OF ADMISSION AND STATE"),
    ("ni_state_detail", r"NONIMMIGRANT ADMISSIONS(?: \(I-94 ONLY\))? BY CLASS OF ADMISSION AND STATE"),
    # FY2002 Table 611 (Excel only): every class of admission (H-1B, F-1, ...) as columns, states as rows
    ("ni_state_611", r"NONIMMIGRANTS ADMITTED BY STATE OF DESTINATION AND CLASS OF ADMISSION"),
    ("lpr_class_us", r"PERSONS OBTAINING (?:LEGAL|LAWFUL) PERMANENT RESIDENT STATUS BY TYPE AND MAJOR CLASS"),
    ("lpr_cob_us", r"PERSONS OBTAINING (?:LEGAL|LAWFUL) PERMANENT RESIDENT STATUS BY (?:TYPE AND )?BROAD CLASS OF "
                   r"ADMISSION AND REGION AND COUNTRY OF BIRTH"),
    # Supplemental Table 1 (Excel only): state x country of birth; only the all-countries row is read (cross-check)
    ("lpr_state_cob", r"(?:PERSONS OBTAINING (?:LEGAL|LAWFUL) PERMANENT RESIDENT STATUS|LEGAL PERMANENT RESIDENT FLOW|"
                      r"IMMIGRANTS \(PERSONS GRANTED LAWFUL PERMANENT RESIDENCE\)|IMMIGRANTS ADMITTED) BY (?:STATE "
                      r"(?:OR TERRITORY )?OF RESIDENCE AND (?:REGION (?:AND|OR) )?COUNTRY OF BIRTH|COUNTRY OF BIRTH AND "
                      r"(?:INTENDED )?STATE OF (?:INTENDED )?RESIDENCE)"),
    ("natz_state_cob", r"(?:PERSONS NATURALIZED|NATURALIZATIONS) BY (?:STATE (?:OR TERRITORY )?OF RESIDENCE AND "
                       r"(?:REGION (?:AND|OR) )?COUNTRY OF BIRTH|COUNTRY OF BIRTH AND (?:INTENDED )?STATE OF "
                       r"(?:INTENDED )?RESIDENCE)"),
    ("ni_class_us", r"NONIMMIGRANT ADMISSIONS(?: \(I-94 ONLY\))? BY CLASS OF ADMISSION\W*FISCAL YEARS"),
]
MEASURE = {"lpr_state": ("lpr", "total"), "natz_state": ("naturalized", "total"),
           "refasy_state": ("lpr", "refugees_asylees"), "lpr_state_cob": ("lpr", "total"),
           "natz_state_cob": ("naturalized", "total")}
EXCEL_ONLY = {"ni_state_611", "lpr_state_cob", "natz_state_cob"}
COB_KINDS = {"lpr_state_cob", "natz_state_cob"}   # cross-checks only, never chosen
POSTAL = {k.lower(): k for k in NAMES}             # FY2002 supplemental tables head their columns AK, AL, ...

# DHS Table 30/31 (FY2008+): fixed columns.
COLS_T30 = ["total", "visa_waiver", "tourists_business_other", "students_exchange_visitors",
            "temp_workers_families", "diplomats_representatives", "all_other", "unknown"]
COLS_T10 = ["total", "immediate_relatives", "family", "employment", "diversity", "refugees_asylees", "other"]
# FY2008-2016 PDFs print Table 10 with family and employment before immediate relatives.
COLS_T10_OLD = ["total", "family", "employment", "immediate_relatives", "diversity", "refugees_asylees", "other"]
# INS-era nonimmigrant x state tables: printed column headers are interleaved in the text layer, so the columns
# are mapped by hand, page by page (fiscal year, page within table) and verified by summing to "All classes".
_P1 = ["total", "a1_a3", "b1", "b2", "c1_c3", "e1_e2", "f1_m1", "f2_m2", "h1_h2_h3", "h4"]
_P2 = ["g1_g5", "i1", "j1", "j2", "k1_k2", "l1", "l2", "n1_n7", "tn"]
_P3 = ["k3_k4", "v1", "v2", "v3", "t1", "t2_t4", "u1", "u2_u4", "other_unknown"]
_P1B = ["total", "a1_a3", "b1_b2"] + _P1[4:]   # FY2000-01: business and pleasure visitors in one column
COLS_OLD = {   # keyed by release (yearbook) year; the 1997 yearbook reprints the FY1996 table
    (1996, 0): _P1, (1996, 1): _P2 + ["unknown"],
    (1997, 0): _P1, (1997, 1): _P2 + ["unknown"],
    (1998, 0): _P1, (1998, 1): _P2 + ["other_unknown"],
    (1999, 0): _P1, (1999, 1): _P2 + ["other_unknown"],
    (2000, 0): _P1B, (2000, 1): _P2 + ["other_unknown"],
    (2001, 0): _P1B, (2001, 1): _P2 + ["td"], (2001, 2): _P3,
    (2002, 0): _P1, (2002, 1): _P2 + ["td"], (2002, 2): _P3,
    (2003, 0): _P1, (2003, 1): _P2 + ["td"], (2003, 2): _P3,
    # FY2004 Table 28: six classes per page, five pages (the sixth page is footnotes only)
    (2004, 0): ["total", "a1_a3", "b1", "b2", "c1_c3", "e1_e2"],
    (2004, 1): ["f1_m1", "f2_m2", "h1_h2_h3", "h4", "g1_g5", "i1"],
    (2004, 2): ["j1", "j2", "k1_k2", "l1", "l2", "n1_n7"],
    (2004, 3): ["tn", "td", "k3_k4", "v1", "v2", "v3"],
    (2004, 4): ["t1", "t2_t4", "u1", "u2_u4", "other_unknown"],
}
WIDE = {("lpr", "total"): "lpr_total", ("lpr", "refugees_asylees"): "lpr_refugees_asylees",
        ("naturalized", "total"): "naturalized", ("i94_admissions", "total"): "i94_total",
        ("i94_admissions", "students_exchange_visitors"): "i94_students_exchange",
        ("i94_admissions", "temp_workers_families"): "i94_temp_workers_families",
        ("i94_admissions", "f1_m1"): "i94_f1_m1", ("i94_admissions", "j1"): "i94_j1",
        ("i94_admissions", "l1"): "i94_l1", ("i94_admissions", "h1_h2_h3"): "i94_h1_h2_h3",
        ("i94_admissions", "tn"): "i94_tn", ("i94_admissions", "h1b"): "i94_h1b",
        ("i94_admissions", "f1"): "i94_f1", ("i94_admissions", "o1"): "i94_o1"}
ORD = {"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th"}
VAL = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+|-|–|X|D|NA)")
YEAR = re.compile(r"((?:19|20)\d\d)\d?")
ROUND_TOL = 5   # OHSS rounds cells to the nearest 10


# ---------------------------------------------------------------- small helpers
def norm(s: str) -> str:
    s = str(s).replace("￾", "").replace("\xad", "").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(?<=\d) ,(?=\d{3}\b)", ",", s)   # "1 ,611" (a kerning gap in the 1998 text layer)
    return re.sub(r"(?<=\b\d)\.(?=\d{3},\d{3}\b)", ",", s)   # "1.010,756" (a typo in the FY2005 Table 26)


def clean_label(s: str) -> str:
    s = re.sub(r"(?<=[a-z])\.(?=[A-Za-z0-9])", " ", norm(s))   # FY2006 text layer: "New.York", "Other.1"
    s = s.strip(" .")
    s = re.sub(r"\s+\d/$", "", s)                                 # INS Excel footnote markers: "Unknown 7/"
    s = re.sub(r"(?<=[A-Za-z)\]])\s?\d{1,2}$", "", s)        # trailing footnote marker: "Other1", "Other 1"
    s = re.sub(r"(?<=[A-Za-z)\]]),?\s?\d(?:,\s?\d)*$", "", s)  # "Other 1, 2"
    return s.strip(" .")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:48]


def state_code(label: str) -> str | None:
    return CODE.get(clean_label(label).lower().rstrip("."))


def to_num(raw) -> tuple[float | None, str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, "blank"
    if isinstance(raw, (int, float)):
        return float(raw), ""
    t = str(raw).strip()
    if t in ("-", "–", "0"):
        return 0.0, ""
    if t in ("D", "X", "NA"):
        return None, {"D": "D: disclosure standards not met", "X": "X: not applicable", "NA": "NA"}[t]
    try:
        return float(t.replace(",", "")), ""
    except ValueError:
        return None, f"unparsed: {t}"


def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def kind_of(title: str) -> str | None:
    t = norm(title).upper().replace("OFADMISSION", "OF ADMISSION")   # 1996 Table 43 typo
    for k, pat in SPECS:
        if re.search(pat, t):
            return k
    return None


# ---------------------------------------------------------------- PDF parsing
def split_line(line: str):
    """'Alabama . . . 1,234 5 -' -> ('Alabama', ['1,234','5','-']); header/notes -> None."""
    line = norm(line)
    m = re.match(r"^(.*?[A-Za-z)\]].*?)\s*(?:\.\s*){2,}(.*)$", line)
    if m:
        toks = m.group(2).split()
        if toks and all(VAL.fullmatch(t) for t in toks):
            return m.group(1), toks
    toks = line.split()
    i = len(toks)
    while i > 0 and VAL.fullmatch(toks[i - 1]):
        i -= 1
    if i == len(toks) or i == 0:
        return None
    return " ".join(toks[:i]), toks[i:]


def header_years(line: str) -> list[int] | None:
    if "FISCAL" in line.upper():
        return None
    toks = norm(line).split()
    # a one-digit footnote marker after a year ("1998 1 1999") is not a value
    toks = [t for i, t in enumerate(toks) if not (re.fullmatch(r"\d", t) and i and YEAR.fullmatch(toks[i - 1]))]
    ys = [YEAR.fullmatch(t) for t in toks]
    ys = [int(m.group(1)) for m in ys if m]
    nonyear_nums = [t for t in toks if VAL.fullmatch(t) and not YEAR.fullmatch(t)]
    return ys if len(ys) >= 2 and not nonyear_nums else None


def pdf_info(path: Path):
    """Fiscal year (from the Table 1 title) and the pages holding each wanted table (located by title)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(path))
    years, found, npages = [], {}, len(doc)
    for i in range(npages):
        tp = doc[i].get_textpage()
        txt = norm(tp.get_text_range()).upper()
        tp.close()
        years += [int(y) for y in re.findall(r"FISCAL YEARS 1820 ?(?:TO|-) ?(\d{4})", txt)]
        # the title is at the top of the page, except on FY2020-22 continuation pages, where the text layer puts it
        # after the data; a page naming several different tables (contents, lists) is skipped
        ms = list(re.finditer(r"TABLE (\d+)\. ?(.{20,260}?FISCAL YEARS? \d{4}(?: ?(?:TO|-) ?\d{2,4})?)", txt))
        if len({m.group(1) for m in ms}) != 1:
            continue
        m = ms[0]
        k = kind_of(m.group(2))
        if k and k not in EXCEL_ONLY:
            found.setdefault((k, int(m.group(1))), {"pages": [], "title": m.group(2)})["pages"].append(i)
    doc.close()
    fy = max(set(years), key=years.count) if years else None
    return fy, npages, found


def read_pdf_table(path: Path, fy: int, kind: str, num: int, pages: list[int]):
    """Parse the pages of one table into grid records [{page, panel, label, col: raw, ...}]."""
    import pdfplumber
    recs, issues, panel = [], [], "total"
    wrap = kind in ("lpr_class_us", "ni_class_us", "lpr_cob_us")
    with pdfplumber.open(str(path)) as pdf:
        for pi, pno in enumerate(pages):
            lines = (pdf.pages[pno].extract_text() or "").split("\n")
            cols, pending = None, []
            if kind == "ni_state" and fy <= 2004:
                cols = COLS_OLD.get((fy, pi))
            elif kind == "ni_state":
                cols = COLS_T30
            elif kind == "lpr_cob_us":
                hdr = " ".join(norm(x) for x in lines[:12])
                cols = COLS_T10_OLD if "Total preferences preferences citizens" in hdr else COLS_T10
            for ln in lines:
                s = norm(ln)
                ys = header_years(s)
                if ys:
                    cols, pending = [str(y) for y in ys], []
                    continue
                up = s.upper()
                if up in ("TOTAL", "ADJUSTMENTS OF STATUS", "ADJUSTMENT OF STATUS", "NEW ARRIVALS"):
                    panel = {"TOTAL": "total", "NEW ARRIVALS": "new_arrival"}.get(up, "adjustment")
                    pending = []
                    continue
                if up in ("REGION", "COUNTRY"):
                    panel, pending = up.lower(), []
                    continue
                sp = split_line(s)
                if not sp:
                    if wrap and s and not s.upper().startswith(("TABLE", "SEE FOOTNOTES")) and len(pending) < 3:
                        pending.append(s)
                    continue
                label, vals = sp
                if wrap and pending:
                    label = " ".join(pending + [label])
                pending = []
                noisy = len(vals) < 2 and not state_code(label)   # page numbers, running heads, footnotes
                if cols is None:
                    if not noisy:
                        issues.append(f"{fy} table {num} p{pno + 1}: no column header before row '{label}'")
                    continue
                if len(vals) > len(cols):   # leading extras are footnote markers printed after the label
                    extra, vals = vals[:len(vals) - len(cols)], vals[len(vals) - len(cols):]
                    if not all(re.fullmatch(r"\d", e) for e in extra):
                        issues.append(f"{fy} table {num} p{pno + 1}: '{label}' has {len(vals) + len(extra)} values"
                                      f" for {len(cols)} columns")
                        continue
                if (len(vals) == len(cols) - 1 and kind == "ni_state" and fy <= 2003 and state_code(label)
                        and cols[-1] in ("unknown", "other_unknown", "td")):
                    # last ("other/unknown") cell printed blank; verified by the class-sum check
                    issues.append(f"{fy} table {num} p{pno + 1}: '{label}' last column ({cols[-1]}) blank in source;"
                                  f" kept the other {len(vals)}")
                    recs.append({"page": pno + 1, "panel": panel, "label": label, **dict(zip(cols, vals))})
                    continue
                if len(vals) < len(cols):
                    if noisy:
                        continue
                    issues.append(f"{fy} table {num} p{pno + 1}: '{label}' has {len(vals)} values for {len(cols)}"
                                  f" columns; skipped")
                    continue
                recs.append({"page": pno + 1, "panel": panel, "label": label, **dict(zip(cols, vals))})
    return recs, issues


# ---------------------------------------------------------------- Excel parsing
def t30_col(h: str) -> str:
    """Excel Table 30/31 column header -> class name."""
    for k, v in (("visa waiver", "visa_waiver"), ("all other", "all_other"), ("students", "students_exchange_visitors"),
                 ("temporary workers", "temp_workers_families"), ("treaty", "treaty_traders_investors"),
                 ("diplomats", "diplomats_representatives"), ("unknown", "unknown"), ("total", "total"),
                 ("other", "tourists_business_other")):
        if k in h:
            return v
    raise ValueError(f"unmapped Table 30 column: {h}")


# INS-era (FY1996-2004) nonimmigrant x state tables: column group headings -> the class codes used for the PDFs
# (COLS_OLD); tested in order against the column's heading text joined top to bottom (lower case).
INS_NI = [(r"^all classes", "total"),
          (r"spouses?.*(?:intra.?company|intracom)", "l2"), (r"spouses?.*exchange", "j2"),
          (r"spouses?,? children,? and parents of victims? of severe", "t2_t4"),
          (r"spouses?,? children,? and parents of victims? of criminal", "u2_u4"),
          (r"spouses?.*(?:free.?trade|nafta)", "td"), (r"spouses?.*temp", "h4"), (r"spouses?.*student", "f2_m2"),
          (r"spouse and/or child of us citizen", "k3_k4"), (r"spouse of legal perm", "v1"),
          (r"^child of legal perm", "v2"), (r"dependent child", "v3"), (r"victims? of severe", "t1"),
          (r"victims? of criminal", "u1"), (r"govern", "a1_a3"), (r"business ?(?:&|and) ?pleasure", "b1_b2"),
          (r"business", "b1"), (r"pleasure", "b2"), (r"transit", "c1_c3"), (r"treaty", "e1_e2"),
          (r"^students", "f1_m1"), (r"temp.*workers|workers and trainee", "h1_h2_h3"),
          (r"media", "i1"), (r"interna", "g1_g5"), (r"exchange", "j1"), (r"fian", "k1_k2"), (r"intra", "l1"),
          (r"nato", "n1_n7"), (r"free.?trade|nafta", "tn"), (r"^other and u", "other_unknown"),
          (r"^unknown", "unknown")]
T10_COL = [("total", "total"), ("family", "family"), ("employment", "employment"), ("immediate", "immediate_relatives"),
           ("diversity", "diversity"), ("refugee", "refugees_asylees"), ("other", "other")]


def _txt(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else norm(v)


def _year(v) -> int | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool) and not pd.isna(v):
        return int(v) if float(v).is_integer() and 1900 <= v <= 2030 else None
    m = re.fullmatch(r"((?:19|20)\d\d)(?:\.0)?(?:\s*/?\d{1,2}/?)?", _txt(v))
    return int(m.group(1)) if m else None


def load_book(data: bytes) -> dict[str, pd.DataFrame]:
    """All sheets of an .xlsx/.xls (calamine; xlrd for the BIFF4 files of the 1996 yearbook), header=None."""
    import io
    try:
        return pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, engine="calamine")
    except Exception:
        import xlrd
        wb = xlrd.open_workbook(file_contents=data, logfile=io.StringIO())
        return {sh.name: pd.DataFrame([[None if (isinstance(v, str) and not v.strip()) else v
                                        for v in sh.row_values(i)] for i in range(sh.nrows)])
                for sh in wb.sheets()}


def sheet_head(d: pd.DataFrame, n: int = 8) -> str:
    """Text of the first rows (every column): the table number and title."""
    return " ".join(_txt(v) for v in d.iloc[:n].values.ravel() if isinstance(v, str) and _txt(v))


def head_title(head: str) -> tuple[str, str]:
    """('Table 4' / 'Supplemental Table 1' / ..., upper-case title through the fiscal year(s))."""
    h = norm(head)
    m = re.search(r"((?:Nonimmigrant |Naturalization )?Supplemental Table \d+|Table \d+[A-Z]?)\.?", h, re.I)
    num = norm(m.group(1)).title() if m else ""
    t = h[m.end():] if m else h
    t = re.sub(r"^.*?Return to Table of Contents\.?", "", t, flags=re.I)
    f = re.search(r"^(.*?FISCAL YEARS? \d{4}(?: ?(?:TO|-) ?\d{2,4})?)", t, re.I)
    return num, norm(f.group(1) if f else t[:200]).upper().strip(" .:|")


def excel_tables(sheets: dict[str, pd.DataFrame]):
    """Yield (kind, sheet, title, rounded, records) for each wanted sheet of a workbook. Records are grid rows in the
    PDF layout: {"panel", "label", <column>: raw value}; columns are years, class codes or state names by kind."""
    for name, d in sheets.items():
        if str(name).upper() == "TOC" or d.shape[0] < 6 or d.shape[1] < 2:
            continue
        d = d.map(lambda v: None if isinstance(v, str) and not v.strip() else v)
        head = sheet_head(d)
        kind = kind_of(head)
        if not kind:
            continue
        _, title = head_title(head)
        prefix = "new_arrival" if "NEW ARRIVALS -" in head.upper() else (
            "adjustment" if "ADJUSTMENT OF STATUS -" in head.upper() or "ADJUSTMENTS OF STATUS -" in head.upper()
            else "total")
        # OHSS (FY2023+) rounds every cell to 10; notes mentioning "rounding" are not a test, so look at the cells
        nums = [v for v in d.values.ravel() if isinstance(v, (int, float)) and not pd.isna(v) and v >= 10
                and float(v).is_integer() and not 1900 <= v <= 2030]
        rounded = len(nums) >= 20 and sum(v % 10 == 0 for v in nums) / len(nums) > 0.98
        txt = [[_txt(v) for v in row] for row in d.values.tolist()]
        # label column: the one (of the first three) naming the most states
        lc = max(range(min(3, d.shape[1])), key=lambda j: sum(bool(state_code(r[j])) for r in txt if r[j]))
        lab = [r[lc] for r in txt]
        low = [x.lower() for x in lab]
        recs = []
        try:
            recs = _excel_records(kind, d, txt, lab, low, lc, prefix, title)
        except StopIteration:
            pass
        if recs:
            yield kind, str(name), title, rounded, recs


def _stop(label: str) -> bool:
    return bool(re.match(r"^\d\s|^\d[A-Z ]|^notes?\b|^source|^- |^d\s|^x\s|^see |^\* ", label, re.I))


def _excel_records(kind, d, txt, lab, low, lc, prefix, title):
    n, ncol = len(txt), d.shape[1]
    recs = []
    if kind in ("lpr_state", "natz_state", "refasy_state", "lpr_class_us", "ni_class_us"):
        hdr = next(i for i in range(n) if sum(_year(v) is not None for j, v in enumerate(d.iloc[i]) if j != lc) >= 2)
        cols = {j: str(_year(d.iat[hdr, j])) for j in range(ncol) if j != lc and _year(d.iat[hdr, j])}
        panel = prefix
        for i in range(hdr + 1, n):
            vals = {c: d.iat[i, j] for j, c in cols.items()}
            empty = all(pd.isna(v) for v in vals.values())
            up = lab[i].upper()
            if empty and up in ("TOTAL", "ADJUSTMENTS OF STATUS", "ADJUSTMENT OF STATUS", "NEW ARRIVALS"):
                panel = {"TOTAL": "total", "NEW ARRIVALS": "new_arrival"}.get(up, "adjustment")
                continue
            if not lab[i] or empty:
                if _stop(lab[i]) and kind not in ("lpr_state", "natz_state", "refasy_state"):
                    break
                continue
            recs.append({"panel": panel, "label": lab[i], **vals})
        return recs
    if kind == "ni_state":
        start = next(i for i in range(n) if re.match(r"(total|all states|all classes)\b", low[i])
                     or state_code(lab[i]) not in (None, "US"))
        top = max([i for i in range(start) if any("FISCAL YEAR" in t.upper() for t in txt[i])] + [-1]) + 1
        fy = int(re.search(r"FISCAL YEAR (\d{4})", title).group(1))
        cols = {}
        for j in range(ncol):
            if j == lc:
                continue
            h = norm(" ".join(txt[i][j] for i in range(top, start) if txt[i][j])).lower()
            h = re.sub(r"(?<=\w)- (?=\w)", "", h)              # hyphenated line breaks: "govern- ment"
            h = re.sub(r"\s*(?:/?\d(?:/|,\s?\d)*/?)+$", "", h)   # footnote markers: "1/2/", "/1, /2", "3"
            if not h:
                continue
            if fy >= 2005:
                cols[j] = t30_col(h)
            else:
                code = next((c for pat, c in INS_NI if re.search(pat, h)), None)
                if code is None:
                    raise ValueError(f"unmapped INS nonimmigrant column '{h}' ({title})")
                if code in ("unknown", "other_unknown"):   # keep the PDF tables' code for this release
                    old = [c for k, v in COLS_OLD.items() if k[0] == fy for c in v if c in ("unknown", "other_unknown")]
                    code = old[0] if old else code
                cols[j] = code
        for i in range(start, n):
            if not lab[i] or all(pd.isna(d.iat[i, j]) for j in cols):
                continue
            recs.append({"panel": "total", "label": lab[i], **{c: d.iat[i, j] for j, c in cols.items()}})
        return recs
    if kind == "ni_state_611":
        hdr = next(i for i in range(n) if low[i].startswith("state of destination"))
        cols, group = {}, ""
        for j in range(1, ncol):
            g, h = txt[hdr - 1][j], txt[hdr][j]
            if g and not re.fullmatch(r"total:?", g, re.I):
                group = g
            m = re.search(r"\(([A-Z0-9]{1,3}(?:-[A-Z0-9]{1,3})?)\)", h)
            h0 = re.sub(r"\s+\d$", "", h).strip()
            if m:
                code = m.group(1).replace("-", "_").lower()
            elif re.fullmatch(r"[A-Z]{1,2}\d?[A-Z]?(?:/[A-Z]\d)?", h0):
                code = h0.replace("/", "_").lower()
            elif h0.lower().startswith("total:") or g.lower().startswith("total:"):
                code = "total_" + slug(re.sub(r"(?i)total:?", "", h0 if h0.lower() != "total:" else h0 + g))
            elif h0.lower() == "total" and j <= 2:
                code = ["total_611_excl_crew_er_vwp_refusals", "total_611_excl_parolees_refugees"][j - 1]
            elif h0.lower() == "total":
                code = "grp_" + slug(group)
            elif h0.lower() == "unknown":
                code = "supp_unknown"
            else:
                code = "col_" + slug(g + " " + h0)
            cols[j] = code
        for i in range(hdr + 1, n):
            if not lab[i] or all(pd.isna(d.iat[i, j]) for j in cols):
                continue
            if _stop(lab[i]):
                break
            recs.append({"panel": "total", "label": lab[i], **{c: d.iat[i, j] for j, c in cols.items()}})
            if low[i] == "unknown":   # the sheet then repeats the last rows with only some columns filled
                break
        return recs
    if kind == "ni_state_detail":
        hdr = next(i for i in range(n) if low[i].startswith("class"))
        cols = [norm(v) if isinstance(v, str) else "" for v in d.iloc[hdr, 2:]]
        for i in range(hdr + 1, n):
            code, desc, vals = lab[i], txt[i][1], d.iloc[i, 2:2 + len(cols)].tolist()
            if not code and desc == "Total":
                code = "Total"
            if not code or all(pd.isna(v) for v in vals):
                if re.match(r"^\d|Notes|Source", code):
                    break
                continue
            recs.append({"panel": "total", "label": code, "description": desc,
                         **{c: v for c, v in zip(cols, vals) if c}})
        return recs
    if kind == "lpr_cob_us":
        hdr = next(i for i in range(n) if low[i].startswith("region and country"))
        crow = next(i for i in range(hdr, n) if any(t.lower().startswith("family") for t in txt[i]))
        cols, typ = {}, prefix
        for j in range(ncol):
            if j == lc:
                continue
            p = txt[hdr][j].lower() if crow != hdr else ""
            if p:
                typ = "adjustment" if p.startswith("adjust") else "new_arrival" if p.startswith("new") else "total"
            h = txt[crow][j].lower()
            c = next((v for k, v in T10_COL if h.startswith(k) or (k == "refugee" and "refugee" in h)), None)
            if c:
                cols[j] = (typ, c)
        panel = "region"
        for i in range(crow + 1, n):
            vals = [d.iat[i, j] for j in cols]
            if low[i] in ("region", "country") and all(pd.isna(v) for v in vals):
                panel = low[i]
                continue
            if not lab[i] or all(pd.isna(v) for v in vals):
                if _stop(lab[i]):
                    break
                continue
            for typ in dict.fromkeys(t for t, _ in cols.values()):
                recs.append({"panel": panel, "label": lab[i], "type": typ,
                             **{c: d.iat[i, j] for j, (t, c) in cols.items() if t == typ}})
        return recs
    if kind in COB_KINDS:   # state x country of birth: keep the all-countries row only
        hdr = next(i for i in range(n) if sum(bool(state_code(t) or t.lower() in POSTAL) for t in txt[i]) >= 10)
        terr = {"gu": "Guam", "mp": "Northern Mariana Islands", "pr": "Puerto Rico", "vi": "U.S. Virgin Islands"}
        cols = {j: (NAMES[POSTAL[t.lower()]] if t.lower() in POSTAL else terr.get(t.lower(), t))
                for j in range(ncol) if j != lc and (t := txt[hdr][j])}
        for i in range(hdr + 1, n):
            if low[i] in ("total", "all countries") and any(not pd.isna(d.iat[i, j]) for j in cols):
                fy = re.search(r"FISCAL YEAR (\d{4})", title).group(1)
                return [{"panel": "total", "label": c, fy: d.iat[i, j]} for j, c in cols.items()]
        return []
    return recs


# ---------------------------------------------------------------- grid records -> tidy rows
def lpr_class_code(label: str, ctx: dict) -> str:
    l = clean_label(label).lower()
    if l.startswith("total"):
        ctx["sec"] = None
        return "total"
    for key, sec, code in (("immediate relatives", "ir", "immediate_relatives"),
                           ("family-sponsored", "fam", "family_total"),
                           ("employment-based", "emp", "employment_total")):
        if l.startswith(key):
            ctx["sec"] = sec
            return code
    m = re.match(r"(first|second|third|fourth|fifth)\b", l)
    if m and ctx.get("sec") in ("fam", "emp"):
        return f"{'family' if ctx['sec'] == 'fam' else 'employment'}_{ORD[m.group(1)]}"
    if ctx.get("sec") == "ir" and l.split()[0] in ("spouses", "children", "parents"):
        return "ir_" + l.split()[0]
    ctx["sec"] = None
    for key, code in (("children born abroad", "children_born_abroad"), ("victims of crimes", "victims_of_crimes"),
                      ("certain iraqis", "iraqi_afghan_us_govt_employees"), ("nicaraguan adjustment", "nacara"),
                      ("haitian refugee", "hrifa")):
        if l.startswith(key):
            return code
    return slug(l)


def ni_class_code(label: str, title: str = "") -> str:
    l = clean_label(label)
    m = re.search(r"\(([A-Z0-9]{1,4}(?:(?:, | to | and )[A-Z0-9]{1,4})*)\)$", l)
    if m:
        return re.sub(r"[ ,]+(?:to |and )?", "_", m.group(1)).lower()
    if l.lower().startswith("total i-94") or (l == "Total" and "I-94 ONLY" in title.upper()):
        return "total_i94"
    if l.lower().startswith("total all admissions"):
        return "total_all_admissions"
    return "group_" + slug(l)


def tidy(kind, recs, meta):
    """Grid records -> long rows. meta: release_fy, source_file, table, table_title, rounded."""
    rows = []
    if kind in MEASURE:
        measure, cls = MEASURE[kind]
        for r in recs:
            st = state_code(r["label"])
            if not st:
                continue
            for c, raw in r.items():
                if c.isdigit():
                    v, note = to_num(raw)
                    rows.append({"fiscal_year": int(c), "state": st, "measure": measure, "class": cls,
                                 "value": v, "note": note, **meta})
    elif kind in ("ni_state", "ni_state_611", "ni_state_detail"):
        # single-year tables: the year printed in the title (the 1997 yearbook's Table 43 is FY1996 data)
        m = re.search(r"FISCAL YEAR (\d{4})", meta.get("table_title") or "")
        fy = int(m.group(1)) if m else meta["release_fy"]
        if kind in ("ni_state", "ni_state_611"):
            states = [(state_code(r["label"]), r) for r in recs]
            merged = {}
            for st, r in states:
                if st:
                    merged.setdefault(st, {}).update({c: v for c, v in r.items() if c not in ("page", "panel", "label")
                                                      and not (st in merged and pd.isna(v))})
            for st, cols in merged.items():
                for c, raw in cols.items():
                    v, note = to_num(raw)
                    rows.append({"fiscal_year": fy, "state": st, "measure": "i94_admissions", "class": c,
                                 "value": v, "note": note, **meta})
        else:
            for r in recs:
                if r["label"] == "Total":
                    continue   # the totals are in Table 30/31; compared in checks
                cls = slug(r["label"].replace(" to ", "_").replace("-", ""))   # FY2005-07 print "H-1B"
                cls = {"other": "supp_other", "unknown": "supp_unknown"}.get(cls, cls)
                for c, raw in r.items():
                    if c in ("panel", "label", "description"):
                        continue
                    st = state_code(c)
                    if st:
                        v, note = to_num(raw)
                        rows.append({"fiscal_year": fy, "state": st, "measure": "i94_admissions", "class": cls,
                                     "value": v, "note": note, **meta})
    elif kind == "lpr_class_us":
        ctx = {}
        for r in recs:
            cls = lpr_class_code(r["label"], ctx)
            for c, raw in r.items():
                if c.isdigit():
                    v, note = to_num(raw)
                    rows.append({"fiscal_year": int(c), "measure": "lpr", "breakdown": "major_class",
                                 "type": r["panel"], "class": cls,
                                 "country": "Total", "geo_level": "world", "value": v, "note": note, **meta})
    elif kind == "ni_class_us":
        for r in recs:
            cls = ni_class_code(r["label"], meta.get("table_title") or "")
            for c, raw in r.items():
                if c.isdigit():
                    v, note = to_num(raw)
                    rows.append({"fiscal_year": int(c), "measure": "i94_admissions", "breakdown": "class",
                                 "type": "total", "class": cls,
                                 "country": "Total", "geo_level": "world", "value": v, "note": note, **meta})
    elif kind == "lpr_cob_us":
        for r in recs:
            lab = clean_label(r["label"])
            level = "world" if lab == "Total" else r["panel"]
            for c in COLS_T10:
                v, note = to_num(r.get(c))
                rows.append({"fiscal_year": meta["release_fy"], "measure": "lpr",
                             "breakdown": "broad_class_by_country_of_birth", "type": r.get("type", "total"),
                             "class": c, "country": lab, "geo_level": level, "value": v, "note": note, **meta})
    return rows


# ---------------------------------------------------------------- choose one release per key
def choose(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    # within a release, a main table (prio 0) wins over FY2002 Table 611 (prio 1) where both give a class
    df = df.sort_values(["release_fy", "prio"], kind="stable").drop_duplicates(keys + ["release_fy"], keep="first")
    latest = df.groupby(keys, dropna=False).tail(1).set_index(keys)
    unr = df[~df.rounded].groupby(keys, dropna=False).tail(1).set_index(keys)
    j = latest.join(unr[["value", "release_fy"]].rename(columns={"value": "u_value", "release_fy": "u_rel"}),
                    how="left")
    use_unr = j.rounded & j.u_value.notna() & j.value.notna() & ((j.value - j.u_value).abs() <= ROUND_TOL)
    pick = pd.concat([latest[~use_unr.values].reset_index(),
                      unr.loc[j.index[use_unr.values]].reset_index()], ignore_index=True)
    return pick


def disagreements(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Cells where two releases differ by more than rounding."""
    d = df[df.value.notna()]
    g = d.groupby(keys, dropna=False)
    m = d.assign(n=g.value.transform("size"), lo=g.value.transform("min"), hi=g.value.transform("max"))
    m = m[(m.n > 1) & ((m.hi - m.lo) > 0)]
    if m.empty:
        return m
    out = (m.groupby(keys, dropna=False)
           .apply(lambda x: pd.Series({"releases": " ".join(f"{int(r)}:{v:g}" for r, v in zip(x.release_fy, x.value)),
                                       "max_abs_diff": x.value.max() - x.value.min(),
                                       "beyond_rounding": (x.value.max() - x.value.min()) > ROUND_TOL
                                       or not x.rounded.any()}), include_groups=False)
           .reset_index())
    return out


# ---------------------------------------------------------------- build
def _members(p: Path):
    """(member name, bytes) of a workbook ('' for the file itself) or of every file in a zip."""
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            return [(n, z.read(n)) for n in z.namelist() if not n.endswith("/")]
    return [("", p.read_bytes())]


WHY = [  # (pattern on the upper-case title or file name, why a table is not used)
    (r"ORPHAN", "orphan adoptions by state; not used"),
    (r"CBSA|CORE.BASED|METROPOLITAN|MSA", "metro areas (CBSA/MSA), not states"),
    (r"COUNTRY OF (?:CITIZENSHIP|RESIDENCE|LAST RESIDENCE|NATIONALITY|CHARGEABILITY)|PORT OF ENTRY|MODE OF TRAVEL",
     "national, by country or port; no state"),
    (r"SELECTED COUNTRY|LEADING COUNTRY|COUNTRY OF FORMER ALLEGIANCE|SELECTED COUNTRY OR BIRTH",
     "state x selected countries of birth; the state totals are in the state table"),
    (r"REFUGEE|ASYL", "refugees / asylees by nationality; no state (the INS-era state table is used)"),
    (r"APPREHEN|REMOV|RETURN|DEPORT|INADMISSIB|PROSECUT|ENFORCEMENT|EXPEL|EXCLU|SEIZ|DETAIN|BORDER|LOCATED|"
     r"ALIENS (?:EXPELLED|REMOVED)", "enforcement; no state"),
    (r"AGE|SEX|GENDER|MARITAL|OCCUPATION|DEMOGRAPHIC", "national demographics; no state"),
    (r"PETITION|APPLICATION|NUMERICAL LIMIT|CERTIFICATE|DERIVATIVE|MILITARY|CROSSING|BORDER|NATURALIZATION "
     r"PROVISION|PROVISION", "national; no state"),
]


USE = {"lpr_state": "green cards by state (preferred over the PDF of the same release)",
       "natz_state": "naturalizations by state (preferred over the PDF)",
       "refasy_state": "refugee/asylee green cards by state (preferred over the PDF)",
       "ni_state": "I-94 admissions by state and class group (preferred over the PDF)",
       "ni_state_611": "I-94 admissions by state x every class of admission, FY2002 (H-1B, F-1, J-1, L-1, O-1, TN)",
       "ni_state_detail": "I-94 admissions by state x every class of admission (H-1B, F-1, J-1, L-1, O-1, TN)",
       "lpr_class_us": "national green cards by class (preferred over the PDF)",
       "ni_class_us": "national I-94 admissions by class (preferred over the PDF)",
       "lpr_cob_us": "national green cards by broad class x country of birth (preferred over the PDF)",
       "lpr_state_cob": "all-countries row only: state green-card totals, cross-checked against Table 4",
       "natz_state_cob": "all-countries row only: state naturalization totals, cross-checked against Table 22"}


def why_not(title: str, member: str, container: str = "") -> str:
    t = title.upper()
    if re.search(r"(?:^|/)ENF|_enf_|enforcement", container, re.I):
        return "enforcement; no state"
    if re.search(r"(?:^|/)RFA|_rfa_|refugees|asylees", container, re.I) and "STATE" not in t:
        return "refugees / asylees by nationality; no state"
    if member.lower().endswith(".pdf"):
        return "chapter PDF of the 1996 yearbook (the full 1996 PDF is parsed)"
    if "TABLE OF CONTENTS" in t or re.search(r"toc\.xls", member, re.I):
        return "table of contents"
    for pat, why in WHY:
        if re.search(pat, t):
            return why
    return "national table not used (no state dimension, or the national series is taken from another table)"


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    GRID.mkdir(parents=True, exist_ok=True)
    files, rows, issues, inv = [], [], [], []
    for p in sorted(SRC.iterdir()):
        if p.name.startswith(".") or p.suffix.lower() != ".pdf":
            continue
        rec = {"file": p.name, "md5": md5(p), "bytes": p.stat().st_size, "format": "pdf"}
        fy, npages, found = pdf_info(p)
        rec.update(fiscal_year=fy, pages_or_sheets=npages)
        used = []
        for (kind, num), info in sorted(found.items(), key=lambda kv: kv[0][1]):
            recs, iss = read_pdf_table(p, fy, kind, num, info["pages"])
            issues += iss
            if not recs:
                issues.append(f"{fy} table {num} ({kind}): no rows parsed")
                continue
            g = pd.DataFrame(recs)
            g.to_csv(GRID / f"{fy}_table{num:02d}.csv", index=False)
            title = re.sub(r"\s*-\s*CONTINUED.*$", "", info["title"])
            meta = {"rounded": False, "release_fy": fy, "source_file": p.name, "table": f"Table {num}",
                    "table_title": title, "fmt": "pdf"}
            rows += [dict(r, kind=kind) for r in tidy(kind, recs, meta)]
            used.append(f"T{num} {kind} (pp. {info['pages'][0] + 1}-{info['pages'][-1] + 1})")
        rec.update(tables_used="; ".join(used), used=bool(used),
                   why_not_used="" if used else "no state or wanted national table found")
        files.append(rec)

    # Excel: the OHSS workbooks next to the PDFs and everything in excel/ (workbooks and the yearbooks' zips)
    seen = {}
    conts = [p for p in sorted(SRC.iterdir()) if p.suffix.lower() in (".xlsx", ".xls")]
    conts += [p for p in sorted((SRC / "excel").iterdir()) if p.suffix.lower() in (".xlsx", ".xls", ".zip")]
    for p in conts:
        rel = p.name if p.parent == SRC else f"excel/{p.name}"
        books = []
        for member, data in _members(p):
            h = hashlib.md5(data).hexdigest()
            base = {"container": rel, "member": member, "md5": h, "bytes": len(data)}
            if not member.lower().endswith((".xls", ".xlsx")) and member:
                inv.append({**base, "used": False, "why_not_used": why_not("", member)})
                continue
            if h in seen:
                inv.append({**base, "used": False, "duplicate_of": seen[h],
                            "why_not_used": "identical copy of another file (the supplemental zips repeat the "
                                            "supplemental tables of the main zips)"})
                continue
            seen[h] = f"{rel}::{member}" if member else rel
            try:
                sheets = load_book(data)
            except Exception as e:
                inv.append({**base, "used": False, "why_not_used": f"unreadable: {type(e).__name__}: {e} (the file "
                                                                    "in the zip is truncated)"})
                issues.append(f"{rel}::{member}: unreadable ({e})")
                continue
            books.append((member, h, sheets))
        ys = []
        for _, _, sheets in books:
            for d in sheets.values():
                ys += [int(y) for y in re.findall(r"FISCAL YEARS? (?:\d{4} ?(?:TO|-) ?)?(\d{4})",
                                                  norm(sheet_head(d)).upper())]
        fy = max(ys) if ys else None
        used = []
        for member, h, sheets in books:
            src = f"{rel}::{member}" if member else rel
            parsed = {}
            if "Dictionary" not in p.name:
                for kind, sheet, title, rounded, recs in excel_tables(sheets):
                    num, _ = head_title(sheet_head(sheets[sheet]))
                    tab = num if (num and (re.match(r"(?i)sheet|temp|table \d|^\d|cob", sheet) or member)) else sheet
                    meta = {"rounded": rounded, "release_fy": fy, "source_file": src, "table": tab,
                            "table_title": title, "fmt": "excel"}
                    rows += [dict(r, kind=kind) for r in tidy(kind, recs, meta)]
                    parsed[sheet] = kind
                    used.append(f"{tab} {kind}")
            for sheet, d in sheets.items():
                head = sheet_head(d)
                if not head.strip():
                    continue
                num, title = head_title(head)
                k = parsed.get(sheet)
                inv.append({"container": rel, "member": member, "sheet": sheet, "md5": h, "bytes": None,
                            "fiscal_year": fy, "table": num, "title": title[:300], "kind": k or "",
                            "used": bool(k),
                            "use": USE.get(k, "") if k else "",
                            "why_not_used": "" if k else ("data dictionary; reference only" if "Dictionary" in p.name
                                                          else why_not(title, member, rel))})
        why = "" if used else next((v for k, v in {
            "refugee": "refugee arrivals by nationality only; no state table",
            "asylee": "asylum grants by nationality only; no state table",
            "rfa": "refugees / asylees by nationality only; no state table",
            "enf": "enforcement actions by nationality / agency region; no state table",
            "Dictionary": "data dictionary (definitions, code lists); reference only"}.items()
            if k.lower() in p.name.lower()), "no wanted table")
        files.append({"file": rel, "md5": md5(p), "bytes": p.stat().st_size, "format": p.suffix.lower().strip("."),
                      "fiscal_year": fy, "pages_or_sheets": sum(len(s) for _, _, s in books),
                      "tables_used": "; ".join(dict.fromkeys(used)), "used": bool(used), "why_not_used": why})

    fl = pd.DataFrame(files)
    top = ~fl.file.str.startswith("excel/")
    fl["kind_key"] = fl.format + "_" + fl.file.str.extract(
        r"(lawful_permanent|naturalization|nonimmigrant|refugee|asylee|enforcement|8-11newadj|Dictionary)",
        expand=False).fillna("yearbook")
    dup = (top & fl[top].duplicated(["kind_key", "fiscal_year"], keep=False).reindex(fl.index, fill_value=False)) \
        | fl.duplicated("md5", keep=False)
    fl["duplicate"] = dup
    if dup.any():
        print("possible duplicate releases:\n", fl[dup][["file", "fiscal_year"]].to_string(index=False))
    fl = fl.drop(columns="kind_key")
    fl.to_csv(OUT / "files.csv", index=False)
    ex = pd.DataFrame(inv)
    ex["bytes"] = ex.groupby("md5").bytes.transform("first")
    ex.to_csv(OUT / "excel_files.csv", index=False)

    allr = pd.DataFrame(rows)
    allr["prio"] = (allr.kind == "ni_state_611").astype(int)
    # FY2005-06 Excel releases print all admissions (Table 25) and I-94 only (Table 26): keep I-94 only, as the PDFs
    t94 = allr.kind.eq("ni_class_us") & allr.table_title.str.contains("I-94 ONLY", regex=False)
    rel94 = set(zip(allr[t94].release_fy, allr[t94].fmt))
    allr = allr[~(allr.kind.eq("ni_class_us") & ~t94 & pd.Series(list(zip(allr.release_fy, allr.fmt)),
                                                                   index=allr.index).isin(rel94))]
    # prefer Excel (exact cells): a PDF table is superseded where the same release has the Excel table of its kind;
    # the PDF values are kept for the comparison in checks.csv and in dhs_releases.csv
    # (by release, kind and LPR type, so the new-arrival / adjustment workbooks do not supersede the Table 10 total)
    grp = pd.Series(list(zip(allr.release_fy, allr.kind, allr["type"].fillna(""))), index=allr.index)
    over = allr.fmt.eq("pdf") & grp.isin(set(grp[allr.fmt == "excel"]))
    allr["superseded_by_excel"] = over
    pdf_over, used_r = allr[over], allr[~over]
    st_kinds = ["lpr_state", "natz_state", "refasy_state", "ni_state", "ni_state_611", "ni_state_detail"]
    skeys = ["fiscal_year", "state", "measure", "class"]
    ukeys = ["fiscal_year", "measure", "breakdown", "type", "class", "country", "geo_level"]
    sdrop = ["breakdown", "type", "country", "geo_level"]
    cob = used_r[used_r.kind.isin(COB_KINDS)].drop(columns=sdrop, errors="ignore")
    rel_state = used_r[used_r.kind.isin(st_kinds)].drop(columns=sdrop, errors="ignore")
    rel_us = used_r[~used_r.kind.isin(st_kinds) & ~used_r.kind.isin(COB_KINDS)].drop(columns=["state"],
                                                                                       errors="ignore")
    # identical tables in two workbooks of one release (e.g. NatzSupTable1 and NatzSupTable1D): keep the first
    rel_state = rel_state.drop_duplicates(skeys + ["release_fy", "kind"], keep="first")
    rel_us = rel_us.drop_duplicates(ukeys + ["release_fy", "kind"], keep="first")
    cob = cob.drop_duplicates(skeys + ["release_fy", "kind"], keep="first")
    pd.concat([rel_state.assign(level="state"), rel_us.assign(level="us"), cob.assign(level="state_supp_check"),
               pdf_over.assign(level=pdf_over.kind.isin(st_kinds).map({True: "state", False: "us"}))]).to_csv(
        OUT / "dhs_releases.csv", index=False)

    scols = skeys + ["value", "note", "rounded", "release_fy", "source_file", "table", "table_title"]
    st = choose(rel_state, skeys)[scols].sort_values(skeys)
    st["fiscal_year"] = st.fiscal_year.astype(int)
    st.to_csv(OUT / "dhs_state.csv", index=False)
    ucols = ukeys + ["value", "note", "rounded", "release_fy", "source_file", "table", "table_title"]
    us = choose(rel_us, ukeys)[ucols].sort_values(ukeys)
    us.to_csv(OUT / "dhs_us.csv", index=False)

    w = st[st[["measure", "class"]].apply(tuple, axis=1).isin(WIDE)].copy()
    w["col"] = w[["measure", "class"]].apply(tuple, axis=1).map(WIDE)
    wide = w.pivot_table(index=["fiscal_year", "state"], columns="col", values="value", aggfunc="first")
    wide = wide[[c for c in WIDE.values() if c in wide]].reset_index()
    wide.to_csv(OUT / "dhs_state_wide.csv", index=False)

    cov = st.groupby(["measure", "class", "fiscal_year"]).agg(
        states=("state", lambda s: s.isin(STATES51).sum()),
        territories=("state", lambda s: " ".join(sorted(set(s) & set(TERR_CODES)))),
        us=("state", lambda s: "US" in set(s)),
        releases=("release_fy", lambda s: " ".join(str(int(x)) for x in sorted(set(s)))),
        files=("source_file", lambda s: " ".join(sorted(set(s))))).reset_index()
    cov.to_csv(OUT / "coverage.csv", index=False)

    checks(rel_state, rel_us, st, us, issues, skeys, ukeys, pdf_over, used_r, cob, st_kinds)
    print(fl[["file", "fiscal_year", "used", "tables_used"]].to_string(index=False, max_colwidth=90))
    print(cov.groupby(["measure", "class"]).agg(years=("fiscal_year", lambda s: f"{s.min()}-{s.max()} ({len(s)})"),
                                                 min_states=("states", "min")).to_string())
    return st, us


# ---------------------------------------------------------------- sanity checks
def checks(rel_state, rel_us, st, us, issues, skeys, ukeys, pdf_over, used_r, cob, st_kinds):
    ck = []

    def add(check, ok, detail="", **k):
        ck.append({"check": check, **k, "ok": bool(ok), "detail": detail})

    for msg in issues:
        add("pdf_parse_issue", False, msg)
    # 1. every release: sum of all non-US rows (states, territories, other, unknown) vs the table's US total
    for (fy, m, c, rel, tab), g in rel_state.groupby(["fiscal_year", "measure", "class", "release_fy", "table"]):
        tot = g[g.state == "US"].value.sum(min_count=1)
        if pd.isna(tot):
            continue
        s = g[g.state != "US"].value.sum()
        n51 = g.state.isin(STATES51).sum()
        rounded = g.rounded.any()
        nd = g.note.str.startswith("D").sum()
        tol = 10 * len(g) if rounded else 0
        ok = abs(s - tot) <= tol or (nd > 0 and s <= tot)
        add("state_sum_vs_us", ok, f"sum {s:,.0f} vs total {tot:,.0f}; {n51} of 51 states"
            + (f"; {nd} cells suppressed (D)" if nd else "") + ("; cells rounded to 10" if rounded else ""),
            fiscal_year=fy, measure=m, cls=c, release_fy=rel, table=tab, diff=s - tot)
        add("states_present", n51 == 51, f"{n51} of 51", fiscal_year=fy, measure=m, cls=c, release_fy=rel,
            table=tab)
    # 2. class sums vs total in the nonimmigrant state tables (every state row)
    ni = rel_state[rel_state.kind == "ni_state"]
    for (fy, rel, tab), g in ni.groupby(["fiscal_year", "release_fy", "table"]):
        p = g.pivot_table(index="state", columns="class", values="value", aggfunc="first")
        if "total" not in p:
            continue
        parts = p.drop(columns="total").sum(axis=1)
        dstates = set(g[g.note.str.startswith("D")].state)
        off = (parts - p.total).abs() > (10 * p.shape[1] if g.rounded.any() else 0)
        bad = off & ~(p.index.isin(dstates) & (parts <= p.total))
        add("ni_classes_sum_to_total", not bad.any(), f"{bad.sum()} of {len(p)} rows off (excl. {off.sum() - bad.sum()}"
            f" rows short only by suppressed D cells); worst {(parts - p.total)[bad].abs().max() if bad.any() else 0:,.0f}"
            + (" " + " ".join(p.index[bad][:10]) if bad.any() else ""), fiscal_year=fy, release_fy=rel, table=tab)
    # 3. Supplemental Table 3 (class x state) vs Table 30/31 totals by state
    det = rel_state[rel_state.kind == "ni_state_detail"]
    for fy, g in det[det.state != "US"].groupby("fiscal_year"):
        s = g.groupby("state").value.sum()
        t = st[(st.fiscal_year == fy) & (st.measure == "i94_admissions") & (st["class"] == "total")].set_index(
            "state").value
        d = (s - t).dropna()
        add("supp3_vs_table30_by_state", (d.abs() <= 10 * g["class"].nunique()).all(),
            f"max abs diff {d.abs().max():,.0f} over {len(d)} states (rounded cells)", fiscal_year=fy)
    # 4. cross-release disagreements
    for name, rel, keys in (("state", rel_state, skeys), ("us", rel_us, ukeys)):
        dis = disagreements(rel, keys)
        if len(dis):
            dis = dis[dis.beyond_rounding]
        summ = (dis.groupby(["measure", "fiscal_year"]).agg(cells=("max_abs_diff", "size"),
                                                           worst=("max_abs_diff", "max")).reset_index()
                if len(dis) else pd.DataFrame())
        add(f"cross_release_{name}", len(dis) == 0, f"{len(dis)} cells differ beyond rounding across releases")
        for _, r in summ.iterrows():
            ex = dis[(dis.measure == r.measure) & (dis.fiscal_year == r.fiscal_year)].sort_values(
                "max_abs_diff", ascending=False).iloc[0]
            who = ex.get("state", ex.get("country", ""))
            add(f"cross_release_{name}_detail", False, f"{r.cells} cells; worst {who} {ex['class']}: {ex.releases}",
                fiscal_year=r.fiscal_year, measure=r.measure, diff=r.worst)
    # 5. within one release: state-table US totals vs national tables; Table 10 world totals vs Table 6
    def us_rel(measure, cls, country="Total", typ="total", title=None):
        x = rel_us[(rel_us.measure == measure) & (rel_us["class"] == cls) & (rel_us["type"] == typ)
                   & (rel_us.country == country)]
        if title:
            x = x[x.table_title.str.contains(title)]
        return x.groupby(["fiscal_year", "release_fy"]).value.first()
    pairs = [(rel_state[(rel_state.measure == "lpr") & (rel_state["class"] == "total") & (rel_state.state == "US")]
              .groupby(["fiscal_year", "release_fy"]).value.first(), us_rel("lpr", "total", title="MAJOR CLASS"),
              "lpr_table4_vs_table6")]
    pairs.append((rel_state[(rel_state.measure == "i94_admissions") & (rel_state["class"] == "total")
                            & (rel_state.state == "US")].groupby(["fiscal_year", "release_fy"]).value.first(),
                  us_rel("i94_admissions", "total_i94"), "i94_table30_vs_table25"))
    t6 = {"employment": "employment_total", "total": "total", "family": "family_total",
          "immediate_relatives": "immediate_relatives", "diversity": "diversity"}
    for c10, c6 in t6.items():
        pairs.append((us_rel("lpr", c10, title="COUNTRY OF BIRTH"), us_rel("lpr", c6, title="MAJOR CLASS"),
                      f"table10_vs_table6_{c10}"))
    for a, b, name in pairs:
        for k in sorted(set(a.index) & set(b.index)):
            add(name, abs(a[k] - b[k]) <= 10, f"{a[k]:,.0f} vs {b[k]:,.0f}", fiscal_year=k[0], release_fy=k[1],
                diff=a[k] - b[k])
    # 6. year-over-year jumps in state LPR / naturalized series (flag only)
    for m in ("lpr", "naturalized"):
        x = st[(st.measure == m) & (st["class"] == "total") & st.state.isin(STATES51)].pivot_table(
            index="state", columns="fiscal_year", values="value")
        r = x.div(x.shift(axis=1)).stack()
        big = r[(r > 3) | (r < 1 / 3)]
        add(f"yoy_jumps_{m}", True, f"{len(big)} state-years change >3x (info): " +
            ", ".join(f"{s} {y}" for s, y in big.index[:25]))
    # 7. Excel vs PDF, same release and table kind: every cell
    cmp_all = []
    for kinds, keys in ((st_kinds, skeys), (None, ukeys)):
        sel = (lambda d: d[d.kind.isin(kinds)]) if kinds else (lambda d: d[~d.kind.isin(st_kinds + list(COB_KINDS))])
        p_ = sel(pdf_over).drop_duplicates(keys + ["release_fy", "kind"])
        x_ = sel(used_r[used_r.fmt == "excel"]).drop_duplicates(keys + ["release_fy", "kind"])
        gk = lambda d: pd.Series(list(zip(d.release_fy, d.kind, d["type"].fillna(""))), index=d.index)
        x_ = x_[gk(x_).isin(set(gk(p_)))]
        m = p_[keys + ["release_fy", "kind", "value", "table", "note"]].merge(
            x_[keys + ["release_fy", "kind", "value", "table", "note", "source_file"]], on=keys + ["release_fy", "kind"],
            how="outer", suffixes=("_pdf", "_excel"), indicator=True)
        cmp_all.append(m)
    cmp = pd.concat(cmp_all, ignore_index=True)
    cmp["diff"] = cmp.value_excel - cmp.value_pdf
    cmp["status"] = cmp._merge.map({"both": "both", "left_only": "pdf_only", "right_only": "excel_only"}).astype(str)
    cmp.loc[(cmp.status == "both") & ((cmp["diff"].abs() > 0) | (cmp.value_pdf.isna() != cmp.value_excel.isna())),
            "status"] = "differ"
    cmp = cmp.drop(columns="_merge")
    cmp[cmp.status != "both"].to_csv(OUT / "excel_vs_pdf.csv", index=False)
    for (rel, kind), g in cmp.groupby(["release_fy", "kind"]):
        n = g.status.value_counts()
        add("excel_vs_pdf", n.get("differ", 0) == 0,
            f"{n.get('both', 0)} cells equal, {n.get('differ', 0)} differ, {n.get('pdf_only', 0)} only in the PDF, "
            f"{n.get('excel_only', 0)} only in Excel; worst {g['diff'].abs().max():,.0f}" if g["diff"].notna().any()
            else f"{n.get('both', 0)} cells equal; {n.get('pdf_only', 0)} PDF-only, {n.get('excel_only', 0)} Excel-only",
            release_fy=rel, table=kind, diff=g["diff"].abs().max())
    for _, r in cmp[cmp.status == "differ"].iterrows():
        who = r.get("state") if isinstance(r.get("state"), str) else r.get("country")
        typ = r.get("type") if isinstance(r.get("type"), str) else ""
        add("excel_vs_pdf_detail", False, f"{r.kind} {who} {r['class']} ({typ}): "
            f"PDF {r.value_pdf} vs Excel {r.value_excel}", fiscal_year=r.fiscal_year, measure=r.measure,
            cls=r["class"], release_fy=r.release_fy, table=r.table_excel, diff=r["diff"])
    # 8. supplemental state x country-of-birth tables: all-countries row vs the state tables (same release)
    for m_, g in cob.groupby(["measure", "fiscal_year", "release_fy"]):
        t = rel_state[(rel_state.measure == m_[0]) & (rel_state["class"] == "total") & (rel_state.fiscal_year == m_[1])
                      & (rel_state.release_fy == m_[2])].set_index("state").value
        if t.empty:
            t = st[(st.measure == m_[0]) & (st["class"] == "total") & (st.fiscal_year == m_[1])].set_index("state").value
        d = (g.set_index("state").value - t).dropna()
        d51 = d[d.index.isin(STATES51 | {"US"})]
        add(f"supp_cob_vs_state_table_{m_[0]}", (d51.abs() == 0).all(),
            f"{(d51 == 0).sum()} of {len(d51)} states + US equal; worst {d51.abs().idxmax() if len(d51) else ''} "
            f"{d51.abs().max() if len(d51) else 0:,.0f}" + (f"; {len(g)} rows in supp" if len(d51) < 52 else ""),
            fiscal_year=m_[1], measure=m_[0], release_fy=m_[2], diff=d51.abs().max() if len(d51) else None)
    # 9. FY2002 Table 611 vs Table 30 (classes in both) and 611 national sums
    t611 = rel_state[rel_state.kind == "ni_state_611"]
    t30 = rel_state[(rel_state.kind == "ni_state") & (rel_state.fiscal_year == 2002)]
    pairs611 = {"total_611_excl_crew_er_vwp_refusals": "total", "j1": "j1", "l1": "l1", "tn": "tn",
                "grp_" + slug("Students"): "f1_m1"}
    for a_, b_ in pairs611.items():
        x = t611[t611["class"] == a_].set_index("state").value
        y = t30[t30["class"] == b_].set_index("state").value
        d = (x - y).dropna()
        if len(d):   # Table 611's totals exclude different classes from Table 30's "All classes": info only
            add("table611_vs_table30_fy2002", b_ == "total" or (d.abs() <= 5).all(), f"{a_} vs {b_}: {(d == 0).sum()} "
                f"of {len(d)} rows equal; worst {d.abs().idxmax()} {d.abs().max():,.0f}"
                + (" (the two totals exclude different classes; info)" if b_ == "total" else ""), fiscal_year=2002,
                cls=b_)
    # 10. detailed state x class tables: their U.S. total per class vs the national class table, same release
    for kind in ("ni_state_detail", "ni_state_611"):
        g = rel_state[(rel_state.kind == kind) & (rel_state.state == "US")]
        if kind == "ni_state_611":
            g = rel_state[(rel_state.kind == kind) & (rel_state.state != "US")].groupby(
                ["fiscal_year", "release_fy", "class"], as_index=False).value.sum()
        nat = rel_us[(rel_us.kind == "ni_class_us")].set_index(["fiscal_year", "release_fy", "class"]).value
        nat = nat[~nat.index.duplicated()]
        if kind == "ni_state_611":   # no FY2002 national table in the 2002 release: use the chosen national value
            nat = us[us.breakdown == "class"].assign(release_fy=2002).set_index(
                ["fiscal_year", "release_fy", "class"]).value
            nat = nat[~nat.index.duplicated()]
        for c in ("h1b", "f1", "j1", "l1", "o1", "tn"):
            for _, r in g[g["class"] == c].iterrows():
                k = (r.fiscal_year, r.release_fy, c)
                if k in nat.index:
                    tol = 10 if kind == "ni_state_detail" and r.fiscal_year >= 2023 else 0
                    add(f"{kind}_us_vs_national_table", abs(r.value - nat[k]) <= tol,
                        f"{c}: state table U.S. {r.value:,.0f} vs national class table {nat[k]:,.0f}",
                        fiscal_year=r.fiscal_year, release_fy=r.release_fy, cls=c, diff=r.value - nat[k])
    ck = pd.DataFrame(ck)
    ck.to_csv(OUT / "checks.csv", index=False)
    bad = ck[~ck.ok]
    print(f"checks: {len(ck)} rows, {len(bad)} not ok")
    print(bad.check.value_counts().to_string())


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    build()
