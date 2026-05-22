from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import heapq
import time
from typing import Dict, List, Tuple

import pandas as pd

from .domain import OrbitalInstance
from .solver_cp_sat import SolveResult
from .validation import validate_schedule


def _topological_order(instance: OrbitalInstance) -> List[int]:
    n = len(instance.maneuvers)
    indeg = [0] * n
    graph = defaultdict(list)
    for edge in instance.precedences:
        graph[edge.pred].append(edge.succ)
        indeg[edge.succ] += 1

    # Launch-window-prioritized Kahn traversal:
    # among available tasks, schedule the tightest/earliest windows first.
    q = []
    for i in range(n):
        if indeg[i] == 0:
            m = instance.maneuvers[i]
            latest_start = m.latest_end - m.min_duration
            heapq.heappush(q, (latest_start, m.latest_end, m.earliest_start, i))

    order = []
    while q:
        _, _, _, u = heapq.heappop(q)
        order.append(u)
        for v in graph[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                m = instance.maneuvers[v]
                latest_start = m.latest_end - m.min_duration
                heapq.heappush(q, (latest_start, m.latest_end, m.earliest_start, v))
    if len(order) != n:
        raise ValueError("precedence graph has a cycle")
    return order


def _candidate_ok_with_safety(
    i: int,
    start: int,
    end: int,
    scheduled: Dict[int, Dict[str, int]],
    instance: OrbitalInstance,
) -> bool:
    for c in instance.safety_conflicts:
        j = None
        sep = c.separation
        if c.left == i:
            j = c.right
        elif c.right == i:
            j = c.left
        if j is None or j not in scheduled:
            continue
        sj = scheduled[j]["start"]
        ej = scheduled[j]["end"]
        left_before = end + sep <= sj
        right_before = ej + sep <= start
        if not (left_before or right_before):
            return False
    return True


def _candidate_ok_with_lane(
    lane: int,
    start: int,
    end: int,
    scheduled: Dict[int, Dict[str, int]],
    instance: OrbitalInstance,
) -> bool:
    for j, row in scheduled.items():
        mj = instance.maneuvers[j]
        if mj.lane != lane:
            continue
        if not (end <= row["start"] or row["end"] <= start):
            return False
    return True


def _candidate_ok_with_capacity(
    start: int,
    end: int,
    dv: int,
    usage: Dict[int, int],
    capacity: int,
) -> bool:
    for t in range(start, end):
        if usage.get(t, 0) + dv > capacity:
            return False
    return True


def solve_greedy(instance: OrbitalInstance) -> SolveResult:
    t0 = time.perf_counter()
    n = len(instance.maneuvers)
    order = _topological_order(instance)

    preds = defaultdict(list)
    for e in instance.precedences:
        preds[e.succ].append((e.pred, e.lag))

    min_dv = {i: min(instance.maneuvers[i].dv_fast, instance.maneuvers[i].dv_eco) for i in range(n)}
    min_remaining_after = {}
    suffix = 0
    for i in reversed(order):
        min_remaining_after[i] = suffix
        suffix += min_dv[i]

    scheduled: Dict[int, Dict[str, int | str]] = {}
    usage: Dict[int, int] = defaultdict(int)
    used_fuel = 0

    for i in order:
        m = instance.maneuvers[i]

        est = m.earliest_start
        if i in preds:
            est = max(est, max(int(scheduled[p]["end"]) + lag for p, lag in preds[i]))

        profiles = [
            ("fast", m.duration_fast, m.dv_fast),
            ("eco", m.duration_eco, m.dv_eco),
        ]
        # Fast first (smaller makespan), eco used when fuel/capacity/window blocks fast.
        profiles.sort(key=lambda x: x[1])

        best = None
        for mode, duration, dv in profiles:
            latest_start = m.latest_end - duration
            if est > latest_start:
                continue

            # Keep enough fuel for remaining tasks minimal profile.
            if used_fuel + dv + min_remaining_after[i] > instance.total_fuel_budget:
                continue

            for t in range(est, latest_start + 1):
                start = t
                end = t + duration
                if not _candidate_ok_with_lane(m.lane, start, end, scheduled, instance):
                    continue
                if not _candidate_ok_with_safety(i, start, end, scheduled, instance):
                    continue
                if not _candidate_ok_with_capacity(start, end, dv, usage, instance.concurrent_dv_capacity):
                    continue

                best = {
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
                    "mode": mode,
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "delta_v": dv,
                    "window_open": m.earliest_start,
                    "window_close": m.latest_end,
                }
                break

            if best is not None:
                break

        if best is None:
            return SolveResult(
                solver_name="greedy",
                status="INFEASIBLE",
                feasible=False,
                objective=None,
                makespan=None,
                total_fuel=None,
                wall_time_s=time.perf_counter() - t0,
                schedule=None,
                metadata={
                    "failed_on_idx": i,
                    "failed_maneuver": m.name,
                    "priority_rule": "topological + earliest latest_start launch window",
                },
            )

        scheduled[i] = best
        used_fuel += int(best["delta_v"])
        for t in range(int(best["start"]), int(best["end"])):
            usage[t] += int(best["delta_v"])

    schedule = pd.DataFrame(scheduled.values()).sort_values(["start", "idx"]).reset_index(drop=True)
    check = validate_schedule(instance, schedule)
    feasible = bool(check["feasible"])
    makespan = int(schedule["end"].max())
    total_fuel = int(schedule["delta_v"].sum())
    lexico_weight = instance.total_fuel_budget + 1
    objective = makespan * lexico_weight + total_fuel

    return SolveResult(
        solver_name="greedy",
        status="FEASIBLE" if feasible else "INVALID",
        feasible=feasible,
        objective=objective if feasible else None,
        makespan=makespan if feasible else None,
        total_fuel=total_fuel if feasible else None,
        wall_time_s=time.perf_counter() - t0,
        schedule=schedule if feasible else None,
        metadata={
            "violations": check["violations"],
            "priority_rule": "topological + earliest latest_start launch window",
        },
    )
