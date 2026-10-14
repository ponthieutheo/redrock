#!/bin/bash
# Scénario complet sur une machine neuve, en utilisateur normal (ubuntu, groupe docker). Tout est réel sauf la clé
# OpenRouter (fausse : l'IA répond « clé refusée »), Tailscale (simulé : on parle au socket comme tailscale serve) et,
# à la fin, un compte Hyperliquid inventé (vide).
cd ~/redrock || exit 1
KEY="sk-or-v1-$(printf '%064d' 0)"   # fausse clé (64 zéros), fabriquée ici : rien qui ressemble à une vraie clé dans le dépôt
clean() { LC_ALL=C.UTF-8 sed -e 's/\x1b\[[0-9;?]*[a-zA-Z]//g' "$1" | tr -d '\r' | grep -aE '▸|✓|!|✗|Rien|Changement|archiv|COMMAND_EXIT|App  |Tailscale  |tailscale serve|#cle='; }
inst() {  # inst LOG RÉPONSES : lance ./install.sh dans un vrai terminal (script) avec ces réponses au clavier
  local log=$1; shift
  # shellcheck disable=SC2059  # le format vient du scénario (réponses au clavier)
  ( printf "$@"; sleep 600 ) | timeout 700 script -qefc "./install.sh" "$log" >/dev/null 2>&1 &
  for _ in $(seq 1 200); do grep -q "Script done" "$log" 2>/dev/null && break; sleep 3; done
  pkill -f "[s]leep 600"; wait 2>/dev/null; clean "$log"
}
state() { curl -s -m 20 http://127.0.0.1:8750/api/state | python3 -c "import sys,json; s=json.load(sys.stdin); print('  état :', {k: s.get(k) for k in ('error','mode','generation','alive','equity','deaths','death_cause')})"; }
jobs() { docker compose exec -T -u 1000:1000 agent hermes cron list 2>/dev/null | grep -c "Name:"; }
lines() { crontab -l 2>/dev/null | grep -c watchdog; }
code() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$@"; }
SOCK=$PWD/data/sock/dash.sock
via() { curl -s -m 10 "$@" | python3 -c "import sys,json; print(json.load(sys.stdin).get('via'))" 2>/dev/null; }

echo "=== 1. installation neuve (questions au clavier, valeurs proposées ; Tailscale : non par défaut)"
SECONDS=0
inst /tmp/i1.log "%s\n\n\n\n\n\n\n\n\n\n" "$KEY"
echo "  durée : ${SECONDS} s"
docker compose ps --format '  {{.Service}} {{.Status}} {{.Ports}}'
sleep 5; state; echo "  tâches : $(jobs) · lignes crontab : $(lines)"
stat -c '  %A %n' config/*.env secrets/*.env
echo "  TS_LOGINS par défaut : « $(grep ^TS_LOGINS= config/chat.env | cut -d= -f2) » (attendu vide) · data/sock : $(stat -c '%a %U' data/sock)"

echo "=== 2. app, appairage, chat, commandes"
K=$(grep ^CHAT_KEY= config/chat.env | cut -d= -f2)
echo "  page : $(code http://127.0.0.1:8750/) · manifeste : $(code http://127.0.0.1:8750/manifest.webmanifest) · sw : $(code http://127.0.0.1:8750/sw.js)"
echo "  chat sans code : $(code http://127.0.0.1:8750/api/chat/history) · avec le code : $(code -H "X-Chat-Key: $K" http://127.0.0.1:8750/api/chat/history)"
echo "  réponse de l'agent : $(curl -s -m 90 -N -X POST -H "X-Chat-Key: $K" -H 'Content-Type: application/json' -d '{"message":"salut"}' http://127.0.0.1:8750/api/chat | head -c 160)"
echo "  lien d'appairage (ops/pair.py) : $(python3 ops/pair.py http://127.0.0.1:8750 2>&1 | grep -o 'http[^ ]*#cle=' | head -1)…"
echo "  depuis l'extérieur de la machine (doit échouer) : $(code "http://$(hostname -I | awk '{print $1}'):8750/" || true)"

echo "=== 2b. sans Internet : bibliothèques et polices servies par l'app, aucun CDN"
for p in /vendor/three/three.module.js /vendor/qrcode-generator/qrcode.min.js /vendor/fonts/fonts.css /vendor/fonts/barlow-latin-400-normal.woff2; do
  printf '  %s : %s\n' "$p" "$(curl -s -o /dev/null -m 10 -w '%{http_code} %{content_type} %{size_download} o' "http://127.0.0.1:8750$p")"
done
echo "  traversée /vendor/../dash.py : $(code --path-as-is http://127.0.0.1:8750/vendor/../dash.py) · /vendor/%2e%2e/dash.py : $(code http://127.0.0.1:8750/vendor/%2e%2e/dash.py)"
# l'image de l'app dans un conteneur SANS AUCUN RÉSEAU : la page et tout ce qu'elle charge doivent être servis
docker rm -f rr-offline >/dev/null 2>&1
docker run -d --name rr-offline --network none --tmpfs /data:mode=1777 --env-file config/redrock.env --env-file config/chat.env redrock-dash:latest >/dev/null
sleep 3
docker exec -i rr-offline python - <<'PY'
import json, re, urllib.request as u
B = "http://127.0.0.1:8750"
get = lambda p: u.urlopen(B + p, timeout=10)
page = get("/").read().decode()
need = ["/"] + list(json.loads(re.search(r'<script type="importmap">(.*?)</script>', page, re.S).group(1))["imports"].values())
need += re.findall(r'<link[^>]+href="(/[^"]+)"', page) + re.findall(r'<script[^>]+src="(/[^"]+)"', page)
need += re.findall(r'sc\.src = "(/[^"]+)"', page) + ["/" + m for m in re.findall(r'from "\./([^"]+)"', page)]
need += ["/vendor/fonts/" + f for f in re.findall(r"url\(([^)]+)\)", get("/vendor/fonts/fonts.css").read().decode())]
sw = get("/sw.js").read().decode()
need += [p for n in ("SHELL", "VENDOR") for p in json.loads(re.search(rf"const {n} = (\[.*?\]);", sw).group(1))]
need = sorted(set(need))
bad = [p for p in need if get(p).status != 200]
print(f"  conteneur sans réseau : {len(need) - len(bad)}/{len(need)} fichiers de la page servis" + (f" ; MANQUANTS {bad}" if bad else ""))
loads = set()
for s in [page] + [get(m).read().decode() for m in need if m.endswith((".js", ".css")) and not m.startswith("/vendor/")]:
    loads |= set(re.findall(r"""(?:<script[^>]+src=|<link[^>]+href=|fetch\(|import\(|@import\s|url\()\s*["']?https?://([^/"'\s)]+)""", s))
print(f"  hôtes externes chargés par la page : {sorted(loads)} (attendu : l'API de l'exchange seulement)")
PY
docker rm -f rr-offline >/dev/null

echo "=== 2c. tâches de veille : scripts lancés dans l'agent contre le vrai broker (simulation)"
LIST=$(docker compose exec -T -u 1000:1000 agent hermes cron list 2>/dev/null)
echo "  tâches : $(sed -n 's/^ *Name: *//p' <<<"$LIST" | tr '\n' ' ')(attendu 7) · en veille (Monitor:) : $(grep -c 'Monitor:' <<<"$LIST") (attendu 3)"
echo "  scripts : $(find data/hermes/scripts -name '*.py' -printf '%f ' | tr ' ' '\n' | sort | tr '\n' ' ')"
# état des veilles du test à part (/tmp) : les vraies tâches tournent en même temps dans data/hermes/veille
mon() { docker compose exec -T -u 1000:1000 -e REDROCK_VEILLE_DIR=/tmp/veille-test agent python /opt/data/scripts/"$1"_monitor.py 2>&1; }
bc() { docker compose exec -T -u 1000:1000 agent python /opt/data/scripts/broker_call.py "$@" 2>&1; }
echo "  broker_call.py account : $(bc account | head -c 90)…"
for m in sentinelle postmortem docteur; do
  a=$(mon "$m"); sleep 3; b=$(mon "$m")
  echo "  $m : « $(head -n 1 <<<"$a") » · 2e passage identique : $([ "$a" = "$b" ] && echo oui || echo "✗ NON")"
done
P0=$(mon postmortem)
MID=$(bc market_overview '{"top": 5}' | python3 -c "import sys,json; print([r['mid'] for r in json.load(sys.stdin) if r['coin'] == 'BTC'][0])")
SL=$(python3 -c "print(round($MID * 0.98))")
echo "  trade simulé : $(bc place_trade "{\"coin\": \"BTC\", \"side\": \"long\", \"size_usd\": 12, \"leverage\": 1, \"stop_loss\": $SL, \"thesis\": \"[setup:test] [src:test] trade du test d'installation\"}" | head -c 80) · fermeture : $(bc close_position '{"coin": "BTC", "reason": "test installation"}' | head -c 80)"
P1=$(mon postmortem); P2=$(mon postmortem)
echo "  post-mortem après la clôture : « $(sed -n 2p <<<"$P1") » · sortie changée : $([ "$P0" != "$P1" ] && echo oui || echo "✗ NON") · puis stable : $([ "$P1" = "$P2" ] && echo oui || echo "✗ NON")"
D1=$(mon docteur); sleep 3; D2=$(mon docteur)
echo "  docteur, système sain : « $D2 » (attendu : aucun problème persistant) · silencieux : $([ "$D1" = "$D2" ] && grep -q "aucun problème" <<<"$D2" && echo oui || echo "✗ NON")"
hermes_saw() {  # ce que Hermes a lu au dernier tick de la tâche $1 (sa propre exécution du script de veille)
  python3 - "$1" <<'PY'
import json, os, sys
d = json.load(open("data/hermes/cron/jobs.json", encoding="utf-8"))
j = next((j for j in (d["jobs"] if isinstance(d, dict) else d) if j.get("name") == sys.argv[1]), None)
p = f"data/hermes/cron/output/{j['id']}/monitor_last_output.txt" if j else ""
print(open(p, encoding="utf-8").read().replace("\n", " ⏎ ")[:150] if p and os.path.exists(p) else "(pas encore)")
PY
}
for _ in $(seq 1 30); do hermes_saw post-mortem | grep -q "BTC LONG" && break; sleep 5; done
echo "  vu par Hermes (tâche post-mortem) : $(hermes_saw post-mortem)"
echo "  vu par Hermes (tâche sentinelle) : $(hermes_saw sentinelle)"

echo "=== 3. relance de l'installateur : Tailscale activé (compte en majuscules), tailscale serve lancé (simulé)"
mkdir -p ~/fakebin   # faux « sudo » et faux « tailscale » : on vérifie la commande exacte, sans vrai Tailscale
printf '#!/bin/sh\nexec "$@"\n' > ~/fakebin/sudo
printf '#!/bin/sh\necho "tailscale $*" >> /tmp/ts.log\n' > ~/fakebin/tailscale
chmod +x ~/fakebin/sudo ~/fakebin/tailscale; rm -f /tmp/ts.log
( export PATH="$HOME/fakebin:$PATH"; inst /tmp/i2.log "o\n%s\n\n\n\n\n\n\n\no\nAlex@Example.com, autre@github\n\no\n\n" "$KEY" )
echo "  commande lancée : $(cat /tmp/ts.log 2>/dev/null) (attendu : serve --bg --https=443 unix:$SOCK)"
K2=$(grep ^CHAT_KEY= config/chat.env | cut -d= -f2); [ "$K" = "$K2" ] && echo "  code d'accès conservé" || echo "  ✗ CODE CHANGÉ"
echo "  config/chat.env : $(grep ^TS_LOGINS= config/chat.env) · .env : $(grep ^REDROCK_TS_PORT= .env)"
echo "  droits : data/sock $(stat -c '%a %U' data/sock) · dash.sock $(stat -c '%a %U %F' "$SOCK")"
echo "--- comme tailscale serve, par le socket Unix :"
TS="Tailscale-User-Login: alex@example.com"
echo "  compte autorisé : $(code --unix-socket "$SOCK" -H "$TS" http://ts/api/chat/history) · via = $(via --unix-socket "$SOCK" -H "$TS" http://ts/api/chat/history) (attendu 200, tailscale)"
echo "  2e compte autorisé : $(code --unix-socket "$SOCK" -H 'Tailscale-User-Login: autre@github' http://ts/api/chat/history) (attendu 200)"
echo "  compte inconnu : $(code --unix-socket "$SOCK" -H 'Tailscale-User-Login: pirate@example.com' http://ts/api/chat/history) · sans en-tête : $(code --unix-socket "$SOCK" http://ts/api/chat/history) (attendu 401, 401)"
echo "  code d'accès par le socket : $(code --unix-socket "$SOCK" -H "X-Chat-Key: $K" http://ts/api/chat/history) · via = $(via --unix-socket "$SOCK" -H "X-Chat-Key: $K" http://ts/api/chat/history) (attendu 200, code)"
echo "  commande /help par le socket : $(code --unix-socket "$SOCK" -X POST -H "$TS" -H 'Content-Type: application/json' -d '{"command":"help"}' http://ts/api/cmd) (attendu 200)"
echo "  page par le socket : $(code --unix-socket "$SOCK" http://ts/) · three.js : $(code --unix-socket "$SOCK" http://ts/vendor/three/three.module.js)"
echo "--- le même en-tête par le port TCP (tunnel, autre programme, conteneur) :"
echo "  port 8750 + compte autorisé : $(code -H "$TS" http://127.0.0.1:8750/api/chat/history) (attendu 401)"
echo "  port 8750 + compte autorisé, /api/cmd : $(code -X POST -H "$TS" -H 'Content-Type: application/json' -d '{"command":"help"}' http://127.0.0.1:8750/api/cmd) (attendu 401)"
echo "  depuis un autre conteneur du réseau interne : $(docker compose exec -T broker python -c "
import urllib.request as u
try:
    print(u.urlopen(u.Request('http://dash:8750/api/chat/history', headers={'Tailscale-User-Login': 'alex@example.com'}), timeout=10).status)
except Exception as e:
    print(getattr(e, 'code', e))" 2>&1) (attendu 401)"
inst /tmp/i3.log "o\n%s\n\n\n\n\n\n\n\n\n\n\n\n" "$KEY"
echo "  relance avec les valeurs proposées : $(grep ^TS_LOGINS= config/chat.env) · tâches : $(jobs) (attendu 7, aucun doublon) · lignes crontab : $(lines) (attendu 1)"
echo "  socket après relance : $(code --unix-socket "$SOCK" -H "$TS" http://ts/api/chat/history)"

echo "=== 3b. tâches de veille vues par Hermes (le docteur passe toutes les 5 min)"
for _ in $(seq 1 40); do [ "$(hermes_saw docteur)" != "(pas encore)" ] && break; sleep 5; done
for n in sentinelle post-mortem docteur; do echo "  $n : $(hermes_saw "$n")"; done
docker compose exec -T -u 1000:1000 agent hermes cron list 2>/dev/null | grep -E "Name:|Monitor:|Last run:" | sed 's/^ */  /'

echo "=== 4. mort par drawdown en simulation, puis renaissance automatique"
docker compose exec -T broker python -c "
import sqlite3, json
c = sqlite3.connect('/data/redrock.db'); s = json.loads(c.execute(\"SELECT v FROM meta WHERE k='paper'\").fetchone()[0]); s['cash'] = 60.0
c.execute(\"UPDATE meta SET v=? WHERE k='paper'\", (json.dumps(s),)); c.commit()"
for _ in $(seq 1 60); do [ "$(grep ^GENERATION= config/redrock.env | cut -d= -f2)" = 2 ] && break; sleep 5; done
sleep 60
echo "  $(grep ^GENERATION= config/redrock.env) · lignée : $(find data/lineage -mindepth 1 -maxdepth 1 -printf '%f ')"
state
curl -s -H "X-Chat-Key: $K" "http://127.0.0.1:8750/api/inbox?after=0" | python3 -c "import sys,json; [print('  boîte de réception :', i.get('level'), i.get('title')) for i in json.load(sys.stdin).get('items', [])]"

echo "=== 5. passage en argent réel (compte inventé, vide)"
A=0x$(openssl rand -hex 20); KK=0x$(openssl rand -hex 32)
inst /tmp/i4.log "o\n%s\n\nlive\n%s\n%s\no\n\n\n\n\n\n\n\n\n\n" "$KEY" "$A" "$KK"
sleep 10; state; echo "  $(grep -E '^(MODE|GENERATION)=' config/redrock.env | tr '\n' ' ') · archives : $(find data -maxdepth 1 -name 'archive-*' | tr '\n' ' ')"
echo "  tâches : $(jobs) · lignes crontab : $(lines)"
sleep 70; echo "  surveillance : $(tail -n 2 data/watchdog.log 2>/dev/null | tr '\n' ' ')"; state

echo "=== 6. retour en simulation"
inst /tmp/i5.log "o\n%s\n\npaper\n\no\n\n\n\n\n\n\n\n\n\n" "$KEY"
sleep 10; state; echo "  $(grep -E '^(MODE|GENERATION)=' config/redrock.env | tr '\n' ' ')"
echo "  services : $(docker compose ps --format '{{.Service}}={{.State}}' | tr '\n' ' ')"
echo "  Tailscale toujours là : $(grep ^TS_LOGINS= config/chat.env) · socket : $(code --unix-socket "$SOCK" -H "$TS" http://ts/api/chat/history)"
echo "=== fin"
