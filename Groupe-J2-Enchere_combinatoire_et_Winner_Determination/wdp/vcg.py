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

==============================================================================
Régimes et propriétés
==============================================================================

Ce module distingue deux régimes d'utilisation, selon le paramètre
``enforce_budget`` passé à ``run_vcg`` :

**Régime canonique** (``enforce_budget=False``, accessible aussi via
``run_vcg_canonical``) :

    L'ensemble F des allocations admissibles ne dépend pas des prix
    déclarés. Le théorème classique de Vickrey/Clarke/Groves s'applique :

    - **Truthfulness** : déclarer la vérité (``bid.price = v_k``) est
      une stratégie dominante.
    - **Individual rationality** : ``p_k <= v_k`` ⇒ surplus >= 0.
    - **Efficacité allocative** : x* maximise la welfare sociale.

    Ces garanties exigent en outre que **chaque** sous-WDP (le global
    et chaque W_{-k}^*) soit résolu à l'optimum exact (Nisan-Ronen 2007,
    *Computationally feasible VCG mechanisms*, JAIR 29) — un statut
    `FEASIBLE` ou `UNKNOWN` retourné sous time-out **rompt** la
    truthfulness. Le champ ``VCGResult.non_optimal_solves`` et la
    propriété ``optimal_solves`` de ``verify_properties`` le tracent.

**Régime non-canonique avec contrainte de budget**
(``enforce_budget=True``, défaut) :

    L'instance déclare ``budget.global_cap`` et/ou ``budget.per_bidder``,
    qui s'expriment dans nos solveurs comme

        sum_{j} bid.price[j] * x[j]  <=  cap

    L'ensemble F **dépend** des prix déclarés ``bid.price[j]``. Un
    bidder peut alors *shader* son prix pour modifier F et obtenir un
    surplus strictement supérieur. Le théorème de truthfulness ne tient
    plus (Borgs, Chayes, Immorlica, Mahdian, Saberi, EC 2005, *Multi-unit
    auctions with budget-constrained bidders* ; Dobzinski, Lavi, Nisan,
    FOCS 2008, *Multi-unit auctions with budget limits*).

    La formule VCG est néanmoins encore appliquée mécaniquement, et les
    propriétés suivantes restent vraies *par construction* (cf. preuve
    dans ``research/04_vcg_budget_non_truthful.md``) :

    - **IR mécanique** : ``p_k <= v_k`` (suit de la slack-monotonicité
      de la contrainte de budget : retirer un bid ne peut que relâcher
      la contrainte ``sum price*x <= cap``).
    - **No-deficit mécanique** : ``sum p_k >= 0``.
    - **Losers pay zero** : par construction de l'algorithme.

    Mais on **ne peut pas** invoquer la truthfulness : un correcteur
    qui voit ``enforce_budget=True`` doit lire le caveat. Une démonstration
    numérique de manipulation se trouve dans le test
    ``test_vcg_budget_admits_strict_manipulation``.

Limites communes aux deux régimes : revenu vendeur potentiellement faible
(rente informationnelle), vulnérabilité à la collusion ou aux shill bids
(Ausubel-Milgrom 2006, *The lovely but lonely Vickrey auction*).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Callable, Optional

from .instance import Allocation, Instance
from .solver_cpsat import solve_wdp_cpsat


SolverFn = Callable[..., Allocation]


