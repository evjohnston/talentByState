"""Suggested competitor sets ("peer sets") for the State Talent Sheet and the state profiles.

    python -m ipeds_clean.peers          # rebuild reference/state_attributes/state_attributes.csv

Most sets come from the IPEDS state panel itself (enrollment, international reliance, STEM focus,
public funding, student exchange). Four use outside, public state attributes only to choose which
states to compare; those attributes are never shown as measures:
  state GDP and population, 2024      FRED series <ST>NGSP and <ST>POP (BEA / Census via FRED)
  2024 presidential vote              MIT Election Data + Science Lab, 2024-elections-official
  Census regions and divisions        U.S. Census Bureau
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .states import DEST, TILES

ROOT = Path(__file__).resolve().parents[1]
ATTR_DIR = ROOT / "reference" / "state_attributes"
RAW = ATTR_DIR / "raw"
ATTR = ATTR_DIR / "state_attributes.csv"

DIVISION = {  # Census division: states
    "New England": "CT ME MA NH RI VT", "Middle Atlantic": "NJ NY PA",
    "East North Central": "IL IN MI OH WI", "West North Central": "IA KS MN MO NE ND SD",
    "South Atlantic": "DE DC FL GA MD NC SC VA WV", "East South Central": "AL KY MS TN",
    "West South Central": "AR LA OK TX", "Mountain": "AZ CO ID MT NV NM UT WY", "Pacific": "AK CA HI OR WA"}
REGION = {"New England": "Northeast", "Middle Atlantic": "Northeast", "East North Central": "Midwest",
          "West North Central": "Midwest", "South Atlantic": "South", "East South Central": "South",
          "West South Central": "South", "Mountain": "West", "Pacific": "West"}


def build_attributes() -> pd.DataFrame:
    rows = []
    v = pd.read_csv(RAW / "medsl_2024_president_state.csv")
    v = v[(v.office == "US PRESIDENT") & (v["mode"].fillna("TOTAL") == "TOTAL") & (v.stage == "GEN")]
    div_of = {s: d for d, ss in DIVISION.items() for s in ss.split()}
    for st in TILES:
        def fred(series):
            f = pd.read_csv(RAW / f"{series}.csv")
            f["year"] = f.iloc[:, 0].str[:4].astype(int)
            x = f[f.year == 2024].iloc[:, 1]
            return float(x.iloc[0]) if len(x) else np.nan
        gdp, pop = fred(f"{st}NGSP"), fred(f"{st}POP")
        x = v[v.state_po == st]
        tot = x.totalvotes.max()
        rep = x[x.party_simplified == "REPUBLICAN"].votes.sum()
        dem = x[x.party_simplified == "DEMOCRAT"].votes.sum()
        rows.append({"state": st, "gdp_2024_musd": gdp, "pop_2024_thousands": pop,
                     "gdp_per_person_2024_usd": gdp * 1e6 / (pop * 1e3) if pop else np.nan,
                     "rep_minus_dem_2024_pts": 100 * (rep - dem) / tot if tot else np.nan,
                     "census_division": div_of[st], "census_region": REGION[div_of[st]]})
    a = pd.DataFrame(rows)
    a.to_csv(ATTR, index=False)
    return a


def _nearest(target: str, score: dict, k: int = 4, log: bool = False) -> list[str]:
    """States closest to `target` on one value (or a tuple of standardised values)."""
    me = score.get(target)
    if me is None:
        return []
    def d(s):
        a, b = score[s], me
        if isinstance(a, tuple):
            return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
        return abs(math.log(a) - math.log(b)) if log else abs(a - b)
    return sorted((s for s in score if s != target and score[s] is not None), key=d)[:k]


def presets(sp: pd.DataFrame, flows: dict | None = None) -> dict:
    """{key: {label, desc, group, peers: {ST: [...]}}} for every state."""
    if not ATTR.exists():
        build_attributes()
    a = pd.read_csv(ATTR).set_index("state")
    last = lambda m: sp[(sp.measure == m) & (sp.state != "US")].pipe(lambda d: d[d.year == d.year.max()]).set_index("state").value
    def z(*ms):
        cols = [last(m) for m in ms]
        df = pd.concat(cols, axis=1).dropna()
        df = (df - df.mean()) / df.std()
        return {s: tuple(r) for s, r in df.iterrows()}
    states = list(TILES)
    out = {}
    def add(key, label, desc, group, fn):
        out[key] = {"label": label, "desc": desc, "group": group, "peers": {s: fn(s) for s in states}}
    enr = last("enroll_total").to_dict()
    add("size", "Similar enrollment", "The four states closest in total fall enrollment.", "IPEDS",
        lambda s: _nearest(s, enr, log=True))
    if flows:
        hi = {h: i for i, h in enumerate(flows["homes"])}
        si = {s: i for i, s in enumerate(flows["states"])}
        def exch(s):
            tot = {o: flows["m"][si[s]][hi[o]] + flows["m"][si[o]][hi[s]] for o in states if o != s}
            return sorted(tot, key=lambda o: -tot[o])[:4]
        add("exchange", "Biggest student exchange", f"The states that send and receive the most first-time students with this one (fall {flows['year']}).",
            "IPEDS", exch)
    ir = z("intl_share_enroll_grad", "intl_share_stem_master")
    add("intl", "Similar international reliance", "Closest on the international share of graduate students and of STEM master's.", "IPEDS",
        lambda s: _nearest(s, ir))
    sf = z("stem_share_bach", "stem_share_master")
    add("stem", "Similar STEM focus", "Closest on the STEM share of bachelor's and master's degrees.", "IPEDS",
        lambda s: _nearest(s, sf))
    fu = z("approp_per_fte", "tuition_pub4_instate")
    add("funding", "Similar public funding", "Closest on state appropriations per student and public 4-year tuition.", "IPEDS",
        lambda s: _nearest(s, fu))
    lead = last("intl_stem_master_count").sort_values(ascending=False)
    add("leaders", "Leaders in international STEM talent", "The four states awarding the most STEM master's to international students.", "IPEDS",
        lambda s: [x for x in lead.index if x != s][:4])
    div = a.census_division.to_dict()
    def region(s):
        same = [x for x in states if x != s and div[x] == div[s]]
        if len(same) < 3:
            same += [x for x in states if x != s and x not in same and a.census_region[x] == a.census_region[s]][:4 - len(same)]
        return same[:7]
    add("region", "Same region", "States in the same Census division (topped up from the Census region when the division is small).",
        "Other public data", region)
    gdp = a.gdp_2024_musd.to_dict()
    add("economy", "Similar economy size", "The four states closest in total GDP, 2024 (BEA via FRED). Used only to choose states.",
        "Other public data", lambda s: _nearest(s, gdp, log=True))
    gpp = a.gdp_per_person_2024_usd.to_dict()
    add("income", "Similar output per person", "The four states closest in GDP per resident, 2024 (BEA and Census via FRED). Used only to choose states.",
        "Other public data", lambda s: _nearest(s, gpp, log=True))
    vote = a.rep_minus_dem_2024_pts.to_dict()
    add("vote", "Similar 2024 presidential vote", "The four states with the closest 2024 presidential margin (MIT Election Lab). Used only to choose states.",
        "Other public data", lambda s: _nearest(s, vote))
    return out


if __name__ == "__main__":
    a = build_attributes()
    print(a.round(1).to_string(index=False))
    sp = pd.read_csv(DEST / "state_panel.csv")
    p = presets(sp)
    for k, v in p.items():
        print(f"{v['label']:<40}", "CA ->", v["peers"]["CA"], " WY ->", v["peers"]["WY"])
