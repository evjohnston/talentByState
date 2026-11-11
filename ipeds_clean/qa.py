"""Check loaded tables against the statistics published in each dictionary.

NCES computes dictionary stats on the file as released, so we compare against
the numeric values *before* sentinel recoding, and also after recoding;
whichever matches is recorded (tells us how NCES treated the codes).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .clean import CleanResult
from .dictionaries import ParsedDict


def _close(a, b, rel=1e-6, abs_=0.6) -> bool:
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return True  # nothing to compare
    return bool(abs(a - b) <= max(abs_, rel * max(abs(a), abs(b))))


def _summ(s: pd.Series) -> dict:
    s = s.dropna().astype(float)
    if s.empty:
        return {"n": 0, "sum": 0.0, "min": np.nan, "max": np.nan, "mean": np.nan, "sd": np.nan}
    return {"n": len(s), "sum": s.sum(), "min": s.min(), "max": s.max(),
            "mean": s.mean(), "sd": s.std(ddof=0)}


def compare_stats(res: CleanResult, d: ParsedDict | None) -> pd.DataFrame:
    if d is None or d.stats.empty:
        return pd.DataFrame()
    rows = []
    for _, st in d.stats.iterrows():
        v = st["varname"]
        if v not in res.df.columns:
            rows.append({"varname": v, "status": "missing_in_data"})
            continue
        if v not in res.raw_numeric:
            # identifier/code columns (fice, opeid, ...) are deliberately strings
            rows.append({"varname": v, "status": "skipped_kept_as_string"})
            continue
        raw = _summ(res.raw_numeric[v])
        cln = _summ(res.df[v])
        keys = [k for k in ["n", "sum", "min", "max", "mean"] if k in st and pd.notna(st[k])]

        def ok(ours):
            # sd: HTML dicts may use n or n-1; check loosely.
            return all(_close(ours[k], st[k], rel=1e-4 if k == "mean" else 1e-6) for k in keys)

        # 1980-2000 HTML dictionaries compute the mean over ALL records with
        # blanks counted as 0 (verified: explains every min/max-matching case).
        raw0 = {**raw, "mean": res.raw_numeric[v].fillna(0).astype(float).mean()}
        if ok(raw):
            status = "match_raw"
        elif ok(cln):
            status = "match_clean"
        elif ok(raw0):
            status = "match_blank_as_zero_mean"
        elif res.revised and not d.stats_describe_revised and d.stats.get("n") is not None:
            status = "mismatch_dict_stats_predate_revision"
        else:
            status = "MISMATCH"
        row = {"varname": v, "status": status}
        for k in keys:
            row[f"dict_{k}"] = st[k]
            row[f"data_{k}"] = raw[k]
        rows.append(row)
    return pd.DataFrame(rows)


def table_summary(res: CleanResult) -> dict:
    df = res.df
    out = {"n_rows": len(df), "n_cols": df.shape[1],
           "exact_dup_rows": int(df.duplicated().sum())}
    if "unitid" in df:
        out["n_unitid"] = int(df["unitid"].nunique())
        out["unitid_unique"] = out["n_unitid"] == len(df)
        out["unitid_missing"] = int(df["unitid"].isna().sum())
    return out
