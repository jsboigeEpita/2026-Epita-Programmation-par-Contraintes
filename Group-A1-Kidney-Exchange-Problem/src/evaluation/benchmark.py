"""
KEP solver benchmark.

Compares CP-SAT, PLNE, and Greedy solvers across instance sizes,
producing performance tables and charts.

Usage from notebook:
    from src.evaluation.benchmark import run_benchmark, plot_results
    df = run_benchmark(sizes=[10, 20, 30, 50], n_seeds=5)
    plot_results(df)
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from src.data.generator import make_random_kep
from src.models.base import KidneyExchangeSolver, SolverResult
from src.models.cpsat_model import CPSatSolver
from src.models.PLNE import PLNESolver
from src.models.greedy import GreedySolver
from src.core.graph import KEPGraph


# ---------------------------------------------------------------------------
# Benchmark row
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkRow:
    """Single row in the benchmark results table."""
    solver: str
    n_pairs: int
    n_ndd: int
    seed: int
    max_cycle_size: int
    with_chains: bool
    status: str
    n_transplants: int
    objective_value: float
    wall_time_s: float
    n_cycles: int
    n_chains: int
    # Optional fields (CP-SAT / MILP only)
    n_cycles_enumerated: int = 0
    n_chains_enumerated: int = 0

    def to_dict(self) -> dict:
        return self.__dict__

def run_benchmark(
    sizes: list[int] = (10, 20, 30, 50),
    n_seeds: int = 5,
    max_cycle_size: int = 3,
    n_ndd: int = 2,
    with_chains: bool = True,
    time_limit: float = 30.0,
    solvers: list[str] = ("cpsat", "plne", "greedy-weight", "greedy-size"),
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Run all solvers on multiple instances and return a results DataFrame.

    Args:
        sizes:          Instance sizes (number of pairs).
        n_seeds:        Seeds per size (for statistical robustness).
        max_cycle_size: Maximum cycle length.
        n_ndd:          Number of NDDs per instance.
        with_chains:    Whether to include altruistic chains.
        time_limit:     Per-run time limit in seconds.
        solvers:        Solvers to include. Valid values:
                        'cpsat', 'plne', 'greedy-weight', 'greedy-size', 'greedy-density'.
        verbose:        Print progress to stdout.

    Returns:
        DataFrame with one row per (solver, instance) combination.
    """
    rows: list[BenchmarkRow] = []

    for n in sizes:
        for seed in range(n_seeds):
            kep = make_random_kep(
                n_pairs=n,
                n_ndd=n_ndd if with_chains else 0,
                seed=seed,
                max_cycle_size=max_cycle_size,
                max_chain_length=max_cycle_size,
            )

            if verbose:
                print(f"  Instance n={n:3d}, seed={seed} | {kep}")

            for solver_name in solvers:
                solver = _build_solver(solver_name, kep, max_cycle_size, with_chains)
                if solver is None:
                    continue

                try:
                    result = solver.solve(time_limit=time_limit)
                except Exception as exc:
                    warnings.warn(f"[{solver_name}] n={n} seed={seed} ERROR: {exc}")
                    result = SolverResult(
                        status="ERROR",
                        solver_name=solver_name,
                    )

                row = BenchmarkRow(
                    solver=solver.name,
                    n_pairs=n,
                    n_ndd=n_ndd if with_chains else 0,
                    seed=seed,
                    max_cycle_size=max_cycle_size,
                    with_chains=with_chains,
                    status=result.status,
                    n_transplants=result.n_transplants,
                    objective_value=result.objective_value,
                    wall_time_s=result.wall_time,
                    n_cycles=len(result.cycles),
                    n_chains=len(result.chains),
                    n_cycles_enumerated=result.metadata.get("n_cycles_enumerated", 0),
                    n_chains_enumerated=result.metadata.get("n_chains_enumerated", 0),
                )
                rows.append(row)

                if verbose:
                    print(
                        f"    [{solver.name:<22s}] "
                        f"status={result.status:<10s} "
                        f"transplants={result.n_transplants:3d} "
                        f"time={result.wall_time:.3f}s"
                    )

    df = pd.DataFrame([r.to_dict() for r in rows])
    return df


def _build_solver(
    name: str,
    kep: KEPGraph,
    max_cycle_size: int,
    with_chains: bool,
) -> KidneyExchangeSolver | None:
    """
    Instantiate a solver by name.

    Args:
        name:           Solver identifier (e.g. 'cpsat', 'plne', 'greedy-weight').
        kep:            KEP graph instance to solve.
        max_cycle_size: Maximum allowed cycle length.
        with_chains:    Whether to enable altruistic donor chains.

    Returns:
        A configured solver instance, or None if the name is unrecognised.
    """
    if name == "cpsat":
        s = CPSatSolver(kep, max_cycle_size=max_cycle_size)
        if with_chains:
            s.enable_altruists()
        return s

    if name == "plne":
        s = PLNESolver(kep, max_cycle_size=max_cycle_size)
        if with_chains:
            s.enable_altruists()
        return s

    if name.startswith("greedy-"):
        strategy = name.split("-", 1)[1]   # 'weight', 'size', or 'density'
        s = GreedySolver(kep, max_cycle_size=max_cycle_size, strategy=strategy)
        if with_chains:
            s.enable_altruists()
        return s

    warnings.warn(f"Unknown solver: {name}")
    return None

def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate results by solver and instance size (mean ± std).

    Args:
        df: DataFrame returned by run_benchmark().

    Returns:
        Aggregated DataFrame with columns: solver, n_pairs,
        n_transplants_mean, n_transplants_std, wall_time_mean,
        wall_time_std, feasible_rate.
    """
    df = df.copy()
    df["feasible"] = df["status"].isin(["OPTIMAL", "FEASIBLE"]).astype(int)

    agg = (
        df.groupby(["solver", "n_pairs"])
        .agg(
            n_transplants_mean=("n_transplants", "mean"),
            n_transplants_std=("n_transplants", "std"),
            wall_time_mean=("wall_time_s", "mean"),
            wall_time_std=("wall_time_s", "std"),
            feasible_rate=("feasible", "mean"),
        )
        .reset_index()
    )
    return agg


def optimality_gap(df: pd.DataFrame, optimal_solver: str = "CP-SAT") -> pd.DataFrame:
    """
    Compute each solver's relative gap against a reference optimal solver.

    gap = (optimal - solver) / optimal  (in %)

    Args:
        df:             DataFrame returned by run_benchmark().
        optimal_solver: Name prefix of the reference solver (column 'solver').

    Returns:
        Input DataFrame with an added 'gap_pct' column.
    """
    opt = (
        df[df["solver"].str.startswith(optimal_solver)]
        [["n_pairs", "seed", "n_transplants"]]
        .rename(columns={"n_transplants": "n_transplants_opt"})
    )
    merged = df.merge(opt, on=["n_pairs", "seed"], how="left")
    merged["gap_pct"] = (
        (merged["n_transplants_opt"] - merged["n_transplants"])
        / merged["n_transplants_opt"].replace(0, float("nan"))
        * 100
    )
    return merged


def verify_solution(result: SolverResult, kep: KEPGraph) -> list[str]:
    """
    Check the integrity of a KEP solution.

    Validates:
    - No pair is assigned twice (disjointness).
    - Every arc in each cycle/chain exists in the graph.
    - No cycle exceeds max_cycle_size.

    Args:
        result: SolverResult to verify.
        kep:    KEP graph used for solving.

    Returns:
        List of error messages; empty if the solution is valid.
    """
    errors: list[str] = []
    seen: set[int] = set()

    # -- Cycle checks
    for cycle in result.cycles:
        if len(cycle) > kep.max_cycle_size:
            errors.append(f"Cycle {cycle} exceeds max_cycle_size={kep.max_cycle_size}")

        for node in cycle:
            if node in seen:
                errors.append(f"Node {node} assigned twice (cycle).")
            seen.add(node)

        for k in range(len(cycle)):
            u, v = cycle[k], cycle[(k + 1) % len(cycle)]
            if not kep.graph.has_edge(u, v):
                errors.append(f"Arc ({u}→{v}) not in graph (cycle).")

    # -- Chain checks
    for chain in result.chains:
        # The NDD (chain[0]) may only appear once as the chain head.
        ndd_id = chain[0]
        if ndd_id in seen:
            errors.append(f"NDD {ndd_id} used in multiple chains.")
        seen.add(ndd_id)

        for node in chain[1:]:
            if node in seen:
                errors.append(f"Node {node} assigned twice (chain).")
            seen.add(node)

        for k in range(len(chain) - 1):
            u, v = chain[k], chain[k + 1]
            if not kep.graph.has_edge(u, v):
                errors.append(f"Arc ({u}→{v}) not in graph (chain).")

    return errors