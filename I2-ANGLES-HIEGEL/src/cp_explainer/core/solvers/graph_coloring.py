"""Solveur CP-SAT — Coloration de graphe (graph coloring)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    CounterfactualEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict) -> SolverOutput:
    n_nodes = params["n_nodes"]
    node_names = params.get("node_names", [str(i) for i in range(n_nodes)])
    edges = params["edges"]
    max_colors = params["max_colors"]

    model = cp_model.CpModel()
    colors = [model.NewIntVar(0, max_colors - 1, f"color_{i}") for i in range(n_nodes)]

    for u, v in edges:
        model.Add(colors[u] != colors[v])

    n_colors_used = model.NewIntVar(1, max_colors, "n_colors_used")
    model.AddMaxEquality(n_colors_used, colors)
    max_color_idx = model.NewIntVar(0, max_colors - 1, "max_color_idx")
    model.AddMaxEquality(max_color_idx, colors)
    actual_colors = model.NewIntVar(1, max_colors, "actual_colors")
    model.Add(actual_colors == max_color_idx + 1)
    model.Minimize(actual_colors)

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="graph_coloring", problem_type="graph_coloring",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable avec ce nombre de couleurs."],
        )

    color_vals = [solver.Value(colors[i]) for i in range(n_nodes)]
    n_used = solver.Value(actual_colors)
    coloring = {node_names[i]: color_vals[i] for i in range(n_nodes)}

    constraint_analyses = []
    for u, v in edges:
        diff = abs(color_vals[u] - color_vals[v])
        constraint_analyses.append(ConstraintAnalysis(
            name=f"edge_{node_names[u]}_{node_names[v]}",
            description=f"Arête {node_names[u]}-{node_names[v]} : couleurs différentes",
            formula=f"color[{node_names[u]}]={color_vals[u]} ≠ color[{node_names[v]}]={color_vals[v]}",
            lhs_value=float(diff),
            rhs_value=1.0,
            slack=float(diff - 1),
            is_binding=(diff == 1),
        ))

    counterfactuals = []
    if n_used > 2:
        m2 = cp_model.CpModel()
        c2 = [m2.NewIntVar(0, n_used - 2, f"c_{i}") for i in range(n_nodes)]
        for u, v in edges:
            m2.Add(c2[u] != c2[v])
        mc2 = m2.NewIntVar(0, n_used - 2, "mc2")
        m2.AddMaxEquality(mc2, c2)
        ac2 = m2.NewIntVar(1, n_used - 1, "ac2")
        m2.Add(ac2 == mc2 + 1)
        m2.Minimize(ac2)
        s2, st2 = solve_with_workers(m2)
        if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            counterfactuals.append(CounterfactualEntry(
                description=f"Colorier avec {n_used - 1} couleurs",
                forced_change=f"max_colors={n_used - 1}",
                new_status=status_name(st2),
                new_objective=float(s2.ObjectiveValue()),
                delta=float(s2.ObjectiveValue() - n_used),
                explanation=f"Avec {n_used - 1} couleurs : {status_name(st2)}.",
            ))
        else:
            counterfactuals.append(CounterfactualEntry(
                description=f"Colorier avec {n_used - 1} couleurs",
                forced_change=f"max_colors={n_used - 1}",
                new_status="INFEASIBLE",
                new_objective=None,
                delta=None,
                explanation=f"{n_used - 1} couleurs est insuffisant pour ce graphe.",
            ))

    notes = [
        f"Nombre chromatique : {n_used} couleurs suffisent.",
        f"Degré maximum : {max(sum(1 for e in edges if i in e) for i in range(n_nodes))}.",
    ]

    return SolverOutput(
        problem_name="graph_coloring",
        problem_type="graph_coloring",
        parameters=params,
        status=status_name(status),
        objective_value=float(n_used),
        objective_direction="minimize",
        variables={"coloring": coloring, "n_colors_used": n_used},
        constraint_analyses=constraint_analyses,
        sensitivity=[],
        counterfactuals=counterfactuals,
        notes=notes,
    )
