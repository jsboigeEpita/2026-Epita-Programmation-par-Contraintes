"""Solveur CP-SAT — Problème des N reines (n-queens)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    CounterfactualEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict) -> SolverOutput:
    n = params["n"]

    model = cp_model.CpModel()
    queens = [model.NewIntVar(0, n - 1, f"q_{i}") for i in range(n)]

    model.AddAllDifferent(queens)

    for i in range(n):
        for j in range(i + 1, n):
            diff = abs(i - j)
            model.Add(queens[i] - queens[j] != diff)
            model.Add(queens[j] - queens[i] != diff)

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="n_queens", problem_type="n_queens",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction=None,
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Aucune solution (n trop petit)."],
        )

    queen_cols = [solver.Value(queens[i]) for i in range(n)]
    placement = {f"row_{i}": queen_cols[i] for i in range(n)}

    constraint_analyses = []
    constraint_analyses.append(ConstraintAnalysis(
        name="all_different_columns",
        description=f"Toutes les {n} reines sur des colonnes différentes",
        formula=f"AllDifferent(queens) = {sorted(queen_cols)}",
        lhs_value=float(len(set(queen_cols))),
        rhs_value=float(n),
        slack=0.0,
        is_binding=True,
    ))

    min_diag_gap = None
    for i in range(n):
        for j in range(i + 1, n):
            row_diff = abs(i - j)
            col_diff = abs(queen_cols[i] - queen_cols[j])
            gap = abs(col_diff - row_diff)
            if min_diag_gap is None or gap < min_diag_gap:
                min_diag_gap = gap

    constraint_analyses.append(ConstraintAnalysis(
        name="no_diagonal_attacks",
        description="Aucune reine ne s'attaque en diagonale",
        formula="|col[i]-col[j]| ≠ |row[i]-row[j]| pour tout i≠j",
        lhs_value=float(min_diag_gap) if min_diag_gap is not None else None,
        rhs_value=1.0,
        slack=float(min_diag_gap - 1) if min_diag_gap is not None else None,
        is_binding=(min_diag_gap == 1) if min_diag_gap is not None else False,
    ))

    counterfactuals = []
    if n >= 4:
        m2 = cp_model.CpModel()
        q2 = [m2.NewIntVar(0, n - 1, f"q_{i}") for i in range(n)]
        m2.AddAllDifferent(q2)
        for i in range(n):
            for j in range(i + 1, n):
                d2 = abs(i - j)
                m2.Add(q2[i] - q2[j] != d2)
                m2.Add(q2[j] - q2[i] != d2)
        m2.Add(q2[0] == 0)
        s2, st2 = solve_with_workers(m2)
        status_str = status_name(st2)
        counterfactuals.append(CounterfactualEntry(
            description="Forcer la reine de la ligne 0 en colonne 0",
            forced_change="queen[0]=0",
            new_status=status_str,
            new_objective=None,
            delta=None,
            explanation=f"Avec queen[0]=0 : {status_str}.",
        ))

    notes = [
        f"Solution trouvée pour {n} reines.",
        f"Placement (colonne par ligne) : {queen_cols}.",
    ]

    return SolverOutput(
        problem_name="n_queens",
        problem_type="n_queens",
        parameters=params,
        status=status_name(status),
        objective_value=float(n),
        objective_direction=None,
        variables={"placement": placement, "queen_cols": queen_cols},
        constraint_analyses=constraint_analyses,
        sensitivity=[],
        counterfactuals=counterfactuals,
        notes=notes,
    )
