"""Refait tous les médias du README public, de bout en bout, sans aucune donnée réelle.

    python -I -X utf8 tools/media/build.py                 # tout
    python -I -X utf8 tools/media/build.py --only teaser installation
    python -I -X utf8 tools/media/build.py --soft           # sans carte graphique (SwiftShader : bien plus lent)

1. dans le dépôt privé, exporte d'abord la version publique (tools/export_public.py --no-git) : l'app filmée est
   exactement celle de GitHub ; dans le dépôt public, filme directement dash/ ;
2. lance le serveur des médias (server.py) : l'app publique + une fausse API aux données inventées (fixtures.py) ;
3. captures PNG (capture.py), aperçu animé WebP (render.py apercu), musiques (music.py), vidéos MP4 (render.py),
   affiche du teaser (render.py --poster) ;
4. contrôle chaque image des vidéos (bulle, bouche, 3D, textes, images vides, sauts : render.py échoue au moindre
   défaut), mesure les vidéos et leur son (verify.py) et sort les planches contact dans tools/media/out/planches/ ;
5. écrit tout dans docs/media/ (dépôt privé : tools/public/docs/media/) (+ la musique seule : tools/media/out/teaser-musique.mp3) et vérifie
   les poids (vidéos ≤ 8 Mo : pièces jointes GitHub ≤ 10 Mo).
Rien n'est publié : regarder les planches une par une, puis committer.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
# dépôt privé : on filme l'export public (tools/export_public.py) et on écrit dans le modèle tools/public/ ;
# dépôt public (GitHub) : on filme directement dash/ et on écrit dans docs/media/
PRIVE = os.path.isfile(os.path.join(REPO, "tools", "export_public.py"))
OUT = os.path.join(REPO, "tools", "public", "docs", "media") if PRIVE else os.path.join(REPO, "docs", "media")
EXTRA = os.path.join(HERE, "out")
PORT = 8897
LIMITS = {".png": 2e6, ".webp": 6e6, ".gif": 6e6, ".mp4": 8e6}
STEPS = ["captures", "apercu", "teaser", "installation"]
POSTER_AT = 13.9   # le trio PC, TV, téléphone


def py(*args, **kw):
    return subprocess.run([sys.executable, "-I", "-X", "utf8", *args], check=True, **kw)


def main():
    sys.path.insert(0, HERE)
    import engine as E
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=STEPS)
    ap.add_argument("--soft", action="store_true")
    a = ap.parse_args()
    steps = a.only or STEPS
    soft = ["--soft"] if a.soft else []
    tmp = tempfile.mkdtemp(prefix="redrock-media-")
    export = os.path.join(tmp, "export")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(EXTRA, "planches"), exist_ok=True)
    if PRIVE:
        py(os.path.join(REPO, "tools", "export_public.py"), "--no-git", "--dest", export)
    app = os.path.join(export if PRIVE else REPO, "dash")
    srv = subprocess.Popen([sys.executable, "-I", "-X", "utf8", os.path.join(HERE, "server.py"),
                            "--app", app, "--port", str(PORT)])
    render = os.path.join(HERE, "render.py")
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/push/key", timeout=1)
                break
            except OSError:
                time.sleep(.2)
        if "captures" in steps:
            py(os.path.join(HERE, "capture.py"), "--out", OUT, *soft)
        if "apercu" in steps:
            py(render, "apercu", "--out", OUT, "--report", EXTRA, *soft)
        for name in ("teaser", "installation"):
            if name not in steps:
                continue
            wav = os.path.join(tmp, name + ".wav")
            dur = []
            if name == "installation":   # la musique prend la durée de la composition (calée sur la fin du terminal)
                d = py(render, name, "--duration", "--out", tmp, capture_output=True, text=True).stdout.strip().splitlines()[-1]
                dur = ["--dur", d]
            py(os.path.join(HERE, "music.py"), name, wav, *dur)
            py(render, name, "--out", OUT, "--audio", wav, "--report", EXTRA, *soft)
            if name == "teaser":
                py(render, name, "--poster", str(POSTER_AT), "--out", OUT, *soft)
                subprocess.run([E.ffmpeg(), "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k",
                                os.path.join(EXTRA, "teaser-musique.mp3")], check=True)
            py(os.path.join(HERE, "verify.py"), "video", os.path.join(OUT, name + ".mp4"), "--sheets", os.path.join(EXTRA, "planches"))
    finally:
        srv.terminate()
        srv.wait(10)
        shutil.rmtree(tmp, ignore_errors=True)
    bad = []
    for f in sorted(os.listdir(OUT)):
        size, lim = os.path.getsize(os.path.join(OUT, f)), LIMITS.get(os.path.splitext(f)[1])
        print(f"  {f:22s} {size / 1e6:6.2f} Mo" + ("   TROP GROS" if lim and size > lim else ""))
        if lim and size > lim:
            bad.append(f)
    if bad:
        sys.exit("fichiers trop gros : " + ", ".join(bad))
    print("Médias prêts dans", OUT, "- regarder les planches de", os.path.join(EXTRA, "planches"), "avant de committer.")


if __name__ == "__main__":
    main()
