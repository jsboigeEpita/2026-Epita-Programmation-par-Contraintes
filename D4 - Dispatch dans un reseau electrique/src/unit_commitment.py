"""Multi-period Unit Commitment with CP-SAT.

Extends the single-period economic dispatch over a discrete horizon
``T = 1, …, H`` (typically 24 hours) with the following commitment logic:

* Binary status   u[g,t] ∈ {0, 1}      (ON/OFF of each generator)
* Start-up        su[g,t]              (≥ u[g,t] − u[g,t-1])
* Shutdown        sd[g,t]              (≥ u[g,t-1] − u[g,t])
* Minimum up time:    once started, a unit stays ON for ≥ min_up hours
* Minimum down time:  once stopped, it stays OFF for ≥ min_down hours
* Ramp limits:        |P[g,t] − P[g,t-1]| ≤ ramp_up (when both periods ON)
* Spinning reserve:   Σ (p_max·u − P[g,t]) ≥ R(t) at every t
* Bus balance + line capacity at every t (same as single-period)

Renewables (wind/solar) carry no commitment variable; their availability
is provided by ``availability[gen_id][t]`` in MW (capped above).

Cost  = Σ_t [ Σ_g fuel_cost(P[g,t], u[g,t])
            + startup_cost · su[g,t]
            + shutdown_cost · sd[g,t] ]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ortools.sat.python import cp_model

from .instance import PowerNetwork, Generator
from .dispatch_solver import POWER_SCALE, COST_SCALE, _pwl_tangents


@dataclass
class UnitCommitmentSolution:
    status: str
    horizon: int
    total_cost: float                       # $
    fuel_cost: float                        # $
    startup_cost: float                     # $
    shutdown_cost: float                    # $
    power: Dict[str, List[float]]           # gen_id -> [MW per period]
    on:    Dict[str, List[int]]             # gen_id -> [0/1 per period]
    startups:  Dict[str, List[int]]
    shutdowns: Dict[str, List[int]]
    flows: List[List[float]]                # [line][t]
    loads: List[List[float]] = field(repr=False, default_factory=list)
    wall_time: float = 0.0
    network: PowerNetwork = field(repr=False, default=None)
    objective_bound: float = 0.0
    gap: float = 0.0

    def is_feasible(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")

    def report(self) -> str:
        lines = [
            f"Status       : {self.status}",
            f"Horizon      : {self.horizon} h",
            f"Total cost   : ${self.total_cost:,.2f}",
            f"  fuel       : ${self.fuel_cost:,.2f}",
            f"  start-ups  : ${self.startup_cost:,.2f}",
            f"  shut-downs : ${self.shutdown_cost:,.2f}",
            f"Optimality   : gap = {self.gap*100:.2f} %",
            f"Wall time    : {self.wall_time:.2f} s",
            "",
            "Schedule (1 = ON):",
        ]
        header = "Gen          " + " ".join(f"{t:>3}" for t in range(self.horizon))
        lines.append(header)
        for g in self.network.generators:
            row = " ".join(f"{self.on[g.id][t]:>3}" for t in range(self.horizon))
            lines.append(f"  {g.id:<10} {row}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Solver
# --------------------------------------------------------------------------- #

def solve_unit_commitment(
    network: PowerNetwork,
    load_profile: List[List[float]],
    availability: Optional[Dict[str, List[float]]] = None,
    reserve_profile: Optional[List[float]] = None,
    time_limit_s: int = 60,
    workers: int = 8,
    log_search: bool = False,
) -> UnitCommitmentSolution:
    """Solve the deterministic UC.

    Parameters
    ----------
    network         : the power system.
    load_profile    : ``load_profile[t][b]`` — load at bus b in period t (MW).
    availability    : ``availability[gen_id][t]`` — renewable cap at t (MW).
                      Thermal units are unaffected.
    reserve_profile : per-period spinning-reserve requirement (MW). Defaults
                      to ``network.reserve_fraction × Σ_b load_profile[t][b]``.
    """
    inst = network
    H = len(load_profile)
    assert all(len(row) == len(inst.buses) for row in load_profile), \
        "load_profile must be [T][n_buses]"

    if reserve_profile is None:
        reserve_profile = [inst.reserve_fraction * sum(row) for row in load_profile]
    assert len(reserve_profile) == H

    if availability is None:
        availability = {}

    model = cp_model.CpModel()

    # ---- decision variables (over the horizon) ----
    p: Dict[str, List[cp_model.IntVar]] = {}
    u: Dict[str, List[cp_model.IntVar]] = {}
    su: Dict[str, List[cp_model.IntVar]] = {}
    sd: Dict[str, List[cp_model.IntVar]] = {}

    for g in inst.generators:
        p_min_i = int(round(g.p_min * POWER_SCALE))
        u_g, p_g, su_g, sd_g = [], [], [], []
        for t in range(H):
            cap_t = g.p_max
            if g.id in availability:
                cap_t = min(cap_t, availability[g.id][t])
            cap_i = int(round(cap_t * POWER_SCALE))
            cap_i = max(cap_i, 0)

            ut = model.new_bool_var(f"u_{g.id}_{t}")
            pt = model.new_int_var(0, cap_i, f"p_{g.id}_{t}")
            model.add(pt <= cap_i * ut)
            if p_min_i > 0 and g.kind == "thermal":
                model.add(pt >= p_min_i * ut)
            u_g.append(ut)
            p_g.append(pt)
            # start-up / shut-down indicators
            sut = model.new_bool_var(f"su_{g.id}_{t}")
            sdt = model.new_bool_var(f"sd_{g.id}_{t}")
            prev = ut if t == 0 else u_g[t - 1]
            if t == 0:
                # use the recorded init_state as u[-1]
                model.add(sut - sdt == ut - g.init_state)
            else:
                model.add(sut - sdt == ut - u_g[t - 1])
            model.add(sut + sdt <= 1)
            su_g.append(sut); sd_g.append(sdt)

        p[g.id] = p_g
        u[g.id] = u_g
        su[g.id] = su_g
        sd[g.id] = sd_g

    # ---- min up / min down ----
    for g in inst.generators:
        if g.kind != "thermal":
            continue
        for t in range(H):
            # if start-up at t, must stay ON for min_up periods
            for k in range(1, g.min_up):
                if t + k < H:
                    model.add(u[g.id][t + k] >= su[g.id][t])
            # if shut-down at t, must stay OFF for min_down periods
            for k in range(1, g.min_down):
                if t + k < H:
                    model.add(u[g.id][t + k] <= 1 - sd[g.id][t])

    # ---- ramp limits ----
    for g in inst.generators:
        if g.kind != "thermal":
            continue
        ru_i = int(round(g.ramp_up * POWER_SCALE))
        rd_i = int(round(g.ramp_down * POWER_SCALE))
        init_p_i = int(round(g.init_power * POWER_SCALE))
        for t in range(H):
            prev_p = init_p_i if t == 0 else p[g.id][t - 1]
            # Allow extra "headroom" of p_min on start/shut so a unit can come
            # online at its p_min directly even when ramp < p_min.
            p_min_i = int(round(g.p_min * POWER_SCALE))
            model.add(p[g.id][t] - prev_p <=  ru_i + p_min_i * su[g.id][t])
            model.add(prev_p - p[g.id][t] <=  rd_i + p_min_i * sd[g.id][t])

    # ---- bus power balance + line flows, per period ----
    flow: List[List[cp_model.IntVar]] = []
    for i, ln in enumerate(inst.lines):
        cap = int(round(ln.capacity * POWER_SCALE))
        flow.append([model.new_int_var(-cap, cap, f"f_{i}_{t}") for t in range(H)])

    for t in range(H):
        for b_idx in range(len(inst.buses)):
            gens_here = [p[g.id][t] for g in inst.gen_at_bus(b_idx)]
            in_f, out_f = [], []
            for i, ln in enumerate(inst.lines):
                if ln.to_bus == b_idx:   in_f.append(flow[i][t])
                if ln.from_bus == b_idx: out_f.append(flow[i][t])
            load_i = int(round(load_profile[t][b_idx] * POWER_SCALE))
            model.add(sum(gens_here) + sum(in_f) - sum(out_f) == load_i)

    # ---- spinning reserve ----
    for t in range(H):
        terms = []
        for g in inst.thermal_generators():
            p_max_i = int(round(g.p_max * POWER_SCALE))
            terms.append(p_max_i * u[g.id][t] - p[g.id][t])
        if terms:
            model.add(sum(terms) >= int(round(reserve_profile[t] * POWER_SCALE)))

    # ---- fuel cost via PWL tangents ----
    fuel_cost: List[cp_model.IntVar] = []
    for g in inst.generators:
        if g.kind != "thermal":
            for _ in range(H):
                fuel_cost.append(model.new_constant(0))
            continue
        ub = int(round(g.cost(g.p_max) * COST_SCALE * 1.05)) + 1
        for t in range(H):
            c = model.new_int_var(0, ub, f"c_{g.id}_{t}")
            for slope, intercept in _pwl_tangents(g):
                model.add(c >= slope * p[g.id][t] + intercept) \
                     .only_enforce_if(u[g.id][t])
            model.add(c == 0).only_enforce_if(u[g.id][t].negated())
            fuel_cost.append(c)

    # ---- start-up and shut-down cost ----
    startup_terms, shutdown_terms = [], []
    for g in inst.thermal_generators():
        sc = int(round(g.startup_cost  * COST_SCALE))
        dc = int(round(g.shutdown_cost * COST_SCALE))
        for t in range(H):
            if sc > 0:
                startup_terms.append(sc * su[g.id][t])
            if dc > 0:
                shutdown_terms.append(dc * sd[g.id][t])

    model.minimize(sum(fuel_cost) + sum(startup_terms) + sum(shutdown_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = log_search

    status_code = solver.solve(model)
    status_map = {
        cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN",
    }
    status = status_map.get(status_code, "UNKNOWN")

    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        power = {g.id: [solver.value(p[g.id][t]) / POWER_SCALE for t in range(H)]
                 for g in inst.generators}
        on    = {g.id: [int(solver.value(u[g.id][t])) for t in range(H)]
                 for g in inst.generators}
        sups  = {g.id: [int(solver.value(su[g.id][t])) for t in range(H)]
                 for g in inst.generators}
        sdns  = {g.id: [int(solver.value(sd[g.id][t])) for t in range(H)]
                 for g in inst.generators}
        flows = [[solver.value(flow[i][t]) / POWER_SCALE for t in range(H)]
                 for i in range(len(inst.lines))]

        fuel = sum(solver.value(c) for c in fuel_cost) / COST_SCALE
        stc  = sum(int(round(g.startup_cost  * COST_SCALE)) * solver.value(su[g.id][t])
                   for g in inst.thermal_generators() for t in range(H)) / COST_SCALE
        sdc  = sum(int(round(g.shutdown_cost * COST_SCALE)) * solver.value(sd[g.id][t])
                   for g in inst.thermal_generators() for t in range(H)) / COST_SCALE

        total = solver.objective_value / COST_SCALE
        bound = solver.best_objective_bound / COST_SCALE
        gap = 0.0 if total <= 0 else abs(total - bound) / max(1e-9, abs(total))
    else:
        power = {g.id: [0.0] * H for g in inst.generators}
        on    = {g.id: [0]   * H for g in inst.generators}
        sups  = {g.id: [0]   * H for g in inst.generators}
        sdns  = {g.id: [0]   * H for g in inst.generators}
        flows = [[0.0] * H for _ in inst.lines]
        fuel = stc = sdc = total = bound = 0.0
        gap = float("inf")

    return UnitCommitmentSolution(
        status=status, horizon=H, total_cost=total,
        fuel_cost=fuel, startup_cost=stc, shutdown_cost=sdc,
        power=power, on=on, startups=sups, shutdowns=sdns,
        flows=flows, loads=load_profile, wall_time=solver.wall_time,
        network=inst, objective_bound=bound, gap=gap,
    )


# --------------------------------------------------------------------------- #
# Helper: typical daily load profile
# --------------------------------------------------------------------------- #

def daily_load_profile(network: PowerNetwork, H: int = 24,
                       peak_factor: float = 1.3, off_peak_factor: float = 0.55,
                       peak_hour: int = 19) -> List[List[float]]:
    """Build a [T][n_buses] load profile by scaling each bus's base load with
    a smooth daily curve (sum of two cosines)."""
    import math
    profile = []
    base = [b.load for b in network.buses]
    for t in range(H):
        # smooth shape: minimum at 04:00, peak at 19:00
        x = 2 * math.pi * (t - peak_hour) / 24
        shape = (peak_factor + off_peak_factor) / 2 \
              + (peak_factor - off_peak_factor) / 2 * math.cos(x)
        profile.append([round(b * shape, 2) for b in base])
    return profile
