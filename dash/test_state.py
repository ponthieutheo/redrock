"""Test hors ligne de /api/state sur une installation neuve : base du broker vide, pas de boîte à outils (bots,
consignes), aucune tâche programmée, pas de sentinelle ; noms d'outils MCP quel que soit le nom du serveur du broker.
Lancer : python -I -X utf8 dash/test_state.py"""
import json, os, sqlite3, sys, tempfile, time
from datetime import datetime, timezone

os.environ.setdefault("HL_SUBACCOUNT", "0x0000000000000000000000000000000000000000")
os.environ["PAPER_CAPITAL"] = "100"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True


ok.bad = False
TMP = tempfile.mkdtemp()
iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")

# ---------------------------------------------------------------- une base broker telle qu'au premier passage du broker
db = os.path.join(TMP, "broker.db")
c = sqlite3.connect(db)
c.executescript("""
    CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE trades(id INTEGER PRIMARY KEY, gen INT, coin TEXT, side TEXT, size REAL, entry REAL, leverage REAL,
      stop_loss REAL, take_profit REAL, opened_at TEXT, thesis TEXT, market_snapshot TEXT, closed_at TEXT, exit REAL,
      pnl REAL, fees REAL, funding REAL, close_reason TEXT, status TEXT, pnl_gross REAL, fees_total REAL, funding_real REAL,
      pnl_net REAL, settled_at TEXT, initial_stop REAL, intended_px REAL, slippage_bps REAL, entry_oid INTEGER, initial_size REAL);
    CREATE TABLE journal(id INTEGER PRIMARY KEY, gen INT, ts TEXT, kind TEXT, text TEXT);
    CREATE TABLE equity(ts TEXT, gen INT, equity REAL);
    CREATE TABLE lessons(id INTEGER PRIMARY KEY, gen INT, ts TEXT, lesson TEXT, evidence TEXT, confirmed INT DEFAULT 0, contradicted INT DEFAULT 0);
""")
born = time.time() - 600
deadline = born + 30 * 3600
for k, v in {"born": born, "day_ref": {"equity": 100.0, "set_at": born, "deadline": deadline},
             "traj": {"base": 100.0, "born": born, "n": 0, "next_deadline": deadline}, "peak": 100.0}.items():
    c.execute("INSERT INTO meta VALUES(?,?)", (k, json.dumps(v)))
c.execute("INSERT INTO equity VALUES(?,?,?)", (iso(born), 1, 100.0))
c.commit()
c.close()
env = os.path.join(TMP, "redrock.env")
with open(env, "w") as f:
    f.write("MODE=paper\nGENERATION=1\nPAPER_CAPITAL=100\nTRAJ_RULE=on\nDEATH_MODE=drawdown\nDD_TOLERANCE=0.35\n")
toolbox = os.path.join(TMP, "toolbox")
os.makedirs(toolbox)                                   # volume monté, mais vide
dash.DB, dash.GEN, dash.TOOLBOX = db, env, toolbox
dash.CRON, dash.LOG = os.path.join(TMP, "cron", "jobs.json"), os.path.join(TMP, "agent.log")
dash.graveyard = lambda: []                            # pas de lignée (et jamais celle de la machine qui lance le test)
dash.news_signals = lambda: []
calls = []
dash.hl = lambda payload: calls.append(payload) or {"BTC": "110000"}

s = dash.state()
json.dumps(s, default=str)
ok("install neuve : génération 1, en vie, simulation", s["generation"] == 1 and s["alive"] is True and s["mode"] == "paper")
ok("capital de départ simulé (100 $), aucun résultat", s["equity"] == 100 and s["pnl_total"] == 0 and s["start_equity"] == 100)
ok("aucun trade, aucune position, aucun ordre", s["trades"] == [] and s["positions"] == [] and s["pending"] == [])
ok("aucune tâche programmée : liste vide", s["jobs"] == [])
ok("pas de boîte à outils : aucun bot (liste vide), pas de consignes", s["bots"] == [] and not s["directives"])
ok("agent au repos (pas de journal Hermes)", s["activity"] == {"thinking": False})
ok("trajectoire et objectif du jour présents", s["trajectory"]["death_line"] == 65 and s["daily"]["target"] == 101)
ok("simulation : seuls les prix sont lus", calls == [{"type": "allMids"}])
ok("courbes de toutes les vies : une seule génération", [g["gen"] for g in dash.curves()] == [1])
a = dash.achievements()
ok("succès : aucun débloqué, série 0", not any(b["at"] for b in a["badges"]) and a["streak"] == 0 and a["record"] == 0)

# ---------------------------------------------------------------- la boîte à outils d'un agent qui en a une
os.makedirs(os.path.join(toolbox, "bots"))
open(os.path.join(toolbox, "bots", "veille.py"), "w").write("print('ok')\n")
open(os.path.join(toolbox, "bots", "trail.py"), "w").write("print('ok')\n")
open(os.path.join(toolbox, "bots", "veille.log"), "w").write("[signal] news : Un titre (jev 0.82)\n")
open(os.path.join(toolbox, "bots", "enabled.txt"), "w").write("# actifs\nveille.py\n")
open(os.path.join(toolbox, "DIRECTIVES.md"), "w", encoding="utf-8").write("# Consignes\n- rester prudent\n")
s = dash.state()
ok("avec une boîte à outils : bots listés, activé ou non", [(b["name"], b["enabled"]) for b in s["bots"]] == [("trail.py", False), ("veille.py", True)])
ok("avec une boîte à outils : consignes lues", s["directives"].startswith("# Consignes"))

# ---------------------------------------------------------------- scores de la sentinelle : absente = aucun score (le compte rendu des actus ne plante pas)
ok("sans sentinelle : aucun score de pertinence, pas d'exception", dash.jev_scores() == {})
open(os.path.join(toolbox, "bots", "sentinel.log"), "w").write("[signal] news : Un titre (jev 0.82)\n")
ok("avec la sentinelle : score lu", dash.jev_scores() == {"Un titre": 0.82})

# ---------------------------------------------------------------- noms d'outils : préfixe MCP retiré, quel que soit le serveur
ok("préfixe du broker privé", dash.tool_name("mcp__clint_broker__place_trade") == "place_trade")
ok("préfixe du broker public", dash.tool_name("mcp__redrock_broker__account") == "account")
ok("préfixe avec tiret", dash.tool_name("mcp__redrock-broker__set_stops") == "set_stops")
ok("outil de Hermes sans préfixe", dash.tool_name("terminal") == "terminal" and dash.tool_name("web_search") == "web_search")

# ---------------------------------------------------------------- activité lue dans le journal de Hermes
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def act(session, tool_line, jobs=()):
    with open(dash.LOG, "w") as f:
        f.write("ligne coupée\n"
                f"{now} INFO [{session}] agent.tool_executor: tool {tool_line} args={{}}\n"
                f"{now} INFO [{session}] agent.conversation_loop: API call #4\n")
    return dash.activity(list(jobs))


a = act("dashboard-chat", "mcp__redrock_broker__place_trade")
ok("chat de l'app : outil du broker public reconnu", a["thinking"] and a["tool"] == "place_trade" and a["doing"] == "passe un ordre")
ok("chat de l'app : « conversation dans l'app »", a["where"] == "conversation dans l'app")
a = act("cron_ab12cd_20261014_100000", "mcp__mon_broker__account", [{"id": "ab12cd", "name": "cycle-trading"}])
ok("tâche programmée : nom de la tâche, outil reconnu", a["where"] == "tâche « cycle-trading »" and a["doing"] == "vérifie son compte")
a = act("20261014_101010_xyz", "terminal")
ok("autre conversation : libellé neutre", a["where"] == "conversation" and a["doing"] == "travaille dans son terminal")

print("\nÉCHEC" if ok.bad else "\nTout est OK")
sys.exit(1 if ok.bad else 0)
