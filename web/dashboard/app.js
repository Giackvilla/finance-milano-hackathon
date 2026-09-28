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
    panel: '<rect x="3" y="4.5" width="18" height="15" rx="3"/><path d="M9 4.5v15"/>'
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
  const savePref = () => { try { localStorage.setItem(PREF, JSON.stringify({ sideOpen: ui.sideOpen, sideTab: ui.sideTab, leftW: ui.leftW })); } catch (e) { /* ignora */ } };
  const ui = { range: '3M', scope: 'rilevanti', ticker: null, q: '', quarter: {}, editing: false, removing: false, current: null, sideOpen: pref.sideOpen !== false, sideTab: pref.sideTab === 'watchlist' ? 'watchlist' : 'portafoglio', leftW: pref.leftW || 320, allNews: {}, lastMain: '#riepilogo', fg: 'italy' };

  const azienda = t => state.aziende[t] || D.aziende[t] || null;
  const tesiDi = t => ({ ...azienda(t).tesi, ...(state.tesi[t] || {}) });
  const held = t => state.portafoglio.some(p => p.ticker === t);
  const watched = t => state.watchlist.some(w => w.ticker === t);
  const tracked = t => held(t) || watched(t);
  const ownership = t => (held(t) ? 'p' : watched(t) ? 'w' : '');
  const varDi = t => (D.mercato[t] ?? 0);
  const serieDi = t => { const a = azienda(t); return D.serie(t, a.prezzo, varDi(t)); };
  const linked = n => n.strumenti.filter(s => s.sim >= D.soglia);
  /* Provenienza: dataset = prezzi/articoli MF; simulato = serie inventata; esempio = holding/tesi demo. */
  const prezzoFonte = a => (a && a.prezzo_fonte) || (D.reale ? 'simulato' : 'esempio');
  const isPrezzoSim = a => prezzoFonte(a) === 'simulato';
  const prov = (kind, title) => {
    const m = { dataset: ['prov-ds', 'Dataset'], modello: ['prov-mod', 'Modello'], esempio: ['prov-ex', 'Esempio'] }[kind];
    return m ? `<span class="prov ${m[0]}"${title ? ` title="${esc(title)}"` : ''}>${m[1]}</span>` : '';
  };
  const cutoffsHTML = () => {
    if (!D.reale) return '';
    const p = D.reale.prezzi_al || D.aggiornamento, n = D.reale.notizie_al || D.aggiornamento;
    return `<span class="cut">Prezzi al ${esc(p)} · Notizie al ${esc(n)}</span>`;
  };
  const syncFooter = () => {
    const el = $('#foot-prov');
    if (!el) return;
    if (D.reale) {
      el.textContent = `Prezzi e articoli MF da dataset (prezzi al ${D.reale.prezzi_al}, notizie al ${D.reale.notizie_al}). Interpretazioni del modello. Portafoglio e tesi di esempio. Non usare per decisioni di investimento.`;
    } else {
      el.textContent = 'Demo interamente simulata: prezzi, notizie e segnali sono inventati. Non usare per decisioni di investimento.';
    }
  };

  /* Pesi sul controvalore a prezzi dataset: le posizioni a prezzo simulato restano in lista ma fuori dal totale. */
  function posizioni() {
    const rows = state.portafoglio.map(p => {
      const a = azienda(p.ticker);
      return a && { ...p, a, simPrezzo: isPrezzoSim(a), valore: p.quantita * a.prezzo };
    }).filter(Boolean);
    const base = D.reale ? rows.filter(r => !r.simPrezzo) : rows;
    const tot = base.reduce((s, r) => s + r.valore, 0);
    if (!rows.length) return { rows: [], base: [], tot: 0 };
    if (!tot) {
      rows.forEach(r => { r.peso = null; });
      rows.sort((a, b) => b.valore - a.valore);
      return { rows, base, tot: 0 };
    }
    const raw = base.map(r => r.valore / tot * 1000), fl = raw.map(Math.floor);
    let rest = 1000 - fl.reduce((a, b) => a + b, 0);
    raw.map((v, i) => [v - fl[i], i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (rest > 0) { fl[i]++; rest--; } });
    base.forEach((r, i) => { r.peso = fl[i] / 10; });
    rows.forEach(r => { if (r.simPrezzo && D.reale) r.peso = null; });
    rows.sort((a, b) => (b.simPrezzo === a.simPrezzo ? b.valore - a.valore : (a.simPrezzo ? 1 : -1)));
    return { rows, base, tot };
  }

  /* ================================================================ vocabolario */
  const STATO = {
    rafforzata: { label: 'Rafforzata', dash: 'Rafforzata', cls: 'pos', ic: 'check' },
    invariata: { label: 'Invariata', dash: 'Invariata', cls: 'neu', ic: 'eq' },
    indebolita: { label: 'Indebolita', dash: 'Da rivedere', cls: 'warn', ic: 'alert' },
    insufficiente: { label: 'Dati insufficienti', dash: 'Dati insufficienti', cls: 'na', ic: 'q' }
  };
  const IND_STATO = {
    a_favore: { label: 'A favore', cls: 'pos', ic: 'check' },
    neutro: { label: 'Neutro', cls: 'neu', ic: 'eq' },
    contro: { label: 'Contro', cls: 'warn', ic: 'alert' },
    non_citato: { label: 'Non citato negli articoli', cls: 'na', ic: 'q' }
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

  const VERD_GROUP = { REACTED: 'reazione', DELAYED: 'reazione', ALREADY_IN_PRICE: 'gia', PARTLY_IN_PRICE: 'gia', MOSTLY_AT_OPEN: 'gia', NO_REACTION: 'nessuna' };

  const statoDi = a => (a.esito && a.esito.stato) || 'insufficiente';
  const chipStato = (stato, lg) => { const s = STATO[stato]; return `<span class="chip ${s.cls}${lg ? ' lg' : ''}">${icon(s.ic)}${s.label}</span>`; };
  const contesto = t => (held(t) ? 'portafoglio' : 'watchlist');
  const decisioneDi = t => { const d = azienda(t).decisione; return d && d.contesto === contesto(t) ? d : null; };
  const trend = d => icon(d === 'up' ? 'up' : d === 'down' ? 'down' : 'flat');
  const pill = v => `<span class="pill ${dirOf(v)}">${signed(v)}</span>`;
  /* Analisi reale se la pipeline ha iniettato tesi_usata o esito.metodo; altrimenti fallback simulato di data.js. */
  const isSimAnalisi = a => !(a && (a.tesi_usata || (a.esito && a.esito.metodo)));
  const sameList = (a, b) => {
    const x = (a || []).map(s => String(s).trim()).filter(Boolean);
    const y = (b || []).map(s => String(s).trim()).filter(Boolean);
    return x.length === y.length && x.every((v, i) => v === y[i]);
  };
  const samePeso = (a, b) => {
    const n = v => (v == null || v === '' || Number.isNaN(Number(v)) ? null : Number(v));
    const x = n(a), y = n(b);
    return x === y;
  };
  const tesiStale = (t, a) => {
    const cur = tesiDi(t);
    if (a && a.tesi_usata) {
      const u = a.tesi_usata;
      const base = (D.aziende[t] && D.aziende[t].tesi) || {};
      const usedPeso = ('pesoPrevisto' in u) ? u.pesoPrevisto : base.pesoPrevisto;
      return String(cur.motivo || '').trim() !== String(u.motivo || '').trim()
        || !sameList(cur.indicatori, u.indicatori)
        || String(cur.orizzonte || '').trim() !== String(u.orizzonte || '').trim()
        || !samePeso(cur.pesoPrevisto, usedPeso);
    }
    return !!(state.tesi[t] && state.tesi[t].modificata);
  };
  /* Stato ricalcolo per ticker: idle | running | error | done. Usato anche da strip riepilogo. */
  const ricalcoli = Object.create(null);
  const statoRicalcolo = t => {
    const r = ricalcoli[t];
    if (r && r.status === 'running') return 'running';
    if (r && r.status === 'error') return 'error';
    if (tesiStale(t, azienda(t))) return 'stale';
    return 'ok';
  };
  const ultimoRicalcolo = t => (ricalcoli[t] && ricalcoli[t].diff) || null;
  const labelStato = s => (STATO[s] ? STATO[s].label : (s || '—'));
  const labelAzione = (ctx, az) => (AZIONI[ctx] && AZIONI[ctx][az]) || az || '—';
  const labelInd = s => (IND_STATO[s] ? IND_STATO[s].label : (s || '—'));
  const diffRicalcolo = (before, after, ctx) => {
    if (!before || !after) return null;
    const out = { status: null, decisione: null, indicatori: [], sintesi: false };
    if ((before.status || '') !== (after.status || '')) {
      out.status = { da: labelStato(before.status), a: labelStato(after.status) };
    }
    const bd = before.decisione || {}, ad = after.decisione || {};
    if ((bd.azione || '') !== (ad.azione || '') || (bd.motivazione || '') !== (ad.motivazione || '')) {
      out.decisione = { da: labelAzione(ctx, bd.azione), a: labelAzione(ctx, ad.azione) };
    }
    const byNome = {};
    (before.indicatori || []).forEach(i => { if (i && i.nome) byNome[i.nome] = i.stato; });
    (after.indicatori || []).forEach(i => {
      if (!i || !i.nome) return;
      const prev = byNome[i.nome];
      if (prev !== i.stato) out.indicatori.push({ nome: i.nome, da: labelInd(prev), a: labelInd(i.stato) });
    });
    out.sintesi = String(before.sintesi || '').trim() !== String(after.sintesi || '').trim();
    return out;
  };
  const tesiUsataLabel = t => {
    const mod = state.tesi[t] && state.tesi[t].modificata;
    return mod || 'versione precedente';
  };
  const fonteLink = f => {
    if (!f || !f.url) return '';
    const label = f.data ? `MF · ${f.data}` : 'MF';
    return `<a class="fact-src" href="${esc(f.url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
  };
  const factHTML = f => {
    if (f == null) return '';
    if (typeof f === 'string') return esc(f);
    const quote = f.citazione
      ? `<details class="fact-quote"><summary>Citazione</summary><q>${esc(f.citazione)}</q></details>` : '';
    return `<span class="fact-body"><span>${esc(f.testo || '')}${f.fonte ? ` ${fonteLink(f.fonte)}` : ''}</span>${quote}</span>`;
  };
  const fontiUniche = items => {
    const seen = new Set(), out = [];
    (items || []).forEach(x => {
      const f = x && typeof x === 'object' ? x.fonte : null;
      if (!f || !f.url || seen.has(f.url)) return;
      seen.add(f.url);
      out.push(f);
    });
    return out;
  };
  const srcNoteHTML = (items, sim) => {
    const fonti = fontiUniche(items);
    if (fonti.length) return `${icon('doc')}${fonti.map(f => `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.titolo || 'Articolo MF')}</a>`).join(' · ')}`;
    return `${icon('doc')}${sim ? 'Fonte non disponibile nella demo' : 'Fonte non disponibile'}`;
  };
  const indHTML = (ind, staleHide) => {
    if (!ind) return '';
    if (staleHide) return '';
    const s = IND_STATO[ind.stato] || IND_STATO.non_citato;
    const quote = ind.citazione
      ? `<details class="fact-quote"><summary>Citazione</summary><q>${esc(ind.citazione)}</q></details>` : '';
    return `<li class="ind-row"><div class="ind-head"><span class="chip ${s.cls}">${icon(s.ic)}${s.label}</span><span class="ind-nome">${esc(ind.nome)}</span></div>
      <p class="ind-testo">${esc(ind.testo || '')}${ind.fonte ? ` ${fonteLink(ind.fonte)}` : ''}</p>${quote}</li>`;
  };

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
    const { rows, base, tot } = posizioni();
    const search = `<label class="search">${icon('search')}<span class="sr">Cerca titoli o notizie</span>
      <input id="q" type="search" placeholder="Cerca" autocomplete="off" value="${esc(ui.q)}"><kbd>⌘K</kbd></label>`;
    let body;
    if (!rows.length) {
      body = `<div class="side-head"><h2>Portafoglio</h2></div>
        <div class="empty"><h3>Nessuna posizione</h3><p>Aggiungi un titolo che possiedi e il motivo per cui l’hai comprato: lo confronteremo con risultati e notizie.</p>
          <button class="btn" type="button" data-act="add-pos">${icon('plus')}Aggiungi posizione</button></div>`;
    } else {
      const chartRows = base.length ? base : rows;
      const { day, pct: dayPct } = dayChange(chartRows, tot || chartRows.reduce((s, r) => s + r.valore, 0));
      const nSim = rows.filter(r => r.simPrezzo).length;
      const prezziLabel = D.reale ? (D.reale.prezzi_al || D.aggiornamento) : D.aggiornamento;

      const counts = { pos: 0, neu: 0, warn: 0, na: 0 };
      rows.forEach(r => counts[STATO[statoDi(r.a)].cls]++);
      const sum = [counts.pos && `${counts.pos} rafforzate`, counts.neu && `${counts.neu} invariate`, counts.warn && `${counts.warn} da rivedere`, counts.na && `${counts.na} senza dati`].filter(Boolean).join(' · ');

      body = `<div class="side-head"><h2>Portafoglio ${prov('esempio', 'Posizioni e quantità di esempio per illustrare il flusso')}</h2><button class="icon-btn" type="button" data-act="add-pos" aria-label="Aggiungi posizione" title="Aggiungi posizione">${icon('plus')}</button></div>
        <div class="summary">
          <div class="label">Valore totale · prezzi al ${esc(prezziLabel)}${nSim && D.reale ? ' · solo dataset' : ''}</div>
          <div class="total num">${eur(tot)}</div>
          <div class="delta num ${dirOf(day)}"><span>${day >= 0 ? '+' : '−'}${eur(Math.abs(day))}</span><span>(${signed(dayPct)})</span><span class="muted">ultima seduta</span></div>
          ${nSim && D.reale ? `<p class="label" style="margin-top:6px">${nSim} ${nSim === 1 ? 'posizione esclusa' : 'posizioni escluse'} (prezzo simulato)</p>` : ''}
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
            const pxBadge = r.simPrezzo && D.reale
              ? prov('esempio', 'Prezzo simulato: assente dal dataset MF')
              : (D.reale ? prov('dataset', 'Prezzo da dataset MF') : prov('esempio', 'Prezzo demo'));
            const pesoTxt = r.peso == null ? 'fuori totale' : `${nf(r.peso, 1)}%`;
            return `<li><button class="sym" type="button" data-open="${esc(r.ticker)}"${ui.current === r.ticker ? ' aria-current="page"' : ''}>
              <span class="sym-l"><span class="sym-t">${esc(r.ticker)} ${pxBadge}</span><span class="sym-n">${esc(r.a.nome)}</span>
                <span class="sym-s"><i class="sdot ${st.cls}"></i>${st.dash} · ${pesoTxt}</span></span>
              ${sparkline(serieDi(r.ticker).slice(-22))}
              <span class="sym-r"><span class="sym-p">${nf(r.a.prezzo, priceDigits(r.a.prezzo))}</span>${pill(varDi(r.ticker))}</span>
            </button></li>`;
          }).join('')}</ul>
        </div>`;
    }
    if (ui.sideTab === 'watchlist') body = watchBody();
    const tabs = `<div class="seg side-tabs" role="tablist" aria-label="Elenco">${[['portafoglio', 'Portafoglio', state.portafoglio.length], ['watchlist', 'Watchlist', state.watchlist.length]]
      .map(([k, l, c]) => `<button type="button" role="tab" data-side-tab="${k}" aria-selected="${ui.sideTab === k}">${l}<span class="c">${c}</span></button>`).join('')}</div>`;
    $('#side-left').innerHTML = `<div class="side-inner">${search}${tabs}${body}</div>`;
    bindSearch();
    drawPortfolioChart();
  }

  function drawPortfolioChart() {
    const { base, rows } = posizioni();
    const chartRows = (base && base.length) ? base : rows;
    if (!chartRows.length) return;
    const n = RANGES[ui.range], N = D.giorni.length, vals = new Array(n).fill(0);
    chartRows.forEach(r => { const s = serieDi(r.ticker); for (let i = 0; i < n; i++) vals[i] += r.quantita * s[N - n + i]; });
    const dates = D.giorni.slice(N - n), ch = vals[n - 1] - vals[0], pct = (vals[n - 1] / vals[0] - 1) * 100;
    const delta = `<span class="${dirOf(ch)}">${ch >= 0 ? '+' : '−'}${eur(Math.abs(ch), 0)} (${signed(pct, 1)})</span> <span class="muted">nel periodo</span>`;
    if ($('#pchart')) { areaChart($('#pchart'), vals, dates, { h: w => Math.round(Math.max(132, Math.min(300, w * 0.42))), padR: 40, xLabels: [0.15, 0.85], year: ui.range === 'MAX', label: 'Valore del portafoglio' }); $('#rdelta').innerHTML = delta; }
    $$('[data-range]').forEach(b => b.setAttribute('aria-pressed', b.dataset.range === ui.range));
  }

  /* ================================================================ barra laterale: scheda watchlist */
  function watchBody() {
    const items = state.watchlist.map(w => azienda(w.ticker)).filter(Boolean);
    const list = items.length ? `<ul class="syms">${items.map(a => {
      const dec = decisioneDi(a.ticker);
      const act = dec ? `<i class="sdot ${AZIONE_BREVE[dec.azione].cls}"></i>${AZIONE_BREVE[dec.azione].label}` : '<i class="sdot na"></i>Dati insufficienti';
      const pxBadge = isPrezzoSim(a) && D.reale
        ? prov('esempio', 'Prezzo simulato')
        : (D.reale ? prov('dataset', 'Prezzo da dataset MF') : prov('esempio', 'Prezzo demo'));
      return `<li><button class="sym" type="button" data-open="${esc(a.ticker)}"${ui.current === a.ticker ? ' aria-current="page"' : ''} title="${esc(tesiDi(a.ticker).motivo)}">
        <span class="sym-l"><span class="sym-t">${esc(a.ticker)} ${pxBadge}</span><span class="sym-n">${esc(a.nome)}</span><span class="sym-s">${act}</span></span>
        ${sparkline(serieDi(a.ticker).slice(-22))}
        <span class="sym-r"><span class="sym-p">${nf(a.prezzo, priceDigits(a.prezzo))}</span>${pill(varDi(a.ticker))}</span>
      </button></li>`;
    }).join('')}</ul>` : `<div class="empty"><h3>Watchlist vuota</h3><p>Aggiungi un’azienda che stai valutando e il motivo del tuo interesse.</p>
      <button class="btn" type="button" data-act="add-watch">${icon('plus')}Aggiungi alla watchlist</button></div>`;
    return `<div class="side-head"><h2>Watchlist ${prov('esempio', 'Watchlist di esempio')}</h2><button class="icon-btn" type="button" data-act="add-watch" aria-label="Aggiungi alla watchlist" title="Aggiungi alla watchlist">${icon('plus')}</button></div>
      ${items.length ? '<p class="label" style="padding:0 6px;margin-top:-10px">Azione da valutare · ultimo mese</p>' : ''}
      ${list}`;
  }

  /* ================================================================ Fear & Greed */
  const FG_BAND = {
    'Extreme fear': 'Paura estrema',
    Fear: 'Paura',
    Neutral: 'Neutro',
    Greed: 'Avidità',
    'Extreme greed': 'Avidità estrema',
  };
  const FG_PART = {
    momentum: 'Momento',
    strength: 'Forza',
    breadth: 'Ampiezza',
    volatility: 'Volatilità',
    narrative: 'Tono notizie',
  };
  const fgTone = score => (score < 45 ? 'var(--down)' : score < 55 ? 'var(--ink-2)' : 'var(--up)');
  const fgBand = label => FG_BAND[label] || label;
  const fgDate = iso => {
    const d = new Date(iso + 'T00:00:00Z');
    return `${d.getUTCDate()} ${MESI[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  };
  const fgCount = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  function fgShocks(block) {
    return `${fgCount(block.shocks_down, 'ribasso', 'ribassi')} · ${fgCount(block.shocks_up, 'rialzo', 'rialzi')} oggi · ${block.shocks_5d} in 5 sedute`;
  }
  function fgGauge(score) {
    const left = Math.max(0, Math.min(100, score));
    return `<div class="fg-gauge" aria-hidden="true"><div class="fg-tick" style="left:${left}%"></div></div>`;
  }
  function fgBars(components) {
    return `<div class="fg-bars">${Object.keys(FG_PART).map(key => {
      const part = components[key];
      const width = Math.max(0, Math.min(100, part.value));
      return `<div class="fg-bar"><span>${FG_PART[key]}</span><div class="fg-track"><i class="fg-fill" style="width:${width}%"></i></div><b class="num">${nf(part.weight * 100, 1)}%</b></div>`;
    }).join('')}</div>`;
  }
  function fgSector(ticker) {
    const fg = window.FEAR_GREED;
    if (!fg) return null;
    return fg.sectors.find(s => (s.tickers || []).indexOf(ticker) >= 0) || null;
  }
  /* Zone e soglie uguali a scripts/fear_greed.py (label_for). */
  const FG_ZONES = [
    { lo: 0, hi: 25, key: 'Extreme fear', short: 'Paura estrema', tone: 'fear' },
    { lo: 25, hi: 45, key: 'Fear', short: 'Paura', tone: 'fear' },
    { lo: 45, hi: 55, key: 'Neutral', short: 'Neutro', tone: 'neutral' },
    { lo: 55, hi: 75, key: 'Greed', short: 'Avidità', tone: 'greed' },
    { lo: 75, hi: 101, key: 'Extreme greed', short: 'Avidità estrema', tone: 'greed' }
  ];
  const fgZone = v => FG_ZONES.find(z => v >= z.lo && v < z.hi) || FG_ZONES[FG_ZONES.length - 1];

  /* Quadrante a semicerchio: cinque zone (quella attiva colorata), scala 0-100, lancetta, valore al centro. */
  function fgDial(score) {
    const W = 360, cx = 180, cy = 184, R = 176, r0 = 112, rl = (R + r0) / 2;
    /* Scala a tratti: il neutro (45-55) occupa il 15% dell'arco invece del 10%, così resta leggibile.
       Lancetta, puntini e numeri usano la stessa scala, quindi i confini delle zone restano esatti. */
    const SPAN = [0.2125, 0.2, 0.15, 0.2, 0.2375];
    const ang = v => {
      const x = Math.max(0, Math.min(100, v));
      let acc = 0;
      for (let k = 0; k < FG_ZONES.length; k++) {
        const z = FG_ZONES[k], hi = Math.min(100, z.hi);
        if (x <= hi || k === FG_ZONES.length - 1) return Math.PI + (acc + SPAN[k] * (x - z.lo) / (hi - z.lo)) * Math.PI;
        acc += SPAN[k];
      }
    };
    const pt = (rad, a) => `${(cx + rad * Math.cos(a)).toFixed(1)} ${(cy + rad * Math.sin(a)).toFixed(1)}`;
    const active = fgZone(score);
    const zones = FG_ZONES.map((z, i) => {
      const a0 = ang(z.lo) + 0.012, a1 = ang(Math.min(100, z.hi)) - 0.012;
      const on = z === active;
      return `<path class="fg-zone${on ? ` on ${z.tone}` : ''}" d="M${pt(R, a0)}A${R} ${R} 0 0 1 ${pt(R, a1)}L${pt(r0, a1)}A${r0} ${r0} 0 0 0 ${pt(r0, a0)}Z"/>
        <path id="fgl${i}" d="M${pt(rl, a0)}A${rl} ${rl} 0 0 1 ${pt(rl, a1)}" fill="none"/>
        ${(() => {
          /* Etichetta sull'arco: se non ci sta, prima carattere più piccolo, poi compressa alla lunghezza dell'arco. */
          const txt = z.short.toUpperCase(), arc = (a1 - a0) * rl * 0.9, est = f => txt.length * f * 0.64;
          const tight = est(12.5) > arc, fit = tight && est(11) > arc ? ` textLength="${arc.toFixed(0)}" lengthAdjust="spacingAndGlyphs"` : '';
          return `<text class="fg-zl${on ? ' on' : ''}${tight ? ' tight' : ''}"><textPath href="#fgl${i}" startOffset="50%" text-anchor="middle" dominant-baseline="middle"${fit}>${txt}</textPath></text>`;
        })()}`;
    }).join('');
    const dots = Array.from({ length: 21 }, (_, i) => i * 5).filter(v => v % 25).map(v => { const a = ang(v); return `<circle cx="${(cx + (r0 - 14) * Math.cos(a)).toFixed(1)}" cy="${(cy + (r0 - 14) * Math.sin(a)).toFixed(1)}" r="1.5"/>`; }).join('');
    const nums = [0, 25, 50, 75, 100].map(v => { const a = ang(v); return `<text class="fg-num" x="${(cx + (r0 - 22) * Math.cos(a)).toFixed(1)}" y="${(cy + (r0 - 22) * Math.sin(a) + 4).toFixed(1)}" text-anchor="middle">${v}</text>`; }).join('');
    const a = ang(score), tip = pt(r0 - 6, a), b1 = pt(5, a + Math.PI / 2), b2 = pt(5, a - Math.PI / 2);
    return `<svg class="fg-dial" viewBox="0 0 ${W} ${cy + 6}" role="img" aria-label="Indice ${nf(score, 1)} su 100: ${esc(active.short)}">
      ${zones}<g class="fg-dots">${dots}</g>${nums}
      <path class="fg-needle" d="M${b1}L${tip}L${b2}Z"/>
      <circle class="fg-hub" cx="${cx}" cy="${cy}" r="36"/>
      <text class="fg-val" x="${cx}" y="${cy - 6}" text-anchor="middle">${Math.round(score)}</text>
    </svg>`;
  }

  function fearGreedHTML() {
    const fg = window.FEAR_GREED;
    if (!fg) return '';
    const selected = ui.fg === 'italy' ? null : fg.sectors.find(s => s.id === ui.fg);
    const block = selected || fg.italy;
    const name = selected ? selected.name : 'Italia';
    const picks = [{ id: 'italy', name: 'Italia', score: fg.italy.score, label: fg.italy.label }].concat(fg.sectors);
    const heads = (selected && selected.headlines) || [];
    const sp = block.spark || [], at = k => (sp.length > k ? sp[sp.length - 1 - k] : null);
    const hist = [['Chiusura precedente', at(1)], ['1 settimana fa', at(5)], ['1 mese fa', at(21)], ['3 mesi fa', sp.length ? sp[0] : null]];
    const zone = fgZone(block.score);
    return `<section class="card fg" id="fear-greed" aria-labelledby="h-fg">
      <div class="card-h"><div><h2 id="h-fg">Fear &amp; Greed · ${esc(name)} ${prov('modello', 'Indice descrittivo sul nastro e sul tono delle notizie. Non è un segnale operativo.')}</h2>
        <p class="muted" style="font-size:13px;margin-top:2px">Che emozione muove il mercato oggi? · ${esc(fgDate(block.date))}</p></div>
        <span class="fg-now ${zone.tone}">${esc(fgBand(block.label))}</span></div>
      <div class="fg-body">
        ${fgDial(block.score)}
        <dl class="fg-hist">${hist.map(([l, v]) => {
          const z = v == null ? null : fgZone(v);
          return `<div><dt><span>${l}</span><b>${z ? esc(z.short) : 'n.d.'}</b></dt><i aria-hidden="true"></i><dd class="${z ? z.tone : ''}">${v == null ? '—' : Math.round(v)}</dd></div>`;
        }).join('')}</dl>
      </div>
      <div class="fg-picks" role="group" aria-label="Mercato o settore">${picks.map(p => `<button class="fg-pick" type="button" data-fg="${esc(p.id)}" aria-pressed="${(selected ? selected.id : 'italy') === p.id}">
        <span class="nm">${esc(p.name)}</span><b class="${fgZone(p.score).tone}">${Math.round(p.score)}</b>
      </button>`).join('')}</div>
      <details class="fg-more"><summary>Come è calcolato</summary>
        <p class="fg-shocks">${fgShocks(block)} <span class="muted">· ${block.names} titoli</span></p>
        ${fgBars(block.components)}
        ${heads.length ? `<ul class="fg-heads">${heads.map(h => `<li>${esc(h)}</li>`).join('')}</ul>` : ''}
      </details>
    </section>`;
  }
  function fearGreedCompanyHTML(ticker) {
    const sector = fgSector(ticker);
    if (!sector) return '';
    return `<section class="card fg-co" aria-label="Fear and Greed del settore">
      <div class="fg-top">
        <div>
          <div class="fg-kicker">Fear &amp; Greed · ${esc(sector.name)} ${prov('modello', 'Stesso indice della home, sul paniere di questo settore.')}</div>
          <div class="label">${esc(fgDate(sector.date))} · ${esc(fgShocks(sector))}</div>
        </div>
        <div class="fg-side">
          <div class="fg-score" style="color:${fgTone(sector.score)}">${nf(sector.score, 1)}</div>
          <div class="fg-band" style="color:${fgTone(sector.score)}">${esc(fgBand(sector.label))}</div>
        </div>
      </div>
      ${fgGauge(sector.score)}
    </section>`;
  }

  /* ================================================================ area centrale: notizie */
  function toolbar(mode) {
    const nav = mode === 'detail'
      ? `<button class="back" type="button" data-act="back">${icon('back')}${ui.lastMain === '#notizie' ? 'Notizie' : 'Riepilogo'}</button>`
      : `<nav class="seg" aria-label="Sezioni"><a href="#riepilogo"${mode === 'home' ? ' aria-current="page"' : ''}>Riepilogo</a><a href="#notizie"${mode === 'news' ? ' aria-current="page"' : ''}>Notizie</a></nav>`;
    const sl = ui.sideOpen ? 'Nascondi la barra laterale' : 'Mostra la barra laterale';
    $('#toolbar').innerHTML = `<button class="icon-btn plain" type="button" data-act="toggle-side" aria-controls="side-left" aria-pressed="${ui.sideOpen}" aria-label="${sl}" title="${sl}">${icon('panel')}</button>
      ${nav}
      <span class="spacer"></span>
      <span class="status">Borsa Italiana · chiusa ·</span>
      <span class="demo"${D.reale ? ` title="${esc(`${D.reale.etichetta} · Prezzi al ${D.reale.prezzi_al || D.aggiornamento} · Notizie al ${D.reale.notizie_al || D.aggiornamento}`)}"` : ''}>${D.reale ? `${esc(D.reale.etichetta)} · ${cutoffsHTML()}` : 'Dati simulati'}</span>`;
  }
  function applySide() {
    $('#shell').classList.toggle('side-closed', !ui.sideOpen);
    $('#side-left').inert = !ui.sideOpen;
    const b = $('[data-act="toggle-side"]');
    if (b) { const l = ui.sideOpen ? 'Nascondi la barra laterale' : 'Mostra la barra laterale'; b.setAttribute('aria-pressed', ui.sideOpen); b.setAttribute('aria-label', l); b.title = l; }
    setTimeout(() => charts.forEach((draw, host) => { if (host.isConnected) draw(); }), 320);
  }

  function newsMatches(n) {
    const q = ui.q.trim().toLowerCase();
    if (!q) return true;
    return n.titolo.toLowerCase().includes(q) || n.riassunto.toLowerCase().includes(q) ||
      n.strumenti.some(s => s.ticker.toLowerCase() === q || (azienda(s.ticker) && azienda(s.ticker).nome.toLowerCase().includes(q)));
  }
  const inScope = t => (ui.scope === 'portafoglio' ? held(t) : ui.scope === 'watchlist' ? watched(t) : tracked(t));

  /* Reazione di prezzo osservata per titolo: media di (direzione × forza × similarità). Descrittiva, non predittiva. */
  function signalBoard() {
    const acc = {};
    D.notizie.forEach(n => {
      if (!n.segnale) return;
      linked(n).forEach(s => {
        if (!tracked(s.ticker)) return;
        const o = acc[s.ticker] || (acc[s.ticker] = { sum: 0, n: 0 });
        o.sum += (s.dir === 'up' ? 1 : s.dir === 'down' ? -1 : 0) * n.segnale.forza * s.sim; o.n++;
      });
    });
    return Object.entries(acc).map(([t, o]) => ({ t, v: o.sum / o.n, n: o.n })).sort((a, b) => Math.abs(b.v) - Math.abs(a.v)).slice(0, 10);
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
      sig = `<div class="sig" title="Reazione di prezzo osservata attorno all’articolo (anche dopo la pubblicazione). Non è una previsione.">
        <span class="chip ${vd.cls}">${esc(vd.label)}</span><span class="hist">${fig}</span> ${prov('modello', 'Verdetto euristico sul movimento osservato')}</div>`;
    } else if (g) {
      sig = `<div class="sig" title="Reazione media osservata su articoli simili in demo. Descrive il passato, non prevede.">
        <span class="dir ${dir}">${trend(dir)}${DIR_LABEL[dir]}</span><span class="meter ${dir}" role="img" aria-label="Intensità osservata ${nf(g.forza, 2)}"><i style="width:${Math.round(g.forza * 100)}%"></i></span>
        <span class="hist">· simili <b class="${dirOf(g.storico.pct)}">${signed(g.storico.pct, 1)}</b> in ${g.storico.sedute} sedute (n=${g.storico.n})</span> ${prov('esempio', 'Dato dimostrativo')}</div>`;
    } else {
      sig = `<div class="sig"><span class="hist">Nessuno strumento sopra la soglia (migliore ${nf(n.migliore, 2)} &lt; ${nf(D.soglia, 2)}): nessuna reazione collegata</span></div>`;
    }
    let tl = '';
    if (n.indicatore && (!t || n.indicatore.ticker === t) && tracked(n.indicatore.ticker)) tl = `<div class="tl">${icon('link')}<span>Tocca la tua tesi: “${esc(n.indicatore.nome)}”</span> ${prov('modello', 'Collegamento generato dal modello')}</div>`;
    else if (n.notaTesi && t) tl = `<div class="tl off">${icon('link')}<span>${esc(n.notaTesi)}</span></div>`;
    const fonte = n.url
      ? `<a href="${esc(n.url)}" target="_blank" rel="noopener">Fonte: MF</a>`
      : '';
    return `<article class="ncard">
      <div class="src">${prov('dataset', 'Articolo MF dal dataset')} MF Milano Finanza · ${esc(n.sezione)}${s && !vd ? ` · similarità ${nf(s.sim, 2)}` : ''}${fonte ? ` · ${fonte}` : ''}</div>
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
      const pxBadge = isPrezzoSim(a) && D.reale
        ? prov('esempio', 'Prezzo simulato')
        : (D.reale ? prov('dataset', 'Prezzo da dataset MF') : prov('esempio', 'Prezzo demo'));
      return `<section class="ssec" aria-labelledby="sec-${esc(t)}">
        <div class="ssec-h"><button class="ssec-title" type="button" data-open="${esc(t)}" id="sec-${esc(t)}"><span class="t">${esc(t)}</span><span class="n">${esc(a.nome)}</span></button><span class="tag">${own}</span></div>
        <div class="quote"><span class="p">${nf(a.prezzo, priceDigits(a.prezzo))}</span><span class="c ${dirOf(v)}">${signed(v)}</span> ${pxBadge}<span class="vsep"></span>${chipStato(statoDi(a))}</div>
        <div class="cards">${items.slice(0, 4).map(n => newsCard(n, t)).join('')}</div>
        <div class="more"><button type="button" data-open="${esc(t)}">SCHEDA <b>${esc(t)}</b>${icon('chev')}</button></div>
      </section>`;
    }).join('') + (loose.length ? `<section class="ssec"><div class="ssec-h"><span class="ssec-title"><span class="t">Mercati</span><span class="n">senza titoli collegati</span></span></div>
        <div class="cards">${loose.map(n => newsCard(n, null)).join('')}</div></section>` : '');

    const board = signalBoard();
    const boardHTML = board.length && !ui.q ? `<section class="card board" aria-labelledby="h-board">
        <div class="board-h"><h2 id="h-board">Reazioni di prezzo osservate</h2><p>${D.reale
          ? 'Media di direzione × intensità del picco di prezzo osservato attorno agli articoli MF (anche dopo la pubblicazione). Descrive reazioni passate, non è una previsione. Scala −1 … +1'
          : 'Demo: media di direzione × intensità × similarità sulle ultime sedute. Descrive reazioni passate inventate, non è una previsione. Scala −1 … +1'}</p></div>
        <div class="board-rows">${board.map(b => `<button class="brow" type="button" data-filter="${esc(b.t)}" aria-pressed="${ui.ticker === b.t}" title="${esc(azienda(b.t).nome)}: ${b.n} ${b.n === 1 ? 'articolo' : 'articoli'}, reazione media osservata ${signed(b.v, 2, '')}">
          <span class="t"><span class="own ${ownership(b.t)}"></span>${esc(b.t)}</span>
          <span class="track"><i class="${b.v >= 0 ? 'up' : 'down'}" style="width:calc(${Math.min(1, Math.abs(b.v)) * 50}% - 1px)"></i></span>
          <span class="v">${signed(b.v, 2, '')}</span></button>`).join('')}</div>
        <div class="board-legend"><span><i style="background:var(--up)"></i>Rialzo osservato</span><span><i style="background:var(--down)"></i>Ribasso osservato</span><span><span class="own p"></span>In portafoglio</span><span><span class="own w"></span>In watchlist</span></div>
      </section>` : '';

    const newsAsOf = D.reale && D.reale.notizie_al ? parseIt(D.reale.notizie_al) : asOfDate;
    const d = newsAsOf || asOfDate;
    $('#app').innerHTML = `<div class="view">
      <h1 class="page-title" tabindex="-1" id="ptitle">Notizie <span class="date">${d.getUTCDate()} ${MESI_LUNGHI[d.getUTCMonth()]}</span></h1>
      <p class="page-sub">${D.reale ? esc(D.reale.sottotitolo) : `Da MF Milano Finanza (demo), collegate ai titoli per similarità tra embedding (soglia ${nf(D.soglia, 2)}). La reazione di prezzo sotto ogni articolo descrive movimenti passati, non una previsione.`}</p>
      ${D.indici.length ? `<div class="tape" aria-label="Indici (demo)">${D.indici.map(x => `<span>${esc(x.nome)}<b>${esc(x.valore)}</b><span class="${dirOf(x.var)}">${signed(x.var)}</span></span>`).join('')}</div>` : ''}
      <div class="controls">
        <div class="seg" role="group" aria-label="Quali notizie">${scopes.map(([k, l]) => `<button type="button" data-scope="${k}" aria-pressed="${ui.scope === k}">${l}<span class="c">${counts[k]}</span></button>`).join('')}</div>
        ${ui.ticker ? `<span class="filter">Solo <b>${esc(ui.ticker)}</b><button type="button" data-act="clear-filter" aria-label="Rimuovi filtro">${icon('x')}</button></span>` : ''}
        ${ui.q ? `<span class="filter">“${esc(ui.q)}”<button type="button" data-act="clear-q" aria-label="Cancella ricerca">${icon('x')}</button></span>` : ''}
      </div>
      ${boardHTML}
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
    const fg = window.FEAR_GREED ? fearGreedHTML() : `<section class="card fg-slot" id="fear-greed" aria-labelledby="h-fg">
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
      /* Come il totale: nelle torte solo le posizioni con un peso (prezzo dal dataset); le altre sono indicate sotto. */
      const inPie = rows.filter(r => typeof r.peso === 'number'), fuori = rows.filter(r => typeof r.peso !== 'number');
      const secs = sectors(inPie), names = new Set(secs.map(x => x.n));
      HOME.rows = inPie; HOME.tot = tot;
      HOME.titoli = companies(inPie);
      HOME.settori = secs.map(x => ({ ...x, members: inPie.filter(r => { const s0 = D.settori[r.ticker] || 'Altro'; return (names.has(s0) ? s0 : 'Altro') === x.n; }) }));
      HOME.fuori = fuori;
      if (HOME.pin != null && !HOME.settori[HOME.pin]) HOME.pin = null;
      body = `<div class="home-grid">
        <section class="card"><div class="card-h"><h2>Per titolo</h2><span class="muted">Clic: scheda del titolo</span></div>${pieInteractive('titoli')}</section>
        <section class="card"><div class="card-h"><h2>Per settore</h2><span class="muted">Clic: i titoli del settore</span></div>${pieInteractive('settori')}</section>
      </div>
      ${fuori.length ? `<p class="note" style="margin-top:10px">Fuori dalle torte e dal totale: ${fuori.map(r => `${esc(r.ticker)} (${esc(r.a.nome.replace(/ · prezzo simulato$/, ''))})`).join(', ')}, perché il prezzo è simulato e non presente nel dataset MF.</p>` : ''}`;
    }
    $('#app').innerHTML = `<div class="view">${head}${fg}${body}</div>`;
    if (typeof window.renderFearGreed === 'function') {
      try { window.renderFearGreed($('#fear-greed'), { data: D, posizioni }); } catch (e) { console.error('renderFearGreed', e); }
    }
  }

  /* ================================================================ area centrale: scheda azienda */
  /* Notizie del titolo raggruppate per indicatore della tesi attuale; il resto finisce in “fuori”. */
  function newsAnalysis(t) {
    const inds = (tesiDi(t).indicatori || []).map(s => String(s).trim()).filter(Boolean);
    const rel = D.notizie.filter(n => n.strumenti.some(s => s.ticker === t && s.sim >= D.soglia)).sort((x, y) => y.data.localeCompare(x.data));
    const groups = inds.map(nome => ({ nome, items: [] })), fuori = [];
    rel.forEach(n => {
      const nome = n.indicatore && n.indicatore.ticker === t ? String(n.indicatore.nome).trim() : null;
      const g = nome && groups.find(x => x.nome === nome);
      (g ? g.items : fuori).push(n);
    });
    return { rel, groups, fuori, touching: rel.length - fuori.length };
  }

  function newsCountsHTML(items, t) {
    if (!items.length) return '';
    const withV = items.filter(n => n.verdetto);
    if (withV.length) {
      const c = { reazione: 0, gia: 0, nessuna: 0 };
      withV.forEach(n => c[VERD_GROUP[n.verdetto.status] || 'nessuna']++);
      return [c.reazione ? `${c.reazione} con reazione del prezzo` : '', c.gia ? `${c.gia} già nel prezzo` : '', c.nessuna ? `${c.nessuna} senza movimento anomalo` : ''].filter(Boolean).join(' · ');
    }
    const c = { up: 0, down: 0, flat: 0 };
    items.forEach(n => { const s = n.strumenti.find(x => x.ticker === t); c[(s && s.dir) || 'flat']++; });
    return [c.up ? `${c.up} rialzist${c.up === 1 ? 'a' : 'e'}` : '', c.down ? `${c.down} ribassist${c.down === 1 ? 'a' : 'e'}` : '', c.flat ? `${c.flat} neutr${c.flat === 1 ? 'a' : 'e'}` : ''].filter(Boolean).join(' · ');
  }

  function newsAnalysisHTML(t, na, stale, sim) {
    const a = azienda(t), da = a.analisi_notizie && a.analisi_notizie.da;
    const rs = statoRicalcolo(t);
    const head = `<div class="card-h"><h2>Analisi delle notizie</h2><span class="muted">${na.rel.length} ${na.rel.length === 1 ? 'articolo' : 'articoli'} MF${da ? ` dal ${esc(da)}` : ''}</span></div>`;
    if (!na.rel.length) return `${head}<p class="note">Nessun articolo${sim ? ' demo' : ''} collegato a questo titolo sopra la soglia di similarità: la decisione si basa solo sui risultati.</p>`;
    const lead = na.groups.length
      ? `${na.touching} ${na.touching === 1 ? 'articolo tocca' : 'articoli toccano'} un indicatore della tua tesi, ${na.fuori.length} no.`
      : 'La tesi non ha indicatori: nessun articolo può esservi collegato.';
    let banner = '';
    if (rs === 'running') {
      banner = `<div class="warnbox">${icon('alert')}<span>Ricalcolo in corso… i collegamenti notizie↔tesi verranno aggiornati.</span></div>`;
    } else if (stale) {
      banner = `<div class="warnbox">${icon('alert')}<span>Da ricalcolare: i collegamenti tra notizie e tesi si riferiscono alla tesi del ${esc(tesiUsataLabel(t))}.</span></div>`;
    }
    const groupsBody = na.groups.map(g => `<div class="block news-group">
        <div class="ind-head"><span class="chip ${g.items.length ? 'act' : 'na'}">${icon('link')}${g.items.length} ${g.items.length === 1 ? 'articolo' : 'articoli'}</span><span class="ind-nome">${esc(g.nome)}</span></div>
        ${g.items.length ? `<p class="note">${newsCountsHTML(g.items, t)}</p><div class="cards">${g.items.map(n => newsCard(n, t)).join('')}</div>` : '<p class="note">Nessun articolo recente su questo indicatore.</p>'}
      </div>`).join('');
    const fuori = na.fuori.length ? `<details class="news-more">
        <summary>Non toccano la tesi · ${na.fuori.length} ${na.fuori.length === 1 ? 'articolo' : 'articoli'}${newsCountsHTML(na.fuori, t) ? ` <span class="muted">(${newsCountsHTML(na.fuori, t)})</span>` : ''}</summary>
        <div class="cards">${na.fuori.map(n => newsCard(n, t)).join('')}</div></details>` : '';
    const groups = (stale || rs === 'running')
      ? `<details class="prev-analisi" style="opacity:.72"><summary class="muted">Analisi precedente (tesi del ${esc(tesiUsataLabel(t))})</summary><div class="stack" style="margin-top:12px">${groupsBody}${fuori}</div></details>`
      : `${groupsBody}${fuori}`;
    return `${head}<div class="stack"><p style="font-size:16px;max-width:68ch">${stale || rs === 'running' ? 'I raggruppamenti per indicatore vanno ricalcolati sulla tesi aggiornata.' : lead}</p>${banner}${groups}</div>`;
  }

  /* Strip sopra la piega: stato → evidenze → fonte → da monitorare. */
  function summaryStripHTML(t, a, e, na, last, dec, rs, diff, dryRun) {
    const chipR = `<span class="chip na">${icon('alert')}Da ricalcolare</span>`;
    const chipRun = `<span class="chip na">${icon('eq')}Ricalcolo in corso…</span>`;
    let statoHTML;
    if (rs === 'running') statoHTML = chipRun;
    else if (rs === 'stale' || rs === 'error' || dryRun) statoHTML = chipR;
    else statoHTML = chipStato(statoDi(a));

    const inds = (e && e.indicatori) || [];
    const nFav = inds.filter(i => i.stato === 'a_favore').length;
    const nCon = inds.filter(i => i.stato === 'contro').length;
    const newsTouch = (na && na.touching) || 0;
    const earnImp = (a.earnings || []).filter(x => !x.mancante && x.impatto);
    const nRaff = earnImp.filter(x => x.impatto.effetto === 'rafforza').length;
    const nIndeb = earnImp.filter(x => x.impatto.effetto === 'indebolisce').length;
    const support = nFav + nRaff;
    const conflict = nCon + nIndeb;
    let evidenzeLine;
    if (!inds.length && !newsTouch && !earnImp.length) {
      evidenzeLine = 'Nessuna evidenza nuova';
    } else {
      const bits = [];
      if (support) bits.push(`${support} a favore`);
      if (conflict) bits.push(`${conflict} in conflitto`);
      if (newsTouch) bits.push(`${newsTouch} ${newsTouch === 1 ? 'notizia tocca' : 'notizie toccano'} la tesi`);
      evidenzeLine = bits.length ? bits.join(' · ') : 'Dati insufficienti';
    }

    let item = inds.find(i => i.stato === 'contro') || inds.find(i => i.stato === 'a_favore') || null;
    let itemText = item ? (item.testo || item.nome) : '';
    let itemKind = item ? 'esito' : null;
    if (!itemText && na && na.rel && na.rel.length) {
      const n0 = (na.groups || []).flatMap(g => g.items).concat(na.fuori || [])[0] || na.rel[0];
      if (n0) {
        itemText = n0.titolo || n0.riassunto || '';
        itemKind = 'news';
        item = n0;
      }
    }
    if (itemText && itemText.length > 110) itemText = itemText.slice(0, 107) + '…';

    let fonteHTML = '<span class="muted">Dati insufficienti</span>';
    if (itemKind === 'esito' && item && item.fonte && item.fonte.url) {
      const d = item.fonte.data ? ` · ${item.fonte.data}` : '';
      fonteHTML = `${prov('dataset', 'Articolo MF dal dataset')}<a class="fact-src" href="${esc(item.fonte.url)}" target="_blank" rel="noopener">Fonte: MF${esc(d)}</a>`;
    } else if (itemKind === 'news' && item && item.url) {
      const d = new Date(item.data + 'Z');
      const ds = `${d.getUTCDate()} ${MESI[d.getUTCMonth()]}`;
      fonteHTML = `${prov('dataset', 'Articolo MF dal dataset')}<a class="fact-src" href="${esc(item.url)}" target="_blank" rel="noopener">Fonte: MF · ${esc(ds)}</a>`;
    } else if (last && last.data) {
      fonteHTML = `${prov('dataset', 'Risultati dal dataset')}<span>Risultati · ${esc(last.data)}</span>`;
    } else if (itemKind === 'esito' && item && item.testo) {
      fonteHTML = `${prov('modello', 'Interpretazione del modello')}<span>Interpretazione del modello</span>`;
    }

    const thesisInds = (tesiDi(t).indicatori || []).map(s => String(s).trim()).filter(Boolean);
    const byNome = {};
    inds.forEach(i => { if (i && i.nome) byNome[i.nome] = i.stato; });
    const pending = thesisInds.find(nome => {
      const st = byNome[nome];
      return !st || st === 'non_citato' || st === 'neutro';
    });
    const nextEarn = (a.earnings || []).find(x => x.mancante);
    let monitorLine = 'Dati insufficienti';
    if (pending) monitorLine = pending;
    else if (dec && dec.cambierebbe) monitorLine = dec.cambierebbe;
    else if (nextEarn) monitorLine = `Prossimi risultati · ${nextEarn.label}`;
    else if (last) monitorLine = `Ultimi risultati · ${last.label}`;
    if (monitorLine.length > 110) monitorLine = monitorLine.slice(0, 107) + '…';

    const diffLine = (!dryRun && diff && (diff.status || diff.decisione || (diff.indicatori || []).length || diff.sintesi))
      ? `<p class="sum-diff"><span class="label">Cosa è cambiato</span> ${[
          diff.status ? `Stato: ${diff.status.da} → ${diff.status.a}` : '',
          diff.decisione ? `Decisione: ${diff.decisione.da} → ${diff.decisione.a}` : '',
          (diff.indicatori || []).length ? `${diff.indicatori.length} indicatori aggiornati` : '',
          diff.sintesi ? 'Sintesi aggiornata' : ''
        ].filter(Boolean).map(esc).join(' · ')}</p>`
      : '';
    const dryLine = dryRun
      ? `<p class="sum-diff warn">${esc('Server in modalità prova (--dry-run): l’analisi non è stata ricalcolata.')}</p>`
      : '';

    const step = (href, label, body) =>
      `<li class="sum-step"><a class="sum-link" href="${href}"><span class="eyebrow">${label}</span><div class="sum-body">${body}</div></a></li>`;

    return `<section class="card summary-strip" aria-label="Sintesi della tesi">
      <ol class="sum-chain">
        ${step('#cambia-card', 'Stato della tesi', statoHTML)}
        ${step('#news-analysis', 'Nuove evidenze', `<span>${esc(evidenzeLine)}</span>${itemText ? `<span class="sum-one muted">${esc(itemText)}</span>` : ''}`)}
        ${step(itemKind === 'news' ? '#news-analysis' : '#cambia-card', 'Fonte', `<span class="sum-fonte">${fonteHTML}</span>`)}
        ${step('#decisione-card', 'Da monitorare', `<span>${esc(monitorLine)}</span>`)}
      </ol>
      ${dryLine}${diffLine}
    </section>`;
  }

  function renderDetail(t) {
    const a = azienda(t);
    toolbar('detail');
    const isHeld = held(t), isWatched = watched(t);
    const pos = posizioni().rows.find(r => r.ticker === t);
    const T = tesiDi(t), stato = statoDi(a);
    const q = (a.earnings || []).filter(e => !e.mancante), last = q[q.length - 1], v = varDi(t);
    const sim = isSimAnalisi(a);
    const e = a.esito;
    const stale = tesiStale(t, a);
    const rs = statoRicalcolo(t);
    const dryRun = !!(ricalcoli[t] && ricalcoli[t].dryRun);
    const diff = dryRun ? null : ultimoRicalcolo(t);
    const na = newsAnalysis(t);
    const ctx = contesto(t), dec = decisioneDi(t);

    const reaz = last && last.reazione
      ? `<div class="react block"><span class="label">Reazione all’ultimo earnings · ${esc(last.label)}</span>
          <span class="big ${dirOf(last.reazione.pct)}">${signed(last.reazione.pct, 1)}</span>
          <span class="interval">${esc(cap(last.reazione.da))} ${icon('arrow')} ${esc(last.reazione.a)}</span>
          <span class="small muted">Chiusura precedente → chiusura successiva alla pubblicazione. ${esc(last.reazione.nota || '')}</span></div>`
      : `<div class="react block"><span class="label">Reazione all’ultimo earnings</span><span class="big muted">n.d.</span><span class="small muted">${sim ? 'Nessuna reazione disponibile nella demo.' : 'Prezzo non disponibile.'}</span></div>`;
    const strip = summaryStripHTML(t, a, e, na, last, dec, rs, diff, dryRun);
    const head = `<div class="dh">
        <div class="dh-title"><h1 tabindex="-1" id="ptitle">${esc(a.ticker)}</h1><span class="n">${esc(a.nome)}</span></div>
        <div class="dh-quote"><span class="p">${eur(a.prezzo, priceDigits(a.prezzo))}</span><span class="${dirOf(v)}" style="font-weight:500">${signed(v)}</span>${isPrezzoSim(a) && D.reale ? ` ${prov('esempio', 'Prezzo simulato')}` : D.reale ? ` ${prov('dataset', 'Prezzo da dataset MF')}` : ` ${prov('esempio', 'Prezzo demo')}`}<span class="muted">Chiusura del ${esc((D.reale && D.reale.prezzi_al) || D.aggiornamento)}</span></div>
        <div class="dh-meta tag">${[isHeld ? `In portafoglio · peso ${nf(pos ? pos.peso : 0, 1)}%` : isWatched ? 'In watchlist' : '', a.settore && a.settore !== '—' ? esc(a.settore) : ''].filter(Boolean).join(' · ')}</div>
      </div>
      ${fearGreedCompanyHTML(t)}
      ${strip}
      <section class="card"><div class="split">
        <div><div class="label" style="margin-bottom:6px">Ultimo anno · le linee verticali indicano la pubblicazione dei risultati</div><div class="chart" id="dchart"></div></div>
        <div class="stack">${reaz}<div class="remove-row" id="remove-row">${removeRow(t)}</div></div>
      </div></section>`;

    const tesi = `<section class="card" id="tesi-card">${ui.editing ? tesiForm(t) : tesiView(t, pos)}</section>`;

    const chipRicalc = `<span class="chip na lg">${icon('alert')}Da ricalcolare</span>`;
    const chipRun = `<span class="chip na lg">${icon('eq')}Ricalcolo in corso…</span>`;
    let cambiaBanner = '';
    if (rs === 'running') {
      cambiaBanner = `<div class="warnbox">${icon('alert')}<span>Ricalcolo in corso… l’analisi verrà aggiornata a breve.</span></div>`;
    } else if (rs === 'error') {
      const errMsg = (ricalcoli[t] && ricalcoli[t].error) || 'Ricalcolo non riuscito.';
      cambiaBanner = `<div class="warnbox">${icon('alert')}<span>${esc(errMsg)} Per rigenerare l’analisi avvia <code>make serve</code> e riprova. <button class="link" type="button" data-act="retry-ricalcolo">Riprova</button></span></div>`;
    } else if (dryRun) {
      cambiaBanner = `<div class="warnbox">${icon('alert')}<span>Server in modalità prova (--dry-run): l’analisi non è stata ricalcolata. Le conclusioni sotto restano quelle precedenti.</span></div>`;
    } else if (stale) {
      cambiaBanner = `<div class="warnbox">${icon('alert')}<span>Hai modificato la tesi: le conclusioni sotto non sono più attuali. Avvia <code>make serve</code> e salva di nuovo, oppure <button class="link" type="button" data-act="retry-ricalcolo">Riprova</button>.</span></div>`;
    }
    const diffBox = diff ? `<div class="block" id="cosa-cambiato" style="border:1px solid var(--line);border-radius:12px;padding:12px 14px">
        <h3 class="mini">Cosa è cambiato</h3>
        <ul class="bullets" style="margin:8px 0 0">
          ${diff.status ? `<li>Stato tesi: <strong>${esc(diff.status.da)}</strong> → <strong>${esc(diff.status.a)}</strong></li>` : ''}
          ${diff.decisione ? `<li>Decisione: <strong>${esc(diff.decisione.da)}</strong> → <strong>${esc(diff.decisione.a)}</strong></li>` : ''}
          ${(diff.indicatori || []).map(i => `<li>${esc(i.nome)}: <strong>${esc(i.da)}</strong> → <strong>${esc(i.a)}</strong></li>`).join('')}
          ${diff.sintesi ? '<li>Sintesi aggiornata</li>' : ''}
          ${!diff.status && !diff.decisione && !(diff.indicatori || []).length && !diff.sintesi ? '<li class="muted">Nessuna differenza nelle conclusioni (tesi allineata).</li>' : ''}
        </ul>
      </div>` : '';
    const interps = [...((e && e.interpretazioni) || [])];
    if (isHeld && pos && pos.peso >= 20) {
      interps.push(`Con un peso del ${nf(pos.peso, 1)}% il titolo concentra già una parte rilevante del portafoglio.`);
    }
    const interpH = e && e.metodo ? 'Interpretazioni del modello (non sono dati)' : 'Interpretazioni (non sono dati)';
    const noEsito = sim
      ? 'Non ci sono risultati trimestrali collegati a questa azienda nella demo: non è possibile confrontare la tesi con i dati.'
      : 'Non ci sono risultati trimestrali collegati a questa azienda: non è possibile confrontare la tesi con i dati.';
    const prevBody = e ? `
        <p style="font-size:16px;max-width:68ch">${esc(e.sintesi)}</p>
        ${(e.indicatori || []).length ? `<div class="block"><h3 class="mini">Indicatori della tua tesi</h3><ul class="ind-list">${e.indicatori.map(ind => indHTML(ind, false)).join('')}</ul></div>` : ''}
        ${((e.fatti && e.fatti.length) || interps.length) ? `<div class="split">
          ${e.fatti && e.fatti.length ? `<div class="block"><h3 class="mini">Fatti documentati nei risultati ${prov('dataset', 'Fatti da articoli/risultati MF')}</h3><ul class="facts">${e.fatti.map(f => `<li>${factHTML(f)}</li>`).join('')}</ul>
            <div class="srcnote">${srcNoteHTML(e.fatti, sim)}</div></div>` : ''}
          ${interps.length ? `<div class="block"><h3 class="mini">${interpH} ${prov('modello', 'Interpretazioni generate dal modello')}</h3><ul class="interps">${interps.map(f => `<li>${esc(f)}</li>`).join('')}</ul></div>` : ''}
        </div>` : ''}` : `<p style="font-size:16px;max-width:68ch">${esc(noEsito)}</p>`;
    const liveCambia = (stale || rs === 'running' || rs === 'error' || dryRun)
      ? `<div>${rs === 'running' ? chipRun : chipRicalc}</div>
        ${cambiaBanner}${diffBox}
        <details class="prev-analisi" style="opacity:.72"><summary class="muted">Analisi precedente (tesi del ${esc(tesiUsataLabel(t))})</summary>
          <div class="stack" style="margin-top:12px"><div>${chipStato(stato)}${e && e.metodo ? `<p class="note metodo">${esc(e.metodo)}</p>` : ''}</div>${prevBody}</div>
        </details>`
      : `<div>${chipStato(stato, true)}${e && e.metodo ? `<p class="note metodo">${esc(e.metodo)}</p>` : ''}</div>
        ${diffBox}${prevBody}`;
    const cambia = `<section class="card" id="cambia-card">
      <div class="card-h"><h2>Cosa cambia dopo gli ultimi risultati</h2>${last ? `<span class="muted">${esc(last.label)} · pubblicati il ${esc(last.data)}</span>` : ''}</div>
      <div class="stack">${liveCambia}</div>
    </section>`;

    const earn = `<section class="card" id="earn">${earningsHTML(t)}</section>`;
    const newsSec = `<section class="card" id="news-analysis">${newsAnalysisHTML(t, na, stale || dryRun, sim)}</section>`;

    let decHTML;
    const decPrev = () => {
      if (!dec) {
        const miss = a.mancano || (a.decisione ? [`Un’indicazione pensata per il nuovo contesto (${isHeld ? 'posizione detenuta' : 'watchlist'})`] : ['Risultati trimestrali collegati all’azienda', 'Una valutazione di riferimento', 'Indicatori da monitorare']);
        return `<div class="stack">
          <div class="dec-scale" aria-label="Possibili indicazioni">${Object.values(AZIONI[ctx]).map(l => `<span>${l}</span>`).join('')}</div>
          <div class="dec-main muted" style="font-size:22px">Dati insufficienti per valutare l’azione</div>
          <div class="block"><h3 class="mini">Cosa manca</h3><ul class="bullets">${miss.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div></div>`;
      }
      const considered = [
        `Tesi ${STATO[stato].label.toLowerCase()}`, `Orizzonte ${T.orizzonte}`,
        isHeld ? `Peso ${nf(pos.peso, 1)}%` : (T.pesoPrevisto ? `Peso previsto ${nf(T.pesoPrevisto, 1)}%` : 'Peso previsto non indicato'),
        a.valutazione, last && last.reazione ? `Reazione ai risultati ${signed(last.reazione.pct, 1)}` : null,
        na.rel.length ? `Notizie: ${na.touching} su ${na.rel.length} toccano la tesi` : 'Nessuna notizia recente'
      ].filter(Boolean);
      const usedNews = (dec.basata_su || []).includes('notizie');
      const decNote = usedNews
        ? `<p class="note">Indicazione generata dai risultati e da ${dec.notizie_considerate} ${dec.notizie_considerate === 1 ? 'notizia' : 'notizie'} MF${dec.notizie_da ? ` dal ${esc(dec.notizie_da)}` : ''}.</p>`
        : `<div class="warnbox">${icon('alert')}<span>Questa indicazione ${sim ? 'di esempio ' : ''}è stata scritta sui soli risultati: non tiene ancora conto delle notizie analizzate qui sopra.</span></div>`;
      return `<div class="split">
          <div class="stack">
            <div class="dec-scale" aria-label="Possibili indicazioni">${Object.entries(AZIONI[ctx]).map(([k, l]) => `<span class="${k === dec.azione ? 'on' : ''}"${k === dec.azione ? ' aria-current="true"' : ''}>${l}</span>`).join('')}</div>
            <div><div class="label">Indicazione principale ${prov('modello', 'Indicazione generata dal modello')}</div><div class="dec-main">${AZIONI[ctx][dec.azione]}</div></div>
            <p style="font-size:16px">${esc(dec.motivazione)}</p>
            ${decNote}
            <p class="disclaimer">Un’indicazione da valutare, non un ordine operativo né una previsione: nessuna probabilità di successo è stimata.</p>
          </div>
          <div class="block"><h3 class="mini">Elementi considerati</h3><p class="considered">${considered.map(esc).join(' · ')}</p></div>
        </div>
        <div class="dec-grid" style="margin-top:18px">
          <div class="block"><h3 class="mini">Elementi a favore</h3><ul class="bullets">${(dec.aFavore || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
          <div class="block"><h3 class="mini">Rischio principale</h3><p>${esc(dec.rischio)}</p></div>
          <div class="block"><h3 class="mini">Cosa cambierebbe la valutazione</h3><p>${esc(dec.cambierebbe)}</p></div>
        </div>`;
    };
    if (stale || rs === 'running' || rs === 'error' || dryRun) {
      decHTML = `<div class="stack">
        <div>${rs === 'running' ? chipRun : chipRicalc}</div>
        <div class="dec-main muted" style="font-size:22px">${rs === 'running' ? 'Ricalcolo in corso…' : 'Da ricalcolare'}</div>
        <p class="note">${dryRun ? 'Server in modalità prova (--dry-run): l’analisi non è stata ricalcolata.' : 'L’indicazione precedente non è più valida sulla tesi aggiornata.'}</p>
        <details class="prev-analisi" style="opacity:.72"><summary class="muted">Analisi precedente (tesi del ${esc(tesiUsataLabel(t))})</summary>
          <div style="margin-top:12px">${decPrev()}</div>
        </details>
      </div>`;
    } else {
      decHTML = decPrev();
    }
    const decisione = `<section class="card" id="decisione-card"><div class="card-h"><h2>Decisione da valutare</h2><span class="muted">${ctx === 'portafoglio' ? 'Posizione detenuta' : 'Azienda in watchlist'} · dopo tesi e notizie</span></div>${decHTML}</section>`;

    $('#app').innerHTML = `<div class="view detail">${head}${tesi}${cambia}${earn}${newsSec}${decisione}</div>`;

    const N = D.giorni.length, n = 252, s = serieDi(t).slice(N - n), dates = D.giorni.slice(N - n);
    const markers = q.map(e => { const pd = parseIt(e.data); if (!pd) return null; const i = dates.findIndex(d => d >= pd); return i >= 0 ? { i, label: e.label.replace(' 20', '') } : null; }).filter(Boolean);
    areaChart($('#dchart'), s, dates, { h: 150, markers, ring: 'var(--card)', fmt: v => eur(v, priceDigits(v)), label: `Prezzo di ${a.nome} nell’ultimo anno` });
  }

  function removeRow(t) {
    const where = held(t) ? 'dal portafoglio' : watched(t) ? 'dalla watchlist' : null;
    if (!where) return '';
    if (!ui.removing) return `<button class="link danger" type="button" data-act="remove">Rimuovi ${where}</button>`;
    return `<span>Rimuovere ${esc(t)} ${where}?</span><button class="link danger" type="button" data-act="remove-yes">Rimuovi</button><button class="link" type="button" data-act="remove-no">Annulla</button>`;
  }

  function tesiView(t, pos) {
    const a = azienda(t), T = tesiDi(t), isHeld = held(t), inds = (T.indicatori || []).filter(Boolean);
    const peso = isHeld
      ? `<div><dt>Peso attuale nel portafoglio</dt><dd>${nf(pos ? pos.peso : 0, 1)}%</dd></div>`
      : `<div><dt>Peso previsto (facoltativo)</dt><dd>${T.pesoPrevisto ? nf(T.pesoPrevisto, 1) + '%' : '<span class="muted" style="font-weight:400">Non indicato</span>'}</dd></div>`;
    const indNote = (a.esito && a.esito.indicatori)
      ? 'Indicatori di esempio, verificati sugli articoli MF qui sotto; puoi modificarli.'
      : 'Indicatori di esempio; puoi modificarli.';
    return `<div class="card-h"><h2>La tua tesi</h2><button class="btn secondary" type="button" data-act="edit" style="height:30px;padding:0 14px">Modifica tesi</button></div>
      <div class="split">
        <div class="stack">
          <div class="block"><h3 class="mini">Perché ${isHeld ? 'l’hai comprata' : 'ti interessa'}</h3><blockquote class="motivo">${esc(T.motivo)}</blockquote></div>
          <div class="block"><h3 class="mini">Indicatori da monitorare</h3>
            ${inds.length ? `<ol class="inds">${inds.map(x => `<li>${esc(x)}</li>`).join('')}</ol><p class="note">${indNote}</p>` : '<p class="note">Nessun indicatore: aggiungine fino a tre con “Modifica tesi”.</p>'}</div>
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
    const a = azienda(t), E = a.earnings || [], sim = isSimAnalisi(a);
    if (!E.length) return `<div class="card-h"><h2>Ultimi quattro earnings</h2></div><p class="note">Nessun risultato trimestrale disponibile${sim ? ' nella demo' : ''} per questa azienda.</p>`;
    const sel = ui.quarter[t] ?? E.length - 1;
    const effCls = e => (e.mancante ? 'na' : EFFETTO[e.impatto.effetto].cls);
    const evo = `<div class="evo">${E.map(e => `<div class="evo-step ${effCls(e)}"><span class="lbl">${esc(e.label)}</span>${e.mancante ? '<span class="chip na">Non disponibile</span>' : `<span class="chip ${EFFETTO[e.impatto.effetto].cls}">${icon(EFFETTO[e.impatto.effetto].ic)}${EFFETTO[e.impatto.effetto].label}</span>`}</div>`).join('')}</div>
      <p class="muted" style="max-width:75ch">${esc(a.evoluzione || '')}</p>`;
    const tabs = `<div class="qtabs"><div class="seg" role="tablist" aria-label="Trimestri">${E.map((e, i) => `<button class="qtab" role="tab" type="button" id="qt-${i}" aria-controls="qp" aria-selected="${i === sel}" aria-pressed="${i === sel}" tabindex="${i === sel ? 0 : -1}" data-q="${i}">
        <span class="l"><i class="sdot ${effCls(e)}" aria-hidden="true"></i>${esc(e.label)}</span><span class="d">${e.mancante ? 'non disponibile' : esc(e.data)}</span></button>`).join('')}</div></div>`;
    const e = E[sel];
    let panel;
    if (e.mancante) panel = `<p class="note">Dati di questo trimestre non disponibili${sim ? ' nella demo' : ''}.</p>`;
    else {
      const base = b => (b === 'a/a' ? 'anno su anno' : b === 't/t' ? 'trimestre su trimestre' : '');
      const mets = e.metriche || [];
      const metrics = mets.length
        ? mets.map(m => m.valore == null
          ? `<div class="metric na"><span class="n">${esc(m.nome)}</span><span class="v">n.d.</span><span class="c">${esc(m.nota || 'Non disponibile')}</span></div>`
          : `<div class="metric"><span class="n">${esc(m.nome)}</span><span class="v">${esc(m.valore)}</span><span class="c"><b>${esc(m.confronto)}</b> ${base(m.base)}${m.nota ? ` · ${esc(m.nota)}` : ''}</span></div>`).join('')
        : '';
      const metricsBlock = mets.length
        ? `<div class="metrics">${metrics}</div>`
        : `<p class="note">Nessun numero riportato negli articoli per questo trimestre.</p>`;
      const guidance = e.guidance == null
        ? (sim ? 'Non disponibile nella demo.' : 'Non indicata negli articoli.')
        : e.guidance;
      const reazioneHTML = e.reazione
        ? `<div class="reaction"><span class="num ${dirOf(e.reazione.pct)}">${signed(e.reazione.pct, 1)}</span><span class="interval">${esc(cap(e.reazione.da))} ${icon('arrow')} ${esc(e.reazione.a)}</span></div><p class="small muted">${esc(e.reazione.nota || '')}</p>`
        : `<p class="note">${sim ? 'Non disponibile nella demo.' : 'Prezzo non disponibile.'}</p>`;
      const fontiNote = e.fonti && e.fonti.length
        ? e.fonti.map(f => `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.titolo)}</a>`).join(' · ')
        : (sim ? 'Fonte non disponibile nella demo' : 'Fonte non disponibile');
      const imp = EFFETTO[e.impatto.effetto];
      panel = `<div class="qpanel">
        <div class="stack">
          <div class="block"><h3 class="mini">Tre fatti essenziali</h3><ul class="facts">${(e.fatti || []).map(f => `<li>${factHTML(f)}</li>`).join('')}</ul></div>
          <div class="block"><h3 class="mini">Indicazioni del management</h3><p>${esc(guidance)}</p></div>
          <div class="block"><h3 class="mini">Cosa è cambiato dal trimestre precedente</h3><p>${esc(e.cambiato)}</p></div>
          <div class="block"><h3 class="mini">Impatto sulla tua tesi</h3><div><span class="chip ${imp.cls}">${icon(imp.ic)}${imp.label}</span></div><p>${esc(e.impatto.testo)}</p></div>
        </div>
        <div class="stack">
          <div class="block"><h3 class="mini">Numeri · ${esc(e.periodo)}</h3>${metricsBlock}</div>
          <div class="block"><h3 class="mini">Reazione del prezzo</h3>${reazioneHTML}</div>
          <div class="srcnote">${icon('doc')}${fontiNote}</div>
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
    ui.sideTab = kind === 'pos' ? 'portafoglio' : 'watchlist'; savePref();
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
    save();
    ui.editing = false;
    ricalcoli[t] = { status: 'idle', diff: ricalcoli[t] && ricalcoli[t].diff };
    renderAll();
    toast('Tesi salvata');
    avviaRicalcolo(t);
  }

  async function apiStatus() {
    if (location.protocol === 'file:') return null;
    try {
      const r = await fetch('/api/status', { cache: 'no-store' });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }

  function mergeAzienda(t, payload) {
    if (!payload || typeof payload !== 'object') return;
    if (!D.aziende[t]) return;
    Object.assign(D.aziende[t], payload);
    if (state.aziende[t]) Object.assign(state.aziende[t], payload);
  }

  function sleep(ms) { return new Promise(res => setTimeout(res, ms)); }

  async function pollJob(t, tries = 120) {
    for (let i = 0; i < tries; i++) {
      const r = await fetch(`/api/tesi/${encodeURIComponent(t)}/job`, { cache: 'no-store' });
      const j = await r.json();
      if (j.status === 'running' || j.status === 'idle') {
        await sleep(1000);
        continue;
      }
      return j;
    }
    return { status: 'error', ok: false, error: 'Timeout in attesa del ricalcolo.' };
  }

  async function avviaRicalcolo(t) {
    const T = tesiDi(t);
    const body = {
      orizzonte: T.orizzonte || '',
      motivo: T.motivo || '',
      indicatori: T.indicatori || [],
      pesoPrevisto: T.pesoPrevisto == null ? null : T.pesoPrevisto
    };
    const st = await apiStatus();
    if (!st || !st.ok) {
      ricalcoli[t] = {
        status: 'error',
        error: 'Server non raggiungibile. Avvia `make serve` (http://localhost:8000) e riprova.',
        diff: ricalcoli[t] && ricalcoli[t].diff
      };
      if (currentTicker() === t) renderAll();
      return;
    }
    ricalcoli[t] = { status: 'running', diff: null, dryRun: false };
    if (currentTicker() === t) renderAll();
    try {
      const res = await fetch(`/api/tesi/${encodeURIComponent(t)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const queued = await res.json().catch(() => ({}));
      if (!res.ok && res.status !== 202) {
        throw new Error((queued && queued.error) || `Errore HTTP ${res.status}`);
      }
      const job = await pollJob(t);
      if (job.status === 'error' || job.ok === false) {
        throw new Error((job && job.error) || 'Ricalcolo fallito.');
      }
      if (job.dry_run) {
        /* Non unire azienda/tesi_usata: le conclusioni restano vecchie; lo stato resta stale. */
        ricalcoli[t] = { status: 'idle', dryRun: true, diff: null };
        toast('Modalità prova: analisi non ricalcolata');
        if (currentTicker() === t) renderAll();
        return;
      }
      if (job.azienda) mergeAzienda(t, job.azienda);
      const ctx = contesto(t);
      const diff = diffRicalcolo(job.before, job.after, ctx);
      const a = azienda(t);
      if (a) {
        a.tesi_usata = {
          motivo: body.motivo,
          indicatori: body.indicatori.slice(),
          orizzonte: body.orizzonte,
          pesoPrevisto: body.pesoPrevisto
        };
      }
      ricalcoli[t] = { status: 'done', diff, dryRun: false };
      toast('Analisi aggiornata');
      if (currentTicker() === t) renderAll();
    } catch (e) {
      ricalcoli[t] = {
        status: 'error',
        error: (e && e.message) || 'Ricalcolo non riuscito. Avvia `make serve` e riprova.',
        diff: ricalcoli[t] && ricalcoli[t].diff
      };
      if (currentTicker() === t) renderAll();
    }
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
    applySide();
  }
  function renderAll() {
    ui.current = currentTicker();
    charts.clear();
    syncFooter();
    renderLeft(); renderMain();
  }
  function route() {
    hideNotif();
    ui.editing = false; ui.removing = false;
    ui.current = currentTicker();
    const c = ui.current;
    if (c && ((ui.sideTab === 'portafoglio' && !held(c) && watched(c)) || (ui.sideTab === 'watchlist' && !watched(c) && held(c)))) {
      ui.sideTab = held(c) ? 'portafoglio' : 'watchlist'; savePref(); renderLeft();
    }
    // aggiorna solo la selezione nella barra laterale, senza ridisegnarla
    $$('.sym').forEach(b => { if (b.dataset.open === ui.current) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
    renderMain();
    window.scrollTo(0, 0);
    const target = ui.scrollTo && document.getElementById(ui.scrollTo);
    ui.scrollTo = null;
    if (target) {
      target.scrollIntoView({ block: 'start' }); window.scrollBy(0, -64);
      target.classList.remove('flash'); void target.offsetWidth; target.classList.add('flash');
      const h = target.querySelector('h2'); if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
    } else { const title = $('#ptitle'); if (title) title.focus({ preventScroll: true }); }
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
    const go = ev.target.closest('[data-goto]');
    if (go) { ui.scrollTo = go.dataset.goto; closePreview(); openCompany(go.dataset.t); return; }
    const slice = ev.target.closest('.ipie [data-i]');
    if (slice) {
      const kind = slice.dataset.k, i = +slice.dataset.i, x = HOME[kind][i];
      if (kind === 'titoli') { if (x && x.open) openCompany(x.open); return; }
      HOME.pin = HOME.pin === i ? null : i;
      const w = slice.closest('.ipie'); w.dataset.state = ''; setActive(w, null);
      return;
    }
    const tab = ev.target.closest('[data-side-tab]');
    if (tab) { ui.sideTab = tab.dataset.sideTab; savePref(); renderLeft(); $(`[data-side-tab="${ui.sideTab}"]`).focus(); return; }
    const el = ev.target.closest('[data-open],[data-act],[data-range],[data-scope],[data-filter],[data-q],[data-fg]');
    if (!el) return;
    if (el.dataset.fg) {
      ui.fg = el.dataset.fg;
      const y = scrollY;
      renderMain();
      scrollTo(0, y);
      return;
    }
    if (el.dataset.open) { openCompany(el.dataset.open); return; }
    if (el.dataset.range) { ui.range = el.dataset.range; drawPortfolioChart(); return; }
    if (el.dataset.scope) { ui.scope = el.dataset.scope; ui.ticker = null; renderMain(); return; }
    if (el.dataset.filter) { ui.ticker = ui.ticker === el.dataset.filter ? null : el.dataset.filter; renderMain(); return; }
    const t = currentTicker();
    if (el.dataset.q) { ui.quarter[t] = +el.dataset.q; $('#earn').innerHTML = earningsHTML(t); $(`#qt-${el.dataset.q}`).focus(); return; }
    switch (el.dataset.act) {
      case 'add-pos': openDialog('pos'); break;
      case 'more-news': { ui.allNews[t] = true; const y = scrollY; renderDetail(t); scrollTo(0, y); break; }
      case 'toggle-side': ui.sideOpen = !ui.sideOpen; savePref(); applySide(); break;
      case 'add-watch': openDialog('watch'); break;
      case 'dlg-close': closeDialog(); break;
      case 'clear-filter': ui.ticker = null; renderMain(); break;
      case 'clear-q': ui.q = ''; $('#q').value = ''; renderMain(); break;
      case 'all-news': ui.scope = 'tutte'; ui.ticker = null; ui.q = ''; $('#q').value = ''; renderMain(); break;
      case 'back': location.hash = ui.lastMain; break;
      case 'edit': ui.editing = true; $('#tesi-card').innerHTML = tesiForm(t); $('#f-motivo').focus(); break;
      case 'edit-cancel': ui.editing = false; $('#tesi-card').innerHTML = tesiView(t, posizioni().rows.find(r => r.ticker === t)); break;
      case 'retry-ricalcolo': if (t) avviaRicalcolo(t); break;
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
  const leftMax = () => Math.max(LEFT_MIN, Math.min(720, window.innerWidth - 440));
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
  /* Anteprima della tesi in stile notifiche, solo sulla torta per titolo: tesi in breve, ultimi risultati,
     e come si è mosso il prezzo rispetto alla tesi. Primo ingresso con un breve ritardo; tra spicchi si aggiorna subito. */
  const notif = document.createElement('div');
  notif.className = 'notif'; notif.id = 'pie-notif'; notif.setAttribute('role', 'tooltip'); notif.hidden = true;
  document.body.appendChild(notif);
  let notifT, notifKey = null;

  /* Ultimi risultati disponibili e variazione del prezzo dalla chiusura precedente la pubblicazione a oggi. */
  function sinceEarnings(t) {
    const q = (azienda(t).earnings || []).filter(e => !e.mancante), e = q[q.length - 1];
    if (!e) return null;
    const pd = parseIt(e.data), s0 = serieDi(t), i = pd ? D.giorni.findIndex(d => d >= pd) : -1;
    return { e, pct: i < 0 ? null : (s0[s0.length - 1] / s0[Math.max(0, i - 1)] - 1) * 100 };
  }
  /* Lettura (interpretazione, non dato): il prezzo dopo i risultati va nella direzione della tesi? */
  function priceVsThesis(stato, pct) {
    if (stato === 'insufficiente' || pct == null) return 'Dati insufficienti per confrontare prezzo e tesi.';
    const up = pct > 0.5, down = pct < -0.5;
    if (stato === 'rafforzata') return up ? 'Il prezzo va nella direzione della tesi.' : down ? 'Il prezzo non riflette ancora il rafforzamento della tesi.' : 'Prezzo quasi fermo nonostante la tesi più forte.';
    if (stato === 'indebolita') return down ? 'Il prezzo conferma l’indebolimento della tesi.' : up ? 'Il prezzo sale nonostante la tesi più debole.' : 'Prezzo quasi fermo con una tesi più debole.';
    return up ? 'Tesi invariata; il prezzo è salito dai risultati.' : down ? 'Tesi invariata; il prezzo è sceso dai risultati.' : 'Tesi e prezzo sostanzialmente fermi.';
  }
  /* Settore: le ultime notizie MF sui suoi titoli, in stile notifiche. */
  function sectorNewsHTML(x) {
    const tickers = x.members.map(m => m.ticker);
    const list = D.notizie.filter(n => linked(n).some(s0 => tickers.includes(s0.ticker))).sort((a, b) => b.data.localeCompare(a.data));
    const cards = list.slice(0, 3).map(n => {
      const d = new Date(n.data + 'Z'), s0 = linked(n).find(y => tickers.includes(y.ticker)), vd = n.verdetto;
      const dir = s0 ? s0.dir : n.segnale && n.segnale.dir;
      const tag = vd ? `<span class="chip ${vd.cls}">${esc(vd.label)}</span>`
        : n.segnale ? `<span class="chip ${dir === 'up' ? 'pos' : dir === 'down' ? 'neg' : 'neu'}">${trend(dir)}${DIR_LABEL[dir]}</span>` : '';
      return `<li class="nt-card"><div class="nt-meta"><span class="nt-app" aria-hidden="true">MF</span><span>${s0 ? `<b>${esc(s0.ticker)}</b> · ` : ''}${d.getUTCDate()} ${MESI[d.getUTCMonth()]}</span>${tag}</div><p>${esc(n.titolo)}</p></li>`;
    }).join('');
    return `<div class="nt-head"><b>${esc(x.n)}</b><span>${list.length ? `${list.length} ${list.length === 1 ? 'notizia' : 'notizie'}` : 'Nessuna notizia'}</span></div>
      ${cards ? `<ul>${cards}</ul>` : '<p class="nt-empty">Nessun articolo MF collegato di recente.</p>'}
      <div class="nt-foot">Clic per vedere i titoli del settore</div>`;
  }
  function notifHTML(x) {
    const t = x.open, a = azienda(t), T = tesiDi(t), stato = statoDi(a), se = sinceEarnings(t);
    const tesi = (state.tesi[t] && state.tesi[t].motivo) || T.motivoBreve || T.motivo || 'Nessuna tesi scritta.';
    const eff = se && EFFETTO[se.e.impatto.effetto];
    return `<div class="nt-head"><b>${esc(x.n)} <span>${esc(x.full)}</span></b>${chipStato(stato)}</div>
      <div class="nt-card"><div class="nt-rows">
        <button class="nt-link" type="button" data-goto="tesi-card" data-t="${esc(t)}" aria-label="Apri la tua tesi su ${esc(x.full)}"><span class="nt-k">Tesi</span><span class="nt-v nt-clamp">${esc(tesi)}</span>${icon('chev')}</button>
        <button class="nt-link" type="button" data-goto="earn" data-t="${esc(t)}" aria-label="Apri gli ultimi risultati di ${esc(x.full)}"><span class="nt-k">Risultati</span><span class="nt-v">${eff ? `<span class="chip ${eff.cls}">${icon(eff.ic)}${eff.label}</span> <span class="muted">· ${esc(se.e.label)}</span>` : '<span class="muted">Non disponibili</span>'}</span>${icon('chev')}</button>
        <div class="nt-row"><span class="nt-k">Prezzo</span><span class="nt-v">${se && se.pct != null ? `<b class="${dirOf(se.pct)}">${signed(se.pct, 1)}</b> dai risultati` : '<span class="muted">n.d.</span>'}</span></div>
      </div>
      <p class="nt-read">${priceVsThesis(stato, se && se.pct)}</p></div>`;
  }
  /* Accanto al bordo esterno dello spicchio, verso l'esterno; dentro la finestra; cresce dal lato dello spicchio. */
  function placeNotif(slice) {
    const box = slice.ownerSVGElement.getBoundingClientRect();
    const R = box.width / 2, cx = box.left + R, cy = box.top + box.height / 2;
    const ux = parseFloat(slice.style.getPropertyValue('--dx')) / 8 || 0, uy = parseFloat(slice.style.getPropertyValue('--dy')) / 8 || 0;
    const ox = cx + ux * R * 0.9, oy = cy + uy * R * 0.9, w = notif.offsetWidth, h = notif.offsetHeight, gap = 16;
    const right = ux >= 0;
    let x = right ? ox + gap : ox - w - gap;
    if (x + w > innerWidth - 8 || x < 8) x = right ? ox - w - gap : ox + gap;
    x = Math.max(8, Math.min(innerWidth - w - 8, x));
    const y = Math.max(60, Math.min(innerHeight - h - 8, oy - h / 2));
    notif.style.left = x + 'px'; notif.style.top = y + 'px';
    notif.style.transformOrigin = `${x > ox ? 'left' : 'right'} ${Math.max(0, Math.min(h, oy - y))}px`;
  }
  function showNotif(hit) {
    const w = hit.closest('.ipie'), kind = w.dataset.kind, i = +hit.dataset.i, x = HOME[kind][i];
    if (!x || (kind === 'titoli' && !x.open)) return hideNotif();
    const key = kind + i, slice = w.querySelector(`.slice[data-i="${i}"]`);
    const render = () => {
      notif.innerHTML = kind === 'titoli' ? notifHTML(x) : sectorNewsHTML(x); placeNotif(slice); notifKey = key;
      $$('[aria-describedby="pie-notif"]').forEach(e => e.removeAttribute('aria-describedby'));
      hit.setAttribute('aria-describedby', 'pie-notif');
    };
    clearTimeout(notifT);
    if (!notif.hidden) {
      if (notifKey !== key) { notif.classList.add('instant'); render(); requestAnimationFrame(() => notif.classList.remove('instant')); }
      return;
    }
    notifT = setTimeout(() => { render(); notif.hidden = false; }, 140);
  }
  function hideNotif() { clearTimeout(notifT); notifKey = null; notif.hidden = true; }

  let hideT;
  const closePreview = () => { clearTimeout(hideT); hideNotif(); $$('.ipie').forEach(w => setActive(w, null)); };
  const pieHover = (target, preview) => {
    if (target && target.closest && target.closest('#pie-notif')) { clearTimeout(hideT); return; }
    const hit = target && target.closest && target.closest('.ipie [data-i]');
    if (hit) {
      clearTimeout(hideT);
      $$('.ipie').forEach(w => setActive(w, w.contains(hit) ? +hit.dataset.i : null));
      if (preview) showNotif(hit); else hideNotif();
      return;
    }
    if (!notif.hidden) { clearTimeout(hideT); hideT = setTimeout(closePreview, 260); return; }
    closePreview();
  };
  document.addEventListener('pointerover', ev => pieHover(ev.target, ev.pointerType !== 'touch'));
  document.addEventListener('focusin', ev => pieHover(ev.target, true));
  document.documentElement.addEventListener('pointerleave', () => pieHover(null));
  window.addEventListener('scroll', closePreview, { passive: true });
  notif.addEventListener('pointerleave', () => { clearTimeout(hideT); hideT = setTimeout(closePreview, 260); });
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
