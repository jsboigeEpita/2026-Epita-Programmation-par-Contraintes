"""Fonctions utilitaires partagées par tous les solveurs."""

from __future__ import annotations

from ortools.sat.python import cp_model


def status_name(status: int) -> str:
    names = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }
    return names.get(status, "UNKNOWN")


def solve_with_workers(model: cp_model.CpModel) -> tuple[cp_model.CpSolver, int]:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    return solver, status
