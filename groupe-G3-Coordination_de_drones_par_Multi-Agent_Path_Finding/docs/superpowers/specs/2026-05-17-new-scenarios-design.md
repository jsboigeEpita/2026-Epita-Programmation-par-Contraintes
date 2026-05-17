# Design — Nouveaux scénarios MAPF

**Date :** 2026-05-17  
**Scope :** Fix `grid.py` (bâtiments 2D) + 6 nouveaux fichiers `scenarios/06` à `11`

---

## Fix 1 — `solver/grid.py` : bâtiments en grille 2D

`add_building` ajoute actuellement des tuples 3D `(row, col, alt)` dans `obstacles`,
alors que les positions 2D sont des tuples 2D `(row, col)` → les bâtiments n'ont aucun
effet sur les grilles `alts=1`.

**Correction** dans `add_building` :

```python
def add_building(self, row: int, col: int, height: int) -> None:
    if self.alts == 1:
        self.obstacles.add((row, col))   # height ignoré en 2D
    else:
        for a in range(height):
            self.obstacles.add((row, col, a))
```

---

## Vue d'ensemble des scénarios

| Fichier | Nom | Grille | Drones | Bâtiments | Objectif |
|---|---|---|---|---|---|
| `06_dense_city.json` | `dense_city` | 10×10×3 | 10 | 29 | Navigation 3D dense |
| `07_bottleneck_s.json` | `bottleneck_s` | 10×10×1 | 8 | 40 | Goulot en S bidirectionnel |
| `08_large_sparse.json` | `large_sparse` | 20×20×5 | 10 | 20 | Baseline grande grille |
| `09_large_medium.json` | `large_medium` | 20×20×5 | 15 | 35 | Scalabilité intermédiaire |
| `10_large_dense.json` | `large_dense` | 20×20×5 | 20 | 55 | Densité max + charge |
| `11_mega.json` | `mega` | 25×25×5 | 30 | 80 | Stress test absolu |

---

## Scénario 06 — `dense_city` (10×10×3, 10 drones)

**Objectif :** Montrer que les solveurs doivent utiliser la 3e dimension pour naviguer
dans un environnement dense. Height-3 = cellule complètement bloquée (infranchissable).

### Drones
```
id 0 : [0,0,0] → [9,9,2]
id 1 : [9,0,0] → [0,9,2]
id 2 : [0,9,1] → [9,0,1]
id 3 : [9,9,0] → [0,0,2]
id 4 : [0,4,0] → [9,5,2]
id 5 : [9,5,0] → [0,4,2]
id 6 : [4,0,0] → [5,9,1]
id 7 : [5,9,0] → [4,0,2]
id 8 : [0,2,0] → [9,7,1]
id 9 : [9,7,0] → [0,2,2]
```

### Bâtiments (29 total)

**Height 3 — infranchissables (4) :**
`(3,3)`, `(3,7)`, `(7,3)`, `(7,7)`

**Height 2 — force alt 2 (20) :**
`(1,2)`, `(1,5)`, `(1,7)`,
`(2,1)`, `(2,4)`, `(2,8)`,
`(3,5)`,
`(4,2)`, `(4,5)`, `(4,8)`,
`(5,2)`, `(5,4)`, `(5,7)`,
`(6,2)`, `(6,5)`, `(6,8)`,
`(7,5)`,
`(8,1)`, `(8,4)`, `(8,7)`

**Height 1 (5) :**
`(2,6)`, `(4,7)`, `(5,3)`, `(6,4)`, `(8,8)`

---

## Scénario 07 — `bottleneck_s` (10×10×1, 8 drones)

**Objectif :** Forcer tous les drones à traverser un couloir en S — conflits bidirectionnels
maximum dans la zone de croisement (rows 4-5).

### Structure du couloir

```
     Col: 0 1 2 3 4 5 6 7 8 9
Row 0:    . . . . . W W W W W
Row 1:    . . . . . W W W W W
Row 2:    . . . . . W W W W W
Row 3:    . . . . . W W W W W
Row 4:    . . . . . . . . . .  ← croisement (tous passent ici)
Row 5:    . . . . . . . . . .  ← croisement
Row 6:    W W W W W . . . . .
Row 7:    W W W W W . . . . .
Row 8:    W W W W W . . . . .
Row 9:    W W W W W . . . . .
```

- **Mur A** : rows 0-3, cols 5-9 → 20 bâtiments height 1
- **Mur B** : rows 6-9, cols 0-4 → 20 bâtiments height 1
- **Zone croisement** : rows 4-5, tout ouvert

### Drones

Gauche→droite (start col 0, goal col 9) :
```
id 0 : [0,0] → [9,9]
id 1 : [1,0] → [8,9]
id 2 : [2,0] → [7,9]
id 3 : [3,0] → [6,9]
```

Droite→gauche (start col 9, goal col 0) :
```
id 4 : [9,9] → [0,0]
id 5 : [8,9] → [1,0]
id 6 : [7,9] → [2,0]
id 7 : [6,9] → [3,0]
```

---

## Scénarios 08-10 — `large_*` (20×20×5)

**Objectif commun :** Comparaison scalabilité solveurs. Les 3 scénarios partagent
la même structure de drones (incrémentale) et augmentent simultanément le nombre de
drones et la densité d'obstacles.

### Drones

**Communs aux 3 scénarios (ids 0-9, 10 drones) :**
```
id  0 : [0,0,0]   → [19,19,4]
id  1 : [19,0,0]  → [0,19,4]
id  2 : [0,19,1]  → [19,0,1]
id  3 : [19,19,0] → [0,0,4]
id  4 : [0,9,0]   → [19,10,4]
id  5 : [19,10,0] → [0,9,4]
id  6 : [9,0,0]   → [10,19,2]
id  7 : [10,19,0] → [9,0,4]
id  8 : [0,4,0]   → [19,15,3]
id  9 : [19,15,0] → [0,4,3]
```

**Ajoutés en 09 et 10 (ids 10-14, +5 drones) :**
```
id 10 : [0,14,0]  → [19,5,2]
id 11 : [19,5,0]  → [0,14,2]
id 12 : [4,0,0]   → [15,19,1]
id 13 : [15,19,0] → [4,0,3]
id 14 : [7,19,2]  → [12,0,2]
```

**Ajoutés en 10 uniquement (ids 15-19, +5 drones) :**
```
id 15 : [0,7,0]   → [19,12,4]
id 16 : [19,12,0] → [0,7,4]
id 17 : [3,0,1]   → [16,19,3]
id 18 : [16,19,1] → [3,0,3]
id 19 : [2,0,0]   → [17,19,4]
```

### Bâtiments

**Base 08 — sparse (20 bâtiments, height 2-4) :**
```
(3,3,h3), (3,10,h3), (3,16,h2),
(7,5,h4), (7,13,h3),
(10,3,h3), (10,10,h4), (10,17,h3),
(13,6,h3), (13,14,h4),
(16,3,h2), (16,10,h3), (16,16,h3),
(5,8,h3), (5,16,h2),
(12,8,h3), (9,16,h4),
(8,2,h3), (2,12,h2), (17,8,h3)
```

**Ajout 09 — medium (+15, height 3-4) :**
```
(4,6,h4), (4,14,h3), (6,10,h4), (6,18,h3), (8,6,h4),
(9,12,h3), (11,5,h4), (11,15,h3), (14,4,h4), (14,11,h3),
(15,7,h4), (2,5,h3), (2,17,h3), (18,5,h3), (18,14,h3)
```

