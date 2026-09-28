/*
 * MF Desk — componenti e interazioni.
 * Non contiene dati: legge tutto da window.DEMO_DATA (data.js).
 * Stato dell'utente (posizioni, watchlist, tesi modificate, aziende aggiunte) in localStorage.
 *
 * Struttura: barra laterale sinistra (portafoglio), area centrale (notizie o scheda azienda),
 * barra laterale destra (watchlist). Le barre restano visibili quando si apre una scheda.
 */
(function () {
  'use strict';

  const D = window.DEMO_DATA;
  const KEY = 'mf-desk:v1';

  /* ================================================================ utilità */
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const nf = (v, d = 2) => Number(v).toLocaleString('it-IT', { minimumFractionDigits: d, maximumFractionDigits: d });
  const eur = (v, d = 2) => nf(v, d) + ' €';
  const priceDigits = v => (v < 1 ? 4 : v < 10 ? 3 : 2);
  const signed = (v, d = 2, suffix = '%') => (v > 0 ? '+' : v < 0 ? '−' : '') + nf(Math.abs(v), d) + suffix;
  const dirOf = v => (v > 0 ? 'up' : v < 0 ? 'down' : 'flat');
  const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : s);
  const MESI = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
  const MESI_LUNGHI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'];
  const fmtDate = d => `${d.getUTCDate()} ${MESI[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  const parseIt = s => { const m = /^(\d{1,2}) (\w{3}) (\d{4})$/.exec(s || ''); if (!m) return null; const mi = MESI.indexOf(m[2]); return mi < 0 ? null : new Date(Date.UTC(+m[3], mi, +m[1])); };
  const hhmm = d => `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
  const asOfDate = parseIt(D.aggiornamento);

  const ICON = {
    plus: '<path d="M12 5v14M5 12h14"/>',
    back: '<path d="M15 18l-6-6 6-6"/>',
    chev: '<path d="M9 6l6 6-6 6"/>',
    up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    down: '<path d="M12 5v14M19 12l-7 7-7-7"/>',
    flat: '<path d="M5 12h14"/>',
    check: '<path d="M5 12l5 5 9-10"/>',
    eq: '<path d="M6 9h12M6 15h12"/>',
    alert: '<path d="M12 8v5M12 16.5v.5"/><circle cx="12" cy="12" r="9"/>',
    q: '<path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17v.5"/><circle cx="12" cy="12" r="9"/>',
    link: '<path d="M9 15l6-6M10 6l1-1a4 4 0 0 1 6 6l-1 1M14 18l-1 1a4 4 0 0 1-6-6l1-1"/>',
    doc: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    panel: '<rect x="3" y="4.5" width="18" height="15" rx="3"/><path d="M15 4.5v15"/>'
  };
  const icon = n => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICON[n]}</svg>`;

  /* ================================================================ stato */
  const seed = () => ({ portafoglio: D.portafoglio.map(p => ({ ...p })), watchlist: D.watchlist.map(w => ({ ...w })), tesi: {}, aziende: {} });
  function load() {
    try {
      const s = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (s && Array.isArray(s.portafoglio) && Array.isArray(s.watchlist)) return { tesi: {}, aziende: {}, ...s };
    } catch (e) { /* storage non disponibile */ }
    return seed();
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignora */ } }
  let state = load();

  const PREF = 'mf-desk:ui';
  const pref = (() => { try { return JSON.parse(localStorage.getItem(PREF) || '{}'); } catch (e) { return {}; } })();
  const savePref = () => { try { localStorage.setItem(PREF, JSON.stringify({ watchOpen: ui.watchOpen, leftW: ui.leftW })); } catch (e) { /* ignora */ } };
  const ui = { range: '3M', scope: 'rilevanti', ticker: null, q: '', quarter: {}, editing: false, removing: false, current: null, watchOpen: pref.watchOpen !== false, leftW: pref.leftW || 320, allNews: {}, lastMain: '#riepilogo' };

  const azienda = t => state.aziende[t] || D.aziende[t] || null;
  const tesiDi = t => ({ ...azienda(t).tesi, ...(state.tesi[t] || {}) });
  const held = t => state.portafoglio.some(p => p.ticker === t);
  const watched = t => state.watchlist.some(w => w.ticker === t);
  const tracked = t => held(t) || watched(t);
  const ownership = t => (held(t) ? 'p' : watched(t) ? 'w' : '');
  const varDi = t => (D.mercato[t] ?? 0);
  const serieDi = t => { const a = azienda(t); return D.serie(t, a.prezzo, varDi(t)); };
  const linked = n => n.strumenti.filter(s => s.sim >= D.soglia);

  /* Pesi calcolati sul controvalore, arrotondati al decimo con il metodo del resto maggiore: sommano sempre a 100,0. */
  function posizioni() {
    const rows = state.portafoglio.map(p => { const a = azienda(p.ticker); return a && { ...p, a, valore: p.quantita * a.prezzo }; }).filter(Boolean);
    const tot = rows.reduce((s, r) => s + r.valore, 0);
    if (!tot) return { rows: [], tot: 0 };
    const raw = rows.map(r => r.valore / tot * 1000), fl = raw.map(Math.floor);
    let rest = 1000 - fl.reduce((a, b) => a + b, 0);
    raw.map((v, i) => [v - fl[i], i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (rest > 0) { fl[i]++; rest--; } });
    rows.forEach((r, i) => { r.peso = fl[i] / 10; });
    rows.sort((a, b) => b.valore - a.valore);
    return { rows, tot };
  }

  /* ================================================================ vocabolario */
  const STATO = {
    rafforzata: { label: 'Rafforzata', dash: 'Rafforzata', cls: 'pos', ic: 'check' },
    invariata: { label: 'Invariata', dash: 'Invariata', cls: 'neu', ic: 'eq' },
    indebolita: { label: 'Indebolita', dash: 'Da rivedere', cls: 'warn', ic: 'alert' },
    insufficiente: { label: 'Dati insufficienti', dash: 'Dati insufficienti', cls: 'na', ic: 'q' }
  };
  const EFFETTO = {
    rafforza: { label: 'Rafforza la tesi', cls: 'pos', ic: 'check' },
    invariata: { label: 'Nessun effetto rilevante', cls: 'neu', ic: 'eq' },
    indebolisce: { label: 'Indebolisce la tesi', cls: 'warn', ic: 'alert' }
  };
  const AZIONI = {
    portafoglio: { mantenere: 'Mantenere', aggiungere: 'Aggiungere', ridurre: 'Ridurre', vendere: 'Vendere' },
    watchlist: { valutare_ingresso: 'Valutare ingresso', attendere: 'Attendere', evitare: 'Evitare per ora' }
  };
  const AZIONE_BREVE = { valutare_ingresso: { label: 'Valuta ingresso', cls: 'act' }, attendere: { label: 'Attendi', cls: 'neu' }, evitare: { label: 'Evita per ora', cls: 'warn' } };
  const ORIZZONTI = ['Meno di 1 anno', '1–3 anni', '3–5 anni', 'Oltre 5 anni'];
  const DIR_LABEL = { up: 'Rialzista', down: 'Ribassista', flat: 'Neutro' };

  const statoDi = a => (a.esito && a.esito.stato) || 'insufficiente';
  const chipStato = (stato, lg) => { const s = STATO[stato]; return `<span class="chip ${s.cls}${lg ? ' lg' : ''}">${icon(s.ic)}${s.label}</span>`; };
  const contesto = t => (held(t) ? 'portafoglio' : 'watchlist');
  const decisioneDi = t => { const d = azienda(t).decisione; return d && d.contesto === contesto(t) ? d : null; };
  const trend = d => icon(d === 'up' ? 'up' : d === 'down' ? 'down' : 'flat');
  const pill = v => `<span class="pill ${dirOf(v)}">${signed(v)}</span>`;

  /* ================================================================ grafici */
  const charts = new Map();

  function niceTicks(lo, hi, count) {
    const raw = (hi - lo) / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || raw;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(8));
    return { ticks: out, step };
  }
  const axisFmt = (v, step) => {
    if (Math.abs(v) >= 1e6) return nf(v / 1e6, 2) + 'M';
    if (Math.abs(v) >= 1e4) return nf(v / 1e3, step < 1000 ? 1 : 0) + 'k';
    return nf(v, step < 0.1 ? 3 : step < 1 ? 2 : step < 10 ? 1 : 0);
  };

  /* Linea come nell'app Borsa: area tenue, riferimento tratteggiato al valore iniziale, asse a destra, mirino con tooltip. */
  function areaChart(host, values, dates, opts = {}) {
    const draw = () => {
      const W = Math.max(200, host.clientWidth), H = typeof opts.h === 'function' ? opts.h(W) : (opts.h || 140), padR = opts.padR ?? 44, padB = 20, padT = opts.markers ? 18 : 6;
      const n = values.length, iw = W - padR, ih = H - padT - padB;
      let lo = Math.min(...values), hi = Math.max(...values);
      const span = hi - lo || hi * 0.02 || 1; lo -= span * 0.08; hi += span * 0.08;
      const { ticks, step } = niceTicks(lo, hi, 3);
      const x = i => (n < 2 ? 0 : (i / (n - 1)) * iw), y = v => padT + (1 - (v - lo) / (hi - lo)) * ih;
      const col = values[n - 1] >= values[0] ? 'var(--up)' : 'var(--down)';
      const gid = 'g' + Math.random().toString(36).slice(2, 8);
      let line = '';
      for (let i = 0; i < n; i++) line += (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(values[i]).toFixed(1);
      const area = `${line}L${iw} ${padT + ih}L0 ${padT + ih}Z`;
      const grid = ticks.map(t => `<line class="grid" x1="0" x2="${iw}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}"/><text class="axis" x="${iw + 6}" y="${(y(t) + 3.5).toFixed(1)}">${axisFmt(t, step)}</text>`).join('');
      const xs = opts.xLabels || [0.12, 0.5, 0.88];
      const xl = xs.map(f => { const i = Math.round(f * (n - 1)); return `<text class="axis" x="${x(i).toFixed(1)}" y="${H - 4}" text-anchor="middle">${fmtDate(dates[i]).replace(/ \d{4}$/, opts.year ? ' ’' + String(dates[i].getUTCFullYear()).slice(2) : '')}</text>`; }).join('');
      const mk = (opts.markers || []).map(m => `<line class="mk" x1="${x(m.i).toFixed(1)}" x2="${x(m.i).toFixed(1)}" y1="${padT - 4}" y2="${padT + ih}"/><text class="mk-label" x="${x(m.i).toFixed(1)}" y="${padT - 7}" text-anchor="middle">${esc(m.label)}</text>`).join('');
      host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="${esc(opts.label || 'Andamento')}">
        <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity=".16"/><stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>
        ${grid}${mk}
        <line class="base" x1="0" x2="${iw}" y1="${y(values[0]).toFixed(1)}" y2="${y(values[0]).toFixed(1)}"/>
        <path d="${area}" fill="url(#${gid})"/>
        <path d="${line}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <line class="cross" x1="0" x2="0" y1="${padT}" y2="${padT + ih}" visibility="hidden"/>
        <circle class="hdot" r="4" fill="${col}" stroke="var(--card)" stroke-width="2" visibility="hidden"/>
        <circle r="4" cx="${x(n - 1).toFixed(1)}" cy="${y(values[n - 1]).toFixed(1)}" fill="${col}" stroke="${opts.ring || 'var(--side)'}" stroke-width="2"/>
        ${xl}
        <rect class="hit" x="0" y="0" width="${iw}" height="${H}" fill="transparent"/>
      </svg><div class="tip" hidden></div>`;
      const svg = host.querySelector('svg'), cross = svg.querySelector('.cross'), dot = svg.querySelector('.hdot'), tip = host.querySelector('.tip');
      const fmt = opts.fmt || (v => eur(v));
      const move = ev => {
        const r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) * (W / r.width);
        const i = Math.max(0, Math.min(n - 1, Math.round((px / iw) * (n - 1))));
        const cx = x(i), cy = y(values[i]), ch = (values[i] / values[0] - 1) * 100;
        cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.setAttribute('visibility', 'visible');
        dot.setAttribute('cx', cx); dot.setAttribute('cy', cy); dot.setAttribute('visibility', 'visible');
        tip.innerHTML = `<div class="d">${fmtDate(dates[i])}</div><div class="num" style="font-weight:600">${fmt(values[i])}</div><div class="num ${dirOf(ch)}">${signed(ch)} <span class="muted">dall’inizio</span></div>`;
        tip.hidden = false;
        const sx = cx * (r.width / W), tw = tip.offsetWidth;
        tip.style.left = Math.max(0, Math.min(r.width - tw, sx + 12 + tw > r.width ? sx - tw - 12 : sx + 12)) + 'px';
        tip.style.top = Math.max(-8, cy * (r.height / H) - 64) + 'px';
      };
      const leave = () => { cross.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); tip.hidden = true; };
      const hit = svg.querySelector('.hit');
      hit.addEventListener('pointermove', move);
      hit.addEventListener('pointerdown', move);
      hit.addEventListener('pointerleave', leave);
    };
    charts.set(host, draw);
    draw();
  }
  let rsz;
  window.addEventListener('resize', () => { clearTimeout(rsz); rsz = setTimeout(() => charts.forEach((draw, host) => { if (host.isConnected) draw(); else charts.delete(host); }), 120); });

  /* Minigrafico con riferimento tratteggiato al primo valore, come le righe di "My Symbols". */
  function sparkline(vals, w = 56, h = 30) {
    const lo = Math.min(...vals), hi = Math.max(...vals), n = vals.length;
    const Y = v => (2 + (1 - (v - lo) / ((hi - lo) || 1)) * (h - 4)).toFixed(1);
    const pts = vals.map((v, i) => `${(i / (n - 1) * (w - 2) + 1).toFixed(1)},${Y(v)}`).join(' ');
    const col = vals[n - 1] >= vals[0] ? 'var(--up)' : 'var(--down)';
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      <line x1="0" x2="${w}" y1="${Y(vals[0])}" y2="${Y(vals[0])}" stroke="${col}" stroke-width="1" stroke-dasharray="1.5 2.5" opacity=".7" vector-effect="non-scaling-stroke"/>
      <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
  }

  /* ================================================================ allocazione: torta */
  const SERIES = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)'];
  /* Ordine validato come anello (anche l'ultimo accanto al primo) in entrambi i temi. */
  const COMPANY_COLS = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s6)', 'var(--s5)'];
  /* Il colore segue il titolo (ordine di inserimento), non il suo peso: cambiare i pesi non ridipinge nulla. Oltre sei: "Altri". */
  function companies(rows) {
    const byT = Object.fromEntries(rows.map(r => [r.ticker, r]));
    const ordered = state.portafoglio.map(p => byT[p.ticker]).filter(Boolean);
    const out = ordered.slice(0, 6).map((r, i) => ({ n: r.ticker, full: r.a.nome, p: r.peso, v: r.valore, col: COMPANY_COLS[i], open: r.ticker }));
    const rest = ordered.slice(6);
    if (rest.length) out.push({ n: 'Altri', full: `${rest.length} posizioni`, p: rest.reduce((s, r) => s + r.peso, 0), v: rest.reduce((s, r) => s + r.valore, 0), col: 'var(--s-other)' });
    return out;
  }
  function sectors(rows) {
    const by = {};
    rows.forEach(r => { const s = D.settori[r.ticker] || 'Altro'; (by[s] = by[s] || { p: 0, v: 0 }); by[s].p += r.peso; by[s].v += r.valore; });
    let secs = Object.entries(by).map(([n, o]) => ({ n, p: o.p, v: o.v })).sort((a, b) => b.v - a.v);
    if (secs.length > 5) {
      const rest = secs.slice(4);
      secs = secs.slice(0, 4).concat([{ n: 'Altro', p: rest.reduce((s, x) => s + x.p, 0), v: rest.reduce((s, x) => s + x.v, 0) }]);
    }
    let i = 0;
    return secs.map(x => ({ ...x, col: x.n === 'Altro' ? 'var(--s-other)' : SERIES[i++] }));
  }
  /* Home: torte grandi e interattive. HOME tiene i dati dell'ultima resa e il settore fissato con un clic. */
  const HOME = { titoli: [], settori: [], rows: [], tot: 0, pin: null };

  function pieInteractive(kind) {
    const items = HOME[kind], size = 240, r = size / 2, tot = items.reduce((s, x) => s + x.p, 0) || 1;
    let a0 = -Math.PI / 2;
    const pt = a => `${(r + r * Math.cos(a)).toFixed(2)} ${(r + r * Math.sin(a)).toFixed(2)}`;
    const paths = items.map((x, i) => {
      const f = x.p / tot, a1 = a0 + f * 2 * Math.PI, mid = (a0 + a1) / 2;
      const d = f > 0.9999 ? `M${r} 0A${r} ${r} 0 1 1 ${r - 0.01} 0Z` : `M${r} ${r}L${pt(a0)}A${r} ${r} 0 ${f > 0.5 ? 1 : 0} 1 ${pt(a1)}Z`;
      a0 = a1;
      const act = kind === 'titoli' ? (x.open ? `apri la scheda di ${x.full}` : '') : 'mostra i titoli del settore';
      return `<path class="slice" d="${d}" fill="${x.col}" data-k="${kind}" data-i="${i}" style="--dx:${(Math.cos(mid) * 8).toFixed(1)}px;--dy:${(Math.sin(mid) * 8).toFixed(1)}px"${act ? ` tabindex="0" role="button" aria-label="${esc(x.full || x.n)}: ${nf(x.p, 1)}%, ${eur(x.v, 0)}. ${cap(act)}"` : ''}></path>`;
    }).join('');
    const legend = items.map((x, i) => `<li><button class="leg" type="button" data-k="${kind}" data-i="${i}"${kind === 'titoli' && !x.open ? ' disabled' : ''}>
        <i style="background:${x.col}"></i><span>${esc(x.n)}${kind === 'titoli' && x.open ? ` <small>${esc(x.full)}</small>` : ''}</span><b>${nf(x.p, 1)}%</b><em>${eur(x.v, 0)}</em></button></li>`).join('');
    const pinned = kind === 'settori' ? HOME.pin : null;
    return `<div class="ipie${pinned != null ? ' hl' : ''}" data-kind="${kind}" data-state="${pinned ?? ''}|${pinned != null}">
      <svg class="pie big" viewBox="-10 -10 ${size + 20} ${size + 20}" role="group" aria-label="Allocazione ${kind === 'titoli' ? 'per titolo' : 'per settore'}">${paths.replace(new RegExp(`data-i="${pinned}"`), `data-i="${pinned}" data-on`)}</svg>
      <div class="readout" aria-live="polite">${readout(kind, pinned, pinned != null)}</div>
      <ul class="ilegend">${legend}</ul>
    </div>`;
  }

  /* Riquadro di lettura: cosa c'è sotto il puntatore, o il settore fissato (con i suoi titoli). */
  function readout(kind, i, list) {
    const items = HOME[kind], x = i == null ? null : items[i];
    if (!x) {
      return kind === 'titoli'
        ? `<div class="r-name">Portafoglio</div><div class="r-big">${eur(HOME.tot, 0)}</div><div class="r-sub">${HOME.rows.length} titoli · passa su uno spicchio per i dettagli</div>`
        : `<div class="r-name">Settori</div><div class="r-big">${items.length}</div><div class="r-sub">Clicca un settore per vedere i suoi titoli</div>`;
    }
    if (kind === 'titoli') {
      const row = HOME.rows.find(r => r.ticker === x.open);
      const extra = row ? ` · oggi <span class="${dirOf(varDi(row.ticker))}">${signed(varDi(row.ticker))}</span> · tesi ${STATO[statoDi(row.a)].dash.toLowerCase()}` : '';
      return `<div class="r-name">${esc(x.n)} <span class="muted">${esc(x.full)}</span></div><div class="r-big">${nf(x.p, 1)}%</div><div class="r-sub">${eur(x.v, 0)}${extra}</div>`;
    }
    return `<div class="r-name">${esc(x.n)}</div><div class="r-big">${nf(x.p, 1)}%</div><div class="r-sub">${eur(x.v, 0)} · ${x.members.length} ${x.members.length === 1 ? 'titolo' : 'titoli'}${list ? '' : ' · clicca per vederli'}</div>
      ${list ? `<ul class="r-list">${x.members.map(m => `<li><button type="button" data-open="${esc(m.ticker)}"><b>${esc(m.ticker)}</b><span>${esc(m.a.nome)}</span><em>${nf(m.peso, 1)}%</em>${icon('chev')}</button></li>`).join('')}</ul>` : ''}`;
  }

  /* Evidenzia l'elemento i (o il settore fissato se i è null). Ridisegna il riquadro solo se lo stato cambia. */
  function setActive(wrap, i) {
    const kind = wrap.dataset.kind, pin = kind === 'settori' ? HOME.pin : null;
    const show = i ?? pin, list = show != null && show === pin;
    const key = `${show ?? ''}|${list}`;
    if (wrap.dataset.state === key) return;
    wrap.dataset.state = key;
    wrap.classList.toggle('hl', show != null);
    $$('[data-i]', wrap).forEach(e => e.toggleAttribute('data-on', show != null && +e.dataset.i === show));
    $('.readout', wrap).innerHTML = readout(kind, show, list);
  }

  const dayChange = (rows, tot) => { const prev = rows.reduce((s, r) => s + r.quantita * r.a.prezzo / (1 + varDi(r.ticker) / 100), 0); return { day: tot - prev, pct: (tot / prev - 1) * 100 }; };

  /* ================================================================ barra sinistra: portafoglio */
  const RANGES = { '1M': 21, '3M': 63, '1A': 252, 'MAX': D.giorni.length };

  function renderLeft() {
    const { rows, tot } = posizioni();
    const search = `<label class="search">${icon('search')}<span class="sr">Cerca titoli o notizie</span>
      <input id="q" type="search" placeholder="Cerca" autocomplete="off" value="${esc(ui.q)}"><kbd>⌘K</kbd></label>`;
    let body;
    if (!rows.length) {
      body = `<div class="side-head"><h2>Portafoglio</h2></div>
        <div class="empty"><h3>Nessuna posizione</h3><p>Aggiungi un titolo che possiedi e il motivo per cui l’hai comprato: lo confronteremo con risultati e notizie.</p>
          <button class="btn" type="button" data-act="add-pos">${icon('plus')}Aggiungi posizione</button></div>`;
    } else {
      const { day, pct: dayPct } = dayChange(rows, tot);

      const counts = { pos: 0, neu: 0, warn: 0, na: 0 };
      rows.forEach(r => counts[STATO[statoDi(r.a)].cls]++);
      const sum = [counts.pos && `${counts.pos} rafforzate`, counts.neu && `${counts.neu} invariate`, counts.warn && `${counts.warn} da rivedere`, counts.na && `${counts.na} senza dati`].filter(Boolean).join(' · ');

      body = `<div class="side-head"><h2>Portafoglio</h2><button class="icon-btn" type="button" data-act="add-pos" aria-label="Aggiungi posizione" title="Aggiungi posizione">${icon('plus')}</button></div>
        <div class="summary">
          <div class="label">Valore totale · al ${esc(D.aggiornamento)}</div>
          <div class="total num">${eur(tot)}</div>
          <div class="delta num ${dirOf(day)}"><span>${day >= 0 ? '+' : '−'}${eur(Math.abs(day))}</span><span>(${signed(dayPct)})</span><span class="muted">ultima seduta</span></div>
        </div>
        <div>
          <div class="chart" id="pchart"></div>
          <div class="range-row" style="margin-top:8px">
            <div class="seg" role="group" aria-label="Periodo del grafico">${Object.keys(RANGES).map(k => `<button type="button" data-range="${k}" aria-pressed="${ui.range === k}">${k}</button>`).join('')}</div>
          </div>
          <div class="range-delta num" id="rdelta" style="padding:6px 6px 0"></div>
        </div>
        <div>
          <div class="side-head"><h3>Posizioni</h3></div><p class="label" style="padding:0 6px;margin:2px 0 6px">Tesi: ${sum}</p>
          <ul class="syms">${rows.map(r => {
            const st = STATO[statoDi(r.a)];
            return `<li><button class="sym" type="button" data-open="${esc(r.ticker)}"${ui.current === r.ticker ? ' aria-current="page"' : ''}>
              <span class="sym-l"><span class="sym-t">${esc(r.ticker)}</span><span class="sym-n">${esc(r.a.nome)}</span>
                <span class="sym-s"><i class="sdot ${st.cls}"></i>${st.dash} · ${nf(r.peso, 1)}%</span></span>
              ${sparkline(serieDi(r.ticker).slice(-22))}
              <span class="sym-r"><span class="sym-p">${nf(r.a.prezzo, priceDigits(r.a.prezzo))}</span>${pill(varDi(r.ticker))}</span>
            </button></li>`;
          }).join('')}</ul>
        </div>`;
    }
    $('#side-left').innerHTML = `<div class="side-inner">${search}${body}</div>`;
    bindSearch();
    drawPortfolioChart();
  }

  function drawPortfolioChart() {
    const { rows } = posizioni();
    if (!rows.length) return;
    const n = RANGES[ui.range], N = D.giorni.length, vals = new Array(n).fill(0);
    rows.forEach(r => { const s = serieDi(r.ticker); for (let i = 0; i < n; i++) vals[i] += r.quantita * s[N - n + i]; });
    const dates = D.giorni.slice(N - n), ch = vals[n - 1] - vals[0], pct = (vals[n - 1] / vals[0] - 1) * 100;
    const delta = `<span class="${dirOf(ch)}">${ch >= 0 ? '+' : '−'}${eur(Math.abs(ch), 0)} (${signed(pct, 1)})</span> <span class="muted">nel periodo</span>`;
    if ($('#pchart')) { areaChart($('#pchart'), vals, dates, { h: w => Math.round(Math.max(132, Math.min(300, w * 0.42))), padR: 40, xLabels: [0.15, 0.85], year: ui.range === 'MAX', label: 'Valore del portafoglio' }); $('#rdelta').innerHTML = delta; }
    $$('[data-range]').forEach(b => b.setAttribute('aria-pressed', b.dataset.range === ui.range));
  }

  /* ================================================================ barra destra: watchlist */
  function renderRight() {
    const items = state.watchlist.map(w => azienda(w.ticker)).filter(Boolean);
    const list = items.length ? `<ul class="syms">${items.map(a => {
      const dec = decisioneDi(a.ticker);
      const act = dec ? `<i class="sdot ${AZIONE_BREVE[dec.azione].cls}"></i>${AZIONE_BREVE[dec.azione].label}` : '<i class="sdot na"></i>Dati insufficienti';
      return `<li><button class="sym" type="button" data-open="${esc(a.ticker)}"${ui.current === a.ticker ? ' aria-current="page"' : ''} title="${esc(tesiDi(a.ticker).motivo)}">
        <span class="sym-l"><span class="sym-t">${esc(a.ticker)}</span><span class="sym-n">${esc(a.nome)}</span><span class="sym-s">${act}</span></span>
        ${sparkline(serieDi(a.ticker).slice(-22))}
        <span class="sym-r"><span class="sym-p">${nf(a.prezzo, priceDigits(a.prezzo))}</span>${pill(varDi(a.ticker))}</span>
      </button></li>`;
    }).join('')}</ul>` : `<div class="empty"><h3>Watchlist vuota</h3><p>Aggiungi un’azienda che stai valutando e il motivo del tuo interesse.</p>
      <button class="btn" type="button" data-act="add-watch">${icon('plus')}Aggiungi alla watchlist</button></div>`;
    $('#side-right').innerHTML = `<div class="side-inner">
      <div class="side-head"><h2>Watchlist</h2><button class="icon-btn" type="button" data-act="add-watch" aria-label="Aggiungi alla watchlist" title="Aggiungi alla watchlist">${icon('plus')}</button></div>
      ${items.length ? '<p class="label" style="padding:0 6px;margin-top:-10px">Azione da valutare · ultimo mese</p>' : ''}
      ${list}
    </div>`;
  }

  /* ================================================================ area centrale: notizie */
  function toolbar(mode) {
    const nav = mode === 'detail'
      ? `<button class="back" type="button" data-act="back">${icon('back')}${ui.lastMain === '#notizie' ? 'Notizie' : 'Riepilogo'}</button>`
      : `<nav class="seg" aria-label="Sezioni"><a href="#riepilogo"${mode === 'home' ? ' aria-current="page"' : ''}>Riepilogo</a><a href="#notizie"${mode === 'news' ? ' aria-current="page"' : ''}>Notizie</a></nav>`;
    $('#toolbar').innerHTML = `${nav}
      <span class="spacer"></span>
      <span class="status">Borsa Italiana · chiusa ·</span>
      <span class="demo">${D.reale ? esc(D.reale.etichetta) : 'Dati simulati'}</span>
      <button class="icon-btn plain" type="button" data-act="toggle-watch" aria-controls="side-right" aria-pressed="${ui.watchOpen}" aria-label="${ui.watchOpen ? 'Nascondi la watchlist' : 'Mostra la watchlist'}" title="${ui.watchOpen ? 'Nascondi la watchlist' : 'Mostra la watchlist'}">${icon('panel')}</button>`;
  }
  function applyWatch() {
    $('#shell').classList.toggle('watch-closed', !ui.watchOpen);
    const side = $('#side-right'); side.inert = !ui.watchOpen;
    const b = $('[data-act="toggle-watch"]');
    if (b) { const l = ui.watchOpen ? 'Nascondi la watchlist' : 'Mostra la watchlist'; b.setAttribute('aria-pressed', ui.watchOpen); b.setAttribute('aria-label', l); b.title = l; }
    setTimeout(() => charts.forEach((draw, host) => { if (host.isConnected) draw(); }), 320);
  }

  function newsMatches(n) {
    const q = ui.q.trim().toLowerCase();
    if (!q) return true;
    return n.titolo.toLowerCase().includes(q) || n.riassunto.toLowerCase().includes(q) ||
      n.strumenti.some(s => s.ticker.toLowerCase() === q || (azienda(s.ticker) && azienda(s.ticker).nome.toLowerCase().includes(q)));
  }
  const inScope = t => (ui.scope === 'portafoglio' ? held(t) : ui.scope === 'watchlist' ? watched(t) : tracked(t));

  /* Segnale netto di un titolo: media di (direzione × forza × similarità) sugli articoli collegati. Scala −1…+1. */
  function signalFor(t) {
    let sum = 0, k = 0;
    D.notizie.forEach(n => {
      if (!n.segnale) return;
      const x = n.strumenti.find(y => y.ticker === t && y.sim >= D.soglia);
      if (!x) return;
      sum += (x.dir === 'up' ? 1 : x.dir === 'down' ? -1 : 0) * n.segnale.forza * x.sim; k++;
    });
    return k ? { v: sum / k, n: k } : null;
  }

  /* Versione semplice per la home: fonte, titolo, riassunto dell'articolo, ora. L'analisi sta nella scheda del titolo. */
  function newsCardSimple(n) {
    const d = new Date(n.data + 'Z');
    return `<article class="ncard">
      <div class="src">MF Milano Finanza · ${esc(n.sezione)}</div>
      <h3>${n.url ? `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.titolo)}</a>` : esc(n.titolo)}</h3>
      ${!n.verdetto && n.riassunto ? `<p class="sum">${esc(n.riassunto)}</p>` : ''}
      <div class="when">${d.getUTCDate()} ${MESI[d.getUTCMonth()]} · ${hhmm(d)}</div>
    </article>`;
  }

  function newsCard(n, t) {
    const d = new Date(n.data + 'Z'), s = t && n.strumenti.find(x => x.ticker === t), g = n.segnale;
    const dir = s ? s.dir : g && g.dir;
    const others = linked(n).filter(x => x.ticker !== t).map(x => x.ticker);
    let sig;
    const vd = n.verdetto;
    if (vd) {
      const fig = vd.move_pct != null && vd.z != null
        ? `${vd.status === 'NO_REACTION' ? 'seduta più ampia' : 'picco'} <b class="${dirOf(vd.move_pct)}">${signed(vd.move_pct, 1)}</b> · ${nf(Math.abs(vd.z), 1)}× il normale${vd.d ? ` · ${fmtDate(new Date(vd.d + 'T00:00:00Z'))}` : ''}` : '';
      sig = `<div class="sig" title="Verdetto sul prezzo: una seduta è anomala se si muove almeno 2 volte l’oscillazione normale delle 20 sedute precedenti.">
        <span class="chip ${vd.cls}">${esc(vd.label)}</span><span class="hist">${fig}</span></div>`;
    } else if (g) {
      sig = `<div class="sig" title="Direzione e forza stimate dal testo. Storico: variazione media del titolo nelle ${g.storico.sedute} sedute dopo ${g.storico.n} articoli simili.">
        <span class="dir ${dir}">${trend(dir)}${DIR_LABEL[dir]}</span><span class="meter ${dir}" role="img" aria-label="Forza ${nf(g.forza, 2)}"><i style="width:${Math.round(g.forza * 100)}%"></i></span>
        <span class="hist">· simili <b class="${dirOf(g.storico.pct)}">${signed(g.storico.pct, 1)}</b> in ${g.storico.sedute} sedute (n=${g.storico.n})</span></div>`;
    } else {
      sig = `<div class="sig"><span class="hist">Nessuno strumento sopra la soglia (migliore ${nf(n.migliore, 2)} &lt; ${nf(D.soglia, 2)}): nessun segnale</span></div>`;
    }
    let tl = '';
    if (n.indicatore && (!t || n.indicatore.ticker === t) && tracked(n.indicatore.ticker)) tl = `<div class="tl">${icon('link')}<span>Tocca la tua tesi: “${esc(n.indicatore.nome)}”</span></div>`;
    else if (n.notaTesi && t) tl = `<div class="tl off">${icon('link')}<span>${esc(n.notaTesi)}</span></div>`;
    return `<article class="ncard">
      <div class="src">MF Milano Finanza · ${esc(n.sezione)}${s && !vd ? ` · similarità ${nf(s.sim, 2)}` : ''}</div>
      <h3>${n.url ? `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.titolo)}</a>` : esc(n.titolo)}</h3>
      <p class="sum">${esc(n.riassunto)}</p>
      ${sig}${tl}
      <div class="when">${d.getUTCDate()} ${MESI[d.getUTCMonth()]} · ${hhmm(d)}${others.length ? ` <span class="muted" style="font-weight:400">· anche ${others.map(esc).join(', ')}</span>` : ''}</div>
    </article>`;
  }

  function renderNews() {
    toolbar('news');
    const counts = {
      rilevanti: D.notizie.filter(n => linked(n).some(s => tracked(s.ticker))).length,
      portafoglio: D.notizie.filter(n => linked(n).some(s => held(s.ticker))).length,
      watchlist: D.notizie.filter(n => linked(n).some(s => watched(s.ticker))).length,
      tutte: D.notizie.length
    };
    const scopes = [['rilevanti', 'Per te'], ['portafoglio', 'Portafoglio'], ['watchlist', 'Watchlist'], ['tutte', 'Tutte']];

    // sezioni per titolo, ordinate per notizia più recente
    const groups = {};
    D.notizie.filter(newsMatches).forEach(n => linked(n).forEach(s => {
      if (!inScope(s.ticker) || (ui.ticker && s.ticker !== ui.ticker)) return;
      (groups[s.ticker] = groups[s.ticker] || []).push(n);
    }));
    const order = Object.keys(groups).map(t => ({ t, items: groups[t].sort((a, b) => b.data.localeCompare(a.data)) }))
      .sort((a, b) => b.items[0].data.localeCompare(a.items[0].data));
    const loose = ui.scope === 'tutte' && !ui.ticker ? D.notizie.filter(n => newsMatches(n) && !linked(n).some(s => tracked(s.ticker))) : [];

    const sections = order.map(({ t, items }) => {
      const a = azienda(t), v = varDi(t), own = held(t) ? 'In portafoglio' : 'In watchlist';
      return `<section class="ssec" aria-labelledby="sec-${esc(t)}">
        <div class="ssec-h"><button class="ssec-title" type="button" data-open="${esc(t)}" id="sec-${esc(t)}"><span class="t">${esc(t)}</span><span class="n">${esc(a.nome)}</span></button><span class="tag">${own}</span></div>
        <div class="quote"><span class="p">${nf(a.prezzo, priceDigits(a.prezzo))}</span><span class="c ${dirOf(v)}">${signed(v)}</span></div>
        <div class="cards">${items.slice(0, 3).map(newsCardSimple).join('')}</div>
        <div class="more"><button type="button" data-open="${esc(t)}">${items.length > 3 ? `${items.length - 3} ${items.length - 3 === 1 ? 'ALTRA' : 'ALTRE'} · ` : ''}IMPATTO E TESI <b>${esc(t)}</b>${icon('chev')}</button></div>
      </section>`;
    }).join('') + (loose.length ? `<section class="ssec"><div class="ssec-h"><span class="ssec-title"><span class="t">Mercati</span><span class="n">senza titoli collegati</span></span></div>
        <div class="cards">${loose.map(newsCardSimple).join('')}</div></section>` : '');

    const d = asOfDate;
    $('#app').innerHTML = `<div class="view">
      <h1 class="page-title" tabindex="-1" id="ptitle">Notizie <span class="date">${d.getUTCDate()} ${MESI_LUNGHI[d.getUTCMonth()]}</span></h1>
      <p class="page-sub">Da MF Milano Finanza, sui titoli che segui. Apri un titolo per vedere l’impatto sul prezzo e sulla tua tesi.</p>
      ${D.indici.length ? `<div class="tape" aria-label="Indici (demo)">${D.indici.map(x => `<span>${esc(x.nome)}<b>${esc(x.valore)}</b><span class="${dirOf(x.var)}">${signed(x.var)}</span></span>`).join('')}</div>` : ''}
      <div class="controls">
        <div class="seg" role="group" aria-label="Quali notizie">${scopes.map(([k, l]) => `<button type="button" data-scope="${k}" aria-pressed="${ui.scope === k}">${l}<span class="c">${counts[k]}</span></button>`).join('')}</div>
        ${ui.ticker ? `<span class="filter">Solo <b>${esc(ui.ticker)}</b><button type="button" data-act="clear-filter" aria-label="Rimuovi filtro">${icon('x')}</button></span>` : ''}
        ${ui.q ? `<span class="filter">“${esc(ui.q)}”<button type="button" data-act="clear-q" aria-label="Cancella ricerca">${icon('x')}</button></span>` : ''}
      </div>
      ${sections || `<div class="feed-empty"><p>${ui.q ? `Nessuna notizia per “${esc(ui.q)}”.` : 'Nessuna notizia collegata ai titoli selezionati.'}</p>
        <button class="btn secondary" type="button" data-act="all-news">Mostra tutte le notizie</button></div>`}
    </div>`;
  }

  /* ================================================================ area centrale: riepilogo (home) */
  /* Semicerchio a cinque zone, vuoto: occupa lo stesso spazio del vero indicatore. */
  function fgGhostGauge() {
    const cx = 160, cy = 160, R = 150, r0 = 96, gap = 0.012;
    const p = (rad, a) => `${(cx + rad * Math.cos(a)).toFixed(1)} ${(cy + rad * Math.sin(a)).toFixed(1)}`;
    const seg = i => { const a0 = Math.PI + i * Math.PI / 5 + gap, a1 = Math.PI + (i + 1) * Math.PI / 5 - gap;
      return `<path d="M${p(R, a0)}A${R} ${R} 0 0 1 ${p(R, a1)}L${p(r0, a1)}A${r0} ${r0} 0 0 0 ${p(r0, a0)}Z"/>`; };
    return `<svg class="fg-gauge" viewBox="0 0 320 172">${[0, 1, 2, 3, 4].map(seg).join('')}
      <text x="${cx - r0 + 8}" y="${cy + 8}" text-anchor="start">0</text><text x="${cx}" y="${cy - r0 + 22}" text-anchor="middle">50</text><text x="${cx + r0 - 8}" y="${cy + 8}" text-anchor="end">100</text>
      <text class="fg-val" x="${cx}" y="${cy + 6}" text-anchor="middle">—</text></svg>`;
  }

  function renderHome() {
    toolbar('home');
    const { rows, tot } = posizioni(), d = asOfDate;
    const head = `<h1 class="page-title" tabindex="-1" id="ptitle">Riepilogo <span class="date">${d.getUTCDate()} ${MESI_LUNGHI[d.getUTCMonth()]}</span></h1>`;
    /* Spazio riservato all'indice Fear & Greed. Chi lo realizza definisce window.renderFearGreed(el):
       viene chiamata dopo ogni resa della home e può sostituire il contenuto di #fear-greed. Vedi README. */
    const fg = `<section class="card fg-slot" id="fear-greed" aria-labelledby="h-fg">
        <div class="card-h"><h2 id="h-fg">Fear &amp; Greed · Italia</h2><span class="muted">In arrivo</span></div>
        <div class="fg-body" aria-hidden="true">${fgGhostGauge()}
          <dl class="fg-hist">${['Chiusura precedente', '1 settimana fa', '1 mese fa', '1 anno fa'].map(l => `<div><dt>${l}</dt><dd>—</dd></div>`).join('')}</dl>
        </div>
        <p class="note">Spazio riservato all’indice di sentiment del mercato italiano.</p>
      </section>`;
    let body;
    if (!rows.length) {
      body = `<section class="card empty" style="margin-top:16px"><h3>Nessuna posizione</h3><p>Aggiungi un titolo che possiedi per vedere come è distribuito il portafoglio.</p>
        <button class="btn" type="button" data-act="add-pos">${icon('plus')}Aggiungi posizione</button></section>`;
    } else {
      const secs = sectors(rows), names = new Set(secs.map(x => x.n));
      HOME.rows = rows; HOME.tot = tot;
      HOME.titoli = companies(rows);
      HOME.settori = secs.map(x => ({ ...x, members: rows.filter(r => { const s0 = D.settori[r.ticker] || 'Altro'; return (names.has(s0) ? s0 : 'Altro') === x.n; }) }));
      if (HOME.pin != null && !HOME.settori[HOME.pin]) HOME.pin = null;
      body = `<div class="home-grid">
        <section class="card"><div class="card-h"><h2>Per titolo</h2><span class="muted">Clic: scheda del titolo</span></div>${pieInteractive('titoli')}</section>
        <section class="card"><div class="card-h"><h2>Per settore</h2><span class="muted">Clic: i titoli del settore</span></div>${pieInteractive('settori')}</section>
      </div>`;
    }
    $('#app').innerHTML = `<div class="view">${head}${fg}${body}</div>`;
    if (typeof window.renderFearGreed === 'function') {
      try { window.renderFearGreed($('#fear-greed'), { data: D, posizioni }); } catch (e) { console.error('renderFearGreed', e); }
    }
  }

  /* ================================================================ area centrale: scheda azienda */
  function renderDetail(t) {
    const a = azienda(t);
    toolbar('detail');
    const isHeld = held(t), isWatched = watched(t);
    const pos = posizioni().rows.find(r => r.ticker === t);
    const T = tesiDi(t), stato = statoDi(a);
    const q = (a.earnings || []).filter(e => !e.mancante), last = q[q.length - 1], v = varDi(t);

    /* 1. Intestazione */
    const reaz = last && last.reazione
      ? `<div class="react block"><span class="label">Reazione all’ultimo earnings · ${esc(last.label)}</span>
          <span class="big ${dirOf(last.reazione.pct)}">${signed(last.reazione.pct, 1)}</span>
          <span class="interval">${esc(cap(last.reazione.da))} ${icon('arrow')} ${esc(last.reazione.a)}</span>
          <span class="small muted">Chiusura precedente → chiusura successiva alla pubblicazione. ${esc(last.reazione.nota || '')}</span></div>`
      : `<div class="react block"><span class="label">Reazione all’ultimo earnings</span><span class="big muted">n.d.</span><span class="small muted">Nessuna reazione disponibile nella demo.</span></div>`;
    const head = `<div class="dh">
        <div class="dh-title"><h1 tabindex="-1" id="ptitle">${esc(a.ticker)}</h1><span class="n">${esc(a.nome)}</span></div>
        <div class="dh-quote"><span class="p">${eur(a.prezzo, priceDigits(a.prezzo))}</span><span class="${dirOf(v)}" style="font-weight:500">${signed(v)}</span><span class="muted">Chiusura del ${esc(D.aggiornamento)}</span></div>
        <div class="dh-meta tag">${[isHeld ? `In portafoglio · peso ${nf(pos ? pos.peso : 0, 1)}%` : isWatched ? 'In watchlist' : '', a.settore && a.settore !== '—' ? esc(a.settore) : ''].filter(Boolean).join(' · ')}</div>
      </div>
      <section class="card"><div class="split">
        <div><div class="label" style="margin-bottom:6px">Ultimo anno · le linee verticali indicano la pubblicazione dei risultati</div><div class="chart" id="dchart"></div></div>
        <div class="stack">${reaz}<div class="remove-row" id="remove-row">${removeRow(t)}</div></div>
      </div></section>`;

    /* 2. La tua tesi */
    const tesi = `<section class="card" id="tesi-card">${ui.editing ? tesiForm(t) : tesiView(t, pos)}</section>`;

    /* 3. Cosa cambia */
    const e = a.esito;
    const mod = state.tesi[t] && state.tesi[t].modificata
      ? `<div class="warnbox">${icon('alert')}<span>Hai modificato la tesi il ${esc(state.tesi[t].modificata)}. Questa valutazione demo si riferisce alla versione precedente e non viene ricalcolata.</span></div>` : '';
    const cambia = `<section class="card">
      <div class="card-h"><h2>Cosa cambia dopo gli ultimi risultati</h2>${last ? `<span class="muted">${esc(last.label)} · pubblicati il ${esc(last.data)}</span>` : ''}</div>
      <div class="stack">
        <div>${chipStato(stato, true)}</div>
        ${mod}
        <p style="font-size:16px;max-width:68ch">${esc(e ? e.sintesi : 'Non ci sono risultati trimestrali collegati a questa azienda nella demo: non è possibile confrontare la tesi con i dati.')}</p>
        ${e && (e.fatti.length || e.interpretazioni.length) ? `<div class="split">
          ${e.fatti.length ? `<div class="block"><h3 class="mini">Fatti documentati nei risultati</h3><ul class="facts">${e.fatti.map(f => `<li>${esc(f)}</li>`).join('')}</ul>
            <div class="srcnote">${icon('doc')}Fonte non disponibile nella demo</div></div>` : ''}
          ${e.interpretazioni.length ? `<div class="block"><h3 class="mini">Interpretazioni (non sono dati)</h3><ul class="interps">${e.interpretazioni.map(f => `<li>${esc(f)}</li>`).join('')}</ul></div>` : ''}
        </div>` : ''}
      </div>
    </section>`;

    /* 4. Decisione */
    const ctx = contesto(t), dec = decisioneDi(t);
    let decHTML;
    if (dec) {
      const considered = [
        `Tesi ${STATO[stato].label.toLowerCase()}`, `Orizzonte ${T.orizzonte}`,
        isHeld ? `Peso ${nf(pos.peso, 1)}%` : (T.pesoPrevisto ? `Peso previsto ${nf(T.pesoPrevisto, 1)}%` : 'Peso previsto non indicato'),
        a.valutazione, last && last.reazione ? `Reazione ai risultati ${signed(last.reazione.pct, 1)}` : null
      ].filter(Boolean);
      decHTML = `<div class="split">
          <div class="stack">
            <div class="dec-scale" aria-label="Possibili indicazioni">${Object.entries(AZIONI[ctx]).map(([k, l]) => `<span class="${k === dec.azione ? 'on' : ''}"${k === dec.azione ? ' aria-current="true"' : ''}>${l}</span>`).join('')}</div>
            <div><div class="label">Indicazione principale</div><div class="dec-main">${AZIONI[ctx][dec.azione]}</div></div>
            <p style="font-size:16px">${esc(dec.motivazione)}</p>
            <p class="disclaimer">Un’indicazione da valutare, non un ordine operativo né una previsione: nessuna probabilità di successo è stimata.</p>
          </div>
          <div class="block"><h3 class="mini">Elementi considerati</h3><p class="considered">${considered.map(esc).join(' · ')}</p></div>
        </div>
        <div class="dec-grid" style="margin-top:18px">
          <div class="block"><h3 class="mini">Elementi a favore</h3><ul class="bullets">${dec.aFavore.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
          <div class="block"><h3 class="mini">Rischio principale</h3><p>${esc(dec.rischio)}</p></div>
          <div class="block"><h3 class="mini">Cosa cambierebbe la valutazione</h3><p>${esc(dec.cambierebbe)}</p></div>
        </div>`;
    } else {
      const miss = a.mancano || (a.decisione ? [`Un’indicazione pensata per il nuovo contesto (${isHeld ? 'posizione detenuta' : 'watchlist'})`] : ['Risultati trimestrali collegati all’azienda', 'Una valutazione di riferimento', 'Indicatori da monitorare']);
      decHTML = `<div class="stack">
        <div class="dec-scale" aria-label="Possibili indicazioni">${Object.values(AZIONI[ctx]).map(l => `<span>${l}</span>`).join('')}</div>
        <div class="dec-main muted" style="font-size:22px">Dati insufficienti per valutare l’azione</div>
        <div class="block"><h3 class="mini">Cosa manca</h3><ul class="bullets">${miss.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div></div>`;
    }
    const decisione = `<section class="card"><div class="card-h"><h2>Decisione da valutare</h2><span class="muted">${ctx === 'portafoglio' ? 'Posizione detenuta' : 'Azienda in watchlist'}</span></div>${decHTML}</section>`;

    /* 5. Earnings */
    const earn = `<section class="card" id="earn">${earningsHTML(t)}</section>`;

    /* Notizie che possono muovere il titolo: qui sta l'analisi (verdetto sul prezzo, segnale, indicatore della tesi) */
    const rel = D.notizie.filter(n => n.strumenti.some(s => s.ticker === t && s.sim >= D.soglia)).sort((x, y) => y.data.localeCompare(x.data));
    const sg = signalFor(t);
    const news = `<section class="card" aria-labelledby="h-news">
      <div class="card-h"><h2 id="h-news">Notizie che possono muovere il titolo</h2><span class="muted">${rel.length} ${rel.length === 1 ? 'articolo' : 'articoli'} MF</span></div>
      ${sg ? `<div class="netsig">
        <div><div class="label">Segnale netto dalle notizie</div><div class="big ${dirOf(sg.v)}">${signed(sg.v, 2, '')}</div><div class="small muted">${sg.n} ${sg.n === 1 ? 'articolo' : 'articoli'}</div></div>
        <div><div class="track" role="img" aria-label="Segnale netto ${signed(sg.v, 2, '')} su una scala da −1 a +1"><i class="${sg.v >= 0 ? 'up' : 'down'}" style="width:calc(${Math.min(1, Math.abs(sg.v)) * 50}% - 1px)"></i></div>
          <div class="scale3"><span>−1 ribassista</span><span>0</span><span>+1 rialzista</span></div>
          <p class="small muted" style="margin-top:6px">${D.reale ? 'Media sugli articoli: direzione del picco × forza (|z| / 6).' : 'Media sugli articoli: direzione × forza × similarità.'}</p></div>
      </div>` : ''}
      ${rel.length ? `<div class="cards">${rel.slice(0, ui.allNews[t] ? rel.length : 4).map(n => newsCard(n, t)).join('')}</div>` : '<p class="note">Nessun articolo collegato a questo titolo sopra la soglia di similarità.</p>'}
      ${rel.length > 4 && !ui.allNews[t] ? `<div class="more"><button type="button" data-act="more-news">MOSTRA ALTRE ${rel.length - 4}${icon('chev')}</button></div>` : ''}
    </section>`;

    $('#app').innerHTML = `<div class="view detail">${head}${news}${tesi}${cambia}${decisione}${earn}</div>`;

    const N = D.giorni.length, n = 252, s = serieDi(t).slice(N - n), dates = D.giorni.slice(N - n);
    const markers = q.map(e => { const pd = parseIt(e.data); if (!pd) return null; const i = dates.findIndex(d => d >= pd); return i >= 0 ? { i, label: e.label.replace(' 20', '') } : null; }).filter(Boolean);
    areaChart($('#dchart'), s, dates, { h: 190, markers, ring: 'var(--card)', fmt: v => eur(v, priceDigits(v)), label: `Prezzo di ${a.nome} nell’ultimo anno` });
  }

  function removeRow(t) {
    const where = held(t) ? 'dal portafoglio' : watched(t) ? 'dalla watchlist' : null;
    if (!where) return '';
    if (!ui.removing) return `<button class="link danger" type="button" data-act="remove">Rimuovi ${where}</button>`;
    return `<span>Rimuovere ${esc(t)} ${where}?</span><button class="link danger" type="button" data-act="remove-yes">Rimuovi</button><button class="link" type="button" data-act="remove-no">Annulla</button>`;
  }

  function tesiView(t, pos) {
    const T = tesiDi(t), isHeld = held(t), inds = (T.indicatori || []).filter(Boolean);
    const peso = isHeld
      ? `<div><dt>Peso attuale nel portafoglio</dt><dd>${nf(pos ? pos.peso : 0, 1)}%</dd></div>`
      : `<div><dt>Peso previsto (facoltativo)</dt><dd>${T.pesoPrevisto ? nf(T.pesoPrevisto, 1) + '%' : '<span class="muted" style="font-weight:400">Non indicato</span>'}</dd></div>`;
    return `<div class="card-h"><h2>La tua tesi</h2><button class="btn secondary" type="button" data-act="edit" style="height:30px;padding:0 14px">Modifica tesi</button></div>
      <div class="split">
        <div class="stack">
          <div class="block"><h3 class="mini">Perché ${isHeld ? 'l’hai comprata' : 'ti interessa'}</h3><blockquote class="motivo">${esc(T.motivo)}</blockquote></div>
          <div class="block"><h3 class="mini">Indicatori da monitorare</h3>
            ${inds.length ? `<ol class="inds">${inds.map(x => `<li>${esc(x)}</li>`).join('')}</ol><p class="note">Proposti dal sistema a partire dal motivo; puoi modificarli.</p>` : '<p class="note">Nessun indicatore: aggiungine fino a tre con “Modifica tesi”.</p>'}</div>
        </div>
        <dl class="group">${peso}<div><dt>Orizzonte</dt><dd>${esc(T.orizzonte || 'Non indicato')}</dd></div></dl>
      </div>`;
  }

  function tesiForm(t) {
    const T = tesiDi(t), isHeld = held(t), ind = (T.indicatori || []).concat(['', '', '']).slice(0, 3);
    return `<form class="form" id="tesi-form" style="padding:0" novalidate>
      <div class="card-h" style="margin:0"><h2>Modifica tesi</h2></div>
      <div class="two">
        <div class="field"><label for="f-oriz">Orizzonte di investimento</label><select id="f-oriz" name="orizzonte">${ORIZZONTI.map(o => `<option${o === T.orizzonte ? ' selected' : ''}>${o}</option>`).join('')}</select></div>
        ${isHeld ? '' : `<div class="field"><label for="f-peso">Peso previsto <span class="opt">(facoltativo, %)</span></label><input id="f-peso" name="peso" type="number" min="0" max="100" step="0.5" inputmode="decimal" value="${T.pesoPrevisto ?? ''}"></div>`}
      </div>
      <div class="field"><label for="f-motivo">Motivo dell’investimento</label><textarea id="f-motivo" name="motivo" rows="3" required>${esc(T.motivo)}</textarea><span class="err" hidden></span></div>
      <div class="field"><label for="f-i1">Indicatori da monitorare <span class="opt">(massimo tre)</span></label>
        ${ind.map((x, i) => `<input id="f-i${i + 1}" name="ind" value="${esc(x)}" placeholder="Indicatore ${i + 1}"${i ? ` aria-label="Indicatore ${i + 1}"` : ''}>`).join('')}</div>
      <div class="form-actions"><button class="btn secondary" type="button" data-act="edit-cancel">Annulla</button><button class="btn" type="submit">Salva tesi</button></div>
    </form>`;
  }

  function earningsHTML(t) {
    const a = azienda(t), E = a.earnings || [];
    if (!E.length) return `<div class="card-h"><h2>Ultimi quattro earnings</h2></div><p class="note">Nessun risultato trimestrale disponibile nella demo per questa azienda.</p>`;
    const sel = ui.quarter[t] ?? E.length - 1;
    const effCls = e => (e.mancante ? 'na' : EFFETTO[e.impatto.effetto].cls);
    const evo = `<div class="evo">${E.map(e => `<div class="evo-step ${effCls(e)}"><span class="lbl">${esc(e.label)}</span>${e.mancante ? '<span class="chip na">Non disponibile</span>' : `<span class="chip ${EFFETTO[e.impatto.effetto].cls}">${icon(EFFETTO[e.impatto.effetto].ic)}${EFFETTO[e.impatto.effetto].label}</span>`}</div>`).join('')}</div>
      <p class="muted" style="max-width:75ch">${esc(a.evoluzione || '')}</p>`;
    const tabs = `<div class="qtabs"><div class="seg" role="tablist" aria-label="Trimestri">${E.map((e, i) => `<button class="qtab" role="tab" type="button" id="qt-${i}" aria-controls="qp" aria-selected="${i === sel}" aria-pressed="${i === sel}" tabindex="${i === sel ? 0 : -1}" data-q="${i}">
        <span class="l"><i class="sdot ${effCls(e)}" aria-hidden="true"></i>${esc(e.label)}</span><span class="d">${e.mancante ? 'non disponibile' : esc(e.data)}</span></button>`).join('')}</div></div>`;
    const e = E[sel];
    let panel;
    if (e.mancante) panel = `<p class="note">Dati di questo trimestre non disponibili nella demo.</p>`;
    else {
      const base = b => (b === 'a/a' ? 'anno su anno' : b === 't/t' ? 'trimestre su trimestre' : '');
      const metrics = e.metriche.map(m => m.valore == null
        ? `<div class="metric na"><span class="n">${esc(m.nome)}</span><span class="v">n.d.</span><span class="c">${esc(m.nota || 'Non disponibile')}</span></div>`
        : `<div class="metric"><span class="n">${esc(m.nome)}</span><span class="v">${esc(m.valore)}</span><span class="c"><b>${esc(m.confronto)}</b> ${base(m.base)}${m.nota ? ` · ${esc(m.nota)}` : ''}</span></div>`).join('');
      const imp = EFFETTO[e.impatto.effetto];
      panel = `<div class="qpanel">
        <div class="stack">
          <div class="block"><h3 class="mini">Tre fatti essenziali</h3><ul class="facts">${e.fatti.map(f => `<li>${esc(f)}</li>`).join('')}</ul></div>
          <div class="block"><h3 class="mini">Indicazioni del management</h3><p>${esc(e.guidance)}</p></div>
          <div class="block"><h3 class="mini">Cosa è cambiato dal trimestre precedente</h3><p>${esc(e.cambiato)}</p></div>
          <div class="block"><h3 class="mini">Impatto sulla tua tesi</h3><div><span class="chip ${imp.cls}">${icon(imp.ic)}${imp.label}</span></div><p>${esc(e.impatto.testo)}</p></div>
        </div>
        <div class="stack">
          <div class="block"><h3 class="mini">Numeri · ${esc(e.periodo)}</h3><div class="metrics">${metrics}</div></div>
          <div class="block"><h3 class="mini">Reazione del prezzo</h3>${e.reazione
            ? `<div class="reaction"><span class="num ${dirOf(e.reazione.pct)}">${signed(e.reazione.pct, 1)}</span><span class="interval">${esc(cap(e.reazione.da))} ${icon('arrow')} ${esc(e.reazione.a)}</span></div><p class="small muted">${esc(e.reazione.nota || '')}</p>`
            : '<p class="note">Non disponibile nella demo.</p>'}</div>
          <div class="srcnote">${icon('doc')}${e.fonti && e.fonti.length ? e.fonti.map(f => `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.titolo)}</a>`).join(' · ') : 'Fonte non disponibile nella demo'}</div>
        </div>
      </div>`;
    }
    return `<div class="card-h"><h2>Ultimi quattro earnings</h2><span class="muted">Dal più vecchio al più recente</span></div>
      <div class="block"><h3 class="mini">Evoluzione della tesi nei quattro trimestri</h3>${evo}</div>
      ${tabs}<div id="qp" role="tabpanel" aria-labelledby="qt-${sel}">${panel}</div>`;
  }

  /* ================================================================ moduli */
  const dlg = $('#dlg');
  function openDialog(kind) {
    const pos = kind === 'pos';
    dlg.innerHTML = `<form class="form" id="add-form" novalidate>
      <h2 id="dlg-title">${pos ? 'Aggiungi posizione' : 'Aggiungi alla watchlist'}</h2>
      <p class="intro">${pos ? 'Indica il titolo e il motivo per cui l’hai comprato.' : 'Indica l’azienda e il motivo del tuo interesse.'} Nella demo i prezzi si inseriscono a mano.</p>
      <div class="two">
        <div class="field"><label for="a-nome">Nome azienda</label><input id="a-nome" name="nome" required autocomplete="off"><span class="err" hidden></span></div>
        <div class="field"><label for="a-ticker">Ticker</label><input id="a-ticker" name="ticker" required autocomplete="off" maxlength="10" style="text-transform:uppercase"><span class="err" hidden></span></div>
      </div>
      <div class="two">
        ${pos ? '<div class="field"><label for="a-qta">Quantità</label><input id="a-qta" name="quantita" type="number" min="1" step="1" inputmode="numeric" required><span class="err" hidden></span></div>'
              : '<div class="field"><label for="a-peso">Peso previsto <span class="opt">(facoltativo, %)</span></label><input id="a-peso" name="peso" type="number" min="0" max="100" step="0.5" inputmode="decimal"><span class="err" hidden></span></div>'}
        <div class="field"><label for="a-prezzo">Prezzo attuale (€)</label><input id="a-prezzo" name="prezzo" type="number" min="0" step="0.0001" inputmode="decimal" required><span class="err" hidden></span></div>
      </div>
      <div class="field"><label for="a-motivo">${pos ? 'Motivo dell’investimento' : 'Motivo dell’interesse'}</label><textarea id="a-motivo" name="motivo" rows="3" required placeholder="Es. Forte generazione di free cash flow"></textarea><span class="err" hidden></span></div>
      <div class="field"><label for="a-oriz">Orizzonte di investimento</label><select id="a-oriz" name="orizzonte">${ORIZZONTI.map(o => `<option${o === '3–5 anni' ? ' selected' : ''}>${o}</option>`).join('')}</select></div>
      <div class="form-actions"><button class="btn secondary" type="button" data-act="dlg-close">Annulla</button><button class="btn" type="submit">${pos ? 'Aggiungi posizione' : 'Aggiungi alla watchlist'}</button></div>
    </form>`;
    dlg.dataset.kind = kind;
    const tk = $('#a-ticker', dlg);
    tk.addEventListener('change', () => {
      const a = azienda(tk.value.trim().toUpperCase());
      if (a) { $('#a-nome', dlg).value ||= a.nome; $('#a-prezzo', dlg).value ||= a.prezzo; $('#a-motivo', dlg).value ||= a.tesi.motivo; }
    });
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    $('#a-nome', dlg).focus();
  }
  function closeDialog() { if (dlg.close) dlg.close(); else dlg.removeAttribute('open'); }

  function fieldErr(input, msg) {
    const err = input.parentElement.querySelector('.err');
    input.setAttribute('aria-invalid', msg ? 'true' : 'false');
    if (err) { err.textContent = msg || ''; err.hidden = !msg; }
    return !msg;
  }

  function submitAdd(form) {
    const kind = dlg.dataset.kind, f = form.elements;
    const nome = f.nome.value.trim(), ticker = f.ticker.value.trim().toUpperCase().replace(/[^A-Z0-9.]/g, '');
    const prezzo = parseFloat(f.prezzo.value), motivo = f.motivo.value.trim();
    let ok = fieldErr(f.nome, nome ? '' : 'Inserisci il nome dell’azienda.');
    const dup = kind === 'pos' ? held(ticker) : tracked(ticker);
    ok = fieldErr(f.ticker, !ticker ? 'Inserisci il ticker (lettere e numeri).' : dup ? `${ticker} è già ${held(ticker) ? 'in portafoglio' : 'in watchlist'}.` : '') && ok;
    ok = fieldErr(f.prezzo, prezzo > 0 ? '' : 'Inserisci un prezzo maggiore di zero.') && ok;
    ok = fieldErr(f.motivo, motivo ? '' : 'Scrivi il motivo in una o due frasi.') && ok;
    let quantita = 0, peso = null;
    if (kind === 'pos') { quantita = parseInt(f.quantita.value, 10); ok = fieldErr(f.quantita, quantita > 0 ? '' : 'Inserisci una quantità di almeno 1.') && ok; }
    else if (f.peso.value) { peso = parseFloat(f.peso.value); ok = fieldErr(f.peso, peso >= 0 && peso <= 100 ? '' : 'Il peso deve essere tra 0 e 100.') && ok; }
    if (!ok) { const bad = form.querySelector('[aria-invalid="true"]'); if (bad) bad.focus(); return; }

    if (!D.aziende[ticker] && !state.aziende[ticker]) {
      state.aziende[ticker] = {
        nome, ticker, settore: '—', prezzo, valutazione: null,
        tesi: { orizzonte: f.orizzonte.value, motivo, motivoBreve: motivo.length > 60 ? motivo.slice(0, 57) + '…' : motivo, indicatori: [], pesoPrevisto: peso },
        esito: null, decisione: null, evoluzione: null, earnings: [], utente: true,
        mancano: ['Risultati trimestrali collegati all’azienda', 'Una valutazione di riferimento', 'Indicatori da monitorare (aggiungili con “Modifica tesi”)']
      };
    } else {
      state.tesi[ticker] = { ...(state.tesi[ticker] || {}), motivo, orizzonte: f.orizzonte.value, ...(peso != null ? { pesoPrevisto: peso } : {}) };
    }
    if (kind === 'pos') { state.portafoglio.push({ ticker, quantita }); state.watchlist = state.watchlist.filter(w => w.ticker !== ticker); }
    else state.watchlist.push({ ticker });
    save(); closeDialog(); renderAll();
    toast(kind === 'pos' ? `${ticker} aggiunto al portafoglio` : `${ticker} aggiunto alla watchlist`);
  }

  function submitTesi(form, t) {
    const f = form.elements, motivo = f.motivo.value.trim();
    if (!fieldErr(f.motivo, motivo ? '' : 'Scrivi il motivo in una o due frasi.')) { f.motivo.focus(); return; }
    const now = new Date();
    const upd = { orizzonte: f.orizzonte.value, motivo, indicatori: $$('input[name="ind"]', form).map(i => i.value.trim()).filter(Boolean).slice(0, 3), modificata: `${now.getDate()} ${MESI[now.getMonth()]} ${now.getFullYear()}` };
    if (f.peso) upd.pesoPrevisto = f.peso.value === '' ? null : Math.max(0, Math.min(100, parseFloat(f.peso.value)));
    state.tesi[t] = { ...(state.tesi[t] || {}), ...upd };
    save(); ui.editing = false; renderAll();
    toast('Tesi salvata');
  }

  let toastT;
  function toast(msg) {
    let el = $('.toast');
    if (!el) { el = document.createElement('div'); el.className = 'toast'; el.setAttribute('role', 'status'); el.hidden = true; document.body.appendChild(el); }
    el.textContent = msg;
    requestAnimationFrame(() => { el.hidden = false; });
    clearTimeout(toastT); toastT = setTimeout(() => { el.hidden = true; }, 2200);
  }

  /* ================================================================ router ed eventi */
  const currentTicker = () => { const h = location.hash; return h.startsWith('#azienda-') ? decodeURIComponent(h.slice(9)) : null; };

  function renderMain() {
    charts.forEach((_, host) => { if (host.id !== 'pchart') charts.delete(host); });
    const t = currentTicker(), ok = !!(t && azienda(t)), h = location.hash;
    if (ok) renderDetail(t);
    else if (h === '#notizie') { ui.lastMain = '#notizie'; renderNews(); }
    else { if (h && h !== '#riepilogo') history.replaceState(null, '', '#riepilogo'); ui.lastMain = '#riepilogo'; renderHome(); }
    $('#shell').classList.toggle('is-detail', ok);
    applyWatch();
  }
  function renderAll() {
    ui.current = currentTicker();
    charts.clear();
    renderLeft(); renderRight(); renderMain();
  }
  function route() {
    ui.editing = false; ui.removing = false;
    ui.current = currentTicker();
    // aggiorna solo la selezione nelle barre laterali, senza ridisegnarle
    $$('.sym').forEach(b => { if (b.dataset.open === ui.current) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
    renderMain();
    window.scrollTo(0, 0);
    const title = $('#ptitle'); if (title) title.focus({ preventScroll: true });
  }
  const openCompany = t => { const h = '#azienda-' + encodeURIComponent(t); if (location.hash === h) route(); else location.hash = h; };

  function bindSearch() {
    const q = $('#q');
    q.addEventListener('input', () => {
      ui.q = q.value;
      if (currentTicker()) location.hash = '#notizie'; else renderMain();
    });
    q.addEventListener('keydown', ev => {
      if (ev.key === 'Enter') { const v = q.value.trim().toUpperCase(); if (azienda(v)) { q.value = ''; ui.q = ''; openCompany(v); } }
      if (ev.key === 'Escape') { q.value = ''; ui.q = ''; renderMain(); }
    });
  }

  document.addEventListener('click', ev => {
    const slice = ev.target.closest('.ipie [data-i]');
    if (slice) {
      const kind = slice.dataset.k, i = +slice.dataset.i, x = HOME[kind][i];
      if (kind === 'titoli') { if (x && x.open) openCompany(x.open); return; }
      HOME.pin = HOME.pin === i ? null : i;
      const w = slice.closest('.ipie'); w.dataset.state = ''; setActive(w, null);
      return;
    }
    const el = ev.target.closest('[data-open],[data-act],[data-range],[data-scope],[data-filter],[data-q]');
    if (!el) return;
    if (el.dataset.open) { openCompany(el.dataset.open); return; }
    if (el.dataset.range) { ui.range = el.dataset.range; drawPortfolioChart(); return; }
    if (el.dataset.scope) { ui.scope = el.dataset.scope; ui.ticker = null; renderMain(); return; }
    if (el.dataset.filter) { ui.ticker = ui.ticker === el.dataset.filter ? null : el.dataset.filter; renderMain(); return; }
    const t = currentTicker();
    if (el.dataset.q) { ui.quarter[t] = +el.dataset.q; $('#earn').innerHTML = earningsHTML(t); $(`#qt-${el.dataset.q}`).focus(); return; }
    switch (el.dataset.act) {
      case 'add-pos': openDialog('pos'); break;
      case 'more-news': { ui.allNews[t] = true; const y = scrollY; renderDetail(t); scrollTo(0, y); break; }
      case 'toggle-watch': ui.watchOpen = !ui.watchOpen; savePref(); applyWatch(); setLeft(clampLeft(ui.leftW)); break;
      case 'add-watch': openDialog('watch'); break;
      case 'dlg-close': closeDialog(); break;
      case 'clear-filter': ui.ticker = null; renderMain(); break;
      case 'clear-q': ui.q = ''; $('#q').value = ''; renderMain(); break;
      case 'all-news': ui.scope = 'tutte'; ui.ticker = null; ui.q = ''; $('#q').value = ''; renderMain(); break;
      case 'back': location.hash = ui.lastMain; break;
      case 'edit': ui.editing = true; $('#tesi-card').innerHTML = tesiForm(t); $('#f-motivo').focus(); break;
      case 'edit-cancel': ui.editing = false; $('#tesi-card').innerHTML = tesiView(t, posizioni().rows.find(r => r.ticker === t)); break;
      case 'remove': ui.removing = true; $('#remove-row').innerHTML = removeRow(t); break;
      case 'remove-no': ui.removing = false; $('#remove-row').innerHTML = removeRow(t); break;
      case 'remove-yes': {
        const where = held(t) ? 'dal portafoglio' : 'dalla watchlist';
        state.portafoglio = state.portafoglio.filter(p => p.ticker !== t);
        state.watchlist = state.watchlist.filter(w => w.ticker !== t);
        save(); ui.removing = false; history.replaceState(null, '', ui.lastMain); renderAll(); toast(`${t} rimosso ${where}`);
        break;
      }
    }
  });

  document.addEventListener('submit', ev => {
    ev.preventDefault();
    if (ev.target.id === 'add-form') submitAdd(ev.target);
    if (ev.target.id === 'tesi-form') submitTesi(ev.target, currentTicker());
  });

  document.addEventListener('keydown', ev => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'k') { ev.preventDefault(); $('#q').focus(); return; }
    const tab = ev.target.closest && ev.target.closest('.qtab');
    if (!tab || !['ArrowLeft', 'ArrowRight'].includes(ev.key)) return;
    const tabs = $$('.qtab'), i = tabs.indexOf(tab);
    tabs[(i + (ev.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length].click();
  });

  /* Divisore tra portafoglio e notizie (regole apple-design): segue il puntatore 1:1 da dove lo si afferra,
     oltre i limiti oppone resistenza elastica e al rilascio torna al limite con la curva "drawer".
     Doppio clic: larghezza predefinita. Tastiera: frecce (Maiusc = passo lungo), Home, Fine. */
  const LEFT_DEF = 320, LEFT_MIN = 260;
  const shell = $('#shell'), splitter = $('#splitter');
  const leftMax = () => Math.max(LEFT_MIN, Math.min(720, window.innerWidth - (ui.watchOpen && window.innerWidth > 1240 ? 320 : 0) - 440));
  const clampLeft = w => Math.max(LEFT_MIN, Math.min(leftMax(), w));
  const rubber = (over, dim = 180, c = 0.55) => (over * dim * c) / (dim + c * Math.abs(over));
  let sideRaf;
  const redrawSide = () => { cancelAnimationFrame(sideRaf); sideRaf = requestAnimationFrame(() => { const h = $('#pchart'), d = h && charts.get(h); if (d) d(); }); };
  function setLeft(w) {
    document.documentElement.style.setProperty('--left-w', w.toFixed(1) + 'px');
    splitter.setAttribute('aria-valuenow', Math.round(w));
    splitter.setAttribute('aria-valuemax', Math.round(leftMax()));
  }
  function settleLeft(w) {
    ui.leftW = clampLeft(w); setLeft(ui.leftW); savePref();
    setTimeout(() => charts.forEach((draw, host) => { if (host.isConnected) draw(); }), 320);
  }
  splitter.addEventListener('pointerdown', ev => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    try { splitter.setPointerCapture(ev.pointerId); } catch (e) { /* puntatore non catturabile: il trascinamento funziona comunque */ }
    const startX = ev.clientX, startW = ui.leftW;
    let w = startW;
    shell.classList.add('resizing'); document.body.classList.add('resizing');
    const move = e => {
      w = startW + (e.clientX - startX);
      const lo = LEFT_MIN, hi = leftMax();
      const shown = w < lo ? lo - rubber(lo - w) : w > hi ? hi + rubber(w - hi) : w;
      setLeft(shown); redrawSide();
    };
    const up = () => {
      splitter.removeEventListener('pointermove', move);
      splitter.removeEventListener('pointerup', up);
      splitter.removeEventListener('pointercancel', up);
      shell.classList.remove('resizing'); document.body.classList.remove('resizing');
      settleLeft(w);
    };
    splitter.addEventListener('pointermove', move);
    splitter.addEventListener('pointerup', up);
    splitter.addEventListener('pointercancel', up);
  });
  splitter.addEventListener('dblclick', () => settleLeft(LEFT_DEF));
  splitter.addEventListener('keydown', ev => {
    const step = ev.shiftKey ? 64 : 16;
    const next = { ArrowLeft: ui.leftW - step, ArrowRight: ui.leftW + step, Home: LEFT_MIN, End: leftMax() }[ev.key];
    if (next === undefined) return;
    ev.preventDefault(); settleLeft(next);
  });
  window.addEventListener('resize', () => setLeft(clampLeft(ui.leftW)));
  setLeft(clampLeft(ui.leftW));

  // torte della home: passando (o con il focus) su uno spicchio o su una voce si aggiornano evidenziazione e riquadro
  const pieHover = target => {
    const hit = target && target.closest && target.closest('.ipie [data-i]');
    $$('.ipie').forEach(w => setActive(w, hit && w.contains(hit) ? +hit.dataset.i : null));
  };
  document.addEventListener('pointerover', ev => pieHover(ev.target));
  document.addEventListener('focusin', ev => pieHover(ev.target));
  document.documentElement.addEventListener('pointerleave', () => pieHover(null));
  document.addEventListener('keydown', ev => {
    const sl = ev.target.closest && ev.target.closest('.slice[role="button"]');
    if (sl && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); sl.dispatchEvent(new MouseEvent('click', { bubbles: true })); }
  });

  // barra degli strumenti: separatore solo quando il contenuto ci scorre sotto
  const tb = $('#toolbar');
  window.addEventListener('scroll', () => tb.classList.toggle('scrolled', window.scrollY > 4), { passive: true });

  $('#reset').addEventListener('click', () => { state = seed(); save(); ui.ticker = null; ui.scope = 'rilevanti'; ui.q = ''; HOME.pin = null; history.replaceState(null, '', '#riepilogo'); renderAll(); toast('Dati demo ripristinati'); });
  $('#clear').addEventListener('click', () => { state.portafoglio = []; save(); history.replaceState(null, '', '#riepilogo'); renderAll(); toast('Portafoglio svuotato'); });
  dlg.addEventListener('click', ev => { if (ev.target === dlg) closeDialog(); });

  window.addEventListener('hashchange', route);
  renderAll();
})();
