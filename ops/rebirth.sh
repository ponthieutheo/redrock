#!/bin/sh
# Archive la génération morte et fait naître la suivante, avec une mémoire vierge.
# Lancé par ops/watchdog.sh (ou à la main) depuis la racine du dépôt RedRock.
set -eu
cd "$(dirname "$0")/.."
[ -f data/broker/DEAD ] || { echo "La génération actuelle n'est pas morte. Abandon."; exit 1; }
GEN=$(grep '^GENERATION=' config/redrock.env | cut -d= -f2)
GEN=${GEN:-1}
A="data/lineage/gen$GEN"
mkdir -p "$A"
docker compose stop agent broker
[ -f "data/broker/autopsy_gen$GEN.json" ] && cp "data/broker/autopsy_gen$GEN.json" "$A/autopsy.json"
# trades, journal et courbe de la génération morte ; on remet à zéro l'état vital du broker
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/data/broker:/d" -v "$PWD/$A:/o" python:3.12-slim python -c "
import sqlite3, json
c = sqlite3.connect('/d/redrock.db'); c.row_factory = sqlite3.Row
for t in ('trades', 'journal', 'equity'):
    json.dump([dict(r) for r in c.execute(f'SELECT * FROM {t} WHERE gen=$GEN')], open(f'/o/{t}.json', 'w'), indent=1, ensure_ascii=False, default=str)
c.execute(\"DELETE FROM meta WHERE k IN ('dead','paper','born','death_cause','live_pending','day_ref','traj','freeze','guard_events','peak')\"); c.commit()"
# sa mémoire et son espace de travail partent aux archives ; le successeur repart à zéro (config, SOUL, .env, crons conservés)
cp -r data/hermes/memories "$A/memory" 2>/dev/null || true
cp -r data/hermes/workspace "$A/workspace" 2>/dev/null || true
docker run --rm -v "$PWD/data/hermes:/h" alpine sh -c "rm -rf /h/memories /h/sessions /h/state.db /h/state.db-shm /h/state.db-wal /h/workspace/*"
rm -f data/broker/DEAD
sed -i.bak "s/^GENERATION=.*/GENERATION=$((GEN + 1))/" config/redrock.env && rm -f config/redrock.env.bak
date -u +%Y-%m-%dT%H:%M:%SZ > data/broker/BORN
docker compose up -d
echo "Génération $((GEN + 1)) née. Archives de la $GEN dans $A"
