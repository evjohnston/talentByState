"""Map every field-of-study code used in the decennial Completions files to CIP-2020.

Vintages in the data (verified against code lists):
    1980        HEGIS taxonomy (1970). Stored as 5 digits ("01020"); HEGIS code = first 4.
    1984-1986   CIP-1980, undotted with the leading zero dropped ("10102" = 01.0102)
    1987-1991   CIP-1985
    1992-2002   CIP-1990
    2003-2009   CIP-2000
    2010-2019   CIP-2010
    2020+       CIP-2020
    (verified per year: each file matches its vintage's code list at 99-100%)

Chain (one step per CIP revision):
    HEGIS --> CIP90 --> CIP2K --> CIP10 --> CIP20
    CIP80 --> CIP85 --> CIP90 ...   (no official CIP80->85 crosswalk exists; CIP-85 was
                                     a light update, so same_code / title_match within
                                     the family resolve it)

Each step resolves a source code with the first rule that applies:
    override     row in crosswalks/cip_overrides.csv (hand-curated, wins always)
    official     NCES crosswalk row with a valid 6-digit target
    report_under "Deleted, report under XX.XXXX" parsed from the NCES crosswalk
    same_code    code not in the crosswalk but exists unchanged in the next vintage
    title_match  fuzzy title match restricted to plausible target families
    sibling      most common official target of codes sharing the 4-digit prefix
    no_field     undesignated field / aggregate ("Undesignated field", HEGIS 90xx)
Every non-official resolution is written to data/ipeds/harmonized/cip_chain_review.csv.
"""
from __future__ import annotations

import difflib
import re
import warnings
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from ..config import CIP_REF, XWALK

CIP_XLS = CIP_REF / "CIP.XLS"
XW_2000_2010 = CIP_REF / "Crosswalk2000to2010.csv"
XW_2010_2020 = CIP_REF / "Crosswalk2010to2020.csv"
CIP2020_LIST = CIP_REF / "CIPCode2020.csv"
OVERRIDES = XWALK / "cip_overrides.csv"

SIX = re.compile(r"^\d{2}\.\d{4}$")
TITLE_MATCH_MIN = 0.70

# ---------------------------------------------------------------- utilities

def _unx(s: pd.Series) -> pd.Series:
    """Strip Excel ="..." quoting."""
    return s.astype("string").str.replace(r'^="?|"$', "", regex=True).str.strip()


_ABBREV = {
    "mgmt": "management", "mgt": "management", "genl": "general", "gen": "general",
    "oth": "other", "tech": "technology", "techn": "technology", "serv": "services",
    "svcs": "services", "prod": "production", "admin": "administration",
    "adm": "administration", "sci": "science", "scis": "sciences", "educ": "education",
    "ed": "education", "agric": "agricultural", "agricul": "agricultural",
    "bus": "business", "comm": "communication", "eng": "engineering",
    "engr": "engineering", "lang": "language", "lit": "literature", "op": "operations",
    "oper": "operations", "rel": "related", "spec": "specialist", "ther": "therapy",
    "med": "medical", "mech": "mechanics", "maint": "maintenance", "equip": "equipment",
    "repr": "repair", "elec": "electrical", "electr": "electronic", "assist": "assistant",
    "asst": "assistant", "info": "information", "proc": "processing", "dev": "development",
    "psych": "psychology", "phys": "physical", "hlth": "health", "pub": "public",
    "intl": "international", "amer": "american", "hist": "history", "tchr": "teacher",
    "tch": "teacher", "voc": "vocational",
}
_STOP = {"and", "or", "of", "the", "in", "for", "a", "an", "general", "other", "related",
         "programs", "program", "studies", "new", "operations"}


def norm_title(t) -> str:
    if t is None or pd.isna(t):
        return ""
    t = str(t).lower().replace("&", " and ").replace("/", " ")
    t = re.sub(r"\(new\)|\(moved.*?\)", " ", t)
    words = re.findall(r"[a-z]+", t)
    return " ".join(_ABBREV.get(w, w) for w in words)


