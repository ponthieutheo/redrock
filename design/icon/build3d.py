"""Icône d'app et de page (PAS le logo de l'app) : le vrai personnage 3D en grand, coupé en bas, devant des bougies
qui montent et descendent sur une tendance qui grimpe. Couleurs de l'app, aplats (aucun dégradé).

    python design/icon/render3d.py design/icon/3d/perso.png "s=1600&mode=win&t=2.0&yaw=-0.22&pitch=0.1&roll=0.1&dist=5.2&ty=0"
    python design/icon/build3d.py      ->  design/icon/3d/*.png  (+ copie dans dash/ avec --installer)
"""
import os, random, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "3d")
BG, GRID = (18, 5, 6), (44, 14, 17)
GAIN, LOSS = (63, 203, 122), (255, 90, 95)
SS = 4                      # suréchantillonnage (anticrénelage des bougies)


def candles(n=11, seed=7):
    """Série inventée : tendance qui monte, avec des replis (rouges) ; valeurs en 0..1 (0 = bas)."""
    rnd = random.Random(seed)
    out, c = [], .12
    for i in range(n):
        drift = .085 + rnd.uniform(-.02, .02)
        down = i in (2, 5, 8)                       # trois replis pour que ça vive
        o = c
        c = o - rnd.uniform(.05, .08) if down else o + drift + rnd.uniform(.0, .05)
        hi = max(o, c) + rnd.uniform(.02, .05)
        lo = min(o, c) - rnd.uniform(.02, .05)
        out.append((o, c, hi, lo))
    return out


def chart(size, box, n=11):
    """Bougies dans box=(x0, y0, x1, y1) en pixels de l'image suréchantillonnée."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    data = candles(n)
    lo_all, hi_all = min(c[3] for c in data), max(c[2] for c in data)
    Y = lambda v: y1 - (v - lo_all) / (hi_all - lo_all) * (y1 - y0)
    step = (x1 - x0) / n
    bw, ww = step * .58, max(2, step * .14)
    for i, (o, c, hi, lo) in enumerate(data):
        cx = x0 + step * (i + .5)
        col = GAIN if c >= o else LOSS
        d.rounded_rectangle([cx - ww / 2, Y(hi), cx + ww / 2, Y(lo)], radius=ww / 2, fill=col)
        top, bot = sorted((Y(o), Y(c)))
        d.rounded_rectangle([cx - bw / 2, top, cx + bw / 2, max(bot, top + ww)], radius=bw * .18, fill=col)
    return im


CUT = .43          # hauteur (fraction de la tête) où l'icône s'arrête : sous les yeux, au-dessus de la bouche (rendu roll=0.1)


def compose(size=1024, maskable=False):
    S = size * SS
    im = Image.new("RGBA", (S, S), BG + (255,))
    d = ImageDraw.Draw(im)
    for k in range(1, 5):                               # quelques lignes de grille discrètes
        y = int(S * k / 5)
        d.rectangle([0, y - SS, S, y + SS], fill=GRID)
    # bougies : de bas-gauche à haut-droite, au-dessus et derrière lui (il lève les yeux vers la courbe qui monte)
    box = (.17, .14, .83, .60) if maskable else (.05, .05, .95, .56)
    im.alpha_composite(chart(S, tuple(int(S * v) for v in box), n=9))
    # le perso : énorme, seuls le haut de la tête et les yeux dépassent ; la bouche reste hors cadre
    p = Image.open(os.path.join(OUT, "perso.png")).convert("RGBA")
    p = p.crop(p.getbbox())
    w = int(S * (.86 if maskable else 1.12))
    h = int(p.height * w / p.width)
    p = p.resize((w, h), Image.LANCZOS)
    bottom = S * (.90 if maskable else 1.0)            # maskable : le bord passe plus haut (zone sûre des masques ronds)
    x, y = int((S - w) / 2), int(bottom - CUT * h)
    p = p.crop((0, 0, w, int(CUT * h)))                 # on coupe sous les yeux : la bouche n'apparaît jamais
    im.alpha_composite(p, (x, y))
    return im.convert("RGB").resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    master = compose(1024)
    master.save(os.path.join(OUT, "icone-1024.png"))
    mask = compose(1024, maskable=True)
    mask.save(os.path.join(OUT, "icone-maskable-1024.png"))
    sizes = {"icon-512.png": (master, 512), "icon-192.png": (master, 192), "apple-touch-icon.png": (master, 180),
             "favicon.png": (master, 64), "icon-maskable.png": (mask, 512)}
    for name, (src, s) in sizes.items():
        src.resize((s, s), Image.LANCZOS).save(os.path.join(OUT, name), optimize=True)
    if "--installer" in sys.argv:
        dash = os.path.join(HERE, "..", "..", "dash")
        for name in sizes:
            Image.open(os.path.join(OUT, name)).save(os.path.join(dash, name), optimize=True)
        print("copié dans dash/")
    print("ok")
