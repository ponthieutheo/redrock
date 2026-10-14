#!/bin/sh
# Teste l'installation de bout en bout sur une machine Linux NEUVE (Ubuntu 24.04 + Docker), recréée dans un conteneur
# sur ta machine : clone du dépôt, ./install.sh au clavier, app, chat, Tailscale (simulé), mort et renaissance en
# simulation, passage au réel avec un compte inventé et vide, retour en simulation.
# Rien ne sort de ta machine et aucun compte réel n'est utilisé (clé OpenRouter factice).
#
#   sh tests/install/run.sh          depuis la racine du dépôt (Docker démarré, ~3 Go de disque, ~15 min)
#   KEEP=1 sh tests/install/run.sh   garde la machine de test à la fin (docker exec -it rr-test bash)
#
# Teste la version COMMITÉE (HEAD) : commite d'abord ce que tu veux tester.
set -e
cd "$(dirname "$0")/../.."
command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 || { echo "Docker est requis et doit être démarré." >&2; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no 2>/dev/null)" ] || echo "Attention : des modifications non commitées ne seront pas testées (seul HEAD l'est)."
D=$(mktemp -d)
git bundle create "$D/redrock.bundle" HEAD 2>/dev/null
win() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }   # Git Bash : chemins Windows pour docker.exe
docker build -q -t redrock-machine-neuve tests/install >/dev/null
docker rm -f rr-test >/dev/null 2>&1 || true; docker volume rm rr-test-docker >/dev/null 2>&1 || true
cleanup() { [ "${KEEP:-0}" = 1 ] || { docker rm -f rr-test >/dev/null 2>&1; docker volume rm rr-test-docker >/dev/null 2>&1; }; rm -rf "$D"; }
trap cleanup EXIT
docker run -d --privileged --name rr-test -v rr-test-docker:/var/lib/docker redrock-machine-neuve >/dev/null
sleep 8
export MSYS_NO_PATHCONV=1
docker cp "$(win "$D/redrock.bundle")" rr-test:/tmp/redrock.bundle
docker cp "$(win tests/install/scenario.sh)" rr-test:/home/ubuntu/scenario.sh
docker exec rr-test sh -c 'chmod 644 /tmp/redrock.bundle; chown ubuntu /home/ubuntu/scenario.sh; cd /home/ubuntu && sudo -u ubuntu git clone -q /tmp/redrock.bundle redrock'
docker exec rr-test sudo -u ubuntu -H bash /home/ubuntu/scenario.sh
# vu de l'hôte : root (comme tailscaled) ouvre le socket de l'app ; un autre utilisateur de la machine, non
docker exec rr-test bash -c '
S=/home/ubuntu/redrock/data/sock/dash.sock
echo "=== socket Tailscale vu des autres comptes de la machine"
echo "  root (= tailscaled), compte autorisé : $(curl -s -o /dev/null -m 10 -w %{http_code} --unix-socket $S -H "Tailscale-User-Login: alex@example.com" http://ts/api/chat/history) (attendu 200)"
echo "  autre utilisateur (nobody) : $(su nobody -s /bin/sh -c "curl -s -o /dev/null -m 10 -w %{http_code} --unix-socket $S http://ts/; echo \" (curl \$?)\"") (attendu 000, curl 7 : refusé)"'
echo "Terminé. Cherche « ✗ » ou « ATTENTION » ci-dessus : il ne doit y en avoir aucun."
