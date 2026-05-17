# Note 03 — Statut des benchmarks CATS

Contexte : intégration du générateur CATS officiel (issue #5).
Statut : **résolu** (clos par PR #2 sur le parser ; cette note est la trace de la décision).

## Contexte

Le sujet (livrable 4) demande explicitement *"Évaluer sur les benchmarks
CATS"*. Une première itération utilisait uniquement des distributions
**inspirées** de CATS, générées par notre propre `wdp/generator.py`
(livrée dans le cadre de l'issue #1). Cette note documente le passage aux
benchmarks CATS officiels durant le travail sur l'issue #3 (parser et dataset).

## Résolution

Le générateur **CATS officiel** (Leyton-Brown, source C++ sur
https://github.com/kevinlb1/CATS) est désormais utilisé. Procédure :

1. Clone du dépôt et compilation locale via le backend **lp_solve 4.0**
   (CPLEX optionnel, désactivé). Ajustements faits sur Makefile pour
   compiler avec `clang/g++` modernes :
   - flag `-Wno-c++11-narrowing` pour les littéraux mixés int/double
     dans `matching.cpp` ;
   - `bison -d` (et non `bison -y`) pour produire `y.tab.h` requis par
     le scanner flex de lp_solve.
2. Exécution sur 5 distributions × seeds variées via le binaire `cats` :
   - `arbitrary`, `regions`, `paths`, `scheduling` à 30 items × 100 bids
     (3 seeds chacun) ;
   - `matching` à 32 items × 100 bids (3 seeds — `matching` exige
     `goods % 4 == 0`) ;
   - 4 instances supplémentaires à plus grande échelle (60 items ×
     200 bids).
   - Total : **18 fichiers** dans `data/cats/`.
3. Parser Python implémenté dans
   [`wdp/cats_parser.py`](../wdp/cats_parser.py) qui :
   - parse l'en-tête CATS (`goods`, `bids`, `dummy`) ;
   - distingue items réels vs dummy goods ;
   - **reconstruit les groupes XOR** depuis les dummy goods (deux bids
     partageant un dummy = mutuellement exclusifs, convention
     standard CATS) ;
   - ramène les prix entiers de `-int_prices` à leur valeur flottante
     en divisant par `bid_alpha` (1000 par défaut) ;
   - expose deux stratégies de regroupement bidder via
     `BidderGrouping`: `PER_BID` (1 bidder par bid, défaut prudent)
     ou `PER_DUMMY` (clustering transitif).

## Vérification

- Les 18 instances sont parsées sans erreur.
- CP-SAT les résout toutes à `OPTIMAL` en moins de 60ms.
- CP-SAT et PLNE accordent leurs valeurs d'objectif (test
  `test_cats_cpsat_milp_agree` paramétré sur **une instance par
  distribution** — arbitrary, matching, paths, regions, scheduling).
- `test_cats_solver_output_respects_constraints` vérifie en plus
  l'exclusivité d'item, la satisfaction des groupes XOR, et la
  cohérence du revenu rapporté avec la somme des prix gagnants
  (parametré une-par-distribution).
- Tests pytest dédiés : **31 cas** dans
  [`tests/test_cats_parser.py`](../tests/test_cats_parser.py).
- `PRICE_SCALE` du solveur CP-SAT a été aligné sur `bid_alpha=1000`
  du générateur CATS pour garantir la précision bit-exacte des prix
  CATS (3 décimales) côté CP-SAT.

## Note sur le langage d'offres

CATS utilise **OR-of-XOR** (un bidder peut soumettre plusieurs clauses
XOR via plusieurs dummy goods). Notre générateur interne reste
**XOR par bidder** (cf. [`research/02_*`](02_greedy_los_approximation.md)
et le README). En important du CATS, on récupère donc des instances
strictement plus expressives : la WDP supporte déjà les `xor_groups`
arbitraires (un par dummy good), donc aucune adaptation du solveur
n'est nécessaire.

Conséquence pour notre framing théorique : le parser CATS génère un
nombre de bidders égal au nombre de bids (mode `PER_BID`), et délègue
toute la sémantique d'agrégation aux groupes XOR explicites. Le
mode `PER_DUMMY` est disponible si on veut grouper logiquement.

## Hors scope volontaire

Le générateur CATS expose plusieurs variantes que nous n'utilisons
**délibérément** pas :

- **L1–L8** : 8 distributions "Legacy" du papier Leyton-Brown 2000
  (artificielles, antérieures à CATS, conservées pour compatibilité
  comparative). Notre objectif est de couvrir les **5 distributions
  économiquement motivées** (arbitrary, matching, paths, regions,
  scheduling) qui sont la contribution principale de CATS ; les
  L1–L8 sont accessibles via `cats -d L1 ...` si besoin futur.
- **Variantes `-npv` / `-upv`** (Normal vs Uniform Private Values)
  pour `arbitrary` et `regions` : ce sont des modèles statistiques
  alternatifs sur la valuation. Sans étude comparative spécifique
  des modèles statistiques, on s'en tient au défaut CATS (UPV).

## Pistes laissées ouvertes

- Échelle : on pourrait générer des `g100_b500` ou `g200_b1000` pour
  benchmarker le régime stress contre nos solveurs exacts.
- `bidder_grouping=PER_DUMMY` n'est pas encore évalué côté
  performance ; il pourrait changer la difficulté du problème
  (groupes XOR plus structurés).
