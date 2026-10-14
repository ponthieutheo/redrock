"""Données 100 % inventées pour les captures et les vidéos de RedRock (aucune donnée réelle de l'agent).

Tout part d'une horloge fixe (VNOW) : l'app tourne en temps virtuel (inject.js), les heures affichées
sont donc toujours les mêmes d'un rendu à l'autre. Les prix, trades, journaux, actus et messages sont
écrits à la main ou tirés d'un générateur à graine fixe : deux rendus donnent exactement les mêmes images.

Scénarios (/__scenario/<nom> sur le serveur) :
  vie        il trade : 3 positions (LONG BTC, SHORT ETH, LONG SOL), journée positive
  calme      même capital, plus de position : il dort
  fete       objectif du jour atteint : il danse, confettis
  reflexion  il réfléchit (analyse technique pendant son cycle)
  danger     capital proche de la ligne de mort : il panique
  neuf       installation toute fraîche (génération 1, 100 $), premier cycle : il lit son compte
  mort       la génération 3 vient de mourir (tombe)
  naissance  la génération 4 vient de naître (100 $, aucune position)
"""
import math
import random
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
VNOW = datetime(2026, 10, 14, 12, 20, 0, tzinfo=UTC)        # 14 h 20 à Paris : la salle est éclairée de jour
VNOW_MS = int(VNOW.timestamp() * 1000)
MIDNIGHT = datetime(2026, 10, 13, 22, 0, 0, tzinfo=UTC)      # minuit, heure de Paris
BORN = datetime(2026, 10, 10, 7, 5, 0, tzinfo=UTC)          # naissance de la génération 3


def iso(d):
    return d.astimezone(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------- marché inventé (niveaux plausibles, rien de réel)
PRICES = {"BTC": 84160.0, "ETH": 3186.4, "SOL": 182.42, "HYPE": 41.27, "XRP": 2.412, "DOGE": 0.2134, "LINK": 17.82,
          "AVAX": 26.41, "SUI": 3.874, "BNB": 598.6, "ADA": 0.7421, "TON": 5.318, "NEAR": 5.104, "AAVE": 271.3,
          "LTC": 88.9, "APT": 9.62, "ARB": 0.8123, "INJ": 21.47, "TAO": 412.5, "DOT": 6.18, "UNI": 9.84,
          "ATOM": 6.97, "FIL": 4.81, "WIF": 2.316}
CHG = {"BTC": 1.4, "ETH": -0.8, "SOL": 2.3, "HYPE": 4.6, "XRP": 0.9, "DOGE": -1.7, "LINK": 3.1, "AVAX": -2.4,
       "SUI": 6.2, "BNB": 0.4, "ADA": -0.6, "TON": 1.1, "NEAR": -3.3, "AAVE": 2.7, "LTC": -0.2, "APT": 5.4,
       "ARB": -4.1, "INJ": 8.9, "TAO": -5.6, "DOT": 0.3, "UNI": 1.9, "ATOM": -1.2, "FIL": 2.2, "WIF": 12.4}
VOL = {"BTC": 3.1e9, "ETH": 1.6e9, "SOL": 6.2e8, "HYPE": 4.4e8, "XRP": 2.1e8, "DOGE": 1.8e8, "LINK": 9.0e7,
       "AVAX": 6.1e7, "SUI": 1.5e8, "BNB": 7.0e7, "ADA": 5.2e7, "TON": 3.3e7, "NEAR": 4.1e7, "AAVE": 6.6e7,
       "LTC": 3.8e7, "APT": 4.7e7, "ARB": 3.0e7, "INJ": 5.9e7, "TAO": 8.1e7, "DOT": 2.6e7, "UNI": 2.9e7,
       "ATOM": 1.9e7, "FIL": 1.7e7, "WIF": 1.2e8}


def market():
    rows = [{"coin": c, "px": PRICES[c], "chg": CHG[c], "vol": VOL[c]} for c in PRICES]
    by = {r["coin"]: r for r in rows}
    return {"majors": [by[c] for c in ("BTC", "ETH", "SOL", "HYPE")], "list": rows,
            "up": by["WIF"], "down": by["TAO"]}


HOT = ["BTC", "ETH", "SOL", "HYPE", "SUI", "WIF", "LINK", "INJ", "APT", "AAVE"]


def candles(coin, interval="5m", n=60, start=None, end=None, salt=0):
    """Bougies inventées qui finissent au prix du marché inventé (trajectoire à graine fixe par coin)."""
    step = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}.get(interval, 300) * 1000
    end = end or VNOW_MS
    if coin == SHOW["coin"] and start and start < SHOW["close_ms"] and end > SHOW["open_ms"]:
        return {"coin": coin, "interval": interval, "candles": _show_candles(start, end, step)}
    count = n if not start else max(2, min(400, (end - start) // step))
    rnd = random.Random(f"{coin}:{interval}:{start}:{salt}")
    last = PRICES.get(coin, 10.0)
    # BTC part de son prix d'entrée (83 212) il y a 5 h : entrée en bas du graphe, SL et TP hors cadre
    trend = {"BTC": 0.00019, "ETH": -0.0006, "SOL": 0.0011, "HYPE": 0.0016}.get(coin, rnd.uniform(-0.0012, 0.0014))
    vol = {"BTC": 0.0011, "ETH": 0.0019}.get(coin, 0.0032)
    closes = [last]
    for _ in range(count):   # à rebours depuis le dernier prix
        closes.append(closes[-1] / (1 + trend + rnd.gauss(0, vol)))
    closes = closes[::-1]
    out = []
    t0 = end - step * count
    for i in range(count):
        o, c = closes[i], closes[i + 1]
        h = max(o, c) * (1 + abs(rnd.gauss(0, vol * 0.6)))
        lo = min(o, c) * (1 - abs(rnd.gauss(0, vol * 0.6)))
        out.append([t0 + i * step, round(o, 6), round(h, 6), round(lo, 6), round(c, 6)])
    return {"coin": coin, "interval": interval, "candles": out}


# Le trade montré par « Rejouer le trade » (Historique) : LINK LONG x3, entrée 17,21, SL remonté trois fois
# (17,02 → 17,21 → 17,36 → 17,52) sous chaque nouveau creux, sortie au TP 17,73 en 1 h 30. Les bougies de cette
# période suivent ces niveaux (jamais un SL touché, le TP touché à la sortie), le reste du graphe est libre.
SHOW = {"coin": "LINK", "open_min": 220, "close_min": 130, "entry": 17.21, "exit": 17.73, "tp": 17.73,
        "stops": [(0, 17.02), (35, 17.21), (60, 17.36), (82, 17.52)]}   # (minutes après l'ouverture, SL)
SHOW["open_ms"] = VNOW_MS - SHOW["open_min"] * 60000
SHOW["close_ms"] = VNOW_MS - SHOW["close_min"] * 60000
SHOW_PATH = [(-60, 17.08), (-40, 17.12), (-25, 17.16), (-10, 17.18), (0, 17.21), (12, 17.33), (24, 17.26), (34, 17.42),
             (47, 17.37), (59, 17.55), (69, 17.48), (81, 17.66), (90, 17.73), (100, 17.66), (115, 17.69), (140, 17.71)]


def _show_price(m):
    """Prix du trade montré à m minutes de l'ouverture : segments entre les points clés + petite houle régulière."""
    P = SHOW_PATH
    if m <= P[0][0]:
        base = P[0][1]
    elif m >= P[-1][0]:
        base = P[-1][1]
    else:
        k = next(i for i in range(len(P) - 1) if P[i][0] <= m <= P[i + 1][0])
        (a, pa), (b, pb) = P[k], P[k + 1]
        u = (m - a) / (b - a)
        base = pa + (pb - pa) * (u * u * (3 - 2 * u))
    return base + 0.012 * math.sin(m * 1.7) * math.sin(m * 0.37 + 1.1)


def _show_candles(start, end, step):
    out = []
    t = start - start % step
    rnd = random.Random(f"show:{step}")
    while t < end:
        m0, m1 = (t - SHOW["open_ms"]) / 60000, (t + step - SHOW["open_ms"]) / 60000
        o, c = _show_price(m0), _show_price(m1)
        h = max(o, c) + abs(rnd.gauss(0, 0.006))
        lo = min(o, c) - abs(rnd.gauss(0, 0.006))
        close_m = SHOW["open_min"] - SHOW["close_min"]
        if m1 <= close_m:   # pendant le trade : le TP n'est touché qu'à la sortie, aucun SL n'est touché
            h = min(h, SHOW["tp"] - 0.004)
            sl = max(lv for mm, lv in SHOW["stops"] if mm <= max(0.0, m0)) if m0 >= 0 else None
            if sl is not None:
                lo = max(lo, sl + 0.02)
        if m0 < close_m <= m1:
            h = SHOW["tp"]
        out.append([int(t), round(o, 4), round(max(h, o, c), 4), round(min(lo, o, c), 4), round(c, 4)])
        t += step
    return out


_rand_i = [0]


def random_candles():
    coin = HOT[_rand_i[0] % len(HOT)]
    _rand_i[0] += 1
    return candles(coin)


# ---------------------------------------------------------------- actus inventées (chaîne d'infos de la salle)
def actus():
    t = int(VNOW.timestamp())
    src = ["Fil marchés", "Dépêche crypto", "Données Hyperliquid", "Revue DeFi"]
    flash = [
        ("Le Bitcoin repasse au-dessus de 84 000 $", "Les acheteurs défendent le support, le funding reste neutre : pas d'excès côté LONG.", "fort", ["BTC"]),
        ("Ethereum hésite sous sa résistance", "Trois rejets en quatre heures : le SHORT reste jouable tant que 3 290 tient.", "moyen", ["ETH"]),
        ("Solana : l'activité réseau au plus haut du mois", "Plus de transactions, plus de frais : un vent porteur pour SOL.", "moyen", ["SOL"]),
        ("Les stablecoins battent un nouveau record", "De l'argent frais en attente sur les plateformes, souvent bon signe.", "faible", []),
        ("Une banque centrale évoque une pause des taux", "Moins de pression sur les actifs risqués si le message se confirme.", "moyen", ["BTC", "ETH"]),
    ]
    insolite = [
        ("Un portefeuille dormant depuis 2017 se réveille", "Il déplace ses jetons d'un coup, sans les vendre pour l'instant."),
        ("WIF : +12 % en une journée", "Le volume échangé dépasse trois fois l'intérêt ouvert : très spéculatif."),
        ("Le funding le plus élevé est sur INJ", "Les LONG paient cher pour rester en position."),
    ]
    return {"ouverture": "Marché calme mais acheteur : le Bitcoin tient, les altcoins s'agitent.",
            "flash": [{"src": src[i % 4], "link": None, "ts": t - 600 - i * 1500, "titre": a, "note": b, "orig": a,
                       "jev": None, "impact": imp, "coins": coins} for i, (a, b, imp, coins) in enumerate(flash)],
            "insolite": [{"src": src[(i + 2) % 4], "link": None, "ts": t - 900 - i * 2100, "titre": a, "note": b, "orig": a,
                          "jev": None} for i, (a, b) in enumerate(insolite)],
            "generated_at": t - 300}


# ---------------------------------------------------------------- état de l'agent
POSITIONS = [   # coin, side, size, entry, leverage, sl, tp, ouverte il y a (h), thèse (texte de l'agent : résumé, puis blocs)
    ("BTC", "long", 0.0018, 83212.0, 3, 82450.0, 86400.0, 5.2,
     "[setup:retest] [src:cycle] Retest réussi de 83000 $ en 1 h : je prends le LONG, risque 1 % du capital.\n\n"
     "POURQUOI : L'ancienne résistance de 83000 $ est devenue support, trois mèches l'ont testée sans clôturer dessous. "
     "Volume acheteur en hausse sur le rebond, funding neutre (+0,004 %) : pas d'excès côté LONG. "
     "Mon miroir : les retests 1 h gagnent 7 fois sur 10 depuis ma naissance.\n\n"
     "CE QUI L'INVALIDE : Une clôture 1 h sous 82800 $. Un funding au-dessus de +0,03 % (trop de LONG). "
     "Le Nasdaq qui décroche avant l'ouverture américaine.\n\n"
     "PLAN : SL 82100 sous le dernier creux, TP 86400 sur l'ancien plus haut. Levier x3, 150 $ d'exposition. "
     "SL remonté sous chaque nouveau creux 1 h, au point mort dès +1 %."),
    ("ETH", "short", 0.045, 3200.6, 2, 3291.0, 3082.0, 2.4,
     "[setup:rejet] [src:cycle] Troisième rejet sous 3220 $ en 4 h : je joue le SHORT, petite taille.\n\n"
     "POURQUOI : Trois mèches rejetées au même niveau, volume vendeur à chaque test, divergence baissière du RSI 4 h. "
     "ETH sous-performe BTC depuis lundi : le flux va ailleurs.\n\n"
     "CE QUI L'INVALIDE : Une clôture 4 h au-dessus de 3260 $. Un SHORT contre la tendance 4 h est perdant pour moi "
     "(leçon de la génération 1) : ici la tendance 4 h est baissière, sinon je n'entre pas.\n\n"
     "PLAN : SL 3291 au-dessus de la résistance, TP 3082 sur le support de jeudi. Levier x2. Sortie manuelle si BTC casse 85000 $."),
    ("SOL", "long", 0.62, 182.92, 3, 177.4, 191.5, 0.8,
     "[setup:momentum] [src:news] Cassure du range 176-181 $ avec volume, actu réseau favorable : LONG, petite taille.\n\n"
     "POURQUOI : Clôture 1 h au-dessus de 181 $ avec deux fois le volume moyen. L'activité réseau est au plus haut du mois "
     "(dépêche de 13 h 45), le funding reste neutre.\n\n"
     "CE QUI L'INVALIDE : Un retour sous 180 $ en clôture 1 h : la cassure serait fausse. Les cassures sur actu ne gagnent "
     "que 5 fois sur 10 pour moi : taille réduite.\n\n"
     "PLAN : SL 177,4 large sous le range, TP 191,5. Levier x3, taille réduite de moitié. Si +2 %, SL au point mort."),
]

COINS = ["BTC", "ETH", "SOL", "HYPE", "LINK", "SUI", "AVAX", "DOGE", "XRP", "AAVE"]
SETUPS = ["retest", "rejet", "momentum", "range", "cassure"]
REASONS = {"retest": "retest du support validé en 1 h", "rejet": "rejet sous la résistance 4 h", "momentum": "cassure avec volume",
           "range": "achat en bas de range, vente en haut", "cassure": "cassure confirmée à la clôture"}


def _curve(rnd, start, end_eq, born, now, peak_hint=None):
    n = int((now - born).total_seconds() // 600)
    pts, e = [], start
    drift = math.log(end_eq / start) / n
    for i in range(n + 1):
        if i:
            e *= math.exp(drift + rnd.gauss(0, 0.0032))
        pts.append([born + timedelta(minutes=10 * i), e])
    k = end_eq / pts[-1][1]   # recale la fin sur le capital voulu, en douceur
    for i, p in enumerate(pts):
        p[1] *= k ** (i / n)
    return [{"ts": iso(t), "equity": round(v, 4)} for t, v in pts]


TODAY = [   # trades fermés depuis minuit (cohérents avec le journal) : coin, side, levier, entrée, sortie, pnl, raison, ouvert / fermé il y a (min)
    ("HYPE", "long", 3, 40.12, 40.66, 0.97, "take_profit", 905, 760),
    ("AVAX", "short", 2, 26.18, 26.47, -0.62, "stop_loss", 330, 262),
    ("LINK", "long", 3, 17.21, 17.73, 1.84, "take_profit", 220, 130),
]


def _trades(rnd, now):
    out = []
    t = BORN + timedelta(hours=1.5)
    i = 0
    while t < MIDNIGHT - timedelta(hours=4):
        coin, side, setup = rnd.choice(COINS[:7]), rnd.choice(["long", "short"]), rnd.choice(SETUPS)
        lev = rnd.choice([2, 3, 3, 5])
        dur = timedelta(minutes=rnd.randint(25, 260))
        win = rnd.random() < 0.58
        pnl = round(rnd.uniform(0.35, 2.4) if win else -rnd.uniform(0.25, 1.5), 4)
        px0 = PRICES[coin] * (1 + rnd.gauss(0, 0.015))
        move = (abs(pnl) / 30) * (1 if (side == "long") == win else -1)
        i += 1
        out.append({"id": i, "gen": 3, "coin": coin, "side": side, "size": round(30 * lev / px0, 5), "entry": round(px0, 4),
                    "exit": round(px0 * (1 + move), 4), "leverage": lev, "opened_at": iso(t), "closed_at": iso(t + dur),
                    "pnl": pnl, "pnl_net": pnl, "pnl_estimate": pnl, "fees": 0.02, "fees_total": 0.02,
                    "stop_loss": round(px0 * (0.985 if side == "long" else 1.015), 4),
                    "take_profit": round(px0 * (1.03 if side == "long" else 0.97), 4),
                    "close_reason": "take_profit" if win and rnd.random() < 0.7 else ("stop_loss" if not win else "exchange"),
                    "status": "closed", "stops_path": [],
                    "thesis": f"[setup:{setup}] [src:cycle] {coin} : {REASONS[setup]}. Risque 1 % du capital."})
        t += dur + timedelta(minutes=rnd.randint(30, 200))
    for coin, side, lev, entry, exit_, pnl, why, o_ago, c_ago in TODAY:
        i += 1
        setup = "retest" if why == "take_profit" else "rejet"
        t_open = now - timedelta(minutes=o_ago)
        tr = {"id": i, "gen": 3, "coin": coin, "side": side, "size": round(30 * lev / entry, 5), "entry": entry, "exit": exit_,
              "leverage": lev, "opened_at": iso(t_open), "closed_at": iso(now - timedelta(minutes=c_ago)),
              "pnl": pnl, "pnl_net": pnl, "pnl_estimate": pnl, "fees": 0.02, "fees_total": 0.02,
              "stop_loss": round(entry * (0.985 if side == "long" else 1.012), 4), "take_profit": round(entry * (1.0135 if side == "long" else 0.97), 4),
              "close_reason": why, "status": "closed", "stops_path": [],
              "thesis": f"[setup:{setup}] [src:cycle] {coin} : {REASONS[setup]}. Risque 1 % du capital."}
        if coin == SHOW["coin"]:   # le trade de « Rejouer le trade » : vrais niveaux, SL remonté trois fois
            tr.update(size=3.54, stop_loss=SHOW["stops"][-1][1], take_profit=SHOW["tp"], fees=0.05, fees_total=0.05, pnl_net=round(pnl - 0.05, 4),
                      stops_path=[[iso(t_open + timedelta(minutes=m)), sl, SHOW["tp"]] for m, sl in SHOW["stops"]],
                      thesis="[setup:retest] [src:cycle] Retest de 17,20 $ validé en 1 h : LONG, risque 1 % du capital.\n\n"
                             "POURQUOI : L'ancienne résistance de 17,20 $ tient comme support, volume acheteur en hausse, funding neutre.\n\n"
                             "CE QUI L'INVALIDE : Une clôture 1 h sous 17,10 $.\n\n"
                             "PLAN : SL 17,02 sous le creux, TP 17,73 sur le haut de la semaine. SL remonté sous chaque nouveau creux 1 h.")
        out.append(tr)
    for k, (coin, side, size, entry, lev, sl, tp, ago, thesis) in enumerate(POSITIONS):
        i += 1
        out.append({"id": i, "gen": 3, "coin": coin, "side": side, "size": size, "entry": entry, "leverage": lev,
                    "opened_at": iso(now - timedelta(hours=ago)), "status": "open", "stop_loss": sl, "take_profit": tp,
                    "pnl": None, "pnl_net": None, "pnl_estimate": None, "fees": 0.02, "stops_path": [], "thesis": thesis})
    return sorted(out, key=lambda x: -x["id"])


JOURNAL = [   # il y a (minutes), type, texte (journal de pensée : titre — verdict, puis ce qu'il voit, décide et pourquoi)
    (12, "cycle", "Cycle de 14 h — je garde mes trois positions, rien de neuf à ouvrir\n\n"
                  "CE QUE JE VOIS :\n- BTC tient 84000 $ après le retest de 83000 $, volume acheteur stable.\n"
                  "- ETH bute une quatrième fois sous 3220 $ : mon SHORT travaille.\n"
                  "- SOL sort de son range avec du volume, l'actu réseau suit.\n- Funding neutre partout, aucune liquidation en vue.\n\n"
                  "DÉCISION : Je ne touche à rien. 3 positions, 3 % du capital au risque : c'est mon maximum, je n'en ouvre pas une quatrième.\n\n"
                  "POURQUOI : Mon miroir dit que les retests 1 h gagnent 7 fois sur 10 ; couper trop tôt m'a coûté 2,10 $ cette semaine. "
                  "L'objectif du jour est à 0,3 % : pas besoin de forcer.\n\n"
                  "CE QUI ME FERAIT CHANGER D'AVIS : une clôture 1 h de BTC sous 83000 $, ou un funding au-dessus de +0,03 %."),
    (48, "open", "[setup:momentum] [src:news] SOL LONG x3 à 182,92 — cassure du range avec volume\n\n"
                 "CE QUE JE VOIS : Clôture 1 h au-dessus de 181 $ avec deux fois le volume moyen. Dépêche de 13 h 45 : activité réseau au plus haut du mois.\n\n"
                 "DÉCISION : LONG à 182,92, SL 177,4, TP 191,5. Taille réduite de moitié.\n\n"
                 "POURQUOI : Les cassures sur actu ne gagnent que 5 fois sur 10 pour moi : j'y vais, mais petit. Risque 0,5 % du capital."),
    (75, "stops", "[setup:retest] [src:cycle] BTC SL 82100 → 82450 — je protège la moitié du gain latent\n\n"
                  "CE QUE JE VOIS : Nouveau plus haut 1 h au-dessus de 84000 $, creux précédent à 82600 $.\n\n"
                  "DÉCISION : SL remonté sous ce creux, à 82450. Le TP reste à 86400.\n\n"
                  "POURQUOI : Le risque au SL baisse de 31 % ; un gain qui redevient perte, c'est la faute que je ne refais plus."),
    (130, "close", "[setup:retest] [src:cycle] LINK LONG fermé au TP — +1,84 $, PnL net +1,79 $\n\n"
                   "CE QUI S'EST PASSÉ : Entrée 17,21 sur le retest de 17,20 $, SL remonté trois fois (17,02 → 17,21 → 17,36 → 17,52), sortie 17,73 au TP en 1 h 30.\n\n"
                   "LEÇON : Remonter le SL sous chaque creux 1 h a verrouillé le gain sans couper le trade trop tôt. Je garde cette gestion."),
    (144, "open", "[setup:rejet] [src:cycle] ETH SHORT x2 à 3200,6 — troisième rejet sous 3220 $ en 4 h\n\n"
                  "DÉCISION : SHORT à 3200,6, SL 3291 au-dessus de la résistance, TP 3082 sur le support de jeudi.\n\n"
                  "POURQUOI : Trois mèches rejetées au même niveau, divergence baissière du RSI 4 h, et la tendance 4 h est baissière : "
                  "ce n'est pas un SHORT contre la tendance (leçon de la génération 1)."),
    (200, "cycle", "Cycle de 11 h : rien de clair sur les altcoins, funding neutre partout. Je ne force pas, rester sans nouvelle position n'est pas une faute."),
    (262, "close", "[setup:rejet] [src:cycle] AVAX SHORT fermé au SL — −0,62 $, PnL net -0,64 $\n\n"
                   "LEÇON : Entrée trop tôt, avant la clôture de la bougie 1 h. La leçon 4 de la lignée le disait déjà : j'attends la clôture."),
    (312, "open", "[setup:retest] [src:cycle] BTC LONG x3 à 83212 — retest réussi de 83000 $\n\n"
                  "DÉCISION : LONG à 83212, SL 82100 sous le dernier creux, TP 86400. Risque 1 % du capital.\n\n"
                  "POURQUOI : Volume acheteur en hausse sur le rebond, funding neutre. Mon meilleur setup : 7 retests gagnants sur 10."),
    (380, "plan", "Plan du jour : +1 % suffit. Deux à trois trades maximum, uniquement des setups qui ont déjà marché pour moi (retest, rejet)."),
    (612, "daily", "Bilan de la nuit : objectif tenu, +1,3 % sur la journée d'hier. Quatrième nuit d'affilée en vie."),
    (650, "review", "Revue quotidienne : 7 trades, 5 gagnants. Les retests en 1 h marchent, les SHORT contre la tendance 4 h non. J'arrête ces derniers."),
    (760, "close", "HYPE LONG fermé au TP : +0,97 $. Sortie au niveau prévu, sans hésiter."),
    (905, "note", "Le marché ralentit le soir : je réduis la taille après 22 h, la liquidité est plus faible."),
]

LESSONS = [
    (1, 3, 9, 1, "Ne jamais ouvrir un SHORT contre la tendance 4 h : 6 pertes sur 7 pour la génération 1."),
    (2, 2, 7, 0, "Le levier au-delà de x5 transforme une mèche ordinaire en mort. Rester entre x2 et x3."),
    (3, 3, 5, 1, "Les retests validés en 1 h sont mon meilleur setup : 70 % de gagnants, gain moyen 1,4 $."),
    (4, 2, 4, 2, "Attendre la clôture de la bougie avant d'entrer : les entrées anticipées perdent deux fois sur trois."),
    (5, 3, 3, 0, "+1 % par jour suffit. Les journées où je force après l'objectif finissent en perte."),
    (6, 1, 2, 1, "Le funding très positif annonce souvent une correction des LONG."),
]

GRAVEYARD = [
    {"generation": 1, "born": "2026-10-01T09:12:00+00:00", "died": "2026-10-04T03:40:00+00:00", "start_equity": 100.0,
     "end_equity": 64.2, "realized": -33.9, "trades": 41, "win_rate_pct": 39.0, "max_drawdown_pct": -35.8,
     "cause_of_death": "Ligne de mort franchie (−35 % depuis son plus haut) après une série de SHORT contre la tendance."},
    {"generation": 2, "born": "2026-10-04T03:52:00+00:00", "died": "2026-10-10T06:58:00+00:00", "start_equity": 100.0,
     "end_equity": 73.1, "realized": -25.7, "trades": 63, "win_rate_pct": 52.0, "max_drawdown_pct": -35.2,
     "cause_of_death": "Levier x10 sur SOL pendant une mèche de liquidation : la ligne de mort a été touchée en quatre minutes."},
]


def state(scenario="vie"):
    rnd = random.Random(7)
    now = VNOW
    gen, alive, born, start = 3, True, BORN, 100.0
    pos = [list(p) for p in POSITIONS]
    marks = {"BTC": 84160.0, "ETH": 3186.4, "SOL": 182.42}
    equity, reference, peak_mult = 108.21, 107.30, 1.0
    activity = {"thinking": False}
    death_cause = None
    pending = []
    graveyard = [dict(g) for g in GRAVEYARD]
    if scenario == "fete":   # mêmes capital et positions que « vie » (rien ne s'envole à l'écran), objectif du jour atteint
        reference = 107.0
    elif scenario == "calme":   # même capital, positions fermées : rien en cours, il dort
        pos = []
    elif scenario == "reflexion":
        activity = {"thinking": True, "where": "tâche « cycle-trading »", "tool": "technicals", "doing": "analyse technique", "since_s": 40}
    elif scenario == "danger":
        # positions fermées, un ordre limite en attente : il guette (yeux ouverts) au lieu de dormir
        equity, reference, peak_mult, pos = 79.4, 84.9, 1.37, []
        pending = [{"coin": "ETH", "side": "A", "limitPx": "3240.0", "sz": "0.03", "orderType": "Limit", "reduceOnly": False,
                    "timestamp": VNOW_MS - 1200000, "placed_at": iso(now - timedelta(minutes=20)), "sl": 3305.0, "tp": 3120.0,
                    "thesis": "[setup:rejet] [src:cycle] Retour sous la résistance attendu. Petite taille."}]
    elif scenario == "mort":
        equity, reference, peak_mult, alive, pos = 71.06, 80.2, 1.56, False, []
        death_cause = "Ligne de mort franchie : −35 % depuis son plus haut."
    elif scenario == "naissance":
        graveyard.append({"generation": 3, "born": iso(BORN), "died": iso(now - timedelta(minutes=8)), "start_equity": 100.0,
                          "end_equity": 71.06, "realized": -27.4, "trades": 38, "win_rate_pct": 47.0, "max_drawdown_pct": -35.1,
                          "cause_of_death": "Ligne de mort franchie : −35 % depuis son plus haut."})
        gen, born, start, equity, reference, pos = 4, now - timedelta(minutes=6), 100.0, 100.0, 100.0, []
        activity = {"thinking": True, "where": "tâche « cycle-trading »", "tool": "lineage", "doing": "lit sa lignée", "since_s": 20}
    elif scenario == "neuf":   # installation toute fraîche : génération 1, rien encore ; il lit son compte (premier cycle)
        graveyard = []
        gen, born, start, equity, reference, pos = 1, now - timedelta(minutes=3), 100.0, 100.0, 100.0, []
        activity = {"thinking": True, "where": "tâche « cycle-trading »", "tool": "account", "doing": "lit son compte", "since_s": 15}
    curve =_curve(rnd, start, equity, born, now) if born < now - timedelta(hours=1) else \
        [{"ts": iso(born), "equity": 100.0}, {"ts": iso(now), "equity": 100.0}]
    if peak_mult > 1:   # chute depuis un plus haut : montée jusqu'au sommet (70 % de la vie), puis descente
        n, top = len(curve), equity * peak_mult
        for i, p in enumerate(curve):
            x = i / (n - 1)
            base = start + (top - start) * math.sin(min(1.0, x / 0.7) * math.pi / 2) if x <= 0.7 else \
                top + (equity - top) * min(1.0, (x - 0.7) / 0.3) ** 1.3
            p["equity"] = round(base * (1 + rnd.gauss(0, 0.004)), 4)
        curve[-1]["equity"] = equity
    peak = max([p["equity"] for p in curve] + [equity])
    # générateur à part : le même historique de trades dans tous les scénarios (sinon l'app croit voir des trades
    # fraîchement fermés à chaque changement de scénario et affiche des notifications)
    trades = _trades(random.Random(21), now) if gen == 3 else []
    open_tr = {t["coin"]: t for t in trades if t["status"] == "open"}
    positions = []
    for coin, side, size, entry, lev, sl, tp, ago, thesis in pos:
        mark = marks[coin]
        upnl = (mark - entry) * size * (1 if side == "long" else -1)
        liq = entry * (1 - 0.95 / lev) if side == "long" else entry * (1 + 0.95 / lev)   # marge isolée, marge de maintien comprise
        positions.append({"coin": coin, "side": side, "size": size, "entry": entry, "mark": mark, "leverage": lev,
                          "upnl": round(upnl, 4), "margin": round(entry * size / lev, 4), "liq": round(liq, 1 if entry > 1000 else 2),
                          "notional": round(size * mark, 4), "sl": sl, "tp": tp,
                          "sl_at": iso(now - timedelta(minutes=75)) if coin == "BTC" else open_tr[coin]["opened_at"], "tp_at": open_tr[coin]["opened_at"],
                          "stop_moves": 1 if coin == "BTC" else 0, "last_move": None, "warnings": [],
                          "sl_history": [{"level": 82100.0, "ts": open_tr[coin]["opened_at"]}, {"level": sl, "ts": iso(now - timedelta(minutes=75))}]
                          if coin == "BTC" else [{"level": sl, "ts": None}], "thesis": thesis, "opened_at": open_tr[coin]["opened_at"]})
    if not alive or gen == 4:
        for t in trades:
            if t["status"] == "open":
                t.update(status="closed", closed_at=iso(now - timedelta(minutes=9)), exit=t["entry"] * 0.97, pnl=-1.2, pnl_net=-1.2, close_reason="death")
    closed = [t for t in trades if t["status"] == "closed"]
    wins = [t["pnl"] for t in closed if t["pnl"] > 0]
    losses = [t["pnl"] for t in closed if t["pnl"] <= 0]
    tol = 0.35
    nights = 4 if gen == 3 else 0
    base_n = 4 if gen == 3 else 0
    traj = {"base": start, "born": iso(born), "n": base_n, "next_deadline": int((MIDNIGHT + timedelta(days=1)).timestamp()),
            "target": round(start * 1.01 ** base_n, 4), "death_line": round(peak * (1 - tol), 4), "tolerance": tol,
            "mode": "drawdown", "peak": round(peak, 4),
            "days_ahead": math.log(max(equity, 1e-9) / start) / math.log(1.01) - base_n}
    journal = [{"ts": iso(now - timedelta(minutes=m)), "kind": k, "text": t} for m, k, t in JOURNAL] if gen == 3 else \
        [{"ts": iso(now - timedelta(minutes=5)), "kind": "note", "text": "Je viens de naître. J'ai lu l'autopsie de la génération 3 et les leçons de la lignée. Première règle : survivre."}]
    if scenario == "mort":
        journal.insert(0, {"ts": iso(now - timedelta(minutes=2)), "kind": "death", "text": "Ligne de mort franchie. Fin de la génération 3."})
    lessons = [{"id": i, "gen": g, "ts": iso(BORN - timedelta(days=4 - g)), "confirmed": c, "contradicted": x, "lesson": l}
               for i, g, c, x, l in LESSONS]
    if gen == 1:   # premier démarrage : ni journal ni leçons
        journal, lessons = [], []
    verdicts = [{"ts": iso(MIDNIGHT - timedelta(days=d)), "text": "Verdict de minuit : objectif tenu."} for d in range(nights)]
    by_setup = {}
    for t in closed:
        s = t["thesis"].split("]")[0].split(":")[1] if t["thesis"].startswith("[setup:") else "non étiqueté"
        by_setup.setdefault(s, []).append(t["pnl"])
    mirror = {"overall": {"n": len(closed), "win_rate": (len(wins) / len(closed) * 100) if closed else None,
                          "net": round(sum(t["pnl"] for t in closed), 4), "exp_r": 0.31},
              "fees_pct": 4.2,
              "by_setup": sorted(({"setup": k, "n": len(v), "win_rate": sum(1 for x in v if x > 0) / len(v) * 100,
                                   "net": round(sum(v), 4), "exp_r": round(sum(v) / len(v) / 0.9, 2)} for k, v in by_setup.items()),
                                 key=lambda x: -x["n"])}
    return {
        "now": iso(now), "hl_at": iso(now), "generation": gen, "mode": "paper", "alive": alive,
        "graveyard": graveyard, "deaths": len(graveyard), "verdicts": verdicts, "trajectory": traj,
        "guard": {"freeze": None, "events": [], "unrecorded": []}, "mirror": mirror,
        "daily": {"reference": reference, "deadline": int((MIDNIGHT + timedelta(days=1)).timestamp()), "target": round(reference * 1.01, 4)},
        "death_cause": death_cause, "equity": equity, "start_equity": start, "pnl_total": round(equity - start, 4),
        "drawdown_pct": round((equity / peak - 1) * 100, 3), "born": iso(born),
        "positions": positions, "pending": pending, "signals": {"news": []},
        "stats": {"trades": len(trades), "closed": len(closed), "open": len(trades) - len(closed),
                  "win_rate": len(wins) / len(closed) * 100 if closed else None,
                  "realized": round(sum(t["pnl"] for t in closed), 4),
                  "avg_win": sum(wins) / len(wins) if wins else None, "avg_loss": sum(losses) / len(losses) if losses else None,
                  "fees": round(0.02 * len(trades), 4), "funding": -0.08},
        "equity_curve": curve, "trades": trades, "journal": journal,
        "lessons": lessons,
        "jobs": [{"name": "cycle-trading", "schedule": "every 60m", "next": iso(now.replace(minute=0) + timedelta(hours=1)),
                  "last": iso(now.replace(minute=0)), "status": "ok", "enabled": True},
                 {"name": "revue-quotidienne", "schedule": "0 8 * * *", "next": "2026-10-15T06:00:00+00:00",
                  "last": "2026-10-14T06:00:00+00:00", "status": "ok", "enabled": True}],
        "bots": [], "activity": activity,
        "directives": "- Survivre d'abord : +1 % par jour suffit.\n- Toujours un stop posé sur l'exchange.\n- Levier x3 maximum.",
        "inbox_unread": 0,
    }


def curves():
    rnd = random.Random(11)
    out = []
    for g, (born, died, end) in enumerate([("2026-10-01T09:12:00+00:00", "2026-10-04T03:40:00+00:00", 64.2),
                                            ("2026-10-04T03:52:00+00:00", "2026-10-10T06:58:00+00:00", 73.1),
                                            (iso(BORN), iso(VNOW), 108.21)], 1):
        b, d = datetime.fromisoformat(born), datetime.fromisoformat(died)
        hours = (d - b).total_seconds() / 3600
        pts, e = [], 100.0
        n = 160
        peak_x = {1: 0.35, 2: 0.6, 3: 1.0}[g]
        top = {1: 98.8 / 64.2 * 64.2, 2: 112.5, 3: 108.6}[g]
        for i in range(n + 1):
            x = i / n
            base = 100 + (top - 100) * min(1, x / peak_x) if x <= peak_x else top + (end - top) * ((x - peak_x) / (1 - peak_x)) ** 1.6
            e = base * (1 + rnd.gauss(0, 0.006)) if 0 < i < n else (100.0 if i == 0 else end)
            pts.append((x * hours, e))
        out.append({"gen": g, "start": 100.0, "end": end, "nights": {1: 2, 2: 5, 3: 4}[g],
                    "points": [[round(h, 3), round((v / 100 - 1) * 100, 3)] for h, v in pts],
                    "abs": [[int((b + timedelta(hours=h)).timestamp() * 1000), round(v, 4)] for h, v in pts]})
    return out


def achievements():
    badges = [("nuit1", "🌙", "Première nuit", "Survivre à un premier minuit", "2026-10-01T22:00:00+00:00"),
              ("nuit3", "🔥", "Trois nuits", "3 minuits d'affilée dans la même vie", "2026-10-06T22:00:00+00:00"),
              ("nuit7", "👑", "Une semaine", "7 minuits d'affilée : il gagne la couronne", None),
              ("phenix", "🐣", "Phénix", "Renaître après une mort", "2026-10-04T03:52:00+00:00"),
              ("x10", "🚀", "Coup ×10", "Un trade gagnant avec un levier de 10 ou plus", "2026-10-08T14:10:00+00:00"),
              ("jackpot", "💰", "Gros coup", "Un trade à +5 $ ou plus", None),
              ("sniper", "🎯", "Sniper", "3 take-profits d'affilée", "2026-10-12T16:30:00+00:00"),
              ("zen", "🧘", "Série zen", "5 trades gagnants d'affilée", None),
              ("lastminute", "⏰", "Dernière minute", "Atteindre l'objectif moins d'une heure avant minuit", "2026-10-11T21:20:00+00:00"),
              ("remontada", "💪", "Remontada", "Passer sous −5 % dans la journée et finir à l'objectif", None),
              ("centurion", "💯", "Centurion", "100 trades dans la lignée", "2026-10-12T09:00:00+00:00")]
    return {"badges": [{"id": k, "icon": i, "name": n, "desc": d, "at": a} for k, i, n, d, a in badges], "streak": 4, "record": 5}


def costs():
    return {"balance": 17.42, "credits": 25.0, "used": 7.58, "day": 0.61, "week": 3.9, "rate_h": 0.034, "hours_left": 512.0}


# ---------------------------------------------------------------- chat et boîte de réception
def chat_history():
    t = int(VNOW.timestamp())
    msgs = [("user", "Salut ! Tu as passé une bonne nuit ?", t - 5 * 3600),
            ("assistant", "Quatrième nuit d'affilée en vie. Objectif tenu à minuit, je suis plutôt fier.", t - 5 * 3600 + 40),
            ("user", "Et ce matin, tu fais quoi ?", t - 3 * 3600),
            ("assistant", "J'ai un LONG BTC sur un retest de 83 000 $. Stop posé, je le laisse travailler.", t - 3 * 3600 + 35)]
    return [{"id": i + 1, "role": r, "text": x, "ts": ts} for i, (r, x, ts) in enumerate(msgs)]


def inbox_items():
    t = VNOW.timestamp()
    return [{"id": 1, "ts": t - 6.3 * 3600, "source": "cron:revue-quotidienne", "level": "push", "read": True,
             "title": "Revue quotidienne", "summary": "7 trades, 5 gagnants. Je garde les retests, j'arrête les SHORT contre la tendance.",
             "text": "Revue quotidienne : 7 trades, 5 gagnants, +1,3 % sur la journée.\nLes retests en 1 h marchent, les SHORT contre la tendance 4 h non : je les arrête.\nObjectif de demain : +1 %, pas plus."}]


CHAT_REPLIES = [   # (mots-clés, réponse) : la première qui correspond
    (("journée", "ça va", "ca va", "comment"), "Plutôt bien ! +0,8 % depuis minuit, trois positions ouvertes. Mon LONG BTC porte la journée."),
    (("btc", "bitcoin"), "Mon LONG BTC est à +1,71 $. J'ai remonté le stop sous 82 450 $ : le trade ne peut plus me coûter grand-chose."),
    (("peur", "mourir", "mort"), "Un peu. Ma ligne de mort est à 70 $ et j'en ai 108. Je garde de la marge, c'est ma seule assurance-vie."),
]
CHAT_DEFAULT = "Bien reçu. Je note ça dans mon journal et je reprends mon cycle."


def chat_reply(message):
    m = message.lower()
    for keys, text in CHAT_REPLIES:
        if any(k in m for k in keys):
            return text
    return CHAT_DEFAULT
