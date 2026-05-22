# D4 — Dispatch économique dans un réseau électrique

> Documentation du projet — EPITA SCIA 2026, Programmation par Contraintes

---

## C'est quoi le problème ?

Un réseau électrique doit produire exactement autant d'énergie qu'il en consomme, en permanence.
Plusieurs centrales (charbon, gaz, nucléaire, éolien, solaire) peuvent produire cette énergie, mais elles ont toutes des coûts différents.

**Le dispatch économique** répond à la question : *quelle centrale doit produire combien de MW pour satisfaire la demande au coût minimum, sans dépasser les capacités des lignes de transport ?*

Ce projet implémente ce problème sous trois formes de complexité croissante, toutes résolues avec **CP-SAT** (le solveur de Google OR-Tools) :

| Modèle | Ce qu'il résout |
|--------|----------------|
| **Dispatch économique (ED)** | Optimisation sur un seul instant |
| **Unit Commitment (UC)** | Planification ON/OFF sur 24 heures |
| **UC stochastique (SUC)** | Planification robuste face à l'incertitude renouvelable |

---

## Structure du projet

```
D4 - Dispatch dans un reseau electrique/
│
├── src/                        ← Code Python (bibliothèque)
│   ├── instance.py             ← Définition des données du réseau
│   ├── dispatch_solver.py      ← Solveur dispatch économique (1 période)
│   ├── unit_commitment.py      ← Solveur UC (24 heures)
│   ├── stochastic.py           ← Solveur UC stochastique (2 étapes)
│   ├── scenarios.py            ← Génération de scénarios renouvelables
│   └── visualization.py        ← Graphiques matplotlib
│
├── notebooks/
│   ├── demo.ipynb              ← Notebook de démonstration (9 sections)
│   └── build_demo.py           ← Script pour régénérer demo.ipynb
│
├── usefull Notebooks/          ← Références CoursIA (ne pas modifier)
│   ├── CSP-4-Scheduling.ipynb
│   ├── CSP-5-Optimization.ipynb
│   ├── App-10-Portfolio.ipynb
│   └── Search-9-LinearProgramming.ipynb
│
├── main.py                     ← Script de test rapide en ligne de commande
├── README.md                   ← Documentation mathématique détaillée
├── subject.md                  ← Énoncé original du projet
└── DOCUMENTATION.md            ← Ce fichier
```

---

## Démarrage rapide

```bash
# Installer les dépendances
pip install ortools matplotlib numpy

# Lancer un test complet (ED + UC + UC stochastique)
python main.py

# Lancer uniquement le dispatch économique (plus rapide)
python main.py --fast

# Contrôler les limites de temps
python main.py --uc-time 60 --suc-time 120
```

Ensuite, ouvrez `notebooks/demo.ipynb` dans Jupyter pour une démonstration interactive et commentée.

---

## Description de chaque fichier source

### `src/instance.py` — les données du réseau

Ce fichier définit les structures de données qui représentent un réseau électrique.
Tout le reste du code travaille avec ces objets.

| Classe | Ce qu'elle représente |
|--------|----------------------|
| `Bus` | Un nœud du réseau (une ville, une centrale). Attributs : identifiant, nom, charge en MW. |
| `Line` | Une ligne de transport entre deux bus. Attribut principal : capacité maximale en MW. |
| `Generator` | Une centrale électrique. Voir le tableau ci-dessous. |
| `PowerNetwork` | Le réseau complet : liste de bus, de lignes, de générateurs. |

**Attributs d'un générateur (`Generator`) :**

| Attribut | Signification |
|----------|---------------|
| `p_min`, `p_max` | Puissance minimale et maximale (MW) quand la centrale est allumée |
| `cost_a`, `cost_b`, `cost_c` | Coefficients du coût quadratique : `a + b·P + c·P²` ($/h) |
| `startup_cost`, `shutdown_cost` | Coût fixe de démarrage / d'arrêt ($) |
| `min_up`, `min_down` | Durée minimale ON / OFF (heures) |
| `ramp_up`, `ramp_down` | Variation maximale de puissance entre deux heures (MW/h) |
| `init_state`, `init_power` | État et puissance initiaux (avant l'horizon planifié) |
| `kind` | Type : `THERMAL`, `WIND`, ou `SOLAR` |

**Réseaux de test fournis :**

```python
from src.instance import three_bus_toy, six_bus_congested, ieee14, add_renewables

net = three_bus_toy(peak_load=300)   # 3 bus, 3 générateurs
net = six_bus_congested()            # 6 bus, congestion volontaire
net = ieee14()                       # 14 bus, standard IEEE
net = add_renewables(net, wind_bus=0, solar_bus=2, wind_cap=80, solar_cap=60)
```

---

### `src/dispatch_solver.py` — dispatch économique (1 période)

Ce solveur répond à la question : *pour ce réseau et cette demande en ce moment, comment répartir la production au moindre coût ?*

**Ce qu'il fait :**
1. Construit un modèle CP-SAT avec des variables de puissance pour chaque générateur
2. Approxime le coût quadratique par 6 droites tangentes (linéarisation convexe)
3. Ajoute les contraintes de transport (flux sur les lignes) et de réserve tournante
4. Lance le solveur et retourne la solution

**Utilisation :**

```python
from src.dispatch_solver import solve_economic_dispatch

sol = solve_economic_dispatch(net, time_limit_s=10)
print(sol.report())            # affiche le résumé textuel
print(sol.merit_order_cost())  # coût sans contraintes de transport (baseline)
```

**Paramètres importants :**

| Paramètre | Rôle | Défaut |
|-----------|------|--------|
| `loads` | Charge par bus (MW). Si `None`, utilise les charges définies dans le réseau. | `None` |
| `renewable_availability` | Dictionnaire `{"WIND@0": 0.7, ...}` — facteur de charge des renouvelables | `1.0` pour tous |
| `reserve_mw` | Réserve tournante requise (MW) | 10 % de la charge totale |
| `time_limit_s` | Temps maximum accordé au solveur | 30 s |

---

### `src/unit_commitment.py` — planification 24 heures

Ce solveur planifie les démarrages/arrêts de toutes les centrales sur un horizon de 24 heures (ou plus), en tenant compte des contraintes temporelles.

**Ce qu'il ajoute par rapport au dispatch simple :**

| Contrainte | Description |
|------------|-------------|
| **Temps minimum ON** | Une centrale démarrée doit rester allumée au moins `min_up` heures |
| **Temps minimum OFF** | Une centrale arrêtée doit rester éteinte au moins `min_down` heures |
| **Rampes** | `|P[g,t] - P[g,t-1]| <= ramp_up/down` — la puissance ne peut pas changer brutalement |
| **Coûts de démarrage/arrêt** | Chaque transition ON↔OFF est pénalisée dans l'objectif |

**Utilisation :**

```python
from src.unit_commitment import solve_unit_commitment, daily_load_profile

# Générer un profil de charge journalier réaliste
load = daily_load_profile(net, H=24, peak_factor=1.3, off_peak_factor=0.55, peak_hour=19)

uc = solve_unit_commitment(net, load, time_limit_s=40)
print(uc.report())
```

---

### `src/stochastic.py` — UC stochastique à deux étapes

Ce solveur résout le problème d'engagement des unités face à l'**incertitude de production renouvelable**.

**Le principe en deux étapes :**

```
Étape 1 (avant d'observer les renouvelables)
  → Décider : quelles centrales thermiques seront disponibles demain ?
  → Variables : u[g,t], su[g,t], sd[g,t]  — identiques pour tous les scénarios

Étape 2 (une fois le scénario réalisé)
  → Décider : combien chaque centrale produit-elle dans ce scénario ?
  → Variables : p[g,t,s], ls[b,t,s], curt[g,t,s]  — spécifiques à chaque scénario
```

Si la demande ne peut pas être satisfaite dans un scénario, on accepte un **délestage** (coupure) très pénalisé (5 000 $/MWh).
Si les renouvelables produisent trop, on accepte un **écrêtage** (50 $/MWh).

**Utilisation :**

```python
from src.stochastic import solve_stochastic_uc

sto = solve_stochastic_uc(net, load, scenarios, time_limit_s=60)
print(sto.report())
print(f"VSS = {det_cost - sto.expected_cost:.2f} $")
```

---

### `src/scenarios.py` — génération de scénarios renouvelables

Ce module génère des scénarios de production renouvelable pour l'UC stochastique.

**Fonctions disponibles :**

```python
from src.scenarios import solar_profile, wind_profile, sample_scenarios

# Profil moyen (déterministe)
mean_solar = solar_profile(T=24, peak_hour=13, width=4.5, max_capacity_factor=0.9)
mean_wind  = wind_profile(T=24, mean=0.45, night_bonus=0.10)

# Générer N scénarios avec bruit AR(1)
asset_means = {"WIND@0": mean_wind, "SOLAR@2": mean_solar}
scenarios = sample_scenarios(asset_means, n_scenarios=8, sigma=0.15, seed=42)
# scenarios est une liste de dicts : scenarios[s]["WIND@0"] = [cf_h0, cf_h1, ...]
```

Le bruit est généré par un processus autorégressif : les erreurs de prévision d'une heure à l'autre sont corrélées, ce qui est réaliste.

---

### `src/visualization.py` — graphiques

Toutes les fonctions retournent un objet `matplotlib.Figure`. Elles peuvent recevoir un `ax` existant pour s'intégrer dans une figure multi-panneaux.

| Fonction | Produit |
|----------|---------|
| `plot_network(net, flows)` | Topologie du réseau — nœuds, lignes, taux de charge (couleur + épaisseur) |
| `plot_single_period(sol)` | Barres de production par centrale, avec P_max en pointillés |
| `plot_dispatch_stack(sol)` | Aires empilées sur 24h + courbe de charge en pointillés noirs |
| `plot_schedule(sol)` | Heatmap ON/OFF par centrale et par heure, avec marqueurs de démarrage/arrêt |
| `plot_line_loadings(sol, top_k)` | Taux de charge des `top_k` lignes les plus sollicitées |
| `plot_cost_breakdown(sol)` | Décomposition du coût total en carburant / démarrages / arrêts |
| `plot_scenarios(scenarios, asset_id)` | Spaghetti plot des scénarios renouvelables autour de la moyenne |

---

## Comment les trois modèles s'enchaînent

```
1. Définir le réseau
   PowerNetwork = buses + lines + generators
          │
          ▼
2. Dispatch économique (1 période)
   solve_economic_dispatch(net, ...)
   → Production optimale ici et maintenant
          │
          ▼
3. Unit Commitment (24 heures)
   solve_unit_commitment(net, load_profile, ...)
   → Calendrier ON/OFF pour demain
          │
          ▼
4. Générer des scénarios renouvelables
   sample_scenarios(asset_means, n_scenarios, ...)
   → 4 à 8 réalisations possibles du vent/solaire
          │
          ▼
5. UC stochastique (robuste)
   solve_stochastic_uc(net, load, scenarios, ...)
   → Calendrier ON/OFF qui minimise le coût espéré
     sur tous les scénarios simultanément
```

---

## Modèle mathématique simplifié

### Dispatch économique

On minimise le coût total de production :

```
min   somme_g [ a_g + b_g * P_g + c_g * P_g^2 ]

sous :
  somme_g P_g[b] = load[b]              pour chaque bus b  (équilibre)
  |flow[i,j]| <= capacity[i,j]          pour chaque ligne  (transport)
  P_min[g] * u[g] <= P[g] <= P_max[g] * u[g]              (capacité)
  somme_g (P_max[g] - P[g]) * u[g] >= reserve              (sécurité)
```

Le coût quadratique est approximé par K=6 droites tangentes pour rester dans le cadre linéaire de CP-SAT.

### Unit Commitment (ajouts)

Pour chaque heure `t` et chaque générateur `g` :

```
u[g,t] - u[g,t-1] = su[g,t] - sd[g,t]           (lien état/transitions)
somme_{t'=t}^{t+min_up-1} u[g,t'] >= min_up * su[g,t]   (temps min ON)
somme_{t'=t}^{t+min_down-1} (1 - u[g,t']) >= min_down * sd[g,t]  (temps min OFF)
|P[g,t] - P[g,t-1]| <= ramp * u[g,t]             (rampe)
```

### UC stochastique (ajouts)

Les variables de 1re étape `u, su, sd` sont partagées entre tous les scénarios.
Les variables de 2e étape `p[s], flow[s], ls[s], curt[s]` sont indépendantes par scénario.
L'objectif devient : `min coût_engagement + somme_s prob[s] * coût_opération[s]`

---

## Instances de test disponibles

| Instance | Bus | Lignes | Générateurs | Charge totale | Usage recommandé |
|----------|-----|--------|-------------|--------------|-----------------|
| `three_bus_toy` | 3 | 3 | 3 | 300 MW | Déboguer, comprendre le modèle |
| `six_bus_congested` | 6 | 7 | 4 | 340 MW | Tester la gestion de congestion |
| `ieee14` | 14 | 20 | 5 | ~260 MW | Valider les performances sur instance réaliste |

---

## Notebooks de référence pédagogique

Ces notebooks proviennent des cours CoursIA. Ils ne font pas partie du projet, mais illustrent les concepts utilisés. **Ne pas modifier.**

| Fichier | Concept illustré | Lien avec ce projet |
|---------|-----------------|---------------------|
| `CSP-5-Optimization.ipynb` | CP-SAT : Bin Packing, Knapsack, Portfolio | Structure de base des solveurs dans `dispatch_solver.py` |
| `CSP-4-Scheduling.ipynb` | IntervalVar, NoOverlap, Cumulative (JSSP, Nurse Scheduling) | Patterns de contraintes temporelles dans `unit_commitment.py` |
| `App-10-Portfolio.ipynb` | Optimisation de portefeuille avec PyGAD | Analogie contrainte de budget ↔ spinning reserve |
| `Search-9-LinearProgramming.ipynb` | Programmation linéaire, relaxation LP, MIP | Contexte théorique pour l'approximation PWL du coût quadratique |

---

## Dépendances

```
ortools      # Solveur CP-SAT de Google
matplotlib   # Visualisation
numpy        # Calculs numériques
```

```bash
pip install ortools matplotlib numpy
```

Python 3.8+ requis. Le module `dataclasses` est inclus dans la bibliothèque standard.
