from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

import pandas as pd

from .domain import OrbitalInstance


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end <= b_start or b_end <= a_start)


def validate_schedule(instance: OrbitalInstance, schedule: pd.DataFrame | None) -> Dict[str, object]:
    if schedule is None or schedule.empty:
        return {"feasible": False, "violations": ["schedule is empty"]}

    violations: List[str] = []
    required_cols = {"idx", "start", "end", "duration", "delta_v", "mode", "lane"}
    missing_cols = sorted(required_cols - set(schedule.columns))
    if missing_cols:
        return {"feasible": False, "violations": [f"missing columns: {missing_cols}"]}

    dup_rows = schedule["idx"].duplicated(keep=False)
    if dup_rows.any():
        duplicated = sorted(int(x) for x in schedule.loc[dup_rows, "idx"].unique().tolist())
        violations.append(f"duplicated maneuvers: {duplicated}")

    required = set(range(len(instance.maneuvers)))
    got = set(int(x) for x in schedule["idx"].tolist())
    if got != required:
        missing = sorted(required - got)
        extra = sorted(got - required)
        if missing:
            violations.append(f"missing maneuvers: {missing}")
        if extra:
            violations.append(f"unexpected maneuvers: {extra}")

    by_idx = {}
    for row in schedule.to_dict("records"):
        i = int(row["idx"])
        by_idx[i] = row
        m = instance.maneuvers[i]

        start = int(row["start"])
        end = int(row["end"])
        duration = int(row["duration"])
        dv = int(row["delta_v"])
        mode = str(row["mode"])

        if end - start != duration:
            violations.append(f"duration mismatch for idx={i}")
        if int(row["lane"]) != int(m.lane):
            violations.append(f"lane mismatch for idx={i}")
        if start < m.earliest_start:
            violations.append(f"window start violation for idx={i}")
        if end > m.latest_end:
            violations.append(f"window end violation for idx={i}")
        if mode == "fast":
            if duration != m.duration_fast or dv != m.dv_fast:
                violations.append(f"fast profile mismatch for idx={i}")
        elif mode == "eco":
            if duration != m.duration_eco or dv != m.dv_eco:
                violations.append(f"eco profile mismatch for idx={i}")
        else:
            violations.append(f"unknown mode for idx={i}: {mode}")

    # Lane exclusivity.
    lane_rows = defaultdict(list)
    for row in schedule.to_dict("records"):
        lane_rows[int(row["lane"])].append(row)
    for lane, rows in lane_rows.items():
        rows = sorted(rows, key=lambda r: int(r["start"]))
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if _overlap(int(rows[i]["start"]), int(rows[i]["end"]), int(rows[j]["start"]), int(rows[j]["end"])):
                    violations.append(
                        f"lane overlap lane={lane} idx={rows[i]['idx']} idx={rows[j]['idx']}"
                    )

    # Precedences.
    for edge in instance.precedences:
        if edge.pred not in by_idx or edge.succ not in by_idx:
            continue
        if int(by_idx[edge.pred]["end"]) + edge.lag > int(by_idx[edge.succ]["start"]):
            violations.append(f"precedence violation {edge.pred}->{edge.succ} lag={edge.lag}")

    # Safety conflicts.
    for c in instance.safety_conflicts:
        if c.left not in by_idx or c.right not in by_idx:
            continue
        li = by_idx[c.left]
        ri = by_idx[c.right]
        left_before = int(li["end"]) + c.separation <= int(ri["start"])
        right_before = int(ri["end"]) + c.separation <= int(li["start"])
        if not (left_before or right_before):
            violations.append(f"safety separation violation {c.left}<->{c.right}")

    # Cumulative delta-v capacity and total fuel budget.
    total_fuel = int(schedule["delta_v"].sum())
    if total_fuel > instance.total_fuel_budget:
        violations.append(
            f"fuel budget exceeded: {total_fuel} > {instance.total_fuel_budget}"
        )

    for t in range(instance.horizon):
        usage = 0
        for row in schedule.to_dict("records"):
            if int(row["start"]) <= t < int(row["end"]):
                usage += int(row["delta_v"])
        if usage > instance.concurrent_dv_capacity:
            violations.append(
                f"cumulative capacity violation t={t}: {usage} > {instance.concurrent_dv_capacity}"
            )
            break

    feasible = len(violations) == 0
    return {"feasible": feasible, "violations": violations}


def schedule_stats(schedule: pd.DataFrame | None) -> Dict[str, int | None]:
    if schedule is None or schedule.empty:
        return {"makespan": None, "total_fuel": None}
    makespan = int(schedule["end"].max())
    total_fuel = int(schedule["delta_v"].sum())
    return {"makespan": makespan, "total_fuel": total_fuel}
