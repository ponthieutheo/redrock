"""Tests du broker (phase 1 de docs/PLAN.md). Aucun appel réseau : tout passe par FakeHL."""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import B, FakeHL, j, load_real


def set_price(hl, coin, px):
    hl.mids[coin] = px
    B._mids["t"] = 0


def open_long(hl, ex, coin="BTC", usd=50, sl=95.0, tp=110.0, thesis="[setup:test] [src:cycle] test"):
    return j(B.place_trade(coin, "long", usd, 5, sl, thesis, take_profit=tp))


def sls(hl, coin="BTC"):
    return [float(o["triggerPx"]) for o in hl.orders if o["coin"] == coin and o["orderType"] == "Stop Market"]


def tps(hl, coin="BTC"):
    return [float(o["triggerPx"]) for o in hl.orders if o["coin"] == coin and o["orderType"] == "Take Profit Market"]


def row(coin="BTC"):
    with B.db() as c:
        return c.execute("SELECT * FROM trades WHERE coin=? ORDER BY id DESC LIMIT 1", (coin,)).fetchone()


# ------------------------------------------------------------------ ouverture
def test_ouverture_marche_pose_sl_et_tp(env):
    hl, ex = env
    r = open_long(hl, ex)
    assert r["filled"] and sls(hl) == [95.0] and tps(hl) == [110.0]
    t = row()
    assert t["status"] == "open" and t["initial_stop"] == 95.0 and t["initial_size"] == t["size"]
    assert t["intended_px"] == 100.0 and t["slippage_bps"] == 0.0


def test_sl_refuse_a_l_ouverture_puis_repose_seul(env):
    hl, ex = env
    ex.reject_sl = 1
    r = open_long(hl, ex)
    assert r["filled"] and "warning" in r
    assert sls(hl) == [95.0] and "BTC" in hl.positions


def test_sl_impossible_ferme_la_position(env):
    hl, ex = env
    ex.reject_sl = 2
    r = open_long(hl, ex)
    assert "error" in r and "fermée" in r["error"]
    assert "BTC" not in hl.positions
    assert row()["status"] == "closed"
    assert any(e["kind"] == "no_stop" for e in B.meta_get("guard_events", []))


def test_limite_dont_le_sl_est_refuse_est_annulee(env):
    hl, ex = env
    ex.reject_sl = 1
    r = j(B.place_trade("BTC", "long", 50, 5, 90.0, "t", take_profit=0, limit_price=98.0))
    assert "error" in r
    assert not [o for o in hl.orders if o["orderType"] == "Limit"]
    assert B.meta_get("live_pending", {}) == {}


# ------------------------------------------------------------------ set_stops
def test_set_stops_remplace_apres_verification(env):
    hl, ex = env
    open_long(hl, ex)
    r = j(B.set_stops("BTC", 97.0, 112.0))
    assert r["ok"] and sls(hl) == [97.0] and tps(hl) == [112.0]
    assert row()["stop_loss"] == 97.0 and row()["take_profit"] == 112.0


def test_set_stops_refuse_garde_l_ancien_stop(env):
    hl, ex = env
    open_long(hl, ex)
    ex.reject_sl = 1
    r = j(B.set_stops("BTC", 97.0, 112.0))
    assert r["ok"] is False and "error" in r          # la sentinelle lit la clé « error »
    assert sls(hl) == [95.0] and row()["stop_loss"] == 95.0


def test_set_stops_accepte_mais_invisible_garde_l_ancien(env):
    hl, ex = env
    open_long(hl, ex)
    ex.invisible_triggers = 1
    r = j(B.set_stops("BTC", 97.0, 112.0))
    assert "error" in r and sls(hl) == [95.0] and row()["stop_loss"] == 95.0


def test_set_stops_tp_refuse_garde_le_nouveau_sl(env):
    hl, ex = env
    open_long(hl, ex)
    ex.reject_tp = 1
    r = j(B.set_stops("BTC", 97.0, 112.0))
    assert r["ok"] and "warning" in r
    assert sls(hl) == [97.0] and tps(hl) == [110.0] and row()["take_profit"] == 110.0


def test_set_stops_sans_tp_retire_le_tp(env):
    hl, ex = env
    open_long(hl, ex)
    assert j(B.set_stops("BTC", 97.0, 0))["ok"]
    assert sls(hl) == [97.0] and tps(hl) == []


