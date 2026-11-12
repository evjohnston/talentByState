"""State profile: every IPEDS data point for one state, as an interactive HTML page.

    python -m ipeds_clean.state_profile CA          # -> data/states/profiles/CA.html
    python -m ipeds_clean.state_profile CA NY TX
    python -m ipeds_clean.state_profile --all       # every state + DC

The page mixes long time series (state vs U.S.), composition over time (stacked shares),
institution-level bubbles and scatter plots for the latest year, migration flows, the state's
rank on all state-panel measures over time, and an animated all-state bubble chart.

Universe and geography follow ipeds_clean.states: degree-granting institutions (Title IV from
1996), located in the state. Dollars are constant REAL_BASE dollars (BLS CPI-U).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import states as S
from .states_explorer import NAMES, full_panel, kit_css, payload as panel_payload, sig, site_nav

HARM = S.HARM
OUT_DIR = S.DEST / "profiles"
TEMPLATE = Path(__file__).parent / "templates" / "profile.html"

CIP2 = {"01": "Agriculture", "03": "Natural resources", "04": "Architecture", "05": "Area & ethnic studies",
        "09": "Communication", "10": "Communications tech", "11": "Computer & info sciences", "12": "Personal & culinary",
        "13": "Education", "14": "Engineering", "15": "Engineering technology", "16": "Languages",
        "19": "Family & consumer sci.", "22": "Law", "23": "English", "24": "Liberal arts", "25": "Library science",
        "26": "Biological sciences", "27": "Math & statistics", "28": "Military science", "29": "Military technologies",
        "30": "Interdisciplinary", "31": "Parks & recreation", "32": "Basic skills", "33": "Citizenship",
        "34": "Health-related knowledge", "35": "Interpersonal skills", "36": "Leisure", "37": "Personal awareness",
        "38": "Philosophy & religion", "39": "Theology", "40": "Physical sciences", "41": "Science technologies",
        "42": "Psychology", "43": "Security & protective", "44": "Public administration", "45": "Social sciences",
        "46": "Construction trades", "47": "Mechanic & repair", "48": "Precision production", "49": "Transportation",
        "50": "Visual & performing arts", "51": "Health professions", "52": "Business", "53": "High school diplomas",
        "54": "History", "60": "Residency programs", "61": "Medical residencies"}
STEM_GROUP = {"11": "Computer & info sciences", "14": "Engineering & eng. technology", "15": "Engineering & eng. technology", "27": "Math & statistics",
              "26": "Biological sciences", "40": "Physical sciences", "03": "Natural resources & architecture",
              "04": "Natural resources & architecture"}
STEM_GROUPS = ["Computer & info sciences", "Engineering & eng. technology", "Math & statistics", "Biological sciences",
               "Physical sciences", "Natural resources & architecture"]
STEM_MATRIX = ["11", "14", "15", "27", "40", "26", "03", "04", "52", "51", "45", "42", "13", "50", "22", "24"]
SECTORS = ["Public 4-year", "Public 2-year", "Private nonprofit", "For-profit"]
RACE = {"white": "White", "hisp": "Hispanic", "api": "Asian / Pacific Islander", "black": "Black",
        "nonres": "International", "two_more": "Two or more", "aian": "American Indian", "unknown": "Unknown"}
AWARDS = {"assoc": "Associate's", "bach": "Bachelor's", "master": "Master's", "doc_res": "Research doctorate",
          "doc_prof": "Professional doctorate"}
RANKS = {"prof": "Professor", "assoc": "Associate professor", "asst": "Assistant professor",
         "instr": "Instructor", "lect": "Lecturer", "norank": "No rank"}


def sector(u: pd.DataFrame) -> pd.Series:
    c, lv = u.control.astype("float"), u.level.astype("float")
    return np.select([((c == 1) & (lv == 1)).to_numpy(bool), (c == 1).to_numpy(bool), (c == 2).to_numpy(bool)],
                     SECTORS[:3], SECTORS[3])


def universe() -> pd.DataFrame:
    u = S._universe()
    u["sector"] = sector(u)
    return u


def series(s: pd.Series) -> dict:
    """{year: value} -> {"y": [...], "v": [...]} with rounded values."""
    s = s.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    return {"y": [int(y) for y in s.index], "v": [sig(float(x)) for x in s.values]}


def frame(df: pd.DataFrame) -> dict:
    """year x category frame -> {"y": [...], "k": [...], "v": [[...]...]} (rows = categories)."""
    df = df.sort_index().fillna(0)
    return {"y": [int(y) for y in df.index], "k": [str(c) for c in df.columns],
            "v": [[sig(float(x)) for x in df[c].values] for c in df.columns]}


class Panels:
    """Loads each harmonized panel once and keeps state + national aggregates."""

    def __init__(self):
        self.u = universe()
        self.real = S._cpi()
        d = pd.read_parquet(HARM / "directory.parquet", columns=["year", "unitid", "instnm", "city"])
        self.names = d.sort_values("year").groupby("unitid").last()[["instnm", "city"]]

    # -------------------------------------------------------------- loaders (cached)
    def _get(self, attr, fn):
        if not hasattr(self, attr):
            setattr(self, attr, fn())
        return getattr(self, attr)

    def enroll(self):
        def f():
            e = pd.read_parquet(HARM / "enrollment.parquet", columns=["year", "unitid", "level", "attendance", "race", "n"])
            e = e.merge(self.u[["year", "unitid", "state", "sector"]], on=["year", "unitid"])
            e["lv"] = np.where(e.level == "ug", "Undergraduate", np.where(e.level.isin(["grad", "first_prof"]), "Graduate", "Other"))
            return e
        return self._get("_e", f)

    def completions(self):
        def f():
            c = pd.read_parquet(HARM / "completions.parquet", columns=["year", "unitid", "award_level", "total"],
                                filters=[("award_level", "in", list(AWARDS))])
            c = c.merge(self.u[["year", "unitid", "state"]], on=["year", "unitid"])
            return c.groupby(["state", "year", "unitid", "award_level"], observed=True).total.sum().reset_index()
        return self._get("_c", f)

    def comp_race(self):
        def f():
            c = pd.read_parquet(HARM / "completions_race.parquet", columns=["year", "unitid", "award_level", "cip2020_2", "race", "n"],
                                filters=[("award_level", "in", ["bach", "master", "doc_res"])])
            c = c.merge(self.u[["year", "unitid", "state"]], on=["year", "unitid"])
            c["intl"] = c.race == "nonres"
            return c.groupby(["state", "year", "unitid", "award_level", "cip2020_2", "intl"], observed=True).n.sum().reset_index()
        return self._get("_cr", f)

    # -------------------------------------------------------------- sections
    def institutions(self, st):
        u = self.u
        x = u[u.state == st].groupby(["year", "sector"]).unitid.nunique().unstack().reindex(columns=SECTORS)
        return {"sectors": frame(x)}

    def students(self, st):
        e = self.enroll()
        es, eu = e[e.state == st], e
        lv = es[es.lv != "Other"].groupby(["year", "lv"]).n.sum().unstack()[["Undergraduate", "Graduate"]]
        sec = es.groupby(["year", "sector"]).n.sum().unstack().reindex(columns=SECTORS)
        race = es.groupby(["year", "race"], observed=True).n.sum().unstack()
        race = race.drop(columns=[c for c in ["not_collected"] if c in race]).reindex(columns=list(RACE)).rename(columns=RACE)
        race_us = eu.groupby(["year", "race"], observed=True).n.sum().unstack().reindex(columns=list(RACE)).rename(columns=RACE)
        pt = 100 * es[es.attendance == "pt"].groupby("year").n.sum() / es.groupby("year").n.sum()
        pt_us = 100 * eu[eu.attendance == "pt"].groupby("year").n.sum() / eu.groupby("year").n.sum()
        tot = es.groupby("year").n.sum()
        share_us = 100 * tot / eu.groupby("year").n.sum()
        return {"level": frame(lv), "sector": frame(sec), "race": frame(race), "race_us": frame(race_us),
                "parttime": series(pt), "parttime_us": series(pt_us), "share_of_us": series(share_us)}

    def international(self, st):
        e = self.enroll()
        collected = e[e.race == "nonres"].groupby("year").n.sum()
        e = e[e.year.isin(collected[collected > 0].index)]
        out = {}
        for lv in ("Undergraduate", "Graduate"):
            x = e[e.lv == lv]
            for tag, d in (("st", x[x.state == st]), ("us", x)):
                tot = d.groupby("year").n.sum()
                nr = d[d.race == "nonres"].groupby("year").n.sum()
                out[f"enroll_{lv[:4].lower()}_{tag}"] = series(100 * nr / tot)
                if tag == "st":
                    out[f"enroll_{lv[:4].lower()}_n"] = series(nr)
        cr = self.comp_race()
        stem = cr.cip2020_2.isin(S.STEM_CIP2)
        for lv in ("bach", "master", "doc_res"):
            x = cr[(cr.award_level == lv)]
            for tag, d in (("st", x[x.state == st]), ("us", x)):
                g = d.groupby(["year", "intl"]).n.sum().unstack(fill_value=0)
                out[f"deg_{lv}_{tag}"] = series(100 * g[True] / g.sum(axis=1))
            xs = x[stem.loc[x.index] & (x.state == st)]
            out[f"stem_{lv}_n"] = series(xs[xs.intl].groupby("year").n.sum())
        # international share by field, latest year, state vs U.S. (master's and research doctorates)
        y = int(cr.year.max())
        fields = {}
        for lv in ("master", "doc_res"):
            x = cr[(cr.award_level == lv) & (cr.year == y)]
            rows = []
            for code, d in x.groupby("cip2020_2"):
                ds = d[d.state == st]
                ts, tu = ds.n.sum(), d.n.sum()
                if ts < 50:
                    continue
                rows.append({"cip": code, "name": CIP2.get(code, code), "n": int(ts),
                             "st": sig(100 * ds[ds.intl].n.sum() / ts), "us": sig(100 * d[d.intl].n.sum() / tu)})
            fields[lv] = sorted(rows, key=lambda r: -r["st"])[:16]
        out["by_field"] = fields
        out["by_field_year"] = y
        return out

    def degrees(self, st):
        c = self.completions()
        cs = c[c.state == st]
        aw = cs.groupby(["year", "award_level"], observed=True).total.sum().unstack().reindex(columns=list(AWARDS)).rename(columns=AWARDS)
        cr = self.comp_race()
        out = {"awards": frame(aw), "fields": {}, "lq": {}}
        y = int(cr.year.max())
        for lv in ("bach", "master", "doc_res"):
            x = cr[cr.award_level == lv]
            xs = x[x.state == st]
            g = xs.groupby(["year", "cip2020_2"]).n.sum().unstack(fill_value=0)
            top = g.loc[g.index.max()].sort_values(ascending=False).index[:8].tolist()
            share = 100 * g[top].div(g.sum(axis=1), axis=0)
            share["Other fields"] = 100 - share.sum(axis=1)
            share.columns = [CIP2.get(c, c) if c != "Other fields" else c for c in share.columns]
            out["fields"][lv] = frame(share)
            # concentration vs U.S. (location quotient), latest year
            a = xs[xs.year == y].groupby("cip2020_2").n.sum()
            b = x[x.year == y].groupby("cip2020_2").n.sum()
            sa, sb = 100 * a / a.sum(), 100 * b / b.sum()
            rows = [{"name": CIP2.get(k, k), "st": sig(sa[k]), "us": sig(sb.get(k, np.nan)), "lq": sig(sa[k] / sb[k]), "n": int(a[k])}
                    for k in a.index if a[k] >= 100 and sb.get(k, 0) > 0]
            out["lq"][lv] = sorted(rows, key=lambda r: -r["lq"])
        out["lq_year"] = y
        return out

    def prices(self, st):
        p = pd.read_parquet(HARM / "prices.parquet", columns=["unitid", "ay", "ug_tf_in_state", "ug_tf_out_state", "room_board"])
        p = p.rename(columns={"ay": "year"}).merge(self.u, on=["year", "unitid"])
        e = self.enroll()
        ug = e[e.lv == "Undergraduate"].groupby(["year", "unitid"]).n.sum().rename("ug").reset_index()
        p = p.merge(ug, on=["year", "unitid"])
        p = p[p.ug > 0]
        out = {}
        for col in ("ug_tf_in_state", "ug_tf_out_state"):
            d = p.dropna(subset=[col]).copy()
            d["w"] = d[col] * d.ug
            for tag, x in (("st", d[d.state == st]), ("us", d)):
                g = x.groupby(["year", "sector"])[["w", "ug"]].sum()
                t = (g.w / g.ug).unstack().reindex(columns=SECTORS)
                t = t.mul(t.index.map(self.real), axis=0)
                out[f"{col}_{tag}"] = frame(t.dropna(how="all"))
        return out

    def finance(self, st):
        f = pd.read_parquet(HARM / "finance.parquet", columns=["year", "unitid", "tuition_net", "state_approp", "local_approp",
                                                                  "fed_grants", "fed_approp", "private_gifts_grants", "auxiliary"])
        f = f.merge(self.u[self.u.control == 1], on=["year", "unitid"])
        fte = pd.read_parquet(HARM / "fte.parquet", columns=["year", "unitid", "fall_fte_total"])
        fte["year"] += 1
        f = f.merge(fte, on=["year", "unitid"])
        f = f[f.fall_fte_total > 0]
        f["federal"] = f.fed_grants.fillna(0) + f.fed_approp.fillna(0)
        cols = {"tuition_net": "Net tuition", "state_approp": "State appropriations", "local_approp": "Local appropriations",
                "federal": "Federal grants & appropriations", "private_gifts_grants": "Private gifts & grants"}
        out = {}
        for tag, x in (("st", f[f.state == st]), ("us", f)):
            g = x.groupby("year")[list(cols) + ["fall_fte_total"]].sum()
            per = g[list(cols)].div(g.fall_fte_total, axis=0).mul(g.index.map(self.real), axis=0).rename(columns=cols)
            out[tag] = frame(per)
        return out

    def outcomes(self, st):
        gr = pd.read_parquet(HARM / "grad_rates.parquet", columns=["year", "unitid", "cohort", "measure", "race", "n"],
                             filters=[("cohort", "in", ["ba4", "c2yr"])])
        gr = gr.merge(self.u[["year", "unitid", "state", "sector"]], on=["year", "unitid"])
        out = {}
        g = gr.groupby(["state", "year", "cohort", "sector", "measure"]).n.sum().unstack("measure")
        ba = g.xs("ba4", level="cohort")
        rate = (100 * ba.comp150_bach / ba.adj_cohort)
        out["bach6_by_sector"] = frame(rate.xs(st, level="state").unstack().reindex(columns=SECTORS[:1] + SECTORS[2:]).dropna(how="all", axis=1))
        tot = gr[gr.cohort == "ba4"].groupby(["state", "year", "measure"]).n.sum().unstack("measure")
        r_all = 100 * tot.comp150_bach / tot.adj_cohort
        us = gr[gr.cohort == "ba4"].groupby(["year", "measure"]).n.sum().unstack()
        out["bach6_st"], out["bach6_us"] = series(r_all.xs(st)), series(100 * us.comp150_bach / us.adj_cohort)
        # by race, latest year
        y = int(gr.year.max())
        x = gr[(gr.cohort == "ba4") & (gr.year == y)]
        rows = []
        for race, lab in RACE.items():
            a, b = x[(x.state == st) & (x.race == race)], x[x.race == race]
            A = a.groupby("measure").n.sum(); B = b.groupby("measure").n.sum()
            if A.get("adj_cohort", 0) >= 100:
                rows.append({"name": lab, "st": sig(100 * A.comp150_bach / A.adj_cohort), "us": sig(100 * B.comp150_bach / B.adj_cohort),
                             "n": int(A.adj_cohort)})
        out["bach6_race"], out["race_year"] = rows, y
        two = gr[gr.cohort == "c2yr"]
        a = two[two.state == st].groupby(["year", "measure"]).n.sum().unstack()
        b = two.groupby(["year", "measure"]).n.sum().unstack()
        out["two_st"], out["two_us"] = series(100 * a.comp150 / a.adj_cohort), series(100 * b.comp150 / b.adj_cohort)
        return out

    def faculty(self, st):
        sal = pd.read_parquet(HARM / "faculty_salaries.parquet", columns=["year", "unitid", "rank", "contract", "n_faculty", "salary_outlay"])
        sal = sal[sal.contract == "9_10"].merge(self.u[["year", "unitid", "state"]], on=["year", "unitid"])
        g = sal[sal.state == st].groupby(["year", "rank"], observed=True)[["salary_outlay", "n_faculty"]].sum()
        r = (g.salary_outlay / g.n_faculty).unstack()
        r = r.reindex(columns=[k for k in ["prof", "assoc", "asst", "instr", "lect"] if k in r]).rename(columns=RANKS)
        r = r.mul(r.index.map(self.real), axis=0)
        a = sal[sal.state == st].groupby("year")[["salary_outlay", "n_faculty"]].sum()
        b = sal.groupby("year")[["salary_outlay", "n_faculty"]].sum()
        ra = a.salary_outlay / a.n_faculty * a.index.map(self.real)
        rb = b.salary_outlay / b.n_faculty * b.index.map(self.real)
        st_ = pd.read_parquet(HARM / "staff.parquet", columns=["year", "unitid", "category", "attendance", "n"])
        st_ = st_[st_.category.isin(["instr_tenured", "instr_tenure_track", "instr_not_tenure_track", "instr_no_faculty_status"])]
        st_ = st_[st_.attendance.isin(["ft", "all", "total"]) | st_.attendance.isna()] if "ft" in set(st_.attendance.dropna()) else st_
        st_ = st_.merge(self.u[["year", "unitid", "state"]], on=["year", "unitid"])
        t = st_[st_.state == st].groupby(["year", "category"]).n.sum().unstack()
        lab = {"instr_tenured": "Tenured", "instr_tenure_track": "On tenure track", "instr_not_tenure_track": "Not on tenure track",
               "instr_no_faculty_status": "No faculty status"}
        t = t.reindex(columns=list(lab)).rename(columns=lab)
        return {"by_rank": frame(r.dropna(how="all")), "avg_st": series(ra), "avg_us": series(rb),
                "tenure": frame(t.dropna(how="all"))}

    def migration(self, st):
        r = pd.read_parquet(HARM / "residence.parquet", columns=["year", "unitid", "state_code", "first_time"])
        r = r[r.year.isin(S.residence_years(r))]
        r = r.merge(self.u[["year", "unitid", "state"]], on=["year", "unitid"])
        r["home"] = pd.to_numeric(r.state_code, errors="coerce").map(S.ABBR)
        r.loc[pd.to_numeric(r.state_code, errors="coerce").isin(S.FOREIGN_CODES), "home"] = "Abroad"
        y = int(r.year.max())
        x = r[r.year == y]
        inflow = x[(x.state == st) & (x.home != st) & x.home.notna()].groupby("home").first_time.sum().sort_values(ascending=False)
        outflow = x[(x.home == st) & (x.state != st)].groupby("state").first_time.sum().sort_values(ascending=False)
        stay = x[(x.state == st) & (x.home == st)].first_time.sum()
        per = r[r.state == st].groupby(["year"]).first_time.sum()
        ins = r[(r.state == st) & (r.home == st)].groupby("year").first_time.sum()
        arr = r[(r.state == st) & (r.home != st) & r.home.notna() & (r.home != "Abroad")].groupby("year").first_time.sum()
        lea = r[(r.home == st) & (r.state != st)].groupby("year").first_time.sum()
        nm = lambda k: NAMES.get(k, k)
        return {"year": y, "stay": int(stay),
                "in": [{"k": k, "name": nm(k), "n": int(v)} for k, v in inflow.head(12).items()],
                "out": [{"k": k, "name": nm(k), "n": int(v)} for k, v in outflow.head(12).items()],
                "in_total": int(inflow.sum()), "out_total": int(outflow.sum()),
                "flows": frame(pd.DataFrame({"Stayed in state": ins, "Arrived from other states": arr, "Left for other states": lea}).dropna())}

    # -------------------------------------------------------------- talent: international x STEM
    def comp_detail(self):
        """State-level completions by level x 2-digit field x race x sex (bach, master, research doctorate)."""
        def f():
            c = pd.read_parquet(HARM / "completions_race.parquet", columns=["year", "unitid", "award_level", "cip2020_2", "race", "sex", "n"],
                                filters=[("award_level", "in", ["bach", "master", "doc_res"])])
            c = c.merge(self.u[["year", "unitid", "state", "sector"]], on=["year", "unitid"])
            c["race"] = c.race.astype(str)
            c["sex"] = c.sex.astype(str)
            return c.groupby(["state", "year", "award_level", "cip2020_2", "race", "sex", "sector"], observed=True).n.sum().reset_index()
        return self._get("_cd", f)

    def talent(self, st):
        c = self.comp_detail()
        c = c.assign(stem=c.cip2020_2.isin(S.STEM_CIP2), intl=c.race == "nonres",
                     grp=c.cip2020_2.map(STEM_GROUP).fillna("Other fields"))
        LV = ("bach", "master", "doc_res")
        y1 = int(c.year.max())
        y0 = 2015
        out = {"y1": y1, "y0": y0, "levels": {}}
        for lv in LV:
            x = c[c.award_level == lv]
            xs = x[x.state == st]
            d = {}
            # counts: STEM / other x international / domestic
            def four(z):
                g = z.groupby(["year", "stem", "intl"]).n.sum().unstack(["stem", "intl"], fill_value=0)
                col = lambda a, b: g[(a, b)] if (a, b) in g.columns else 0 * g.iloc[:, 0]
                return pd.DataFrame({"Domestic STEM": col(True, False), "International STEM": col(True, True),
                                     "Domestic, other fields": col(False, False), "International, other fields": col(False, True)})
            fs, fu = four(xs), four(x)
            d["four"] = frame(fs)
            for tag, f4 in (("st", fs), ("us", fu)):
                stem = f4["Domestic STEM"] + f4["International STEM"]
                oth = f4["Domestic, other fields"] + f4["International, other fields"]
                d[f"intl_stem_{tag}"] = series(100 * f4["International STEM"] / stem)
                d[f"intl_other_{tag}"] = series(100 * f4["International, other fields"] / oth)
                d[f"stem_share_{tag}"] = series(100 * stem / (stem + oth))
                d[f"stem_n_{tag}"] = series(stem)
            d["share_of_us_stem"] = series(100 * (fs["Domestic STEM"] + fs["International STEM"]) / (fu["Domestic STEM"] + fu["International STEM"]))
            d["share_of_us_intl_stem"] = series(100 * fs["International STEM"] / fu["International STEM"])
            d["share_of_us_dom_stem"] = series(100 * fs["Domestic STEM"] / fu["Domestic STEM"])
            # STEM by field group, all and international only
            sg = xs[xs.stem].groupby(["year", "grp"]).n.sum().unstack(fill_value=0).reindex(columns=STEM_GROUPS, fill_value=0)
            si = xs[xs.stem & xs.intl].groupby(["year", "grp"]).n.sum().unstack(fill_value=0).reindex(columns=STEM_GROUPS, fill_value=0)
            d["stem_fields"], d["intl_stem_fields"] = frame(sg), frame(si)
            # international STEM by sector
            sec = xs[xs.stem & xs.intl].groupby(["year", "sector"]).n.sum().unstack(fill_value=0).reindex(columns=SECTORS, fill_value=0)
            d["intl_stem_sector"] = frame(sec)
            # women's share of STEM degrees, international vs domestic
            for tag, z in (("st", xs[xs.stem]), ("us", x[x.stem])):
                for who, zz in (("intl", z[z.intl]), ("dom", z[~z.intl])):
                    g = zz.groupby(["year", "sex"]).n.sum().unstack(fill_value=0)
                    if "women" in g:
                        d[f"women_{who}_{tag}"] = series(100 * g["women"] / g.sum(axis=1))
            # race/ethnicity of STEM graduates, latest year
            rows = []
            a = xs[xs.stem & (xs.year == y1)].groupby("race").n.sum()
            b = x[x.stem & (x.year == y1)].groupby("race").n.sum()
            for r_, lab in RACE.items():
                if a.sum() and r_ in a.index:
                    rows.append({"name": lab, "st": sig(100 * a[r_] / a.sum()), "us": sig(100 * b.get(r_, 0) / b.sum()), "n": int(a[r_])})
            d["stem_race"] = rows
            # growth decomposition, y0 -> y1
            g0 = fs.loc[y0] if y0 in fs.index else None
            if g0 is not None:
                g1 = fs.loc[y1]
                d["growth"] = {k: int(g1[k] - g0[k]) for k in fs.columns} | {f"{k}_0": int(g0[k]) for k in fs.columns} | {f"{k}_1": int(g1[k]) for k in fs.columns}
                # by STEM field: change in domestic and international counts
                h = xs[xs.stem & xs.year.isin([y0, y1])].groupby(["grp", "intl", "year"]).n.sum().unstack("year", fill_value=0)
                rows = []
                for gname in STEM_GROUPS:
                    def ch(flag):
                        k = (gname, flag)
                        return int(h.loc[k, y1] - h.loc[k, y0]) if k in h.index else 0
                    rows.append({"name": gname, "dom": ch(False), "intl": ch(True)})
                d["growth_fields"] = rows
            # field map: every 2-digit family with 50+ degrees in the latest year
            fm = []
            a = xs[xs.year == y1].groupby(["cip2020_2", "intl"]).n.sum().unstack(fill_value=0)
            b = x[x.year == y1].groupby(["cip2020_2", "intl"]).n.sum().unstack(fill_value=0)
            a0 = xs[xs.year == y0].groupby("cip2020_2").n.sum()
            tot = a.sum().sum()
            for k, r_ in a.iterrows():
                n = r_.sum()
                if n < 50:
                    continue
                bi = b.loc[k] if k in b.index else None
                fm.append({"cip": k, "name": CIP2.get(k, k), "n": int(n), "share": sig(100 * n / tot),
                           "intl": sig(100 * r_.get(True, 0) / n), "us": sig(100 * bi.get(True, 0) / bi.sum()) if bi is not None and bi.sum() else None,
                           "stem": k in S.STEM_CIP2, "growth": sig(100 * (n / a0[k] - 1)) if k in a0.index and a0[k] >= 20 else None})
            d["field_map"] = sorted(fm, key=lambda r: -r["n"])
            out["levels"][lv] = d
        # pipeline ratios (same-year counts)
        for tag, z in (("st", c[c.state == st]), ("us", c)):
            g = z[z.stem].groupby(["year", "award_level"]).n.sum().unstack()
            out[f"ms_per_ba_{tag}"] = series(100 * g["master"] / g["bach"])
            out[f"phd_per_ba_{tag}"] = series(100 * g["doc_res"] / g["bach"])
        # dependency matrix: international share by field x level, latest year
        mat = []
        for k in STEM_MATRIX:
            row = {"cip": k, "name": CIP2.get(k, k), "stem": k in S.STEM_CIP2}
            for lv in LV:
                x = c[(c.award_level == lv) & (c.year == y1) & (c.cip2020_2 == k)]
                xs = x[x.state == st]
                ns, nu = xs.n.sum(), x.n.sum()
                row[lv] = {"st": sig(100 * xs[xs.intl].n.sum() / ns) if ns >= 20 else None, "us": sig(100 * x[x.intl].n.sum() / nu) if nu else None, "n": int(ns)}
            mat.append(row)
        out["matrix"] = mat
        return out

    def institutions_table(self, st):
        """One row per institution in the state, latest year of each source."""
        u = self.u
        yu = int(u.year.max())
        base = u[(u.state == st) & (u.year == yu)][["unitid", "sector"]].copy()
        e = self.enroll()
        ye = int(e.year.max())
        ee = e[(e.state == st) & (e.year == ye)]
        base = base.merge(ee.groupby("unitid").n.sum().rename("enroll"), on="unitid", how="left")
        g = ee[ee.lv == "Graduate"]
        gi = g.groupby("unitid").n.sum()
        base = base.merge((100 * g[g.race == "nonres"].groupby("unitid").n.sum() / gi[gi >= 50]).rename("intl_grad"), on="unitid", how="left")
        ugr = ee[ee.lv == "Undergraduate"]
        ugt = ugr.groupby("unitid").n.sum()
        base = base.merge((100 * ugr[ugr.race == "nonres"].groupby("unitid").n.sum() / ugt[ugt >= 100]).rename("intl_ug"), on="unitid", how="left")
        cr = self.comp_race()
        yc = int(cr.year.max())
        c = cr[(cr.state == st) & (cr.year == yc)]
        stem = c.cip2020_2.isin(S.STEM_CIP2)
        for lv, tag in (("master", "ms"), ("bach", "ba"), ("doc_res", "phd")):
            x = c[c.award_level == lv]
            base = base.merge(x.groupby("unitid").n.sum().rename(f"{tag}"), on="unitid", how="left")
            base = base.merge(x[x.intl].groupby("unitid").n.sum().rename(f"{tag}_intl"), on="unitid", how="left")
            base = base.merge(x[stem.loc[x.index]].groupby("unitid").n.sum().rename(f"{tag}_stem"), on="unitid", how="left")
            xs = x[stem.loc[x.index] & x.intl]
            base = base.merge(xs.groupby("unitid").n.sum().rename(f"{tag}_stem_intl"), on="unitid", how="left")
        gr = pd.read_parquet(HARM / "grad_rates.parquet", columns=["year", "unitid", "cohort", "measure", "n"],
                             filters=[("cohort", "==", "ba4"), ("measure", "in", ["adj_cohort", "comp150_bach"])])
        yg = int(gr.year.max())
        gg = gr[gr.year == yg].groupby(["unitid", "measure"]).n.sum().unstack()
        gg = gg[gg.adj_cohort >= 50]
        base = base.merge((100 * gg.comp150_bach / gg.adj_cohort).rename("grad6"), on="unitid", how="left")
        p = pd.read_parquet(HARM / "prices.parquet", columns=["unitid", "ay", "ug_tf_in_state", "ug_tf_out_state"])
        yp = int(p.dropna(subset=["ug_tf_in_state"]).ay.max())
        pp = p[p.ay == yp].groupby("unitid")[["ug_tf_in_state", "ug_tf_out_state"]].mean()
        base = base.merge(pp, on="unitid", how="left")
        a = pd.read_parquet(HARM / "admissions.parquet", columns=["year", "unitid", "applcn", "admssn", "enrlt"])
        ya = int(a.year.max())
        aa = a[a.year == ya].set_index("unitid")
        aa = aa[aa.applcn >= 200]
        base = base.merge(pd.DataFrame({"apps": aa.applcn, "admit": 100 * aa.admssn / aa.applcn,
                                        "yield": 100 * aa.enrlt / aa.admssn}), on="unitid", how="left")
        base = base.merge(self.names, left_on="unitid", right_index=True, how="left")
        base = base[base.enroll.fillna(0) > 0].sort_values("enroll", ascending=False)
        cols = [c for c in base.columns if c not in ("unitid", "sector", "instnm", "city")]
        rows = []
        for _, r in base.iterrows():
            d = {"id": int(r.unitid), "name": r.instnm, "city": r.city, "sector": r.sector}
            for k in cols:
                v = r[k]
                if pd.notna(v):
                    d[k] = sig(float(v))
            rows.append(d)
        return {"rows": rows, "years": {"enroll": ye, "completions": yc, "grad": yg, "prices": yp, "admissions": ya, "directory": yu}}


# ---------------------------------------------------------------- flows for the Sankey diagrams
PIPE_GROUPS = STEM_GROUPS + ["Health professions", "Business", "Social sciences & psychology", "Education", "Other fields"]
PIPE_MAP = {**STEM_GROUP, "51": "Health professions", "52": "Business", "45": "Social sciences & psychology",
            "42": "Social sciences & psychology", "13": "Education"}


def pipeline_all(P: "Panels") -> dict:
    """Latest-year degrees by state x level x residency x field group: {year, groups, levels, v: {ST: [[[n]]]}}."""
    c = P.comp_detail()
    y = int(c.year.max())
    x = c[c.year == y].assign(intl=lambda d: d.race == "nonres", grp=lambda d: d.cip2020_2.map(PIPE_MAP).fillna("Other fields"))
    g = x.groupby(["state", "award_level", "intl", "grp"]).n.sum()
    out = {}
    for st in S.TILES:
        out[st] = [[[int(g.get((st, lv, flag, gr), 0)) for gr in PIPE_GROUPS] for flag in (False, True)] for lv in ("bach", "master", "doc_res")]
    return {"year": y, "groups": PIPE_GROUPS, "levels": ["bach", "master", "doc_res"], "v": out}


def flows_all(P: "Panels") -> dict:
    """First-time students by institution state x home state (latest near-complete year)."""
    r = pd.read_parquet(HARM / "residence.parquet", columns=["year", "unitid", "state_code", "first_time"])
    r = r[r.year.isin(S.residence_years(r))]
    y = int(r.year.max())
    r = r[r.year == y].merge(P.u[["year", "unitid", "state"]], on=["year", "unitid"])
    code = pd.to_numeric(r.state_code, errors="coerce")
    r["home"] = code.map(S.ABBR)
    r.loc[code.isin(S.FOREIGN_CODES), "home"] = "XX"
    g = r.dropna(subset=["home"]).groupby(["state", "home"]).first_time.sum()
    homes = list(S.TILES) + ["XX"]
    m = [[int(g.get((st, h), 0)) for h in homes] for st in S.TILES]
    return {"year": y, "states": list(S.TILES), "homes": homes, "m": m}


_SEVIS = None


def sevis(st: str):
    """DHS SEVIS by the Numbers summary for the state (countries of citizenship, STEM by level); None if not built."""
    global _SEVIS
    if _SEVIS is None:
        try:
            from .sevis import state_payloads
            _SEVIS = state_payloads(list(S.TILES))
        except FileNotFoundError:
            _SEVIS = {}
    return _SEVIS.get(st)


_H1B_TOP = None


def h1b_top(st: str, n: int = 10) -> dict | None:
    """The state's largest H-1B petitioners (USCIS Employer Data Hub), latest complete fiscal year."""
    global _H1B_TOP
    if _H1B_TOP is None:
        try:
            t = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "h1b" / "h1b_top_employers.csv")
            f = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "h1b" / "files.csv")
            f = f[f.used.eq("yes")] if "used" in f else f            # superseded files are listed with used = no
            bad = f[f.incomplete_export.astype(bool)].fiscal_year
            t = t[~t.fiscal_year.isin(bad)]
            _H1B_TOP = t[t.fiscal_year == t.fiscal_year.max()]
        except FileNotFoundError:
            _H1B_TOP = pd.DataFrame(columns=["state"])
    t = _H1B_TOP[_H1B_TOP.state == st].head(n)
    if t.empty:
        return None
    return {"fy": int(t.fiscal_year.iloc[0]),
            "rows": [{"n": r.employer.title(), "v": int(r.initial_approved), "c": int(r.continuing_approved)} for r in t.itertuples()]}


