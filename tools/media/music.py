"""Musiques des vidéos, entièrement synthétisées ici (numpy) : aucun échantillon, aucun son sous droits.

    python tools/media/music.py teaser musique-teaser.wav          # 22 s, calée sur teaser.html (120 BPM)
    python tools/media/music.py installation musique-install.wav   # boucle calme (100 BPM), durée de install.html
    python tools/media/music.py teaser out.wav --raw                # sans normalisation (pour régler le mix)

Synthèse soignée (personne n'écoute pendant le rendu, tout est vérifié par des mesures) :
  - additive : chaque son est une somme d'harmoniques sous Nyquist (pas de repliement), les aigus s'éteignent
    plus vite que le fondamental (effet de filtre naturel, sans filtre qui claque) ;
  - chaque son commence et finit à zéro (attaque et fin en cos², vérifié à l'ajout) : aucun clic ;
  - réverbération par convolution (réponse impulsionnelle de bruit amorti), pompe (sidechain) aux attaques douces ;
  - master : passe-haut 25 Hz (pas de composante continue), limiteur à anticipation, puis ffmpeg loudnorm en
    deux passes (linéaire) vers -14 LUFS, crête vraie ≤ -1,5 dBTP.
Les instants clés du teaser (changements de plan, mort, relève) sont ceux de teaser.html : les modifier ensemble.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 48000
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- briques
def secs(n):
    return np.arange(n) / SR


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def edges(x, a=0.002, r=0.01):
    """Début et fin en cos² : le son part de zéro et y revient (jamais de saut, donc jamais de clic)."""
    x = np.array(x, dtype=float, copy=True)
    n = len(x)
    na, nr = min(n // 2, max(2, int(a * SR))), min(n // 2, max(2, int(r * SR)))
    ramp_a = np.sin(np.linspace(0, np.pi / 2, na)) ** 2
    ramp_r = np.cos(np.linspace(0, np.pi / 2, nr)) ** 2
    if x.ndim == 1:
        x[:na] *= ramp_a
        x[-nr:] *= ramp_r
    else:
        x[:na] *= ramp_a[:, None]
        x[-nr:] *= ramp_r[:, None]
    return x


def noise(n):
    return rng.standard_normal(n)


def sos_filter(x, kind, f, order=2):
    f = np.atleast_1d(f) / (SR / 2)
    sos = signal.butter(order, f if len(f) > 1 else f[0], kind, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def additive(f, dur, amp, decay, maxf=12000.0, phase=0.0):
    """Somme d'harmoniques k·f (k·f < maxf) ; amp(k) et decay(k) (1/s) donnent le timbre et son extinction."""
    n = int(dur * SR)
    t = secs(n)
    out = np.zeros(n)
    k = 1
    while k * f < min(maxf, SR * 0.45):
        a = amp(k)
        if a > 1e-4:
            out += a * np.sin(2 * np.pi * k * f * t + phase * k) * np.exp(-decay(k) * t)
        k += 1
    return out


def release(x, gate, rel):
    """Note tenue `gate` secondes puis relâchée en `rel` secondes (cos²), coupée ensuite."""
    g, r = int(gate * SR), int(rel * SR)
    x = x[:g + r].copy()
    if len(x) > g:
        k = len(x) - g
        x[g:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
    return x


# ---------------------------------------------------------------- instruments
def kick(punch=1.0, dur=0.42):
    t = secs(int(dur * SR))
    f = 50 + 105 * np.exp(-t * 30)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8.5)
    click = sos_filter(noise(len(t)), "low", 4500) * np.exp(-t * 320) * 0.22 * punch
    x = np.tanh(1.4 * (body + click)) / np.tanh(1.4)
    return edges(x, a=0.0006, r=0.03)


def clap(dur=0.32):
    n = int(dur * SR)
    t = secs(n)
    nz = sos_filter(noise(n), "bandpass", [1200, 7000])
    env = np.zeros(n)
    for k, off in enumerate((0.0, 0.009, 0.018)):
        m = t >= off
        env[m] += np.exp(-(t[m] - off) * 150) * (0.7 if k < 2 else 1.0)
    m = t >= 0.018
    env[m] += np.exp(-(t[m] - 0.018) * 19) * 0.42
    body = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30) * 0.22
    return edges(nz / 2.2 * env + body, a=0.0006, r=0.03)


def snare(dur=0.22, g=1.0):
    n = int(dur * SR)
    t = secs(n)
    nz = sos_filter(noise(n), "bandpass", [1500, 7000]) / 2.0 * np.exp(-t * 24)
    body = np.sin(2 * np.pi * 200 * t) * np.exp(-t * 32) * 0.5
    return edges((nz + body) * g, a=0.0006, r=0.02)


def hat(open_=False, g=1.0):
    n = int((0.34 if open_ else 0.07) * SR)
    t = secs(n)
    nz = sos_filter(sos_filter(noise(n), "high", 7500, 4), "low", 14000, 2)
    return edges(nz * np.exp(-t * (11 if open_ else 85)) * 0.42 * g, a=0.0004, r=0.012)


def crash(dur=2.2, g=1.0):
    n = int(dur * SR)
    t = secs(n)
    nz = sos_filter(sos_filter(noise(n), "high", 4200, 2), "low", 13000, 2)
    return edges(nz * np.exp(-t * 2.0) * 0.16 * g, a=0.001, r=0.05)


def bass(m, dur):
    f = hz(m)
    x = additive(f, dur + 0.04, lambda k: [1, .42, .2, .1, .05][k - 1] if k <= 5 else 0, lambda k: 1.2 + .8 * k, maxf=900)
    x = np.tanh(1.6 * x) / np.tanh(1.6)
    return edges(release(x, dur, 0.03), a=0.004, r=0.004)


def pluck(m, dur, bright=1.0, cents=4.0):
    """Pluck en stéréo : deux voix à ±`cents` (léger, pas de bouillie), aigus qui s'éteignent vite."""
    out = []
    for c in (cents, -cents):
        f = hz(m) * 2 ** (c / 1200)
        x = additive(f, dur + 0.12, lambda k: 1 / k, lambda k: 3.5 + 1.1 * k, maxf=1200 + 7800 * bright, phase=0.3 * c)
        out.append(edges(release(x, dur, 0.1), a=0.002, r=0.004))
    n = min(len(o) for o in out)
    return np.stack([out[0][:n], out[1][:n]], 1) * 0.5


def lead(m, dur, bright=1.0):
    out = []
    for c in (6.0, -6.0):
        f = hz(m) * 2 ** (c / 1200)
        x = additive(f, dur + 0.15, lambda k: 1 / k, lambda k: 2.5 + 0.55 * k, maxf=2000 + 7000 * bright)
        out.append(edges(release(x, dur, 0.14), a=0.004, r=0.004))
    n = min(len(o) for o in out)
    return np.stack([out[0][:n], out[1][:n]], 1) * 0.35


def pad(notes, dur, att=0.35, rel=0.5, bright=0.35):
    """Nappe : harmoniques douces (1/k^1.7), attaque et relâche lentes, deux voix à ±5 cents (gauche, droite)."""
    n = int((dur + rel) * SR)
    t = secs(n)
    L, R = np.zeros(n), np.zeros(n)
    for m in notes:
        for c, side in ((5.0, 0), (-5.0, 1)):
            f = hz(m) * 2 ** (c / 1200)
            x = additive(f, dur + rel, lambda k: 1 / k ** 1.7, lambda k: 0.15 * k, maxf=400 + 3200 * bright, phase=1.1 * side)
            (L if side == 0 else R)[:len(x)] += x
    env = np.minimum(1, t / att) ** 2
    g = int(dur * SR)
    env[g:] *= np.cos(np.linspace(0, np.pi / 2, n - g)) ** 2
    st = np.stack([L * env, R * env], 1) / max(1, len(notes))
    return edges(st, a=0.004, r=0.004) * 0.5


def sub_boom(dur=2.8, f0=56, f1=27, g=1.0):
    t = secs(int(dur * SR))
    f = f1 + (f0 - f1) * np.exp(-t * 2.2)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    thud = sos_filter(noise(len(t)), "low", 260, 2) * np.exp(-t * 7) * 0.5
    return edges((x + thud) * g, a=0.003, r=0.08)


def banded_noise(dur, centers, gains):
    """Bruit dans des bandes fixes, mélangées par des gains qui varient lentement : un balayage sans artefact."""
    n = int(dur * SR)
    base = noise(n)
    out = np.zeros(n)
    for c, g in zip(centers, gains):
        out += sos_filter(base, "bandpass", [c / 1.35, min(c * 1.35, SR * 0.45)]) * g
    return out


