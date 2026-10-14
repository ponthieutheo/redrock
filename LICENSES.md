# Licences

RedRock n'a pas une seule licence : le code est libre, le personnage et les médias ne le sont qu'en usage non commercial.

| Partie | Chemins | Licence | En pratique |
|---|---|---|---|
| Code (dashboard, broker, scripts, installation, docs) | tout le dépôt, sauf les lignes ci-dessous | [MIT](LICENSE) | libre, y compris en usage commercial, en gardant la mention de copyright |
| Le personnage RedRock (modèle 3D, visage, animations, émotes, tenues, scène de mort) | `dash/character/` | [PolyForm Noncommercial 1.0.0](dash/character/LICENSE) | gratuit pour tout usage **non commercial** (perso, recherche, association, école…) ; un usage commercial demande une licence séparée |
| Médias : logo, icônes d'app, images, vidéos | `dash/logo.png`, `dash/favicon.png`, `dash/icon-*.png`, `dash/apple-touch-icon.png`, `design/`, `media/` | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.fr) | partage et adaptation libres en citant RedRock, pas d'usage commercial |
| Le nom « RedRock » et son logo | — | aucune | ce sont des signes distinctifs : ne les utilisez pas pour présenter un produit dérivé comme officiel |

## Pourquoi ce découpage

- **Le code est sous MIT** pour que chacun puisse brancher son agent, l'auditer, le modifier et contribuer sans friction.
- **Le personnage est sous PolyForm Noncommercial** : c'est du code (de la 3D générée en JavaScript), et les licences Creative Commons sont déconseillées pour du logiciel. PolyForm est faite pour ça.
- Une licence non commerciale n'est pas « open source » au sens de l'OSI : ce dépôt est donc **open source, sauf le personnage et les médias**.

## Remplacer le personnage

Le personnage est un module isolé, branché par un contrat documenté ([docs/personnage.md](docs/personnage.md)). Pour un usage commercial sans licence, remplacez `dash/character/` par votre propre personnage : le reste du dashboard fonctionne pareil.

## Bibliothèques tierces

Le dashboard charge [three.js](https://threejs.org) (MIT), [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) (MIT) et les polices Chakra Petch et Barlow (SIL Open Font License). L'agent est [Hermes Agent](https://github.com/NousResearch/hermes-agent) de Nous Research, sous sa propre licence.

*Ce document n'est pas un avis juridique.*
