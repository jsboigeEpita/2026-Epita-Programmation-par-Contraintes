# Note 01 — Équivalence algébrique IR ↔ monotonie du welfare en VCG

Contexte : audit du module `wdp/vcg.py`, méthode `VCGResult.verify_properties`.

## Constat

Dans la version initiale de `verify_properties`, quatre propriétés étaient
testées : **(1) IR**, **(2) p_k ≥ 0**, **(3) revenue ≤ welfare**,
**(4) W_{-k}* ≤ W***.

Or, par construction de la formule de paiement VCG :

    p_k = W_{-k}* − (W* − v_k)

On a immédiatement :

    p_k ≤ v_k   ⇔   W_{-k}* ≤ W*

Les vérifications (1) et (4) sont donc **mathématiquement équivalentes**
quand `payments` est calculé à partir de la formule ci-dessus. Tester les
deux donne deux fois la même information, et masque le **vrai risque**
sous-jacent : si l'un des sous-WDP renvoie un statut `FEASIBLE` (et non
`OPTIMAL`) sous time-out, la valeur de `W_{-k}*` peut être inférieure à
la valeur optimale, sans qu'aucun de ces tests le détecte (la relation
p_k ≤ v_k reste mécaniquement vraie).

## Décision

1. Reformuler `verify_properties` pour distinguer **deux catégories** :
   - propriétés du mécanisme VCG : IR, losers-pay-zero, no-deficit ;
   - vérifications de consistance solveur : monotonie du welfare, statut
     OPTIMAL de chaque sous-résolution.
2. Tracer explicitement dans `VCGResult` la liste `non_optimal_solves`,
   alimentée par `run_vcg` à chaque appel solveur.
3. Reformuler la cellule notebook : la monotonie est nommée "solver
   consistency check", pas "propriété VCG". L'erreur de labelling était
   un piège théorique repérable par un correcteur.

## Référence pour la suite

- Vickrey 1961, *Counterspeculation, Auctions, and Competitive Sealed Tenders*.
- Clarke 1971, *Multipart pricing of public goods*.
- Groves 1973, *Incentives in teams*.
- Nisan 2007, *Algorithmic Game Theory*, chap. 9 (VCG mechanism).
