"""NSF/NCSES Survey of Federal Funds for Research and Development (FFS): federal R&D and R&D plant obligations by state.

    python -m ipeds_clean.ffs            # -> data/ffs/*.csv and a printed sanity-check report

Source: the FFS published data-table zips in sources/nsf_ffs/, one per volume (tab07323 = FY2004 actuals ...
nsf26316 = FY2024 actuals). Zips are read in place. Each volume reports actual obligations for its first fiscal
year and preliminary national figures for one or two later years; the state tables are for the actual year only.
A volume's year is the most common year among its single-year "by state" table titles. Tables are found by
title, not by number (numbering changes between volumes).

What is used
* Own-year state tables (single fiscal year, $ thousands):
  - "... for research and development and for R&D plant ..., by state or location / and other locations: FY"
    -> rd_plant_oblig/all, rd_oblig/all, plant_oblig/all
  - "... research and (experimental) development ..., by state ... and performer" -> rd_oblig/perf_*
  - "... research and (experimental) development, by state ... and (selected) agency" -> rd_oblig/ag_*
  - "... R&D plant ..., by state ... and performer" / "and (selected) agency" -> plant_oblig/perf_*, ag_*
* rd_oblig/all_own_volume, plant_oblig/all_own_volume: the own-year volume's total, which its performer and
  agency breakdowns add up to (rd_oblig/all may be a later revision). rd_oblig/arra, plant_oblig/arra: the
  American Recovery and Reinvestment Act share (FY2009-10 tables split ARRA / non-ARRA).
* Multi-year state trend tables ("... by state or location: FYs 2016-24", $ millions): rd_oblig/all and
  plant_oblig/all for every year shown, FY1985-2024.
Not used: percentage-distribution tables (derivable), state x agency x performer detail, DOD RDT&E by state,
and all national tables (by agency, field, character of work, FFRDC). Reasons are listed per file in files.csv.

Selection ("prefer the latest volume"): rd_oblig/all and plant_oblig/all come from the latest volume that
reports the fiscal year. When that is a later volume's trend table ($ millions) and it agrees with the
own-year table within rounding (0.5 million), the own-year value ($ thousands) is kept and the note says it was
confirmed; when it differs, the later (revised) value is used (x 1000) and the own-year value is in checks.csv.
All other breakdowns exist only in the own-year volume. Every row records release_year (volume year),
source_zip and source_file.

Outputs (data/ffs/):
  ffs_state.csv       fiscal_year, state, measure, category, value (USD thousands), basis, note, release_year,
                      source_zip, source_file, table_title
  ffs_state_wide.csv  one row per state-year, columns <measure>__<category>
  files.csv, coverage.csv, checks.csv

Geography: 50 states + DC as postal codes; "US" is the "All locations" total (it includes outlying areas,
offices abroad and undistributed obligations). Puerto Rico PR, Guam GU, U.S. Virgin Islands VI, American Samoa
AS, Northern Mariana Islands MP; OUTLYING = "Outlying areas" subtotal, OTHER_AREAS = "Other areas", ABROAD =
"Offices abroad", UNDIST = "Undistributed" (obligations not assigned to a state).

Caveats
* Series break at FY2021 (FY2021 volume, nsf24309): through FY2020 the state tables cover "selected agencies"
  (the agencies required to report geography; the FY2011 notes say eleven); from FY2021 they cover all
  agencies reporting (an "Other" agency column appears). Performers were regrouped at the same time: FFRDCs
  (before: industry-, university- and nonprofit-administered FFRDCs as separate extramural columns, summed here
  into perf_ffrdc) are shown under intramural, and intramural federal R&D rose from $49.6B (FY2020) to $71.7B
  (FY2021). The nsf2xxxx trend tables republish FY2013-20 without the "selected agencies" label; the values
  agree with the own-year tables within rounding except where noted.
* FY2009-10 include American Recovery and Reinvestment Act obligations (rd_oblig/arra). The FY2024 volume's
  FY2009 total ($139.0B) is higher than the FY2009 volume's ($131.2B); the revision is kept per "latest
  volume" and the own-year figure is in all_own_volume and checks.csv.
* Obligations are recorded where the performer (prime recipient) is located, not where subawards are spent;
  single large obligations (often DOD contracts) make some state series jumpy (e.g. Alabama FY2017).
* Non-state lines are not comparable across volumes: e.g. the FY2011 volume put $4.5B of undistributed
  obligations under "Other areas", which later volumes moved to "Undistributed".
* FY2004-05 tables flag revised values with "r"; they are used as published. FY2010 plant-by-agency values are
  rounded to $0.1M in the source.
* "Research and development" became "research and experimental development" (FY2019+) without a change in
  scope.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
import zipfile

import pandas as pd

from .herd import NAMES, STATES51, clean, first_sheet, num, state_code, year_of

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "nsf_ffs"
OUT = ROOT / "data" / "ffs"

OTHER = [(r"^(all locations|united states|total)", "US"), (r"^outlying areas", "OUTLYING"),
         (r"^other (areas|outlying)", "OTHER_AREAS"), (r"^offices? abroad|^foreign|^abroad", "ABROAD"),
         (r"^undistribut|^unknown|^other/unknown", "UNDIST"), (r"^american samoa", "AS"),
         (r"^northern mariana", "MP"), (r"^(u\.s\. )?virgin islands", "VI"), (r"^guam", "GU"),
         (r"^puerto rico", "PR"), (r"^trust territor|^marshall|^micronesia|^palau", "OTHER_AREAS")]
TERR = {"PR", "GU", "VI", "AS", "MP"}
AGENCIES = ["dhs", "doc", "dod", "doe", "doi", "dot", "epa", "hhs", "nasa", "nsf", "usda", "si", "ed", "va", "other"]
HEADLINE = [("rd_plant_oblig", "all"), ("rd_oblig", "all"), ("plant_oblig", "all"), ("rd_oblig", "all_own_volume"),
            ("plant_oblig", "all_own_volume"), ("rd_oblig", "arra")] + \
    [("rd_oblig", "perf_" + p) for p in ("intramural", "ffrdc", "business", "higher_ed", "nonprofit", "state_local",
                                         "other")] + \
    [("rd_oblig", "ag_" + a) for a in AGENCIES]


def sources():
    for p in sorted(SRC.glob("*.zip")):
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                if not n.endswith("/"):
                    yield p.name, n, z.read(n)


def title_of(df) -> str:
    parts = []
    for v in df.iloc[:5, 0]:
        s = clean(v)
        if not s or s.startswith("("):
            continue
        parts.append(s)
        if year_of(unflag(s)) or len(parts) == 3:
            break
    return re.sub(r"^(table \S+?)\.?\s+", r"\1. ", " ".join(parts), flags=re.I)[:300]


def unflag(s: str) -> str:
    return re.sub(r"\s*\((corrected|revised)[^)]*\)\s*$", "", s)


def place(s: str) -> str | None:
    c = state_code(s)
    if c:
        return c
    t = s.lower()
    for pat, code in OTHER:
        if re.match(pat, t):
            return code
    return None


def classify(t: str) -> str | None:
    t = t.lower()
    if "by state" not in t:
        return None
    if re.search(r"percentage|department of defense|agency, and performer|selected agency, and performer", t):
        return None
    multi = re.search(r"fys? (19|20)\d\d\s*[–-]\s*\d{2,4}", t)
    plant_only = re.search(r"obligations for r&d plant", t)
    if multi:
        return "trend_plant" if plant_only else "trend_rd"
    if "and for r&d plant" in t:
        return "summary"
    base = "plant" if plant_only else "rd"
    if "performer" in t:
        return base + "_perf"
    if "agency" in t:
        return base + "_agency"
    return None


def perf_cat(h: str) -> str | None:
    if "total" in h and not re.search(r"ffrdc|intramural|extramural", h):
        return "all"
    if "ffrdc" in h:
        return "perf_ffrdc"
    if "intramural" in h or "federal agenc" in h:
        return "perf_intramural"
    if re.search(r"industr|business", h):
        return "perf_business"
    if re.search(r"universit|higher education", h):
        return "perf_higher_ed"
    if "nonprofit" in h:
        return "perf_nonprofit"
    if re.search(r"state.{0,6}local", h):
        return "perf_state_local"
    if re.search(r"foreign|other|u\.s\. territories$", h):
        return "perf_other"
    return None


def agency_cat(h: str) -> str | None:
    h = re.sub(r"non-\s*arra|\barra\b", "", h).strip()
    if re.search(r"\btotal\b", h):
        return "all"
    toks = re.findall(r"[a-z]+", h)
    if not toks:
        return None
    last = toks[-1]
    for a in AGENCIES:
        if last == a or (len(last) == len(a) + 1 and last.startswith(a) and last[-1] in "abcdefg"):
            return "ag_" + a
    return None


def parse(df, kind, year):
    lab = df.map(clean)
    start = next((i for i in range(1, min(len(df), 30)) if place(lab.iat[i, 0]) == "US"), None)
    if start is None:
        return [], []
    millions = any("millions" in lab.iat[i, 0].lower() for i in range(start))
    body = df.iloc[start:]
    data = [j for j in range(1, df.shape[1]) if body.iloc[:, j].map(lambda v: num(v) is not None).mean() >= 0.3]
    hdr_rows = lab.iloc[1:start, data[0]:] if data else None
    filled = hdr_rows.replace("", None).T.ffill().T.fillna("")
    hdr = {j: " ".join(x for x in filled[j] if x).lower() for j in data}
    if kind.startswith("trend"):
        meas = "plant_oblig" if kind == "trend_plant" else "rd_oblig"
        cmap = {}
        for j in data:
            m = re.fullmatch(r"(?:fy\s*)?((?:19|20)\d\d)", hdr[j].strip())
            if m:
                cmap[j] = (int(m.group(1)), meas, "all")
    elif kind == "summary":                               # Total | R&D | R&D plant (FY2009-10: ARRA + non-ARRA)
        groups = defaultdict(list)
        for j in data:
            h = hdr[j]
            c = ("rd_plant_oblig" if h.startswith("total") else "plant_oblig" if "plant" in h else
                 "rd_oblig" if "r&d" in h else None)
            if c:
                groups[(c, "all")].append(j)
                if re.search(r"(?<!non-)\barra\b", h) and "non" not in h:
                    groups[(c, "arra")].append(j)
        return sum_rows(df, lab, start, {k: v for k, v in groups.items()}, year, millions)
    else:
        meas = "plant_oblig" if kind.startswith("plant") else "rd_oblig"
        f = perf_cat if kind.endswith("perf") else agency_cat
        cmap, sums = {}, defaultdict(list)
        for j in data:
            c = f(hdr[j])
            if c:
                sums[c].append(j)
        # category -> list of columns (FFRDCs by operator, ARRA + non-ARRA are summed)
        return sum_rows(df, lab, start, {(meas, c): js for c, js in sums.items()}, year, millions)
    rows, unknown = [], []
    for i in range(start, len(df)):
        s = lab.iat[i, 0]
        if not s:
            continue
        code = place(s)
        if code is None:
            if re.match(r"^(notes?|sources?|[a-z] |\w+ = |\* = )", s, re.I):
                break
            unknown.append(s)
            continue
        for j, (y, m, c) in cmap.items():
            v = num(df.iat[i, j])
            if v is not None:
                rows.append(dict(fiscal_year=y, state=code, measure=m, category=c, value=v * (1000 if millions else 1),
                                 unit_published="millions" if millions else "thousands"))
    return rows, unknown


def sum_rows(df, lab, start, groups, year, millions):
    rows, unknown = [], []
    for i in range(start, len(df)):
        s = lab.iat[i, 0]
        if not s:
            continue
        code = place(s)
        if code is None:
            if re.match(r"^(notes?|sources?|[a-z] |\w+ = |\* = )", s, re.I):
                break
            unknown.append(s)
            continue
        for (m, c), js in groups.items():
            vals = [v for v in (num(df.iat[i, j]) for j in js) if v is not None]
            if vals:
                rows.append(dict(fiscal_year=year, state=code, measure=m, category=c,
                                 value=sum(vals) * (1000 if millions else 1),
                                 unit_published="millions" if millions else "thousands"))
    return rows, unknown


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    files, tables = [], []
    for zp, name, b in sources():
        rec = dict(zip=zp, file=name, md5=hashlib.md5(b).hexdigest(), title_year=None, table_title="", kind="",
                   used="no", why_not_used="")
        files.append(rec)
        low = name.lower()
        if not low.endswith((".xls", ".xlsx")):
            rec["why_not_used"] = ("technical notes (PDF)" if "tech_notes" in low else "PDF of all tables"
                                   if low.endswith(".pdf") else "index of table titles" if low.endswith(".txt")
                                   else "not a data table")
            continue
        df = first_sheet(b)
        if df is None:
            rec["why_not_used"] = "unreadable"
            continue
        t = title_of(df)
        k = classify(t)
        rec.update(table_title=t, title_year=year_of(unflag(t)), kind=k or "")
        if k:
            tables.append((zp, name, t, k, df, rec))
    vol = {}
    for z in {r["zip"] for r in files}:
        ys = [r["title_year"] for r in files if r["zip"] == z and r["kind"] and not r["kind"].startswith("trend")]
        vol[z] = Counter(ys).most_common(1)[0][0]
    for r in files:
        r["release_year"] = vol[r["zip"]]
    rows, unknown = [], Counter()
    for zp, name, t, k, df, rec in tables:
        y = vol[zp]
        if not k.startswith("trend") and rec["title_year"] != y:
            rec["why_not_used"] = f"title year {rec['title_year']} is not the volume year {y}"
            continue
        r, unk = parse(df, k, y)
        unknown.update(unk)
        base = dict(release_year=y, source_zip=zp, source_file=name.split("/")[-1], table_title=t, kind=k)
        rows += [{**base, **x} for x in r]
        rec["used"] = "parsed" if r else "no"
        if not r:
            rec["why_not_used"] = "classified but nothing parsed"
    if unknown:
        print("unmapped row labels:", dict(unknown.most_common(15)))
    df = pd.DataFrame(rows)
    df["unit_published"] = df.unit_published.fillna("thousands")
    df["lag"] = df.release_year - df.fiscal_year
    key = ["fiscal_year", "state", "measure", "category"]
    pri = {"summary": 0, "rd_perf": 1, "rd_agency": 2, "plant_perf": 1, "plant_agency": 2}
    own = df[(df.lag == 0) & ~df.kind.str.startswith("trend")].assign(p=lambda d: d.kind.map(pri)).sort_values(
        "p").drop_duplicates(key).drop(columns="p")
    trend = df[df.kind.str.startswith("trend")]
    latest = trend.sort_values("release_year").drop_duplicates(key, keep="last")
    j = own.merge(latest, on=key, how="outer", suffixes=("", "_l"), indicator=True)
    srccols = ["value", "release_year", "source_zip", "source_file", "table_title", "kind", "unit_published", "lag"]
    later = (j._merge == "both") & (j.release_year_l > j.release_year)
    agree = later & ((j.value_l - j.value).abs() <= 500)
    revised = later & ~agree
    only_l = j._merge == "right_only"
    j["note"] = ""
    j.loc[agree, "note"] = "own-year value; confirmed within rounding by the FY" + j.loc[agree, "release_year_l"].astype(
        int).astype(str) + " volume"
    j.loc[revised, "note"] = ("revised in the FY" + j.loc[revised, "release_year_l"].astype(int).astype(str) +
                              " volume (own-year value " + j.loc[revised, "value"].map("{:,.0f}".format) + ")")
    rev = j.loc[revised, key + ["value", "value_l", "source_zip_l"]].rename(
        columns={"value": "own", "value_l": "latest", "source_zip_l": "latest_volume"})
    for c in srccols:
        j.loc[revised | only_l, c] = j.loc[revised | only_l, c + "_l"]
    j.loc[only_l, "note"] = j.loc[only_l, "lag"].map(lambda l: "from a later volume's trend table" if l > 0
                                                     else "trend table")
    out = j[key + srccols + ["note"]].copy()
    # the own-volume totals as well, so the volume's breakdowns can be compared with the total they add up to
    ownt = own[own.category == "all"].assign(category="all_own_volume",
                                             note="own-year volume total (consistent with its breakdowns)")
    out = pd.concat([out, ownt[key + srccols + ["note"]]], ignore_index=True)
    out["basis"] = out.apply(lambda r: ("all agencies reporting" if r.fiscal_year >= 2021 else "selected agencies"), axis=1)
    out.loc[out.unit_published == "millions", "note"] = (out.loc[out.unit_published == "millions", "note"] +
                                                         "; published in $ millions").str.strip("; ")
    # derived: plant = total - R&D where the summary table is missing a plant column (never), R&D+plant sum check
    out["value"] = out.value.astype(float)
    out = out.sort_values(key)
    cols = ["fiscal_year", "state", "measure", "category", "value", "basis", "note", "release_year", "source_zip",
            "source_file", "table_title"]
    out[cols].to_csv(OUT / "ffs_state.csv", index=False)
    wide = out.pivot_table(index=["fiscal_year", "state"], columns=["measure", "category"], values="value",
                           aggfunc="first")
    order = [c for c in HEADLINE if c in wide.columns] + sorted(c for c in wide.columns if c not in HEADLINE)
    wide = wide[order]
    wide.columns = [f"{m}__{c}" for m, c in wide.columns]
    wide.reset_index().to_csv(OUT / "ffs_state_wide.csv", index=False)

    fl = pd.DataFrame(files)
    fl["base"] = fl.file.str.split("/").str[-1]
    used = set(map(tuple, out[["source_zip", "source_file"]].drop_duplicates().values))
    hit = pd.Series([(z, f) in used for z, f in fl[["zip", "base"]].values], index=fl.index)
    fl.loc[(fl.used == "parsed") & hit, "used"] = "yes"
    fl.loc[(fl.used == "parsed") & ~hit, ["used", "why_not_used"]] = [
        "check only", "trend values superseded by a later volume; parsed for checks.csv"]
    def why(r):
        t = r.table_title.lower()
        return ("percentage distribution (derivable from the dollar tables)" if "percentage" in t else
                "state x agency x performer / DOD RDT&E detail; not kept" if "by state" in t else
                "national table; no state detail")
    m = (fl.used == "no") & (fl.why_not_used == "")
    fl.loc[m, "why_not_used"] = fl[m].apply(why, axis=1)
    fl[["zip", "file", "md5", "title_year", "release_year", "table_title", "kind", "used", "why_not_used"]].to_csv(
        OUT / "files.csv", index=False)

    cov = out.groupby(["measure", "category", "fiscal_year"]).agg(
        n_states=("state", lambda s: s.isin(STATES51).sum()),
        territories=("state", lambda s: " ".join(sorted(set(s) & TERR))),
        us=("state", lambda s: "yes" if (s == "US").any() else "no"),
        volume=("source_zip", lambda s: " ".join(sorted(set(s)))),
        unit_published=("unit_published", lambda s: "/".join(sorted(set(s))))).reset_index()
    cov.to_csv(OUT / "coverage.csv", index=False)
    checks(out, df, pd.DataFrame(rev), fl)


def checks(out, df, rev, fl):
    res = []
    parts = {"US", "OUTLYING", "ABROAD", "UNDIST"}
    for (y, m, c, z, f), g in df.groupby(["fiscal_year", "measure", "category", "source_zip", "source_file"]):
        us = g.loc[g.state == "US", "value"]
        if us.empty or not us.iat[0]:
            continue
        s51 = g[g.state.isin(STATES51)].value.sum()
        oth = g[g.state.isin({"OUTLYING", "ABROAD", "UNDIST"})].value.sum()
        if not g.state.isin(["OUTLYING"]).any():                # older tables list territories without a subtotal
            oth += g[g.state.isin(TERR | {"OTHER_AREAS"})].value.sum()
        res.append(dict(check="state_sum_vs_all_locations", fiscal_year=y, measure=m, category=c, source=f"{z}/{f}",
                        us=us.iat[0], sum_51=s51, sum_all_parts=s51 + oth, share_51_pct=round(100 * s51 / us.iat[0], 2),
                        diff_pct=round(100 * ((s51 + oth) / us.iat[0] - 1), 3)))
    w = out.pivot_table(index=["fiscal_year", "state"], columns=["measure", "category"], values="value", aggfunc="first")
    def comp(name, meas, prefix):
        cols = [c for c in w.columns if c[0] == meas and c[1].startswith(prefix)]
        if (meas, "all_own_volume") not in w or not cols:
            return
        s, t = w[cols].sum(axis=1, min_count=1), w[(meas, "all_own_volume")]
        for (y, st), a, b in zip(w.index, s, t):
            if pd.notna(a) and pd.notna(b) and b:
                res.append(dict(check=name, fiscal_year=y, state=st, measure=meas, category="all", us=b, sum_51=a,
                                diff_pct=round(100 * (a / b - 1), 3)))
    comp("performers_vs_total", "rd_oblig", "perf_")
    comp("agencies_vs_total", "rd_oblig", "ag_")
    comp("plant_performers_vs_total", "plant_oblig", "perf_")
    comp("plant_agencies_vs_total", "plant_oblig", "ag_")
    if ("rd_plant_oblig", "all") in w:
        s = w[("rd_oblig", "all_own_volume")] + w[("plant_oblig", "all_own_volume")]
        for (y, st), a, b in zip(w.index, s, w[("rd_plant_oblig", "all")]):
            if pd.notna(a) and pd.notna(b) and b:
                res.append(dict(check="rd_plus_plant_vs_total", fiscal_year=y, state=st, measure="rd_plant_oblig",
                                category="all", us=b, sum_51=a, diff_pct=round(100 * (a / b - 1), 3)))
    for r in rev.itertuples() if len(rev) else []:
        res.append(dict(check="revised_in_later_volume", fiscal_year=r.fiscal_year, state=r.state, measure=r.measure,
                        category=r.category, source=r.latest_volume, us=r.own, sum_51=r.latest,
                        diff_pct=round(100 * (r.latest / r.own - 1), 3) if r.own else None))
    # volume overlap: every trend value vs the own-year value for the same FY
    pri = {"summary": 0, "rd_perf": 1, "rd_agency": 2, "plant_perf": 1, "plant_agency": 2}
    own = df[(df.lag == 0) & ~df.kind.str.startswith("trend")].assign(p=lambda d: d.kind.map(pri)).sort_values(
        "p").drop_duplicates(["fiscal_year", "state", "measure", "category"]).set_index(
        ["fiscal_year", "state", "measure", "category"]).value
    tr = df[df.kind.str.startswith("trend")]
    for r in tr.itertuples():
        o = own.get((r.fiscal_year, r.state, r.measure, r.category))
        if o is not None and r.release_year != r.fiscal_year and r.state in STATES51 | {"US"}:
            res.append(dict(check="trend_vs_own_year", fiscal_year=r.fiscal_year, state=r.state, measure=r.measure,
                            category=r.category, source=f"{r.source_zip}/{r.source_file}", us=o, sum_51=r.value,
                            diff_pct=round(100 * (r.value / o - 1), 3) if o else None,
                            flag="" if abs(r.value - o) <= 500 else "differs beyond rounding"))
    us = w.xs("US", level="state")
    for mc in [("rd_oblig", "all"), ("plant_oblig", "all")]:
        s = us[mc].dropna()
        for y, v, ch in zip(s.index, s.values, s.pct_change().values * 100):
            res.append(dict(check="us_continuity", fiscal_year=y, state="US", measure=mc[0], category=mc[1], us=v,
                            diff_pct=None if pd.isna(ch) else round(ch, 2),
                            flag="jump" if pd.notna(ch) and abs(ch) > 15 else ""))
    ck = pd.DataFrame(res)
    ck["flag"] = ck.flag.fillna("")
    ck.loc[ck.check.isin(["state_sum_vs_all_locations", "performers_vs_total", "agencies_vs_total",
                          "plant_performers_vs_total", "plant_agencies_vs_total", "rd_plus_plant_vs_total"]) &
           (ck.diff_pct.abs() > 0.5), "flag"] = "> 0.5%"
    ck.to_csv(OUT / "checks.csv", index=False)

    pd.set_option("display.width", 220)
    print(f"files: {len(fl)}, used {(fl.used == 'yes').sum()}, check only {(fl.used == 'check only').sum()}")
    print("volume years:", dict(sorted(fl.groupby("zip").release_year.first().items(), key=lambda x: x[1])))
    for c in ck.check.unique():
        s = ck[ck.check == c]
        if c != "us_continuity":
            print(f"{c}: {len(s)} rows, median {s.diff_pct.median():.3f}%, max |diff| {s.diff_pct.abs().max():.2f}%,"
                  f" flagged {(s.flag != '').sum()}")
    u = out[(out.state == "US") & (out.measure == "rd_oblig") & (out.category == "all")]
    print("US rd_oblig/all ($B):", " ".join(f"{int(y)}:{v / 1e6:.1f}" for y, v in zip(u.fiscal_year, u.value)))
    cov = out[out.state.isin(STATES51)].groupby(["measure", "category"]).fiscal_year.agg(
        lambda s: f"{int(s.min())}-{int(s.max())} ({s.nunique()} yrs)")
    print(cov.to_string())


if __name__ == "__main__":
    build()
