#!/usr/bin/env python3
"""Docteur de RedRock : source de la tâche « docteur » (Hermes, toutes les 5 min, sans IA).

Contrôle la santé du système et n'imprime un problème que s'il est vu à DEUX contrôles de suite (une panne passagère
ne réveille personne) :
  - le broker ne répond pas ;
  - une position sans stop-loss (sur l'exchange en argent réel) ;
  - le coupe-circuit du broker est actif ;
  - le broker n'enregistre plus son equity (données figées) ;
  - une tâche planifiée a échoué au moins deux fois de suite (cron/jobs.json de Hermes) ;
  - une veille (sentinelle, post-mortem) ne tourne plus ou ne joint plus le broker.
Sain : une seule ligne fixe. La sortie change quand un problème s'installe (réveil) ou disparaît.
"""
import json
import os
import sys

sys.dont_write_bytecode = True   # rien à écrire dans data/hermes/scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veille  # noqa: E402
from broker_call import Session  # noqa: E402

NAME = "docteur"
TITLE = "Docteur RedRock"
HEALTHY = f"{TITLE} : aucun problème persistant."
EQUITY_STALE = 20 * 60      # le broker enregistre son equity toutes les 5 min
VEILLE_STALE = 15 * 60
WATCHED = {"sentinelle_monitor.py": "sentinelle", "postmortem_monitor.py": "postmortem"}


def jobs_file():
    return os.path.join(veille.HOME, "cron", "jobs.json")


def checks(t):
    """{clé stable: description} des problèmes vus maintenant."""
    found = {}
    try:
        with Session(timeout=30) as s:
            acc = s.call_json("account")
            if acc.get("alive", True) is not False:
                for p in acc.get("positions") or []:
                    coin, side = p.get("coin"), str(p.get("side") or "").upper()
                    if "stop_loss_on_exchange" in p:
                        if not p.get("stop_loss_on_exchange"):
                            found[f"stop:{coin}"] = f"position {coin} {side} sans stop-loss sur l'exchange"
                    elif not p.get("stop_loss"):
                        found[f"stop:{coin}"] = f"position {coin} {side} sans stop-loss"
                cb = acc.get("circuit_breaker") or {}
                if cb.get("frozen"):
                    found["coupe-circuit"] = (f"coupe-circuit actif : nouvelles ouvertures gelées jusqu'à {cb.get('until_paris')} "
                                              f"(heure de Paris) ; raison : {veille.clean(cb.get('reason'), 160)}")
                eq = s.call_json("history", {"limit": 1}).get("equity_recent") or []
                last = veille.parse_ts(eq[-1].get("ts")) if eq and isinstance(eq[-1], dict) else None
                if last is None or t - last > EQUITY_STALE:
                    found["donnees"] = ("le broker n'enregistre plus son equity depuis plus de 20 min (dernier point : "
                                        f"{veille.utc(last) if last else 'aucun'}) : données du marché ou boucle de garde bloquées ?")
    except Exception as e:   # noqa: BLE001
        found["broker"] = f"le broker ne répond pas normalement ({type(e).__name__})"
    try:
        with open(jobs_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        jobs = data.get("jobs") if isinstance(data, dict) else data
    except (OSError, ValueError):
        jobs = []
    for j in jobs if isinstance(jobs, list) else []:
        if not isinstance(j, dict) or j.get("enabled") is False or j.get("state") in ("paused", "completed"):
            continue
        name = veille.clean(j.get("name") or j.get("id"), 60)
        try:
            streak = int(j.get("failure_streak") or 0)
        except (TypeError, ValueError):
            streak = 0
        if streak >= 2:
            found[f"tache:{name}"] = f"la tâche « {name} » a échoué au moins deux fois de suite (voir hermes cron list)"
        watched = WATCHED.get(os.path.basename(str(j.get("monitor_script") or "")))
        if watched and "broker" not in found:
            st = veille.load(watched)
            run_at, ok_at = st.get("_run_at"), st.get("_ok_at")
            if run_at and t - run_at > VEILLE_STALE:
                found[f"veille:{watched}"] = f"la veille de la tâche « {name} » ne tourne plus depuis plus de 15 min"
            elif run_at and (ok_at is None or t - ok_at > VEILLE_STALE):
                found[f"veille:{watched}"] = f"la veille de la tâche « {name} » ne joint plus le broker depuis plus de 15 min"
    return found


def build(st):
    found = checks(veille.now())
    prev = set(st.get("prev") or [])
    st["prev"] = sorted(found)
    lasting = {k: v for k, v in found.items() if k in prev}
    if not lasting:
        return HEALTHY
    return (f"{TITLE} : problème(s) vu(s) à deux contrôles de suite (5 min d'écart)\n"
            + "\n".join(f"• [{k}] {v}" for k, v in sorted(lasting.items())))


if __name__ == "__main__":
    sys.exit(veille.run(NAME, build, HEALTHY))
