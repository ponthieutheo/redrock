// Outils des compositions (teaser.html, install.html, apercu.html), rendues image par image par render.py.
// Une composition expose window.COMP = {w, h, fps, dur, init(), frame(t, dt)} ; render.py appelle init() une fois,
// puis frame(t, dt) avant chaque capture. L'app tourne dans des iframes en temps virtuel (inject.js) :
// C.step(win, ms) fait avancer son horloge, par pas de 1/60 s comme un vrai écran.
(() => {
  const C = window.C = {};
  const real = window.__real || {setTimeout: setTimeout.bind(window)};
  C.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  C.E = {
    out: x => 1 - Math.pow(1 - x, 3), out4: x => 1 - Math.pow(1 - x, 4), io: x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2,
    back: x => { const c = 1.70158, d = c + 1; return 1 + d * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
    lin: x => x,
  };
  C.seg = (t, a, b, f = C.E.out) => f(C.clamp((t - a) / (b - a)));
  C.wait = ms => new Promise(r => real.setTimeout(r, ms));
  C.until = async (fn, ms = 1500) => { for (let i = 0; i < ms / 15; i++) { try { if (fn()) return true; } catch (e) {} await C.wait(15); } return false; };   // attente réelle
  C.$ = id => document.getElementById(id);
  C.win = id => C.$(id).contentWindow;
  C.doc = id => C.$(id).contentDocument;

  // horloge de l'app : pas de 1/60 s (les lissages de la scène sont réglés pour ça)
  const acc = new WeakMap();
  C.step = (win, ms) => {
    let a = (acc.get(win) || 0) + ms;
    while (a >= 16.6666) { win.__vt.tick(16.6666); a -= 16.6666; }
    acc.set(win, a);
  };
  // attend qu'une iframe d'app soit prête (3D allumée, polices chargées), puis la laisse vivre `warm` ms
  C.ready = async (id, warm = 4000) => {
    const f = C.$(id);
    await C.until(() => f.contentWindow && f.contentWindow.__vt && f.contentDocument.readyState === "complete", 20000);
    await f.contentDocument.fonts.ready;
    const w = f.contentWindow;
    for (let i = 0; i < warm / 16.6666; i++) { w.__vt.tick(16.6666); if (i % 20 === 19) await C.wait(6); }
    await C.until(() => w.document.getElementById("arena").classList.contains("three-on"), 5000);
  };

  // événements datés : chacun s'exécute une fois, à son heure, dans l'ordre
  C.timeline = list => { const ev = list.slice().sort((a, b) => a.t - b.t); let i = 0;
    return async t => { while (i < ev.length && ev[i].t <= t + 1e-6) { const e = ev[i++]; try { await e.fn(); } catch (x) { console.log("événement", e.t, x && x.message); } } }; };

  // chat de l'app : frappe lettre à lettre, envoi, réponse débitée morceau par morceau (serveur en mode gate)
  C.typeInto = (win, text, k) => { const d = win.document, i = d.getElementById("chat-in"), v = text.slice(0, Math.max(0, k));
    if (i.value !== v) { i.value = v; i.dispatchEvent(new win.Event("input")); } };
  C.submit = win => win.document.getElementById("chat-form").requestSubmit();
  C.streamLen = win => { const b = win.document.querySelector("#chat-log .msg.streaming"); return b ? b.textContent.length : -1; };
  C.release = async win => {
    const n0 = C.streamLen(win), typing = !!win.document.querySelector("#chat-log .typing");
    if (!typing && n0 < 0) return false;   // rien en cours
    await fetch("/__release");
    await C.until(() => C.streamLen(win) !== n0 || (!win.document.querySelector("#chat-log .typing") && C.streamLen(win) < 0), 600);
    return true;
  };
  C.scenario = async (win, name) => { await fetch("/__scenario/" + name); await win.refresh(true); };
  C.emote = (win, kind) => win.__emote && win.__emote(kind);
  C.css = (win, text) => { const s = win.document.createElement("style"); s.textContent = text; win.document.head.appendChild(s); };

  // Personnage muet : plus de bulle de parole ni de réplique (l'app appelle window.talk à chaque état, y compris
  // « Je suis mort » ou « Je vérifie mon compte… » pendant la relève). La bouche ne bouge plus que pour le chat.
  // all : masque aussi les bulles de pensée et les « Zzz » (mort et relève).
  C.noTalk = (win, all) => {
    win.talk = () => {};
    const d = win.document, s = d.getElementById("say"), a = d.getElementById("arena");
    if (s) s.classList.remove("on");
    if (a) a.classList.remove("talking");
    win.__say = null;
    C.css(win, "#say { display: none !important; }" + (all ? " .ov-thought, .ov-zzz { display: none !important; }" : ""));
  };

  // Contrôle d'une image : état de chaque app (bulle, bouche, 3D, textes) ; erreurs = l'image est fausse.
  // Deuxième argument : talkOk (intervalles [a, b) où la bouche peut bouger), ou un objet d'options :
  //   talkOk  : idem (réponse du chat, « Salut ! ») ; partout ailleurs, la bouche ne doit pas parler ;
  //   safe    : {l, t, r, b} zone sûre (vidéo verticale : ni le haut, ni le bas, ni la colonne de droite des réseaux) :
  //             chaque texte de la composition ([data-txt]) et le visage du perso (s'il est à l'image) doivent y tenir ;
  //   face    : true = aucun texte de la composition ne doit toucher le visage du perso (window.__headPx de l'app).
  // Toujours : aucun texte de la composition coupé (débordement de sa boîte ou du cadre).
  // Un élément .card affiché en plein (opacité 1) cache les apps : pas de contrôle du visage tant qu'il est là.
  const BAD = /\bundefined\b|\bNaN\b|\[object /;
  const inter = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  const effOpacity = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden") return 0; o *= +cs.opacity; } return o; };
  // textes visibles ; une ligne faite de mots animés (.w) compte dès qu'un de ses mots se voit
  C.texts = () => [...document.querySelectorAll("[data-txt]")].filter(e => {
    if (!e.getClientRects().length || effOpacity(e) <= .02) return false;
    const ws = e.querySelectorAll(":scope > .w");
    return !ws.length || [...ws].some(w => +getComputedStyle(w).opacity > .02);
  });
  // boîte d'un texte une fois posé (sans les transformations des animations d'entrée), en px de la composition
  const layoutRect = e => { let x = 0, y = 0; for (let n = e; n; n = n.offsetParent) { x += n.offsetLeft; y += n.offsetTop; }
    return {left: x, top: y, right: x + e.offsetWidth, bottom: y + e.offsetHeight}; };
  // largeur naturelle du texte (mots .w : somme des largeurs et marges ; sinon scrollWidth)
  const natW = e => { const ws = e.querySelectorAll(":scope > .w"); if (!ws.length) return e.scrollWidth;
    let s = 0; ws.forEach(w => { const cs = getComputedStyle(w); s += w.offsetWidth + parseFloat(cs.marginLeft) + parseFloat(cs.marginRight); }); return s; };
  // visage du perso de l'app `id`, dans les coordonnées de la composition : {x, y, r} (null si la tête n'est pas là)
  C.face = id => {
    const f = C.$(id), w = f.contentWindow;
    if (!w || !w.__headPx || !f.getClientRects().length || effOpacity(f) < .05) return null;
    const h = w.__headPx(), R = f.getBoundingClientRect(), k = R.width / f.offsetWidth;
    if (!(h.s > .3)) return null;
    return {x: R.left + h.x * k, y: R.top + h.y * k, r: h.rad * k * h.s};
  };
  C.probe = (ids, t, opt) => {
    const o = Array.isArray(opt) || !opt ? {talkOk: opt} : opt;
    const errs = [], st = [];
    const ok = (o.talkOk || []).some(([a, b]) => t >= a - 1e-6 && t < b);
    if (BAD.test(document.body.innerText)) errs.push("composition : texte « undefined »/« NaN »");
    const W = innerWidth, H = innerHeight, txt = C.texts(), rects = txt.map(e => [e, layoutRect(e)]);
    for (const [e, r] of rects) {
      const name = e.dataset.txt || e.id || e.className, nw = natW(e);
      if (r.left < -1 || r.top < -1 || r.right > W + 1 || r.bottom > H + 1) errs.push(`texte « ${name} » hors du cadre`);
      if (nw > e.clientWidth + 2) errs.push(`texte « ${name} » coupé (${Math.round(nw)} > ${e.clientWidth} px)`);
      if (o.safe && (r.left < o.safe.l - 1 || r.top < o.safe.t - 1 || r.right > o.safe.r + 1 || r.bottom > o.safe.b + 1))
        errs.push(`texte « ${name} » hors de la zone sûre (${Math.round(r.left)},${Math.round(r.top)} → ${Math.round(r.right)},${Math.round(r.bottom)})`);
    }
    const card = [...document.querySelectorAll(".card")].some(e => e.getClientRects().length && effOpacity(e) > .99);
    for (const id of ids) {
      const w = C.win(id), d = C.doc(id), say = d.getElementById("say"), ar = d.getElementById("arena");
      const sayOn = !!say && say.classList.contains("on");
      const cs = say && w.getComputedStyle(say);
      const sayVis = sayOn && cs.display !== "none" && cs.visibility !== "hidden" && +cs.opacity > .01;
      const talking = !!ar && ar.classList.contains("talking");
      const s = w.__say, speaking = talking && !!s && (w.performance.now() - s.t0) / 62 < s.text.length;
      const th = [...d.querySelectorAll(".ov-thought, .ov-zzz")].some(e => w.getComputedStyle(e).display !== "none");
      const three = !!ar && ar.classList.contains("three-on");
      const hatchT = w.__hatchT ? Math.round(w.__hatchT() * 100) / 100 : null;
      const fc = card ? null : C.face(id);
      st.push({id, sayOn, sayVis, talking, speaking, bulle_pensee: th, three, hatchT, visage: fc && [Math.round(fc.x), Math.round(fc.y), Math.round(fc.r)]});
      if (sayOn || sayVis) errs.push(`${id} : bulle de parole`);
      if ((talking || speaking) && !ok) errs.push(`${id} : la bouche parle hors des moments permis`);
      if (th) errs.push(`${id} : bulle de pensée ou Zzz`);
      if (!three) errs.push(`${id} : 3D éteinte`);
      // texte visible seulement (une iframe hors page renverrait aussi le code de ses scripts)
      if (C.$(id).getClientRects().length && BAD.test(d.body.innerText)) errs.push(`${id} : texte « undefined »/« NaN »`);
      // le visage (cercle de la tête, un peu resserré) : aucun texte dessus ; dans la zone sûre s'il est à l'image
      if (fc && fc.x > 0 && fc.x < W && fc.y > 0 && fc.y < H) {
        const fr = {left: fc.x - fc.r * .85, right: fc.x + fc.r * .85, top: fc.y - fc.r * .85, bottom: fc.y + fc.r * .85};
        if (o.face) for (const [e, r] of rects) if (inter(fr, r)) errs.push(`${id} : le texte « ${e.dataset.txt || e.id} » touche le visage`);
        if (o.safe && (fc.x < o.safe.l || fc.x > o.safe.r || fc.y < o.safe.t || fc.y > o.safe.b)) errs.push(`${id} : visage hors de la zone sûre (${Math.round(fc.x)}, ${Math.round(fc.y)})`);
      }
    }
    return {errs, st};
  };
})();
