"""International Talent: the national view of U.S. nonresident students and graduates, by state.

    python -m ipeds_clean.international      # -> data/states/international.html

IPEDS records international students as U.S. nonresidents (temporary visas). It does not record
their country of citizenship; first-time students from abroad are one residence category
("foreign countries"). Flows here therefore run from abroad, degree level and field to the states and
institutions where students enroll and graduate.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import states as S
from .states_explorer import NAMES, kit_css, sig, site_nav

TEMPLATE = Path(__file__).parent / "templates" / "international.html"
OUT_FILE = S.DEST / "international.html"


def series(sp, m, st="US"):
    x = sp[(sp.measure == m) & (sp.state == st)].sort_values("year")
    return {"y": [int(v) for v in x.year], "v": [sig(float(v)) for v in x.value]}


def build_payload() -> dict:
    from .state_profile import Panels, flows_all, pipeline_all, CIP2
    sp = pd.read_csv(S.DEST / "state_panel.csv")
    P = Panels()
    st = list(S.TILES)
    last = lambda m: int(sp[sp.measure == m].year.max())
    def by_state(m, y=None):
        y = y or last(m)
        x = sp[(sp.measure == m) & (sp.year == y) & (sp.state != "US")].set_index("state").value
        return {s: (sig(float(x[s])) if s in x else None) for s in st}
    nat = {k: series(sp, k) for k in ["intl_share_enroll_grad", "intl_share_enroll_ug", "intl_share_bach", "intl_share_master",
                                      "intl_share_doc", "intl_share_stem_bach", "intl_share_stem_master", "intl_share_stem_doc",
                                      "intl_stem_master_count"]}
    # international enrollment counts by state, latest fall
    e = P.enroll()
    ye = int(e.year.max())
    ee = e[(e.year == ye) & (e.race == "nonres") & (e.lv != "Other")]
    enr = ee.groupby(["state", "lv"]).n.sum().unstack(fill_value=0)
    enr_n = {s: {"grad": int(enr.loc[s, "Graduate"]) if s in enr.index else 0, "ug": int(enr.loc[s, "Undergraduate"]) if s in enr.index else 0} for s in st}
    nat_counts = e[(e.race == "nonres") & (e.lv != "Other")].groupby(["year", "lv"]).n.sum().unstack(fill_value=0)
    collected = e[e.race == "nonres"].groupby("year").n.sum()
    nat_counts = nat_counts.loc[collected[collected > 0].index]
    nat["enroll_grad_n"] = {"y": [int(y) for y in nat_counts.index], "v": [int(v) for v in nat_counts["Graduate"]]}
    nat["enroll_ug_n"] = {"y": [int(y) for y in nat_counts.index], "v": [int(v) for v in nat_counts["Undergraduate"]]}
    # top institutions nationally: international STEM master's and doctorates, latest year
    cr = P.comp_race()
    yc = int(cr.year.max())
    x = cr[(cr.year == yc) & cr.intl & cr.cip2020_2.isin(S.STEM_CIP2)]
    inst = []
    for lv, tag in (("master", "ms"), ("doc_res", "phd")):
        g = x[x.award_level == lv].groupby(["unitid", "state"]).n.sum().sort_values(ascending=False).head(25)
        for (u, s), n in g.items():
            nm = P.names.loc[u, "instnm"] if u in P.names.index else str(u)
            inst.append({"lv": tag, "id": int(u), "name": nm, "state": s, "n": int(n)})
    # growth since 2015 in international STEM master's
    cnt = sp[sp.measure == "intl_stem_master_count"]
    g0 = cnt[cnt.year == 2015].set_index("state").value
    g1 = cnt[cnt.year == last("intl_stem_master_count")].set_index("state").value
    growth = {s: {"y0": sig(float(g0.get(s))) if s in g0 else None, "y1": sig(float(g1.get(s))) if s in g1 else None} for s in st}
    trend_states = {s: series(sp, "intl_stem_master_count", s) for s in st}
    return {"built": pd.Timestamp.now().strftime("%Y-%m-%d"), "names": NAMES, "states": st, "tiles": {s: S.TILES[s] for s in st},
            "nat": nat, "pipeline": pipeline_all(P), "flows": flows_all(P), "enroll_year": ye, "enroll_n": enr_n,
            "share": {"intl_share_stem_master": by_state("intl_share_stem_master"), "intl_share_enroll_grad": by_state("intl_share_enroll_grad"),
                      "intl_stem_master_count": by_state("intl_stem_master_count"), "share_of_us_intl_stem_master": by_state("share_of_us_intl_stem_master"),
                      "intl_share_stem_doc": by_state("intl_share_stem_doc")},
            "years": {"stem_master": last("intl_stem_master_count"), "enroll_share": last("intl_share_enroll_grad"), "completions": yc},
            "inst": inst, "growth": growth, "trend_states": trend_states, "online": __import__("ipeds_clean.states_explorer", fromlist=["ONLINE_GIANTS"]).ONLINE_GIANTS}


def build(path: Path = OUT_FILE) -> Path:
    blob = json.dumps(build_payload(), separators=(",", ":"), allow_nan=False, default=str)
    tpl = TEMPLATE.parent
    html = (TEMPLATE.read_text().replace("/*__KIT__*/", kit_css()).replace("<!--__SITENAV__-->", site_nav("international")).replace("/*__SANKEY__*/", (tpl / "sankey.js").read_text())
            .replace("/*__DATA__*/null", blob.replace("</", "<\\/")))
    path.write_text(html)
    return path


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size / 1e6:.1f} MB)")
