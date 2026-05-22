from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import time

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

from solver import ProblemData, Solution

DEFAULT_WEIGHTS = {
    "imbalance": 100,
    "anti_affinity": 10,
    "churn": 1,
    "size_deviation": 1,
}


def _active_sets(data: ProblemData) -> List[Optional[set]]:
    if data.active_by_time is None:
        return [None for _ in range(data.time_steps)]
    if len(data.active_by_time) != data.time_steps:
        raise ValueError("active_by_time must match time_steps")
    return [set(items) for items in data.active_by_time]


def solve_milp(
    data: ProblemData,
    weights: Optional[Dict[str, int]] = None,
    time_limit_s: float = 10.0,
) -> Solution:
    """Solve the MILP (PLNE) formulation using CBC."""
    if len(data.operators) != data.num_validators:
        raise ValueError("operators length must match num_validators")

    if weights is None:
        weights = DEFAULT_WEIGHTS

    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise RuntimeError("CBC solver is not available")
    
    before_time = time.time()

    solver.SetTimeLimit(int(time_limit_s * 1000))

    validators = list(range(data.num_validators))
    committees = list(range(data.num_committees))
    times = list(range(data.time_steps))
    active_by_time = _active_sets(data)

    x: Dict[Tuple[int, int, int], pywraplp.Variable] = {}
    for v in validators:
        for c in committees:
            for t in times:
                x[(v, c, t)] = solver.IntVar(0, 1, f"x_v{v}_c{c}_t{t}")

    for v in validators:
        for t in times:
            if active_by_time[t] is not None and v not in active_by_time[t]:
                for c in committees:
                    solver.Add(x[(v, c, t)] == 0)
            else:
                solver.Add(sum(x[(v, c, t)] for c in committees) == 1)

    committee_sizes: Dict[Tuple[int, int], pywraplp.Variable] = {}
    size_deviation: Dict[Tuple[int, int], pywraplp.Variable] = {}
    for c in committees:
        for t in times:
            size_var = solver.IntVar(0, data.num_validators, f"size_c{c}_t{t}")
            solver.Add(size_var == sum(x[(v, c, t)] for v in validators))
            solver.Add(size_var >= data.min_size)
            solver.Add(size_var <= data.max_size)
            committee_sizes[(c, t)] = size_var

            if data.target_size is not None:
                dev = solver.IntVar(0, data.num_validators, f"dev_c{c}_t{t}")
                solver.Add(dev >= size_var - data.target_size)
                solver.Add(dev >= data.target_size - size_var)
                size_deviation[(c, t)] = dev

    loads: Dict[int, pywraplp.Variable] = {}
    for v in validators:
        load = solver.IntVar(0, data.time_steps, f"load_v{v}")
        solver.Add(load == sum(x[(v, c, t)] for c in committees for t in times))
        loads[v] = load

    load_max = solver.IntVar(0, data.time_steps, "load_max")
    load_min = solver.IntVar(0, data.time_steps, "load_min")
    for v in validators:
        solver.Add(load_max >= loads[v])
        solver.Add(load_min <= loads[v])
    imbalance = solver.IntVar(0, data.time_steps, "imbalance")
    solver.Add(imbalance == load_max - load_min)

    operators = sorted(set(data.operators))
    excess_terms: List[pywraplp.Variable] = []
    for o in operators:
        for c in committees:
            for t in times:
                op_validators = [v for v in validators if data.operators[v] == o]
                if not op_validators:
                    continue
                n_op = solver.IntVar(0, len(op_validators), f"n_op{o}_c{c}_t{t}")
                solver.Add(n_op == sum(x[(v, c, t)] for v in op_validators))
                if data.max_per_operator is not None:
                    solver.Add(n_op <= data.max_per_operator)
                excess = solver.IntVar(0, len(op_validators), f"excess_op{o}_c{c}_t{t}")
                solver.Add(excess >= n_op - 1)
                solver.Add(excess >= 0)
                excess_terms.append(excess)

    churn_terms: List[pywraplp.Variable] = []
    if data.time_steps > 1:
        for v in validators:
            for t in times[1:]:
                if active_by_time[t] is not None:
                    if v not in active_by_time[t] or v not in active_by_time[t - 1]:
                        continue
                stayed = solver.IntVar(0, 1, f"stayed_v{v}_t{t}")
                same_bools = []
                for c in committees:
                    same = solver.IntVar(0, 1, f"same_v{v}_c{c}_t{t}")
                    solver.Add(same <= x[(v, c, t)])
                    solver.Add(same <= x[(v, c, t - 1)])
                    solver.Add(same >= x[(v, c, t)] + x[(v, c, t - 1)] - 1)
                    same_bools.append(same)
                solver.Add(stayed == sum(same_bools))
                churn = solver.IntVar(0, 1, f"churn_v{v}_t{t}")
                solver.Add(churn + stayed == 1)
                churn_terms.append(churn)

    objective_terms = []
    if weights.get("imbalance", 0) > 0:
        objective_terms.append(imbalance * weights["imbalance"])

    if weights.get("anti_affinity", 0) > 0 and excess_terms:
        anti_affinity = solver.IntVar(0, len(excess_terms) * data.num_validators, "anti_affinity")
        solver.Add(anti_affinity == sum(excess_terms))
        objective_terms.append(anti_affinity * weights["anti_affinity"])
    else:
        anti_affinity = solver.IntVar(0, 0, "anti_affinity")

    if weights.get("churn", 0) > 0 and churn_terms:
        churn_sum = solver.IntVar(0, len(churn_terms), "churn_sum")
        solver.Add(churn_sum == sum(churn_terms))
        objective_terms.append(churn_sum * weights["churn"])
    else:
        churn_sum = solver.IntVar(0, 0, "churn_sum")

    if weights.get("size_deviation", 0) > 0 and size_deviation:
        dev_sum = solver.IntVar(0, len(size_deviation) * data.num_validators, "size_deviation_sum")
        solver.Add(dev_sum == sum(size_deviation.values()))
        objective_terms.append(dev_sum * weights["size_deviation"])
    else:
        dev_sum = solver.IntVar(0, 0, "size_deviation_sum")

    if objective_terms:
        solver.Minimize(sum(objective_terms))

    print(f"Model built in {time.time() - before_time} seconds.")
    before_time = time.time()
    status = solver.Solve()

    assignment: Dict[int, Dict[int, int]] = {t: {} for t in times}
    loads_out: Dict[int, int] = {}
    committee_sizes_out: Dict[Tuple[int, int], int] = {}

    if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        for v in validators:
            loads_out[v] = int(loads[v].solution_value())

        for (c, t), size_var in committee_sizes.items():
            committee_sizes_out[(c, t)] = int(size_var.solution_value())

        for v in validators:
            for t in times:
                for c in committees:
                    if x[(v, c, t)].solution_value() > 0.5:
                        assignment[t][v] = c
                        break

    print(f"Model solved in {time.time() - before_time} seconds.")
    metrics = {
        "imbalance": int(imbalance.solution_value()) if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else 0,
        "anti_affinity": int(anti_affinity.solution_value()) if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else 0,
        "churn": int(churn_sum.solution_value()) if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else 0,
        "size_deviation": int(dev_sum.solution_value()) if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else 0,
    }

    if status == pywraplp.Solver.OPTIMAL:
        status_out = cp_model.OPTIMAL
    elif status == pywraplp.Solver.FEASIBLE:
        status_out = cp_model.FEASIBLE
    elif status == pywraplp.Solver.INFEASIBLE:
        status_out = cp_model.INFEASIBLE
    else:
        status_out = cp_model.UNKNOWN

    objective_value = solver.Objective().Value() if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else 0.0

    return Solution(
        status=status_out,
        objective=float(objective_value),
        assignment=assignment,
        loads=loads_out,
        committee_sizes=committee_sizes_out,
        metrics=metrics,
        problem_data=data,
    )
