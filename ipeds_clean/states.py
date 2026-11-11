"""State-by-state measures from the harmonized IPEDS panels, and tile-grid heatmaps of them.

    python -m ipeds_clean.states                 # state panel + the standard set of maps
    from ipeds_clean import states
    sp = states.panel()                          # long: state x year x measure
    states.tile_map(sp, "approp_per_fte", 2023)  # one map (returns the matplotlib figure)
    states.change_map(sp, "enroll_total", 2010, 2023)
    states.map_grid(sp, "share_online_only", [2012, 2016, 2020, 2023])

Geography is where the INSTITUTION is located (directory.stabbr), 50 states + DC. The one
exception is the migration measures, built from where first-time students came FROM
(residence.parquet, Fall Enrollment part C).

Universe: degree-granting institutions, and from 1996 on Title IV participants (the Digest's
universe). Dollar measures are in constant dollars (BLS CPI-U, base REAL_BASE).

Measures (state x year)
  enroll_total          fall headcount
  share_public, share_forprofit, share_parttime, share_grad   share of fall headcount (%)
  share_online_only     % of students enrolled exclusively in distance education (2012+)
  bach_per_100_ug       bachelor's degrees awarded per 100 undergraduates enrolled the prior fall
  tuition_pub4_instate  enrollment-weighted in-state tuition & fees, public 4-year (real $)
  approp_per_fte        state + local appropriations per FTE student, public institutions
                        (fiscal year t over fall t-1 FTE; real $)
  tuition_reliance_pub  net tuition / (net tuition + state & local appropriations), publics (%)
  grad_rate_bach6       bachelor's within 6 years, first-time full-time bachelor's-seeking cohort,
                        4-year institutions (%; year = survey year, cohort entered 6 years earlier)
  grad_rate_2yr         award within 150% of normal time, 2-year institutions (%)
  faculty_salary        average salary, full-time instructional faculty, 9/10-month contracts (real $)
  instate_share_ft      % of first-time students at the state's institutions who are state residents
  net_migration_ft      (first-time students arriving from other states - residents leaving to
                        study in other states) per 100 resident first-time students
"""
from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd

from .config import DATA, OUT

HARM = OUT / "harmonized"
DEST = DATA / "states"
REAL_BASE = 2024

# ---------------------------------------------------------------- tile grid (col, row)
TILES = {
    "AK": (0, 0), "ME": (11, 0),
    "WI": (6, 1), "VT": (10, 1), "NH": (11, 1),
    "WA": (1, 2), "ID": (2, 2), "MT": (3, 2), "ND": (4, 2), "MN": (5, 2), "IL": (6, 2), "MI": (7, 2),
    "NY": (9, 2), "MA": (10, 2),
    "OR": (1, 3), "NV": (2, 3), "WY": (3, 3), "SD": (4, 3), "IA": (5, 3), "IN": (6, 3), "OH": (7, 3),
    "PA": (8, 3), "NJ": (9, 3), "CT": (10, 3), "RI": (11, 3),
    "CA": (1, 4), "UT": (2, 4), "CO": (3, 4), "NE": (4, 4), "MO": (5, 4), "KY": (6, 4), "WV": (7, 4),
    "VA": (8, 4), "MD": (9, 4), "DE": (10, 4),
    "AZ": (2, 5), "NM": (3, 5), "KS": (4, 5), "AR": (5, 5), "TN": (6, 5), "NC": (7, 5), "SC": (8, 5),
    "DC": (9, 5),
    "OK": (4, 6), "LA": (5, 6), "MS": (6, 6), "AL": (7, 6), "GA": (8, 6),
    "HI": (0, 7), "TX": (4, 7), "FL": (9, 7),
}
FIPS = {"AL": 1, "AK": 2, "AZ": 4, "AR": 5, "CA": 6, "CO": 8, "CT": 9, "DE": 10, "DC": 11, "FL": 12,
        "GA": 13, "HI": 15, "ID": 16, "IL": 17, "IN": 18, "IA": 19, "KS": 20, "KY": 21, "LA": 22,
        "ME": 23, "MD": 24, "MA": 25, "MI": 26, "MN": 27, "MS": 28, "MO": 29, "MT": 30, "NE": 31,
        "NV": 32, "NH": 33, "NJ": 34, "NM": 35, "NY": 36, "NC": 37, "ND": 38, "OH": 39, "OK": 40,
        "OR": 41, "PA": 42, "RI": 44, "SC": 45, "SD": 46, "TN": 47, "TX": 48, "UT": 49, "VT": 50,
        "VA": 51, "WA": 53, "WV": 54, "WI": 55, "WY": 56}
ABBR = {v: k for k, v in FIPS.items()}

# STEM = 2-digit CIP-2020 families. The seven families in the 2026 US Talent Report's Table 1.01
# (natural resources 03, architecture 04, computing 11, engineering 14, biological 26, math &
# statistics 27, physical sciences 40) plus engineering technology 15. Within ~4% of the report's
# 6-digit STEM totals and 0.6 pp of its 51.3% international share of STEM master's (2025).
# Edit here to change the definition everywhere.
STEM_CIP2 = ["03", "04", "11", "14", "15", "26", "27", "40"]
FIELDS = {"cs": ["11"], "eng": ["14", "15"], "math": ["27"], "bio": ["26"], "phys": ["40"],
          "health": ["51"], "business": ["52"]}
FIELD_NAMES = {"cs": "computer & information sciences", "eng": "engineering & eng. technology",
               "math": "mathematics & statistics", "bio": "biological & biomedical sciences",
               "phys": "physical sciences", "health": "health professions", "business": "business"}
INTL_FIELDS = {"cs", "eng", "math", "phys", "bio"}
LEVELS = {"bach": "bach", "master": "master", "doc_res": "doc"}
LEVEL_NAMES = {"bach": "bachelor's", "master": "master's", "doc": "research doctorates"}
FOREIGN_CODES = [64, 90]   # residence: "Foreign countries"

MEASURES = {   # name: (title, unit, format)
    "enroll_total": ("Fall enrollment", "students", "{:,.0f}"),
    "share_public": ("Share of enrollment at public institutions", "%", "{:.0f}%"),
    "share_forprofit": ("Share of enrollment at for-profit institutions", "%", "{:.0f}%"),
    "share_parttime": ("Share of students enrolled part-time", "%", "{:.0f}%"),
    "share_grad": ("Share of students who are graduate students", "%", "{:.0f}%"),
    "share_online_only": ("Share of students enrolled exclusively online", "%", "{:.0f}%"),
    "bach_per_100_ug": ("Bachelor's degrees per 100 undergraduates", "per 100", "{:.1f}"),
    "tuition_pub4_instate": ("In-state tuition & fees, public 4-year", f"{REAL_BASE} $", "${:,.0f}"),
    "approp_per_fte": ("State & local appropriations per FTE, public institutions", f"{REAL_BASE} $", "${:,.0f}"),
    "tuition_reliance_pub": ("Tuition share of core revenue, public institutions", "%", "{:.0f}%"),
    "grad_rate_bach6": ("Six-year bachelor's graduation rate, 4-year institutions", "%", "{:.0f}%"),
    "grad_rate_2yr": ("Completion within 150% of normal time, 2-year institutions", "%", "{:.0f}%"),
    "faculty_salary": ("Average full-time faculty salary (9/10-month)", f"{REAL_BASE} $", "${:,.0f}"),
    "instate_share_ft": ("First-time students who are in-state residents", "%", "{:.0f}%"),
    "net_migration_ft": ("Net student migration (per 100 resident first-time students)", "per 100", "{:+.0f}"),
    "foreign_share_ft": ("First-time students whose home is outside the US", "%", "{:.1f}%"),
    "intl_stem_master_count": ("STEM master's degrees earned by international students", "degrees", "{:,.0f}"),
    "share_of_us_intl_stem_master": ("Share of all US international STEM master's degrees", "%", "{:.1f}%"),
    "stem_master_per_doc": ("STEM master's degrees per research doctorate", "ratio", "{:.1f}"),
    "intl_share_enroll_ug": ("International share of undergraduate enrollment", "%", "{:.1f}%"),
    "intl_share_enroll_grad": ("International share of graduate enrollment", "%", "{:.0f}%"),
}
for _t, _ln in LEVEL_NAMES.items():
    MEASURES[f"intl_share_{_t}"] = (f"International share of all {_ln}", "%", "{:.0f}%" if _t != "bach" else "{:.1f}%")
    MEASURES[f"intl_share_stem_{_t}"] = (f"International share of STEM {_ln}", "%", "{:.0f}%" if _t != "bach" else "{:.1f}%")
    MEASURES[f"stem_share_{_t}"] = (f"STEM share of {_ln}", "%", "{:.0f}%")
    for _f, _fn in FIELD_NAMES.items():
        MEASURES[f"field_share_{_f}_{_t}"] = (f"Share of {_ln} in {_fn}", "%", "{:.1f}%")
        if _f in INTL_FIELDS and _t != "bach":
            MEASURES[f"intl_share_{_f}_{_t}"] = (f"International share of {_fn} {_ln}", "%", "{:.0f}%")

# ---------------------------------------------------------------- data


def residence_years(r: pd.DataFrame) -> list[int]:
    """Years in which residence of first-time students is near-complete. Since 2001 the item is
    required only in even years; odd years are voluntary and about 40% of institutions report, which
    would make every migration measure zigzag. Drop an odd year from 2001 on when it has fewer than
    80% of the reporters of its neighbouring even years; keep everything else."""
    n = r.groupby("year").unitid.nunique()
    keep = []
    for y, k in n.items():
        nb = [n[z] for z in (y - 1, y + 1) if z in n.index]
        if y >= 2001 and y % 2 and nb and k < 0.8 * (sum(nb) / len(nb)):
            continue
        keep.append(int(y))
    return keep


def _universe() -> pd.DataFrame:
    d = pd.read_parquet(HARM / "directory.parquet",
                        columns=["year", "unitid", "stabbr", "fips", "control", "level", "degree_granting", "title_iv"])
    ok = d.degree_granting.fillna(False) & d.fips.isin(list(FIPS.values()))
    ok &= (d.year < 1996) | d.title_iv.fillna(False)
    d = d[ok].copy()
    d["state"] = d.fips.map(ABBR)
    return d[["year", "unitid", "state", "control", "level"]]


def _cpi() -> pd.Series:
    from .harmonize.finance import deflators
    idx = deflators()
    return idx[REAL_BASE] / idx


def build() -> pd.DataFrame:
    u = _universe()
    real = _cpi()
    out = []

    def add(name, s: pd.Series):
        s = s.replace([np.inf, -np.inf], np.nan).dropna()
        out.append(pd.DataFrame({"state": s.index.get_level_values("state"),
                                 "year": s.index.get_level_values("year").astype(int),
                                 "measure": name, "value": s.values}))

    # ---- enrollment
    e = pd.read_parquet(HARM / "enrollment.parquet", columns=["year", "unitid", "level", "attendance", "n"])
    e = e.merge(u, on=["year", "unitid"], suffixes=("", "_inst"))
    tot = e.groupby(["state", "year"]).n.sum()
    add("enroll_total", tot)
    add("share_public", 100 * e[e.control == 1].groupby(["state", "year"]).n.sum() / tot)
    add("share_forprofit", 100 * e[e.control == 3].groupby(["state", "year"]).n.sum().reindex(tot.index, fill_value=0) / tot)
    add("share_parttime", 100 * e[e.attendance == "pt"].groupby(["state", "year"]).n.sum() / tot)
    add("share_grad", 100 * e[e.level.isin(["grad", "first_prof"])].groupby(["state", "year"]).n.sum() / tot)
    ug = e[e.level == "ug"].groupby(["state", "year"]).n.sum()
    ug_inst = e[e.level == "ug"].groupby(["year", "unitid"]).n.sum().rename("ug").reset_index()
    del e

    # ---- online only (all students, exclusively distance)
    de = pd.read_parquet(HARM / "distance_ed.parquet", columns=["year", "unitid", "efdelev", "efdetot", "efdeexc"])
    de = de[de.efdelev == 1].merge(u, on=["year", "unitid"])
    g = de.groupby(["state", "year"])[["efdeexc", "efdetot"]].sum()
    add("share_online_only", 100 * g.efdeexc / g.efdetot)

    # ---- bachelor's per 100 undergraduates (degrees in year t / fall t-1 undergrads)
    c = pd.read_parquet(HARM / "completions.parquet", columns=["year", "unitid", "award_level", "total"])
    c = c[c.award_level == "bach"].merge(u, on=["year", "unitid"])
    b = c.groupby(["state", "year"]).total.sum()
    ug_prev = ug.rename(lambda y: y + 1, level="year")
    add("bach_per_100_ug", 100 * b / ug_prev.reindex(b.index))
    del c

    # ---- published in-state tuition, public 4-year, weighted by undergraduate enrollment
    p = pd.read_parquet(HARM / "prices.parquet", columns=["unitid", "ay", "ug_tf_in_state"]).rename(columns={"ay": "year"})
    p = p.dropna().merge(u[(u.control == 1) & (u.level == 1)], on=["year", "unitid"]).merge(ug_inst, on=["year", "unitid"])
    p = p[p.ug > 0]
    p["w"] = p.ug_tf_in_state * p.ug
    g = p.groupby(["state", "year"])[["w", "ug"]].sum()
    t = (g.w / g.ug)
    add("tuition_pub4_instate", t * t.index.get_level_values("year").map(real).values)

    # ---- appropriations per FTE and tuition reliance, publics (fiscal year t, FTE fall t-1)
    f = pd.read_parquet(HARM / "finance.parquet", columns=["year", "unitid", "state_approp", "local_approp", "tuition_net"])
    f = f.merge(u[u.control == 1], on=["year", "unitid"])
    fte = pd.read_parquet(HARM / "fte.parquet", columns=["year", "unitid", "fall_fte_total"])
    fte["year"] += 1
    f = f.merge(fte, on=["year", "unitid"], how="left")
    f["approp"] = f.state_approp.fillna(0) + f.local_approp.fillna(0)
    ok = f.fall_fte_total > 0
    g = f[ok].groupby(["state", "year"])[["approp", "fall_fte_total"]].sum()
    a = g.approp / g.fall_fte_total
    add("approp_per_fte", a * a.index.get_level_values("year").map(real).values)
    g = f.dropna(subset=["tuition_net"]).groupby(["state", "year"])[["tuition_net", "approp"]].sum()
    add("tuition_reliance_pub", 100 * g.tuition_net / (g.tuition_net + g.approp))
    del f

    # ---- graduation rates (pooled counts)
    gr = pd.read_parquet(HARM / "grad_rates.parquet", columns=["year", "unitid", "cohort", "measure", "n"])
    gr = gr.merge(u[["year", "unitid", "state"]], on=["year", "unitid"])
    s = gr.groupby(["state", "year", "cohort", "measure"]).n.sum().unstack("measure")
    bach = s.xs("ba4", level="cohort")
    add("grad_rate_bach6", 100 * bach.comp150_bach / bach.adj_cohort)
    two = s.xs("c2yr", level="cohort")
    add("grad_rate_2yr", 100 * two.comp150 / two.adj_cohort)
    del gr

    # ---- faculty salaries, 9/10-month contracts
    sal = pd.read_parquet(HARM / "faculty_salaries.parquet", columns=["year", "unitid", "contract", "n_faculty", "salary_outlay"])
    sal = sal[sal.contract == "9_10"].merge(u[["year", "unitid", "state"]], on=["year", "unitid"])
    g = sal.groupby(["state", "year"])[["salary_outlay", "n_faculty"]].sum()
    s = g.salary_outlay / g.n_faculty
    add("faculty_salary", s * s.index.get_level_values("year").map(real).values)

    # ---- first-time student migration (residence of first-time students)
    r = pd.read_parquet(HARM / "residence.parquet", columns=["year", "unitid", "state_code", "first_time"])
    r = r[r.year.isin(residence_years(r))]
    r = r.merge(u[["year", "unitid", "state"]], on=["year", "unitid"])
    r["home"] = pd.to_numeric(r.state_code, errors="coerce").map(ABBR)
    us = r[r.home.notna()]
    enrolled_here = r.groupby(["state", "year"]).first_time.sum()
    instate = us[us.home == us.state].groupby(["state", "year"]).first_time.sum()
    add("instate_share_ft", 100 * instate / enrolled_here)
    arriving = us[us.home != us.state].groupby(["state", "year"]).first_time.sum()
    leaving = us[us.home != us.state].groupby(["home", "year"]).first_time.sum().rename_axis(["state", "year"])
    residents = us.groupby(["home", "year"]).first_time.sum().rename_axis(["state", "year"])
    idx = residents.index
    add("net_migration_ft", 100 * (arriving.reindex(idx, fill_value=0) - leaving.reindex(idx, fill_value=0)) / residents)
    foreign = r[pd.to_numeric(r.state_code, errors="coerce").isin(FOREIGN_CODES)].groupby(["state", "year"]).first_time.sum()
    add("foreign_share_ft", 100 * foreign.reindex(enrolled_here.index, fill_value=0) / enrolled_here)

    out.extend(_international(u))
    sp = pd.concat(out, ignore_index=True)
    return sp.sort_values(["measure", "year", "state"]).reset_index(drop=True)


def _international(u: pd.DataFrame) -> list[pd.DataFrame]:
    """International (US nonresident) and field-mix measures from completions by race x
    2-digit CIP-2020 family (1995+ from 6-digit files; earlier years allocated) and fall
    enrollment by race. Levels: bach, master, doc_res (research/scholarship doctorates;
    the report's doctorate shares come from the SED, so IPEDS doctorate shares differ)."""
    out = []

    def add(name, s):
        s = s.replace([np.inf, -np.inf], np.nan).dropna()
        out.append(pd.DataFrame({"state": s.index.get_level_values("state"),
                                 "year": s.index.get_level_values("year").astype(int),
                                 "measure": name, "value": s.values}))

    cr = pd.read_parquet(HARM / "completions_race.parquet", columns=["year", "unitid", "award_level", "cip2020_2", "race", "n"],
                         filters=[("award_level", "in", list(LEVELS))])
    cr = cr.merge(u[["year", "unitid", "state"]], on=["year", "unitid"])
    cr["stem"] = cr.cip2020_2.isin(STEM_CIP2)
    cr["intl"] = cr.race == "nonres"
    key = ["state", "year"]
    for lv, tag in LEVELS.items():
        x = cr[cr.award_level == lv]
        tot = x.groupby(key).n.sum()
        stem = x[x.stem].groupby(key).n.sum()
        add(f"intl_share_{tag}", 100 * x[x.intl].groupby(key).n.sum().reindex(tot.index, fill_value=0) / tot)
        add(f"intl_share_stem_{tag}", 100 * x[x.stem & x.intl].groupby(key).n.sum().reindex(stem.index, fill_value=0) / stem)
        add(f"stem_share_{tag}", 100 * stem / tot)
        for f, cips in FIELDS.items():
            fx = x[x.cip2020_2.isin(cips)]
            ft = fx.groupby(key).n.sum()
            add(f"field_share_{f}_{tag}", 100 * ft.reindex(tot.index, fill_value=0) / tot)
            if f in INTL_FIELDS and tag != "bach":
                add(f"intl_share_{f}_{tag}", 100 * fx[fx.intl].groupby(key).n.sum().reindex(ft.index, fill_value=0) / ft[ft >= 30])
        if tag == "master":
            # where the country's international STEM master's graduates are trained
            ism = x[x.stem & x.intl].groupby(key).n.sum()
            add("intl_stem_master_count", ism)
            add("share_of_us_intl_stem_master", 100 * ism / ism.groupby(level="year").transform("sum"))
    sm = cr[cr.stem & (cr.award_level == "master")].groupby(key).n.sum()
    sd = cr[cr.stem & (cr.award_level == "doc_res")].groupby(key).n.sum()
    add("stem_master_per_doc", sm / sd[sd >= 20])

    e = pd.read_parquet(HARM / "enrollment.parquet", columns=["year", "unitid", "level", "race", "n"])
    e = e.merge(u[["year", "unitid", "state"]], on=["year", "unitid"])
    e["grp"] = np.where(e.level == "ug", "ug", np.where(e.level.isin(["grad", "first_prof"]), "grad", "other"))
    collected = e[e.race == "nonres"].groupby("year").n.sum()
    e = e[e.year.isin(collected[collected > 0].index)]
    for g in ("ug", "grad"):
        x = e[e.grp == g]
        tot = x.groupby(key).n.sum()
        add(f"intl_share_enroll_{g}", 100 * x[x.race == "nonres"].groupby(key).n.sum().reindex(tot.index, fill_value=0) / tot)
    return out


def panel() -> pd.DataFrame:
    return pd.read_csv(DEST / "state_panel.csv")


def wide(sp: pd.DataFrame, year: int) -> pd.DataFrame:
    """One row per state, one column per measure, for a single year (the table view)."""
    return sp[sp.year == year].pivot(index="state", columns="measure", values="value")

# ---------------------------------------------------------------- maps
# Colors: reference palette (dataviz skill). Sequential = one blue ramp light->dark;
# diverging = red <- neutral gray -> blue, equal arms.
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#e7e6e2"
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
       "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
DIV = ["#8f1d1d", "#b83232", "#e34948", "#ee8b89", "#f5c4c2", "#f0efec",
       "#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"]


def _cmap(colors, name):
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(name, colors)


def _ink_for(rgb) -> str:
    r, g, b = [c / 255 if c > 1 else c for c in rgb[:3]]
    lum = 0.2126 * r ** 2.2 + 0.7152 * g ** 2.2 + 0.0722 * b ** 2.2
    return INK if lum > 0.28 else "#ffffff"


def _draw(ax, values: pd.Series, cmap, norm, fmt: str, label_values: bool = True, fontsize=7.5):
    from matplotlib.patches import FancyBboxPatch
    for st, (cx, cy) in TILES.items():
        v = values.get(st, np.nan)
        x, y = cx, -cy
        if pd.isna(v):
            fc, ink = MUTED, INK2
        else:
            fc = cmap(norm(v))
            ink = _ink_for(fc)
        ax.add_patch(FancyBboxPatch((x + 0.04, y + 0.04), 0.92, 0.92, boxstyle="round,pad=0,rounding_size=0.08",
                                    fc=fc, ec=SURFACE, lw=1.5))
        ax.text(x + 0.5, y + 0.64, st, ha="center", va="center", fontsize=fontsize + 0.5, fontweight="bold", color=ink)
        if label_values:
            ax.text(x + 0.5, y + 0.3, "–" if pd.isna(v) else fmt.format(v), ha="center", va="center",
                    fontsize=fontsize - 1.5, color=ink)
    ax.set_xlim(-0.2, 12.2)
    ax.set_ylim(-7.2, 1.15)
    ax.set_aspect("equal")
    ax.axis("off")


