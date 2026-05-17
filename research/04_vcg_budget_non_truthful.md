# Note 04 — VCG sous contrainte de budget : DSIC perdue

Contexte : module [`wdp/vcg.py`](../wdp/vcg.py), paramètre `enforce_budget=True` (issue #4).

## Constat

Le solveur impose la contrainte de budget sous la forme

    sum_{j} bid.price[j] * x[j]  <=  cap

(cf. [`wdp/solver_cpsat.py`](../wdp/solver_cpsat.py), lignes 96–111, et la
formulation symétrique dans [`wdp/solver_milp.py`](../wdp/solver_milp.py)).

Cette contrainte est exprimée **en fonction des prix déclarés** par les
bidders. Notons F l'ensemble des allocations admissibles. Alors F dépend
de `bid.price` : si un bidder change son prix déclaré, il modifie F et
peut donc influencer la solution optimale.

## Conséquence pour le théorème de Vickrey-Clarke-Groves

Le théorème classique (Vickrey 1961, Clarke 1971, Groves 1973) garantit
la *dominant-strategy incentive compatibility* (DSIC) **à condition que
F soit indépendant des rapports**. Les références centrales :

- Lavi, R. (2007). *Computationally Efficient Approximation Mechanisms*,
  chapitre 12 dans Nisan, Roughgarden, Tardos, Vazirani (eds.),
  *Algorithmic Game Theory*, §12.4.
- Borgs, C., Chayes, J., Immorlica, N., Mahdian, M., Saberi, A. (2005).
  *Multi-unit Auctions with Budget-Constrained Bidders*, EC.
- Dobzinski, S., Lavi, R., Nisan, N. (2008). *Multi-unit Auctions with
  Budget Limits*, FOCS.
- Nisan, N., Ronen, A. (2007). *Computationally Feasible VCG Mechanisms*,
  JAIR 29 (DSIC perdue dès que la maximisation est approximée).

Dans notre régime `enforce_budget=True`, F dépend des `bid.price` →
**DSIC perdue**. Il existe au moins une instance et une stratégie de
shading qui donne strictement plus de surplus que la déclaration honnête.

## Contre-exemple numérique

(Implanté comme test pytest `test_vcg_budget_admits_strict_manipulation`
dans [`tests/test_pedagogical.py`](../tests/test_pedagogical.py).)

Soient :

- 2 items : A, B
- 3 bidders : b1, b2, b3
- b1 désire {A}, valeur réelle v_1 = 8
- b2 désire {B}, valeur réelle v_2 = 8
- b3 désire {A, B}, valeur réelle v_3 = 9
- Budget global : C = 11

### Stratégie 1 — déclaration honnête (r_i = v_i)

Allocations candidates et coût (somme des prix déclarés) :

| Allocation | Items pris | Welfare déclaré | Coût | Faisable ? |
|------------|------------|-----------------|------|-----------|
| ∅          | —          | 0               | 0    | ✓ |
| {b1}       | {A}        | 8               | 8    | ✓ |
| {b2}       | {B}        | 8               | 8    | ✓ |
| {b3}       | {A,B}      | 9               | 9    | ✓ |
| {b1, b2}   | {A,B}      | 16              | 16   | ✗ (16 > 11) |

**Optimum dans F : {b3}**, welfare 9.

b1 perd → ne paie rien → surplus = 0.

### Stratégie 2 — shading (r_1 = 3, r_2 = 8, r_3 = 9)

Allocations candidates :

| Allocation | Welfare déclaré | Coût |
|------------|-----------------|------|
| {b1, b2}   | 3 + 8 = 11      | 11   ✓ (11 ≤ 11) |
| {b3}       | 9               | 9    ✓ |

**Optimum dans F : {b1, b2}**, welfare déclaré 11. b1 gagne A.

Paiement VCG de b1 :

    p_1 = W_{-1}(F)  -  (W(F)  -  r_1)
        = 9          -  (11    -  3)
        = 9 - 8
        = 1

Vrai surplus de b1 : v_1 − p_1 = 8 − 1 = **7**.

### Conclusion

7 > 0 strictement. Mentir (`r_1 = 3` au lieu de 8) procure à b1 un
surplus de 7, contre 0 en déclarant la vérité. **DSIC violée.**

## Algèbre : ce qui reste vrai mécaniquement

Bien que la truthfulness disparaisse, certaines propriétés survivent
**par construction de la formule** et de la contrainte de budget. On
les démontre rigoureusement ici.

### Hypothèse opérationnelle : *slack-monotonicity*

La contrainte de budget de notre code est de la forme

    sum_{j ∈ S} price[j]  <=  cap

(somme positive sur le sous-ensemble S des bids gagnants). Elle est
**slack-monotone** au sens où S' ⊆ S ⇒ si S satisfait la contrainte,
S' aussi (les prix sont positifs). Ce point est essentiel : l'argument
qui suit s'effondrerait pour des contraintes non monotones (par
exemple "exactement k gagnants").

### IR mécanique : `p_k <= v_k`

Posons p_k = W_{-k} − (W − v_k). On veut v_k − p_k ≥ 0, soit
W_{-k} ≤ W. C'est la **monotonie du welfare** : retirer les bids de k
restreint l'ensemble F (moins de bids disponibles), donc l'optimum ne
peut que stagner ou diminuer. ✓

### No-deficit mécanique : `sum_k p_k >= 0`

Pour un perdant k, p_k = 0 par construction (ne figure pas dans
`payments`).

Pour un gagnant k, on doit montrer p_k ≥ 0, soit W_{-k} ≥ W − v_k.

Considérons l'allocation x* (optimale dans F avec tous les bidders),
et notons x*_{−k} son sous-ensemble obtenu en retirant les bids de k.
Alors :

1. x*_{−k} est composé de bids dont le bidder n'est pas k → admissible
   au problème "sans k".
2. x*_{−k} respecte les contraintes d'item (sous-ensemble d'une
   allocation déjà disjointe).
3. x*_{−k} respecte les contraintes XOR pour j ≠ k (les groupes XOR
   par bidder sont disjoints).
4. x*_{−k} respecte la contrainte de budget par **slack-monotonicité** :
   on a retiré une masse v_k ≥ 0 de la somme `Σ price·x`, donc la
   contrainte est *plus* relâchée.
5. La welfare de x*_{−k} est W − v_k.

Donc x*_{−k} est admissible dans le problème sans k, et W_{-k} (l'optimum
de ce problème) satisfait W_{-k} ≥ welfare(x*_{−k}) = W − v_k. ✓

D'où p_k = W_{-k} − (W − v_k) ≥ 0. ∎

### Losers pay zero

Par construction de `run_vcg` : on ne calcule p_k que pour les bidders
de `winners_by_bidder`. Les autres ne figurent pas dans `payments`.
C'est tautologique côté code, mais opérationnellement correct.

## Interprétation (régime de la contrainte)

Notre code implémente l'**interprétation A** : le cap s'applique à la
somme des **prix déclarés** des bids gagnants. C'est l'interprétation
"plafond de revenu vendeur" ou "budget réglementaire".

L'**interprétation B** ("plafond sur les paiements") serait
intrinsèquement circulaire (les paiements sont calculés *après* la
résolution du WDP) et n'est pas implémentée.

## Décision pour le projet

1. Garder `enforce_budget=True` comme défaut de `run_vcg` (le budget
   est une caractéristique de l'instance, pas un toggle de mécanisme).
2. Exposer `run_vcg_canonical(instance)` qui refuse les instances
   budgétées — pour rendre explicite l'invocation du régime DSIC.
3. Documenter clairement les deux régimes dans le notebook (section 5)
   et le module docstring.
4. Tests :
   - `test_vcg_canonical_properties` : régime canonique, sur instances
     sans budget uniquement.
   - `test_vcg_with_budget_constraint_loses_dsic` : régime non-canonique,
     vérifie ce qui reste mécaniquement vrai.
   - `test_vcg_budget_admits_strict_manipulation` : preuve numérique
     de la perte de DSIC.

## Références

- Vickrey (1961). *Counterspeculation, Auctions, and Competitive Sealed Tenders*. JoF 16.
- Clarke (1971). *Multipart Pricing of Public Goods*. Public Choice 11.
- Groves (1973). *Incentives in Teams*. Econometrica 41.
- Borgs, Chayes, Immorlica, Mahdian, Saberi (2005). *Multi-unit Auctions with Budget-Constrained Bidders*. EC.
- Nisan, Ronen (2007). *Computationally Feasible VCG Mechanisms*. JAIR 29.
- Lavi (2007). chap. 12 de *Algorithmic Game Theory*, §12.4.
- Dobzinski, Lavi, Nisan (2008/2012). *Multi-unit Auctions with Budget Limits*. FOCS / GEB.
