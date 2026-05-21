"""Solveur CP-SAT — Problème de bin packing."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    SensitivityEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict, _depth: int = 0) -> SolverOutput:
    items = params["items"]
    bin_capacity = params["bin_capacity"]
    n = len(items)
    sizes = [it["size"] for it in items]
    item_names = [it["name"] for it in items]
    max_bins = n

    model = cp_model.CpModel()
    bin_used = [model.NewBoolVar(f"bin_{b}") for b in range(max_bins)]
    assign = [[model.NewBoolVar(f"assign_{i}_{b}") for b in range(max_bins)] for i in range(n)]

    for i in range(n):
        model.Add(sum(assign[i][b] for b in range(max_bins)) == 1)

    for b in range(max_bins):
        model.Add(sum(sizes[i] * assign[i][b] for i in range(n)) <= bin_capacity * bin_used[b])

    for b in range(max_bins - 1):
        model.Add(bin_used[b] >= bin_used[b + 1])

    model.Minimize(sum(bin_used))

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="bin_packing", problem_type="bin_packing",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    n_bins = int(solver.ObjectiveValue())
    bin_contents: dict[int, list] = {}
    for b in range(max_bins):
        if solver.Value(bin_used[b]):
            bin_contents[b] = [item_names[i] for i in range(n) if solver.Value(assign[i][b])]

    constraint_analyses = []
    for b, contents in bin_contents.items():
        load = sum(sizes[i] for i in range(n) if solver.Value(assign[i][b]))
        slack = bin_capacity - load
        constraint_analyses.append(ConstraintAnalysis(
            name=f"bin_{b}_capacity",
            description=f"Capacité du bac {b} : charge {load}/{bin_capacity}",
            formula=f"sum(sizes in bin {b}) = {load} ≤ {bin_capacity}",
            lhs_value=float(load),
            rhs_value=float(bin_capacity),
            slack=float(slack),
            is_binding=(slack == 0),
        ))

    total_size = sum(sizes)
    lb = -(-total_size // bin_capacity)
    sensitivity = []
    if _depth == 0 and bin_capacity < total_size:
        new_cap = bin_capacity + 2
        res2 = solve({**params, "bin_capacity": new_cap}, _depth=1)
        if res2.objective_value is not None:
            improvement = n_bins - int(res2.objective_value)
            sensitivity.append(SensitivityEntry(
                constraint_name="bin_capacity",
                relaxation_amount=2.0,
                original_objective=float(n_bins),
                new_objective=res2.objective_value,
                improvement=float(improvement),
                description=f"Capacite +2 ({new_cap}) → {int(res2.objective_value)} bacs (-{improvement})",
            ))

    notes = [
        f"Nombre optimal de bacs : {n_bins}.",
        f"Borne inférieure théorique (ceil(total_size/capacity)) = {lb}.",
        f"Taille totale des objets : {total_size} / (capacité {bin_capacity} × {n_bins} bacs = {bin_capacity * n_bins}).",
    ]

    return SolverOutput(
        problem_name="bin_packing",
        problem_type="bin_packing",
        parameters=params,
        status=status_name(status),
        objective_value=float(n_bins),
        objective_direction="minimize",
        variables={
            "n_bins": n_bins,
            "bin_contents": {str(b): c for b, c in bin_contents.items()},
            "theoretical_lower_bound": lb,
            "total_size": total_size,
            "bin_capacity": bin_capacity,
        },
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )
