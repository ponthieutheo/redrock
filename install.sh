#!/usr/bin/env bash
# Installe RedRock en une commande : ./install.sh
#
#   --dry-run   n'écrit rien et ne lance rien : affiche ce qui serait fait (secrets masqués)
#   --yes       accepte les valeurs par défaut sans poser de question (mode simulation)
#
# Variables reconnues (utile avec --yes) : OPENROUTER_API_KEY, REDROCK_MODEL, REDROCK_MODE (paper|live),
# PAPER_CAPITAL, HL_SUBACCOUNT, HL_AGENT_KEY, DD_TOLERANCE, REDROCK_BIND, REDROCK_PORT, REDROCK_TZ.
set -euo pipefail
cd "$(dirname "$0")"

DRY=0; YES=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --yes|-y) YES=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Option inconnue : $a" >&2; exit 2 ;;
  esac
done

R=$'\e[31m'; G=$'\e[32m'; B=$'\e[1m'; D=$'\e[2m'; N=$'\e[0m'
[ -t 1 ] || { R=""; G=""; B=""; D=""; N=""; }
say()  { printf '%s\n' "$*"; }
step() { printf '\n%s▸ %s%s\n' "$B" "$*" "$N"; }
ok()   { printf '  %s✓%s %s\n' "$G" "$N" "$*"; }
die()  { printf '%s✗ %s%s\n' "$R" "$*" "$N" >&2; exit 1; }
run()  { if [ "$DRY" = 1 ]; then printf '  %s[à blanc]%s %s\n' "$D" "$N" "$*"; else "$@"; fi; }

ask() {  # ask VAR "question" "défaut"
  local __v=$1 __q=$2 __d=${3:-} __r=""
  if [ -n "${!__v:-}" ]; then return; fi
  if [ "$YES" = 1 ] || [ ! -t 0 ]; then printf -v "$__v" '%s' "$__d"; return; fi
  read -r -p "  $__q${__d:+ [$__d]} : " __r || true
  printf -v "$__v" '%s' "${__r:-$__d}"
}
ask_secret() {  # ask_secret VAR "question" (vide autorisé)
  local __v=$1 __q=$2 __r=""
  if [ -n "${!__v:-}" ]; then return; fi
  if [ "$YES" = 1 ] || [ ! -t 0 ]; then printf -v "$__v" '%s' ""; return; fi
  read -r -s -p "  $__q : " __r || true; echo
  printf -v "$__v" '%s' "$__r"
}
rand() { if command -v openssl >/dev/null 2>&1; then openssl rand -hex 32; else python3 -c 'import secrets; print(secrets.token_hex(32))'; fi; }
mask() { local s=$1; [ -z "$s" ] && { echo "(vide)"; return; }; echo "${s:0:4}…(${#s} caractères)"; }
write() {  # write FICHIER MODE  (contenu sur l'entrée standard)
  local f=$1 m=$2 content; content=$(cat)
  if [ "$DRY" = 1 ]; then
    printf '  %s[à blanc]%s %s (droits %s) :\n' "$D" "$N" "$f" "$m"
    printf '%s\n' "$content" | sed -E 's/^((OPENROUTER_API_KEY|HL_AGENT_KEY|CHAT_KEY|HERMES_API_KEY|API_SERVER_KEY)=).+/\1•••/; s/^/      /'
  else
    umask 077; printf '%s\n' "$content" > "$f"; chmod "$m" "$f"
  fi
}

