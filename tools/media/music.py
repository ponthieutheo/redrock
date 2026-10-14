"""Musiques des vidéos, entièrement synthétisées ici (numpy) : aucun échantillon, aucun son sous droits.

    python tools/media/music.py teaser musique-teaser.wav          # 26,5 s, calée sur teaser.html (120 BPM), les deux formats
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


# ---------------------------------------------------------------- teaser v3 (26,5 s, 120 BPM : un temps = 0,5 s, une mesure = 2 s)
# Bande-annonce moderne, racontée par le son : le cœur du perso (deux coups d'808 saturés) bat dès la première image ;
# groove trap en demi-temps (808 qui glisse, clap sec, charleston en doubles croches avec des roulements en triolets et
# en triples croches) ; accords « future bass » (supersaw large, pompe du sidechain) ; un crochet de lead court
# (mi-la-do… si-la) ; design sonore de bande-annonce : souffles sur chaque mouvement de caméra, cymbale inversée et
# montée avant les révélations, « braam » + chute de sub sur le titre et la mort, arrêt de bande (ralenti) et
# bégaiement numérique sur le choc, trait continu du moniteur cardiaque, vrai silence, puis le cœur qui repart et le drop.
BPM = 120
BEAT = 60 / BPM
S16 = BEAT / 4
# accords : notes de la nappe/supersaw, fondamentale de l'808
CH = {
    "Am": ([57, 60, 64, 69], 33), "F": ([53, 57, 60, 65], 29), "C": ([55, 60, 64, 67], 36), "G": ([55, 59, 62, 67], 31),
    "E": ([56, 59, 64, 68], 28), "Dm": ([57, 62, 65, 69], 26),
}
# instants partagés avec teaser.html (secondes) : chaque coupe et chaque mot qui claque tombe sur un temps
T = {"salut": 0.5, "hook1": 2.0, "hook2": 4.0, "titre": 6.0, "trade": 8.0, "trade2": 9.0, "chat": 10.0, "envoi": 10.5,
     "vie": 12.0, "seuil": 13.5, "ralenti": 15.0, "mort": 16.0, "noir": 16.25, "silence": 17.0, "tombe": 17.5, "plop": 17.7,
     "releve": 18.0, "atterrit": 18.6, "appareils": 20.0, "tv": 21.0, "tel": 22.0, "tap": 22.4, "fin": 24.0, "dur": 26.5}
# le crochet : (instant dans la phrase, note MIDI, durée) — mi, la, do… si, la (une mesure)
HOOK = [(0.0, 76, .2), (.25, 81, .2), (.5, 84, .6), (1.25, 83, .2), (1.5, 81, .5)]
HOOK_SOMBRE = [(0.0, 76, .2), (.25, 81, .2), (.5, 84, .6), (1.25, 83, .2), (1.5, 77, .55)]   # finit sur fa : ça tourne mal
HOOK_ESPOIR = [(0.0, 76, .2), (.25, 81, .2), (.5, 84, .4), (1.0, 86, .4), (1.5, 88, .5)]     # monte jusqu'au mi aigu


def lp_gain(f, fc, order=2):
    """Gain d'un passe-bas doux (Butterworth idéalisé) à la fréquence f : sert à « filtrer » les harmoniques additives."""
    return 1 / np.sqrt(1 + (f / np.maximum(fc, 1.0)) ** (2 * order))


