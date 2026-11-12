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
  margin       a figure whose bottom passes the bottom margin (y > 962 px of 1056)
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
  const isec = P.institutions && P.institutions.sectors, nInst = isec ? isec.v.reduce((a, s) => a + (s[s.length - 1] || 0), 0) : null;
  const instBox = sel('.stat').filter(e => /^Degree-granting institutions/.test(e.querySelector('.l')?.textContent || '')).map(e => e.querySelector('.v').textContent.trim());
  const instMismatch = nInst == null ? [] : instBox.filter(v => v !== nf(nInst)).map(v => `box ${v} vs sectors ${nf(nInst)}`);
  const sv = P.sevis, stemN = sv ? sv.stem.flows.reduce((o, f) => (o[f.c] = (o[f.c] || 0) + f.n, o), {}) : {};
  const stemOver = sv ? Object.entries(stemN).filter(([c, n]) => { const t = sv.top.find(x => x.country === c); return t && n > t.n; }).map(([c]) => c) : [];
  const sevisNoteMissing = stemOver.length && !/does not draw its STEM pages/.test(txt) ? stemOver : [];
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
    usHundred, instMismatch, sevisNoteMissing, dumbBad: dumbBad.slice(0, 6), dumbBadN: dumbBad.length,
    pairs: sel('.phead').length, rails: sel('.prail').length, sheets: sections.length,
    errorsNan: [txt.split('NaN').length - 1, txt.split('undefined').length - 1],
    overflow: {lede: sel('.plede').filter(over).length, head: sel('.phead').filter(over).length, rail: sel('.prail').filter(over).length},
    margin: sel('.pgF').map(rel).filter(v => v > 962).length,
    figGaps: [...seqBad(fn), ...seqBad(tn).map(n => 'T' + n)],
    statbox: box, sboxHigh: sbH,
    newSheets: sections.map((s, i) => s.querySelector('.phead, .prail') ? i + 1 : 0).filter(Boolean),
    ledeKept: sel('.plede').map(e => e.querySelectorAll('p').length),
  };
})()"""


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
    if r.get("figGaps"): out.append(f"figure numbering {r['figGaps']}")
    if r.get("statbox"): out.append(f"stat box vs table {r['statbox']}")
    if r.get("sboxHigh"): out.append(f"{r['sboxHigh']} stat box(es) reach the prose")
    if r.get("ledeKept") and min(r["ledeKept"]) < 1: out.append("a paired page lost all its prose")
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
    return res


def pngs(st: str, sheets: list[int]) -> list[Path]:
    import pypdfium2 as pdfium
    from ipeds_clean import state_pdf as sp
    d = OUT / st; d.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(sp.OUT / f"{st}.pdf"))
    out = []
    for n in sheets:
        if n <= len(pdf):
            p = d / f"sheet{n:02d}.png"; pdf[n - 1].render(scale=1.0).to_pil().save(p); out.append(p)
    return out


def main(argv: list[str]) -> int:
    from ipeds_clean import states as S
    opts = {a for a in argv if a.startswith("--")}
    sts = [a.upper() for a in argv if not a.startswith("--")] or (list(S.TILES) if "--all" in opts else SAMPLE)
    lay = layout(sts)
    pdfr = pdf_checks(sts) if ("--pdf" in opts or "--png" in opts) else {}
    bad = 0
    for st in sts:
        f = flags(lay[st]) + pdfr.get(st, [])
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