def _stem(w: str) -> str:
    for suf in ("ing", "ion", "ant", "ics", "ies", "es", "s", "y"):
        if len(w) > 5 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _sim(a: str, b: str) -> float:
    """0.5 * character similarity + 0.5 * soft token overlap (content words)."""
    ta = {_stem(w) for w in a.split()} - _STOP
    tb = {_stem(w) for w in b.split()} - _STOP
    if not ta or not tb:
        return 0.0
    hit = sum(any(x == y or difflib.SequenceMatcher(None, x, y).ratio() >= 0.8 for y in tb) for x in ta)
    tok = hit / max(len(ta), len(tb))
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    return 0.5 * seq + 0.5 * tok

# ---------------------------------------------------------------- code lists

@dataclass
class Vintage:
    name: str
    titles: dict[str, str]          # 6-digit code -> title

    def has(self, code) -> bool:
        return code in self.titles


@lru_cache(maxsize=None)
def _xls() -> dict[str, pd.DataFrame]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.read_excel(CIP_XLS, sheet_name=None, dtype=str)


@lru_cache(maxsize=None)
def vintages() -> dict[str, Vintage]:
    x = _xls()
    six = lambda d: {k: v for k, v in d.items() if isinstance(k, str) and SIX.match(k)}
    v85 = dict(zip(x["CIP1985"]["CIP85"], x["CIP1985"]["CIPTITLE"]))
    # The CIP1985 sheet is incomplete; the completions dictionaries label every code
    # actually used in the data, so add those (all CIP-85 years).
    lab = _dict_cip_labels()
    for y in range(1987, 1992):
        v85.update({k: v for k, v in lab.get(y, {}).items() if k not in v85})
    v90 = dict(zip(x["CIP1990"]["CIP90"], x["CIP1990"]["CIPTITLE"]))
    for y in range(1992, 2003):
        v90.update({k: v for k, v in lab.get(y, {}).items() if k not in v90 and not k.endswith("00")})
    v80 = {}
    for y in (1984, 1985, 1986):
        v80.update({norm_cip80(k): v for k, v in lab.get(y, {}).items()})
    c2k = x["CIP2000"]
    c2k = c2k[~c2k["ACTIONCODE"].isin(["D", "M"])]  # D=deleted, M=moved (old location)
    v2k = dict(zip(c2k["CIPCode"], c2k["CIPTITLE"]))
    a = pd.read_csv(XW_2000_2010, dtype=str)
    v2k.update({k: t for k, t in zip(_unx(a.CIPCode2000), a.CIPTitle2000) if k not in v2k})
    b = pd.read_csv(XW_2010_2020, dtype=str)
    v10 = dict(zip(_unx(b.CIPCode2010), b.CIPTitle2010))
    v10.update({k: t for k, t in zip(_unx(a.CIPCode2010), a.CIPTitle2010)
                if k not in v10 and not str(t).startswith("Deleted")})
    c = pd.read_csv(CIP2020_LIST, dtype=str)
    v20 = dict(zip(_unx(c.CIPCode), c.CIPTitle))
    hg = x["Crosswalk_HEGIStoCIP90"]
    vh = dict(zip(hg.HEGIS, hg.HEGIS_TITLE))
    from .. import labels as L
    for t in ["c1980_4ormore_cip", "c1980subba_cip"]:
        for k, lab in L(1980, t, "cipcode").items():
            vh.setdefault(k[:4], lab)
    return {
        "HEGIS": Vintage("HEGIS", {k: v for k, v in vh.items() if re.fullmatch(r"\d{4}", k)}),
        "CIP80": Vintage("CIP80", {k: v for k, v in six(v80).items() if not k.endswith("00")}),
        # In CIP-85/90, xx.xx00 rows are family/series headers, not reportable codes.
        "CIP85": Vintage("CIP85", {k: v for k, v in six(v85).items() if not k.endswith("00")}),
        "CIP90": Vintage("CIP90", {k: v for k, v in six(v90).items() if not k.endswith("00")}),
        "CIP2K": Vintage("CIP2K", six(v2k)),
        "CIP10": Vintage("CIP10", six(v10)),
        "CIP20": Vintage("CIP20", six(v20)),
    }

