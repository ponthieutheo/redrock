"""Tests hors ligne des tâches de veille : client MCP (agent/scripts/broker_call.py) et scripts de veille (sentinelle,
post-mortem, docteur) face à un FAUX broker MCP (streamable HTTP, réponses JSON ou SSE). Aucun réseau extérieur.

    python -X utf8 tests/veille/test_veille.py      (depuis la racine du dépôt public)
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "agent", "scripts"))
sys.dont_write_bytecode = True   # pas de __pycache__ à côté des scripts
sys.path.insert(0, SCRIPTS)
import broker_call  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
T0 = 1_800_000_000.0     # instant fixe des tests (2027-01-15 08:00 UTC)


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(t))


def pub(t):
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(t))


# ------------------------------------------------------------------ faux broker MCP
FAKE = {}
CALLS = []                      # (outil, arguments)
SESSIONS = set()
MODE = {"sse": False, "down": False, "notify_first": False}


def reset(now=T0):
    FAKE.clear()
    FAKE.update(account={"equity": 100.0, "positions": [], "alive": True, "generation": 1, "mode": "paper",
                         "circuit_breaker": {"frozen": False}, "recent_actions": []},
                history={"trades": [], "equity_recent": [{"ts": iso(now - 120), "equity": 100.0}], "journal_recent": []},
                events={"untrusted_external_content": True, "count": 0, "events": []},
                news={"untrusted_external_content": True, "items": []})
    CALLS.clear()


class Broker(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj=None, headers=None):
        body = b""
        if obj is not None:
            if MODE["sse"]:
                events = []
                if MODE["notify_first"]:
                    events.append({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "x"}})
                events.append(obj)
                # une ligne « data: » par ligne du JSON indenté : le client doit les recoller
                body = "".join("event: message\n" + "".join(f"data: {ln}\n" for ln in json.dumps(e, indent=1).splitlines()) + "\n"
                               for e in events).encode()
            else:
                body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/event-stream" if MODE["sse"] and obj is not None else "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_DELETE(self):
        SESSIONS.discard(self.headers.get("Mcp-Session-Id"))
        self._send(200)

    def do_POST(self):
        if MODE["down"]:
            return self._send(503, {"error": "down"})
        if "text/event-stream" not in (self.headers.get("Accept") or ""):
            return self._send(406, {"error": "accept"})
        msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        method, rid = msg.get("method"), msg.get("id")
        if method == "initialize":
            sid = uuid.uuid4().hex
            SESSIONS.add(sid)
            return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2025-03-26", "capabilities": {},
                                                                                "serverInfo": {"name": "faux", "version": "0"}}},
                              {"mcp-session-id": sid})
        if self.headers.get("Mcp-Session-Id") not in SESSIONS:
            return self._send(400, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32600, "message": "session inconnue"}})
        if method == "notifications/initialized":
            return self._send(202)
        if method == "tools/call":
            name, args = msg["params"]["name"], msg["params"].get("arguments") or {}
            CALLS.append((name, args))
            if name not in FAKE:
                return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": f"outil inconnu {name}"}], "isError": True}})
            text = FAKE[name] if isinstance(FAKE[name], str) else json.dumps(FAKE[name])
            return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}], "isError": False}})
        self._send(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "méthode inconnue"}})


srv = ThreadingHTTPServer(("127.0.0.1", 0), Broker)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/mcp"
DEAD_URL = "http://127.0.0.1:1/mcp"
os.environ["REDROCK_BROKER_URL"] = URL


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad += 1
    ok.n += 1


ok.bad = ok.n = 0


# ------------------------------------------------------------------ 1. client MCP
reset()
FAKE["account"] = {"equity": 101.5, "positions": [], "note": "é"}
ok("JSON : account rendu tel quel", json.loads(broker_call.call("account"))["equity"] == 101.5)
ok("JSON : session fermée (DELETE) après l'appel", not SESSIONS)
MODE.update(sse=True, notify_first=True)
with broker_call.Session() as s:
    a = s.call_json("account")
    h = s.call_json("history", {"limit": 3})
ok("SSE : notification ignorée, data sur plusieurs lignes recollées", a["note"] == "é" and h["equity_recent"][0]["equity"] == 100.0)
ok("SSE : une seule session pour deux appels, arguments transmis", [c[0] for c in CALLS[-2:]] == ["account", "history"] and CALLS[-1][1] == {"limit": 3})
ok("SSE : session fermée en sortie du with", not SESSIONS)
MODE.update(sse=False, notify_first=False)
try:
    broker_call.call("inconnu")
    raised = None
except broker_call.BrokerError as e:
    raised = str(e)
ok("outil en erreur (isError) : BrokerError avec le texte", raised and "outil inconnu" in raised)
t = time.time()
try:
    broker_call.call("account", url=DEAD_URL, timeout=3)
    raised = None
except broker_call.BrokerError as e:
    raised = str(e)
ok("broker injoignable : BrokerError rapide", raised and "injoignable" in raised and time.time() - t < 5)
MODE["down"] = True
try:
    broker_call.call("account")
    raised = None
except broker_call.BrokerError as e:
    raised = str(e)
MODE["down"] = False
ok("broker en erreur HTTP : BrokerError", raised and "503" in raised)

d = tempfile.mkdtemp()
cfg = os.path.join(d, "config.yaml")
with open(cfg, "w", encoding="utf-8") as fh:
    fh.write('model:\n  default: "x"\n  base_url: "https://openrouter.ai/api/v1"\nmcp_servers:\n  autre:\n    url: "http://autre:9000/mcp"\n'
             '  redrock-broker:\n    url: "http://broker:8765/mcp"  # le broker\nmemory:\n  memory_enabled: true\n')
env_url = os.environ.pop("REDROCK_BROKER_URL")
ok("config.yaml : l'url du serveur dont le nom contient « broker »", broker_call.broker_url(cfg) == "http://broker:8765/mcp")
with open(cfg, "w", encoding="utf-8") as fh:
    fh.write('mcp_servers:\n  outils:\n    url: http://outils:1234/mcp\n')
ok("config.yaml : sinon le premier serveur MCP", broker_call.broker_url(cfg) == "http://outils:1234/mcp")
ok("config.yaml absent : adresse par défaut", broker_call.broker_url(os.path.join(d, "absent.yaml")) == "http://broker:8765/mcp")
os.environ["REDROCK_BROKER_URL"] = env_url
ok("REDROCK_BROKER_URL prioritaire", broker_call.broker_url(cfg) == URL)

cli = [sys.executable, "-X", "utf8", os.path.join(SCRIPTS, "broker_call.py")]
r = subprocess.run(cli + ["history", '{"limit": 2}'], capture_output=True, env=dict(os.environ))
ok("ligne de commande : sortie = texte de l'outil, code 0", r.returncode == 0 and json.loads(r.stdout.decode())["trades"] == [] and CALLS[-1] == ("history", {"limit": 2}))
r = subprocess.run(cli + ["account", "[1]"], capture_output=True, env=dict(os.environ))
ok("ligne de commande : arguments non-objet refusés (code 2)", r.returncode == 2)
r = subprocess.run(cli + ["account"], capture_output=True, env=dict(os.environ, REDROCK_BROKER_URL=DEAD_URL))
ok("ligne de commande : broker injoignable = code 1, message sur stderr", r.returncode == 1 and "injoignable" in r.stderr.decode())

# ------------------------------------------------------------------ 2. scripts de veille
STATE = tempfile.mkdtemp()
HOME = tempfile.mkdtemp()


def mon(name, now, url=URL, sse=False):
    MODE["sse"] = sse
    if FAKE.get("fresh_equity", True):   # le broker enregistre son equity toutes les 5 min
        FAKE["history"]["equity_recent"] = [{"ts": iso(now - 120), "equity": 100.0}]
    if name == "docteur" and FAKE.get("fresh_veilles", True):   # les veilles tournent chaque minute
        for n in ("sentinelle", "postmortem"):
            with open(os.path.join(STATE, n + ".json"), "w", encoding="utf-8") as fh:
                json.dump({"_run_at": now - 30, "_ok_at": now - 30}, fh)
    env = dict(os.environ, REDROCK_BROKER_URL=url, REDROCK_VEILLE_DIR=STATE, HERMES_HOME=HOME, REDROCK_VEILLE_NOW=str(now))
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(SCRIPTS, f"{name}_monitor.py")], capture_output=True, env=env, timeout=60)
    MODE["sse"] = False
    err = (state(name).get("_error") or {}) if url == URL and name != "docteur" else {}
    if err.get("at") == now:   # le faux broker n'a pas répondu : à distinguer d'une erreur de logique
        print(f"     (passage {name} à T0+{now - T0:.0f} : {err.get('msg')})")
    return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")


def state(name):
    with open(os.path.join(STATE, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def pos(coin="BTC", side="long", entry=100.0, mark=100.0, sl=95.0, opened=T0 - 3600, **kw):
    return {"coin": coin, "side": side, "size": 0.5, "entry": entry, "leverage": 2, "stop_loss": sl, "take_profit": None,
            "opened_at": iso(opened), "mark": mark, "unrealized_pnl": (mark - entry) * 0.5, **kw}


# ---- sentinelle
reset()
FAKE["news"]["items"] = [{"src": "coindesk", "title": "Exchange X hacked for $100M", "published": pub(T0 - 600), "link": "https://example.com/a"}]
c1, o1, e1 = mon("sentinelle", T0)
c2, o2, _ = mon("sentinelle", T0 + 60)
ok("sentinelle : rien à signaler = « aucune alerte », code 0", c1 == 0 and o1 == "Sentinelle RedRock : aucune alerte.\n" and not e1)
ok("sentinelle : deux passages identiques (pas de réveil)", o1 == o2)
ok("sentinelle : 1er passage, l'actualité déjà là n'est pas rejouée", "hacked" not in o1)
news_calls = sum(1 for c in CALLS if c[0] == "news")
ok("sentinelle : news lue au 1er passage puis pas avant 5 min", news_calls == 1)
ok("sentinelle : sessions MCP toutes fermées", not SESSIONS)

FAKE["account"]["positions"] = [pos(mark=100.0)]
_, o, _ = mon("sentinelle", T0 + 120)
FAKE["account"]["positions"] = [pos(mark=99.0)]
_, o3, _ = mon("sentinelle", T0 + 420)
ok("sentinelle : -1 % en 5 min, sous le seuil : rien", o3 == o1)
FAKE["account"]["positions"] = [pos(mark=96.6)]
_, o4, _ = mon("sentinelle", T0 + 720)
ok("sentinelle : -3,4 % en 10 min sur un coin tenu : alerte « mouvement »", "mouvement · BTC -3.4 % en 10 min (100 → 96.6)" in o4 and "à contre-sens" in o4)
_, o5, _ = mon("sentinelle", T0 + 780)
ok("sentinelle : même mouvement le tick suivant : sortie identique (une seule fois)", o5 == o4)

FAKE["account"]["positions"] = [pos(mark=96.6, sl=96.3)]
_, o6, _ = mon("sentinelle", T0 + 840)
ok("sentinelle : stop à 0,31 % : alerte « stop proche »", o6.count("\n• ") == 2 and "stop proche · BTC LONG à 0.31 % de son stop (96.3" in o6)
ok("sentinelle : la plus récente en premier", o6.splitlines()[1].startswith("• ") and "stop proche" in o6.splitlines()[1])
_, o7, _ = mon("sentinelle", T0 + 900)
ok("sentinelle : stop toujours proche : rien de neuf", o7 == o6)

FAKE["account"]["positions"] = [pos(coin="ETH", side="short", entry=2000, mark=2000, sl=2100, liquidation_px="2080", opened=T0)]
FAKE["account"]["positions"][0].pop("mark")
FAKE["account"]["positions"][0].update(unrealized_pnl=0.0, stop_loss_on_exchange=[2100.0])
FAKE["account"]["positions"][0].pop("stop_loss")
_, o8, _ = mon("sentinelle", T0 + 960)
ok("sentinelle : réel (prix déduit du PnL, stops de l'exchange) : liquidation à 4 % = alerte", "liquidation proche · ETH SHORT à 4.0 % de sa liquidation (2080" in o8)
ok("sentinelle : coin fermé : son historique de prix oublié", list(state("sentinelle")["prices"]) == ["ETH"])

FAKE["events"]["events"] = [
    {"id": "ff:US CPI m/m:1", "kind": "macro", "source": "forexfactory", "title": "US CPI m/m", "impact": "high",
     "when_utc": "2027-01-15 08:50", "in_hours": 0.4, "detail": {"forecast": "0.3%", "previous": "0.2%"}, "coins": ["BTC", "ETH"]},
    {"id": "ff:US FOMC:2", "kind": "macro", "source": "forexfactory", "title": "US FOMC", "impact": "high",
     "when_utc": "2027-01-15 09:50", "in_hours": 1.0, "coins": ["BTC", "ETH"]},
    {"id": "binance:1", "kind": "delisting", "source": "binance", "title": "Binance will delist DOGE", "impact": "high",
     "when_utc": "2027-01-15 07:40", "ago_hours": 0.3, "coins": ["DOGE"]},
    {"id": "binance:2", "kind": "delisting", "source": "binance", "title": "Binance will delist ETH perps", "impact": "high",
     "when_utc": "2027-01-15 07:40", "ago_hours": 0.3, "coins": ["ETH"]}]
_, o9, _ = mon("sentinelle", T0 + 1020)
ok("sentinelle : annonce macro dans 24 min : alerte avec prévision", "annonce macro · US CPI m/m à 2027-01-15 08:50 UTC (dans moins de 30 min), forecast 0.3%, previous 0.2%" in o9)
ok("sentinelle : macro dans 1 h : pas encore", "FOMC" not in o9)
ok("sentinelle : annonce sur un coin tenu (ETH) oui, sur un autre (DOGE) non", "delist ETH" in o9 and "DOGE" not in o9)
ok("sentinelle : events demandé à fort impact seulement", CALLS[-1][0] == "events" and CALLS[-1][1]["min_impact"] == "high" or any(c == ("events", {"hours_back": 1, "hours_ahead": 1, "min_impact": "high"}) for c in CALLS))
_, o10, _ = mon("sentinelle", T0 + 1080)
ok("sentinelle : mêmes annonces : sortie identique", o10 == o9)

FAKE["news"]["items"] = [
    {"src": "coindesk", "title": "Exchange X hacked for $100M", "published": pub(T0 - 600), "link": "https://example.com/a"},
    {"src": "theblock", "title": "Bridge exploit drains $40M​ from protocol", "published": pub(T0 + 1000), "link": "https://example.com/b"},
    {"src": "decrypt", "title": "Ethereum price plunges after ETF outflows", "published": pub(T0 + 1000), "link": "https://example.com/c"},
    {"src": "decrypt", "title": "Solana price plunges", "published": pub(T0 + 1000), "link": "https://example.com/d"},
    {"src": "decrypt", "title": "Old hack story", "published": pub(T0 - 7200), "link": "https://example.com/e"},
    {"src": "coinmarketcap", "via": "Média A", "title": "Markets are calm today", "published": pub(T0 + 1000), "link": "https://example.com/f"}]
n_news = sum(1 for c in CALLS if c[0] == "news")
_, o11, _ = mon("sentinelle", T0 + 1320)
ok("sentinelle : actualité forte récente : alerte, caractère invisible retiré", "actualité · [theblock] Bridge exploit drains $40M from protocol" in o11 and "​" not in o11)
ok("sentinelle : coin tenu (ETH, nom complet) + mot de mouvement : alerte", "Ethereum price plunges after ETF outflows (coins tenus : ETH)" in o11)
ok("sentinelle : coin non tenu, vieille actu, actu banale, déjà vue : rien", all(x not in o11 for x in ("Solana", "Old hack", "calm", "hacked for")))
_, o12, _ = mon("sentinelle", T0 + 1380)
ok("sentinelle : news relue 5 min après la précédente, pas avant ; sortie identique", o12 == o11 and sum(1 for c in CALLS if c[0] == "news") == n_news + 1)

FAKE["account"]["circuit_breaker"] = {"frozen": True, "reason": "equity -16 % en une heure", "until_paris": "2027-01-15T10:20+01:00"}
FAKE["account"]["recent_actions"] = [{"ts": iso(T0 + 1430), "kind": "guard", "text": "ETH : stop absent de l'exchange, reposé à 2100"},
                                     {"ts": iso(T0 - 7200), "kind": "guard", "text": "vieille action de garde"},
                                     {"ts": iso(T0 + 1430), "kind": "open", "text": "long BTC"}]
_, o13, _ = mon("sentinelle", T0 + 1440)
ok("sentinelle : coupe-circuit et action de garde récente : alertes", "coupe-circuit · nouvelles ouvertures gelées jusqu'à 2027-01-15T10:20+01:00" in o13 and "garde du broker · ETH : stop absent" in o13)
ok("sentinelle : vieille action de garde et action normale ignorées", "vieille action" not in o13 and "long BTC" not in o13)
lines = [x for x in o13.splitlines() if x.startswith("• ")]
ok("sentinelle : sortie bornée à 8 alertes", len(lines) == 8)
_, o14, _ = mon("sentinelle", T0 + 1500)
ok("sentinelle : rien de neuf : identique", o14 == o13)

c, o15, e = mon("sentinelle", T0 + 1560, url=DEAD_URL)
st = state("sentinelle")
ok("sentinelle : broker injoignable : même sortie, code 0 (pas de réveil, pas d'alerte d'échec)", c == 0 and o15 == o13)
ok("sentinelle : panne notée dans l'état pour le docteur", st.get("_error", {}).get("since") == T0 + 1560 and st["_ok_at"] == T0 + 1500)
_, o16, _ = mon("sentinelle", T0 + 1620, sse=True)
ok("sentinelle : broker revenu (réponses SSE) : identique, panne effacée", o16 == o13 and "_error" not in state("sentinelle"))
FAKE["account"]["generation"] = 2
FAKE["account"]["positions"], FAKE["account"]["circuit_breaker"], FAKE["account"]["recent_actions"] = [], {"frozen": False}, []
FAKE["events"]["events"] = []
_, o17, _ = mon("sentinelle", T0 + 1680)
ok("sentinelle : nouvelle génération : journal d'alertes vierge", o17 == "Sentinelle RedRock : aucune alerte.\n")
n_news = sum(1 for c in CALLS if c[0] == "news")
_, o18, _ = mon("sentinelle", T0 + 1980)
ok("sentinelle : après la relève, les actualités déjà signalées ne reviennent pas", o18 == o17 and sum(1 for c in CALLS if c[0] == "news") == n_news + 1)
ok("sentinelle : sessions MCP toutes fermées", not SESSIONS)

# ---- post-mortem
reset()
_, p1, _ = mon("postmortem", T0)
_, p2, _ = mon("postmortem", T0 + 60)
ok("post-mortem : aucun trade fermé, deux passages identiques", p1 == p2 == "Post-mortem RedRock : aucun trade fermé pour l'instant.\n")
trade = {"id": 7, "coin": "BTC", "side": "long", "size": 0.001, "entry": 84160.123, "exit": 83010.0, "pnl": -1.15,
         "close_reason": "stop_loss", "closed_at": iso(T0 + 100), "status": "closed", "pnl_net": None, "thesis": "[setup:x] [src:cycle] …"}
FAKE["history"]["trades"] = [{"id": 8, "coin": "ETH", "side": "short", "status": "open", "entry": 2000}, dict(trade)]
_, p3, _ = mon("postmortem", T0 + 120)
ok("post-mortem : un trade se ferme : la sortie change et le nomme", p3 != p2 and "#7 BTC LONG · entrée 84160.1 · sortie 83010 · stop_loss · fermé" in p3)
ok("post-mortem : positions ouvertes non listées", "#8" not in p3)
FAKE["history"]["trades"][1].update(pnl_net=-1.21, fees_total=0.06, settled_at=iso(T0 + 160))
_, p4, _ = mon("postmortem", T0 + 180)
ok("post-mortem : pnl_net calculé ensuite : sortie identique (pas de 2e réveil)", p4 == p3)
FAKE["history"]["trades"].insert(0, dict(trade, id=9, coin="SOL", side="short", close_reason="manuel :\nraison longue", closed_at=iso(T0 + 200)))
_, p5, _ = mon("postmortem", T0 + 240)
ok("post-mortem : 2e trade fermé : en tête, raison sur une ligne", p5.splitlines()[1].startswith("• #9 SOL SHORT") and "manuel : raison longue" in p5 and "#7 BTC" in p5.splitlines()[2])
_, p6, _ = mon("postmortem", T0 + 300, url=DEAD_URL)
ok("post-mortem : broker injoignable : dernière sortie", p6 == p5)

# ---- docteur
reset()
cron_dir = os.path.join(HOME, "cron")
os.makedirs(cron_dir, exist_ok=True)
jobs = {"jobs": [{"id": "a1", "name": "cycle-trading", "enabled": True, "state": "scheduled", "failure_streak": 0},
                 {"id": "a2", "name": "sentinelle", "enabled": True, "monitor_script": "sentinelle_monitor.py", "failure_streak": 1},
                 {"id": "a3", "name": "post-mortem", "enabled": True, "monitor_script": "postmortem_monitor.py", "failure_streak": 0}]}


def put_jobs():
    with open(os.path.join(cron_dir, "jobs.json"), "w", encoding="utf-8") as fh:
        json.dump(jobs, fh)


put_jobs()
HEALTHY = "Docteur RedRock : aucun problème persistant.\n"
_, d1, _ = mon("docteur", T0)
_, d2, _ = mon("docteur", T0 + 300)
ok("docteur : tout va bien, deux contrôles : même ligne fixe", d1 == d2 == HEALTHY)
FAKE["account"]["positions"] = [pos(sl=None)]
_, d3, _ = mon("docteur", T0 + 600)
ok("docteur : position sans stop vue une fois : silence", d3 == HEALTHY)
FAKE["account"]["positions"] = [pos()]
_, d4, _ = mon("docteur", T0 + 900)
ok("docteur : problème passager (un seul contrôle) : jamais signalé", d4 == HEALTHY)
FAKE["account"]["positions"] = [dict(pos(coin="ETH", side="short", entry=2000, mark=2000, sl=None), stop_loss_on_exchange=[])]
mon("docteur", T0 + 1200)
_, d5, _ = mon("docteur", T0 + 1500)
ok("docteur : sans stop sur l'exchange à deux contrôles : signalé", d5.startswith("Docteur RedRock : problème(s) vu(s) à deux contrôles") and "[stop:ETH] position ETH SHORT sans stop-loss sur l'exchange" in d5)
_, d6, _ = mon("docteur", T0 + 1800)
ok("docteur : problème qui dure : sortie identique (un seul réveil)", d6 == d5)
FAKE["account"]["positions"] = []
_, d7, _ = mon("docteur", T0 + 2100)
ok("docteur : problème réglé : retour à la ligne fixe", d7 == HEALTHY)

mon("docteur", T0 + 2400, url=DEAD_URL)
_, d8, _ = mon("docteur", T0 + 2700, url=DEAD_URL)
ok("docteur : broker injoignable deux fois : signalé, code 0", "[broker] le broker ne répond pas normalement (BrokerError)" in d8)
ok("docteur : broker en panne : pas de fausse alerte sur les veilles", "[veille:" not in d8)
_, d9, _ = mon("docteur", T0 + 3000)
ok("docteur : broker revenu : ligne fixe", d9 == HEALTHY)

FAKE["account"]["circuit_breaker"] = {"frozen": True, "reason": "6 ouvertures en 60 s", "until_paris": "2027-01-15T10:00+01:00"}
FAKE["fresh_equity"] = FAKE["fresh_veilles"] = False
FAKE["history"]["equity_recent"] = [{"ts": iso(T0 + 3300 - 1800), "equity": 100.0}]
jobs["jobs"][0]["failure_streak"] = 3
put_jobs()
with open(os.path.join(STATE, "sentinelle.json"), "w", encoding="utf-8") as fh:
    json.dump({"_run_at": T0 + 3290, "_ok_at": T0 + 1000}, fh)
with open(os.path.join(STATE, "postmortem.json"), "w", encoding="utf-8") as fh:
    json.dump({"_run_at": T0 + 1000, "_ok_at": T0 + 1000}, fh)
mon("docteur", T0 + 3300)
_, d10, _ = mon("docteur", T0 + 3600)
ok("docteur : coupe-circuit, données figées, tâche en échec, veilles muettes : tout signalé",
   all(k in d10 for k in ("[coupe-circuit] coupe-circuit actif", "[donnees] le broker n'enregistre plus son equity",
                          "[tache:cycle-trading] la tâche « cycle-trading » a échoué au moins deux fois de suite",
                          "[veille:sentinelle] la veille de la tâche « sentinelle » ne joint plus le broker",
                          "[veille:postmortem] la veille de la tâche « post-mortem » ne tourne plus")))
ok("docteur : tâche avec un seul échec : pas signalée", "« sentinelle » a échoué" not in d10)
lines = d10.splitlines()[1:]
ok("docteur : problèmes triés (sortie stable)", lines == sorted(lines))
jobs["jobs"][1]["enabled"] = False
put_jobs()
mon("docteur", T0 + 3900)
_, d11, _ = mon("docteur", T0 + 4200)
ok("docteur : tâche désactivée : sa veille n'est plus surveillée", "[veille:sentinelle]" not in d11 and "[veille:postmortem]" in d11)
FAKE["account"]["alive"] = False
mon("docteur", T0 + 4500)
_, d12, _ = mon("docteur", T0 + 4800)
ok("docteur : génération morte : positions, coupe-circuit et données non contrôlés", all(k not in d12 for k in ("[coupe-circuit]", "[donnees]", "[stop:")))
ok("docteur : sessions MCP toutes fermées", not SESSIONS)

print(f"\n{ok.n - ok.bad}/{ok.n} OK")
sys.exit(1 if ok.bad else 0)
