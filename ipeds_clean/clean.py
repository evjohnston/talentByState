"""Read one IPEDS table from its raw zip and return a standardized frame.

Cleaning rules (applied identically to every year):
  1. Read the revised (_rv) csv when present; detect utf-8 vs cp1252.
  2. Lowercase + strip column names; strip whitespace from every cell.
  3. "", ".", "NA" -> missing.
  4. Types: unitid -> Int64. Identifier/code columns (cipcode, opeid, zip, ...)
     and dictionary type "A" -> string. Imputation flag columns (x<var>) ->
     string. Everything else that parses fully as a number -> Int64 or Float64.
     Columns that *should* be numeric but don't parse are left as strings and
     reported.
  5. Negative missing-data codes (-1 not reported, -2 not applicable,
     -3 not available, -9 not active, ...):
       * categorical ("disc") variables: codes are KEPT -- they carry meaning
         ("not applicable, special focus institution") and are labelled in
         value_labels.csv. Filter them when you harmonize.
       * continuous variables (counts, dollars): a negative code is set to
         missing when the dictionary labels it, or, outside Finance, when the
         only negatives present are -1/-2/-3. Finance keeps unlabelled
         negatives (genuine negative dollars).
     Every recode/kept code is logged with its count.
"""
from __future__ import annotations

import csv
import io
import warnings
import zipfile
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import FORCE_STRING, NA_TOKENS, ROOT
from .dictionaries import ParsedDict
from .inventory import Source


@dataclass
class CleanResult:
    df: pd.DataFrame
    encoding: str
    revised: bool = False
    sentinel_log: list[dict] = field(default_factory=list)
    type_issues: list[dict] = field(default_factory=list)
    raw_numeric: dict[str, pd.Series] = field(default_factory=dict)  # pre-recode, for QA


def read_raw(src: Source) -> tuple[pd.DataFrame, str]:
    with zipfile.ZipFile(ROOT / src.data_zip) as zf:
        raw = zf.read(src.data_member)
    try:
        raw.decode("utf-8")
        enc = "utf-8-sig"
    except UnicodeDecodeError:
        enc = "cp1252"
    _check_ragged(raw.decode(enc, errors="replace"), src)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pd.errors.ParserWarning)
        df = _read(raw, enc)
    df.columns = [c.strip().lower() for c in df.columns]
    # Some 2010-era files end each line with a trailing comma -> empty column.
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("unnamed:")]]
    for c in df.columns:
        s = df[c].str.strip()
        df[c] = s.mask(s.isin(NA_TOKENS))
    return df, enc


def _check_ragged(text: str, src: Source) -> None:
    """Rows longer than the header are only OK if the extra fields are empty."""
    r = csv.reader(io.StringIO(text))
    nh = len(next(r))
    for i, row in enumerate(r, start=2):
        if len(row) > nh and any(x.strip() for x in row[nh:]):
            raise ValueError(f"{src.data_member} line {i}: non-empty field beyond header")


def _read(raw: bytes, enc: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(raw), dtype=str, encoding=enc, keep_default_na=False,
                     na_values=[], skipinitialspace=True, low_memory=False,
                     # rows with a trailing comma have 1 more field than the header;
                     # without this pandas silently shifts column 1 into the index.
                     index_col=False)


def _is_flag(col: str, cols: set[str], dict_flags: set[str]) -> bool:
    return col in dict_flags or (col.startswith("x") and col[1:] in cols)


def _to_number(s: pd.Series) -> tuple[pd.Series, int]:
    n = pd.to_numeric(s, errors="coerce")
    bad = int((n.isna() & s.notna()).sum())
    return n, bad


def clean_table(src: Source, d: ParsedDict | None) -> CleanResult:
    df, enc = read_raw(src)
    res = CleanResult(df=df, encoding=enc, revised=src.revised)
    cols = set(df.columns)

    dtypes, formats, dict_flags, neg_labels = {}, {}, set(), {}
    if d is not None:
        v = d.variables
        dtypes = dict(zip(v["varname"], v.get("datatype", pd.Series(dtype=str)).fillna("")))
        formats = dict(zip(v["varname"], v.get("format", pd.Series(dtype=str)).fillna("")))
        if "imputationvar" in v:
            dict_flags = set(v["imputationvar"].dropna())
        vl = d.value_labels
        if len(vl):
            codes = pd.to_numeric(vl["code"], errors="coerce")
            neg = vl[codes < 0].assign(code_num=codes[codes < 0])
            for var, g in neg.groupby("varname"):
                neg_labels[var] = dict(zip(g["code_num"], g["label"]))

    out = {}
    for c in df.columns:
        s = df[c]
        if c == "unitid":
            out[c] = pd.to_numeric(s, errors="raise").astype("Int64")
            continue
        if c in FORCE_STRING or _is_flag(c, cols, dict_flags) or dtypes.get(c, "").upper() == "A":
            out[c] = s.astype("string")
            continue
        n, bad = _to_number(s)
        if bad:
            # Not cleanly numeric: keep the text, report it.
            if dtypes.get(c, "").upper() == "N":
                res.type_issues.append({"varname": c, "issue": "dict says numeric but has text",
                                        "n_bad": bad,
                                        "examples": "; ".join(s[n.isna() & s.notna()].unique()[:5])})
            out[c] = s.astype("string")
            continue
        res.raw_numeric[c] = n
        categorical = formats.get(c, "").startswith("disc")
        if c in neg_labels:
            for code, label in neg_labels[c].items():
                hit = n == code
                k = int(hit.sum())
                if k:
                    res.sentinel_log.append({"varname": c, "code": int(code), "label": label, "n": k,
                                             "action": "kept (categorical)" if categorical else "set missing"})
                    if not categorical:
                        n = n.mask(hit)
        else:
            small = n.isin([-1, -2, -3])
            if small.any() and (n.dropna() < 0).sum() == small.sum():
                # The only negatives are -1/-2/-3 but the dictionary has no label
                # for them. Outside Finance these are always status/ID fields
                # (idx_*, newid, deathyr, pctmin*) using the standard IPEDS codes,
                # so recode them. Finance may have genuine small negatives: keep.
                counts = n[small].value_counts().to_dict()
                if categorical:
                    pass
                elif src.component == "F":
                    res.type_issues.append({"varname": c, "issue": "unlabelled -1/-2/-3 kept (finance)",
                                            "n_bad": int(small.sum()), "examples": str(counts)})
                else:
                    std = {-1: "Not reported", -2: "Not applicable", -3: "Not available"}
                    for code, k in counts.items():
                        res.sentinel_log.append({"varname": c, "code": int(code),
                                                 "label": f"{std[int(code)]} (assumed; unlabelled)",
                                                 "n": int(k), "action": "set missing"})
                    n = n.mask(small)
        nn = n.dropna()
        if len(nn) and np.all(np.mod(nn, 1) == 0) and nn.abs().max() < 2**62:
            out[c] = n.astype("Int64")
        else:
            out[c] = n.astype("Float64")
    res.df = pd.DataFrame(out)
    return res
