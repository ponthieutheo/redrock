# Médias du README public

Captures, aperçu animé et vidéos de `docs/media/` (les vidéos sont publiées comme vidéos jointes GitHub, lues
directement dans le README ; elles ne sont pas dans le dépôt).

**Aucune donnée réelle.** L'app filmée est celle du dépôt (`dash/`), branchée sur une fausse API (`server.py`) dont
toutes les réponses viennent de `fixtures.py` : capital, trades, journal, actus, chat, tout est inventé. Ne jamais
brancher ces scripts sur un vrai compte ou un vrai serveur. Avant de publier, regarder chaque image.

## Tout refaire (après un changement de design)

```
python -I -X utf8 tools/media/build.py                          # ~6 min avec la carte graphique
python -I -X utf8 tools/media/build.py --only teaser installation
python -I -X utf8 tools/media/build.py --only teaser-vertical   # le teaser en 9:16 (TikTok, Shorts, Reels)
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
| `positions.png` | positions ouvertes (téléphone, deux colonnes) : LONG BTC, gain, graphique avec entrée / SL / TP, SL déplacé une fois, thèse dépliée (pourquoi, ce qui l'invalide, plan) | `capture.py` |
| `journal.png` | journal de pensée : un cycle déplié (ce qu'il voit, décision, pourquoi, ce qui le ferait changer d'avis), ouvertures, stops, fermetures avec leurs étiquettes `[setup:…]` `[src:…]` | `capture.py` |
| `suivi.png` | suivi : l'historique des trades (LONG / SHORT, TP / SL touché, résultat) et la feuille Survie jusqu'au miroir par type de setup (résultats réels, espérance, frais) | `capture.py` |
| `rejouer.webp` | « Rejouer le trade », 720 px, en boucle : bougies derrière le curseur, entrée, SL remonté trois fois en escalier, sortie au TP, résultat | `capture.py` |
| `apercu.webp` | 12 s en boucle, 720×450 : toucher le perso, chat, `/status`, question, réponse | `render.py apercu` + `apercu.html` |
| `teaser.mp4` | 26,5 s, 1920×1080, ≤ 8 Mo : le salut, les questions, le titre, il trade seul, le chat, l'enjeu, la mort, la relève, PC / TV / téléphone, carte de fin | `render.py teaser` + `teaser.html` + `music.py` |
| `teaser-vertical.mp4` | le même en 1080×1920 (TikTok, Shorts, Reels) : même musique, mêmes coupes, mise en page verticale dans les zones sûres | `render.py teaser-vertical` + `teaser.html?fmt=v` |
| `teaser-poster.png` | 1280×720 : le trio PC, TV, téléphone, tuile d'icône, nom, bouton lecture (affiche du README) | `render.py teaser --poster 23.5` |
| `installation.mp4` | 28,5 s, 1080p : `./install.sh` (vrais textes, question Tailscale comprise ; clé et code masqués), puis l'app | `render.py installation` + `install.html` + `music.py` |

## Le teaser (26,5 s, 120 BPM : un temps = 0,5 s, une mesure = 2 s), en 16:9 et en 9:16

Une seule composition pour les deux formats (`teaser.html`, `?fmt=v` pour la verticale) : même texte, mêmes
coupes, même musique. Les instants sont dans `teaser.html` (`T`) et dans `music.py` (`T`) : les modifier ensemble.
Chaque coupe et chaque mot qui claque tombe sur un temps.

| Instant | Plan | Texte à l'écran | Musique |
|---|---|---|---|
| 0 → 2 s | dès la 1re image le perso ; la caméra de l'app fonce sur lui (de toute la salle au visage), il se tourne vers nous et salue de la main (émote `salut` de l'app) | bulle « Salut ! » | premier coup, souffle, le cœur bat (« lub-dub »), le crochet au lead (0,5 s) |
| 2 → 4 s | le cadre glisse pour laisser la place au texte (verre flouté derrière) | « Et si une IA devait gagner sa vie ? » | charleston (le temps qui passe), 808 tenue |
| 4 → 6 s | il grimace, l'image s'assombrit | « …et mourir si elle échoue ? » | chute de sub, accord de mi, cymbale inversée et montée |
| 6 → 8 s | carte : tuile d'icône (lueur, reflet), VOICI REDROCK, traversée en zoom à 8 s | « Voici RedRock. Un agent de trading autonome. » | braam, chute de sub, accord supersaw, le crochet |
| 8 → 10 s | plongée de la caméra de l'app sur l'écran des positions (LONG / SHORT, SL, TP), puis les trades du jour ; filigrane d'icône | « Il trade seul, jour et nuit. » | trap en demi-temps, 808 qui glisse, roulements de charleston |
| 10 → 12 s | le chat : question tapée, réponse en direct (la bouche suit) ; vertical : l'app passe en 390×554, le chat tient au-dessus des boutons des réseaux | « Tu lui parles, il te répond. » | |
| 12 → 13,5 s | plongée sur la courbe du capital qui chute (scénario `danger`) | « Son capital, c'est sa vie. » | le cœur accélère, bips du moniteur |
| 13,5 → 15 s | il panique, poussée qui accélère sur son visage | « −35 % depuis son plus haut… » | coup sombre, charleston en triolets puis triples croches, montée |
| 15 → 16 s | ralenti (l'horloge de l'app ×0,25), la scène de mort lancée à 15,8 s | | arrêt de bande, un battement traîné, cymbale inversée |
| 16 s | yeux en croix pile sur le choc : secousse, aberration chromatique, bug (déplacement par bandes) | | braam sombre, bégaiement, chute de sub, trait continu du moniteur |
| 16,25 → 17,5 s | coupe au noir (noir voulu 16,25 → 16,5) | « …il meurt. » | le trait continu, puis vrai silence (17 → 17,5 s) |
| 17,5 → 20 s | retour : la tombe « GÉN. 3 » surgit ; la relève tombe du ciel, étincelles et confettis à l'atterrissage, le balai | « Le suivant hérite de ses erreurs. » | coup sourd, « plop » ; le cœur repart, montée, roulements |
| 20 → 24 s | coups de fouet (flou de mouvement) : écran d'ordinateur, TV en mode TV, téléphone (écran d'accueil avec l'icône de l'app, on la touche, lancement, l'app) | « Sur ton PC. » « Ta TV. » « Ton téléphone. » | le drop : supersaw qui pompe, 808, clap, le crochet |
| 24 → 26,5 s | carte de fin : tuile d'icône qui se résout (lueur, reflet), REDROCK, OPEN SOURCE, l'adresse, les licences | « Code MIT · personnage PolyForm Noncommercial » | impact, accord large, écho du crochet, queue |

Trois parties (`render.py`, `COMPS[...]["parts"]`), chacune une page neuve (`teaser.html?part=salle|mort|appareils`) :
l'app tourne en 1280×720 agrandie ×1,5 en 16:9, en 390×1100 (portrait du téléphone, mur d'écrans au-dessus du
perso) agrandie à 1080 px de large en 9:16 ; le PC, la TV et le téléphone sont trois apps en même temps.
Vertical : tout texte et le visage du perso restent dans la zone sûre des réseaux (ni les 8 % du haut, ni les 20 %
du bas, ni les 12 % de droite) ; les appareils sont recomposés un par un, grands et centrés.
Effets (tous dans la page, image par image) : secousses aux impacts (l'image grossit juste assez pour ne jamais
montrer de bord), flashs et traînées de lumière sur les temps forts, flou de mouvement (filtre SVG) sur les coups de
fouet, aberration chromatique et bug au choc de la mort, typographie qui surgit (échelle, flou, bascule 3D) sur les
temps, étincelles calculées en fonction du temps.

## Contrôles (aucune image fausse)

- **Le perso ne parle jamais quand il ne doit pas.** L'app appelle `window.talk` à chaque état (« Je suis mort… »,
  « Je vérifie mon compte… » pendant la relève) : les compositions la remplacent par une fonction vide et cachent
  la bulle (`C.noTalk` dans `comp.js`) ; la bouche ne bouge que pour la réponse du chat (6 → 8 s du teaser).
- **Chaque image est contrôlée** pendant le rendu (`COMP.probe` → `C.probe`) : bulle de parole (`.ov-say` avec la
  classe `on`, visible ou non), bouche qui parle (classe `talking` de `#arena`, synchro labiale en cours) hors des
  moments permis (le « Salut ! » du début, la réponse du chat), bulle de pensée ou « Zzz », 3D éteinte,
  « undefined »/« NaN » à l'écran. Chaque texte de la composition (`[data-txt]`) : jamais coupé (plus large que sa
  boîte), jamais hors du cadre, jamais sur le visage du perso (position de la tête donnée par `window.__headPx` de
  l'app, sauf derrière une carte plein cadre) ; en vertical, textes et visage dans la zone sûre des réseaux.
  Côté Python : image vide (noire, d'une seule couleur, pas encore dessinée ; un petit texte clair sur du noir
  compte comme du contenu) hors des noirs voulus (`COMP.blanks`), et saut brutal d'une image à l'autre hors des coupes
  et mouvements prévus (`COMP.cuts`, `COMP.moves`). Un seul défaut et `render.py` échoue (code 1).
- **Le salut** : émote `salut` du perso (`dash/character/redrock.js`, bouton 👋 « Salut » des émotes de l'app) : la
  main monte à côté de la tête, trois signes, yeux rieurs, tête penchée, il dit « Salut ! ». La composition masque la
  bulle de l'app (la sienne est plus grande et posée hors du visage) mais garde la bouche qui parle.
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
- Rien ne sort de la machine : dans toutes les pages filmées, une requête vers un autre site échoue et le WebSocket
  est un faux (`engine.OFFLINE`) ; les graphiques de position de l'app, qui lisent d'ordinaire les vraies bougies
  d'Hyperliquid, n'affichent que les bougies inventées du serveur des médias.
- Le trade rejoué (`fixtures.SHOW`, LINK) a ses propres bougies, calées sur ses niveaux : le SL n'est jamais touché,
  le TP l'est à la sortie. L'animation du rejeu est celle de l'app (CSS en temps virtuel, SMIL piloté image par image).
- Musiques synthétisées par `music.py` (numpy, synthèse additive) : aucun échantillon, aucun son sous droits.
  La durée de la vidéo d'installation suit la fin du terminal (`render.py installation --duration`).