# ------------------------------------------------------------------ garde des stops
def test_garde_repose_un_stop_disparu(env):
    hl, ex = env
    open_long(hl, ex)
    hl.orders = [o for o in hl.orders if o["orderType"] != "Stop Market"]
    snap = B.snapshot()
    B.stop_guard(snap)
    assert sls(hl) == []                      # 1er contrôle : on laisse une chance (set_stops en cours)
    B.stop_guard(snap)
    assert sls(hl) == [95.0]
    assert any(e["kind"] == "stop_restored" for e in B.meta_get("guard_events", []))


def test_garde_ferme_si_le_stop_est_deja_depasse(env):
    hl, ex = env
    open_long(hl, ex)
    hl.orders = []
    set_price(hl, "BTC", 94.0)
    snap = B.snapshot()
    B.stop_guard(snap)
    B.stop_guard(snap)
    assert "BTC" not in hl.positions and row()["status"] == "closed"


def test_garde_ne_touche_pas_une_position_protegee(env):
    hl, ex = env
    open_long(hl, ex)
    n = len(ex.sent)
    for _ in range(3):
        B.stop_guard(B.snapshot())
    assert len(ex.sent) == n


# ------------------------------------------------------------------ clôtures
def test_cloture_partielle_reduit_et_reprotege(env):
    hl, ex = env
    open_long(hl, ex, usd=60)
    size0 = row()["size"]
    set_price(hl, "BTC", 104.0)
    r = j(B.close_position("BTC", "prise partielle", 0.5))
    assert r["partial"] and r["realized_pnl"] > 0
    t = row()
    assert t["status"] == "open" and abs(t["size"] - (size0 - r["closed_size"])) < 1e-9
    assert t["initial_size"] == size0
    sl = [o for o in hl.orders if o["orderType"] == "Stop Market"]
    assert len(sl) == 1 and float(sl[0]["sz"]) == pytest.approx(t["size"])
    assert len(tps(hl)) == 1


def test_cloture_partielle_trop_petite_refusee(env):
    hl, ex = env
    open_long(hl, ex, usd=15)
    r = j(B.close_position("BTC", "x", 0.5))
    assert "error" in r and "BTC" in hl.positions


def test_cloture_totale(env):
    hl, ex = env
    open_long(hl, ex)
    set_price(hl, "BTC", 102.0)
    r = j(B.close_position("BTC", "thèse invalidée"))
    assert r["closed"] and r["px"] == 102.0
    t = row()
    assert t["status"] == "closed" and t["exit"] == 102.0 and t["pnl"] > 0
    assert not [o for o in hl.orders if o["coin"] == "BTC"]


def test_cloture_incomplete_garde_la_ligne_ouverte(env):
    hl, ex = env
    open_long(hl, ex, usd=60)
    ex.close_fill_ratio = 0.5
    j(B.close_position("BTC", "x"))
    assert "BTC" in hl.positions and row()["status"] == "open"
    assert sls(hl)  # toujours protégée


# ------------------------------------------------------------------ rapprochement
def test_ordres_en_attente_interroges_au_plus_toutes_les_15_s(env):
    hl, ex = env
    B.place_trade("BTC", "long", 50, 5, 90.0, "t", limit_price=98.0)
    hl.calls.clear()
    for _ in range(20):
        B.live_reconcile()
    assert hl.calls.count("frontendOpenOrders") <= 1


def test_entree_limite_remplie_enregistree_avec_glissement(env):
    hl, ex = env
    B.place_trade("BTC", "long", 50, 5, 90.0, "t", limit_price=98.0)
    lim = [o for o in hl.orders if o["orderType"] == "Limit"][0]
    hl.orders.remove(lim)
    hl.add_fill("BTC", True, float(lim["sz"]), 98.0, lim["oid"])
    B.live_reconcile()
    t = row()
    assert t["status"] == "open" and t["intended_px"] == 98.0 and t["slippage_bps"] == 0.0


def test_ordre_limite_rempli_avant_que_la_position_apparaisse(env):
    """Bug du 09/10 (SOL) : l'ordre a quitté le carnet mais la position n'était pas encore visible."""
    hl, ex = env
    B.place_trade("BTC", "long", 50, 5, 90.0, "t", limit_price=98.0)
    lim = [o for o in hl.orders if o["orderType"] == "Limit"][0]
    hl.orders.remove(lim)
    hl.add_fill("BTC", True, float(lim["sz"]), 98.0, lim["oid"])
    pos = hl.positions.pop("BTC")              # l'état du compte est en retard d'un instant
    B.live_reconcile()
    assert "BTC" in B.meta_get("live_pending", {})   # pas de « disparu sans remplissage »
    hl.positions["BTC"] = pos
    B.live_reconcile()
    assert row()["status"] == "open" and B.meta_get("live_pending", {}) == {}


# ------------------------------------------------------------------ coupe-circuit
def test_coupe_circuit_trop_d_ouvertures(env):
    hl, ex = env
    for coin in ("BTC", "ETH", "SOL"):
        B.journal("open", f"long {coin} x")
    for _ in range(3):
        B.journal("order", "limite x")
    r = j(B.place_trade("BTC", "long", 50, 5, 95.0, "t"))
    assert "rejected" in r and B.frozen()
    r2 = j(B.place_trade("ETH", "long", 50, 5, 45.0, "t"))
    assert "Coupe-circuit" in r2["rejected"]


def test_coupe_circuit_chute_d_equity_et_expiration(env):
    hl, ex = env
    B.watch_equity(100.0)
    B.watch_equity(90.0)
    assert not B.frozen()
    B.watch_equity(84.0)
    assert B.frozen()
    f = B.meta_get("freeze")
    f["until"] = time.time() - 1
    B.meta_set("freeze", f)
    assert not B.frozen()


# ------------------------------------------------------------------ trajectoire
def _born(days_ago, eq=80.0):
    b = time.time() - days_ago * 86400
    B.meta_set("born", b)
    with B.db() as c:
        c.execute("INSERT INTO equity VALUES(?,?,?)",
                  (datetime.fromtimestamp(b, timezone.utc).isoformat(timespec="seconds"), B.GEN, eq))
    return b


def test_trajectoire_compte_les_points_de_controle(env, monkeypatch):
    monkeypatch.setattr(B, "TRAJ_RULE", True)
    b = _born(3.5)
    t = B.traj()
    n, dl = 0, B.first_deadline(b)
    while dl <= time.time():
        n, dl = n + 1, B.next_paris_midnight(dl + 60)
    assert t["n"] == n and t["base"] == 80.0 and t["next_deadline"] == dl
    st = B.traj_status(80 * 1.01 ** (n + 2), t)
    assert st["days_ahead"] == pytest.approx(2.0, abs=0.01)
    assert st["death_line_equity"] == pytest.approx(80 * 1.01 ** n * 0.65, abs=1e-3)


def test_trajectoire_verdict_vie_et_mort(env, monkeypatch):
    monkeypatch.setattr(B, "TRAJ_RULE", True)
    _born(3.5)
    t = B.traj()
    t["next_deadline"] = time.time() - 1
    B.meta_set("traj", t)
    assert B.daily_verdict(80.0) is None              # en retard mais au-dessus de la ligne : vivant
    assert B.meta_get("traj")["n"] == t["n"] + 1
    t = B.meta_get("traj")
    t["next_deadline"] = time.time() - 1
    B.meta_set("traj", t)
    cause = B.daily_verdict(40.0)
    assert cause and "ligne de mort" in cause


def test_trajectoire_depot_ajuste_la_base(env, monkeypatch):
    hl, ex = env
    monkeypatch.setattr(B, "TRAJ_RULE", True)
    _born(2.5)
    t = B.traj()
    hl.ledger.append({"time": t["cursor_ms"] + 10, "delta": {"type": "send", "user": "0xabcd",
                      "destination": B.SUB, "token": "USDC", "amount": "20", "usdcValue": "20"}})
    hl.ledger.append({"time": t["cursor_ms"] + 20, "delta": {"type": "send", "user": "0xabcd",
                      "destination": B.SUB, "token": "HYPE", "amount": "1", "usdcValue": "30"}})
    B.track_transfers()
    t2 = B.meta_get("traj")
    assert t2["base"] == pytest.approx(80 + 20 / 1.01 ** t["n"])


def test_regle_actuelle_inchangee_si_trajectoire_off(env, monkeypatch):
    monkeypatch.setattr(B, "TRAJ_RULE", False)
    _born(1.5, 80.0)
    B.meta_set("day_ref", {"equity": 80.0, "set_at": time.time() - 86400, "deadline": time.time() - 1})
    assert "objectif quotidien manqué" in B.daily_verdict(80.5)


