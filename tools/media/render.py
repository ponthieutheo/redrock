"""Rendu image par image des compositions (aperçu animé du README, teaser, vidéo d'installation).

    python tools/media/render.py apercu --out DOSSIER                          # apercu.webp (animé ; --gif pour un GIF en plus)
    python tools/media/render.py teaser --out DOSSIER --audio musique.wav      # teaser.mp4 (+ journal des contrôles)
    python tools/media/render.py installation --out DOSSIER --audio musique.wav
    python tools/media/render.py teaser --stills 3,9.5,21 --out DOSSIER        # quelques images PNG pour vérifier
    python tools/media/render.py teaser --part fin --out DOSSIER               # une seule partie (images gardées)

Le serveur des médias doit tourner (server.py). Chaque image est calculée au bon instant (temps virtuel),
capturée en JPEG dans un dossier de travail, CONTRÔLÉE, puis le tout est encodé par ffmpeg (CRF relevé tant que
le fichier dépasse sa limite de poids : pas besoin de refaire le rendu).

Une composition peut être faite de parties (COMPS[...]["parts"]) : chaque partie est une page neuve (contexte,
scénario et apps neufs), rendue sur sa plage de temps ; les images s'enchaînent dans la même vidéo.
Contrôles de chaque image (COMP.probe dans la page, voir comp.js) : jamais de bulle de parole, bouche immobile
hors du chat, 3D allumée, aucun « undefined »/« NaN » à l'écran ; plus, côté Python : aucune image noire ou
presque uniforme, et pas de saut brutal d'une image à l'autre ailleurs qu'aux coupes prévues (COMP.cuts).
Le moindre défaut fait échouer le rendu (code de sortie 1) ; tout est écrit dans <nom>-controle.json.
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

STORE = {"redrock-hint": "1", "hc1-tama-day": "2026-10-14", "hc1.chatkey": "demo"}
COMPS = {
    "apercu": {"page": "apercu.html", "w": 960, "h": 600, "fps": 15, "dur": 12.0, "kind": "gif", "gif_w": 720},
    # parties : (nom, début, fin, scénario de départ, densité de pixels des apps). 26,5 s, 120 BPM (voir music.py).
    # Le même montage en deux formats : 16:9 (README, YouTube) et 9:16 (TikTok, Shorts, Reels : teaser.html?fmt=v)
    "teaser": {"page": "teaser.html", "w": 1920, "h": 1080, "fps": 30, "dur": 26.5, "kind": "mp4", "crf": 20, "max_mb": 7.6,
               "parts": [("salle", 0.0, 12.0, "vie", 2.0), ("mort", 12.0, 20.0, "danger", 2.5), ("appareils", 20.0, 26.5, "vie", 1.25)]},
    "teaser-vertical": {"page": "teaser.html", "query": "fmt=v", "w": 1080, "h": 1920, "fps": 30, "dur": 26.5, "kind": "mp4", "crf": 20, "max_mb": 7.6,
                        "parts": [("salle", 0.0, 12.0, "vie", 3.0), ("mort", 12.0, 20.0, "danger", 3.4), ("appareils", 20.0, 26.5, "vie", 1.3)]},
    # installation neuve : génération 1 ; il dit bonjour (pas de « hc1-tama-day ») ; « hc1-hatched » évite la scène de
    # relève que l'app joue sinon à la première ouverture (avec une tombe « GÉN. 1 » alors que personne n'est mort)
    # durée : celle de la page (COMP.dur, calée sur la fin du terminal) ; `render.py installation --duration` l'affiche
    "installation": {"page": "install.html", "w": 1920, "h": 1080, "fps": 30, "dur": None, "kind": "mp4", "crf": 21, "max_mb": 7.6,
                     "scenario": "neuf", "store": {"redrock-hint": "1", "hc1-hatched": "1"}, "dpr_frames": 1.3},
}
JUMP = 38.0   # écart moyen (0-255) entre deux vignettes successives au-delà duquel on parle de saut


def encode_mp4(c, frames, out, audio, crf):
    ff = E.ffmpeg()
    cmd = [ff, "-y", "-loglevel", "error", "-framerate", str(c["fps"]), "-i", os.path.join(frames, "f%05d.jpg")]
    if audio:
        cmd += ["-i", audio]
    # captures JPEG = plage complète : conversion explicite en yuv420p « TV », lu partout (sinon ffmpeg sort du yuvj420p)
    cmd += ["-map", "0:v"] + (["-map", "1:a"] if audio else [])
    cmd += ["-vf", "scale=in_range=full:out_range=limited,format=yuv420p", "-color_range", "tv",
            "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(c["fps"]),
            "-movflags", "+faststart", "-tune", "animation"]
    cmd += (["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest"] if audio else ["-an"])
    subprocess.run(cmd + [out], check=True)


def anim_from_frames(c, frames, out_webp, out_gif=None):
    """WebP animé (couleurs vraies, ~3 Mo) ; GIF en option : 256 couleurs, 12 i/s, deux fois plus lourd."""
    ff = E.ffmpeg()
    src = ["-framerate", str(c["fps"]), "-i", os.path.join(frames, "f%05d.png")]
    scale = f"scale={c['gif_w']}:-1:flags=lanczos"
    subprocess.run([ff, "-y", "-loglevel", "error", *src, "-vf", scale, "-c:v", "libwebp_anim", "-lossless", "0",
                    "-q:v", "75", "-compression_level", "6", "-preset", "picture", "-loop", "0", out_webp], check=True)
    if out_gif:
        vf = f"fps=12,{scale}"
        pal = os.path.join(frames, "palette.png")
        subprocess.run([ff, "-y", "-loglevel", "error", *src, "-vf", f"{vf},palettegen=max_colors=256", pal], check=True)
        subprocess.run([ff, "-y", "-loglevel", "error", *src, "-i", pal, "-lavfi",
                        f"{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", "-loop", "0", out_gif], check=True)


def thumb(jpeg):
    """Vignette 96×54 (sauts d'une image à l'autre) et contraste de l'image (écart entre ses pixels clairs et sombres ;
    un petit texte clair sur du noir compte aussi : on regarde les 0,1 % extrêmes, un peu pondérés)."""
    im = Image.open(io.BytesIO(jpeg)).convert("L")
    mid = np.asarray(im.resize((240, 135), Image.BILINEAR), dtype=float)
    c = max(np.percentile(mid, 99.5) - np.percentile(mid, 0.5), 0.8 * (np.percentile(mid, 99.9) - np.percentile(mid, 0.1)))
    return np.asarray(im.resize((96, 54), Image.BILINEAR), dtype=float), float(c)


def render_part(p, c, a, part, frames_dir, stills, log):
    """Rend une partie (ou toute la composition si part est None). Remplit log (contrôles image par image)."""
    name, t0, t1, scenario, dpr = part if part else (None, 0.0, c["dur"], c.get("scenario", "vie"), c.get("dpr_frames"))
    E.server_get("/__reset")
    E.server_get("/__scenario/" + scenario)
    fps = c["fps"]
    b = E.launch(p, a.soft)
    ctx = E.context(b, c["w"], c["h"], 1, False, c.get("store", STORE), dpr)
    pg = ctx.new_page()
    errors = []
    E.watch(pg, errors)
    q = [f"part={name}"] if name else []
    q += [c["query"]] if c.get("query") else []
    q += ["poster=1"] if a.poster is not None else []
    url = f"{E.BASE_URL}/media/{c['page']}" + ("?" + "&".join(q) if q else "")
    pg.goto(url, wait_until="load")
    pg.wait_for_function("window.COMP && window.C", timeout=20000)
    pg.evaluate("async () => { await document.fonts.ready; await COMP.init(); }")
    if not part:
        c["dur"] = c["dur"] or pg.evaluate("() => COMP.dur")
        t1 = c["dur"]
    cuts = pg.evaluate("() => COMP.cuts || []")
    moves = pg.evaluate("() => COMP.moves || []")   # mouvements rapides voulus (volets, glissements, effets) : sauts tolérés
    blanks = pg.evaluate("() => COMP.blanks || []")  # noirs voulus (la coupe au noir de la mort) : image vide tolérée
    cuts = cuts + [x for b in blanks for x in b]
    has_probe = pg.evaluate("() => typeof COMP.probe === 'function'")
    i0, i1 = round(t0 * fps), round(t1 * fps)
    if stills:
        mine = [s for s in stills if t0 - 1e-6 <= s < t1]
        if not mine:
            ctx.close()
            b.close()
            return
        i1 = min(i1, round(max(mine) * fps) + 1)
    dt = 1000 / fps
    prev = None
    pg.screenshot(type="jpeg", quality=10)   # une image jetée : la page et ses apps sont peintes avant la première vraie image
    tstart = time.time()
    for i in range(i0, i1):
        t = i / fps
        pg.evaluate("async ([t, dt]) => { await COMP.frame(t, dt); }", [t, dt])
        if stills:
            if any(abs(s - t) < 0.5 / fps for s in stills):
                if a.poster is not None:   # affiche : 1280×720 (README)
                    im = Image.open(io.BytesIO(pg.screenshot(type="png"))).convert("RGB").resize((1280, 720), Image.LANCZOS)
                    path = os.path.join(a.out, f"{a.comp}-poster.png")
                    im.save(path, optimize=True)
                    print(path, f"{os.path.getsize(path) / 1e6:.2f} Mo", flush=True)
                else:
                    pg.screenshot(path=os.path.join(a.out, f"{a.comp}_{t:05.2f}.png"))
                    print("image", f"{t:.2f}", flush=True)
            continue
        if c["kind"] == "gif":
            pg.screenshot(path=os.path.join(frames_dir, f"f{i:05d}.png"))
        else:
            jpg = pg.screenshot(type="jpeg", quality=94)
            with open(os.path.join(frames_dir, f"f{i:05d}.jpg"), "wb") as f:
                f.write(jpg)
            th, contrast = thumb(jpg)
            rec = {"i": i, "t": round(t, 3), "part": name, "luma": round(float(th.mean()), 1), "contraste": round(contrast, 1)}
            if prev is not None:
                rec["saut"] = round(float(np.abs(th - prev).mean()), 1)
            prev = th
            errs = []
            if has_probe:
                pr = pg.evaluate("(t) => COMP.probe(t)", t)
                rec["apps"] = pr["st"]
                errs += pr["errs"]
            if contrast < 24 and not any(b0 - 1e-6 <= t < b1 - 1e-6 for b0, b1 in blanks):   # image vide : noire, unie, pas encore dessinée
                errs.append(f"image vide (luma {th.mean():.0f}, contraste {contrast:.0f})")
            near_cut = any(abs(t - k) < 1.5 / fps for k in cuts) or i == i0 or any(m0 <= t <= m1 for m0, m1 in moves)
            if rec.get("saut", 0) > JUMP and not near_cut:
                errs.append(f"saut brutal ({rec['saut']}) hors des coupes prévues")
            rec["erreurs"] = errs
            log.append(rec)
        if (i - i0) % (fps * 2) == 0:
            print(f"{a.comp}{'/' + name if name else ''} {t:5.1f}/{c['dur']} s  ({time.time() - tstart:.0f} s)", flush=True)
    ctx.close()
    b.close()
    E.server_get("/__gate/off")
    if errors:
        print("erreurs JS :", errors[:5], flush=True)
        log.append({"js": errors[:20]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("comp", choices=sorted(COMPS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio")
    ap.add_argument("--stills", help="instants (s) à enregistrer en PNG, sans encoder la vidéo")
    ap.add_argument("--part", help="teaser : ne rendre que cette partie (images JPEG gardées dans --frames)")
    ap.add_argument("--frames", help="dossier des images (gardé) ; sinon dossier temporaire effacé à la fin")
    ap.add_argument("--report", help="dossier du journal des contrôles <nom>-controle.json (défaut : --out)")
    ap.add_argument("--gif", action="store_true", help="aperçu : produire aussi un GIF (plus lourd) en plus du WebP animé")
    ap.add_argument("--soft", action="store_true")
    ap.add_argument("--duration", action="store_true", help="affiche la durée de la composition et s'arrête")
    ap.add_argument("--poster", type=float, help="teaser : image d'affiche 1280×720 (<nom>-poster.png) à cet instant")
    a = ap.parse_args()
    c = COMPS[a.comp]
    if a.duration:
        if not c["dur"]:
            with sync_playwright() as p:
                b = E.launch(p, a.soft)
                pg = b.new_page()
                pg.goto(f"{E.BASE_URL}/media/{c['page']}", wait_until="domcontentloaded")
                pg.wait_for_function("window.COMP", timeout=20000)
                c["dur"] = pg.evaluate("() => COMP.dur")
                b.close()
        print(c["dur"])
        return
    os.makedirs(a.out, exist_ok=True)
    stills = [a.poster] if a.poster is not None else [float(x) for x in a.stills.split(",")] if a.stills else None
    frames_dir = None
    if not stills:
        frames_dir = a.frames or tempfile.mkdtemp(prefix="redrock-frames-")
        os.makedirs(frames_dir, exist_ok=True)
    parts = c.get("parts") or [None]
    if a.part:
        parts = [x for x in parts if x and x[0] == a.part]
    t0 = time.time()
    log = []
    try:
        with sync_playwright() as p:
            for part in parts:
                render_part(p, c, a, part, frames_dir, stills, log)
    finally:
        try:
            E.server_get("/__gate/off")
        except OSError:
            pass
    if stills:
        print(f"fini en {time.time() - t0:.0f} s")
        return
    bad = [r for r in log if r.get("erreurs") or r.get("js")]
    rdir = a.report or (frames_dir if a.part else a.out)
    os.makedirs(rdir, exist_ok=True)
    report = os.path.join(rdir, f"{a.comp}{'-' + a.part if a.part else ''}-controle.json")
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"images": len([r for r in log if "i" in r]), "images_fautives": len(bad), "journal": log}, f, ensure_ascii=False)
    jumps = sorted((r for r in log if "saut" in r), key=lambda r: -r["saut"])[:8]
    print("plus grands sauts :", [(r["t"], r["saut"]) for r in jumps])
    if bad:
        for r in bad[:20]:
            print("  FAUTE", r.get("t"), r.get("erreurs") or r.get("js"))
        print(f"{len(bad)} image(s) fautive(s) : voir {report}")
        if not a.part:
            sys.exit(1)
    if a.part:
        print(f"partie {a.part} : images dans {frames_dir} ; contrôle : {report} ; fini en {time.time() - t0:.0f} s")
        return
    if c["kind"] == "gif":
        anim_from_frames(c, frames_dir, os.path.join(a.out, a.comp + ".webp"), os.path.join(a.out, a.comp + ".gif") if a.gif else None)
    else:
        out = os.path.join(a.out, a.comp + ".mp4")
        crf = c["crf"]
        while True:   # poids limité (pièce jointe GitHub ≤ 10 Mo) : on relève le CRF tant qu'il le faut
            encode_mp4(c, frames_dir, out, a.audio, crf)
            mb = os.path.getsize(out) / 1e6
            print(f"{out} : {mb:.2f} Mo (CRF {crf})", flush=True)
            if mb <= c.get("max_mb", 99) or crf >= 30:
                break
            # un cran de CRF ≈ −11 % de poids : on saute directement près du bon réglage (puis cran par cran)
            crf += max(1, int(np.log(mb / c["max_mb"]) / np.log(1 / 0.89)))
        if mb > c.get("max_mb", 99):
            sys.exit(f"{out} trop lourd ({mb:.2f} Mo)")
    if not a.frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"contrôles : {report} (0 image fautive) ; fini en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
