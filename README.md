# EPITA 2026 — Programmation par Contraintes

## Liste des sujets de projet

Ce document presente les sujets de projet pour le cours de Programmation par Contraintes (SCIA). Chaque sujet inclut une description detaillee, des references academiques et pratiques, des liens vers des ressources de bootstrapping (tutoriels, notebooks, benchmarks), et les technologies pertinentes.

> **Consignes de choix** : Chaque groupe doit forker ce depot et creer un dossier pour son projet contenant le code source, un notebook explicatif une UI ou une démo, et les slides de soutenance. Les livraisons se font via des pull requests regulieres idéalement.

---

## Modalites du projet

### Taille des groupes

| Taille | Bonus/Malus |
|--------|-------------|
| 3 personnes | Standard |
| 2 personnes | +1 point |
| 1 personne (solo) | +3 points |
| 4 personnes | -1 point |

### Bonus de TP

2 TPs rendus dans le semestre. Pour chaque TP :
- 0.5 point de bonus par exercice supplementaire rendu au-dela du minimum requis
- **1 point de bonus max par TP**, soit **2 points de bonus TP max au total**

Ces points s'ajoutent a la note de projet.

### Soutenance — Evaluation collegiale

La soutenance finale est evaluee de maniere **collegiale** (pairs + enseignants). Chaque groupe est note sur **4 criteres** (0-10 chacun) :

| Critere | Description |
|---------|-------------|
| **Qualite de la presentation** | Communication, clarte, pedagogie, qualite des slides, demonstrations |
| **Qualite theorique** | Principes CP/CSP utilises, classes d'algorithmes, contexte historique, explication des performances et limitations |
| **Qualite technique** | Livrables (code, notebook, UI), qualite du code, commits Git, demonstrations, resultats, perspectives |
| **Organisation** | Planning, repartition des taches, collaboration, activite Git, documentation |

**Note finale = somme des 4 criteres / 2 (echelle /20), ajustee du bonus/malus taille de groupe et des bonus TP.**

### Livrables attendus

- **Code source** documente dans un sous-dossier dedie (`groupe-XX-nom-sujet/`)
- **Notebook Jupyter** explicatif avec analyse et visualisations **OU** **UI/demo fonctionnelle** (au choix — un notebook tres complet peut tenir lieu de demo, et inversement)
- **Slides de soutenance** (PDF ou lien)
- **Pull Request** soumise au plus tard **2 jours avant la soutenance**

### Echeances

- **Date de soutenance** : en cours de confirmation avec la scolarite
- **Deadline PR** : 2 jours avant la soutenance

---

## Ressources communes a tous les sujets