def saw_stack(f, dur, voices=5, detune=12.0, fc=6000.0, width=0.8, maxf=11000.0):
    """Supersaw propre : `voices` dents de scie à bande limitée (additives, rien au-dessus de maxf), désaccordées de
    ±`detune` cents et réparties en stéréo ; fc (nombre ou fonction du temps) = passe-bas sur les harmoniques."""
    n = int(dur * SR)
    t = secs(n)
    fcv = fc(t) if callable(fc) else np.full(n, float(fc))
    L, R = np.zeros(n), np.zeros(n)
    for v in range(voices):
        x = (v / (voices - 1) * 2 - 1) if voices > 1 else 0.0
        fv = f * 2 ** (x * detune / 1200)
        ph0 = 1.7 * v
        sig = np.zeros(n)
        k = 1
        while k * fv < maxf:
            sig += np.sin(2 * np.pi * k * fv * t + ph0 * k) / k * lp_gain(k * fv, fcv)
            k += 1
        pan = x * width
        th = (pan + 1) * np.pi / 4
        L += sig * np.cos(th)
        R += sig * np.sin(th)
    return np.stack([L, R], 1) / voices


def supersaw(notes, dur, att=0.01, rel=0.25, fc=5200.0, g=1.0, detune=12.0):
    """Accord supersaw (future bass) : attaque nette, relâche douce, passe-bas sur les harmoniques."""
    out = None
    for nt in notes:
        x = saw_stack(hz(nt), dur + rel, voices=5, detune=detune, fc=fc)
        out = x if out is None else out + x
    n = len(out)
    t = secs(n)
    env = np.minimum(1, t / max(att, 1e-3)) * np.clip((dur + rel - t) / rel, 0, 1) ** 2
    return edges(out * env[:, None] / len(notes) * 0.9 * g, a=0.002, r=0.006)


def pluck_lead(m, dur, g=1.0):
    """Lead du crochet : trois dents de scie un peu désaccordées + octave, filtre qui se referme vite (pluck moderne)."""
    f = hz(m)
    fc = lambda t: 900 + 7000 * np.exp(-t * 14)
    x = saw_stack(f, dur + 0.15, voices=3, detune=9, fc=fc, width=0.5) + 0.35 * saw_stack(2 * f, dur + 0.15, voices=2, detune=6, fc=fc, width=0.7)
    n = len(x)
    t = secs(n)
    env = np.exp(-t * 2.2) * np.minimum(1, t / 0.002)
    g_ = int(dur * SR)
    env[g_:] *= np.cos(np.linspace(0, np.pi / 2, n - g_)) ** 2
    return edges(x * env[:, None] * 0.9 * g, a=0.0015, r=0.004)


def b808(m, dur, from_m=None, glide=0.08, drive=2.4, g=1.0):
    """808 : sinus grave saturé (harmoniques audibles sur un téléphone), petit coup de hauteur à l'attaque,
    glissé depuis la note précédente (`from_m`) ; longue tenue puis relâche."""
    n = int((dur + 0.08) * SR)
    t = secs(n)
    f1 = hz(m)
    f0 = hz(from_m) if from_m is not None else f1
    f = f1 + (f0 - f1) * np.exp(-t / glide * 3) if from_m is not None else f1 * np.ones(n)
    f = f * (1 + 0.6 * np.exp(-t * 55))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = np.exp(-t * 0.9) * np.minimum(1, t / 0.003)
    gt = int(dur * SR)
    env[gt:] *= np.cos(np.linspace(0, np.pi / 2, n - gt)) ** 2
    x = np.tanh(drive * x * env) / np.tanh(drive)
    return edges(x * 0.55 * g, a=0.003, r=0.01)


def kick2(punch=1.0, dur=0.38):
    """Grosse caisse moderne : corps qui plonge vite (180 → 48 Hz), clic court, légère saturation."""
    t = secs(int(dur * SR))
    f = 48 + 135 * np.exp(-t * 42)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)
    click = sos_filter(noise(len(t)), "bandpass", [1800, 6000]) * np.exp(-t * 600) * 0.35 * punch
    x = np.tanh(1.8 * (body + click)) / np.tanh(1.8)
    return edges(x, a=0.0005, r=0.03)


def clap2(g=1.0):
    """Clap/snare sec : trois claquements serrés + queue courte + corps tonal (200 Hz)."""
    n = int(0.36 * SR)
    t = secs(n)
    nz = sos_filter(noise(n), "bandpass", [1300, 8500])
    env = np.zeros(n)
    for k, off in enumerate((0.0, 0.008, 0.016)):
        mk = t >= off
        env[mk] += np.exp(-(t[mk] - off) * 170) * (0.75 if k < 2 else 1.0)
    mk = t >= 0.016
    env[mk] += np.exp(-(t[mk] - 0.016) * 16) * 0.38
    body = np.sin(2 * np.pi * 205 * t) * np.exp(-t * 28) * 0.3
    return edges((nz / 2.0 * env + body) * g, a=0.0005, r=0.03)


def heart(g=1.0, slow=1.0):
    """Battement de cœur « lub-dub » : deux coups d'808 sourds et saturés (le second plus haut, plus doux, 0,17 s
    après), avec un peu de médium (le « toc ») pour qu'on l'entende aussi sur un téléphone. slow > 1 : ralenti."""
    def thump(f0, f1, dur, amp):
        t = secs(int(dur * slow * SR))
        f = (f1 + (f0 - f1) * np.exp(-t * 26 / slow)) / slow ** 0.5
        ph = 2 * np.pi * np.cumsum(f) / SR
        body = (np.sin(ph) + 0.35 * np.sin(2 * ph)) * np.exp(-t * 12 / slow) * np.minimum(1, t / 0.005)
        knock = np.sin(2 * np.pi * 150 / slow ** 0.5 * t) * np.exp(-t * 45 / slow) * 0.3
        return edges((body + knock) * amp, a=0.002, r=0.04)
    a, b = thump(80, 46, 0.36, 1.0), thump(94, 56, 0.32, 0.68)
    off = int(0.17 * slow * SR)
    x = np.zeros(off + len(b))
    x[:len(a)] += a
    x[off:off + len(b)] += b
    return edges(np.tanh(1.5 * x) / np.tanh(1.5) * g, a=0.002, r=0.03)


def braam(notes=(33, 40, 45), dur=2.4, g=1.0, dark=False):
    """« Braam » de bande-annonce : dents de scie graves empilées dont le filtre s'ouvre d'un coup puis se referme,
    saturées ; long, large."""
    top = 1400 if dark else 2600
    fc = lambda t: 120 + top * (1 - np.exp(-t * 14)) * np.exp(-t * 1.3)
    out = None
    for nt in notes:
        x = saw_stack(hz(nt), dur, voices=4, detune=10, fc=fc, width=0.9, maxf=6000)
        out = x if out is None else out + x
    t = secs(len(out))
    env = (1 - np.exp(-t * 40)) * np.exp(-t * 1.2)
    y = np.tanh(1.7 * out * env[:, None]) / np.tanh(1.7)
    y = sos_filter(y, "low", 5000, 4)   # la saturation crée des aigus (et du repliement) : on les retire
    return edges(y * 0.85 * g, a=0.002, r=0.08)


def sub_drop(dur=1.8, f0=90.0, f1=28.0, g=1.0):
    """Chute de sub : sinus qui plonge de f0 à f1, saturé, longue fin."""
    t = secs(int(dur * SR))
    f = f1 + (f0 - f1) * np.exp(-t * 2.4)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.3)
    return edges(np.tanh(1.6 * x) / np.tanh(1.6) * 0.8 * g, a=0.003, r=0.08)


def rev_cymbal(dur=1.0, g=1.0):
    """Cymbale inversée : souffle brillant qui enfle jusqu'au temps fort (fin en 6 ms, pile sur le coup)."""
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    nz = sos_filter(sos_filter(noise(n), "high", 3000, 2), "low", 13000, 2)
    shimmer = sos_filter(noise(n), "bandpass", [6000, 11000]) * 0.4
    return edges((nz + shimmer) * x ** 3.2 * 0.35 * g, a=0.01, r=0.006)


def shimmer(dur=1.2, g=1.0):
    """Paillettes (la relève, les particules) : cloches aiguës en arpège rapide, très douces."""
    n = int(dur * SR)
    out = np.zeros(n)
    for k, m in enumerate((88, 91, 93, 96, 100, 103)):
        i = int(k * 0.045 * SR)
        t = secs(n - i)
        f = hz(m)
        out[i:] += (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t * 6)) * np.exp(-t * 4.5) * 0.18 * np.minimum(1, t / 0.002)
    return edges(out * g, a=0.002, r=0.05)


def flatline(dur=1.0, g=1.0):
    """Trait continu du moniteur cardiaque, travaillé : deux sinus à 2 Hz d'écart (battement lent), passe-bande,
    attaque de 15 ms ; le haut s'adoucit au fil de la seconde."""
    n = int(dur * SR)
    t = secs(n)
    x = np.sin(2 * np.pi * 988 * t) + 0.8 * np.sin(2 * np.pi * 990 * t + 0.4) + 0.12 * np.sin(2 * np.pi * 1976 * t) * np.exp(-t * 2)
    x *= np.minimum(1, t / 0.015)
    return edges(x * 0.1 * g, a=0.004, r=0.012)


def monitor_bip(g=1.0):
    """Bip du moniteur (avec le cœur) : court, doux, même timbre que le trait continu."""
    t = secs(int(0.1 * SR))
    x = (np.sin(2 * np.pi * 988 * t) + 0.8 * np.sin(2 * np.pi * 990 * t)) * np.exp(-t * 18) * np.minimum(1, t / 0.004)
    return edges(x * 0.1 * g, a=0.003, r=0.012)


def text_hit(g=1.0):
    """Mot qui claque à l'écran : petit souffle court + coup sourd, discret."""
    w = whoosh(0.16, 0.9)
    t = secs(len(w))
    thud = np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 40)) * t) * np.exp(-t * 18) * 0.5
    return edges((w + thud) * g, a=0.002, r=0.01)


def tape_stop(x, t0, dur):
    """Arrêt de bande à partir de t0 : la lecture ralentit jusqu'à zéro en `dur` s (la hauteur tombe), silence après."""
    i0, n = int(t0 * SR), int(dur * SR)
    tau = np.arange(n) / n
    pos = i0 + np.cumsum((1 - tau) ** 2)            # vitesse 1 → 0 (quadratique)
    seg_ = np.stack([np.interp(pos, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)
    seg_ *= np.cos(np.linspace(0, np.pi / 2, n))[:, None] ** 1.5   # s'éteint avec la vitesse
    y = x.copy()
    y[i0:i0 + n] = seg_
    y[i0 + n:] = 0
    return y


def hats(m, t0, t1, step=S16, g=0.55, pan=0.2):
    t = t0
    while t < t1 - 1e-6:
        m.add("drums", hat(g=g), t, pan=pan)
        t += step


def hat_roll(m, t0, t1, div=8, g0=0.3, g1=0.7):
    """Roulement de charleston : div coups par temps (6 = triolets de doubles croches, 8 = triples croches)."""
    n = int(round((t1 - t0) / (BEAT / div)))
    for i in range(n):
        m.add("drums", hat(g=g0 + (g1 - g0) * i / max(1, n - 1)), t0 + i * BEAT / div, pan=0.25 * (-1) ** i)


def snare_roll(m, t0, t1, div=4, g0=0.2, g1=0.7):
    n = int(round((t1 - t0) / (BEAT / div)))
    for i in range(n):
        m.add("drums", snare(g=g0 + (g1 - g0) * (i / max(1, n - 1)) ** 1.5), t0 + i * BEAT / div, pan=0.1 * (-1) ** i, send=0.08)


def hook(m, t0, notes, g=1.0, octave=0, send=0.25):
    for dt, nt, d in notes:
        m.add("music", pluck_lead(nt + octave, d, 1.0), t0 + dt, g=g, send=send)


def impact(m, t, g=1.0, dark=False, duck=None):
    """Coup de bande-annonce : grosse caisse, braam, chute de sub, crash."""
    m.add("drums", kick2(1.2), t, g=0.85 * g)
    m.add("fx", braam(dur=2.2, g=0.9 * g, dark=dark), t, send=0.25)
    m.add("fx", sub_drop(1.8, g=0.7 * g), t)
    m.add("drums", crash(2.0, 0.6 * g), t, send=0.2)
    if duck is not None:
        duck.append(t)


def trap_bar(m, t0, chords, duck, hat_rolls=()):
    """Une mesure de trap en demi-temps : grosse caisse sur 1 (et la « et » du 2), clap sur 3, charleston en doubles
    croches (roulements aux instants donnés), 808 qui glisse d'un accord à l'autre."""
    m.add("drums", kick2(), t0, g=0.75)
    m.add("drums", kick2(0.7), t0 + 0.75, g=0.5)
    duck += [t0, t0 + 0.75]
    m.add("drums", clap2(), t0 + 1.0, g=0.7, send=0.12)
    t = t0
    while t < t0 + 2.0 - 1e-6:
        if not any(a - 1e-6 <= t < b - 1e-6 for a, b in hat_rolls):
            m.add("drums", hat(g=0.75 if int(round((t - t0) / S16)) % 2 else 1.0), t, pan=0.2)
        t += S16
    for a, b in hat_rolls:
        hat_roll(m, a, b, div=6, g0=0.35, g1=0.6)


def teaser_vie():
    """0 → 15 s : jusqu'au ralenti (arrêt de bande sur 15 → 15,4 s)."""
    m = Mix(15.6)
    duck = []
    # 0 : premier coup sur la première image (la caméra fonce sur lui) ; le cœur bat
    m.add("fx", whoosh(0.7, 1.0), 0.0)
    m.add("drums", kick2(1.0), 0.0, g=0.7)
    m.add("fx", sub_drop(1.6, 80, 30, 0.6), 0.0)
    m.add("music", supersaw(CH["Am"][0], 2.0, att=0.4, rel=0.4, fc=900, g=0.45), 0.0, send=0.35)
    for tb in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0):
        m.add("drums", heart(0.95), tb, g=0.95)
    # 0,5 : « Salut ! » — le crochet, joueur
    hook(m, T["salut"], HOOK, g=0.75)
    # 2 → 6 : les questions. Charleston en croches (le temps qui passe), 808 tenue, nappe filtrée qui s'assombrit
    m.add("fx", text_hit(0.8), T["hook1"])
    hats(m, T["hook1"] + S16 * 2, T["hook2"], step=BEAT / 2, g=0.75)
    m.add("bass", b808(29, 1.9, g=0.8), T["hook1"])
    m.add("music", supersaw(CH["F"][0], 2.0, att=0.2, rel=0.3, fc=1100, g=0.45), T["hook1"], send=0.35)
    m.add("fx", text_hit(1.0), T["hook2"])
    m.add("fx", sub_drop(1.4, 70, 28, 0.6), T["hook2"])
    m.add("bass", b808(28, 1.6, from_m=33, glide=0.15, g=0.85), T["hook2"])
    m.add("music", supersaw(CH["E"][0], 1.7, att=0.1, rel=0.3, fc=800, g=0.5), T["hook2"], send=0.4)
    hook(m, T["hook2"], HOOK_SOMBRE, g=0.55, octave=-12, send=0.4)
    m.add("fx", rev_cymbal(1.2, 0.9), T["titre"] - 1.2)
    m.add("fx", riser(1.0, top=8000, g=0.6), T["titre"] - 1.0)
    # 6 : « Voici RedRock » — braam, chute de sub, accord, le crochet
    impact(m, T["titre"], duck=duck)
    m.add("music", supersaw(CH["Am"][0] + [76], 1.9, att=0.005, rel=0.3, fc=lambda t: 1500 + 6000 * np.exp(-t * 2.5), g=0.6), T["titre"], send=0.3)
    hook(m, T["titre"], HOOK, g=0.9)
    m.add("drums", heart(0.8), 7.0, g=0.8)
    m.add("fx", whoosh(0.5, 0.8), T["trade"] - 0.25)
    # 8 → 12 : il trade seul, le chat. Trap en demi-temps, 808 qui glisse, roulements de charleston
    prog = [("F", 29, None), ("C", 36, 29), ("G", 31, 36), ("Am", 33, 31)]
    for b in range(2):
        t0 = T["trade"] + 2 * b
        trap_bar(m, t0, None, duck, hat_rolls=[(t0 + 1.5, t0 + 2.0)] if b == 0 else [(t0 + 1.75, t0 + 2.0)])
    for k, (ch, root, prev) in enumerate(prog):
        t0 = T["trade"] + k
        m.add("bass", b808(root, 0.9, from_m=prev, g=0.85), t0)
        m.add("music", supersaw(CH[ch][0], 0.95, att=0.01, rel=0.2, fc=2600, g=0.42), t0, send=0.25)
    hook(m, T["trade"], HOOK, g=0.75)
    hook(m, T["chat"], HOOK, g=0.55, octave=-12)
    for tw in (T["trade2"], T["chat"]):
        m.add("fx", whoosh(0.5, 0.8), tw - 0.25)
    m.add("fx", tap(0.8), T["envoi"], pan=0.2)
    # 12 → 15 : l'enjeu. Le cœur accélère, charleston en doubles croches → triolets → triples croches, montée
    m.add("fx", whoosh(0.5, 0.8), T["vie"] - 0.25)
    m.add("fx", text_hit(1.0), T["vie"])
    m.add("bass", b808(26, 1.45, from_m=33, glide=0.1, g=0.85), T["vie"])
    m.add("bass", b808(28, 1.45, from_m=26, glide=0.12, g=0.9), T["seuil"])
    m.add("music", supersaw(CH["Dm"][0], 1.45, att=0.05, rel=0.1, fc=1200, g=0.45), T["vie"], send=0.3)
    m.add("music", supersaw(CH["E"][0], 1.5, att=0.05, rel=0.1, fc=lambda t: 900 + 2600 * t / 1.6, g=0.5), T["seuil"], send=0.3)
    impact(m, T["seuil"], g=0.6, dark=True, duck=duck)
    for tb in (12.0, 12.75, 13.5, 14.0, 14.5, 14.75, 15.0):
        m.add("drums", heart(1.0), tb, g=1.0)
        m.add("fx", monitor_bip(0.8), tb + 0.02, pan=0.15, send=0.25)
    hats(m, T["vie"], T["seuil"], step=S16, g=0.7)
    hat_roll(m, T["seuil"], 14.25, div=6, g0=0.4, g1=0.55)
    hat_roll(m, 14.25, T["ralenti"], div=8, g0=0.45, g1=0.75)
    snare_roll(m, 14.0, T["ralenti"], div=4, g0=0.15, g1=0.6)
    m.add("fx", riser(T["ralenti"] - T["seuil"], top=9000, g=0.9), T["seuil"])
    x = m.render(duck_times=duck, depth=0.6)
    return tape_stop(x, T["ralenti"], 0.42), m.onsets


def teaser_mort():
    """15 → 17 s : ralenti (un battement traîné, cymbale inversée), le choc (bégaiement, braam sombre), le trait
    continu ; coupé net à 17 s (vrai silence ensuite)."""
    off = T["ralenti"]
    m = Mix(T["silence"] - off)
    m.add("drums", heart(1.0, slow=1.6), 15.45 - off, g=1.0, send=0.35)
    m.add("fx", rev_cymbal(0.9, 1.0), T["mort"] - 0.9 - off)
    m.add("fx", swell(0.9, 0.8), T["mort"] - 0.9 - off)
    # le choc : trois bégaiements du coup (45 ms) puis le coup entier
    k = kick2(1.3)
    sl = edges(k[: int(0.04 * SR)], a=0.0005, r=0.008)
    for i in range(3):
        m.add("drums", sl, T["mort"] - off + i * 0.045, g=0.55 + 0.1 * i)
    tm = T["mort"] - off + 0.135
    m.add("drums", k, tm, g=0.9)
    m.add("fx", braam((28, 35, 40), dur=1.8, g=1.0, dark=True), T["mort"] - off, send=0.3)
    m.add("fx", sub_drop(1.6, 95, 25, 1.0), T["mort"] - off)
    m.add("fx", zap(0.8), T["mort"] - off, pan=-0.1)
    m.add("fx", flatline(T["silence"] - T["mort"], 1.0), T["mort"] - off, send=0.2)
    x = m.render(gate_at=T["silence"] - off, rt=1.6, wet=0.32)
    return x, [t + off for t in m.onsets] + [T["silence"]]


def zap(g=1.0, dur=0.24):
    """Bug numérique au moment du choc : un ton qui dégringole, haché à 26 Hz (hachage doux, sans clic)."""
    t = secs(int(dur * SR))
    f = 110 + 1600 * np.exp(-t * 20)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.3 * np.sin(3 * ph)) * np.exp(-t * 8) * (0.55 + 0.45 * np.cos(2 * np.pi * 26 * t))
    return edges(x * 0.3 * g, a=0.001, r=0.02)