# ------------------------------------------------------------------ account / history / jev
def test_account_garde_tous_les_anciens_champs(env, monkeypatch):
    hl, ex = env
    _born(1.0)
    open_long(hl, ex)
    old = {"equity", "positions", "alive", "generation", "mode", "death_threshold_usd", "daily_rule",
           "daily_reference_equity", "daily_target_equity", "daily_deadline_paris", "daily_hours_left",
           "pending_orders", "guardrails"}
    a = j(B.account())
    assert old <= set(a)
    assert a["positions"][0]["stop_loss_on_exchange"] == [95.0]
    assert a["recent_actions"][0]["kind"] == "open"
    assert a["circuit_breaker"] == {"frozen": False}
    assert "trajectory" not in a
    monkeypatch.setattr(B, "TRAJ_RULE", True)
    a = j(B.account())
    assert old <= set(a) and "days_ahead" in a["trajectory"]


def test_jev_journalise_et_garde_le_format(env, monkeypatch):
    class R:
        text = json.dumps({"answers": {"reveiller": {"choice": "oui", "probabilities": {"oui": 0.7, "non": 0.3}}}})

        def json(self):
            return json.loads(self.text)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(B.requests, "post", lambda *a, **k: R())
    r = j(B.jev_decide({"x": 1}, {"reveiller": {"type": "choice"}}))
    assert r["answers"]["reveiller"]["probabilities"]["oui"] == 0.7 and r["jev_id"] == 1
    assert j(B.jev_outcome(1, "non"))["ok"]
    sc = j(B.scorecard())
    assert sc["jev"]["with_outcome"] == 1 and sc["jev"]["brier"] == pytest.approx(0.7 ** 2 + 0.7 ** 2)


# ------------------------------------------------------------------ journal réel (données réelles)
def _load_real_db(real):
    with B.db() as c:
        cols = [r["name"] for r in c.execute("PRAGMA table_info(trades)")]
        for t in real["trades"]:
            keys = [k for k in t if k in cols]
            c.execute(f"INSERT INTO trades({','.join(keys)}) VALUES({','.join('?' * len(keys))})",
                      [t[k] for k in keys])
        for r in real["journal"]:
            c.execute("INSERT INTO journal(id,gen,ts,kind,text) VALUES(?,?,?,?,?)",
                      (r["id"], r["gen"], r["ts"], r["kind"], r["text"]))
        # simule une base d'avant le 11/10 : nouvelles colonnes vides
        c.execute("UPDATE trades SET " + ",".join(f"{k}=NULL" for k in B.TRADE_COLUMNS))


def test_journal_reel_egal_a_hyperliquid_au_centime(env):
    hl, ex = env
    real = load_real()
    hl.fills, hl.funding = real["fills"], real["funding"]
    _load_real_db(real)
    B.init_db()  # migration : stop initial relu dans le journal, taille initiale
    before = {r["id"]: (r["pnl"], r["exit"], r["fees"], r["close_reason"]) for r in
              B.db().execute("SELECT * FROM trades")}
    n = B.settle_trades()
    rows = {r["id"]: r for r in B.db().execute("SELECT * FROM trades")}
    closed = [r for r in rows.values() if r["status"] == "closed"]
    assert n == len(closed)
    # les colonnes lues par le monitor de post-mortem ne bougent pas
    assert all(before[i] == (r["pnl"], r["exit"], r["fees"], r["close_reason"]) for i, r in rows.items())
    # le net de toutes les vies de position fermées = somme des pnl_net
    lives = [l for l in B.lifecycles(real["fills"]) if l["close_ms"]]
    net_hl = sum(float(f["closedPnl"]) - float(f["fee"]) for l in lives for f in l["fills"])
    fund = sum(float(x["delta"]["usdc"]) for x in real["funding"]
               if any(l["coin"] == x["delta"]["coin"] and l["open_ms"] <= x["time"] <= l["close_ms"] + 60000 for l in lives))
    orphans = B.meta_get("unrecorded_lives", [])
    assert [o["coin"] for o in orphans] == ["SOL"]       # la position SOL du 09/10 jamais enregistrée
    assert sum(r["pnl_net"] for r in closed) + sum(o["net"] for o in orphans) == pytest.approx(net_hl + fund, abs=0.005)
    assert not [l for l in lives if l["coin"] == "NEAR" and len(l["fills"]) == 1]  # plus de vie coupée en deux
    # trades vérifiés à la main le 11/10
    assert rows[17]["pnl_net"] == pytest.approx(-1.886, abs=0.01)
    assert rows[19]["pnl_net"] == pytest.approx(17.82, abs=0.01)
    assert rows[20]["pnl_net"] == pytest.approx(0.193, abs=0.01)
    assert rows[22]["pnl_net"] == pytest.approx(-0.151, abs=0.01)
    assert all(r["initial_stop"] for r in closed)


