# Sécurité

RedRock pilote un agent qui peut passer des ordres et exécuter des commandes. Ces règles évitent qu'un inconnu
le fasse à ta place.

## Ce que l'installation fait pour toi

- **L'app n'écoute que sur ta machine** (`127.0.0.1:8750`). L'agent et le broker n'ont aucun port publié : ils
  ne sont joignables que sur le réseau interne de Docker.
- **Le chat et les commandes demandent un code d'accès** (`CHAT_KEY`, 64 caractères aléatoires, généré par
  `install.sh`). Les écrans en lecture seule (courbe, positions, actus) restent visibles sans code.
- **La clé de trading n'est lue que par le broker** (`secrets/broker.env`, droits 600). Ni l'agent ni l'app n'y
  ont accès. L'agent n'agit sur le marché que par les outils du broker, qui imposent les garde-fous.
- **La règle de mort est hors de portée de l'agent** : elle est appliquée par le broker, dans un autre conteneur.
- **Les fichiers de configuration sont en droits 600.**

## Appairer un appareil

Le lien d'appairage `https://…/#cle=…` contient ton code d'accès. Il voyage dans le fragment de l'adresse (après
`#`), que le navigateur n'envoie jamais au serveur ; l'app l'enregistre puis l'efface de la barre d'adresse.

- Ne partage jamais ce lien ni le QR code.
- Pour retirer un appareil : Réglages → Appareils → « Oublier le code sur cet appareil ».
- Si le code a fuité : remplace `CHAT_KEY` dans `config/chat.env`, puis `docker compose up -d dash`, et
  réappaire tes appareils.

## Accéder à l'app depuis ton téléphone

**N'ouvre pas le port de l'app sur Internet.** Utilise un réseau privé :

- [Tailscale](https://tailscale.com) (le plus simple) : installe-le sur la machine et le téléphone, puis
  `tailscale serve --bg 8750` donne une adresse HTTPS privée à ton tailnet.
- ou WireGuard, ou un tunnel SSH.

Les notifications et l'installation en app (PWA) demandent HTTPS : `tailscale serve` le fournit.

Si tu dois quand même exposer l'app, mets-la derrière un reverse proxy HTTPS avec une authentification en plus
du code d'accès, et garde le code secret.

## Le terminal de l'agent

Hermes peut exécuter des commandes (`terminal.backend`). Dans RedRock, il les exécute **dans son propre
conteneur**, qui sert de bac à sable : pas de socket Docker monté, pas de port publié, pas d'accès aux secrets
du broker ni aux fichiers de ta machine hors de `data/hermes/`.

Ne monte pas `/var/run/docker.sock` dans le conteneur de l'agent (le backend `docker` de Hermes le demande) :
l'accès au socket Docker équivaut à un accès administrateur à ta machine.

## Clé Hyperliquid (argent réel)

- Crée un **sous-compte dédié** avec un petit capital.
- Utilise une clé d'**API wallet** (Hyperliquid → More → API) : elle peut trader, pas retirer.
- **Jamais la clé principale de ton wallet.**

## Contenu externe

Les actualités et pages web que lit l'agent sont du contenu non fiable. Le broker les marque comme tel et la
personnalité de l'agent lui interdit d'en suivre les instructions, mais aucune protection contre l'injection de
consignes n'est parfaite : c'est une raison de plus pour limiter le capital.

## Signaler une faille

Ouvre une issue **sans détails exploitables** en demandant un contact privé, ou utilise
« Report a vulnerability » (GitHub Security Advisories) sur le dépôt.
