/* HC-1 : moteur son / haptique / événements. window.FX = {emit, sfx, haptic, volume, enabled, setEnabled, demo} */
(function () {
  "use strict";
  const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
  const reduced = () => { try { return matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } };
  const enabled = () => { const s = store.get("hc1-sound"); return s === "1" || (s === null && !reduced()); };
  const volume = v => {
    if (v !== undefined) { v = Math.max(0, Math.min(1, +v || 0)); store.set("hc1-vol", String(v)); if (master) master.gain.value = v * v; }
    const s = parseFloat(store.get("hc1-vol")); return isNaN(s) ? 0.8 : s;
  };
  const setEnabled = on => { store.set("hc1-sound", on ? "1" : "0"); if (on) unlock(); };

  let ctx = null, master = null, noiseBuf = null, lastAny = 0;
  const lastType = {};
  function ac() {
    if (!ctx) {
      try {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        master = ctx.createGain(); master.gain.value = volume() ** 2;
        const comp = ctx.createDynamicsCompressor();
        comp.threshold.value = -18; comp.knee.value = 12; comp.ratio.value = 6; comp.attack.value = .003; comp.release.value = .2;
        master.connect(comp); comp.connect(ctx.destination);
      } catch (e) { ctx = null; return null; }
    }
    if (ctx.state === "suspended") { try { ctx.resume(); } catch (e) {} }
    return ctx;
  }
  function unlock() { return ac(); }
  // iOS/Chrome : le contexte ne se débloque qu'à un vrai geste ; on réessaie à chaque geste tant qu'il dort
  ["pointerdown", "touchend", "keydown"].forEach(ev => addEventListener(ev, () => { if (ctx ? ctx.state !== "running" : enabled()) ac(); }, {passive: true}));

  // garde-fous : onglet caché, son coupé, 40 ms entre deux sons, cadence minimale par type
  function gate(type, minGap) {
    if (!enabled() || document.hidden) return false;
    const n = performance.now();
    if (n - lastAny < 40) return false;
    if (minGap && n - (lastType[type] || 0) < minGap) return false;
    lastAny = n; lastType[type] = n; return true;
  }
  function tone(f, t0, d, type, vol, slide) {
    const c = ac(); if (!c) return;
    const t = c.currentTime + t0, o = c.createOscillator(), g = c.createGain();
    o.type = type || "sine"; o.frequency.setValueAtTime(f, t); if (slide) o.frequency.exponentialRampToValueAtTime(slide, t + d);
    g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(vol || .1, t + .012); g.gain.exponentialRampToValueAtTime(.0001, t + d);
    o.connect(g).connect(master); o.start(t); o.stop(t + d + .05);
  }
  function noise(t0, d, vol, f0, f1, q, type) {
    const c = ac(); if (!c) return;
    if (!noiseBuf) { noiseBuf = c.createBuffer(1, c.sampleRate * .6, c.sampleRate); const dd = noiseBuf.getChannelData(0); for (let i = 0; i < dd.length; i++) dd[i] = Math.random() * 2 - 1; }
    const t = c.currentTime + t0, n = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    n.buffer = noiseBuf; f.type = type || "bandpass"; f.Q.value = q || 1.2;
    f.frequency.setValueAtTime(f0, t); if (f1) f.frequency.exponentialRampToValueAtTime(f1, t + d);
    g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + Math.min(.01, d / 3)); g.gain.exponentialRampToValueAtTime(.0001, t + d);
    n.connect(f).connect(g).connect(master); n.start(t); n.stop(t + d + .02);
  }
  const click = vol => noise(0, .045, vol, 2600 + Math.random() * 1800, 0, 1.2);

  const sfx = {
    unlock,
    key() { if (!gate("key", 75)) return; click(.16); },
    tap() { if (!gate("tap", 50)) return; tone(520, 0, .06, "sine", .05, 760); click(.05); },
    tick() { if (!gate("tick", 40)) return; tone(880, 0, .04, "triangle", .04); },
    open() { if (!gate("open", 120)) return; noise(0, .22, .07, 400, 2400, .9); tone(330, 0, .18, "sine", .04, 560); },
    close() { if (!gate("close", 120)) return; noise(0, .18, .06, 2200, 380, .9); tone(500, 0, .15, "sine", .035, 280); },
    toggle(on) { if (!gate("toggle", 60)) return; on ? (tone(600, 0, .07, "triangle", .07), tone(900, .06, .1, "triangle", .07)) : (tone(700, 0, .07, "triangle", .06), tone(450, .06, .1, "triangle", .06)); },
    send() { if (!gate("send", 80)) return; tone(420, 0, .09, "sine", .08, 840); },
    recv() { if (!gate("recv", 80)) return; tone(740, 0, .08, "sine", .07); tone(990, .07, .12, "sine", .06); },
    ching(pnl) {
      if (!gate("ching", 80)) return;
      const a = Math.abs(+pnl || 0), tier = a >= 5 ? 3 : a >= 1 ? 2 : 1;
      tone(1318.5, 0, .2, "triangle", .1); tone(1760, .09, .4, "triangle", .1);
      if (tier >= 2) tone(2093, .18, .4, "triangle", .08);
      if (tier >= 3) { tone(2637, .27, .5, "triangle", .08); tone(1568, .27, .5, "sine", .05); }
    },
    bonk() { if (!gate("bonk", 80)) return; tone(240, 0, .3, "sine", .14, 110); },
    alarm() { if (!gate("alarm", 400)) return; tone(466, 0, .2, "triangle", .06); tone(349, .24, .26, "triangle", .06); },
    boop() { if (!gate("boop", 80)) return; tone(480, 0, .14, "sine", .12, 900); },
    pop() { if (!gate("pop", 80)) return; tone(260, 0, .1, "square", .045, 980); tone(1200, .08, .25, "triangle", .07); },
    fanfare() { if (!gate("fanfare", 300)) return; [523.3, 659.3, 784, 1046.5].forEach((f, i) => tone(f, i * .11, .32, "triangle", .09)); },
    off() { if (!gate("off", 300)) return; tone(180, 0, .5, "sawtooth", .03, 60); },
    clac() { if (!gate("clac", 80)) return; tone(110, 0, .12, "square", .06, 70); noise(0, .05, .1, 1800, 0, 1); tone(660, .1, .08, "triangle", .06, 990); },
    flame() { if (!gate("flame", 200)) return; noise(0, .5, .09, 500, 3000, .8); tone(784, .3, .3, "triangle", .08); tone(1046.5, .38, .3, "triangle", .07); },
    record() { if (!gate("record", 300)) return; [523.3, 659.3, 784, 1046.5, 1318.5, 1568].forEach((f, i) => tone(f, i * .08, .4, "triangle", .08)); },
    ding() { if (!gate("ding", 400)) return; tone(988, 0, .5, "sine", .06); tone(740, .22, .6, "sine", .06); },
    coin() { if (!gate("coin", 120)) return; tone(1500, 0, .05, "square", .025); tone(2000, .05, .12, "square", .025); },
    rise() { if (!gate("rise", 300)) return; [330, 440, 554, 740, 988].forEach((f, i) => tone(f, i * .09, .3, "sine", .07)); tone(1318.5, .5, .5, "triangle", .08); },
  };

  const PROFILES = {tp: [10, 40, 10], sl: [40], open: [8], tap: [8], record: [30, 40, 30, 40, 60], achievement: [30, 40, 30], news: [12, 60, 12], renaissance: [20, 30, 40], heavy: [20]};
  function haptic(p) {
    if (store.get("hc1-haptic") === "0" || reduced() || !navigator.vibrate) return;
    const v = typeof p === "string" ? PROFILES[p] : p;
    if (v) try { navigator.vibrate(v); } catch (e) {}
  }

  const call = (fn, a) => { try { fn(a); } catch (e) {} };
  const RULES = {
    "trade:open": p => { call(sfx.clac); haptic("open"); },
    "trade:close": p => {
      const r = p && p.reason, win = (+(p && p.pnl) || 0) >= 0;
      if (r === "sl" || (r !== "tp" && !win)) { call(sfx.bonk); haptic("sl"); } else { call(sfx.ching, p && p.pnl); haptic("tp"); }
    },
    "trade:sl_move": () => call(sfx.tick),
    "record": () => { call(sfx.record); haptic("record"); },
    "streak": () => call(sfx.flame),
    "news": p => { if (!p || p.impact === "high" || p.impact === undefined) { call(sfx.ding); haptic("news"); } },
    "achievement": () => { call(sfx.fanfare); haptic("achievement"); },
    "mood": p => { const s = p && p.state; if (s === "danger") call(sfx.alarm); else if (s === "happy" || s === "wow") call(sfx.boop); },
    "renaissance": () => { call(sfx.rise); haptic("renaissance"); },
    "ui:tab": () => call(sfx.tick),
    "ui:open": () => call(sfx.open),
    "ui:close": () => call(sfx.close),
    "ui:toggle": p => call(sfx.toggle, !(p && p.on === false)),
    "chat:send": () => call(sfx.send),
    "chat:recv": () => call(sfx.recv),
  };
  function emit(name, payload) { const r = RULES[name]; if (r) try { r(payload || {}); } catch (e) {} }

  // une seule délégation pour tous les boutons de l'interface
  addEventListener("pointerdown", e => {
    const t = e.target && e.target.closest && e.target.closest("button,[role=tab],[role=switch],summary");
    if (!t || t.disabled) return;
    if (t.matches("[role=switch]")) { call(sfx.toggle, t.getAttribute("aria-checked") !== "true"); return; }
    if (t.matches("[role=tab],[data-sec],.segs button,.pills button")) { call(sfx.tick); return; }
    if (t.closest(".dock")) return;
    call(sfx.tap);
  }, {passive: true});

  function demo() {
    const seq = [["trade:open", {side: "long", coin: "BTC"}], ["trade:close", {pnl: 0.4, reason: "tp"}], ["trade:close", {pnl: 3, reason: "tp"}], ["trade:close", {pnl: 8, reason: "tp"}],
      ["trade:close", {pnl: -1, reason: "sl"}], ["trade:sl_move"], ["record"], ["streak"], ["news", {impact: "high"}], ["achievement"], ["mood", {state: "danger"}],
      ["renaissance"], ["ui:tab"], ["ui:open"], ["ui:close"], ["ui:toggle", {on: true}], ["ui:toggle", {on: false}], ["chat:send"], ["chat:recv"]];
    seq.forEach((s, i) => setTimeout(() => { lastAny = 0; Object.keys(lastType).forEach(k => lastType[k] = 0); console.log("FX.demo", s[0]); emit(s[0], s[1]); }, i * 900));
  }

  window.FX = {emit, sfx, haptic, volume, enabled, setEnabled, unlock, demo};
})();
