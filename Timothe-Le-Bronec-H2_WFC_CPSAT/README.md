# H2 — Génération procédurale de niveaux de jeu par WFC et CP-SAT

## Rappel du sujet

La génération procédurale de niveaux par Wave Function Collapse (WFC) consiste à générer des grilles 2D à partir d’un ensemble de tuiles avec des contraintes d’adjacence. WFC est proche d’un problème de satisfaction de contraintes : chaque case possède des valeurs possibles et les contraintes locales limitent les voisins autorisés.

Ce projet montre comment enrichir WFC avec CP-SAT afin d’ajouter des contraintes globales que WFC pur gère mal : connectivité, chemin joueur, placement d’objets, difficulté et variété.

## Contenu

- `timothe-le-bronec-h2_wfc_cpsat.ipynb` : notebook principal visuel.
- `requirements.txt` : dépendances Python.
- `.env` : env Python.

## Cas étudiés

1. Donjon : génération d’un labyrinthe avec plusieurs salles, couloirs, spawn, sortie, trésors et ennemis.
2. Île / biomes : génération d’une île  irrégulière avec plage, herbe, forêt, village, port et ruines.

## Méthodes comparées

- Random : tuiles tirées sans contraintes.
- WFC simplifié : contraintes locales d’adjacence.
- WFC + CP-SAT : contraintes locales + contraintes globales de jouabilité.

## Installation

```bash
source .env/bin/acivate
pip install -r requirements.txt
jupyter notebook H2_WFC_CPSAT_Final.ipynb
```
