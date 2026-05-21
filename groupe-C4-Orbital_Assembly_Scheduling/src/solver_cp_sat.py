from __future__ import annotations

from dataclasses import dataclass
import time
from collections import defaultdict
from typing import Any, Dict, List

import pandas as pd
from ortools.sat.python import cp_model

from .domain import OrbitalInstance


@dataclass
class SolveResult:
    solver_name: str
    status: str
    feasible: bool
    objective: int | None
    makespan: int | None
    total_fuel: int | None
    wall_time_s: float
    schedule: pd.DataFrame | None
    metadata: Dict[str, Any]


def solve_cpsat(
    instance: OrbitalInstance,
    time_limit_s: float = 20.0,
    workers: int = 8,
    seed: int = 0,
) -> SolveResult:
    ok, msg = instance.validate()
    if not ok:
        raise ValueError(f"Invalid instance: {msg}")

    model = cp_model.CpModel()
    n = len(instance.maneuvers)

    starts = {}
    ends = {}
    durations = {}
    dvs = {}
    use_fast = {}
    intervals = {}

    lane_intervals: Dict[int, List[cp_model.IntervalVar]] = defaultdict(list)

    for i, m in enumerate(instance.maneuvers):
        start_lb = m.earliest_start
        start_ub = m.latest_end - m.min_duration
        if start_lb > start_ub:
            return SolveResult(
                solver_name="cp-sat",
                status="INFEASIBLE_WINDOWS",
                feasible=False,
                objective=None,
                makespan=None,
                total_fuel=None,
                wall_time_s=0.0,
                schedule=None,
                metadata={"reason": f"empty window for {m.name}"},
            )

        starts[i] = model.NewIntVar(start_lb, start_ub, f"start_{i}")
        ends[i] = model.NewIntVar(start_lb + m.min_duration, m.latest_end, f"end_{i}")
        durations[i] = model.NewIntVar(m.min_duration, m.max_duration, f"dur_{i}")
        dvs[i] = model.NewIntVar(min(m.dv_fast, m.dv_eco), max(m.dv_fast, m.dv_eco), f"dv_{i}")
        use_fast[i] = model.NewBoolVar(f"use_fast_{i}")

        model.Add(durations[i] == m.duration_fast).OnlyEnforceIf(use_fast[i])
        model.Add(durations[i] == m.duration_eco).OnlyEnforceIf(use_fast[i].Not())
        model.Add(dvs[i] == m.dv_fast).OnlyEnforceIf(use_fast[i])
        model.Add(dvs[i] == m.dv_eco).OnlyEnforceIf(use_fast[i].Not())

        intervals[i] = model.NewIntervalVar(starts[i], durations[i], ends[i], f"itv_{i}")
        lane_intervals[m.lane].append(intervals[i])

    for lane, itvs in lane_intervals.items():
        if len(itvs) >= 2:
            model.AddNoOverlap(itvs)

    for edge in instance.precedences:
        model.Add(ends[edge.pred] + edge.lag <= starts[edge.succ])

    for c in instance.safety_conflicts:
        left_before = model.NewBoolVar(f"sep_{c.left}_{c.right}")
        model.Add(ends[c.left] + c.separation <= starts[c.right]).OnlyEnforceIf(left_before)
        model.Add(ends[c.right] + c.separation <= starts[c.left]).OnlyEnforceIf(left_before.Not())

    total_fuel = model.NewIntVar(0, instance.total_fuel_budget, "total_fuel")
    model.Add(total_fuel == sum(dvs[i] for i in range(n)))
    model.Add(total_fuel <= instance.total_fuel_budget)

    model.AddCumulative(
        [intervals[i] for i in range(n)],
        [dvs[i] for i in range(n)],
        instance.concurrent_dv_capacity,
    )

    makespan = model.NewIntVar(0, instance.horizon, "makespan")
    model.AddMaxEquality(makespan, [ends[i] for i in range(n)])

    lexico_weight = instance.total_fuel_budget + 1
    objective = model.NewIntVar(0, instance.horizon * lexico_weight + instance.total_fuel_budget, "objective")
    model.Add(objective == makespan * lexico_weight + total_fuel)
    model.Minimize(objective)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    status_name = solver.StatusName(status)

    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not feasible:
        return SolveResult(
            solver_name="cp-sat",
            status=status_name,
            feasible=False,
            objective=None,
            makespan=None,
            total_fuel=None,
            wall_time_s=elapsed,
            schedule=None,
            metadata={"best_objective_bound": solver.BestObjectiveBound()},
        )

    rows = []
    for i, m in enumerate(instance.maneuvers):
        is_fast = solver.Value(use_fast[i]) == 1
        rows.append(
            {
                "idx": i,
                "name": m.name,
                "module": m.module,
                "phase": m.phase,
                "mission_regime": m.mission_regime,
                "lane": m.lane,
                "orbit_from_km": m.orbit_from_km,
                "orbit_to_km": m.orbit_to_km,
                "base_delta_v_mps": m.base_delta_v_mps,
                "base_time_s": m.base_time_s,
                "mode": "fast" if is_fast else "eco",
                "start": solver.Value(starts[i]),
                "end": solver.Value(ends[i]),
                "duration": solver.Value(durations[i]),
                "delta_v": solver.Value(dvs[i]),
                "window_open": m.earliest_start,
                "window_close": m.latest_end,
            }
        )

    schedule = pd.DataFrame(rows).sort_values(["start", "idx"]).reset_index(drop=True)
    return SolveResult(
        solver_name="cp-sat",
        status=status_name,
        feasible=True,
        objective=int(solver.Value(objective)),
        makespan=int(solver.Value(makespan)),
        total_fuel=int(solver.Value(total_fuel)),
        wall_time_s=elapsed,
        schedule=schedule,
        metadata={
            "num_conflicts": solver.NumConflicts(),
            "num_branches": solver.NumBranches(),
            "best_objective_bound": solver.BestObjectiveBound(),
        },
    )
