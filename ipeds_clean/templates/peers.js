/* Peer-set menu shared by the sheet and the profiles.
   peerMenu({btn, label, menu, presets, current, focus, names, onPick}) */
function peerMenu(o) {
  const P = o.presets, groups = [...new Set(Object.values(P).map(p => p.group))];
  const nm = s => o.names[s] || s;
  o.label.textContent = o.current() === "custom" ? "Custom" : (P[o.current()] || {}).label || "Custom";
  o.menu.innerHTML = groups.map(g => `<h5>${g === "IPEDS" ? "From IPEDS" : "From other public data (used only to choose states)"}</h5>` +
    Object.entries(P).filter(([, p]) => p.group === g).map(([k, p]) => { const list = (p.peers[o.focus()] || []).map(nm);
      return `<button role="menuitemradio" aria-checked="${k === o.current()}" data-k="${k}"><b>${p.label}</b><span>${p.desc}</span><em>${list.join(", ")}</em></button>`; }).join("")).join("");
  const close = () => { o.menu.hidden = true; o.btn.setAttribute("aria-expanded", "false"); };
  o.btn.onclick = e => { e.stopPropagation(); const open = o.menu.hidden; o.menu.hidden = !open; o.btn.setAttribute("aria-expanded", String(open)); if (open) (o.menu.querySelector('[aria-checked="true"]') || o.menu.querySelector("button")).focus(); };
  o.menu.querySelectorAll("button").forEach(b => b.onclick = () => { close(); o.onPick(b.dataset.k, (P[b.dataset.k].peers[o.focus()] || []).slice()); });
  o.menu.onkeydown = e => { if (e.key === "Escape") { close(); o.btn.focus(); }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const bs = [...o.menu.querySelectorAll("button")], i = bs.indexOf(document.activeElement); bs[(i + (e.key === "ArrowDown" ? 1 : bs.length - 1)) % bs.length].focus(); } };
  if (!peerMenu.bound) { peerMenu.bound = true; document.addEventListener("click", e => { document.querySelectorAll(".pmenu .menu").forEach(m => { if (!m.parentNode.contains(e.target)) { m.hidden = true; m.parentNode.querySelector("button").setAttribute("aria-expanded", "false"); } }); }); }
}
