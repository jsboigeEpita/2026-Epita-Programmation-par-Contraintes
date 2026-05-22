"""Dispatcher : route problem_type vers le solveur correspondant."""

from __future__ import annotations

from cp_explainer.core.schemas import SolverOutput
from cp_explainer.core.solvers import (
    assignment,
    bin_packing,
    diet,
    graph_coloring,
    job_shop,
    knapsack,
    n_queens,
    nurse_scheduling,
    production_planning,
    tsp,
)

SOLVERS = {
    "knapsack": knapsack.solve,
    "diet": diet.solve,
    "job_shop": job_shop.solve,
    "assignment": assignment.solve,
    "bin_packing": bin_packing.solve,
    "nurse_scheduling": nurse_scheduling.solve,
    "graph_coloring": graph_coloring.solve,
    "n_queens": n_queens.solve,
    "production_planning": production_planning.solve,
    "tsp": tsp.solve,
}


def solve(problem_type: str, params: dict) -> SolverOutput:
    """Résoudre un problème CP-SAT et retourner une analyse complète."""
    fn = SOLVERS.get(problem_type)
    if fn is None:
        raise ValueError(
            f"Type de probleme inconnu : {problem_type!r}. "
            f"Disponibles : {list(SOLVERS)}"
        )
    return fn(params)
