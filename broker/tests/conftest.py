"""Faux Hyperliquid pour tester le broker sans jamais toucher au compte réel.

Les formats (statuts d'ordres, ordres ouverts, remplissages) reprennent ceux observés en réel le 11/10.
"""
import itertools
import json
import os
import sys
import time

import pytest

os.environ.setdefault("HL_SUBACCOUNT", "0x0000000000000000000000000000000000000001")
os.environ.setdefault("MODE", "live")
os.environ.setdefault("GENERATION", "2")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import broker as B  # noqa: E402

SUB = os.environ["HL_SUBACCOUNT"]
FIX = os.path.join(os.path.dirname(__file__), "fixtures", "real_2026-10-11.json")


def ok_statuses(statuses):
    return {"status": "ok", "response": {"type": "order", "data": {"statuses": statuses}}}


class FakeHL:
    def __init__(self):
        self.positions = {}   # coin -> {"szi": float, "entryPx": float, "lev": int}
        self.orders = []      # format frontendOpenOrders
        self.fills = []
        self.funding = []
        self.ledger = []
        self.mids = {"BTC": 100.0, "ETH": 50.0, "SOL": 20.0}
        self.usdc = 100.0
        self.calls = []
        self.oid = itertools.count(1000)
        self.tid = itertools.count(1)
        self.now_ms = int(time.time() * 1000)

    # ------------------------------------------------------------- info
    def info(self, p, timeout=15):
        t = p["type"]
        self.calls.append(t)
        if t == "clearinghouseState":
            return {"assetPositions": [
                {"position": {"coin": c, "szi": str(x["szi"]), "entryPx": str(x["entryPx"]),
                              "unrealizedPnl": str((self.mids[c] - x["entryPx"]) * x["szi"]),
                              "leverage": {"type": "isolated", "value": x.get("lev", 5)},
                              "liquidationPx": None}} for c, x in self.positions.items()],
                "marginSummary": {"accountValue": str(self.usdc)}}
        if t == "spotClearinghouseState":
            return {"balances": [{"coin": "USDC", "total": str(self.usdc)}]}
        if t == "userAbstraction":
            return "default"
        if t == "frontendOpenOrders":
            return [dict(o) for o in self.orders]
        if t == "allMids":
            return {k: str(v) for k, v in self.mids.items()}
        if t == "metaAndAssetCtxs":
            coins = list(self.mids)
            return [{"universe": [{"name": c, "szDecimals": 3, "maxLeverage": 20} for c in coins]},
                    [{"midPx": str(self.mids[c]), "markPx": str(self.mids[c]), "funding": "0.00001",
                      "openInterest": "1000", "dayNtlVlm": str(1e6 * (len(coins) - i)),
                      "prevDayPx": str(self.mids[c]), "premium": "0"} for i, c in enumerate(coins)]]
        if t == "userFillsByTime":
            return [f for f in self.fills if f["time"] >= p["startTime"]][:2000]
        if t == "userFills":
            return list(reversed(self.fills))[:2000]
        if t == "userFunding":
            return [f for f in self.funding if f["time"] >= p["startTime"]][:500]
        if t == "userNonFundingLedgerUpdates":
            return [u for u in self.ledger if u["time"] >= p["startTime"]]
        if t == "l2Book":
            m = self.mids[p["coin"]]
            return {"levels": [[{"px": str(m - i), "sz": "1", "n": 1} for i in range(1, 4)],
                               [{"px": str(m + i), "sz": "1", "n": 1} for i in range(1, 4)]]}
        if t == "candleSnapshot":
            # série synthétique : prix constant, amplitude ±0,5 % (ATR = 1 % du prix)
            req = p["req"]
            step = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}[req["interval"]] * 1000
            end = req.get("endTime") or self.now_ms
            m = self.mids.get(req["coin"], 90.0)
            out, ts_ = [], max(req["startTime"], end - 500 * step)
            while ts_ <= end:
                out.append({"t": ts_, "o": str(m), "h": str(m * 1.005), "l": str(m * 0.995), "c": str(m), "v": "1"})
                ts_ += step
            return out
        raise AssertionError(f"appel info inattendu : {p}")

    # ------------------------------------------------------------- helpers
    def add_fill(self, coin, is_buy, sz, px, oid):
        pos = self.positions.get(coin)
        start = pos["szi"] if pos else 0.0
        signed = sz if is_buy else -sz
        closing = start != 0 and (start > 0) != (signed > 0)
        closed_pnl = (px - pos["entryPx"]) * min(sz, abs(start)) * (1 if start > 0 else -1) if closing else 0.0
        self.now_ms += 1000
        self.fills.append({"coin": coin, "px": str(px), "sz": str(sz), "side": "B" if is_buy else "A",
                           "time": self.now_ms, "startPosition": str(start),
                           "dir": ("Close " if closing else "Open ") + ("Long" if (start > 0 or (start == 0 and is_buy)) else "Short"),
                           "closedPnl": str(closed_pnl), "fee": str(round(px * sz * 0.00045, 8)),
                           "oid": oid, "tid": next(self.tid), "crossed": True})
        new = round(start + signed, 10)
        if new == 0:
            self.positions.pop(coin, None)
        elif pos:
            pos["szi"] = new
        else:
            self.positions[coin] = {"szi": new, "entryPx": px, "lev": 5}

    def add_trigger(self, coin, req):
        oid = next(self.oid)
        trig = req["order_type"]["trigger"]
        self.orders.append({"coin": coin, "side": "B" if req["is_buy"] else "A", "limitPx": str(req["limit_px"]),
                            "sz": str(req["sz"]), "oid": oid, "isTrigger": True, "triggerPx": str(trig["triggerPx"]),
                            "orderType": "Stop Market" if trig["tpsl"] == "sl" else "Take Profit Market",
                            "reduceOnly": True, "isPositionTpsl": False, "children": []})
        return oid


class FakeExchange:
    def __init__(self, hl):
        self.hl = hl
        self.reject_sl = 0          # nombre de SL à refuser
        self.reject_tp = 0
        self.invisible_triggers = 0  # nombre de déclencheurs acceptés mais absents des ordres ouverts
        self.close_fill_ratio = 1.0
        self.sent = []

    def update_leverage(self, lev, coin, is_cross=True):
        return {"status": "ok"}

    def bulk_orders(self, reqs, grouping="na"):
        self.sent.append((grouping, reqs))
        statuses = []
        filled = False
        for i, r in enumerate(reqs):
            coin = r["coin"]
            if "trigger" in r["order_type"]:
                kind = r["order_type"]["trigger"]["tpsl"]
                if kind == "sl" and self.reject_sl:
                    self.reject_sl -= 1
                    statuses.append({"error": "Invalid TP/SL price."})
                    continue
                if kind == "tp" and self.reject_tp:
                    self.reject_tp -= 1
                    statuses.append({"error": "Invalid TP/SL price."})
                    continue
                if self.invisible_triggers:
                    self.invisible_triggers -= 1
                    statuses.append({"resting": {"oid": 1}})
                    continue
                if grouping == "normalTpsl" and not filled:
                    statuses.append("waitingForFill")  # enfant d'une entrée limite en attente
                    continue
                oid = self.hl.add_trigger(coin, r)
                statuses.append("waitingForFill" if grouping == "normalTpsl" else {"resting": {"oid": oid}})
            else:
                oid = next(self.hl.oid)
                if r["order_type"]["limit"]["tif"] == "Ioc":
                    px = self.hl.mids[coin]
                    self.hl.add_fill(coin, r["is_buy"], r["sz"], px, oid)
                    filled = True
                    statuses.append({"filled": {"totalSz": str(r["sz"]), "avgPx": str(px), "oid": oid}})
                else:
                    self.hl.orders.append({"coin": coin, "side": "B" if r["is_buy"] else "A", "limitPx": str(r["limit_px"]),
                                           "sz": str(r["sz"]), "oid": oid, "isTrigger": False, "orderType": "Limit",
                                           "reduceOnly": False, "children": []})
                    statuses.append({"resting": {"oid": oid}})
        return ok_statuses(statuses)

    def cancel(self, coin, oid):
        before = len(self.hl.orders)
        self.hl.orders = [o for o in self.hl.orders if o["oid"] != oid]
        st = "success" if len(self.hl.orders) < before else {"error": "Order was never placed, already canceled, or filled."}
        return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": [st]}}}

    def market_close(self, coin, sz=None, **kw):
        pos = self.hl.positions.get(coin)
        if not pos:
            return None
        size = sz or abs(pos["szi"])
        size = round(size * self.close_fill_ratio, 6)
        oid = next(self.hl.oid)
        px = self.hl.mids[coin]
        self.hl.add_fill(coin, pos["szi"] < 0, size, px, oid)
        return ok_statuses([{"filled": {"totalSz": str(size), "avgPx": str(px), "oid": oid}}])


@pytest.fixture
def env(tmp_path, monkeypatch):
    hl = FakeHL()
    ex = FakeExchange(hl)
    monkeypatch.setattr(B, "DB_PATH", str(tmp_path / "clint.db"))
    monkeypatch.setattr(B, "MARKET_DB_PATH", str(tmp_path / "market.db"))
    monkeypatch.setattr(B, "info", hl.info)
    monkeypatch.setattr(B, "_ex", ex)
    monkeypatch.setattr(B.time, "sleep", lambda s: None)
    monkeypatch.setattr(B, "MODE", "live")
    monkeypatch.setattr(B, "RISK_ENGINE", False)  # testé à part (tests du moteur de risque)
    for k, v in (("_no_sl", {}), ("_eq_hist", []), ("_pend_check", {"t": 0}),
                 ("_mids", {"t": 0, "v": {}}), ("_meta_cache", {"t": 0, "v": None}), ("_missing_fills", {})):
        monkeypatch.setattr(B, k, v)
    B.init_db()
    return hl, ex


def load_real():
    if not os.path.exists(FIX):   # données réelles exportées, jamais versionnées (dépôt public : test sauté)
        pytest.skip("fixture de données réelles absente")
    with open(FIX) as f:
        return json.load(f)


def j(s):
    return json.loads(s)
