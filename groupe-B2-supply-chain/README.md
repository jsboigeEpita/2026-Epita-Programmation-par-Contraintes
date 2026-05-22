# B2 — Supply Chain Network Design

Rémi Brenaut, Edouard André, Quentin Lauret — SCIA 2027

## Problème

Le CFLP (Capacitated Facility Location Problem) consiste à choisir quels entrepôts
ouvrir parmi un ensemble de candidats et à affecter chaque client à un entrepôt ouvert,
en minimisant les coûts fixes d'ouverture et les coûts de transport sous des contraintes
de capacité.

## Approches implémentées

| Méthode | Type | Description |
|---|---|---|
| CP-SAT | Exacte | Modélisation par contraintes via OR-Tools |
| PLNE | Exacte | Programmation linéaire en nombres entiers via PuLP (CBC) |
| GRASP | Métaheuristique | Construction gloutonne randomisée + recherche locale |
| ALNS | Métaheuristique | Destruction/réparation adaptative + Simulated Annealing |

## Extensions

- **Robustesse** : modèle worst-case pour la demande incertaine (paramètre `uncertainty`)
- **Durabilité** : choix diesel/électrique avec budget CO₂ configurable

## Données

Instances CAP de l'OR-Library de Beasley (1988) :
`data/cap71.txt`, `data/cap101.txt`, `data/cap131.txt`, `data/cap134.txt`, `data/capopt.txt`

Source : http://people.brunel.ac.uk/~mastjjb/jeb/orlib/capinfo.html

## Installation

```bash
uv sync
```

## Utilisation

Ouvrir et exécuter `project.ipynb` dans l'ordre des cellules.

## Résultats principaux (cap134, 50 entrepôts, 50 clients)

| Méthode | Coût | Gap | Temps |
|---|---|---|---|
| CP-SAT | 928 941.67 | 0.000% | ~0.1s |
| PLNE | 928 941.75 | 0.000% | ~0.15s |
| GRASP | 928 941.75 | 0.000% | ~3s |
| ALNS | 945 438.08 | 1.776% | ~2s |

## Références

- Beasley, J.E. (1988). OR-Library. Brunel University.
- Melo et al. (2009). Facility Location and Supply Chain Management. EJOR.
- ADEME (2022). Facteurs d'émission transport.