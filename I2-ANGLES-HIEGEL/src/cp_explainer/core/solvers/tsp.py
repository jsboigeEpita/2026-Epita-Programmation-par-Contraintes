"""Solveur CP-SAT — Problème du voyageur de commerce (TSP)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    SensitivityEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict) -> SolverOutput:
    cities = params["cities"]
    distances = params["distances"]
    n = len(cities)

    model = cp_model.CpModel()
    nxt = [model.NewIntVar(0, n - 1, f"next_{i}") for i in range(n)]

    arcs = []
    for i in range(n):
        for j in range(n):
            if i != j:
                arc_lit = model.NewBoolVar(f"arc_{i}_{j}")
                arcs.append((i, j, arc_lit))
    model.AddCircuit(arcs)

    arc_map: dict[tuple, object] = {}
    for i, j, lit in arcs:
        arc_map[(i, j)] = lit

    total_dist = model.NewIntVar(0, sum(max(row) for row in distances) * n, "total_dist")
    model.Add(total_dist == sum(
        distances[i][j] * arc_map[(i, j)]
        for i in range(n) for j in range(n) if i != j
    ))
    model.Minimize(total_dist)

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="tsp", problem_type="tsp",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    total_dist_val = int(solver.ObjectiveValue())

    nxt_vals = {i: j for i, j, lit in arcs if solver.Value(lit)}
    tour = [0]
    while len(tour) < n:
        tour.append(nxt_vals[tour[-1]])
    tour_names = [cities[i] for i in tour] + [cities[0]]

    constraint_analyses = []
    used_arcs = [(i, j) for i, j, lit in arcs if solver.Value(lit)]
    arc_distances = [(distances[i][j], i, j) for i, j in used_arcs]
    arc_distances.sort()
    if arc_distances:
        min_d, mi, mj = arc_distances[0]
        max_d, xi, xj = arc_distances[-1]
        constraint_analyses.append(ConstraintAnalysis(
            name="circuit_constraint",
            description=f"Circuit hamiltonien : {n} villes, toutes visitées exactement une fois",
            formula=f"AddCircuit({n} villes) = {total_dist_val} km",
            lhs_value=float(total_dist_val),
            rhs_value=float(total_dist_val),
            slack=0.0,
            is_binding=True,
        ))
        constraint_analyses.append(ConstraintAnalysis(
            name="longest_arc",
            description=f"Arc le plus long : {cities[xi]}→{cities[xj]} = {max_d} km",
            formula=f"dist({cities[xi]},{cities[xj]}) = {max_d}",
            lhs_value=float(max_d),
            rhs_value=float(max_d),
            slack=0.0,
            is_binding=True,
        ))

    sensitivity = []
    if arc_distances and len(arc_distances) > 1:
        max_d, xi, xj = arc_distances[-1]
        m2 = cp_model.CpModel()
        arcs2 = []
        arc_map2: dict[tuple, object] = {}
        for i in range(n):
            for j in range(n):
                if i != j and not (i == xi and j == xj):
                    lit2 = m2.NewBoolVar(f"arc_{i}_{j}")
                    arcs2.append((i, j, lit2))
                    arc_map2[(i, j)] = lit2
        if arcs2:
            m2.AddCircuit(arcs2)
            td2 = m2.NewIntVar(0, sum(max(row) for row in distances) * n, "td2")
            m2.Add(td2 == sum(
                distances[i][j] * arc_map2[(i, j)]
                for i, j in arc_map2
            ))
            m2.Minimize(td2)
            s2, st2 = solve_with_workers(m2)
            if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_dist = int(s2.ObjectiveValue())
                improvement = new_dist - total_dist_val
                sensitivity.append(SensitivityEntry(
                    constraint_name=f"arc_{cities[xi]}_{cities[xj]}",
                    relaxation_amount=float(max_d),
                    original_objective=float(total_dist_val),
                    new_objective=float(new_dist),
                    improvement=float(improvement),
                    description=(f"Sans l'arc {cities[xi]}→{cities[xj]} ({max_d}km) "
                                 f"→ distance {new_dist} km ({improvement:+d})"),
                ))

    notes = [
        f"Distance optimale : {total_dist_val} km.",
        f"Tour : {' → '.join(tour_names)}.",
    ]

    return SolverOutput(
        problem_name="tsp",
        problem_type="tsp",
        parameters=params,
        status=status_name(status),
        objective_value=float(total_dist_val),
        objective_direction="minimize",
        variables={"tour": tour_names, "tour_indices": tour + [0], "total_distance": total_dist_val},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )
