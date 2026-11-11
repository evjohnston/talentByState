"""Digest of Education Statistics tables (reference/digest/{edition}/) -> tidy, linked, comparable.

    python -m ipeds_clean.digest          # catalog + parse IPEDS/HEGIS tables -> data/ipeds/digest/

Outputs (data/ipeds/digest/)
  catalog.csv      every table file in every edition: edition, table_id, title, source note,
                   ipeds (source cites IPEDS or HEGIS), format, parse status, series_id
  values.parquet   long format, IPEDS/HEGIS-based tables only, one row per data cell:
                   edition, table_id, series_id, row (order), row_label, row_path (section >
                   ... > label), col (column number printed in the table), col_label (header
                   path joined " | "), value (float), value_raw, flag, notes (footnote markers)
  series.csv       one row per series_id: the current table number and title, editions present

Formats handled
  1995-2005  fixed-width text inside <pre> with "|" column separators
  2006-2025  HTML tables (old sequential numbers through 2012, "303.10" style from 2013)
Both carry a row of printed column numbers (1, 2, 3, ...) between the header and the data,
which anchors the parse. Header cells above it are stacked into col_label; rows below are data.

Value flags (Digest conventions)
  na     ---, —, (not available)          dagger   † not applicable
  zero   # rounds to zero                  rsnm     ‡ reporting standards not met
  caution  value followed by "!"           se       value in parentheses (standard error)

Linking editions (series_id)
  2013+ editions use stable numbers ("303.10"), which are the series_id. Tables in 1995-2012
  editions are linked to the 2013+ table whose normalized title matches best (years, "Fall 2004",
  institution-universe wording stripped); link_score records the match, and tables with no
  match at >= LINK_MIN keep their own id ("2008:189").
Scope: only tables whose SOURCE note cites IPEDS or HEGIS are parsed; the rest are cataloged.
"""
from __future__ import annotations

import difflib
import html as _html
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from .config import OUT, REF

SRC = REF / "digest"
DEST = OUT / "digest"
LINK_MIN = 0.86
IPEDS_RX = re.compile(r"Integrated Postsecondary|IPEDS|Higher Education General Information|HEGIS", re.I)

# --------------------------------------------------------------------------- catalog


def _table_id(name: str) -> tuple[int, str] | None:
    """(edition, printed table id) from the filename; None for non-table pages."""
    stem = Path(name).stem
    for rx in (r"^dt(\d{2})_(.+)$", r"^d(\d{2})t(.+)$"):
        m = re.match(rx, stem)
        if m:
            return int(m.group(1)), m.group(2)
    m = re.match(r"^dtab(\d+.*)$", stem)          # 1995
    if m:
        return 95, m.group(1)
    m = re.match(r"^dt(\d{3}[a-z]?)$", stem)      # 2000-2003
    if m:
        return -1, m.group(1)
    return None


def _clean_id(tid: str) -> str:
    tid = tid.lower()
    if re.match(r"^\d{3}\.\d{2}", tid):
        return tid
    m = re.match(r"^0*(\d+)(.*)$", tid)
    return (m.group(1) + m.group(2)) if m else tid


def _text(fragment: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def _source_note(page: str) -> str:
    t = _text(page)
    m = re.search(r"SOURCE\s*:(.{0,1500}?)(?=Download|Previous Page|Back to|Next Page|Table\s+\d|Publications|$)", t)
    return m.group(1).strip() if m else ""


def catalog_entry(path: Path) -> dict:
    page = path.read_text(errors="ignore")
    ti = re.search(r"<title>(.*?)</title>", page, re.S | re.I)
    title = _text(ti.group(1)) if ti else ""
    title = re.sub(r"^Digest of Education Statistics[,\s\d-]*", "", title).strip()
    edition = int(path.parent.name)
    tid = _clean_id(_table_id(path.name)[1])
    src = _source_note(page)
    units = re.search(r"\[(In [^\]]{3,80}|[^\]]{0,40}dollars[^\]]{0,40})\]", _text(page[:200000]))
    return {"edition": edition, "table_id": tid, "file": str(path.relative_to(SRC)),
            "title": title, "units": units.group(1) if units else "",
            "source": src[:1500], "ipeds": bool(IPEDS_RX.search(src)),
            "format": "pre" if re.search(r"<pre\b", page, re.I) else "html"}


def table_files() -> list[Path]:
    out = []
    for ed in sorted(p for p in SRC.iterdir() if p.is_dir() and p.name.isdigit()):
        out += [f for f in sorted(ed.iterdir()) if f.is_file() and _table_id(f.name)]
    return out

# --------------------------------------------------------------------------- values

_NA = {"---", "—", "--", "–", "(—)", "(---)", "—!", "n/a", "na"}


def parse_value(raw: str) -> tuple[float | None, str]:
    """Digest cell text -> (number, flag)."""
    s = raw.replace("\xa0", " ").strip()
    if not s:
        return None, ""
    if s in _NA or set(s) <= set("-—–"):
        return None, "na"
    if s.startswith("†"):
        return None, "dagger"
    if s.startswith("‡"):
        return None, "rsnm"
    if s == "#" or s.startswith("#"):
        return 0.0, "zero"
    flag = ""
    if s.endswith("!"):
        flag, s = "caution", s[:-1].strip()
    if s.startswith("(") and s.endswith(")"):
        flag, s = ("se" if not flag else flag), s[1:-1].strip()
        if s in _NA or s.startswith("†"):
            return None, "se"
    t = re.sub(r"[,$%\s]", "", s)
    try:
        return float(t), flag
    except ValueError:
        return None, "text"


class _RowTree:
    """Row hierarchy from indentation.

    Label-only rows are sections: they apply to following rows indented the same or deeper,
    until a section at the same or a shallower indent replaces them. Rows with values become
    parents of following rows indented strictly deeper (e.g. "Full-time" > "Under 18")."""

    def __init__(self):
        self.stack: list[tuple[int, str, bool]] = []      # (indent, label, is_section)

    def section(self, indent: int, label: str) -> None:
        self.stack = [s for s in self.stack if s[0] < indent]
        self.stack.append((indent, label, True))

    def data(self, indent: int, label: str) -> str:
        self.stack = [s for s in self.stack if (s[0] <= indent if s[2] else s[0] < indent)]
        path = " > ".join([s[1] for s in self.stack if s[1]] + [label])
        if data_period(label)[0] is None:            # a year row is never a parent
            self.stack.append((indent, label, False))
        return path

    def continue_last(self, text: str) -> None:
        if self.stack:
            i, l, sec = self.stack[-1]
            self.stack[-1] = (i, f"{l} {text}", sec)


def _numbers_row(texts: list[str]) -> bool:
    nums = [t for t in texts if t]
    return len(nums) >= 2 and all(t.isdigit() for t in nums) and [int(t) for t in nums] == list(range(1, len(nums) + 1))


# ---- <pre> tables

_FOOT = re.compile(r"\\(\d+|[a-z])\\")


def _pre_text(page: str) -> str | None:
    m = re.search(r"<pre[^>]*>(.*?)</pre>", page, re.S | re.I)
    if not m:
        return None
    return _html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))


def _segments(line: str) -> list[tuple[int, int, str]]:
    out, start = [], 0
    for i, ch in enumerate(line + "|"):
        if ch == "|":
            out.append((start, i, line[start:i]))
            start = i + 1
    return out


