"""Test hors ligne : en simulation (MODE=paper), l'app lit le compte simulé du broker, jamais le solde d'une adresse.
Lancer : python -X utf8 dash/test_paper.py"""
import os, sys

os.environ.setdefault("HL_SUBACCOUNT", "0x0000000000000000000000000000000000000000")
sys.path.insert(0, os.path.dirname(__file__))
import dash


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True


ok.bad = False
mids = {"BTC": "110000", "ETH": "4000"}
paper = {"cash": 98.5, "start": 100.0,
         "positions": {"BTC": {"side": "long", "size": 0.001, "entry": 100000.0, "leverage": 5, "stop_loss": 95000.0,
                               "take_profit": 120000.0, "entry_fee": .05, "funding": 0, "opened_at": "2026-10-14T10:00:00+00:00"}},
         "orders": {"ETH": {"side": "short", "size": 0.01, "leverage": 3, "stop_loss": 4200.0, "take_profit": None,
                            "thesis": "[setup:test] rejet sous 4000", "price": 4100.0, "placed_at": "2026-10-14T11:00:00+00:00"}}}
dash.meta = lambda k, d=None: paper if k == "paper" else d
perp, orders, equity = dash.paper_account(mids)
ok("equity = cash + PnL latent (98,5 + 10)", abs(equity - 108.5) < 1e-9)
p = perp["assetPositions"][0]["position"]
ok("position au format Hyperliquid (LONG = taille positive)", p["coin"] == "BTC" and float(p["szi"]) == 0.001 and float(p["entryPx"]) == 100000)
ok("PnL latent et marge", abs(float(p["unrealizedPnl"]) - 10) < 1e-9 and abs(float(p["marginUsed"]) - 20) < 1e-9)
trig = [o for o in orders if o["coin"] == "BTC"]
ok("stop et objectif de la position", {o["orderType"] for o in trig} == {"Stop Market", "Take Profit Market"}
   and all(o["reduceOnly"] for o in trig))
lim = [o for o in orders if o["coin"] == "ETH" and not o["reduceOnly"]]
ok("ordre limite en attente (SHORT = côté A)", len(lim) == 1 and lim[0]["side"] == "A" and float(lim[0]["limitPx"]) == 4100)
ok("son stop (pas d'objectif posé)", [o["orderType"] for o in orders if o["coin"] == "ETH" and o["reduceOnly"]] == ["Stop Market"])
ok("horodatage en ms", lim[0]["timestamp"] == 1791975600000)
# compte simulé pas encore créé par le broker : on annonce le capital de départ
paper_none = None
dash.meta = lambda k, d=None: paper_none if k == "paper" else d
os.environ["PAPER_CAPITAL"] = "250"
_, o2, eq2 = dash.paper_account(mids)
ok("avant le premier passage du broker : capital de départ", eq2 == 250 and o2 == [])
# jamais de lecture du compte en simulation
calls = []
dash.hl = lambda payload: calls.append(payload) or ({"BTC": "110000"} if payload.get("type") == "allMids" else {})
dash.env = lambda: {"MODE": "paper"}
try:
    dash.state()
except Exception:
    pass   # la suite de state() lit la base du broker, absente ici : seules les requêtes comptent
ok("simulation : aucune requête sur une adresse (seulement les prix)", calls and all("user" not in c for c in calls))

print("\nÉCHEC" if ok.bad else "\nTout est OK")
sys.exit(1 if ok.bad else 0)
