"""USPTO granted patents by state of the inventor's residence, from the PatentsView bulk tables.

    python -m ipeds_clean.patents_inventors     # -> data/patents/patents_inventor_state*.csv

Companion to patents.py, which counts patents by the state of their owner (assignee). Owners and inventors are
often in different states: a company headquartered in one state patents work done by engineers in another. This
module counts the same granted patents by where their inventors live, so each profile can show both.

Sources (sources/uspto_patents/):
* bulk/g_inventor_disambiguated.tsv.zip   one row per patent x inventor: patent_id, inventor_sequence, inventor_id,
                                          gender_code (M/F, inferred by PatentsView from the first name), location_id
* bulk/g_location_disambiguated.tsv.zip   location_id -> disambiguated city, state, country
* {year}.zip (annualized files)           grant year, first WIPO field and assignee locations for each patent, the
                                          same files patents.py reads, so both counts cover the same patents
Downloaded from the USPTO Open Data Portal (PatentsView bulk tables), March 2026 release.

Counting:
* patents        whole count: patents with at least one inventor living in the state
* patents_frac   fractional count: each patent split evenly across all of its inventors, wherever they live, so a
                 state is credited with its inventors' share; US states and DC sum to the U.S. total
* US row         the 50 states and DC (territories and inventors abroad are left out of the U.S. total)
* share_owned_elsewhere   of the state's whole-count patents, the share with an assignee but no assignee in the
                 state (invented in the state, owned outside it); patents with no assignee are left out
* women_share_of_inventors   women's share of the state's inventor-patent records with a gender code
Inventors with no location (about 1% of records) count toward a patent's inventor total but toward no state.
Technology fields are the WIPO 35-field classification of the patent's first listed field, grouped as in
patents.GROUPS.

Outputs (data/patents/):
  patents_inventor_state_wide.csv    one row per state-year
  patents_inventor_state.csv         grant_year, state, measure, value
  patents_inventor_files.csv         record counts and match rates by grant year
"""
from __future__ import annotations

import zipfile

import pandas as pd

from .patents import GROUPS, OUT, ROOT, SRC, STATES

BULK = SRC / "bulk"
CACHE = ROOT / "cache" / "patents"


def patents_table() -> pd.DataFrame:
    """patent_number -> grant_year, field, and the set of US assignee states (from the annualized files)."""
    p = CACHE / "patents_index.parquet"
    if p.exists():
        return pd.read_parquet(p)
    out = []
    for path in sorted(SRC.glob("*.zip")):
        if not path.stem.isdigit():
            continue
        with zipfile.ZipFile(path) as z:
            d = pd.read_csv(z.open(z.namelist()[0]), usecols=["patent_number", "grant_year", "country", "state",
                            "d_assignee", "first_wipo_field_title"], dtype=str, low_memory=False)
        d["us_st"] = d.state.where((d.country == "US") & d.state.isin(STATES))
        g = d.groupby("patent_number")
        out.append(pd.DataFrame({"grant_year": int(path.stem), "field": g.first_wipo_field_title.first(),
                                 "has_assignee": g.d_assignee.first().fillna("0").astype(float).gt(0),
                                 "owner_states": g.us_st.agg(lambda s: "|".join(sorted(set(s.dropna()))))}))
        print("patents", path.stem, len(out[-1]), flush=True)
    t = pd.concat(out)
    t.index.name = "patent_id"
    t = t[~t.index.duplicated()].reset_index()
    CACHE.mkdir(parents=True, exist_ok=True)
    t.to_parquet(p, index=False)
    return t


def inventors() -> pd.DataFrame:
    """One row per patent x inventor: patent_id, state (US residence or None), woman (1/0/NaN)."""
    p = CACHE / "inventors_state.parquet"
    if p.exists():
        return pd.read_parquet(p)
    with zipfile.ZipFile(BULK / "g_location_disambiguated.tsv.zip") as z:
        loc = pd.read_csv(z.open(z.namelist()[0]), sep="\t", usecols=["location_id", "disambig_state", "disambig_country"],
                          dtype=str, keep_default_na=False)
    loc = loc[(loc.disambig_country == "US") & loc.disambig_state.isin(STATES)].set_index("location_id").disambig_state
    with zipfile.ZipFile(BULK / "g_inventor_disambiguated.tsv.zip") as z:
        d = pd.read_csv(z.open(z.namelist()[0]), sep="\t", usecols=["patent_id", "gender_code", "location_id"],
                        dtype=str, keep_default_na=False, engine="c")
    d["state"] = d.location_id.map(loc)
    d["woman"] = d.gender_code.map({"F": 1.0, "M": 0.0})
    d = d[["patent_id", "state", "woman"]]
    d["state"] = d.state.astype("category")
    CACHE.mkdir(parents=True, exist_ok=True)
    d.to_parquet(p, index=False)
    return d


def build() -> None:
    pt, inv = patents_table(), inventors()
    inv = inv.merge(pt, on="patent_id", how="inner")
    inv["n_inv"] = inv.groupby("patent_id").patent_id.transform("size")
    files = inv.groupby("grant_year").agg(records=("patent_id", "size"), patents=("patent_id", "nunique"),
                                          located_us=("state", lambda s: s.notna().mean())).reset_index()
    files["patents_in_annual_files"] = files.grant_year.map(pt.groupby("grant_year").size())
    st = inv.dropna(subset=["state"]).copy()
    st["state"] = st.state.astype(str)
    st["w"] = 1 / st.n_inv
    # one row per patent x state; weights add up when a patent has two inventors in the state
    ps = st.groupby(["grant_year", "state", "patent_id"], observed=True).agg(
        w=("w", "sum"), field=("field", "first"), has_a=("has_assignee", "first"), owners=("owner_states", "first"),
        women=("woman", "sum"), coded=("woman", "count")).reset_index()
    ps["elsewhere"] = ps.has_a & ~pd.Series([s in o.split("|") for s, o in zip(ps.state, ps.owners)], index=ps.index)
    us = ps.groupby(["grant_year", "patent_id"]).agg(w=("w", "sum"), field=("field", "first"), has_a=("has_a", "first"),
                                                       women=("women", "sum"), coded=("coded", "sum")).reset_index()
    us["state"], us["elsewhere"] = "US", False   # owned outside the U.S. is a different question; not computed
    rows = pd.concat([ps, us])
    g = rows.groupby(["grant_year", "state"])
    m = pd.DataFrame({"patents": g.size(), "patents_frac": g.w.sum(),
                      "women_share_of_inventors": g.women.sum() / g.coded.sum()})
    for name, fields in GROUPS.items():
        m[f"share_{name}"] = rows[rows.field.isin(fields)].groupby(["grant_year", "state"]).size().reindex(m.index).fillna(0) / m.patents
    owned = rows[rows.has_a & (rows.state != "US")].groupby(["grant_year", "state"])
    m["share_owned_elsewhere"] = owned.elsewhere.mean()
    m = m.reset_index()
    m["share_of_us_frac"] = m.patents_frac / m.grant_year.map(m[m.state == "US"].set_index("grant_year").patents_frac)
    OUT.mkdir(parents=True, exist_ok=True)
    m.to_csv(OUT / "patents_inventor_state_wide.csv", index=False)
    m.melt(id_vars=["grant_year", "state"], var_name="measure").dropna().to_csv(OUT / "patents_inventor_state.csv", index=False)
    files.to_csv(OUT / "patents_inventor_files.csv", index=False)
    print(files.tail(5).to_string(index=False))


if __name__ == "__main__":
    build()
