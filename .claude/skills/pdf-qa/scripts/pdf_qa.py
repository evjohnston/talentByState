"""QA for the State Talent Profile PDFs (ipeds_clean/templates/state_pdf.html + ipeds_clean/state_pdf.py).

    uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py                 # layout checks on the sample states
    uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py CA NY --pdf     # also rebuild those PDFs, check fonts/pages
    uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py --all           # every state (layout only, ~4 min)
    uv run python .claude/skills/pdf-qa/scripts/pdf_qa.py CA --png        # + PNGs of the paired/rail spreads

Checks, per state, on the rendered HTML (what the PDF prints):
  errors       browser errors or console errors while building
  nan          "NaN" or "undefined" anywhere in the text
  overflow     a box whose content runs past it, vertically OR sideways (two-column prose spills sideways,
               which a height-only check misses): paired-spread prose and headings, rails, stat boxes
  margin       a figure whose bottom passes the bottom margin (y > 990 px of 1056; the report's live area ends at 984)
  figures      figure numbers not 1, 2, 3, ... in reading order (rails included)
  statbox      a stat-box number tagged with a measure (data-m) that differs from that measure's latest value,
               formatted the way By the Numbers formats it
  sbox-height  a stat box that reaches into the prose below it
With --pdf, on the written PDFs: every font embedded (no Type3, no missing FontFile) and an even page count for
the print version. Exit code 1 if anything is flagged.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

SAMPLE = ["CA", "TX", "WY", "DC", "VT", "RI"]   # largest, mid, smallest, no-state DC, small New England, smallest state
OUT = ROOT / "cache" / "pdf_qa"

JS = r"""(() => {
  const sec = e => e.closest('section'), rel = e => Math.round(e.getBoundingClientRect().bottom - sec(e).getBoundingClientRect().top);
  const over = e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1;
  const sel = s => [...document.querySelectorAll(s)];
  const txt = document.body.innerText;
  const figs = sel('.fig .ft em, .prail .fno').map(e => e.textContent.trim());
  const fn = figs.filter(f => f.startsWith('Figure')).map(f => +f.split(' ')[1]), tn = figs.filter(f => f.startsWith('Table')).map(f => +f.split(' ')[1]);
  const seqBad = a => a.filter((n, i) => n !== i + 1);
  const box = sel('.sbox .stat[data-m], .prail .stat[data-m]').map(e => { const m = e.dataset.m, r = R[m] || {};
    const want = r.v1 == null ? null : fmtSpec(r.v1, r.fmt, r.unit), got = e.querySelector('.v').textContent.trim();
    return want == null || got === want ? null : `${m}: box ${got} vs table ${want}`; }).filter(Boolean);
  const sbH = sel('.sbox').filter(e => e.getBoundingClientRect().bottom - e.closest('.pg').getBoundingClientRect().top > 262 - 6).length;
  const sections = sel('section');
  /* reconciliation: numbers that must agree with each other */
  const usHundred = (txt.match(/U\.S\.\s*100(\.0)?%/g) || []).length;          // share-of-U.S. measures have no U.S. value
  /* chart text that collides: any two labels in one SVG overlapping by more than 3 x 4 px */
  const collide = []; document.querySelectorAll('section.spread svg').forEach(svg => { const ts = [...svg.querySelectorAll('text')].filter(t => t.textContent.trim()).map(t => ({t, r: t.getBoundingClientRect()})).filter(o => o.r.width > 0);
    for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) { const a = ts[i].r, b = ts[j].r, w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w > 3 && h > 4) collide.push(ts[i].t.textContent.slice(0, 24) + ' / ' + ts[j].t.textContent.slice(0, 24)); } });
  /* spacing: a figure title closer than 18 px to the text above it, and facing pages whose body text starts at different heights */
  const tight = [], misalign = [];
  document.querySelectorAll('section.spread .rcol .r-fig, section.spread .abs > .fig').forEach(f => { const prev = f.previousElementSibling; if (!prev) return;
    const g = f.getBoundingClientRect().top - prev.getBoundingClientRect().bottom; if (g < 18) tight.push(((f.querySelector('.ft') || {}).textContent || '').slice(0, 40) + ` (${Math.round(g)} px)`); });
  document.querySelectorAll('section.spread').forEach(sp => { const b = [...sp.querySelectorAll(':scope > .pg')].map(pg => { const e = pg.querySelector('.rcol'); return e ? e.getBoundingClientRect().top - pg.getBoundingClientRect().top : null; });
    if (b[0] != null && b[1] != null && b[1] > b[0] + 40) misalign.push(Math.round(b[1] - b[0])); });   // a right page left blank at the top
  const vagueAx = [...document.querySelectorAll('section.spread text.ylab, section.spread .xax')].filter(e => /^(Percent|Number|Dollars)?$/.test(e.textContent.trim())).length;
  const dotLead = [...document.querySelectorAll('.stat .c, .t9 .c')].filter(e => /^\s*·/.test(e.textContent)).length;   // caption opening on a separator
  const szEx = [...txt.matchAll(/.{0,70}[+−-]0\.0(?!\d)\s*(pp|pts|points|%)/g)].map(m => m[0]), signedZero = szEx.length;   // '+0.0 pp' reads as a change
  const usDash = (txt.match(/U\.S\.\s*[–-]\s*[)·,;]/g) || []).length;          // a U.S. comparison with no value
  const isec = P.institutions && P.institutions.sectors, nInst = isec ? isec.v.reduce((a, s) => a + (s[s.length - 1] || 0), 0) : null;
  const instBox = sel('.stat').filter(e => /^Degree-granting institutions/.test(e.querySelector('.l')?.textContent || '')).map(e => e.querySelector('.v').textContent.trim());
  const instMismatch = nInst == null ? [] : instBox.filter(v => v !== nf(nInst)).map(v => `box ${v} vs sectors ${nf(nInst)}`);
  const sv = P.sevis, stemN = sv ? sv.stem.flows.reduce((o, f) => (o[f.c] = (o[f.c] || 0) + f.n, o), {}) : {};
  const stemOver = sv ? Object.entries(stemN).filter(([c, n]) => { const t = sv.top.find(x => x.country === c); return t && n > t.n; }).map(([c]) => c) : [];
  const sevisNoteMissing = stemOver.length && /Which Countries Supply/.test(txt) && !/does not draw its STEM pages/.test(txt) ? stemOver : [];
  /* dot plots: a state's value label must sit nearer the state's filled dot than the U.S. open dot (or name the state) */
  const dumbBad = [];
  sel('svg').forEach(s => { const fill = [...s.querySelectorAll('circle')].filter(c => c.getAttribute('fill') === CRIM), open = [...s.querySelectorAll('circle')].filter(c => c.getAttribute('fill') === '#fff');
    if (!fill.length || !open.length || [...s.querySelectorAll('text')].some(t => t.textContent.trim() === 'Gap')) return;   // value-column plots print values in columns, not beside dots
    const labs = [...s.querySelectorAll('text')].filter(t => (t.getAttribute('style') || '').includes(CRIM) && /%$/.test(t.textContent.trim()));
    fill.forEach(f => { const y = +f.getAttribute('cy'), o = open.find(c => Math.abs(+c.getAttribute('cy') - y) < 1); if (!o) return;
      const l = labs.find(t => Math.abs(+t.getAttribute('y') - y) < 6); if (!l || l.textContent.trim().startsWith(ST)) return;
      const b = l.getBBox(), d = x => Math.min(Math.abs(b.x - x), Math.abs(b.x + b.width - x)), fx = +f.getAttribute('cx'), ox = +o.getAttribute('cx');
      if (Math.abs(fx - ox) > 14 && d(ox) < d(fx) - 2) dumbBad.push(l.textContent.trim()); }); });
  return {
    usHundred, usDash, collide: collide.slice(0, 4), collideN: collide.length, vagueAx, tight: tight.slice(0, 3), tightN: tight.length, misalign: misalign.length, dotLead, signedZero, szEx: szEx.slice(0, 2), instMismatch, sevisNoteMissing, dumbBad: dumbBad.slice(0, 6), dumbBadN: dumbBad.length,
    pairs: sel('.phead').length, rails: sel('.prail').length, sheets: sections.length,
    errorsNan: [txt.split('NaN').length - 1, txt.split('undefined').length - 1],
    overflow: {lede: sel('.plede').filter(over).length, head: sel('.phead').filter(over).length, rail: sel('.prail').filter(over).length},
    margin: sel('.pgF').map(rel).filter(v => v > 990).length,
    heroClash: sel('section').filter(s => { const f = s.querySelector('.heroF'), t = s.querySelector('.htxt'); return f && t && f.getBoundingClientRect().bottom > t.getBoundingClientRect().top - 4; }).length,
    tableClash: sel('section').filter(s => { const t = s.querySelector('table.dt'), b = s.querySelector('.band'); return t && b && t.getBoundingClientRect().bottom > b.getBoundingClientRect().top + 1; }).length,
    figGaps: [...seqBad(fn), ...seqBad(tn).map(n => 'T' + n)],
    statbox: box, sboxHigh: sbH,
    newSheets: sections.map((s, i) => s.querySelector('.phead, .prail') ? i + 1 : 0).filter(Boolean),
    ledeKept: sel('.plede').map(e => e.querySelectorAll('p').length),
  };
})()"""


SUMJS = r"""(() => { const ps = [...document.querySelectorAll('.sum')], o = {pages: ps.length, clash: [], wide: []};
  ps.forEach((p, i) => { const f = p.querySelector('.foot').getBoundingClientRect().top;
    const bot = Math.max(...[...p.querySelectorAll('.body *')].map(k => k.getBoundingClientRect().bottom));
    if (bot > f - 4) o.clash.push(i + 1); if (p.scrollWidth > p.clientWidth + 1) o.wide.push(i + 1); });
  const t = document.body.innerText;
  o.nan = (t.match(/NaN|undefined|Infinity/g) || []).length;
  o.usDash = (t.match(/U\.S\.\s*[–-]\s*[)·,;]/g) || []).length;
  o.signedZero = (t.match(/[+−-]0\.0(?!\d)\s*(pp|pts|%)/g) || []).length;
  o.dcThe = D.st === 'DC' ? (t.match(/(^|[^Tt]he )District of Columbia('s)? (ranks|compares|and states|\d)/gm) || []).length : 0;
  return o; })()"""


def summary_layout(states: list[str]) -> dict:
    """The two-sided summary (variant "summary"): two pages, nothing into the footer or off the page edge."""
    from playwright.sync_api import sync_playwright
    from ipeds_clean import state_pdf as sp
    from ipeds_clean.peers import presets
    Pn = sp.Panel(); peers = presets(Pn.sp)["size"]["peers"]; fonts = sp.font_css()
    res = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome")
        for st in states:
            pg = b.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(sp.write_html(Pn, st, peers[st], fonts, "summary").as_uri())
            try:
                pg.wait_for_function("window.__ready === true", timeout=40000)
                r = pg.evaluate(SUMJS)
            except Exception as e:
                r = {"pages": 0}; errs.append(str(e)[:120])
            out = [f"summary: {e}" for e in errs[:2]]
            if r.get("pages") != 2: out.append(f"summary: {r.get('pages')} pages, not 2")
            if r.get("clash"): out.append(f"summary: content runs into the footer on page(s) {r['clash']}")
            if r.get("wide"): out.append(f"summary: content wider than the page on page(s) {r['wide']}")
            for k, lab in (("nan", "NaN/undefined"), ("usDash", "'U.S. –'"), ("signedZero", "signed zero"), ("dcThe", "'District of Columbia' without 'the'")):
                if r.get(k): out.append(f"summary: {lab} printed {r[k]} time(s)")
            res[st] = out
            pg.close()
        b.close()
    return res


def layout(states: list[str]) -> dict:
    from playwright.sync_api import sync_playwright
    from ipeds_clean import state_pdf as sp
    from ipeds_clean.peers import presets
    Pn = sp.Panel(); peers = presets(Pn.sp)["size"]["peers"]; fonts = sp.font_css()
    res = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome")
        for st in states:
            pg = b.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
            pg.goto(sp.write_html(Pn, st, peers[st], fonts).as_uri())
            try:
                pg.wait_for_function("window.__ready === true", timeout=40000)
            except Exception:
                errs.append("not ready after 40 s")
            r = pg.evaluate(JS) if not errs else {}
            r["errors"] = errs[:3]
            res[st] = r
            pg.close()
        b.close()
    return res


def flags(r: dict) -> list[str]:
    out = []
    if r.get("errors"): out.append(f"errors {r['errors']}")
    if any(r.get("errorsNan", [])): out.append(f"NaN/undefined {r['errorsNan']}")
    ov = r.get("overflow", {})
    if any(ov.values()): out.append(f"overflow {ov}")
    if r.get("margin"): out.append(f"{r['margin']} figure(s) past the bottom margin")
    if r.get("heroClash"): out.append(f"{r['heroClash']} spread chart(s) run into the text block below")
    if r.get("tableClash"): out.append(f"{r['tableClash']} table(s) run into the shaded band below")
    if r.get("figGaps"): out.append(f"figure numbering {r['figGaps']}")
    if r.get("statbox"): out.append(f"stat box vs table {r['statbox']}")
    if r.get("sboxHigh"): out.append(f"{r['sboxHigh']} stat box(es) reach the prose")
    if r.get("ledeKept") and min(r["ledeKept"]) < 1: out.append("a paired page lost all its prose")
    if r.get("dotLead"): out.append(f"{r['dotLead']} stat caption(s) start with '·'")
    if r.get("signedZero"): out.append(f"signed zero change (+0.0/−0.0) printed {r['signedZero']} time(s): {r.get('szEx')}")
    if r.get("collideN"): out.append(f"{r['collideN']} chart label collision(s): {r.get('collide')}")
    if r.get("vagueAx"): out.append(f"{r['vagueAx']} figure(s) with an axis title that only names the unit")
    if r.get("tightN"): out.append(f"{r['tightN']} figure(s) crowding the text above: {r.get('tight')}")
    if r.get("misalign"): out.append(f"{r['misalign']} spread(s) whose right page starts well below the left page (blank band under the running head)")
    if r.get("usDash"): out.append(f"'U.S. –' printed {r['usDash']} time(s) (drop the comparison when the U.S. value is missing)")
    if r.get("usHundred"): out.append(f"'U.S. 100%' printed {r['usHundred']} time(s) (share-of-U.S. measures have no U.S. value)")
    if r.get("instMismatch"): out.append(f"institution count {r['instMismatch']}")
    if r.get("sevisNoteMissing"): out.append(f"STEM count above all-level count without the DHS note: {r['sevisNoteMissing']}")
    if r.get("dumbBadN"): out.append(f"{r['dumbBadN']} dot-plot label(s) nearer the U.S. dot than the state's: {r['dumbBad']}")
    return out


def pdf_checks(states: list[str]) -> dict:
    from pypdf import PdfReader
    from ipeds_clean import state_pdf as sp
    sp.render(states)
    res = {}
    for st in states:
        issues = []
        for p in (sp.OUT / f"{st}.pdf", sp.OUT / f"{st}_print.pdf"):
            r = PdfReader(p)
            if p.stem.endswith("_print") and len(r.pages) % 2:
                issues.append(f"{p.name}: odd page count {len(r.pages)}")
            for pg in r.pages:
                for _, f in ((pg.get("/Resources") or {}).get("/Font") or {}).items():
                    f = f.get_object()
                    if f.get("/Subtype") == "/Type3":
                        issues.append(f"{p.name}: Type3 font"); continue
                    fd = f["/DescendantFonts"][0].get_object().get("/FontDescriptor") if f.get("/Subtype") == "/Type0" else f.get("/FontDescriptor")
                    if fd is not None and not any(k in fd.get_object() for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                        issues.append(f"{p.name}: {f.get('/BaseFont')} not embedded")
        res[st] = sorted(set(issues))
    sp.render(states, "summary")
    for st in states:
        p = sp.OUT / f"{st}_summary.pdf"; r = PdfReader(p); issues = []
        if len(r.pages) != 2:
            issues.append(f"{p.name}: {len(r.pages)} pages, not 2")
        for pg in r.pages:
            for _, f in ((pg.get("/Resources") or {}).get("/Font") or {}).items():
                f = f.get_object()
                if f.get("/Subtype") == "/Type3":
                    issues.append(f"{p.name}: Type3 font")
        res[st] = sorted(set(res[st] + issues))
    return res


def pngs(st: str, sheets: list[int]) -> list[Path]:
    import pypdfium2 as pdfium
    from ipeds_clean import state_pdf as sp
    d = OUT / st; d.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(sp.OUT / f"{st}.pdf"))
    out = []
    for n in sheets:
        if n <= len(pdf):
            im = pdf[n - 1].render(scale=1.0).to_pil(); p = d / f"sheet{n:02d}.png"; im.save(p); out.append(p)
            im.convert("L").save(d / f"sheet{n:02d}_grey.png")   # what an office printer in greyscale shows
    return out


def main(argv: list[str]) -> int:
    from ipeds_clean import states as S
    opts = {a for a in argv if a.startswith("--")}
    sts = [a.upper() for a in argv if not a.startswith("--")] or (list(S.TILES) if "--all" in opts else SAMPLE)
    lay = layout(sts)
    summ = summary_layout(sts)
    pdfr = pdf_checks(sts) if ("--pdf" in opts or "--png" in opts) else {}
    bad = 0
    for st in sts:
        f = flags(lay[st]) + summ.get(st, []) + pdfr.get(st, [])
        bad += bool(f)
        r = lay[st]
        print(f"{st}: {'OK' if not f else 'FLAGGED'}  sheets {r.get('sheets')}, paired {r.get('pairs')}, rails {r.get('rails')}, "
              f"prose paragraphs kept min {min(r.get('ledeKept') or [0])}")
        for x in f:
            print("   -", x)
        if "--png" in opts and r.get("newSheets"):
            ps = pngs(st, r["newSheets"])
            print(f"   PNGs of {len(ps)} paired/rail sheets in {OUT / st}")
    print(f"\n{len(sts)} state(s), {bad} flagged" + ("" if pdfr else " (layout only; add --pdf for fonts and page counts)"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