def parse_pre(page: str) -> pd.DataFrame:
    text = _pre_text(page)
    if text is None:
        return pd.DataFrame()
    lines = text.splitlines()
    k = next((i for i, l in enumerate(lines)
              if "|" in l and _numbers_row([s[2].strip() for s in _segments(l)])), None)
    if k is None:
        return pd.DataFrame()
    cols = _segments(lines[k])                      # (start, end, text) per printed column
    ncol = len(cols)
    # ---- header: for each column walk the header lines and stack cell texts
    head_lines = [l for l in lines[:k] if l.strip() and set(l.strip()) - set("_|- ")]
    head_all = lines[:k]
    labels = []
    for (a, b, _) in cols:
        mid = (a + b) // 2
        stack, cur_key, cur_txt = [], None, []
        for l in head_all:
            seg = next(((s, e, t) for s, e, t in _segments(l) if s <= mid <= e), None)
            if seg is None:
                continue
            s, e, t = seg
            closed = set(t.strip()) <= set("_") and t.strip() != ""
            txt = t.replace("_", " ").strip()
            key = (s, e)
            if key != cur_key:
                if cur_txt:
                    stack.append(" ".join(cur_txt))
                cur_key, cur_txt = key, []
            if txt:
                cur_txt.append(txt)
            if closed and cur_txt:
                stack.append(" ".join(cur_txt))
                cur_key, cur_txt = None, []
        if cur_txt:
            stack.append(" ".join(cur_txt))
        dedup = [x for i, x in enumerate(stack) if not i or x != stack[i - 1]]
        labels.append(" | ".join(_FOOT.sub("", x).strip() for x in dedup if x))
    del head_lines
    # ---- data rows
    rows, tree, r = [], _RowTree(), 0
    pending: tuple[int, str] | None = None          # label-only line that may wrap onto the next
    for l in lines[k + 1:]:
        if not l.strip() or set(l.strip()) <= set("_|- "):
            continue
        if "|" not in l:
            break                                    # notes below the table
        segs = _segments(l)
        if len(segs) < ncol:
            segs += [(0, 0, "")] * (ncol - len(segs))
        stub_raw = segs[0][2]
        indent = len(stub_raw) - len(stub_raw.lstrip(" "))
        notes = ",".join(_FOOT.findall(stub_raw))
        stub = re.sub(r"\s*\.{2,}\s*$|\s*\.{2,}|\s+\.\s*$", "", _FOOT.sub("", stub_raw)).strip()
        vals = [_FOOT.sub("", segs[j][2]).strip() for j in range(1, ncol)]
        vnotes = [",".join(_FOOT.findall(segs[j][2])) for j in range(1, ncol)]
        # a line starting in lower case continues the label above it ("Institutions / of higher")
        wraps = bool(stub) and stub[0].islower() and pending is not None
        if not any(vals):
            if stub:
                if wraps:
                    tree.continue_last(stub)
                else:
                    tree.section(indent, stub)
                    pending = (indent, stub)
            continue
        if wraps:                                    # wrapped label of this data row
            tree.stack.pop()
            stub, indent = f"{pending[1]} {stub}", pending[0]
        pending = None
        r += 1
        path = tree.data(indent, stub)
        for j, (v, vn) in enumerate(zip(vals, vnotes), start=2):
            if not v:
                continue
            num, flag = parse_value(v)
            rows.append((r, stub, path, indent, j, labels[j - 1], num, v, flag, ",".join(x for x in (notes, vn) if x)))
    return pd.DataFrame(rows, columns=["row", "row_label", "row_path", "indent", "col", "col_label",
                                       "value", "value_raw", "flag", "notes"])


# ---- HTML tables

def _main_table(doc):
    best, nbest = None, 0
    for t in doc.iter("table"):
        if t.find(".//table") is not None:
            continue
        n = len(t.findall(".//tr"))
        if n > nbest:
            best, nbest = t, n
    return best


def _cell_text(td) -> tuple[str, str, int]:
    """(text without footnote marks, footnote marks, leading-indent estimate)."""
    import copy
    td = copy.deepcopy(td)
    notes = []
    for sup in td.findall(".//sup"):
        notes.append((sup.text_content() or "").strip())
        sup.drop_tree()
    raw = td.text_content() or ""
    # indentation = leading non-breaking spaces only; ordinary whitespace is source formatting
    core = raw.lstrip(" \t\r\n")
    lead = len(core) - len(core.lstrip("\xa0"))
    style = (td.get("style") or "") + " " + (td.get("class") or "")
    m = re.search(r"padding-left:\s*([\d.]+)\s*(em|px|pt)?", style)
    pad = float(m.group(1)) * (1 if (m.group(2) or "em") == "em" else 1 / 8) if m else 0
    txt = re.sub(r"\s+", " ", raw.replace("\xa0", " ")).strip()
    txt = re.sub(r"\s*\.{2,}\s*$", "", txt)
    return txt, ",".join(n for n in notes if n), int(lead + 2 * pad)


def parse_html(page: str) -> pd.DataFrame:
    import lxml.html
    page = re.sub(r"<br\s*/?>", " ", page, flags=re.I)
    doc = lxml.html.fromstring(page)
    # css classes with a padding-left (2013+ pages set stub indentation by class)
    pad = {}
    for cls, val, unit in re.findall(r"\.(\w+)\s*\{[^}]*?padding-left:\s*([\d.]+)\s*(em|px|pt)?", page):
        pad[cls] = float(val) * (1 if (unit or "em") == "em" else 1 / 6)   # ~6px per em
    t = _main_table(doc)
    if t is None:
        return pd.DataFrame()
    grid: dict[tuple[int, int], tuple[int, str, str, int]] = {}
    trs = t.findall(".//tr")
    cid = 0
    for ri, tr in enumerate(trs):
        ci = 0
        for td in tr:
            if td.tag not in ("td", "th"):
                continue
            while (ri, ci) in grid:
                ci += 1
            rs = int(re.sub(r"\D", "", td.get("rowspan", "1")) or 1)
            cs = int(re.sub(r"\D", "", td.get("colspan", "1")) or 1)
            txt, notes, ind = _cell_text(td)
            ind += int(2 * max([pad.get(c, 0) for c in (td.get("class") or "").split()] or [0]))
            cid += 1
            for dr in range(rs):
                for dc in range(cs):
                    grid[(ri + dr, ci + dc)] = (cid, txt, notes, ind)
            ci += cs
    nrows = len(trs)
    ncols = 1 + max((c for _, c in grid), default=0)

    def rowcells(ri):
        seen, out = set(), []
        for c in range(ncols):
            g = grid.get((ri, c))
            if g and g[0] not in seen:
                seen.add(g[0])
                out.append((c, g))
        return out

    k = next((ri for ri in range(nrows) if _numbers_row([g[1] for _, g in rowcells(ri)])), None)
    if k is None:
        return pd.DataFrame()
    # printed column number -> grid columns it spans
    spans: list[tuple[int, list[int]]] = []
    for c in range(ncols):
        g = grid.get((k, c))
        if g and g[1].isdigit():
            if spans and spans[-1][0] == int(g[1]):
                spans[-1][1].append(c)
            else:
                spans.append((int(g[1]), [c]))
    labels = {}
    for num, cs in spans:
        stack, seen = [], set()
        for ri in range(k):
            g = grid.get((ri, cs[0]))
            if g and g[0] not in seen and g[1]:
                seen.add(g[0])
                stack.append(g[1])
        labels[num] = " | ".join(stack)
    rows, tree, r = [], _RowTree(), 0
    stub_cols = dict(spans).get(1, [0])
    for ri in range(k + 1, nrows):
        cells = rowcells(ri)
        if not cells:
            continue
        if len(cells) == 1 and len([c for c in range(ncols) if grid.get((ri, c), (None,))[0] == cells[0][1][0]]) >= ncols - 1:
            txt = cells[0][1][1]
            if re.match(r"^(NOTE|SOURCE|\d|[a-z]\s)", txt or ""):
                break                                # notes block
            if txt:
                tree.section(-1, txt)                # full-width banner row
            continue
        g0 = grid.get((ri, stub_cols[0]))
        stub, snotes, indent = (g0[1], g0[2], g0[3]) if g0 else ("", "", 0)
        vals, vcells = [], set()
        for num, cs in spans:
            if num == 1:
                continue
            txts = [grid[(ri, c)] for c in cs if (ri, c) in grid]
            main = next((x for x in txts if x[1]), None)
            if main:
                vcells.add(main[0])
            vals.append((num, main[1] if main else "", ",".join(x[2] for x in txts if x[2])))
        # banner across the value columns ("Current dollars", "Constant 2023-24 dollars")
        if not stub and len(vcells) == 1:
            txt = next(v for _, v, _ in vals if v)
            if parse_value(txt)[1] == "text":
                tree.section(-1, re.sub(r"\d+$", "", txt).strip())
                continue
        if not any(v for _, v, _ in vals):
            if stub:
                if re.match(r"^(NOTE|SOURCE)\s*:", stub):
                    break
                tree.section(indent, stub)
            continue
        r += 1
        path = tree.data(indent, stub)
        for num, v, vn in vals:
            if not v:
                continue
            numv, flag = parse_value(v)
            rows.append((r, stub, path, indent, num, labels.get(num, ""), numv, v, flag,
                         ",".join(x for x in (snotes, vn) if x)))
    return pd.DataFrame(rows, columns=["row", "row_label", "row_path", "indent", "col", "col_label",
                                       "value", "value_raw", "flag", "notes"])


