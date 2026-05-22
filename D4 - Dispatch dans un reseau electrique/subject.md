## D4 - Dispatch dans un reseau electrique

Le dispatch economique (Economic Dispatch) consiste a determiner la production optimale de chaque centrale electrique d'un reseau pour satisfaire la demande a chaque instant, en minimisant le cout total de production tout en respectant les contraintes de capacite des lignes de transport, les limites de generation par centrale, et l'equilibre offre-demande en temps reel. Avec l'integration des energies renouvelables intermittentes (eolien, solaire), le probleme devient stochastique. La modelisation CP-SAT capture les contraintes discretes (on/off des centrales, demarrage minimum) et les contraintes lineaires de flux.

### Objectifs
- Modeliser le dispatch economique comme un probleme d'optimisation sous contraintes avec CP-SAT
- Implementer les contraintes de capacite de generation, de lignes de transport, et d'equilibre offre-demande
- Ajouter les couts de demarrage/arret des centrales (unit commitment) et les reserves de spinning
- Etendre au cas stochastique avec des scenarios de production renouvelable (eolien, solaire)
- Evaluer sur des instances IEEE (IEEE 14-bus, 30-bus, 118-bus) et des donnees RTE France

### Notebooks CoursIA pertinents

| Notebook | Chemin | Pertinence |
|----------|--------|------------|
| Search-9 Programmation lineaire | [Search/Part1-Foundations/Search-9-LinearProgramming.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part1-Foundations/Search-9-LinearProgramming.ipynb) | PLNE, simplex, optimisation lineaire |
| CSP-5 Optimization | [Search/Part2-CSP/CSP-5-Optimization.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-5-Optimization.ipynb) | Optimisation sous contraintes |
| CSP-4 Scheduling | [Search/Part2-CSP/CSP-4-Scheduling.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-4-Scheduling.ipynb) | IntervalVar, scheduling temporel |
| App-10 Portfolio | [Search/Applications/Hybrid/App-10-Portfolio.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Applications/Hybrid/App-10-Portfolio.ipynb) | Optimisation sous contraintes de budget |

### References externes
- Wood, A.J., & Wollenberg, B.F. (2012). "Power Generation, Operation, and Control." *Wiley*. [Wiley](https://www.wiley.com/en-us/Power+Generation%2C+Operation%2C+and+Control%2C+3rd+Edition-p-9780471790556)
- Padhy, N.P. (2004). "Unit Commitment - A Bibliographical Survey." *IEEE Transactions on Power Systems*, 19(2), 1196-1205. [IEEE](https://ieeexplore.ieee.org/document/1291440)
- IEEE Power Systems Test Case Archive. [University of Washington](https://labs.ece.uw.edu/pstca/)
- RTE France - Donnees en energie. [RTE](https://www.services-rte.com/fr/visualisez-les-donnees-publiees-par-rte.html)

### Difficulte : 4/5

