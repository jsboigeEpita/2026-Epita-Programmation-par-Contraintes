 # VM Allocation Optimization

## Instructions

Le VM Scheduling Problem consiste a allouer des machines virtuelles (VMs) avec des caracteristiques heterogenes (CPU, RAM, stockage, bande passante) sur des serveurs physiques, sous des contraintes de capacite, d'affinite (certaines VMs doivent etre co-localisees ou separees pour des raisons de securite/performance), et de resilience (anti-affinite pour la tolerance aux pannes). C'est un probleme de Bin Packing multi-dimensionnel avec des contraintes d'affinite, directement modelisable en CP-SAT.

### Objectifs
- Modeliser le VM Scheduling comme un Bin Packing multi-dimensionnel avec contraintes d'affinite en CP-SAT
- Implementer les contraintes de capacite (CPU, RAM, stockage), d'affinite/anti-affinite, et de resilience
- Ajouter la consolidation dynamique (migration de VMs) et la minimisation de la fragmentation
- Evaluer sur des instances reelles (Google Cluster Trace) et des benchmarks synthetiques
- Comparer avec le First Fit Decreasing (FFD) et un modele PLNE sur les memes instances

### Notebooks CoursIA pertinents

| Notebook | Chemin | Pertinence |
|----------|--------|------------|
| CSP-5 Optimization | [Search/Part2-CSP/CSP-5-Optimization.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-5-Optimization.ipynb) | Bin Packing, Knapsack |
| CSP-1 Fondamentaux | [Search/Part2-CSP/CSP-1-Fundamentals.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-1-Fundamentals.ipynb) | Modelisation CSP |
| Search-9 Programmation lineaire | [Search/Part1-Foundations/Search-9-LinearProgramming.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part1-Foundations/Search-9-LinearProgramming.ipynb) | PLNE, relaxation |
| CSP-7 Soft Constraints | [Search/Part2-CSP/CSP-7-Soft.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-7-Soft.ipynb) | Preferences, penalites |

### References externes
- Mann, Z.A. (2015). "Allocation of Virtual Machines in Cloud Data Centers - A Survey." *European Journal of Operational Research*, 246(3), 779-798. [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0377221715003633)
- Google Cluster Trace. [GitHub](https://github.com/google/cluster-data)
- Beloglazov, A., & Buyya, R. (2012). "Optimal Online Deterministic Algorithms and Adaptive Heuristics for Energy and Performance Efficient Dynamic Consolidation." *Future Generation Computer Systems*, 28(5), 753-768. [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0167739X11000689)
- Salimian, A., et al. (2017). "A Survey of Energy-Aware Scheduling in Cloud Computing." *The Journal of Supercomputing*. [Springer](https://link.springer.com/article/10.1007/s11227-017-2190-3)

### Difficulte : 3/5