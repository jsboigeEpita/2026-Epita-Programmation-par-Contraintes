# Note 02 — Choix de l'heuristique gloutonne : LOS (Lehmann-O'Callaghan-Shoham)

Contexte : implémentation de `wdp/solver_greedy.py` (issue #2).

## Alternatives considérées

Deux variantes naturelles de greedy pour le WDP single-minded :

| Critère de tri | Garantie connue | Source |
|----------------|-----------------|--------|
| `price / \|S\|`      | aucune          | trivial |
| `price / sqrt(\|S\|)` | **ratio sqrt(m)** | Lehmann, O'Callaghan, Shoham (2002), JACM 49(5) |

## Décision

On adopte **LOS** (`price / sqrt(|S|)`). Justifications :

1. **Cité dans la littérature** : permet de revendiquer une borne
   d'approximation sqrt(m) prouvée plutôt qu'une heuristique ad-hoc.
2. **Single-minded** : le théorème suppose qu'un bidder déclare **un
   seul** bundle désiré. Dans notre projet, un bidder peut soumettre
   plusieurs offres XOR : le cadre est donc plus général que single-minded
   et la garantie sqrt(m) ne s'applique **pas** directement (cf. Limites).
3. **Truthfulness approximée** : Lehmann et al. prouvent aussi que LOS
   est *strategy-proof* (truthful) pour les enchères single-minded, ce
   qui crée un pont thématique avec le livrable 5 (VCG, truthful exact).

## Limites

- La borne sqrt(m) suppose des bidders single-minded ; en présence de
  groupes XOR de taille >1 par bidder (notre cas général), la garantie
  formelle ne s'applique pas directement, mais l'algorithme reste un
  bon point de référence empirique.
- Le ratio observé sur petites instances (toy, with_budget, with_xor)
  n'a pas d'intérêt statistique : ces instances se résolvent en exact
  en quelques ms.

## À faire (perspective)

- Implémenter un **warm-start CP-SAT** : passer la solution greedy comme
  hint via `model.AddHint(x[j], 1)` pour les `j` gagnants. Mesurer l'impact
  sur le time-to-optimal des instances `large` et `stress`.
- Tester sur instances stress où CP-SAT atteint le time limit : c'est
  le seul cas où le greedy a une vraie utilité opérationnelle.

## Conséquence opérationnelle pour ce projet

Toutes nos instances de benchmark sont générées par `wdp/generator.py`,
qui crée **systématiquement** un groupe XOR par bidder ayant ≥2 offres.
Le cadre single-minded de Lehmann et al. n'est donc **jamais** vérifié
sur nos données — la borne sqrt(m) n'a jamais été opérante dans aucune
mesure de ce projet.

Conséquence : le ratio greedy/exact (82–96% mesuré sur les instances
pédagogiques, variable sur les benchmarks synthétiques) est une mesure
**empirique pure**, pas une instance d'une borne théorique. Les notebooks
et le README doivent l'énoncer ainsi pour éviter une revendication
théorique inappropriée.
