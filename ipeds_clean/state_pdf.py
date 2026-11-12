"""Printable State Talent Profile: a PDF per state, styled after the 2026 US Talent Report.

    python -m ipeds_clean.state_pdf CA            # one state  -> data/states/profiles/pdf/CA.pdf
    python -m ipeds_clean.state_pdf --all         # all 50 states + DC

Layout is HTML/CSS (templates/state_pdf.html). The cover and "By the Numbers" pages are fixed,
full-bleed warm-grey pages; everything else flows on white pages, where figures and tables never
split across pages (CSS break-inside: avoid). Playwright drives the installed Chrome to print the
document; a second print supplies the running headers and page numbers, merged with pypdf.

Inputs: the state panel (every measure in the State Talent Sheet), the profile JSON written by
state_profile.py (every chart in the HTML profile), and the "Similar enrollment" peer set.
"""
from __future__ import annotations

import base64
import re
import json
import sys
from pathlib import Path

import pandas as pd

from . import states as S
from .states_explorer import NAMES, full_panel, payload as sheet_payload
from .peers import presets

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).parent / "templates" / "state_pdf.html"
FONTS = ROOT / "reference" / "fonts"
PROF = S.DEST / "profiles"
OUT = PROF / "pdf"
HTML_DIR = OUT / "_html"
BASE = 2015

# outside-source series drawn in the "Beyond campus" spreads (state and U.S.)
EXT_LINES = ["naep_math8", "naep_math8_prof", "naep_math4", "naep_read8", "gss_grad_se_tv_share", "gss_postdoc_se_tv_share",
             "dol_h1b_positions", "dol_perm_cert", "dol_perm_f1_share", "dol_perm_india_share", "dol_h1b_stem_share",
             "h1b_initial", "acs_stem_fb_share", "acs_stem_grad_fb_share", "acs_stem_phd_fb_share", "pat_patents",
             "pat_share_digital", "pat_share_life", "pseo_instate_bach_y1", "pseo_instate_bach_y5", "pseo_instate_master_y1",
             "opt_retention", "mig_net_ba_plus_per_1000", "rd_herd", "rd_ffs", "rd_usa_rd", "rd_herd_fed_share"]
PEER_ROWS = ["enroll_total", "share_grad", "stem_share_bach", "stem_share_master", "intl_stem_master_count",
             "share_of_us_intl_stem_master", "intl_share_stem_master", "intl_share_stem_doc", "intl_share_enroll_grad",
             "intl_share_enroll_ug", "grad_rate_bach6", "tuition_pub4_instate", "approp_per_fte", "faculty_salary",
             "instate_share_ft", "net_migration_ft"]


STATIC_FONTS = ROOT / "cache" / "fonts"
# (family, variable source in reference/fonts, weights used by the template)
VARIABLE_FONTS = [("Montserrat", "montserrat-latin-400-normal.woff2", range(300, 1000, 100)),
                  ("EB Garamond", "eb-garamond-latin-400-normal.woff2", range(400, 900, 100))]


def static_font(fam: str, src: str, w: int) -> Path:
    """A static TrueType instance of a variable font at one weight (cached in cache/fonts/).

    The template's Montserrat and EB Garamond files are variable fonts. Chrome cannot embed a variable font as a
    TrueType subset, so it writes every glyph set in one as a Type3 font, and print services (Vistaprint and
    other preflight checks) reject Type3 as "non-embedded fonts". Static instances embed as ordinary subsetted
    TrueType fonts and look the same."""
    out = STATIC_FONTS / f"{fam.lower().replace(' ', '-')}-{w}.ttf"
    if not out.exists():
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
        STATIC_FONTS.mkdir(parents=True, exist_ok=True)
        f = TTFont(FONTS / src)
        f.flavor = None                                   # write plain TrueType, not woff2
        inst = instantiateVariableFont(f, {"wght": w}, updateFontNames=False)
        style = {300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}[w]
        nm = inst["name"]                                 # give each instance its own names (the source says "Thin")
        for rec in list(nm.names):
            if rec.nameID in (1, 2, 3, 4, 6, 16, 17):
                nm.removeNames(nameID=rec.nameID)
        for nid, val in ((1, fam), (2, "Regular"), (3, f"{fam.replace(' ', '')}-{style}"), (4, f"{fam} {style}"),
                         (6, f"{fam.replace(' ', '')}-{style}"), (16, fam), (17, style)):
            nm.setName(val, nid, 3, 1, 0x409)
            nm.setName(val, nid, 1, 0, 0)
        inst["OS/2"].usWeightClass = w
        inst.save(out)
    return out


def font_css() -> str:
    def face(fam, data, fmt, w, style="normal"):
        b = base64.b64encode(data).decode()
        return f"@font-face{{font-family:'{fam}';src:url(data:font/{fmt};base64,{b}) format('{fmt == 'ttf' and 'truetype' or fmt}');font-weight:{w};font-style:{style};font-display:block}}"
    css = [face(fam, static_font(fam, src, w).read_bytes(), "ttf", w) for fam, src, ws in VARIABLE_FONTS for w in ws]
    # the italic is already a static font; declared at 400 only so Chrome never synthesizes a bold italic (Type3)
    css.append(face("EB Garamond", (FONTS / "eb-garamond-latin-400-italic.woff2").read_bytes(), "woff2", 400, "italic"))
    return "".join(css)


class Panel:
    def __init__(self):
        self.sp = pd.read_csv(S.DEST / "state_panel.csv")          # IPEDS only (peer presets use this)
        rows, extra = full_panel(self.sp)                           # + SEVIS, ACS, NAEP, NSF, USCIS, DOL, USPTO
        self.w = {m: g.pivot(index="year", columns="state", values="value") for m, g in rows.groupby("measure")}
        sheet = sheet_payload(rows, extra)
        self.meta, self.groups, self.src_lines = sheet["meta"], sheet["groups"], sheet["srcLines"]

    def at(self, m, st, y):
        t = self.w.get(m)
        if t is None or y is None or y not in t.index or st not in t.columns or pd.isna(t.loc[y, st]):
            return None
        return float(t.loc[y, st])

    def last_year(self, m, st):
        t = self.w[m]
        if st not in t:
            return None
        s = t[st].dropna()
        return int(s.index.max()) if len(s) else None

    def first_from(self, m, st, y):
        t = self.w[m]
        if st not in t:
            return None
        s = t[st].dropna()
        s = s[s.index >= y]
        return int(s.index.min()) if len(s) else None

    def prev_year(self, m, st, y):
        """The latest year before y with a value (the previous report, for year-over-year change)."""
        t = self.w.get(m)
        if t is None or y is None or st not in t:
            return None
        s = t[st].dropna()
        s = s[s.index < y]
        return int(s.index.max()) if len(s) else None

    def rank(self, m, st, y):
        row = self.w[m].loc[y].drop(labels=["US"], errors="ignore").dropna()
        return (int((row > row[st]).sum() + 1), len(row)) if st in row else (None, len(row))

    def series(self, m, st, y0=1985):
        t = self.w.get(m)
        if t is None or st not in t:
            return {"y": [], "v": []}
        s = t[st].dropna()
        s = s[s.index >= y0]
        return {"y": [int(y) for y in s.index], "v": [round(float(v), 3) for v in s.values]}


def measure_row(Pn: Panel, m: str, st: str) -> dict:
    meta = Pn.meta[m]
    y1 = Pn.last_year(m, st)
    y0 = Pn.first_from(m, st, BASE)
    yp = Pn.prev_year(m, st, y1)
    r, n = Pn.rank(m, st, y1) if y1 else (None, 51)
    return {"m": m, "title": meta["title"], "unit": meta["unit"], "fmt": meta["fmt"], "change": meta["change"],
            "group": meta["group"], "y0": y0, "y1": y1, "v0": Pn.at(m, st, y0), "v1": Pn.at(m, st, y1),
            "yp": yp, "vp": Pn.at(m, st, yp),
            "us0": Pn.at(m, "US", y0), "us1": Pn.at(m, "US", y1), "rank": r, "n": n, "src": meta["src"]}


def build_payload(Pn: Panel, st: str, peers: list[str]) -> dict:
    prof = json.loads((PROF / "data" / f"{st}.json").read_text())
    rows = {m: measure_row(Pn, m, st) for m in Pn.meta}
    peer_tab = []
    for m in PEER_ROWS:
        y = Pn.last_year(m, st)
        peer_tab.append({"m": m, "title": Pn.meta[m]["title"], "unit": Pn.meta[m]["unit"], "fmt": Pn.meta[m]["fmt"], "y": y,
                         "vals": {s: Pn.at(m, s, y) for s in [st] + peers + ["US"]},
                         "ranks": {s: Pn.rank(m, s, y)[0] if Pn.at(m, s, y) is not None else None for s in [st] + peers}})
    peer_lines = {m: {s: Pn.series(m, s, 1995) for s in [st] + peers + ["US"]}
                  for m in ["intl_share_stem_master", "intl_share_enroll_grad", "stem_share_master", "grad_rate_bach6"]}
    panel_lines = {m: {s: Pn.series(m, s) for s in [st, "US"]}
                   for m in ["approp_per_fte", "tuition_reliance_pub", "share_online_only", "bach_per_100_ug", "stem_master_per_doc",
                             "instate_share_ft", "foreign_share_ft", "net_migration_ft", "share_of_us_intl_stem_master", "intl_stem_master_count"]}
    ext_lines = {m: {s: Pn.series(m, s, 1976) for s in [st, "US"]} for m in EXT_LINES if m in Pn.w}
    insts = sorted(prof["inst"]["rows"], key=lambda r: -(r.get("enroll") or 0))
    prof["inst"]["top_enroll"] = insts[:15]
    prof["inst"]["top_intl"] = sorted(prof["inst"]["rows"], key=lambda r: -((r.get("ms_stem_intl") or 0) + (r.get("phd_stem_intl") or 0)))[:12]
    prof["inst"]["n"] = len(prof["inst"]["rows"])
    del prof["inst"]["rows"]
    return {"st": st, "name": NAMES[st], "peers": peers, "names": NAMES, "base": BASE, "built": pd.Timestamp.now().strftime("%B %Y"),
            "groups": Pn.groups, "rows": rows, "peer_tab": peer_tab, "peer_lines": peer_lines, "panel_lines": panel_lines, "prof": prof,
            "ext_lines": ext_lines, "srcLines": Pn.src_lines}


COVER = "G"   # cover art: postal code in caps, bright share scattered (mockups in pdf/_covers)
FRONT = ROOT / "reference" / "profile_frontmatter.json"
LOGOS = ROOT / "reference" / "logo"
FRONT_DEFAULT = {
    "series": "Talent Profile",
    "authors": [
        {"name": "Emerson Victoria Johnston", "bio": "is a research assistant with the Hoover Institution's Technology Policy Accelerator. A Knight-Hennessy Scholar, she holds a master's in international policy from Stanford University, and is on leave from its master's program in the history of science, technology, environment, and medicine."},
        {"name": "Dr. Amy Zegart", "bio": "is the Morris Arnold and Nona Jean Cox Senior Fellow at the Hoover Institution, director of Hoover's Technology Policy Accelerator, and a senior fellow and associate director at Stanford University's Institute for Human-Centered Artificial Intelligence."}],
    "byline": "By Emerson Johnston and Amy Zegart",
    "cite_authors": "Emerson V. Johnston and Amy Zegart",
    "publisher": "Technology Policy Accelerator, Hoover Institution, and the Institute for Human-Centered Artificial Intelligence, Stanford University, Stanford, CA",
    "publication_note": "A publication jointly produced by the Hoover Institution and the Institute for Human-Centered Artificial Intelligence at Stanford University.",
    "companion": "The 2026 US Talent Report: Benchmarking America's STEM Pipeline Amid the Great Talent Competition",
    "process": "Data come from the Integrated Postsecondary Education Data System (IPEDS), the Department of Homeland Security's SEVIS by the Numbers, the National Assessment of Educational Progress, NSF's Survey of Graduate Students and Postdoctorates and Survey of Earned Doctorates, the Department of Labor's Office of Foreign Labor Certification, the USCIS H-1B Employer Data Hub, the Census Bureau's American Community Survey and USPTO patent data via PatentsView, processed in Python; every figure and table is generated from those sources, and each one names its source.",
    "acknowledgments": [],
    "data_url": "",
    "license": "This profile is licensed under Attribution-NoDerivatives 4.0 International (CC BY-ND 4.0)."}


def front_matter() -> dict:
    """Front-matter text; edit reference/profile_frontmatter.json to change authors, credits or links."""
    if not FRONT.exists():
        FRONT.write_text(json.dumps(FRONT_DEFAULT, indent=2))
    return {**FRONT_DEFAULT, **json.loads(FRONT.read_text())}


def logos() -> dict:
    """Logos in reference/logo/: 1 HAI white, 2 Hoover|Stanford white, 3 HAI black, 4 Hoover|Stanford black.
    Cropped to their ink and shown Hoover|Stanford first, HAI second, as on the Talent Report."""
    import base64, io
    from PIL import Image
    def enc(f):
        im = Image.open(f).convert("RGBA"); im = im.crop(im.getchannel("A").getbbox())
        im = im.resize((round(im.width * 140 / im.height), 140), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    have = {i: LOGOS / f"{i}.png" for i in range(1, 5) if (LOGOS / f"{i}.png").exists()}
    pick = lambda ids: [enc(have[i]) for i in ids if i in have]
    return {"dark": pick([2, 1]), "light": pick([4, 3])}


def cover_shade() -> dict:
    """International share of STEM master's by state, latest year: shades the cover map."""
    sp = pd.read_csv(S.DEST / "state_panel.csv")
    x = sp[sp.measure == "intl_share_stem_master"]
    x = x[x.year == x.year.max()].set_index("state").value
    return {s: round(float(v), 1) for s, v in x.items() if s != "US"}


def write_html(Pn: Panel, st: str, peers: list[str], fonts: str, variant: str = "spread") -> Path:
    data = build_payload(Pn, st, peers)
    data["variant"], data["tiles"] = variant, {s: S.TILES[s] for s in S.TILES}
    data["front"], data["logos"], data["shade"], data["cover"] = front_matter(), logos(), cover_shade(), COVER
    blob = json.dumps(data, separators=(",", ":"), allow_nan=False, default=lambda o: None).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__FONTS__*/", fonts).replace("/*__DATA__*/null", blob)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    p = HTML_DIR / (f"{st}.html" if variant == "spread" else f"{st}.{variant}.html")
    p.write_text(html)
    return p


OVERLAY = """<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
@page {{ size: 8.5in 11in; margin: 0 }} html,body {{ margin:0; background: transparent }}
.p {{ width: 8.5in; height: 11in; position: relative; break-after: page }}
.rh {{ position:absolute; top:.55in; left:1.17in; right:1.12in; display:flex; justify-content:space-between; font-family: Montserrat, sans-serif }}
.rh .l {{ font-size:7.4pt; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:#6f6a64; line-height:1.35 }}
.rh .l b {{ display:block; color:#111; font-weight:800 }}
.rh .r {{ text-align:right; line-height:1.15 }} .rh .r b {{ display:block; color:#9a0033; font-weight:800; font-size:11pt }}
.rh .r span {{ font-size:7.2pt; font-weight:700; color:#111 }}
.pn {{ position:absolute; bottom:.42in; right:1.12in; font: 500 7.5pt Montserrat, sans-serif; color:#111 }}
.src {{ position:absolute; bottom:.42in; left:1.17in; font: 400 6.6pt Montserrat, sans-serif; color:#6f6a64 }}
</style></head><body>{pages}</body></html>"""


def render(states: list[str], variant: str = "spread", out_dir: Path | None = None) -> list[Path]:
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter
    Pn = Panel()
    peers = presets(Pn.sp)["size"]["peers"]
    fonts = font_css()
    OUT.mkdir(parents=True, exist_ok=True)
    done = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page()
        for st in states:
            h = write_html(Pn, st, peers[st], fonts, variant)
            page.goto(h.as_uri())
            page.wait_for_function("window.__ready === true", timeout=30000)
            if variant == "spread":   # folios and running heads are drawn on the spreads themselves
                out = (out_dir or OUT) / f"{st}.pdf"
                out.parent.mkdir(parents=True, exist_ok=True)
                tmp = HTML_DIR / f"{st}.main.pdf"
                page.pdf(path=str(tmp), print_background=True, prefer_css_page_size=True)
                rd, w = PdfReader(str(tmp)), PdfWriter()
                for pg_ in rd.pages:
                    w.add_page(pg_)
                w.add_metadata({"/Title": f"{NAMES[st]} State Talent Profile", "/Subject": "State talent profile (digital, spreads)"})
                with open(out, "wb") as f:
                    w.write(f)
                tmp.unlink(missing_ok=True)
                pr = print_version(out, page)
                done.append(out)
                print(f"{st} -> {out.name} ({len(rd.pages)} sheets), {pr.name} ({len(PdfReader(str(pr)).pages)} pages)")
                continue
            main = HTML_DIR / f"{st}.main.pdf"
            page.pdf(path=str(main), print_background=True, prefer_css_page_size=True)
            # section label for every page: read the markers the template leaves at each section start
            titles = page.evaluate("window.__titles")
            rd = PdfReader(str(main))
            n = len(rd.pages)
            labels, cur, dark = [], "", []
            for i, pg in enumerate(rd.pages):
                txt = re.sub(r"\s+", " ", pg.extract_text() or "")
                if i > 0 and not cur:
                    cur = "By the Numbers"
                dark.append(variant == "report" and txt.strip().startswith("SECTION"))
                m = re.search(r"SECTION (\d+) ", txt)
                if m and int(m.group(1)) < len(titles):
                    cur = titles[int(m.group(1))]
                if re.search(r"NOTES About These Data", txt):
                    cur = "About These Data"
                labels.append(cur)
            pages = "".join(
                f'<div class="p">' + ("" if i == 0 or dark[i] else f'<div class="rh"><div class="l"><b>State Talent Profile</b>IPEDS, 1980–2025</div>'
                                      f'<div class="r"><b>{NAMES[st]}</b><span>{labels[i]}</span></div></div>')
                + ("" if i == 0 or dark[i] else '<div class="src">Source: NCES, Integrated Postsecondary Education Data System (IPEDS).</div>')
                + f'<div class="pn"{" style=\'color:#fff\'" if dark[i] else ""}>{i + 1}</div></div>' for i in range(n))
            ov_html = HTML_DIR / f"{st}.overlay.html"
            ov_html.write_text(OVERLAY.format(fonts=fonts, pages=pages))
            page.goto(ov_html.as_uri())
            page.evaluate("document.fonts.ready")
            ov = HTML_DIR / f"{st}.overlay.pdf"
            page.pdf(path=str(ov), print_background=False, prefer_css_page_size=True)
            base, over, w = PdfReader(str(main)), PdfReader(str(ov)), PdfWriter()
            for i, p in enumerate(base.pages):
                p.merge_page(over.pages[i])
                w.add_page(p)
            w.add_metadata({"/Title": f"{NAMES[st]} State Talent Profile", "/Subject": "IPEDS state talent profile"})
            out = (out_dir or OUT) / f"{st}.pdf"
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "wb") as f:
                w.write(f)
            for tmp in (main, ov, ov_html):
                tmp.unlink(missing_ok=True)
            done.append(out)
            print(f"{st} -> {out.name} ({n} pages, {out.stat().st_size / 1e3:.0f} kB)")
        browser.close()
    return done