DIVERGING = {"net_migration_ft": "Blue = more first-time students arrive than leave; red = net exporter."}
NOTES = {
    "approp_per_fte": "Colorado funds students through College Opportunity Fund stipends, which IPEDS records as "
                      "tuition, so its appropriations look low.",
    "tuition_reliance_pub": "Core revenue = net tuition + state and local appropriations. Colorado's stipends count "
                            "as tuition.",
    "net_migration_ft": "Arrivals from other states minus residents leaving to study elsewhere, as reported by "
                        "institutions (Fall Enrollment, residence of first-time students).",
    "share_online_only": "2020 reflects the pandemic shift to remote instruction.",
    "grad_rate_bach6": "Cohort entered six years earlier (2024 = fall 2018 entrants). First-time, full-time students only.",
}


INTL_NOTE = ("International = US nonresidents (students on temporary visas). Completions count first majors; "
             "STEM = CIP families 03, 04, 11, 14, 15, 26, 27, 40.")


def _note(measure: str) -> str:
    if measure in NOTES:
        return NOTES[measure] + "\n"
    if measure.startswith(("intl_", "field_", "stem_", "share_of_us")):
        return INTL_NOTE + "\n"
    return ""


def _legend(fig, ax, cmap, norm, fmt, clipped_lo, clipped_hi, note=""):
    import matplotlib as mpl
    # empty middle of the top tile row (between AK and ME), in data coordinates
    cax = ax.inset_axes([3.0, 0.55, 5.6, 0.2], transform=ax.transData)
    cb = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    ticks = np.linspace(norm.vmin, norm.vmax, 3)
    if getattr(norm, "vcenter", None) is not None:
        ticks = [norm.vmin, norm.vcenter, norm.vmax]
    cb.set_ticks(ticks)
    labs = [fmt.format(t) for t in ticks]
    if clipped_lo:
        labs[0] = "≤" + labs[0]
    if clipped_hi:
        labs[-1] = "≥" + labs[-1]
    cb.set_ticklabels(labs)
    cax.tick_params(labelsize=7, colors=INK2, length=0, pad=2)
    if note:
        cax.set_title(note, fontsize=7, color=INK2, loc="left", pad=3)


DPI = 300          # PNG resolution (print / Retina quality)
FONT = ["Avenir Next", "Helvetica Neue", "Helvetica", "DejaVu Sans"]


def _style():
    import matplotlib as mpl
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": FONT,
                         "svg.fonttype": "none", "savefig.dpi": DPI})


def _save(fig, path):
    """PNG at DPI plus a vector SVG (text stays editable in the SVG). If the PNG goes in a
    folder named png/, the SVG goes in a sibling svg/ folder; otherwise next to the PNG."""
    from pathlib import Path
    path = Path(path).with_suffix(".png")
    svg_dir = path.parent.parent / "svg" if path.parent.name == "png" else path.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    svg_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", dpi=DPI)
    fig.savefig(svg_dir / (path.stem + ".svg"), facecolor=SURFACE, bbox_inches="tight")


def _fig(width=7.2, height=5.0):
    import matplotlib.pyplot as plt
    _style()
    fig, ax = plt.subplots(figsize=(width, height), dpi=DPI)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    return fig, ax


def _limits(v: pd.Series, robust: bool):
    lo, hi = (v.quantile(0.05), v.quantile(0.95)) if robust and len(v) > 10 else (v.min(), v.max())
    return lo, hi, bool((v < lo).any()), bool((v > hi).any())


def _title(fig, title, subtitle):
    fig.text(0.03, 0.965, title, fontsize=11.5, fontweight="bold", color=INK, va="top")
    fig.text(0.03, 0.915, subtitle, fontsize=8, color=INK2, va="top")


def _footer(fig, text):
    fig.text(0.03, 0.025, text, fontsize=6.5, color=INK2, va="bottom")


SOURCE = "Source: IPEDS (harmonized panels). Institutions in each state; degree-granting, Title IV from 1996."


