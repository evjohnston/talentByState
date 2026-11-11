"""Interactive state explorer: one self-contained HTML file built from the state panel.

    python -m ipeds_clean.states_explorer            # -> data/states/explorer.html

Data come from data/states/state_panel.csv (python -m ipeds_clean.states builds it) and the
measure definitions in ipeds_clean.states. The page needs no server; open the file in a browser.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd

from .external import SOURCES as EXT_SOURCES
from .states import DEST, DIVERGING, INTL_NOTE, LEVEL_NAMES, MEASURES, NOTES, REAL_BASE, TILES

TEMPLATE = Path(__file__).parent / "templates" / "sheet.html"
SANKEY = Path(__file__).parent / "templates" / "sankey.js"
KIT = Path(__file__).parent / "templates" / "kit.css"
FONTS = Path(__file__).resolve().parents[1] / "reference" / "fonts"
OUT_FILE = DEST / "sheet.html"

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
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "US": "United States",
}

# Measure groups shown in the rail, in order. Families ending in a degree level collapse into one
# entry with a level switch.
GROUPS = [
    ("International talent", lambda m: m.startswith(("intl_", "share_of_us_intl")) or m == "foreign_share_ft"),
    ("International students by country (SEVIS)", lambda m: m.startswith("sevis_")),
    ("International students' economic value (IIE, NAFSA)", lambda m: m.startswith("iie_")),
    ("Graduate students & postdocs (NSF GSS)", lambda m: m.startswith("gss_")),
    ("Doctorates (NSF SED)", lambda m: m.startswith("sed_")),
    ("Research funding (NSF HERD, Federal Funds, USAspending)", lambda m: m.startswith("rd_")),
    ("H-1B jobs & green cards (DOL)", lambda m: m.startswith("dol_")),
    ("Green cards & citizenship (DHS)", lambda m: m.startswith("dhs_")),
    ("H-1B petitions by employer (USCIS)", lambda m: m.startswith("h1b_")),
    ("Workforce: foreign-born STEM workers (ACS)", lambda m: m.startswith("acs_")),
    ("STEM jobs & wages (BLS)", lambda m: m.startswith("oews_")),
    ("Patents (USPTO)", lambda m: m.startswith("pat_")),
    ("K-12 preparation (NAEP)", lambda m: m.startswith(("naep_", "k12_", "crdc_"))),
    ("OPT: international graduates' first jobs (ICE)", lambda m: m.startswith("opt_")),
    ("Exchange visitors (J-1)", lambda m: m.startswith("j1_")),
    ("Do graduates stay? (Census PSEO)", lambda m: m.startswith("pseo_")),
    ("Graduate migration (ACS)", lambda m: m.startswith("mig_")),
    ("Graduate earnings & debt (College Scorecard)", lambda m: m.startswith("sc_")),
    ("STEM & field mix", lambda m: m.startswith(("stem_", "field_share_"))),
    ("Enrollment", lambda m: m in {"enroll_total", "share_public", "share_forprofit", "share_parttime",
                                   "share_grad", "share_online_only"}),
    ("Outcomes", lambda m: m in {"bach_per_100_ug", "grad_rate_bach6", "grad_rate_2yr"}),
    ("Prices & finance", lambda m: m in {"tuition_pub4_instate", "approp_per_fte", "tuition_reliance_pub",
                                         "faculty_salary"}),
    ("Student migration", lambda m: m in {"instate_share_ft", "net_migration_ft"} or m.startswith("fresh_")),
]
LEVEL_RE = re.compile(r"^((?:intl_share|stem_share|field_share)(?:_[a-z]+)?)_(bach|master|doc)$")
FIELD_LABEL = {"cs": "Computer & information sciences", "eng": "Engineering & eng. technology",
               "math": "Mathematics & statistics", "bio": "Biological & biomedical sciences",
               "phys": "Physical sciences", "health": "Health professions", "business": "Business"}

# Institutions that enroll students nationwide online but report from one state.
ONLINE_GIANTS = {
    "UT": "Western Governors University (online, nationwide) reports from Utah, so Utah's totals include "
          "students and graduates who live in every state.",
    "NH": "Southern New Hampshire University's online students (nationwide) are counted in New Hampshire.",
    "MD": "University of Maryland Global Campus's online students (nationwide) are counted in Maryland.",
}
NO_ONLINE_CAVEAT = {"tuition_pub4_instate", "approp_per_fte", "tuition_reliance_pub", "faculty_salary",
                    "grad_rate_bach6", "grad_rate_2yr", "instate_share_ft", "net_migration_ft", "foreign_share_ft"}


def family_label(fam: str) -> str:
    if fam == "intl_share_stem":
        return "International share of STEM degrees"
    if fam == "intl_share":
        return "International share of all degrees"
    if fam == "stem_share":
        return "STEM share of degrees"
    if fam.startswith("field_share_"):
        return f"{FIELD_LABEL[fam.removeprefix('field_share_')]}: share of degrees"
    if fam.startswith("intl_share_"):
        return f"{FIELD_LABEL[fam.removeprefix('intl_share_')]}: international share"
    return fam


def fmt_spec(f: str) -> dict:
    """Python format string -> {d, comma, sign, pre, suf} for the page's formatter."""
    m = re.fullmatch(r"(.*?)\{:([+]?)(,?)\.(\d)f\}(.*)", f)
    pre, sign, comma, d, suf = m.groups()
    return {"d": int(d), "comma": bool(comma), "sign": bool(sign), "pre": pre, "suf": suf}


