"""Run the full cleaning pass:  python -m ipeds_clean [--years 2010 2020] [--tables ef2010a ...]

Outputs
  data/ipeds/clean/{year}/{table}.parquet      one cleaned file per source table
  data/ipeds/meta/tables.csv                   inventory + row/col/unitid summary per table
  data/ipeds/meta/variables.csv                every variable in every dictionary (+ in_data, dtype)
  data/ipeds/meta/value_labels.csv             code -> label for every coded variable
  data/ipeds/meta/qa_stats.csv                 our stats vs. dictionary stats, per variable
  data/ipeds/meta/sentinel_codes.csv           every negative missing-code: set missing or kept
  data/ipeds/meta/type_issues.csv              columns that need a human look
  data/ipeds/meta/cip_crosswalk_2010_2020.csv  cleaned NCES crosswalk
"""
from __future__ import annotations

import argparse
import time

import pandas as pd

from . import qa
from .cip import load_crosswalk_2010_2020
from .clean import clean_table
from .config import CLEAN_DIR, META_DIR, ROOT, YEARS
from .dictionaries import load_dictionary
from .inventory import discover


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="*", default=YEARS)
    ap.add_argument("--tables", nargs="*", default=None)
    args = ap.parse_args(argv)

    META_DIR.mkdir(parents=True, exist_ok=True)
    tables, variables, labels, qas, sents, issues, failures = [], [], [], [], [], [], []

    for src in discover(args.years):
        if args.tables and src.table not in args.tables:
            continue
        t0 = time.time()
        key = {"year": src.year, "table": src.table}
        try:
            d = load_dictionary(src.dict_zip, src.dict_member, src.revised) if src.dict_zip else None
        except Exception as e:  # unreadable dictionary: clean without it, but log
            failures.append({**key, "stage": "dictionary", "error": repr(e)[:300]})
            d = None
        try:
            res = clean_table(src, d)
        except Exception as e:
            failures.append({**key, "stage": "data", "error": repr(e)[:300]})
            print(f"{src.year} {src.table:20s} FAILED: {repr(e)[:120]}")
            continue

        out = CLEAN_DIR / str(src.year) / f"{src.table}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        res.df.to_parquet(out, index=False)

        q = qa.compare_stats(res, d)
        summ = qa.table_summary(res)
        dict_vars = set(d.variables["varname"]) if d is not None else set()
        data_cols = set(res.df.columns)
        tables.append({**src.as_dict(), "encoding": res.encoding, **summ,
                       "n_dict_vars": len(dict_vars),
                       "cols_not_in_dict": " ".join(sorted(c for c in data_cols - dict_vars
                                                         if c != "unitid" and not c.startswith("x"))),
                       "dict_vars_not_in_data": " ".join(sorted(dict_vars - data_cols - {"instnm"})),
                       "qa_vars_checked": len(q),
                       "qa_mismatch": int((q.get("status") == "MISMATCH").sum()) if len(q) else 0,
                       "n_set_missing": sum(s["n"] for s in res.sentinel_log if s["action"] == "set missing"),
                       "output": str(out.relative_to(ROOT))})
        if d is not None:
            v = d.variables.copy()
            v["in_data"] = v["varname"].isin(data_cols)
            v["clean_dtype"] = v["varname"].map({c: str(t) for c, t in res.df.dtypes.items()})
            variables.append(v.assign(**key))
            labels.append(d.value_labels.assign(**key))
        if len(q):
            qas.append(q.assign(**key))
        sents += [{**key, **s} for s in res.sentinel_log]
        issues += [{**key, **s} for s in res.type_issues]
        print(f"{src.year} {src.table:20s} {summ['n_rows']:>8,} rows  {summ['n_cols']:>4} cols  "
              f"qa_mismatch={tables[-1]['qa_mismatch']:<3} set_missing={tables[-1]['n_set_missing']:<7,} "
              f"{time.time() - t0:5.1f}s")

    def cat(frames):
        frames = [f for f in frames if len(f)]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def front(df):
        lead = [c for c in ["year", "table"] if c in df]
        return df[lead + [c for c in df.columns if c not in lead]]

    partial = bool(args.tables) or args.years != YEARS
    done = {(t["year"], t["table"]) for t in tables} | {(f["year"], f["table"]) for f in failures}

    def write(df: pd.DataFrame, name: str) -> None:
        """Full run: overwrite. Partial run: replace only the (year, table) rows just processed."""
        path = META_DIR / f"{name}.csv"
        if partial and path.exists():
            old = pd.read_csv(path, low_memory=False)
            keep = ~pd.Series(list(zip(old["year"], old["table"]))).isin(done).values
            df = pd.concat([old[keep], df], ignore_index=True)
        front(df).sort_values(["year", "table"], kind="stable").to_csv(path, index=False)

    write(pd.DataFrame(tables), "tables")
    write(cat(variables), "variables")
    write(cat(labels), "value_labels")
    write(cat(qas), "qa_stats")
    write(pd.DataFrame(sents, columns=["year", "table", "varname", "code", "label", "n", "action"]), "sentinel_codes")
    write(pd.DataFrame(issues, columns=["year", "table", "varname", "issue", "n_bad", "examples"]), "type_issues")
    write(pd.DataFrame(failures, columns=["year", "table", "stage", "error"]), "failures")
    xw = load_crosswalk_2010_2020()
    xw.to_csv(META_DIR / "cip_crosswalk_2010_2020.csv", index=False)
    xw.to_parquet(META_DIR / "cip_crosswalk_2010_2020.parquet", index=False)  # keeps "01.0101" as text
    print(f"\nwrote {len(tables)} tables -> {CLEAN_DIR.relative_to(ROOT)}, metadata -> {META_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