def test_miroir_sur_donnees_reelles(env):
    hl, ex = env
    real = load_real()
    hl.fills, hl.funding = real["fills"], real["funding"]
    _load_real_db(real)
    B.init_db()
    B.settle_trades()
    B.meta_set("born", float(real["meta"]["born"]))
    sc = j(B.scorecard())
    assert sc["overall"]["trades"] > 0 and sc["money"]["trades_not_yet_settled"] == 0
    assert sc["overall"]["risk_per_trade_pct_suggested"] is not None
    assert "non_etiquete" in sc["by_setup"]


def test_vies_de_position_reduction_partielle_et_retournement():
    f = lambda t, s, side, sz: {"coin": "X", "time": t, "tid": t, "startPosition": str(s), "side": side,
                                "sz": str(sz), "closedPnl": "0", "fee": "0"}
    lives = B.lifecycles([f(1, 0, "B", 2), f(2, 2, "A", 1), f(3, 1, "A", 1), f(4, 0, "A", 3), f(5, -3, "B", 4)])
    assert [(l["open_ms"], l["close_ms"], len(l["fills"])) for l in lives] == [(1, 3, 3), (4, 5, 2)]


# ------------------------------------------------------------------ enregistreur
def test_enregistreur_une_minute(env):
    hl, ex = env
    B.init_market_db()
    B.record_market()
    with B.mdb() as c:
        assert c.execute("SELECT COUNT(*) FROM ctx").fetchone()[0] == len(hl.mids)
        assert c.execute("SELECT COUNT(*) FROM l2").fetchone()[0] == len(hl.mids)
    assert B._flow_coins["v"]


def test_agregation_du_flux():
    a = B.FlowAgg()
    a.add({"tid": 1, "time": 60_000, "px": "100", "sz": "600", "side": "B", "coin": "BTC"})
    a.add({"tid": 1, "time": 60_000, "px": "100", "sz": "600", "side": "B", "coin": "BTC"})  # doublon
    a.add({"tid": 2, "time": 61_000, "px": "100", "sz": "1", "side": "A", "coin": "BTC"})
    a.add({"tid": 3, "time": 125_000, "px": "100", "sz": "1", "side": "A", "coin": "BTC"})
    assert a.flush(120) == [(60, "BTC", 60000.0, 100.0, 2, 1)]
    assert len(a.buckets) == 1


def test_export_des_donnees_de_marche(env):
    hl, ex = env
    B.init_market_db()
    B.record_market()
    r = j(B.export_market_data("ctx", "BTC", 1))
    assert r["rows"] == 1 and r["written"].endswith("ctx_BTC_1h.csv")
    import csv
    rows = list(csv.DictReader(open(r["written"].replace("/opt/data/workspace", "/workspace"))))
    assert rows[0]["coin"] == "BTC" and float(rows[0]["mid"]) == 100.0
    assert "error" in j(B.export_market_data("drop table", "", 1))
    assert j(B.export_market_data("flow", "BTC", 1))["rows"] == 0


def test_libelle_du_miroir_pour_le_total(env):
    s = B._group_stats([(1.0, -0.5, 0.1)] * 25, "l'ensemble de tes trades")
    assert "l'ensemble de tes trades" in s["sizing"] and "ce type" not in s["sizing"]


def test_noms_de_coin_hostiles_refuses(env):
    for bad in ("../../etc/x", "BTC/../x", "a b", "", "X" * 21):
        if bad:
            assert "error" in j(B.export_market_data("ctx", bad, 1))
        assert "error" in j(B.export_candles(bad or "..", "1h", 10))
    assert "error" in j(B.export_candles("BTC", "../1h", 10))


