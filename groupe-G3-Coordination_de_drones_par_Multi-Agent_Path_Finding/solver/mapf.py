from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from ortools.sat.python import cp_model
from .grid import Grid, Pos
from .astar import astar


@dataclass
class Drone:
    id: int
    start: Pos
    goal: Pos


@dataclass
class Solution:
    status: str
    makespan: int
    flowtime: int
    solve_time_ms: float
    paths: Dict[int, List[Pos]]
    conflicts_avoided: int


class MAPFSolver:
    def __init__(self, grid: Grid, drones: List[Drone], time_limit_s: float = 10.0):
        self.grid = grid
        self.drones = drones
        self.time_limit_s = time_limit_s

    def solve(self) -> Solution:
        positions = self.grid.positions
        pos_to_idx = {p: i for i, p in enumerate(positions)}
        N = len(self.drones)
        P = len(positions)

        t0 = time.time()

        # A* individual paths — horizon + warm-start hints (unchanged)
        astar_paths: List[Optional[List[Pos]]] = [
            astar(self.grid, d.start, d.goal) for d in self.drones
        ]
        astar_lens = [len(p) - 1 for p in astar_paths if p is not None]
        if astar_lens:
            T = max(astar_lens) + max(N - 1, 3)
        else:
            T = 2 * (self.grid.rows + self.grid.cols) + N

        model = cp_model.CpModel()

        # Neighbor index lists (includes self for wait move)
        nbrs: List[List[int]] = [
            [pos_to_idx[nb] for nb in self.grid.neighbors(positions[p]) if nb in pos_to_idx]
            for p in range(P)
        ]

        # ── Variables ────────────────────────────────────────────────────────
        # here[a][p][t]: agent a is at position p at time t
        here = [
            [[model.NewBoolVar(f'here_{a}_{p}_{t}') for t in range(T + 1)]
             for p in range(P)]
            for a in range(N)
        ]

        # move[(a,p,q,t)]: agent a moves from p to q at time t (q ∈ nbrs[p], includes wait p→p)
        move: Dict[Tuple[int, int, int, int], cp_model.IntVar] = {}
        for a in range(N):
            for t in range(T):
                for p in range(P):
                    for q in nbrs[p]:
                        move[(a, p, q, t)] = model.NewBoolVar(f'mv_{a}_{p}_{q}_{t}')

        # ── Constraints ──────────────────────────────────────────────────────
        # 1. Exactly one position per agent per timestep
        for a in range(N):
            for t in range(T + 1):
                model.AddExactlyOne(here[a][p][t] for p in range(P))

        # 2. Initial positions
        for a, drone in enumerate(self.drones):
            start_idx = pos_to_idx.get(drone.start)
            if start_idx is None:
                return Solution("infeasible", 0, 0, 0.0, {}, 0)
            model.Add(here[a][start_idx][0] == 1)

        # 3. Movement — flow conservation linking here ↔ move
        #    Grid is undirected: nbrs[p] == reverse_nbrs[p] (symmetry + self-loop for wait)
        for a in range(N):
            for t in range(T):
                for p in range(P):
                    # Outgoing: exactly one move leaves p at t iff agent is there
                    model.Add(
                        sum(move[(a, p, q, t)] for q in nbrs[p]) == here[a][p][t]
                    )
                    # Incoming: agent at p at t+1 came from some q via move q→p
                    model.Add(
                        sum(move[(a, q, p, t)] for q in nbrs[p]) == here[a][p][t + 1]
                    )

        # 4. Vertex conflict — AddNoOverlap per position (CSP-4 primitive)
        #    Replaces P*(T+1) individual AddAtMostOne constraints
        for p in range(P):
            model.AddNoOverlap([
                model.NewOptionalIntervalVar(t, 1, t + 1, here[a][p][t], f'ivp_{a}_{p}_{t}')
                for a in range(N)
                for t in range(T + 1)
            ])

        # 5. Edge (swap) conflict — AddNoOverlap per undirected arc (CSP-4 primitive)
        #    Replaces T*N*(N-1)/2*P*avg_nbrs individual 4-literal constraints
        seen_arcs: Set[Tuple[int, int]] = set()
        for p in range(P):
            for q in nbrs[p]:
                if q != p:
                    key = (min(p, q), max(p, q))
                    if key not in seen_arcs:
                        seen_arcs.add(key)
                        iv_arc = []
                        for a in range(N):
                            for t in range(T):
                                iv_arc.append(model.NewOptionalIntervalVar(
                                    t, 1, t + 1, move[(a, p, q, t)], f'iva_{a}_{p}_{q}_{t}'
                                ))
                                iv_arc.append(model.NewOptionalIntervalVar(
                                    t, 1, t + 1, move[(a, q, p, t)], f'iva_{a}_{q}_{p}_{t}'
                                ))
                        model.AddNoOverlap(iv_arc)

        # 6. Goal persistence: once at goal, stay there
        for a, drone in enumerate(self.drones):
            goal_idx = pos_to_idx.get(drone.goal)
            if goal_idx is None:
                return Solution("infeasible", 0, 0, 0.0, {}, 0)
            for t in range(T):
                model.Add(here[a][goal_idx][t + 1] >= here[a][goal_idx][t])

        # ── Objective (unchanged) ─────────────────────────────────────────────
        makespan_var = model.NewIntVar(0, T, 'makespan')
        arrival_vars = []
        for a, drone in enumerate(self.drones):
            goal_idx = pos_to_idx[drone.goal]
            arr = model.NewIntVar(0, T, f'arrival_{a}')
            model.Add(arr == T + 1 - sum(here[a][goal_idx][t] for t in range(T + 1)))
            arrival_vars.append(arr)
        model.AddMaxEquality(makespan_var, arrival_vars)
        model.Minimize(makespan_var)

        # ── Warm-start (unchanged, on here instead of x) ─────────────────────
        for a, path in enumerate(astar_paths):
            if path is None:
                continue
            for t in range(T + 1):
                pos = path[min(t, len(path) - 1)]
                hint_idx = pos_to_idx.get(pos)
                if hint_idx is None:
                    continue
                for p in range(P):
                    model.AddHint(here[a][p][t], 1 if p == hint_idx else 0)

        # ── Solve ─────────────────────────────────────────────────────────────
        elapsed_build = time.time() - t0
        if elapsed_build >= self.time_limit_s:
            return Solution("timeout", 0, 0, elapsed_build * 1000, {}, 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_s - elapsed_build
        solver.parameters.num_search_workers = 4

        status_code = solver.Solve(model)
        solve_time_ms = (time.time() - t0) * 1000

        status_map = {
            cp_model.OPTIMAL: "optimal",
            cp_model.FEASIBLE: "feasible",
            cp_model.INFEASIBLE: "infeasible",
            cp_model.UNKNOWN: "timeout",
            cp_model.MODEL_INVALID: "infeasible",
        }

        if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return Solution(status_map.get(status_code, "unknown"), 0, 0, solve_time_ms, {}, 0)

        makespan_val = int(solver.ObjectiveValue())

        # ── Path extraction (unchanged, here instead of x) ───────────────────
        paths: Dict[int, List[Pos]] = {}
        for a, drone in enumerate(self.drones):
            path: List[Pos] = []
            for t in range(makespan_val + 1):
                for p in range(P):
                    if solver.Value(here[a][p][t]):
                        path.append(positions[p])
                        break
            paths[drone.id] = path

        flowtime = sum(int(solver.Value(arr)) for arr in arrival_vars)
        return Solution(
            status=status_map.get(status_code, "unknown"),
            makespan=makespan_val,
            flowtime=flowtime,
            solve_time_ms=solve_time_ms,
            paths=paths,
            conflicts_avoided=self._near_passes(paths),
        )

    def _near_passes(self, paths: Dict[int, List[Pos]]) -> int:
        ids = list(paths.keys())
        max_t = max(len(p) for p in paths.values())
        count = 0
        for t in range(max_t):
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    pa = paths[a][min(t, len(paths[a]) - 1)]
                    pb = paths[b][min(t, len(paths[b]) - 1)]
                    dist = sum(abs(pa[k] - pb[k]) for k in range(len(pa)))
                    if dist == 1:
                        count += 1
        return count
