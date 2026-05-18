"""
CP-SAT solver for the Electric Vehicle Routing Problem (EVRP).

Model overview
--------------
Nodes: 0 = depot, 1..C = customers, C+1..C+S = charging stations.

For k vehicles, each vehicle gets its own AddCircuit over all n_nodes.
Self-loops allow skipping non-mandatory nodes:
  - Customers : must be visited by exactly one vehicle → Σ_v self_loop[v][i] = K-1
  - Stations  : optional for every vehicle (no uniqueness constraint)
  - Depot     : vehicles that do nothing use self-loop on depot

Battery model (two variables per node)
---------------------------------------
  bat_arrive[v][i]  : battery level on ARRIVAL at node i for vehicle v
  bat_depart[v][i]  : battery level on DEPARTURE from node i
    - Non-stations  : bat_depart = bat_arrive  (no charging)
    - Stations      : bat_depart = B           (full recharge, simplified)
    - Depot start   : bat_depart = B

Load-dependent energy consumption
-----------------------------------
  Arc energy (in ENERGY_SCALE units) for vehicle v travelling i→j:
      e(i,j,q) = base_e[i,j] + ⌊base_e[i,j] · ls · q / Q⌋
  where q = load[v][i] (CP variable), ls = load_sensitivity, Q = vehicle_capacity.

  Implementation: for each arc where the per-full-load bonus
  ls_bonus_per_Q = round(base_e · ls) > 0, we introduce an IntVar bonus_var
  and enforce bonus_var = ls_bonus_per_Q · load[v][i] // Q using
  add_division_equality (exact integer division, CP-SAT native).
  When ls = 0 (e.g. Schneider instances) or the coefficient rounds to 0
  (very short arcs), the base energy is used directly — no overhead.

  Arc propagation:
      bat_arrive[v][j] = bat_depart[v][i] - base_e[i,j] - bonus_var[v][i,j]
      enforced with OnlyEnforceIf(arc[v][(i,j)])

Objective
---------
  Minimise total scaled distance (proxy for CO₂ / energy cost).
"""

from __future__ import annotations
from typing import List, Dict

from ortools.sat.python import cp_model

from .instance import EVRPInstance, DEPOT, CUSTOMER, STATION


# ── result ────────────────────────────────────────────────────────────────────

