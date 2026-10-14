"""Captures d'écran du README (PNG, WebP animé), en temps virtuel : mêmes images à chaque rendu.

    python tools/media/capture.py --out tools/public/docs/media [--only scene-pc rejouer] [--candidates DOSSIER]

Le serveur des médias doit tourner (server.py). --candidates enregistre en plus une série d'images autour
du moment choisi, pour en choisir un autre si le design a changé (puis ajuster le nombre d'images ci-dessous).

Captures « ce qu'il te montre » (téléphone 390 px de large, ×2, écran haut pour tout voir sans faire défiler) :
  positions.png   positions ouvertes : graphique, SL / TP, SL déplacé, thèse dépliée (deux colonnes)
  journal.png     journal de pensée : ce qu'il voit, décide et pourquoi (deux colonnes)
  suivi.png       suivi des trades : l'historique (résultats nets) et son miroir par type de setup (deux colonnes)
  rejouer.webp    « Rejouer le trade » : bougies derrière un curseur, SL remonté en escalier, résultat (boucle)
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

HINT = {"redrock-hint": "1"}                       # l'astuce « Touche un écran » déjà vue
QUIET = {**HINT, "hc1-tama-day": "2026-10-14"}     # pas de bulle de bonjour (déjà dit aujourd'hui)
CHAT = {**QUIET, "hc1.chatkey": "demo"}            # appareil appairé (la fausse API accepte tout)
LOOK = "window.__look.hold = Date.now() + 1e9; window.__look.tx = 0; window.__look.ty = 20;"   # il nous regarde
TYPE = """const i = document.getElementById('chat-in'); i.value = %r; i.dispatchEvent(new Event('input'));
          document.getElementById('chat-form').requestSubmit();"""
SAY_OFF = "!document.getElementById('say').classList.contains('on')"   # sa bulle de parole a disparu
NO_SAY ="const s = document.createElement('style'); s.textContent = '#say{display:none!important}'; document.head.appendChild(s);"

# nom, (largeur, hauteur, densité, mobile), scénario, localStorage, actions [(type, valeur)]
SHOTS = [
    ("scene-pc", (1440, 900, 1, False), "vie", HINT, [("js", LOOK), ("tick", 280)]),
    ("scene-tel", (390, 844, 2, True), "vie", QUIET, [("js", LOOK), ("tick", 240), ("until", (SAY_OFF, 900)), ("tick", 40)]),
    ("chat-tel", (390, 844, 2, True), "vie", CHAT, [
        ("tick", 200), ("js", "window.__chatOpen();"), ("tick", 90), ("js", TYPE % "/status"), ("tick", 60),
        ("gate", True), ("js", TYPE % "Ta journée, ça va ?"), ("tick", 30), ("stream", 4), ("tick", 4)]),
    ("mort", (1440, 900, 1, False), "vie", QUIET, [
        ("tick", 300), ("js", NO_SAY + "await fetch('/__scenario/naissance'); await refresh(true);"), ("tick", 300)]),
]


def run(shot, browser, out, cand):
    name, (w, h, dpr, mobile), scenario, storage, actions = shot
    E.server_get("/__reset")
    E.server_get("/__scenario/" + scenario)
    ctx = E.context(browser, w, h, dpr, mobile, storage)
    pg = ctx.new_page()
    errors = []
    E.watch(pg, errors)
    pg.goto(E.BASE_URL + "/?render=force", wait_until="load")
    pg.evaluate("document.fonts.ready.then(() => 1)")
    for kind, val in actions:
        if kind == "tick":
            E.ticks(pg, val)
        elif kind == "js":
            pg.evaluate("async () => { " + val + " }")
        elif kind == "until":    # avance image par image jusqu'à ce que la condition soit vraie (au plus max images)
            cond, most = val
            for i in range(most):
                if pg.evaluate("() => !!(" + cond + ")"):
                    break
                E.ticks(pg, 1, every=0)
                if i % 30 == 29:
                    pg.wait_for_timeout(8)
        elif kind == "gate":
            E.server_get("/__gate/" + ("on" if val else "off"))
        elif kind == "stream":   # réponse du chat : un morceau toutes les `val` images, jusqu'à la fin
            for _ in range(80):
                n = pg.evaluate("() => (document.querySelector('#chat-log .msg.streaming') || {textContent: ''}).textContent.length")
                done = pg.evaluate("() => !document.querySelector('#chat-log .typing') && !document.querySelector('#chat-log .streaming')")
                if done and n == 0:
                    break
                E.server_get("/__release")
                pg.wait_for_timeout(60)
                E.ticks(pg, val)
    pg.wait_for_timeout(50)
    path = os.path.join(out, name + ".png")
    pg.screenshot(path=path)
    if cand:
        for k in range(12):
            E.ticks(pg, 10)
            pg.screenshot(path=os.path.join(cand, f"{name}_{k:02d}.png"))
    ctx.close()
    E.server_get("/__gate/off")
    print(f"{path} ({os.path.getsize(path) // 1024} Ko)" + (f"  erreurs JS : {errors[:3]}" if errors else ""), flush=True)


# ---------------------------------------------------------------- ce qu'il te montre (panneaux de l'app)
TALL = (390, 1800, 2, True)        # téléphone, écran haut : tout le panneau tient sans défiler
MUTE = "document.getElementById('say').style.display = 'none'; window.talk = () => {};"


def open_app(browser, size, scenario="vie", storage=CHAT):
    E.server_get("/__reset")
    E.server_get("/__scenario/" + scenario)
    w, h, dpr, mobile = size
    ctx = E.context(browser, w, h, dpr, mobile, storage)
    pg = ctx.new_page()
    errors = []
    E.watch(pg, errors)
    pg.goto(E.BASE_URL + "/?render=force", wait_until="load")
    pg.evaluate("document.fonts.ready.then(() => 1)")
    E.ticks(pg, 200)
    pg.evaluate("() => { " + MUTE + " }")
    return ctx, pg, errors


def act(pg, code, ticks=0):
    r = pg.evaluate("async () => { " + code + " }")
    if ticks:
        E.ticks(pg, ticks, every=10)
    return r


def box(pg, sel, i=0):
    """Rectangle (px CSS) du i-ème élément qui correspond : top, bottom, left, right."""
    r = pg.evaluate("([s, i]) => { const e = document.querySelectorAll(s)[i]; if (!e) return null; const b = e.getBoundingClientRect(); return [b.top, b.bottom, b.left, b.right]; }", [sel, i])
    if r is None:
        raise SystemExit(f"capture : élément introuvable {sel} [{i}]")
    return r


def screen(pg):
    return Image.open(io.BytesIO(pg.screenshot(type="png"))).convert("RGB")


def columns(parts, dpr, gap=28):
    """Colonnes côte à côte, comme les colonnes d'un journal : parts = [(image, y0, y1)] en px CSS, sur le fond du panneau."""
    crops = [im.crop((0, int(y0 * dpr), im.width, int(min(y1 * dpr, im.height)))) for im, y0, y1 in parts]
    bg = crops[0].getpixel((6, crops[0].height - 6))
    W = sum(c.width for c in crops) + gap * dpr * (len(crops) - 1)
    out = Image.new("RGB", (W, max(c.height for c in crops)), bg)
    x = 0
    for c in crops:
        out.paste(c, (x, 0))
        x += c.width + gap * dpr
    return out