def note_for(m: str) -> str:
    if m in NOTES:
        return NOTES[m]
    if m.startswith(("intl_", "field_", "stem_", "share_of_us")):
        return INTL_NOTE
    return ""


def guilloche(size=640, n=18) -> str:
    """Security-print rosette as an SVG data URI (used faintly behind the map and data page)."""
    c = size / 2
    paths = []
    for k in range(n):
        ph = 2 * math.pi * k / n
        pts = []
        for i in range(721):
            t = 2 * math.pi * i / 720
            r = c * (0.56 + 0.17 * math.sin(7 * t + ph) + 0.07 * math.sin(19 * t - 2 * ph))
            pts.append(f"{c + r * math.cos(t):.1f},{c + r * math.sin(t):.1f}")
        paths.append(f'<polyline points="{" ".join(pts)}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
           f'<g fill="none" stroke="#1f2d5c" stroke-width="0.6">{"".join(paths)}</g></svg>')
    return "data:image/svg+xml," + re.sub(r"[#<>\"%]", lambda x: "%" + format(ord(x.group()), "02X"), svg)


def sig(x: float) -> float:
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, max(0, 4 - int(math.floor(math.log10(abs(x)))) - 1))


def payload(sp: pd.DataFrame, extra: dict | None = None) -> dict:
    """extra = {"measures": {name: (title, unit, fmt)}, "notes": {...}, "months": {name: {year: label}},
    "src": {name: source key}} for measures from outside IPEDS (rows already appended to sp)."""
    states = list(TILES)                      # 51 (50 + DC), tile order
    order = states + ["US"]
    data, meta = {}, {}
    extra = extra or {"measures": {}, "notes": {}, "months": {}, "src": {}}
    for m, (title, unit, f) in (MEASURES | extra["measures"]).items():
        d = sp[sp.measure == m]
        if d.empty:
            continue
        w = d.pivot(index="year", columns="state", values="value").reindex(columns=order).sort_index()
        years = [int(y) for y in w.index]
        sv = w[states].stack().astype(float).dropna()
        if sv.empty:                          # national-only measure (no state reports it): not a sheet row
            continue
        data[m] = {"y": years, "v": [[None if pd.isna(x) else sig(float(x)) for x in row] for row in w.values]}
        lo, hi = float(sv.quantile(0.02)), float(sv.quantile(0.98))
        if unit == "%" and lo >= 0:
            lo = min(lo, 0.0) if hi <= 25 else lo
        lm = LEVEL_RE.match(m)
        fam, lev = (lm.group(1), lm.group(2)) if lm else (m, None)
        group = next(g for g, test in GROUPS if test(m))
        meta[m] = {
            "title": title, "unit": unit, "fmt": fmt_spec(f), "group": group,
            "family": fam, "level": lev, "label": family_label(fam) if lev else title,
            "note": extra["notes"].get(m) or note_for(m), "div": m in DIVERGING, "divNote": DIVERGING.get(m, ""),
            "change": "diff" if unit in ("%", "per 100", "per 1,000", "score", "ratio") else "pct",
            "gap": {"naep": 5, "pseo": 6, "crdc": 4, "k12": 10}.get(extra["src"].get(m), 2),   # survey spacing (NAEP 2-4 years, PSEO 3/5-year cohorts, CRDC 2-3 years, Digest's selected years 1970/1980/1990): don't break lines
            "lo": sig(lo), "hi": sig(hi),
            "online": m not in NO_ONLINE_CAVEAT and m not in extra["measures"],
            "src": extra["src"].get(m, "ipeds"),
            "months": extra["months"].get(m),
        }
    return {
        "states": states, "names": NAMES, "tiles": {s: TILES[s] for s in states},
        "groups": [g for g, _ in GROUPS], "levels": {"bach": "Bachelor's", "master": "Master's",
                                                     "doc": "Doctoral"},
        "levelNames": LEVEL_NAMES, "meta": meta, "data": data, "realBase": REAL_BASE,
        "onlineGiants": ONLINE_GIANTS, "built": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "srcLines": {"ipeds": "Data from NCES, IPEDS", "sevis": "Data from DHS, SEVIS by the Numbers",
                     **{k: v[1] for k, v in EXT_SOURCES.items()}},
    }


