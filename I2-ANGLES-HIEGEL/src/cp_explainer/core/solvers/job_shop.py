"""Solveur CP-SAT — Problème d'ordonnancement d'atelier (job shop)."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.core.schemas import (
    ConstraintAnalysis,
    SensitivityEntry,
    SolverOutput,
)
from cp_explainer.core.solvers._helpers import solve_with_workers, status_name


def solve(params: dict, _depth: int = 0) -> SolverOutput:
    jobs = params["jobs"]
    n_machines = params["n_machines"]
    horizon = sum(task["duration"] for job in jobs for task in job["tasks"])

    model = cp_model.CpModel()
    starts: dict[tuple, object] = {}
    ends: dict[tuple, object] = {}
    intervals_by_machine: dict[int, list] = {m: [] for m in range(n_machines)}

    for j, job in enumerate(jobs):
        prev_end = None
        for k, task in enumerate(job["tasks"]):
            m_id = task["machine"]
            dur = task["duration"]
            s = model.NewIntVar(0, horizon, f"s_{j}_{k}")
            e = model.NewIntVar(0, horizon, f"e_{j}_{k}")
            iv = model.NewIntervalVar(s, dur, e, f"iv_{j}_{k}")
            starts[(j, k)] = s
            ends[(j, k)] = e
            intervals_by_machine[m_id].append(iv)
            if prev_end is not None:
                model.Add(s >= prev_end)
            prev_end = e

    for m_id, ivs in intervals_by_machine.items():
        model.AddNoOverlap(ivs)

    makespan = model.NewIntVar(0, horizon, "makespan")
    last_ends = [ends[(j, len(job["tasks"]) - 1)] for j, job in enumerate(jobs)]
    model.AddMaxEquality(makespan, last_ends)
    model.Minimize(makespan)

    solver, status = solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="job_shop", problem_type="job_shop",
            parameters=params, status=status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    makespan_val = int(solver.ObjectiveValue())
    schedule = {}
    for j, job in enumerate(jobs):
        for k, task in enumerate(job["tasks"]):
            s_val = solver.Value(starts[(j, k)])
            e_val = solver.Value(ends[(j, k)])
            key = f"job_{j}_task_{k}"
            schedule[key] = {"start": s_val, "end": e_val, "machine": task["machine"],
                             "job_name": job["name"], "task_idx": k}

    job_durations = [sum(t["duration"] for t in job["tasks"]) for job in jobs]
    critical_job_idx = job_durations.index(max(job_durations))

    constraint_analyses = []
    for m_id in range(n_machines):
        machine_name = params.get("machine_names", {}).get(str(m_id), f"Machine {m_id}")
        machine_tasks = [
            (j, k, task)
            for j, job in enumerate(jobs)
            for k, task in enumerate(job["tasks"])
            if task["machine"] == m_id
        ]
        task_times = [(solver.Value(starts[(j, k)]), solver.Value(ends[(j, k)]), j, k)
                      for j, k, _ in machine_tasks]
        task_times.sort()

        min_gap = None
        for idx in range(len(task_times) - 1):
            gap = task_times[idx + 1][0] - task_times[idx][1]
            if min_gap is None or gap < min_gap:
                min_gap = gap

        constraint_analyses.append(ConstraintAnalysis(
            name=f"no_overlap_machine_{m_id}",
            description=f"Pas de chevauchement sur {machine_name}",
            formula=f"NoOverlap(tasks on machine {m_id})",
            lhs_value=None,
            rhs_value=None,
            slack=float(min_gap) if min_gap is not None else None,
            is_binding=(min_gap == 0) if min_gap is not None else False,
        ))

    constraint_analyses.append(ConstraintAnalysis(
        name="makespan",
        description=f"Makespan = max(job completion times) = {makespan_val}",
        formula=f"makespan = max(end_times) = {makespan_val}",
        lhs_value=float(makespan_val),
        rhs_value=float(makespan_val),
        slack=0.0,
        is_binding=True,
    ))

    sensitivity = []
    if _depth == 0:
        for j, job in enumerate(jobs):
            for k, task in enumerate(job["tasks"]):
                if task["duration"] >= 3:
                    jobs2 = [{
                        "name": jb["name"],
                        "tasks": [
                            {"machine": t["machine"],
                             "duration": t["duration"] - 1 if (jj == j and kk == k) else t["duration"]}
                            for kk, t in enumerate(jb["tasks"])
                        ]
                    } for jj, jb in enumerate(jobs)]
                    res2 = solve(
                        {"jobs": jobs2, "n_machines": n_machines,
                         "machine_names": params.get("machine_names", {})},
                        _depth=1,
                    )
                    if res2.objective_value is not None:
                        improvement = makespan_val - res2.objective_value
                        if improvement > 0:
                            sensitivity.append(SensitivityEntry(
                                constraint_name=f"duration_job{j}_task{k}",
                                relaxation_amount=1.0,
                                original_objective=float(makespan_val),
                                new_objective=res2.objective_value,
                                improvement=improvement,
                                description=(
                                    f"Réduire la durée de la tâche {k} du job '{job['name']}' "
                                    f"de 1 unité → makespan {res2.objective_value} "
                                    f"(-{improvement})"
                                ),
                            ))

    job_names = [job["name"] for job in jobs]
    notes = [
        f"Makespan optimal : {makespan_val}.",
        f"Job avec la durée totale maximale : '{jobs[critical_job_idx]['name']}' "
        f"({job_durations[critical_job_idx]} unités).",
    ]

    return SolverOutput(
        problem_name="job_shop",
        problem_type="job_shop",
        parameters=params,
        status=status_name(status),
        objective_value=float(makespan_val),
        objective_direction="minimize",
        variables={"schedule": schedule, "makespan": makespan_val, "jobs": job_names},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity[:3],
        counterfactuals=[],
        notes=notes,
    )