def parse_file(path: Path) -> pd.DataFrame:
    page = path.read_text(errors="ignore")
    return parse_pre(page) if re.search(r"<pre\b", page, re.I) else parse_html(page)


def _parse_job(args):
    file, edition, tid = args
    try:
        df = parse_file(SRC / file)
        status = "ok" if len(df) else "no grid"
    except Exception as e:  # keep going; record why
        df, status = pd.DataFrame(), f"error: {e!r:.120}"
    if len(df):
        df.insert(0, "table_id", tid)
        df.insert(0, "edition", edition)
    return file, status, df

# --------------------------------------------------------------------------- linking

_UNIVERSE = [
    (r"institutions of higher education", "degree-granting institutions"),
    (r"degree-granting postsecondary institutions", "degree-granting institutions"),
    (r"postsecondary degree-granting institutions", "degree-granting institutions"),
    (r"title iv (participating|eligible)? ?", ""),
    (r"\bmen and women\b", "sex"), (r"\bsex of student\b", "sex"),
    (r"colleges and universities", "degree-granting institutions"),
    (r"\bearned degrees\b", "degrees"), (r"\bdegrees conferred by\b", "degrees conferred in"),
    (r"\bdegree-granting institutions\b", "degree-granting institutions"), (r"\bmales?\b|\bmen\b", "sex"),
]


