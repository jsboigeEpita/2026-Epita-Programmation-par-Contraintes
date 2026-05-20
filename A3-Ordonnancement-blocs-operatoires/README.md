# Groupe A3 — Ordonnancement de blocs opératoires

Planification d'interventions chirurgicales dans un bloc opératoire multi-salles
sous contraintes de disponibilité (chirurgiens, salles, équipements), avec
priorités d'urgence, temps de nettoyage entre interventions, et préférences de
chirurgiens. Trois approches sont comparées : CP-SAT (OR-Tools), heuristique
par règle de priorité, et recuit simulé.

## Structure

```
A3-Ordonnancement-blocs-operatoires/
├── src/
│   ├── __init__.py          # exports publics
│   ├── models.py            # Surgery, Surgeon, Room, Instance, Schedule
│   ├── instances.py         # générateur d'instances synthétiques
│   ├── cp_solver.py         # modèle CP-SAT (IntervalVar / NoOverlap / Cumulative)
│   ├── heuristics.py        # priority rule + recuit simulé
│   └── visualization.py     # diagrammes de Gantt et utilisation
├── notebooks/
│   └── A3_or_scheduling.ipynb
├── main.py                  # démo CLI
├── pyproject.toml
└── README.md
```

## Installation (uv)

```bash
uv sync
```

## Utilisation

CLI :

```bash
uv run main.py
```

Notebook :

```bash
uv run jupyter lab notebooks/A3_or_scheduling.ipynb
```

API :

```python
from src import generate_instance, solve_cp_sat, plot_gantt

instance = generate_instance(n_surgeries=12, n_rooms=3, n_surgeons=4, seed=0)
result = solve_cp_sat(instance, time_limit_s=10.0)
print(result.makespan, result.objective)
plot_gantt(result, instance)
```

## Formulation CP-SAT

Variables : pour chaque chirurgie *i*, un `IntervalVar(start_i, duration_i, end_i)`
plus une affectation booléenne `assign_{i,r}` à une salle *r* et `surg_{i,s}` à
un chirurgien *s* compatible.

Contraintes :

- **Salles** : `NoOverlap` sur les intervalles d'une même salle, incluant un
  délai de nettoyage `clean_r` ajouté à la durée.
- **Chirurgiens** : `Cumulative` de capacité 1 par chirurgien (un chirurgien
  ne peut opérer qu'une intervention à la fois).
- **Équipements** : `Cumulative` par type d'équipement (capacité = nombre
  d'unités disponibles).
- **Urgence** : les interventions d'urgence (`priority=URGENT`) doivent
  démarrer avant un délai limite `deadline_i`.
- **Préférence chirurgien** : si une intervention a un chirurgien préféré,
  un terme de pénalité est ajouté à l'objectif si un autre chirurgien est
  affecté.

Objectif (soft) :

$$\min \; \alpha \cdot \text{makespan} + \beta \cdot \sum_i w_i \cdot \text{wait}_i + \gamma \cdot \text{penalties}$$

où $w_i$ est le poids d'urgence (URGENT > ELECTIVE).

## Baselines

- **Priority rule** : tri des chirurgies par (urgence, deadline, durée) puis
  affectation gloutonne au plus tôt sur la première salle/chirurgien
  disponible.
- **Recuit simulé** : perturbation par swap/relocation sur la permutation des
  chirurgies, refroidissement géométrique.

## Références

- Cardoen, Demeulemeester & Beliën (2010). *European Journal of Operational
  Research*, 201(3), 921–932.
- Guerriero & Guido (2016). *Health Care Management Science*, 19, 89–114.
- OR-Tools — Scheduling : https://developers.google.com/optimization/scheduling
- van Oostrum et al. (2008). *Health Systems*, 1(1), 35–50.