def tile_map(sp: pd.DataFrame, measure: str, year: int, robust: bool = True, path=None):
    """Sequential tile-grid map of one measure in one year."""
    from matplotlib.colors import Normalize, TwoSlopeNorm
    title, unit, fmt = MEASURES[measure]
    v = sp[(sp.measure == measure) & (sp.year == year) & (sp.state != "US")].set_index("state").value
    if v.empty:
        raise ValueError(f"no {measure} for {year}; years available: "
                         f"{sorted(sp[sp.measure == measure].year.unique())}")
    lo, hi, clo, chi = _limits(v, robust)
    if measure in DIVERGING:
        m = max(abs(lo), abs(hi))
        norm, cmap = TwoSlopeNorm(vmin=-m, vcenter=0, vmax=m), _cmap(DIV, "div")
        clo, chi = bool((v < -m).any()), bool((v > m).any())
        sub = DIVERGING[measure]
    else:
        norm, cmap = Normalize(lo, hi, clip=True), _cmap(SEQ, "seq")
        us = None if measure.startswith("share_of_us") else _us_value(sp, measure, year)
        sub = "Darker = higher." + (f" U.S. {fmt.format(us)}" if us is not None else "")
    fig, ax = _fig()
    _draw(ax, v, cmap, norm, fmt)
    _title(fig, f"{title}, {year}", sub)
    _legend(fig, ax, cmap, norm, fmt, clo, chi)
    _footer(fig, _note(measure) + SOURCE)
    if path:
        _save(fig, path)
    return fig


def change_map(sp: pd.DataFrame, measure: str, y0: int, y1: int, pct: bool = True, path=None):
    """Diverging map of change between two years (percent change, or points for % measures)."""
    from matplotlib.colors import TwoSlopeNorm
    title, unit, fmt = MEASURES[measure]
    a = sp[(sp.measure == measure) & (sp.year == y0)].set_index("state").value
    b = sp[(sp.measure == measure) & (sp.year == y1)].set_index("state").value
    points = unit == "%"
    ch = (b - a) if points or not pct else 100 * (b / a - 1)
    ch = ch.dropna()
    lab = "{:+.1f} pts" if points else "{:+.0f}%"
    m = max(abs(ch.quantile(0.05)), abs(ch.quantile(0.95)), 1e-9)
    norm = TwoSlopeNorm(vmin=-m, vcenter=0, vmax=m)
    cmap = _cmap(DIV, "div")
    fig, ax = _fig()
    ch = ch[ch.index != "US"]
    _draw(ax, ch, cmap, norm, lab)
    usa, usb = _us_value(sp, measure, y0), _us_value(sp, measure, y1)
    sub = "Blue = increase, red = decrease, gray = no change."
    if usa is not None and usb is not None:
        usch = (usb - usa) if points else 100 * (usb / usa - 1)
        sub += f" U.S. {lab.format(usch)}"
    _title(fig, f"{title}: change {y0} to {y1}", sub)
    _legend(fig, ax, cmap, norm, lab, bool((ch < -m).any()), bool((ch > m).any()))
    note = _note(measure)
    if unit == f"{REAL_BASE} $":
        note += f"Change in constant {REAL_BASE} dollars.\n"
    _footer(fig, note + SOURCE)
    if path:
        _save(fig, path)
    return fig


