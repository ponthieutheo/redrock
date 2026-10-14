"""Vérifications des vidéos et des musiques (personne ne regarde ni n'écoute pendant le rendu : on mesure).

    python tools/media/verify.py video tools/public/docs/media/teaser.mp4 --sheets DOSSIER   # format + planches
    python tools/media/verify.py audio fichier.wav|.mp3|.mp4                                   # sonie, crête, spectre

Vidéo : codec, taille, i/s, yuv420p, faststart (moov avant mdat), durée, poids ; planches contact d'une image
toutes les 0,25 s (horodatées) à regarder une par une.
Audio : sonie intégrée (LUFS), LRA, crête vraie (dBTP) par ffmpeg ebur128 ; composante continue, écrêtage,
plus grand saut d'un échantillon au suivant, énergie par bande de fréquences.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

BANDS = [("sub 20-60", 20, 60), ("grave 60-250", 60, 250), ("bas-médium 250-2k", 250, 2000),
         ("haut-médium 2k-6k", 2000, 6000), ("aigu 6k-20k", 6000, 20000)]


def ffprobe():
    ff = E.ffmpeg()
    p = os.path.join(os.path.dirname(ff), "ffprobe" + (".exe" if ff.lower().endswith(".exe") else ""))
    return p if os.path.isfile(p) else "ffprobe"


def video_info(path):
    r = subprocess.run([ffprobe(), "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8")
    j = json.loads(r.stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    with open(path, "rb") as f:
        head = f.read(1 << 20)
    moov, mdat = head.find(b"moov"), head.find(b"mdat")
    return {"fichier": os.path.basename(path), "octets": os.path.getsize(path), "Mo": round(os.path.getsize(path) / 1e6, 2),
            "durée_s": round(float(j["format"]["duration"]), 3), "vidéo": f"{v['codec_name']} {v.get('profile', '')}",
            "taille": f"{v['width']}x{v['height']}", "pix_fmt": v["pix_fmt"], "i/s": v["r_frame_rate"],
            "images": int(v.get("nb_frames", 0)), "audio": f"{a['codec_name']} {a.get('sample_rate')} Hz {a.get('channels')} can." if a else None,
            "faststart": moov >= 0 and (mdat < 0 or moov < mdat)}


def sheets(path, out, every=0.25, cols=6, rows=4, width=480, prefix="planche"):
    """Une image toutes les `every` s, en planches de cols×rows, horodatées. Renvoie la liste des planches."""
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="redrock-sheet-")
    # une image toutes les `every` secondes (la plus proche de k·every)
    subprocess.run([E.ffmpeg(), "-v", "error", "-y", "-i", path, "-vf", f"fps=1/{every},scale={width}:-1",
                    os.path.join(tmp, "f%04d.png")], check=True)
    files = sorted(os.listdir(tmp))
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    per = cols * rows
    made = []
    for s in range(0, len(files), per):
        chunk = files[s:s + per]
        im0 = Image.open(os.path.join(tmp, chunk[0]))
        w, h = im0.size
        sheet = Image.new("RGB", (cols * w + (cols + 1) * 4, rows * h + (rows + 1) * 4), (40, 40, 40))
        for k, f in enumerate(chunk):
            im = Image.open(os.path.join(tmp, f)).convert("RGB")
            x, y = 4 + (k % cols) * (w + 4), 4 + (k // cols) * (h + 4)
            sheet.paste(im, (x, y))
            d = ImageDraw.Draw(sheet)
            label = f"{(s + k) * every:5.2f} s"
            d.rectangle([x, y, x + 78, y + 24], fill=(0, 0, 0))
            d.text((x + 5, y + 2), label, fill=(255, 255, 0), font=font)
        p = os.path.join(out, f"{prefix}-{s // per + 1:02d}.jpg")
        sheet.save(p, quality=88)
        made.append(p)
    shutil.rmtree(tmp, ignore_errors=True)
    return made


def decode(path):
    """Décode n'importe quel fichier audio/vidéo en float32 48 kHz stéréo."""
    r = subprocess.run([E.ffmpeg(), "-v", "error", "-i", path, "-map", "a:0", "-f", "f32le", "-ac", "2", "-ar", "48000", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).astype(float)


def ebur128(path):
    r = subprocess.run([E.ffmpeg(), "-hide_banner", "-nostats", "-i", path, "-map", "a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = r.stderr[r.stderr.rfind("Summary:"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+|-inf)", s).group(1).replace("-inf", "-999"))
    return {"LUFS": g("I"), "LRA": g("LRA"), "crête_vraie_dBTP": g("Peak")}


def audio_report(path):
    x = decode(path)
    rep = ebur128(path)
    mono = x.mean(1)
    from scipy import signal
    f, p = signal.welch(mono, 48000, nperseg=8192)
    tot = np.trapezoid(p, f)
    bands = {}
    for name, lo, hi in BANDS:
        m = (f >= lo) & (f < hi)
        e = np.trapezoid(p[m], f[m])
        bands[name] = f"{e / tot * 100:5.1f} %  ({10 * np.log10(e / tot):6.1f} dB)"
    rep.update({"durée_s": round(len(x) / 48000, 3), "composante_continue": [round(float(v), 6) for v in x.mean(0)],
                "échantillons_écrêtés": int((np.abs(x) >= 0.999).sum()),
                "plus_grand_saut": round(float(np.abs(np.diff(x, axis=0)).max()), 4),
                "à_t_s": round(float(np.abs(np.diff(x, axis=0)).max(1).argmax() / 48000), 3), "bandes": bands})
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["video", "audio"])
    ap.add_argument("path")
    ap.add_argument("--sheets")
    ap.add_argument("--every", type=float, default=0.25)
    a = ap.parse_args()
    if a.kind == "video":
        print(json.dumps(video_info(a.path), ensure_ascii=False, indent=1))
        print(json.dumps(audio_report(a.path), ensure_ascii=False, indent=1))
        if a.sheets:
            pre = os.path.splitext(os.path.basename(a.path))[0]
            for p in sheets(a.path, a.sheets, a.every, prefix=pre):
                print(p)
    else:
        print(json.dumps(audio_report(a.path), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
