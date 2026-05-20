"""Solveurs CP-SAT pour 5 problemes + analyse des contraintes et sensibilite."""

from __future__ import annotations

from ortools.sat.python import cp_model

from cp_explainer.schemas import (
    ConstraintAnalysis,
    CounterfactualEntry,
    SensitivityEntry,
    SolverOutput,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status_name(status: int) -> str:
    names = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }
    return names.get(status, "UNKNOWN")


def _solve_with_workers(model: cp_model.CpModel) -> tuple[cp_model.CpSolver, int]:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    return solver, status


# ---------------------------------------------------------------------------
# Knapsack 0/1
# ---------------------------------------------------------------------------

def _solve_knapsack(params: dict) -> SolverOutput:
    capacity = params["capacity"]
    items = params["items"]
    n = len(items)
    weights = [it["weight"] for it in items]
    values = [it["value"] for it in items]
    names = [it["name"] for it in items]

    model = cp_model.CpModel()
    take = [model.NewBoolVar(f"take_{i}") for i in range(n)]
    model.Add(sum(weights[i] * take[i] for i in range(n)) <= capacity)
    model.Maximize(sum(values[i] * take[i] for i in range(n)))

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="knapsack", problem_type="knapsack",
            parameters=params, status=_status_name(status),
            objective_value=None, objective_direction="maximize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable ou inconnu."],
        )

    take_vals = [bool(solver.Value(take[i])) for i in range(n)]
    weight_used = sum(weights[i] * take_vals[i] for i in range(n))
    total_value = int(solver.ObjectiveValue())

    cap_slack = capacity - weight_used
    constraints = [
        ConstraintAnalysis(
            name="capacity",
            description=f"Poids total ≤ {capacity}",
            formula=f"sum(weights × take) = {weight_used} ≤ {capacity}",
            lhs_value=float(weight_used),
            rhs_value=float(capacity),
            slack=float(cap_slack),
            is_binding=(cap_slack == 0),
        )
    ]

    # Sensibilite : relacher la capacite par tranches
    sensitivity = []
    for delta in [5, 10, 20]:
        m2 = cp_model.CpModel()
        t2 = [m2.NewBoolVar(f"take_{i}") for i in range(n)]
        m2.Add(sum(weights[i] * t2[i] for i in range(n)) <= capacity + delta)
        m2.Maximize(sum(values[i] * t2[i] for i in range(n)))
        s2, st2 = _solve_with_workers(m2)
        if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            new_obj = int(s2.ObjectiveValue())
            improvement = new_obj - total_value
            sensitivity.append(SensitivityEntry(
                constraint_name="capacity",
                relaxation_amount=float(delta),
                original_objective=float(total_value),
                new_objective=float(new_obj),
                improvement=float(improvement),
                description=f"Capacite +{delta} → valeur {new_obj} (+{improvement})",
            ))

    # Contrefactuels : forcer chaque item non selectionne
    counterfactuals = []
    for i in range(n):
        if not take_vals[i]:
            m3 = cp_model.CpModel()
            t3 = [m3.NewBoolVar(f"take_{j}") for j in range(n)]
            m3.Add(sum(weights[j] * t3[j] for j in range(n)) <= capacity)
            m3.Add(t3[i] == 1)
            m3.Maximize(sum(values[j] * t3[j] for j in range(n)))
            s3, st3 = _solve_with_workers(m3)
            if st3 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_obj3 = int(s3.ObjectiveValue())
                delta3 = new_obj3 - total_value
                expl = (
                    f"Forcer '{names[i]}' donne une valeur de {new_obj3} "
                    f"({delta3:+d} par rapport à l'optimal {total_value})."
                )
            else:
                new_obj3 = None
                delta3 = None
                expl = f"Forcer '{names[i]}' rend le problème infaisable (poids trop élevé)."
            counterfactuals.append(CounterfactualEntry(
                description=f"Forcer l'inclusion de '{names[i]}'",
                forced_change=f"take[{i}]=1",
                new_status=_status_name(st3),
                new_objective=float(new_obj3) if new_obj3 is not None else None,
                delta=float(delta3) if delta3 is not None else None,
                explanation=expl,
            ))

    unselected = [names[i] for i in range(n) if not take_vals[i]]
    notes = []
    if cap_slack == 0:
        notes.append("La contrainte de capacité est active (slack=0) : le sac est plein.")
    else:
        notes.append(f"La contrainte de capacité a une marge de {cap_slack} unités de poids.")
    if unselected:
        notes.append(f"Articles non sélectionnés : {', '.join(unselected)}.")

    return SolverOutput(
        problem_name="knapsack",
        problem_type="knapsack",
        parameters=params,
        status=_status_name(status),
        objective_value=float(total_value),
        objective_direction="maximize",
        variables={
            "selected_items": [names[i] for i in range(n) if take_vals[i]],
            "rejected_items": unselected,
            "take": take_vals,
            "weight_used": weight_used,
            "capacity": capacity,
            "total_value": total_value,
        },
        constraint_analyses=constraints,
        sensitivity=sensitivity,
        counterfactuals=counterfactuals,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Diet problem
# ---------------------------------------------------------------------------

def _solve_diet(params: dict) -> SolverOutput:
    foods = params["foods"]
    requirements = params["requirements"]
    n = len(foods)
    max_servings = params.get("max_servings_per_food", 5)

    # Portees : portions entieres (0..max_servings).
    # Valeurs nutritionnelles par portion entiere (deja entieres dans le JSON).
    # Couts en centimes pour l'arithmetique entiere CP-SAT.
    COST_SCALE = 100  # 1 euro = 100 unites
    nutrient_keys = ["calories", "protein", "fat", "carbs"]

    def _build_model(req_override: dict | None = None):
        reqs = {**requirements, **(req_override or {})}
        m = cp_model.CpModel()
        q = [m.NewIntVar(0, max_servings, f"qty_{i}") for i in range(n)]
        for key in nutrient_keys:
            vals = [round(f[key]) for f in foods]
            if f"min_{key}" in reqs:
                m.Add(sum(vals[i] * q[i] for i in range(n)) >= round(reqs[f"min_{key}"]))
            if f"max_{key}" in reqs:
                m.Add(sum(vals[i] * q[i] for i in range(n)) <= round(reqs[f"max_{key}"]))
        costs = [round(f["cost"] * COST_SCALE) for f in foods]
        m.Minimize(sum(costs[i] * q[i] for i in range(n)))
        return m, q

    model, qty = _build_model()
    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="diet", problem_type="diet",
            parameters=params, status=_status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    qty_vals = [solver.Value(qty[i]) for i in range(n)]
    total_cost = solver.ObjectiveValue() / COST_SCALE
    actual = {k: sum(foods[i][k] * qty_vals[i] for i in range(n)) for k in nutrient_keys}

    constraint_analyses = []
    for key in nutrient_keys:
        if f"min_{key}" in requirements:
            rhs = requirements[f"min_{key}"]
            lhs = actual[key]
            slack = lhs - rhs
            constraint_analyses.append(ConstraintAnalysis(
                name=f"min_{key}",
                description=f"{key} ≥ {rhs}",
                formula=f"sum({key} × qty) = {lhs:.0f} ≥ {rhs}",
                lhs_value=round(lhs, 1),
                rhs_value=float(rhs),
                slack=round(slack, 1),
                is_binding=(abs(slack) < 1.0),
            ))
        if f"max_{key}" in requirements:
            rhs = requirements[f"max_{key}"]
            lhs = actual[key]
            slack = rhs - lhs
            constraint_analyses.append(ConstraintAnalysis(
                name=f"max_{key}",
                description=f"{key} ≤ {rhs}",
                formula=f"sum({key} × qty) = {lhs:.0f} ≤ {rhs}",
                lhs_value=round(lhs, 1),
                rhs_value=float(rhs),
                slack=round(slack, 1),
                is_binding=(abs(slack) < 1.0),
            ))

    # Sensibilite : relacher min_calories de 100 et 200 kcal
    sensitivity = []
    if "min_calories" in requirements:
        for delta in [100, 200]:
            new_reqs = {**requirements, "min_calories": requirements["min_calories"] - delta}
            m2, q2 = _build_model(new_reqs)
            s2, st2 = _solve_with_workers(m2)
            if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_cost = s2.ObjectiveValue() / COST_SCALE
                improvement = total_cost - new_cost
                sensitivity.append(SensitivityEntry(
                    constraint_name="min_calories",
                    relaxation_amount=float(delta),
                    original_objective=round(total_cost, 2),
                    new_objective=round(new_cost, 2),
                    improvement=round(improvement, 2),
                    description=(
                        f"Calories min -{delta} kcal → coût {new_cost:.2f}€ "
                        f"(économie {improvement:.2f}€)"
                    ),
                ))

    food_names = [f["name"] for f in foods]
    selection = {food_names[i]: qty_vals[i] for i in range(n) if qty_vals[i] > 0}

    notes = []
    binding = [c.name for c in constraint_analyses if c.is_binding]
    if binding:
        notes.append(f"Contraintes actives : {', '.join(binding)}.")
    notes.append(f"Coût total : {total_cost:.2f}€ pour {sum(qty_vals)} portions.")

    return SolverOutput(
        problem_name="diet",
        problem_type="diet",
        parameters=params,
        status=_status_name(status),
        objective_value=round(total_cost, 2),
        objective_direction="minimize",
        variables={
            "selection": selection,
            "actual_nutrients": {k: round(actual[k], 1) for k in nutrient_keys},
            "total_cost": round(total_cost, 2),
        },
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Job Shop
# ---------------------------------------------------------------------------

def _solve_job_shop(params: dict, _depth: int = 0) -> SolverOutput:
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

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="job_shop", problem_type="job_shop",
            parameters=params, status=_status_name(status),
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

    # Identifier la chaine critique
    job_durations = [sum(t["duration"] for t in job["tasks"]) for job in jobs]
    critical_job_idx = job_durations.index(max(job_durations))

    # Contraintes de no-overlap : verifier les chevauchements evites
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

        # Slack = gap entre taches consecutives sur la meme machine
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

    # Sensibilite : reduire la duree de la tache la plus longue (seulement au niveau 0)
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
                    res2 = _solve_job_shop(
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
        status=_status_name(status),
        objective_value=float(makespan_val),
        objective_direction="minimize",
        variables={"schedule": schedule, "makespan": makespan_val, "jobs": job_names},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity[:3],
        counterfactuals=[],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Assignment problem
# ---------------------------------------------------------------------------

def _solve_assignment(params: dict) -> SolverOutput:
    workers = params["workers"]
    tasks = params["tasks"]
    cost_matrix = params["cost_matrix"]
    nw, nt = len(workers), len(tasks)

    model = cp_model.CpModel()
    assign = [[model.NewBoolVar(f"x_{i}_{j}") for j in range(nt)] for i in range(nw)]

    # Chaque travailleur assigné a exactement 1 tache
    for i in range(nw):
        model.Add(sum(assign[i][j] for j in range(nt)) == 1)
    # Chaque tache assignee a exactement 1 travailleur
    for j in range(nt):
        model.Add(sum(assign[i][j] for i in range(nw)) == 1)

    model.Minimize(sum(
        cost_matrix[i][j] * assign[i][j]
        for i in range(nw) for j in range(nt)
    ))

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="assignment", problem_type="assignment",
            parameters=params, status=_status_name(status),
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

    # Contrefactuels : forcer chaque affectation non-optimale
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
                s2, st2 = _solve_with_workers(m2)
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
                    new_status=_status_name(st2),
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
        status=_status_name(status),
        objective_value=float(total_cost),
        objective_direction="minimize",
        variables={"assignment": assignment, "total_cost": total_cost},
        constraint_analyses=constraint_analyses,
        sensitivity=[],
        counterfactuals=counterfactuals[:6],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Bin Packing
# ---------------------------------------------------------------------------

def _solve_bin_packing(params: dict, _depth: int = 0) -> SolverOutput:
    items = params["items"]
    bin_capacity = params["bin_capacity"]
    n = len(items)
    sizes = [it["size"] for it in items]
    item_names = [it["name"] for it in items]
    max_bins = n  # borne sup triviale

    model = cp_model.CpModel()
    # bin_used[b] : bin b est utilise
    bin_used = [model.NewBoolVar(f"bin_{b}") for b in range(max_bins)]
    # assign[i][b] : item i est dans bin b
    assign = [[model.NewBoolVar(f"assign_{i}_{b}") for b in range(max_bins)] for i in range(n)]

    # Chaque item dans exactement un bin
    for i in range(n):
        model.Add(sum(assign[i][b] for b in range(max_bins)) == 1)

    # Capacite de chaque bin
    for b in range(max_bins):
        model.Add(sum(sizes[i] * assign[i][b] for i in range(n)) <= bin_capacity * bin_used[b])

    # Symetrie : bin b+1 ne peut etre utilise que si bin b l'est
    for b in range(max_bins - 1):
        model.Add(bin_used[b] >= bin_used[b + 1])

    model.Minimize(sum(bin_used))

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="bin_packing", problem_type="bin_packing",
            parameters=params, status=_status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    n_bins = int(solver.ObjectiveValue())
    bin_contents: dict[int, list] = {}
    for b in range(max_bins):
        if solver.Value(bin_used[b]):
            bin_contents[b] = [item_names[i] for i in range(n) if solver.Value(assign[i][b])]

    constraint_analyses = []
    for b, contents in bin_contents.items():
        load = sum(sizes[i] for i in range(n) if solver.Value(assign[i][b]))
        slack = bin_capacity - load
        constraint_analyses.append(ConstraintAnalysis(
            name=f"bin_{b}_capacity",
            description=f"Capacité du bac {b} : charge {load}/{bin_capacity}",
            formula=f"sum(sizes in bin {b}) = {load} ≤ {bin_capacity}",
            lhs_value=float(load),
            rhs_value=float(bin_capacity),
            slack=float(slack),
            is_binding=(slack == 0),
        ))

    # Borne inferieure theorique
    total_size = sum(sizes)
    lb = -(-total_size // bin_capacity)  # ceil division
    sensitivity = []
    if _depth == 0 and bin_capacity < total_size:
        new_cap = bin_capacity + 2
        res2 = _solve_bin_packing({**params, "bin_capacity": new_cap}, _depth=1)
        if res2.objective_value is not None:
            improvement = n_bins - int(res2.objective_value)
            sensitivity.append(SensitivityEntry(
                constraint_name="bin_capacity",
                relaxation_amount=2.0,
                original_objective=float(n_bins),
                new_objective=res2.objective_value,
                improvement=float(improvement),
                description=f"Capacite +2 ({new_cap}) → {int(res2.objective_value)} bacs (-{improvement})",
            ))

    notes = [
        f"Nombre optimal de bacs : {n_bins}.",
        f"Borne inférieure théorique (ceil(total_size/capacity)) = {lb}.",
        f"Taille totale des objets : {total_size} / (capacité {bin_capacity} × {n_bins} bacs = {bin_capacity * n_bins}).",
    ]

    return SolverOutput(
        problem_name="bin_packing",
        problem_type="bin_packing",
        parameters=params,
        status=_status_name(status),
        objective_value=float(n_bins),
        objective_direction="minimize",
        variables={
            "n_bins": n_bins,
            "bin_contents": {str(b): c for b, c in bin_contents.items()},
            "theoretical_lower_bound": lb,
            "total_size": total_size,
            "bin_capacity": bin_capacity,
        },
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Nurse Scheduling
# ---------------------------------------------------------------------------

def _solve_nurse_scheduling(params: dict) -> SolverOutput:
    nurses = params["nurses"]
    n_days = params["n_days"]
    n_shifts = params["shifts_per_day"]
    min_nurses = params["min_nurses_per_shift"]
    max_shifts = params["max_shifts_per_nurse"]
    shift_names = params.get("shift_names", [str(s) for s in range(n_shifts)])
    nn, nd, ns = len(nurses), n_days, n_shifts

    model = cp_model.CpModel()
    # shift_assigned[n][d][s] = 1 si infirmier n travaille le jour d, shift s
    sa = [[[model.NewBoolVar(f"sa_{n}_{d}_{s}") for s in range(ns)]
           for d in range(nd)] for n in range(nn)]

    # Au moins min_nurses par shift
    for d in range(nd):
        for s in range(ns):
            model.Add(sum(sa[n][d][s] for n in range(nn)) >= min_nurses)

    # Au plus 1 shift par infirmier par jour
    for n in range(nn):
        for d in range(nd):
            model.Add(sum(sa[n][d][s] for s in range(ns)) <= 1)

    # Chaque infirmier travaille au plus max_shifts shifts au total
    for n in range(nn):
        model.Add(sum(sa[n][d][s] for d in range(nd) for s in range(ns)) <= max_shifts)

    # Objectif : maximiser la couverture (total shifts couverts)
    total_covered = model.NewIntVar(0, nn * nd * ns, "total_covered")
    model.Add(total_covered == sum(
        sa[n][d][s] for n in range(nn) for d in range(nd) for s in range(ns)
    ))
    model.Maximize(total_covered)

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="nurse_scheduling", problem_type="nurse_scheduling",
            parameters=params, status=_status_name(status),
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

    # Coverage par shift
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

    # Sensibilite : relacher max_shifts de +1
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
    s2, st2 = _solve_with_workers(m2)
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
        status=_status_name(status),
        objective_value=float(total_val),
        objective_direction="maximize",
        variables={"schedule": schedule, "shifts_per_nurse": dict(zip(nurses, shifts_per_nurse))},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Graph Coloring
# ---------------------------------------------------------------------------

def _solve_graph_coloring(params: dict) -> SolverOutput:
    n_nodes = params["n_nodes"]
    node_names = params.get("node_names", [str(i) for i in range(n_nodes)])
    edges = params["edges"]
    max_colors = params["max_colors"]

    model = cp_model.CpModel()
    colors = [model.NewIntVar(0, max_colors - 1, f"color_{i}") for i in range(n_nodes)]

    for u, v in edges:
        model.Add(colors[u] != colors[v])

    # Minimiser le nombre de couleurs utilisees
    n_colors_used = model.NewIntVar(1, max_colors, "n_colors_used")
    model.AddMaxEquality(n_colors_used, colors)
    # n_colors_used = max(colors) + 1 avec une variable auxiliaire
    max_color_idx = model.NewIntVar(0, max_colors - 1, "max_color_idx")
    model.AddMaxEquality(max_color_idx, colors)
    actual_colors = model.NewIntVar(1, max_colors, "actual_colors")
    model.Add(actual_colors == max_color_idx + 1)
    model.Minimize(actual_colors)

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="graph_coloring", problem_type="graph_coloring",
            parameters=params, status=_status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable avec ce nombre de couleurs."],
        )

    color_vals = [solver.Value(colors[i]) for i in range(n_nodes)]
    n_used = solver.Value(actual_colors)
    coloring = {node_names[i]: color_vals[i] for i in range(n_nodes)}

    # Contraintes actives : toutes les aretes avec couleurs differentes (binding par definition)
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

    # Sensibilite : impact si on ajoute une arete
    sensitivity = []
    # Contrefactuels : forcer deux noeuds adjacents a meme couleur (infaisable) ou tester n+1 couleurs
    counterfactuals = []
    # Forcer coloration avec n_used-1 couleurs si possible
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
        s2, st2 = _solve_with_workers(m2)
        if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            new_colors = solver.Value(ac2) if hasattr(s2, 'Value') else n_used - 1
            counterfactuals.append(CounterfactualEntry(
                description=f"Colorier avec {n_used - 1} couleurs",
                forced_change=f"max_colors={n_used - 1}",
                new_status=_status_name(st2),
                new_objective=float(s2.ObjectiveValue()),
                delta=float(s2.ObjectiveValue() - n_used),
                explanation=f"Avec {n_used - 1} couleurs : {_status_name(st2)}.",
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
        status=_status_name(status),
        objective_value=float(n_used),
        objective_direction="minimize",
        variables={"coloring": coloring, "n_colors_used": n_used},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=counterfactuals,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# N-Queens
# ---------------------------------------------------------------------------

def _solve_n_queens(params: dict) -> SolverOutput:
    n = params["n"]

    model = cp_model.CpModel()
    queens = [model.NewIntVar(0, n - 1, f"q_{i}") for i in range(n)]

    # Toutes colonnes differentes (reines sur des colonnes distinctes)
    model.AddAllDifferent(queens)

    # Diagonales : q[i] - q[j] != i - j et q[i] - q[j] != j - i
    for i in range(n):
        for j in range(i + 1, n):
            diff = abs(i - j)
            model.Add(queens[i] - queens[j] != diff)
            model.Add(queens[j] - queens[i] != diff)

    # Juste trouver une solution
    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="n_queens", problem_type="n_queens",
            parameters=params, status=_status_name(status),
            objective_value=None, objective_direction=None,
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Aucune solution (n trop petit)."],
        )

    queen_cols = [solver.Value(queens[i]) for i in range(n)]
    placement = {f"row_{i}": queen_cols[i] for i in range(n)}

    # Analyser les contraintes diagonales les plus "serrées"
    constraint_analyses = []
    # AllDifferent sur les colonnes
    constraint_analyses.append(ConstraintAnalysis(
        name="all_different_columns",
        description=f"Toutes les {n} reines sur des colonnes différentes",
        formula=f"AllDifferent(queens) = {sorted(queen_cols)}",
        lhs_value=float(len(set(queen_cols))),
        rhs_value=float(n),
        slack=0.0,
        is_binding=True,
    ))

    # Contraintes diagonales actives (paires proches)
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
        description=f"Aucune reine ne s'attaque en diagonale",
        formula=f"|col[i]-col[j]| ≠ |row[i]-row[j]| pour tout i≠j",
        lhs_value=float(min_diag_gap) if min_diag_gap is not None else None,
        rhs_value=1.0,
        slack=float(min_diag_gap - 1) if min_diag_gap is not None else None,
        is_binding=(min_diag_gap == 1) if min_diag_gap is not None else False,
    ))

    # Contrefactuels : forcer une reine specifique sur une ligne/colonne
    counterfactuals = []
    if n >= 4:
        # Forcer la reine de la ligne 0 a la colonne 0
        m2 = cp_model.CpModel()
        q2 = [m2.NewIntVar(0, n - 1, f"q_{i}") for i in range(n)]
        m2.AddAllDifferent(q2)
        for i in range(n):
            for j in range(i + 1, n):
                d2 = abs(i - j)
                m2.Add(q2[i] - q2[j] != d2)
                m2.Add(q2[j] - q2[i] != d2)
        m2.Add(q2[0] == 0)
        s2, st2 = _solve_with_workers(m2)
        status_str = _status_name(st2)
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
        status=_status_name(status),
        objective_value=float(n),
        objective_direction=None,
        variables={"placement": placement, "queen_cols": queen_cols},
        constraint_analyses=constraint_analyses,
        sensitivity=[],
        counterfactuals=counterfactuals,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Production Planning
# ---------------------------------------------------------------------------

def _solve_production_planning(params: dict) -> SolverOutput:
    products = params["products"]
    resources = params["resources"]
    max_units = params.get("max_units_per_product", 10)
    n = len(products)
    resource_keys = list(resources.keys())

    model = cp_model.CpModel()
    qty = [model.NewIntVar(0, max_units, f"qty_{i}") for i in range(n)]

    for rk in resource_keys:
        usage = [p[rk] for p in products]
        model.Add(sum(usage[i] * qty[i] for i in range(n)) <= resources[rk])

    profits = [p["profit"] for p in products]
    model.Maximize(sum(profits[i] * qty[i] for i in range(n)))

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="production_planning", problem_type="production_planning",
            parameters=params, status=_status_name(status),
            objective_value=None, objective_direction="maximize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    total_profit = int(solver.ObjectiveValue())
    qty_vals = [solver.Value(qty[i]) for i in range(n)]
    production = {products[i]["name"]: qty_vals[i] for i in range(n)}

    constraint_analyses = []
    for rk in resource_keys:
        usage = [p[rk] for p in products]
        used = sum(usage[i] * qty_vals[i] for i in range(n))
        cap = resources[rk]
        slack = cap - used
        constraint_analyses.append(ConstraintAnalysis(
            name=f"resource_{rk}",
            description=f"Ressource {rk} : {used}/{cap}",
            formula=f"sum({rk}_usage × qty) = {used} ≤ {cap}",
            lhs_value=float(used),
            rhs_value=float(cap),
            slack=float(slack),
            is_binding=(slack == 0),
        ))

    # Sensibilite : relacher chaque ressource contraignante de 10%
    sensitivity = []
    for rk in resource_keys:
        delta = max(1, resources[rk] // 10)
        m2 = cp_model.CpModel()
        q2 = [m2.NewIntVar(0, max_units, f"q_{i}") for i in range(n)]
        for rk2 in resource_keys:
            usage2 = [p[rk2] for p in products]
            cap2 = resources[rk2] + (delta if rk2 == rk else 0)
            m2.Add(sum(usage2[i] * q2[i] for i in range(n)) <= cap2)
        m2.Maximize(sum(profits[i] * q2[i] for i in range(n)))
        s2, st2 = _solve_with_workers(m2)
        if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            new_profit = int(s2.ObjectiveValue())
            improvement = new_profit - total_profit
            sensitivity.append(SensitivityEntry(
                constraint_name=f"resource_{rk}",
                relaxation_amount=float(delta),
                original_objective=float(total_profit),
                new_objective=float(new_profit),
                improvement=float(improvement),
                description=f"{rk} +{delta} → profit {new_profit} (+{improvement})",
            ))

    # Contrefactuels : forcer production minimale de chaque produit a 1
    counterfactuals = []
    for i in range(n):
        if qty_vals[i] == 0:
            m3 = cp_model.CpModel()
            q3 = [m3.NewIntVar(0, max_units, f"q_{j}") for j in range(n)]
            for rk in resource_keys:
                usage3 = [p[rk] for p in products]
                m3.Add(sum(usage3[j] * q3[j] for j in range(n)) <= resources[rk])
            m3.Add(q3[i] >= 1)
            m3.Maximize(sum(profits[j] * q3[j] for j in range(n)))
            s3, st3 = _solve_with_workers(m3)
            if st3 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_p = int(s3.ObjectiveValue())
                delta3 = new_p - total_profit
                expl = (f"Forcer au moins 1 '{products[i]['name']}' → profit {new_p} "
                        f"({delta3:+d}).")
            else:
                new_p = None
                delta3 = None
                expl = f"Produire '{products[i]['name']}' est infaisable avec les ressources."
            counterfactuals.append(CounterfactualEntry(
                description=f"Forcer production de '{products[i]['name']}'",
                forced_change=f"qty[{i}]>=1",
                new_status=_status_name(st3),
                new_objective=float(new_p) if new_p is not None else None,
                delta=float(delta3) if delta3 is not None else None,
                explanation=expl,
            ))

    notes = [
        f"Profit total optimal : {total_profit}.",
        f"Plan : {', '.join(f'{k}={v}' for k, v in production.items() if v > 0)}.",
    ]

    return SolverOutput(
        problem_name="production_planning",
        problem_type="production_planning",
        parameters=params,
        status=_status_name(status),
        objective_value=float(total_profit),
        objective_direction="maximize",
        variables={"production": production, "total_profit": total_profit},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=counterfactuals,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# TSP (Traveling Salesman Problem)
# ---------------------------------------------------------------------------

def _solve_tsp(params: dict) -> SolverOutput:
    cities = params["cities"]
    distances = params["distances"]
    n = len(cities)

    model = cp_model.CpModel()
    # next_city[i] = ville suivante apres la ville i
    nxt = [model.NewIntVar(0, n - 1, f"next_{i}") for i in range(n)]

    # Circuit hamiltonien via AddCircuit
    arcs = []
    for i in range(n):
        for j in range(n):
            if i != j:
                arc_lit = model.NewBoolVar(f"arc_{i}_{j}")
                arcs.append((i, j, arc_lit))
    model.AddCircuit(arcs)

    # Lier next[i] aux arc_lit
    arc_map: dict[tuple, object] = {}
    for i, j, lit in arcs:
        arc_map[(i, j)] = lit

    # Distance totale (arrondie a des entiers)
    total_dist = model.NewIntVar(0, sum(max(row) for row in distances) * n, "total_dist")
    model.Add(total_dist == sum(
        distances[i][j] * arc_map[(i, j)]
        for i in range(n) for j in range(n) if i != j
    ))
    model.Minimize(total_dist)

    solver, status = _solve_with_workers(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverOutput(
            problem_name="tsp", problem_type="tsp",
            parameters=params, status=_status_name(status),
            objective_value=None, objective_direction="minimize",
            variables={}, constraint_analyses=[], sensitivity=[],
            counterfactuals=[], notes=["Infaisable."],
        )

    total_dist_val = int(solver.ObjectiveValue())

    # Reconstruire le tour
    nxt_vals = {i: j for i, j, lit in arcs if solver.Value(lit)}
    tour = [0]
    while len(tour) < n:
        tour.append(nxt_vals[tour[-1]])
    tour_names = [cities[i] for i in tour] + [cities[0]]

    constraint_analyses = []
    # Analyser chaque arc utilise
    used_arcs = [(i, j) for i, j, lit in arcs if solver.Value(lit)]
    # Arcs les plus courts et plus longs
    arc_distances = [(distances[i][j], i, j) for i, j in used_arcs]
    arc_distances.sort()
    if arc_distances:
        min_d, mi, mj = arc_distances[0]
        max_d, xi, xj = arc_distances[-1]
        constraint_analyses.append(ConstraintAnalysis(
            name="circuit_constraint",
            description=f"Circuit hamiltonien : {n} villes, toutes visitées exactement une fois",
            formula=f"AddCircuit({n} villes) = {total_dist_val} km",
            lhs_value=float(total_dist_val),
            rhs_value=float(total_dist_val),
            slack=0.0,
            is_binding=True,
        ))
        constraint_analyses.append(ConstraintAnalysis(
            name="longest_arc",
            description=f"Arc le plus long : {cities[xi]}→{cities[xj]} = {max_d} km",
            formula=f"dist({cities[xi]},{cities[xj]}) = {max_d}",
            lhs_value=float(max_d),
            rhs_value=float(max_d),
            slack=0.0,
            is_binding=True,
        ))

    # Sensibilite : retirer l'arc le plus long (forcer a ne pas l'utiliser)
    sensitivity = []
    if arc_distances and len(arc_distances) > 1:
        max_d, xi, xj = arc_distances[-1]
        m2 = cp_model.CpModel()
        arcs2 = []
        arc_map2: dict[tuple, object] = {}
        for i in range(n):
            for j in range(n):
                if i != j and not (i == xi and j == xj):
                    lit2 = m2.NewBoolVar(f"arc_{i}_{j}")
                    arcs2.append((i, j, lit2))
                    arc_map2[(i, j)] = lit2
        if arcs2:
            m2.AddCircuit(arcs2)
            td2 = m2.NewIntVar(0, sum(max(row) for row in distances) * n, "td2")
            m2.Add(td2 == sum(
                distances[i][j] * arc_map2[(i, j)]
                for i, j in arc_map2
            ))
            m2.Minimize(td2)
            s2, st2 = _solve_with_workers(m2)
            if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                new_dist = int(s2.ObjectiveValue())
                improvement = new_dist - total_dist_val
                sensitivity.append(SensitivityEntry(
                    constraint_name=f"arc_{cities[xi]}_{cities[xj]}",
                    relaxation_amount=float(max_d),
                    original_objective=float(total_dist_val),
                    new_objective=float(new_dist),
                    improvement=float(improvement),
                    description=(f"Sans l'arc {cities[xi]}→{cities[xj]} ({max_d}km) "
                                 f"→ distance {new_dist} km ({improvement:+d})"),
                ))

    notes = [
        f"Distance optimale : {total_dist_val} km.",
        f"Tour : {' → '.join(tour_names)}.",
    ]

    return SolverOutput(
        problem_name="tsp",
        problem_type="tsp",
        parameters=params,
        status=_status_name(status),
        objective_value=float(total_dist_val),
        objective_direction="minimize",
        variables={"tour": tour_names, "tour_indices": tour + [0], "total_distance": total_dist_val},
        constraint_analyses=constraint_analyses,
        sensitivity=sensitivity,
        counterfactuals=[],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

SOLVERS = {
    "knapsack": _solve_knapsack,
    "diet": _solve_diet,
    "job_shop": _solve_job_shop,
    "assignment": _solve_assignment,
    "bin_packing": _solve_bin_packing,
    "nurse_scheduling": _solve_nurse_scheduling,
    "graph_coloring": _solve_graph_coloring,
    "n_queens": _solve_n_queens,
    "production_planning": _solve_production_planning,
    "tsp": _solve_tsp,
}


def solve(problem_type: str, params: dict) -> SolverOutput:
    """Resoudre un probleme CP-SAT et retourner une analyse complete."""
    fn = SOLVERS.get(problem_type)
    if fn is None:
        raise ValueError(f"Type de probleme inconnu : {problem_type!r}. "
                         f"Disponibles : {list(SOLVERS)}")
    return fn(params)
