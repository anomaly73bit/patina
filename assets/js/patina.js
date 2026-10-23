(function () {
  /* ---------- ricerca: orologi e guide ---------- */
  const P = window.PATINA, input = document.getElementById("q"), box = document.getElementById("results");
  if (!input) return;
  const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const escH = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const items = P.models.map(m => ({
    kind: "Orologio", title: `${m.brand} ${m.name} ${m.ref}`, sub: `${m.years} · cal. ${m.cal}`,
    url: P.base + "orologi/" + m.id + "/", text: norm(`${m.brand} ${m.name} ${m.ref} ${m.match.join(" ")} ${m.cal} ${m.note}`)
  })).concat((P.posts || []).map(p => ({ kind: "Guida", title: p.t, sub: p.e, url: p.u, text: norm(`${p.t} ${p.e} ${p.c}`) })));
  let sel = -1, hits = [];
  function mark(s, words) {
    let out = escH(s);
    words.forEach(w => { if (w.length > 1) out = out.replace(new RegExp(`(${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig"), "<mark>$1</mark>"); });
    return out;
  }
  function run() {
    const q = norm(input.value.trim());
    if (!q) { box.hidden = true; return; }
    const words = q.split(/\s+/);
    hits = items.map(it => {
      if (!words.every(w => it.text.includes(w))) return null;
      const t = norm(it.title);
      return { it, score: words.reduce((a, w) => a + (t.includes(w) ? 3 : 1), 0) + (it.kind === "Orologio" ? 1 : 0) };
    }).filter(Boolean).sort((a, b) => b.score - a.score).slice(0, 8).map(h => h.it);
    sel = -1;
    box.innerHTML = hits.length ? hits.map((h, i) => `<a href="${escH(h.url)}" data-i="${i}"><small>${h.kind}</small><b>${mark(h.title, input.value.trim().split(/\s+/))}</b><span>${escH(h.sub).slice(0, 110)}</span></a>`).join("")
      : `<div class="none">Nessun risultato per «${escH(input.value.trim())}».</div>`;
    box.hidden = false;
  }
  input.addEventListener("input", run);
  input.addEventListener("focus", run);
  input.addEventListener("keydown", e => {
    const links = box.querySelectorAll("a");
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault(); if (!links.length) return;
      sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
      links.forEach((a, i) => a.classList.toggle("on", i === sel));
    } else if (e.key === "Enter") {
      const a = links[sel >= 0 ? sel : 0]; if (a) location.href = a.href;
    } else if (e.key === "Escape") { box.hidden = true; input.blur(); }
  });
  document.addEventListener("click", e => { if (!e.target.closest(".search")) box.hidden = true; });
})();

(function () {
  const P = window.PATINA;
  const MODELS = P.models, SRC = P.sources, PHOTOS = P.photos || {};
  const byId = Object.fromEntries(MODELS.map(m => [m.id, m]));
  const now = Date.now();
  // annunci venduti o aste già chiuse spariscono subito, anche tra un giro dello scanner e l'altro
  const LIST = (P.listings.items || []).map(l => {
    const fee = (SRC[l.src] || {}).fee || 0;
    const endMs = l.endDate ? Date.parse(l.endDate) : (l.endDays != null ? now + l.endDays * 864e5 : null);
    return Object.assign({}, l, { fee, endMs, end: endMs });
  }).filter(l => !l.sold && l.type !== "Asta" && !(l.endMs && l.endMs <= now));

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = n => "€ " + Math.round(n).toLocaleString("it-IT");
  const mid = m => (m.lo + m.hi) / 2;
  const temp = t => Math.max(0, Math.min(100, (t + 10) / 25 * 100));
  const pct = d => (d >= 0 ? "−" : "+") + Math.abs(d * 100).toFixed(0) + "%";
  const trendCls = t => t > 0 ? "up" : t < 0 ? "down" : "flat";
  // verdetto dato dal robot per ogni annuncio (scanner/evaluate.py); il calcolo semplice resta solo come riserva
  const VCLS = { "occasione": "s-good", "prezzo giusto": "s-fair", "da verificare": "s-fair", "caro": "s-bad", "sospetto": "s-bad" };
  const verdictOf = l => l.verdict || (l.disc > .35 ? "sospetto" : l.disc >= .12 ? "occasione" : l.disc >= -.05 ? "prezzo giusto" : "caro");
  const verdict = l => [VCLS[verdictOf(l)], verdictOf(l)];
  const isDeal = l => verdictOf(l) === "occasione";
  const VORD = { "occasione": 0, "da verificare": 1, "prezzo giusto": 2, "sospetto": 3, "caro": 4 };
  const fair = l => l.fair_lo ? (l.fair_lo + l.fair_hi) / 2 : mid(byId[l.m]);
  const best = id => LIST.filter(l => l.m === id && isDeal(l)).sort((a, b) => b.disc - a.disc)[0];
  const giorni = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"];
  function endInfo(l) {
    if (!l.endMs) return null;
    const ms = l.endMs - Date.now();
    if (ms <= 0) return { text: "asta chiusa", urgent: true };
    const min = Math.floor(ms / 6e4), h = Math.floor(min / 60), d = Math.floor(h / 24);
    const text = d >= 1 ? `chiude tra ${d} g ${h % 24} h` : h >= 1 ? `chiude tra ${h} h ${min % 60} min` : `chiude tra ${min} min`;
    let when = "";
    if (l.endDate) { const t = new Date(l.endMs); when = `${giorni[t.getDay()]} ${t.getDate()}/${t.getMonth() + 1}, ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`; }
    return { text, when, urgent: ms < 864e5 };
  }
  const countdown = l => { const e = endInfo(l); return e ? `<span class="countdown${e.urgent ? " urgent" : ""}">⏱ ${e.text}${e.when ? ` · ${e.when}` : ""}</span>` : ""; };
  const isNew = l => l.first && Date.now() - Date.parse(l.first) < 864e5;
  const pageUrl = id => P.base + "orologi/" + id + "/";

  /* ---------- foto ---------- */
  function photosFor(id) {
    const commons = (PHOTOS[id] || []).map(p => ({
      src: p.src, link: P.base + "crediti/#" + id, internal: true, credit: `Foto: ${p.author} · ${p.license} · Wikimedia Commons${p.exact === false ? " · stessa famiglia, non la ref. esatta" : ""}`
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
    if (!ph.length) { el.innerHTML = `<div class="main">${placeholder(m)}</div>`; return; }
    el.innerHTML = `<div class="main"><img alt="${esc(m.brand + " " + m.name + " " + m.ref)}"><a class="info" href="#">i</a></div>
      ${ph.length > 1 ? `<div class="thumbs">${ph.map((p, i) => `<button type="button" data-i="${i}" aria-label="Foto ${i + 1}"><img src="${esc(p.src)}" alt="" loading="lazy"></button>`).join("")}</div>` : ""}`;
    const img = el.querySelector(".main img"), info = el.querySelector(".main .info");
    const show = i => {
      img.src = ph[i].src;
      // niente testo sotto la foto: la «i» porta ai crediti (foto Commons) o all'annuncio (foto degli annunci)
      info.href = ph[i].link || "#";
      info.title = ph[i].credit;
      info.setAttribute("aria-label", ph[i].credit);
      if (ph[i].internal) { info.removeAttribute("target"); info.removeAttribute("rel"); }
      else { info.target = "_blank"; info.rel = "noopener"; }
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
    const m = byId[l.m], [cls, word] = verdict(l);
    const title = `${esc(m.brand)} ${esc(m.name)} <span class="mono muted" style="font-weight:400">${esc(m.ref)}</span>`;
    const asta = l.type === "Asta";
    return `<article class="deal${asta ? " is-asta" : ""}" style="${hl && !asta ? "border-color:var(--gilt)" : ""}">
      <div class="score ${cls}"><div>${pct(l.disc)}<small>${word}</small></div></div>
      <div style="min-width:0"><h4>${l.url ? `<a class="title" href="${esc(l.url)}" target="_blank" rel="noopener">${title}</a>` : title}</h4>
        <div class="meta">${isNew(l) ? `<span class="tag new">nuovo</span>` : ""}<span class="tag ${l.type === "Asta" ? "asta" : ""}">${esc(l.type)}</span><span>${esc(l.src)}</span>${l.cty ? `<span>${esc(l.cty)}</span>` : ""}${l.cond ? `<span>${esc(l.cond)}</span>` : ""}</div>
        ${asta ? countdown(l) : ""}
        ${(l.reasons || []).length ? `<ul class="why">${l.reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}</div>
      <div class="price"><b>${eur(l.total)}</b><small>${l.fee ? `${eur(l.p)} + ${Math.round(l.fee * 100)}% comm.` : "prezzo richiesto"}</small><small>${l.fair_lo ? `valore ${eur(l.fair_lo)}–${Math.round(l.fair_hi).toLocaleString("it-IT")}` : `stima ${eur(mid(m))}`}</small></div>
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
          const inner = `<span>${esc(l.src)} · ${esc(l.type)}</span><span class="mono">${eur(l.total)} <span class="${isDeal(l) ? "up" : ["caro", "sospetto"].includes(verdictOf(l)) ? "down" : "muted"}">${verdictOf(l)}</span></span>`;
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
  document.getElementById("stDeals").textContent = LIST.filter(isDeal).length;
  document.getElementById("stNew").textContent = LIST.filter(isNew).length;
  (function () {
    const u = P.listings.updated && Date.parse(P.listings.updated.replace(" UTC", "Z").replace(" ", "T"));
    if (!u) return;
    const d = new Date(u), today = new Date(), yest = new Date(Date.now() - 864e5);
    const day = d.toDateString() === today.toDateString() ? "oggi" : d.toDateString() === yest.toDateString() ? "ieri" : d.toLocaleDateString("it-IT");
    document.getElementById("stUpd").textContent =
      `Scanner aggiornato ${day} alle ${d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })} · ${new Set(LIST.map(l => l.src)).size} siti in ${new Set(LIST.map(l => (l.cty || "").slice(0, 2)).filter(Boolean)).size} paesi`;
  })();

  /* ---------- orologio vintage in apertura: segna l'ora, il contatore a ore 6 è l'indice di mercato ---------- */
  (function drawWatch() {
    const avg = MODELS.reduce((a, m) => a + m.t, 0) / MODELS.length, T = temp(avg);
    const C = 150, CY = 180, P = (r, deg) => [C + r * Math.sin(deg * Math.PI / 180), CY - r * Math.cos(deg * Math.PI / 180)];
    const f = n => n.toFixed(1);
    let h = `<defs>
      <linearGradient id="wSteel" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" style="stop-color:var(--case-a)"/><stop offset=".5" style="stop-color:var(--case-b)"/><stop offset="1" style="stop-color:var(--case-a)"/></linearGradient>
      <radialGradient id="wDial" cx=".45" cy=".4" r=".7">
        <stop offset="0" style="stop-color:var(--dial)"/><stop offset=".75" style="stop-color:var(--dial)"/><stop offset="1" style="stop-color:var(--dial-edge)"/></radialGradient>
      <radialGradient id="wGlass" cx=".35" cy=".25" r=".6">
        <stop offset="0" style="stop-color:#fff;stop-opacity:.22"/><stop offset="1" style="stop-color:#fff;stop-opacity:0"/></radialGradient>
    </defs>`;
    // anse, corona, cassa, lunetta
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sy]) => {
      const x = C + sx * 62 - 13, y = sy < 0 ? CY - 150 : CY + 98;
      h += `<rect x="${x}" y="${y}" width="26" height="52" rx="6" fill="url(#wSteel)" stroke="var(--case-line)" stroke-width="1"/>`;
    });
    h += `<rect x="262" y="${CY - 14}" width="16" height="28" rx="3" fill="url(#wSteel)" stroke="var(--case-line)"/>`;
    for (let i = 0; i < 6; i++) h += `<line x1="${264 + i * 2.4}" y1="${CY - 12}" x2="${264 + i * 2.4}" y2="${CY + 12}" stroke="var(--case-line)" stroke-width=".8"/>`;
    h += `<circle cx="${C}" cy="${CY}" r="120" fill="url(#wSteel)" stroke="var(--case-line)" stroke-width="1.2"/>
      <circle cx="${C}" cy="${CY}" r="110" fill="var(--case-b)" stroke="var(--case-line)"/>
      <circle cx="${C}" cy="${CY}" r="104" fill="url(#wDial)"/>`;
    // binario dei minuti
    h += `<circle cx="${C}" cy="${CY}" r="99" fill="none" stroke="var(--dial-ink)" stroke-width=".6"/><circle cx="${C}" cy="${CY}" r="93" fill="none" stroke="var(--dial-ink)" stroke-width=".6"/>`;
    for (let i = 0; i < 60; i++) {
      const [x1, y1] = P(93, i * 6), [x2, y2] = P(99, i * 6);
      h += `<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke="var(--dial-ink)" stroke-width="${i % 5 ? .6 : 1.4}"/>`;
    }
    // indici al trizio (a ore 6 c'è il contatore)
    for (let i = 0; i < 12; i++) {
      if (i === 6) continue;
      const deg = i * 30, wide = i % 3 === 0;
      const w = wide ? 7 : 5, len = wide ? 20 : 15;
      const draw = dx => {
        const [x, y] = P(84 - len / 2, deg);
        h += `<rect x="${f(x - w / 2 + dx)}" y="${f(y - len / 2)}" width="${w}" height="${len}" rx="1" fill="var(--lume)" stroke="var(--dial-ink)" stroke-width=".8" transform="rotate(${deg} ${f(x)} ${f(y)})"/>`;
      };
      if (i === 0) { draw(-5); draw(5); } else draw(0);
    }
    // scritte
    h += `<text x="${C}" y="${CY - 44}" text-anchor="middle" font-family="Italiana,Didot,Georgia,serif" font-size="21" letter-spacing="2" fill="var(--dial-ink)">PATINA</text>
      <text x="${C}" y="${CY - 32}" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="6" letter-spacing="2.4" fill="var(--dial-ink)">AUTOMATIC · CHRONOMETER</text>`;
    // contatore a ore 6: indice di mercato 0–100
    const SX = C, SY = CY + 46, SR = 25;
    h += `<circle cx="${SX}" cy="${SY}" r="${SR}" fill="var(--dial-edge)" stroke="var(--dial-ink)" stroke-width=".8"/>`;
    for (let i = 0; i <= 10; i++) {
      const deg = -135 + i * 27, a = deg * Math.PI / 180, r1 = i % 5 ? SR - 4 : SR - 7;
      h += `<line x1="${f(SX + r1 * Math.sin(a))}" y1="${f(SY - r1 * Math.cos(a))}" x2="${f(SX + (SR - 1) * Math.sin(a))}" y2="${f(SY - (SR - 1) * Math.cos(a))}" stroke="var(--dial-ink)" stroke-width="${i % 5 ? .6 : 1.1}"/>`;
    }
    [["0", -135], ["50", 0], ["100", 135]].forEach(([t, d]) => {
      const a = d * Math.PI / 180;
      h += `<text x="${f(SX + (SR - 12) * Math.sin(a))}" y="${f(SY - (SR - 12) * Math.cos(a) + 2.2)}" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="5.5" fill="var(--dial-ink)">${t}</text>`;
    });
    h += `<text x="${SX}" y="${SY + 13}" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="4.6" letter-spacing="1.2" fill="var(--dial-ink)">MERCATO</text>
      <g transform="rotate(${f(-135 + T * 2.7)} ${SX} ${SY})"><line x1="${SX}" y1="${SY + 4}" x2="${SX}" y2="${SY - SR + 5}" stroke="var(--gilt)" stroke-width="1.6" stroke-linecap="round"/></g>
      <circle cx="${SX}" cy="${SY}" r="2" fill="var(--dial-ink)"/>`;
    // lancette (a spada, con trizio) e secondi
    const sword = (len, w) => `M${C} ${CY + 12} L${C - w / 2} ${CY} L${C - w / 2} ${CY - len + w} L${C} ${CY - len} L${C + w / 2} ${CY - len + w} L${C + w / 2} ${CY} Z`;
    h += `<g id="wHour"><path d="${sword(56, 8)}" fill="var(--hand)"/><path d="M${C - 2} ${CY - 14} L${C - 2} ${CY - 46} L${C} ${CY - 50} L${C + 2} ${CY - 46} L${C + 2} ${CY - 14} Z" fill="var(--lume)"/></g>
      <g id="wMin"><path d="${sword(86, 6)}" fill="var(--hand)"/><path d="M${C - 1.4} ${CY - 16} L${C - 1.4} ${CY - 78} L${C} ${CY - 81} L${C + 1.4} ${CY - 78} L${C + 1.4} ${CY - 16} Z" fill="var(--lume)"/></g>
      <g id="wSec"><line x1="${C}" y1="${CY + 22}" x2="${C}" y2="${CY - 94}" stroke="var(--gilt)" stroke-width="1.1"/><circle cx="${C}" cy="${CY - 70}" r="2.6" fill="none" stroke="var(--gilt)" stroke-width="1"/></g>
      <circle cx="${C}" cy="${CY}" r="4.5" fill="var(--hand)"/><circle cx="${C}" cy="${CY}" r="1.6" fill="var(--gilt)"/>
      <circle cx="${C}" cy="${CY}" r="104" fill="url(#wGlass)" pointer-events="none"/>`;
    const svg = document.getElementById("dial");
    svg.setAttribute("viewBox", "0 0 300 360");
    svg.setAttribute("aria-label", `Orologio Patina: indice di mercato ${Math.round(T)} su 100`);
    svg.innerHTML = h;
    const hH = svg.querySelector("#wHour"), hM = svg.querySelector("#wMin"), hS = svg.querySelector("#wSec");
    const tick = () => {
      const d = new Date(), sec = d.getSeconds(), min = d.getMinutes() + sec / 60, hr = (d.getHours() % 12) + min / 60;
      hH.setAttribute("transform", `rotate(${f(hr * 30)} ${C} ${CY})`);
      hM.setAttribute("transform", `rotate(${f(min * 6)} ${C} ${CY})`);
      hS.setAttribute("transform", `rotate(${sec * 6} ${C} ${CY})`);
    };
    tick();
    setInterval(tick, 1000);
    const lbl = T < 40 ? "freddo" : T < 60 ? "neutro" : T < 75 ? "tiepido" : "caldo";
    const ups = MODELS.filter(m => m.t > 0).length;
    const hot = [...MODELS].sort((a, b) => b.t - a.t).slice(0, 2).map(m => m.brand).join(" e ");
    const cold = MODELS.filter(m => m.t < 0).map(m => `${m.brand} ${m.name}`);
    document.getElementById("dialCaption").textContent =
      `Il contatore a ore 6 segna l'indice di mercato: ${Math.round(T)} su 100, ${lbl}. Variazione media stimata a 12 mesi ${avg >= 0 ? "+" : ""}${avg.toFixed(1)}%; ${ups} modelli su ${MODELS.length} in crescita, più vivaci ${hot}${cold.length ? `, in calo ${cold.join(", ")}` : ""}.`;
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
        <td class="num">${b ? `<span class="up">${pct(b.disc)}</span> <span class="muted">${esc(b.src)}</span>` : "–"}</td></tr>`;
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

  function renderAuctions() {
    const el = document.getElementById("auctions");
    const au = (type === "Tutte" || type === "Asta") ? LIST.filter(l => l.type === "Asta" && l.endMs && l.endMs > Date.now()).sort((a, b) => a.endMs - b.endMs).slice(0, 4) : [];
    el.innerHTML = au.length ? `<div class="auc-head">Aste in chiusura</div>` + au.map(l => {
      const m = byId[l.m], tag = l.url ? "a" : "div";
      return `<${tag} class="auc"${l.url ? ` href="${esc(l.url)}" target="_blank" rel="noopener"` : ""}>
        ${countdown(l)}
        <h4>${esc(m.brand)} ${esc(m.name)} <span class="mono muted" style="font-weight:400">${esc(m.ref)}</span></h4>
        <div class="row"><span>${esc(l.src)}${l.cty ? " · " + esc(l.cty) : ""}</span></div>
        <div class="row"><span>offerta + comm.</span><b>${eur(l.total)}</b></div>
        <div class="row"><span>${verdictOf(l)}</span><span>${pct(l.disc)}</span></div>
      </${tag}>`;
    }).join("") : "";
  }

  function renderDeals() {
    renderAuctions();
    chips("typeBar", ["Tutte", "Marketplace", "Mercatino"], type, v => { type = v; renderDeals(); });
    const sort = document.getElementById("sortSel").value;
    const ls = LIST.filter(l => (type === "Tutte" || l.type === type) && !(l.endMs && l.endMs <= Date.now()))
      .sort((a, b) => sort === "price" ? a.total - b.total : sort === "end" ? (a.endMs ?? Infinity) - (b.endMs ?? Infinity)
        : (VORD[verdictOf(a)] - VORD[verdictOf(b)]) || (b.disc - a.disc))
      .slice(0, 60);
    document.getElementById("deals").innerHTML = ls.map(l => dealHTML(l, l.m === sel)).join("") || (LIST.length ? `<p class="muted">Nessun annuncio per questo filtro.</p>` : `<p class="empty-note">Lo scanner sta raccogliendo gli annunci attivi. Le occasioni compaiono qui al prossimo aggiornamento.</p>`);
  }
  document.getElementById("sortSel").addEventListener("change", renderDeals);

  renderModels(); renderDetail(); renderDeals();
  setInterval(renderDeals, 60000); // aggiorna i conti alla rovescia ogni minuto
  // apertura diretta: index.html#rolex-5513
  const h = location.hash.slice(1);
  if (byId[h]) pick(h, true);
})();