def test_point_de_controle_note_le_rythme_du_jour(env, monkeypatch):
    monkeypatch.setattr(B, "TRAJ_RULE", True)
    _born(3.5)
    B.meta_set("day_ref", {"equity": 80.0, "set_at": time.time(), "deadline": time.time()})
    t = B.traj()
    t["next_deadline"] = time.time() - 1
    B.meta_set("traj", t)
    assert B.daily_verdict(81.0) is None
    txt = B.db().execute("SELECT text FROM journal WHERE kind='daily' ORDER BY id DESC LIMIT 1").fetchone()["text"]
    assert txt.startswith("Point de contrôle") and "rythme du jour tenu : 81.00 $ >= 80.80 $" in txt
    assert float(txt.split(">=", 1)[1].split("$")[0]) == 80.8   # format lu par les succès du dashboard


def test_history_compact_sur_vraies_theses(env):
    hl, ex = env
    real = load_real()
    _load_real_db(real)
    B.init_db()
    out = B.history(30)
    assert len(out) < 40_000, len(out)          # Hermes range en fichier au-delà de 50 000 caractères
    h = j(out)
    full = json.load(open(h["full_details_file"].replace("/opt/data/workspace", "/workspace")))
    assert len(full["trades"]) == len(h["trades"]) and len(full["trades"][0]["thesis"]) >= len(h["trades"][0]["thesis"])
    assert set(h["trades"][0]) >= {"id", "coin", "side", "entry", "exit", "pnl", "close_reason", "status", "pnl_net"}


def test_these_coupee_garde_ses_etiquettes():
    long = "x" * 3000 + " [setup:momentum] [gestion:serrée] shot de survie [src:cycle]"
    cut = B._cut_thesis(long, 250)
    assert len(cut) < 400
    for tag in ("[setup:momentum]", "[gestion:serrée]", "[src:cycle]", "[survie]"):
        assert tag in cut
    assert B._cut_thesis("court [trail]", 250) == "court [trail]"


def test_lineage_compacte(env):
    with B.db() as c:
        for i in range(71):
            c.execute("INSERT INTO lessons(gen,ts,lesson,evidence) VALUES(2,'t',?,?)", ("L" * 520, "E" * 950))
    out = B.lineage()
    assert len(out) < 50_000, len(out)
    full = json.load(open(j(out)["lessons_full_file"].replace("/opt/data/workspace", "/workspace")))
    assert len(full) == 71 and len(full[0]["evidence"]) == 950


# ------------------------------------------------------------------ moteur de risque
def _closed_setup(n, net, setup="momentum"):
    with B.db() as c:
        for i in range(n):
            c.execute("INSERT INTO trades(gen,coin,side,size,entry,leverage,stop_loss,take_profit,opened_at,thesis,"
                      "closed_at,exit,pnl,fees,status,initial_stop,initial_size,pnl_net,fees_total) "
                      "VALUES(2,'ETH','long',1,100,5,99,0,'2026-10-01T00:00:00+00:00',?, '2026-10-01T01:00:00+00:00',"
                      "100,?,0,'closed',99,1,?,0.05)", (f"[setup:{setup}] [src:cycle]", net(i), net(i)))


def T(setup="momentum", src="cycle"):
    return f"[setup:{setup}] [src:{src}] thèse"


def test_moteur_etiquettes_obligatoires(env, monkeypatch):
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    r = j(B.place_trade("BTC", "long", 20, 5, 99.0, "sans étiquette"))
    assert "étiquettes" in r["rejected"] and not env[0].positions


def test_moteur_exploration_limite_le_risque(env, monkeypatch):
    hl, ex = env
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    r = j(B.place_trade("BTC", "long", 50, 5, 98.0, T()))     # risque 1 $ = 1 % > 0,5 %
    assert "0.50 % autorisés" in r["rejected"] and "taille max 25.00 $" in r["rejected"]
    r = j(B.place_trade("BTC", "long", 25, 5, 98.0, T()))     # risque 0,5 $ = 0,5 %
    assert r.get("filled")
    assert B.trades_today() == 1


def test_moteur_refuse_un_setup_sans_avantage(env, monkeypatch):
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    _closed_setup(25, lambda i: 1.0 if i % 4 == 0 else -1.0)   # 25 % gagnants à 1R : espérance négative
    r = j(B.place_trade("BTC", "long", 20, 5, 99.0, T()))
    assert "pas d'avantage mesuré" in r["rejected"]


def test_moteur_setup_prouve_autorise_plus(env, monkeypatch):
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    _closed_setup(30, lambda i: 2.0 if i % 2 == 0 else -1.0)   # 50 % à +2R / -1R : Kelly 0,25
    pol = B.setup_policy("momentum")
    assert pol["status"] == "prouvé" and 0.5 < pol["max_risk_pct"] <= 3.0
    r = j(B.place_trade("BTC", "long", 100, 5, 98.0, T()))    # risque 2 % < plafond (demi-Kelly réduit ≈ 7,5 % → 3 %)
    assert r.get("filled"), r


def test_moteur_limite_quotidienne(env, monkeypatch):
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    B.meta_set("day_count", {"day": B._paris_day(), "n": B.MAX_TRADES_PER_DAY})
    r = j(B.place_trade("BTC", "long", 20, 5, 99.0, T()))
    assert "nouveaux trades déjà pris" in r["rejected"]
    B.meta_set("day_count", {"day": "2026-01-01", "n": 99})     # un autre jour : compteur remis à zéro
    assert B.trades_today() == 0


def test_moteur_gain_vise_couvre_les_frais(env, monkeypatch):
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    r = j(B.place_trade("BTC", "long", 20, 5, 99.0, T(), take_profit=100.2))   # +0,2 % < 4 × 0,09 %
    assert "perdant d'avance" in r["rejected"]
    r = j(B.place_trade("BTC", "long", 20, 5, 99.0, T(), take_profit=101.0))
    assert r.get("filled"), r


def test_moteur_risque_total(env, monkeypatch):
    hl, ex = env
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    monkeypatch.setattr(B, "EXPLORE_RISK", 0.08)
    assert j(B.place_trade("BTC", "long", 400, 20, 98.0, T()))["filled"]       # 8 $ de risque
    r = j(B.place_trade("ETH", "long", 150, 20, 49.0, T("autre")))             # +3 $ → 11 % > 10 %
    assert "risque total ouvert" in r["rejected"]


def test_moteur_ne_bloque_jamais_fermer_ni_les_stops(env, monkeypatch):
    hl, ex = env
    open_long(hl, ex)
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    B.meta_set("day_count", {"day": B._paris_day(), "n": 99})
    assert j(B.set_stops("BTC", 97.0, 112.0))["ok"]
    assert j(B.close_position("BTC", "x"))["closed"]


def test_account_expose_le_moteur(env, monkeypatch):
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    a = j(B.account())
    assert a["risk_engine"]["max_trades_per_day"] == B.MAX_TRADES_PER_DAY and "rules" in a["risk_engine"]


def test_moteur_refuse_un_stop_dans_le_bruit(env, monkeypatch):
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    assert abs(B.atr_1h("BTC") - 1.0) < 1e-6
    r = j(B.place_trade("BTC", "long", 20, 5, 99.5, T()))          # 0,5 ATR < 0,75
    assert "dans le bruit" in r["rejected"]
    assert j(B.place_trade("BTC", "long", 20, 5, 99.0, T())).get("filled")   # 1 ATR


def test_regime_et_panique(env, monkeypatch):
    rg = B.regime()
    assert rg["label"] in ("range", "tendance haussière", "tendance baissière", "panique") and rg["risk_multiplier"] in (0.5, 1.0)
    monkeypatch.setattr(B, "RISK_ENGINE", True)
    monkeypatch.setattr(B, "regime", lambda: {"label": "panique", "risk_multiplier": 0.5})
    r = j(B.place_trade("BTC", "long", 25, 5, 98.0, T()))           # 0,5 % de risque, plafond 0,25 % en panique
    assert "panique" in r["rejected"] and "taille max 12.50 $" in r["rejected"]
    assert j(B.account())["market_regime"]["label"] == "panique"


def test_temoin_sans_ia(env, monkeypatch):
    hl, ex = env
    assert B.witness_pick()[0] == []                      # prix constants : aucune hausse ≥ 5 %
    monkeypatch.setattr(B, "witness_pick", lambda: (["BTC", "ETH"], {}))
    r1 = B.witness_step(force=True)
    assert r1["picks"] == ["BTC", "ETH"] and abs(r1["equity"] - 100 * (1 - B.WITNESS_COST)) < 1e-9
    assert B.witness_step(force=True) is None              # une seule fois par jour
    with B.db() as c:
        c.execute("UPDATE witness SET day='2000-01-01', ts=?", (time.time() - 3600,))
    set_price(hl, "BTC", 110.0)
    B._meta_cache["t"] = 0
    r2 = B.witness_step(force=True)
    expected = (0.10 - 1e-5 * 1 + 0.0 - 1e-5 * 1) / 2      # BTC +10 %, ETH plat, funding 0,001 %/h pendant 1 h
    assert abs(r2["day_return"] - expected) < 1e-4 and abs(r2["equity"] - r1["equity"] * (1 + r2["day_return"])) < 1e-6
    sc = j(B.scorecard())
    assert sc["witness_no_ai"]["witness"]["today_picks"] == ["BTC", "ETH"] and "rule" in sc["witness_no_ai"]["witness"]


