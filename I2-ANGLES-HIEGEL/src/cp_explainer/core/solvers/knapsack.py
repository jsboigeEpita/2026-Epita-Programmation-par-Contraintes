"""Solveur CP-SAT — Problème du sac à dos (0/1 knapsack)."""

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
    capacity = params["capacity"]
    items = params["items"]
    n = len(items)
    weights = [it["weight"] for it in items]
    values = [it["value"] for it in items]
    names = [it["name"] for it in items]

    model = cp_model.CpModel()
    take = [model.NewBoolVar(f"take_{i}") for i in range(n)]
    model.Add(sum(weights[i] * take[i] for i in range(n)) <= capacity)
    model.Maximize(sum(values[i] * take[i] for i in range(n)))

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="knapsack", problem_type="knapsack",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="maximize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable ou inconnu."],
        )

    take_vals = [bool(solver.Value(take[i])) for i in range(n)]
    weight_used = sum(weights[i] * take_vals[i] for i in range(n))
    total_value = int(solver.ObjectiveValue())

    cap_slack = capacity - weight_used
    constraints = [
        ConstraintAnalysis(
            name="capacity",
            description=f"Poids total ≤ {capacity}",
            formula=f"sum(weights × take) = {weight_used} ≤ {capacity}",
            lhs_value=float(weight_used),
            rhs_value=float(capacity),
            slack=float(cap_slack),
            is_binding=(cap_slack == 0),
        )
    ]

    sensitivity = []
    for delta in [5, 10, 20]:
        m2 = cp_model.CpModel()
        t2 = [m2.NewBoolVar(f"take_{i}") for i in range(n)]
        m2.Add(sum(weights[i] * t2[i] for i in range(n)) <= capacity + delta)
        m2.Maximize(sum(values[i] * t2[i] for i in range(n)))
        s2, st2 = solve_with_workers(m2)
        if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            new_obj = int(s2.ObjectiveValue())
            improvement = new_obj - total_value
            sensitivity.append(SensitivityEntry(
                constraint_name="capacity",
                relaxation_amount=float(delta),
                original_objective=float(total_value),
                new_objective=float(new_obj),
                improvement=float(improvement),
                description=f"Capacite +{delta} → valeur {new_obj} (+{improvement})",
            ))

    counterfactuals = []
    for i in range(n):
        if not take_vals[i]:
            m3 = cp_model.CpModel()
            t3 = [m3.NewBoolVar(f"take_{j}") for j in range(n)]
            m3.Add(sum(weights[j] * t3[j] for j in range(n)) <= capacity)
            m3.Add(t3[i] == 1)
            m3.Maximize(sum(values[j] * t3[j] for j in range(n)))
            s3, st3 = solve_with_workers(m3)
            if st3 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_obj3 = int(s3.ObjectiveValue())
                delta3 = new_obj3 - total_value
                expl = (
                    f"Forcer '{names[i]}' donne une valeur de {new_obj3} "
                    f"({delta3:+d} par rapport à l'optimal {total_value})."
                )
            else:
                new_obj3 = None
                delta3 = None
                expl = f"Forcer '{names[i]}' rend le problème infaisable (poids trop élevé)."
            counterfactuals.append(CounterfactualEntry(
                description=f"Forcer l'inclusion de '{names[i]}'",
                forced_change=f"take[{i}]=1",
                new_status=status_name(st3),
                new_objective=float(new_obj3) if new_obj3 is not None else None,
                delta=float(delta3) if delta3 is not None else None,
                explanation=expl,
            ))

    unselected = [names[i] for i in range(n) if not take_vals[i]]
    notes = []
    if cap_slack == 0:
        notes.append("La contrainte de capacité est active (slack=0) : le sac est plein.")
    else:
        notes.append(f"La contrainte de capacité a une marge de {cap_slack} unités de poids.")
    if unselected:
        notes.append(f"Articles non sélectionnés : {', '.join(unselected)}.")

    return SolverOutput(
        problem_name="knapsack",
        problem_type="knapsack",
        parameters=params,
        status=status_name(status),
        objective_value=float(total_value),
        objective_direction="maximize",
        variables={
            "selected_items": [names[i] for i in range(n) if take_vals[i]],
            "rejected_items": unselected,
            "take": take_vals,
            "weight_used": weight_used,
            "capacity": capacity,
            "total_value": total_value,
        },
        constraint_analyses=constraints,
        sensitivity=sensitivity,
        counterfactuals=counterfactuals,
        notes=notes,
    )