def norm_cip80(code) -> str:
    """1984-86 files store CIP-80 undotted without the leading zero: 10102 -> 01.0102."""
    c = str(code).strip().zfill(6)
    return f"{c[:2]}.{c[2:]}"


@lru_cache(maxsize=None)
def _dict_cip_labels() -> dict[int, dict[str, str]]:
    """year -> {cipcode: label} from every completions dictionary (value_labels.csv)."""
    from ..config import META_DIR
    v = pd.read_csv(META_DIR / "value_labels.csv", dtype={"code": str},
                    usecols=["year", "table", "varname", "code", "label"])
    v = v[(v.varname == "cipcode") & v.table.str.match(r"^c\d")]
    return {int(y): dict(zip(g.code.str.strip(), g.label)) for y, g in v.groupby("year")}


# ---------------------------------------------------------------- official steps

@lru_cache(maxsize=None)
def official_steps() -> dict[tuple[str, str], pd.DataFrame]:
    """(src, dst) -> frame[src_code, dst_code, note]. Only 6-digit / HEGIS rows."""
    x = _xls()
    steps = {}
    h = x["Crosswalk_HEGIStoCIP90"]
    steps[("HEGIS", "CIP90")] = pd.DataFrame({"src": h.HEGIS, "dst": h.CIP90, "note": ""})
    s = x["Crosswalk_CIP85toCIP90"]
    steps[("CIP85", "CIP90")] = pd.DataFrame({"src": s.CIP85, "dst": s.CIP90, "note": ""})
    s = x["Crosswalk_CIP90toCIP2K"]
    steps[("CIP90", "CIP2K")] = pd.DataFrame({"src": s.CIPCODE90, "dst": s.CIPCODE2k,
                                              "note": s.CIPTEXT2K.fillna("")})
    for (a, b), f, ca, cb, tb in [(("CIP2K", "CIP10"), XW_2000_2010, "CIPCode2000", "CIPCode2010", "CIPTitle2010"),
                                  (("CIP10", "CIP20"), XW_2010_2020, "CIPCode2010", "CIPCode2020", "CIPTitle2020")]:
        d = pd.read_csv(f, dtype=str)
        deleted = d.Action.str.strip().eq("Deleted")
        steps[(a, b)] = pd.DataFrame({
            "src": _unx(d[ca]),
            # "Deleted" rows repeat the old code as target: not a real mapping.
            "dst": _unx(d[cb]).where(~deleted),
            "note": d[tb].fillna("").where(deleted, ""),
        })
    # No official CIP80 -> CIP85 crosswalk: resolved by same_code / title_match / sibling.
    steps[("CIP80", "CIP85")] = pd.DataFrame(columns=["src", "dst", "note"])
    out = {}
    for k, d in steps.items():
        d = d.dropna(subset=["src"])
        d = d[d.src.str.match(r"^\d{2}\.\d{4}$|^\d{4}$")]
        out[k] = d.reset_index(drop=True)
    return out


def _family_targets(src: str, dst: str) -> dict[str, set[str]]:
    """Empirical 2-digit family transitions from the official step (plus identity)."""
    d = official_steps()[(src, dst)].dropna(subset=["dst"])
    d = d[d.dst.str.match(r"^\d{2}\.\d{4}$")]
    fam = {}
    for s, t in zip(d.src.str[:2], d.dst.str[:2]):
        fam.setdefault(s, set()).add(t)
    return fam


