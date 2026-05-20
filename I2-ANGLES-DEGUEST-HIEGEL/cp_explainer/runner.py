"""Orchestrateur du pipeline complet : solve -> analyze -> explain."""

from __future__ import annotations

import json
import time
from pathlib import Path

from cp_explainer.explainer import (
    explain_how_to_improve,
    explain_why_not,
    explain_why_optimal,
    template_how_to_improve,
    template_why_not,
    template_why_optimal,
)
from cp_explainer.llm_client import LLMClient
from cp_explainer.schemas import ExplainerResult
from cp_explainer.solver import solve


def run_template_only(problem_path: str | Path) -> ExplainerResult:
    """Pipeline sans LLM : uniquement le solveur + explications template."""
    path = Path(problem_path)
    problem_data = json.loads(path.read_text(encoding="utf-8"))
    problem_name = problem_data.get("name", path.stem)

    t_start = time.perf_counter()
    try:
        solution = solve(problem_data["type"], problem_data["parameters"])
    except Exception as e:
        return ExplainerResult(problem_name=problem_name, solution=None,  # type: ignore[arg-type]
                               error=str(e), error_stage="solver")

    return ExplainerResult(
        problem_name=problem_name,
        solution=solution,
        template_why_optimal=template_why_optimal(solution),
        template_why_not=template_why_not(solution),
        template_how_to_improve=template_how_to_improve(solution),
        execution_time_s=round(time.perf_counter() - t_start, 3),
    )


def run_explainer(
    client: LLMClient,
    problem_path: str | Path,
) -> ExplainerResult:
    """Pipeline complet pour un probleme.

    1. Charge le JSON du probleme.
    2. Resout avec CP-SAT + analyse des contraintes.
    3. Genere 3 explications LLM.
    4. Genere 3 explications template (pour comparaison).
    """
    path = Path(problem_path)
    problem_data = json.loads(path.read_text(encoding="utf-8"))
    problem_type = problem_data["type"]
    params = problem_data["parameters"]
    problem_name = problem_data.get("name", path.stem)

    t_start = time.perf_counter()

    # Etape 1 : resoudre
    try:
        solution = solve(problem_type, params)
    except Exception as e:
        return ExplainerResult(
            problem_name=problem_name,
            solution=None,  # type: ignore[arg-type]
            error=str(e),
            error_stage="solver",
        )

    # Etape 2 : explications LLM
    why_optimal_out = None
    why_not_out = None
    how_to_improve_out = None
    error = None
    error_stage = None

    try:
        why_optimal_out = explain_why_optimal(client, solution)
    except Exception as e:
        error = str(e)
        error_stage = "why_optimal"

    if error is None:
        try:
            why_not_out = explain_why_not(client, solution)
        except Exception as e:
            error = str(e)
            error_stage = "why_not"

    if error is None:
        try:
            how_to_improve_out = explain_how_to_improve(client, solution)
        except Exception as e:
            error = str(e)
            error_stage = "how_to_improve"

    # Etape 3 : explications template
    tmpl_optimal = template_why_optimal(solution)
    tmpl_why_not = template_why_not(solution)
    tmpl_improve = template_how_to_improve(solution)

    execution_time = time.perf_counter() - t_start

    return ExplainerResult(
        problem_name=problem_name,
        solution=solution,
        why_optimal=why_optimal_out,
        why_not=why_not_out,
        how_to_improve=how_to_improve_out,
        template_why_optimal=tmpl_optimal,
        template_why_not=tmpl_why_not,
        template_how_to_improve=tmpl_improve,
        execution_time_s=round(execution_time, 3),
        error=error,
        error_stage=error_stage,
    )
