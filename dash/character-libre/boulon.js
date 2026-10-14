/* Boulon — le personnage libre de RedRock : un petit robot rond dont le visage est un écran.
   Copyright (c) 2026 Théo Ponthieu. Licence MIT (voir character-libre/LICENSE) : usage libre, y compris commercial.
   Il respecte le même contrat scène ↔ personnage que le personnage RedRock (détails : character-libre/README.md) :
     const perso = createCharacter({THREE, rig, desk, renderer})   puis perso.mount({props, hitZone})
     chaque image : perso.update(dt, now, t, S) ; perso.updateHands(dt, now, t, S) ; perso.lateUpdate(dt)
   Rien n'est alloué image par image : vecteurs et couleurs réservés d'avance, visage redessiné seulement s'il change. */

const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
const lerp = (a, b, k) => a + (b - a) * k;
const sm = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);
const seg = (t, a, b) => sm((t - a) / (b - a));
const ease = (rate, dt) => 1 - Math.exp(-rate * dt);   // lissage identique quelle que soit la cadence
const pick = a => a[Math.floor(Math.random() * a.length)];
const NO = {};

// répertoire : répliques, durée des émotes
const TALK = ["Bip boup. Le marché est calme… trop calme.", "Je carbure au café et aux chandeliers.", "Stop serré, boulons serrés.",
  "Mes capteurs flairent un setup.", "Batterie pleine, discipline pleine.", "Un jour, j'aurai un bureau avec fenêtre."];
const BOOP = ["Bip ! Ça chatouille.", "Hé, mes capteurs !", "Je calcule, là…", "Boup.", "Doucement, je suis fragile.", "Toujours en ligne !"];
const DUR = {dance: 6000, think: 4500, panic: 4000, sleep: 5000, type: 4000, shades: 6000};

// visage : codes des expressions (yeux) et des bouches
const E_OPEN = 0, E_HAPPY = 1, E_CLOSED = 2, E_WIDE = 3, E_SQUINT = 4, E_X = 5, E_CRT = 6, E_BOOT = 7, E_GLITCH = 8, E_BLACK = 9;
const M_SMILE = 0, M_FLAT = 1, M_GRIN = 2, M_O = 3, M_ZIG = 4, M_WAVE = 5, M_BARS = 6, M_YAWN = 7, M_DOTS = 8, M_BATT = 9, M_SMIRK = 10, M_SLEEP = 11;
// lunettes pixel : X = noir, W = reflet
const SHADES = ["XXXXXXXXXXXXXXXXXXXXXXXXXXX", "XXWWXXXXXXXX...XXWWXXXXXXXX", "XWWXXXXXXXXX...XWWXXXXXXXXX", ".XXXXXXXXXX.....XXXXXXXXXX.", "..XXXXXXXX.......XXXXXXXX.."];

