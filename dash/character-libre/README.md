# Boulon, le personnage libre

Boulon est un petit robot rond, crème et graphite, dont le visage est un écran : des yeux qui brillent, une bouche
qui devient un égaliseur quand il parle, une antenne à ressort dont la lumière change avec son humeur, deux boulons
en guise d'oreilles. Il fait tout ce que fait le personnage RedRock dans la scène : il trade, réfléchit, dort, panique,
danse, sort son téléphone quand un message arrive, boit son café, s'habille, meurt et se fait remplacer.

**Licence : MIT** (fichier `LICENSE`). Usage, modification et redistribution libres, **y compris commerciaux**, en
gardant la mention de copyright. C'est le personnage à prendre pour un usage commercial de RedRock, ou comme point de
départ pour écrire le vôtre.

## Fichiers

| Fichier | Rôle |
|---|---|
| `boulon.js` | Le personnage entier : modèle 3D, visage peint sur une toile, mains, téléphone, tasse, tenues, émotes, scène de mort et de relève |
| `LICENSE` | MIT |

## Le choisir

| Comment | Effet |
|---|---|
| rien | RedRock (`dash/character/`) s'il est présent, sinon Boulon |
| `CHARACTER=libre` dans l'environnement de l'app (`config/redrock.env`) | Boulon pour tout le monde (le serveur marque la page `<html data-perso="libre">`) |
| `?perso=libre` dans l'adresse | Boulon dans cet onglet, pour essayer (`?perso=redrock` pour revenir) |
| supprimer `dash/character/` | Boulon : l'app, l'image Docker et le mode hors ligne fonctionnent sans le personnage non commercial |

## Ce qu'il sait faire

