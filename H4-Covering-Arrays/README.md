H4 - Covering Arrays
==

# Installation

```sh
nix develop

uv sync

uv run jupyter lab
```

# Contenu

L'intégralité du code du projet se trouve dans le main.ipynb dans le dossier src.

Il contient :
- une explication des covering arrays et des contraintes sémentiques
- un exemple de résolution avec k = 5, des v différents entre 2 et 4 et t = 3, avec des contraintes sémentiques
- l'implémentation des 3 générateurs de Covering Arrays (CPSAT, IPOG, et AETG)
- un benchmark des 3 générateurs sur des k et v grandissants avec t = 3
