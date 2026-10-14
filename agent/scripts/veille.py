"""Socle commun des scripts de veille de RedRock (sentinelle, post-mortem, docteur).

Hermes lance chaque script à chaque tick (« monitor mode ») et ne réveille l'IA que si sa sortie change, octet pour
octet : la sortie doit donc être STABLE (même état = même texte, aucune heure du tick). Chaque script garde son petit
état dans un fichier JSON ($HERMES_HOME/veille/<nom>.json). Si le broker ne répond pas, le script réimprime sa
dernière sortie (pas de réveil pour une panne passagère) ; c'est le docteur qui signale une panne qui dure.
"""
import calendar
import copy
import json
import os
import sys
import time
import unicodedata
from datetime import datetime, timezone

HOME = os.environ.get("HERMES_HOME") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.environ.get("REDROCK_VEILLE_DIR") or os.path.join(HOME, "veille")


def now():
    """Heure courante (REDROCK_VEILLE_NOW la fixe, pour les tests)."""
    fixed = os.environ.get("REDROCK_VEILLE_NOW")
    return float(fixed) if fixed else time.time()


def utc(ts):
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts))


def parse_ts(text):
    """Horodatage d'un texte ISO (« 2026-10-14T13:05:00+00:00 », UTC si sans fuseau) ou « 2026-10-14 13:05 UTC »."""
    s = str(text or "").strip()
    try:
        return float(calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M UTC")))
    except ValueError:
        pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return None


def num(x):
    """Nombre court et stable (6 chiffres significatifs, sans « .0 »)."""
    try:
        return f"{float(x):.6g}"
    except (TypeError, ValueError):
        return str(x)


def clean(text, n=160):
    """Texte externe (titres d'actualité…) sur une ligne, sans caractères de contrôle ni invisibles, borné."""
    text = "".join(" " if unicodedata.category(c)[0] in "CZ" else c for c in str(text or ""))
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def load(name):
    try:
        with open(os.path.join(STATE_DIR, name + ".json"), encoding="utf-8") as fh:
            st = json.load(fh)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save(name, st):
    os.makedirs(STATE_DIR, exist_ok=True)
    path = os.path.join(STATE_DIR, name + ".json")
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


def run(name, build, fallback):
    """Lance build(état) -> texte, l'imprime et enregistre l'état. En cas d'erreur (broker injoignable…) : la
    dernière sortie connue (ou fallback), l'erreur notée dans l'état pour le docteur, et toujours le code 0
    (un code d'erreur ferait livrer une alerte à chaque tick)."""
    st = load(name)
    t = now()
    try:
        work = copy.deepcopy(st)   # l'état n'est remplacé que si tout le passage a réussi
        out = build(work)
        st = work
        st["_ok_at"] = t
        st["_last_output"] = out
        st.pop("_error", None)
    except Exception as e:   # noqa: BLE001 — une veille ne doit jamais planter
        out = st.get("_last_output") or fallback
        err = st.get("_error") or {"since": t}
        err.update(at=t, msg=f"{type(e).__name__}: {e}"[:300])
        st["_error"] = err
    st["_run_at"] = t
    try:
        save(name, st)
    except OSError as e:
        print(f"veille {name} : état non enregistré ({e})", file=sys.stderr)
    sys.stdout.buffer.write((out.rstrip("\n") + "\n").encode("utf-8"))   # octets fixes : UTF-8, « \n » partout
    sys.stdout.flush()
    return 0