@lru_cache(maxsize=None)
def overrides() -> pd.DataFrame:
    if not OVERRIDES.exists():
        return pd.DataFrame(columns=["step", "src", "dst", "comment"])
    return pd.read_csv(OVERRIDES, dtype=str, comment="#").fillna("")


def _series_code(series: str, tgt: "Vintage", prefer: str) -> str | None:
    """Pick a 6-digit code inside a 4-digit series: its General (xx.xx01/00) or Other (xx.xx99)."""
    order = [f"{series}01", f"{series}00", f"{series}99"] if prefer == "general" \
        else [f"{series}99", f"{series}01", f"{series}00"]
    for c in order:
        if tgt.has(c):
            return c
    inside = sorted(k for k in tgt.titles if k.startswith(series))
    return inside[0] if inside else None


# ---------------------------------------------------------------- resolve one step

NO_FIELD_HEGIS = {"9001", "9002", "9003", "9004", "9099", "9900"}  # intermediate degrees / totals
NO_FIELD_CIP_PREFIX = ("95.", "99.")  # undesignated field / totals


def resolve_step(src: str, dst: str, codes) -> pd.DataFrame:
    """Return rows: src_code, dst_code, share, method, score, note."""
    V = vintages()
    tgt = V[dst]
    off = official_steps()[(src, dst)]
    off_map = off.dropna(subset=["dst"]).groupby("src")["dst"].apply(lambda s: sorted(set(s)))
    notes = off.groupby("src")["note"].first()
    ov = overrides()
    ov = ov[ov.step == f"{src}->{dst}"].groupby("src")["dst"].apply(list)
    fams = _family_targets(src, dst)
    # sibling rule: most common official 6-digit target among codes sharing the prefix
    od = off.dropna(subset=["dst"])
    od = od[od.dst.str.match(r"^\d{2}\.\d{4}$")]
    plen = 2 if src == "HEGIS" else 5
    sib = od.assign(p=od.src.str[:plen]).groupby("p")["dst"].agg(lambda s: s.value_counts().index[0])

    rows = []

    def add(code, targets, method, score=None, note=""):
        targets = [t for t in targets if t]
        if not targets:
            rows.append((code, None, 1.0, method, score, note))
        for t in targets:
            rows.append((code, t, 1.0 / len(targets), method, score, note))

    for code in sorted(set(codes)):
        if code in ov.index:
            add(code, [] if ov[code] == [""] else ov[code], "override")
            continue
        if (src == "HEGIS" and code in NO_FIELD_HEGIS) or code.startswith(NO_FIELD_CIP_PREFIX):
            add(code, [], "no_field")
            continue
        offt = off_map.get(code, [])
        hits = [t for t in offt if SIX.match(t) and tgt.has(t)]
        if hits:
            add(code, hits, "official")
            continue
        series = [t for t in offt if re.fullmatch(r"\d{2}\.\d{2}", t)]
        hits = [c for c in (_series_code(t, tgt, "general") for t in series) if c]
        if hits:
            add(code, hits[:1], "official_series", note=f"official target series {series[0]}")
            continue
        note = str(notes.get(code, "") or "")
        ru = []
        if "report under" in note.lower():
            for t in re.findall(r"\d{2}\.\d{2}(?:\d{2})?", note):
                c = t if SIX.match(t) else _series_code(t, tgt, "other")
                if c and tgt.has(c):
                    ru.append(c)
            # 4-digit lists ("report under 51.38, 51.39") -> first series only
            if ru and not all(SIX.match(t) for t in re.findall(r"\d{2}\.\d{2}(?:\d{2})?", note)):
                ru = ru[:1]
        if ru:
            add(code, ru, "report_under", note=note)
            continue
        if src != "HEGIS" and tgt.has(code) and code not in off_map.index:
            add(code, [code], "same_code")
            continue
        # fuzzy title, restricted to plausible families
        title = V[src].titles.get(code) or ""
        fam = code[:2]
        allowed = fams.get(fam, set()) | ({fam} if src != "HEGIS" else set())
        cands = {k: v for k, v in tgt.titles.items() if not allowed or k[:2] in allowed}
        nt = norm_title(title)
        best, score = None, 0.0
        for k, v in cands.items():
            sc = _sim(nt, norm_title(v))
            if sc > score:
                best, score = k, sc
        if best and score >= TITLE_MATCH_MIN:
            add(code, [best], "title_match", round(score, 3),
                note=f"{title} -> {tgt.titles[best]}")
            continue
        s = sib.get(code[:plen])
        if s and tgt.has(s):
            add(code, [s], "sibling", round(score, 3),
                note=f"{title} -> {tgt.titles[s]} (best title score {score:.2f})")
            continue
        add(code, [], "unresolved", round(score, 3), note=title)
    return pd.DataFrame(rows, columns=["src_code", "dst_code", "share", "method", "score", "note"])


CHAINS = {
    "HEGIS": ["HEGIS", "CIP90", "CIP2K", "CIP10", "CIP20"],
    "CIP80": ["CIP80", "CIP85", "CIP90", "CIP2K", "CIP10", "CIP20"],
    "CIP85": ["CIP85", "CIP90", "CIP2K", "CIP10", "CIP20"],
    "CIP2K": ["CIP2K", "CIP10", "CIP20"],
    "CIP90": ["CIP90", "CIP2K", "CIP10", "CIP20"],
    "CIP10": ["CIP10", "CIP20"],
    "CIP20": ["CIP20"],
}


def build_chain(vintage: str, codes) -> pd.DataFrame:
    """Compose steps: original code -> CIP-2020 with product of shares.

    `method` is the weakest rule used along the way (official < ... < unresolved),
    and `path` records every hop so any mapping can be audited.
    """
    rank = ["identity", "official", "official_series", "override", "report_under", "same_code",
            "title_match", "sibling", "no_field", "unresolved"]
    cur = pd.DataFrame({"orig_code": sorted(set(codes))})
    cur["code"], cur["share"], cur["method"], cur["path"] = cur.orig_code, 1.0, "identity", cur.orig_code
    notes = []
    chain = CHAINS[vintage]
    for a, b in zip(chain, chain[1:]):
        live = cur[cur.code.notna()]
        step = resolve_step(a, b, live.code)
        step["step"] = f"{a}->{b}"
        notes.append(step[step.method != "official"])
        m = cur.merge(step, how="left", left_on="code", right_on="src_code")
        dead = m.code.isna()
        m.loc[~dead, "share"] = m.loc[~dead, "share_x"] * m.loc[~dead, "share_y"]
        m.loc[dead, "share"] = m.loc[dead, "share_x"]
        wk = lambda x, y: x if pd.isna(y) or rank.index(x) >= rank.index(y) else y
        m["method"] = [wk(x, y) for x, y in zip(m.method_x, m.method_y)]
        m["path"] = m.path + " > " + m.dst_code.fillna("∅").where(~dead, "")
        m["code"] = m.dst_code.where(~dead)
        cur = m[["orig_code", "code", "share", "method", "path"]]
    if vintage == "CIP20":
        V = vintages()["CIP20"]
        cur["method"] = ["official" if V.has(c) else ("no_field" if c.startswith(NO_FIELD_CIP_PREFIX) else "unresolved")
                         for c in cur.orig_code]
        cur.loc[cur.method != "official", "code"] = None
    cur = cur.rename(columns={"code": "cip2020"})
    cur.insert(0, "vintage", vintage)
    t20 = vintages()["CIP20"].titles
    cur["cip2020_title"] = cur.cip2020.map(t20)
    review = pd.concat(notes, ignore_index=True) if notes else pd.DataFrame()
    return cur, review
