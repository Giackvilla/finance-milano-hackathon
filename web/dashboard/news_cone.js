/**
 * Mini forecast cones next to each stock block on #notizie.
 * News → Monte Carlo fan → keep Q2+Q3 → white realized path.
 * No legend; palette follows the desk theme.
 */
(function (global) {
  "use strict";

  const HORIZON = 10;
  const PATHS = 36;
  const PAD = { t: 10, r: 8, b: 16, l: 36 };

  function mulberry32(a) {
    return () => {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function randn(rng) {
    const u = Math.max(1e-12, rng());
    const v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function dayISO(d) {
    if (d instanceof Date) return d.toISOString().slice(0, 10);
    return String(d).slice(0, 10);
  }

  function theme(el) {
    const cs = getComputedStyle(el);
    const ink = cs.getPropertyValue("--ink").trim() || "#1d1d1f";
    const ink2 = cs.getPropertyValue("--ink-2").trim() || "#6e6e73";
    const sep = cs.getPropertyValue("--sep").trim() || "rgba(0,0,0,.09)";
    const up = cs.getPropertyValue("--up").trim() || "#1f8a3b";
    const warn = cs.getPropertyValue("--warn").trim() || "#b25000";
    return {
      hist: ink,
      label: ink2,
      grid: sep,
      news: warn,
      cone: up,
      coneFill: colorAlpha(up, 0.14),
      coneFillOuter: colorAlpha(up, 0.05),
      coneFillIqr: colorAlpha(up, 0.26),
      path: colorAlpha(up, 0.2),
      pathIqr: colorAlpha(up, 0.4),
      median: colorAlpha(up, 0.7),
    };
  }

  function colorAlpha(cssColor, a) {
    const c = document.createElement("canvas").getContext("2d");
    c.fillStyle = cssColor;
    const m = String(c.fillStyle).match(/^#([0-9a-f]{6})$/i);
    if (m) {
      const n = parseInt(m[1], 16);
      return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
    }
    if (cssColor.startsWith("rgb(")) return cssColor.replace("rgb(", "rgba(").replace(")", `,${a})`);
    if (cssColor.startsWith("rgba(")) return cssColor.replace(/,\s*[\d.]+\)$/, `,${a})`);
    return cssColor;
  }

  function priorFromNews(n) {
    const vd = n.verdetto;
    if (vd && vd.move_pct != null) {
      const z = Math.min(4, Math.abs(vd.z || 1));
      const dir = Math.sign(vd.move_pct) || 1;
      return {
        mu: dir * 0.00055 * z,
        sigma: 0.006 + 0.0018 * z,
      };
    }
    const g = n.segnale;
    if (g) {
      const dir = g.dir === "down" ? -1 : g.dir === "up" ? 1 : 0;
      const f = g.forza != null ? g.forza : 0.4;
      return { mu: dir * 0.0007 * f, sigma: 0.0065 + 0.006 * f };
    }
    return { mu: 0, sigma: 0.009 };
  }

  function simulatePaths(p0, horizon, mu, sigma, count, seed) {
    const rng = mulberry32(seed);
    const paths = [];
    for (let p = 0; p < count; p++) {
      const series = [p0];
      for (let t = 1; t <= horizon; t++) series.push(series[t - 1] * Math.exp(mu + sigma * randn(rng)));
      paths.push(series);
    }
    return paths;
  }

  function percentileBands(paths) {
    const horizon = paths[0].length - 1;
    const qs = [0.1, 0.25, 0.5, 0.75, 0.9];
    const bands = qs.map(() => new Array(horizon + 1));
    for (let t = 0; t <= horizon; t++) {
      const col = paths.map((p) => p[t]).sort((a, b) => a - b);
      qs.forEach((q, qi) => {
        bands[qi][t] = col[Math.min(col.length - 1, Math.floor(q * (col.length - 1)))];
      });
    }
    return { p10: bands[0], p25: bands[1], p50: bands[2], p75: bands[3], p90: bands[4] };
  }

  function dayIndex(dates, iso) {
    const want = dayISO(iso);
    let i = dates.findIndex((d) => dayISO(d) >= want);
    if (i < 0) i = dates.length - 1;
    return i;
  }

  function buildModel(ticker, prices, dates, newsItems) {
    if (!prices || !dates || prices.length < 5) return null;
    const n = Math.min(prices.length, dates.length);
    const events = [];
    const seen = new Set();
    const sorted = newsItems.slice().sort((a, b) => a.data.localeCompare(b.data));
    for (const news of sorted) {
      const i = dayIndex(dates, news.data);
      if (i < 8 || i >= n - 2) continue;
      const key = dayISO(dates[i]);
      if (seen.has(key)) continue;
      seen.add(key);
      const { mu, sigma } = priorFromNews(news);
      const seed = (ticker.charCodeAt(0) * 997 + i * 131 + seen.size * 17) | 0;
      const paths = simulatePaths(prices[i], HORIZON, mu, sigma, PATHS, seed >>> 0);
      const bands = percentileBands(paths);
      const end = HORIZON;
      const classes = paths.map((series) => {
        const p = series[end];
        if (p < bands.p10[end] || p > bands.p90[end]) return "outlier";
        if (p < bands.p25[end] || p > bands.p75[end]) return "outer";
        return "iqr";
      });
      events.push({ i, news, paths, bands, classes });
      if (events.length >= 3) break;
    }
    if (!events.length) return null;

    const first = Math.max(0, events[0].i - 16);
    const last = Math.min(n - 1, events[events.length - 1].i + HORIZON + 4);
    return {
      ticker,
      prices,
      dates,
      events,
      i0: first,
      i1: last,
    };
  }

  function priceAt(prices, t) {
    if (t <= 0) return prices[0];
    if (t >= prices.length - 1) return prices[prices.length - 1];
    const i = Math.floor(t);
    return lerp(prices[i], prices[i + 1], t - i);
  }

  function mountCanvas(canvas, model, opts = {}) {
    if (!canvas || !model) return null;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const state = {
      reveal: model.i0,
      events: model.events.map(() => ({ pathT: 0, focus: 0, visible: false })),
      phase: reduced ? "done" : "draw-hist",
      cursor: -1,
      playing: !reduced,
      raf: 0,
      lastTs: 0,
      dead: false,
    };
    if (reduced) {
      state.reveal = model.i1;
      state.events.forEach((e) => {
        e.visible = true;
        e.pathT = 1;
        e.focus = 1;
      });
    }

    const draw = () => paint(canvas, model, state);
    const tick = (ts) => {
      if (state.dead || !state.playing) return;
      if (!state.lastTs) state.lastTs = ts;
      const dt = Math.min(0.032, (ts - state.lastTs) / 1000);
      state.lastTs = ts;
      step(model, state, dt);
      draw();
      if (state.playing) state.raf = requestAnimationFrame(tick);
    };

    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas);
    draw();
    const delay = opts.delay || 0;
    const start = () => {
      if (state.dead || reduced) return;
      state.playing = true;
      state.lastTs = 0;
      state.raf = requestAnimationFrame(tick);
    };
    const timer = setTimeout(start, delay);

    return () => {
      state.dead = true;
      state.playing = false;
      clearTimeout(timer);
      cancelAnimationFrame(state.raf);
      ro.disconnect();
    };
  }

  function step(model, state, dt) {
    const { events, i0, i1 } = model;
    if (state.phase === "draw-hist") {
      const next = events.find((e, i) => e.i > state.reveal && !state.events[i].visible);
      const target = next ? next.i : i1;
      state.reveal = Math.min(target, state.reveal + dt * 3.2);
      if (state.reveal >= target - 0.001) {
        state.reveal = target;
        if (next) {
          const idx = events.indexOf(next);
          state.events[idx].visible = true;
          state.events[idx].pathT = 0;
          state.events[idx].focus = 0;
          state.cursor = idx;
          state.phase = "cone";
        } else {
          state.phase = "done";
          state.playing = false;
        }
      }
    } else if (state.phase === "cone") {
      const st = state.events[state.cursor];
      st.pathT = Math.min(1, st.pathT + dt * 0.175);
      if (st.pathT >= 1) state.phase = "focus-iqr";
    } else if (state.phase === "focus-iqr") {
      const st = state.events[state.cursor];
      st.focus = Math.min(1, st.focus + dt * 0.55);
      if (st.focus >= 1) state.phase = "reveal-true";
    } else if (state.phase === "reveal-true") {
      const ev = events[state.cursor];
      const target = Math.min(i1, ev.i + HORIZON);
      state.reveal = Math.min(target, state.reveal + dt * 2.6);
      if (state.reveal >= target - 0.001) {
        state.reveal = target;
        const more = events.some((e, i) => e.i > state.reveal && !state.events[i].visible);
        state.phase = more || state.reveal < i1 ? "draw-hist" : "done";
        if (state.phase === "done") state.playing = false;
      }
    }
  }

  function paint(canvas, model, state) {
    const dpr = Math.min(2, devicePixelRatio || 1);
    const cssW = canvas.clientWidth || 320;
    const cssH = canvas.clientHeight || 140;
    if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    const C = theme(canvas);
    const { prices, dates, events, i0, i1 } = model;
    const r = Math.min(Math.max(state.reveal, i0), i1);

    let lo = Infinity, hi = -Infinity;
    const maxI = Math.min(i1, Math.ceil(r));
    for (let i = i0; i <= maxI; i++) {
      lo = Math.min(lo, prices[i]);
      hi = Math.max(hi, prices[i]);
    }
    events.forEach((ev, ei) => {
      const st = state.events[ei];
      if (!st.visible) return;
      const b = ev.bands;
      for (let t = 0; t < b.p10.length; t++) {
        lo = Math.min(lo, b.p10[t]);
        hi = Math.max(hi, b.p90[t]);
      }
    });
    const pad = (hi - lo) * 0.14 || 0.05;
    lo -= pad;
    hi += pad;

    const x0 = PAD.l, x1 = cssW - PAD.r, y0 = PAD.t, y1 = cssH - PAD.b;
    const span = Math.max(1, i1 - i0);
    const x = (i) => x0 + ((i - i0) / span) * (x1 - x0);
    const y = (p) => y1 - ((p - lo) / (hi - lo)) * (y1 - y0);

    // grid / axes
    ctx.strokeStyle = C.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x0, y1);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.fillStyle = C.label;
    ctx.font = "10px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let k = 0; k < 3; k++) {
      const p = lo + ((hi - lo) * k) / 2;
      const yy = y(p);
      ctx.strokeStyle = C.grid;
      ctx.beginPath();
      ctx.moveTo(x0, yy);
      ctx.lineTo(x1, yy);
      ctx.stroke();
      ctx.fillStyle = C.label;
      ctx.fillText(p < 10 ? p.toFixed(2) : p.toFixed(1), x0 - 4, yy);
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    [i0, Math.round((i0 + i1) / 2), i1].forEach((i) => {
      const d = dayISO(dates[i]);
      const [, m, day] = d.split("-");
      ctx.fillText(`${Number(day)}/${Number(m)}`, x(i), y1 + 3);
    });

    // cones
    events.forEach((ev, ei) => {
      const st = state.events[ei];
      if (!st.visible || st.pathT <= 0) return;
      const tMax = st.pathT * HORIZON;
      const focus = st.focus || 0;
      const outerA = 1 - focus;
      const iqrBoost = 0.55 + 0.45 * focus;
      const b = ev.bands;

      ctx.save();
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      if (outerA > 0.02) {
        ctx.globalAlpha = outerA;
        fillBand(ctx, x, y, ev.i, b.p10, b.p90, tMax, C.coneFillOuter);
      }
      ctx.globalAlpha = iqrBoost;
      fillBand(ctx, x, y, ev.i, b.p25, b.p75, tMax, focus > 0.2 ? C.coneFillIqr : C.coneFill);

      const show = Math.min(ev.paths.length, st.pathT < 1 ? 28 : ev.paths.length);
      if (outerA > 0.02) {
        ctx.globalAlpha = outerA * 0.85;
        ctx.strokeStyle = C.path;
        ctx.lineWidth = 1;
        for (let p = 0; p < show; p++) {
          if (ev.classes[p] === "iqr") continue;
          strokeSeries(ctx, x, y, ev.i, ev.paths[p], tMax);
        }
      }
      ctx.globalAlpha = iqrBoost;
      ctx.strokeStyle = focus > 0.4 ? C.pathIqr : C.path;
      ctx.lineWidth = focus > 0.5 ? 1.25 : 1;
      for (let p = 0; p < show; p++) {
        if (ev.classes[p] !== "iqr") continue;
        strokeSeries(ctx, x, y, ev.i, ev.paths[p], tMax);
      }
      ctx.globalAlpha = 1;
      ctx.strokeStyle = C.median;
      ctx.lineWidth = focus > 0.5 ? 1.6 : 1.2;
      ctx.setLineDash([3, 3]);
      strokeSeries(ctx, x, y, ev.i, b.p50, tMax);
      ctx.setLineDash([]);
      ctx.restore();
    });

    // history + white outcome through cones
    if (r >= i0) {
      const iFull = Math.floor(r);
      ctx.save();
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.strokeStyle = C.hist;
      ctx.lineWidth = 1.7;
      ctx.beginPath();
      let started = false;
      for (let i = i0; i <= iFull; i++) {
        const xx = x(i), yy = y(prices[i]);
        if (!started) { ctx.moveTo(xx, yy); started = true; }
        else ctx.lineTo(xx, yy);
      }
      if (r > iFull) ctx.lineTo(x(r), y(priceAt(prices, r)));
      if (started) ctx.stroke();

      // thicker white over cone windows already revealed
      events.forEach((ev, ei) => {
        const st = state.events[ei];
        if (!st.visible) return;
        const end = Math.min(r, ev.i + HORIZON);
        if (end <= ev.i) return;
        const eFull = Math.floor(end);
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let i = ev.i; i <= eFull; i++) {
          const xx = x(i), yy = y(prices[i]);
          if (i === ev.i) ctx.moveTo(xx, yy);
          else ctx.lineTo(xx, yy);
        }
        if (end > eFull) ctx.lineTo(x(end), y(priceAt(prices, end)));
        ctx.stroke();
      });

      ctx.fillStyle = C.hist;
      ctx.beginPath();
      ctx.arc(x(r), y(priceAt(prices, r)), 2.6, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // news markers
    events.forEach((ev, ei) => {
      const st = state.events[ei];
      if (r < ev.i && !st.visible) return;
      const xx = x(ev.i);
      ctx.save();
      ctx.strokeStyle = C.news;
      ctx.globalAlpha = st.visible ? 0.85 : 0.35;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(xx, y0);
      ctx.lineTo(xx, y1);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = C.news;
      ctx.beginPath();
      ctx.arc(xx, y(prices[ev.i]), 2.8, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    });
  }

  function strokeSeries(ctx, x, y, i0, series, tMax) {
    const last = Math.min(tMax, series.length - 1);
    if (last <= 0) return;
    const iFull = Math.floor(last);
    ctx.beginPath();
    for (let t = 0; t <= iFull; t++) {
      const xx = x(i0 + t), yy = y(series[t]);
      if (t === 0) ctx.moveTo(xx, yy);
      else ctx.lineTo(xx, yy);
    }
    if (last > iFull && iFull + 1 < series.length) {
      const f = last - iFull;
      ctx.lineTo(x(i0 + last), y(lerp(series[iFull], series[iFull + 1], f)));
    }
    ctx.stroke();
  }

  function fillBand(ctx, x, y, i0, lo, hi, tMax, fill) {
    const last = Math.min(tMax, lo.length - 1);
    if (last <= 0) return;
    const iFull = Math.floor(last);
    const f = last - iFull;
    ctx.beginPath();
    for (let t = 0; t <= iFull; t++) {
      const xx = x(i0 + t), yy = y(hi[t]);
      if (t === 0) ctx.moveTo(xx, yy);
      else ctx.lineTo(xx, yy);
    }
    if (f > 0 && iFull + 1 < hi.length) {
      ctx.lineTo(x(i0 + last), y(lerp(hi[iFull], hi[iFull + 1], f)));
      ctx.lineTo(x(i0 + last), y(lerp(lo[iFull], lo[iFull + 1], f)));
    }
    for (let t = iFull; t >= 0; t--) ctx.lineTo(x(i0 + t), y(lo[t]));
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
  }

  const cleanups = new Map();

  function mountAll(root, api) {
    cleanups.forEach((fn) => fn());
    cleanups.clear();
    const nodes = root.querySelectorAll("[data-cone]");
    nodes.forEach((canvas, idx) => {
      const ticker = canvas.getAttribute("data-cone");
      const prices = api.serie(ticker);
      const dates = api.dates();
      const news = api.news(ticker) || [];
      const model = buildModel(ticker, prices, dates, news);
      if (!model) {
        canvas.hidden = true;
        return;
      }
      canvas.hidden = false;
      const stop = mountCanvas(canvas, model, { delay: 180 + idx * 140 });
      cleanups.set(canvas, stop);
    });
  }

  global.NewsCone = { mountAll, buildModel };
})(window);
