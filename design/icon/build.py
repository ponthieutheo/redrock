"""Génère les 3 variantes d'icône RedRock en SVG (perso vectoriel redessiné d'après dash/logo.png + petit graphique).

python design/icon/build.py   ->  variante-a.svg, variante-b.svg, variante-c.svg (+ versions « maskable » dans sortie/)
Couleurs = celles de l'app (dash/index.html) ; aucun dégradé.
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BG, PANEL, LINE, LINE2 = "#120506", "#1c0809", "#3a1416", "#4d1a1d"
RED, BLACK, GAIN, LOSS = "#f0101c", "#000000", "#3fcb7a", "#ff5a5f"

# ---- perso (repère du logo 320 px, mesuré sur dash/logo.png) : boule = ellipse cx=167.5 cy=152 rx=150.5 ry=142,
# encoche des cornes = cercle cx=167.5 cy=54 r=45.5 ; pointes des cornes arrondies (rayon TIP) par un trait de même couleur
CX, CY, RX, RY = 167.5, 152.0, 150.5, 142.0
NX, NY, RN = 167.5, 54.0, 45.5
TIP = 6.0


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def body_path(grow=0.0):
    """Contour du corps réduit de TIP (le trait arrondi de largeur 2·TIP le ramène à la bonne taille) ; grow l'élargit encore."""
    rx, ry, rn = RX - TIP + grow, RY - TIP + grow, RN + TIP - grow
    xe = lambda y: CX - rx * math.sqrt(max(0.0, 1 - ((y - CY) / ry) ** 2))
    xc = lambda y: NX - math.sqrt(max(0.0, rn ** 2 - (y - NY) ** 2))
    lo, hi = CY - ry, NY                       # pointe gauche : là où l'ellipse rejoint le cercle de l'encoche
    for _ in range(80):
        mid = (lo + hi) / 2
        if xe(mid) > xc(mid): lo = mid
        else: hi = mid
    y = (lo + hi) / 2; x = xe(y); m = 2 * CX - x
    return (f"M{f(x)} {f(y)}A{f(rn)} {f(rn)} 0 1 0 {f(m)} {f(y)}"
            f"A{f(rx)} {f(ry)} 0 1 1 {f(x)} {f(y)}Z")


MOUTH = ("M71 189Q83 194 96 204L101.5 227L112 207Q140 208 167.5 214.5Q195 208 223 207L233.5 227L239 204"
         "Q252 194 264 189C247 228 210 243.5 167.5 243.5C125 243.5 88 228 71 189Z")
EYES = '<rect x="110" y="126" width="29.5" height="60" rx="14.75"/><rect x="195.5" y="126" width="29.5" height="60" rx="14.75"/>'


def character(cx, cy, size, gap=0):
    """Perso centré sur (cx, cy), largeur `size` px ; `gap` = liseré couleur du fond qui le détache du graphique derrière."""
    s = size / (2 * RX)
    tx, ty = cx - CX * s, cy - CY * s
    d = body_path()
    halo = (f'<path d="{d}" fill="{BG}" stroke="{BG}" stroke-width="{f(2 * TIP + 2 * gap / s)}" stroke-linejoin="round"/>'
            if gap else "")
    return (f'<g transform="translate({f(tx)} {f(ty)}) scale({f(s)})">{halo}'
            f'<path d="{d}" fill="{RED}" stroke="{RED}" stroke-width="{f(2 * TIP)}" stroke-linejoin="round"/>'
            f'<g fill="{BLACK}">{EYES}<path d="{MOUTH}"/></g></g>')


def svg(content, scale=1.0):
    inner = content if scale == 1 else f'<g transform="translate(256 256) scale({scale}) translate(-256 -256)">{content}</g>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">'
            f'<rect width="512" height="512" fill="{BG}"/>{inner}</svg>\n')


def grid(y0, y1, n, x0=56, x1=456):
    return "".join(f'<line x1="{x0}" y1="{f(y)}" x2="{x1}" y2="{f(y)}" stroke="{LINE}" stroke-width="4" stroke-linecap="round"/>'
                   for y in [y0 + (y1 - y0) * i / (n - 1) for i in range(n)])


# A : une courbe de gain qui traverse l'icône au-dessus de sa tête, le perso au premier plan
def variant_a():
    pts = [(62, 252), (124, 206), (178, 230), (246, 146), (302, 172), (372, 92), (448, 70)]
    poly = " ".join(f"{x},{y}" for x, y in pts)
    chart = (grid(112, 412, 4)
             + f'<polyline points="{poly}" fill="none" stroke="{GAIN}" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>'
             + f'<circle cx="448" cy="70" r="25" fill="{BG}"/><circle cx="448" cy="70" r="15" fill="{GAIN}"/>')
    return chart + character(256, 334, 296, gap=16)


# B : perso + bougies derrière (LONG vert, SHORT rouge), tendance haussière ; une mèche passe dans l'encoche des cornes
def variant_b():
    # (x, haut mèche, haut corps, bas corps, bas mèche, couleur)
    candles = [(76, 246, 274, 352, 380, GAIN), (166, 186, 212, 270, 298, LOSS), (256, 100, 128, 222, 250, GAIN),
               (346, 118, 146, 206, 232, LOSS), (436, 54, 82, 196, 224, GAIN)]
    out = grid(96, 410, 4)
    for x, wt, bt, bb, wb, c in candles:
        out += (f'<line x1="{x}" y1="{wt}" x2="{x}" y2="{wb}" stroke="{c}" stroke-width="8" stroke-linecap="round"/>'
                f'<rect x="{x - 20}" y="{bt}" width="40" height="{bb - bt}" rx="7" fill="{c}"/>')
    return out + character(256, 322, 286, gap=16)


# C : le perso devant son écran de trading (cadre arrondi comme les moniteurs de l'app) avec une mini-courbe
def variant_c():
    pts = [(118, 238), (162, 214), (198, 228), (242, 178), (280, 192), (324, 140), (362, 152), (396, 112)]
    poly = " ".join(f"{x},{y}" for x, y in pts)
    screen = (f'<rect x="78" y="66" width="356" height="240" rx="36" fill="{PANEL}" stroke="#5a2125" stroke-width="10"/>'
              + grid(118, 262, 3, 118, 394)
              + f'<polyline points="{poly}" fill="none" stroke="{GAIN}" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>'
              + f'<circle cx="396" cy="112" r="11" fill="{GAIN}"/>')
    return screen + character(256, 344, 276, gap=16)


VARIANTS = {"a": variant_a, "b": variant_b, "c": variant_c}

if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "maskable"), exist_ok=True)
    for k, fn in VARIANTS.items():
        art = fn()
        with open(os.path.join(HERE, f"variante-{k}.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg(art))
        with open(os.path.join(HERE, "maskable", f"variante-{k}.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg(art, 0.8))      # tout le contenu dans le cercle central de 80 %
    with open(os.path.join(HERE, "perso.svg"), "w", encoding="utf-8") as fh:   # le perso seul, fond transparent
        fh.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">{character(256, 256, 470)}</svg>\n')
    print("ok")
