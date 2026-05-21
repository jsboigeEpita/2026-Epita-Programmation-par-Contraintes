"""Solveur CP-SAT — Problème d'affectation (assignment)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    CounterfactualEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict) -> SolverOutput:
    workers = params["workers"]
    tasks = params["tasks"]
    cost_matrix = params["cost_matrix"]
    nw, nt = len(workers), len(tasks)

    model = cp_model.CpModel()
    assign = [[model.NewBoolVar(f"x_{i}_{j}") for j in range(nt)] for i in range(nw)]

    for i in range(nw):
        model.Add(sum(assign[i][j] for j in range(nt)) == 1)
    for j in range(nt):
        model.Add(sum(assign[i][j] for i in range(nw)) == 1)

    model.Minimize(sum(
        cost_matrix[i][j] * assign[i][j]
        for i in range(nw) for j in range(nt)
    ))

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="assignment", problem_type="assignment",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    total_cost = int(solver.ObjectiveValue())
    assignment = {}
    for i in range(nw):
        for j in range(nt):
            if solver.Value(assign[i][j]):
                assignment[workers[i]] = tasks[j]

    constraint_analyses = []
    for i in range(nw):
        actual = sum(solver.Value(assign[i][j]) for j in range(nt))
        constraint_analyses.append(ConstraintAnalysis(
            name=f"worker_{i}_assigned_once",
            description=f"'{workers[i]}' assigné à exactement 1 tâche",
            formula=f"sum(assign[{i}]) = {actual} = 1",
            lhs_value=float(actual),
            rhs_value=1.0,
            slack=0.0,
            is_binding=True,
        ))
    for j in range(nt):
        actual = sum(solver.Value(assign[i][j]) for i in range(nw))
        constraint_analyses.append(ConstraintAnalysis(
            name=f"task_{j}_covered_once",
            description=f"Tâche '{tasks[j]}' couverte par exactement 1 travailleur",
            formula=f"sum(assign[*][{j}]) = {actual} = 1",
            lhs_value=float(actual),
            rhs_value=1.0,
            slack=0.0,
            is_binding=True,
        ))

    counterfactuals = []
    for i in range(nw):
        for j in range(nt):
            if not solver.Value(assign[i][j]):
                m2 = cp_model.CpModel()
                a2 = [[m2.NewBoolVar(f"x_{ii}_{jj}") for jj in range(nt)] for ii in range(nw)]
                for ii in range(nw):
                    m2.Add(sum(a2[ii][jj] for jj in range(nt)) == 1)
                for jj in range(nt):
                    m2.Add(sum(a2[ii][jj] for ii in range(nw)) == 1)
                m2.Add(a2[i][j] == 1)
                m2.Minimize(sum(cost_matrix[ii][jj] * a2[ii][jj] for ii in range(nw) for jj in range(nt)))
                s2, st2 = solve_with_workers(m2)
                if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    new_cost = int(s2.ObjectiveValue())
                    delta = new_cost - total_cost
                    expl = (
                        f"Forcer '{workers[i]} → {tasks[j]}' coûte {new_cost} "
                        f"({delta:+d} par rapport à l'optimal {total_cost})."
                    )
                else:
                    new_cost = None
                    delta = None
                    expl = f"Forcer '{workers[i]} → {tasks[j]}' rend le problème infaisable."
                counterfactuals.append(CounterfactualEntry(
                    description=f"Forcer '{workers[i]}' → '{tasks[j]}'",
                    forced_change=f"assign[{i}][{j}]=1",
                    new_status=status_name(st2),
                    new_objective=float(new_cost) if new_cost is not None else None,
                    delta=float(delta) if delta is not None else None,
                    explanation=expl,
                ))

    notes = [
        f"Coût total optimal : {total_cost}.",
        f"Affectations : {', '.join(f'{w} → {t}' for w, t in assignment.items())}.",
    ]

    return SolverOutput(
        problem_name="assignment",
        problem_type="assignment",
        parameters=params,
        status=status_name(status),
        objective_value=float(total_cost),
        objective_direction="minimize",
        variables={"assignment": assignment, "total_cost": total_cost},
        constraint_analyses=constraint_analyses,
        sensitivity=[],
        counterfactuals=counterfactuals[:6],
        notes=notes,
    )