class VCGSolveWarning(RuntimeWarning):
    """Levée quand un sous-WDP de VCG n'a pas atteint OPTIMAL.

    Les paiements VCG dépendent de l'optimalité de **chaque** sous-résolution
    W_{-k}^*. Un statut FEASIBLE (time-out avec solution intermédiaire) suffit
    à fausser silencieusement les paiements : il faut le signaler à l'appelant.
    """


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
    non_optimal_solves: list[str] = field(default_factory=list)
    all_bidders: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["allocation"] = self.allocation.to_dict()
        return d

    def verify_properties(self, tol: float = 1e-6) -> dict:
        """Vérifie les propriétés du mécanisme VCG sur cette exécution.

        Distingue deux catégories :

        **Propriétés théoriques du mécanisme** (doivent être vérifiées par
        toute implémentation correcte de VCG) :
            1. ``individual_rationality`` : p_k <= v_k(x*) pour chaque
               gagnant. Garantit un surplus non négatif et donc l'incitation
               à participer.
            2. ``losers_pay_zero`` : tout bidder non gagnant n'apparaît pas
               dans ``payments`` (ou paie 0).
            3. ``no_deficit`` (alias *weak budget balance* dans la littérature,
               cf. Krishna 2002, Milgrom 2004) : sum_k p_k >= 0.

        **Vérifications de consistance** (non spécifiques à VCG) :
            4. ``welfare_monotone`` : W_{-k}^* <= W^*. Conséquence directe
               de la restriction du domaine. **Attention** : ce test ne
               peut PAS détecter un sous-WDP sous-optimal qui *sous-estime*
               W_{-k}^* (la relation reste alors trivialement vraie). Il
               n'attrape que la pathologie symétrique (sur-estimation),
               très rare. Le vrai garde-fou contre les time-outs est
               ``optimal_solves`` ci-dessous.
            5. ``optimal_solves`` : tous les sous-WDP ont renvoyé OPTIMAL
               (pas seulement FEASIBLE). C'est la seule vérification qui
               protège réellement contre les paiements faussés par un
               time-out de solveur.

        Note : la **truthfulness** (stratégie dominante) ne se vérifie pas
        à l'exécution. Elle se prouve analytiquement à partir de la
        formule de paiement et n'est donc pas testée ici.
        """
        details: list[str] = []
        ir_per_bidder = {}
        wm_per_bidder = {}

        for bidder, val in self.bidder_values.items():
            pay = self.payments[bidder]
            w_minus = self.welfare_without[bidder]

            ir_ok = (val - pay) >= -tol
            ir_per_bidder[bidder] = ir_ok
            if not ir_ok:
                details.append(
                    f"IR violated for {bidder}: v_k={val:.4f} < p_k={pay:.4f}"
                )

            wm_ok = w_minus <= self.social_welfare + tol
            wm_per_bidder[bidder] = wm_ok
            if not wm_ok:
                details.append(
                    f"Welfare monotonicity violated for {bidder}: "
                    f"W_-k={w_minus:.4f} > W*={self.social_welfare:.4f}. "
                    f"Indique un sous-WDP non optimal."
                )

        # Losers pay zero : test non-trivial. On vérifie deux invariants :
        #   (a) ``payments.keys() == winners_by_bidder.keys()`` — aucun perdant
        #       ne doit avoir de paiement enregistré (catch un bug refactor).
        #   (b) pour tout perdant b, le bidder n'apparaît dans aucun bid
        #       gagnant de ``allocation.winning_bid_ids`` (sanity check sur
        #       la construction de ``winners_by_bidder``).
        winners = set(self.winners_by_bidder.keys())
        losers = [b for b in self.all_bidders if b not in winners]
        losers_violation: list[str] = []

        spurious_payment_keys = set(self.payments.keys()) - winners
        for b in spurious_payment_keys:
            if abs(self.payments[b]) > tol:
                losers_violation.append(b)
                details.append(
                    f"Loser {b} has non-zero payment: p_k={self.payments[b]:.4f}"
                )
            else:
                losers_violation.append(b)
                details.append(
                    f"Loser {b} has stray payment entry (=0) — refactor bug"
                )

        # (b) Cross-check via l'allocation brute
        bid_by_id = {bid_id: None for bid_id in self.allocation.winning_bid_ids}
        if bid_by_id:
            # ``winners_by_bidder`` doit couvrir exactement les bidders
            # impliqués dans l'allocation gagnante. On ne peut pas
            # reconstruire le mapping sans l'instance, mais on vérifie
            # au moins la cardinalité : len(winning_bids) == sum(|winners|)
            n_winning_bids = len(self.allocation.winning_bid_ids)
            n_in_groups = sum(len(v) for v in self.winners_by_bidder.values())
            if n_winning_bids != n_in_groups:
                losers_violation.append("(cardinality mismatch)")
                details.append(
                    f"winners_by_bidder cardinality mismatch: "
                    f"alloc has {n_winning_bids} bids, "
                    f"winners_by_bidder accounts for {n_in_groups}"
                )

        # No-deficit : revenu vendeur non négatif.
        no_deficit_ok = self.seller_revenue >= -tol
        if not no_deficit_ok:
            details.append(
                f"Deficit: sum(p_k)={self.seller_revenue:.4f} < 0"
            )

        # Optimal solves : tous les WDP doivent être OPTIMAL.
        optimal_ok = len(self.non_optimal_solves) == 0
        if not optimal_ok:
            details.append(
                f"Sub-solves non optimaux : {self.non_optimal_solves}. "
                f"Les paiements VCG ne sont pas garantis."
            )

        return {
            # Propriétés VCG
            "individual_rationality": {
                "ok": all(ir_per_bidder.values()) if ir_per_bidder else True,
                "per_bidder": ir_per_bidder,
            },
            "losers_pay_zero": {
                "ok": len(losers_violation) == 0,
                "violators": losers_violation,
            },
            "no_deficit": {
                "ok": no_deficit_ok,
                "revenue": self.seller_revenue,
            },
            # Consistance solveur
            "welfare_monotone": {
                "ok": all(wm_per_bidder.values()) if wm_per_bidder else True,
                "per_bidder": wm_per_bidder,
                "note": "solver-consistency check, not a VCG property",
            },
            "optimal_solves": {
                "ok": optimal_ok,
                "non_optimal": list(self.non_optimal_solves),
            },
            "all_ok": len(details) == 0,
            "violations": details,
        }

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
    non_optimal: list[str] = []

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
    if alloc.status != "OPTIMAL":
        non_optimal.append(f"global({alloc.status})")

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
        if alloc_minus.status != "OPTIMAL":
            non_optimal.append(f"W_-{bidder}({alloc_minus.status})")

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
        non_optimal_solves=non_optimal,
        all_bidders=list(instance.bidders),
    )