def build_state(P: Panels, st: str, panel: dict) -> dict:
    return {"sevis": sevis(st), "h1b_top": h1b_top(st), "state": st, "name": NAMES[st], "built": pd.Timestamp.now().strftime("%Y-%m-%d"), "realBase": S.REAL_BASE,
            "institutions": P.institutions(st), "students": P.students(st), "international": P.international(st),
            "degrees": P.degrees(st), "prices": P.prices(st), "finance": P.finance(st), "outcomes": P.outcomes(st),
            "faculty": P.faculty(st), "talent": P.talent(st), "migration": P.migration(st), "inst": P.institutions_table(st),
            "panel": panel, "online": __import__("ipeds_clean.states_explorer", fromlist=["ONLINE_GIANTS"]).ONLINE_GIANTS.get(st, "")}


def write(states: list[str]) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    P = Panels()
    sp_ = pd.read_csv(S.DEST / "state_panel.csv")
    panel = panel_payload(*full_panel(sp_))
    from .peers import presets
    panel["presets"] = presets(sp_, flows_all(P))
    tpl = TEMPLATE.read_text().replace("/*__KIT__*/", kit_css()).replace("/*__SANKEY__*/", (TEMPLATE.parent / "sankey.js").read_text()).replace("/*__PEERS__*/", (TEMPLATE.parent / "peers.js").read_text()).replace("<!--__SITENAV__-->", site_nav("profiles", "../"))
    paths = []
    for st in states:
        data = build_state(P, st, panel)
        (OUT_DIR / "data").mkdir(exist_ok=True)
        (OUT_DIR / "data" / f"{st}.json").write_text(json.dumps({k: v for k, v in data.items() if k != "panel"}, separators=(",", ":"), allow_nan=False, default=str))
        blob = json.dumps(data, separators=(",", ":"), allow_nan=False, default=str)
        p = OUT_DIR / f"{st}.html"
        p.write_text(tpl.replace("__TITLE__", f"{NAMES[st]} Profile").replace("/*__DATA__*/null", blob.replace("</", "<\\/")))
        paths.append(p)
        print(f"wrote {p} ({p.stat().st_size / 1e6:.1f} MB)")
    return paths