export function createCharacter(ctx) {
  const {THREE, rig} = ctx, {mouse, M0, mWheel, mLed, pressNear} = ctx.desk, SW = ctx.desk.screenW || 512;
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const trash = [], owned = [];   // géométries, matériaux, textures à libérer ; racines posées dans la scène
  const G = g => (trash.push(g), g), M = m => (trash.push(m), m);
  const std = (color, roughness = .5, metalness = 0, extra) => M(new THREE.MeshStandardMaterial(Object.assign({color, roughness, metalness}, extra)));
  const mesh = (geo, mat, parent, x = 0, y = 0, z = 0, shadow = true) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = shadow; parent.add(m); return m; };
  const canvas = (w, h) => { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; };
  const texOf = (c, fast) => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; if (fast) { t.generateMipmaps = false; t.minFilter = THREE.LinearFilter; } trash.push(t); return t; };
  const sfx = (name, a) => { try { const s = window.__sfx; if (s && s[name]) s[name](a); } catch (e) {} };
  const buzz = p => { try { if (window.__buzz) window.__buzz(p); } catch (e) {} };
  const RM = matchMedia("(prefers-reduced-motion: reduce)");
  const rr = (c, x, y, w, h, r) => { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); };

  // ---------- la coque : un galet carré (super-ellipsoïde), demi-axes A, B, C, rondeur P ----------
  const A = 1, B = .86, C = .86, P = 3;
  const surfZ = (x, y) => C * Math.pow(Math.max(0, 1 - Math.abs(x / A) ** P - Math.abs(y / B) ** P), 1 / P);   // avant de la coque au-dessus de (x, y)
  const normalAt = (x, y, z, out) => out.set(Math.sign(x) * Math.abs(x / A) ** (P - 1) / A, Math.sign(y) * Math.abs(y / B) ** (P - 1) / B, Math.sign(z) * Math.abs(z / C) ** (P - 1) / C).normalize();
  const nv = V(0, 0, 0), ZUP = V(0, 0, 1);
  const shellGeo = (() => { const g = new THREE.SphereGeometry(1, 72, 54), p = g.attributes.position, n = g.attributes.normal, v = V(0, 0, 0);
    for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); v.multiplyScalar((Math.abs(v.x) ** P + Math.abs(v.y) ** P + Math.abs(v.z) ** P) ** (-1 / P));
      v.set(v.x * A, v.y * B, v.z * C); p.setXYZ(i, v.x, v.y, v.z); normalAt(v.x, v.y, v.z, nv); n.setXYZ(i, nv.x, nv.y, nv.z); }   // normales exactes : pas de couture
    return G(g); })();
  // écran du visage : plaque qui épouse l'avant de la coque, bord en super-ellipse (coins ronds), UV = projection de face
  const FW = .7, FH = .5, FY = .04, Q = 4.5;
  function decalGeo(sc, lift) {
    const nx = 28, ny = 20, pos = [], uv = [], nor = [], idx = [];
    for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) {
      let u = i / nx * 2 - 1, w = j / ny * 2 - 1; const rs = Math.max(Math.abs(u), Math.abs(w)), re = (Math.abs(u) ** Q + Math.abs(w) ** Q) ** (1 / Q);
      if (re > 0) { u *= rs / re; w *= rs / re; }
      const x = u * FW * sc, y = FY + w * FH * sc, z = surfZ(x, y); normalAt(x, y, z, nv);
      pos.push(x + nv.x * lift, y + nv.y * lift, z + nv.z * lift); nor.push(nv.x, nv.y, nv.z); uv.push((u + 1) / 2, (w + 1) / 2);
      if (i && j) { const a = (j - 1) * (nx + 1) + i - 1, b = a + 1, c = a + nx + 1, d = c + 1; idx.push(a, b, d, a, d, c); } }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.setIndex(idx); return G(g);
  }
  // un objet posé à plat sur la coque au point (x, y) de la face avant
  const stick = (o, x, y, lift) => { const z = surfZ(x, y); normalAt(x, y, z, nv); o.position.set(x + nv.x * lift, y + nv.y * lift, z + nv.z * lift); o.quaternion.setFromUnitVectors(ZUP, nv); return o; };

  const head = new THREE.Group(); rig.add(head); owned.push(head);
  const HEAD = V(.05, .86, .75), HS = .88;   // place de repos (dans le rig) et taille : la scène s'en sert pour la caméra, les bulles et le toucher
  head.position.copy(HEAD); head.scale.setScalar(HS);
  const CREAM = new THREE.Color(0xeee7dc), DEADC = new THREE.Color(0x8d8a86);
  const shellMat = std(0xeee7dc, .42, .04), graphite = std(0x2b2e35, .5, .2), steel = std(0x9ba3ad, .32, .65), amber = std(0xffa83a, .45);
  const shell = mesh(shellGeo, shellMat, head); shell.receiveShadow = true;
  const bezelMat = std(0x24272d, .45, .15, {polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1});
  mesh(decalGeo(1.075, .004), bezelMat, head, 0, 0, 0, false);
  // le visage est peint sur une petite toile ; l'écran s'éclaire lui-même (il brille aussi la nuit, sans reflet des lampes de la salle)
  const FCW = 320, FCH = 228, CX = 160, EY = 100, MY = 176, EDX = 66;
  const faceCv = canvas(FCW, FCH), fx = faceCv.getContext("2d"), faceTex = texOf(faceCv, true);
  const screenMat = M(new THREE.MeshBasicMaterial({map: faceTex, toneMapped: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2}));
  mesh(decalGeo(1, .011), screenMat, head, 0, 0, 0, false);
  const bgCv = canvas(FCW, FCH);
  { const c = bgCv.getContext("2d"), g = c.createRadialGradient(CX, 96, 10, CX, 110, 230); g.addColorStop(0, "#13202a"); g.addColorStop(1, "#04060a");
    c.fillStyle = g; c.fillRect(0, 0, FCW, FCH); c.fillStyle = "rgba(150,235,255,.04)"; for (let y = 0; y < FCH; y += 4) c.fillRect(0, y, FCW, 1);
    const s = c.createLinearGradient(0, 0, 150, 120); s.addColorStop(0, "rgba(255,255,255,.13)"); s.addColorStop(1, "rgba(255,255,255,0)");   // reflet du verre
    c.fillStyle = s; c.beginPath(); c.moveTo(0, 0); c.lineTo(190, 0); c.lineTo(0, 120); c.fill(); }
  // canevas → coque (pour poser des objets devant les yeux)
  const cx3 = px => (px / FCW * 2 - 1) * FW, cy3 = py => FY + (1 - py / FCH * 2) * FH;

  // boulons des oreilles (d'où son nom) et antenne à ressort
  { const nut = G(new THREE.CylinderGeometry(.15, .15, .1, 6)), cap = G(new THREE.CylinderGeometry(.07, .07, .06, 16));
    [-1, 1].forEach(sd => { const b = mesh(nut, steel, head, sd * (A + .015), .02, 0); b.rotation.z = Math.PI / 2;
      const c = mesh(cap, graphite, head, sd * (A + .07), .02, 0); c.rotation.z = Math.PI / 2; }); }
  const ant = new THREE.Group(); ant.position.set(0, B - .03, 0); head.add(ant);
  mesh(G(new THREE.CylinderGeometry(.085, .11, .1, 20)), graphite, ant, 0, .04, 0);
  mesh(G(new THREE.CylinderGeometry(.02, .024, .34, 10)), steel, ant, 0, .26, 0);
  const bulbMat = std(0x2a2a2a, .3, 0, {emissive: 0xffb648, emissiveIntensity: 1});
  mesh(G(new THREE.SphereGeometry(.085, 20, 14)), bulbMat, ant, 0, .46, 0);
  const AS = {x: 0, z: 0, vx: 0, vz: 0, px: 0, py: 0, pvx: 0, pvy: 0, init: false};
  const BULB = new THREE.Color(0xffb648), C_AMBER = new THREE.Color(0xffb648), C_RED = new THREE.Color(0xff3b30), C_CYAN = new THREE.Color(0x7df9ff),
    C_GREEN = new THREE.Color(0x5dff9a), C_BLUE = new THREE.Color(0x5a7cff), C_GOLD = new THREE.Color(0xffd45c), C_TMP = new THREE.Color();

  // ---------- tenues (la scène clone crown, topHat, partyHat, bowTie et appelle makeHeadset() pour la vitrine de la garde-robe) ----------
  const gold = std(0xf2c14e, .35, .5, {side: THREE.DoubleSide});
  const crown = new THREE.Group();
  { const g = new THREE.CylinderGeometry(.36, .36, .3, 10, 1, true), p = g.attributes.position;   // couronne en zigzag : un sommet sur deux du bord haut redescend
    for (let i = 0; i <= 10; i++) if (i % 2) p.setY(i, p.getY(i) - .17);
    g.translate(0, .15, 0); mesh(G(g), gold, crown);
    const rim = mesh(G(new THREE.TorusGeometry(.36, .03, 8, 40)), gold, crown, 0, .02, 0); rim.rotation.x = Math.PI / 2;
    const gem = G(new THREE.SphereGeometry(.045, 14, 10));
    for (let i = 0; i < 5; i++) { const a = i / 5 * Math.PI * 2; mesh(gem, amber, crown, Math.sin(a) * .36, .3, Math.cos(a) * .36); } }   // une gemme au bout de chaque pointe
  const topHat = new THREE.Group(), hatMat = std(0x1d1f24, .55, .1);
  mesh(G(new THREE.CylinderGeometry(.56, .56, .04, 40)), hatMat, topHat, 0, .02, 0);
  mesh(G(new THREE.CylinderGeometry(.36, .38, .58, 40)), hatMat, topHat, 0, .33, 0);
  mesh(G(new THREE.CylinderGeometry(.385, .385, .1, 40, 1, true)), amber, topHat, 0, .1, 0);
  const partyHat = new THREE.Group();
  { const c = canvas(64, 64), x = c.getContext("2d"); x.fillStyle = "#f3eee6"; x.fillRect(0, 0, 64, 64);
    for (let i = -64; i < 128; i += 32) { x.fillStyle = "#4fd8e8"; x.beginPath(); x.moveTo(i, 64); x.lineTo(i + 10, 64); x.lineTo(i + 74, 0); x.lineTo(i + 64, 0); x.fill();
      x.fillStyle = "#ffa83a"; x.beginPath(); x.moveTo(i + 16, 64); x.lineTo(i + 22, 64); x.lineTo(i + 86, 0); x.lineTo(i + 80, 0); x.fill(); }
    const t = texOf(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 1);
    mesh(G(new THREE.ConeGeometry(.28, .72, 32, 1, true)), std(0xffffff, .6, 0, {map: t, side: THREE.DoubleSide}), partyHat, 0, .36, 0);
    mesh(G(new THREE.SphereGeometry(.085, 16, 12)), amber, partyHat, 0, .74, 0); }
  const bowTie = new THREE.Group();
  { const wing = G(new THREE.ConeGeometry(.13, .25, 18));   // deux cônes pointe contre pointe
    [-1, 1].forEach(sd => { const w = mesh(wing, graphite, bowTie, sd * .125, 0, 0); w.rotation.z = sd * Math.PI / 2; w.scale.z = .45; });
    mesh(G(new THREE.SphereGeometry(.055, 14, 10)), amber, bowTie); }
  const hsGeo = {};   // le casque : géométries partagées entre le modèle porté et celui de la vitrine
  function makeHeadset() {
    if (!hsGeo.band) { const pts = []; for (let i = 0; i <= 16; i++) { const a = i / 16 * Math.PI, c = Math.cos(a), s = Math.sin(a);   // arceau qui suit la coque (super-ellipse) à distance
        pts.push(V(Math.sign(c) * Math.abs(c) ** (2 / P) * (A + .1), Math.abs(s) ** (2 / P) * (B + .12), 0)); }
      hsGeo.band = G(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, .04, 8)); hsGeo.cup = G(new THREE.CylinderGeometry(.21, .21, .14, 24));
      hsGeo.pad = G(new THREE.CylinderGeometry(.13, .13, .03, 24));
      hsGeo.mic = G(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([V(-1.1, -.05, .06), V(-1.04, -.42, .42), V(-.72, -.64, .74), V(-.36, -.62, .86)]), 24, .022, 8));
      hsGeo.ball = G(new THREE.SphereGeometry(.06, 12, 10)); }
    const g = new THREE.Group(), band = mesh(hsGeo.band, graphite, g); band.rotation.x = -.26;   // arceau penché en arrière : il passe derrière l'antenne
    [-1, 1].forEach(sd => { const c = mesh(hsGeo.cup, graphite, g, sd * 1.07, 0, 0); c.rotation.z = Math.PI / 2; const p = mesh(hsGeo.pad, amber, g, sd * 1.15, 0, 0); p.rotation.z = Math.PI / 2; });
    mesh(hsGeo.mic, graphite, g); mesh(hsGeo.ball, amber, g, -.36, -.62, .86); return g;
  }
  const headset = makeHeadset();
  const glasses = new THREE.Group();   // lunettes rondes : montures dorées devant l'écran
  { const ring = G(new THREE.TorusGeometry(.19, .02, 10, 36)), ey = cy3(EY);
    [-1, 1].forEach(sd => { const x = cx3(CX + sd * EDX); const r = mesh(ring, gold, glasses, x, ey, surfZ(x, ey) + .05); r.rotation.y = sd * .18; });
    const br = mesh(G(new THREE.CylinderGeometry(.016, .016, .2, 8)), gold, glasses, 0, ey + .06, surfZ(0, ey) + .06); br.rotation.z = Math.PI / 2; }
  const bandage = new THREE.Group();   // sparadrap en croix sur un coin de l'écran (les jours de bobo)
  { const tape = std(0xeec9a1, .8), g = G(new THREE.BoxGeometry(.36, .1, .014));
    [-1, 1].forEach(sd => { const b = mesh(g, tape, bandage); b.rotation.z = sd * .6; }); stick(bandage, -.62, .56, .02); }
  [crown, topHat, partyHat, bowTie, headset, glasses, bandage].forEach(o => { o.visible = false; head.add(o); });
  const OUT_Y = {crown: .8, top: .86};
  crown.position.set(-.02, OUT_Y.crown, 0); crown.rotation.set(.06, 0, .12);
  topHat.position.set(0, OUT_Y.top, 0); topHat.rotation.set(.04, 0, -.1);
  partyHat.position.set(.5, .76, .1); partyHat.rotation.z = -.45;
  stick(bowTie, 0, -.64, .03);

  // ---------- gouttes de sueur ----------
  const dropGeo = (() => { const pts = []; for (let i = 0; i <= 20; i++) { const a = i / 20 * Math.PI; pts.push(new THREE.Vector2(.5 * Math.sin(a) * Math.sin(a / 2) ** 1.2, .75 * Math.cos(a))); }
    return G(new THREE.LatheGeometry(pts, 16)); })();
  const dropMat = std(0x9fd8ff, .05, .1, {emissive: 0x2f8fd0, emissiveIntensity: .5, transparent: true, opacity: .9});
  const drops = Array.from({length: 6}, () => { const m = mesh(dropGeo, dropMat, head, 0, 0, 0, false); m.visible = false; return {m, t: 1, sd: 1, z: 0}; });
  let dropClock = 0;

  // ---------- mains ----------
  const handGeo = G(new THREE.SphereGeometry(.21, 28, 20));
  const hands = [0, 1].map(i => { const h = mesh(handGeo, shellMat, rig, i ? .5 : -.45, .3, 1.58); h.scale.set(1, .88, 1.06); h.userData.prevY = h.position.y; owned.push(h); return h; });
  const POSE = {key: [V(-.45, .3, 1.58), V(.5, .3, 1.58)], rest: [V(-1.02, .22, 1.45), V(.98, .22, 1.42)], up: [V(-1.42, 1.6, 1.3), V(1.48, 1.6, 1.3)]};
  const KEY_HIT = .335, HP = V(0, 0, 0);   // une main qui redescend sous cette hauteur au-dessus du clavier frappe une touche

  // ---------- téléphone : messages non lus => il le sort, le regarde, il vibre ; un coup d'œil vers nous de temps en temps ----------
  const PH = {k: 0, n: 0, buzzT: -1, nextBuzz: 0, glanceT: -1, nextGlance: 0, look: 0, glance: 0, lit: 0, shake: 0, drawn: -1, hand: V(0, 0, 0)};
  const phone = new THREE.Group(); phone.visible = false; rig.add(phone); owned.push(phone);
  const phCv = canvas(128, 224), phx = phCv.getContext("2d"), phTex = texOf(phCv, true), phMat = M(new THREE.MeshBasicMaterial({map: phTex, toneMapped: false}));
  { const w = .34, h = .6, r = .06, sh = new THREE.Shape(); sh.moveTo(-w / 2 + r, -h / 2); sh.lineTo(w / 2 - r, -h / 2); sh.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
    sh.lineTo(w / 2, h / 2 - r); sh.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2); sh.lineTo(-w / 2 + r, h / 2); sh.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
    sh.lineTo(-w / 2, -h / 2 + r); sh.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
    const g = new THREE.ExtrudeGeometry(sh, {depth: .035, bevelEnabled: true, bevelThickness: .008, bevelSize: .008, bevelSegments: 2, curveSegments: 8}); g.center();
    mesh(G(g), std(0x23262c, .45, .2), phone);
    mesh(G(new THREE.PlaneGeometry(.29, .52)), phMat, phone, 0, 0, .027, false); }
  const PH0 = V(1.55, -.35, 1.9);
  function drawPhone(n) {
    const c = phx; PH.drawn = n;
    c.fillStyle = "#0b1016"; c.fillRect(0, 0, 128, 224);
    c.fillStyle = "#1b2633"; rr(c, 10, 74, 108, 86, 12); c.fill();
    c.fillStyle = "#7df9ff"; c.beginPath(); c.ellipse(34, 100, 15, 11, 0, 0, Math.PI * 2); c.fill();   // bulle de discussion
    c.beginPath(); c.moveTo(26, 108); c.lineTo(22, 118); c.lineTo(34, 110); c.fill();
    c.fillStyle = "#ffb648"; c.beginPath(); c.arc(104, 76, 15, 0, Math.PI * 2); c.fill();
    c.fillStyle = "#1b1206"; c.textAlign = "center"; c.font = "700 " + (n > 9 ? 13 : 17) + "px 'Chakra Petch', sans-serif"; c.fillText(n > 99 ? "99+" : String(n), 104, n > 9 ? 81 : 82);
    c.textAlign = "left"; c.fillStyle = "#e8eef4"; c.font = "600 16px 'Chakra Petch', sans-serif"; c.fillText(n > 1 ? n + " messages" : "1 message", 20, 138);
    c.fillStyle = "#8aa0b4"; c.font = "500 13px sans-serif"; c.fillText(n > 1 ? "non lus" : "non lu", 20, 153);
    phTex.needsUpdate = true;
  }
  function phoneStep(dt, now, alive, hatching, S) {
    const n = S.unread | 0, want = alive && !hatching && !S.chatOpen && n > 0 ? 1 : 0;
    if (n > PH.n && want) { PH.buzzT = 0; PH.nextBuzz = 3.4; PH.nextGlance = 4 + Math.random() * 3; buzz(12); }
    PH.n = n;
    const d = want - PH.k; if (d) { const mv = RM.matches ? 1 : dt / (want ? .85 : .55); PH.k = Math.abs(d) <= mv ? want : PH.k + Math.sign(d) * mv; }
    if (PH.k <= 0) { phone.visible = false; PH.look = PH.glance = PH.shake = PH.lit = 0; PH.buzzT = PH.glanceT = -1; return; }
    const e = sm(PH.k);
    if (PH.k >= 1) { PH.nextBuzz -= dt; if (PH.nextBuzz <= 0 && PH.buzzT < 0) { PH.buzzT = 0; PH.nextBuzz = 3.2 + Math.random() * 1.2; } }   // une petite salve toutes les 3-4 s
    let env = 0; if (PH.buzzT >= 0) { PH.buzzT += dt; if (PH.buzzT > .5) PH.buzzT = -1; else env = Math.sin(PH.buzzT / .5 * Math.PI); }
    PH.shake = RM.matches ? 0 : env;
    if (PH.k >= 1) { PH.nextGlance -= dt; if (PH.nextGlance <= 0 && PH.glanceT < 0) { PH.glanceT = 0; PH.nextGlance = 6 + Math.random() * 4; } }
    if (PH.glanceT >= 0) { PH.glanceT += dt; if (PH.glanceT > 1.5) PH.glanceT = -1; }
    PH.glance = lerp(PH.glance, PH.glanceT >= 0 ? Math.sin(Math.min(1, PH.glanceT / 1.5) * Math.PI) : 0, ease(10, dt));
    PH.look = e * (1 - PH.glance * .92);
    PH.lit = lerp(PH.lit, Math.min(1, PH.k * 1.4) * (.6 + .4 * env), ease(12, dt));
    phMat.color.setScalar(.25 + .75 * PH.lit);
    if (PH.drawn !== n) drawPhone(n);
    const hp = head.position, hx = hp.x + 1.05, hy = hp.y - .38, hz = 2.0, s = now / 1000;   // de sous le bureau jusqu'à côté de l'écran, en arc
    PH.hand.set(lerp(PH0.x, hx, e), lerp(PH0.y, hy, e) + Math.sin(e * Math.PI) * .14, lerp(PH0.z, hz, e));
    if (PH.k >= 1) { PH.hand.x += Math.sin(s * 1.1) * .012; PH.hand.y += Math.sin(s * 1.7) * .014 - PH.glance * .08; }
    PH.hand.x += Math.sin(s * 90) * .014 * PH.shake; PH.hand.y += Math.sin(s * 77) * .01 * PH.shake;
    phone.visible = true;
  }
  function phonePlace(now) {
    if (!phone.visible) return;
    const h = hands[1].position, e = sm(PH.k);
    phone.position.set(h.x - .1, h.y + .34, h.z + .1);
    phone.rotation.set(-.1, -.75 + (1 - e) * .5, .08 + Math.sin(now / 1000 * 55) * .05 * PH.shake);
    phone.scale.setScalar((.55 + .45 * e) * 1.3);
  }

  // ---------- tasse (posée au montage) : gorgée = la main l'apporte devant la bouche, l'écran affiche une pile qui se recharge ----------
  const MUG = {t: -1, T: 4.4, hand: V(0, 0, 0), g: null, x0: 1.42, z0: 1.25};
  function mugStep(dt) {
    const mug = MUG.g; if (!mug || MUG.t < 0) return;
    MUG.t += dt; const t = MUG.t, hp = head.position;
    if (t > MUG.T || hatchT >= 0) { MUG.t = -1; mug.position.set(MUG.x0, 0, MUG.z0); mug.rotation.set(0, 0, 0); return; }
    const up = seg(t, .7, 1.6) - seg(t, 2.9, 3.8), tilt = (seg(t, 1.6, 1.9) - seg(t, 2.6, 2.9)) * -.55;
    mug.position.set(lerp(MUG.x0, hp.x + .1, up), lerp(0, hp.y - .5, up), lerp(MUG.z0, hp.z + .96, up));
    mug.rotation.set(tilt, -up * .4, 0);
    const reach = seg(t, 0, .7) * (1 - seg(t, 3.8, 4.3));
    MUG.hand.set(mug.position.x + .24, mug.position.y + .16 + (1 - reach) * .25, mug.position.z + .04 + (1 - reach) * .15);
  }

  // ---------- scène de mort et de relève : panne, écran qui s'éteint, un rayon l'aspire ; le remplaçant descend et démarre ----------
  const beam = new THREE.Group(); beam.visible = false; rig.add(beam); owned.push(beam);
  const BH = 4.6;
  const beamTex = (() => { const c = canvas(64, 128), x = c.getContext("2d");
    for (let i = 0; i < 64; i++) { const v = .55 + .45 * Math.sin(i / 64 * Math.PI * 6) ** 2; x.fillStyle = `rgba(255,255,255,${v})`; x.fillRect(i, 0, 1, 128); }
    const g = x.createLinearGradient(0, 0, 0, 128); g.addColorStop(0, "rgba(0,0,0,1)"); g.addColorStop(.25, "rgba(0,0,0,0)"); g.addColorStop(.85, "rgba(0,0,0,.15)"); g.addColorStop(1, "rgba(0,0,0,.6)");
    x.fillStyle = g; x.fillRect(0, 0, 64, 128); const t = texOf(c); t.wrapS = THREE.RepeatWrapping; return t; })();
  const beamMat = M(new THREE.MeshBasicMaterial({color: 0xbff8ff, alphaMap: beamTex, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide, toneMapped: false}));
  { const g = new THREE.CylinderGeometry(.62, .92, BH, 40, 1, true); g.translate(0, -BH / 2, 0); mesh(G(g), beamMat, beam, 0, 0, 0, false); }   // pivot en haut : il descend du plafond
  const glowMat = M(new THREE.MeshBasicMaterial({color: 0xbff8ff, transparent: true, opacity: 0, depthWrite: false, toneMapped: false,
    map: (() => { const c = canvas(64, 64), x = c.getContext("2d"), g = x.createRadialGradient(32, 32, 2, 32, 32, 32); g.addColorStop(0, "#fff"); g.addColorStop(1, "rgba(255,255,255,0)"); x.fillStyle = g; x.fillRect(0, 0, 64, 64); return texOf(c); })()}));
  const glow = mesh(G(new THREE.CircleGeometry(1.05, 40)), glowMat, rig, HEAD.x, .015, HEAD.z, false); glow.rotation.x = -Math.PI / 2; glow.visible = false; owned.push(glow);
  const sparkMat = M(new THREE.MeshBasicMaterial({color: 0xe8fdff, transparent: true, opacity: .9, depthWrite: false, toneMapped: false}));
  const sparkGeo = G(new THREE.OctahedronGeometry(.05));
  const sparks = Array.from({length: 10}, (_, i) => { const m = mesh(sparkGeo, sparkMat, beam, 0, 0, 0, false); m.userData = {a: i * 2.4, r: .25 + (i % 3) * .14, s: .7 + (i % 4) * .2}; return m; });
  beam.position.set(HEAD.x, BH, HEAD.z);
  const HF = {off: false, rise: false, land: false, boot: false, talk: false};

  // ---------- état du personnage ----------
  let hatchT = -1, partyUntil = 0, emoteK = null, emoteUntil = 0, yawnT = 0, yawnNext = 100 + Math.random() * 120, prevAct = "", lastAlive = true;
  let fearNow = 0, tiredNow = 0, hungryNow = 0, gladNow = 0, sadNow = 0, caressNow = 0, boopK = 0, shadesK = 0, deadK = 0, screenK = 1, bulbI = 1;
  let blinkT = 0, nextBlink = 2, eyeX = 0, eyeY = 0, eyeTX = 0, eyeTY = 0, nextSacc = 0, mouthNow = .1, faceAt = 0, faceDirty = true, gone = false;
  const F = new Float32Array(20), F1 = new Float32Array(20);   // paramètres du visage (quantifiés) : on ne redessine que s'ils changent
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { faceDirty = true; PH.drawn = -1; }).catch(() => {});

  function hatch() { hatchT = 0; for (const k in HF) HF[k] = false; MUG.t = MUG.t >= 0 ? MUG.T + 1 : -1; }
  function emote(kind) {
    const n = performance.now();
    if (kind === "wow" || kind === "ouch") { window.__react = {kind, dur: 1600, until: n + 1600}; sfx(kind === "wow" ? "ching" : "bonk"); return; }
    if (kind === "boop") { window.__react = {kind, dur: 1300, until: n + 1300}; sfx("boop"); if (window.talk) window.talk(pick(BOOP)); return; }
    if (kind === "yawn") { yawnT = 2.6; return; }
    if (kind === "hatch") { hatch(); return; }
    if (kind === "talk") { if (window.talk) window.talk(pick(TALK)); return; }
    if (!DUR[kind]) return;   // émote inconnue : ignorée
    emoteK = kind; emoteUntil = n + DUR[kind];
    if (kind === "dance") sfx("fanfare");
  }

  // ---------- chaque image : corps, tenues, téléphone, regard, scène de mort, antenne, visage, sueur ----------
  function update(dt, now, t, S) {
    let act = S.act, win = S.win, danger = S.danger; const alive = S.alive, talking = S.talking; lastAlive = alive;
    // émote en cours (bouton 🎭) : elle prend le dessus quelques secondes
    const em = alive && now < emoteUntil ? emoteK : null;
    if (em === "dance") win = true;
    if (em === "panic") { danger = true; if (act === "sleeping") act = "watching"; }
    if (em === "sleep") act = "sleeping";
    if (em === "think" || em === "type") act = "thinking";
    const task = act === "thinking" ? (em === "think" ? "pense" : em === "type" ? "code" : S.task || "pense") : "";
    S.act = act; S.win = win; S.danger = danger; S.em = em; S.task = task;   // état résolu : la scène s'en sert (écrans, confettis)
    const sleeping = act === "sleeping", OF = S.outfit || NO, TM = S.tama || NO, hatching = hatchT >= 0;
    // humeur lissée (peur, fatigue, faim, bonne ou mauvaise humeur, caresse)
    fearNow = lerp(fearNow, alive ? Math.max(danger ? .85 : 0, +S.fear || 0) : 0, ease(1.5, dt));
    tiredNow = lerp(tiredNow, alive && TM.energy != null ? clamp((.45 - TM.energy) / .35, 0, 1) : 0, ease(1.2, dt));
    hungryNow = lerp(hungryNow, alive && TM.hunger != null ? clamp((.3 - TM.hunger) / .25, 0, 1) : 0, ease(1.2, dt));
    gladNow = lerp(gladNow, alive && TM.mood != null ? clamp((TM.mood - .55) / .35, 0, 1) : 0, ease(1.2, dt));
    sadNow = lerp(sadNow, alive && TM.mood != null ? clamp((.3 - TM.mood) / .25, 0, 1) : 0, ease(1.2, dt));
    caressNow = lerp(caressNow, alive && S.caress ? 1 : 0, ease(8, dt));
    // corps : flottement, sommeil, petits bonds de victoire (danse robot), tremblements, réactions
    let x = HEAD.x, y = HEAD.y + Math.sin(t * 1.7) * .05, rz = 0, sx = 1, sy = 1, yawAdd = 0;
    if (sleeping) { const b = Math.sin(t * 1.1); y = HEAD.y - .12 + b * .025; rz = -.1; sy = 1 + b * .02; sx = 1 - b * .01; }
    if (act === "dead") { y = HEAD.y - .3; rz = .5; }
    if (win) { const h = Math.abs(Math.sin(t * 4.6)), c = Math.min(1, h * 1.8); y = HEAD.y + h * .34; sy = .84 + .2 * c; sx = 1.1 - .1 * c;
      if (em === "dance") { yawAdd = Math.sin(t * 2.3) > 0 ? .32 : -.32; rz += Math.sin(t * 2.3) * .1; } }   // danse robot : la tête claque d'un côté à l'autre
    if (danger) { x += Math.sin(t * 15) * .028 + Math.sin(t * 27) * .01; rz += Math.sin(t * 12) * .04; }
    const R = window.__react, react = alive && R && R.until > now ? R.kind : null, rk = react ? clamp((R.until - now) / R.dur, 0, 1) : 0;
    if (react === "wow") y += Math.sin((1 - rk) * Math.PI) * .25;
    if (react === "ouch") { x += Math.sin(t * 31) * .035 * rk; rz += Math.sin(t * 23) * .06 * rk; }
    boopK = react === "boop" ? rk : Math.max(0, boopK - dt * 4);
    if (boopK > 0) { const b = Math.sin((1 - boopK) * Math.PI * 3) * boopK; sy *= 1 - .18 * b; sx *= 1 + .12 * b; }
    // bâillement : en s'endormant, et de temps en temps quand il s'ennuie à l'affût
    if (prevAct && prevAct !== act && sleeping) yawnT = 2.6;
    prevAct = act;
    if (act === "watching" && !talking) { yawnNext -= dt; if (yawnNext <= 0) { yawnT = 2.6; yawnNext = 100 + Math.random() * 140; } }
    yawnT = alive && !react ? Math.max(0, yawnT - dt) : 0;
    const yawn = yawnT > 0 ? Math.sin((1 - yawnT / 2.6) * Math.PI) ** .7 : 0;
    sy *= 1 + yawn * .08; sx *= 1 - yawn * .02;
    if (alive && !sleeping) { const br = Math.sin(t * (1.5 + tiredNow * 1.5)); sy *= 1 + br * (.01 + .012 * tiredNow); }
    if (alive && !win) { y += -(tiredNow * .09 + hungryNow * .05 + sadNow * .05) + gladNow * (Math.sin(t * 2.4) * .5 + .5) * .03; rz += sadNow * .05; x += Math.sin(t * 21) * .007 * hungryNow; }
    if (caressNow > .01) { rz += Math.sin(t * 5) * .06 * caressNow; y -= .03 * caressNow; sx *= 1 + .03 * caressNow; sy *= 1 - .03 * caressNow; }
    head.position.set(lerp(head.position.x, x, ease(14, dt)), lerp(head.position.y, y, ease(12, dt)), HEAD.z);
    head.scale.set(lerp(head.scale.x, sx * HS, ease(16, dt)), lerp(head.scale.y, sy * HS, ease(16, dt)), lerp(head.scale.z, sx * HS, ease(16, dt)));
    // tenues
    crown.visible = alive && (OF.hat === "crown" || (!OF.hat && !!S.crown));
    topHat.visible = OF.hat === "top"; partyHat.visible = OF.hat === "party";
    headset.visible = OF.ear === "headset"; bowTie.visible = OF.neck === "bow"; bandage.visible = alive && !!S.bandage;
    shadesK = alive && (S.shades || em === "shades" || OF.glasses === "pixel") ? Math.min(1, shadesK + dt / .9) : 0;
    glasses.visible = alive && OF.glasses === "round" && shadesK <= 0;
    { const up = headset.visible ? .12 : 0; topHat.position.y = OUT_Y.top + up; crown.position.y = OUT_Y.crown + up; partyHat.position.z = headset.visible ? .2 : .1; }
    phoneStep(dt, now, alive, hatching, S);
    // regard : la tête suit le pointeur / les écrans ; il lit en balayant ; il dort la tête basse ; il regarde son téléphone
    // (un écran plat se lit mal de profil : la tête tourne moins que celle de RedRock, les yeux font le reste)
    const lk = S.look || NO, atScreen = act === "trading" || act === "watching" || (task && task !== "pense");
    let yaw = alive ? clamp(Math.asin(clamp((lk.x || 0) / 565, -.9, .9)) * (atScreen ? 1.7 : 1.3), -.75, .75) : 0;
    if (task === "compte" || task === "news") yaw += Math.sin(t * 1.6) * .1;
    if (task === "jev") rz += Math.sin(t * 1.3) * .09;   // curieux : tête qui penche
    let pitch = alive ? clamp(Math.asin(clamp((lk.y || 0) / 565, -.9, .9)) * 1.1, -.5, .4) - yawn * .3 : .25;
    if (alive && sleeping) { yaw = Math.sin(t * .23) * .05; pitch = .22 + Math.sin(t * 1.1) * .04 - yawn * .35; }
    yaw += yawAdd;
    if (PH.look > .001) { yaw = lerp(yaw, .42, PH.look); pitch = lerp(pitch, .24, PH.look); rz -= .06 * PH.look; }
    const sip = MUG.t >= 0 ? seg(MUG.t, 1.2, 1.8) * (1 - seg(MUG.t, 2.9, 3.4)) : 0;
    if (sip) { yaw = lerp(yaw, .05, sip); pitch = lerp(pitch, -.12, sip); }
    head.rotation.set(lerp(head.rotation.x, pitch, ease(5, dt)), lerp(head.rotation.y, yaw, ease(em === "dance" ? 11 : 5, dt)), lerp(head.rotation.z, rz, ease(8, dt)));

    // scène de mort et de relève (elle écrase la pose ci-dessus) : visage forcé, antenne éteinte
    let hMode = -1, hK = 0, antOff = !alive;
    head.visible = true;
    if (hatchT >= 0) {
      hatchT += dt; const T = hatchT;
      if (T < 1.9) {   // panne : il grésille, yeux en croix, il s'affaisse ; l'écran s'éteint comme une vieille télé
        const sag = seg(T, .35, 1.3);
        head.position.x = x + (T < .4 ? Math.sin(T * 60) * .03 : 0); head.position.y = y - .22 * sag; head.rotation.z = .42 * sag; head.rotation.x = .3 * sag;
        hMode = T < .35 ? E_GLITCH : T < 1.25 ? E_X : E_CRT; hK = clamp((T - 1.25) / .5, 0, 1); antOff = T > .35;
        if (!HF.off && T > .35) { HF.off = true; sfx("off"); buzz([30, 40, 30]); }
      } else if (T < 3.1) {   // un rayon descend et l'aspire en tournant
        const k = seg(T, 2.1, 3.0);
        head.position.y = y - .22 + k * k * 2.6; head.rotation.set(.3 * (1 - k), k * 6, .42 * (1 - k)); head.scale.setScalar(HS * Math.max(.0001, 1 - k));
        hMode = E_BLACK; antOff = true;
      } else if (T < 4.3) { head.visible = false; hMode = E_BLACK; antOff = true; }
      else if (T < 5.1) {   // le remplaçant descend dans le rayon
        const d = (T - 4.3) / .8, e = 1 - (1 - d) ** 3;
        head.position.set(HEAD.x, HEAD.y + (1 - e) * 2.8, HEAD.z); head.rotation.set(0, (1 - e) * -4, 0); head.scale.setScalar(HS * (.55 + .45 * e));
        hMode = E_BLACK; antOff = true;
        if (!HF.rise) { HF.rise = true; sfx("rise"); }
      } else {   // il atterrit (écrasement élastique), démarre (BOOT, numéro de génération), puis ouvre les yeux
        const k = T - 5.1, b = Math.exp(-k * 6) * Math.cos(k * 17);
        head.position.set(HEAD.x, HEAD.y - .06 * b, HEAD.z); head.rotation.set(0, 0, 0); head.scale.set(HS * (1 + .14 * b), HS * (1 - .18 * b), HS * (1 + .14 * b));
        if (k < 1.5) { hMode = E_BOOT; hK = k / 1.5; }
        if (!HF.land) { HF.land = true; sfx("pop"); buzz([20, 30, 40]); partyUntil = now + 1800; }
        if (!HF.boot && k > 1.5) { HF.boot = true; sfx("ding"); blinkT = .16; }
      }
      // le rayon : il descend du plafond à 1,9 s, s'efface après l'atterrissage
      const bo = seg(T, 1.9, 2.25) * (1 - seg(T, 5.3, 5.9));
      beam.visible = glow.visible = bo > 0; beam.scale.set(1, Math.max(.0001, seg(T, 1.9, 2.3)), 1);
      beamMat.opacity = .42 * bo; glowMat.opacity = .7 * bo; beamTex.offset.x = (T * .35) % 1;
      for (let i = 0; i < sparks.length; i++) { const s = sparks[i], u = s.userData, ph = (T * .45 * u.s + i / sparks.length) % 1, a = u.a + T * 2.2;
        s.visible = T > 2.0 && T < 5.2; s.position.set(Math.cos(a) * u.r, -BH + ph * BH * .85, Math.sin(a) * u.r); s.rotation.y = a * 2; s.scale.setScalar(Math.sin(ph * Math.PI)); }
      if (T > 6.6 && !HF.talk) { HF.talk = true; if (window.talk) window.talk("Système rallumé. Je prends le relais."); if (window.__emote) window.__emote("wow"); }
      if (T > 7.4) { hatchT = -1; beam.visible = glow.visible = false; }
    }

    // coque grisée quand il est mort, écran plus sombre quand il dort
    deadK = lerp(deadK, !alive && hMode < 0 ? 1 : 0, ease(3, dt));
    shellMat.color.lerpColors(CREAM, DEADC, deadK);
    screenK = lerp(screenK, !alive ? .6 : sleeping ? .55 : 1, ease(4, dt));
    screenMat.color.setScalar(screenK);
    // antenne : couleur selon l'humeur, et elle ballotte (ressort) quand la tête accélère
    let ai = .9 + .25 * Math.sin(t * 2); C_TMP.copy(C_AMBER);
    if (antOff) ai = 0;
    else if (hMode === E_BOOT) { C_TMP.copy(C_GREEN); ai = (t * 4 % 1) < .5 ? 1.6 : .3; }
    else if (react === "ouch") { C_TMP.copy(C_RED); ai = 1.8; }
    else if (react === "wow") { C_TMP.copy(C_GOLD); ai = 1.8; }
    else if (danger) { C_TMP.copy(C_RED); ai = Math.sin(t * 14) > 0 ? 1.8 : .3; }
    else if (win) { C_TMP.setHSL(t * .5 % 1, .9, .6); ai = 1.6; }
    else if (sleeping) { C_TMP.copy(C_BLUE); ai = .25 + .2 * Math.sin(t * 1.1); }
    else if (act === "thinking") { C_TMP.copy(C_CYAN); ai = (t * 2.2 % 1) < .5 ? 1.4 : .35; }
    else if (act === "trading") { C_TMP.copy(C_GREEN); ai = .8 + .45 * Math.sin(t * 3); }
    if (!antOff && PH.shake > .05) ai += PH.shake * 1.2;                 // il clignote avec les vibrations du téléphone
    if (!antOff && talking) ai += mouthNow * .8;                         // et quand il parle
    BULB.lerp(C_TMP, ease(8, dt)); bulbI = lerp(bulbI, ai, ease(antOff ? 6 : 14, dt));
    bulbMat.emissive.copy(BULB); bulbMat.emissiveIntensity = bulbI;
    if (!AS.init || hatching) { AS.init = true; AS.px = head.position.x; AS.py = head.position.y; AS.pvx = AS.pvy = 0; }
    if (dt > 0 && !hatching) {
      const vx = (head.position.x - AS.px) / dt, vy = (head.position.y - AS.py) / dt, ax = (vx - AS.pvx) / dt, ay = (vy - AS.pvy) / dt;
      AS.px = head.position.x; AS.py = head.position.y; AS.pvx = vx; AS.pvy = vy;
      const droop = !alive ? .9 : sleeping ? .3 : tiredNow * .3, tz = clamp(-ax * .012, -.6, .6) + droop, tx = clamp(ay * .004, -.45, .45);
      if (RM.matches) { AS.z = tz; AS.x = tx; AS.vz = AS.vx = 0; }
      else { const h = Math.min(dt, .05); AS.vz += (-(AS.z - tz) * 150 - AS.vz * 6) * h; AS.z += AS.vz * h; AS.vx += (-(AS.x - tx) * 150 - AS.vx * 6) * h; AS.x += AS.vx * h; }
    }
    ant.rotation.set(AS.x, 0, AS.z);

    // ---------- visage ----------
    nextBlink -= dt; if (nextBlink <= 0) { blinkT = .16; nextBlink = Math.random() < .18 ? .3 : (danger ? .9 : 2.5) + Math.random() * (danger ? 1.2 : 3.5); }   // parfois un double clignement
    blinkT = Math.max(0, blinkT - dt);
    const blink = blinkT > 0 ? Math.abs(blinkT / .08 - 1) * .92 + .08 : 1;
    // synchro labiale : l'égaliseur de la bouche suit les lettres de sa bulle (voyelles ouvertes, m/b/p fermées, pauses)
    const say = window.__say, si = say && say.text ? Math.floor((now - say.t0) / 62) : -1, speaking = talking && alive && si >= 0 && si < say.text.length;
    let mT = .1;
    if (speaking) { const ch = say.text.charAt(si).toLowerCase();
      mT = "aàâoô".includes(ch) ? 1 : "eéèêëiîïuùûy".includes(ch) ? .72 : "mbp".includes(ch) ? .06 : ".,!?…:;".includes(ch) ? .04 : ch === " " ? .22 : .45; }
    mouthNow = lerp(mouthNow, mT, ease(speaking ? 24 : 8, dt));
    // regard : il lit les lignes de l'écran (compte, news, code), lève les yeux quand il pense, sinon petits mouvements naturels
    if (task === "compte" || task === "news" || task === "code") { const ph = (t % 1.2) / 1.2; eyeTX = ph > .88 ? -20 : -20 + ph / .88 * 40; eyeTY = -12 + (Math.floor(t / 1.2) % 3) * 8; }
    else if (task === "ordre") { eyeTX = 0; eyeTY = -4; }
    else if (task === "pense") { eyeTX = 16 + Math.sin(t * .9) * 4; eyeTY = -15; }
    else { nextSacc -= dt; if (nextSacc <= 0) { nextSacc = .4 + Math.random() * 1.8; eyeTX = (Math.random() * 2 - 1) * 14; eyeTY = (Math.random() * 2 - 1) * 8; } }
    let tx = eyeTX + clamp((lk.x || 0) * .05, -10, 10), ty = eyeTY + clamp((lk.y || 0) * .045, -12, 8);   // les yeux suivent aussi le regard
    if (PH.look > .001) { tx = lerp(tx, 22, PH.look); ty = lerp(ty, 12, PH.look); }
    eyeX = lerp(eyeX, tx, ease(26, dt)); eyeY = lerp(eyeY, ty, ease(26, dt));
    let mode = !alive ? E_X : sleeping ? E_CLOSED : win ? E_HAPPY : E_OPEN, mouth = !alive ? M_FLAT : sleeping ? M_SLEEP : win ? M_GRIN : M_SMILE, mo = !alive ? 0 : sleeping ? .5 + .5 * Math.sin(t * 1.1) : win ? 1 : gladNow;
    let brow = alive ? Math.max(fearNow, sadNow * .5, tiredNow * .25) : 0, size = 1 - fearNow * .28, lid = alive ? tiredNow * .38 : 0, phase = 0, blush = alive && (S.content || gladNow > .6) ? .7 : 0, heart = 0;
    if (alive) {
      if (danger && !speaking) { mouth = M_WAVE; phase = Math.floor(t * 10) % 64; }
      if (task === "pense") { mouth = M_DOTS; phase = Math.floor(t * 3) % 3; }
      if (task === "ordre") { brow = -.8; lid = Math.max(lid, .28); }
      if (yawn > 0) { mouth = M_YAWN; mo = yawn; if (yawn > .45) mode = E_CLOSED; }
      if (caressNow > .4 && !sleeping && !react) { mode = E_HAPPY; mouth = M_GRIN; mo = .5; blush = 1; heart = 1; }
      if (react === "wow") { mode = E_WIDE; mouth = M_O; mo = Math.min(1, (1 - rk) * 5) * Math.min(1, rk * 6); }
      if (react === "ouch") { mode = E_SQUINT; mouth = M_ZIG; }
      if (react === "boop") { mode = rk > .5 ? E_SQUINT : E_HAPPY; mouth = M_GRIN; mo = .7; blush = 1; }
      if (shadesK > 0 && mouth === M_SMILE) mouth = M_SMIRK;
      if (sip > .2) { mode = E_HAPPY; mouth = M_BATT; mo = seg(MUG.t, 1.6, 2.9); }
      if (speaking) { mouth = M_BARS; mo = mouthNow; phase = si % 64; }
    }
    if (hMode >= 0) { mode = hMode; mouth = M_FLAT; mo = 0; blush = heart = 0; }
    // couleur des yeux : cyan ; violet avec la peur ; corail en danger ; or quand il gagne ; rouge éteint s'il est mort
    let cr = 125, cg = 249, cb = 255;
    if (!alive && hMode < 0) { cr = 150; cg = 70; cb = 70; }
    else if (danger) { cr = 255; cg = 128; cb = 96; }
    else if (win || mode === E_BOOT) { cr = 255; cg = 214; cb = 92; }
    else if (fearNow > .02) { cr = lerp(125, 190, fearNow); cg = lerp(249, 160, fearNow); cb = 255; }
    const free = mode === E_OPEN || mode === E_WIDE;
    const N = F1;
    N[0] = mode; N[1] = Math.round(blink * 8) / 8; N[2] = free ? Math.round(eyeX / 2) * 2 : 0; N[3] = free ? Math.round(eyeY / 2) * 2 : 0;
    N[4] = Math.round(size * 20) / 20; N[5] = Math.round(lid * 10) / 10; N[6] = Math.round(brow * 10) / 10; N[7] = mouth; N[8] = Math.round(mo * 12) / 12;
    N[9] = Math.round(cr / 8) * 8; N[10] = Math.round(cg / 8) * 8; N[11] = Math.round(cb / 8) * 8; N[12] = blush; N[13] = heart;
    N[14] = shadesK > 0 ? Math.round(-(1 - bounce(shadesK)) * 150 / 4) * 4 : -999; N[15] = phase;
    N[16] = hMode === E_CRT || hMode === E_BOOT ? Math.round(hK * 40) / 40 : hMode === E_GLITCH ? Math.floor(t * 20) : 0;
    N[17] = alive && hungryNow > .5 ? (Math.floor(t * 1.5) % 2) : 0; N[18] = Math.round(fearNow * 10) / 10; N[19] = S.generation || 1;
    let changed = faceDirty; for (let i = 0; i < 20 && !changed; i++) if (N[i] !== F[i]) changed = true;
    if (changed && (now - faceAt > 33 || N[0] !== F[0] || faceDirty)) { F.set(N); faceAt = now; faceDirty = false; drawFace(); }

    // sueur
    const every = !alive ? 0 : danger ? .75 : fearNow > .45 ? 2.2 : 0;
    if (every && !sleeping && hMode < 0) { dropClock += dt; if (dropClock > every) { dropClock = 0; spawnDrop(); } }
    updateDrops(dt);
  }
  const bounce = x => { const n = 7.5625, d = 2.75;   // rebond des lunettes pixel qui tombent
    return x < 1 / d ? n * x * x : x < 2 / d ? n * (x -= 1.5 / d) * x + .75 : x < 2.5 / d ? n * (x -= 2.25 / d) * x + .9375 : n * (x -= 2.625 / d) * x + .984375; };

  function spawnDrop() { for (const d of drops) if (d.t >= 1) { d.t = 0; d.sd = Math.random() < .5 ? -1 : 1; d.z = .2 + Math.random() * .25; d.m.visible = true; return; } }
  function updateDrops(dt) {
    for (const d of drops) {
      if (d.t >= 1) continue;
      d.t = Math.min(1, d.t + dt / 2.2); const t = d.t, m = d.m;
      const yy = t < .2 ? .62 : lerp(.62, -.15, Math.min(1, (t - .2) / .5)), xx = A * Math.pow(Math.max(0, 1 - Math.abs(yy / B) ** P - (d.z / C) ** P), 1 / P) + .03;   // glisse le long du flanc
      m.position.set(d.sd * xx, yy, d.z);
      if (t > .7) { const f = (t - .7) / .3; m.position.y -= f * f * 1.3; m.position.x += d.sd * f * .12; }
      m.scale.setScalar(.14 * Math.min(1, t / .15) * (t > .8 ? (1 - t) / .2 : 1));
      if (t >= 1) m.visible = false;
    }
  }

  // le visage, peint d'après F (voir update) : fond de l'écran, yeux, sourcils, bouche, joues, accessoires
  function drawFace() {
    const c = fx, f = F, mode = f[0];
    c.globalAlpha = 1; c.shadowBlur = 0; c.drawImage(bgCv, 0, 0);
    if (mode === E_BLACK) { c.fillStyle = "#020304"; c.fillRect(0, 0, FCW, FCH); c.globalAlpha = .35; c.drawImage(bgCv, 0, 0); c.globalAlpha = 1; faceTex.needsUpdate = true; return; }   // écran éteint : verre sombre
    const col = "rgb(" + f[9] + "," + f[10] + "," + f[11] + ")";
    c.fillStyle = c.strokeStyle = c.shadowColor = col; c.lineCap = c.lineJoin = "round";
    if (mode === E_CRT) {   // extinction façon vieille télé : un trait, puis un point, puis le noir
      const k = f[16]; c.fillStyle = "#020304"; c.fillRect(0, 0, FCW, FCH); c.fillStyle = "#e8fdff"; c.shadowColor = "#7df9ff"; c.shadowBlur = 18;
      if (k < .55) { const h = Math.max(3, FCH * (1 - k / .55) ** 2), w = FCW * (1 - k * .5); c.fillRect(CX - w / 2, FCH / 2 - h / 2, w, h); }
      else if (k < 1) { c.beginPath(); c.arc(CX, FCH / 2, 9 * (1 - (k - .55) / .45) + .5, 0, Math.PI * 2); c.fill(); }
      faceTex.needsUpdate = true; return;
    }
    if (mode === E_BOOT) {   // démarrage du remplaçant : BOOT et barre de progression, puis sa génération
      const k = f[16]; c.shadowBlur = 12; c.textAlign = "center";
      if (k < .6) { c.font = "700 34px 'Chakra Petch', sans-serif"; c.fillText("BOOT", CX, 92); c.lineWidth = 4; rr(c, CX - 90, 118, 180, 22, 11); c.stroke();
        const w = 172 * Math.min(1, k / .55); if (w > 4) { rr(c, CX - 86, 122, w, 14, 7); c.fill(); } }
      else { c.font = "700 46px 'Chakra Petch', sans-serif"; c.fillText("GÉN. " + f[19], CX, 132); }
      faceTex.needsUpdate = true; return;
    }
    if (f[18] > 0) { c.fillStyle = "rgba(120,90,255," + (f[18] * .2) + ")"; c.fillRect(0, 0, FCW, FCH); c.fillStyle = col; }   // la peur teinte l'écran
    const open = f[1], ex = f[2], ey = f[3], size = f[4], lid = f[5], brow = f[6], shaded = f[14] > -6;   // lunettes pixel posées : les yeux sont dessous
    let jx = 0; if (mode === E_GLITCH) jx = (Math.random() - .5) * 14;
    c.shadowBlur = 14;
    for (let i = 0; i < 2 && !shaded; i++) {
      const sd = i ? 1 : -1, x = CX + sd * EDX + ex + jx, y = EY + ey;
      c.lineWidth = 10;
      if (mode === E_OPEN || mode === E_GLITCH) {
        const w = 42 * size, full = 60 * size, h = Math.max(7, full * open), yc = y + (full - h) * .22;
        c.save(); if (lid > 0) { c.beginPath(); c.rect(x - 40, yc - h / 2 + lid * h, 80, h * 2); c.clip(); }
        rr(c, x - w / 2, yc - h / 2, w, h, Math.min(w, h) / 2); c.fill(); c.restore();
        if (h > 26 && lid < .3) { c.shadowBlur = 0; c.fillStyle = "#ffffff"; c.beginPath(); c.arc(x - w * .2, yc - h * .22, 5.5 * size, 0, Math.PI * 2); c.fill(); c.fillStyle = col; c.shadowBlur = 14; }
      } else if (mode === E_WIDE) {
        c.beginPath(); c.arc(x, y, 31 * size, 0, Math.PI * 2); c.fill();
        c.shadowBlur = 0; c.fillStyle = "#ffffff"; c.beginPath(); c.arc(x - 10, y - 10, 8, 0, Math.PI * 2); c.fill(); c.beginPath(); c.arc(x + 9, y + 9, 3.5, 0, Math.PI * 2); c.fill(); c.fillStyle = col; c.shadowBlur = 14;
      } else if (mode === E_HAPPY) { c.beginPath(); c.arc(x, y + 12, 23, Math.PI * 1.12, Math.PI * 1.88); c.stroke(); }
      else if (mode === E_CLOSED) { c.lineWidth = 8; c.beginPath(); c.arc(x, y - 10, 22, Math.PI * .14, Math.PI * .86); c.stroke(); }
      else if (mode === E_SQUINT) { c.beginPath(); c.moveTo(x + sd * 16, y - 18); c.lineTo(x - sd * 16, y); c.lineTo(x + sd * 16, y + 18); c.stroke(); }
      else if (mode === E_X) { c.beginPath(); c.moveTo(x - 17, y - 17); c.lineTo(x + 17, y + 17); c.moveTo(x + 17, y - 17); c.lineTo(x - 17, y + 17); c.stroke(); }
      if (Math.abs(brow) > .05 && (mode === E_OPEN || mode === E_WIDE)) {   // sourcils : inquiet (> 0, bout intérieur relevé) ou déterminé (< 0)
        const by = EY + ey * .5 - 30 * size - 20; c.lineWidth = 7; c.beginPath(); c.moveTo(x + sd * 24, by + 6 * brow); c.lineTo(x - sd * 22, by - 10 * brow); c.stroke(); }
    }
    // bouche
    const mo = f[8], mk = f[7]; c.lineWidth = 7;
    if (mk === M_SMILE) { c.beginPath(); c.arc(CX, MY - 24, 24 + mo * 6, Math.PI * .24, Math.PI * .76); c.stroke(); }
    else if (mk === M_SMIRK) { c.beginPath(); c.arc(CX + 8, MY - 22, 22, Math.PI * .2, Math.PI * .62); c.stroke(); }
    else if (mk === M_FLAT) { c.beginPath(); c.moveTo(CX - 20, MY - 2); c.lineTo(CX + 20, MY - 2); c.stroke(); }
    else if (mk === M_GRIN) { c.beginPath(); c.ellipse(CX, MY - 12, 30, 7 + 17 * mo, 0, 0, Math.PI); c.closePath(); c.fill(); }
    else if (mk === M_O) { c.beginPath(); c.ellipse(CX, MY - 4, 9 + 7 * mo, 11 + 9 * mo, 0, 0, Math.PI * 2); c.stroke(); }
    else if (mk === M_ZIG) { c.lineWidth = 6; c.beginPath(); c.moveTo(CX - 28, MY - 2); for (let k = 1; k <= 6; k++) c.lineTo(CX - 28 + k * 56 / 6, MY - 2 + (k % 2 ? -8 : 8)); c.stroke(); }
    else if (mk === M_WAVE) { c.lineWidth = 6; c.beginPath(); for (let k = 0; k <= 20; k++) { const xx = CX - 30 + k * 3, yy = MY - 2 + Math.sin(k / 20 * Math.PI * 3 + f[15]) * 6; k ? c.lineTo(xx, yy) : c.moveTo(xx, yy); } c.stroke(); }
    else if (mk === M_BARS) { for (let k = 0; k < 7; k++) { const env = 1 - Math.abs(k - 3) / 4.5, a = .45 + .55 * Math.abs(Math.sin(f[15] * 1.7 + k * 1.3)), h = 6 + mo * a * env * 38;
        rr(c, CX + (k - 3) * 13 - 3.5, MY - 4 - h / 2, 7, h, 3.5); c.fill(); } }
    else if (mk === M_YAWN) { c.beginPath(); c.ellipse(CX, MY - 6, 14 + 8 * mo, 6 + 24 * mo, 0, 0, Math.PI * 2); c.fill(); }
    else if (mk === M_SLEEP) { c.lineWidth = 6; c.beginPath(); c.ellipse(CX, MY - 4, 7 + 3 * mo, 4 + 3 * mo, 0, 0, Math.PI * 2); c.stroke(); }
    else if (mk === M_DOTS) { for (let k = 0; k < 3; k++) { c.globalAlpha = k === f[15] ? 1 : .4; c.beginPath(); c.arc(CX + (k - 1) * 20, MY - 4, k === f[15] ? 7 : 5.5, 0, Math.PI * 2); c.fill(); } c.globalAlpha = 1; }
    else if (mk === M_BATT) { c.lineWidth = 4; rr(c, CX - 26, MY - 18, 46, 26, 5); c.stroke(); c.fillRect(CX + 22, MY - 10, 5, 10); const w = 38 * mo; if (w > 1) c.fillRect(CX - 22, MY - 14, w, 18); }
    c.shadowBlur = 0;
    if (f[12] > 0) { c.fillStyle = "rgba(255,110,150," + (.5 * f[12]) + ")"; for (let i = 0; i < 2; i++) { c.beginPath(); c.ellipse(CX + (i ? 1 : -1) * 100, EY + 40, 17, 8, 0, 0, Math.PI * 2); c.fill(); } }
    if (f[13] > 0) { const hx = FCW - 52, hy = 34; c.fillStyle = "#ff7aa8"; c.shadowColor = "#ff7aa8"; c.shadowBlur = 10; c.beginPath(); c.moveTo(hx, hy + 12);
      c.bezierCurveTo(hx - 18, hy, hx - 12, hy - 14, hx, hy - 5); c.bezierCurveTo(hx + 12, hy - 14, hx + 18, hy, hx, hy + 12); c.fill(); c.shadowBlur = 0; }
    if (f[17] > 0) { c.strokeStyle = "#ff6b5e"; c.fillStyle = "#ff6b5e"; c.lineWidth = 3; rr(c, 22, 16, 30, 15, 3); c.stroke(); c.fillRect(52, 20, 3, 7); c.fillRect(25, 19, 7, 9); }   // pile faible : il a faim
    if (f[14] > -999) {   // lunettes pixel qui tombent du haut de l'écran
      const px = 8, x0 = CX - 27 * px / 2, y0 = EY - 24 + f[14];
      for (let r = 0; r < SHADES.length; r++) for (let k = 0; k < 27; k++) { const ch = SHADES[r].charCodeAt(k); if (ch === 46) continue; c.fillStyle = ch === 87 ? "#ffffff" : "#050505"; c.fillRect(x0 + k * px, y0 + r * px, px, px); }
    }
    if (mode === E_GLITCH) { for (let i = 0; i < 6; i++) { const y = Math.random() * FCH, h = 3 + Math.random() * 14; c.drawImage(faceCv, 0, y, FCW, h, (Math.random() - .5) * 40, y, FCW, h); }
      c.fillStyle = "rgba(255,60,200,.25)"; c.fillRect(0, Math.random() * FCH, FCW, 6); }
    faceTex.needsUpdate = true;
  }

  // ---------- mains : clavier (tape), souris (déplace, clique, molette), menton, joues (panique), en l'air (victoire), téléphone, tasse ----------
  const TP = V(0, 0, 0);
  function updateHands(dt, now, t, S) {
    const {act, task, alive, win, danger} = S, hatching = hatchT >= 0;
    const cheeks = alive && danger && act !== "trading";
    const typing = act === "trading" && (danger || Math.floor(t / 7) % 2 === 0);   // en trade : alterne clavier et souris
    const mouseMode = alive && !win && !cheeks && !typing && !hatching && task !== "code" && task !== "ordre" && task !== "pense" && act !== "sleeping";
    let wheel = 0, click = 0;
    if (mouseMode) {
      let tx = M0.x, tz = M0.z, per = 3;
      if (task === "marche") { const ph = (t * 60 % (SW - 28)) / (SW - 28); tx += -.15 + ph * .3; tz += Math.sin(t * 2.1) * .03; per = 1.6; }   // suit le curseur du graphique
      else if (task === "compte" || task === "news") { wheel = 1; per = 0; tx += Math.sin(t * .5) * .02; }                                  // fait défiler à la molette
      else if (task === "jev") { tx += Math.sin(t * 3.1) * .03; tz += Math.cos(t * 2.3) * .025; per = 2.2; }
      else { tx += Math.sin(t * .7) * .11 + Math.sin(t * 1.9) * .03; tz += Math.sin(t * 1.1) * .06; per = act === "watching" ? 4.2 : 2.8; }
      mouse.position.x = lerp(mouse.position.x, tx, ease(5, dt)); mouse.position.z = lerp(mouse.position.z, tz, ease(5, dt));
      mouse.rotation.y = lerp(mouse.rotation.y, (tx - mouse.position.x) * -1.2, ease(4, dt));
      click = per && (t % per) / per < .06 ? 1 : 0;
    } else { mouse.position.x = lerp(mouse.position.x, M0.x, ease(2, dt)); mouse.position.z = lerp(mouse.position.z, M0.z, ease(2, dt)); mouse.rotation.y = lerp(mouse.rotation.y, 0, ease(2, dt)); }
    mWheel.rotation.x -= wheel * dt * 9;
    mLed.material.emissiveIntensity = lerp(mLed.material.emissiveIntensity, click ? 5 : 1, ease(click ? 40 : 6, dt));
    const hp = head.position; window.__headPos = hp;
    const hidden = hatching && hatchT > 2.0 && hatchT < 5.25, mugOn = MUG.t >= 0 && alive;
    for (let i = 0; i < 2; i++) {
      const h = hands[i], sd = i ? 1 : -1;
      if (!alive || act === "sleeping") TP.copy(POSE.rest[i]);
      else if (win) TP.copy(POSE.up[i]);
      else if (act === "thinking" && task === "pense" && i === 1) TP.set(hp.x + .58, hp.y - .66, hp.z + .82);   // la main au menton
      else TP.copy(POSE.key[i]);
      if (cheeks) TP.set(hp.x + sd * .98, hp.y - .14, hp.z + .38);
      let rate = 8;
      if (alive && !win && !cheeks) {
        if (mouseMode && i === 1) { TP.set(mouse.position.x - .02, .31 - click * .04 + (wheel ? Math.max(0, Math.sin(t * 6)) * .02 : 0), mouse.position.z - .24); rate = 16; }
        else if (mouseMode) { const ph = (t % 2.6) / 2.6; if (ph < .16) TP.y += Math.sin(ph / .16 * Math.PI) * .09; TP.x += Math.sin(t * .4) * .05; rate = 22; }   // une touche de temps en temps
        else if (typing || task === "code") { TP.y += Math.max(0, Math.sin(t * (danger ? 34 : task === "code" ? 26 : 20) + i * Math.PI)) * .1; TP.x += Math.sin(t * 1.3 + i * 2) * .07; rate = 30; }
        else if (task === "ordre" && i === 1) { const ph = (t % 1.4) / 1.4;   // lève la main… et écrase la touche
          TP.y += ph < .7 ? Math.sin(ph / .7 * Math.PI / 2) * .95 : (1 - (ph - .7) / .3) ** 2 * .95; TP.z -= ph < .7 ? .2 : 0; rate = 30; }
        else if (task === "pense" && i === 1) { TP.y += Math.sin(t * 2.4) * .025; }
      }
      if (cheeks) TP.y += Math.sin(t * 9 + i * 2) * .025;
      if (win) { TP.x += Math.sin(t * 6 + i) * .15; TP.y += Math.sin(t * 9 + i) * .12; }
      if (i === 1 && mugOn) { TP.copy(MUG.hand); rate = 20; }
      if (i === 1 && PH.k > 0 && alive) { TP.copy(PH.hand); rate = 16; }
      h.visible = !hidden;
      if (hidden) { h.position.copy(hp); h.userData.prevY = hp.y; continue; }   // rangées dans le corps : elles en ressortent au démarrage
      h.position.lerp(TP, ease(h.position.distanceToSquared(TP) > .12 ? 9 : rate, dt));   // grands trajets (clavier ↔ souris) en douceur
      const hy = h.position.y;
      if (alive && h.userData.prevY >= KEY_HIT && hy < KEY_HIT) pressNear(h.position, task === "ordre" && i === 1);
      h.userData.prevY = hy;
    }
    phonePlace(now);
  }

  // ---------- montage au bureau : la tasse et sa zone de toucher ----------
  function mount({props, hitZone}) {
    const mug = new THREE.Group(); mug.position.set(MUG.x0, 0, MUG.z0); props.add(mug); owned.push(mug); MUG.g = mug;
    mesh(G(new THREE.CylinderGeometry(.14, .13, .26, 28)), shellMat, mug, 0, .13, 0);   // tasse crème, bandeau graphite, anse ambre
    mesh(G(new THREE.CylinderGeometry(.142, .142, .045, 28, 1, true)), graphite, mug, 0, .2, 0, false);
    const top = mesh(G(new THREE.CircleGeometry(.125, 24)), std(0x3a2416, .3), mug, 0, .255, 0, false); top.rotation.x = -Math.PI / 2;
    const hd = mesh(G(new THREE.TorusGeometry(.07, .022, 8, 18)), amber, mug, .16, .13, 0); hd.scale.set(1, 1.15, 1);
    hitZone(mug, .3, .15, "mug");
    window.__mugActive = () => MUG.t >= 0; window.__mugHand = MUG.hand;
    return api;
  }

  function dispose() {
    gone = true;
    owned.forEach(o => { if (o.parent) o.parent.remove(o); }); owned.length = 0;
    trash.forEach(x => x.dispose()); trash.length = 0;
    delete window.__phoneDbg; delete window.__mugActive; delete window.__mugHand;
  }

  window.__phoneDbg = () => ({k: PH.k, shake: PH.shake, glance: PH.glance, look: PH.look, lit: PH.lit, vis: phone.visible, n: PH.n});   // pour les tests
  const api = {
    head, HEAD, HS,
    outfit: {crown, topHat, partyHat, bowTie, makeHeadset},
    get hatchT() { return hatchT; },
    get partyUntil() { return partyUntil; },
    hatch, emote,
    party(ms) { partyUntil = performance.now() + (ms || 3000); },
    // toucher de la tête : il sursaute (et bâille s'il dormait) ; la scène décide ensuite (chat ou réplique)
    tap(sleeping) { window.__react = {kind: "boop", dur: 1300, until: performance.now() + 1300}; sfx("boop"); buzz(15); if (sleeping) yawnT = 2.6; },
    line(kind) { return pick(kind === "talk" ? TALK : BOOP); },
    sip() { if (MUG.g && MUG.t < 0 && hatchT < 0 && lastAlive && !(window.__unread > 0 && !window.__chatIsOpen)) MUG.t = 0; },
    debug: {liveTexels: FCW * FCH, benchFace() { if (!gone) drawFace(); }},
    mount, update, updateHands, lateUpdate: mugStep, dispose,
  };
  return api;
}
