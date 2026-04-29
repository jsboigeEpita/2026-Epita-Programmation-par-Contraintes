"""Solveur CP-SAT pour le Winner Determination Problem.

Modélisation Set Packing pondéré avec OR-Tools CP-SAT (livrables 1-2-3) :

Variables :
    x[j] in {0, 1}  pour chaque offre j  (1 = offre acceptée)

Objectif :
    max  sum_j  price[j] * x[j]

Contraintes :
    (1) Exclusivité d'item   : pour chaque item i,
           sum_{j : i in S_j} x[j] <= 1
    (2) Budget global        : sum_j  price[j] * x[j]  <= B          (optionnel)
    (3) Budget par bidder    : sum_{j : bidder(j)=k} price[j]*x[j] <= B_k (optionnel)
    (4) XOR par groupe       : pour chaque groupe G,
           sum_{j in G} x[j] <= 1                                    (optionnel)

CP-SAT travaille en entiers : les prix flottants sont mis à l'échelle par
``PRICE_SCALE`` (centimes par défaut) pour éviter toute perte de précision.
"""

from __future__ import annotations

import time
from typing import Optional

from ortools.sat.python import cp_model

from .instance import Allocation, Instance


PRICE_SCALE = 1000  # 3 décimales : 1.234 -> 1234. Aligné avec
# CATS ``bid_alpha=1000`` (cf. ``wdp/cats_parser.py``) pour éviter la
# perte de précision lors de la conversion en centimes des prix CATS.
# Les pédagogiques (2 décimales) restent exacts par construction.


def _scale(price: float) -> int:
    """Convertit un prix flottant en entier (centimes)."""
    return int(round(price * PRICE_SCALE))


def _unscale(value: int) -> float:
    return value / PRICE_SCALE


def solve_wdp_cpsat(
    instance: Instance,
    enforce_budget: bool = True,
    enforce_xor: bool = True,
    time_limit_s: float = 60.0,
    excluded_bidders: Optional[set[str]] = None,
    log: bool = False,
) -> Allocation:
    """Résout le WDP avec CP-SAT.

    Args:
        instance: instance du WDP.
        enforce_budget: active les contraintes de budget (global + per_bidder).
            Mettre False pour le livrable 1 (Set Packing pur).
        enforce_xor: active les contraintes XOR (groupes explicites de
            l'instance). Mettre False pour les livrables 1-2.
        time_limit_s: limite de temps de résolution (secondes).
        excluded_bidders: bidders dont les offres sont retirées du modèle.
            Utilisé par VCG pour calculer W_{-k}^*.
        log: si True, active le log du solveur CP-SAT.

    Returns:
        Allocation contenant les ids d'offres gagnantes, le revenu, le statut,
        le temps de résolution et le nom du solveur.
    """
    excluded = excluded_bidders or set()

    model = cp_model.CpModel()

    # ---- Variables binaires ------------------------------------------------
    # Une seule variable par bid actif (les bids des bidders exclus sont
    # simplement omis du modèle, c'est équivalent à les forcer à 0 mais plus
    # léger).
    x: dict[int, cp_model.IntVar] = {}
    for b in instance.bids:
        if b.bidder in excluded:
            continue
        x[b.id] = model.NewBoolVar(f"x_{b.id}")

    # ---- (1) Exclusivité par item -----------------------------------------
    # Hypothèse de FREE DISPOSAL côté vendeur (Cramton, Shoham, Steinberg
    # 2006, *Combinatorial Auctions*, ch. 1) : on impose <= 1 (et non = 1),
    # donc un item peut rester non alloué sans coût.
    for item in instance.items:
        vars_for_item = [
            x[b.id] for b in instance.bids if b.id in x and item in b.items
        ]
        if len(vars_for_item) >= 2:
            model.AddAtMostOne(vars_for_item)
        # Si 0 ou 1 var, contrainte triviale, on n'ajoute rien.

    # ---- (2)(3) Budget -----------------------------------------------------
    if enforce_budget and instance.budget.is_active():
        # Budget global
        if instance.budget.global_cap is not None:
            model.Add(
                sum(_scale(b.price) * x[b.id] for b in instance.bids if b.id in x)
                <= _scale(instance.budget.global_cap)
            )
        # Budget par bidder
        for bidder, cap in instance.budget.per_bidder.items():
            if bidder in excluded:
                continue
            terms = [
                _scale(b.price) * x[b.id]
                for b in instance.bids
                if b.id in x and b.bidder == bidder
            ]
            if terms:
                model.Add(sum(terms) <= _scale(cap))

    # ---- (4) Contraintes XOR ----------------------------------------------
    if enforce_xor:
        for group in instance.xor_groups:
            vars_in_group = [x[bid] for bid in group if bid in x]
            if len(vars_in_group) >= 2:
                model.AddAtMostOne(vars_in_group)

    # ---- Objectif : maximiser le revenu -----------------------------------
    model.Maximize(
        sum(_scale(b.price) * x[b.id] for b in instance.bids if b.id in x)
    )

    # ---- Résolution --------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.log_search_progress = log

    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0

    status_name = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }.get(status, f"STATUS_{status}")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        winners = sorted(bid_id for bid_id, var in x.items() if solver.Value(var) == 1)
        # ObjectiveValue() est un float ; arrondir avant unscale pour
        # absorber le bruit FP (sinon 4099.9999 -> 40.99 au lieu de 41.00).
        revenue = _unscale(round(solver.ObjectiveValue()))
    else:
        winners = []
        revenue = 0.0

    return Allocation(
        winning_bid_ids=winners,
        revenue=revenue,
        status=status_name,
        solve_time=elapsed,
        solver="CP-SAT",
    )