| La scène lui demande | Boulon |
|---|---|
| `act` : `trading`, `watching`, `thinking`, `sleeping`, `dead` | clavier et souris, yeux qui lisent l'écran, main au menton, yeux fermés et tête basse, coque grise et yeux en croix |
| `win`, `danger`, `fear`, `content` | petits bonds (et danse robot), tremblement et sueur, yeux violets qui rapetissent, joues roses |
| `tama` (énergie, faim, humeur), `caress` | paupières lourdes, pile faible qui clignote, petit rebond, cœur et joues roses |
| émotes `dance`, `wow`, `ouch`, `boop`, `think`, `panic`, `yawn`, `sleep`, `type`, `shades`, `hatch`, `talk` | toutes (les lunettes pixel tombent du haut de l'écran) |
| `talking` + `window.__say` | la bouche-égaliseur suit les lettres de la bulle (voyelles ouvertes, m/b/p fermées, pauses) |
| `unread`, `chatOpen` | il sort son téléphone (« 2 messages non lus »), le regarde, il vibre, l'antenne clignote avec |
| tenues `hat` (`top`, `party`, `crown`), `glasses` (`pixel`, `round`), `ear` (`headset`), `neck` (`bow`) | toutes ; les autres valeurs sont ignorées |
| `crown`, `shades`, `bandage` (drapeaux du jour) | couronne, lunettes pixel, sparadrap sur un coin de l'écran |
| `hatch()` | panne : il grésille, yeux en croix, il s'affaisse, l'écran s'éteint comme une vieille télé ; un rayon l'aspire ; le remplaçant descend, atterrit, démarre (`BOOT`, puis sa génération) et ouvre les yeux |
| `tap()`, `sip()` | il sursaute (et bâille s'il dormait) ; il porte la tasse devant l'écran, une pile s'y recharge |

Rien n'est alloué image par image (vecteurs et couleurs réservés d'avance), le visage n'est redessiné que lorsqu'il
change (au plus 30 fois par seconde), et `dispose()` libère toutes les géométries, matières et textures.

## Le contrat entre la scène et le personnage

La scène (`dash/index.html`) construit le bureau, puis charge un module qui exporte `createCharacter(ctx)`.
Tout personnage qui respecte ce contrat peut remplacer Boulon ou RedRock.

### Création et montage

```js
const perso = createCharacter({THREE, rig, desk, renderer});
perso.mount({props, hitZone});      // une fois le mobilier posé
```

| Champ | Contenu |
|---|---|
| `THREE` | la bibliothèque three.js de la scène (0.170) |
| `rig` | le groupe du poste de travail : tête, mains, téléphone s'y accrochent (coordonnées : clavier vers `z = 1.72`, souris vers `x = 1.3`) |
| `desk.mouse`, `desk.M0` | la souris (le personnage la déplace) et sa place de repos (la scène la change selon le cadrage) |
| `desk.mWheel`, `desk.mLed` | la molette (elle tourne) et la diode (son `emissiveIntensity` flashe au clic) |
| `desk.pressNear(pos, slam)` | enfonce la touche du clavier sous une main qui frappe (`slam` : toute la zone, pour un ordre) |
| `desk.screenW` | largeur des toiles d'écran (pour suivre le curseur du graphique « marché ») |
| `renderer` | facultatif : le `WebGLRenderer` |
| `props` | le groupe des objets du bureau (la tasse y va) |
| `hitZone(objet, rayon, y, nom)` | déclare une zone que l'on peut toucher ; `"mug"` appelle `sip()` |

### Chaque image, dans cet ordre

```js
perso.update(dt, now, t, S);       // corps, visage, humeur, tenues, téléphone, scène de mort
perso.updateHands(dt, now, t, S);  // mains, souris, téléphone en main
perso.lateUpdate(dt);              // la tasse
```

`dt` en secondes (au plus 0,1), `now` en millisecondes, `t = now / 1000`. `S` est l'état du jour :

| Champ | Sens |
|---|---|
| `act` | `"dead"`, `"thinking"`, `"trading"`, `"watching"` ou `"sleeping"` |
| `alive`, `talking`, `win`, `danger` | vivant, en train de parler, objectif atteint, en danger |
| `task` | ce qu'il fait en réfléchissant : `"code"`, `"compte"`, `"news"`, `"marche"`, `"ordre"`, `"jev"`, `"pense"` |
| `wide` | cadrage large (PC) plutôt que portrait |
| `chatOpen`, `unread` | chat ouvert, nombre de messages non lus |
| `outfit` | tenue `{hat, glasses, ear, neck}` |
| `tama`, `caress`, `look` | humeur `{energy, hunger, mood}` (0..1), caresse en cours, regard `{x, y}` (en pixels autour de la tête, quelques centaines au plus) |
| `generation` | numéro de génération |
| `fear`, `content`, `crown`, `shades`, `bandage` | peur 0..1 et drapeaux du jour |

**Obligatoire :** après ses émotes, `update()` recopie dans `S` l'état résolu : `S.act`, `S.win`, `S.danger`, `S.task`
et `S.em` (émote en cours ou `null`). La scène s'en sert pour les écrans, les confettis et les bulles.

Signaux lus en direct : `window.__react` (`{kind: "wow" | "ouch" | "boop", dur, until}`, réaction passagère) et
`window.__say` (`{text, t0}`, texte de la bulle). Le personnage peut appeler `window.talk(texte)`, `window.__sfx.*()`,
`window.__buzz(motif)` et `window.__emote(nom)`.

### Ce que le personnage expose

| Membre | Rôle |
|---|---|
| `head`, `HEAD`, `HS` | l'objet de la tête (position dans le `rig`), sa place de repos, sa taille : caméra, bulles, toucher |
| `outfit` | `{crown, topHat, partyHat, bowTie, makeHeadset}` : la scène clone les quatre premiers (origine à la base) et appelle `makeHeadset()` pour la vitrine de la garde-robe |
| `hatchT` | `-1` hors scène de mort, sinon secondes écoulées (la caméra se fige pendant la scène) |
| `partyUntil` | fin de la fête en cours (confettis), en millisecondes |
| `hatch()`, `party(ms)`, `emote(nom)` | scène de mort et de relève, fête, émote |
| `tap(dort)`, `line("boop" \| "talk")`, `sip()` | toucher de la tête, réplique au hasard, gorgée de café |
| `debug` | `{benchFace(), liveTexels}` pour `window.__hc1bench()` |
| `dispose()` | retire et libère tout ce que le personnage a posé |

Le personnage met `window.__headPos` à jour à chaque image et pose `window.__phoneDbg`, `__mugActive`, `__mugHand` (tests).

## Écrire le vôtre

Copiez ce dossier (la licence MIT le permet), renommez `boulon.js`, changez le modèle et le visage, et faites pointer
l'import de `dash/index.html` (fonction `libre`) vers votre fichier ; ajoutez-le au `SHELL` de `dash/sw.js` pour le
mode hors ligne. Les fonctions dont votre personnage n'a pas besoin peuvent ne rien faire, tant que `outfit` contient
les cinq modèles (des groupes vides suffisent : la scène les clone) et que `update()` remplit `S.act`, `S.win`,
`S.danger`, `S.task` et `S.em`.
