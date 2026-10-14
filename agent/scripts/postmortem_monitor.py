#!/usr/bin/env python3
"""Post-mortem de RedRock : source de la tâche « post-mortem » (Hermes, chaque minute, sans IA).

Imprime les derniers trades FERMÉS de la génération (outil history du broker), avec seulement les champs qui ne
bougent plus après la clôture (id, coin, sens, entrée, sortie, raison, heure). Un nouveau trade fermé change la sortie
et réveille l'agent pour son post-mortem ; le résultat réel (pnl_net), calculé dans la minute qui suit, n'est
volontairement pas affiché (sinon un deuxième réveil pour le même trade).
"""
import os
import sys

sys.dont_write_bytecode = True   # rien à écrire dans data/hermes/scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veille  # noqa: E402
from broker_call import Session  # noqa: E402

NAME = "postmortem"
TITLE = "Post-mortem RedRock"
EMPTY = f"{TITLE} : aucun trade fermé pour l'instant."
SHOW = 10


def build(st):
    with Session(timeout=30) as s:
        h = s.call_json("history", {"limit": 3 * SHOW})
    closed = [x for x in h.get("trades") or [] if isinstance(x, dict) and x.get("status") == "closed"]
    closed.sort(key=lambda x: int(x.get("id") or 0), reverse=True)
    if not closed:
        return EMPTY
    lines = [f"• #{x.get('id')} {x.get('coin')} {str(x.get('side') or '').upper()} · entrée {veille.num(x.get('entry'))}"
             f" · sortie {veille.num(x.get('exit'))} · {veille.clean(x.get('close_reason') or '?', 80)} · fermé {x.get('closed_at')}"
             for x in closed[:SHOW]]
    return f"{TITLE} : derniers trades fermés, le plus récent en premier\n" + "\n".join(lines)


if __name__ == "__main__":
    sys.exit(veille.run(NAME, build, EMPTY))
