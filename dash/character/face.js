/* RedRock — le personnage. Copyright (c) 2026 Théo Ponthieu (RedRock).
   Licence : PolyForm Noncommercial 1.0.0 (voir character/LICENSE) — usage non commercial uniquement.
   Le reste du dashboard est sous une licence libre distincte. */
/* Visage du personnage : le logo RedRock projeté sur la sphère de la tête (vu de face = le logo exact).
   Yeux, sourcils, bouche, lunettes et pansement sont peints dans une toile 2D puis reportés sur la texture
   équirectangulaire de la sphère ; seuls les texels qui peuvent changer (LIVE) sont recalculés, et seul leur rectangle
   est relu dans la toile et renvoyé au GPU (texture de données, pas de recopie de 2 Mo à chaque expression).
   createFace(THREE, renderer?) → {headTex, alphaTex, featTex, fearAlphaTex, draw(mode, blink, mouthS, o, fearNow), featOn, resetCache(), liveTexels}
   renderer (facultatif) : sert à téléverser le seul rectangle modifié ; sans lui, la texture entière est renvoyée. */

export function createFace(THREE, renderer) {
  const FS = 512, k = FS / 1254, face = document.createElement("canvas"); face.width = face.height = FS;
  const fctx = face.getContext("2d", {willReadFrequently: true});
  const SLEEP = new Path2D("M405 650Q466 700 527 650M728 650Q789 700 850 650");
  const XEYES = new Path2D("M400 560L532 700M532 560L400 700M722 560L854 700M854 560L722 700");
  const TW = 1024, TH = 512;
  // texture de la sphère : mêmes octets qu'avant (Uint8ClampedArray = même arrondi qu'une ImageData), rangés dans l'ordre du GPU
  // (ligne 0 = bas de l'image : la ligne r de la toile d'origine est la ligne TH-1-r ici, d'où l'absence de retournement)
  const data = new Uint8ClampedArray(TW * TH * 4);
  const map = new Int32Array(TW * TH), cut = new Uint8Array(TW * TH);
  const COS = new Float64Array(TW), SIN = new Float64Array(TW);   // trigonométrie par colonne, calculée une fois (mêmes valeurs qu'avant)
  for (let c = 0; c < TW; c++) { const ph = (c + .5) / TW * Math.PI * 2; COS[c] = Math.cos(ph); SIN[c] = Math.sin(ph); }
  for (let r = 0; r < TH; r++) {
    const th = (r + .5) / TH * Math.PI, st = Math.sin(th), y = Math.cos(th);
    for (let c = 0; c < TW; c++) {
      const x = -COS[c] * st, z = SIN[c] * st, i = r * TW + c;
      cut[i] = (x * x + (y - .7044) ** 2 < .297 ** 2) || (Math.abs(x) < .186 && y > .7044) ? 1 : 0;
      if (z > 0) { const px = Math.round((627 + x * 565) * k), py = Math.round((660 - y * 565) * k);
        map[i] = px >= 0 && px < FS && py >= 0 && py < FS ? py * FS + px : -1; } else map[i] = -1;
    }
  }
  // seuls ces texels peuvent changer (yeux + bouche) : on ne retraite qu'eux à chaque mise à jour
  const fx0 = Math.floor(200 * k), fx1 = Math.ceil(1054 * k), fy0 = Math.floor(395 * k), fy1 = Math.ceil(1000 * k);   // 395 : l'arc du sourcil « réfléchit » monte jusqu'à y ≈ 405
  // pour chaque texel vivant : où le lire dans le rectangle relu de la toile (LS) et où l'écrire dans la texture (LD) ;
  // et le rectangle de texture qui les contient (seul renvoyé au GPU)
  const RW = fx1 - fx0 + 1, RH = fy1 - fy0 + 1, ls = [], ld = [];
  let c0 = TW, c1 = -1, g0 = TH, g1 = -1;
  for (let i = 0; i < TW * TH; i++) { const m = map[i]; if (m < 0 || cut[i]) continue; const px = m % FS, py = (m / FS) | 0;
    if (px >= fx0 && px <= fx1 && py >= fy0 && py <= fy1) { const r = (i / TW) | 0, c = i % TW, g = TH - 1 - r;
      ls.push(((py - fy0) * RW + px - fx0) * 4); ld.push((g * TW + c) * 4);
      if (c < c0) c0 = c; if (c > c1) c1 = c; if (g < g0) g0 = g; if (g > g1) g1 = g; } }
  const LS = Int32Array.from(ls), LD = Int32Array.from(ld), NLIVE = LS.length;
  const RECT = new THREE.Box2(new THREE.Vector2(c0, g0), new THREE.Vector2(c1 + 1, g1 + 1)), RPOS = new THREE.Vector2(c0, g0);
  // textures fixes en données (ordre du GPU) : mêmes octets que les anciennes toiles, sans toile de 2 Mo ni relecture
  const fixedTex = arr => { const t = new THREE.DataTexture(arr, TW, TH, THREE.RGBAFormat, THREE.UnsignedByteType);
    t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true; t.unpackAlignment = 4; t.needsUpdate = true; return t; };
  // texture d'alpha (la fente) pour l'intérieur
  const alA = new Uint8ClampedArray(TW * TH * 4);
  for (let i = 0; i < TW * TH; i++) { const v = cut[i] ? 0 : 255, o = ((TH - 1 - ((i / TW) | 0)) * TW + i % TW) * 4; alA[o] = alA[o + 1] = alA[o + 2] = v; alA[o + 3] = 255; }
  const alphaTex = fixedTex(alA);

  // mêmes réglages qu'une CanvasTexture (filtrage, mipmaps, anisotropie) : seul le chemin de téléversement change
  const dataTex = arr => { const t = new THREE.DataTexture(arr, TW, TH, THREE.RGBAFormat, THREE.UnsignedByteType);
    t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true;
    t.anisotropy = 4; t.unpackAlignment = 4; t.needsUpdate = true; return t; };
  // sphère rouge (240, 16, 28), fente transparente ; les yeux et la bouche sont repeints à chaque changement
  for (let i = 0, n = TW * TH; i < n; i++) { const p = ((TH - 1 - ((i / TW) | 0)) * TW + i % TW) * 4;
    if (cut[i]) { data[p + 3] = 0; continue; } data[p] = 240; data[p + 1] = 16; data[p + 2] = 28; data[p + 3] = 255; }
  const headTex = dataTex(data);
  // traits du visage (yeux, sourcils, bouche) redessinés PAR-DESSUS le voile violet de la peur : ils gardent leur noir plein au lieu d'être teintés
  const ft = new Uint8ClampedArray(TW * TH * 4), featTex = dataTex(ft);
  let featOn = false;
  // renvoie au GPU le seul rectangle vivant (la texture entière la toute première fois, ou sans moteur de rendu)
  const upload = t => { if (!renderer || t.version === 0) { t.needsUpdate = true; return; } renderer.copyTextureToTexture(t, t, RECT, RPOS); };

  let faceKey = "";
  const BROWS = new Path2D("M392 505Q452 470 528 452M726 452Q802 470 862 505");
  // 🤔 : sourcil gauche levé en arc, sourcil droit droit et bas, collé à l'œil
  const THINK_UP = new Path2D("M386 478Q458 400 540 446");
  const THINK_FLAT = new Path2D("M722 497L862 497");
  const HAPPY = new Path2D("M405 690Q466 590 527 690M728 690Q789 590 850 690");
  const SHADES = ["######################", "#ww#######..#ww#######", ".#w######....#w######.", "..######......######..", "...####........####..."];
  const SQUINT = new Path2D("M412 585L524 640L412 695M842 585L730 640L842 695");          // > <
  const FOCUS = new Path2D("M392 474L530 522M724 522L862 474");                            // sourcils froncés (concentré)
  const ZIG = new Path2D("M430 866L478 834L526 870L574 834L626 870L678 834L730 870L778 834L824 866");   // bouche crispée
  /* Visage peint (yeux noirs unis, sourcils, bouche), projeté sur la sphère.
     o = {brows: 0..1, panic, think, focus: bool, ex/ey: regard dans le visage,
          mouth: "grin" | "o" | "zig" | "yawn" | "sleep", mo: ouverture 0..1} */
  // contour de la bouche du logo (crocs compris), échantillonné pour pouvoir la refermer progressivement
  const MOUTH_PTS = (() => { const P = [[262, 758], [352, 798], [374, 905], [428, 826]];
    const q = (x0, y0, cx, cy, x1, y1) => { for (let i = 1; i <= 14; i++) { const t = i / 14, u = 1 - t; P.push([u * u * x0 + 2 * u * t * cx + t * t * x1, u * u * y0 + 2 * u * t * cy + t * t * y1]); } };
    q(428, 826, 627, 862, 824, 826); P.push([878, 905], [898, 798], [990, 758]);
    q(990, 758, 936, 885, 790, 940); q(790, 940, 627, 990, 464, 940); q(464, 940, 318, 885, 262, 758); return P; })();
  // bord haut de la bouche du logo (coins, crocs, courbe) : c'est le trait en zigzag de la bouche fermée
  const TOP_N = MOUTH_PTS.findIndex(([x, y]) => x === 990 && y === 758), TOP = MOUTH_PTS.slice(0, TOP_N + 1);
  // lèvre du haut sans les pointes des crocs ; les crocs = triangles rouges du logo, toujours à la même taille
  const LIP = TOP.filter(([, y]) => y !== 905);
  const lipY = x => { for (let k = 1; k < LIP.length; k++) if (x <= LIP[k][0]) { const [x0, y0] = LIP[k - 1], [x1, y1] = LIP[k]; return y0 + (y1 - y0) * (x - x0) / (x1 - x0 || 1); } return 758; };
  const FANGS = [[[352, 798], [374, 905], [428, 826]], [[824, 826], [878, 905], [898, 798]]];
  const topY = x => { for (let k = 1; k < TOP.length; k++) if (x <= TOP[k][0]) { const [x0, y0] = TOP[k - 1], [x1, y1] = TOP[k]; return y0 + (y1 - y0) * (x - x0) / (x1 - x0 || 1); } return 758; };
  function drawFace(mode, blink, mouthS, o, fearNow) {
    const ex = o.ex || 0, ey = o.ey || 0, mouth = o.mouth || "grin", mo = o.mo == null ? 1 : Math.max(0, Math.min(1, o.mo));
    const fearOn = fearNow > .02, keyNow = `${mode}|${blink.toFixed(2)}|${mouthS.toFixed(2)}|${o.brows.toFixed(1)}|${o.panic}|${o.think}|${o.focus}|${ex}|${ey}|${mouth}|${mo.toFixed(2)}|${o.shades}|${o.shadesY}|${o.bandage}|${o.glasses}|${fearOn}`;
    if (keyNow === faceKey) return;
    faceKey = keyNow;
    fctx.clearRect(0, 0, FS, FS); fctx.save(); fctx.scale(k, k); fctx.lineCap = "round"; fctx.lineJoin = "round";
    fctx.fillStyle = fctx.strokeStyle = "#120506";
    const landed = o.shades && !o.shadesY;   // lunettes posées : on ne voit plus les yeux
    if (mode === "open" || mode === "wide") { if (!landed) for (const cx of [466, 789]) {
      const sc = mode === "wide" ? 1.16 : 1, w = 112 * sc, h = Math.max(236 * sc * blink * (o.panic ? .92 : 1), 16), x = cx - w / 2 + ex, y = 640 + ey - h / 2;
      fctx.beginPath(); fctx.roundRect ? fctx.roundRect(x, y, w, h, Math.min(w / 2, h / 2)) : fctx.rect(x, y, w, h); fctx.fill();
    } }
    else if (mode === "happy") { fctx.lineWidth = 42; fctx.save(); fctx.translate(ex * .5, ey * .5); fctx.stroke(HAPPY); fctx.restore(); }
    else if (mode === "closed") { fctx.lineWidth = 40; fctx.stroke(SLEEP); }
    else if (mode === "squint") { fctx.lineWidth = 42; fctx.stroke(SQUINT); }
    else { fctx.lineWidth = 44; fctx.stroke(XEYES); }
    if (o.glasses === "round" && mode !== "x") {   // lunettes rondes d'intello
      fctx.save(); fctx.lineWidth = 17;
      for (const cx of [466, 789]) { fctx.beginPath(); fctx.arc(cx, 640, 134, 0, Math.PI * 2); fctx.stroke(); }
      fctx.beginPath(); fctx.moveTo(598, 622); fctx.quadraticCurveTo(627, 598, 656, 622); fctx.moveTo(334, 626); fctx.lineTo(262, 606); fctx.moveTo(920, 626); fctx.lineTo(992, 606); fctx.stroke();
      fctx.restore();
    }
    fctx.lineWidth = 38;
    if (o.think && !o.panic && mode === "open") { fctx.stroke(THINK_UP); fctx.stroke(THINK_FLAT); }
    else if (o.focus && !o.panic && mode === "open") fctx.stroke(FOCUS);
    else if (o.brows > .05 && mode !== "x") { fctx.lineWidth = 38 * Math.min(1, .45 + o.brows * 1.2); fctx.stroke(BROWS); }   // même noir plein que les yeux (jamais translucide) : l'intensité joue sur l'épaisseur
    if (o.shades && mode !== "x") {   // lunettes pixel « Deal with it » (grosse journée), qui tombent du haut
      const P = 36, x0 = 627 - 11 * P, y0 = 540 + (o.shadesY || 0);
      SHADES.forEach((row, r) => [...row].forEach((c, k) => { if (c === ".") return;
        fctx.fillStyle = c === "w" ? "#ffffff" : "#050101"; fctx.fillRect(x0 + k * P, y0 + r * P, P + 1, P + 1); }));
      fctx.fillStyle = fctx.strokeStyle = "#120506";
    }
    if (mode === "x") { fctx.beginPath(); fctx.ellipse(627, 884, 62, 86, 0, 0, Math.PI * 2); fctx.fill(); }
    if (mode !== "x") {
      fctx.beginPath();
      if (mouth === "o") { fctx.ellipse(627, 872, 22 + 52 * mo, 14 + 82 * mo, 0, 0, Math.PI * 2); fctx.fill(); }
      else if (mouth === "yawn") { fctx.ellipse(627, 872, 34 + 76 * mo, 12 + 110 * mo, 0, 0, Math.PI * 2); fctx.fill(); }
      else if (mouth === "sleep") { fctx.ellipse(627, 872, 34, 12 + 14 * mo, 0, 0, Math.PI * 2); fctx.fill(); }
      else if (mouth === "zig") { fctx.lineWidth = 30; fctx.stroke(ZIG); }
      else {   // m = 0 : sourire fermé (un trait, un peu moins large) … m = 1 : le grand sourire du logo
        // m = 1 : la bouche exacte du logo. m = 0 : bouche fermée = trait noir fin qui suit la lèvre et contourne les crocs.
        // Les crocs (triangles rouges) gardent toujours la taille du logo ; seule la mâchoire du bas descend sous la lèvre.
        const m = mouthS;
        fctx.beginPath(); LIP.forEach(([x, y], i) => i ? fctx.lineTo(x, y) : fctx.moveTo(x, y));
        MOUTH_PTS.slice(TOP_N + 1).forEach(([x, y]) => fctx.lineTo(x, lipY(x) + (y - lipY(x)) * m));
        fctx.closePath(); fctx.fill();
        fctx.fillStyle = "#f0101c";
        for (const f of FANGS) { fctx.beginPath(); f.forEach(([x, y], i) => i ? fctx.lineTo(x, y) : fctx.moveTo(x, y)); fctx.closePath(); fctx.fill(); }
        fctx.fillStyle = "#120506";
        const lw = 15 * (1 - Math.min(1, m * 1.8));
        // trait fin qui contourne les crocs (descend jusqu'à la pointe, remonte) : jamais de trait sur leur base,
        // ils restent rouges et attachés à la lèvre du haut
        if (lw > .5) { fctx.lineWidth = lw; fctx.beginPath(); TOP.forEach(([x, y], i) => i ? fctx.lineTo(x, y) : fctx.moveTo(x, y)); fctx.stroke(); }
      }
    }
    if (o.bandage && mode !== "x") {   // pansement (perte récente)
      fctx.save(); fctx.translate(300, 606); fctx.rotate(-.55); fctx.fillStyle = "#f1cf9f";
      fctx.beginPath(); fctx.roundRect ? fctx.roundRect(-92, -30, 184, 60, 24) : fctx.rect(-92, -30, 184, 60); fctx.fill();
      fctx.fillStyle = "#d9a86c"; fctx.beginPath(); fctx.roundRect ? fctx.roundRect(-30, -23, 60, 46, 8) : fctx.rect(-30, -23, 60, 46); fctx.fill();
      fctx.fillStyle = "rgba(120,70,30,.35)"; for (const x of [-72, -54, 54, 72]) for (const y of [-11, 9]) { fctx.beginPath(); fctx.arc(x, y, 4, 0, Math.PI * 2); fctx.fill(); }
      fctx.restore();
    }
    fctx.restore();
    const fd = fctx.getImageData(fx0, fy0, RW, RH).data, d = data;   // seul le rectangle qui peut changer est relu
    for (let j = 0; j < NLIVE; j++) {   // mélange peinture / rouge de la sphère
      const p = LD[j], m = LS[j], a = fd[m + 3] / 255, b = 1 - a;
      d[p] = 240 * b + fd[m] * a; d[p + 1] = 16 * b + fd[m + 1] * a; d[p + 2] = 28 * b + fd[m + 2] * a;
      if (fearOn) { ft[p] = fd[m]; ft[p + 1] = fd[m + 1]; ft[p + 2] = fd[m + 2]; ft[p + 3] = fd[m + 3]; }
    }
    upload(headTex);
    if (fearOn) upload(featTex);
    featOn = fearOn;
  }

  // peur : front qui vire au violet (sphère légèrement plus grande, dégradé du haut vers les yeux)
  const faA = new Uint8ClampedArray(TW * TH * 4);
  for (let r = 0; r < TH; r++) { const yy = Math.cos((r + .5) / TH * Math.PI), v = Math.max(0, Math.min(1, (yy + .02) / .6)) ** .9 * 255, g = (TH - 1 - r) * TW;
    for (let c = 0; c < TW; c++) { const i = r * TW + c, p = (g + c) * 4; const val = cut[i] ? 0 : v; faA[p] = faA[p + 1] = faA[p + 2] = val; faA[p + 3] = 255; } }
  const fearAlphaTex = fixedTex(faA);

  return {headTex, alphaTex, featTex, fearAlphaTex, draw: drawFace, liveTexels: NLIVE,
    get featOn() { return featOn; }, resetCache() { faceKey = ""; }};
}