def teaser_releve():
    """17,5 → 26,5 s : coup sourd et la tombe, le cœur qui repart, la montée, le drop, la carte de fin."""
    off = T["tombe"]
    m = Mix(T["dur"] - off)
    duck = []
    m.add("fx", sub_drop(2.4, 60, 24, 1.0), 0.0, send=0.2)
    m.add("drums", kick2(1.0), 0.0, g=0.7)
    m.add("fx", braam((33, 40), dur=1.6, g=0.5, dark=True), 0.0, send=0.3)
    m.add("fx", pop(g=0.6), T["plop"] - off, pan=-0.3, send=0.2)
    # 18 : le cœur repart (et le moniteur avec) ; la relève atterrit à 18,6 s (paillettes) ; la montée vers le drop
    for tb in (18.0, 18.75, 19.25, 19.5, 19.75):
        m.add("drums", heart(0.95), tb - off, g=0.95)
        m.add("fx", monitor_bip(0.7), tb - off + 0.02, pan=0.15, send=0.25)
    m.add("music", supersaw(CH["Am"][0], 2.0, att=0.3, rel=0.05,
                            fc=lambda t: 500 + 4500 * (t / 2.05) ** 2, g=0.5), T["releve"] - off, send=0.3)
    hook(m, T["releve"] - off, HOOK_ESPOIR, g=0.6)
    m.add("fx", pop(500, 1300, 0.6), T["atterrit"] - off, send=0.15)
    m.add("music", shimmer(1.4, 0.9), T["atterrit"] - off, send=0.45)
    m.add("fx", riser(1.0, top=10000, g=0.9), 19.0 - off)
    m.add("fx", rev_cymbal(1.0, 0.8), 19.0 - off)
    hat_roll(m, 19.0 - off, 19.5 - off, div=6, g0=0.3, g1=0.5)
    hat_roll(m, 19.5 - off, T["appareils"] - off, div=8, g0=0.45, g1=0.75)
    snare_roll(m, 19.5 - off, T["appareils"] - off, div=4, g0=0.2, g1=0.65)
    # 20 → 24 : le drop. Future bass : supersaw large qui pompe sur chaque temps, 808, clap sur 2 et 4, crochet
    impact(m, T["appareils"] - off, g=0.7, duck=duck)
    prog = [("Am", 33, None), ("F", 29, 33), ("C", 36, 29), ("G", 31, 36)]
    for b, (ch, root, prev) in enumerate(prog):
        t0 = T["appareils"] - off + b
        for q in range(2):
            m.add("drums", kick2(), t0 + q * BEAT, g=0.75)
            duck.append(t0 + q * BEAT)
        m.add("drums", clap2(), t0 + BEAT, g=0.7, send=0.12)
        hats(m, t0 + S16, t0 + 1.0, step=S16 * 2, g=0.85)
        m.add("drums", hat(True, 0.5), t0 + BEAT / 2, pan=0.25, send=0.05)
        m.add("bass", b808(root, 0.92, from_m=prev, g=0.9), t0)
        m.add("music", supersaw(CH[ch][0] + [CH[ch][0][0] + 12], 0.95, att=0.005, rel=0.15, fc=8500, g=0.7), t0, send=0.25)
    hook(m, T["appareils"] - off, HOOK, g=0.95, send=0.3)
    hook(m, T["tel"] - off, HOOK_ESPOIR, g=0.95, send=0.3)
    for tw in (T["tv"], T["tel"]):
        m.add("fx", whoosh(0.5, 0.8), tw - off - 0.25)
    m.add("fx", tap(0.9), T["tap"] - off, pan=0.2)
    hat_roll(m, 23.5 - off, T["fin"] - off, div=8, g0=0.35, g1=0.7)
    m.add("fx", rev_cymbal(0.5, 0.7), T["fin"] - off - 0.5)
    # 24 : carte de fin. Impact, accord large (la mineur + 9e) qui s'ouvre, écho du crochet, queue
    tf = T["fin"] - off
    impact(m, tf, g=0.9)
    m.add("music", supersaw([57, 64, 69, 71, 72, 76], 1.6, att=0.005, rel=0.8, fc=lambda t: 5200 * np.exp(-t * 0.8) + 600, g=0.6), tf, send=0.4)
    m.add("music", shimmer(1.6, 0.7), tf + 0.1, send=0.5)
    for k, (dt, nt) in enumerate(((0.5, 83), (0.75, 81), (1.25, 83), (1.5, 81))):
        m.add("music", pluck_lead(nt, 0.35, 1.0), tf + dt, g=0.5 / (1 + k), send=0.55)
    return m.render(duck_times=duck, depth=0.7, rel=0.16), [t + off for t in m.onsets]


def teaser(path, raw=False):
    a, oa = teaser_vie()
    b, ob = teaser_mort()
    c, oc = teaser_releve()
    n = int(round(T["dur"] * SR))
    x = np.zeros((n, 2))
    x[:len(a)] += a
    i = int(round(T["ralenti"] * SR))
    x[i:i + len(b)] += b[: n - i]
    i = int(round(T["tombe"] * SR))
    x[i:i + len(c)] += c[: n - i]
    info = {"sons": len(oa) + len(ob) + len(oc) - 1, "clics_suspects": click_scan(x, oa + ob + oc + [T["ralenti"] + 0.42])}
    if raw:
        write_wav(path, x / np.abs(x).max() * 0.5)
        return info
    info.update(master(path, x, TP=-1.5, fade_out=0.6))
    return info


# ---------------------------------------------------------------- installation (calme, 100 BPM)
# accords de la musique d'installation : nappe, basse, motif du pluck
CH_INST = {
    "Am": ([57, 60, 64, 69], 33, [76, 69, 72, 76]), "F": ([53, 57, 60, 65], 29, [72, 65, 69, 72]),
    "C": ([55, 60, 64, 67], 36, [76, 67, 72, 76]), "G": ([55, 59, 62, 67], 31, [74, 67, 71, 74]),
}


def installation(path, dur=34.0, raw=False):
    beat = 60 / 100
    bar = 4 * beat
    m = Mix(dur)
    duck = []
    seq = ["Am", "F", "C", "G"]
    t, k = 0.0, 0
    while t < dur - 0.5:
        ch = seq[k % 4]
        notes, root, mot = CH_INST[ch]
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
