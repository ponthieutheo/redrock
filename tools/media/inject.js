// Temps virtuel, injecté avant tout script de la page (et de ses iframes) par render.py / capture.py.
// L'horloge n'avance que quand on appelle window.__vt.tick(ms) : chaque image d'une vidéo est calculée
// exactement au bon instant, quelle que soit la vitesse de la machine (rendu 3D, polices, réseau).
// Virtualisé : Date (sans argument) / Date.now, performance.now, requestAnimationFrame, setTimeout/setInterval
// et les animations CSS (mises en pause puis positionnées à la main). Les vraies fonctions restent
// accessibles sous window.__real.
(() => {
  if (window.__vt) return;
  const BASE = window.__VT_BASE || Date.parse("2026-10-14T12:20:00Z");
  const RD = Date, rST = window.setTimeout.bind(window), rCT = window.clearTimeout.bind(window), rPN = performance.now.bind(performance);
  window.__real = {Date: RD, setTimeout: rST, clearTimeout: rCT, now: rPN, setInterval: window.setInterval.bind(window), clearInterval: window.clearInterval.bind(window)};
  let V = 0, cbs = [], rafId = 0, tid = 1e6;
  const timers = new Map();
  function VDate(...a) {
    if (!new.target) return new RD(BASE + V).toString();
    return a.length ? new RD(...a) : new RD(BASE + V);
  }
  VDate.prototype = RD.prototype;
  VDate.now = () => BASE + Math.floor(V);
  VDate.parse = RD.parse; VDate.UTC = RD.UTC;
  window.Date = VDate;
  performance.now = () => V;
  window.requestAnimationFrame = f => { cbs.push(f); return ++rafId; };
  window.cancelAnimationFrame = () => {};
  window.setTimeout = (fn, ms, ...a) => { const id = ++tid; timers.set(id, {at: V + Math.max(0, +ms || 0), fn, a, every: 0}); return id; };
  window.setInterval = (fn, ms, ...a) => { const id = ++tid, p = Math.max(4, +ms || 0); timers.set(id, {at: V + p, fn, a, every: p}); return id; };
  window.clearTimeout = window.clearInterval = id => { timers.delete(id); };
  let seed = 1234567;
  Math.random = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
  const born = new WeakMap();
  const call = f => { try { typeof f === "function" && f(); } catch (e) { console.log("vt err", e && e.message); } };
  window.__vt = {
    tick(ms) {
      const end = V + ms;
      for (let guard = 0; guard < 5000; guard++) {   // minuteries échues, dans l'ordre
        let best = null, bid = 0;
        for (const [id, t] of timers) if (t.at <= end && (!best || t.at < best.at)) { best = t; bid = id; }
        if (!best) break;
        V = Math.max(V, best.at);
        if (best.every) best.at += best.every; else timers.delete(bid);
        call(() => best.fn(...best.a));
      }
      V = end;
      const run = cbs; cbs = [];
      for (const f of run) call(() => f(V));
      try { document.getAnimations().forEach(a => { if (!born.has(a)) born.set(a, V); a.pause(); a.currentTime = V - born.get(a); }); } catch (e) {}
    },
    get now() { return V; },
  };
  if (window.__VT_DPR) Object.defineProperty(window, "devicePixelRatio", {get: () => window.__VT_DPR});
})();
