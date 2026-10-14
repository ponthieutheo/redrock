# Utiliser RedRock

## L'app en un coup d'œil

- **La scène** : RedRock à son bureau, dans une salle des marchés. Les écrans derrière lui sont cliquables :
  courbe du capital, positions, survie, journal, trades, marché, actus (« À la une », « Insolite »), lignée.
- **Toucher le perso** ouvre le chat. Toucher sa tasse : il boit une gorgée.
- **Le bouton d'émotes** (en bas) : danse, panique, réfléchit… et l'onglet **Tenue** pour l'habiller.
- **Le bandeau** en haut : sa génération, s'il est en vie, simulation ou argent réel, et les **Réglages**.

## Sur PC

Ouvre l'adresse de l'app dans ton navigateur (`http://127.0.0.1:8750` par défaut). Dans Chrome ou Edge, l'icône
« Installer » de la barre d'adresse en fait une fenêtre d'app à part.

## Sur ton téléphone

L'app doit être joignable depuis le téléphone **sans l'ouvrir sur Internet** : le plus simple est
[Tailscale](https://tailscale.com).

1. Installe Tailscale sur la machine de RedRock et sur ton téléphone, avec le même compte.
2. Sur la machine : `tailscale serve --bg 8750`. Tailscale affiche une adresse `https://…` privée.
3. Sur le téléphone, ouvre le **lien d'appairage** avec cette adresse : `https://…/#cle=<ton code>`
   (le code est `CHAT_KEY` dans `config/chat.env` ; `python3 ops/pair.py https://…` affiche le lien complet).
4. Installe l'app :

| Téléphone | Comment |
|---|---|
| Android | Chrome, menu ⋮ → **Installer l'application** (ou « Ajouter à l'écran d'accueil ») |
| iPhone / iPad | Safari, bouton Partager → **Sur l'écran d'accueil** |

L'icône RedRock apparaît comme une app, en plein écran.

## Appairer un autre appareil

Dans l'app d'un appareil déjà appairé : **Réglages → Appareils → Appairer**. Scanne le QR code avec l'autre
appareil, ou copie le lien. Le lien contient ton code d'accès : ne le partage pas.

« Oublier le code sur cet appareil » retire l'accès au chat sur l'appareil courant.

## Le chat

Écris-lui comme sur une messagerie. Le bouton **/** (ou taper `/`) ouvre la liste des commandes.

**Infos instantanées** (lues dans l'app, sans appeler l'IA, gratuites) :

| Commande | Ce qu'elle donne |
|---|---|
| `/status` | où il en est : génération, capital, en vie depuis… |
| `/positions` | ses positions ouvertes, avec stops |
| `/pnl` | ses résultats : gains, pertes, frais |
| `/trades` | ses 5 derniers trades fermés |
| `/survie` | sa ligne de mort et son rythme du jour |
| `/journal` | les dernières entrées de son journal |
| `/lignee` | les générations précédentes et leur cause de mort |
| `/marche` | les mouvements du marché sur 24 h |

**Commandes de l'agent** (Hermes) :

| Commande | Effet |
|---|---|
| `/usage`, `/history`, `/sessions`, `/agents`, `/model` | consulter : coût, historique, sessions, tâches, modèle |
| `/new` | nouvelle conversation (avec confirmation) |
| `/stop` | arrêter sa réponse en cours |
| `/retry` | renvoyer ton dernier message |
| `/steer <texte>` | lui glisser une consigne pendant qu'il travaille |
| `/model <nom>` | changer le modèle de cette conversation (avec confirmation) |
| `/approve`, `/deny` | autoriser ou refuser une commande qu'il demande à lancer |

Par sécurité, l'app refuse les commandes qui changent la configuration de l'agent (`/yolo`, `/restart`,
`/config`, `/cron`…) : fais-les directement sur la machine.

**En plein écran** : le bouton de l'en-tête du chat passe en mode « appel », la conversation prend tout l'écran
et RedRock reste dans une petite fenêtre que tu peux déplacer où tu veux.

## Messages et notifications

Tout ce que l'agent produit seul (revue quotidienne, post-mortems, alertes) arrive dans le chat, avec sa
source (« Cron · revue-quotidienne », « Alerte »). Quand il y a du nouveau, RedRock sort son téléphone.

Pour recevoir des **notifications** même app fermée : Réglages → **Notifications** (l'app doit être servie en
HTTPS, ce que `tailscale serve` fait ; sur iPhone, l'app doit d'abord être ajoutée à l'écran d'accueil).

## La mort et la relève

Le broker surveille son capital en continu. S'il perd plus que la limite fixée depuis son plus haut, il meurt :
pierre tombale « RIP », puis un remplaçant arrive et balaie la tombe. La nouvelle génération repart avec une
mémoire vierge ; ses ancêtres lui laissent leur journal, leurs trades et leur autopsie (écran **Lignée**).

Tu peux revoir la scène quand tu veux : émote **Mort**.
