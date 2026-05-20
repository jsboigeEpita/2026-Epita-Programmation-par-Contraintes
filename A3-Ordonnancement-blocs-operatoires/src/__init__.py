"""
A3 — Ordonnancement de blocs opératoires
========================================
Modules
-------
models
    Surgery, Surgeon, Room, Instance, Assignment, ScheduleResult, Priority.
instances
    Générateur d'instances synthétiques.
cp_solver
    Modèle CP-SAT (OR-Tools).
heuristics
    Règle de priorité et recuit simulé.
visualization
    Gantt et tracés comparatifs.
"""

from .models import (
    Assignment,
    Instance,
    Priority,
    Room,
    ScheduleResult,
    Surgeon,
    Surgery,
)
from .instances import generate_instance, format_instance
from .cp_solver import solve_cp_sat, ALPHA_MAKESPAN, BETA_WAIT, GAMMA_PREF
from .heuristics import (
    solve_priority_rule,
    solve_simulated_annealing,
    schedule_objective,
)
from .visualization import (
    plot_gantt,
    plot_surgeon_utilization,
    plot_solver_comparison,
    format_schedule,
)

__all__ = [
    # models
    "Assignment", "Instance", "Priority", "Room", "ScheduleResult",
    "Surgeon", "Surgery",
    # instances
    "generate_instance", "format_instance",
    # cp_solver
    "solve_cp_sat", "ALPHA_MAKESPAN", "BETA_WAIT", "GAMMA_PREF",
    # heuristics
    "solve_priority_rule", "solve_simulated_annealing", "schedule_objective",
    # visualization
    "plot_gantt", "plot_surgeon_utilization", "plot_solver_comparison",
    "format_schedule",
]