BLANK_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
@page {{ size: 8.5in 11in; margin: 0 }} html,body {{ margin:0 }}
.p {{ width: 8.5in; height: 11in; display: grid; place-items: center; font: italic 400 15px 'EB Garamond', serif; color: #6f6a64 }}
</style></head><body><div class="p">This page intentionally left blank.</div></body></html>"""


def blank_page(page=None) -> Path:
    """A single 8.5 x 11 in "This page intentionally left blank." page, set like the template's blank pages."""
    out = HTML_DIR / "blank.pdf"
    if out.exists():
        return out
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    h = HTML_DIR / "blank.html"
    h.write_text(BLANK_HTML.format(fonts=font_css()))
    def _print(pg):
        pg.goto(h.as_uri()); pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(out), print_background=True, prefer_css_page_size=True)
    if page is not None:
        _print(page)
    else:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome"); _print(br.new_page()); br.close()
    h.unlink(missing_ok=True)
    return out


def print_version(digital: Path, page=None) -> Path:
    """{st}_print.pdf: the digital PDF as single 8.5 x 11 in pages in duplex order, for printing double-sided.

    PDF page 1 is the cover (front of sheet 1) and page 2 its back, "This page intentionally left blank." From
    there each sheet carries two consecutive folios: sheet 2 is folio 2 (front) and 3 (back), sheet 3 is 4 and 5,
    and so on. Each 17 x 11 in spread is cut at the gutter into its left and right pages. A blank page is added at
    the end if needed so the last sheet is complete. Charts that ran across a spread continue on the back of
    the same sheet. The landscape By the Numbers pages (11 x 8.5 in) are turned a quarter turn onto 8.5 x 11 in
    pages, top of the table toward the left edge, so every page of the booklet has the same size."""
    from pypdf import PdfReader, PdfWriter
    from pypdf import PageObject, Transformation
    from pypdf.generic import RectangleObject
    left, right, w = PdfReader(str(digital)), PdfReader(str(digital)), PdfWriter()   # two readers: independent page objects
    blank = PdfReader(str(blank_page(page))).pages[0]
    for i, (pl, pr) in enumerate(zip(left.pages, right.pages)):
        x0, y0, x1, y1 = (float(v) for v in pl.mediabox)
        wd, ht = x1 - x0, y1 - y0
        if wd > ht * 1.4:                                   # a 17 x 11 in spread: split at the gutter
            mid = (x0 + x1) / 2
            for pg, box in ((pl, (x0, y0, mid, y1)), (pr, (mid, y0, x1, y1))):
                pg.mediabox = pg.cropbox = RectangleObject(box)
                w.add_page(pg)
        elif wd > ht:                                       # an 11 x 8.5 in landscape page (By the Numbers):
            pg = PageObject.create_blank_page(width=ht, height=wd)   # turned onto an 8.5 x 11 in page, top toward the spine side
            pg.merge_transformed_page(pl, Transformation().translate(-x0, -y0).rotate(90).translate(ht, 0))
            w.add_page(pg)
        else:
            w.add_page(pl)
            if i == 0:                                      # back of the cover
                w.add_page(blank)
    if len(w.pages) % 2:                                    # finish the last sheet
        w.add_page(blank)
    w.add_metadata({**(left.metadata or {}), "/Subject": "State talent profile (print, 8.5 x 11 in pages, duplex order)"})
    w.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)   # both halves share one copy
    out = digital.with_name(digital.stem + "_print.pdf")
    with open(out, "wb") as f:
        w.write(f)
    return out