def data_period(label: str) -> tuple[int | None, int | None]:
    """(first, last) calendar year named by a row label: "1947" -> (1947, 1947), "Fall 2009" ->
    (2009, 2009), "2010-11" / "2010–11" -> (2010, 2011), "1869-70" -> (1869, 1870). None if no year."""
    s = (label or "").strip()
    m = re.match(r"^(?:Fall\s+|Spring\s+)?((?:1[89]|20)\d\d)\s*(?:[-–—]\s*(\d{2}|\d{4}))?\s*(?:\(.*\))?$", s, re.I)
    if not m:
        return None, None
    a = int(m.group(1))
    if not m.group(2):
        return a, a
    b = m.group(2)
    return a, int(b) if len(b) == 4 else (a // 100) * 100 + int(b) + (100 if int(b) < a % 100 else 0)


def norm_title(t: str) -> str:
    s = t.lower()
    s = re.sub(r"\[.*?\]", " ", s)
    # strip the trailing time span ": 1990 through 2004", ": fall 2003", ": 2001-02 and 2002-03"
    s = re.sub(r":[^:]*\b(1[89]\d\d|20\d\d)\b[^:]*$", "", s)
    s = re.sub(r"\b(fall|spring|academic year|school year|selected years|selected academic years)\b", " ", s)
    s = re.sub(r"\b(1[89]\d\d|20\d\d)(-\d{2,4})?\b", " ", s)
    for a, b in _UNIVERSE:
        s = re.sub(a, b, s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _pairs(src: list[str], dst: list[str]) -> list[tuple[float, int, int]]:
    """All (score, i, j) with score >= LINK_MIN, using difflib's cheap upper bounds to skip."""
    out = []
    for i, a in enumerate(src):
        sm = difflib.SequenceMatcher(None, a, "")
        for j, b in enumerate(dst):
            sm.set_seq2(b)
            if sm.real_quick_ratio() < LINK_MIN or sm.quick_ratio() < LINK_MIN:
                continue
            r = sm.ratio()
            if r >= LINK_MIN:
                out.append((r, i, j))
    return sorted(out, reverse=True)


def link_series(cat: pd.DataFrame) -> pd.DataFrame:
    """series_id for every table. 2013+ tables keep their number. Older editions are linked
    newest first: each table can match the next newer edition's tables (inheriting their
    series_id) or a 2013+ title directly. Matching is one-to-one within an edition (best scores
    assigned first, each series used once), so two different tables never merge into a series.
    link_via records how each link was made; link_score is the title similarity (0-1)."""
    cat = cat.copy()
    new = cat.table_id.str.match(r"^\d{3}\.\d{2}")
    cat["norm"] = cat.title.map(lambda t: norm_title(_FOOT.sub(" ", t)))
    cat["series_id"] = cat.table_id.where(new)
    cat["link_score"] = new.astype(float)
    cat["link_via"] = pd.Series("own number", index=cat.index).where(new)
    # every distinct wording a current table has had since 2013 (titles drift between editions)
    cur = cat[new & cat.ipeds].sort_values("edition").drop_duplicates(["table_id", "norm"], keep="last")
    old_eds = sorted(cat.loc[~new, "edition"].unique(), reverse=True)
    for k, ed in enumerate(old_eds):
        here = cat.index[(cat.edition == ed) & ~new & cat.ipeds]
        nxt = old_eds[k - 1] if k else None
        nx = cat[(cat.edition == nxt) & cat.ipeds & (cat.link_via != "unlinked")] if nxt else cat.iloc[0:0]
        # targets: next edition's linked tables first (closer wording), then current titles
        tgt = [(n, s, f"chained via {nxt}") for n, s in zip(nx.norm, nx.series_id)] + \
              [(n, s, "current title") for n, s in zip(cur.norm, cur.table_id)]
        used_src, used_sid = set(), set()
        for score, i, j in _pairs(cat.loc[here, "norm"].tolist(), [t[0] for t in tgt]):
            sid = tgt[j][1]
            if i in used_src or sid in used_sid:
                continue
            used_src.add(i), used_sid.add(sid)
            ix = here[i]
            cat.at[ix, "series_id"], cat.at[ix, "link_score"], cat.at[ix, "link_via"] = sid, round(score, 3), tgt[j][2]
        for i, ix in enumerate(here):
            if i not in used_src:
                cat.at[ix, "series_id"], cat.at[ix, "link_score"], cat.at[ix, "link_via"] = f"{ed}:{cat.at[ix, 'table_id']}", 0.0, "unlinked"
    nonip = ~new & ~cat.ipeds
    cat.loc[nonip, "series_id"] = cat.loc[nonip, "edition"].astype(str) + ":" + cat.loc[nonip, "table_id"]
    return cat.drop(columns="norm")

# --------------------------------------------------------------------------- build


def build(workers: int = 8) -> tuple[pd.DataFrame, pd.DataFrame]:
    DEST.mkdir(parents=True, exist_ok=True)
    files = table_files()
    with ProcessPoolExecutor(workers) as ex:
        cat = pd.DataFrame(list(ex.map(catalog_entry, files, chunksize=32)))
    cat = link_series(cat)
    jobs = [(f, e, t) for f, e, t, ok in zip(cat.file, cat.edition, cat.table_id, cat.ipeds) if ok]
    status, parts = {}, []
    with ProcessPoolExecutor(workers) as ex:
        for i, (f, st, df) in enumerate(ex.map(_parse_job, jobs, chunksize=8), 1):
            status[f] = st
            if len(df):
                parts.append(df)
            if i % 500 == 0:
                print(f"  parsed {i}/{len(jobs)}", flush=True)
    cat["parse_status"] = cat.file.map(status).fillna("not parsed (not IPEDS/HEGIS)")
    vals = pd.concat(parts, ignore_index=True)
    vals = vals.merge(cat[["edition", "table_id", "series_id"]], on=["edition", "table_id"], how="left")
    per = {lab: data_period(lab) for lab in vals.row_label.unique()}
    vals["year_first"] = vals.row_label.map(lambda l: per[l][0]).astype("Int64")
    vals["year_last"] = vals.row_label.map(lambda l: per[l][1]).astype("Int64")
    cols = ["edition", "table_id", "series_id", "row", "row_label", "row_path", "indent", "col",
            "col_label", "year_first", "year_last", "value", "value_raw", "flag", "notes"]
    vals = vals[cols]
    vals["value"] = vals["value"].astype(float)
    vals.to_parquet(DEST / "values.parquet", index=False)
    cat.to_csv(DEST / "catalog.csv", index=False)
    _write_series(cat)
    return cat, vals


def _write_series(cat: pd.DataFrame) -> pd.DataFrame:
    s = cat[cat.ipeds].sort_values("edition")
    series = s.groupby("series_id").agg(
        title=("title", "last"), first_edition=("edition", "min"), last_edition=("edition", "max"),
        n_editions=("edition", "nunique"),
        editions=("edition", lambda e: " ".join(map(str, sorted(set(e))))),
        old_ids=("table_id", lambda t: " ".join(sorted({x for x in t if not re.match(r"^\d{3}\.\d{2}", x)})))).reset_index()
    series.to_csv(DEST / "series.csv", index=False)
    return series


def relink() -> pd.DataFrame:
    """Recompute series links from catalog.csv and update values.parquet without re-parsing."""
    cat = pd.read_csv(DEST / "catalog.csv")
    cat = link_series(cat.drop(columns=["series_id", "link_score", "link_via"], errors="ignore"))
    cat.to_csv(DEST / "catalog.csv", index=False)
    v = pd.read_parquet(DEST / "values.parquet")
    m = dict(zip(zip(cat.edition, cat.table_id.astype(str)), cat.series_id))
    v["series_id"] = [m.get(k) for k in zip(v.edition, v.table_id.astype(str))]
    v.to_parquet(DEST / "values.parquet", index=False)
    _write_series(cat)
    return cat


def load_values(series_id: str | None = None, edition: int | None = None) -> pd.DataFrame:
    """Read parsed Digest values; filter by series (e.g. "303.10") and/or edition."""
    filters = []
    if series_id:
        filters.append(("series_id", "==", series_id))
    if edition:
        filters.append(("edition", "==", edition))
    return pd.read_parquet(DEST / "values.parquet", filters=filters or None)


if __name__ == "__main__":
    cat, vals = build(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
    ip = cat[cat.ipeds]
    print(f"catalog: {len(cat):,} tables in {cat.edition.nunique()} editions; IPEDS/HEGIS-based: {len(ip):,}")
    print("parse status:", ip.parse_status.str.split(":").str[0].value_counts().to_dict())
    old = ip[~ip.table_id.str.match(r"^\d{3}\.\d{2}")]
    print(f"values: {len(vals):,} cells; series: {ip.series_id.nunique():,}; "
          f"1995-2012 tables linked to a 2013+ series: {(old.link_via != 'unlinked').sum():,} of {len(old):,}")