def test_temoin_tendance(env, monkeypatch):
    hl, ex = env
    assert B.trend_pick()[0] == []                    # prix constants : pas au-dessus de la moyenne 50 j
    real = hl.info

    def rising(p, timeout=15):
        if p["type"] == "candleSnapshot" and p["req"]["coin"] == "BTC":
            out = real(p)
            for i, c in enumerate(out):
                c["c"] = str(100 + i)                 # tendance haussière : dernière clôture > moyenne 50 j
            return out
        return real(p)
    monkeypatch.setattr(B, "info", rising)
    assert B.trend_pick()[0] == ["BTC"]
    r = B.witness_step(force=True, table="witness_trend", picker=B.trend_pick)
    assert r["picks"] == ["BTC"]
    B.init_witness_db("witness")
    with B.db() as c:
        assert c.execute("SELECT COUNT(*) FROM witness").fetchone()[0] == 0    # tables séparées
        assert c.execute("SELECT COUNT(*) FROM witness_trend").fetchone()[0] == 1


# ------------------------------------------------------------------ news : CoinMarketCap (pas de RSS : JSON de la page)
def cmc_page():
    return (Path(__file__).parent / "fixtures" / "cmc_news_2026-10-13.html").read_text(encoding="utf-8")


class FakeResp:
    def __init__(self, text, code=200):
        self.text, self.status_code, self.content = text, code, text.encode()


def test_cmc_page_sauvegardee_donne_20_articles():
    items = B.parse_cmc_news(cmc_page())
    assert len(items) == 20
    assert all(i["title"] and i["link"].startswith("https://") and isinstance(i["ts"], int) and i["via"] for i in items)


@pytest.mark.parametrize("bad", [
    "", "<html>rien</html>",
    '<script id="__NEXT_DATA__" type="application/json">{oups</script>',
    '<script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>',
    '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"newsFeed":5}}}</script>',
    '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"newsFeed":[{"meta":{"title":"x","sourceUrl":"https://a","releasedAt":"hier"}}]}}}</script>'])
def test_cmc_page_changee_liste_vide_sans_exception(bad):
    assert B.parse_cmc_news(bad) == []


def test_news_inclut_cmc_meme_si_les_rss_sont_en_panne_et_met_en_cache(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if "coinmarketcap.com" in url:
            return FakeResp(cmc_page(), fake_get.code)
        raise OSError("hors ligne")
    fake_get.code = 200
    monkeypatch.setattr(B.requests, "get", fake_get)
    B._cmc.update(at=0.0, items=[])
    r = j(B.news(limit=50))
    assert r["untrusted_external_content"] is True
    items = r["items"]
    assert len(items) == 15 and all(i["src"] == "coinmarketcap" and i["via"] for i in items)
    assert set(items[0]) == {"src", "via", "title", "published", "link"}
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d UTC", items[0]["published"])
    assert [i["published"] for i in items] == sorted((i["published"] for i in items), reverse=True)
    B.news(); B.news()
    assert sum("coinmarketcap" in u for u in calls) == 1            # cache de 10 min
    # cache expiré + CoinMarketCap répond 403 : on garde la dernière liste connue
    B._cmc["at"] = 0.0
    fake_get.code = 403
    assert len(j(B.news(limit=50))["items"]) == 15



# ------------------------------------------------------------------ simulation sans compte (PAPER_CAPITAL)
def test_paper_capital_demarre_sans_lire_le_compte(env, monkeypatch):
    hl, _ = env
    monkeypatch.setattr(B, "MODE", "paper")
    monkeypatch.setattr(B, "PAPER_CAPITAL", "250")
    hl.calls.clear()
    s = B.paper_state()
    assert s["cash"] == 250.0 and s["start"] == 250.0
    assert "clearinghouseState" not in hl.calls and "spotClearinghouseState" not in hl.calls
    assert B.snapshot()["equity"] == 250.0
