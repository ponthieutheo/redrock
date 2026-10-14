"""Test hors ligne : connexion par Tailscale (sans code) et synchronisation du chat entre appareils.
Lancer : python -X utf8 dash/test_sync.py"""
import json, os, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


class FakeHermes(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for t in ("Bien ", "reçu"):
            self.wfile.write(("data: " + json.dumps({"id": "chatcmpl-ab12", "choices": [{"delta": {"content": t}}]}) + "\n\n").encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")


hp = ThreadingHTTPServer(("127.0.0.1", 0), FakeHermes)
threading.Thread(target=hp.serve_forever, daemon=True).start()
os.environ.update(HL_SUBACCOUNT="0x0", CHAT_KEY="secret", HERMES_API_KEY="hk", HERMES_URL=f"http://127.0.0.1:{hp.server_port}",
                  TS_LOGINS="alex@example.com, Autre@Example.com")
sys.path.insert(0, os.path.dirname(__file__))
import dash

dash.DATA = tempfile.mkdtemp()
dp = ThreadingHTTPServer(("127.0.0.1", 0), dash.H)
threading.Thread(target=dp.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{dp.server_port}"
K = {"X-Chat-Key": "secret"}
TS = {"Tailscale-User-Login": "alex@example.com"}


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True


ok.bad = False

# --- identité Tailscale : crue seulement par le socket de tailscale serve (HS), jamais par le port TCP (H)
ok("socket + compte autorisé : reconnu", dash.ts_login(TS, True) == "alex@example.com")
ok("casse du compte ignorée", dash.ts_login({"Tailscale-User-Login": "AUTRE@example.com"}, True) == "autre@example.com")
ok("port TCP (agent, RustDesk, tunnel…) : en-tête ignoré", dash.ts_login(TS, False) is None)
ok("compte non autorisé : refusé", dash.ts_login({"Tailscale-User-Login": "pirate@example.com"}, True) is None)
ok("sans en-tête : refusé", dash.ts_login({}, True) is None)
ok("chat_auth : socket + Tailscale = autorisé sans code", dash.chat_auth(TS, True) is None)
ok("chat_auth : port TCP + Tailscale forgé = 401", dash.chat_auth(TS, False) == (401, "clé invalide"))
ok("chat_auth : bon code toujours accepté", dash.chat_auth(K, False) is None)
saved = dash.TS_LOGINS
dash.TS_LOGINS = set()
ok("TS_LOGINS vide : fonction coupée", dash.ts_login(TS, True) is None)
dash.TS_LOGINS = saved
ok("H (port TCP) n'est pas de confiance, HS (socket) l'est", dash.H.via_sock is False and dash.HS.via_sock is True)
# par HTTP sur le port TCP : un en-tête Tailscale ne suffit JAMAIS
r = requests.get(U + "/api/chat/history", headers=TS)
ok("HTTP port TCP : en-tête Tailscale seul = 401", r.status_code == 401)
ok("HTTP : avec code, via = code", requests.get(U + "/api/chat/history", headers=K).json().get("via") == "code")
# même serveur mais avec le gestionnaire du socket (HS) : Tailscale accepté
sp = ThreadingHTTPServer(("127.0.0.1", 0), dash.HS)
threading.Thread(target=sp.serve_forever, daemon=True).start()
r = requests.get(f"http://127.0.0.1:{sp.server_port}/api/chat/history", headers=TS)
ok("gestionnaire du socket : historique sans code via Tailscale", r.status_code == 200 and r.json().get("via") == "tailscale")
r = requests.get(f"http://127.0.0.1:{sp.server_port}/api/chat/history", headers={"Tailscale-User-Login": "pirate@example.com"})
ok("gestionnaire du socket : compte inconnu = 401", r.status_code == 401)

# --- synchronisation : numéros de message, ?after=, numéros renvoyés à la fin du flux
r = requests.post(U + "/api/chat", json={"message": "coucou"}, headers=K, stream=True)
events = [json.loads(l[5:]) for l in r.iter_lines(decode_unicode=True) if l and l.startswith("data:")]
done = next((e for e in events if e.get("done")), {})
ok("fin du flux : numéros [utilisateur, réponse]", done.get("ids") == [1, 2])
h = requests.get(U + "/api/chat/history", headers=K).json()["messages"]
ok("historique numéroté, réponse enregistrée une seule fois", [m["id"] for m in h] == [1, 2] and h[1]["text"] == "Bien reçu")
ok("after=1 : seulement la réponse", [m["id"] for m in requests.get(U + "/api/chat/history?after=1", headers=K).json()["messages"]] == [2])
ok("after=2 : rien de neuf", requests.get(U + "/api/chat/history?after=2", headers=K).json()["messages"] == [])
ok("after bidon : tout l'historique", len(requests.get(U + "/api/chat/history?after=x", headers=K).json()["messages"]) == 2)
# ancien historique sans numéros : numérotés à la volée sans collision avec les nouveaux
dash.jsave("chat_history.json", [{"role": "user", "text": "vieux", "ts": 1}, {"role": "assistant", "text": "vieux2", "ts": 2}])
nid = dash.chat_append("user", "neuf")
hh = dash.chat_history()
ok("ancien historique : numéros croissants, nouveau message après", [m["id"] for m in hh] == sorted(m["id"] for m in hh) and hh[-1]["id"] == nid == 1)
ok("sans after : les anciens inclus", len(dash.chat_history()) == 3)
ok("after=0 : seulement les messages numérotés (pas de doublon des anciens)", [m["text"] for m in dash.chat_history(0)] == ["neuf"])

print("\nÉCHEC" if ok.bad else "\nTout est OK")
sys.exit(1 if ok.bad else 0)
