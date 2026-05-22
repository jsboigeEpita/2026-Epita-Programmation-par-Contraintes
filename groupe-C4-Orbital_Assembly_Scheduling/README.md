# C4 - Orbital Assembly Scheduling (CP-SAT)

Projet EPITA 2026 de Programmation par Contraintes pour le sujet C4.

Le probleme consiste a planifier des manoeuvres d'assemblage orbital entre modules autonomes. Le modele prend en compte les fenetres de lancement, la visibilite station sol, les precedences d'assemblage, les separations de securite, le budget carburant total et la capacite delta-v concurrente.

## Livrables

- `rapport.md`: rapport final du projet, avec formulation, resultats et limites.
- `README.md`: presentation rapide du rendu et commandes de reproduction.
- `benchmark_overview.png`: synthese graphique du benchmark CP-SAT vs glouton.
- `single_instance_schedule_comparison.png`: comparaison visuelle d'un planning CP-SAT et glouton.
- `src/`: code source du modele, du generateur d'instances, de la baseline et des outils de validation.
- `run_experiments.py`: script de reproduction du benchmark.
- `results/`: sorties CSV et figures produites par les experiences.
- `notebook.ipynb`: annexe explicative et exploratoire.

## Structure du code

- `src/domain.py`: structures de donnees du probleme.
- `src/orbit_physics.py`: formules orbitales simplifiees et discretisation.
- `src/instance_generator.py`: generation d'instances synthetiques LEO/GEO.
- `src/solver_cp_sat.py`: modele CP-SAT principal.
- `src/baseline_greedy.py`: baseline gloutonne.
- `src/validation.py`: verification de faisabilite des plannings.
- `src/experiments.py`: pipeline de benchmark et agregations.
- `src/plotting.py`: generation des visualisations.
- `src/test_solver.py`: test de fumee reproductible sur une petite instance.

## Installation

```bash
python -m pip install -r requirements.txt
```

## Verification rapide

```bash
python -m src.test_solver
```

## Reproduire les resultats

```bash
python run_experiments.py
```

Sorties generees:

- `results/benchmark_raw.csv`
- `results/benchmark_summary.csv`
- `results/figures/benchmark_overview.png`
- `results/figures/single_instance_schedule_comparison.png`
- `benchmark_overview.png`
- `single_instance_schedule_comparison.png`
