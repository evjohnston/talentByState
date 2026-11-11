"""Compare national totals from the harmonized panels with the published Digest tables.

    python -m ipeds_clean.harmonize.digest_benchmarks     # -> data/ipeds/harmonized/qa_digest.csv

Universe used for the panel side (the Digest's): degree-granting institutions in the 50 states and
DC (fips <= 56); from 1996 on, also Title IV participating (directory.title_iv). Before 1996 the
Digest covers "institutions of higher education" (accredited), which degree_granting approximates.

Each benchmark: Digest series (linked across editions), column, the row-label year that maps to
the panel year, and the panel aggregate. The Digest value is taken from the most recent edition
published after the data year (edition > data year), so revisions are used and projections are
not. qa_digest.csv: measure, year, digest_value, digest_edition, digest_table, panel_value,
diff, diff_pct.
"""
from __future__ import annotations

import pandas as pd

from ..config import OUT
from ..digest import load_values

HARM = OUT / "harmonized"

# measure -> (series_id, col_label (exact), panel-year rule, row filter on row_path)
#   "first": panel year = first year of the label (fall 2009 -> 2009; 2010-11 -> 2010)
#   "last":  panel year = last year (2010-11 -> 2011), used for completions
SPECS = {
    "enroll_total":        ("303.10", "Total enrollment", "first", None),
    "enroll_ft":           ("303.10", "Attendance status | Full-time", "first", None),
    "enroll_pt":           ("303.10", "Attendance status | Part-time", "first", None),
    "enroll_men":          ("303.10", "Sex of student | Male", "first", None),
    "enroll_women":        ("303.10", "Sex of student | Female", "first", None),
    "enroll_public":       ("303.10", "Control of institution | Public", "first", None),
    "enroll_nonprofit":    ("303.10", "Control of institution | Private | Nonprofit", "first", None),
    "enroll_forprofit":    ("303.10", "Control of institution | Private | For-profit", "first", None),
    "deg_assoc":           ("318.10", "Associate's degrees | Total", "last", None),
    "deg_bach":            ("318.10", "Bachelor's degrees | Total", "last", None),
    "deg_master":          ("318.10", "Master's degrees | Total", "last", None),
    "deg_doctor":          ("318.10", "Doctor's degrees | Total", "last", None),
    "deg_bach_women":      ("318.10", "Bachelor's degrees | Female", "last", None),
    "inst_total":          ("317.10", "All institutions | Total", "first", r"^Including branch"),
    "inst_public_4yr":     ("317.10", "Public | 4-year", "first", r"^Including branch"),
    "inst_public_2yr":     ("317.10", "Public | 2-year", "first", r"^Including branch"),
    "inst_nonprofit_4yr":  ("317.10", "Private | Nonprofit | 4-year", "first", r"^Including branch"),
    "inst_forprofit_total": ("317.10", "Private | For-profit | Total", "first", r"^Including branch"),
    "salary_avg_all":      ("316.10", "All faculty", "first", r"^(?:Current dollars > )?Total > "),
    "salary_avg_prof":     ("316.10", "Academic rank | Professor", "first", r"^(?:Current dollars > )?Total > "),
}
# Institution counts: the Digest counts institutions that reported fall enrollment, directly or
# through a parent; directory rows with no enrollment that year are not counted.


def digest_side() -> pd.DataFrame:
    out = []
    for measure, (sid, col, rule, rowf) in SPECS.items():
        v = load_values(sid)
        v = v[(v.col_label == col) & v.value.notna() & v.year_first.notna()]
        if rowf:
            v = v[v.row_path.str.contains(rowf, regex=True)]
        v = v.assign(year=(v.year_first if rule == "first" else v.year_last).astype(int))
        v = v[v.edition > v.year_last.astype(int)]                  # published after the data year
        v = v.sort_values("edition").groupby("year").tail(1)
        out.append(pd.DataFrame({"measure": measure, "year": v.year, "digest_value": v.value,
                                 "digest_edition": v.edition, "digest_table": v.table_id}))
    return pd.concat(out, ignore_index=True)


