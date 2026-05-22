# D4 — Dispatch économique dans un réseau électrique

**EPITA SCIA 2026 — Programmation par Contraintes**
*Martin Couturier · Arthur Philippe · Xavier Ghostine*

---

## Présentation

Ce projet résout le **dispatch économique** d'un réseau électrique avec
**Google OR-Tools CP-SAT**. Trois niveaux de complexité sont couverts :

1. **Economic Dispatch (ED)** — instant t : produire la demande au moindre coût
   en respectant les capacités de génération et de transport.
2. **Unit Commitment (UC)** — horizon de 24 h : décider quand allumer / éteindre
   chaque centrale (coûts de démarrage, temps minimum de marche/arrêt, ramps).
3. **Stochastic Unit Commitment (SUC)** — UC à deux étages avec scénarios
   d'éolien / solaire ; le commitment est figé avant le tirage des aléas, le
   dispatch s'adapte ensuite.

Tous les solveurs sont **purement entiers** (CP-SAT) : les puissances sont
exprimées en MW, les coûts en cents, et le terme quadratique
`a + b·P + c·P²` est approximé par sa borne inférieure convexe formée de `K`
tangentes.

## Structure du projet

```
D4 - Dispatch dans un reseau electrique/
├── README.md                       # ce fichier
├── pyproject.toml                  # métadonnées Python + dépendances
├── requirements.txt
├── main.py                         # smoke-test CLI (`python main.py --fast`)
├── src/
│   ├── instance.py                 # PowerNetwork, Bus, Line, Generator + IEEE 14-bus
│   ├── dispatch_solver.py          # Economic Dispatch (CP-SAT mono-période)
│   ├── unit_commitment.py          # UC multi-période (24 h) avec coûts de start-up
│   ├── stochastic.py               # SUC deux-étages avec scénarios renouvelables
│   ├── scenarios.py                # profils éolien/solaire + échantillonnage AR(1)
│   └── visualization.py            # plots matplotlib (réseau, stack, schedule, …)
├── notebooks/
│   ├── demo.ipynb                  # démo end-to-end (à ouvrir en premier)
│   └── build_demo.py               # script qui (re-)génère demo.ipynb
└── usefull Notebooks/              # notebooks CoursIA de référence
```

## Installation et démarrage rapide

```bash
cd "D4 - Dispatch dans un reseau electrique"
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (a) smoke test en CLI — ED + UC + SUC sur l'instance toy
python main.py            # ~2 min
python main.py --fast     # ED seul, quelques secondes

# (b) démo interactive
jupyter notebook notebooks/demo.ipynb
```

L'instance toy (3 bus) résout en quelques millisecondes ;
IEEE 14-bus en < 1 s ; le UC 24 h en 30-60 s ; le SUC à 4 scénarios en 60-120 s.

## Modélisation

### Notations

| Symbole | Type | Signification |
|---------|------|---------------|
| `G`, `B`, `L`, `T` | ensembles | générateurs, buses, lignes, périodes |
| `S` | ensemble | scénarios renouvelables |
| `P[g,t]`     | entier ≥ 0 | puissance de `g` à l'instant `t` (MW) |
| `u[g,t]`     | binaire    | 1 si `g` est allumé à `t` |
| `su[g,t]`, `sd[g,t]` | binaire | démarrage / arrêt à `t` |
| `flow[ℓ,t]`  | entier signé | flux MW sur la ligne `ℓ` |
| `ls[b,t]`    | entier ≥ 0 | délestage (load-shed) au bus `b` (SUC) |
| `curt[g,t]`  | entier ≥ 0 | curtailment d'un renouvelable (SUC) |
| `Π[s]`       | proba | poids du scénario `s` |

### Variables et contraintes — Economic Dispatch

**Variables.** `P[g] ∈ [0, p_max]` entier, `u[g] ∈ {0,1}`,
`flow[ℓ] ∈ [-cap, +cap]`.

**Contraintes.**

- **Capacité par générateur** : `p_min · u[g] ≤ P[g] ≤ p_max · u[g]`.
- **Équilibre par bus** : ∀ b,
  `Σ_{g@b} P[g] + Σ_{ℓ:to=b} flow[ℓ] − Σ_{ℓ:from=b} flow[ℓ] = load[b]`.
- **Capacité des lignes** : `|flow[ℓ]| ≤ capacity[ℓ]` (modèle de transport).
- **Réserve tournante** : `Σ_{g thermal} (p_max · u[g] − P[g]) ≥ R`.

**Coût quadratique convexe en CP-SAT entier.** Pour chaque centrale thermique
`g` et `K` points d'échantillonnage `P_k ∈ [p_min, p_max]` on ajoute une
contrainte de **tangente** :

```
cost[g] ≥ slope_k · P[g] + intercept_k       enforced if u[g] = 1
cost[g] = 0                                  enforced if u[g] = 0
```

