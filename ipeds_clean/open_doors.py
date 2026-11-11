"""IIE Open Doors state fact sheets: international students hosted and U.S. students abroad, by state.

    python -m ipeds_clean.open_doors      # -> data/open_doors/*.csv and a printed check report

Source: the Institute of International Education (IIE) Open Doors "State Fact Sheets" / "State Facts and Figures"
PDFs in sources/iie_open_doors/, one page per state (50 states, DC, Puerto Rico, U.S. Virgin Islands; 2025 adds the
Northern Mariana Islands). Seven editions are here:

  Open-Doors-2020-US-State-Fact-Sheets.pdf       Open Doors 2020  international students 2019/20
  OpenDoors2021_State-Sheet.pdf                  Open Doors 2021  2020/21
  Open-Doors-2022_State-Sheets.pdf               Open Doors 2022  2021/22
  Open-Doors-2023-State-Sheets.pdf               Open Doors 2023  2022/23
  OD24_Fact-Sheets_States.pdf                    Open Doors 2024  2023/24
  OpenDoors_FactSheet_All-States_-2025-1.pdf     Open Doors 2025  2024/25
  OD26_State-Sheets_All-States.pdf               Open Doors 2026  2025/26

The 2026 file was received pre-release (named "..._EMBARGO.pdf"); the embargo lifted (confirmed 2026-11-11) and
the file was renamed. It is used like the other editions.

The edition is read from the page title ("2021 FACT SHEET", "State Facts and Figures 2023"). The academic year of
the international-student counts is printed on 2023+ sheets ("INTERNATIONAL STUDENTS, 2022/23"); 2020-2022
sheets do not print it, and Open Doors convention (edition N reports year N-1/N) is used. That is confirmed by the
NAFSA Economic Value reports, whose state enrollments for the same academic year equal these exactly (checks.csv).
Study abroad years: printed on 2020 and 2022+ sheets (2020 shows 2017/18 and 2018/19, 2022 shows 2019/20 and
2020/21; 2023+ show one, two years before the edition). The 2021 sheet's year labels are two overprinted text layers ("22001178//1189"); its two
columns are taken to be 2018/19 and 2019/20 (edition - 3 and - 2, the 2022 rule), which the 2019/20 value repeated
in the 2022 sheet confirms (and the 2018/19 value repeated from the 2020 sheet).

2020 layout: the 2021/2022 one-column layout with small differences (institution list titled "INSTITUTIONS WITH
THE HIGHEST NUMBER ...", a Rank column before the place of origin, footnotes between the headline and the lists,
Department of State programs Fulbright and Gilman only, Gilman for 2019/20 as printed). Its 53 pages sum to
1,075,496 students, Open Doors 2020's national total.

What is extracted (measure, category):
  intl_students             total international students hosted in the state (Open Doors census of institutions;
                            includes students on OPT)
  intl_students_pct_change  % change from the previous year (whole percent on 2026 sheets)
  intl_students_rank        rank among the states, DC and territories
  intl_expenditure_usd      "Estimated International Student Expenditure" (NAFSA economic analysis, US$)
  origin_share_pct          leading places of origin, category = place, rank 1-5, % of the state's students
                            (whole percent on 2026 sheets). Counts are not printed, only shares;
                            origin_count_est = share x total is added and flagged as derived.
  institution_intl_students leading host institutions (top 5), category = institution; 2021-22 also give the city
  leading_major_intl        2026 only: the single leading major of international students (category; value empty)
  study_abroad              U.S. students from the state's institutions studying abroad for credit (academic_year is
                            the year abroad, not the edition year)
  study_abroad_pct_change, study_abroad_rank      2023+
  study_abroad_dest_share_pct   2023+: leading destinations, % of the state's study-abroad students
  study_abroad_institution      2023+: leading institutions sending students abroad (count)
  leading_major_study_abroad    2023+: leading major of study-abroad students (category)
  fulbright_us, gilman_us, cls_us, fulbright_intl  U.S. Department of State program participants (2020-2026;
                            no cls_us in 2020)
Jobs supported are not on these sheets (NAFSA reports them: ipeds_clean.nafsa). Fields of study beyond the single
"leading major" are not on the sheets.

Also used: "Fall 2025 International Student Enrollment Snapshot Economic Impact Overview FINAL.pdf" (NAFSA / JB
International, Nov 2025, built on IIE's Fall 2025 Snapshot): national only, to open_doors_us.csv (total
students, dollars contributed and jobs for 2023/24-2025/26, and the chart's dollar series 2020/21-2025/26).
Inventoried, not used: Fall_2026_International_Student_Economic_Snapshot_NAFSA_JBI.pdf (NAFSA / JB International,
Aug 2026, "Fall 2026 International Student Enrollment Outlook"): national projections only, no state numbers
(2024/25 actual, 2025/26 projection 1,168,602, 2026/27 "mid" 1,104,912 and "upper" 1,056,884 scenarios, from
IIE's Spring 2026 Snapshot survey). Superseded for 2025/26 by the Open Doors 2026 sheets.
Not used: In_the_Moment_and_Over_Time.pdf and its " (1)" copy are an unrelated research paper (a social-media pilot
study) filed in this folder by mistake; the two copies differ (the "(1)" copy is a marked-up revision).

Outputs (data/open_doors/):
  open_doors_state.csv       edition, academic_year, year (fall), state, measure, category, rank, value, city,
                             note, source_file, page
  open_doors_state_wide.csv  one row per state x academic_year: international students, change, rank,
                             expenditure, study abroad (same academic year, latest edition reporting it)
  open_doors_us.csv          national series from the Fall 2025 snapshot
  files.csv                  every file in the folder: md5, pages, edition, used, why, notes
  checks.csv                 origin shares sum <= 100, state sum vs national total (snapshot), cross-edition
                             % change vs. counts, study abroad repeated across editions, vs NAFSA enrollments
  pdf_tables/                every table pdfplumber finds, one CSV per page (raw grid), for audit

Verification (checks.csv): all 51 (+ territories) pages found in every edition; the printed % change equals the
change computed from the previous edition's count within rounding for every state 2020/21-2025/26; study abroad
2018/19 (2020 and 2021 sheets) and 2019/20 (2021 and 2022 sheets) are identical across editions; the sum of all
pages equals Open Doors' national total for 2019/20 (1,075,496) and the Fall 2025 snapshot's exactly for 2023/24
(1,126,690) and 2024/25 (1,177,766) (2025/26 pages sum to 1,146,008; the snapshot's 1,168,520 was a projection);
enrollments equal NAFSA's for every state 2019/20-2024/25 except Mississippi 2024/25 (3,445 here vs 3,444); and
expenditure equals NAFSA's rounded dollars except Michigan 2021/22 ($965,457,224 here vs NAFSA's $695.5M, a NAFSA
transposition) and North and South Dakota 2019/20 ($46,446,418 and $39,147,263 here; NAFSA prints $46.5M and
$39.2M, rounded up). The 2020 Delaware and Montana sheets list only four places of origin (as printed).

Caveats
* Draft text: the 2025 and 2026 sheets carry a leftover Tableau note ("Update years, make sure all rankings are
  correct ...") in the page margin; it is not part of the data and is ignored. The 2022 sheets' footnote says the
  expenditure is based on Open Doors 2021, but the values equal NAFSA's 2021-22 analysis.
* Open Doors counts students at accredited U.S. higher-education institutions over the academic year (fall
  census plus OPT); SEVIS (ipeds_clean.sevis) counts active records on a date at all levels. They do not match.
* "state" is where the institution is. Territories are kept as PR, VI, MP; Open Doors prints no U.S. total on the
  sheets (the sum of the pages is checked against the national total from the snapshot and NAFSA).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import pdfplumber

from .gss import NAMES

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "iie_open_doors"
OUT = ROOT / "data" / "open_doors"
TABLES = OUT / "pdf_tables"

TERR = {"Puerto Rico": "PR", "US Virgin Islands": "VI", "U.S. Virgin Islands": "VI", "Virgin Islands": "VI",
        "Northern Mariana Islands": "MP", "Guam": "GU"}
CODE = {**{v.lower(): k for k, v in NAMES.items()}, **{k.lower(): v for k, v in TERR.items()}}
NAME_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, CODE), key=len, reverse=True)) + r")\b", re.I)
SNAPSHOT = "Fall 2025 International Student Enrollment Snapshot Economic Impact Overview FINAL.pdf"
OUTLOOK = "Fall_2026_International_Student_Economic_Snapshot_NAFSA_JBI.pdf"     # national projections only
UNRELATED = {"In_the_Moment_and_Over_Time.pdf", "In_the_Moment_and_Over_Time (1).pdf"}
NUM = re.compile(r"^[-+]?\$?\d[\d,]*(\.\d+)?$")
SPLIT = 315          # x: left column (headline numbers) | right column (lists) on 2023+ sheets
VALX = 480           # x: list values start right of this


# ---------------------------------------------------------------- shared helpers (also used by nafsa, sevis_reports)
def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def num(s: str | None) -> float | None:
    """'1,234' '$6,002,408,439' '-13.0' '37.5A.' '8cb' '1,292#' -> float; None for N/A or text."""
    if s is None:
        return None
    s = re.sub(r"\D+$", "", s.strip())     # trailing junk glyphs: 'A.', 'cb', '#', '.'
    if not NUM.match(s):
        return None
    return float(s.replace("$", "").replace(",", ""))


def dump_tables(pdf: pdfplumber.PDF, stem: str, out: Path, pages=None) -> int:
    """Write every pdfplumber table on each page to out/<stem>_p<page>.csv (raw grid, table and row index)."""
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for i, pg in enumerate(pdf.pages, 1):
        if pages is not None and i not in pages:
            continue
        rows = []
        for t, tb in enumerate(pg.extract_tables()):
            for r, row in enumerate(tb):
                rows.append({"table": t, "row": r, **{f"c{j}": c for j, c in enumerate(row)}})
        if rows:
            pd.DataFrame(rows).to_csv(out / f"{stem}_p{i:03d}.csv", index=False)
            n += 1
    return n


def rows_of(words, tol=4.0):
    """Cluster words into visual rows by top coordinate."""
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(w["top"] - out[-1][0]["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in out]


def text(ws) -> str:
    return " ".join(w["text"] for w in ws)


# ---------------------------------------------------------------- page parsing
def find(words, *tokens, after=-1.0, xmax=1e9, xmin=-1.0):
    """Top of the first row (below `after`) whose words start with the given token sequence."""
    for r in rows_of([w for w in words if xmin <= w["x0"] < xmax], tol=2):
        if r[0]["top"] <= after:
            continue
        t = [w["text"] for w in r]
        for k in range(len(t) - len(tokens) + 1):
            if all(t[k + j].upper().startswith(tok.upper()) for j, tok in enumerate(tokens)):
                return r[0]["top"]
    return None


def next_row(words, top):
    """Top of the first visual row below `top`."""
    return min(w["top"] for w in words if w["top"] > top + 3)


def pairs(words, top, bottom, xmin, xname_max, xval_min, city_x=None):
    """Name/value list in a box: name lines left of xname_max, numeric values right of xval_min, paired by
    nearest top; wrapped name lines that land on the same value are joined."""
    box = [w for w in words if top < w["top"] < bottom and w["x0"] >= xmin]
    vals = [(w["top"], num(w["text"])) for w in box if w["x0"] >= xval_min and num(w["text"]) is not None]
    names = [r for r in rows_of([w for w in box if w["x0"] < xname_max], tol=2.5)]
    if not vals:
        return []
    got = {}
    for r in names:
        t = r[0]["top"]
        j = min(range(len(vals)), key=lambda k: abs(vals[k][0] - t))
        if abs(vals[j][0] - t) > 12:
            continue
        name = [w for w in r if city_x is None or w["x0"] < city_x]
        city = [w for w in r if city_x is not None and w["x0"] >= city_x]
        g = got.setdefault(j, {"name": [], "city": []})
        g["name"] += name
        g["city"] += city
    out = []
    for j in sorted(got):
        nm = re.sub(r"\s+", " ", text(got[j]["name"])).strip()
        if nm:
            out.append((nm, text(got[j]["city"]) or None, vals[j][1]))
    return out


def state_of(words) -> str | None:
    head = text([w for w in words if w["top"] < 80 and w["x0"] < 300])
    m = [x.group(1) for x in NAME_RE.finditer(head)]
    return CODE[m[-1].lower()] if m else None


def parse_old(words, edition):
    """2020-2022 layout: one column, headline row of four numbers. 2020 differs in small ways: the institution
    list is titled "INSTITUTIONS WITH THE HIGHEST NUMBER ...", the origin list has a Rank column left of the
    place name, the footnotes sit between the headline and the origin list, and Department of State programs are
    Fulbright and Gilman only (no Critical Language Scholarship)."""
    rec, lists = {}, {}
    t_or = find(words, "LEADING", "PLACES")
    t_inst = find(words, "INSTITUTIONS", "HOSTING") or find(words, "INSTITUTIONS", "WITH", "THE", "HIGHEST")
    t_ab = find(words, "U.S.", "STUDENTS", "STUDYING")
    t_dos = find(words, "STUDENTS", "PARTICIPATING")
    head = [w for w in words if 80 < w["top"] < t_or and num(w["text"]) is not None]
    head = next((r for r in rows_of(head, tol=5) if len(r) == 4), [])     # first row of four numbers
    if len(head) == 4:
        rec = dict(zip(["intl_students", "intl_students_pct_change", "intl_students_rank", "intl_expenditure_usd"],
                       [num(w["text"]) for w in head]))
    t_ph = find(words, "Place", "of", "Origin")
    lists["origin_share_pct"] = [(re.sub(r"^\d+\s+", "", nm), c, v)            # 2020: drop the Rank column
                                 for nm, c, v in pairs(words, t_ph + 5, t_inst - 2, 0, 400, 500)]
    t_ih = find(words, "Institution", "City")
    city_x = next(w["x0"] for w in words if abs(w["top"] - t_ih) < 3 and w["text"] == "City")
    lists["institution_intl_students"] = pairs(words, t_ih + 5, t_ab - 2, 0, 500, 500, city_x=city_x - 2)
    ab = sorted([w for w in words if t_ab < w["top"] < t_dos and w["x0"] > 400 and num(w["text"]) is not None
                 and not re.search(r"\d/\d", w["text"])], key=lambda w: w["x0"])
    yrs = [f"{edition - 3}/{str(edition - 2)[2:]}", f"{edition - 2}/{str(edition - 1)[2:]}"]
    printed = re.findall(r"(20\d\d)/(\d\d)\b", text([w for w in words if t_ab < w["top"] < t_dos]))
    if printed and len(printed) == 2:
        assert [f"{a}/{b}" for a, b in printed] == yrs, (printed, yrs)
    abroad = [(y, num(w["text"]), "#" if w["text"].endswith("#") else None) for y, w in zip(yrs, ab)]
    return rec, lists, abroad, dos(words, t_dos)


def dos(words, t_dos):
    """U.S. Department of State programs: Fulbright / Gilman / Critical Language Scholarship participants."""
    if t_dos is None:
        return {}
    rs = rows_of([w for w in words if w["top"] > t_dos], tol=3)
    out = {}
    for r in rs:
        t = text(r)
        nums = [num(w["text"]) for w in r if num(w["text"]) is not None and w["x0"] > 300]
        if t.startswith("U.S. students from") and len(nums) == 3:
            out.update(fulbright_us=nums[0], gilman_us=nums[1], cls_us=nums[2])
        elif t.startswith("U.S. students from") and len(nums) == 2:       # 2020: Fulbright, Gilman
            out.update(fulbright_us=nums[0], gilman_us=nums[1])
        elif t.startswith("International students at") and nums:
            out["fulbright_intl"] = nums[0]
        elif t.startswith("*Rankings"):
            break
    if "fulbright_intl" not in out:            # 2021/2022: the value sits on its own row below the label
        lab = [r for r in rs if text(r).startswith("International students at")]
        if lab:
            nxt = [w for w in words if lab[0][0]["top"] < w["top"] < lab[0][0]["top"] + 20 and w["x0"] > 300
                   and num(w["text"]) is not None]
            if nxt:
                out["fulbright_intl"] = num(nxt[0]["text"])
    return out


def parse_new(words, edition):
    """2023-2026 layout: headline numbers on the left, ranked lists on the right."""
    left = [w for w in words if w["x0"] < SPLIT]
    t_is = find(words, "INTERNATIONAL", "STUDENTS,")
    t_ab = find(words, "U.S.", "STUDENTS", "STUDYING")
    t_dos = find(words, "U.S.", "DEPARTMENT", "OF", "STATE")
    ay = re.search(r"(20\d\d)/(\d\d)", text([w for w in words if abs(w["top"] - t_is) < 3])).group(0)
    ab_ay = re.search(r"(20\d\d)/(\d\d)", text([w for w in words if abs(w["top"] - t_ab) < 3])).group(0)

    def headline(top, bottom):
        rs = [r for r in rows_of([w for w in left if top + 3 < w["top"] < bottom], tol=5)
              if any(num(w["text"]) is not None or w["text"] == "N/A" for w in r)]
        return rs

    def val(w):
        return None if w["text"] == "N/A" else num(w["text"])

    rec, notes = {}, {}
    rs = headline(t_is, t_ab)
    if rs:
        a = [w for w in rs[0] if val(w) is not None or w["text"] == "N/A"]
        rec["intl_students"] = val(a[0])
        rec["intl_students_rank"] = val(a[1]) if len(a) > 1 else None
    for r in rs[1:]:
        dollar = [w for w in r if w["text"].startswith("$")]
        if dollar:
            pre = [w for w in r if w["x0"] < dollar[0]["x0"] and (val(w) is not None or w["text"] == "N/A")]
            rec["intl_students_pct_change"] = val(pre[0]) if pre else None
            rec["intl_expenditure_usd"] = val(dollar[0])
            major = [w for w in r if w["x0"] > dollar[0]["x1"]]
            if major:
                notes["leading_major_intl"] = text(major)
            break
    rs = headline(t_ab, t_dos)
    if rs:
        a = [w for w in rs[0] if val(w) is not None or w["text"] == "N/A"]
        rec["study_abroad"] = val(a[0])
        rec["study_abroad_rank"] = val(a[1]) if len(a) > 1 else None
    if len(rs) > 1:
        r = rs[1]
        a = [w for w in r if val(w) is not None or w["text"] == "N/A"]
        rec["study_abroad_pct_change"] = val(a[0]) if a else None
        major = [w for w in r if val(w) is None and w["text"] != "N/A"]
        if major:
            notes["leading_major_study_abroad"] = text(major)

    right = [w for w in words if w["x0"] >= SPLIT]
    # each list has a column-header row right below its title; its wording varies ("Institution Total",
    # "CENSUS Institution Instit..", "Place of Origin #"), so the row after the title is taken
    t_ph = next_row(right, find(right, "LEADING", "PLACES"))
    t_li = find(right, "LEADING", "INSTITUTIONS")
    t_ih = next_row(right, t_li)
    t_dh = next_row(right, find(right, "LEADING", "DESTINATIONS"))
    t_li2 = find(right, "LEADING", "INSTITUTIONS", after=t_dh)
    t_ih2 = next_row(right, t_li2)
    lists = {"origin_share_pct": pairs(right, t_ph + 5, t_li - 2, SPLIT, VALX, VALX),
             "institution_intl_students": pairs(right, t_ih + 5, t_ab - 4, SPLIT, VALX + 30, VALX + 30),
             "study_abroad_dest_share_pct": pairs(right, t_dh + 5, t_li2 - 2, SPLIT, VALX, VALX),
             "study_abroad_institution": pairs(right, t_ih2 + 5, t_dos - 2, SPLIT, VALX + 30, VALX + 30)}
    return ay, ab_ay, rec, notes, lists, dos(words, t_dos)


def fy(ay: str) -> int:
    return int(ay[:4])


def parse_file(path: Path):
    rows, pages = [], 0
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, TABLES)
        for i, pg in enumerate(pdf.pages, 1):
            pg = pg.dedupe_chars()
            words = pg.extract_words()
            first = text([w for w in words if w["top"] < 60])
            m = re.search(r"(20\d\d)\s*FACT SHEET|Figures\s*(20\d\d)", first)
            if not m:
                continue
            edition = int(m.group(1) or m.group(2))
            st = state_of(words)
            pages += 1
            base = dict(edition=edition, state=st, source_file=path.name, page=i)

            def add(ay, measure, value, category=None, rank=None, city=None, note=None):
                rows.append({**base, "academic_year": ay, "year": fy(ay), "measure": measure,
                             "category": category, "rank": rank, "value": value, "city": city, "note": note})

            if edition <= 2022:
                rec, lists, abroad, dosv = parse_old(words, edition)
                ay = f"{edition - 1}/{str(edition)[2:]}"
                for y, v, flag in abroad:
                    add(y, "study_abroad", v, note="'#' mark on the sheet, no footnote printed (likely COVID-19)" if flag else None)
                notes = {}
            else:
                ay, ab_ay, rec, notes, lists, dosv = parse_new(words, edition)
                for k in ("study_abroad", "study_abroad_rank", "study_abroad_pct_change"):
                    if k in rec:
                        add(ab_ay, k, rec.pop(k))
                for k, (meas, ayk) in {"leading_major_study_abroad": ("leading_major_study_abroad", ab_ay),
                                       "leading_major_intl": ("leading_major_intl", ay)}.items():
                    if k in notes:
                        add(ayk, meas, None, category=notes[k])
            for k, v in rec.items():
                add(ay, k, v)
            for meas, items in lists.items():
                lay = ab_ay if meas.startswith("study_abroad") and edition > 2022 else ay
                for rk, (name, city, v) in enumerate(items, 1):
                    add(lay, meas, v, category=name, rank=rk, city=city)
                    if meas == "origin_share_pct" and rec.get("intl_students"):
                        add(lay, "origin_count_est", round(v / 100 * rec["intl_students"]), category=name, rank=rk,
                            note="derived: printed share x total students (not printed on the sheet)")
            for k, v in dosv.items():
                add(ay, k, v, note="U.S. Department of State program year as printed on the sheet")
    return rows, pages


def snapshot(path: Path):
    """National series from the NAFSA/JB International Fall 2025 snapshot overview."""
    out = []
    with pdfplumber.open(path) as pdf:
        dump_tables(pdf, path.stem, TABLES)
        p1 = pdf.pages[0].extract_words()
        xl = [(w["x0"] + w["x1"]) / 2 for w in p1 if re.fullmatch(r"20\d\d-\d\d", w["text"])]
        labels = [w["text"] for w in p1 if re.fullmatch(r"20\d\d-\d\d", w["text"])]
        for w in p1:
            if re.fullmatch(r"\$\d{1,3}(,\d{3}){3}", w["text"]) and w["x0"] > 120:
                c = (w["x0"] + w["x1"]) / 2
                j = min(range(len(xl)), key=lambda k: abs(xl[k] - c))
                out.append(dict(academic_year=labels[j].replace("-", "/"), measure="econ_contribution_usd",
                                value=num(w["text"]), note="chart label, assigned to the nearest year axis label",
                                source_file=path.name, page=1))
        t2 = pdf.pages[1].extract_text()
        for m in re.finditer(r"(20\d\d)[–-](20\d\d) (Actuals|Snapshot Enrollment\*) ([\d,]+) \$([\d.]+)B ([\d,]+)", t2):
            ay = f"{m.group(1)}/{m.group(2)[2:]}"
            note = "actual" if m.group(3) == "Actuals" else "projection from IIE Fall 2025 Snapshot (7% decline)"
            out += [dict(academic_year=ay, measure="intl_students_incl_opt", value=num(m.group(4)), note=note),
                    dict(academic_year=ay, measure="econ_contribution_usd", value=float(m.group(5)) * 1e9,
                         note=note + "; rounded to $0.1B; excludes students on OPT"),
                    dict(academic_year=ay, measure="jobs_supported", value=num(m.group(6)),
                         note=note + "; excludes students on OPT")]
            for r in out[-3:]:
                r.update(source_file=path.name, page=2)
    d = pd.DataFrame(out)
    d["state"] = "US"
    d["year"] = d.academic_year.str[:4].astype(int)
    return d


# ---------------------------------------------------------------- build
def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, files = [], []
    us = None
    for p in sorted(SRC.glob("*.pdf")):
        f = dict(file=p.name, md5=md5(p), pages=None, edition=None, used="no", why="", note="")
        with pdfplumber.open(p) as pdf:
            f["pages"] = len(pdf.pages)
        if p.name in UNRELATED:
            f["why"] = ("unrelated document: research paper 'In the Moment and Over Time' (social-media pilot study), "
                        "not IIE data")
            if "(1)" in p.name:
                f["note"] = "DIFFERS from In_the_Moment_and_Over_Time.pdf (marked-up revision)"
        elif p.name == OUTLOOK:
            f["why"] = ("national projections only, no state numbers (2025/26 projection and 2026/27 scenarios); "
                        "inventoried, not parsed")
            f["note"] = "NAFSA/JB International Fall 2026 outlook (Aug 2026), built on IIE's Spring 2026 Snapshot"
        elif p.name == SNAPSHOT:
            us = snapshot(p)
            f.update(used="yes", why="national series only (no state detail) -> open_doors_us.csv",
                     note="NAFSA/JB International projections built on the IIE Fall 2025 Snapshot")
        else:
            r, n = parse_file(p)
            rows += r
            f.update(used="yes", why=f"{n} state pages parsed", edition=r[0]["edition"] if r else None)
        files.append(f)
    long = pd.DataFrame(rows)
    cols = ["edition", "academic_year", "year", "state", "measure", "category", "rank", "value", "city", "note",
            "source_file", "page"]
    long = long[cols].sort_values(["state", "academic_year", "edition", "measure", "rank"], na_position="first")
    long.to_csv(OUT / "open_doors_state.csv", index=False)

    head = ["intl_students", "intl_students_pct_change", "intl_students_rank", "intl_expenditure_usd",
            "study_abroad", "study_abroad_pct_change", "study_abroad_rank"]
    h = long[long.measure.isin(head)].sort_values("edition")
    h = h.drop_duplicates(["academic_year", "state", "measure"], keep="last")     # latest edition wins
    wide = h.pivot_table(index=["academic_year", "year", "state"], columns="measure", values="value",
                         aggfunc="first").reindex(columns=head).reset_index()
    ed = h[h.measure == "intl_students"].set_index(["academic_year", "state"]).edition
    wide["edition"] = [ed.get((a, s)) for a, s in zip(wide.academic_year, wide.state)]
    lm = long[long.measure == "leading_major_intl"].set_index(["academic_year", "state"]).category
    wide["leading_major_intl"] = [lm.get((a, s)) for a, s in zip(wide.academic_year, wide.state)]
    top = long[(long.measure == "origin_share_pct") & (long["rank"] == 1)].set_index(["academic_year", "state"])
    wide["top_origin"] = [top.category.get((a, s)) for a, s in zip(wide.academic_year, wide.state)]
    wide["top_origin_share_pct"] = [top.value.get((a, s)) for a, s in zip(wide.academic_year, wide.state)]
    wide.to_csv(OUT / "open_doors_state_wide.csv", index=False)
    if us is not None:
        us[["academic_year", "year", "state", "measure", "value", "note", "source_file", "page"]] \
            .to_csv(OUT / "open_doors_us.csv", index=False)
    fl = pd.DataFrame(files)
    fl.to_csv(OUT / "files.csv", index=False)
    checks(long, wide, us)


def checks(long, wide, us):
    out = []
    st51 = set(NAMES)
    # 1. pages: every edition has 50 states + DC, each once
    for (e, src), g in long.groupby(["edition", "source_file"]):
        s = set(g.state.dropna())
        out.append(dict(check="states_covered", edition=e, source=src, value=len(s & st51),
                        detail="missing: " + " ".join(sorted(st51 - s)) + "; territories: " +
                        " ".join(sorted(s - st51)), flag="" if st51 <= s else "MISSING STATES"))
        if g.state.isna().any():
            out.append(dict(check="unidentified_pages", edition=e, source=src, value=g[g.state.isna()].page.nunique(),
                            flag="UNMATCHED"))
    # 2. headline completeness
    for m in ["intl_students", "intl_students_pct_change", "intl_students_rank", "intl_expenditure_usd"]:
        for ay, g in wide[wide.intl_students.notna()].groupby("academic_year"):
            n = g[g.state.isin(st51)][m].notna().sum()
            out.append(dict(check="headline_present", academic_year=ay, measure=m, value=n,
                            flag="" if n == 51 else "incomplete"))
    # 3. origin shares: five, descending, sum <= 100
    o = long[long.measure == "origin_share_pct"]
    for (e, s), g in o.groupby(["edition", "state"]):
        v = g.sort_values("rank").value.tolist()
        ties = len(v) > 5 and v[4] == v[-1]                 # sheets list every place tied for 5th
        bad = (len(v) != 5 and not ties) or sum(v) > 100.5 or any(a < b for a, b in zip(v, v[1:]))
        if bad:
            out.append(dict(check="origin_list", edition=e, state=s, value=sum(v), detail=str(v), flag="odd"))
    out.append(dict(check="origin_list_summary", value=o.groupby(["edition", "state"]).ngroups,
                    detail="state-editions with a 5-item (more when tied for 5th), descending, <=100% origin list unless flagged"))
    # 4. institutions: top institution <= state total
    ins = long[(long.measure == "institution_intl_students") & (long["rank"] == 1)]
    j = ins.merge(long[long.measure == "intl_students"][["edition", "state", "value"]], on=["edition", "state"],
                  suffixes=("", "_tot"))
    for r in j[j.value > j.value_tot].itertuples():
        out.append(dict(check="top_institution_le_total", edition=r.edition, state=r.state, value=r.value,
                        detail=f"total {r.value_tot}", flag="top institution exceeds state total"))
    n_inst = long[long.measure == "institution_intl_students"].groupby(["edition", "state"]).size()
    out.append(dict(check="institutions_listed", value=int((n_inst == 5).sum()),
                    detail=f"state-editions with 5 institutions; fewer: "
                           f"{', '.join(f'{e}:{s}={n}' for (e, s), n in n_inst[n_inst != 5].items())}"))
    # 5. printed % change vs computed from consecutive editions
    w = wide.set_index(["year", "state"])
    for (y, s), r in w.iterrows():
        prev = w.intl_students.get((y - 1, s))
        if pd.notna(prev) and pd.notna(r.intl_students_pct_change):
            calc = 100 * (r.intl_students / prev - 1)
            d = calc - r.intl_students_pct_change
            tol = 0.6 if r.edition == 2026 else 0.15
            out.append(dict(check="pct_change_vs_prior_edition", academic_year=r.academic_year, state=s,
                            value=r.intl_students_pct_change, computed=round(calc, 2), diff=round(d, 2),
                            flag="" if abs(d) <= tol else "differs (prior year revised?)"))
    # 6. study abroad reported for the same year by two editions
    sa = long[long.measure == "study_abroad"]
    for (ay, s), g in sa.groupby(["academic_year", "state"]):
        if g.edition.nunique() > 1:
            v = g.value.tolist()
            out.append(dict(check="study_abroad_cross_edition", academic_year=ay, state=s, value=v[-1],
                            detail=" vs ".join(f"{e}:{x:g}" for e, x in zip(g.edition, v)),
                            flag="" if len(set(v)) == 1 else "differs"))
    # 7. sum of state pages vs national totals (snapshot / NAFSA)
    if us is not None:
        nat = us[us.measure == "intl_students_incl_opt"].set_index("academic_year").value
        for ay, g in wide.groupby("academic_year"):
            s51 = g[g.state.isin(st51)].intl_students.sum()
            sall = g.intl_students.sum()
            if ay in nat:
                out.append(dict(check="state_sum_vs_us_total", academic_year=ay, value=sall, computed=nat[ay],
                                detail=f"51 only {s51:,.0f}; source: Fall 2025 snapshot",
                                diff=round(100 * (sall / nat[ay] - 1), 3)))
    # 8. vs NAFSA economic value reports (same enrollment basis)
    nafsa = ROOT / "data" / "nafsa" / "nafsa_state_wide.csv"
    if nafsa.exists():
        n = pd.read_csv(nafsa)
        n = n.assign(academic_year=n.academic_year.str.replace("-", "/"))
        j = wide[wide.intl_students.notna()].merge(n, on=["academic_year", "state"], suffixes=("", "_nafsa"))
        for ay, g in j.groupby("academic_year"):
            a = (g.intl_students == g.intl_students_nafsa)
            e = (g.intl_expenditure_usd - g.econ_contribution_usd).abs() <= g.econ_contribution_rounding * 1.001
            out.append(dict(check="vs_nafsa_students", academic_year=ay, value=int(a.sum()), computed=len(g),
                            detail="states where Open Doors count == NAFSA count; differ: " +
                                   ", ".join(f"{r.state} {r.intl_students:g}/{r.intl_students_nafsa:g}"
                                             for r in g[~a].itertuples()),
                            flag="" if a.all() else "differs"))
            out.append(dict(check="vs_nafsa_dollars", academic_year=ay, value=int(e.sum()), computed=len(g),
                            detail="Open Doors expenditure within NAFSA's printed rounding; differ: " +
                                   ", ".join(f"{r.state} {r.intl_expenditure_usd:,.0f}/{r.econ_contribution_usd:,.0f}"
                                             for r in g[~e].itertuples()),
                            flag="" if e.all() else "differs"))
    ck = pd.DataFrame(out)
    ck.to_csv(OUT / "checks.csv", index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 140)
    print(ck[ck.flag.fillna("") != ""].to_string() if (ck.flag.fillna("") != "").any() else "no flagged checks")
    print(ck[ck.check.isin(["state_sum_vs_us_total", "vs_nafsa_students", "vs_nafsa_dollars",
                            "institutions_listed", "origin_list_summary"])].to_string())
    print(wide[wide.state.isin(["CA", "TX"])].to_string())


if __name__ == "__main__":
    build()
