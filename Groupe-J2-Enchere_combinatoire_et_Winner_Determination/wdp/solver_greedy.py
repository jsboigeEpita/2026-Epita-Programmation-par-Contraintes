"""Heuristique gloutonne pour le Winner Determination Problem.

**Cadre opérationnel pour ce projet** : nous générons des instances
avec des groupes XOR par bidder (cf. `wdp/generator.py`). Dans ce
cadre, **aucune borne formelle d'approximation n'est garantie** ;
l'algorithme est une heuristique empirique, utilisée comme borne
inférieure rapide et comparaison à CP-SAT/PLNE. Voir le caveat
théorique ci-dessous pour les conditions sous lesquelles la borne
sqrt(m) de Lehmann et al. s'appliquerait.

Algorithme **LOS** (Lehmann, O'Callaghan, Shoham, 2002, "Truth Revelation
in Approximately Efficient Combinatorial Auctions", JACM 49(5)) :

    tri des offres par ``price / sqrt(|items|)`` décroissant,
    puis sélection séquentielle si compatible avec :
        (1) items déjà alloués (exclusivité) ;
        (2) budget global et par bidder ;
        (3) groupes XOR déjà "consommés".

**Caveat théorique sur la borne sqrt(m).** Lehmann et al. prouvent que
ce greedy atteint un ratio d'approximation de sqrt(m) (m = nombre
d'items) **uniquement dans le cadre single-minded** : chaque bidder
déclare un unique bundle désiré, sans contraintes additionnelles
(pas de budget, pas de XOR). Le choix de sqrt(|S_j|) au dénominateur
est essentiel pour cette borne : la densité plate price/|S_j| n'a
aucune garantie connue.

**Hors du cadre single-minded** (XOR groups, budgets), la borne
sqrt(m) ne s'applique pas. Aucune généralisation propre n'existe
dans Lehmann et al. ni dans Mu'alem-Nisan 2008 (extensions). En
pratique, **toutes** nos instances synthétiques tombent dans ce cas
(XOR auto-générés par bidder), donc le greedy est utilisé ici comme
**heuristique empirique pure**.

**Pas de revendication d'incitation.** Lehmann et al. prouvent aussi
que LOS *avec paiements de valeurs critiques* est strategy-proof. Nous
n'implémentons PAS ces paiements ici : `solve_wdp_greedy` ne calcule
aucun paiement, c'est uniquement un solveur d'allocation. Aucune
propriété d'incitation (truthful, DSIC) n'est revendiquée.

Complexité : O(n_bids * (n_items + n_xor)). Usages :
    - borne inférieure rapide sur les instances "stress" où CP-SAT/PLNE
      atteignent la limite de temps ;
    - mesure empirique du ratio d'approximation vs solveur exact ;
    - support pour comparer rapidement plusieurs variantes d'instance.
"""

from __future__ import annotations

import math
import time
from typing import Optional

from .instance import Allocation, Instance


def solve_wdp_greedy(
    instance: Instance,
    enforce_budget: bool = True,
    enforce_xor: bool = True,
    time_limit_s: float = 60.0,  # ignoré, gardé pour signature uniforme
    excluded_bidders: Optional[set[str]] = None,
    log: bool = False,
) -> Allocation:
    """Résout le WDP avec l'heuristique gloutonne LOS (Lehmann et al. 2002).

    Tri par ``price / sqrt(|items|)`` décroissant. Signature alignée sur
    ``solve_wdp_cpsat`` / ``solve_wdp_milp`` pour permettre un branchement
    direct depuis VCG ou les benchmarks.
    """
    excluded = excluded_bidders or set()
    t0 = time.perf_counter()

    # ---- Pré-calculs -------------------------------------------------------
    candidates = [b for b in instance.bids if b.bidder not in excluded]
    # LOS-greedy : tri par price / sqrt(|items|) décroissant.
    # Garantit un ratio d'approximation sqrt(m) (m = nb d'items).
    candidates.sort(
        key=lambda b: b.price / math.sqrt(max(len(b.items), 1)),
        reverse=True,
    )

    bid_to_xor: dict[int, int] = {}
    if enforce_xor:
        for k, group in enumerate(instance.xor_groups):
            for bid_id in group:
                bid_to_xor[bid_id] = k

    # ---- État courant ------------------------------------------------------
    used_items: set[str] = set()
    used_xor: set[int] = set()
    spend_total = 0.0
    spend_per_bidder: dict[str, float] = {}

    global_cap = instance.budget.global_cap if enforce_budget else None
    per_bidder_cap = instance.budget.per_bidder if enforce_budget else {}

    winners: list[int] = []
    revenue = 0.0

    # ---- Boucle gloutonne --------------------------------------------------
    for b in candidates:
        if b.items & used_items:
            continue
        if enforce_xor:
            grp = bid_to_xor.get(b.id)
            if grp is not None and grp in used_xor:
                continue
        if global_cap is not None and spend_total + b.price > global_cap + 1e-9:
            continue
        cap = per_bidder_cap.get(b.bidder)
        if cap is not None and spend_per_bidder.get(b.bidder, 0.0) + b.price > cap + 1e-9:
            continue

        # Acceptée
        winners.append(b.id)
        revenue += b.price
        used_items |= b.items
        if enforce_xor:
            grp = bid_to_xor.get(b.id)
            if grp is not None:
                used_xor.add(grp)
        spend_total += b.price
        spend_per_bidder[b.bidder] = spend_per_bidder.get(b.bidder, 0.0) + b.price

    elapsed = time.perf_counter() - t0

    if log:
        print(
            f"[greedy] kept {len(winners)}/{len(candidates)} bids, "
            f"revenue={revenue:.2f}, time={elapsed*1000:.2f}ms"
        )

    return Allocation(
        winning_bid_ids=sorted(winners),
        revenue=revenue,
        status="HEURISTIC",
        solve_time=elapsed,
        solver="GREEDY-LOS",
    )
