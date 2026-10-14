"""Test hors ligne de /api/cmd (commandes Hermes du chat) : faux Hermes + vrai serveur dash. Lancer : python dash/test_cmd.py
Aucun appel au vrai agent : le faux Hermes enregistre tout ce qu'on lui envoie."""
import json, os, re, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

sys.stdout.reconfigure(encoding="utf-8")
calls = []                       # (méthode, chemin, corps) reçus par le faux Hermes
sessions = {"dashboard-chat": {"id": "dashboard-chat", "source": "api_server", "model": "fake/model-1", "message_count": 4, "tool_call_count": 1,
                               "input_tokens": 1000, "output_tokens": 200, "cache_read_tokens": 50, "reasoning_tokens": 7, "api_call_count": 3,
                               "estimated_cost_usd": 0.0123, "actual_cost_usd": None, "last_active": 1791800000}}
release = threading.Event()      # libère la réponse en cours du faux Hermes
at_approval = threading.Event()  # le faux Hermes a émis sa demande d'approbation
mode = {"approval": False, "stop_status": 200}


class FakeHermes(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        calls.append(("GET", self.path, None))
        p = self.path.partition("?")[0]
        if p == "/v1/models":
            return self._json(200, {"data": [{"id": "fake-agent"}]})
        if p == "/api/sessions":
            return self._json(200, {"object": "list", "data": list(sessions.values()) + [{"id": "cron_x_1", "source": "cron", "message_count": 9}, {"id": "20261007_tg", "source": "telegram", "message_count": 155, "last_active": 1791700000}]})
        m = re.fullmatch(r"/api/sessions/([^/]+)(/messages)?", p)
        if m:
            sid = m.group(1)
            if sid not in sessions:
                return self._json(404, {"error": {"message": "Session not found"}})
            if m.group(2):
                return self._json(200, {"data": [{"id": 3, "role": "assistant", "content": "Salut Alex", "timestamp": 3}, {"id": 2, "role": "tool", "content": "x", "timestamp": 2},
                                                  {"id": 1, "role": "user", "content": "Coucou", "timestamp": 1}]})
            return self._json(200, {"object": "hermes.session", "session": sessions[sid]})
        if p == "/api/model/options":
            return self._json(200, {"providers": [{"slug": "openrouter", "is_current": True, "models": ["a/one", "b/two"]}, {"slug": "moa", "is_current": False, "models": ["m"]}]})
        if p == "/health/detailed":
            return self._json(200, {"status": "ok", "gateway_state": "running", "readiness": {"checks": {"background_queues": {"active_api_runs": 1, "active_delegations": 0}}}})
        self._json(404, {"error": "?"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        calls.append(("POST", self.path, body))
        if self.path == "/v1/chat/completions":
            calls[-1] = ("POST", self.path, {**body, "_sid": self.headers.get("X-Hermes-Session-Id")})
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            w = self.wfile.write
            w(("data: " + json.dumps({"id": "chatcmpl-abc", "choices": [{"delta": {"content": "Début "}}]}) + "\n\n").encode()); self.wfile.flush()
            if mode["approval"]:
                w(b'event: approval.request\ndata: {"run_id":"chatcmpl-abc","request_id":"req1","command":"rm -rf x","description":"danger","choices":["once","deny"]}\n\n'); self.wfile.flush()
                w((": " + "x" * 700 + "\n\n").encode()); self.wfile.flush()  # le faux serveur n'est pas en « chunked » : de quoi remplir le tampon de lecture de requests
                at_approval.set()
                release.wait(8)
            w(("data: " + json.dumps({"choices": [{"delta": {"content": "fin"}}]}) + "\n\n").encode())
            w(b"data: [DONE]\n\n")
            return
        if re.fullmatch(r"/v1/runs/[^/]+/stop", self.path):
            return self._json(mode["stop_status"], {"status": "stopping"})  # ne libère pas le flux : c'est la fermeture côté dash qui doit l'arrêter
        if re.fullmatch(r"/v1/runs/[^/]+/steer", self.path):
            return self._json(200, {"ok": True})
        if re.fullmatch(r"/v1/runs/[^/]+/approval", self.path):
            release.set(); return self._json(200, {"ok": True})
        if re.fullmatch(r"/api/sessions/[^/]+/model", self.path):
            sid = self.path.split("/")[3]
            if sid not in sessions:
                return self._json(404, {"error": {"message": "Session not found"}})
            if body.get("model") == "refuse/me":
                return self._json(409, {"error": {"message": "model_lock_unavailable"}})
            return self._json(200, {"object": "hermes.session.model_lock"})
        if self.path == "/api/sessions":
            sessions[body["id"]] = {"id": body["id"], "source": "api_server", "model": body.get("model")}
            return self._json(201, {"session": sessions[body["id"]]})
        self._json(404, {"error": "?"})


hp = ThreadingHTTPServer(("127.0.0.1", 0), FakeHermes)
threading.Thread(target=hp.serve_forever, daemon=True).start()
os.environ.update(HL_SUBACCOUNT="0x0", CHAT_KEY="secret", HERMES_API_KEY="hk", HERMES_URL=f"http://127.0.0.1:{hp.server_port}")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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


def cmd(command, args="", confirmed=False, **extra):
    dash._chat_times.clear()  # la cadence est testée à part
    r = requests.post(U + "/api/cmd", json={"command": command, "args": args, "confirmed": confirmed, **extra}, headers=K)
    return r.status_code, r.json()


def mutating():
    return [c for c in calls if c[0] == "POST" and c[1] != "/v1/chat/completions"]


# ---- auth / validation --------------------------------------------------------------------------------------------
ok("401 sans clé", requests.post(U + "/api/cmd", json={"command": "status"}).status_code == 401)
ok("401 mauvaise clé", requests.post(U + "/api/cmd", json={"command": "status"}, headers={"X-Chat-Key": "nope"}).status_code == 401)
ok("400 corps pas un objet", requests.post(U + "/api/cmd", data="[1]", headers=K).status_code == 400)
ok("400 commande invalide", cmd("../etc")[0] == 400 and cmd("")[0] == 400)
ok("404 commande inconnue", cmd("blabla")[0] == 404)
n0 = len(calls)

# ---- exclues ---------------------------------------------------------------------------------------------------------
for c in ("yolo", "approvals", "restart", "reload", "config", "cron", "pause", "reload-mcp"):
    code, j = cmd(c, confirmed=True)
    ok(f"exclue refusée : /{c}", code == 403 and j["ok"] is False and j["level"] == "excluded" and "refusée" in j["text"])
ok("exclues : Hermes jamais appelé", len(calls) == n0)

# ---- lecture ---------------------------------------------------------------------------------------------------------
code, j = cmd("status"); ok("lecture /status", code == 200 and j["ok"] and j["level"] == "read" and "fake/model-1" in j["text"] and "dashboard-chat" in j["text"])
code, j = cmd("usage"); ok("lecture /usage", code == 200 and "1000 entrée" in j["text"] and "0.0123" in j["text"])
code, j = cmd("history", "5"); ok("lecture /history (user/assistant seulement, dans l'ordre)", code == 200 and j["text"] == "Toi : Coucou\nLui : Salut Alex")
code, j = cmd("sessions"); ok("lecture /sessions (pas de cron, chat marqué)", code == 200 and "cron" not in j["text"] and "← chat du dashboard" in j["text"] and "telegram" in j["text"])
code, j = cmd("agents"); ok("lecture /agents", code == 200 and "running" in j["text"] and "Exécutions API actives : 1" in j["text"])
code, j = cmd("model"); ok("lecture /model", code == 200 and j["level"] == "read" and "a/one, b/two" in j["text"] and "moa" not in j["text"])
code, j = cmd("model", "list"); ok("lecture /model list", code == 200 and j["level"] == "read")
code, j = cmd("help"); ok("lecture /help", code == 200 and "/new" in j["text"] and "/yolo" not in j["text"])
ok("lecture : aucune écriture vers Hermes", not mutating())

# ---- confirmation requise ----------------------------------------------------------------------------------------------
for c, a in (("new", ""), ("stop", ""), ("model", "a/one"), ("retry", ""), ("steer", "va plus vite"), ("approve", ""), ("deny", "")):
    code, j = cmd(c, a)
    ok(f"confirmation demandée : /{c}", code == 200 and j["ok"] and j.get("confirm") is True and j["level"] == "action")
ok("sans confirmation : rien d'envoyé à Hermes, session inchangée", not mutating() and dash.chat_session_id() == "dashboard-chat")

# ---- mauvaise session -------------------------------------------------------------------------------------------------
n1 = len(calls)
for c in ("status", "new", "stop", "model"):
    code, j = cmd(c, "a/one" if c == "model" else "", confirmed=True, session="cron_f5cc14d25a62_20261013_204436")
    ok(f"mauvaise session refusée : /{c}", code == 403 and j["ok"] is False)
code, j = cmd("status", session="dashboard-chat"); ok("bonne session acceptée", code == 200)
ok("mauvaise session : Hermes jamais appelé pour elle", all("cron_f5cc" not in c[1] for c in calls) and not mutating())

# ---- non pris en charge -------------------------------------------------------------------------------------------------
for c in ("compress", "undo"):
    code, j = cmd(c, confirmed=True); ok(f"/{c} : indisponible, dit clairement", code == 501 and j["ok"] is False and j["supported"] is False and "API de Hermes" in j["text"])

# ---- retry --------------------------------------------------------------------------------------------------------------
code, j = cmd("retry", confirmed=True); ok("/retry sans message : 409", code == 409)
dash.chat_append("user", "Quel est ton plan ?"); dash.chat_append("assistant", "Rien."); dash.chat_append("user", "/status")
code, j = cmd("retry", confirmed=True); ok("/retry renvoie le dernier vrai message (pas une /commande)", code == 200 and j["resend"] == "Quel est ton plan ?")

# ---- model --------------------------------------------------------------------------------------------------------------
code, j = cmd("model", "a/one", confirmed=True)
last = mutating()[-1]
ok("/model confirmé : verrou sur la session du chat", code == 200 and last[1] == "/api/sessions/dashboard-chat/model" and last[2] == {"model": "a/one", "require_model_lock": True})
ok("/model nom invalide : 400", cmd("model", "a b; rm", confirmed=True)[0] == 400)
code, j = cmd("model", "refuse/me", confirmed=True); ok("/model refusé par Hermes : 409 avec message", code == 409 and "model_lock_unavailable" in j["text"])

# ---- new (confirmé) ------------------------------------------------------------------------------------------------------
code, j = cmd("new", confirmed=True)
sid = dash.chat_session_id()
ok("/new confirmé : nouvelle session dashboard-chat-…", code == 200 and re.fullmatch(r"dashboard-chat-\d{8}_\d{6}", sid) is not None and sid in j["text"])
ok("/new : ancien historique archivé, nouveau vide", dash.chat_history() == [] and len(dash.jload("chat_history_dashboard-chat.json", [])) == 3)
code, j = cmd("model", "a/one", confirmed=True)
ok("/model sur session neuve : la crée verrouillée", code == 200 and mutating()[-1][1] == "/api/sessions" and mutating()[-1][2]["id"] == sid and mutating()[-1][2]["require_model_lock"] is True)
code, j = cmd("status", session="dashboard-chat"); ok("l'ancienne session n'est plus la bonne", code == 403)

# ---- tour en cours : approbation, consigne, arrêt ---------------------------------------------------------------------------
mode["approval"] = True
ev = []


def chat():
    r = requests.post(U + "/api/chat", json={"message": "fais un truc"}, headers=K, stream=True); r.encoding = "utf-8"
    for l in r.iter_lines(chunk_size=1, decode_unicode=True):
        if l.startswith("data: "):
            ev.append(json.loads(l[6:]))


t = threading.Thread(target=chat); t.start()
ok("tour en cours : le faux Hermes a émis l'approbation", at_approval.wait(5))
time.sleep(0.3)
ok("chat vers la session courante", [c for c in calls if c[1] == "/v1/chat/completions"][-1][2]["_sid"] == sid)
ok("approbation annoncée au client (SSE)", any(e.get("approval", {}).get("command") == "rm -rf x" and e["approval"]["request_id"] == "req1" for e in ev))
code, j = cmd("status"); ok("/status voit le tour et l'approbation", "Réponse en cours : oui" in j["text"] and "rm -rf x" in j["text"])
code, j = cmd("new", confirmed=True); ok("/new refusé pendant un tour", code == 409 and dash.chat_session_id() == sid)
ok("/approve toujours = une fois : « always » refusé", cmd("approve", "always", confirmed=True)[0] == 403)
n2 = len(mutating())
code, j = cmd("steer", "va plus vite", confirmed=True)
c = mutating()[-1]
ok("/steer confirmé → /v1/runs/<id>/steer", code == 200 and c[1] == "/v1/runs/chatcmpl-abc/steer" and c[2] == {"input": "va plus vite"})
release.clear()
code, j = cmd("approve", confirmed=True)
c = mutating()[-1]
ok("/approve confirmé → once + request_id", code == 200 and c[1] == "/v1/runs/chatcmpl-abc/approval" and c[2] == {"choice": "once", "request_id": "req1"})
t.join(5)
ok("le tour se termine après l'approbation", not t.is_alive() and "".join(e.get("delta", "") for e in ev) == "Début fin")
ok("/approve sans approbation en attente : 409", cmd("approve", confirmed=True)[0] == 409)
ok("/steer sans tour : 409", cmd("steer", "x", confirmed=True)[0] == 409)
ok("/stop sans tour : message clair", cmd("stop", confirmed=True)[1]["text"] == "Aucune réponse en cours.")

# arrêt d'un tour bloqué
release.clear(); at_approval.clear(); ev.clear()
t = threading.Thread(target=chat); t.start(); at_approval.wait(5); time.sleep(0.3)
code, j = cmd("stop", confirmed=True)
c = mutating()[-1]
t.join(4)
ok("/stop confirmé → /v1/runs/<id>/stop et le flux se ferme (sans que Hermes le libère)", code == 200 and c[1] == "/v1/runs/chatcmpl-abc/stop" and not t.is_alive())
ok("après /stop, pas de message d'erreur affiché", not any("error" in e for e in ev))
mode["approval"] = False

# ---- /deny ------------------------------------------------------------------------------------------------------------------
release.clear(); at_approval.clear(); mode["approval"] = True; ev.clear()
t = threading.Thread(target=chat); t.start(); at_approval.wait(5); time.sleep(0.3)
code, j = cmd("deny", confirmed=True); c = mutating()[-1]
ok("/deny confirmé → deny", code == 200 and c[2] == {"choice": "deny", "request_id": "req1"})
t.join(5); mode["approval"] = False

# ---- erreurs sans fuite, cadence, désactivation ---------------------------------------------------------------------------
dash._chat_times[:] = [time.time()] * 20
ok("429 au-delà de 20/min (même cadence que le chat)", requests.post(U + "/api/cmd", json={"command": "help"}, headers=K).status_code == 429)
dash._chat_times.clear()
hp.shutdown(); hp.server_close()
code, j = cmd("status")
ok("Hermes éteint : message clair sans fuite", code == 502 and j["ok"] is False and "127.0.0.1" not in json.dumps(j) and "hk" not in json.dumps(j).replace("check", ""))
dash.CHAT_KEY = ""
ok("503 si CHAT_KEY vide", requests.post(U + "/api/cmd", json={"command": "help"}, headers=K).status_code == 503)
sys.exit(1 if ok.bad else 0)
