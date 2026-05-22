"""Quick smoke test: run the three solvers on the toy network.

    python main.py            # full run (~2 min total)
    python main.py --fast     # ED only (a few seconds)
"""

from __future__ import annotations

import argparse, time, sys

from src import (
    three_bus_toy, six_bus_congested, ieee14,
    solve_economic_dispatch, solve_unit_commitment, solve_stochastic_uc,
    solar_profile, wind_profile, sample_scenarios,
)
from src.instance import add_renewables
from src.unit_commitment import daily_load_profile


def banner(text: str) -> None:
    line = "-" * (len(text) + 4)
    print(f"\n{line}\n  {text}\n{line}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fast", action="store_true",
                        help="run only single-period ED (skip UC and SUC)")
    parser.add_argument("--uc-time", type=int, default=30,
                        help="UC time limit in seconds (default: 30)")
    parser.add_argument("--suc-time", type=int, default=60,
                        help="Stochastic UC time limit (default: 60)")
    args = parser.parse_args(argv)

    banner("1. Economic Dispatch on three instances")
    for net in (three_bus_toy(300), six_bus_congested(), ieee14()):
        t0 = time.time()
        sol = solve_economic_dispatch(net, time_limit_s=10)
        print(f"  {net.name:<20}  cost=${sol.total_cost:>10,.2f}/h"
              f"  status={sol.status:<8}  t={time.time()-t0:.2f}s")

    if args.fast:
        return 0

    banner("2. Unit Commitment (24 h on toy)")
    net = three_bus_toy(300)
    load = daily_load_profile(net, H=24)
    uc = solve_unit_commitment(net, load, time_limit_s=args.uc_time)
    print(f"  status={uc.status}  cost=${uc.total_cost:,.2f}  "
          f"gap={uc.gap*100:.1f}%  t={uc.wall_time:.1f}s")

    banner("3. Stochastic UC (4 scenarios)")
    net_r = add_renewables(three_bus_toy(300),
                           wind_bus=0, solar_bus=2,
                           wind_cap=80, solar_cap=60)
    asset_means = {"WIND@0":  wind_profile(24),
                   "SOLAR@2": solar_profile(24)}
    scens = sample_scenarios(asset_means, n_scenarios=4, sigma=0.15, seed=42)
    sto = solve_stochastic_uc(net_r, load, scens, time_limit_s=args.suc_time)
    print(f"  status={sto.status}  E[cost]=${sto.expected_cost:,.2f}  "
          f"curtail={sto.expected_curtailment:.1f} MWh  "
          f"unserved={sto.expected_loadshed:.2f} MWh  "
          f"t={sto.wall_time:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
