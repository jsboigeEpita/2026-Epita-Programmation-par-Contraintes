import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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


def _compute_metrics(
    data: ProblemData,
    assignment: Dict[int, Dict[int, int]],
    committee_sizes: Dict[Tuple[int, int], int],
    loads: Dict[int, int],
) -> Dict[str, int]:
    imbalance = max(loads.values()) - min(loads.values()) if loads else 0

    anti_affinity = 0
    validators = list(range(data.num_validators))
    committees = list(range(data.num_committees))
    times = list(range(data.time_steps))
    operators = sorted(set(data.operators))
    for o in operators:
        for c in committees:
            for t in times:
                count = 0
                for v in validators:
                    if assignment.get(t, {}).get(v) == c and data.operators[v] == o:
                        count += 1
                if count > 0:
                    anti_affinity += max(0, count - 1)

    churn = 0
    active_by_time = _active_sets(data)
    for v in validators:
        for t in range(1, data.time_steps):
            if active_by_time[t] is not None:
                if v not in active_by_time[t] or v not in active_by_time[t - 1]:
                    continue
            prev_c = assignment.get(t - 1, {}).get(v)
            cur_c = assignment.get(t, {}).get(v)
            if prev_c is not None and cur_c is not None and prev_c != cur_c:
                churn += 1

    size_deviation = 0
    if data.target_size is not None:
        for (c, t), size in committee_sizes.items():
            size_deviation += abs(size - data.target_size)

    return {
        "imbalance": imbalance,
        "anti_affinity": anti_affinity,
        "churn": churn,
        "size_deviation": size_deviation,
    }


def solve_rng(
    data: ProblemData,
    weights: Optional[Dict[str, int]] = None,
    seed: Optional[int] = None,
) -> Solution:
    """Build a random baseline assignment with soft repair for size bounds."""
    if len(data.operators) != data.num_validators:
        raise ValueError("operators length must match num_validators")

    rng = random.Random(seed)
    validators = list(range(data.num_validators))
    committees = list(range(data.num_committees))
    times = list(range(data.time_steps))
    active_by_time = _active_sets(data)

    assignment: Dict[int, Dict[int, int]] = {t: {} for t in times}
    committee_sizes: Dict[Tuple[int, int], int] = {}

    for t in times:
        active = validators
        if active_by_time[t] is not None:
            active = [v for v in validators if v in active_by_time[t]]

        total = len(active)
        if total < data.min_size * data.num_committees:
            raise ValueError("Not enough active validators for min_size constraints")
        if total > data.max_size * data.num_committees:
            raise ValueError("Too many active validators for max_size constraints")

        sizes = [data.min_size for _ in committees]
        remainder = total - data.min_size * data.num_committees
        idx = 0
        while remainder > 0:
            if sizes[idx] < data.max_size:
                sizes[idx] += 1
                remainder -= 1
            idx = (idx + 1) % data.num_committees

        rng.shuffle(active)
        start = 0
        for c, size in zip(committees, sizes):
            group = active[start : start + size]
            for v in group:
                assignment[t][v] = c
            committee_sizes[(c, t)] = size
            start += size

    loads: Dict[int, int] = {}
    for v in validators:
        loads[v] = sum(1 for t in times if v in assignment[t])

    metrics = _compute_metrics(data, assignment, committee_sizes, loads)
    if weights is None:
        weights = DEFAULT_WEIGHTS
    objective = (
        metrics["imbalance"] * weights.get("imbalance", 0)
        + metrics["anti_affinity"] * weights.get("anti_affinity", 0)
        + metrics["churn"] * weights.get("churn", 0)
        + metrics["size_deviation"] * weights.get("size_deviation", 0)
    )

    return Solution(
        status=cp_model.FEASIBLE,
        objective=float(objective),
        assignment=assignment,
        loads=loads,
        committee_sizes=committee_sizes,
        metrics=metrics,
        problem_data=data,
    )