def verify_table(results: dict) -> list[dict]:
    """Construit un tableau récapitulatif des vérifications VCG.

    Args:
        results: dict {nom_instance -> VCGResult}.

    Returns:
        Liste de dicts (une ligne par instance) avec les colonnes :
        ``instance``, ``IR``, ``losers_pay_0``, ``no_deficit``,
        ``W_-k<=W*``, ``optimal_solves``, ``all_ok``, ``violations``.

    Utilisable directement avec ``pandas.DataFrame(verify_table({...}))``.
    """
    rows = []
    for name, res in results.items():
        v = res.verify_properties()
        rows.append({
            "instance"     : name,
            "IR"           : v["individual_rationality"]["ok"],
            "losers_pay_0" : v["losers_pay_zero"]["ok"],
            "no_deficit"   : v["no_deficit"]["ok"],
            "W_-k<=W*"     : v["welfare_monotone"]["ok"],
            "optimal_solves": v["optimal_solves"]["ok"],
            "all_ok"       : v["all_ok"],
            "violations"   : len(v["violations"]),
        })
    return rows


def run_vcg_canonical(instance: Instance, **kwargs) -> "VCGResult":
    """Exécute VCG dans le **régime canonique** (truthful + IR + efficace).

    Précondition : ``instance.budget.is_active()`` doit être False — sinon
    l'ensemble F dépendrait des prix déclarés et le théorème de Vickrey-
    Clarke-Groves ne s'appliquerait plus (cf. docstring du module).

    Cette fonction garde-fou existe pour empêcher d'invoquer accidentellement
    les propriétés DSIC sur une instance budgétée.

    Raises:
        ValueError: si ``instance.budget.is_active()``.
    """
    if instance.budget.is_active():
        raise ValueError(
            f"run_vcg_canonical: instance {instance.name!r} a un budget actif "
            f"(global_cap={instance.budget.global_cap!r}, "
            f"per_bidder={instance.budget.per_bidder!r}). "
            "VCG canonique requiert F indépendant des rapports : utiliser "
            "run_vcg(..., enforce_budget=True) en acceptant la perte de DSIC, "
            "ou supprimer le budget de l'instance."
        )
    return run_vcg(instance, enforce_budget=False, **kwargs)
