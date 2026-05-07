"""Mécanisme Vickrey-Clarke-Groves (VCG) pour les enchères combinatoires.

Le mécanisme VCG généralise l'enchère de Vickrey (second prix) au cadre
combinatoire. Il calcule pour chaque agent gagnant un paiement basé sur
l'externalité qu'il impose aux autres.

Formule du paiement VCG pour un gagnant k :

    p_k^VCG  =  W_{-k}^*  -  (W^*  -  v_k(x^*))

où :
    W^*       : valeur sociale optimale avec tous les bidders
    W_{-k}^*  : valeur sociale optimale en excluant les bids de k
    v_k(x^*)  : valeur des bids gagnants de k dans l'allocation globale

Interprétation : k paie exactement le "manque à gagner" qu'il cause aux autres
agents en participant à l'enchère.

Propriétés :
    - Truthfulness (incentive-compatibility) : dire la vérité est dominant.
    - Individual rationality : p_k <= v_k(x^*), donc surplus >= 0.
    - Efficacité : allocation socialement optimale.

Limite : revenu vendeur potentiellement faible, voire nul, vs first-price.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Optional

from .instance import Allocation, Instance
from .solver_cpsat import solve_wdp_cpsat


SolverFn = Callable[..., Allocation]


@dataclass
class VCGResult:
    """Résultat complet d'une enchère VCG.

    Attributes:
        allocation: allocation socialement optimale (sortie du WDP global).
        social_welfare: valeur sociale W^* = somme des prix des bids gagnants.
        winners_by_bidder: dict {bidder -> liste de bids gagnants}.
        bidder_values: dict {bidder -> v_k(x^*)} = somme des prix offerts par k
            dans l'allocation globale.
        welfare_without: dict {bidder -> W_{-k}^*} = valeur sociale optimale
            sans les bids de k.
        payments: dict {bidder -> p_k^VCG} = paiement VCG par gagnant.
        seller_revenue: somme des paiements VCG (revenu effectif du vendeur).
        total_solve_time: temps cumulé de toutes les résolutions WDP.
    """

    allocation: Allocation
    social_welfare: float
    winners_by_bidder: dict[str, list[int]]
    bidder_values: dict[str, float]
    welfare_without: dict[str, float]
    payments: dict[str, float]
    seller_revenue: float
    total_solve_time: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["allocation"] = self.allocation.to_dict()
        return d

    def summary(self) -> str:
        lines = [
            f"VCG result for instance '{self.allocation.solver}'",
            f"  Social welfare W*       : {self.social_welfare:.2f}",
            f"  Seller revenue (sum p_k): {self.seller_revenue:.2f}",
            f"  Total solve time        : {self.total_solve_time:.3f}s",
            "",
            f"  {'Bidder':<10}{'value v_k':>12}{'W_{-k}^*':>12}{'payment p_k':>14}{'surplus':>10}",
        ]
        for bidder, val in self.bidder_values.items():
            w_minus = self.welfare_without[bidder]
            pay = self.payments[bidder]
            surplus = val - pay
            lines.append(
                f"  {bidder:<10}{val:>12.2f}{w_minus:>12.2f}{pay:>14.2f}{surplus:>10.2f}"
            )
        return "\n".join(lines)


def run_vcg(
    instance: Instance,
    solver_fn: SolverFn = solve_wdp_cpsat,
    enforce_budget: bool = True,
    enforce_xor: bool = True,
    time_limit_s: float = 60.0,
    **solver_kwargs,
) -> VCGResult:
    """Calcule l'allocation et les paiements VCG pour une instance WDP.

    Args:
        instance: instance du WDP.
        solver_fn: fonction de résolution du WDP (par défaut CP-SAT).
            Doit accepter les kwargs ``enforce_budget``, ``enforce_xor``,
            ``time_limit_s``, ``excluded_bidders`` et renvoyer une Allocation.
        enforce_budget: active les contraintes de budget.
        enforce_xor: active les contraintes XOR.
        time_limit_s: limite de temps par résolution WDP.
        **solver_kwargs: passés à chaque appel au solveur.

    Returns:
        VCGResult avec l'allocation optimale, les valeurs W*, W_{-k}*, et
        les paiements VCG pour chaque bidder gagnant.

    Note:
        Le calcul nécessite (1 + nombre de bidders gagnants) résolutions du
        WDP, ce qui peut être coûteux sur des grandes instances.
    """
    # ---- 1. Résolution globale --------------------------------------------
    alloc = solver_fn(
        instance,
        enforce_budget=enforce_budget,
        enforce_xor=enforce_xor,
        time_limit_s=time_limit_s,
        **solver_kwargs,
    )
    social_welfare = alloc.revenue
    total_time = alloc.solve_time

    # Indexer les bids par id pour retrouver bidder et price
    bid_by_id = {b.id: b for b in instance.bids}

    # Groupe les gagnants par bidder
    winners_by_bidder: dict[str, list[int]] = {}
    bidder_values: dict[str, float] = {}
    for bid_id in alloc.winning_bid_ids:
        b = bid_by_id[bid_id]
        winners_by_bidder.setdefault(b.bidder, []).append(bid_id)
        bidder_values[b.bidder] = bidder_values.get(b.bidder, 0.0) + b.price

    # ---- 2. Pour chaque gagnant : résoudre WDP sans ses bids --------------
    welfare_without: dict[str, float] = {}
    payments: dict[str, float] = {}

    for bidder in winners_by_bidder:
        alloc_minus = solver_fn(
            instance,
            enforce_budget=enforce_budget,
            enforce_xor=enforce_xor,
            time_limit_s=time_limit_s,
            excluded_bidders={bidder},
            **solver_kwargs,
        )
        welfare_without[bidder] = alloc_minus.revenue
        total_time += alloc_minus.solve_time

        # p_k^VCG = W_{-k}^* - (W^* - v_k(x^*))
        v_k = bidder_values[bidder]
        payments[bidder] = welfare_without[bidder] - (social_welfare - v_k)

    seller_revenue = sum(payments.values())

    return VCGResult(
        allocation=alloc,
        social_welfare=social_welfare,
        winners_by_bidder=winners_by_bidder,
        bidder_values=bidder_values,
        welfare_without=welfare_without,
        payments=payments,
        seller_revenue=seller_revenue,
        total_solve_time=total_time,
    )
