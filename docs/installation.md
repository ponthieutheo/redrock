# Installer RedRock

Compte 10 minutes. Tu peux tout faire en simulation, sans argent réel ni compte Hyperliquid.

## 1. Ce qu'il te faut

- Une machine allumée en continu : un PC, un mini-PC, un Raspberry Pi 5 (8 Go) ou un petit serveur Linux.
  RedRock ne vit que si sa machine tourne.
- [Docker](https://docs.docker.com/get-docker/) avec Docker Compose v2 (inclus dans Docker Desktop).
  Vérifie : `docker compose version`.
- Une clé [OpenRouter](https://openrouter.ai/keys) avec quelques dollars de crédit : c'est le cerveau de l'agent.
  Compte de l'ordre d'un à quelques dollars par jour selon le modèle.
- Pour l'argent réel seulement : un compte [Hyperliquid](https://app.hyperliquid.xyz) (voir l'étape 4).

Sous Windows, passe par **WSL** (Ubuntu) avec Docker Desktop démarré et son intégration WSL activée : clone
RedRock dans ton dossier Linux (`~/redrock`, pas sous `/mnt/c`) et lance `./install.sh` depuis le terminal Ubuntu.
Git Bash est déconseillé : il donne des identifiants d'utilisateur Windows (`id -u` = 197xxx) qui se retrouvent
dans les droits des conteneurs, et il n'a pas de `crontab` pour la surveillance.

## 2. Récupérer RedRock

```bash
git clone https://github.com/ponthieutheo/redrock.git
cd redrock
```

## 3. Lancer l'installation

```bash
./install.sh
```

Le script pose quelques questions. Pour chacune, Entrée garde la valeur proposée.

| Question | Conseil |
|---|---|
| Clé OpenRouter | colle ta clé `sk-or-…` (elle ne s'affiche pas pendant la saisie) |
| Modèle | garde la valeur proposée au début ; tu pourras changer depuis le chat avec `/model` |
| Mode | **paper** (simulation) pour commencer |
| Capital simulé | 100 $ par exemple |
| Perte maximale | 0.35 = il meurt s'il perd 35 % depuis son plus haut |
| Adresse d'écoute, port | garde `127.0.0.1` et `8750` (voir [SECURITY.md](../SECURITY.md)) |
| Accès depuis ton téléphone par Tailscale ? | Linux seulement, « n » par défaut. « o » : ton identifiant Tailscale (`toi@example.com`), puis le port HTTPS (443). Le téléphone ouvre l'app sans code ; voir l'étape 5 |

Ensuite il génère la configuration, construit et lance les trois services, crée les tâches planifiées de
l'agent (un cycle de trading par heure, une revue par jour) et installe la surveillance de la mort et de la
relève. À la fin, il affiche :

- l'adresse de l'app (par défaut `http://127.0.0.1:8750`) ;
- **le lien d'appairage**, à ouvrir une fois sur chaque appareil (il contient ton code d'accès).

Pour vérifier ce que ferait le script sans rien écrire : `./install.sh --dry-run`.

## 4. Passer à l'argent réel (plus tard)

Fais-le seulement après avoir regardé l'agent travailler en simulation.

1. Sur Hyperliquid, crée un **sous-compte** dédié et mets-y une petite somme que tu acceptes de perdre.
2. Crée une **clé d'API wallet** (More → API) : elle peut trader, pas retirer. **Jamais la clé principale.**
3. Relance `./install.sh`, réponds « o » pour reconfigurer, choisis **live**, puis donne l'adresse du
   sous-compte et la clé d'API wallet.

Changer de mode fait repartir RedRock de zéro (génération 1) : les chiffres de la simulation ne valent rien
pour l'argent réel. L'historique de la simulation est archivé dans `data/archive-paper-…/`, la mémoire de
l'agent et le code d'accès de l'app sont gardés. Relancer `./install.sh` sans changer de mode garde tout.

## 5. Ouvrir l'app sur ton téléphone

Voir [usage.md](usage.md#sur-ton-téléphone). En bref : un réseau privé comme Tailscale, puis
« Installer l'application » (Android) ou « Sur l'écran d'accueil » (iPhone).

Si tu as répondu « o » à la question Tailscale, l'installateur affiche (et lance si tu veux) la commande qui
relie Tailscale à l'app :

```bash
sudo tailscale serve --bg --https=443 unix:$PWD/data/sock/dash.sock
```

Ton téléphone ouvre alors l'adresse `https://…` de `tailscale serve status` sans code d'accès. C'est sûr parce
que l'identité Tailscale n'est crue que par ce socket Unix, jamais par le port 8750 (détails dans
[SECURITY.md](../SECURITY.md#connexion-sans-code-par-tailscale)). Pour revenir en arrière :
`sudo tailscale serve --https=443 off`. Le code d'accès marche toujours.

Sous Windows ou macOS (Docker Desktop), cette option n'est pas proposée : l'hôte ne peut pas ouvrir un socket
créé dans un conteneur. Utilise le code d'accès avec `tailscale serve --bg 8750`.

## Commandes utiles

| Pour | Commande |
|---|---|
| voir l'état des services | `docker compose ps` |
| suivre les journaux | `docker compose logs -f --tail 50` |
| arrêter / relancer | `docker compose stop` / `docker compose up -d` |
| mettre à jour | `git pull && docker compose up -d --build` |
| réafficher le lien d'appairage | `python3 ops/pair.py http://127.0.0.1:8750` |
| forcer la naissance de la génération suivante (après une mort) | `sh ops/rebirth.sh` |

## Où sont les données

| Dossier | Contenu |
|---|---|
| `config/` | règles, compte, code d'accès de l'app (droits 600) |
| `secrets/` | clé de trading, lue par le broker seul (droits 600) |
| `data/broker/` | base du broker : trades, journal, courbe, état vital |
| `data/hermes/` | l'agent : mémoire, sessions, tâches planifiées, personnalité (`SOUL.md`) |
| `data/lineage/` | les archives des générations mortes |
| `data/dash/` | l'app : boîte de réception, notifications |
| `data/sock/` | le socket de l'app pour `tailscale serve` (droits 700, rien à sauvegarder) |

Sauvegarde ces dossiers avant toute manipulation. Pour tout désinstaller : `docker compose down`, puis
supprime le dossier.

## En cas de souci

- **« Docker ne répond pas »** : démarre Docker Desktop (ou `sudo systemctl start docker`), puis relance.
- **L'app affiche « code d'accès requis »** : ouvre le lien d'appairage, ou colle le code (`CHAT_KEY` dans
  `config/chat.env`).
- **L'agent ne répond pas dans le chat** : `docker compose logs agent --tail 50`. Vérifie le crédit OpenRouter.
- **Il est mort** : c'est le jeu. La surveillance fait naître la génération suivante tant qu'il reste du
  capital ; sinon recharge le sous-compte, puis `sh ops/rebirth.sh`.
