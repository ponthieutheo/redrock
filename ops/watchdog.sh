#!/bin/sh
# Cron de l'hôte (chaque minute, installé par install.sh) : quand le broker déclare la mort, on arrête l'agent,
# on prévient dans l'app (boîte de réception + notification), et si du capital reste, la génération suivante naît.
# Une mort par capital épuisé attend un rechargement manuel (puis : ops/rebirth.sh).
cd "$(dirname "$0")/.." || exit 1
[ -f data/broker/DEAD ] || exit 0
[ "$(docker compose ps -q --status running agent 2>/dev/null)" ] || exit 0
val() { grep "^$1=" "$2" 2>/dev/null | head -n1 | cut -d= -f2-; }
GEN=$(val GENERATION config/redrock.env); GEN=${GEN:-1}
MODE=$(val MODE config/redrock.env)
CAUSE=$(cat data/broker/DEAD)
KEY=$(val CHAT_KEY config/chat.env)
PORT=$(val REDROCK_PORT .env); PORT=${PORT:-8750}
notify() {  # dépose le message dans la boîte de réception de l'app (chat + notification push)
  body=$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps({"title": sys.stdin.read()[:120], "source": "alerte", "level": "alert"}))' 2>/dev/null) || return 0
  curl -s -m 10 -o /dev/null -X POST "http://127.0.0.1:$PORT/api/inbox/notify" \
       -H "Content-Type: application/json" -H "X-Chat-Key: $KEY" -d "$body" || true
}
notify "☠️ RedRock génération $GEN est mort : $CAUSE"
docker compose stop agent >/dev/null 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) génération $GEN morte ($CAUSE) : agent arrêté" >> data/watchdog.log
case "$CAUSE" in
  capital*) exit 0 ;;   # plus de capital : on attend un rechargement manuel
esac
if [ "$MODE" = "live" ]; then
  SUB=$(val HL_SUBACCOUNT config/redrock.env)
  EQ=$(curl -s -m 15 https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
       -d "{\"type\":\"spotClearinghouseState\",\"user\":\"$SUB\"}" \
       | python3 -c "import sys,json;print(sum(float(b['total']) for b in json.load(sys.stdin)['balances'] if b['coin']=='USDC'))" 2>/dev/null)
  python3 -c "import sys; sys.exit(0 if float('${EQ:-0}') >= 10 else 1)" || exit 0
fi
if ./ops/rebirth.sh >> data/watchdog.log 2>&1; then
  sleep 45
  NEW=$(val GENERATION config/redrock.env)
  notify "🐣 Génération $NEW est née. Mémoire vierge ; elle hérite du journal, des trades et de l'autopsie de ses ancêtres."
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) échec de ops/rebirth.sh" >> data/watchdog.log
fi