ZIP_NAME = "State_Talent_Profiles_all_states.zip"
ZIP_PRINT = "State_Talent_Profiles_all_states_print.zip"


def file_name(st: str, kind: str = "digital") -> str:
    return NAMES[st].replace(" ", "_") + "_State_Talent_Profile" + ("_print" if kind == "print" else "") + ".pdf"


def zip_all() -> list[Path]:
    """One zip of the digital PDFs (spreads) and one of the print PDFs (8.5 x 11 pages)."""
    import zipfile
    out = []
    for name, suffix, kind in ((ZIP_NAME, "", "digital"), (ZIP_PRINT, "_print", "print")):
        z = OUT / name
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as f:   # deflate: the print PDFs shrink by half (stays under GitHub's 100 MB file limit)
            for st in sorted(S.TILES, key=lambda s: NAMES[s]):
                p = OUT / f"{st}{suffix}.pdf"
                if p.exists():
                    f.write(p, file_name(st, kind))
        out.append(z)
    return out


def write_viewer() -> Path:
    """profiles/viewer.html: view a state's PDF, download it, or download all 51 as one zip."""
    from .states_explorer import kit_css, site_nav
    states = sorted(S.TILES, key=lambda s: NAMES[s])
    opts = "".join(f'<option value="{s}">{NAMES[s]}</option>' for s in states)
    names = json.dumps({s: NAMES[s] for s in states})
    fnames = json.dumps({s: file_name(s) for s in states})
    pnames = json.dumps({s: file_name(s, "print") for s in states})
    dl = '<svg class="i" viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 19h14"/></svg>'
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>State Talent Profile PDF</title><style>{kit_css()}
html,body{{height:100%;margin:0}} body{{display:flex;flex-direction:column;background:var(--bg)}}
.bar{{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;padding:10px max(16px,env(safe-area-inset-right,0px)) 10px max(16px,env(safe-area-inset-left,0px));border-bottom:1px solid var(--rule-2)}}
.brand{{font-weight:700;font-size:16px;margin-right:6px}} .grow{{flex:1}}
.btn.primary svg.i, .btn svg.i{{width:16px;height:16px}}
main{{flex:1;min-height:0;background:#525659}} iframe{{width:100%;height:100%;border:0;display:block}}
.note{{font-size:12.5px;color:var(--ink-3)}}
.fmtnote{{margin:0;padding:6px max(16px,env(safe-area-inset-left,0px));font-size:12.5px;color:var(--ink-3);border-bottom:1px solid var(--rule-2)}}
</style></head><body>
{site_nav("profiles", "../")}
<div class="bar"><span class="brand">State Talent Profile PDF</span>
<label class="lab" for="st">State</label><select id="st">{opts}</select>
<span class="note" id="meta"></span><span class="grow"></span>
<a class="btn link" id="prof" href="#">Interactive profile</a>
<div class="seg" role="group" aria-label="PDF format"><button id="fd" aria-pressed="true" title="Two-page spreads, for reading on screen">Digital</button><button id="fp" aria-pressed="false" title="Single 8.5 x 11 in pages in booklet order, for printing">Print</button></div>
<a class="btn primary" id="dl" href="#" download>{dl}Download PDF</a>
<a class="btn" id="all" href="pdf/{ZIP_NAME}" download="{ZIP_NAME}" title="All 51 state PDFs in one zip file">{dl}Download all PDFs</a></div>
<p class="fmtnote" id="fmtnote"></p>
<main><iframe id="pdf" title="State Talent Profile PDF"></iframe></main>
<script>
const N = {names}, F = {fnames}, FP = {pnames}, $ = id => document.getElementById(id);
let fmt = "digital", cur = "CA";
const NOTE = {{digital: "Digital: two-page spreads, as the profile is meant to be read on screen.",
  print: "Print: every page 8.5 × 11 in, in order for double-sided printing: the cover with a blank back, then two pages per sheet (2 and 3, 4 and 5, …). Print double-sided, flip on the long edge."}};
function setFmt(f) {{ fmt = f; $("fd").setAttribute("aria-pressed", f === "digital"); $("fp").setAttribute("aria-pressed", f === "print");
  $("all").href = "pdf/" + (f === "print" ? "{ZIP_PRINT}" : "{ZIP_NAME}"); $("all").setAttribute("download", f === "print" ? "{ZIP_PRINT}" : "{ZIP_NAME}");
  $("fmtnote").textContent = NOTE[f]; show(cur); }}
$("fd").onclick = () => setFmt("digital"); $("fp").onclick = () => setFmt("print");
function show(s) {{ if (!N[s]) s = "CA"; cur = s; const file = "pdf/" + s + (fmt === "print" ? "_print" : "") + ".pdf";
  $("st").value = s; $("pdf").src = file + "#view=FitH";
  $("dl").href = file; $("dl").setAttribute("download", fmt === "print" ? FP[s] : F[s]); $("prof").href = s + ".html";
  $("meta").textContent = "Compared with the four states closest in enrollment"; document.title = N[s] + " State Talent Profile PDF";
  try {{ history.replaceState(null, "", "#" + s); }} catch (e) {{}} }}
$("st").onchange = e => show(e.target.value);
addEventListener("hashchange", () => show(location.hash.slice(1).toUpperCase()));
try {{ const t = localStorage.getItem("se-theme"); if (t) document.documentElement.dataset.theme = t; }} catch (e) {{}}
cur = location.hash.slice(1).toUpperCase() || "CA";   // read the state before setFmt redraws (show() rewrites the hash)
setFmt(new URLSearchParams(location.search).get("format") === "print" ? "print" : "digital");
</script></body></html>"""
    out = PROF / "viewer.html"
    out.write_text(html)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    sts = list(S.TILES) if (not args or "--all" in args) else [a.upper() for a in args]
    render(sts)
    print("viewer:", write_viewer(), "| zips:", ", ".join(p.name for p in zip_all()))
