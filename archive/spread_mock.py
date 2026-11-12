"""Mockups of a two-page-spread layout for the State Talent Profile PDF.

    python -m ipeds_clean.spread_mock CA     # -> data/states/profiles/pdf/_spreads/index.html
"""
from __future__ import annotations

import sys

from .state_pdf import OUT, Panel, font_css, presets, write_html

DEST = OUT / "_spreads"


def build(st: str = "CA") -> None:
    from playwright.sync_api import sync_playwright
    Pn = Panel()
    peers = presets(Pn.sp)["size"]["peers"][st]
    h = write_html(Pn, st, peers, font_css(), "spread")
    DEST.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 1700, "height": 1100}, device_scale_factor=1.5)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(h.as_uri())
        pg.wait_for_function("window.__ready === true", timeout=30000)
        shots = []
        for i, el in enumerate(pg.query_selector_all(".spread")):
            p = DEST / f"{st}-spread{i}.png"
            el.screenshot(path=str(p))
            shots.append(p.name)
        b.close()
    if errs:
        print("page errors:", errs)
    labels = ["Cover (single page, unchanged)", "Pages 2–3 · At a glance", "Pages 4–5 · International dependence",
              "Pages 6–7 · Where students come from", "Pages 8–9 · Competitors", "Pages 10–11 · Students, money and outcomes"]
    items = "".join(f'<figure><figcaption>{labels[i] if i < len(labels) else ""}</figcaption><img src="{s}" alt="{labels[i] if i < len(labels) else s}"></figure>' for i, s in enumerate(shots))
    (DEST / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spread Mockups</title><style>:root{{--bg:#2b2b2b;--ink:#f1f1f1;--mut:#b9b9b9}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,system-ui,sans-serif;padding:24px max(16px,env(safe-area-inset-left,0px))}}
h1{{font-size:24px;margin:0 0 6px}} p{{color:var(--mut);max-width:90ch;margin:0 0 24px}} figure{{margin:0 0 36px}} figcaption{{font-weight:600;margin:0 0 8px}}
img{{max-width:100%;display:block;margin:0 auto;box-shadow:0 6px 24px #0008;cursor:zoom-in}}</style></head><body>
<h1>Two-page spread mockups: {st}</h1><p>Printed as a booklet: the cover stays a single page, then pages 2–3, 4–5 and so on are designed together. Charts and colour bands run across the fold; each spread mixes one large figure with smaller ones and a band of headline numbers. The fold shadow is only for the mockup. Click a spread to open it full size.</p>{items}
<script>document.querySelectorAll("img").forEach(i=>i.onclick=()=>window.open(i.src))</script></body></html>""")
    print("wrote", DEST / "index.html", len(shots), "spreads")


if __name__ == "__main__":
    build((sys.argv[1:] or ["CA"])[0].upper())