def map_grid(sp: pd.DataFrame, measure: str, years: list[int], path=None):
    """Small multiples on one shared scale, to see how the map moves over time."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    title, unit, fmt = MEASURES[measure]
    sub = sp[(sp.measure == measure) & sp.year.isin(years) & (sp.state != "US")]
    years = [y for y in years if (sub.year == y).any()]
    lo, hi, clo, chi = _limits(sub.value, True)
    norm, cmap = Normalize(lo, hi, clip=True), _cmap(SEQ, "seq")
    ncol = 2 if len(years) > 1 else 1
    nrow = math.ceil(len(years) / ncol)
    _style()
    fig, axes = plt.subplots(nrow, ncol, figsize=(7.2, 2.35 * nrow + 0.8), dpi=DPI, squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    for ax, y in zip(axes.flat, years):
        ax.set_facecolor(SURFACE)
        _draw(ax, sub[sub.year == y].set_index("state").value, cmap, norm, fmt, label_values=False, fontsize=6)
        ax.set_title(str(y), fontsize=9, color=INK, loc="left", pad=1)
    for ax in list(axes.flat)[len(years):]:
        ax.axis("off")
    fig.subplots_adjust(top=0.86, bottom=0.08, hspace=0.08, wspace=0.04)
    _title(fig, title, "Same color scale in every panel. Darker = higher.")
    _legend(fig, axes.flat[0], cmap, norm, fmt, clo, chi)
    _footer(fig, _note(measure) + SOURCE)
    if path:
        _save(fig, path)
    return fig


def _us_value(sp, measure, year):
    """National value where it can be formed from the state values (sums only for counts)."""
    if measure == "enroll_total":
        x = sp[(sp.measure == measure) & (sp.year == year)].value
        return x.sum() if len(x) else None
    nat = sp[(sp.measure == measure) & (sp.year == year) & (sp.state == "US")].value
    return nat.iloc[0] if len(nat) else None


def national(sp: pd.DataFrame) -> pd.DataFrame:
    """Add state = "US" rows: the same measures computed for the whole country (re-run build
    on a single pseudo-state) so maps can show the national figure."""
    import ipeds_clean.states as S
    orig = S._universe

    def us_universe():
        d = orig()
        d["state"] = "US"
        return d
    S._universe = us_universe
    try:
        us = S.build()
    finally:
        S._universe = orig
    us = us[us.state == "US"]
    return pd.concat([sp[sp.state != "US"], us], ignore_index=True)


STANDARD = [  # (kind, measure, year(s)) for python -m ipeds_clean.states
    ("map", "approp_per_fte", 2024), ("change", "approp_per_fte", 2008, 2024),
    ("map", "tuition_reliance_pub", 2024),
    ("map", "tuition_pub4_instate", 2023), ("change", "tuition_pub4_instate", 2008, 2023),
    ("map", "enroll_total", 2023), ("change", "enroll_total", 2010, 2023),
    ("map", "share_forprofit", 2010), ("map", "share_online_only", 2023),
    ("grid", "share_online_only", [2012, 2016, 2020, 2023]),
    ("map", "grad_rate_bach6", 2024), ("map", "grad_rate_2yr", 2024),
    ("map", "instate_share_ft", 2024), ("map", "net_migration_ft", 2024),
    ("map", "faculty_salary", 2024), ("map", "bach_per_100_ug", 2024),
    # international talent and field mix (follows the 2026 US Talent Report, ch. 1-2)
    ("map", "intl_share_stem_master", 2025), ("change", "intl_share_stem_master", 2015, 2025),
    ("grid", "intl_share_stem_master", [1995, 2005, 2015, 2025]),
    ("map", "intl_share_cs_master", 2025), ("map", "intl_share_eng_master", 2025),
    ("map", "intl_share_math_master", 2025), ("map", "intl_share_stem_doc", 2025),
    ("map", "intl_share_stem_bach", 2025), ("map", "share_of_us_intl_stem_master", 2025),
    ("map", "intl_share_enroll_grad", 2024), ("map", "foreign_share_ft", 2024),
    ("map", "stem_share_bach", 2025), ("map", "stem_master_per_doc", 2025),
    ("map", "field_share_cs_bach", 2025), ("change", "field_share_cs_bach", 2015, 2025),
    ("map", "field_share_eng_bach", 2025), ("map", "field_share_cs_master", 2025),
    ("map", "field_share_bio_bach", 2025), ("map", "field_share_math_bach", 2025),
]


def _latest(sp, measure, year):
    ys = sorted(sp[sp.measure == measure].year.unique())
    return year if year in ys else max([y for y in ys if y <= year] or ys)


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "figures").mkdir(exist_ok=True)
    sp = national(build())
    sp.to_csv(DEST / "state_panel.csv", index=False)
    cov = sp[sp.state != "US"].groupby("measure").agg(years=("year", lambda y: f"{y.min()}-{y.max()}"),
                                                      n_years=("year", "nunique"), states=("state", "nunique"))
    print(cov.to_string())
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    only = set(sys.argv[1:])
    for spec in STANDARD:
        kind, m = spec[0], spec[1]
        if only and m not in only:
            continue
        if kind == "map":
            y = _latest(sp, m, spec[2])
            p = DEST / "figures" / "png" / f"{m}_{y}.png"
            tile_map(sp, m, y, path=p)
        elif kind == "change":
            y0, y1 = _latest(sp, m, spec[2]), _latest(sp, m, spec[3])
            p = DEST / "figures" / "png" / f"{m}_change_{y0}_{y1}.png"
            change_map(sp, m, y0, y1, path=p)
        else:
            p = DEST / "figures" / "png" / f"{m}_grid.png"
            map_grid(sp, m, spec[2], path=p)
        plt.close("all")
        print("wrote", p.relative_to(DATA.parent))
    for y in (2010, 2023):
        wide(sp[sp.state != "US"], y).round(1).to_csv(DEST / f"state_table_{y}.csv")
