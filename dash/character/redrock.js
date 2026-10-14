/* RedRock — le personnage. Copyright (c) 2026 Théo Ponthieu (RedRock).
   Licence : PolyForm Noncommercial 1.0.0 (voir character/LICENSE) — usage non commercial uniquement.
   Le reste du dashboard est sous une licence libre distincte. */
/* CONTRAT scène ↔ personnage (détails : character/README.md)

   const hero = createCharacter({THREE, rig, desk, renderer})
     THREE : la bibliothèque three.js de la scène ; rig : le groupe du poste de travail (le perso s'y accroche) ;
     renderer (facultatif) : le WebGLRenderer, pour ne renvoyer au GPU que la partie du visage qui change ;
     desk : {mouse, M0, mWheel, mLed, pressNear(pos, slam), screenW} — la souris (que le perso déplace), sa place de repos,
            sa molette et sa diode, la frappe d'une touche du clavier, la largeur des toiles d'écran.
   hero.mount({props, hitZone})   une fois le mobilier posé : tasse (zone de toucher « mug »), mains, téléphone, sueur.
   Chaque image, dans cet ordre :
     hero.update(dt, now, t, S)       S = état du jour (ci-dessous) ; le perso le complète : S.act, S.win, S.danger, S.task, S.em
     hero.updateHands(dt, now, t, S)  mains, souris, téléphone (après les confettis et le sticker de la scène)
     hero.lateUpdate(dt)              tasse (après la garde-robe de la scène)
   S (fourni par la scène) : act ("dead" | "thinking" | "trading" | "watching" | "sleeping"), alive, talking, win, danger,
     task (tâche en cours, ex. "code", "compte", "ordre"), wide (cadrage large), chatOpen, unread (messages non lus),
     outfit {hat, glasses, ear, neck}, tama {energy, hunger, mood}, caress, look {x, y}, generation,
     fear (0..1), content, crown, shades, bandage (drapeaux du jour).
   Signaux lus en direct (ils peuvent changer pendant l'image) : window.__react {kind, dur, until}, window.__say {text, t0}.
   Le perso peut appeler l'app : window.talk(texte), window.__sfx.*(), window.__buzz(motif), window.__emote(nom).
   Exposé : head (Object3D, position locale au rig), HEAD (repos), HS (taille), outfit {crown, topHat, partyHat, bowTie, makeHeadset},
     hatchT (scène de mort/relève : -1 = aucune, sinon secondes écoulées), partyUntil, hatch(), party(ms), emote(nom),
     tap(dort) (toucher de la tête), line("boop" | "talk"), sip() (boire une gorgée), debug {benchFace(), liveTexels}, dispose().
   Crochets de test posés par le perso : window.__phoneDbg, window.__mugActive, window.__mugHand. */

import {createFace} from "./face.js";