### Solveurs et outils
- **Google OR-Tools CP-SAT** : le solveur de reference pour ce cours. [Documentation officielle](https://developers.google.com/optimization/cp/cp_solver), [Guide Python](https://developers.google.com/optimization/cp/introduction), [Exemples par probleme](https://github.com/google/or-tools/tree/stable/examples/python)
- **Z3 SMT Solver** : pour les problemes de verification et de raisonnement symbolique. [Documentation](https://z3prover.github.io/api/html/namespacez3py.html), [Tutoriel Python](https://ericpony.github.io/z3py-tutorial/guide-examples.htm)
- **MiniZinc** : langage de modelisation CP de haut niveau. [Tutoriel](https://www.minizinc.org/doc-2.5.5/en/), [Benchmarks](https://www.minizinc.org/challenge.html)
- **CPMpy** : interface Python pour CP avec backends multiples. [Documentation](https://cpmpy.readthedocs.io/), [Exemples](https://github.com/CPMpy/cpmpy/tree/master/examples)

### Benchmarks et instances
- **CSPLib** : bibliotheque de problemes CP de reference. [En ligne](https://www.csplib.org/)
- **OR-Library** : instances pour problemes d'OR. [Beasley OR-Library](http://people.brunel.ac.uk/~mastjjb/jeb/info.html)
- **MiniZinc Challenge Benchmarks** : instances de competition. [GitHub](https://github.com/minizinc/minizinc-benchmarks)

### Notebooks du cours CoursIA
Les notebooks suivants sont disponibles dans le depot CoursIA ([jsboige/CoursIA](https://github.com/jsboige/CoursIA)) et constituent des prerequis ou des points de depart pour les projets :
- **Search/Part1-Foundations/** : Search-1 (StateSpace), Search-3 (A*, heuristiques), Search-4 (Local Search), Search-9 (Programmation lineaire), Search-11 (Metaheuristiques)
- **Search/Part2-CSP/** : CSP-1 (Fondamentaux), CSP-4 (Scheduling, IntervalVar, NoOverlap, Cumulative), CSP-5 (Optimization, Bin Packing, Knapsack), CSP-6 (Hybridation CP+SAT, LLM+CSP), CSP-7 (Soft Constraints), CSP-9 (Distributed CSP)
- **Search/Applications/CSP/** : App-4 (Job-Shop Scheduling), App-8 (MiniZinc), App-11 (Picross)
- **Search/Applications/Hybrid/** : App-10 (Portfolio Optimization), App-13 (TSP Metaheuristics), App-17 (VRP avec SA, GA, ACO, CP-SAT)
- **SymbolicAI/SmartContracts/** : Serie de 27 notebooks (SC-0 a SC-26) couvrant blockchain, Solidity, verification formelle (SC-14), fuzz testing (SC-13), cryptographie ZKP/HE (SC-15/16)
- **SymbolicAI/Planners/** : Planners-1 a Planners-12 couvrant PDDL, Fast Downward, planification temporelle, HTN, LLM Planning
- **SymbolicAI/Linq2Z3.ipynb** : Z3 SMT Solver en C#
- **SymbolicAI/OR-tools-Stiegler.ipynb** : OR-Tools CP en C#
- **Sudoku/** : 18 notebooks couvrant Sudoku avec multiples solveurs (Z3, CP-SAT, backtracking)
- **GameTheory/** : 17+ notebooks couvrant Nash Equilibrium, Cooperative Games, Shapley Value, Mechanism Design
- **Integration LLM** : function calling avec OpenAI/MCP pour assister la modelisation CP. Voir [Function Calling - OpenAI](https://platform.openai.com/docs/guides/function-calling) et [MCP Specification](https://modelcontextprotocol.io/)

---

## Index des Sujets

### Categorie I : LLM + CSP Hybride

| # | Sujet | Difficulte |
|---|-------|------------|
| [I1](#i1---assistant-de-planification-conversationnel-llm--csp) | Assistant de planification conversationnel (LLM + CSP) | 3/5 |
| [I2](#i2---explicateur-de-solutions-cp-par-llm) | Explicateur de solutions CP par LLM | 3/5 |
| [I3](#i3---modelisation-cp-assistee-par-llm) | Modelisation CP assistee par LLM | 4/5 |

---

## I2 - Explicateur de solutions CP par LLM

L'explication de solutions CP consiste a generer des explications en langage naturel qui decrivent pourquoi une solution donnee est optimale (ou pourquoi aucune solution n'existe), quelles contraintes sont actives (binding), et comment modifier les contraintes pour obtenir un meilleur resultat. L'approche combine l'analyse des contraintes du solveur (shadows prices, conflict analysis) avec un LLM pour produire des explications comprehensibles par un non-expert. C'est un pont entre l'optimisation mathematique et l'intelligence artificielle dialoguee.

### Objectifs
- Extraire les informations structurelles d'une solution CP-SAT (contraintes actives, marges, conflits)
- Concevoir un pipeline d'explication : analyse du solveur, structuration des faits, generation en langage naturel
- Implementer les explications de type "pourquoi cette solution", "pourquoi pas X", et "comment ameliorer"
- Evaluer la qualite des explications avec des metriques automatiques et une evaluation humaine
- Comparer avec des explications template-based (sans LLM) sur la clarte et la precision

### Notebooks CoursIA pertinents

| Notebook | Chemin | Pertinence |
|----------|--------|------------|
| CSP-6 Hybridation CP+SAT | [Search/Part2-CSP/CSP-6-Hybridization.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-6-Hybridization.ipynb) | LLM+CSP |
| CSP-1 Fondamentaux | [Search/Part2-CSP/CSP-1-Fundamentals.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-1-Fundamentals.ipynb) | Modelisation, solutions |
| CSP-7 Soft Constraints | [Search/Part2-CSP/CSP-7-Soft.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-7-Soft.ipynb) | Compromis, marges |
| CSP-5 Optimization | [Search/Part2-CSP/CSP-5-Optimization.ipynb](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part2-CSP/CSP-5-Optimization.ipynb) | Optimalite |

### References externes
- Cyras, K., et al. (2021). "Explainable Constraint-Driven Scheduling." *AAAI*. [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/16677)
- Fox, M., et al. (2017). "Explainable Planning." *IJCAI Workshop on XAI*. [arXiv](https://arxiv.org/abs/1709.10256)
- Guidotti, R., et al. (2018). "A Survey of Methods for Explaining Black Box Models." *ACM Computing Surveys*, 51(5). [ACM](https://dl.acm.org/doi/10.1145/3236009)
- Rago, A., et al. (2023). "Argumentative Explanations for Constraint Optimization." *KR*. [CEUR](https://ceur-ws.org/Vol-3361/)

### Difficulte : 3/5

---

*Derniere mise a jour : Avril 2026*
*Contact : Equipe pedagogique Programmation par Contraintes, EPITA SCIA*

