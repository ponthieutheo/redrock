"""Test hors ligne de l'inbox (sorties de crons + alertes de l'hôte, remplaçant de Telegram) : faux Hermes + vrai serveur dash.
Lancer : python -X utf8 dash/test_inbox.py. Aucun appel au vrai agent ; le faux Hermes ne reçoit que des GET (vérifié) et le push est simulé."""
import json, os, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

sys.stdout.reconfigure(encoding="utf-8")
calls = []                      # (méthode, chemin) reçus par le faux Hermes
NOW = time.time()
rows = {}                       # id -> ligne de /api/sessions
texts = {}                      # id -> texte final de l'assistant (None = aucun message)
down = {"on": False}


def sess(sid, title, ended_ago, text, end_reason="cron_complete"):
    rows[sid] = {"id": sid, "source": "cron", "title": title, "started_at": NOW - (ended_ago or 0) - 60,
                 "ended_at": None if ended_ago is None else NOW - ended_ago, "end_reason": end_reason}
    texts[sid] = text


class FakeHermes(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        calls.append(("POST", self.path)); self._json(200, {})

    def do_GET(self):
        calls.append(("GET", self.path))
        if down["on"]:
            return self._json(500, {})
        p = self.path.partition("?")[0]
        if p == "/api/sessions":
            return self._json(200, {"object": "list", "data": list(rows.values()) + [{"id": "20261007_tg", "source": "telegram", "ended_at": NOW - 5}]})
        if p.startswith("/api/sessions/") and p.endswith("/messages"):
            sid = p.split("/")[3]
            t = texts.get(sid)
            msgs = [{"role": "user", "content": "go"}, {"role": "assistant", "content": "réflexion"}]
            if t is not None:
                msgs.append({"role": "assistant", "content": t})
            return self._json(200, {"data": msgs})
        self._json(404, {})


hp = ThreadingHTTPServer(("127.0.0.1", 0), FakeHermes)
threading.Thread(target=hp.serve_forever, daemon=True).start()
os.environ.update(HL_SUBACCOUNT="0x0", CHAT_KEY="secret", HERMES_API_KEY="hk", HERMES_URL=f"http://127.0.0.1:{hp.server_port}")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash

dash.DATA = tempfile.mkdtemp()
pushes = []
dash.push = lambda title, body, tag=None, url="/", only=None: pushes.append((title, body, tag, url)) or 1
dp = ThreadingHTTPServer(("127.0.0.1", 0), dash.H)
threading.Thread(target=dp.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{dp.server_port}"
K = {"X-Chat-Key": "secret"}


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True
ok.bad = False


def get(path="/api/inbox", **kw):
    dash._inbox_times.clear()
    r = requests.get(U + path, headers=K, **kw)
    return r.status_code, r.json()


def post(path, body, headers=K):
    dash._inbox_times.clear()
    r = requests.post(U + path, json=body, headers=headers)
    return r.status_code, r.json()


def msg_gets():
    return [c for c in calls if c[1].endswith("/messages")]


SID = lambda job, n: f"cron_{job}_20261013_{n:06d}"
LONG = "**Post-mortem — kPEPE SHORT #42** · fermé le 13/10\n\n**Le trade**\n- kPEPE SHORT, `levier ×3`\n- PnL net **+0,12 $**\n\n---\n## Leçon\nRien à changer."

# ---- premier passage : l'historique récent est repris en « lu » sans push, l'ancien est seulement marqué vu ---------------------------
sess(SID("aaaaaa", 1), "post-mortem trades · Oct 13 05:39", 20 * 3600, LONG)               # trop ancien : pas rejoué
sess(SID("bbbbbb", 2), "compte-rendu quotidien minuit · Oct 13 00:01", 3600, "**Compte-rendu — minuit**\n- Equity : 90 $")
sess(SID("cccccc", 3), "cycle-trading · Oct 13 21:50", 1800, "[SILENT]")
dash.inbox_scan()
db = dash.inbox_db()
ok("1er passage : 1 seul élément repris (récent, pas SILENT)", len(db["items"]) == 1 and db["items"][0]["source"] == "cron:compte-rendu quotidien minuit")
ok("1er passage : repris en lu, aucun push", db["items"][0]["read"] is True and not pushes and dash.inbox_unread() == 0)
ok("1er passage : l'ancien n'a pas été lu côté Hermes (pas de GET messages)", all(SID("aaaaaa", 1) not in c[1] for c in msg_gets()))
ok("1er passage : état « primed » posé, tout est mémorisé", db.get("primed") is True and len(db["keys"]) == 3)
n_gets = len(msg_gets())
dash.inbox_scan()
ok("2e passage identique : rien de nouveau, aucun GET messages en plus", len(dash.inbox_db()["items"]) == 1 and len(msg_gets()) == n_gets)

# ---- nouvelles sorties --------------------------------------------------------------------------------------------------------------
sess(SID("dddddd", 4), "post-mortem trades · Oct 13 22:10", 120, LONG)                     # push
sess(SID("eeeeee", 5), "sentinel-alerte · Oct 13 22:12", 90, "Cycle sentinelle terminé — rien à faire.\n\n## Le signal\nBaleine BTC.")   # dans le chat, sans push
sess(SID("ffffff", 6), "cycle-trading · Oct 13 22:15", 60, "[SILENT]")                      # ignoré
sess(SID("a1a1a1", 7), "docteur · Oct 13 22:16", 50, "[CRON_FAILURE]\nle docteur a planté : boom")   # alerte push
sess(SID("b2b2b2", 8), "cycle-trading · Oct 13 22:17", 40, None, end_reason="cron_error")   # fin anormale sans texte : alerte push
sess(SID("c3c3c3", 9), "revue-quotidienne · Oct 13 22:18", None, "pas fini")                # encore en cours : on attend
rows["cron_../../etc_20261013_000001"] = {"id": "cron_../../etc_20261013_000001", "source": "cron", "title": "x", "ended_at": NOW - 5, "end_reason": "cron_complete"}
texts["cron_../../etc_20261013_000001"] = "piège"
dash.inbox_scan()
items = dash.inbox_db()["items"]
by = {i["source"] + "|" + i["title"][:20]: i for i in items}
ok("nouvelles sorties : 4 éléments de plus (post-mortem, sentinelle, échec, fin anormale)", len(items) == 5)
pm = next(i for i in items if i["source"] == "cron:post-mortem trades")
ok("post-mortem : titre = 1re ligne sans markdown", pm["title"] == "Post-mortem — kPEPE SHORT #42 · fermé le 13/10")
ok("post-mortem : résumé sans gras/code/séparateurs", "**" not in pm["summary"] and "`" not in pm["summary"] and "---" not in pm["summary"] and "PnL net +0,12 $" in pm["summary"])
ok("post-mortem : texte complet gardé (markdown intact)", pm["text"] == LONG and pm["read"] is False and pm["level"] == "push")
ok("post-mortem : horodaté à la fin du cron", abs(pm["ts"] - (NOW - 120)) < 1)
se = next(i for i in items if i["source"] == "cron:sentinel-alerte")
ok("sentinelle : niveau quiet, non lu", se["level"] == "quiet" and se["read"] is False)
ok("SILENT ignoré", not any(i["source"] == "cron:cycle-trading" and i["level"] != "alert" for i in items))
fail = next(i for i in items if i["source"] == "cron:docteur")
ok("[CRON_FAILURE] : alerte « a échoué » avec le détail", fail["level"] == "alert" and fail["title"] == "docteur a échoué" and "boom" in fail["summary"] and "[CRON_FAILURE]" not in fail["summary"])
ab = next(i for i in items if i["source"] == "cron:cycle-trading")
ok("fin anormale sans texte : alerte avec la raison", ab["level"] == "alert" and "cron_error" in ab["summary"])
ok("cron encore en cours : pas encore repris", not any(i["source"] == "cron:revue-quotidienne" for i in items))
ok("id de session douteux : jamais utilisé dans une URL", all(".." not in c[1] for c in calls))
ok("sessions Telegram/non-cron ignorées", not any("20261007_tg" in c[1] for c in calls))
tags = [p[2] for p in pushes]
ok("push : post-mortem + échec + fin anormale, pas la sentinelle", len(pushes) == 3 and f"inbox-{pm['id']}" in tags and f"inbox-{se['id']}" not in tags)
ok("push : titre/corps/lien", any(p[0] == "Post-mortem trades" and "kPEPE" in p[1] and p[3] == "/?chat=1" for p in pushes) and any(p[0].startswith("⚠️") and "boom" in p[1] for p in pushes))
ok("non lus = 3 (post-mortem + échec + fin anormale ; la sentinelle « quiet » ne compte pas)", dash.inbox_unread() == 3)
ok("tout le test : Hermes n'a reçu que des GET", all(c[0] == "GET" for c in calls))

# le cron en cours se termine : repris au passage suivant
rows[SID("c3c3c3", 9)]["ended_at"] = NOW - 5
texts[SID("c3c3c3", 9)] = "**Revue quotidienne du 13/10**\nTout va bien."
dash.inbox_scan()
ok("cron terminé ensuite : repris, dans le chat sans push (revue = push)", any(i["source"] == "cron:revue-quotidienne" for i in dash.inbox_db()["items"]) and len(pushes) == 4)

# ---- Hermes injoignable / illisible : jamais d'exception, une seule trace --------------------------------------------------------------
down["on"] = True
try:
    dash.inbox_watch(); dash.inbox_watch(); fine = True
except Exception:
    fine = False
ok("Hermes en panne : inbox_watch n'échoue pas", fine and dash._inbox_state["err"] == "HTTPError")
down["on"] = False
dash.inbox_watch()
ok("Hermes revenu : l'erreur est effacée", dash._inbox_state["err"] is None)

# ---- endpoints ---------------------------------------------------------------------------------------------------------------------
ok("GET sans clé = 401", requests.get(U + "/api/inbox").status_code == 401)
ok("GET mauvaise clé = 401", requests.get(U + "/api/inbox", headers={"X-Chat-Key": "x"}).status_code == 401)
ok("POST read sans clé = 401", requests.post(U + "/api/inbox/read", json={"all": True}).status_code == 401)
ok("POST notify sans clé = 401", requests.post(U + "/api/inbox/notify", json={"title": "x"}).status_code == 401)
code, j = get()
ids = [i["id"] for i in j["items"]]
# non lus = seulement ce qui mérite l'attention (push / alert) ; les « quiet » restent dans le chat sans compter
nl = lambda: sum(1 for i in dash.inbox_db()["items"] if not i.get("read") and i.get("level") in ("push", "alert"))
n0 = nl()
ok("GET : items triés par id, compteur et dernier id", code == 200 and ids == sorted(ids) and j["unread"] == n0 > 0 and j["last"] == max(ids))
code, j2 = get(params={"since": ids[2]})
ok("GET since : seulement les plus récents", [i["id"] for i in j2["items"]] == ids[3:])
code, j3 = get(params={"limit": 2})
ok("GET limit sans since : les 2 derniers", [i["id"] for i in j3["items"]] == ids[-2:])
code, j4 = get(params={"since": "abc", "limit": "zzz"})
ok("GET paramètres bidons : défauts, pas d'erreur", code == 200 and len(j4["items"]) == len(ids))
code, j = post("/api/inbox/read", {"upto": ids[1]})
ok("read upto : marque lus jusqu'à cet id", code == 200 and j["unread"] == nl() and all(i["read"] for i in dash.inbox_db()["items"] if i["id"] <= ids[1]))
code, j = post("/api/inbox/read", {"ids": [ids[-1]]})
ok("read ids : marque cet id", code == 200 and j["unread"] == nl() and next(i for i in dash.inbox_db()["items"] if i["id"] == ids[-1])["read"])
n1 = nl()
code, j = post("/api/inbox/read", {"ids": ["x", True, 2.5, None]})
ok("read ids bidons : ignorés", code == 200 and j["unread"] == n1)
code, j = post("/api/inbox/read", {"all": True})
ok("read all", code == 200 and j["unread"] == 0 and get()[1]["unread"] == 0)

n_push = len(pushes)
code, j = post("/api/inbox/notify", {"title": "⚠️ HC-1 — problème détecté", "text": "• broker lent\n• disque 91 %", "key": "mon-1"})
ok("notify : alerte ajoutée et poussée", code == 200 and j["ok"] and j["id"] and not j["deduped"] and len(pushes) == n_push + 1 and pushes[-1][3] == "/?chat=1")
al = dash.inbox_db()["items"][-1]
ok("notify : source « alerte », niveau alert, non lue, texte complet", al["source"] == "alerte" and al["level"] == "alert" and al["read"] is False and "disque 91 %" in al["text"])
code, j = post("/api/inbox/notify", {"title": "⚠️ HC-1 — problème détecté", "text": "autre", "key": "mon-1"})
ok("notify : même clé = dédoublonné, pas de nouveau push", code == 200 and j["deduped"] is True and j["id"] is None and len(pushes) == n_push + 1)
code, j = post("/api/inbox/notify", {"text": "Texte seul : première ligne devient le titre\nsuite", "level": "info"})
ok("notify info : dans le chat sans push, titre déduit", code == 200 and len(pushes) == n_push + 1 and dash.inbox_db()["items"][-1]["title"].startswith("Texte seul") and dash.inbox_db()["items"][-1]["level"] == "quiet")
code, j = post("/api/inbox/notify", {"title": "silencieux", "push": False})
ok("notify push:false : pas de notification", code == 200 and len(pushes) == n_push + 1)
a, b = post("/api/inbox/notify", {"title": "doublon auto", "text": "même"}), post("/api/inbox/notify", {"title": "doublon auto", "text": "même"})
ok("notify sans clé : doublon identique dans les 10 min écarté", a[1]["deduped"] is False and b[1]["deduped"] is True)
ok("notify : 400 sans titre ni texte", post("/api/inbox/notify", {})[0] == 400)
ok("notify : 400 source invalide", post("/api/inbox/notify", {"title": "x", "source": "../x"})[0] == 400)
ok("notify : source personnalisée valide", post("/api/inbox/notify", {"title": "y", "source": "monitor:disque"})[0] == 200 and dash.inbox_db()["items"][-1]["source"] == "monitor:disque")
ok("notify : 400 corps pas un objet", requests.post(U + "/api/inbox/notify", data="[1]", headers=K).status_code == 400)
ok("notify : 400 corps trop gros", requests.post(U + "/api/inbox/notify", data=b"x" * 20000, headers=K).status_code == 400)
dash._inbox_times.clear(); ok("POST inbox inconnu = 404", requests.post(U + "/api/inbox/zzz", json={}, headers=K).status_code == 404)
big = post("/api/inbox/notify", {"title": "gros", "text": "z" * 9000})
ok("texte tronqué à 4000", big[0] == 200 and len(dash.inbox_db()["items"][-1]["text"]) == 4000)
dash._inbox_times.clear()
codes = [requests.post(U + "/api/inbox/notify", json={"title": f"rafale {i}"}, headers=K).status_code for i in range(35)]
ok("notify : rafale limitée à 30/min (429)", 429 in codes and codes[:30].count(200) == 30)

# ---- bornes et persistance ----------------------------------------------------------------------------------------------------------------
for i in range(dash.INBOX_MAX + 20):
    dash.inbox_add("alerte", f"t{i}", "", "x", "quiet", f"k{i}", notify=False)
db = dash.inbox_db()
ok("inbox bornée à INBOX_MAX éléments, ids toujours croissants", len(db["items"]) == dash.INBOX_MAX and [i["id"] for i in db["items"]] == sorted(i["id"] for i in db["items"]))
ok("fichier persistant relu à l'identique", json.load(open(os.path.join(dash.DATA, "inbox.json")))["next"] == db["next"])
ok("aucune écriture vers Hermes sur tout le test", all(c[0] == "GET" for c in calls))
sys.exit(1 if ok.bad else 0)
