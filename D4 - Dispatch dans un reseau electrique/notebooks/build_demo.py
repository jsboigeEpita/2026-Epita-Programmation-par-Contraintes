"""Generate the demo.ipynb notebook programmatically."""

import json, sys, os, pathlib

NB = {"cells": [], "metadata": {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"}
}, "nbformat": 4, "nbformat_minor": 5}


def md(text):
    NB["cells"].append({"cell_type": "markdown", "metadata": {}, "source": text.split("\n")})


def code(text):
    src = text.split("\n")
    src = [s + "\n" for s in src[:-1]] + ([src[-1]] if src[-1] else [])
    NB["cells"].append({
        "cell_type": "code", "metadata": {}, "execution_count": None,
        "outputs": [], "source": src,
    })


md("""# D4 — Economic Dispatch in a Power Network
## CP-SAT models for Economic Dispatch, Unit Commitment, and Stochastic UC

**EPITA SCIA 2026 — Programmation par Contraintes**
*Martin Couturier · Arthur Philippe · Xavier Ghostine*

---

This notebook walks through everything the `src/` package can do:

1. **Single-period Economic Dispatch** — find the cheapest way to meet demand right now, given line constraints.
2. **6-bus congested instance** — show that the optimal solution differs from the merit-order solution when the grid is congested.
3. **IEEE 14-bus** — a standard test case (5 generators, 20 branches).
4. **Daily Unit Commitment** — schedule start-ups and shut-downs over 24 hours.
5. **Renewable scenarios** — sample wind/solar profiles.
6. **Stochastic UC** — first-stage commitment hedged against scenario uncertainty.

The full mathematical model is in the [README](../README.md).""")


code("""# Make src importable regardless of CWD
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent))

%matplotlib inline
import matplotlib.pyplot as plt
plt.rcParams['figure.dpi'] = 110

from src import (
    Generator, Bus, Line, PowerNetwork,
    three_bus_toy, six_bus_congested, ieee14,
    solve_economic_dispatch, solve_unit_commitment, solve_stochastic_uc,
    solar_profile, wind_profile, sample_scenarios,
)
from src.instance import add_renewables
from src.unit_commitment import daily_load_profile
from src import visualization as viz
print("Package loaded.")""")


md("""## 1 · Single-period Economic Dispatch — toy 3-bus network

We start with a small system: a remote power plant (Bus 0), a city
(Bus 1, 120 MW load) and another city (Bus 2, 180 MW load). Three thermal
generators with very different cost structures:

| Gen | Bus | Min/Max (MW) | Cost (\\$/h) | Comment |
|-----|----:|-------------:|------------:|---------|
| G1-base   | 0 | 50 / 250 | 300 + 18·P + 0.0040·P² | cheap baseload |
| G2-mid    | 1 | 20 / 120 | 200 + 25·P + 0.0080·P² | mid-merit |
| G3-peaker | 2 | 10 /  80 | 100 + 40·P + 0.0150·P² | expensive peaker |

The CP-SAT model finds the per-generator output `P[g]` minimising fuel cost.""")


code("""net = three_bus_toy(peak_load=300)

fig = viz.plot_network(net, layout={0:(-1.5, 0), 1:(0, 0), 2:(1.5, 0)},
                       title='3-bus toy network')
plt.show()""")


code("""sol = solve_economic_dispatch(net, time_limit_s=10)
print(sol.report())""")


code("""fig = viz.plot_single_period(sol)
plt.show()""")


md("""**Reading the result.** The cheapest unit (G1, $18 + 0.004 P$) takes the
bulk of the load; the peaker (G3) only fills the deficit. The 10 % spinning
reserve (default) means total ON capacity must exceed total load by 30 MW —
that's why G2 stays on even when its output is small.""")


md("""## 2 · A congested 6-bus instance — when transmission matters

The CP-SAT formulation distinguishes itself from a pure merit-order rule when
the grid is congested. Here we use a 6-bus instance with cheap coal in the
North, mid-cost gas in the middle and expensive peakers near the southern load.
The North-to-South path is throttled by a 70 MW link (`L3`).""")


code("""net6 = six_bus_congested()
sol6 = solve_economic_dispatch(net6, time_limit_s=10)
print(sol6.report())
print(f'\\nMerit-order baseline (ignoring lines): ${sol6.merit_order_cost():,.2f}/h')
print(f'Transmission premium:                  ${sol6.total_cost - sol6.merit_order_cost():,.2f}/h '
      f'(+{100*(sol6.total_cost/sol6.merit_order_cost()-1):.1f}%)')""")


code("""layout6 = {0:(-1.2,  1.0), 1:( 0.0,  1.4), 2:(-1.0, 0.0),
           3:( 1.0,  0.0), 4:( 0.2, -1.2), 5:( 1.5, -1.2)}
fig = viz.plot_network(net6, flows=sol6.flows, layout=layout6,
                       title=f'6-bus dispatch — cost ${sol6.total_cost:,.0f}/h '
                              '(red lines = saturated)')
plt.show()""")


