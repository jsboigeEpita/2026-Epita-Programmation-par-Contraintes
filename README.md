## A2 - Planification nutritionnelle (DIET Problem)

Le Diet Problem est un classique de la recherche operationnelle : determiner la combinaison d'aliments la moins coutee satisfaisant l'ensemble des besoins nutritionnels journaliers. Modelisable comme un programme lineaire en nombres entiers (Knapsack multi-dimensionnel), il se prete remarquablement a une modelisation CP-SAT avec des contraintes sur les calories, proteines, lipides, glucides, vitamines et mineraux. Le sujet s'etend naturellement vers la generation de menus hebdomadaires equilibres en ajoutant des contraintes de variete (ne pas manger le meme plat deux jours de suite), de saisonnalite, de budget, et de preferences alimentaires.

### Objectifs
- Modeliser le Diet Problem comme un knapsack multi-dimensionnel avec CP-SAT (variables binaires par aliment, contraintes nutritionnelles)
- Etendre le modele en planification de menus hebdomadaires avec contraintes de variete, budget et saisonnalite
- Integrer des preferences utilisateur comme soft constraints avec penalites ponderees
- Benchmarker sur les donnees USDA FoodData Central et les apports nutritionnels OMS/ANSES
- Comparer l'approche CP-SAT avec une resolution PLNE classique (OR-Tools linear solver)

### Notebooks CoursIA pertinents

| Notebook | Chemin | Pertinence |
|----------|--------|------------|
| CSP-5 Optimization | [Search/Part2-CSP/CSP-5.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-5.ipynb) | Knapsack, Bin Packing, optimisation |
| CSP-7 Soft Constraints | [Search/Part2-CSP/CSP-7.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-7.ipynb) | Penalites, preferences, compromis |
| Search-9 Programmation lineaire | [Search/Part1-Foundations/Search-9.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part1-Foundations/Search-9.ipynb) | PLNE, simplex, dualite |
| App-10 Portfolio Optimization | [Search/Applications/Hybrid/App-10.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Applications/Hybrid/App-10.ipynb) | Optimisation sous contraintes de budget |

### References externes
- Stigler, G.J. (1945). "The Cost of Subsistence." *Journal of Farm Economics*, 27(2), 303-314. [JSTOR](https://www.jstor.org/stable/1231810)
- USDA FoodData Central. [fdc.nal.usda.gov](https://fdc.nal.usda.gov/)
- ANSES - Apports nutritionnels conseilles. [anses.fr](https://www.anses.fr/en/content/nutrition)
- Briend, A., et al. (2020). "Modelling the Cost of a Diet: A Review." *Public Health Nutrition*. [Cambridge Core](https://www.cambridge.org/core/journals/public-health-nutrition)
- OR-Tools Linear Solver Example: Diet Problem. [Google Developers](https://developers.google.com/optimization/lp/glop)