class EVRPSolution:
    def __init__(self, routes, instance, total_dist, status, wall_time,
                 open_stations=None):
        self.routes         = routes
        self.instance       = instance
        self.total_dist     = total_dist
        self.status         = status
        self.wall_time      = wall_time
        self.open_stations  = open_stations or []

    def total_dist_km(self) -> float:
        from .instance import DIST_SCALE
        return self.total_dist / DIST_SCALE

    def is_feasible(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")

    def __repr__(self) -> str:
        lines = [
            f"Status     : {self.status}",
            f"Total dist : {self.total_dist_km():.2f} km",
            f"Wall time  : {self.wall_time:.2f} s",
        ]
        if self.open_stations:
            lines.append(f"Stations   : {self.open_stations} ({len(self.open_stations)} open)")
        for k, route in enumerate(self.routes):
            if route:
                names = ["depot"] + [f"n{i}" for i in route] + ["depot"]
                lines.append(f"  V{k}: {' → '.join(names)}")
        return "\n".join(lines)


# ── solver ────────────────────────────────────────────────────────────────────

def solve_evrp(
    instance: EVRPInstance,
    time_limit_s: int = 60,
    use_time_windows: bool = True,
    optimize_stations: bool = False,
    station_open_cost: int = 500,
) -> EVRPSolution:
    """
    Solve the EVRP with CP-SAT.

    Parameters
    ----------
    optimize_stations : bool
        If True, station placement becomes a decision variable: the model
        decides which charging stations to open.  An ``open_station[s]``
        BoolVar gates every arc entering/leaving station s, and the number
        of open stations is penalised by ``station_open_cost`` in the
        objective (same unit as distance, i.e. DIST_SCALE units).
    station_open_cost : int
        Fixed cost (in DIST_SCALE units) for opening one charging station.
        Only used when ``optimize_stations=True``.
    """
    inst = instance
    n    = inst.n_nodes
    K    = inst.n_vehicles
    B    = inst.battery_capacity
    Q    = inst.vehicle_capacity
    ls   = inst.load_sensitivity

    model  = cp_model.CpModel()
    solver = cp_model.CpSolver()

    # ── arc variables ─────────────────────────────────────────────────────────
    arc: List[Dict] = [{} for _ in range(K)]
    for v in range(K):
        for i in range(n):
            for j in range(n):
                arc[v][(i, j)] = model.new_bool_var(f"x_{v}_{i}_{j}")

    # ── AddCircuit (one independent circuit per vehicle) ──────────────────────
    for v in range(K):
        circuit_arcs = [(i, j, arc[v][(i, j)]) for i in range(n) for j in range(n)]
        model.add_circuit(circuit_arcs)

    # ── customer assignment: visited by exactly one vehicle ───────────────────
    for i in inst.customer_indices:
        model.add(sum(arc[v][(i, i)] for v in range(K)) == K - 1)

    # ── station placement decision variables ──────────────────────────────────
    open_station: Dict = {}
    for s in inst.station_indices:
        if optimize_stations:
            open_station[s] = model.new_bool_var(f"open_{s}")
        else:
            v_fixed = model.new_bool_var(f"open_{s}")
            model.add(v_fixed == 1)
            open_station[s] = v_fixed

    if optimize_stations:
        for s in inst.station_indices:
            for v in range(K):
                for i in range(n):
                    if i != s:
                        model.add_implication(arc[v][(i, s)], open_station[s])
                        model.add_implication(arc[v][(s, i)], open_station[s])

    # ── load variables ────────────────────────────────────────────────────────
    load = [[model.new_int_var(0, Q, f"ld_{v}_{i}") for i in range(n)] for v in range(K)]

    for v in range(K):
        model.add(load[v][DEPOT] == 0)
        for i in range(n):
            for j in range(n):
                if i == j or j == DEPOT:
                    continue
                if inst.node_types[j] == CUSTOMER:
                    model.add(load[v][j] == load[v][i] + inst.demands[j]).only_enforce_if(arc[v][(i, j)])
                else:
                    model.add(load[v][j] == load[v][i]).only_enforce_if(arc[v][(i, j)])

    # ── battery variables ─────────────────────────────────────────────────────
    bat_arr = [[model.new_int_var(0, B, f"ba_{v}_{i}") for i in range(n)] for v in range(K)]
    bat_dep = [[model.new_int_var(0, B, f"bd_{v}_{i}") for i in range(n)] for v in range(K)]

    for v in range(K):
        model.add(bat_dep[v][DEPOT] == B)

        for i in range(n):
            if inst.node_types[i] == STATION:
                model.add(bat_dep[v][i] == B)
            elif i != DEPOT:
                model.add(bat_dep[v][i] == bat_arr[v][i])

        # Arc propagation with load-dependent energy
        # e(i→j, q) = base_e + ⌊base_e · ls · q / Q⌋
        # Implemented via add_division_equality when the per-Q bonus > 0.
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                base_e = inst._energy[i][j]
                ls_bonus_per_Q = int(round(base_e * ls)) if ls > 0 else 0

                if ls_bonus_per_Q > 0:
                    # bonus_var = ls_bonus_per_Q * load[v][i] // Q
                    bonus_var = model.new_int_var(0, ls_bonus_per_Q, f"eb_{v}_{i}_{j}")
                    model.add_division_equality(
                        bonus_var,
                        ls_bonus_per_Q * load[v][i],
                        Q,
                    )
                    model.add(
                        bat_arr[v][j] == bat_dep[v][i] - base_e - bonus_var
                    ).only_enforce_if(arc[v][(i, j)])
                else:
                    model.add(
                        bat_arr[v][j] == bat_dep[v][i] - base_e
                    ).only_enforce_if(arc[v][(i, j)])

                model.add(bat_arr[v][j] >= 0).only_enforce_if(arc[v][(i, j)])

    # ── time-window variables ─────────────────────────────────────────────────
    max_time = max(tw[1] for tw in inst.time_windows) + 120
    time_arr = [[model.new_int_var(0, max_time, f"t_{v}_{i}") for i in range(n)] for v in range(K)]

    for v in range(K):
        model.add(time_arr[v][DEPOT] == 0)
        for i in range(n):
            for j in range(n):
                if i == j or j == DEPOT:
                    continue
                travel  = inst.travel_time(i, j)
                service = inst.service_times[i]
                model.add(
                    time_arr[v][j] >= time_arr[v][i] + service + travel
                ).only_enforce_if(arc[v][(i, j)])

        if use_time_windows:
            for i in range(1, n):
                lo, hi = inst.time_windows[i]
                model.add(time_arr[v][i] >= lo).only_enforce_if(arc[v][(i, i)].negated())
                model.add(time_arr[v][i] <= hi).only_enforce_if(arc[v][(i, i)].negated())

    # ── objective ─────────────────────────────────────────────────────────────
    obj_terms = [
        inst.dist(i, j) * arc[v][(i, j)]
        for v in range(K)
        for i in range(n)
        for j in range(n)
        if i != j
    ]
    if optimize_stations:
        station_cost_terms = [
            station_open_cost * open_station[s] for s in inst.station_indices
        ]
        model.minimize(sum(obj_terms) + sum(station_cost_terms))
    else:
        model.minimize(sum(obj_terms))

    # ── solve ─────────────────────────────────────────────────────────────────
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers  = 4
    status_code = solver.solve(model)

    status_map = {
        cp_model.OPTIMAL:    "OPTIMAL",
        cp_model.FEASIBLE:   "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN:    "UNKNOWN",
    }
    status = status_map.get(status_code, "UNKNOWN")

    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        routes        = _extract_routes(solver, arc, inst, K, n)
        dist_val      = int(solver.objective_value)
        open_stations = [s for s in inst.station_indices
                         if solver.value(open_station[s]) == 1]
    else:
        routes        = [[] for _ in range(K)]
        dist_val      = -1
        open_stations = []

    return EVRPSolution(
        routes=routes,
        instance=inst,
        total_dist=dist_val,
        status=status,
        wall_time=solver.wall_time,
        open_stations=open_stations,
    )


def _extract_routes(solver, arc, inst, K, n) -> List[List[int]]:
    routes = []
    for v in range(K):
        succ = {i: j for i in range(n) for j in range(n)
                if i != j and solver.value(arc[v][(i, j)]) == 1}
        route = []
        cur = succ.get(DEPOT, DEPOT)
        seen = set()
        while cur != DEPOT and cur not in seen:
            seen.add(cur)
            route.append(cur)
            cur = succ.get(cur, DEPOT)
        routes.append(route)
    return routes