md("""Lines `L0` (B0→B1), `L3` (B2→B3) and `L5` (B3→B5) hit their capacity. As a
consequence, the cheap coal plant is dispatched well below its `p_max` and
the expensive southern peakers are forced ON — the **dispatch is no longer
merit-order**. This is the key value of CP-SAT over a naive rule.""")


md("""## 3 · IEEE 14-bus standard test case

We now switch to the classical IEEE 14-bus system: 5 generators across the
network, 20 transmission branches, ~260 MW of load. The model is solved to
optimality in well under a second.""")


code("""net14 = ieee14()
sol14 = solve_economic_dispatch(net14, time_limit_s=10)
print(sol14.report())""")


code("""# Bus layout taken from the canonical IEEE 14-bus diagram
layout14 = {
    0:(-2.5,  2.5), 1:(-2.0,  3.5), 2:( 0.0,  4.0), 3:( 1.5,  2.0),
    4:(-1.0,  1.5), 5:( 2.5,  0.0), 6:( 3.0,  3.0), 7:( 3.5,  4.5),
    8:( 1.5,  0.0), 9:( 1.0, -1.0), 10:(2.0, -1.5), 11:(3.0, -1.5),
    12:(3.5, -0.5), 13:(2.0,  1.0),
}
fig = viz.plot_network(net14, flows=sol14.flows, layout=layout14,
                       title=f'IEEE 14-bus dispatch — cost ${sol14.total_cost:,.0f}/h')
plt.show()""")


md("""## 4 · Daily Unit Commitment

Optimising one hour at a time misses the temporal coupling: minimum-up times,
ramp limits, and start-up costs all force decisions that look sub-optimal on
their own but pay off across the day.

The full **Unit Commitment** (UC) problem adds for every generator and every
hour:

* a binary status `u[g,t]` (ON/OFF),
* indicator variables `su[g,t]`, `sd[g,t]` for the change of status,
* minimum-up / minimum-down constraints,
* ramp limits between consecutive hours,
* a fuel-cost approximation via tangents (convex quadratic).

For the toy network, a smooth daily load curve (peak at 19 h, minimum at 04 h)
is generated, then the UC is solved over 24 hours.""")


code("""net  = three_bus_toy(peak_load=300)
load = daily_load_profile(net, H=24, peak_factor=1.3, off_peak_factor=0.55,
                          peak_hour=19)

uc = solve_unit_commitment(net, load, time_limit_s=40)
print(uc.report())""")


code("""fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                         gridspec_kw=dict(height_ratios=[3, 1]))
viz.plot_dispatch_stack(uc, ax=axes[0])
viz.plot_schedule(uc, ax=axes[1])
plt.tight_layout(); plt.show()""")


code("""fig = viz.plot_line_loadings(uc, top_k=4)
plt.show()
fig = viz.plot_cost_breakdown(uc)
plt.show()""")


md("""**What the schedule shows.** G1 (the cheap baseload) runs the whole day.
G2 starts at midnight, shuts off through the morning trough, then restarts
mid-afternoon to cover the evening peak. G3 (the peaker) is only ON during
the steepest part of the peak — turning it on once costs $150 but produces
energy worth more than that to avoid violating reserve.""")


md("""## 5 · Renewable generation scenarios

Real grids increasingly rely on wind and solar — both intermittent. We model
their hourly availability as a stochastic process: a deterministic mean
profile (bell curve for solar, gentle diurnal for wind) plus AR(1) noise.""")


code("""asset_means = {
    'WIND@0':  wind_profile(24),
    'SOLAR@2': solar_profile(24),
}
scens = sample_scenarios(asset_means, n_scenarios=8, sigma=0.18, seed=11)

fig, axes = plt.subplots(1, 2, figsize=(13, 4))
viz.plot_scenarios(scens, 'WIND@0',  capacity_mw=80,
                   mean_profile=asset_means['WIND@0'], ax=axes[0])
viz.plot_scenarios(scens, 'SOLAR@2', capacity_mw=60,
                   mean_profile=asset_means['SOLAR@2'], ax=axes[1])
plt.tight_layout(); plt.show()""")


md("""## 6 · Two-stage Stochastic Unit Commitment

Now combine commitment and uncertainty. The grid operator must commit
thermal units **before** observing the actual wind/solar realisation. The
power output is then re-optimised per scenario.

The CP-SAT model has:

* one set of first-stage variables  `u[g,t], su[g,t], sd[g,t]`  (shared);
* one set of second-stage variables  `p[g,t,s]`  per scenario;
* expected fuel cost as the objective, plus a load-shedding penalty
  (`$5 000/MWh`) and a curtailment penalty (`$50/MWh`).

We add a wind farm at Bus 0 and a solar plant at Bus 2 to the toy network,
re-use the same load profile, and run with 4 scenarios.""")


