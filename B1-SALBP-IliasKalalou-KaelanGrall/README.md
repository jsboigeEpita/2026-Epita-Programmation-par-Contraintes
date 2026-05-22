Projet B1 — Équilibrage de chaîne d'assemblage (SALBP)
=======================================================

Groupe : Ilias Kalalou et Kaelan Grall
EPITA SCIA — Programmation par Contraintes 2026

Couverture du sujet
-------------------

| Objectif énoncé                                      | État    |
|------------------------------------------------------|---------|
| 1. SALBP-1 et SALBP-2 en CP-SAT                      | Couvert |
| 2. Précédence + cycle + exclusion mutuelle           | Couvert |
| 3. Variantes multi-modèles (MMALBP) ET multi-objectifs | Couvert |
| 4. Benchmark sur instances de référence              | Couvert |
| 5. Comparaison CP-SAT vs RPW vs PLNE                 | Couvert |

Structure
---------

    B1-SALBP-IliasKalalou-KaelanGrall/
    ├── app.py                    Application Streamlit (5 modes)
    ├── benchmark.py              Module de benchmark batch
    ├── SALBP.ipynb               Notebook explicatif
    ├── instances/
    │   ├── __init__.py           Dataclasses Instance et Solution
    │   ├── toy.py                Instance jouet 11 tâches
    │   ├── library.py            7 instances classiques avec optima connus
    │   ├── scholl.py             25 instances Scholl 1993 + parser .IN2
    │   ├── otto.py               Parser format .alb (Otto 2013) avec validation
    │   ├── multimodel.py         Dataclass multi-modèles (MMALBP)
    │   ├── validators.py         Validation précédences (cycles, plage, doublons)
    │   └── otto_data/            25 fichiers .IN2 de la littérature
    ├── solvers/
    │   ├── cpsat.py              CP-SAT SALBP-1 et SALBP-2
    │   ├── plne.py               PLNE PuLP/CBC SALBP-1
    │   ├── rpw.py                Heuristique Ranked Positional Weight
    │   ├── multimodel.py         CP-SAT MMALBP
    │   └── biobjective.py        Front de Pareto + somme pondérée (m, C)
    ├── visualisation/
    │   ├── gantt.py              Diagramme de Gantt
    │   ├── loads.py              Charges cumulées par station
    │   ├── precedence.py         Graphe de précédence
    │   └── pareto.py             Front de Pareto (m vs C)
    ├── tests/
    │   ├── test_instances.py     Tests instances, library, validators
    │   ├── test_solvers.py       Tests CP-SAT, PLNE, RPW sur optima
    │   ├── test_otto_parser.py   Tests robustesse parser .alb
    │   ├── test_scholl_parser.py Tests parser .IN2
    │   ├── test_multimodel.py    Tests MMALBP
    │   └── test_biobjective.py   Tests Pareto + weighted sum
    └── requirements.txt

Installation
------------

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Lancement
---------

Application interactive :

    streamlit run app.py

Tests unitaires :

    pytest

Sources d'instances supportées
-------------------------------

1. Instance jouet (11 tâches, fabriquée à la main)
2. Bibliothèque classique embarquée (7 instances avec optima connus :
   Mertens, Bowman, Jaeschke, Jackson, Mansoor, Mitchell, Heskiaoff)
3. Scholl 1993 préchargé (25 instances .IN2 de la littérature historique :
   Mertens, Bowman, Jaeschke, Jackson, Mansoor, Mitchell, Roszieg, Buxey,
   Sawyer30, Lutz1/2/3, Gunther, Kilbridge, Hahn, Warnecke, Tonge70,
   Wee-Mag, Arcus83/111, Mukherjee, Barthold/2, Heskia, Scholl).
   Ces instances sont un sous-ensemble du catalogue référencé par
   Otto et al. (2013).
4. Upload de fichier .alb (format Otto et al. 2013)
5. Édition manuelle dans l'interface

Modèles et algorithmes
----------------------

| Solveur        | Type         | Variante           | Optimal |
|----------------|--------------|--------------------|---------|
| CP-SAT         | Exact        | SALBP-1, SALBP-2   | Oui     |
| PLNE (PuLP/CBC) | Exact        | SALBP-1            | Oui     |
| RPW            | Heuristique  | SALBP-1            | Non     |
| CP-SAT MMALBP  | Exact        | Multi-modèles      | Oui     |
| Front Pareto   | Exact        | Bi-objectif (m, C) | Oui     |
| Somme pondérée | Exact        | α·m + β·max_charge | Oui     |

Modes de l'application
----------------------

1. Solveur unique : choix d'une instance et d'un solveur
2. Comparaison côte-à-côte : CP-SAT + PLNE + RPW sur la même instance
3. Benchmark : batch sur 7 classiques ou 25 instances Scholl avec gap vs optimum
4. Multi-modèles : variante MMALBP avec mix de demande
5. Bi-objectif (Pareto) : front entre m et C + résolution pondérée α·m + β·max_charge

Cycle times et optima connus
-----------------------------

Le module `instances/scholl.py` embarque les cycles standards de la littérature
pour chaque instance et leur optimum prouvé, permettant un benchmark rigoureux
avec calcul automatique du gap.

Références
----------

- Scholl A. (1999) Balancing and Sequencing of Assembly Lines, Physica-Verlag
- Otto A., Otto C., Scholl A. (2013) Systematic Data Generation for SALBP, EJOR 228(1)
- Boysen N., Fliedner M., Scholl A. (2007) A Classification of ALBP, EJOR 183(2)
- Benchmarks publics : https://assembly-line-balancing.de
- Helgeson W.B., Birnie D.P. (1961) Assembly line balancing using the Ranked Positional Weight technique
- Pinto P.A., Dannenbring D.G., Khumawala B.M. (1981) Branch and Bound and heuristic procedures for assembly line balancing with paralleling of stations, IJPR
