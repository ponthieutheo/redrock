# Le personnage RedRock

Ce dossier contient le personnage RedRock : la boule rouge, son visage, ses mains, ses émotes, ses tenues,
sa tasse, son téléphone, sa scène de mort et de relève.

**Licence : PolyForm Noncommercial 1.0.0** (fichier `LICENSE`). Usage, modification et partage libres
pour un usage non commercial. Le reste du dashboard (la scène, les écrans, le serveur) est sous une licence
libre distincte. Le nom « RedRock » et le logo ne sont couverts par aucune des deux licences.

## Fichiers

| Fichier | Rôle |
|---|---|
| `redrock.js` | Le personnage : modèles 3D, animation image par image, émotes, répliques, scène de mort/relève |
| `face.js` | Le visage : le logo projeté sur la sphère, yeux/sourcils/bouche peints puis reportés sur la texture |
| `LICENSE` | PolyForm Noncommercial 1.0.0 |

## Le contrat entre la scène et le personnage

La scène (`index.html`) construit le décor et appelle le personnage. N'importe quel autre personnage qui respecte
ce contrat peut prendre sa place : il suffit d'exporter `createCharacter(ctx)` et de changer l'import en haut du
module de la scène.

### Création

```js
const ch = createCharacter({THREE, rig, desk, renderer});
```

| Champ | Contenu |
|---|---|
| `THREE` | la bibliothèque three.js de la scène |
| `rig` | le groupe du poste de travail : le personnage y accroche sa tête, ses mains, son téléphone, la tombe et le balai |
| `desk.mouse`, `desk.M0` | la souris (le personnage la déplace) et sa place de repos (la scène la change selon le cadrage) |
| `desk.mWheel`, `desk.mLed` | la molette et la diode de la souris (elles tournent et s'allument quand il s'en sert) |
| `desk.pressNear(pos, slam)` | enfonce la ou les touches du clavier sous une main qui frappe |
| `desk.screenW` | largeur des toiles d'écran (le curseur du graphique « marché » que la souris suit) |
| `renderer` | facultatif : le `WebGLRenderer` de la scène. Le visage s'en sert pour ne renvoyer au GPU que le rectangle qui change (`copyTextureToTexture`) ; sans lui, toute la texture est renvoyée à chaque expression |

Puis, une fois le mobilier posé :

```js
ch.mount({props, hitZone});
```

`props` est le groupe des objets du bureau (le personnage y pose sa tasse), `hitZone(objet, rayon, y, nom)`
déclare une zone que l'on peut toucher. Le personnage y installe aussi ses mains, son téléphone et ses gouttes de sueur.

### Chaque image, dans cet ordre

```js
ch.update(dt, now, t, S);       // tête, visage, humeur, tenues, téléphone, scène de mort, sueur
// … la scène : confettis, sticker
ch.updateHands(dt, now, t, S);  // mains, souris, téléphone en main
// … la scène : clavier, écrans, bulles, garde-robe
ch.lateUpdate(dt);              // la tasse
```

`dt` en secondes, `now` en millisecondes, `t = now / 1000`.

`S`, l'état du jour, est fourni par la scène :

| Champ | Sens |
|---|---|
| `act` | `"dead"`, `"thinking"`, `"trading"`, `"watching"` ou `"sleeping"` |
| `alive`, `talking`, `win`, `danger` | vivant, en train de parler, objectif atteint (fête), en danger |
| `task` | ce qu'il fait quand il réfléchit (`"code"`, `"compte"`, `"news"`, `"ordre"`, `"jev"`…) |
| `wide` | cadrage large (PC) plutôt que portrait |
| `chatOpen`, `unread` | chat ouvert, nombre de messages non lus (il sort son téléphone) |
| `outfit` | tenue `{hat, glasses, ear, neck}` |
| `tama`, `caress`, `look` | humeur `{energy, hunger, mood}`, caresse en cours, regard `{x, y}` |
| `generation` | numéro de génération (gravé sur la tombe) |
| `fear`, `content`, `crown`, `shades`, `bandage` | drapeaux du jour (peur 0..1, content, couronne, lunettes, pansement) |

Après `update`, le personnage complète `S` avec l'état résolu après ses émotes : `S.act`, `S.win`, `S.danger`,
`S.task`, `S.em` (émote en cours). La scène s'en sert pour les écrans et les confettis.

Deux signaux sont lus en direct parce qu'ils peuvent changer pendant l'image : `window.__react` (réaction passagère
`{kind, dur, until}`) et `window.__say` (texte de la bulle, pour la synchro des lèvres `{text, t0}`).
Le personnage peut appeler l'app : `window.talk(texte)`, `window.__sfx.*()`, `window.__buzz(motif)`, `window.__emote(nom)`.

### Ce que le personnage expose

| Membre | Rôle |
|---|---|
| `head`, `HEAD`, `HS` | la tête (position locale au `rig`), sa place de repos, sa taille : la scène s'en sert pour la caméra, les bulles et le toucher |
| `outfit` | les modèles des tenues `{crown, topHat, partyHat, bowTie, makeHeadset}` (vitrine de la garde-robe) |
| `hatchT` | scène de mort/relève : `-1` si aucune, sinon secondes écoulées (la caméra se fige pendant la scène) |
| `partyUntil` | fin de la fête en cours (confettis) |
| `hatch()` | lance la scène de mort et de relève |
| `party(ms)` | fait la fête quelques secondes |
| `emote(nom)` | `dance`, `wow`, `ouch`, `boop`, `think`, `panic`, `yawn`, `sleep`, `type`, `shades`, `hatch`, `talk` |
| `tap(dort)` | on lui touche la tête : il sursaute (et bâille s'il dormait) |
| `line(type)` | une réplique au hasard (`"boop"` ou `"talk"`) |
| `sip()` | boire une gorgée de café (toucher de la tasse) |
| `debug` | `benchFace()` (mesure du visage), `liveTexels` |
| `dispose()` | retire et libère tout ce que le personnage a posé dans la scène |

La scène garde les crochets `window.__emote`, `__hatch`, `__hatchT`, `__party`, `__unread`, `__unreadT`, `__markRead`
et `__hc1bench`, qu'elle relaie au personnage. Le personnage pose lui-même `window.__phoneDbg`, `__mugActive`
et `__mugHand` (tests), et met `window.__headPos` à jour à chaque image.

## Écrire un autre personnage

Le minimum : `createCharacter(ctx)` qui renvoie un objet avec `head`, `HEAD`, `HS`, `outfit`, `hatchT`, `partyUntil`,
`hatch()`, `party()`, `emote()`, `tap()`, `line()`, `sip()`, `mount()`, `update()`, `updateHands()`, `lateUpdate()`,
`debug` et `dispose()`. Les fonctions dont il n'a pas besoin peuvent ne rien faire, mais `update()` doit toujours
recopier dans `S` les champs `act`, `win`, `danger`, `task` et `em` (au besoin tels quels, `em` à `null`).