def write_index() -> Path:
    """profiles/index.html: a tile map linking to every state's profile."""
    tiles = "".join(f'<a class="t" href="{st}.html" style="grid-column:{c + 1};grid-row:{r + 1}" title="{NAMES[st]}"><b>{st}</b><span>{NAMES[st]}</span></a>'
                    for st, (c, r) in S.TILES.items())
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>State Talent Profiles</title><style>{kit_css()}
.wrap{{max-width:1100px;margin:0 auto;padding-block:28px 40px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
h1{{margin:0;font-size:32px;font-weight:700}}
p{{font-size:15px;line-height:1.55;color:var(--ink-2);max-width:70ch;margin:8px 0 22px}}
.g{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:5px}}
.t{{aspect-ratio:1;border-radius:3px;background:var(--focus-bg);color:var(--ink);text-decoration:none;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:4px;text-align:center;border:1px solid var(--rule)}}
.t b{{font-size:clamp(13px,1.6vw,19px);font-weight:700}}.t span{{font-size:clamp(8px,.8vw,11px);color:var(--ink-3);margin-top:3px;line-height:1.15}}
.t:hover{{background:var(--accent);color:var(--on-accent);border-color:var(--accent)}}.t:hover span{{color:var(--on-accent)}}
@media (max-width:700px){{.t span{{display:none}}}}
</style></head><body>{site_nav("profiles", "../")}<div class="wrap"><h1>State Talent Profiles</h1>
<p>Every IPEDS data point for each state, read against the competitor states you choose: institutions, students, international and STEM talent, fields, money, outcomes, faculty and migration. Pick a state, or <a href="../sheet.html">compare all states in the sheet</a>.</p>
<p style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn" href="viewer.html">View PDF profiles</a><a class="btn primary" href="pdf/State_Talent_Profiles_all_states.zip" download title="Two-page spreads, for reading on screen">Download all PDFs: digital (zip)</a><a class="btn" href="pdf/State_Talent_Profiles_all_states_print.zip" download title="Single 8.5 x 11 in pages in booklet order, for printing">Download all PDFs: print (zip)</a></p>
<nav class="g" aria-label="States">{tiles}</nav></div></body></html>"""
    path = OUT_DIR / "index.html"
    path.write_text(html)
    return path


if __name__ == "__main__":
    args = sys.argv[1:] or ["CA"]
    write(list(S.TILES) if args == ["--all"] else [a.upper() for a in args])
    print("wrote", write_index())
