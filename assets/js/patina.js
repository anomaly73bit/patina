(function () {
  const P = window.PATINA;
  const MODELS = P.models, SRC = P.sources, PHOTOS = P.photos || {};
  const byId = Object.fromEntries(MODELS.map(m => [m.id, m]));
  const now = Date.now();
  const LIST = (P.listings.items || []).map(l => {
    const fee = (SRC[l.src] || {}).fee || 0;
    const end = l.endDate ? Math.max(0, Math.ceil((Date.parse(l.endDate) - now) / 864e5)) : l.endDays;
    return Object.assign({}, l, { fee, end: end ?? null });
  });

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = n => "€ " + Math.round(n).toLocaleString("it-IT");
  const mid = m => (m.lo + m.hi) / 2;
  const temp = t => Math.max(0, Math.min(100, (t + 10) / 25 * 100));
  const pct = d => (d >= 0 ? "−" : "+") + Math.abs(d * 100).toFixed(0) + "%";
  const trendCls = t => t > 0 ? "up" : t < 0 ? "down" : "flat";
  const verdict = d => d > .35 ? ["s-bad", "verifica"] : d >= .12 ? ["s-good", "occasione"] : d >= -.05 ? ["s-fair", "prezzo giusto"] : ["s-bad", "caro"];
  const best = id => LIST.filter(l => l.m === id).sort((a, b) => b.disc - a.disc)[0];
  const pageUrl = id => P.base + "orologi/" + id + "/";

  /* ---------- foto ---------- */
  function photosFor(id) {
    const commons = (PHOTOS[id] || []).map(p => ({
      src: p.src, link: p.page, credit: `Foto: ${p.author} · ${p.license} · Wikimedia Commons`
    }));
    const fromListings = LIST.filter(l => l.m === id && l.img).slice(0, 6).map(l => ({
      src: l.img, link: l.url, credit: `Foto dall'annuncio su ${l.src} · ${eur(l.total)}`
    }));
    return commons.concat(fromListings);
  }
  function placeholder(m) {
    let ticks = "";
    for (let i = 0; i < 60; i++) {
      const a = i * 6 * Math.PI / 180, r1 = i % 5 ? 84 : 76;
      ticks += `<line x1="${100 + r1 * Math.sin(a)}" y1="${100 - r1 * Math.cos(a)}" x2="${100 + 90 * Math.sin(a)}" y2="${100 - 90 * Math.cos(a)}" stroke="var(--muted)" stroke-width="${i % 5 ? 1 : 2.5}"/>`;
    }
    return `<svg viewBox="0 0 200 200" role="img" aria-label="Foto non ancora disponibile">
      <circle cx="100" cy="100" r="96" fill="none" stroke="var(--line)" stroke-width="2"/>${ticks}
      <text x="100" y="92" text-anchor="middle" font-family="Italiana,Georgia,serif" font-size="18" fill="var(--ink)">${esc(m.brand)}</text>
      <text x="100" y="112" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--gilt)">REF. ${esc(m.ref)}</text>
      <text x="100" y="140" text-anchor="middle" font-family="IBM Plex Sans,sans-serif" font-size="8" fill="var(--muted)">foto in arrivo dallo scanner</text></svg>`;
  }
  function mountGallery(el, id) {
    const m = byId[id], ph = photosFor(id);
    if (!ph.length) { el.innerHTML = `<div class="main">${placeholder(m)}</div><div class="credit">Nessuna foto libera trovata finora per questa referenza.</div>`; return; }
    el.innerHTML = `<div class="main"><img alt="${esc(m.brand + " " + m.name + " " + m.ref)}"></div>
      <div class="credit"></div>
      ${ph.length > 1 ? `<div class="thumbs">${ph.map((p, i) => `<button type="button" data-i="${i}" aria-label="Foto ${i + 1}"><img src="${esc(p.src)}" alt="" loading="lazy"></button>`).join("")}</div>` : ""}`;
    const img = el.querySelector(".main img"), credit = el.querySelector(".credit");
    const show = i => {
      img.src = ph[i].src;
      credit.innerHTML = ph[i].link ? `<a href="${esc(ph[i].link)}" target="_blank" rel="noopener">${esc(ph[i].credit)}</a>` : esc(ph[i].credit);
      el.querySelectorAll(".thumbs button").forEach((b, j) => b.setAttribute("aria-current", j === i));
    };
    img.onerror = () => { img.replaceWith(Object.assign(document.createElement("div"), { innerHTML: placeholder(m) }).firstChild); };
    el.querySelector(".thumbs")?.addEventListener("click", e => { const b = e.target.closest("button"); if (b) show(+b.dataset.i); });
    show(0);
  }

  /* ---------- curva indicativa 24 mesi ---------- */
  function spark(m) {
    const M = mid(m), start = M / Math.pow(1 + m.t / 100, 2), pts = [];
    for (let i = 0; i < 8; i++) pts.push((start + (M - start) * i / 7) * (1 + .018 * Math.sin(i * 1.7 + m.ref.length)));
    pts[7] = M;
    const W = 320, H = 120, pad = 26, mn = Math.min(...pts, m.lo) * .97, mx = Math.max(...pts, m.hi) * 1.01;
    const x = i => pad + i * (W - pad * 2) / 7, y = v => H - 18 - (v - mn) / (mx - mn) * (H - 34);
    const line = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
    const qs = ["T4 2024", "", "", "T3 2025", "", "", "", "T3 2026"];
    let s = `<rect x="${pad}" y="${y(m.hi)}" width="${W - pad * 2}" height="${y(m.lo) - y(m.hi)}" fill="var(--gilt-soft)"/>`;
    s += `<path d="${line} L${x(7)} ${H - 18} L${x(0)} ${H - 18} Z" fill="var(--gilt)" opacity=".12"/><path d="${line}" fill="none" stroke="var(--gilt)" stroke-width="2"/>`;
    s += `<circle cx="${x(7)}" cy="${y(M)}" r="4" fill="var(--gilt)"/>`;
    qs.forEach((q, i) => { if (q) s += `<text x="${x(i)}" y="${H - 4}" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9" fill="var(--muted)">${q}</text>`; });
    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto" role="img" aria-label="Andamento stimato 24 mesi">${s}</svg>
      <p class="muted" style="font-size:12px;margin-top:4px">Curva indicativa a 24 mesi; la fascia dorata è l'intervallo di stima attuale.</p>`;
  }

  /* ---------- annunci ---------- */
  function dealHTML(l, hl) {
    const m = byId[l.m], [cls, word] = verdict(l.disc);
    const title = `${esc(m.brand)} ${esc(m.name)} <span class="mono muted" style="font-weight:400">${esc(m.ref)}</span>`;
    return `<article class="deal" style="${hl ? "border-color:var(--gilt)" : ""}">
      <div class="score ${cls}"><div>${pct(l.disc)}<small>${word}</small></div></div>
      <div style="min-width:0"><h4>${l.url ? `<a class="title" href="${esc(l.url)}" target="_blank" rel="noopener">${title}</a>` : title}</h4>
        <div class="meta"><span class="tag ${l.type === "Asta" ? "asta" : ""}">${esc(l.type)}</span><span>${esc(l.src)}</span>${l.cty ? `<span>${esc(l.cty)}</span>` : ""}${l.cond ? `<span>${esc(l.cond)}</span>` : ""}${l.end != null ? `<span>chiude tra ${l.end} g</span>` : ""}</div>
        ${l.disc > .35 ? `<div class="flag">Sconto anomalo: controlla foto del movimento, seriale e quadrante prima di offrire.</div>` : ""}</div>
      <div class="price"><b>${eur(l.total)}</b><small>${l.fee ? `${eur(l.p)} + ${Math.round(l.fee * 100)}% comm.` : "prezzo richiesto"}</small><small>stima ${eur(mid(m))}</small></div>
    </article>`;
  }

  /* ---------- scheda (finestra) ---------- */
  function schedaHTML(m) {
    const ls = LIST.filter(l => l.m === m.id).sort((a, b) => b.disc - a.disc);
    return `<div class="sch-head"><div><div class="eyebrow">${esc(m.brand)} · ref. ${esc(m.ref)}</div><h3 id="schTitle">${esc(m.name)}</h3></div>
        <button class="close" type="button" aria-label="Chiudi" data-close>×</button></div>
      <div class="gallery" data-gallery></div>
      <div style="display:grid;gap:14px;align-content:start;min-width:0">
        <p>${esc(m.note)}</p>
        <dl class="kv">
          <dt>Stima Patina</dt><dd>${eur(m.lo)} – ${eur(m.hi)}</dd>
          <dt>Variazione 12 mesi</dt><dd class="${trendCls(m.t)}">${m.t > 0 ? "+" : ""}${m.t}%</dd>
          <dt>Produzione</dt><dd>${esc(m.years)}</dd>
          <dt>Calibro</dt><dd>${esc(m.cal)}</dd>
          <dt>Diametro · cassa</dt><dd>${m.mm} mm · ${esc(m.case)}</dd>
          <dt>Liquidità</dt><dd>${esc(m.liq)}</dd>
        </dl>
        ${spark(m)}
        <div class="mini-deals">${ls.slice(0, 4).map(l => {
          const inner = `<span>${esc(l.src)} · ${esc(l.type)}</span><span class="mono">${eur(l.total)} <span class="${l.disc >= .12 && l.disc <= .35 ? "up" : l.disc < -.05 ? "down" : "muted"}">${pct(l.disc)}</span></span>`;
          return l.url ? `<a href="${esc(l.url)}" target="_blank" rel="noopener">${inner}</a>` : `<div>${inner}</div>`;
        }).join("") || `<span class="muted">Nessun annuncio attivo.</span>`}</div>
        <a class="btn" href="${pageUrl(m.id)}">Apri la scheda completa</a>
      </div>`;
  }
  function openScheda(id) {
    const dlg = document.getElementById("scheda"), body = document.getElementById("schBody");
    body.innerHTML = schedaHTML(byId[id]);
    mountGallery(body.querySelector("[data-gallery]"), id);
    dlg.showModal();
  }
  const dlg = document.getElementById("scheda");
  if (dlg) {
    dlg.addEventListener("click", e => { if (e.target === dlg || e.target.closest("[data-close]")) dlg.close(); });
  }

  /* ---------- pagina singola orologio ---------- */
  const mp = document.getElementById("modelPage");
  if (mp) {
    const id = mp.dataset.id, m = byId[id];
    mountGallery(mp.querySelector("[data-gallery]"), id);
    mp.querySelector("[data-spark]").innerHTML = spark(m);
    const ls = LIST.filter(l => l.m === id).sort((a, b) => b.disc - a.disc);
    mp.querySelector("[data-deals]").innerHTML = ls.map(l => dealHTML(l)).join("") || `<p class="muted">Nessun annuncio attivo per questa referenza.</p>`;
    return;
  }

  /* ---------- pagina principale ---------- */
  if (!document.getElementById("dial")) return;
  let brand = "Tutte", type = "Tutte", sel = MODELS[0].id;
  try { const s = localStorage.getItem("patina-sel"); if (s && byId[s]) sel = s; } catch (e) {}

  document.getElementById("stModels").textContent = MODELS.length;
  document.getElementById("stListings").textContent = LIST.length;
  document.getElementById("stDeals").textContent = LIST.filter(l => l.disc >= .12 && l.disc <= .35).length;

  (function drawDial() {
    const avg = MODELS.reduce((a, m) => a + m.t, 0) / MODELS.length, T = temp(avg);
    let h = `<circle cx="150" cy="150" r="140" fill="var(--surface)" stroke="var(--line)" stroke-width="1.5"/><circle cx="150" cy="150" r="126" fill="none" stroke="var(--line)"/>`;
    for (let i = 0; i <= 60; i++) {
      const a = (-135 + i * 4.5) * Math.PI / 180, major = i % 10 === 0, r1 = major ? 108 : 116;
      h += `<line x1="${150 + r1 * Math.sin(a)}" y1="${150 - r1 * Math.cos(a)}" x2="${150 + 124 * Math.sin(a)}" y2="${150 - 124 * Math.cos(a)}" stroke="${major ? "var(--ink)" : "var(--muted)"}" stroke-width="${major ? 2 : 1}"/>`;
    }
    [["0", -135], ["25", -67.5], ["50", 0], ["75", 67.5], ["100", 135]].forEach(([t, d]) => {
      const a = d * Math.PI / 180;
      h += `<text x="${150 + 92 * Math.sin(a)}" y="${150 - 92 * Math.cos(a) + 4}" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="11" fill="var(--muted)">${t}</text>`;
    });
    const lbl = T < 40 ? "FREDDO" : T < 60 ? "NEUTRO" : T < 75 ? "TIEPIDO" : "CALDO";
    h += `<text x="150" y="102" text-anchor="middle" font-family="Italiana,Georgia,serif" font-size="20" fill="var(--ink)">PATINA</text>
      <text x="150" y="118" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="8" letter-spacing="2" fill="var(--gilt)">INDICE DI MERCATO</text>
      <text x="150" y="214" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="30" font-weight="500" fill="var(--ink)">${Math.round(T)}</text>
      <text x="150" y="232" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9" letter-spacing="2" fill="var(--gilt)">${lbl}</text>
      <g id="hand" style="transform-origin:150px 150px;transform:rotate(-135deg)"><line x1="150" y1="168" x2="150" y2="44" stroke="var(--gilt)" stroke-width="3" stroke-linecap="round"/></g>
      <circle cx="150" cy="150" r="7" fill="var(--ink)"/><circle cx="150" cy="150" r="2.5" fill="var(--gilt)"/>`;
    document.getElementById("dial").innerHTML = h;
    requestAnimationFrame(() => requestAnimationFrame(() => { document.getElementById("hand").style.transform = `rotate(${-135 + T * 2.7}deg)`; }));
    const ups = MODELS.filter(m => m.t > 0).length;
    const hot = [...MODELS].sort((a, b) => b.t - a.t).slice(0, 2).map(m => m.brand).join(" e ");
    const cold = MODELS.filter(m => m.t < 0).map(m => `${m.brand} ${m.name}`);
    document.getElementById("dialCaption").textContent =
      `Variazione media stimata a 12 mesi: ${avg >= 0 ? "+" : ""}${avg.toFixed(1)}%. ${ups} modelli su ${MODELS.length} in crescita; più vivaci ${hot}${cold.length ? `, in calo ${cold.join(", ")}` : ""}.`;
  })();

  function chips(id, vals, cur, set) {
    const el = document.getElementById(id);
    el.innerHTML = vals.map(v => `<button class="chip" aria-pressed="${v === cur}" data-v="${v}">${v}</button>`).join("");
    el.onclick = e => { const b = e.target.closest("button"); if (b) set(b.dataset.v); };
  }

  function renderModels() {
    chips("brandBar", ["Tutte", "Rolex", "Omega", "Heuer", "Altri"], brand, v => { brand = v; renderModels(); });
    const main = ["Rolex", "Omega", "Heuer"];
    const rows = MODELS.filter(m => brand === "Tutte" || (brand === "Altri" ? !main.includes(m.brand) : m.brand === brand));
    document.getElementById("modelRows").innerHTML = rows.map(m => {
      const b = best(m.id);
      return `<tr data-id="${m.id}" class="${m.id === sel ? "sel" : ""}" tabindex="0">
        <td class="mdl"><b>${esc(m.brand)} ${esc(m.name)}</b><small>ref. ${esc(m.ref)}</small></td>
        <td class="mono muted">${esc(m.years)}</td>
        <td class="num">${eur(m.lo)}–${Math.round(m.hi).toLocaleString("it-IT")}</td>
        <td class="num ${trendCls(m.t)}">${m.t > 0 ? "+" : ""}${m.t}%</td>
        <td><span class="temp"><i style="width:${temp(m.t)}%"></i></span></td>
        <td>${esc(m.liq)}</td>
        <td class="num">${b ? `<span class="${b.disc >= .12 && b.disc <= .35 ? "up" : b.disc < -.05 ? "down" : ""}">${pct(b.disc)}</span> <span class="muted">${esc(b.src)}</span>` : "–"}</td></tr>`;
    }).join("");
  }
  const rowsEl = document.getElementById("modelRows");
  rowsEl.addEventListener("click", e => { const tr = e.target.closest("tr"); if (tr) pick(tr.dataset.id, true); });
  rowsEl.addEventListener("keydown", e => { if (e.key === "Enter") { const tr = e.target.closest("tr"); if (tr) pick(tr.dataset.id, true); } });

  function pick(id, open) {
    sel = id;
    try { localStorage.setItem("patina-sel", id); } catch (e) {}
    renderModels(); renderDetail(); renderDeals();
    if (open) openScheda(id);
  }

  function renderDetail() {
    const m = byId[sel], n = LIST.filter(l => l.m === sel).length;
    document.getElementById("detail").innerHTML = `
      <div><div class="eyebrow">${esc(m.brand)} · ref. ${esc(m.ref)}</div><h3>${esc(m.name)}</h3></div>
      ${spark(m)}
      <dl class="kv">
        <dt>Stima Patina</dt><dd>${eur(m.lo)} – ${eur(m.hi)}</dd>
        <dt>Valore centrale</dt><dd>${eur(mid(m))}</dd>
        <dt>Variazione 12 mesi</dt><dd class="${trendCls(m.t)}">${m.t > 0 ? "+" : ""}${m.t}%</dd>
        <dt>Annunci trovati</dt><dd>${n}</dd>
      </dl>
      <button class="btn" type="button" id="openSel" style="border:0;cursor:pointer">Foto e scheda</button>`;
    document.getElementById("openSel").onclick = () => openScheda(sel);
  }

  function renderDeals() {
    chips("typeBar", ["Tutte", "Marketplace", "Asta", "Mercatino"], type, v => { type = v; renderDeals(); });
    const sort = document.getElementById("sortSel").value;
    const ls = LIST.filter(l => type === "Tutte" || l.type === type)
      .sort((a, b) => sort === "price" ? a.total - b.total : sort === "end" ? (a.end ?? 999) - (b.end ?? 999) : b.disc - a.disc)
      .slice(0, 60);
    document.getElementById("deals").innerHTML = ls.map(l => dealHTML(l, l.m === sel)).join("") || `<p class="muted">Nessun annuncio per questo filtro.</p>`;
  }
  document.getElementById("sortSel").addEventListener("change", renderDeals);

  renderModels(); renderDetail(); renderDeals();
  // apertura diretta: index.html#rolex-5513
  const h = location.hash.slice(1);
  if (byId[h]) pick(h, true);
})();