def site_nav(current: str, base: str = "") -> str:
    """Tab bar shared by every page. base is the path prefix back to data/states/ ("" or "../")."""
    tabs = [("sheet", "Sheet", f"{base}sheet.html"), ("profiles", "State Talent Profile", f"{base}profiles/index.html"),
            ("international", "International Talent", f"{base}international.html")]
    return '<nav class="site" aria-label="Pages">' + "".join(
        f'<a href="{h}"{' aria-current="page"' if k == current else ""}>{l}</a>' for k, l, h in tabs) + "</nav>"


def kit_css() -> str:
    """Shared CSS for the HTML pages, with the fonts embedded so the files work offline."""
    import base64
    faces = [("IBM Plex Sans", f"ibm-plex-sans-latin-{w}-normal.woff2", str(w), "normal", "") for w in (400, 500, 600, 700)]
    css = []
    for fam, f, w, style, extra in faces:
        p = FONTS / f
        if p.exists():
            b = base64.b64encode(p.read_bytes()).decode()
            css.append(f"@font-face{{font-family:\"{fam}\";src:url(data:font/woff2;base64,{b}) format(\"woff2\");"
                       f"font-weight:{w};font-style:{style};{extra}font-display:swap}}")
    return "\n".join(css) + "\n" + KIT.read_text()


def full_panel(sp: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The IPEDS state panel plus every outside source (SEVIS, ACS, NAEP, NSF GSS/SED, USCIS, DOL, USPTO), as
    (long rows, extra) for payload(). Shared by the sheet and the state profiles."""
    from . import external, sevis
    sv, notes, months = sevis.sheet_panel(list(TILES))
    extra = {"measures": dict(sevis.SHEET_MEASURES), "notes": notes, "months": months,
             "src": {m: "sevis" for m in sevis.SHEET_MEASURES}}
    rows = [sp, sv]
    for src, d, m, n in external.sheet_panels(list(TILES)):
        rows.append(d)
        extra["measures"] |= m
        extra["notes"] |= n
        extra["src"] |= {k: src for k in m}
    extra["months"] |= {k: v for k, v in external.MONTHS.items() if k in extra["measures"]}
    return pd.concat(rows, ignore_index=True), extra


def build(path: Path = OUT_FILE) -> Path:
    sp = pd.read_csv(DEST / "state_panel.csv")
    data = payload(*full_panel(sp))
    from .state_profile import Panels, flows_all, pipeline_all   # heavy; only for the Sankey views
    P = Panels()
    data["flows"], data["pipeline"] = flows_all(P), pipeline_all(P)
    from .peers import presets
    data["presets"] = presets(sp, data["flows"])   # IPEDS panel only
    blob = json.dumps(data, separators=(",", ":"), allow_nan=False)
    html = TEMPLATE.read_text().replace("/*__KIT__*/", kit_css()).replace("<!--__SITENAV__-->", site_nav("sheet"))
    html = html.replace("/*__DATA__*/null", blob.replace("</", "<\\/")).replace("__GUILLOCHE__", guilloche())
    html = html.replace("/*__SANKEY__*/", SANKEY.read_text()).replace("/*__PEERS__*/", (SANKEY.parent / "peers.js").read_text())
    path.write_text(html)
    (DEST / "explorer.html").write_text('<!doctype html><meta charset="utf-8"><title>State Talent Sheet</title>'
                                        '<script>location.replace("sheet.html" + location.hash)</script>'
                                        '<a href="sheet.html">Open the State Talent Sheet</a>')
    return path


def artifact(path: Path) -> Path:
    """Variant for a claude.ai artifact: the host supplies doctype/html/head/body."""
    html = build().read_text()
    for tag in ("<!doctype html>", '<html lang="en">', "<head>", "</head>", "<body>", "</body>", "</html>",
                '<meta charset="utf-8">', '<meta name="viewport" content="width=device-width, initial-scale=1">'):
        html = html.replace(tag, "", 1)
    path.write_text(html.strip() + "\n")
    return path


if __name__ == "__main__":
    import sys
    p = artifact(Path(sys.argv[2])) if sys.argv[1:2] == ["--artifact"] else build()
    print(f"wrote {p} ({p.stat().st_size / 1e6:.1f} MB)")