code("""net_r = add_renewables(three_bus_toy(peak_load=300),
                       wind_bus=0, solar_bus=2,
                       wind_cap=80, solar_cap=60)
asset_means = {'WIND@0':  wind_profile(24),
               'SOLAR@2': solar_profile(24)}
scens = sample_scenarios(asset_means, n_scenarios=4, sigma=0.15, seed=42)

sto = solve_stochastic_uc(net_r, load, scens, time_limit_s=60)
print(sto.report())""")


code("""# Plot per-scenario dispatch (each scenario as a small subplot)
fig, axes = plt.subplots(2, 2, figsize=(13, 7), sharex=True, sharey=True)
import numpy as np
xs = np.arange(sto.horizon)
for s, ax in enumerate(axes.flat):
    bottom = np.zeros(sto.horizon)
    for i, g in enumerate(net_r.generators):
        ys = np.array(sto.power[g.id][s])
        ax.fill_between(xs, bottom, bottom + ys,
                        color=viz._gen_color(net_r, g.id, i), alpha=0.85,
                        step='post', label=g.id if s == 0 else None)
        bottom += ys
    ax.step(xs, [sum(r) for r in load], where='post',
            color='black', linewidth=1.6, linestyle='--')
    ax.set_title(f'Scenario {s+1}  (prob={sto.probabilities[s]:.2f})')
    ax.grid(alpha=0.3)
axes[0,0].legend(fontsize=7, loc='upper left')
fig.text(0.5, 0.04, 'Hour', ha='center'); fig.text(0.04, 0.5, 'Power (MW)',
        va='center', rotation='vertical')
fig.suptitle('Stochastic UC — per-scenario dispatch (same commitment)')
plt.tight_layout(rect=[0.05, 0.05, 1, 0.96]); plt.show()""")


md("""## 7 · Deterministic vs stochastic — value of the stochastic solution

A standard sanity check is to compare:

* **Mean-value problem (MVP).** Deterministic UC where renewables are pinned
  at their *expected* profile — i.e. assume the forecast is the truth.
* **Stochastic UC.** Same horizon, but the commitment is hedged against the
  whole scenario set.

Both numbers come from the integer-objective CP-SAT solver under the same
30-60 s budget, so neither is necessarily globally optimal — but the
comparison is informative: when the stochastic cost is close to the MVP
cost, the operator gains little by modelling uncertainty (the system has
enough firm capacity to absorb it). When the stochastic cost is **higher**,
the gap is the *value of the stochastic solution* (VSS) — the price of
ignoring uncertainty when committing.""")


code("""# Mean-value problem: run a deterministic UC with renewables at their mean availability
det_avail = {gid: [cf * (80 if 'WIND' in gid else 60) for cf in cfs]
             for gid, cfs in asset_means.items()}
det_uc = solve_unit_commitment(net_r, load, availability=det_avail, time_limit_s=40)
print(f'Mean-value-problem UC cost           : ${det_uc.total_cost:,.2f}')
print(f'Stochastic UC (expected cost, 4 scen): ${sto.expected_cost:,.2f}')
delta = sto.expected_cost - det_uc.total_cost
print(f'Δ                                    : ${delta:+,.2f}'
      f'   ({\"VSS-positive\" if delta > 0 else \"≤ MVP — uncertainty cheap on this instance\"})')""")


md("""## 8 · Scaling — wall-clock as the network grows

Quick smoke test of solve times on the three instances.""")


code("""import time
print(f'{\"instance\":<22}{\"buses\":>7}{\"gens\":>6}{\"load(MW)\":>11}'
      f'{\"cost($/h)\":>12}{\"time(s)\":>10}{\"status\":>11}')
for net in (three_bus_toy(300), six_bus_congested(), ieee14()):
    t0 = time.time()
    s = solve_economic_dispatch(net, time_limit_s=30)
    dt = time.time() - t0
    print(f'{net.name:<22}{len(net.buses):>7}{len(net.generators):>6}'
          f'{net.total_load():>11.0f}{s.total_cost:>12,.0f}'
          f'{dt:>10.2f}{s.status:>11}')""")


md("""## 9 · Going further

The package supports several extensions that didn't make it into this short
demo but are exposed in `src/`:

* **Custom networks.** Build any `PowerNetwork` from scratch by listing buses,
  lines and generators (see `src/instance.py`).
* **Reserve schedules.** Pass `reserve_profile=[…]` (MW per hour) to UC and
  stochastic UC.
* **Renewable availability.** Pass `availability={"WIND@0": [...]}` to the
  deterministic UC to study a single forecast.
* **Different time horizons.** Both UC and stochastic UC accept any
  `load_profile` length — try `H = 48` for two days.
* **Solver tuning.** All solvers accept `time_limit_s`, `workers`, and
  `log_search` parameters that map to CP-SAT `CpSolver` parameters.

For the full mathematical formulation and an architecture diagram, see
[`README.md`](../README.md).""")

# write
out = pathlib.Path(__file__).parent / "demo.ipynb"
out.write_text(json.dumps(NB, indent=1))
print(f"Wrote {out}")
