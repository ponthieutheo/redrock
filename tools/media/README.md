# Médias du README public

Captures, aperçu animé et vidéos de `docs/media/` (les vidéos sont publiées comme vidéos jointes GitHub, lues
directement dans le README ; elles ne sont pas dans le dépôt).

**Aucune donnée réelle.** L'app filmée est celle du dépôt (`dash/`), branchée sur une fausse API (`server.py`) dont
toutes les réponses viennent de `fixtures.py` : capital, trades, journal, actus, chat, tout est inventé. Ne jamais
brancher ces scripts sur un vrai compte ou un vrai serveur. Avant de publier, regarder chaque image.

## Tout refaire (après un changement de design)

```
python -I -X utf8 tools/media/build.py                          # ~4 min avec la carte graphique
python -I -X utf8 tools/media/build.py --only teaser installation
```

Il faut : Python 3 avec `playwright`, `numpy`, `scipy`, `Pillow` ; Google Chrome ; ffmpeg (variable `FFMPEG`,
PATH ou WinGet) avec libx264, aac, libmp3lame, loudnorm, ebur128 ; Internet pour les polices Google.
Sans carte graphique : `--soft` (SwiftShader, bien plus lent).

`build.py` s'arrête au moindre défaut ; il laisse dans `tools/media/out/` :
- `teaser-musique.mp3` : la musique du teaser seule, pour l'écouter (dans le dépôt) ;
- `planches/*.jpg` : une image toutes les 0,25 s, horodatée, à regarder une par une avant de committer ;
- `*-controle.json` : l'état de chaque image (voir « Contrôles »). Ces deux derniers ne sont pas committés.

| Fichier | Contenu | Fabriqué par |
|---|---|---|
| `scene-pc.png` | la salle en 1440×900, il dit bonjour | `capture.py` |
| `scene-tel.png`, `chat-tel.png` | téléphone 390×844 ×2 : la salle ; le chat avec `/status` et une réponse | `capture.py` |
| `mort.png` | la relève : tombe « GÉN. 3 », la génération 4 arrive | `capture.py` |
| `apercu.webp` | 12 s en boucle, 720×450 : toucher le perso, chat, `/status`, question, réponse | `render.py apercu` + `apercu.html` |
| `teaser.mp4` | 22 s, 1080p, ≤ 8 Mo : accroche, titre, la salle, le chat, PC / TV / téléphone, la mort, la relève, carte de fin | `render.py teaser` + `teaser.html` + `music.py` |
| `teaser-poster.png` | 1280×720 : le trio PC, TV, téléphone, nom, bouton lecture (affiche du README) | `render.py teaser --poster 13.9` |
| `installation.mp4` | 28,5 s, 1080p : `./install.sh` (vrais textes, question Tailscale comprise ; clé et code masqués), puis l'app | `render.py installation` + `install.html` + `music.py` |

## Le teaser (22 s, 120 BPM : un temps = 0,5 s, une mesure = 2 s)

Les instants sont dans `teaser.html` (`T`) et dans `music.py` (`T`) : les modifier ensemble. Chaque coupe tombe sur un temps.

