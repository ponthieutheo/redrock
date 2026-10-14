# Licences

RedRock n'a pas une seule licence : le code est libre, le personnage et les médias ne le sont qu'en usage non commercial.

| Partie | Chemins | Licence | En pratique |
|---|---|---|---|
| Code (dashboard, broker, scripts, installation, docs) | tout le dépôt, sauf les lignes ci-dessous | [MIT](LICENSE) | libre, y compris en usage commercial, en gardant la mention de copyright |
| Le personnage RedRock (modèle 3D, visage, animations, émotes, tenues, scène de mort) | `dash/character/` | [PolyForm Noncommercial 1.0.0](dash/character/LICENSE) | gratuit pour tout usage **non commercial** (perso, recherche, association, école…) ; un usage commercial demande une licence séparée |
| Boulon, le personnage libre (petit robot à écran, mêmes fonctions que RedRock) | `dash/character-libre/` | [MIT](dash/character-libre/LICENSE) | libre, y compris en usage commercial, en gardant la mention de copyright |
| Médias : logo, icônes d'app, images, vidéos | `dash/logo.png`, `dash/favicon.png`, `dash/icon-*.png`, `dash/apple-touch-icon.png`, `design/`, `docs/media/` | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.fr) | partage et adaptation libres en citant RedRock, pas d'usage commercial |
| Bibliothèques et polices tierces | `dash/vendor/` (sauf `fonts.css`) | MIT et SIL OFL 1.1, celles de leurs auteurs | voir [Bibliothèques tierces](#bibliothèques-tierces) |
| Le nom « RedRock » et son logo | — | aucune | ce sont des signes distinctifs : ne les utilisez pas pour présenter un produit dérivé comme officiel |

## Pourquoi ce découpage

- **Le code est sous MIT** pour que chacun puisse brancher son agent, l'auditer, le modifier et contribuer sans friction.
- **Le personnage est sous PolyForm Noncommercial** : c'est du code (de la 3D générée en JavaScript), et les licences Creative Commons sont déconseillées pour du logiciel. PolyForm est faite pour ça.
- Une licence non commerciale n'est pas « open source » au sens de l'OSI : ce dépôt est donc **open source, sauf le personnage et les médias**.

## Remplacer le personnage

Le personnage est un module isolé, branché par un contrat documenté ([docs/personnage.md](docs/personnage.md)). Pour un usage commercial sans licence, prenez **Boulon**, le personnage libre (`CHARACTER=libre` dans `config/redrock.env`), ou supprimez `dash/character/` : l'app passe seule à Boulon, et le reste du dashboard fonctionne pareil. Vous pouvez aussi partir de Boulon pour écrire votre propre personnage.

## Bibliothèques tierces

Le dashboard embarque ses bibliothèques dans `dash/vendor/` et les sert lui-même : aucun CDN ni Google Fonts, l'app
s'affiche sans accès à Internet (seules les données de marché viennent de l'API publique d'Hyperliquid). Les fichiers
sont ceux des paquets officiels, sans modification ; leurs empreintes sont vérifiées par `dash/test_vendor.py`.

| Bibliothèque | Version | Fichiers | Licence | Origine |
|---|---|---|---|---|
| [three.js](https://threejs.org) | 0.170.0 | `dash/vendor/three/three.module.js` | MIT, © 2010-2024 three.js authors ([texte](dash/vendor/three/LICENSE)) | paquet npm `three` |
| [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | 1.4.4 | `dash/vendor/qrcode-generator/qrcode.min.js` | MIT, © 2009 Kazuhiko Arase ([texte](dash/vendor/qrcode-generator/LICENSE)) | cdnjs, conforme au SRI de la page |
| [Chakra Petch](https://github.com/m4rc1e/Chakra-Petch) | @fontsource 5.3.0 | `dash/vendor/fonts/chakra-petch-*.woff2` | SIL Open Font License 1.1, © 2018 The Chakra Petch Project Authors ([texte](dash/vendor/fonts/LICENSE-ChakraPetch.txt)) | paquet npm `@fontsource/chakra-petch` |
| [Barlow](https://github.com/jpt/barlow) | @fontsource 5.3.0 | `dash/vendor/fonts/barlow-*.woff2` | SIL Open Font License 1.1, © 2017 The Barlow Project Authors ([texte](dash/vendor/fonts/LICENSE-Barlow.txt)) | paquet npm `@fontsource/barlow` |

`dash/vendor/fonts/fonts.css` (les déclarations `@font-face`) fait partie du code RedRock (MIT). Les polices restent
sous OFL : elles peuvent être redistribuées avec RedRock, pas vendues seules.

L'agent est [Hermes Agent](https://github.com/NousResearch/hermes-agent) de Nous Research, sous sa propre licence.

*Ce document n'est pas un avis juridique.*