export function createCharacter(ctx) {
  const {THREE, rig} = ctx, {mouse, M0, mWheel, mLed, pressNear} = ctx.desk, SW = ctx.desk.screenW;
  const lerp = (a, b, t) => a + (b - a) * t, V = (x, y, z) => new THREE.Vector3(x, y, z);
  const owned = [];   // racines posées dans la scène (pour dispose)

  // ---------- la tête : logo projeté sur la sphère (le visage est peint dans face.js) ----------
  const face = createFace(THREE, ctx.renderer), {headTex, alphaTex, featTex} = face;
  const headMat = new THREE.MeshStandardMaterial({map: headTex, roughness: .62, metalness: 0, alphaTest: .5, transparent: false});
  const innerMat = new THREE.MeshStandardMaterial({color: 0xf0101c, roughness: .62, metalness: 0, side: THREE.BackSide, alphaMap: alphaTex, alphaTest: .5});
  const head = new THREE.Group(); rig.add(head);
  owned.push(head);
  const ball = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64), headMat); ball.castShadow = true; head.add(ball);
  const inner = new THREE.Mesh(new THREE.SphereGeometry(.985, 64, 48), innerMat); head.add(inner);
  // paroi du creux des cornes : tube de l'encoche (contour extrudé en z jusqu'à la sphère) pour que la boule ne s'ouvre pas sur son vide
  { const R = .301, W = .19, CY = .7044, y1 = CY + Math.sqrt(R * R - W * W), yTop = Math.sqrt(1 - W * W), pts = [];
    for (let i = 0; i <= 24; i++) { const u = 1 - (1 - i / 24) ** 1.6; pts.push([-W, yTop - (yTop - y1) * u, 1, 0]); }
    const a0 = Math.atan2(y1 - CY, -W), a1 = Math.atan2(y1 - CY, W) + Math.PI * 2;
    for (let i = 1; i < 72; i++) { const a = a0 + (a1 - a0) * i / 72, c = Math.cos(a), s = Math.sin(a); pts.push([R * c, CY + R * s, -c, -s]); }
    for (let i = 0; i <= 24; i++) { const u = (i / 24) ** 1.6; pts.push([W, y1 + (yTop - y1) * u, -1, 0]); }
    const pos = [], nor = [], idx = [];
    pts.forEach(([x, y, nx, ny], i) => { const z = Math.sqrt(Math.max(0, 1 - x * x - y * y));
      pos.push(x, y, -z, x, y, z); nor.push(nx, ny, 0, nx, ny, 0);
      if (i) { const b = (i - 1) * 2; idx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2); } });
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3)); g.setIndex(idx);
    const wall = new THREE.Mesh(g, new THREE.MeshStandardMaterial({color: 0xf0101c, roughness: .62, metalness: 0, side: THREE.DoubleSide})); head.add(wall);
  }
  const HEAD = new THREE.Vector3(0.05, 0.9, 0.75);
  const HS = 0.88;   // taille de la tête
  const fearMat = new THREE.MeshStandardMaterial({color: 0x7a3cff, emissive: 0x3a12a8, emissiveIntensity: .9, roughness: .45, transparent: true, opacity: 0, alphaMap: face.fearAlphaTex, depthWrite: false});
  const fear = new THREE.Mesh(new THREE.SphereGeometry(1.004, 96, 64), fearMat); fear.renderOrder = 1; head.add(fear);
  const featMesh = new THREE.Mesh(new THREE.SphereGeometry(1.007, 96, 64), new THREE.MeshStandardMaterial({map: featTex, roughness: .62, metalness: 0, transparent: true, depthWrite: false}));
  featMesh.renderOrder = 2; featMesh.visible = false; head.add(featMesh);

  // couronne dorée posée de travers (7 nuits d'affilée)
  // or mat (pas de reflets sombres), même rugosité que le reste : bandeau + 5 pointes + gemmes rouges, posée sur les deux cornes
  const gold = new THREE.MeshStandardMaterial({color: 0xf4bd2c, metalness: .3, roughness: .42, emissive: 0x2a1c00, emissiveIntensity: .3, side: THREE.DoubleSide});
  const crown = new THREE.Group();
  { const R = .4, Hb = .17, band = new THREE.Mesh(new THREE.CylinderGeometry(R, R * .95, Hb, 40, 1, true), gold); band.position.y = Hb / 2; crown.add(band);
    [[0, R * .95], [Hb, R]].forEach(([y, r]) => { const rim = new THREE.Mesh(new THREE.TorusGeometry(r, .018, 8, 40), gold); rim.rotation.x = Math.PI / 2; rim.position.y = y; crown.add(rim); });
    const gemMat = new THREE.MeshStandardMaterial({color: 0xf0101c, roughness: .3});
    for (let i = 0; i < 5; i++) { const a = i / 5 * Math.PI * 2 + Math.PI / 2, cx = Math.cos(a), cz = Math.sin(a);
      const sp = new THREE.Mesh(new THREE.ConeGeometry(.095, .3, 24), gold); sp.position.set(cx * (R - .02), Hb + .15, cz * (R - .02)); crown.add(sp);
      const tip = new THREE.Mesh(new THREE.SphereGeometry(.036, 12, 10), gold); tip.position.set(cx * (R - .02), Hb + .3, cz * (R - .02)); crown.add(tip);
      const gem = new THREE.Mesh(new THREE.SphereGeometry(.04, 14, 10), gemMat); gem.scale.set(1, 1, .6); gem.position.set(cx * (R + .005), Hb * .5, cz * (R + .005)); gem.lookAt(cx * 2, Hb * .5, cz * 2); crown.add(gem); } }
  crown.position.set(-.04, .93, 0); crown.rotation.set(.08, 0, .16); crown.visible = false; head.add(crown);

  // garde-robe (bouton 🎭 → Tenue)
  const felt = new THREE.MeshStandardMaterial({color: 0x161012, roughness: .55, metalness: .1});
  const redMat = new THREE.MeshStandardMaterial({color: 0xf0101c, roughness: .4});
  const topHat = new THREE.Group();
  { const brim = new THREE.Mesh(new THREE.CylinderGeometry(.62, .62, .04, 40), felt); topHat.add(brim);
    const body = new THREE.Mesh(new THREE.CylinderGeometry(.39, .41, .62, 40), felt); body.position.y = .33; topHat.add(body);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(.415, .415, .1, 40, 1, true), redMat); band.position.y = .08; topHat.add(band); }
  topHat.position.set(0, .93, 0); topHat.rotation.set(.05, 0, -.1);   // à cheval sur les deux cornes (le creux est dessous)
  const stripeCv = document.createElement("canvas"); stripeCv.width = stripeCv.height = 128;
  { const x = stripeCv.getContext("2d"); x.fillStyle = "#f6ebe6"; x.fillRect(0, 0, 128, 128); x.fillStyle = "#f0101c";
    for (let i = -128; i < 256; i += 32) { x.beginPath(); x.moveTo(i, 128); x.lineTo(i + 16, 128); x.lineTo(i + 144, 0); x.lineTo(i + 128, 0); x.fill(); } }
  const stripeTex = new THREE.CanvasTexture(stripeCv); stripeTex.colorSpace = THREE.SRGBColorSpace; stripeTex.wrapS = stripeTex.wrapT = THREE.RepeatWrapping; stripeTex.repeat.set(3, 1);
  const partyHat = new THREE.Group();
  { const cone = new THREE.Mesh(new THREE.ConeGeometry(.33, .8, 32, 1, true), new THREE.MeshStandardMaterial({map: stripeTex, roughness: .6, side: THREE.DoubleSide})); cone.position.y = .4; partyHat.add(cone);
    const pom = new THREE.Mesh(new THREE.SphereGeometry(.1, 16, 12), new THREE.MeshStandardMaterial({color: 0xffc83d, roughness: .7})); pom.position.y = .82; partyHat.add(pom); }
  partyHat.position.set(.634, .68, .02); partyHat.rotation.z = -.75;   // sur le côté droit, base enfoncée dans la boule (pas de jour) et loin du creux des cornes
  const bowTie = new THREE.Group();
  { const wing = new THREE.Shape(); wing.moveTo(0, 0); wing.lineTo(.26, .14); wing.quadraticCurveTo(.3, 0, .26, -.14); wing.lineTo(0, 0);
    const wg = new THREE.ExtrudeGeometry(wing, {depth: .05, bevelEnabled: true, bevelSize: .012, bevelThickness: .012, bevelSegments: 2}); wg.translate(0, 0, -.025);
    const bowMat = felt.clone(); const l = new THREE.Mesh(wg, bowMat), r = new THREE.Mesh(wg, bowMat); r.rotation.y = Math.PI; bowTie.add(l, r);
    const knot = new THREE.Mesh(new THREE.SphereGeometry(.07, 16, 12), redMat); knot.scale.set(1, 1.1, .8); bowTie.add(knot); }
  bowTie.position.set(0, -.6, .837); bowTie.rotation.x = .62; bowTie.scale.setScalar(.78);   // sous la bouche, à plat sur la boule, au-dessus du clavier (avant, il était sous la boule et invisible)
  function makeHeadset() { const g = new THREE.Group(), blk = new THREE.MeshStandardMaterial({color: 0x15090b, roughness: .5}), red = new THREE.MeshStandardMaterial({color: 0xf0101c, roughness: .4});
    const add = (geo, m, x, y, z, rz) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); if (rz) o.rotation.z = rz; o.castShadow = true; g.add(o); return o; };
    add(new THREE.TorusGeometry(1.05, .045, 10, 40, Math.PI), blk, 0, 0, -.08);
    [-1, 1].forEach(sd => { add(new THREE.CylinderGeometry(.24, .24, .16, 24), blk, sd * 1.04, -.02, -.06, Math.PI / 2); add(new THREE.CylinderGeometry(.15, .15, .03, 24), red, sd * 1.13, -.02, -.06, Math.PI / 2); });
    add(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([new THREE.Vector3(-1.08, -.1, -.02), new THREE.Vector3(-1.02, -.5, .35), new THREE.Vector3(-.75, -.72, .78), new THREE.Vector3(-.4, -.7, .97)]), 24, .03, 8), blk, 0, 0, 0);
    add(new THREE.SphereGeometry(.07, 12, 10), red, -.4, -.7, .97); return g; }
  const headset = makeHeadset(); headset.visible = false; head.add(headset);
  [topHat, partyHat, bowTie].forEach(g => { g.visible = false; g.traverse(m => { if (m.isMesh) m.castShadow = true; }); head.add(g); });

  let deadFace = false, brAct = false, tbReady = false, brHand = new THREE.Vector3(), deadLook = false, hatchTalked = false, hatchT = -1, hatchPopped = false, hatchSad = false, partyUntil = 0;
  const bounce = x => { const n = 7.5625, d = 2.75;   // rebond à l'atterrissage des lunettes
    return x < 1 / d ? n * x * x : x < 2 / d ? n * (x -= 1.5 / d) * x + .75 : x < 2.5 / d ? n * (x -= 2.25 / d) * x + .9375 : n * (x -= 2.625 / d) * x + .984375; };
  const easeBack = x => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2; };
  const easeElastic = x => x <= 0 ? 0 : x >= 1 ? 1 : 2 ** (-10 * x) * Math.sin((x * 10 - .75) * (2 * Math.PI / 3)) + 1;
  // pierre tombale (RIP + génération) et balai du remplaçant
  const TB = new THREE.Group(); TB.visible = false; rig.add(TB);
  const tbTex = new THREE.CanvasTexture(document.createElement("canvas")); tbTex.colorSpace = THREE.SRGBColorSpace;
  function tbPaint(gen) { const c = tbTex.image; c.width = 320; c.height = 400; const x = c.getContext("2d");
    x.clearRect(0, 0, 320, 400); x.textAlign = "center"; x.fillStyle = "#2b2224";
    x.font = "700 110px 'Chakra Petch', sans-serif"; x.fillText("RIP", 160, 150);
    x.fillRect(100, 166, 120, 6);
    x.font = "700 74px 'Chakra Petch', sans-serif"; x.fillText("GÉN. " + gen, 160, 276);
    tbTex.needsUpdate = true; }
  { const stone = new THREE.MeshStandardMaterial({color: 0xa7a09b, roughness: .9}), base = new THREE.MeshStandardMaterial({color: 0x827b77, roughness: .9});
    const sh = new THREE.Shape(); sh.moveTo(-.4, 0); sh.lineTo(.4, 0); sh.lineTo(.4, .62); sh.absarc(0, .62, .4, 0, Math.PI, false); sh.lineTo(-.4, 0);
    const slab = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, {depth: .16, bevelEnabled: false, curveSegments: 24}), stone); slab.position.set(0, .1, -.08); slab.castShadow = true; TB.add(slab);
    const bs = new THREE.Mesh(new THREE.BoxGeometry(.98, .1, .42), base); bs.position.y = .05; bs.castShadow = true; TB.add(bs);
    const face = new THREE.Mesh(new THREE.PlaneGeometry(.64, .8), new THREE.MeshBasicMaterial({map: tbTex, transparent: true})); face.position.set(0, .66, .085); TB.add(face);
    TB.position.set(-1.3, 0, .45); }
  const BR = new THREE.Group(); BR.visible = false; rig.add(BR);
  { const wood = new THREE.MeshStandardMaterial({color: 0x9c7a4e, roughness: .8}), straw = new THREE.MeshStandardMaterial({color: 0xd4b062, roughness: .9}), band = new THREE.MeshStandardMaterial({color: 0xa9121c, roughness: .7});
    const st = new THREE.Mesh(new THREE.CylinderGeometry(.022, .022, 1.5, 10), wood); st.position.y = .95; st.castShadow = true; BR.add(st);
    const br = new THREE.Mesh(new THREE.CylinderGeometry(.06, .27, .34, 4, 1), straw); br.rotation.y = Math.PI / 4; br.scale.z = .4; br.position.y = .17; br.castShadow = true; BR.add(br);
    const bd = new THREE.Mesh(new THREE.CylinderGeometry(.075, .075, .05, 12), band); bd.position.y = .37; BR.add(bd); }
  owned.push(TB, BR);
  let shadesK = 0, emoteK = null, emoteUntil = 0, waveAt = 0, waveNow = 0;
  const WAVE_MS = 2300;   // émote « salut » : la main monte à côté de la tête, trois signes, redescend
  const POSE = {
    trading: [V(-0.45, .3, 1.58), V(.5, .3, 1.58)], watching: [V(-0.45, .3, 1.58), V(.5, .3, 1.58)],
    thinking: [V(-0.45, .3, 1.58), V(.8, .55, 1.6)], sleeping: [V(-1.05, .24, 1.5), V(.95, .24, 1.45)],
    win: [V(-1.4, 1.55, 1.3), V(1.5, 1.55, 1.3)], dead: [V(-1, .24, 1.5), V(.95, .24, 1.45)],
  };
  const KEY_HIT = .335;   // une main qui redescend sous cette hauteur au-dessus du clavier frappe une touche
  let mouthNow = .05, grinT = 0, grinGap = 6, eyeX = 0, eyeY = 0, eyeTX = 0, eyeTY = 0, nextSacc = 0, yawnT = 0, yawnNext = 120, prevAct = null, boopK = 0;
  let nextBlink = 2, blinkT = 0, fearNow = 0, browNow = 0;
  let tiredNow = 0, hungryNow = 0, gladNow = 0, sadNow = 0, caressNow = 0;   // état tamagotchi lissé (window.__tama)
  let faceAt = 0;

  // ---------- répertoire : émotes et répliques ----------
  const TALK = ["+1 % par jour ? Easy.", "Regarde mes beaux crocs.", "Je suis le meilleur trader de la lignée.", "Tu crois que je passe la nuit ?", "Un jour je m'achèterai un vrai bureau.", "Mon stop est plus serré que mon budget IA."];
  const BOOP = ["Hé ! Je bosse, là.", "Ça chatouille !", "Pas touche, je trade.", "Hihi.", "Tu me déconcentres…", "Oui oui, je suis vivant."];
  function hatch() { hatchT = 0; hatchPopped = false; hatchSad = false; }
  function emote(kind) {
    const n = performance.now(), pick = a => a[Math.floor(Math.random() * a.length)];
    if (kind === "wow" || kind === "ouch") { window.__react = {kind, dur: 1600, until: n + 1600}; window.__sfx && (kind === "wow" ? window.__sfx.ching() : window.__sfx.bonk()); return; }
    if (kind === "boop") { window.__react = {kind, dur: 1300, until: n + 1300}; window.__sfx && window.__sfx.boop(); if (window.talk) window.talk(pick(BOOP)); return; }
    if (kind === "yawn") { yawnT = 2.6; return; }
    if (kind === "hatch") { hatch(); return; }
    if (kind === "talk") { if (window.talk) window.talk(pick(TALK)); return; }
    emoteK = kind; emoteUntil = n + ({dance: 6000, think: 4500, panic: 4000, sleep: 5000, type: 4000, shades: 6000, salut: WAVE_MS}[kind] || 4000);
    if (kind === "dance" && window.__sfx) window.__sfx.fanfare();
    if (kind === "salut") { waveAt = n; if (window.talk) window.talk("Salut !"); }
  }

  const api = {
    head, HEAD, HS,
    outfit: {crown, topHat, partyHat, bowTie, makeHeadset},
    get hatchT() { return hatchT; },
    get partyUntil() { return partyUntil; },
    hatch, emote,
    party(ms) { partyUntil = performance.now() + (ms || 3000); },
    // toucher de la tête : il sursaute (et bâille s'il dormait) ; la scène décide ensuite (chat ou réplique)
    tap(sleeping) {
      window.__react = {kind: "boop", dur: 1300, until: performance.now() + 1300};
      window.__sfx && window.__sfx.boop(); window.__buzz && window.__buzz(15);
      if (sleeping) yawnT = 2.6;
    },
    line(kind) { const L = kind === "talk" ? TALK : BOOP; return L[Math.floor(Math.random() * L.length)]; },
    debug: {liveTexels: face.liveTexels, benchFace() { face.resetCache(); face.draw("open", .5, .6, {brows: 0, panic: false, think: false}, fearNow); }},
    mount, dispose,
  };

  // ---------- le perso s'installe au bureau : tasse, sueur, mains, téléphone ; puis son animation ----------
  function mount({props, hitZone}) {
    const stdM = (c, r = .8, m = .04) => new THREE.MeshStandardMaterial({color: c, roughness: r, metalness: m});
    const MBONE = stdM(0xe9ddd2, .7), MDARK = stdM(0x120506, .9);
    const mk = (geo, mat, x, y, z, parent) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; parent.add(m); return m; };
    const cyl = (rt, rb, h, seg = 32) => new THREE.CylinderGeometry(rt, rb, h, seg);
    const mug = new THREE.Group(); mug.position.set(1.42, 0, 1.25); props.add(mug);
    mk(cyl(.15, .13, .26), MBONE, 0, .13, 0, mug);
    { const top = mk(new THREE.CircleGeometry(.125, 28), MDARK, 0, .262, 0, mug); top.rotation.x = -Math.PI / 2;
      const hd = mk(new THREE.TorusGeometry(.07, .02, 8, 20), MBONE, .17, .13, 0, mug); hd.scale.set(1, 1.15, 1); }

    hitZone(mug, .3, .15, "mug");
    const MUGD = {t: -1, hand: new THREE.Vector3(), T: 4.6};
    const mSm = x => x * x * (3 - 2 * x), seg = (t, a, b) => mSm(Math.max(0, Math.min(1, (t - a) / (b - a))));
    function mugStep(dt) {
      if (MUGD.t < 0) return;
      MUGD.t += dt; const t = MUGD.t, hp = window.__headPos;
      if (t > MUGD.T || !hp) { MUGD.t = -1; mug.position.set(1.42, 0, 1.25); mug.rotation.set(0, 0, 0); return; }
      const up = seg(t, .8, 1.9) - seg(t, 3.2, 4.2), tilt = Math.max(0, seg(t, 1.9, 2.3) - seg(t, 2.9, 3.2)) * -.55 + Math.sin(Math.max(0, t - 2.3) * 9) * .05 * (seg(t, 2.3, 2.4) - seg(t, 2.8, 2.9));
      const m = new THREE.Vector3(1.42 + (hp.x + .38 - 1.42) * up, .0 + (hp.y - .42) * up, 1.25 + (1.82 - 1.25) * up);
      mug.position.copy(m); mug.rotation.set(tilt, -up * .5, 0);
      MUGD.hand.set(m.x + .24, m.y + .06, m.z + .06);
      if (t < .8) MUGD.hand.set(1.42 + .24, .06 + (1 - seg(t, 0, .8)) * .25, 1.25 + .06 + (1 - seg(t, 0, .8)) * .2);
    }
    window.__mugActive = () => MUGD.t >= 0; window.__mugHand = MUGD.hand;
    owned.push(mug);

    // gouttes de sueur
    const dropPts = []; for (let i = 0; i <= 24; i++) { const a = i / 24 * Math.PI; dropPts.push(new THREE.Vector2(Math.sin(a) * Math.sin(a / 2) * .55, Math.cos(a) * .8)); }
    const dropGeo = new THREE.LatheGeometry(dropPts, 24);
    const drops = Array.from({length: 7}, () => {
      const m = new THREE.Mesh(dropGeo, new THREE.MeshStandardMaterial({color: 0x8ccfff, roughness: .03, metalness: .1, transparent: true, opacity: 0, emissive: 0x2f8fd0, emissiveIntensity: .55}));
      m.visible = false; m.scale.setScalar(.001); head.add(m); return {m, t: 1};
    });
    let dropClock = 0;
    function spawnDrop() {
      const d = drops.find(x => x.t >= 1); if (!d) return;
      d.t = 0; d.side = Math.random() < .5 ? -1 : 1; d.lon = d.side * (.75 + Math.random() * .35); d.lat0 = .55 + Math.random() * .2; d.m.visible = true;
    }
    function updateDrops(dt) {
      for (const d of drops) {
        if (d.t >= 1) continue;
        d.t = Math.min(1, d.t + dt / 2.4);
        const t = d.t, m = d.m;
        const lat = t < .25 ? d.lat0 : d.lat0 - (Math.min(t, .7) - .25) / .45 * (d.lat0 - .02);
        const cl = Math.cos(lat), R = 1.03;
        m.position.set(Math.sin(d.lon) * cl * R, Math.sin(lat) * R, Math.cos(d.lon) * cl * R);
        if (t > .7) { const f = (t - .7) / .3; m.position.y -= f * f * 1.4; m.position.x += d.side * f * .12; }
        m.scale.setScalar(.15 * Math.min(1, t / .18) * (t > .7 ? 1 - (t - .7) * .6 : 1));
        m.material.opacity = t > .82 ? (1 - t) / .18 * .9 : .9;
        if (t >= 1) m.visible = false;
      }
    }

    // mains
    const handMat = new THREE.MeshStandardMaterial({color: 0xf0101c, roughness: .62, metalness: 0});
    const hands = [0, 1].map(() => { const h = new THREE.Mesh(new THREE.SphereGeometry(.24, 32, 24), handMat); h.castShadow = true; rig.add(h); return h; });
    hands.forEach(h => h.position.set(0.6, 0.24, 1));

    // ---------- téléphone : un message non lu (window.__unread) => il sort son téléphone, le regarde, il vibre de temps en temps ----------
    window.__phoneDbg = () => ({k: PH.k, shake: PH.shake, glance: PH.glance, look: PH.look, lit: PH.lit, vis: phone.visible, n: PH.n});   // pour les tests
    const PH = {k: 0, n: 0, buzzT: -1, nextBuzz: 0, glanceT: -1, nextGlance: 0, look: 0, glance: 0, lit: 0, shake: 0, drawn: -1,
                hand: new THREE.Vector3(), yawT: .46, pitchT: .26, rz: .07};
    const phone = new THREE.Group(); phone.visible = false; rig.add(phone);
    {
      const w = .36, h = .62, r = .065, sh = new THREE.Shape();
      sh.moveTo(-w / 2 + r, -h / 2); sh.lineTo(w / 2 - r, -h / 2); sh.absarc(w / 2 - r, -h / 2 + r, r, -Math.PI / 2, 0, false);
      sh.lineTo(w / 2, h / 2 - r); sh.absarc(w / 2 - r, h / 2 - r, r, 0, Math.PI / 2, false);
      sh.lineTo(-w / 2 + r, h / 2); sh.absarc(-w / 2 + r, h / 2 - r, r, Math.PI / 2, Math.PI, false);
      sh.lineTo(-w / 2, -h / 2 + r); sh.absarc(-w / 2 + r, -h / 2 + r, r, Math.PI, Math.PI * 1.5, false);
      const bg = new THREE.ExtrudeGeometry(sh, {depth: .04, bevelEnabled: true, bevelThickness: .008, bevelSize: .008, bevelSegments: 3, curveSegments: 12}); bg.center();
      const body = new THREE.Mesh(bg, new THREE.MeshStandardMaterial({color: 0x17181b, roughness: .5, metalness: .15})); body.castShadow = true; phone.add(body);
      PH.cv = document.createElement("canvas"); PH.cv.width = 160; PH.cv.height = 280; PH.cx = PH.cv.getContext("2d");
      PH.tex = new THREE.CanvasTexture(PH.cv); PH.tex.colorSpace = THREE.SRGBColorSpace;
      PH.mat = new THREE.MeshBasicMaterial({map: PH.tex, toneMapped: false});
      const scr = new THREE.Mesh(new THREE.PlaneGeometry(.31, .55), PH.mat); scr.position.z = .0285; phone.add(scr);
      PH.light = new THREE.PointLight(0xcfe4ff, 0, 2.4, 2); PH.light.position.set(-.05, .1, .45); phone.add(PH.light);
    }
    function drawPhone(n) {
      const c = PH.cx, W = 160, H = 280; PH.drawn = n;
      c.fillStyle = "#0d0e11"; c.fillRect(0, 0, W, H);
      c.fillStyle = "#f1e7e3"; c.beginPath(); c.roundRect(10, 98, 140, 92, 14); c.fill();
      c.fillStyle = "#f0101c"; c.beginPath(); c.arc(27, 118, 6, 0, Math.PI * 2); c.fill();
      c.fillStyle = "#2a1114"; c.textAlign = "left"; c.font = "700 14px 'Chakra Petch', sans-serif"; c.fillText("REDROCK", 40, 123);
      c.font = "600 21px 'Chakra Petch', sans-serif"; c.fillText(n > 1 ? n + " messages" : "1 message", 22, 156);
      c.fillStyle = "#6f5653"; c.font = "500 14px sans-serif"; c.fillText(n > 1 ? "non lus" : "non lu", 22, 177);
      c.fillStyle = "#f0101c"; c.beginPath(); c.arc(138, 98, 19, 0, Math.PI * 2); c.fill();
      c.fillStyle = "#fff"; c.textAlign = "center"; c.font = "700 " + (n > 9 ? 17 : 21) + "px 'Chakra Petch', sans-serif"; c.fillText(n > 99 ? "99+" : String(n), 138, n > 9 ? 104 : 106);
      PH.tex.needsUpdate = true;
    }
    const PH0 = new THREE.Vector3(1.55, -.3, 1.85), PH1 = new THREE.Vector3();
    // état : k = présence (0 rangé → 1 en main), buzz = salve de vibrations, glance = coup d'œil vers l'utilisateur
    function phoneStep(dt, now, alive, act, hatching, S) {
      const n = S.unread, open = S.chatOpen;
      const want = alive && !hatching && !open && n > 0 ? 1 : 0, rm = matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (n > PH.n && want) { PH.buzzT = 0; PH.nextBuzz = 3.4; PH.nextGlance = 4 + Math.random() * 3; try { window.__buzz && window.__buzz(12); } catch (x) {} }
      PH.n = n;
      const d = want - PH.k; if (d) { const mv = rm ? 1 : dt / (want ? .85 : .55); PH.k = Math.abs(d) <= mv ? want : PH.k + Math.sign(d) * mv; }
      if (PH.k <= 0) { phone.visible = false; PH.look = 0; PH.glance = 0; PH.shake = 0; PH.lit = 0; if (PH.light.intensity) PH.light.intensity = 0; PH.buzzT = -1; return; }
      const e = mSm(PH.k);
      // salves de vibration, une petite toutes les ~3,4 s une fois en main
      if (PH.k >= 1) { PH.nextBuzz -= dt; if (PH.nextBuzz <= 0 && PH.buzzT < 0) { PH.buzzT = 0; PH.nextBuzz = 3.2 + Math.random() * 1.2; } }
      let env = 0; if (PH.buzzT >= 0) { PH.buzzT += dt; if (PH.buzzT > .5) PH.buzzT = -1; else env = Math.sin(PH.buzzT / .5 * Math.PI); }
      PH.shake = rm ? 0 : env;
      // coup d'œil vers l'utilisateur de temps en temps
      if (PH.k >= 1) { PH.nextGlance -= dt; if (PH.nextGlance <= 0 && PH.glanceT < 0) { PH.glanceT = 0; PH.nextGlance = 6 + Math.random() * 4; } }
      if (PH.glanceT >= 0) { PH.glanceT += dt; if (PH.glanceT > 1.5) PH.glanceT = -1; }
      const g = PH.glanceT >= 0 ? Math.sin(Math.min(1, PH.glanceT / 1.5) * Math.PI) : 0;
      PH.glance += (g - PH.glance) * Math.min(1, dt * 10);
      PH.look = e * (1 - PH.glance * .92);
      PH.lit += (Math.min(1, PH.k * 1.4) * (.62 + .38 * env) - PH.lit) * Math.min(1, dt * 12);
      PH.mat.color.setScalar(.25 + .75 * PH.lit); PH.light.intensity = 1.9 * PH.lit * (PH.k >= 1 ? 1 : e);
      if (PH.drawn !== n) drawPhone(n);
      // trajet de la main : sous le bureau (à droite) → à côté de la joue, avec un petit arc
      const hp = head.position, hx = hp.x + .98, hy = hp.y - .42, hz = 1.98;   // même geste en large et en portrait : le cadre montre tout le perso
      PH.hand.set(PH0.x + (hx - PH0.x) * e, PH0.y + (hy - PH0.y) * e + Math.sin(e * Math.PI) * .14, PH0.z + (hz - PH0.z) * e);
      if (PH.k >= 1) { PH.hand.x += Math.sin(now / 1000 * 1.1) * .012; PH.hand.y += Math.sin(now / 1000 * 1.7) * .014 - PH.glance * .08; }
      PH.hand.x += Math.sin(now / 1000 * 90) * .014 * PH.shake; PH.hand.y += Math.sin(now / 1000 * 77) * .01 * PH.shake;
      phone.visible = true;
    }
    function phonePlace() {
      if (!phone.visible) return;
      const h = hands[1].position, e = mSm(PH.k);
      phone.position.set(h.x - .1, h.y + .36, h.z + .08);
      phone.rotation.set(-.12, -.8 + (1 - e) * .5, .1 + Math.sin(performance.now() / 1000 * 55) * .05 * PH.shake);
      phone.scale.setScalar((.55 + .45 * e) * 1.3);
    }
    owned.push(...hands, phone);

    function update(dt, now, t, S) {
      const ease = (rate) => 1 - Math.exp(-rate * dt);   // lissage identique quelle que soit la cadence
      let act = S.act; const alive = S.alive, talking = S.talking;
      let win = S.win, danger = S.danger;
      // émote en cours (bouton 🎭) : elle prend le dessus quelques secondes
      const em = alive && now < emoteUntil ? emoteK : null;
      if (em === "dance") win = true;
      if (em === "panic") { danger = true; if (act === "sleeping") act = "watching"; }   // la panique réveille : yeux ouverts, sueur
      if (em === "sleep") act = "sleeping";
      if (em === "think" || em === "type") act = "thinking";
      if (em === "salut" && act === "sleeping") act = "watching";   // on ne salue pas en dormant
      // salut : il se tourne vers nous, penche la tête vers sa main, yeux rieurs (0 → 1 → 0 sur le geste)
      waveNow = em === "salut" ? seg(now - waveAt, 0, 350) * (1 - seg(now - waveAt, WAVE_MS - 450, WAVE_MS)) : 0;
      const task = act === "thinking" ? (em === "think" ? "pense" : em === "type" ? "code" : S.task || "pense") : "";
      S.act = act; S.win = win; S.danger = danger; S.em = em; S.task = task;   // état résolu après les émotes : la scène s'en sert (écrans, confettis)
      const OF = S.outfit || {};
      const atScreen = act === "trading" || act === "watching" || (task && task !== "pense");
      const fearLvl = alive ? Math.max(danger ? .85 : 0, S.fear) : 0;
      const content = alive && S.content;
      fearNow = lerp(fearNow, fearLvl, ease(1.5));
      const TM = S.tama || {}, k01 = v => Math.max(0, Math.min(1, v));
      tiredNow = lerp(tiredNow, alive && TM.energy != null ? k01((.45 - TM.energy) / .35) : 0, ease(1.2));
      hungryNow = lerp(hungryNow, alive && TM.hunger != null ? k01((.3 - TM.hunger) / .25) : 0, ease(1.2));
      gladNow = lerp(gladNow, alive && TM.mood != null ? k01((TM.mood - .55) / .35) : 0, ease(1.2));
      sadNow = lerp(sadNow, alive && TM.mood != null ? k01((.3 - TM.mood) / .25) : 0, ease(1.2));
      caressNow = lerp(caressNow, alive && S.caress ? 1 : 0, ease(8));
      browNow = lerp(browNow, Math.max(fearNow, sadNow * .45, tiredNow * .3), ease(3));
      // tête : flottement, sommeil, saut élastique, tremblement de panique (oscillations douces)
      let y = HEAD.y + Math.sin(t * 1.6) * .06, x = HEAD.x, rz = 0, sx = 1, sy = 1;
      if (act === "sleeping") { y = HEAD.y - .1 + Math.sin(t * 1.1) * .03; rz = .12 + Math.sin(t * 1.1) * .02; sx = sy = 1 + Math.sin(t * 1.1) * .022; }
      if (act === "dead") { y = HEAD.y - .45; rz = -.65; }
      if (win) { const h = Math.abs(Math.sin(t * 4.5)); y = HEAD.y + h * .38; sy = .86 + .18 * Math.min(1, h * 1.6); sx = 1.08 - .08 * Math.min(1, h * 1.6); }
      if (danger) { x += Math.sin(t * 14) * .03 + Math.sin(t * 23) * .012; rz += Math.sin(t * 11) * .045; }
      // réactions passagères : gain (wow), perte (aïe), on le touche (boop)
      const R = window.__react || {}, react = alive && R.until > now ? R.kind : null, rk = react ? Math.max(0, Math.min(1, (R.until - now) / R.dur)) : 0;
      if (react === "wow") y += Math.sin((1 - rk) * Math.PI) * .22;
      if (react === "ouch") { x += Math.sin(t * 30) * .035 * rk; rz += Math.sin(t * 22) * .05 * rk; }
      boopK = react === "boop" ? rk : Math.max(0, boopK - dt * 4);
      if (boopK > 0) { const b = Math.sin((1 - boopK) * Math.PI * 3) * boopK; sy *= 1 - .2 * b; sx *= 1 + .14 * b; }
      // bâillement : en s'endormant, et de temps en temps quand il s'ennuie à l'affût
      if (prevAct && prevAct !== act && act === "sleeping") yawnT = 2.6;
      prevAct = act;
      if (act === "watching" && !talking) { yawnNext -= dt; if (yawnNext <= 0) { yawnT = 2.6; yawnNext = 100 + Math.random() * 140; } }
      yawnT = alive && !react ? Math.max(0, yawnT - dt) : 0;
      const yawn = yawnT > 0 ? Math.sin((1 - yawnT / 2.6) * Math.PI) ** .7 : 0;
      sy *= 1 + yawn * .07;
      // âme : respiration (plus rapide quand il est à plat), posture affaissée, tremblement de faim, petit rebond de bonne humeur, caresse
      if (alive && act !== "sleeping") { const br = Math.sin(t * (1.5 + tiredNow * 1.6)); sy *= 1 + br * (.01 + .014 * tiredNow); sx *= 1 - br * .006; }
      if (alive && !win) { y += -(tiredNow * .1 + hungryNow * .06 + sadNow * .05) + gladNow * (Math.sin(t * 2.4) * .5 + .5) * .03; rz += sadNow * .05; x += Math.sin(t * 19) * .008 * hungryNow; }
      if (caressNow > .01) { rz += Math.sin(t * 5) * .05 * caressNow; y -= .03 * caressNow; sx *= 1 + .03 * caressNow; sy *= 1 - .03 * caressNow; }
      if (waveNow > 0) { rz -= .13 * waveNow; y += Math.sin((now - waveAt) / 1000 * 4.4 * Math.PI) * .025 * waveNow; }
      head.position.set(lerp(head.position.x, x, ease(14)), lerp(head.position.y, y, ease(12)), HEAD.z);
      head.scale.set(lerp(head.scale.x, sx * HS, ease(16)), lerp(head.scale.y, sy * HS, ease(16)), lerp(head.scale.z, sx * HS, ease(16)));
      crown.visible = alive && (OF.hat === "crown" || (!OF.hat && S.crown));
      topHat.visible = OF.hat === "top"; partyHat.visible = OF.hat === "party";
      headset.visible = OF.ear === "headset"; bowTie.visible = OF.neck === "bow";
      { const up = headset.visible ? .2 : 0;   // avec le casque, le chapeau repose sur l'arceau au lieu de le traverser
        topHat.position.y = .93 + up; crown.position.y = .93 + up;
        if (headset.visible) { partyHat.position.set(.2, 1.12, .02); partyHat.rotation.z = -.3; } else { partyHat.position.set(.634, .68, .02); partyHat.rotation.z = -.75; } }
      shadesK = alive && (S.shades || em === "shades" || OF.glasses === "pixel") ? Math.min(1, shadesK + dt / .9) : 0;
      phoneStep(dt, now, alive, act, hatchT >= 0, S);
      const lk = S.look || {x: 0, y: 0};
      let yaw = !alive ? 0 : Math.asin(Math.max(-.9, Math.min(.9, lk.x / 565))) * (atScreen ? 2.4 : 1.7);
      if (task === "compte" || task === "news") yaw += Math.sin(t * 1.6) * .1;   // il lit : la tête balaie l'écran
      if (task === "jev") rz += Math.sin(t * 1.3) * .08;                         // curieux : tête qui penche
      let pitch = !alive ? .2 : Math.asin(Math.max(-.9, Math.min(.9, lk.y / 565))) * 1.7 - yawn * .3;
      // il dort : tête baissée qui dodeline au rythme de la respiration, visage (yeux fermés) toujours tourné vers nous ; il relève la tête en bâillant
      if (alive && act === "sleeping") { yaw = Math.sin(t * .23) * .05; pitch = .2 + Math.sin(t * 1.1) * .04 - yawn * .35; }
      if (PH.look > .001) { yaw = lerp(yaw, PH.yawT, PH.look); pitch = lerp(pitch, PH.pitchT, PH.look); rz += PH.rz * PH.look; }   // il regarde son téléphone
      if (waveNow > 0) { yaw = lerp(yaw, 0, waveNow); pitch = lerp(pitch, -.04, waveNow); }   // il salue en nous regardant
      head.rotation.set(lerp(head.rotation.x, pitch, ease(5)), lerp(head.rotation.y, yaw, ease(5)), lerp(head.rotation.z, rz, ease(8)));
      // mort : yeux en croix, bouche noire, il vacille et tombe ; une pierre tombale surgit ; le remplaçant arrive, balaie la tombe et s'installe
      deadLook = !alive; deadFace = false; brAct = false;
      if (hatchT >= 0) {
        hatchT += dt; const T = hatchT, bx = x, by = y, bs = sx * HS;
        if (T < 1.85) {
          deadLook = T > .25; deadFace = T > .2;
          const tp = seg(T, .5, 1.2), wob = T < .5 ? Math.sin(T * 34) * .05 * (T / .5) : 0;
          head.position.x = bx + wob; head.position.y = by - .1 * tp; head.rotation.z = -.65 * tp + wob;   // il s'affaisse sans s'enfoncer dans le sol
          if (T > 1.2) { const k = Math.min(1, (T - 1.2) / .65); head.position.y = by - .1 - k * k * .8; head.position.x = bx - k * .7; head.rotation.z = -.65 - k * 2.2;
            head.scale.setScalar(Math.max(.0001, bs * (1 - k) ** 1.3));   // il rapetisse en roulant (plus de tête qui traverse le sol, la caméra reste fixe)
            if (!hatchSad) { hatchSad = true; window.__sfx && window.__sfx.bonk(); window.__buzz && window.__buzz([30, 40, 30]); } }
        } else if (T < 4.5) { head.scale.setScalar(.0001); deadFace = true; }
        else { const d = Math.min(1, (T - 4.5) / .9); head.position.y = by + (1 - bounce(d)) * 3.4; head.scale.setScalar(bs * Math.min(1, d * 6));
          if (!hatchPopped && d > .55) { hatchPopped = true; window.__sfx && window.__sfx.pop(); window.__buzz && window.__buzz([20, 30, 40]); partyUntil = now + 1800; } }
        // pierre tombale : surgit à 1,9 s, balayée à 6,6 s
        if (T >= 1.9 && T < 7.3) {
          if (!tbReady) { tbReady = true; tbPaint(Math.max(1, (S.generation || 2) - 1)); window.__sfx && window.__sfx.pop(); window.__buzz && window.__buzz(14); }
          TB.visible = true; const a = Math.min(1, (T - 1.9) / .45), sc = Math.max(.0001, easeBack(a)); TB.scale.setScalar(sc); TB.position.set(-1.3, 0, .45); TB.rotation.set(0, 0, 0);
          if (T > 6.5) { const k = Math.min(1, (T - 6.5) / .7); TB.position.set(-1.3 - k * 2.6, -k * k * 2.6, .45); TB.rotation.z = k * 1.1; TB.scale.setScalar(1); }
        } else TB.visible = false;
        // balai : 5,4 s → 7 s, la main gauche le tient
        if (T > 5.4 && T < 7.3) {
          const ap = seg(T, 5.4, 5.75), out = 1 - seg(T, 6.95, 7.25), ph = Math.max(0, T - 5.75) * 7.2;
          BR.visible = true; BR.scale.setScalar(Math.max(.0001, ap * out));
          const rz = -.38 + Math.cos(ph) * .22, bx2 = -1.3 + Math.sin(ph) * .5;
          BR.position.set(bx2, .02, 1.42); BR.rotation.z = rz;
          brHand.set(bx2 - Math.sin(rz) * 1.0, Math.cos(rz) * 1.0, 1.55); brAct = ap > .2 && out > .1;
        } else BR.visible = false;
        if (T > 7.3 && !hatchTalked) { hatchTalked = true; window.talk && window.talk("Ici pour prendre le relais."); window.__emote && window.__emote("wow"); }
        if (T > 8.4) { hatchT = -1; hatchTalked = false; tbReady = false; TB.visible = false; BR.visible = false; }
      }
      headMat.color.setRGB(deadLook ? .38 : 1, deadLook ? .38 : 1, deadLook ? .38 : 1);
      innerMat.color.setHex(deadLook ? 0x5a0609 : 0xf0101c);
      fearMat.opacity = fearNow * .97; fear.visible = fearMat.opacity >= 1 / 512; featMesh.visible = face.featOn;   // sous 1/512 le voile change moins d'un demi-niveau de couleur : inutile de dessiner la sphère
      // visage
      nextBlink -= dt; if (nextBlink <= 0) { blinkT = .16; nextBlink = Math.random() < .18 ? .3 : (danger ? .9 : 2.5) + Math.random() * (danger ? 1.2 : 3.5); }   // parfois un double clignement
      blinkT = Math.max(0, blinkT - dt);
      const blink = blinkT > 0 ? Math.abs(blinkT / .08 - 1) * .92 + .08 : 1;
      // synchro labiale : la bouche suit les lettres du texte de sa bulle (voyelles ouvertes, m/b/p fermées, pauses sur la ponctuation)
      const say = window.__say;
      grinT -= dt; if (grinT < -grinGap) { grinT = 1.2 + Math.random() * 2; grinGap = (content || gladNow > .5 ? 4 : 7) + Math.random() * 9; }   // un grand sourire de temps en temps
      const speaking = talking && alive && say && (now - say.t0) / 62 < say.text.length;
      let mTarget = grinT > 0 ? 1 : .04 + gladNow * .1;                                      // au repos : bouche fermée
      if (speaking) { const ch = (say.text[Math.floor((now - say.t0) / 62)] || " ").toLowerCase();
        mTarget = /[aoàâ]/.test(ch) ? 1 : /[eiuyéèêëîïôûù]/.test(ch) ? .72 : /[mbp]/.test(ch) ? 0 : /[.,!?…:;]/.test(ch) ? .08 : ch === " " ? .22 : .42; }
      else if (win || react === "boop" || waveNow > .3) mTarget = 1;
      else if (caressNow > .5) mTarget = .8;
      else if (danger) mTarget = .5 + .12 * Math.sin(t * 7);
      mouthNow = lerp(mouthNow, mTarget, ease(speaking ? 22 : 7));
      // regard : lit les lignes de l'écran (compte, news, code), sinon petits mouvements d'yeux naturels
      if (task === "compte" || task === "news" || task === "code") { const ph = (t % 1.2) / 1.2; eyeTX = ph > .88 ? -24 : -24 + ph / .88 * 48; eyeTY = -14 + (Math.floor(t / 1.2) % 3) * 9; }
      else if (task === "ordre") { eyeTX = 0; eyeTY = -6; }
      else { nextSacc -= dt; if (nextSacc <= 0) { nextSacc = .4 + Math.random() * 1.8; eyeTX = (Math.random() * 2 - 1) * 18; eyeTY = (Math.random() * 2 - 1) * 10; } }
      eyeX = lerp(eyeX, eyeTX, ease(28)); eyeY = lerp(eyeY, eyeTY, ease(28));
      if (now - faceAt > 33) { faceAt = now;
        let mode = !alive || deadFace ? "x" : act === "sleeping" ? "closed" : win ? "happy" : "open", mouth = "grin", mo = 1;
        if (alive && act === "sleeping") { mouth = "sleep"; mo = .5 + .5 * Math.sin(t * 1.1); }
        if (yawn > 0) { mouth = "yawn"; mo = yawn; if (yawn > .45) mode = "closed"; }
        if (react === "wow") { mode = "wide"; mouth = "o"; mo = Math.min(1, (1 - rk) * 5) * Math.min(1, rk * 6); }
        if (react === "ouch") { mode = "squint"; mouth = "zig"; }
        if (react === "boop") { mode = "happy"; mouth = "grin"; }
        if (caressNow > .4 && act !== "sleeping" && !react) { mode = "happy"; mouth = "grin"; }
        if (waveNow > .3 && alive && !deadFace && !react) { mode = "happy"; mouth = "grin"; }
        const free = mode === "open" || mode === "wide" || mode === "happy";
        face.draw(mode, Math.round(blink * 6) / 6, Math.round((mouth === "grin" ? mouthNow : 1) * 32) / 32,
          {brows: Math.round(browNow * 10) / 10, panic: danger, think: task === "pense", focus: task === "ordre",
           shades: alive && shadesK > 0, glasses: alive && shadesK <= 0 && OF.glasses === "round" ? "round" : "", shadesY: shadesK >= 1 ? 0 : Math.round(-(1 - bounce(shadesK)) * 460 / 6) * 6, bandage: alive && S.bandage,
           ex: free ? Math.round(eyeX / 3) * 3 : 0, ey: free ? Math.round(eyeY / 3) * 3 : 0, mouth, mo: Math.round(mo * 24) / 24}, fearNow); }
      // sueur
      const every = danger ? .75 : fearNow > .45 ? 2.2 : 0;
      if (every && act !== "sleeping") { dropClock += dt; if (dropClock > every) { dropClock = 0; spawnDrop(); } }
      updateDrops(dt);
    }

    function updateHands(dt, now, t, S) {
      const ease = (rate) => 1 - Math.exp(-rate * dt);
      const {act, task, alive, win, danger} = S;
      // mains : clavier (tape), souris (déplace, clique, molette), menton, joues (panique hors trading), en l'air (victoire)
      const cheeks = danger && act !== "trading";
      const typing = act === "trading" && (danger || Math.floor(t / 7) % 2 === 0);   // en trade : alterne clavier / souris
      const mouseMode = alive && !win && !cheeks && !typing && task !== "code" && task !== "ordre" && task !== "pense" && act !== "sleeping";
      let wheel = 0, click = 0;
      if (mouseMode) {
        let tx = M0.x, tz = M0.z, per = 3;
        if (task === "marche") { const ph = (t * 60 % (SW - 28)) / (SW - 28); tx += -.15 + ph * .3; tz += Math.sin(t * 2.1) * .03; per = 1.6; }   // suit le curseur de l'écran
        else if (task === "compte" || task === "news") { wheel = 1; per = 0; tx += Math.sin(t * .5) * .02; }                                  // fait défiler à la molette
        else if (task === "jev") { tx += Math.sin(t * 3.1) * .03; tz += Math.cos(t * 2.3) * .025; per = 2.2; }
        else { tx += Math.sin(t * .7) * .11 + Math.sin(t * 1.9) * .03; tz += Math.sin(t * 1.1) * .06; per = act === "watching" ? 4.2 : 2.8; }
        mouse.position.x = lerp(mouse.position.x, tx, ease(5)); mouse.position.z = lerp(mouse.position.z, tz, ease(5));
        mouse.rotation.y = lerp(mouse.rotation.y, (tx - mouse.position.x) * -1.2, ease(4));
        click = per && (t % per) / per < .06 ? 1 : 0;
      }
      mWheel.rotation.x -= wheel * dt * 9;
      mLed.material.emissiveIntensity = lerp(mLed.material.emissiveIntensity, click ? 5 : 1, ease(click ? 40 : 6));
      let pose = POSE[win ? "win" : task && task !== "pense" ? "trading" : act];
      if (cheeks) { const hp = head.position; pose = [V(hp.x - .92, hp.y - .22, hp.z + .4), V(hp.x + .92, hp.y - .22, hp.z + .4)]; }
      window.__headPos = head.position;
      hands.forEach((h, i) => {
        const p = pose[i].clone();
        let rate = 8;
        if (!win && !cheeks && alive) {
          if (mouseMode && i === 1) { p.set(mouse.position.x - .02, .31 - click * .04 + (wheel ? Math.max(0, Math.sin(t * 6)) * .02 : 0), mouse.position.z - .24); rate = 16; }
          else if (mouseMode) { const ph = (t % 2.6) / 2.6; if (ph < .16) p.y += Math.sin(ph / .16 * Math.PI) * .09; p.x += Math.sin(t * .4) * .05; rate = 22; }   // une touche de temps en temps
          else if (typing || task === "code") { p.y += Math.max(0, Math.sin(t * (danger ? 34 : task === "code" ? 26 : 20) + i * Math.PI)) * .1; p.x += Math.sin(t * 1.3 + i * 2) * .07; rate = 30; }
          else if (task === "ordre" && i === 1) { const ph = (t % 1.4) / 1.4;   // lève la main… et écrase la touche
            p.y += ph < .7 ? Math.sin(ph / .7 * Math.PI / 2) * .95 : (1 - (ph - .7) / .3) ** 2 * .95; p.z -= ph < .7 ? .2 : 0; rate = 30; }
          else if (task === "pense" && i === 1) { p.x += Math.sin(t * 2.4) * .03; p.y += Math.sin(t * 2.4) * .03; }
        }
        if (i === 0 && brAct && alive) { p.copy(brHand); rate = 22; }
        if (i === 1 && window.__mugActive && window.__mugActive() && alive) { p.copy(window.__mugHand); rate = 20; }
        if (i === 1 && PH.k > 0 && alive) { p.copy(PH.hand); rate = 16; }
        if (i === 1 && waveNow > 0 && alive) {   // salut : main levée à côté de la tête, trois signes du poignet
          const w = (now - waveAt) / 1000, hp = head.position;
          const sw = Math.sin(Math.max(0, w - .3) * Math.PI * 2 * 2.1) * seg(w, .3, .5) * (1 - seg(w, 1.65, 1.95));
          p.lerp(V(hp.x + 1.08 + sw * .15, hp.y + .62 - Math.abs(sw) * .05, hp.z + .5), waveNow); rate = 24;
        }
        if (cheeks) p.y += Math.sin(t * 9 + i * 2) * .025;
        if (win) { p.x += Math.sin(t * 6 + i) * .15; p.y += Math.sin(t * 9 + i) * .12; }
        h.position.lerp(p, ease(h.position.distanceToSquared(p) > .12 ? 9 : rate));   // grands trajets (clavier ↔ souris) en douceur
        const hy = h.position.y;
        if (alive && h.prevY != null && h.prevY >= KEY_HIT && hy < KEY_HIT) pressNear(h.position, task === "ordre" && i === 1);
        h.prevY = hy;
        h.visible = alive && !(hatchT >= 0 && hatchT < 4.7);
      });
      phonePlace();
    }

    api.update = update; api.updateHands = updateHands; api.lateUpdate = mugStep;
    api.sip = () => { if (MUGD.t < 0 && window.__headPos && !(window.__unread > 0 && !window.__chatIsOpen)) MUGD.t = 0; };
    return api;
  }

  function dispose() {
    owned.forEach(o => { if (o.parent) o.parent.remove(o);
      o.traverse(m => { if (m.geometry) m.geometry.dispose();
        [].concat(m.material || []).forEach(x => { ["map", "alphaMap"].forEach(k => x[k] && x[k].dispose()); x.dispose(); }); }); });
    owned.length = 0;
    delete window.__phoneDbg; delete window.__mugActive; delete window.__mugHand;
  }

  return api;
}
