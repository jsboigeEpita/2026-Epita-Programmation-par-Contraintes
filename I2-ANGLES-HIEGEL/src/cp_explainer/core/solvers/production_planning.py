"""Solveur CP-SAT — Planification de production (production planning)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    CounterfactualEntry,
    SensitivityEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict) -> SolverOutput:
    products = params["products"]
    resources = params["resources"]
    max_units = params.get("max_units_per_product", 10)
    n = len(products)
    resource_keys = list(resources.keys())

    model = cp_model.CpModel()
    qty = [model.NewIntVar(0, max_units, f"qty_{i}") for i in range(n)]

    for rk in resource_keys:
        usage = [p[rk] for p in products]
        model.Add(sum(usage[i] * qty[i] for i in range(n)) <= resources[rk])

    profits = [p["profit"] for p in products]
    model.Maximize(sum(profits[i] * qty[i] for i in range(n)))

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="production_planning", problem_type="production_planning",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="maximize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    total_profit = int(solver.ObjectiveValue())
    qty_vals = [solver.Value(qty[i]) for i in range(n)]
    production = {products[i]["name"]: qty_vals[i] for i in range(n)}

    constraint_analyses = []
    for rk in resource_keys:
        usage = [p[rk] for p in products]
        used = sum(usage[i] * qty_vals[i] for i in range(n))
        cap = resources[rk]
        slack = cap - used
        constraint_analyses.append(ConstraintAnalysis(
            name=f"resource_{rk}",
            description=f"Ressource {rk} : {used}/{cap}",
            formula=f"sum({rk}_usage × qty) = {used} ≤ {cap}",
            lhs_value=float(used),
            rhs_value=float(cap),
            slack=float(slack),
            is_binding=(slack == 0),
        ))

    sensitivity = []
    for rk in resource_keys:
        delta = max(1, resources[rk] // 10)
        m2 = cp_model.CpModel()
        q2 = [m2.NewIntVar(0, max_units, f"q_{i}") for i in range(n)]
        for rk2 in resource_keys:
            usage2 = [p[rk2] for p in products]
            cap2 = resources[rk2] + (delta if rk2 == rk else 0)
            m2.Add(sum(usage2[i] * q2[i] for i in range(n)) <= cap2)
        m2.Maximize(sum(profits[i] * q2[i] for i in range(n)))
        s2, st2 = solve_with_workers(m2)
        if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            new_profit = int(s2.ObjectiveValue())
            improvement = new_profit - total_profit
            sensitivity.append(SensitivityEntry(
                constraint_name=f"resource_{rk}",
                relaxation_amount=float(delta),
                original_objective=float(total_profit),
                new_objective=float(new_profit),
                improvement=float(improvement),
                description=f"{rk} +{delta} → profit {new_profit} (+{improvement})",
            ))

    counterfactuals = []
    for i in range(n):
        if qty_vals[i] == 0:
            m3 = cp_model.CpModel()
            q3 = [m3.NewIntVar(0, max_units, f"q_{j}") for j in range(n)]
            for rk in resource_keys:
                usage3 = [p[rk] for p in products]
                m3.Add(sum(usage3[j] * q3[j] for j in range(n)) <= resources[rk])
            m3.Add(q3[i] >= 1)
            m3.Maximize(sum(profits[j] * q3[j] for j in range(n)))
            s3, st3 = solve_with_workers(m3)
            if st3 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_p = int(s3.ObjectiveValue())
                delta3 = new_p - total_profit
                expl = (f"Forcer au moins 1 '{products[i]['name']}' → profit {new_p} "
                        f"({delta3:+d}).")
            else:
                new_p = None
                delta3 = None
                expl = f"Produire '{products[i]['name']}' est infaisable avec les ressources."
            counterfactuals.append(CounterfactualEntry(
                description=f"Forcer production de '{products[i]['name']}'",
                forced_change=f"qty[{i}]>=1",
                new_status=status_name(st3),
                new_objective=float(new_p) if new_p is not None else None,
                delta=float(delta3) if delta3 is not None else None,
                explanation=expl,
            ))

    notes = [
        f"Profit total optimal : {total_profit}.",
        f"Plan : {', '.join(f'{k}={v}' for k, v in production.items() if v > 0)}.",
    ]

    return SolverOutput(
        problem_name="production_planning",
        problem_type="production_planning",
        parameters=params,
        status=status_name(status),
        objective_value=float(total_profit),
        objective_direction="maximize",
        variables={"production": production, "total_profit": total_profit},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=counterfactuals,
        notes=notes,
    )
