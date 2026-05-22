"""Single-period Economic Dispatch with CP-SAT.

Given a `PowerNetwork` and a vector of bus loads, find the generation
schedule that satisfies demand at minimum cost subject to:

* Generator capacity         p_min·u ≤ P[g] ≤ p_max·u, u ∈ {0,1}
* Bus power balance          Σ P[g@b] + Σ flow_in − Σ flow_out = load[b]
* Line capacity              −cap ≤ flow[l] ≤ +cap
* Spinning reserve           Σ (p_max·u − P[g]) ≥ R

The quadratic cost  c_g(P) = a + b·P + c·P²  is approximated by its convex
piecewise-linear lower envelope: for each thermal unit we sample K break-
points in [p_min, p_max] and add one tangent constraint per breakpoint.
Because the function is convex, the supremum of these tangents matches the
true cost at the optimum.

All quantities are scaled to integers (``POWER_SCALE`` MW units,
``COST_SCALE`` × $) so that CP-SAT stays purely integer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ortools.sat.python import cp_model

from .instance import PowerNetwork, Generator


# Scaling: power is internally in MW (integer), cost in cents
POWER_SCALE = 1        # 1 unit = 1 MW
COST_SCALE = 100       # 1 internal unit = 0.01 $
PWL_BREAKPOINTS = 6


@dataclass
class EconomicDispatchSolution:
    status: str
    total_cost: float                  # $/h
    power: Dict[str, float]            # generator id -> MW
    on: Dict[str, int]                 # generator id -> 0/1
    flows: List[float]                 # per-line MW (positive = from->to)
    wall_time: float
    network: PowerNetwork = field(repr=False)
    loads: List[float] = field(repr=False, default_factory=list)

    def is_feasible(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")

    def merit_order_cost(self) -> float:
        """Cost obtained by sorting generators by average cost and stacking
        them greedily — ignores transmission limits. Useful as a baseline."""
        total = sum(self.loads)
        gens = sorted(self.network.thermal_generators(),
                      key=lambda g: g.cost_b + g.cost_c * g.p_max)
        remaining, cost = total, 0.0
        for g in gens:
            p = max(g.p_min, min(g.p_max, remaining)) if remaining > 0 else 0
            if p <= 0:
                continue
            cost += g.cost(p)
            remaining -= p
            if remaining <= 0:
                break
        return cost

    def report(self) -> str:
        lines = [f"Status      : {self.status}",
                 f"Total cost  : ${self.total_cost:,.2f}/h",
                 f"Wall time   : {self.wall_time:.2f} s",
                 "",
                 f"{'Generator':<14}{'Bus':>4}{'  P (MW)':>10}{'  P_min':>9}{'  P_max':>9}  on"]
        for g in self.network.generators:
            lines.append(f"{g.id:<14}{g.bus:>4}{self.power[g.id]:>10.2f}"
                         f"{g.p_min:>9.0f}{g.p_max:>9.0f}{self.on[g.id]:>4}")
        lines.append("")
        lines.append("Line flows (positive = from -> to):")
        for i, ln in enumerate(self.network.lines):
            f = self.flows[i]
            sat = "***" if abs(f) >= 0.99 * ln.capacity else ""
            lines.append(f"  L{i}  B{ln.from_bus}->B{ln.to_bus}"
                         f"   {f:+7.2f} / ±{ln.capacity:.0f} MW   {sat}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Piece-wise-linear cost helper
# --------------------------------------------------------------------------- #

def _pwl_tangents(g: Generator, k: int = PWL_BREAKPOINTS):
    """Return (slope, intercept) of `k` tangent lines to the quadratic cost.

    Each tangent at breakpoint P_i has equation
        y = (b + 2 c P_i)·p + (a − c P_i²)
    Slopes and intercepts are integers (rounded after the cost scale).
    """
    out = []
    if g.p_max <= g.p_min:
        return [(int(round(g.cost_b * COST_SCALE)),
                 int(round(g.cost_a * COST_SCALE)))]
    for i in range(k):
        # evenly spaced breakpoints in [p_min, p_max]
        p_i = g.p_min + (g.p_max - g.p_min) * i / max(k - 1, 1)
        slope     = g.cost_b + 2 * g.cost_c * p_i
        intercept = g.cost_a - g.cost_c * p_i * p_i
        out.append((int(round(slope     * COST_SCALE)),
                    int(round(intercept * COST_SCALE))))
    return out


# --------------------------------------------------------------------------- #
# Solver
# --------------------------------------------------------------------------- #

def solve_economic_dispatch(
    network: PowerNetwork,
    loads: Optional[List[float]] = None,
    renewable_availability: Optional[Dict[str, float]] = None,
    reserve_mw: Optional[float] = None,
    enforce_min_output: bool = True,
    time_limit_s: int = 30,
    workers: int = 4,
    log_search: bool = False,
) -> EconomicDispatchSolution:
    """Solve the single-period economic dispatch.

    Parameters
    ----------
    network : the power system.
    loads   : per-bus demand in MW (overrides ``network.buses[*].load``).
    renewable_availability : optional dict ``{gen_id -> available MW}`` used to
                             cap renewable generators in this period.
    reserve_mw : minimum spare capacity (sum of (p_max·u − P)) in MW.
                 If None, ``network.reserve_fraction`` × total load is used.
    enforce_min_output : if False, ignore p_min (each unit can operate down
                         to 0 even when ON) — useful for continuous LP-style
                         comparison.
    """
    inst = network
    if loads is None:
        loads = [b.load for b in inst.buses]
    assert len(loads) == len(inst.buses), "loads length mismatch"

    if reserve_mw is None:
        reserve_mw = inst.reserve_fraction * sum(loads)

    model = cp_model.CpModel()

    # ---- decision variables ----
    p_var: Dict[str, cp_model.IntVar] = {}
    u_var: Dict[str, cp_model.IntVar] = {}
    for g in inst.generators:
        p_max_avail = g.p_max
        if renewable_availability and g.id in renewable_availability:
            p_max_avail = min(p_max_avail, renewable_availability[g.id])
        p_max_i = int(round(p_max_avail * POWER_SCALE))
        p_min_i = int(round(g.p_min * POWER_SCALE)) if enforce_min_output else 0

        u = model.new_bool_var(f"u_{g.id}")
        p = model.new_int_var(0, p_max_i, f"p_{g.id}")
        # link p and u
        model.add(p <= p_max_i * u)
        if p_min_i > 0:
            model.add(p >= p_min_i * u)
        u_var[g.id] = u
        p_var[g.id] = p

    # ---- line flows ----
    flow_var: List[cp_model.IntVar] = []
    for i, ln in enumerate(inst.lines):
        cap = int(round(ln.capacity * POWER_SCALE))
        flow_var.append(model.new_int_var(-cap, cap, f"flow_{i}"))

    # ---- bus power balance ----
    for b_idx, bus in enumerate(inst.buses):
        gens_here = [p_var[g.id] for g in inst.gen_at_bus(b_idx)]
        in_flow, out_flow = [], []
        for i, ln in enumerate(inst.lines):
            if ln.to_bus == b_idx:
                in_flow.append(flow_var[i])
            if ln.from_bus == b_idx:
                out_flow.append(flow_var[i])
        load_i = int(round(loads[b_idx] * POWER_SCALE))
        model.add(sum(gens_here) + sum(in_flow) - sum(out_flow) == load_i)

    # ---- spinning reserve ----
    # sum over THERMAL units only (renewables provide no firm reserve)
    reserve_terms = []
    for g in inst.thermal_generators():
        p_max_i = int(round(g.p_max * POWER_SCALE))
        reserve_terms.append(p_max_i * u_var[g.id] - p_var[g.id])
    if reserve_terms:
        model.add(sum(reserve_terms) >= int(round(reserve_mw * POWER_SCALE)))

    # ---- piece-wise-linear cost ----
    cost_var: Dict[str, cp_model.IntVar] = {}
    for g in inst.generators:
        if g.kind != "thermal":
            cost_var[g.id] = model.new_constant(0)
            continue
        # upper bound on cost: a + b·p_max + c·p_max²
        ub = int(round(g.cost(g.p_max) * COST_SCALE * 1.05)) + 1
        c = model.new_int_var(0, ub, f"c_{g.id}")
        for slope, intercept in _pwl_tangents(g):
            # cost ≥ slope·p + intercept   (only when ON; else cost = 0)
            model.add(c >= slope * p_var[g.id] + intercept).only_enforce_if(u_var[g.id])
        model.add(c == 0).only_enforce_if(u_var[g.id].negated())
        cost_var[g.id] = c

    model.minimize(sum(cost_var.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = log_search

    status_code = solver.solve(model)
    status_map = {
        cp_model.OPTIMAL:    "OPTIMAL",
        cp_model.FEASIBLE:   "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN:    "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }
    status = status_map.get(status_code, "UNKNOWN")

    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        power = {g.id: solver.value(p_var[g.id]) / POWER_SCALE
                 for g in inst.generators}
        on    = {g.id: int(solver.value(u_var[g.id])) for g in inst.generators}
        flows = [solver.value(f) / POWER_SCALE for f in flow_var]
        total_cost = solver.objective_value / COST_SCALE
    else:
        power = {g.id: 0.0 for g in inst.generators}
        on    = {g.id: 0   for g in inst.generators}
        flows = [0.0] * len(inst.lines)
        total_cost = float("inf")

    return EconomicDispatchSolution(
        status=status, total_cost=total_cost,
        power=power, on=on, flows=flows,
        wall_time=solver.wall_time, network=inst, loads=list(loads),
    )
