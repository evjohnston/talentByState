"""Delta Cost Project database (1987-2012), keyed to IPEDS unitid x year, plus a check against
the harmonized finance panel.

    python -m ipeds_clean.harmonize.delta_cost

Source: sources/delta_cost/IPEDS_Analytics_DCP_87_12_CSV.zip (delta_public_87_99.csv,
delta_public_00_12.csv), built by the Delta Cost Project / AIR from IPEDS; documentation in
sources/delta_cost/docs/.

Outputs (data/ipeds/harmonized/)
  delta_cost.parquet        one row per unitid x year (974 variables as published)
      year              = academicyear (fiscal/academic year END: 2010 = 2009-10), the same
                          convention as finance.parquet
      groupid           negative = single institution; positive = a Delta Cost "group" (parent
                          plus children combined, isgrouped = 1). Grouped rows carry the group's
                          combined finances, so compare or analyze them with isgrouped == 0
                          unless you want Delta's parent-child aggregation.
      missing codes     recoded to NA only where the dictionary defines them: -3 in iclevel,
                          control and the carnegie* fields; -1/-2 in medical, hospital; -2 in
                          instacttype. Imputation flags (I* columns) keep -1/-2 as categories.
                          Finance values are untouched (negatives can be real, e.g. net tuition).
  delta_cost_variables.csv  variable, label, type, calculated, source, definition
  qa_delta_cost.csv         by year and measure: institution-years matched (isgrouped == 0) and
                          share where Delta and finance.parquet agree within 1%
"""
from __future__ import annotations

import zipfile

import pandas as pd

from ..config import OUT, ROOT

SRC = ROOT / "sources" / "delta_cost"
ZIP = SRC / "IPEDS_Analytics_DCP_87_12_CSV.zip"
DICT = SRC / "docs" / "Delta_Data_Dictionary_1987_2012.xls"
HARM = OUT / "harmonized"
TEXT = ["instname", "TCSName", "city", "state", "zip"]
NA_CODES = {"iclevel": [-3], "control": [-3], "medical": [-1, -2], "hospital": [-1, -2], "instacttype": [-2]}

# Delta variable -> finance.parquet concept, for the cross-check
COMPARE = {"tuition03": "tuition_gross", "state03": "state_approp", "federal03": "fed_approp",
           "instruction01": "instruction", "research01": "research", "studserv01": "student_services",
           "total01": "total_expenses", "total03_revenue": "total_revenue"}


def read() -> pd.DataFrame:
    parts = []
    with zipfile.ZipFile(ZIP) as z:
        for name in sorted(z.namelist()):
            with z.open(name) as fh:
                parts.append(pd.read_csv(fh, dtype={c: "string" for c in TEXT}, low_memory=False,
                                         encoding="cp1252"))
    d = pd.concat(parts, ignore_index=True)
    for c, codes in NA_CODES.items():
        if c in d:
            d[c] = d[c].mask(d[c].isin(codes))
    for c in [c for c in d.columns if c.startswith("carnegie")]:
        if pd.api.types.is_numeric_dtype(d[c]):
            d[c] = d[c].mask(d[c] == -3)
    d.insert(0, "year", d.pop("academicyear").astype("int64"))
    d["unitid"] = d["unitid"].astype("Int64")
    return d.sort_values(["unitid", "year"]).reset_index(drop=True)


def variables() -> pd.DataFrame:
    p = pd.read_excel(DICT, sheet_name="Proc Contents Order")
    p.columns = [str(c).strip() for c in p.columns]
    defn = next(c for c in p.columns if c.startswith("Definition"))
    out = p.rename(columns={"Variable": "variable", "Label": "label", "Type": "type",
                            "Calculated": "calculated", "Source": "source", defn: "definition"})
    return out[["variable", "label", "type", "calculated", "source", "definition"]]


def compare(d: pd.DataFrame) -> pd.DataFrame:
    fin = pd.read_parquet(HARM / "finance.parquet")
    keep = ["year", "unitid"] + [c for c in COMPARE.values() if c in fin]
    m = d[d.isgrouped == 0][["year", "unitid", *COMPARE]].merge(fin[keep], on=["year", "unitid"])
    rows = []
    for dv, fv in COMPARE.items():
        if fv not in m:
            continue
        x = m[["year", dv, fv]].dropna()
        x = x[(x[dv] != 0) | (x[fv] != 0)]
        close = ((x[dv] - x[fv]).abs() <= 0.01 * x[[dv, fv]].abs().max(axis=1)) | (x[dv] == x[fv])
        g = pd.DataFrame({"year": x.year, "close": close, "d": x[dv], "f": x[fv]}).groupby("year")
        r = g.agg(n=("close", "size"), within_1pct=("close", "mean"), delta_sum=("d", "sum"), finance_sum=("f", "sum"))
        r["sum_diff_pct"] = (100 * (r.finance_sum / r.delta_sum - 1)).round(2)
        rows.append(r.reset_index().assign(delta_var=dv, finance_concept=fv))
    q = pd.concat(rows, ignore_index=True)
    q["within_1pct"] = q.within_1pct.round(3)
    return q[["delta_var", "finance_concept", "year", "n", "within_1pct", "delta_sum", "finance_sum", "sum_diff_pct"]]


if __name__ == "__main__":
    d = read()
    d.to_parquet(HARM / "delta_cost.parquet", index=False)
    variables().to_csv(HARM / "delta_cost_variables.csv", index=False)
    print(f"delta_cost: {len(d):,} rows, {d.unitid.nunique():,} unitids, {d.year.min()}-{d.year.max()}, "
          f"{d.shape[1]} columns; grouped rows: {int((d.isgrouped == 1).sum()):,}")
    dirx = pd.read_parquet(HARM / "directory.parquet", columns=["year", "unitid"])
    link = d[["year", "unitid"]].merge(dirx, how="left", indicator=True)
    print("unitid x year found in the IPEDS directory:", f"{(link._merge == 'both').mean():.1%}")
    q = compare(d)
    q.to_csv(HARM / "qa_delta_cost.csv", index=False)
    s = q.groupby("delta_var").apply(lambda g: pd.Series({
        "years": f"{g.year.min()}-{g.year.max()}", "inst_years": int(g.n.sum()),
        "within_1pct": f"{(g.within_1pct * g.n).sum() / g.n.sum():.1%}",
        "median_sum_diff_pct": g.sum_diff_pct.median()}), include_groups=False)
    print(s.to_string())