où `slope_k = b + 2c·P_k`, `intercept_k = a − c·P_k²`. La fonction étant
convexe, le **sup des tangentes** est exact à l'optimum.

**Objectif** : `min Σ_g cost[g]`.

### Extension Unit Commitment (24 h)

Tous les indices passent à `[g, t]`. On ajoute :

- **Lien démarrage / arrêt** : `su[g,t] − sd[g,t] = u[g,t] − u[g,t-1]`.
- **Min up** : `u[g,t+k] ≥ su[g,t]` pour `k = 1, …, min_up − 1`.
- **Min down** : `u[g,t+k] ≤ 1 − sd[g,t]` pour `k = 1, …, min_down − 1`.
- **Ramps** : `P[g,t] − P[g,t-1] ≤ ramp_up + p_min · su[g,t]`
  (idem en `ramp_down + p_min · sd[g,t]` pour la descente — le terme
  supplémentaire `p_min · su` permet à une unité de démarrer à sa puissance
  minimale même si `ramp_up < p_min`).
- **Coûts** : `Σ_t Σ_g [ fuel(P[g,t]) + startup_cost·su[g,t] + shutdown_cost·sd[g,t] ]`.

### Extension Stochastic UC

**Première étape (avant tirage des aléas)** : `u`, `su`, `sd` — identiques
pour tous les scénarios.

**Deuxième étape (après tirage)** : `P[g,t,s]`, `flow[ℓ,t,s]`, `ls[b,t,s]`,
`curt[g,t,s]` — propres à chaque scénario.

Le renouvelable disponible au scénario `s` est plafonné par la capacité × le
facteur de capacité tiré : `P[g,t,s] + curt[g,t,s] = avail[g,t,s]`.

**Objectif** :

```
min  Σ_s Π[s] · [ fuel(P[·,·,s]) + λ_curt·curt[·,·,s] + λ_LS·ls[·,·,s] ]
   + Σ_t Σ_g [ startup_cost·su[g,t] + shutdown_cost·sd[g,t] ]
```

avec `λ_LS = 5 000 $/MWh` (lost load) et `λ_curt = 50 $/MWh`. Le délestage
n'est utilisé qu'en dernier recours pour préserver la faisabilité.

## Instances fournies

| Instance | Buses | Lignes | Générateurs | Charge crête | Note |
|----------|------:|------:|------------:|------------:|------|
| `three_bus_toy(peak_load)`  | 3  | 2  | 3 thermal           | 300 MW | démo introductif |
| `six_bus_congested()`       | 6  | 7  | 4 thermal           | 340 MW | montre l'effet d'une ligne congestionnée |
| `ieee14()`                  | 14 | 20 | 5 thermal           | 259 MW | test case standard IEEE |
| `add_renewables(net, …)`    | —  | —  | +1 wind +1 solar    | —      | greffe wind/solar sur n'importe quel réseau |

## Quelques résultats

Mesures sur un MacBook M-series (8 workers, time limit 30-60 s).

| Instance | Modèle | Coût | Temps mur | Statut |
|----------|--------|------:|------------:|-------:|
| 3-bus toy           | ED              | 7 360.96 $/h     | 0.03 s | OPTIMAL |
| 6-bus congested     | ED              | 11 713.67 $/h    | 0.00 s | OPTIMAL |
| 6-bus *(merit-order, sans lignes)* | baseline | 6 251.20 $/h | — | — |
| IEEE 14-bus         | ED              | 5 911.96 $/h     | 0.23 s | OPTIMAL |
| 3-bus toy           | UC 24 h         | 148 424.76 $     | 30 s   | FEASIBLE (gap 13 %) |
| 3-bus toy + W+S     | SUC, 4 scénarios| 117 164.49 $     | 60 s   | FEASIBLE |

Le surcoût de **+87 %** sur 6-bus (`11 713 $` vs `6 251 $`) illustre bien le
fait qu'optimiser la dispatch sans tenir compte du réseau n'a pas de sens
dès qu'il y a congestion.

## Notebooks CoursIA pertinents

| Notebook | Pertinence |
|----------|-----------|
| `Search-9 Programmation lineaire`  | borne MIP du dispatch ; relaxation linéaire des contraintes de capacité |
| `CSP-5 Optimization`               | optimisation sous contraintes en CP-SAT (squelette du solveur) |
| `CSP-4 Scheduling`                 | `IntervalVar` et `NoOverlap` — gabarit pour les contraintes min-up / min-down |
| `App-10 Portfolio`                 | optimisation budgétaire — analogue à la réserve tournante |

## Références

- Wood, A.J. & Wollenberg, B.F. (2012). *Power Generation, Operation, and Control* (3rd ed.). Wiley.
- Padhy, N.P. (2004). *Unit Commitment — A Bibliographical Survey.* IEEE TPS 19(2).
- IEEE Power Systems Test Case Archive: <https://labs.ece.uw.edu/pstca/>
- Google OR-Tools CP-SAT: <https://developers.google.com/optimization/cp/cp_solver>