def universe() -> pd.DataFrame:
    d = pd.read_parquet(HARM / "directory.parquet")
    ok = d.degree_granting.fillna(False) & d.fips.le(56).fillna(False)
    ok &= (d.year < 1996) | d.title_iv.fillna(False)
    return d.loc[ok, ["year", "unitid", "control", "level"]]


def panel_side() -> pd.DataFrame:
    u = universe()
    rows = []

    def add(measure, s):
        for y, val in s.items():
            rows.append({"measure": measure, "year": int(y), "panel_value": float(val)})

    e = pd.read_parquet(HARM / "enrollment.parquet").merge(u, on=["year", "unitid"])
    rep = pd.read_parquet(HARM / "reporting.parquet")
    child = rep[(rep.component == "ef") & rep.prch.isin([2, 3, 4, 5])][["year", "unitid"]]
    has_enr = e[e.n > 0][["year", "unitid"]].drop_duplicates()
    active = pd.concat([has_enr, child]).drop_duplicates()
    ua = u.merge(active, on=["year", "unitid"])
    add("enroll_total", e.groupby("year").n.sum())
    add("enroll_ft", e[e.attendance == "ft"].groupby("year").n.sum())
    add("enroll_pt", e[e.attendance == "pt"].groupby("year").n.sum())
    add("enroll_men", e[e.sex == "men"].groupby("year").n.sum())
    add("enroll_women", e[e.sex == "women"].groupby("year").n.sum())
    for k, c in [("public", 1), ("nonprofit", 2), ("forprofit", 3)]:
        add(f"enroll_{k}", e[e.control == c].groupby("year").n.sum())
    del e
    c = pd.read_parquet(HARM / "completions.parquet", columns=["year", "unitid", "award_level", "total", "women"])
    c = c.merge(u, on=["year", "unitid"])
    for k, lv in [("assoc", ["assoc"]), ("bach", ["bach"]), ("master", ["master"]),
                  ("doctor", ["doc_res", "doc_prof"])]:
        add(f"deg_{k}", c[c.award_level.isin(lv)].groupby("year").total.sum())
    add("deg_bach_women", c[c.award_level == "bach"].groupby("year").women.sum())
    del c
    add("inst_total", ua.groupby("year").size())
    add("inst_public_4yr", ua[(ua.control == 1) & (ua.level == 1)].groupby("year").size())
    add("inst_public_2yr", ua[(ua.control == 1) & (ua.level.isin([2, 3]))].groupby("year").size())
    add("inst_nonprofit_4yr", ua[(ua.control == 2) & (ua.level == 1)].groupby("year").size())
    add("inst_forprofit_total", ua[ua.control == 3].groupby("year").size())
    # Digest 316.10: faculty on 9- and 10-month contracts only (not equated 11/12-month), excl.
    # medical schools. 2012-2015 outlays are not split by contract (contract "9_12"), so those
    # years have no comparable panel value.
    s = pd.read_parquet(HARM / "faculty_salaries.parquet").merge(u[["year", "unitid"]], on=["year", "unitid"])
    s = s[s.contract == "9_10"]
    g = s.groupby("year")[["salary_outlay", "n_faculty"]].sum()
    add("salary_avg_all", g.salary_outlay / g.n_faculty)
    p = s[s["rank"] == "prof"].groupby("year")[["salary_outlay", "n_faculty"]].sum()
    add("salary_avg_prof", p.salary_outlay / p.n_faculty)
    return pd.DataFrame(rows)


def build() -> pd.DataFrame:
    q = digest_side().merge(panel_side(), on=["measure", "year"], how="inner")
    q["diff"] = q.panel_value - q.digest_value
    q["diff_pct"] = (100 * q["diff"] / q.digest_value).round(2)
    return q.sort_values(["measure", "year"]).reset_index(drop=True)


if __name__ == "__main__":
    q = build()
    q.to_csv(HARM / "qa_digest.csv", index=False)
    s = q.groupby("measure").agg(years=("year", lambda y: f"{y.min()}-{y.max()} ({len(y)})"),
                                 median_diff_pct=("diff_pct", "median"),
                                 within_1pct=("diff_pct", lambda d: f"{(d.abs() <= 1).mean():.0%}"),
                                 worst_pct=("diff_pct", lambda d: d.loc[d.abs().idxmax()]))
    print(s.to_string())