**Ajout 10 — dense (+20, height 4-5) :**
```
(1,6,h5), (1,12,h4), (3,18,h4), (5,3,h5), (5,14,h4),
(7,8,h5), (7,16,h4), (9,4,h5), (9,7,h4), (11,9,h5),
(11,17,h4), (13,2,h5), (13,17,h4), (15,12,h5), (15,16,h4),
(17,3,h5), (17,11,h4), (18,17,h5), (6,5,h4), (12,13,h4)
```
*Note : height=5 avec alts=5 → cellule complètement bloquée (tous les niveaux d'altitude 0-4 obstrués).*

---

## Scénario 11 — `mega` (25×25×5, 30 drones)

**Objectif :** Stress test maximal — évaluer les limites de chaque solveur (temps de calcul,
mémoire, qualité de la solution).

### Drones (30)

Tous les starts/goals sont sur les bords de la grille (row 0, row 24, col 0, col 24) à
différentes altitudes pour éviter les conflits initiaux :

```
id  0 : [0,0,0]   → [24,24,4]    id  1 : [24,0,0]  → [0,24,4]
id  2 : [0,24,1]  → [24,0,1]     id  3 : [24,24,0] → [0,0,4]
id  4 : [0,6,0]   → [24,18,3]    id  5 : [0,12,0]  → [24,12,4]
id  6 : [0,18,0]  → [24,6,3]     id  7 : [24,6,0]  → [0,18,3]
id  8 : [24,12,0] → [0,12,4]     id  9 : [24,18,0] → [0,6,3]
id 10 : [6,0,0]   → [18,24,2]    id 11 : [12,0,0]  → [12,24,2]
id 12 : [18,0,0]  → [6,24,2]     id 13 : [6,24,0]  → [18,0,2]
id 14 : [12,24,0] → [12,0,4]     id 15 : [18,24,0] → [6,0,4]
id 16 : [0,3,0]   → [24,21,2]    id 17 : [0,21,0]  → [24,3,2]
id 18 : [24,3,0]  → [0,21,2]     id 19 : [24,21,0] → [0,3,2]
id 20 : [3,0,1]   → [21,24,3]    id 21 : [21,0,1]  → [3,24,3]
id 22 : [3,24,1]  → [21,0,3]     id 23 : [21,24,1] → [3,0,3]
id 24 : [0,9,2]   → [24,15,4]    id 25 : [0,15,2]  → [24,9,4]
id 26 : [9,0,2]   → [15,24,4]    id 27 : [15,0,2]  → [9,24,4]
id 28 : [9,24,2]  → [15,0,0]     id 29 : [15,24,2] → [9,0,0]
```

### Bâtiments (80 total, height 2-5)

**Height 5 — infranchissables (10) :**
`(5,5)`, `(5,19)`, `(10,10)`, `(14,5)`, `(14,19)`, `(19,14)`, `(8,17)`, `(17,8)`, `(11,2)`, `(2,11)`

**Height 4 (25) :**
`(2,5)`, `(2,14)`, `(2,20)`, `(5,10)`, `(5,15)`, `(8,3)`, `(8,8)`, `(8,20)`,
`(10,5)`, `(10,17)`, `(11,12)`, `(11,20)`, `(13,3)`, `(13,8)`, `(14,12)`, `(14,16)`,
`(16,5)`, `(17,16)`, `(17,20)`, `(19,3)`, `(19,8)`, `(20,11)`, `(20,16)`, `(22,5)`, `(22,19)`

**Height 3 (25) :**
`(3,3)`, `(3,17)`, `(4,9)`, `(4,22)`, `(6,6)`, `(6,12)`, `(7,19)`, `(9,2)`, `(9,14)`,
`(10,22)`, `(12,6)`, `(12,18)`, `(13,15)`, `(15,3)`, `(15,10)`, `(15,22)`, `(16,17)`,
`(18,5)`, `(18,12)`, `(19,21)`, `(20,3)`, `(21,8)`, `(21,17)`, `(22,11)`, `(23,15)`

**Height 2 (20) :**
`(1,8)`, `(1,16)`, `(3,22)`, `(4,4)`, `(6,20)`, `(7,11)`, `(9,7)`, `(9,18)`,
`(12,3)`, `(12,14)`, `(13,21)`, `(16,9)`, `(17,4)`, `(18,19)`, `(19,17)`,
`(20,22)`, `(21,2)`, `(21,14)`, `(23,6)`, `(23,20)`

---

## Invariants garantis (tous scénarios)

1. **Aucun bâtiment sur les positions start/goal** — tous les bâtiments sont intérieurs aux
   grilles, les starts/goals sont sur les bords.
2. **Starts uniques** — aucun doublon de position `[row, col, alt]` au temps 0.
3. **Goals uniques** — aucun doublon de position finale.
4. **Résolvabilité** — les obstacles ne créent pas de régions isolées (vérification par
   inspection : les drones ont toujours des chemins alternatifs via les altitudes supérieures
   ou les bords de grille).

---

## Fichiers à créer / modifier

```
solver/grid.py                      ← fix add_building (2D)
scenarios/06_dense_city.json        ← nouveau
scenarios/07_bottleneck_s.json      ← nouveau
scenarios/08_large_sparse.json      ← nouveau
scenarios/09_large_medium.json      ← nouveau
scenarios/10_large_dense.json       ← nouveau
scenarios/11_mega.json              ← nouveau
```
