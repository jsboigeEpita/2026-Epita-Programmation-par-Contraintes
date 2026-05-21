"""Solveur CP-SAT — Planification des infirmiers (nurse scheduling)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    SensitivityEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict) -> SolverOutput:
    nurses = params["nurses"]
    n_days = params["n_days"]
    n_shifts = params["shifts_per_day"]
    min_nurses = params["min_nurses_per_shift"]
    max_shifts = params["max_shifts_per_nurse"]
    shift_names = params.get("shift_names", [str(s) for s in range(n_shifts)])
    nn, nd, ns = len(nurses), n_days, n_shifts

    model = cp_model.CpModel()
    sa = [[[model.NewBoolVar(f"sa_{n}_{d}_{s}") for s in range(ns)]
           for d in range(nd)] for n in range(nn)]

    for d in range(nd):
        for s in range(ns):
            model.Add(sum(sa[n][d][s] for n in range(nn)) >= min_nurses)

    for n in range(nn):
        for d in range(nd):
            model.Add(sum(sa[n][d][s] for s in range(ns)) <= 1)

    for n in range(nn):
        model.Add(sum(sa[n][d][s] for d in range(nd) for s in range(ns)) <= max_shifts)

    total_covered = model.NewIntVar(0, nn * nd * ns, "total_covered")
    model.Add(total_covered == sum(
        sa[n][d][s] for n in range(nn) for d in range(nd) for s in range(ns)
    ))
    model.Maximize(total_covered)

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="nurse_scheduling", problem_type="nurse_scheduling",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="maximize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    total_val = int(solver.ObjectiveValue())
    schedule: dict[str, list] = {n: [] for n in nurses}
    for n in range(nn):
        for d in range(nd):
            for s in range(ns):
                if solver.Value(sa[n][d][s]):
                    schedule[nurses[n]].append({"day": d, "shift": shift_names[s]})

    shifts_per_nurse = [sum(solver.Value(sa[n][d][s]) for d in range(nd) for s in range(ns))
                        for n in range(nn)]

    constraint_analyses = []
    for n in range(nn):
        total_n = shifts_per_nurse[n]
        slack = max_shifts - total_n
        constraint_analyses.append(ConstraintAnalysis(
            name=f"max_shifts_{nurses[n]}",
            description=f"{nurses[n]} : au plus {max_shifts} shifts",
            formula=f"shifts({nurses[n]}) = {total_n} ≤ {max_shifts}",
            lhs_value=float(total_n),
            rhs_value=float(max_shifts),
            slack=float(slack),
            is_binding=(slack == 0),
        ))

    for s in range(ns):
        covered = sum(
            1 for d in range(nd)
            if sum(solver.Value(sa[n][d][s]) for n in range(nn)) >= min_nurses
        )
        constraint_analyses.append(ConstraintAnalysis(
            name=f"coverage_shift_{shift_names[s]}",
            description=f"Shift {shift_names[s]} couvert {covered}/{nd} jours",
            formula=f"coverage({shift_names[s]}) = {covered}/{nd}",
            lhs_value=float(covered),
            rhs_value=float(nd),
            slack=float(nd - covered),
            is_binding=(covered == nd),
        ))

    sensitivity = []
    new_max = max_shifts + 1
    m2 = cp_model.CpModel()
    sa2 = [[[m2.NewBoolVar(f"sa_{n}_{d}_{s}") for s in range(ns)]
             for d in range(nd)] for n in range(nn)]
    for d in range(nd):
        for s in range(ns):
            m2.Add(sum(sa2[n][d][s] for n in range(nn)) >= min_nurses)
    for n in range(nn):
        for d in range(nd):
            m2.Add(sum(sa2[n][d][s] for s in range(ns)) <= 1)
        m2.Add(sum(sa2[n][d][s] for d in range(nd) for s in range(ns)) <= new_max)
    tc2 = m2.NewIntVar(0, nn * nd * ns, "tc2")
    m2.Add(tc2 == sum(sa2[n][d][s] for n in range(nn) for d in range(nd) for s in range(ns)))
    m2.Maximize(tc2)
    s2, st2 = solve_with_workers(m2)
    if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        new_val = int(s2.ObjectiveValue())
        improvement = new_val - total_val
        sensitivity.append(SensitivityEntry(
            constraint_name="max_shifts_per_nurse",
            relaxation_amount=1.0,
            original_objective=float(total_val),
            new_objective=float(new_val),
            improvement=float(improvement),
            description=f"max_shifts +1 ({new_max}) → {new_val} shifts couverts (+{improvement})",
        ))

    notes = [
        f"Total shifts couverts : {total_val} / {nd * ns} slots quotidiens.",
        f"Répartition : {', '.join(f'{nurses[n]}={shifts_per_nurse[n]}' for n in range(nn))}.",
    ]

    return SolverOutput(
        problem_name="nurse_scheduling",
        problem_type="nurse_scheduling",
        parameters=params,
        status=status_name(status),
        objective_value=float(total_val),
        objective_direction="maximize",
        variables={"schedule": schedule, "shifts_per_nurse": dict(zip(nurses, shifts_per_nurse))},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )
