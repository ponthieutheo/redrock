"""Outils communs : Chrome sans fenêtre (GPU si possible), pages en temps virtuel, ffmpeg."""
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
BASE_URL = os.environ.get("MEDIA_URL", "http://127.0.0.1:8897")
VT_BASE = "2026-10-14T12:20:00Z"   # même horloge que fixtures.VNOW
GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
SOFT_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
COMMON_ARGS = ["--autoplay-policy=no-user-gesture-required", "--disable-background-timer-throttling",
               "--disable-renderer-backgrounding", "--hide-scrollbars", "--mute-audio"]


def ffmpeg():
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not exe:
        winget = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
        if os.path.isdir(winget):
            for root, _d, files in os.walk(winget):
                if "ffmpeg.exe" in files:
                    return os.path.join(root, "ffmpeg.exe")
        raise SystemExit("ffmpeg introuvable (variable FFMPEG ou PATH)")
    return exe


def launch(p, soft=False):
    """Chrome sans fenêtre ; WebGL sur la carte graphique (D3D11) sauf --soft (SwiftShader, beaucoup plus lent)."""
    kw = {"headless": True, "args": (SOFT_ARGS if soft else GPU_ARGS) + COMMON_ARGS}
    if os.path.isfile(CHROME):
        kw["executable_path"] = CHROME
    return p.chromium.launch(**kw)


def init_script(storage=None, dpr_frames=None):
    """Script injecté dans la page ET ses iframes : horloge virtuelle + réglages de l'app (localStorage)."""
    pre = [f"window.__VT_BASE = Date.parse('{VT_BASE}');"]
    if dpr_frames:   # densité de pixels forcée dans les iframes (app réduite dans une composition)
        pre.append(f"if (window.top !== window) window.__VT_DPR = {dpr_frames};")
    for k, v in (storage or {}).items():
        pre.append(f"try {{ localStorage.setItem({k!r}, {v!r}); }} catch (e) {{}}")
    with open(os.path.join(HERE, "inject.js"), encoding="utf-8") as f:
        return "\n".join(pre) + "\n" + f.read() + "\n" + OFFLINE


# Rien ne sort de la machine : l'app ne doit afficher que les données inventées du serveur des médias. Les graphiques
# de position de l'app lisent d'ordinaire les vraies bougies d'Hyperliquid (requête et WebSocket publics) : ici les
# requêtes vers un autre site échouent et le WebSocket est un faux, ouvert mais muet (l'app garde ses bougies locales).
OFFLINE = """(() => {
  const RF = window.fetch.bind(window);
  window.fetch = (u, o) => { const s = String(u && u.url || u);
    if (/^https?:/i.test(s) && !s.startsWith(location.origin)) return Promise.reject(new TypeError("hors ligne (médias)"));
    return RF(u, o); };
  window.WebSocket = class { constructor() { this.readyState = 0; setTimeout(() => { this.readyState = 1; this.onopen && this.onopen({}); }, 40); }
    send() {} close() { this.readyState = 3; } addEventListener() {} removeEventListener() {} };
})();"""


def context(browser, w, h, dpr=1, mobile=False, storage=None, dpr_frames=None):
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, has_touch=mobile, is_mobile=mobile,
                              timezone_id="Europe/Paris", locale="fr-FR")
    ctx.add_init_script(init_script(storage, dpr_frames))
    return ctx


def watch(page, errors):
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "404" not in m.text else None)


def ticks(page, n, every=30, frame=None):
    """Avance l'horloge de n images à 60 i/s (dans la page ou dans une iframe) ; laisse respirer le réseau."""
    target = frame or page
    for i in range(n):
        target.evaluate("() => window.__vt.tick(1000 / 60)")
        if every and i % every == every - 1:
            page.wait_for_timeout(8)


def server_get(path, tries=3):
    """Ordre au serveur des médias (scénario, gate…) ; patient si la machine est chargée."""
    import time
    import urllib.request
    for k in range(tries):
        try:
            with urllib.request.urlopen(BASE_URL + path, timeout=30) as r:
                return r.read()
        except OSError:
            if k == tries - 1:
                raise
            time.sleep(1)
