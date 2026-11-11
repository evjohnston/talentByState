"""Parse IPEDS data dictionaries into tidy frames.

Two formats:
  * 1980-2000: HTML exports (one <hr>-separated block per variable), with
    value labels and min/max/mean/sd for continuous variables.
  * 2010+: Excel workbooks with varlist / Frequencies / Statistics sheets
    (plus *RV variants that describe the revised file).

Every parser returns a ParsedDict with three frames:
  variables    varname, label, description, datatype (N/A), format, width,
               imputationvar
  value_labels varname, code, label
  stats        varname, n, sum, min, max, mean, sd   (whatever is available)
"""
from __future__ import annotations

import html as htmllib
import io
import re
import warnings
import zipfile
from dataclasses import dataclass, field

import pandas as pd

from .config import ROOT


@dataclass
class ParsedDict:
    variables: pd.DataFrame
    value_labels: pd.DataFrame
    stats: pd.DataFrame
    notes: list[str] = field(default_factory=list)
    stats_describe_revised: bool = False  # Excel: stats came from a *RV sheet


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _text(fragment: str) -> str:
    t = re.sub(r"<[^>]+>", "\n", fragment)
    t = htmllib.unescape(t).replace("\xa0", " ")
    return "\n".join(line.strip() for line in t.splitlines() if line.strip())


_HEADER = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)-(\d+)-(.*)$", re.M)


def parse_html(raw: bytes) -> ParsedDict:
    h = raw.decode("cp1252", errors="replace")
    blocks = re.split(r"<hr[^>]*>", h, flags=re.I)
    variables, labels, stats, notes = [], [], [], []
    for b in blocks:
        text = _text(b)
        heads = list(_HEADER.finditer(text))
        if not heads:
            # e.g. "IF66-No description available in IPEDS database"
            m = re.match(r"^([A-Za-z][A-Za-z0-9_]*)-No description", text)
            if m:
                variables.append({"varname": m.group(1).lower(), "label": None})
                notes.append(f"{m.group(1)}: no description in dictionary")
            continue
        hd = heads[-1]
        var = hd.group(1).lower()
        body = text[hd.end():]
        desc = body.split("\nFormat\n")[0].strip() or None

        def grab(key: str) -> str | None:
            m = re.search(rf"^{key}-(.*)$", body, re.M)
            return m.group(1).strip() if m else None

        variables.append({
            "varname": var,
            "label": hd.group(3).strip(),
            "description": desc,
            "datatype": grab("Data type"),
            "width": _num(grab("Field width")),
            "format": (grab("Format") or "").lower() or None,
            "source_table": grab("Table name"),
        })

        # value-label rows: <td>label</td><td align=center>code</td><td>freq</td><td>pct</td>
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", b, flags=re.S | re.I):
            if "bgcolor=black" in tr.lower():
                continue  # header row
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)
            if len(tds) == 4 and re.search(r"<td align=center>", tr, re.I):
                labels.append({"varname": var, "code": _text(tds[1]),
                               "label": _text(tds[0]), "frequency": _num(_text(tds[2]))})

        m = re.search(r"Min.*?Max.*?Mean.*?Std Dev.*?</tr>\s*<tr>(.*?)</tr>", b, re.S | re.I)
        if m:
            vals = [_num(_text(c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)]
            if len(vals) == 4:
                stats.append({"varname": var, "min": vals[0], "max": vals[1],
                              "mean": vals[2], "sd": vals[3]})
    v = pd.DataFrame(variables, columns=["varname", "label", "description", "datatype", "width",
                                         "format", "source_table"]).drop_duplicates("varname", keep="last")
    if v.empty:
        notes.append("dictionary has no variable blocks (empty export)")
    return ParsedDict(v, pd.DataFrame(labels, columns=["varname", "code", "label", "frequency"]),
                      pd.DataFrame(stats, columns=["varname", "min", "max", "mean", "sd"]), notes)


def _sheet(book: dict[str, pd.DataFrame], *names: str) -> pd.DataFrame | None:
    low = {k.lower().strip(): v for k, v in book.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def parse_excel(raw: bytes, revised: bool) -> ParsedDict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        book = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype=str)
    notes = []
    vl = _sheet(book, "varlist")
    if vl is None:
        raise ValueError(f"no varlist sheet; sheets={list(book)}")
    vl.columns = [c.strip().lower() for c in vl.columns]
    desc = _sheet(book, "Description")
    variables = pd.DataFrame({
        "varname": vl["varname"].str.strip().str.lower(),
        "label": vl.get("vartitle"),
        "datatype": vl.get("datatype"),
        "width": pd.to_numeric(vl.get("fieldwidth"), errors="coerce"),
        "format": vl.get("format", pd.Series(dtype=str)).str.lower(),
        "imputationvar": vl.get("imputationvar", pd.Series(dtype=str)).str.strip().str.lower(),
    })
    if desc is not None:
        desc.columns = [c.strip().lower() for c in desc.columns]
        if "longdescription" in desc:
            d = dict(zip(desc["varname"].str.strip().str.lower(), desc["longdescription"]))
            variables["description"] = variables["varname"].map(d)

    # Prefer the RV sheets when the revised csv was the one loaded.
    order = ("FrequenciesRV", "Frequencies") if revised else ("Frequencies", "FrequenciesRV")
    fr = _sheet(book, *order)
    if fr is not None:
        fr.columns = [c.strip().lower() for c in fr.columns]
        labels = pd.DataFrame({
            "varname": fr["varname"].str.strip().str.lower(),
            "code": fr["codevalue"].astype(str).str.strip(),
            "label": fr["valuelabel"],
            "frequency": pd.to_numeric(fr.get("frequency"), errors="coerce"),
        })
    else:
        labels = pd.DataFrame(columns=["varname", "code", "label", "frequency"])

    order = ("StatisticsRV", "Statistics") if revised else ("Statistics", "StatisticsRV")
    st = _sheet(book, *order)
    stats_rv = _sheet(book, "StatisticsRV") is not None and st is _sheet(book, "StatisticsRV")
    if st is not None:
        st.columns = [c.strip().lower() for c in st.columns]
        stats = pd.DataFrame({"varname": st["varname"].str.strip().str.lower()})
        for c in ["n", "sum", "min", "max", "mean", "stddev"]:
            if c in st:
                stats["sd" if c == "stddev" else c] = pd.to_numeric(st[c], errors="coerce")
    else:
        stats = pd.DataFrame(columns=["varname"])
        notes.append("no Statistics sheet")
    return ParsedDict(variables, labels, stats, notes, stats_describe_revised=stats_rv)


def load_dictionary(dict_zip: str, member: str, revised: bool) -> ParsedDict:
    with zipfile.ZipFile(ROOT / dict_zip) as zf:
        raw = zf.read(member)
    if member.lower().endswith((".html", ".htm")):
        return parse_html(raw)
    return parse_excel(raw, revised)
