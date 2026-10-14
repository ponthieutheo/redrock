"""Test hors ligne du chat : faux Hermes (SSE) + vrai serveur dash. Lancer : python dash/test_chat.py"""
import json, os, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

seen = {}


class FakeHermes(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.update(auth=self.headers.get("Authorization"), sid=self.headers.get("X-Hermes-Session-Id"), body=req)
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        w = self.wfile.write
        w(b": keepalive\n\n")
        w(b'event: hermes.tool.progress\ndata: {"tool":"x","delta":"NE PAS AFFICHER"}\n\n')
        for t in ("Salut ", "Alex", " !"):
            w(("data: " + json.dumps({"choices": [{"delta": {"content": t}}]}) + "\n\n").encode()); self.wfile.flush(); time.sleep(0.15)
        w(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


hp = ThreadingHTTPServer(("127.0.0.1", 0), FakeHermes)
threading.Thread(target=hp.serve_forever, daemon=True).start()
os.environ.update(HL_SUBACCOUNT="0x0", CHAT_KEY="secret", HERMES_API_KEY="hk", HERMES_URL=f"http://127.0.0.1:{hp.server_port}")
sys.path.insert(0, os.path.dirname(__file__))
import dash

dash.DATA = tempfile.mkdtemp()
dp = ThreadingHTTPServer(("127.0.0.1", 0), dash.H)
threading.Thread(target=dp.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{dp.server_port}"
K = {"X-Chat-Key": "secret"}


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True
ok.bad = False


def run(msg="coucou"):
    r = requests.post(U + "/api/chat", json={"message": msg}, headers=K, stream=True); r.encoding = "utf-8"
    return r, [json.loads(l[6:]) for l in r.iter_lines(decode_unicode=True) if l.startswith("data: ")]


ok("401 sans clé", requests.post(U + "/api/chat", json={"message": "x"}).status_code == 401)
ok("401 mauvaise clé", requests.post(U + "/api/chat", json={"message": "x"}, headers={"X-Chat-Key": "nope"}).status_code == 401)
ok("401 historique", requests.get(U + "/api/chat/history").status_code == 401)
ok("400 message vide", requests.post(U + "/api/chat", json={"message": " "}, headers=K).status_code == 400)
ok("400 trop long", requests.post(U + "/api/chat", json={"message": "a" * 2001}, headers=K).status_code == 400)

r, ev = run()
text = "".join(e.get("delta", "") for e in ev)
ok("stream SSE", r.headers["Content-Type"] == "text/event-stream" and text == "Salut Alex !" and ev[-1].get("done") is True and len(ev[-1].get("ids", [])) == 2)
ok("progress d'outil filtré", "NE PAS" not in text)
ok("auth/session/modèle vers Hermes", seen["auth"] == "Bearer hk" and seen["sid"] == "dashboard-chat" and seen["body"]["model"] == "fake-model" and seen["body"]["stream"] is True)
ok("préambule système", seen["body"]["messages"][0]["role"] == "system")
h = requests.get(U + "/api/chat/history", headers=K).json()["messages"]
ok("historique", [m["role"] for m in h] == ["user", "assistant"] and h[1]["text"] == "Salut Alex !" and isinstance(h[0]["ts"], int))

res = {}
t = threading.Thread(target=lambda: res.update(r=run("a")))
t.start(); time.sleep(0.2)
ok("429 si déjà une réponse en cours", requests.post(U + "/api/chat", json={"message": "b"}, headers=K).status_code == 429)
t.join()

dash._chat_times[:] = [time.time()] * 20
ok("429 au-delà de 20/min", requests.post(U + "/api/chat", json={"message": "c"}, headers=K).status_code == 429)
dash._chat_times.clear()

for i in range(45):
    dash.chat_append("user", str(i))
ok("historique borné à 40", len(requests.get(U + "/api/chat/history", headers=K).json()["messages"]) == 40)

hp.shutdown(); hp.server_close()
r, ev = run()
ok("erreur Hermes → event error sans fuite", ev and "error" in ev[-1] and "127.0.0.1" not in json.dumps(ev) and "hk" not in json.dumps(ev))

dash.CHAT_KEY = ""
ok("503 si CHAT_KEY vide", requests.post(U + "/api/chat", json={"message": "x"}, headers=K).status_code == 503)
sys.exit(1 if ok.bad else 0)