| Instant | Plan | Musique |
|---|---|---|
| 0 → 2 s | accroche : gros plan sur le perso, « Son capital, c'est sa vie. » | deux coups (0 et 1 s), pluck filtré |
| 2 → 4 s | titre : logo, REDROCK, « Un agent de trading autonome. » | impact, quatre temps, roulement |
| 4 → 6 s | la salle : « Il trade seul. » | groove complet (do) |
| 6 → 8 s | le chat : question tapée, réponse en direct (la bouche suit la réponse) | montée, souffle à 7,75 s |
| 8 → 9,5 s | écran d'ordinateur, navigateur : « Sur ton PC. » | refrain (la mineur), lead à l'octave |
| 9,5 → 11 s | téléviseur en mode TV (bandeau, il danse) : « Sur ta TV. » | |
| 11 → 13 s | téléphone : écran d'accueil, on touche l'icône, écran de lancement, l'app installée | « tap » à 11,4 s |
| 13 → 14 s | les trois ensemble : « Le même agent, partout. » | cymbale |
| 14 → 16 s | il panique : « S'il perd trop, » | accord de mi, montée, roulement |
| 16 → 18 s | sa mort (scène de l'app lancée à 15,8 s : yeux en croix à 16 s pile, il roule, la tombe « GÉN. 3 » surgit) : « il meurt. » | arrêt net, grondement, coup sourd (17 s), « plop » de la tombe |
| 18 → 20 s | la relève : le remplaçant tombe du ciel, le balai : « Le suivant prend la relève. » | refrain (la mineur) |
| 20 → 22 s | carte de fin : REDROCK, Open source, l'adresse GitHub, les licences | coup final, queue courte |

Le teaser est fait de trois parties (`render.py`, `COMPS["teaser"]["parts"]`), chacune une page neuve
(`teaser.html?part=salle|appareils|fin`) : le PC, la TV et le téléphone sont trois apps en même temps ; l'app
des parties 1 et 3 tourne en 1280×720 agrandie ×1,5 (interface et chat lisibles).

## Contrôles (aucune image fausse)

- **Le perso ne parle jamais quand il ne doit pas.** L'app appelle `window.talk` à chaque état (« Je suis mort… »,
  « Je vérifie mon compte… » pendant la relève) : les compositions la remplacent par une fonction vide et cachent
  la bulle (`C.noTalk` dans `comp.js`) ; la bouche ne bouge que pour la réponse du chat (6 → 8 s du teaser).
- **Chaque image est contrôlée** pendant le rendu (`COMP.probe` → `C.probe`) : bulle de parole (`.ov-say` avec la
  classe `on`, visible ou non), bouche qui parle (classe `talking` de `#arena`, synchro labiale en cours) hors des
  moments permis, bulle de pensée ou « Zzz », 3D éteinte, « undefined »/« NaN » à l'écran. Côté Python : image vide
  (noire, d'une seule couleur, pas encore dessinée) et saut brutal d'une image à l'autre hors des coupes et
  mouvements prévus (`COMP.cuts`, `COMP.moves`). Un seul défaut et `render.py` échoue (code 1).
- **Le son est mesuré** : `music.py` refuse tout son qui ne commence ou ne finit pas à zéro (clic garanti), cherche
  les clics restants (bouffées d'aigus sans note qui commence), normalise par ffmpeg `loudnorm` en deux passes
  linéaires (−14 LUFS, crête vraie ≤ −1,5 dBTP avant AAC) ; `verify.py audio|video` donne sonie, LRA, crête vraie,
  composante continue, écrêtage, bandes de fréquences, et le format des vidéos (H.264, yuv420p, faststart).

## Comment ça marche

- `inject.js` met l'app en **temps virtuel** (horloge, minuteries, animations CSS) : chaque image est calculée
  au bon instant, la vitesse de la machine ne change rien et deux rendus donnent les mêmes images.
- Les compositions (`apercu.html`, `teaser.html`, `install.html`, outils dans `comp.js`) chargent l'app dans des
  iframes et la pilotent par ses crochets (`__chatOpen`, `__emote`, `__hatch`, `__zoom`, `tvOn`, `refresh`…) ;
  `render.py` capture chaque image, la contrôle, puis ffmpeg encode (CRF relevé tant que la vidéo dépasse 7,6 Mo).
  `render.py teaser --part fin --stills 16,18.5 --out DOSSIER` sort quelques images PNG pour vérifier un plan.
- Scénarios de `fixtures.py` (`vie`, `calme`, `fete`, `danger`, `mort`, `naissance`, `neuf`) : changer de scénario
  pendant un rendu fait réagir l'app comme en vrai (fête, panique, relève). Les moments choisis des captures sont
  dans `capture.py` (`--candidates` pour en voir d'autres).
- Musiques synthétisées par `music.py` (numpy, synthèse additive) : aucun échantillon, aucun son sous droits.
  La durée de la vidéo d'installation suit la fin du terminal (`render.py installation --duration`).