printf '%s\n' "${R}${B}"
cat <<'EOF'
   ____          _ ____            _
  |  _ \ ___  __| |  _ \ ___   ___| | __
  | |_) / _ \/ _` | |_) / _ \ / __| |/ /
  |  _ <  __/ (_| |  _ < (_) | (__|   <
  |_| \_\___|\__,_|_| \_\___/ \___|_|\_\
EOF
printf '%s\n' "$N  Un agent de trading autonome qui doit gagner sa vie. Installation."
[ "$DRY" = 1 ] && say "  ${D}Mode à blanc : rien ne sera écrit ni lancé.${N}"

step "Vérifications"
command -v docker >/dev/null 2>&1 || die "Docker est requis : https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 est requis (commande « docker compose »)."
if [ "$DRY" = 0 ]; then docker info >/dev/null 2>&1 || die "Docker est installé mais ne répond pas : démarre-le, puis relance."; fi
command -v curl >/dev/null 2>&1 || die "curl est requis."
ok "Docker et Docker Compose"
val() { grep "^$1=" "$2" 2>/dev/null | head -n1 | cut -d= -f2-; }
OLD_MODE=""; OLD_GEN=""; OLD_CHAT=""; OLD_API=""
if [ -f config/redrock.env ] && [ "$DRY" = 0 ]; then
  say "  RedRock semble déjà installé ici (config/redrock.env existe)."
  ask REINSTALL "Tout reconfigurer ? (o/N)" "n"
  case "$REINSTALL" in o|O|oui|y|yes) ;; *) say "  Rien n'a changé. Pour relancer : docker compose up -d"; exit 0 ;; esac
  # on garde la génération en cours et le code d'accès (les appareils restent appairés)
  OLD_MODE=$(val MODE config/redrock.env); OLD_GEN=$(val GENERATION config/redrock.env)
  OLD_CHAT=$(val CHAT_KEY config/chat.env); OLD_API=$(val HERMES_API_KEY config/chat.env)
fi

step "Cerveau de l'agent (fournisseur d'IA)"
say "  RedRock utilise OpenRouter par défaut (une clé, des centaines de modèles) : https://openrouter.ai/keys"
ask_secret OPENROUTER_API_KEY "Clé OpenRouter (sk-or-…)"
[ -n "$OPENROUTER_API_KEY" ] || [ "$DRY" = 1 ] || die "Sans clé d'IA, l'agent ne peut pas réfléchir."
ask REDROCK_MODEL "Modèle" "deepseek/deepseek-v4.1-flash"

step "Argent réel ou simulation"
say "  ${B}simulation${N} : ordres simulés sur les vrais prix, aucun risque. ${B}réel${N} : de vrais ordres sur Hyperliquid."
ask REDROCK_MODE "Mode (paper = simulation, live = réel)" "paper"
case "$REDROCK_MODE" in paper|live) ;; *) die "Mode inconnu : $REDROCK_MODE (paper ou live)." ;; esac
HL_SUBACCOUNT=${HL_SUBACCOUNT:-}; HL_AGENT_KEY=${HL_AGENT_KEY:-}; PAPER_CAPITAL=${PAPER_CAPITAL:-}
if [ "$REDROCK_MODE" = live ]; then
  say "  ${R}Argent réel.${N} Utilise un SOUS-COMPTE dédié avec un petit capital, et une clé d'« API wallet »"
  say "  (Hyperliquid > More > API) : elle peut trader mais pas retirer. ${B}Jamais la clé principale de ton wallet.${N}"
  ask HL_SUBACCOUNT "Adresse du sous-compte (0x…)"
  [[ "$HL_SUBACCOUNT" =~ ^0x[0-9a-fA-F]{40}$ ]] || die "Adresse invalide."
  ask_secret HL_AGENT_KEY "Clé privée de l'API wallet (0x…)"
  [[ "$HL_AGENT_KEY" =~ ^0x[0-9a-fA-F]{64}$ ]] || [ "$DRY" = 1 ] || die "Clé invalide."
else
  ask PAPER_CAPITAL "Capital de départ simulé (en \$)" "100"
  [[ "$PAPER_CAPITAL" =~ ^[0-9]+(\.[0-9]+)?$ ]] || die "Montant invalide."
  HL_SUBACCOUNT=${HL_SUBACCOUNT:-0x0000000000000000000000000000000000000000}
fi
RESET=0
if [ -n "$OLD_MODE" ] && [ "$OLD_MODE" != "$REDROCK_MODE" ]; then
  # Les chiffres de la simulation (plus haut, courbe, trades) ne valent rien pour l'argent réel, et inversement :
  # garder le plus haut simulé ferait mourir l'agent dès son premier passage si le vrai capital est plus petit.
  say "  Changement de mode ($OLD_MODE → $REDROCK_MODE) : RedRock repart de zéro, génération 1."
  say "  L'historique actuel (broker et lignée) est archivé dans data/archive-$OLD_MODE-…/ ; sa mémoire est gardée."
  ask RESET_OK "Continuer ? (o/N)" "n"
  case "$RESET_OK" in o|O|oui|y|yes) RESET=1 ;; *) say "  Rien n'a changé."; exit 0 ;; esac
fi

step "Règle de mort"
say "  Le broker tue l'agent si son capital tombe trop loin sous son plus haut. L'agent ne peut pas changer cette règle."
ask DD_TOLERANCE "Perte maximale depuis le plus haut, en fraction (0.35 = 35 %)" "0.35"
python3 -c "import sys; v=float(sys.argv[1]); sys.exit(0 if 0.05 <= v <= 0.9 else 1)" "$DD_TOLERANCE" 2>/dev/null \
  || [[ "$DD_TOLERANCE" =~ ^0\.[0-9]+$ ]] || die "Valeur invalide (entre 0.05 et 0.9)."

step "Accès à l'app"
say "  Par défaut l'app n'écoute que sur cette machine (127.0.0.1). Pour ton téléphone, passe par un VPN privé"
say "  (Tailscale, WireGuard…) plutôt que d'ouvrir un port sur Internet : voir SECURITY.md."
ask REDROCK_BIND "Adresse d'écoute" "127.0.0.1"
ask REDROCK_PORT "Port" "8750"
ask REDROCK_TZ "Fuseau horaire" "Europe/Paris"

step "Génération de la configuration"
CHAT_KEY=${OLD_CHAT:-$(rand)}; API_KEY=${OLD_API:-$(rand)}
GENERATION=${OLD_GEN:-1}
UID_=$(id -u); GID_=$(id -g)
if [ "$RESET" = 1 ]; then
  ARCH="data/archive-$OLD_MODE-$(date +%Y%m%d-%H%M%S)"
  run docker compose stop
  run mkdir -p "$ARCH"
  run mv data/broker data/lineage "$ARCH/"
  [ -f data/watchdog.log ] && run mv data/watchdog.log "$ARCH/"
  GENERATION=1
  ok "ancien historique archivé dans $ARCH"
fi
run mkdir -p config secrets data/broker data/dash data/lineage data/hermes/workspace data/hermes/cron data/hermes/logs data/hermes/toolbox
write .env 600 <<EOF
REDROCK_UID=$UID_
REDROCK_GID=$GID_
REDROCK_BIND=$REDROCK_BIND
REDROCK_PORT=$REDROCK_PORT
EOF
write config/redrock.env 600 <<EOF
# Règles et compte (lus par le broker et par l'app ; la clé de trading n'est PAS ici)
MODE=$REDROCK_MODE
GENERATION=$GENERATION
HL_SUBACCOUNT=$HL_SUBACCOUNT
PAPER_CAPITAL=$PAPER_CAPITAL
DEATH_EQUITY=1
TRAJ_RULE=on
DEATH_MODE=drawdown
DD_TOLERANCE=$DD_TOLERANCE
DAILY_TARGET_PCT=1
OPENROUTER_API_KEY=$OPENROUTER_API_KEY
EOF
write secrets/broker.env 600 <<EOF
# Seul le broker lit ce fichier. Clé d'API wallet Hyperliquid (vide en simulation).
HL_AGENT_KEY=$HL_AGENT_KEY
EOF
write config/chat.env 600 <<EOF
# Code d'accès de l'app (chat et commandes) et clé de l'API interne de l'agent
CHAT_KEY=$CHAT_KEY
HERMES_API_KEY=$API_KEY
EOF
write data/hermes/.env 600 <<EOF
OPENROUTER_API_KEY=$OPENROUTER_API_KEY
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_KEY=$API_KEY
EOF
if [ "$DRY" = 1 ]; then
  say "  ${D}[à blanc]${N} agent/config.yaml -> data/hermes/config.yaml (modèle $REDROCK_MODEL, fuseau $REDROCK_TZ)"
  say "  ${D}[à blanc]${N} agent/SOUL.md -> data/hermes/SOUL.md"
else
  sed -e "s|__MODEL__|$REDROCK_MODEL|" -e "s|__TZ__|$REDROCK_TZ|" agent/config.yaml > data/hermes/config.yaml
  [ -f data/hermes/SOUL.md ] || cp agent/SOUL.md data/hermes/SOUL.md
  [ -f data/broker/BORN ] || date -u +%Y-%m-%dT%H:%M:%SZ > data/broker/BORN
fi
ok "config/redrock.env, secrets/broker.env, config/chat.env, data/hermes/ (droits 600)"
ok "Code d'accès de l'app : $(mask "$CHAT_KEY")"

step "Démarrage"
run docker compose up -d --build
if [ "$DRY" = 0 ]; then
  printf '  attente de l'"'"'agent'
  for _ in $(seq 1 60); do
    if docker compose exec -T agent true >/dev/null 2>&1 && [ -d data/hermes/cron ]; then break; fi
    printf '.'; sleep 2
  done; echo
fi
[ "$DRY" = 1 ] || ok "broker, agent et app lancés"

step "Tâches planifiées de l'agent"
CYCLE="Cycle de trading. 1) account : ta vie, ta ligne de mort, tes positions et leurs stops. 2) Gère l'existant : la raison de chaque position tient-elle ? Sinon ferme (close_position). 3) N'ouvre une position que pour une raison chiffrée, risque petit, stop posé. Sinon ne fais rien : rester sans position n'est pas une faute. 4) Termine par write_journal : ce que tu as vu, décidé, et pourquoi. Sois économe en appels."
REVUE="Revue quotidienne. 1) scorecard puis history : tes vrais résultats, frais et funding inclus. 2) Pour chaque trade des dernières 24 h : erreur de raisonnement, mauvaise exécution, ou variance ? 3) Garde ce qui marche, arrête ce qui ne marche pas, note tes leçons chiffrées (add_lesson). 4) Écris ta revue dans le journal."
cron() {  # cron NOM PLANNING CONSIGNE
  if [ "$DRY" = 1 ]; then printf '  %s[à blanc]%s hermes cron create "%s" … --name %s\n' "$D" "$N" "$2" "$1"; return; fi
  # liste lue d'abord, puis cherchée sans tube : avec « pipefail », « … | grep -q » échoue parfois alors que la tâche
  # existe (grep s'arrête au premier résultat, la commande d'avant reçoit SIGPIPE) et on créait un doublon
  local jobs; jobs=$(docker compose exec -T -u "$UID_:$GID_" agent hermes cron list 2>/dev/null || true)
  if grep -qF -- "$1" <<<"$jobs"; then ok "$1 (déjà là)"; return; fi
  if docker compose exec -T -u "$UID_:$GID_" agent hermes cron create "$2" "$3" --name "$1" >/dev/null; then
    ok "$1 ($2)"
  else
    say "  ${R}!${N} $1 non créée : crée-la avec « docker compose exec agent hermes cron create »."
  fi
}
cron cycle-trading "every 60m" "$CYCLE"
cron revue-quotidienne "0 8 * * *" "$REVUE"   # expression cron, lue dans le fuseau de config.yaml (« every 1d at … » est refusé)

step "Surveillance de la mort et de la relève"
if command -v crontab >/dev/null 2>&1; then
  LINE="* * * * * cd $PWD && sh ops/watchdog.sh >/dev/null 2>&1"
  if [ "$DRY" = 1 ]; then say "  ${D}[à blanc]${N} crontab : $LINE"
  elif grep -qF "ops/watchdog.sh" <<<"$(crontab -l 2>/dev/null || true)"; then ok "déjà en place"
  else (crontab -l 2>/dev/null; echo "$LINE") | crontab - && ok "ops/watchdog.sh chaque minute (crontab)"; fi
else
  say "  crontab absent : lance « sh ops/watchdog.sh » chaque minute avec ton planificateur."
fi

URL="http://$([ "$REDROCK_BIND" = 0.0.0.0 ] && echo localhost || echo "$REDROCK_BIND"):$REDROCK_PORT"
step "C'est prêt"
say "  App          : ${B}$URL${N}"
say "  Appairage    : ouvre une fois ce lien sur chaque appareil (il contient ton code d'accès, ne le partage pas)"
say "                 ${B}$URL/#cle=$( [ "$DRY" = 1 ] && echo '•••' || echo "$CHAT_KEY")${N}"
if [ "$DRY" = 0 ] && command -v qrencode >/dev/null 2>&1; then qrencode -t ansiutf8 "$URL/#cle=$CHAT_KEY"; fi
say "  Téléphone    : Android (Chrome) menu ⋮ > « Installer l'application » ; iPhone (Safari) Partager > « Sur l'écran d'accueil »."
say "  Autres appareils : dans l'app, Réglages > Appareils > Appairer (QR code)."
say "  Guide        : docs/usage.md   ·   Sécurité : SECURITY.md"
[ "$REDROCK_MODE" = live ] && say "  ${R}Argent réel : RedRock peut perdre tout son capital. Ce n'est pas un conseil financier.${N}"
exit 0
