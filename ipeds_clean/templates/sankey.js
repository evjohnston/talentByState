/* Animated Sankey: saturated vertical node bars, low-opacity ribbons, dots travelling source -> target.
   sankey(el, {nodes: [{id, label, col, color, sub}], links: [{s, t, v}], fmt, H, colLabels, gap})
   Nodes are placed in the column given by `col`, ordered as listed; heights are proportional to flow. */
const SANKEY = {runs: new Set()};
function sankey(el, opt) {
  for (const r of SANKEY.runs) if (r.el === el) { cancelAnimationFrame(r.raf); r.io && r.io.disconnect(); SANKEY.runs.delete(r); }
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fmt = opt.fmt || (v => Math.round(v).toLocaleString("en-US"));
  const H = opt.H || 420, nw = 14, gap = opt.gap ?? 10, top = opt.colLabels ? 26 : 6, bot = 8;
  el.innerHTML = ""; const W = Math.max(320, el.clientWidth || 720);
  const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("height", H); svg.style.width = "100%"; svg.style.display = "block"; svg.style.overflow = "visible";
  svg.setAttribute("role", "img"); svg.setAttribute("aria-label", opt.label || "Flow diagram");
  el.appendChild(svg);
  const nodes = opt.nodes.map(n => ({...n, inV: 0, outV: 0})), byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const links = opt.links.filter(l => l.v > 0 && byId[l.s] && byId[l.t]).map(l => ({...l, S: byId[l.s], T: byId[l.t]}));
  links.forEach(l => { l.S.outV += l.v; l.T.inV += l.v; });
  nodes.forEach(n => n.v = Math.max(n.inV, n.outV));
  const colsN = Math.max(...nodes.map(n => n.col)) + 1;
  let labW = opt.labelW || Math.min(170, W * .2);
  // narrow screens: columns move to the edges and labels go inside, beside their own bars
  const narrow = W < 2 * labW + 300; if (narrow) labW = 4;
  const xs = c => colsN === 1 ? labW : labW + c * ((W - 2 * labW - nw) / (colsN - 1));
  const colNodes = [...Array(colsN)].map((_, c) => nodes.filter(n => n.col === c && n.v > 0));
  const k = Math.min(...colNodes.map(ns => (H - top - bot - gap * Math.max(0, ns.length - 1)) / (ns.reduce((a, n) => a + n.v, 0) || 1)));
  colNodes.forEach((ns, c) => { const tot = ns.reduce((a, n) => a + n.v * k, 0) + gap * Math.max(0, ns.length - 1); let y = top + (H - top - bot - tot) / 2;
    ns.forEach(n => { n.x = xs(c); n.y = y; n.h = Math.max(1, n.v * k); y += n.h + gap; n.so = 0; n.to = 0; }); });
  // stack link ends in the order of the opposite node's position, so ribbons do not cross needlessly
  [...links].sort((a, b) => a.T.y - b.T.y).forEach(l => { l.w = l.v * k; l.y0 = l.S.y + l.S.so + l.w / 2; l.S.so += l.w; });
  [...links].sort((a, b) => a.S.y - b.S.y).forEach(l => { l.y1 = l.T.y + l.T.to + l.w / 2; l.T.to += l.w; });
  let h = "";
  if (opt.colLabels) h += opt.colLabels.map((t, c) => `<text x="${xs(c) + nw / 2}" y="14" text-anchor="${c === 0 ? "start" : c === colsN - 1 ? "end" : "middle"}" data-n="${narrow ? 1 : 0}" style="font-size:12px;font-weight:600;fill:var(--ink-2)">${t}</text>`).join("");
  const path = l => { const x0 = l.S.x + nw, x1 = l.T.x, mx = (x0 + x1) / 2; return `M${x0},${l.y0}C${mx},${l.y0} ${mx},${l.y1} ${x1},${l.y1}`; };
  const cid = "skc" + Math.random().toString(36).slice(2, 8);
  h += `<defs><clipPath id="${cid}"><rect x="0" y="0" width="${W}" height="${H}"/></clipPath></defs><g clip-path="url(#${cid})">`;
  links.forEach((l, i) => { l.d = path(l); h += `<path class="sk-l" data-i="${i}" d="${l.d}" fill="none" stroke="${l.color || l.S.color}" stroke-opacity=".16" stroke-width="${Math.max(1, l.w)}"/>`; });
  h += `</g>`;
  nodes.filter(n => n.v > 0).forEach(n => { h += `<rect class="sk-n" data-id="${n.id}" x="${n.x}" y="${n.y}" width="${nw}" height="${n.h}" rx="2" fill="${n.color}"/>`; });
  // labels: every node labelled; within a column, labels are nudged apart so small nodes stay readable
  let lh = ""; const boxes = [], skipped = new Set();
  colNodes.forEach((ns, c) => { const right = c === colsN - 1, left = c === 0, ys = ns.map(n => n.y + n.h / 2);
    for (let i = 1; i < ys.length; i++) if (ys[i] - ys[i - 1] < 15) ys[i] = ys[i - 1] + 15;
    const over = ys.length ? ys[ys.length - 1] - (H - 4) : 0; if (over > 0) for (let i = ys.length - 1; i >= 0; i--) { ys[i] -= over; if (i && ys[i] - ys[i - 1] >= 15) break; }
    ns.forEach((n, i) => { const inR = narrow && right, inL = narrow && left;
      const tx = inR ? n.x - 6 : inL ? n.x + nw + 6 : right ? n.x + nw + 8 : left ? n.x - 8 : n.x + nw + 8;
      const anchor = inR ? "end" : inL ? "start" : right || !left ? "start" : "end", moved = Math.abs(ys[i] - (n.y + n.h / 2)) > 2;
      const txt = n.label + " " + fmt(n.v), bw = txt.length * 6.4, bx = anchor === "start" ? tx : tx - bw, box = {x: bx, y: ys[i] - 11, w: bw, h: 14};
      const hitsBar = narrow && nodes.some(o => o !== n && o.v > 0 && !(box.x > o.x + nw + 2 || box.x + box.w < o.x - 2 || box.y > o.y + o.h || box.y + box.h < o.y));
      if (hitsBar) { skipped.add(n.id); return; }
      if (narrow && (boxes.some(o => !(box.x > o.x + o.w || box.x + box.w < o.x || box.y > o.y + o.h || box.y + box.h < o.y)) || box.x < 0 || box.x + box.w > W)) { skipped.add(n.id); return; }
      boxes.push(box);
      if (moved) lh += `<line x1="${anchor === "start" ? n.x + nw + 1 : n.x - 1}" x2="${anchor === "start" ? tx - 2 : tx + 2}" y1="${n.y + n.h / 2}" y2="${ys[i] - 4}" stroke="var(--rule-2)"/>`;
      lh += `<text x="${tx}" y="${ys[i]}" text-anchor="${anchor}" style="font-size:12px;fill:var(--ink);paint-order:stroke;stroke:var(--bg);stroke-width:4px;stroke-linejoin:round"><tspan style="font-weight:600">${n.label}</tspan><tspan style="fill:var(--ink-3)"> ${fmt(n.v)}</tspan></text>`; }); });
  const g = document.createElementNS(NS, "g"); g.setAttribute("class", "sk-dots"); g.setAttribute("clip-path", `url(#${cid})`);
  svg.innerHTML = h; svg.appendChild(g);
  const lg = document.createElementNS(NS, "g"); lg.setAttribute("class", "sk-labels"); lg.style.pointerEvents = "none"; svg.appendChild(lg); lg.innerHTML = lh;
  if (narrow && skipped.size) { // a key keeps every node readable on small screens
    const key = document.createElement("div"); key.className = "legend"; key.style.marginTop = "8px";
    key.innerHTML = colNodes.map((ns, c) => ns.map(n => `<span><i style="background:${n.color}"></i>${n.label} <b style="font-weight:600">${fmt(n.v)}</b></span>`).join("")).join("");
    el.appendChild(key); }
  // travelling dots: count proportional to flow, speed constant along every ribbon
  const total = links.reduce((a, l) => a + l.v, 0) || 1, P = [];
  // Each ribbon's centre line is sampled once into a table of points and unit normals, so the animation loop never
  // queries SVG geometry (getPointAtLength in every frame is what made the dots stutter).
  const STEP = 1.5;
  const table = p => { const len = p.getTotalLength(), n = Math.max(2, Math.ceil(len / STEP) + 1), xy = new Float32Array(n * 2), nr = new Float32Array(n * 2);
    for (let k = 0; k < n; k++) { const q = p.getPointAtLength(len * k / (n - 1)); xy[2 * k] = q.x; xy[2 * k + 1] = q.y; }
    for (let k = 0; k < n; k++) { const a = Math.max(0, k - 1), b = Math.min(n - 1, k + 1), dx = xy[2 * b] - xy[2 * a], dy = xy[2 * b + 1] - xy[2 * a + 1], m = Math.hypot(dx, dy) || 1;
      nr[2 * k] = -dy / m; nr[2 * k + 1] = dx / m; }
    return {len, n, xy, nr}; };
  links.forEach((l, i) => { const p = svg.querySelector(`.sk-l[data-i="${i}"]`), T = table(p), n = Math.max(1, Math.min(40, Math.round(l.v / total * (opt.dots || 160))));
    for (let j = 0; j < n; j++) { const c = document.createElementNS(NS, "circle"); c.setAttribute("r", Math.min(2.6, 1.2 + l.w / 14)); c.setAttribute("fill", l.color || l.S.color); c.setAttribute("fill-opacity", ".85"); g.appendChild(c);
      // each dot has its own pace (0.55-1.45x the average) and a slow, individual surge-and-ease, so dots pass one another
      P.push({c, T, t: Math.random(), off: (Math.random() - .5) * Math.max(0, l.w - 3) * .8,
              v: .55 + Math.random() * .9, ph: Math.random() * 6.283, fq: .25 + Math.random() * .5}); } });
  const place = (d, f) => { const T = d.T, u = f * (T.n - 1), k = Math.min(T.n - 2, Math.floor(u)), r = u - k, i0 = 2 * k, i1 = i0 + 2;
    const x = T.xy[i0] + (T.xy[i1] - T.xy[i0]) * r + (T.nr[i0] + (T.nr[i1] - T.nr[i0]) * r) * d.off,
          y = T.xy[i0 + 1] + (T.xy[i1 + 1] - T.xy[i0 + 1]) * r + (T.nr[i0 + 1] + (T.nr[i1 + 1] - T.nr[i0 + 1]) * r) * d.off;
    d.c.setAttribute("transform", `translate(${x.toFixed(2)} ${y.toFixed(2)})`); };
  const run = {el, raf: 0, on: true}; SANKEY.runs.add(run);
  if (RM) P.forEach(d => place(d, d.t));
  else { let last = performance.now(); const speed = 70; // px per second
    // only animate while the chart is on screen; time spent off screen is skipped, not caught up
    if ("IntersectionObserver" in window) { const io = new IntersectionObserver(es => es.forEach(e => { run.on = e.isIntersecting; if (run.on) { last = performance.now(); if (!run.raf) run.raf = requestAnimationFrame(tick); } }), {rootMargin: "100px"}); io.observe(svg); run.io = io; }
    const tick = now => { run.raf = 0; if (!el.isConnected) { SANKEY.runs.delete(run); run.io && run.io.disconnect(); return; } if (!run.on) return;
      const dt = Math.min(.05, (now - last) / 1000); last = now;
      const sec = now / 1000;
      for (const d of P) { const pace = d.v * (1 + .25 * Math.sin(d.ph + sec * d.fq * 6.283));
        d.t = (d.t + dt * speed * pace / d.T.len) % 1; place(d, d.t); } run.raf = requestAnimationFrame(tick); };
    run.raf = requestAnimationFrame(tick); }
  // hover: a ribbon or a node lifts its flows
  const lit = set => { svg.querySelectorAll(".sk-l").forEach(p => p.setAttribute("stroke-opacity", set ? (set.has(+p.dataset.i) ? ".42" : ".06") : ".16")); };
  const tipf = opt.tip || ((html, e) => {});
  svg.querySelectorAll(".sk-l").forEach(p => { const l = links[+p.dataset.i];
    p.onmousemove = e => { lit(new Set([+p.dataset.i])); tipf(`<b>${l.S.label} → ${l.T.label}</b><br>${fmt(l.v)}${opt.unit ? " " + opt.unit : ""} (${(100 * l.v / l.S.outV).toFixed(0)}% of ${l.S.label})`, e); };
    p.onmouseleave = () => { lit(null); tipf(null); }; });
  svg.querySelectorAll(".sk-n").forEach(r => { const n = byId[r.dataset.id];
    r.onmousemove = e => { lit(new Set(links.map((l, i) => l.S === n || l.T === n ? i : -1).filter(i => i >= 0))); tipf(`<b>${n.label}</b><br>${fmt(n.v)}${opt.unit ? " " + opt.unit : ""}${n.sub ? "<br>" + n.sub : ""}`, e); };
    r.onmouseleave = () => { lit(null); tipf(null); }; });
}
