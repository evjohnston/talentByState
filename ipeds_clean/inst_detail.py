"""Per-institution detail for the interactive state profiles.

    python -m ipeds_clean.inst_detail          # -> data/states/profiles/data/inst/<ST>.json for every state

Clicking an institution in a profile (a bar, a bubble, or a row in the institution list) opens a panel
fed by these files: directory and Carnegie classification, enrollment and international shares over
time, degrees by level with international and STEM counts, top fields, prices, admissions, retention,
aid, faculty and finance. All IPEDS. Finance is reported in the fiscal year's own dollars.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import states as S
from .state_profile import Panels, CIP2, OUT_DIR, HARM
from .states_explorer import sig

DEST = OUT_DIR / "data" / "inst"


def _f(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)) or pd.isna(v):
        return None
    return sig(float(v))


def ok(v) -> bool:
    return v is not None and not pd.isna(v) and v != 0


def build() -> list:
    P = Panels()
    univ = set(P.u.unitid.unique())
    # directory: first year seen, flags
    d = pd.read_parquet(HARM / "directory.parquet", columns=["year", "unitid", "opeid", "hbcu", "tribal", "title_iv", "city", "stabbr"])
    d = d[d.unitid.isin(univ)]
    first = d.groupby("unitid").year.min()
    dl = d.sort_values("year").groupby("unitid").last()
    cc = pd.read_parquet(HARM / "carnegie.parquet", columns=["unitid", "cc_year", "basic_label", "research_tier"])
    cc = cc[cc.unitid.isin(univ)].sort_values("cc_year").groupby("unitid").last()
    # enrollment series
    e = P.enroll()
    tot = e.groupby(["unitid", "year"]).n.sum()
    lvn = e.groupby(["unitid", "year", "lv"]).n.sum().unstack(fill_value=0)
    nres = e[e.race == "nonres"].groupby(["unitid", "year", "lv"]).n.sum().unstack(fill_value=0)
    collected = e[e.race == "nonres"].groupby("year").n.sum()
    okyrs = set(collected[collected > 0].index)
    # completions
    c = P.comp_race()
    yc = int(c.year.max())
    stem = c.cip2020_2.isin(S.STEM_CIP2)
    c = c.assign(stem=stem)
    clast = c[c.year == yc]
    lv_tab = {}
    for (u, lv), g in clast.groupby(["unitid", "award_level"]):
        lv_tab.setdefault(u, {})[lv] = {"n": _f(g.n.sum()), "intl": _f(g[g.intl].n.sum()), "stem": _f(g[g.stem].n.sum()), "stem_intl": _f(g[g.stem & g.intl].n.sum())}
    fld = clast.groupby(["unitid", "award_level", "cip2020_2"]).apply(lambda g: pd.Series({"n": g.n.sum(), "intl": g[g.intl].n.sum()}), include_groups=False).reset_index()
    ism = c[(c.award_level == "master") & c.stem & c.intl].groupby(["unitid", "year"]).n.sum()
    # other panels, latest year per institution
    def latest(df):
        return df.sort_values("year").groupby("unitid").last()
    fte = latest(pd.read_parquet(HARM / "fte.parquet", columns=["year", "unitid", "fall_fte_total", "fte12_ug_reported", "fte12_grad_reported"]))
    de = pd.read_parquet(HARM / "distance_ed.parquet", columns=["year", "unitid", "efdelev", "efdetot", "efdeexc", "efdesom"])
    de = latest(de[de.efdelev == 1])
    ret = latest(pd.read_parquet(HARM / "retention.parquet", columns=["year", "unitid", "ret_pcf", "stufacr"]))
    aid = latest(pd.read_parquet(HARM / "student_aid.parquet", columns=["year", "unitid", "cohort_ftft", "ug_all_n", "ug_pell_n", "loan_n", "any_grant_avg", "fed_loan_avg"]))
    fs = pd.read_parquet(HARM / "faculty_salaries.parquet", columns=["year", "unitid", "n_faculty", "outlay_eq9"])
    fy = fs.groupby("unitid").year.max()
    fs = fs[fs.year == fs.unitid.map(fy)].groupby("unitid").agg(year=("year", "max"), n=("n_faculty", "sum"), out=("outlay_eq9", "sum"))
    fin = latest(pd.read_parquet(HARM / "finance.parquet", columns=["year", "unitid", "tuition_net", "state_approp", "local_approp", "fed_grants", "private_gifts_grants", "instruction", "research", "total_expenses"]))
    adm = latest(pd.read_parquet(HARM / "admissions.parquet", columns=["year", "unitid", "applcn", "admssn", "enrlt"]))
    pr = pd.read_parquet(HARM / "prices.parquet", columns=["unitid", "ay", "ug_tf_in_state", "ug_tf_out_state"]).dropna(subset=["ug_tf_in_state"])
    pr = pr.sort_values("ay").groupby("unitid").last()
    gr = pd.read_parquet(HARM / "grad_rates.parquet", columns=["year", "unitid", "cohort", "measure", "n"],
                         filters=[("cohort", "==", "ba4"), ("measure", "in", ["adj_cohort", "comp150_bach"])])
    grw = gr.groupby(["unitid", "year", "measure"]).n.sum().unstack()
    out = []
    for st in S.TILES:
        tab = P.institutions_table(st)
        rows = {r["id"]: r for r in tab["rows"]}
        enr_rank = {u: i + 1 for i, u in enumerate(sorted(rows, key=lambda u: -(rows[u].get("enroll") or 0)))}
        ms_rank = {u: i + 1 for i, u in enumerate(sorted(rows, key=lambda u: -(rows[u].get("ms_stem_intl") or 0)))}
        res = {}
        for u, r in rows.items():
            x = {"id": u, "name": r["name"], "city": r.get("city"), "sector": r.get("sector"), "rank_enroll": enr_rank[u], "rank_ms_intl": ms_rank[u] if r.get("ms_stem_intl") else None, "n_state": len(rows)}
            if u in dl.index:
                z = dl.loc[u]
                x.update({"opeid": None if pd.isna(z.opeid) else str(z.opeid), "hbcu": bool(z.hbcu) if pd.notna(z.hbcu) else False, "tribal": bool(z.tribal) if pd.notna(z.tribal) else False, "first_year": int(first.get(u, 0))})
            if u in cc.index:
                x.update({"carnegie": cc.loc[u, "basic_label"], "carnegie_year": int(cc.loc[u, "cc_year"]), "research_tier": cc.loc[u, "research_tier"] if pd.notna(cc.loc[u, "research_tier"]) else None})
            if u in tot.index.get_level_values(0):
                t = tot.loc[u]
                x["enroll_series"] = {"y": [int(y) for y in t.index], "v": [_f(v) for v in t.values]}
                if u in lvn.index.get_level_values(0):
                    L = lvn.loc[u]
                    ys = [y for y in L.index if y in okyrs]
                    g_tot = L.get("Graduate", pd.Series(0, index=L.index))
                    ng = nres.loc[u].get("Graduate", pd.Series(dtype=float)) if u in nres.index.get_level_values(0) else pd.Series(dtype=float)
                    nu = nres.loc[u].get("Undergraduate", pd.Series(dtype=float)) if u in nres.index.get_level_values(0) else pd.Series(dtype=float)
                    u_tot = L.get("Undergraduate", pd.Series(0, index=L.index))
                    x["intl_grad_series"] = {"y": [int(y) for y in ys if g_tot.get(y, 0) >= 50], "v": [_f(100 * ng.get(y, 0) / g_tot[y]) for y in ys if g_tot.get(y, 0) >= 50]}
                    x["intl_ug_series"] = {"y": [int(y) for y in ys if u_tot.get(y, 0) >= 100], "v": [_f(100 * nu.get(y, 0) / u_tot[y]) for y in ys if u_tot.get(y, 0) >= 100]}
                    ly = int(L.index.max())
                    x.update({"ug": _f(u_tot.get(ly)), "grad": _f(g_tot.get(ly)), "enroll_year": ly})
            if u in ism.index.get_level_values(0):
                s = ism.loc[u]
                x["intl_stem_ms_series"] = {"y": [int(y) for y in s.index], "v": [_f(v) for v in s.values]}
            x["degrees"] = lv_tab.get(u, {})
            x["degrees_year"] = yc
            ff = fld[fld.unitid == u]
            x["fields"] = {lv: [{"name": CIP2.get(k, k), "n": _f(g.n), "intl": _f(g.intl), "stem": k in S.STEM_CIP2}
                                for k, g in ff[ff.award_level == lv].sort_values("n", ascending=False).head(8).set_index("cip2020_2").iterrows()]
                           for lv in ("bach", "master", "doc_res")}
            if u in fte.index:
                z = fte.loc[u]; x["fte"] = _f(z.fall_fte_total if pd.notna(z.fall_fte_total) else (z.fte12_ug_reported if ok(z.fte12_ug_reported) else 0) + (z.fte12_grad_reported if ok(z.fte12_grad_reported) else 0)); x["fte_year"] = int(z.year)
            if u in de.index and de.loc[u, "efdetot"]:
                z = de.loc[u]; x.update({"online_excl": _f(100 * z.efdeexc / z.efdetot), "online_some": _f(100 * z.efdesom / z.efdetot), "online_year": int(z.year)})
            if u in ret.index:
                z = ret.loc[u]; x.update({"retention": _f(z.ret_pcf), "stufac": _f(z.stufacr), "retention_year": int(z.year)})
            if u in aid.index:
                z = aid.loc[u]
                x.update({"pell_share": _f(100 * z.ug_pell_n / z.ug_all_n) if ok(z.ug_all_n) else None, "loan_share": _f(100 * z.loan_n / z.cohort_ftft) if ok(z.cohort_ftft) else None,
                          "grant_avg": _f(z.any_grant_avg), "aid_year": int(z.year)})
            if u in fs.index and fs.loc[u, "n"]:
                z = fs.loc[u]; x.update({"faculty_n": _f(z.n), "faculty_salary": _f(z.out / z.n), "faculty_year": int(z.year)})
            if u in fin.index:
                z = fin.loc[u]
                x["finance"] = {k: _f(z[k]) for k in ("tuition_net", "state_approp", "local_approp", "fed_grants", "private_gifts_grants", "instruction", "research", "total_expenses")}
                x["finance_year"] = int(z.year)
            if u in adm.index and adm.loc[u, "applcn"]:
                z = adm.loc[u]; x.update({"apps": _f(z.applcn), "admit": _f(100 * z.admssn / z.applcn) if ok(z.applcn) else None, "yield": _f(100 * z.enrlt / z.admssn) if ok(z.admssn) else None, "adm_year": int(z.year)})
            if u in pr.index:
                z = pr.loc[u]; x.update({"tuition_in": _f(z.ug_tf_in_state), "tuition_out": _f(z.ug_tf_out_state), "price_year": int(z.ay)})
            if u in grw.index.get_level_values(0):
                g = grw.loc[u].dropna()
                g = g[g.adj_cohort >= 30] if "adj_cohort" in g else g.iloc[0:0]
                if len(g):
                    x["grad6_series"] = {"y": [int(y) for y in g.index], "v": [_f(100 * a / b) for a, b in zip(g.comp150_bach, g.adj_cohort)]}
            for k in ("intl_grad", "intl_ug", "grad6", "enroll"):
                if r.get(k) is not None:
                    x[k] = r[k]
            res[str(u)] = x
        DEST.mkdir(parents=True, exist_ok=True)
        p = DEST / f"{st}.json"
        p.write_text(json.dumps(res, separators=(",", ":"), allow_nan=False, default=lambda o: None))
        out.append(p)
        print(st, len(res), f"{p.stat().st_size / 1e3:.0f} kB")
    return out


if __name__ == "__main__":
    build()
