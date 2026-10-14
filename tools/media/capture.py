"""Captures d'écran du README (PNG), en temps virtuel : mêmes images à chaque rendu.

    python tools/media/capture.py --out tools/public/docs/media [--only scene-pc] [--candidates DOSSIER]

Le serveur des médias doit tourner (server.py). --candidates enregistre en plus une série d'images autour
du moment choisi, pour en choisir un autre si le design a changé (puis ajuster le nombre d'images ci-dessous).
"""
import argparse
import os
import sys

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
        b.close()


if __name__ == "__main__":
    main()
