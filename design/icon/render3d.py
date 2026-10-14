"""Rend le personnage 3D seul (fond transparent) avec design/icon/perso3d.html, servi par un petit serveur local
qui sert dash/ (three.js embarqué, personnage). Sortie : PNG RGBA.
    python design/icon/render3d.py sortie.png "s=1024&mode=win&t=2.2&yaw=-0.28"
"""
import os, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..", "..", "dash")
PAGE = open(os.path.join(HERE, "perso3d.html"), encoding="utf-8").read()


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path):
        return "text/javascript" if path.endswith(".js") else super().guess_type(path)

    def do_GET(self):
        if self.path.startswith("/__perso3d.html"):
            b = PAGE.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(b)
            return
        return super().do_GET()


def render(out, query):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(H, directory=os.path.abspath(DASH)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    size = int(dict(x.split("=") for x in query.split("&") if "=" in x).get("s", 1024))
    try:
        with sync_playwright() as p:
            # CHROME=chemin/vers/chrome pour utiliser un Chrome installé ; sinon le Chromium de Playwright (playwright install chromium)
            b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None, headless=True,
                                  args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            pg = b.new_page(viewport={"width": size, "height": size})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(f"http://127.0.0.1:{srv.server_port}/__perso3d.html?{query}")
            pg.wait_for_function("window.__done === true", timeout=60000)
            pg.locator("canvas").screenshot(path=out, omit_background=True)
            b.close()
            if errs:
                print("erreurs JS :", errs[:3])
    finally:
        srv.shutdown()


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
    print("ok", sys.argv[1])