def riser(dur, top=9000.0, g=1.0):
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    centers = np.geomspace(250, top, 12)
    pos = 0.05 + 0.95 * x ** 1.6          # bande la plus forte : monte avec le temps
    lc = np.log(centers / centers[0]) / np.log(centers[-1] / centers[0])
    gains = [np.exp(-((pos - p) / 0.13) ** 2) for p in lc]
    nz = banded_noise(dur, centers, gains)
    f = 180 * 2 ** (3.2 * x ** 1.5)        # ton qui monte (3,2 octaves)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.18
    env = x ** 2.2
    return edges((nz * 0.55 + tone) * env * g, a=0.01, r=0.006)


def whoosh(dur=0.5, g=1.0):
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    centers = np.geomspace(400, 6000, 8)
    pos = np.sin(np.pi * x)
    lc = np.linspace(0, 1, len(centers))
    gains = [np.exp(-((pos * 0.9 - p) / 0.2) ** 2) for p in lc]
    return edges(banded_noise(dur, centers, gains) * np.sin(np.pi * x) ** 2 * 0.35 * g, a=0.005, r=0.005)


def swell(dur, g=1.0):
    """Souffle inversé qui monte jusqu'au temps fort (fin douce en 6 ms)."""
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    nz = sos_filter(sos_filter(noise(n), "high", 900, 2), "low", 8000, 2)
    return edges(nz * x ** 3 * 0.3 * g, a=0.01, r=0.006)


def bonk(g=1.0):
    """Coup sourd et boisé (la tête qui tombe) : deux partiels qui descendent un peu, pas de bruit aigu."""
    t = secs(int(0.35 * SR))
    f = 150 + 60 * np.exp(-t * 40)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16) + 0.35 * np.sin(2 * np.pi * np.cumsum(f * 2.7) / SR) * np.exp(-t * 30)
    return edges(x * 0.5 * g, a=0.001, r=0.03)


def pop(f0=380.0, f1=950.0, g=1.0):
    """« Plop » (la tombe ou le nouveau qui surgit) : sinus qui monte vite, très court."""
    t = secs(int(0.14 * SR))
    f = f1 + (f0 - f1) * np.exp(-t * 45)
    return edges(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 26) * 0.4 * g, a=0.001, r=0.02)


def tap(g=1.0):
    t = secs(int(0.06 * SR))
    x = np.sin(2 * np.pi * 1450 * t) * np.exp(-t * 90) * 0.25
    return edges(x * g, a=0.0006, r=0.01)


def reverb(x, rt=1.3, pre=0.018, damp=7000.0, seed=11):
    """Convolution par une réponse de bruit amorti (gauche et droite décorrélées) : queue douce, sans métal."""
    r = np.random.default_rng(seed)
    n = int(rt * 1.4 * SR)
    t = secs(n)
    env = np.exp(-6.9 * t / rt)
    out = np.zeros((len(x) + n + int(pre * SR) - 1, 2))
    for ch in (0, 1):
        ir = sos_filter(r.standard_normal(n), "low", damp, 2) * env
        ir[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
        ir /= np.sqrt(np.sum(ir ** 2))
        ir = np.concatenate([np.zeros(int(pre * SR)), ir])
        y = signal.fftconvolve(x[:, ch], ir)
        out[:len(y), ch] = y
    return out[:len(x)]


# ---------------------------------------------------------------- mix
BUS_GAIN = {"drums": 1.0, "bass": 0.6, "music": 2.2, "fx": 0.7}   # équilibre : mesuré par bandes (verify.py audio)


class Mix:
    def __init__(self, dur):
        self.n = int(round(dur * SR))
        self.bus = {}
        self.events = 0
        self.onsets = []

    def _b(self, name):
        if name not in self.bus:
            self.bus[name] = np.zeros((self.n, 2))
        return self.bus[name]

    def add(self, bus, sig, t, pan=0.0, g=1.0, send=0.0):
        peak = float(np.abs(sig).max()) or 1.0
        first, last = np.abs(sig[0]).max(), np.abs(sig[-1]).max()
        assert first <= 1e-6 * peak and last <= 2e-3 * peak, f"son sans fondu ({bus} à {t:.3f} s) : clic garanti"
        i = int(round(t * SR))
        if i >= self.n or i < 0:
            return
        s = sig[: self.n - i] * g * BUS_GAIN.get(bus, 1.0)
        if s.ndim == 1:
            th = (pan + 1) * np.pi / 4
            s = np.stack([s * np.cos(th), s * np.sin(th)], 1) * np.sqrt(2)
        self._b(bus)[i:i + len(s)] += s
        if send:
            self._b("send")[i:i + len(s)] += s * send
        self.events += 1
        self.onsets.append(t)

    def render(self, duck_times=(), duck_buses=("bass", "music"), depth=0.5, rel=0.11, rt=1.3, wet=0.28, gate_at=None):
        """Somme des bus, pompe sous chaque grosse caisse, réverb, coupure nette (gate_at) avec fondu de 8 ms."""
        duck = np.ones(self.n)
        k_n = int(0.6 * SR)
        tt = secs(k_n)
        shape = depth * np.minimum(1, tt / 0.004) * np.exp(-tt / rel)   # attaque de 4 ms : la pompe ne claque pas
        for tk in duck_times:
            i = int(round(tk * SR))
            if 0 <= i < self.n:
                m = min(k_n, self.n - i)
                duck[i:i + m] *= 1 - shape[:m]
        out = np.zeros((self.n, 2))
        for name, b in self.bus.items():
            if name == "send":
                continue
            out += b * (duck[:, None] if name in duck_buses else 1)
        if "send" in self.bus:
            out += reverb(self.bus["send"], rt=rt) * wet
        if gate_at is not None:
            i, f = int(round(gate_at * SR)), int(0.008 * SR)
            g = np.ones(self.n)
            g[i - f:i] = np.cos(np.linspace(0, np.pi / 2, f)) ** 2
            g[i:] = 0
            out *= g[:, None]
        return out


def limiter(x, ceiling_db=-3.0, look=0.004, rel=0.12):
    """Limiteur à anticipation (crête d'échantillon) : le gain descend AVANT la crête et remonte en douceur."""
    ceil = 10 ** (ceiling_db / 20)
    peak = np.abs(x).max(axis=1)
    la = int(look * SR)
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    pk = maximum_filter1d(peak, size=2 * la + 1, origin=0)
    target = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    # relâche exponentielle (le gain ne remonte qu'à la vitesse `rel`), puis lissage de l'attaque sur la fenêtre
    a = np.exp(-1 / (rel * SR))
    g = np.empty_like(target)
    cur = 1.0
    for i, v in enumerate(target.tolist()):
        cur = v if v < cur else v + (cur - v) * a
        g[i] = cur
    g = uniform_filter1d(g, size=la + 1)   # fenêtre centrée, contenue dans le maintien de ±la : la crête reste sous le plafond
    g = np.minimum(g, 1.0)
    return x * g[:, None]


def click_scan(x, onsets, thr_db=18.0):
    """Clics : bouffées d'aigus (> 10 kHz, fenêtres de 0,5 ms) qui dépassent de `thr_db` leur voisinage (±25 ms)
    sans qu'aucune note ne commence à moins de 10 ms (attaque d'une charleston). Renvoie les instants suspects (doit être vide)."""
    from scipy.ndimage import median_filter
    hp = sos_filter(x.mean(1), "high", 10000, 4)
    w = int(0.0005 * SR)
    m = len(hp) // w
    e = (hp[:m * w] ** 2).reshape(m, w).mean(1)
    ref = median_filter(e, size=101)
    lvl, base = 10 * np.log10(e + 1e-20), 10 * np.log10(ref + 1e-20)
    sus = np.where((lvl - base > thr_db) & (lvl > -75))[0] * w / SR
    on = np.sort(np.asarray(onsets))
    bad = []
    for t in sus:
        j = np.searchsorted(on, t)
        near = min(abs(t - on[k]) for k in (j - 1, j) if 0 <= k < len(on)) if len(on) else 9
        if near > 0.010 and (not bad or t - bad[-1] > 0.01):
            bad.append(round(float(t), 4))
    return bad


def write_wav(path, x):
    wavfile.write(path, SR, x.astype(np.float32))


# ---------------------------------------------------------------- normalisation (ffmpeg loudnorm, deux passes)
def _ff():
    import engine as E
    return E.ffmpeg()


def loudnorm_measure(path, I=-14.0, TP=-1.5, LRA=11.0):
    r = subprocess.run([_ff(), "-hide_banner", "-nostats", "-i", path, "-af",
                        f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    return json.loads(m.group(0))


def loudnorm(src, dst, I=-14.0, TP=-1.5, LRA=11.0):
    """Deux passes : mesure, puis gain linéaire (pas de compression dynamique). Renvoie la mesure de sortie."""
    m = loudnorm_measure(src, I, TP, LRA)
    af = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
          f"linear=true:print_format=json")
    r = subprocess.run([_ff(), "-hide_banner", "-nostats", "-y", "-i", src, "-af", af, "-ar", str(SR), "-c:a", "pcm_f32le", dst],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S).group(0))
    if out.get("normalization_type") != "linear":
        raise SystemExit(f"loudnorm n'a pas pu rester linéaire : {out}")
    return out


def master(path, x, I=-14.0, TP=-1.5, fade_out=0.0):
    """Passe-haut 25 Hz, limiteur réglé pour que le gain linéaire vers -14 LUFS tienne sous TP, loudnorm 2 passes."""
    x = sos_filter(x, "high", 25, 2)
    x -= x.mean(axis=0)
    if fade_out:
        f = int(fade_out * SR)
        x[-f:] *= (np.cos(np.linspace(0, np.pi / 2, f)) ** 2)[:, None]
    x[-int(0.004 * SR):] = 0
    x /= np.abs(x).max()
    tmp = tempfile.mkdtemp(prefix="redrock-music-")
    raw = os.path.join(tmp, "raw.wav")
    ceiling = -1.0
    for _ in range(6):   # resserre le limiteur jusqu'à ce que le gain linéaire suffise
        y = limiter(x, ceiling)
        gr = 20 * np.log10(np.maximum(np.abs(y).max(1), 1e-9) / np.maximum(np.abs(x).max(1), 1e-9))
        write_wav(raw, y)
        m = loudnorm_measure(raw, I, TP)
        gain = I - float(m["input_i"])
        if float(m["input_tp"]) + gain <= TP - 0.2:
            break
        ceiling -= max(0.5, float(m["input_tp"]) + gain - TP + 0.3)
    out = loudnorm(raw, path, I, TP)
    shutil.rmtree(tmp, ignore_errors=True)
    loud = np.abs(x).max(1) > 10 ** ((ceiling - 6) / 20)
    return {"limiteur": {"plafond_dB": round(ceiling, 2), "réduction_max_dB": round(float(-gr.min()), 2),
                         "réduction_sup_1_dB": f"{float((gr < -1).sum() / max(1, loud.sum()) * 100):.1f} % des passages forts"},
            "loudnorm": out}


# ---------------------------------------------------------------- teaser (22 s, 120 BPM : un temps = 0,5 s, une mesure = 2 s)
BPM = 120
BEAT = 60 / BPM
S16 = BEAT / 4
# accords : nappe, basse, motif du pluck (rythme 3-3-2 en doubles croches)
CH = {
    "Am": ([57, 60, 64, 69], 33, [76, 69, 72, 76, 74, 72, 69]),
    "F": ([53, 57, 60, 65], 29, [72, 65, 69, 72, 71, 69, 65]),
    "C": ([55, 60, 64, 67], 36, [76, 67, 72, 76, 74, 72, 67]),
    "G": ([55, 59, 62, 67], 31, [74, 67, 71, 74, 72, 71, 67]),
    "E": ([56, 59, 64, 68], 28, [71, 64, 68, 71, 69, 68, 64]),
}
POS, LEN = [0, 3, 6, 8, 10, 12, 14], [3, 3, 2, 2, 2, 2, 2]
# instants partagés avec teaser.html (secondes)
T = {"titre": 2.0, "salle": 4.0, "chat": 6.0, "souffle": 7.75, "appareils": 8.0, "tv": 9.5, "tel": 11.0, "tap": 11.4,
     "trio": 13.0, "enjeu": 14.0, "mort": 16.0, "bonk": 16.967, "tombe": 17.667, "releve": 18.0, "atterrit": 18.567, "fin": 20.0, "dur": 22.0}
# scène de mort de l'app lancée à 15,8 s : yeux en croix à 16 s, la tête roule à 17 s, la tombe surgit à 17,7 s ;
# relève : le remplaçant tombe du ciel et rebondit vers 18,6 s


def motif(m, t0, ch, bright=1.0, g=1.0, octave=0, inst=None, send=0.22, gate=None):
    _, _, notes = CH[ch]
    for p, ln, nt in zip(POS, LEN, notes):
        t = t0 + p * S16
        if gate is not None and t >= gate:
            break
        d = ln * S16 * 0.9
        if inst == "lead":
            m.add("music", lead(nt + octave, d, bright), t, g=g * 0.8, send=send + 0.08)
        else:
            m.add("music", pluck(nt + octave, d, bright), t, g=g, send=send)


def drums(m, t0, t1, clap_on=True, hats16=False, open_hats=False, kick_g=1.0, duck=None):
    t = t0
    while t < t1 - 1e-6:
        m.add("drums", kick(), t, g=0.65 * kick_g)
        if duck is not None:
            duck.append(t)
        beat = int(round((t - t0) / BEAT))
        if clap_on and beat % 2 == 1:
            m.add("drums", clap(), t, g=0.62, send=0.12)
        last = t + BEAT > t1 + 1e-6   # dernier temps tronqué (souffle avant le refrain) : rien après t1
        if not last or t + BEAT / 2 < t1 - 1e-6:
            m.add("drums", hat(), t + BEAT / 2, pan=0.2, g=0.8)
            if open_hats:
                m.add("drums", hat(True, 0.7), t + BEAT / 2, pan=0.25, send=0.05)
        if hats16:
            for q in (1, 3):
                if t + q * BEAT / 4 < t1 - 1e-6:
                    m.add("drums", hat(g=0.45), t + q * BEAT / 4, pan=-0.2)
        t += BEAT


def bassline(m, t0, ch, bars=1, g=0.55, stop=None):
    root = CH[ch][1]
    for i in range(8 * bars):
        t = t0 + i * BEAT / 2
        if stop is not None and t >= stop - 1e-6:
            break
        note = root + (7 if i % 8 == 7 else 0)
        m.add("bass", bass(note, BEAT / 2 * 0.82), t, g=g)


def roll(m, t0, t1, g0=0.25, g1=0.8, div=4):
    n = int(round((t1 - t0) / (BEAT / div)))
    for i in range(n):
        k = i / max(1, n - 1)
        m.add("drums", snare(g=g0 + (g1 - g0) * k), t0 + i * BEAT / div, pan=0.1 * (-1) ** i, send=0.08)


def teaser_song():
    """Avant la mort (0 → 16 s), coupée net à 16 s."""
    m = Mix(T["mort"])
    duck = []
    # grille : Am | F | C | G | Am | F | G | E (une mesure = 2 s), puis silence, Am, coup final
    # 0-2 : accroche. Deux coups sur les deux phrases (0 et 1 s), pluck filtré, nappe
    for k, tk in enumerate((0.0, 1.0)):
        m.add("drums", kick(1.2), tk, g=1.0)
        m.add("fx", sub_boom(1.2, 60, 38, 0.3), tk)
        m.add("drums", clap(), tk, g=0.35, send=0.3)
        duck.append(tk)
    m.add("music", pad(CH["Am"][0], 2.0, att=0.25, bright=0.2), 0.0, g=0.55, send=0.3)
    motif(m, 0.0, "Am", bright=0.15, g=0.75, send=0.3)
    # 2-4 : titre. Impact, quatre temps, pluck qui s'ouvre, roulement vers 4 s
    m.add("drums", crash(g=0.9), T["titre"], send=0.15)
    m.add("fx", sub_boom(1.6, 58, 32, 0.4), T["titre"])
    for i in range(4):
        tk = T["titre"] + i * BEAT
        m.add("drums", kick(), tk, g=0.85)
        duck.append(tk)
    for i in range(8):
        m.add("drums", hat(g=0.35 + 0.06 * i), T["titre"] + 1.0 + i * BEAT / 4 + BEAT / 8, pan=0.2)
    m.add("music", pad(CH["F"][0], 2.0, att=0.1, bright=0.3), T["titre"], g=0.55, send=0.3)
    motif(m, T["titre"], "F", bright=0.45, g=0.85)
    roll(m, 3.0, 4.0, 0.12, 0.6, div=4)
    m.add("fx", swell(0.98, 0.8), 3.0)
    # 4-8 : la salle, le chat. Groove complet ; montée avant les appareils, souffle à 7,75
    for b, ch in enumerate(["C", "G"]):
        t0 = T["salle"] + 2 * b
        drums(m, t0, t0 + 2.0 if b == 0 else T["souffle"], duck=duck)
        bassline(m, t0, ch, stop=T["souffle"] if b == 1 else None)
        m.add("music", pad(CH[ch][0], 2.0 if b == 0 else T["souffle"] - t0, bright=0.4, rel=0.2), t0, g=0.5, send=0.3)
        motif(m, t0, ch, bright=0.9, g=0.9, gate=T["souffle"])
    m.add("drums", crash(g=0.8), T["salle"], send=0.15)
    m.add("fx", riser(T["souffle"] - T["chat"], g=0.75), T["chat"])
    roll(m, 7.0, T["souffle"], 0.15, 0.5, div=4)
    # 8-14 : les appareils. Le refrain : groove plein, charleston ouvert, lead à l'octave
    m.add("drums", crash(g=1.0), T["appareils"], send=0.2)
    m.add("fx", sub_boom(1.8, 62, 30, 0.45), T["appareils"])
    for b, ch in enumerate(["Am", "F", "G"]):
        t0 = T["appareils"] + 2 * b
        drums(m, t0, t0 + 2.0, hats16=True, open_hats=True, duck=duck)
        bassline(m, t0, ch)
        m.add("music", pad(CH[ch][0], 2.0, bright=0.5, rel=0.25), t0, g=0.5, send=0.3)
        motif(m, t0, ch, bright=1.0, g=0.85)
        motif(m, t0, ch, bright=0.7, g=0.5, octave=12, inst="lead")
    for tw in (T["tv"], T["tel"]):
        m.add("fx", whoosh(0.5, 0.8), tw - 0.25)
    m.add("fx", tap(0.9), T["tap"], pan=0.2)
    m.add("drums", crash(1.4, 0.6), T["trio"], send=0.15)
    roll(m, 13.5, 14.0, 0.2, 0.45, div=4)
    # 14-16 : l'enjeu. Accord de mi (tension), basse en doubles croches, roulement qui accélère, montée
    t0 = T["enjeu"]
    for i in range(4):
        m.add("drums", kick(), t0 + i * BEAT, g=0.75)
        duck.append(t0 + i * BEAT)
    for i in range(16):
        m.add("drums", hat(g=0.5 + 0.03 * i), t0 + i * S16, pan=0.2 * (-1) ** i)
    for i in range(16):
        m.add("bass", bass(CH["E"][1], S16 * 0.8), t0 + i * S16, g=0.5)
    m.add("music", pad(CH["E"][0], 2.0, att=0.2, bright=0.3, rel=0.05), t0, g=0.75, send=0.3)
    for i in range(8):   # demi-ton qui insiste : si / do
        m.add("music", pluck(71 + (i % 2), BEAT / 2 * 0.7, 0.6), t0 + i * BEAT / 2, g=0.6, send=0.25)
    for i in (1, 3):
        m.add("drums", clap(), t0 + i * BEAT, g=0.5, send=0.15)
    m.add("fx", riser(2.0, top=10000, g=1.25), t0)
    roll(m, 15.0, T["mort"], 0.25, 0.9, div=4)
    return m.render(duck_times=duck, gate_at=T["mort"]), m.onsets + [T["mort"]]


def teaser_after():
    """Après la mort (16 → 22 s) : silence et grondement, puis la relève et la carte de fin."""
    off = T["mort"]
    m = Mix(T["dur"] - off)
    duck = []
    m.add("fx", sub_boom(3.2, 58, 26, 1.2), 0.0, send=0.25)
    m.add("fx", bonk(0.9), T["bonk"] - off, send=0.2)
    m.add("fx", pop(g=0.8), T["tombe"] - off, pan=-0.3, send=0.2)
    m.add("music", pad(CH["Am"][0], 0.9, att=0.85, bright=0.15, rel=0.1), 17.0 - off, g=0.35, send=0.4)
    m.add("fx", swell(0.995, 0.9), 17.0 - off)
    # 18-20 : la relève
    t0 = T["releve"] - off
    m.add("drums", crash(g=1.0), t0, send=0.2)
    m.add("fx", sub_boom(1.6, 62, 30, 0.4), t0)
    drums(m, t0, t0 + 2.0, hats16=True, open_hats=True, duck=duck)
    bassline(m, t0, "Am")
    m.add("music", pad(CH["Am"][0], 2.0, bright=0.5, rel=0.2), t0, g=0.5, send=0.3)
    motif(m, t0, "Am", bright=1.0, g=0.85)
    motif(m, t0, "Am", bright=0.7, g=0.5, octave=12, inst="lead")
    m.add("fx", pop(500, 1300, 0.7), T["atterrit"] - off, send=0.15)
    roll(m, 19.5 - off, T["fin"] - off, 0.2, 0.6, div=4)
    # 20 : coup final sur le logo, accord de la mineur (+ 9e), queue courte
    tf = T["fin"] - off
    m.add("drums", kick(1.1), tf, g=0.75)
    m.add("drums", crash(2.0, 0.9), tf, send=0.25)
    m.add("fx", sub_boom(2.0, 60, 30, 0.35), tf)
    for nt in (57, 64, 69, 71, 72, 76):
        m.add("music", pluck(nt, 1.2, 0.8, cents=3), tf, g=0.26, send=0.45)
    m.add("music", pad([45, 57, 64, 71, 72], 1.0, att=0.02, rel=0.8, bright=0.4), tf, g=0.45, send=0.4)
    return m.render(duck_times=duck), [t + off for t in m.onsets]


def teaser(path, raw=False):
    a, oa = teaser_song()
    b, ob = teaser_after()
    n = int(round(T["dur"] * SR))
    x = np.zeros((n, 2))
    x[:len(a)] += a
    i = int(round(T["mort"] * SR))
    x[i:i + len(b)] += b[: n - i]
    info = {"sons": len(oa) + len(ob) - 1, "clics_suspects": click_scan(x, oa + ob)}
    if raw:
        write_wav(path, x / np.abs(x).max() * 0.5)
        return info
    info.update(master(path, x, fade_out=0.35))
    return info


# ---------------------------------------------------------------- installation (calme, 100 BPM)
def installation(path, dur=34.0, raw=False):
    beat = 60 / 100
    bar = 4 * beat
    m = Mix(dur)
    duck = []
    seq = ["Am", "F", "C", "G"]
    t, k = 0.0, 0
    while t < dur - 0.5:
        ch = seq[k % 4]
        notes, root, mot = CH[ch]
        end = min(dur - 1.2, t + bar)
        if end - t < 0.3:
            break
        m.add("music", pad(notes, end - t, att=0.6, bright=0.25, rel=0.6), t, g=0.45, send=0.35)
        for i in range(4):
            tb = t + i * beat
            if tb >= dur - 1.5:
                break
            if k >= 2:
                m.add("drums", kick(0.6), tb, g=0.5 if i % 2 == 0 else 0.35)
                duck.append(tb)
                if i % 2 == 1:
                    m.add("drums", clap(), tb, g=0.22, send=0.15)
            m.add("drums", hat(g=0.85), tb + beat / 2, pan=0.25)
        if k >= 1:
            m.add("bass", bass(root, bar * 0.45), t, g=0.4)
            m.add("bass", bass(root + 7, bar * 0.18), t + bar * 0.625, g=0.3)
        for i, nt in enumerate(mot[:4]):
            tn = t + i * beat
            if tn < dur - 1.5:
                m.add("music", pluck(nt, beat * 0.8, 0.6), tn, pan=0.2 * (-1) ** i, g=0.45 if k % 2 == 0 else 0.35, send=0.35)
        t += bar
        k += 1
    x = m.render(duck_times=duck, depth=0.3)
    info = {"sons": m.events, "clics_suspects": click_scan(x, m.onsets)}
    if raw:
        write_wav(path, x / np.abs(x).max() * 0.5)
        return info
    info.update(master(path, x, I=-16.0, fade_out=2.0))
    return info


if __name__ == "__main__":
    which, out = sys.argv[1], sys.argv[2]
    raw = "--raw" in sys.argv
    if which == "teaser":
        info = teaser(out, raw)
    else:
        dur = float(sys.argv[sys.argv.index("--dur") + 1]) if "--dur" in sys.argv else 34.0
        info = installation(out, dur, raw)
    print(json.dumps(info, ensure_ascii=False))
