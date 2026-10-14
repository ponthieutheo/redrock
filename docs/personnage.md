# Brancher son propre personnage

Le dashboard ne connaît pas le personnage RedRock : il charge un module, `dash/character/redrock.js`, qui
respecte un contrat. Tout autre personnage qui respecte ce contrat peut prendre sa place.

C'est utile si tu veux :
- un personnage à toi (ta mascotte, ton style) ;
- un usage **commercial** : le personnage RedRock est sous licence non commerciale
  ([PolyForm Noncommercial 1.0.0](../dash/character/LICENSE)), le reste du dashboard est sous MIT.

## En trois étapes

1. Crée `dash/character/monperso.js` qui exporte `createCharacter(ctx)`.
2. Dans le `<script type="module">` de `dash/index.html`, remplace l'import de `./character/redrock.js` par
   `./character/monperso.js`.
3. Ajoute le fichier au `SHELL` de `dash/sw.js` (pour le mode hors ligne) et change le nom du cache.

## Le contrat

La référence complète (ce que la scène fournit, l'ordre des appels à chaque image, l'état `S`, ce que le
personnage doit exposer) est dans **[dash/character/README.md](../dash/character/README.md)**.

En résumé :

```js
export function createCharacter({THREE, rig, desk, renderer}) {
  const head = new THREE.Mesh(/* … */);
  rig.add(head);
  return {
    head, HEAD: head.position.clone(), HS: 1,        // la caméra, les bulles et le toucher s'en servent
    outfit: {}, hatchT: -1, partyUntil: 0,
    mount({props, hitZone}) {},                       // une fois le bureau posé
    update(dt, now, t, S) {                           // chaque image
      // anime la tête selon S.act, S.alive, S.talking, S.unread…
      S.em = null;                                    // obligatoire : renvoyer l'état résolu
    },
    updateHands(dt, now, t, S) {}, lateUpdate(dt) {},
    hatch() {}, party(ms) {}, emote(name) {}, tap(sleeping) {}, line(kind) {}, sip() {},
    debug: {}, dispose() { rig.remove(head); },
  };
}
```

Les fonctions dont ton personnage n'a pas besoin peuvent ne rien faire. Seule obligation : `update()` doit
recopier dans `S` les champs `act`, `win`, `danger`, `task` et `em` (au besoin tels quels, `em` à `null`).

## Vérifier

Ouvre l'app avec `?render=force` et, dans la console du navigateur :
- `__emote("dance")`, `__emote("panic")` : les émotes ;
- `__unreadT(2)` : il sort son téléphone ;
- `__hatch()` : la scène de mort et de relève.