def save_png(im, path, limit=1.9e6):
    """PNG optimisé ; réduit un peu s'il dépasse la limite de poids (jamais agrandi)."""
    while True:
        im.save(path, optimize=True)
        if os.path.getsize(path) <= limit or im.width < 900:
            return
        im = im.resize((int(im.width * .9), int(im.height * .9)), Image.LANCZOS)


def cap_positions(browser, out):
    ctx, pg, errors = open_app(browser, TALL)
    act(pg, "openSec('positions');", 140)
    act(pg, "document.querySelector('#positions article.pos .th-head').click();", 40)
    im = screen(pg)
    th, art = box(pg, "#positions article.pos .th2"), box(pg, "#positions article.pos")
    save_png(columns([(im, 0, th[0] - 14), (im, th[0] - 14, art[1] + 10)], TALL[2]), os.path.join(out, "positions.png"))
    ctx.close()
    return errors


def cap_journal(browser, out):
    ctx, pg, errors = open_app(browser, TALL)
    act(pg, "openSub('historique', 'journal');", 140)
    act(pg, "document.querySelector('#journal .item .th-head').click();", 40)
    im = screen(pg)
    i0, i1 = box(pg, "#journal .item", 0), box(pg, "#journal .item", 1)
    last, k = i1, 2   # colonne de droite : les entrées suivantes, tant qu'elles tiennent dans la hauteur de la gauche
    while k < 12:
        nxt = box(pg, "#journal .item", k)
        if nxt[1] - i1[0] > i0[1] + 12 or nxt[1] > TALL[1]:
            break
        last, k = nxt, k + 1
    save_png(columns([(im, 0, i0[1] + 6), (im, i1[0] - 6, last[1] + 6)], TALL[2]), os.path.join(out, "journal.png"))
    ctx.close()
    return errors


def cap_suivi(browser, out):
    ctx, pg, errors = open_app(browser, TALL)
    act(pg, "openSub('historique', 'trades');", 140)
    left = screen(pg)
    t7 = box(pg, "#trades .item", 7)
    act(pg, "openSec('survie');", 140)
    right = screen(pg)
    mi = box(pg, "#mirror")
    save_png(columns([(left, 0, t7[1] + 6), (right, 0, mi[1] + 10)], TALL[2]), os.path.join(out, "suivi.png"))
    ctx.close()
    return errors


def cap_rejouer(browser, out, fps=15, dur=5.2, width=720):
    """Le trade LINK (fixtures.SHOW) rejoué : animation de l'app (CSS en temps virtuel + SMIL piloté image par image)."""
    size = (390, 1100, 2, True)
    ctx, pg, errors = open_app(browser, size)
    act(pg, "openSub('historique', 'trades');", 140)
    tid = act(pg, "const b = [...document.querySelectorAll('#trades button.replay')].find(x => x.closest('.item').querySelector('.coin').textContent === 'LINK');"
                  "const d = b.closest('details'); d.open = true; return b.dataset.id;", 20)
    # pendant le rendu, seules les images animées comptent : l'app ne redessine pas le rejeu à chaque lecture de l'état
    act(pg, "const orig = drawReplay; window.drawReplay = (t, a) => a ? orig(t, true) : Promise.resolve();"
            f"document.querySelector('#trades button.replay[data-id=\"{tid}\"]').click();")
    for _ in range(200):   # bougies chargées (vraie attente réseau local), puis le dessin animé commence
        if pg.evaluate(f"() => !!document.querySelector('#rp-{tid} svg')"):
            break
        pg.wait_for_timeout(15)
    frames = tempfile.mkdtemp(prefix="redrock-rejouer-")
    step = """([id, t]) => { const s = document.querySelector('#rp-' + id + ' svg'); if (!s) return;
      if (s.__t0 == null) { s.__t0 = performance.now(); s.pauseAnimations(); }
      s.setCurrentTime(Math.max(0, (performance.now() - s.__t0) / 1000)); }"""
    for k in range(int(dur * fps)):
        pg.evaluate(step, [tid, k])
        it = box(pg, f"#trades .item:has(#rp-{tid})")
        rp = box(pg, f"#rp-{tid}")
        clip = {"x": 0, "y": max(0, it[0] - 6), "width": size[0], "height": rp[1] + 10 - max(0, it[0] - 6)}
        pg.screenshot(path=os.path.join(frames, f"f{k:04d}.png"), clip=clip)
        E.ticks(pg, int(60 / fps), every=0)
    path = os.path.join(out, "rejouer.webp")
    subprocess.run([E.ffmpeg(), "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(frames, "f%04d.png"),
                    "-vf", f"scale={width}:-1:flags=lanczos", "-c:v", "libwebp_anim", "-lossless", "0", "-q:v", "80",
                    "-compression_level", "6", "-loop", "0", path], check=True)
    shutil.rmtree(frames, ignore_errors=True)
    ctx.close()
    print(f"{path} ({os.path.getsize(path) // 1024} Ko)", flush=True)
    return errors


PANELS = {"positions": cap_positions, "journal": cap_journal, "suivi": cap_suivi, "rejouer": cap_rejouer}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--candidates")
    ap.add_argument("--soft", action="store_true", help="WebGL logiciel (sans carte graphique)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.candidates:
        os.makedirs(a.candidates, exist_ok=True)
    with sync_playwright() as p:
        b = E.launch(p, a.soft)
        for s in SHOTS:
            if not a.only or s[0] in a.only:
                run(s, b, a.out, a.candidates)
        for name, fn in PANELS.items():
            if not a.only or name in a.only:
                errs = fn(b, a.out)
                if name != "rejouer":
                    print(os.path.join(a.out, name + ".png"), f"({os.path.getsize(os.path.join(a.out, name + '.png')) // 1024} Ko)"
                          + (f"  erreurs JS : {errs[:3]}" if errs else ""), flush=True)
        b.close()


if __name__ == "__main__":
    main()
