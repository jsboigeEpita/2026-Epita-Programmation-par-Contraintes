# D4 — Dispatch dans un réseau électrique

## Vue d'ensemble

Ce projet implémente le **dispatch économique et l'engagement des unités (Unit Commitment)** comme problème d'optimisation sous contraintes avec Google OR-Tools CP-SAT. Trois modèles sont construits progressivement :

1. **Dispatch économique (ED)** — période unique, coût minimal, équilibre offre-demande
2. **Unit Commitment (UC)** — horizon 24 h, décisions binaires ON/OFF, contraintes temporelles
3. **UC stochastique (SUC)** — deux étapes, scénarios de production renouvelable

---

## Architecture du projet

```
D4 - Dispatch dans un reseau electrique/
├── src/                    # Bibliothèque Python (solveurs + utilitaires)
│   ├── instance.py         # Modèle de données (réseau, générateurs, lignes)
│   ├── dispatch_solver.py  # Solveur ED période unique
│   ├── unit_commitment.py  # Solveur UC multi-période
│   ├── stochastic.py       # Solveur UC stochastique deux étapes
│   ├── scenarios.py        # Génération de scénarios renouvelables
│   └── visualization.py   # Fonctions de visualisation matplotlib
├── notebooks/
│   ├── demo.ipynb          # Notebook de démonstration complet (9 sections)
│   └── build_demo.py       # Script de régénération de demo.ipynb
├── usefull Notebooks/      # Références pédagogiques CoursIA (lecture seule)
│   ├── CSP-4-Scheduling.ipynb
│   ├── CSP-5-Optimization.ipynb
│   ├── App-10-Portfolio.ipynb
│   └── Search-9-LinearProgramming.ipynb
├── main.py                 # Script de test en ligne de commande
├── README.md               # Documentation mathématique détaillée (FR)
├── subject.md              # Énoncé du projet
└── DOCUMENTATION.md        # Ce fichier
```

---

## Responsabilité de chaque fichier

### `src/instance.py`
Définit les **structures de données** du réseau électrique.

| Classe | Rôle |
|--------|------|
| `Generator` | Centrale : bus, P_min/P_max, coûts quadratiques (a,b,c), startup/shutdown, min-up/down, rampes, état initial, type (thermal/wind/solar) |
| `Bus` | Nœud du réseau : identifiant, nom, charge (MW) |
| `Line` | Ligne de transport : bus_from, bus_to, capacité (MW) |
| `PowerNetwork` | Réseau complet : listes de Bus/Line/Generator, nom, base MVA, fraction de réserve |

Fonctions usine : `three_bus_toy()`, `six_bus_congested()`, `ieee14()`, `add_renewables(network, capacities)`.

### `src/dispatch_solver.py`
**Solveur pour un seul pas de temps.** Reçoit un réseau + charges + disponibilités renouvelables, retourne la production optimale de chaque centrale.

Points clés :
- Coût quadratique `a + b·P + c·P²` approximé par **K tangentes linéaires** (`PWL_BREAKPOINTS=6`)
- Variables entières : puissance scalée par `POWER_SCALE=1`, coût scalé par `COST_SCALE=100`
- Contraintes : flux de transport (conservation par bus, borne ±capacité), spinning reserve, sortie minimale
- `_pwl_tangents(g, k)` → liste de `(slope, intercept)` pour l'enveloppe convexe
- Retourne `EconomicDispatchSolution` avec méthodes `.report()` et `.merit_order_cost()`

### `src/unit_commitment.py`
**Solveur multi-période (24 h).** Planifie les démarrages/arrêts en minimisant le coût total sur un horizon.

Variables additionnelles par rapport à l'ED :
- `u[g,t]` — variable binaire ON/OFF pour le générateur g à l'heure t
- `su[g,t]`, `sd[g,t]` — binaires de démarrage/arrêt

Contraintes temporelles :
- **Min-up time** : une fois démarré, doit rester ON au moins `min_up` périodes
- **Min-down time** : une fois arrêté, doit rester OFF au moins `min_down` périodes
- **Rampes** : `|P[g,t] - P[g,t-1]| ≤ ramp_up/down` (avec marge au démarrage `p_min * su[g,t]`)

Fonction utilitaire : `daily_load_profile(network, H, peak_factor, off_peak_factor, peak_hour)`.
Retourne `UnitCommitmentSolution`.

### `src/stochastic.py`
**Solveur UC deux étapes** face à l'incertitude renouvelable.

Architecture :
- **Première étape** : décisions d'engagement `u, su, sd` identiques pour tous les scénarios (avant observation)
- **Deuxième étape** : puissance `p[g,t,s]`, flux `flow[i,s,t]`, délestage `ls[b,s,t]`, écrêtage `curt[g,s,t]` par scénario

Pénalités : délestage `LOAD_SHED_PENALTY=5000 €/MWh`, écrêtage `CURTAIL_PENALTY=50 €/MWh`.
Probabilités entières : `pw = int(round(p * 10_000))` pour CP-SAT.
Retourne `StochasticUCSolution` avec calcul du **VSS** (Value of Stochastic Solution).

### `src/scenarios.py`
**Génération de scénarios** de production renouvelable via un processus AR(1).

| Fonction | Description |
|----------|-------------|
| `solar_profile(T, peak_hour, width, max_capacity_factor)` | Profil solaire gaussien centré sur midi |
| `wind_profile(T, mean, night_bonus)` | Profil éolien avec bonus nocturne |
| `sample_scenarios(asset_means, n_scenarios, sigma, seed)` | Bruit AR(1) : `ε[t] = 0.7·ε[t-1] + √(1−0.49)·N(0,σ)`, clipé dans [0,1] |

### `src/visualization.py`
**Visualisations matplotlib.** Toutes les fonctions retournent un objet `Figure`.

| Fonction | Rendu |
|----------|-------|
| `plot_network(net, flows, ...)` | Diagramme du réseau, couleur/épaisseur des arcs proportionnelles au taux de charge |
| `plot_single_period(sol, ...)` | Barres de production avec P_max en pointillés |
| `plot_dispatch_stack(sol, ...)` | Aires empilées + courbe de charge en noir |
| `plot_schedule(sol, ...)` | Heatmap ON/OFF + symboles ↑↓ pour démarrages/arrêts |
| `plot_line_loadings(sol, ...)` | Top-k lignes par taux d'utilisation |
| `plot_cost_breakdown(sol, ...)` | Décomposition carburant/démarrage/arrêt |
| `plot_scenarios(scenarios, ...)` | Graphe spaghetti des scénarios renouvelables |

### `notebooks/demo.ipynb`
**Notebook de démonstration principal.** Couvre l'ensemble du projet en 9 sections progressives :

| Section | Contenu |
|---------|---------|
| 1. Réseau jouet 3 bus | Dispatch économique basique, vérification des flux |
| 2. Instance 6 bus congestionnée | Congestion de lignes, prix nodaux |
| 3. IEEE 14-bus | Instance standard, benchmark de performance |
| 4. Unit Commitment 24 h | Planning journalier, heatmap ON/OFF |
| 5. Scénarios renouvelables | Profils solaire/éolien, processus AR(1) |
| 6. UC stochastique | Deux étapes, décisions robustes |
| 7. VSS | Comparaison stochastique vs déterministe (valeur espérée) |
| 8. Scalabilité | Benchmarks sur instances croissantes |
| 9. Extensions | Pistes : HVDC, stockage batterie, marchés d'énergie |

### `notebooks/build_demo.py`
Script Python qui **régénère `demo.ipynb` programmatiquement** via `json.dumps`. Utile pour reconstruire le notebook après modification de la structure. Ne pas exécuter si les cellules ont été modifiées manuellement.

### `main.py`
**Script de smoke-test en ligne de commande.**

```bash
python main.py              # ED + UC + SUC sur instance jouet
python main.py --fast       # ED uniquement
python main.py --uc-time 60 --suc-time 120  # Limites de temps personnalisées
```

---

## Comment ça fonctionne — pipeline complet

```
PowerNetwork (instance.py)
        │
        ▼
solve_economic_dispatch()   ←─ dispatch_solver.py
        │  période unique, variables continues/entières
        │  coût PWL, flux de transport, spinning reserve
        │
        ▼
solve_unit_commitment()     ←─ unit_commitment.py
        │  horizon 24h, binaires u/su/sd
        │  min-up/down, rampes, profil de charge
        │
        ▼
sample_scenarios()          ←─ scenarios.py
        │  AR(1), profils solaire + éolien
        │
        ▼
solve_stochastic_uc()       ←─ stochastic.py
        │  deux étapes, délestage/écrêtage
        │  calcul VSS
        │
        ▼
visualization.py            ←─ figures matplotlib
```

---

## Modèle mathématique (résumé)

**Dispatch économique (période unique) :**

```
min  Σ_g C_g(p_g)           avec C_g(p) = a_g + b_g·p + c_g·p²  (approx. PWL)
s.t. Σ_g p_g - Σ_b load_b = 0                    (équilibre)
     p_min_g · u_g ≤ p_g ≤ p_max_g · u_g          (capacité)
     |flow_ij| ≤ cap_ij                            (transport)
     Σ_g (p_max_g - p_g) · u_g ≥ reserve_req      (spinning reserve)
```

**Unit Commitment (horizon T) :** ajoute les contraintes temporelles sur `u[g,t]`, `su[g,t]`, `sd[g,t]` + coûts de démarrage/arrêt.

**UC Stochastique :** première étape sur `u`, deuxième étape sur `p, flow, ls, curt` pour chaque scénario `s`.

---

## Instances de test

| Instance | Bus | Lignes | Générateurs | Usage |
|----------|-----|--------|-------------|-------|
| `three_bus_toy` | 3 | 3 | 3 | Tests unitaires, vérification |
| `six_bus_congested` | 6 | 7 | 4 | Congestion, prix nodaux |
| `ieee14` | 14 | 20 | 5 | Benchmark standard IEEE |

---

## Notebooks de référence (usefull Notebooks/)

Ces notebooks CoursIA sont des **ressources pédagogiques en lecture seule**. Ne pas modifier.

| Fichier | Pertinence pour ce projet |
|---------|--------------------------|
| `CSP-5-Optimization.ipynb` | Squelette CP-SAT (Bin Packing, Knapsack) — patron utilisé dans dispatch_solver.py |
| `CSP-4-Scheduling.ipynb` | IntervalVar, NoOverlap, Cumulative — patterns min-up/down dans unit_commitment.py |
| `App-10-Portfolio.ipynb` | Contrainte de budget ↔ spinning reserve, PyGAD pour optimisation continue |
| `Search-9-LinearProgramming.ipynb` | Relaxation LP, bornes MIP — contexte théorique pour l'approximation PWL |

---

## Dépendances

```
ortools          # CP-SAT solver
matplotlib       # Visualisation
numpy            # Calculs numériques
dataclasses      # Structures de données (stdlib Python 3.7+)
```

Installation : `pip install ortools matplotlib numpy`
