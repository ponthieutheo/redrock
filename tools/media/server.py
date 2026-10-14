"""Serveur local des médias : l'app PUBLIQUE (dossier dash/ d'un export) + une fausse API aux données inventées.

    python tools/media/server.py --app <export>/dash [--port 8897]

Rien ne sort de la machine (127.0.0.1 seulement), rien n'est lu dans les données de l'agent :
toutes les réponses viennent de fixtures.py. Les pages de composition (teaser.html, install.html…)
sont servies sous /media/.

Pilotage (pour les rendus image par image) :
  /__scenario/<nom>   change l'état renvoyé par /api/state (voir fixtures.py)
  /__gate/on|off      réponses du chat débitées à la demande (déterministe) ou en temps réel
  /__release          libère le morceau suivant de la réponse en cours (mode gate)
  /__reset            vide les messages ajoutés pendant le rendu
"""
import argparse
import importlib
import json
import mimetypes
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fixtures as F  # noqa: E402

S = {"scenario": "vie", "gate": False, "released": 0, "extra": [], "app": None}
COND = threading.Condition()
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png",
        ".json": "application/json", ".webmanifest": "application/manifest+json", ".css": "text/css",
        ".svg": "image/svg+xml", ".woff2": "font/woff2", ".ttf": "font/ttf", ".wav": "audio/wav"}


def chunks(text):
    """Découpe une réponse en petits morceaux, comme un flux de modèle (2 ou 3 mots à la fois)."""
    words, out, cur = text.split(" "), [], ""
    for i, w in enumerate(words):
        cur += w + (" " if i < len(words) - 1 else "")
        if len(cur) >= 9 or i == len(words) - 1:
            out.append(cur)
            cur = ""
    return out


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, root, rel):
        f = os.path.abspath(os.path.join(root, rel))
        if not f.startswith(os.path.abspath(root)) or not os.path.isfile(f):
            return self._send(404, b"", "text/plain")
        with open(f, "rb") as fh:
            body = fh.read()
        self._send(200, body, MIME.get(os.path.splitext(f)[1].lower()) or mimetypes.guess_type(f)[0] or "application/octet-stream")

    def do_GET(self):
        global F
        u = urllib.parse.urlparse(self.path)
        p, q = u.path, dict(urllib.parse.parse_qsl(u.query))
        if p.startswith("/__scenario/"):
            S["scenario"] = p.split("/")[2]
            return self._send(200, {"ok": True, "scenario": S["scenario"]})
        if p.startswith("/__gate/"):
            with COND:
                S["gate"], S["released"] = p.endswith("/on"), 0
                COND.notify_all()
            return self._send(200, {"ok": True})
        if p == "/__release":
            with COND:
                S["released"] += int(q.get("n", 1))
                COND.notify_all()
            return self._send(200, {"ok": True, "released": S["released"]})
        if p == "/__reset":   # nouveau rendu : messages ajoutés effacés, fixtures relues (modifiables sans relancer)
            S["extra"].clear()
            S["gate"], S["released"] = False, 0
            F = importlib.reload(F)
            return self._send(200, {"ok": True})
        if p == "/api/state":
            st = F.state(S["scenario"])
            return self._send(200, st)
        if p == "/api/candles":
            coin = q.get("coin", "random")
            if coin == "random":
                return self._send(200, F.random_candles())
            st, en = (int(q[k]) if q.get(k, "").isdigit() else None for k in ("start", "end"))
            return self._send(200, F.candles(coin, q.get("interval", "5m"), start=st, end=en))
        simple = {"/api/market": F.market, "/api/actus": F.actus, "/api/costs": F.costs, "/api/curves": F.curves,
                  "/api/achievements": F.achievements, "/api/push/key": lambda: {"key": None}}
        if p in simple:
            return self._send(200, simple[p]())
        if p == "/api/chat/history":
            msgs = F.chat_history() + S["extra"]
            after = q.get("after")
            if after is not None and after.isdigit():
                msgs = [m for m in msgs if m["id"] > int(after)]
            return self._send(200, {"messages": msgs[-40:], "via": "code"})
        if p == "/api/inbox":
            items = F.inbox_items()
            since = int(q.get("since", 0) or 0)
            return self._send(200, {"items": [i for i in items if i["id"] > since], "unread": 0, "last": len(items)})
        if p == "/sw.js":
            return self._send(404, b"", "text/plain")
        if p.startswith("/media/"):
            return self._file(HERE, p[len("/media/"):])
        return self._file(S["app"], "index.html" if p in ("/", "/index.html") else p.lstrip("/"))

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        if p == "/api/inbox/read":
            return self._send(200, {"ok": True, "unread": 0})
        if p == "/api/cmd":
            return self._send(200, {"ok": True, "command": body.get("command"), "level": "read",
                                    "text": "Conversation : 12 messages · modèle de démonstration · 0,04 $ aujourd'hui."})
        if p == "/api/chat":
            return self._chat(str(body.get("message") or ""))
        return self._send(404, b"", "text/plain")

    def _chat(self, message):
        reply = F.chat_reply(message)
        base = max([m["id"] for m in F.chat_history() + S["extra"]] + [0])
        now = F.VNOW.timestamp()
        S["extra"].append({"id": base + 1, "role": "user", "text": message, "ts": int(now)})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def emit(obj):
            self.wfile.write(f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
        try:
            for k, part in enumerate(chunks(reply)):
                if S["gate"]:
                    with COND:
                        COND.wait_for(lambda: S["released"] > k or not S["gate"], timeout=120)
                else:
                    time.sleep(0.08 if k else 0.6)
                emit({"delta": part})
            S["extra"].append({"id": base + 2, "role": "assistant", "text": reply, "ts": int(now)})
            emit({"done": True, "ids": [base + 1, base + 2]})
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True, help="dossier dash/ de l'export public")
    ap.add_argument("--port", type=int, default=8897)
    a = ap.parse_args()
    S["app"] = os.path.abspath(a.app)
    if not os.path.isfile(os.path.join(S["app"], "index.html")):
        sys.exit(f"index.html introuvable dans {S['app']}")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    srv.daemon_threads = True
    print(f"médias : http://127.0.0.1:{a.port}/ (app {S['app']})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
