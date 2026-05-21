"""Solveur CP-SAT — Problème de régime alimentaire (diet)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    SensitivityEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict) -> SolverOutput:
    foods = params["foods"]
    requirements = params["requirements"]
    n = len(foods)
    max_servings = params.get("max_servings_per_food", 5)

    COST_SCALE = 100
    nutrient_keys = ["calories", "protein", "fat", "carbs"]

    def _build_model(req_override: dict | None = None):
        reqs = {**requirements, **(req_override or {})}
        m = cp_model.CpModel()
        q = [m.NewIntVar(0, max_servings, f"qty_{i}") for i in range(n)]
        for key in nutrient_keys:
            vals = [round(f[key]) for f in foods]
            if f"min_{key}" in reqs:
                m.Add(sum(vals[i] * q[i] for i in range(n)) >= round(reqs[f"min_{key}"]))
            if f"max_{key}" in reqs:
                m.Add(sum(vals[i] * q[i] for i in range(n)) <= round(reqs[f"max_{key}"]))
        costs = [round(f["cost"] * COST_SCALE) for f in foods]
        m.Minimize(sum(costs[i] * q[i] for i in range(n)))
        return m, q

    model, qty = _build_model()
    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="diet", problem_type="diet",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    qty_vals = [solver.Value(qty[i]) for i in range(n)]
    total_cost = solver.ObjectiveValue() / COST_SCALE
    actual = {k: sum(foods[i][k] * qty_vals[i] for i in range(n)) for k in nutrient_keys}

    constraint_analyses = []
    for key in nutrient_keys:
        if f"min_{key}" in requirements:
            rhs = requirements[f"min_{key}"]
            lhs = actual[key]
            slack = lhs - rhs
            constraint_analyses.append(ConstraintAnalysis(
                name=f"min_{key}",
                description=f"{key} ≥ {rhs}",
                formula=f"sum({key} × qty) = {lhs:.0f} ≥ {rhs}",
                lhs_value=round(lhs, 1),
                rhs_value=float(rhs),
                slack=round(slack, 1),
                is_binding=(abs(slack) < 1.0),
            ))
        if f"max_{key}" in requirements:
            rhs = requirements[f"max_{key}"]
            lhs = actual[key]
            slack = rhs - lhs
            constraint_analyses.append(ConstraintAnalysis(
                name=f"max_{key}",
                description=f"{key} ≤ {rhs}",
                formula=f"sum({key} × qty) = {lhs:.0f} ≤ {rhs}",
                lhs_value=round(lhs, 1),
                rhs_value=float(rhs),
                slack=round(slack, 1),
                is_binding=(abs(slack) < 1.0),
            ))

    sensitivity = []
    if "min_calories" in requirements:
        for delta in [100, 200]:
            new_reqs = {**requirements, "min_calories": requirements["min_calories"] - delta}
            m2, q2 = _build_model(new_reqs)
            s2, st2 = solve_with_workers(m2)
            if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_cost = s2.ObjectiveValue() / COST_SCALE
                improvement = total_cost - new_cost
                sensitivity.append(SensitivityEntry(
                    constraint_name="min_calories",
                    relaxation_amount=float(delta),
                    original_objective=round(total_cost, 2),
                    new_objective=round(new_cost, 2),
                    improvement=round(improvement, 2),
                    description=(
                        f"Calories min -{delta} kcal → coût {new_cost:.2f}€ "
                        f"(économie {improvement:.2f}€)"
                    ),
                ))

    food_names = [f["name"] for f in foods]
    selection = {food_names[i]: qty_vals[i] for i in range(n) if qty_vals[i] > 0}

    notes = []
    binding = [c.name for c in constraint_analyses if c.is_binding]
    if binding:
        notes.append(f"Contraintes actives : {', '.join(binding)}.")
    notes.append(f"Coût total : {total_cost:.2f}€ pour {sum(qty_vals)} portions.")

    return SolverOutput(
        problem_name="diet",
        problem_type="diet",
        parameters=params,
        status=status_name(status),
        objective_value=round(total_cost, 2),
        objective_direction="minimize",
        variables={
            "selection": selection,
            "actual_nutrients": {k: round(actual[k], 1) for k in nutrient_keys},
            "total_cost": round(total_cost, 2),
        },
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )
