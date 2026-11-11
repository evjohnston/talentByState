"""Parse the DHS "SEVIS by the Numbers" data mapping tool pages into tidy tables.

    python -m ipeds_clean.sevis          # -> data/sevis/*.parquet + a validation report
    python -m ipeds_clean.sevis --check  # -> data/sevis/ipeds_check.csv: SEVIS vs IPEDS nonresident enrollment

Source: Study in the States (DHS/ICE SEVP), "SEVIS Data Mapping Tool Data", one HTML page per month,
saved in sources/dhs_sevis/ as .html (or a browser "save as single file" .mhtml named like the page; when both exist
the .html is used and the copies are compared in files.csv). Two layouts exist:

* All active F-1/M-1 students (no "stem" in the filename): one row per country of citizenship with the
  total, male/female, counts by education level, and one column per state or territory. State and level
  are reported separately, never crossed.
* Active STEM students ("-stem-" in the filename): one row per state x education level x country x sex.

Outputs (data/sevis/):
  all_country.parquet        month, country, continent, region, total, male, female, <level counts>
  all_state_country.parquet  month, state, country, n          (all students; long form of the state columns)
  stem.parquet               month, state, level, country, sex, n
  files.csv                  one row per source file with row counts and internal consistency checks

SEVIS counts are a snapshot of active records in the month named, not an academic-year count, and they
include students at every level (primary school through doctorate, flight and language training).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "dhs_sevis"
OUT = ROOT / "data" / "sevis"

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}
LEVEL = {  # every spelling seen across vintages -> one code
    "associate": "associate", "bachelors": "bachelors", "bachelor's": "bachelors", "doctorate": "doctorate",
    "flight school": "flight", "flight training": "flight", "flight_school": "flight",
    "high school": "high_school", "high_school": "high_school", "language training": "language",
    "language_training": "language", "masters": "masters", "master's": "masters", "other": "other",
    "other vocational school": "vocational", "other_vocational_school": "vocational",
    "primary": "primary", "secondary": "secondary"}
LEVELS = ["associate", "bachelors", "masters", "doctorate", "high_school", "secondary", "primary",
          "language", "flight", "vocational", "other"]
SEX = {"MALE": "MALE", "FEMALE": "FEMALE"}
ALIAS = {  # renames and long forms used in some months -> the name DHS uses in most months
    "REPUBLIC OF KOREA (SOUTH KOREA)": "SOUTH KOREA", "DEMOCRATIC PEOPLE'S REPUBLIC OF KOREA (NORTH KOREA)": "NORTH KOREA",
    "DEMOCRATIC REPUBLIC OF THE CONGO": "CONGO (KINSHASA)", "REPUBLIC OF THE CONGO": "CONGO (BRAZZAVILLE)",
    "BAHAMA, THE": "BAHAMAS, THE", "TIMOR": "TIMOR-LESTE",
    "REPUBLIC HF THE CONGO": "CONGO (BRAZZAVILLE)", "DEMOCRATHC REPUBLIC OF THE CONGO": "CONGO (KINSHASA)"}
STATE_RE = re.compile(r"[A-Z]{2}")
ROW_RE = re.compile(r"<tr.*?</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def _cells(row: str) -> list[str]:
    return [html.unescape(TAG_RE.sub("", c)).replace("﻿", "").strip() for c in CELL_RE.findall(row)]


def _num(x: str) -> int:
    x = x.replace(",", "").strip()
    return int(float(x)) if x not in ("", "-") else 0


def _month(name: str) -> pd.Timestamp:
    m = re.match(r"([a-z]+)-(\d{4})", name)
    return pd.Timestamp(int(m.group(2)), MONTHS[m.group(1)], 1)


def _page(path: Path) -> str:
    """Page HTML. A browser "Save as single file" (.mhtml) is decoded to its HTML part."""
    if path.suffix == ".mhtml":
        import email
        from email import policy
        msg = email.message_from_binary_file(path.open("rb"), policy=policy.default)
        return next((p.get_content() for p in msg.walk() if p.get_content_type() == "text/html"), "")
    return path.read_text(encoding="utf-8", errors="replace")


def _table_rows(path: Path) -> list[list[str]]:
    tables = re.findall(r"<table.*?</table>", _page(path), re.S)   # saved pages can carry layout tables too
    return [_cells(r) for r in ROW_RE.findall(max(tables, key=len))] if tables else []


def parse_all(path: Path, rows: list[list[str]]):
    head = rows[0]
    key = [h.lower() for h in head]
    idx = {k: i for i, k in enumerate(key)}
    states = [(i, h) for i, h in enumerate(head) if STATE_RE.fullmatch(h)]
    lv = [(i, LEVEL[k]) for i, k in enumerate(key) if k in LEVEL]
    tot = next(i for i, k in enumerate(key) if "active" in k)
    month = _month(path.name)
    wide, long = [], []
    for r in rows[1:]:
        if len(r) != len(head) or not r[0] or "total" in r[0].lower():
            continue
        c = r[0].upper()
        rec = {"month": month, "country": c, "continent": r[idx["continent"]], "region": r[idx["region"]],
               "total": _num(r[tot]), "male": _num(r[idx["male"]]), "female": _num(r[idx["female"]])}
        for i, code in lv:
            rec[code] = rec.get(code, 0) + _num(r[i])
        wide.append(rec)
        long += [(month, st, c, _num(r[i])) for i, st in states if _num(r[i])]
    w = pd.DataFrame(wide)
    for code in LEVELS:
        if code not in w:
            w[code] = 0
    l = pd.DataFrame(long, columns=["month", "state", "country", "n"])
    chk = {"file": path.name, "kind": "all", "month": month, "rows": len(w), "total": int(w.total.sum()),
           "state_sum": int(l.n.sum()), "level_sum": int(w[LEVELS].sum().sum()), "sex_sum": int((w.male + w.female).sum())}
    return w, l, chk


def parse_stem(path: Path, rows: list[list[str]]):
    head = [h.lower() for h in rows[0]]
    ab = next(i for i, h in enumerate(head) if h.startswith("abbr"))
    lvl = next(i for i, h in enumerate(head) if "level" in h)
    coc = next(i for i, h in enumerate(head) if h in ("coc", "country of citizenship"))
    sex = next(i for i, h in enumerate(head) if h in ("sex", "gender"))
    n = len(head) - 1
    month = _month(path.name)
    out = []
    for r in rows[1:]:
        while len(r) > len(head) and r[-1] == "":
            r = r[:-1]
        if len(r) != len(head) or not r[ab]:
            continue
        c, sx = r[coc].upper(), r[sex].upper()
        if "-" in sx and sx.rsplit("-", 1)[1] in ("MALE", "FEMALE"):   # Aug 2018: "GUINEA" | "BISSAU-FEMALE"
            pre, sx = sx.rsplit("-", 1)
            c = f"{c}-{pre}"
        out.append((month, r[ab].upper(), LEVEL.get(r[lvl].lower(), r[lvl].lower()), c, SEX.get(sx, "UNKNOWN"), _num(r[n])))
    d = pd.DataFrame(out, columns=["month", "state", "level", "country", "sex", "n"])
    chk = {"file": path.name, "kind": "stem", "month": month, "rows": len(d), "total": int(d.n.sum()),
           "state_sum": int(d.n.sum()), "level_sum": int(d.n.sum()), "sex_sum": int(d.n.sum())}
    return d, chk


def canonical_countries(series) -> dict:
    """Raw name -> canonical name. Collapse whitespace, apply ALIAS, then map rare spellings (scanning errors such
    as "AHD" for "AND", or missing spaces) to the closest name that appears in at least a third of the months."""
    import difflib
    names = pd.concat([pd.Series(s.unique()) for s in series]).value_counts()   # months each raw name appears in
    clean = {r: ALIAS.get(re.sub(r"\s+", " ", r).strip(), re.sub(r"\s+", " ", r).strip()) for r in names.index}
    months = pd.Series({c: names[[r for r in names.index if clean[r] == c]].sum() for c in set(clean.values())})
    common = sorted(months[months >= months.max() / 3].index)
    key = lambda x: re.sub(r"[^A-Z]", "", x)
    keys = {key(c): c for c in common}
    out = {}
    for r, c in clean.items():
        if c in common:
            out[r] = c
            continue
        hit = difflib.get_close_matches(key(c), list(keys), n=1, cutoff=0.86)
        out[r] = keys[hit[0]] if hit else c
    return out


def sources() -> dict[str, list[Path]]:
    """Page name -> saved copies, .html first. A .mhtml copy (browser "save as single file") is named like the
    .html page it duplicates, e.g. july-2018-sevis-data-mapping-tool-data.mhtml."""
    out: dict[str, list[Path]] = {}
    for f in sorted(SRC.glob("*.html")) + sorted(SRC.glob("*.mhtml")):
        out.setdefault(f.stem, []).append(f)
    return dict(sorted(out.items()))


def flag_months(c: pd.DataFrame, l: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """Mark source pages that are not a usable snapshot (column `flag`; blank = usable):
    * all-student pages whose state x country table repeats an earlier month exactly (DHS's November 2023 page
      republishes May 2023);
    * STEM pages whose total is under half the usual STEM/all-student ratio of the surrounding months
      (September 2020, September and November 2022 carry roughly a third of the usual rows)."""
    c = c.copy()
    c["flag"] = ""
    c.loc[c.rows == 0, "flag"] = "no table"
    seen = {}
    for m, d in l.groupby("month"):
        key = tuple(map(tuple, d.sort_values(["state", "country"])[["state", "country", "n"]].values))
        if key in seen:
            c.loc[(c.kind == "all") & (c.month == m), "flag"] = f"repeats {pd.Timestamp(seen[key]).strftime('%B %Y')}"
        else:
            seen[key] = m
    ok_all = c[(c.kind == "all") & (c.flag == "")].set_index("month").state_sum
    r = (s.groupby("month").n.sum() / ok_all.reindex(s.month.unique()).values).dropna()
    usual = r.rolling(7, center=True, min_periods=3).median()
    for m in r[r < 0.5 * usual].index:
        c.loc[(c.kind == "stem") & (c.month == m), "flag"] = f"partial ({100 * r[m]:.0f}% of the all-student count vs {100 * usual[m]:.0f}% usually)"
    return c


def usable_months(kind: str) -> set:
    c = pd.read_csv(OUT / "files.csv", parse_dates=["month"]).fillna({"flag": ""})
    return set(c[(c.kind == kind) & (c.flag == "")].month)


def build() -> dict:
    W, L, S, C = [], [], [], []
    for stem, copies in sources().items():
        parsed = [(f, _table_rows(f)) for f in copies]
        usable = [(f, r) for f, r in parsed if len(r) >= 2]
        kind = "stem" if "-stem-" in stem else "all"
        alt = ", ".join(f.name for f in copies[1:])
        if not usable:
            C.append({"file": copies[0].name, "kind": kind, "month": _month(stem), "rows": 0, "copies": alt,
                      "note": "no data table on the page in any saved copy"})
            continue
        f, rows = usable[0]
        note = ""
        if len(usable) > 1:
            note = "other saved copies identical" if all(r == rows for _, r in usable[1:]) else "saved copies DIFFER; first used"
        elif len(copies) > 1:
            note = "other saved copies have no table"
        if kind == "stem":
            d, chk = parse_stem(f, rows); S.append(d)
        else:
            w, l, chk = parse_all(f, rows); W.append(w); L.append(l)
        C.append({**chk, "copies": alt, "note": note})
    OUT.mkdir(parents=True, exist_ok=True)
    cmap = canonical_countries([d.country for d in W + S])
    for d in W + L + S:
        d["country"] = d.country.map(cmap)
    pd.Series(cmap, name="canonical").rename_axis("raw").reset_index().query("raw != canonical").to_csv(OUT / "country_map.csv", index=False)
    w = pd.concat(W, ignore_index=True).sort_values(["month", "country"])
    l = pd.concat(L, ignore_index=True).sort_values(["month", "state", "country"])
    s = pd.concat(S, ignore_index=True).sort_values(["month", "state", "level", "country", "sex"])
    w.to_parquet(OUT / "all_country.parquet", index=False)
    l.to_parquet(OUT / "all_state_country.parquet", index=False)
    s.to_parquet(OUT / "stem.parquet", index=False)
    c = flag_months(pd.DataFrame(C).sort_values(["kind", "month"]), l, s)
    c.to_csv(OUT / "files.csv", index=False)
    return {"all_country": w, "all_state_country": l, "stem": s, "files": c}


# ---------------------------------------------------------------- per-state summaries for the profiles
DEGREE = ["bachelors", "masters", "doctorate"]
MONTH_NAME = lambda m: pd.Timestamp(m).strftime("%B %Y")


def nice(c: str) -> str:
    """Display name: 'BAHAMAS, THE' -> 'Bahamas', 'CONGO (KINSHASA)' -> 'Congo (Kinshasa)'."""
    c = re.sub(r",\s*THE$", "", c).title()
    for a, b in ((" And ", " and "), (" Of ", " of "), (" The ", " the "), ("D'Ivoire", "d'Ivoire"), ("'S ", "'s ")):
        c = c.replace(a, b)
    return c


def state_payloads(states: list[str]) -> dict:
    """{state: {...}} with the latest snapshot, a yearly trend (latest month in each calendar year) and STEM by level.
    Built from the parquet files written by build()."""
    l = pd.read_parquet(OUT / "all_state_country.parquet")
    s = pd.read_parquet(OUT / "stem.parquet")
    l, s = l[l.month.isin(usable_months("all"))], s[s.month.isin(usable_months("stem"))]
    m1, sm1 = l.month.max(), s.month.max()
    yearly = l.groupby(l.month.dt.year).month.max().sort_index()   # one snapshot per year
    ly = l[l.month.isin(yearly.values)].assign(year=lambda d: d.month.dt.year)
    now = l[l.month == m1]
    us = now.groupby("country").n.sum()
    us_tot = int(us.sum())
    st_tot = now.groupby("state").n.sum()
    ranked = st_tot[st_tot.index.isin(states)].sort_values(ascending=False)
    snow = s[s.month == sm1]
    us_stem_tot = int(snow.n.sum())
    out = {}
    for st in states:
        x = now[now.state == st].groupby("country").n.sum().sort_values(ascending=False)
        tot = int(x.sum())
        if not tot:
            continue
        top = [{"country": nice(c), "n": int(n), "share": round(100 * n / tot, 2), "us_share": round(100 * us.get(c, 0) / us_tot, 2)} for c, n in x.head(12).items()]
        tr = ly[ly.state == st]
        years = sorted(tr.year.unique())
        tot_series = tr.groupby("year").n.sum().reindex(years, fill_value=0)
        top5 = list(x.head(5).index)
        lines = [{"country": nice(c), "y": [int(v) for v in years], "v": [int(v) for v in tr[tr.country == c].groupby("year").n.sum().reindex(years, fill_value=0)]} for c in top5]
        sx = snow[snow.state == st]
        stem_tot = int(sx.n.sum())
        lv = {}
        for k in DEGREE:
            g = sx[sx.level == k].groupby("country").n.sum().sort_values(ascending=False)
            lv[k] = {"n": int(g.sum()), "top": [{"country": nice(c), "n": int(n)} for c, n in g.head(6).items()]}
        lv["other"] = {"n": int(sx[~sx.level.isin(DEGREE)].n.sum())}
        sc = sx.groupby("country").n.sum().sort_values(ascending=False)
        keep = list(sc.head(8).index)
        flows = (sx.assign(c=sx.country.where(sx.country.isin(keep), "ALL OTHER COUNTRIES"), lev=sx.level.where(sx.level.isin(DEGREE), "other"))
                 .groupby(["c", "lev"]).n.sum())
        out[st] = {
            "month": MONTH_NAME(m1), "total": tot, "us_total": us_tot, "rank": int(list(ranked.index).index(st)) + 1 if st in ranked.index else None, "n_ranked": len(ranked),
            "top": top, "top2_share": round(100 * x.head(2).sum() / tot, 1), "countries": int((x > 0).sum()),
            "trend": {"y": [int(v) for v in years], "v": [int(v) for v in tot_series], "first_month": MONTH_NAME(yearly.iloc[0]), "lines": lines},
            "stem": {"month": MONTH_NAME(sm1), "total": stem_tot, "share": round(100 * stem_tot / tot, 1) if MONTH_NAME(sm1) == MONTH_NAME(m1) else None,
                     "us_share": round(100 * us_stem_tot / us_tot, 1), "levels": lv,
                     "flows": [{"c": nice(c) if c != "ALL OTHER COUNTRIES" else "All other countries", "lev": lev, "n": int(n)} for (c, lev), n in flows.items()],
                     "order": [nice(c) for c in keep] + ["All other countries"]},
        }
    return out


# ---------------------------------------------------------------- state x year measures for the State Talent Sheet
SOURCE = "Data from DHS, SEVIS by the Numbers"
SHEET_MEASURES = {   # name: (title, unit, format), same shape as states.MEASURES
    "sevis_total": ("Active F-1/M-1 students, all levels (SEVIS)", "students", "{:,.0f}"),
    "sevis_share_of_us": ("Share of U.S. active F-1/M-1 students (SEVIS)", "%", "{:.1f}%"),
    "sevis_share_india": ("Share of F-1/M-1 students from India (SEVIS)", "%", "{:.1f}%"),
    "sevis_share_china": ("Share of F-1/M-1 students from China (SEVIS)", "%", "{:.1f}%"),
    "sevis_top2_share": ("Share from the two largest countries of origin (SEVIS)", "%", "{:.1f}%"),
    "sevis_countries": ("Countries of citizenship represented (SEVIS)", "countries", "{:,.0f}"),
    "sevis_stem_total": ("Active STEM F-1/M-1 students (SEVIS)", "students", "{:,.0f}"),
    "sevis_stem_master": ("Active STEM master's students (SEVIS)", "students", "{:,.0f}"),
    "sevis_stem_doc": ("Active STEM doctoral students (SEVIS)", "students", "{:,.0f}"),
    "sevis_stem_master_india": ("Share of STEM master's students from India (SEVIS)", "%", "{:.1f}%"),
}


def fall_months(months) -> pd.Series:
    """year -> the September-December snapshot closest to November (lines up with the IPEDS fall census).
    Years with no fall page (2019 has only March) are left out rather than filled from another season."""
    m = pd.Series(pd.to_datetime(sorted(set(months))))
    m = m[m.dt.month >= 9]
    return m.groupby(m.dt.year).agg(lambda s: s.iloc[(s.dt.month - 11).abs().values.argmin()])


def sheet_panel(states: list[str]) -> tuple[pd.DataFrame, dict, dict]:
    """(long state x year x measure x value with US = sum of the listed states, notes by measure,
    {measure: {year: "Dec 2025"}}) from the parquet files written by build()."""
    l = pd.read_parquet(OUT / "all_state_country.parquet")
    s = pd.read_parquet(OUT / "stem.parquet")
    fa, fs = fall_months(usable_months("all")), fall_months(usable_months("stem"))
    l = l[l.month.isin(fa.values) & l.state.isin(states)].assign(year=lambda d: d.month.dt.year)
    s = s[s.month.isin(fs.values) & s.state.isin(states)].assign(year=lambda d: d.month.dt.year)
    us = lambda d: d.assign(state="US")
    L, S = pd.concat([l, us(l)]), pd.concat([s, us(s)])
    k = ["state", "year"]
    tot = L.groupby(k).n.sum()
    by_c = L.groupby(k + ["country"]).n.sum()
    top2 = by_c.groupby(level=k, group_keys=False).apply(lambda x: x.nlargest(2).sum())
    stem = S.groupby(k).n.sum()
    lev = S.groupby(k + ["level"]).n.sum().unstack(fill_value=0)
    sm = S[S.level == "masters"]
    share = lambda part, whole: 100 * part.reindex(whole.index, fill_value=0) / whole
    us_tot = tot.xs("US", level="state")
    out = {
        "sevis_total": tot,
        "sevis_share_of_us": 100 * tot / tot.index.get_level_values("year").map(us_tot).values,
        "sevis_share_india": share(L[L.country == "INDIA"].groupby(k).n.sum(), tot),
        "sevis_share_china": share(L[L.country == "CHINA"].groupby(k).n.sum(), tot),
        "sevis_top2_share": 100 * top2 / tot,
        "sevis_countries": (by_c > 0).groupby(level=k).sum(),
        "sevis_stem_total": stem,
        "sevis_stem_master": lev["masters"],
        "sevis_stem_doc": lev["doctorate"],
        "sevis_stem_master_india": share(sm[sm.country == "INDIA"].groupby(k).n.sum(), sm.groupby(k).n.sum()[lambda x: x >= 30]),
    }
    rows = [pd.DataFrame({"state": v.index.get_level_values("state"), "year": v.index.get_level_values("year"),
                          "measure": m, "value": v.values.astype(float)}) for m, v in out.items()]
    lab = lambda f: {int(y): pd.Timestamp(m).strftime("%b %Y") for y, m in f.items()}
    months = {m: lab(fs if m.startswith("sevis_stem") else fa) for m in out}
    snap = lambda f: ", ".join(f"{y}={pd.Timestamp(m).strftime('%b')}" for y, m in f.items())
    base = (f"{SOURCE}. Active F-1/M-1 records at schools in each state, one fall snapshot per year (the month "
            "closest to November; 2019 has no fall page). Counts every level SEVIS covers, from primary school to "
            "doctorate plus language and flight training, so it is not the same population as IPEDS degree-granting "
            "enrollment. U.S. = 50 states + DC. ")
    notes = {m: base + f"Snapshots: {snap(fa)} (November 2023 repeats May 2023, so 2023 uses October)." for m in out}
    for m in out:
        if m.startswith("sevis_stem"):
            notes[m] = (base + "STEM = DHS STEM Designated Degree Program List (not the IPEDS CIP families used elsewhere). "
                        "DHS's STEM pages are not drawn on the same basis as its all-student pages (New Jersey's STEM count "
                        "exceeds its all-student count), so no STEM share is computed. "
                        f"Snapshots: {snap(fs)}. Fall 2022 is blank: both fall STEM pages are partial.")
    notes["sevis_stem_master_india"] += " States with fewer than 30 STEM master's students are blank."
    notes["sevis_countries"] += " Countries with at least one active student."
    return pd.concat(rows, ignore_index=True), notes, months


# ---------------------------------------------------------------- check against IPEDS nonresident enrollment
def ipeds_check() -> pd.DataFrame:
    """SEVIS fall snapshot vs IPEDS fall nonresident headcount, by state and year (both 50 states + DC).

        python -m ipeds_clean.sevis --check     # -> data/sevis/ipeds_check.csv, national_levels.csv + summary

    They measure different populations, so the ratio is a consistency check, not a reconciliation: SEVIS covers
    every level from primary school up plus language and flight schools and counts F-1/M-1 visa holders only;
    IPEDS counts students on any temporary visa at degree-granting Title IV institutions."""
    from .states import HARM, _universe
    from .states_explorer import NAMES
    st51 = [s for s in NAMES if s != "US"]
    u = _universe()
    e = pd.read_parquet(HARM / "enrollment.parquet", columns=["year", "unitid", "race", "n"])
    e = e[(e.race == "nonres") & (e.year >= 2014)].merge(u[["year", "unitid", "state"]], on=["year", "unitid"])
    ip = e.groupby(["state", "year"]).n.sum().rename("ipeds_nonres")
    l = pd.read_parquet(OUT / "all_state_country.parquet")
    fa = fall_months(usable_months("all"))
    sv = (l[l.month.isin(fa.values) & l.state.isin(st51)].assign(year=lambda d: d.month.dt.year)
          .groupby(["state", "year", "month"]).n.sum().rename("sevis_all").reset_index())
    d = sv.merge(ip.reset_index(), on=["state", "year"], how="inner")
    us = d.groupby(["year", "month"])[["sevis_all", "ipeds_nonres"]].sum().reset_index().assign(state="US")
    d = pd.concat([d, us], ignore_index=True)
    d["ratio"] = (d.sevis_all / d.ipeds_nonres).round(3)
    d["month"] = d.month.dt.strftime("%Y-%m")
    d = d[["state", "year", "month", "sevis_all", "ipeds_nonres", "ratio"]].sort_values(["state", "year"])
    d.to_csv(OUT / "ipeds_check.csv", index=False)
    # national, by level: SEVIS degree levels vs IPEDS undergraduate / graduate nonresidents
    w = pd.read_parquet(OUT / "all_country.parquet")
    w = w[w.month.isin(fa.values)].assign(year=lambda x: x.month.dt.year).groupby("year")[LEVELS + ["total"]].sum()
    e2 = pd.read_parquet(HARM / "enrollment.parquet", columns=["year", "unitid", "level", "race", "n"])
    e2 = e2[(e2.race == "nonres") & (e2.year >= 2014)].merge(u[["year", "unitid"]], on=["year", "unitid"])
    g = e2.assign(lv=e2.level.map({"ug": "ug", "grad": "grad", "first_prof": "grad"}).fillna("other")).groupby(["year", "lv"]).n.sum().unstack(fill_value=0)
    nat = pd.DataFrame({"sevis_assoc_bach": w.associate + w.bachelors, "ipeds_ug": g.get("ug"),
                        "sevis_master_doc": w.masters + w.doctorate, "ipeds_grad": g.get("grad"),
                        "sevis_other_levels": w.total - w[["associate", "bachelors", "masters", "doctorate"]].sum(axis=1),
                        "sevis_total": w.total}).dropna()
    nat["ug_ratio"] = (nat.sevis_assoc_bach / nat.ipeds_ug).round(3)
    nat["grad_ratio"] = (nat.sevis_master_doc / nat.ipeds_grad).round(3)
    nat.astype({c: "int64" for c in nat.columns if not c.endswith("ratio")}).to_csv(OUT / "national_levels.csv")
    return d


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv[1:]:
        d = ipeds_check()
        us = d[d.state == "US"].set_index("year")
        print("U.S. (50 states + DC): SEVIS fall snapshot vs IPEDS fall nonresident headcount")
        print(us[["month", "sevis_all", "ipeds_nonres", "ratio"]].to_string())
        st = d[d.state != "US"]
        last = st[st.year == st.year.max()].sort_values("ratio")
        print(f"\nstate ratios, fall {int(st.year.max())}: median {last.ratio.median():.2f}")
        print("lowest:", last.head(5)[["state", "ratio"]].to_dict("records"))
        print("highest:", last.tail(5)[["state", "ratio"]].to_dict("records"))
        print("\nnational by level:\n", pd.read_csv(OUT / "national_levels.csv").to_string(index=False))
        sys.exit()
    r = build()
    c = r["files"]
    print(c.groupby("kind").agg(files=("file", "count"), first=("month", "min"), last=("month", "max")))
    a = c[c.kind == "all"]
    print("all-student files where state, level or sex sums differ from the total by >0.5%:")
    for col in ("state_sum", "level_sum", "sex_sum"):
        off = a[(a[col] - a.total).abs() > 0.005 * a.total]
        print(f"  {col}: {len(off)}", off[["file", "total", col]].head(3).to_dict("records") if len(off) else "")
    print("flagged (left out of snapshots):")
    print(c[c.flag != ""][["file", "flag"]].to_string(index=False))
