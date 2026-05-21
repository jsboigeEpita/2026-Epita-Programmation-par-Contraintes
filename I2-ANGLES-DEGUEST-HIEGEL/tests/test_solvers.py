"""Tests : verifie que tous les solveurs CP-SAT tournent et produisent des resultats valides."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PROBLEMS_DIR = SRC / "data"

import sys
sys.path.insert(0, str(SRC))

from cp_explainer.core.solver import solve


def _load(name: str) -> dict:
    path = PROBLEMS_DIR / f"{name}.json"
    data = json.loads(path.read_text())
    return data["type"], data["parameters"]


def test_knapsack():
    problem_type, params = _load("knapsack")
    result = solve(problem_type, params)
    assert result.status == "OPTIMAL"
    assert result.objective_value is not None and result.objective_value > 0
    assert len(result.variables["selected_items"]) > 0
    assert result.variables["weight_used"] <= params["capacity"]


def test_diet():
    problem_type, params = _load("diet")
    result = solve(problem_type, params)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective_value is not None
    reqs = params["requirements"]
    actual = result.variables["actual_nutrients"]
    assert actual["calories"] >= reqs["min_calories"] - 1
    assert actual["calories"] <= reqs["max_calories"] + 1
    assert actual["protein"] >= reqs["min_protein"] - 1


def test_job_shop():
    problem_type, params = _load("job_shop")
    result = solve(problem_type, params)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective_value is not None and result.objective_value > 0
    assert "schedule" in result.variables


def test_assignment():
    problem_type, params = _load("assignment")
    result = solve(problem_type, params)
    assert result.status == "OPTIMAL"
    assignment = result.variables["assignment"]
    assert set(assignment.keys()) == set(params["workers"])
    assert set(assignment.values()) == set(params["tasks"])
    assert result.objective_value == 13


def test_bin_packing():
    problem_type, params = _load("bin_packing")
    result = solve(problem_type, params)
    assert result.status == "OPTIMAL"
    n_bins = int(result.objective_value)
    total_size = sum(it["size"] for it in params["items"])
    lb = -(-total_size // params["bin_capacity"])
    assert n_bins >= lb
    assert n_bins == 4


def test_constraint_analyses_populated():
    for name in ["knapsack", "diet", "job_shop", "assignment", "bin_packing"]:
        problem_type, params = _load(name)
        result = solve(problem_type, params)
        assert len(result.constraint_analyses) > 0, f"{name}: pas de constraint_analyses"


def test_sensitivity_knapsack():
    problem_type, params = _load("knapsack")
    result = solve(problem_type, params)
    assert len(result.sensitivity) > 0
    for s in result.sensitivity:
        assert s.new_objective >= s.original_objective


def test_counterfactuals_knapsack():
    problem_type, params = _load("knapsack")
    result = solve(problem_type, params)
    rejected = result.variables.get("rejected_items", [])
    assert len(result.counterfactuals) == len(rejected)


def test_nurse_scheduling():
    problem_type, params = _load("nurse_scheduling")
    result = solve(problem_type, params)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective_value is not None and result.objective_value > 0
    assert "schedule" in result.variables
    assert "shifts_per_nurse" in result.variables
    for nurse, shifts in result.variables["shifts_per_nurse"].items():
        assert shifts <= params["max_shifts_per_nurse"]


def test_graph_coloring():
    problem_type, params = _load("graph_coloring")
    result = solve(problem_type, params)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective_value is not None
    coloring = result.variables["coloring"]
    for u, v in params["edges"]:
        nu = params["node_names"][u]
        nv = params["node_names"][v]
        assert coloring[nu] != coloring[nv], f"Conflit de couleur : {nu}-{nv}"
    assert result.variables["n_colors_used"] <= params["max_colors"]


def test_n_queens():
    problem_type, params = _load("n_queens")
    result = solve(problem_type, params)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    cols = result.variables["queen_cols"]
    n = params["n"]
    assert len(cols) == n
    assert len(set(cols)) == n
    for i in range(n):
        for j in range(i + 1, n):
            assert abs(cols[i] - cols[j]) != abs(i - j)


def test_production_planning():
    problem_type, params = _load("production_planning")
    result = solve(problem_type, params)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective_value is not None and result.objective_value > 0
    production = result.variables["production"]
    for rk, cap in params["resources"].items():
        used = sum(params["products"][i][rk] * production[p["name"]]
                   for i, p in enumerate(params["products"]))
        assert used <= cap


def test_tsp():
    problem_type, params = _load("tsp")
    result = solve(problem_type, params)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective_value is not None and result.objective_value > 0
    tour = result.variables["tour"]
    cities = params["cities"]
    assert len(tour) == len(cities) + 1
    assert tour[0] == tour[-1]
    assert set(tour[:-1]) == set(cities)


def test_constraint_analyses_all_problems():
    all_problems = [
        "knapsack", "diet", "job_shop", "assignment", "bin_packing",
        "nurse_scheduling", "graph_coloring", "n_queens",
        "production_planning", "tsp",
    ]
    for name in all_problems:
        problem_type, params = _load(name)
        result = solve(problem_type, params)
        assert len(result.constraint_analyses) > 0, f"{name}: pas de constraint_analyses"
