"""Solveur PLNE (Programmation Linéaire en Nombres Entiers) pour le WDP.

Modélisation identique au solveur CP-SAT (mêmes variables, mêmes contraintes,
même objectif), mais résolue par PuLP avec le solver CBC (Coin-OR Branch and
Cut). Permet la comparaison de performances CP-SAT vs PLNE (livrable 4).

Variables :
    x[j] in {0, 1}  pour chaque offre j

Objectif :
    max  sum_j  price[j] * x[j]

Contraintes :
    (1) Exclusivité d'item   : sum_{j : i in S_j} x[j] <= 1
    (2) Budget global        : sum_j  price[j] * x[j] <= B
    (3) Budget par bidder    : sum_{j : bidder(j)=k} price[j]*x[j] <= B_k
    (4) XOR par groupe       : sum_{j in G} x[j] <= 1

Une fonction utilitaire ``solve_wdp_lp_relaxation`` est également exposée :
elle résout la **relaxation continue** (variables dans [0,1] au lieu de
{0,1}). La borne supérieure obtenue sert à mesurer le **gap d'intégralité**.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import pulp

from .instance import Allocation, Instance


_log = logging.getLogger(__name__)


def _check_feasibility(
    instance: Instance,
    winning_bid_ids: list[int],
    enforce_budget: bool,
    enforce_xor: bool,
    excluded: set[str],
    tol: float = 1e-6,
) -> Optional[str]:
    """Re-vérifie indépendamment qu'un sous-ensemble de bids est admissible.

    Returns:
        ``None`` si feasible, sinon une chaîne décrivant la première
        violation rencontrée.
    """
    if not winning_bid_ids:
        return None  # ensemble vide trivialement faisable

    bid_by_id = {b.id: b for b in instance.bids}
    selected = [bid_by_id[i] for i in winning_bid_ids if i in bid_by_id]

    # 0. Aucun bid d'un bidder exclu ne doit apparaître
    for b in selected:
        if b.bidder in excluded:
            return f"bid {b.id} from excluded bidder {b.bidder!r}"

    # 1. Exclusivité d'item
    used = set()
    for b in selected:
        overlap = b.items & used
        if overlap:
            return f"item overlap on {sorted(overlap)} (bid {b.id})"
        used |= b.items

    # 2. Budget
    if enforce_budget and instance.budget.is_active():
        total = sum(b.price for b in selected)
        if instance.budget.global_cap is not None and total > instance.budget.global_cap + tol:
            return f"global budget exceeded: {total:.4f} > {instance.budget.global_cap}"
        for bidder, cap in instance.budget.per_bidder.items():
            spend = sum(b.price for b in selected if b.bidder == bidder)
            if spend > cap + tol:
                return f"per-bidder budget exceeded for {bidder}: {spend:.4f} > {cap}"

    # 3. XOR
    if enforce_xor:
        for k, group in enumerate(instance.xor_groups):
            count = sum(1 for b in selected if b.id in set(group))
            if count > 1:
                return f"xor_group {k} has {count} winners (>1)"

    return None


def _build_model(
    instance: Instance,
    enforce_budget: bool,
    enforce_xor: bool,
    excluded_bidders: set[str],
    continuous: bool = False,
) -> tuple[pulp.LpProblem, dict[int, pulp.LpVariable]]:
    """Construit le modèle PuLP du WDP.

    Si ``continuous=True``, les variables sont dans [0,1] (relaxation linéaire).
    Sinon, elles sont binaires.
    """
    cat = "Continuous" if continuous else "Binary"
    model = pulp.LpProblem(f"WDP_{instance.name}", pulp.LpMaximize)

    x: dict[int, pulp.LpVariable] = {}
    for b in instance.bids:
        if b.bidder in excluded_bidders:
            continue
        x[b.id] = pulp.LpVariable(f"x_{b.id}", lowBound=0, upBound=1, cat=cat)

    # Objectif
    model += pulp.lpSum(b.price * x[b.id] for b in instance.bids if b.id in x)

    # (1) Exclusivité par item — hypothèse FREE DISPOSAL (Cramton, Shoham,
    # Steinberg 2006, ch. 1) : <= 1, donc un item peut rester non alloué.
    for item in instance.items:
        terms = [x[b.id] for b in instance.bids if b.id in x and item in b.items]
        if len(terms) >= 2:
            model += pulp.lpSum(terms) <= 1, f"item_{item}"

    # (2)(3) Budget
    if enforce_budget and instance.budget.is_active():
        if instance.budget.global_cap is not None:
            model += (
                pulp.lpSum(b.price * x[b.id] for b in instance.bids if b.id in x)
                <= instance.budget.global_cap
            ), "budget_global"
        for bidder, cap in instance.budget.per_bidder.items():
            if bidder in excluded_bidders:
                continue
            terms = [
                b.price * x[b.id]
                for b in instance.bids
                if b.id in x and b.bidder == bidder
            ]
            if terms:
                model += pulp.lpSum(terms) <= cap, f"budget_{bidder}"

    # (4) XOR
    if enforce_xor:
        for k, group in enumerate(instance.xor_groups):
            terms = [x[bid] for bid in group if bid in x]
            if len(terms) >= 2:
                model += pulp.lpSum(terms) <= 1, f"xor_{k}"

    return model, x


def solve_wdp_milp(
    instance: Instance,
    enforce_budget: bool = True,
    enforce_xor: bool = True,
    time_limit_s: float = 60.0,
    excluded_bidders: Optional[set[str]] = None,
    log: bool = False,
) -> Allocation:
    """Résout le WDP en PLNE (variables binaires) avec CBC.

    Signature identique à ``solver_cpsat.solve_wdp_cpsat``.

    Statuts retournés (alignés sur ``solver_cpsat`` pour comparabilité) :

        - ``"OPTIMAL"``    : optimum prouvé (CBC = "Optimal").
        - ``"FEASIBLE"``   : un incumbent feasible récupéré sous time-out
                              (CBC = "Not Solved" mais `.value()` non None
                              et la re-vérification de faisabilité passe).
        - ``"INFEASIBLE"`` : modèle prouvé infaisable.
        - ``"UNKNOWN"``    : aucun incumbent exploitable (variables None,
                              ou re-vérification de faisabilité échoue ;
                              cf. :class:`VCGSolveWarning`).
    """
    excluded = excluded_bidders or set()
    model, x = _build_model(
        instance,
        enforce_budget=enforce_budget,
        enforce_xor=enforce_xor,
        excluded_bidders=excluded,
        continuous=False,
    )

    solver = pulp.PULP_CBC_CMD(msg=int(log), timeLimit=time_limit_s)

    t0 = time.perf_counter()
    status = model.solve(solver)
    elapsed = time.perf_counter() - t0

    status_name = pulp.LpStatus[status]

    # ---- Extraction unifiée ----------------------------------------------
    # On tente toujours de lire les valeurs ; CBC peut renvoyer "Not Solved"
    # tout en ayant un incumbent dans `.value()`. À l'inverse, on ne fait
    # confiance ni à `pulp.value(model.objective)` (parfois stale), ni au
    # statut PuLP qui peut classer un incumbent feasible en "Not Solved".

    # 1. Garde-fou : toute variable à None invalide l'incumbent (peut
    #    arriver après crash, presolve avec interruption, ou échec total).
    var_values: dict[int, float] = {}
    incomplete = False
    for bid_id, var in x.items():
        v = var.value()
        if v is None:
            incomplete = True
            break
        var_values[bid_id] = v

    if status_name == "Infeasible":
        return Allocation(
            winning_bid_ids=[],
            revenue=0.0,
            status="INFEASIBLE",
            solve_time=elapsed,
            solver="PLNE-CBC",
        )

    if incomplete:
        # Pas d'incumbent exploitable
        return Allocation(
            winning_bid_ids=[],
            revenue=0.0,
            status="UNKNOWN",
            solve_time=elapsed,
            solver="PLNE-CBC",
        )

    # 2. Arrondi des binaires (CBC retourne float ; tolérance 0.5).
    winners = sorted(bid_id for bid_id, v in var_values.items() if v > 0.5)

    # 3. Re-vérification indépendante en Python (tolérance arrondi +
    #    bug rare CBC). Sans ça, un VCG appellerait p_k sur une allocation
    #    fantôme.
    violation = _check_feasibility(
        instance, winners,
        enforce_budget=enforce_budget,
        enforce_xor=enforce_xor,
        excluded=excluded,
    )
    if violation is not None:
        _log.warning(
            "PLNE-CBC incumbent rejeté (status=%s) : %s — instance=%s",
            status_name, violation, instance.name,
        )
        return Allocation(
            winning_bid_ids=[],
            revenue=0.0,
            status="UNKNOWN",
            solve_time=elapsed,
            solver="PLNE-CBC",
        )

    # 4. Recalcul du revenu directement depuis instance.bids
    #    (plus fiable que pulp.value(model.objective) sur incumbent partiel).
    bid_price = {b.id: b.price for b in instance.bids}
    revenue = float(sum(bid_price[i] for i in winners))

    # 5. Étiquetage du statut
    if status_name == "Optimal":
        out_status = "OPTIMAL"
    else:
        # CBC a renvoyé "Not Solved" mais on a un incumbent valide.
        out_status = "FEASIBLE"
        _log.info(
            "PLNE-CBC FEASIBLE incumbent (status=%s, time=%.2fs, revenue=%.2f) "
            "— instance=%s. Pas optimum prouvé.",
            status_name, elapsed, revenue, instance.name,
        )

    return Allocation(
        winning_bid_ids=winners,
        revenue=revenue,
        status=out_status,
        solve_time=elapsed,
        solver="PLNE-CBC",
    )


def solve_wdp_lp_relaxation(
    instance: Instance,
    enforce_budget: bool = True,
    enforce_xor: bool = True,
    time_limit_s: float = 60.0,
    excluded_bidders: Optional[set[str]] = None,
) -> Allocation:
    """Résout la relaxation linéaire (variables dans [0,1]).

    La valeur optimale obtenue est une **borne supérieure** sur le revenu
    optimal entier. Le gap d'intégralité se calcule comme :
        gap = (revenue_LP - revenue_ILP) / revenue_ILP
    Plus le gap est petit, plus la PLNE est rapide à résoudre.
    """
    excluded = excluded_bidders or set()
    model, x = _build_model(
        instance,
        enforce_budget=enforce_budget,
        enforce_xor=enforce_xor,
        excluded_bidders=excluded,
        continuous=True,
    )

    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit_s)

    t0 = time.perf_counter()
    status = model.solve(solver)
    elapsed = time.perf_counter() - t0

    status_name = pulp.LpStatus[status]
    if status_name == "Optimal":
        # En relaxation, les "gagnants" peuvent être fractionnaires ;
        # on rapporte les bids avec x_j > 1e-6 comme indicatifs.
        winners = sorted(
            bid_id for bid_id, var in x.items() if var.value() is not None and var.value() > 1e-6
        )
        revenue = float(pulp.value(model.objective))
    else:
        winners = []
        revenue = 0.0

    return Allocation(
        winning_bid_ids=winners,
        revenue=revenue,
        status=status_name.upper(),
        solve_time=elapsed,
        solver="LP-relaxation",
    )
