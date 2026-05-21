Projet B1 — Équilibrage de chaîne d'assemblage (SALBP)
=======================================================

Groupe : Ilias Kalalou et Kaelan Grall
EPITA SCIA — Programmation par Contraintes 2026

Structure
---------

    B1-SALBP-IliasKalalou-KaelanGrall/
    ├── app.py                  Application Streamlit (4 modes)
    ├── benchmark.py            Module de benchmark batch
    ├── SALBP.ipynb             Notebook explicatif
    ├── instances/
    │   ├── __init__.py         Dataclasses Instance et Solution
    │   ├── toy.py              Instance jouet 11 tâches
    │   ├── library.py          7 instances classiques avec optima connus
    │   ├── scholl.py           25 instances Scholl/Otto + parser .IN2
    │   ├── otto.py             Parser format .alb avec validation
    │   ├── multimodel.py       Dataclass multi-modèles (MMALBP)
    │   ├── validators.py       Validation précédences (cycles, plage, doublons)
    │   └── otto_data/          25 fichiers .IN2 de la littérature
    ├── solvers/
    │   ├── cpsat.py            CP-SAT SALBP-1 et SALBP-2
    │   ├── plne.py             PLNE PuLP/CBC SALBP-1
    │   ├── rpw.py              Heuristique Ranked Positional Weight
    │   └── multimodel.py       CP-SAT MMALBP
    ├── visualisation/
    │   ├── gantt.py            Diagramme de Gantt
    │   ├── loads.py            Charges cumulées par station
    │   └── precedence.py       Graphe de précédence
    ├── tests/
    │   ├── test_instances.py   Tests des instances et validateurs
    │   ├── test_solvers.py     Tests des 3 solveurs sur optima connus
    │   └── test_otto_parser.py Tests robustesse parser .alb
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
2. Bibliothèque classique embarquée (7 instances avec optima connus : Mertens, Bowman, Jaeschke, Jackson, Mansoor, Mitchell, Heskiaoff)
3. Scholl/Otto préchargé (25 instances .IN2 de la littérature : Mertens, Bowman, Jaeschke, Jackson, Mansoor, Mitchell, Roszieg, Buxey, Sawyer30, Lutz1/2/3, Gunther, Kilbridge, Hahn, Warnecke, Tonge70, Wee-Mag, Arcus83/111, Mukherjee, Barthold/2, Heskia, Scholl)
4. Upload de fichier .alb (Otto et al. 2013)
5. Édition manuelle dans l'interface

Modèles et algorithmes
----------------------

| Solveur | Type        | Variante         | Optimal |
|---------|-------------|------------------|---------|
| CP-SAT  | Exact       | SALBP-1, SALBP-2 | Oui     |
| PLNE    | Exact       | SALBP-1          | Oui     |
| RPW     | Heuristique | SALBP-1          | Non     |
| CP-SAT  | Exact       | MMALBP           | Oui     |

Modes de l'application
----------------------

1. Solveur unique : choix d'une instance et d'un solveur
2. Comparaison côte-à-côte : CP-SAT + PLNE + RPW sur la même instance
3. Benchmark : batch sur 7 classiques ou 25 instances Scholl/Otto, avec gap vs optimum
4. Multi-modèles : variante MMALBP avec mix de demande

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
- Benchmarks : https://assembly-line-balancing.de
- Helgeson, W.B., Birnie, D.P. (1961) Assembly line balancing using the Ranked Positional Weight technique
