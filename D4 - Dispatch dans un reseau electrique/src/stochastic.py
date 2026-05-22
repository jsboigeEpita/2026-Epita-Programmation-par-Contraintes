"""Two-stage stochastic Unit Commitment with renewable scenarios.

The commitment variables  u[g,t], su[g,t], sd[g,t]  are **first-stage**
decisions: they must be taken before the renewable realisations are
revealed, and are therefore *the same in every scenario*.

The dispatch  p[g,t,s]  is **second-stage** (recourse): per scenario.
Renewables come with a per-scenario availability profile.

We optimise the expected total cost
    Σ_s π_s · [ fuel(p^s) + curtailment_penalty · curtail^s ]
  + start-up / shut-down costs (paid once, scenario-independent).

When the problem is genuinely infeasible for a scenario (lack of firm
capacity), we allow load-shedding ``ls[b,t,s]`` at a high penalty so that
the model always returns a feasible plan with a quantified shortage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ortools.sat.python import cp_model

from .instance import PowerNetwork, Generator
from .dispatch_solver import POWER_SCALE, COST_SCALE, _pwl_tangents


# Penalties (per MWh) — high enough to dominate fuel costs
LOAD_SHED_PENALTY  = 5_000.0
CURTAIL_PENALTY    =    50.0


@dataclass
class StochasticUCSolution:
    status: str
    horizon: int
    n_scenarios: int
    expected_cost: float
    commitment_cost: float                          # start-up + shut-down
    expected_fuel: float
    expected_curtailment: float                     # MWh of renewable curtailed
    expected_loadshed: float                        # MWh of unserved energy
    on:        Dict[str, List[int]]                 # first-stage  (gen, t)
    startups:  Dict[str, List[int]]
    shutdowns: Dict[str, List[int]]
    power:     Dict[str, List[List[float]]]         # gen -> [s][t]   MW
    flows:     List[List[List[float]]]              # line -> [s][t]  MW
    loadshed:  List[List[List[float]]]              # bus  -> [s][t]  MW
    probabilities: List[float]
    wall_time: float
    network: PowerNetwork = field(repr=False, default=None)

    def is_feasible(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")

    def report(self) -> str:
        out = [
            f"Status            : {self.status}",
            f"Horizon × Scen.   : {self.horizon} × {self.n_scenarios}",
            f"Expected cost     : ${self.expected_cost:,.2f}",
            f"  fuel (expected) : ${self.expected_fuel:,.2f}",
            f"  commitment      : ${self.commitment_cost:,.2f}",
            f"  curtailed (avg) : {self.expected_curtailment:,.1f} MWh "
            f"({CURTAIL_PENALTY:.0f} $/MWh penalty)",
            f"  unserved  (avg) : {self.expected_loadshed:,.2f} MWh "
            f"({LOAD_SHED_PENALTY:.0f} $/MWh penalty)",
            f"Wall time         : {self.wall_time:.2f} s",
            "",
            "First-stage commitment (same for every scenario):",
        ]
        header = "Gen          " + " ".join(f"{t:>3}" for t in range(self.horizon))
        out.append(header)
        for g in self.network.generators:
            row = " ".join(f"{self.on[g.id][t]:>3}" for t in range(self.horizon))
            out.append(f"  {g.id:<10} {row}")
        return "\n".join(out)


# --------------------------------------------------------------------------- #
# Solver
# --------------------------------------------------------------------------- #

def solve_stochastic_uc(
    network: PowerNetwork,
    load_profile: List[List[float]],
    scenarios: List[Dict[str, List[float]]],
    probabilities: Optional[List[float]] = None,
    reserve_profile: Optional[List[float]] = None,
    time_limit_s: int = 120,
    workers: int = 8,
    log_search: bool = False,
) -> StochasticUCSolution:
    """Solve the two-stage stochastic UC.

    Parameters
    ----------
    network        : the power system (includes renewables).
    load_profile   : ``load_profile[t][b]`` (deterministic demand, MW).
    scenarios      : list of renewable realisations, each a dict
                     ``{renewable_id -> [cap_factor per period]}``.
    probabilities  : sums to 1; default = uniform.
    reserve_profile: spinning-reserve MW per period (default 10% of load).
    """
    inst = network
    H = len(load_profile)
    S = len(scenarios)
    if probabilities is None:
        probabilities = [1.0 / S] * S
    assert abs(sum(probabilities) - 1.0) < 1e-6
    if reserve_profile is None:
        reserve_profile = [inst.reserve_fraction * sum(row) for row in load_profile]

    # Integer probability weights for the integer objective (parts per 10 000)
    pw = [int(round(p * 10_000)) for p in probabilities]
    pw_sum = sum(pw)  # ≈ 10 000

    model = cp_model.CpModel()

    # ---- First-stage commitment (shared) ----
    u: Dict[str, List[cp_model.IntVar]] = {}
    su: Dict[str, List[cp_model.IntVar]] = {}
    sd: Dict[str, List[cp_model.IntVar]] = {}
    for g in inst.generators:
        u_g, su_g, sd_g = [], [], []
        for t in range(H):
            if g.kind == "thermal":
                ut = model.new_bool_var(f"u_{g.id}_{t}")
                sut = model.new_bool_var(f"su_{g.id}_{t}")
                sdt = model.new_bool_var(f"sd_{g.id}_{t}")
                if t == 0:
                    model.add(sut - sdt == ut - g.init_state)
                else:
                    model.add(sut - sdt == ut - u_g[t - 1])
                model.add(sut + sdt <= 1)
            else:
                # renewables always "available" (we cap by scenario)
                ut  = model.new_constant(1)
                sut = model.new_constant(0)
                sdt = model.new_constant(0)
            u_g.append(ut); su_g.append(sut); sd_g.append(sdt)
        u[g.id] = u_g; su[g.id] = su_g; sd[g.id] = sd_g

    # min up / min down (thermal)
    for g in inst.thermal_generators():
        for t in range(H):
            for k in range(1, g.min_up):
                if t + k < H:
                    model.add(u[g.id][t + k] >= su[g.id][t])
            for k in range(1, g.min_down):
                if t + k < H:
                    model.add(u[g.id][t + k] <= 1 - sd[g.id][t])

    # ---- Second-stage variables (per scenario) ----
    p: Dict[str, List[List[cp_model.IntVar]]] = {}   # p[gid][s][t]
    flow: List[List[List[cp_model.IntVar]]] = []     # flow[i][s][t]
    ls:   List[List[List[cp_model.IntVar]]] = []     # ls[b][s][t]  load shed
    curt: Dict[str, List[List[cp_model.IntVar]]] = {}  # curt[gid][s][t] curtail

    for g in inst.generators:
        p_min_i = int(round(g.p_min * POWER_SCALE))
        p[g.id] = []
        if g.kind != "thermal":
            curt[g.id] = []
        for s in range(S):
            pg_s, cg_s = [], []
            for t in range(H):
                if g.kind == "thermal":
                    p_max_i = int(round(g.p_max * POWER_SCALE))
                    pt = model.new_int_var(0, p_max_i, f"p_{g.id}_{s}_{t}")
                    model.add(pt <= p_max_i * u[g.id][t])
                    if p_min_i > 0:
                        model.add(pt >= p_min_i * u[g.id][t])
                    pg_s.append(pt)
                else:
                    avail = scenarios[s].get(g.id, [0.0] * H)[t] * g.p_max
                    cap_i = int(round(avail * POWER_SCALE))
                    cap_i = max(cap_i, 0)
                    pt = model.new_int_var(0, cap_i, f"p_{g.id}_{s}_{t}")
                    # curtailment = capacity − output
                    ct = model.new_int_var(0, cap_i, f"curt_{g.id}_{s}_{t}")
                    model.add(pt + ct == cap_i)
                    pg_s.append(pt); cg_s.append(ct)
            p[g.id].append(pg_s)
            if g.kind != "thermal":
                curt[g.id].append(cg_s)

    # ramp limits (per-scenario dispatch; commitment is shared)
    for g in inst.thermal_generators():
        ru_i = int(round(g.ramp_up * POWER_SCALE))
        rd_i = int(round(g.ramp_down * POWER_SCALE))
        init_p_i = int(round(g.init_power * POWER_SCALE))
        p_min_i = int(round(g.p_min * POWER_SCALE))
        for s in range(S):
            for t in range(H):
                prev_p = init_p_i if t == 0 else p[g.id][s][t - 1]
                model.add(p[g.id][s][t] - prev_p <= ru_i + p_min_i * su[g.id][t])
                model.add(prev_p - p[g.id][s][t] <= rd_i + p_min_i * sd[g.id][t])

    # line flows + load-shed per scenario
    for i, ln in enumerate(inst.lines):
        cap = int(round(ln.capacity * POWER_SCALE))
        flow.append([[model.new_int_var(-cap, cap, f"f_{i}_{s}_{t}")
                      for t in range(H)] for s in range(S)])
    for b_idx, bus in enumerate(inst.buses):
        ls.append([])
        for s in range(S):
            row = []
            for t in range(H):
                cap = int(round(load_profile[t][b_idx] * POWER_SCALE))
                row.append(model.new_int_var(0, max(cap, 0), f"ls_{b_idx}_{s}_{t}"))
            ls[-1].append(row)

    # bus balance per (s, t)
    for s in range(S):
        for t in range(H):
            for b_idx in range(len(inst.buses)):
                gens_here = [p[g.id][s][t] for g in inst.gen_at_bus(b_idx)]
                in_f, out_f = [], []
                for i, ln in enumerate(inst.lines):
                    if ln.to_bus == b_idx:   in_f.append(flow[i][s][t])
                    if ln.from_bus == b_idx: out_f.append(flow[i][s][t])
                load_i = int(round(load_profile[t][b_idx] * POWER_SCALE))
                shed_i = ls[b_idx][s][t]
                model.add(sum(gens_here) + sum(in_f) - sum(out_f) + shed_i == load_i)

    # spinning reserve per (s, t) on thermal units only
    for s in range(S):
        for t in range(H):
            terms = []
            for g in inst.thermal_generators():
                p_max_i = int(round(g.p_max * POWER_SCALE))
                terms.append(p_max_i * u[g.id][t] - p[g.id][s][t])
            if terms:
                model.add(sum(terms) >= int(round(reserve_profile[t] * POWER_SCALE)))

    # ---- Objective ----
    # Expected fuel cost (PWL tangents per scenario)
    fuel_terms_per_scen: List[List[cp_model.IntVar]] = [[] for _ in range(S)]
    for g in inst.thermal_generators():
        ub = int(round(g.cost(g.p_max) * COST_SCALE * 1.05)) + 1
        for s in range(S):
            for t in range(H):
                c = model.new_int_var(0, ub, f"c_{g.id}_{s}_{t}")
                for slope, intercept in _pwl_tangents(g):
                    model.add(c >= slope * p[g.id][s][t] + intercept) \
                         .only_enforce_if(u[g.id][t])
                model.add(c == 0).only_enforce_if(u[g.id][t].negated())
                fuel_terms_per_scen[s].append(c)

    # First-stage commitment cost
    commit_terms = []
    for g in inst.thermal_generators():
        sc = int(round(g.startup_cost  * COST_SCALE))
        dc = int(round(g.shutdown_cost * COST_SCALE))
        for t in range(H):
            if sc > 0: commit_terms.append(sc * su[g.id][t])
            if dc > 0: commit_terms.append(dc * sd[g.id][t])

    # Expected curtail + load-shed
    ls_pen = int(round(LOAD_SHED_PENALTY * COST_SCALE))
    cu_pen = int(round(CURTAIL_PENALTY   * COST_SCALE))
    scen_costs = []
    for s in range(S):
        terms = list(fuel_terms_per_scen[s])
        for b_idx in range(len(inst.buses)):
            for t in range(H):
                terms.append(ls_pen * ls[b_idx][s][t])
        for g in inst.renewable_generators():
            for t in range(H):
                terms.append(cu_pen * curt[g.id][s][t])
        scen_costs.append(sum(terms))

    # Weighted expected cost using integer weights: cost * pw / pw_sum
    weighted = sum(pw[s] * scen_costs[s] for s in range(S))
    # Multiply commitment costs by pw_sum (so units match) then divide at the end
    model.minimize(weighted + pw_sum * sum(commit_terms))

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
        on    = {g.id: [int(solver.value(u[g.id][t])) for t in range(H)]
                 for g in inst.generators}
        sups  = {g.id: [int(solver.value(su[g.id][t])) for t in range(H)]
                 for g in inst.generators}
        sdns  = {g.id: [int(solver.value(sd[g.id][t])) for t in range(H)]
                 for g in inst.generators}
        power = {g.id: [[solver.value(p[g.id][s][t]) / POWER_SCALE
                         for t in range(H)] for s in range(S)]
                 for g in inst.generators}
        flows = [[[solver.value(flow[i][s][t]) / POWER_SCALE for t in range(H)]
                  for s in range(S)] for i in range(len(inst.lines))]
        shed  = [[[solver.value(ls[b][s][t]) / POWER_SCALE for t in range(H)]
                  for s in range(S)] for b in range(len(inst.buses))]

        commitment_cost = sum(
            (g.startup_cost  * solver.value(su[g.id][t]) +
             g.shutdown_cost * solver.value(sd[g.id][t]))
            for g in inst.thermal_generators() for t in range(H)
        )
        # expected fuel and penalties (in $)
        exp_fuel = sum(probabilities[s] *
                       sum(solver.value(c) for c in fuel_terms_per_scen[s])
                       for s in range(S)) / COST_SCALE
        exp_shed_mwh = sum(probabilities[s] * sum(shed[b][s][t]
                            for b in range(len(inst.buses)) for t in range(H))
                            for s in range(S))
        exp_curt_mwh = sum(
            probabilities[s] * sum(solver.value(curt[g.id][s][t]) / POWER_SCALE
                                   for g in inst.renewable_generators()
                                   for t in range(H))
            for s in range(S)
        )
        exp_cost = (exp_fuel + commitment_cost
                    + LOAD_SHED_PENALTY * exp_shed_mwh
                    + CURTAIL_PENALTY   * exp_curt_mwh)
    else:
        on = {g.id: [0]*H for g in inst.generators}
        sups = {g.id: [0]*H for g in inst.generators}
        sdns = {g.id: [0]*H for g in inst.generators}
        power = {g.id: [[0.0]*H for _ in range(S)] for g in inst.generators}
        flows = [[[0.0]*H for _ in range(S)] for _ in inst.lines]
        shed  = [[[0.0]*H for _ in range(S)] for _ in inst.buses]
        exp_cost = commitment_cost = exp_fuel = exp_shed_mwh = exp_curt_mwh = 0.0

    return StochasticUCSolution(
        status=status, horizon=H, n_scenarios=S,
        expected_cost=exp_cost, commitment_cost=commitment_cost,
        expected_fuel=exp_fuel, expected_curtailment=exp_curt_mwh,
        expected_loadshed=exp_shed_mwh,
        on=on, startups=sups, shutdowns=sdns,
        power=power, flows=flows, loadshed=shed,
        probabilities=probabilities, wall_time=solver.wall_time, network=inst,
    )
