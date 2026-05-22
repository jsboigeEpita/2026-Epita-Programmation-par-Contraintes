from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import numpy as np
import pandas as pd

from .baseline_greedy import solve_greedy
from .instance_generator import generate_instance
from .solver_cp_sat import solve_cpsat
from .validation import validate_schedule


@dataclass(frozen=True)
class BenchmarkConfig:
    module_sizes: List[int]
    seeds: List[int]
    horizon: int = 420
    cp_time_limit_s: float = 20.0
    cp_workers: int = 8


def run_single(
    n_modules: int,
    seed: int,
    horizon: int = 420,
    cp_time_limit_s: float = 20.0,
    cp_workers: int = 8,
) -> dict:
    adaptive_horizon = max(horizon, 120 + 30 * n_modules)
    instance = generate_instance(n_modules=n_modules, horizon=adaptive_horizon, seed=seed)

    cp = solve_cpsat(
        instance=instance,
        time_limit_s=cp_time_limit_s,
        workers=cp_workers,
        seed=seed,
    )
    gr = solve_greedy(instance)

    cp_valid = validate_schedule(instance, cp.schedule) if cp.schedule is not None else {"feasible": False, "violations": ["no schedule"]}
    gr_valid = validate_schedule(instance, gr.schedule) if gr.schedule is not None else {"feasible": False, "violations": ["no schedule"]}

    return {
        "instance_name": instance.name,
        "n_modules": n_modules,
        "n_maneuvers": instance.n(),
        "seed": seed,
        "cp_status": cp.status,
        "cp_feasible": cp.feasible,
        "cp_valid": bool(cp_valid["feasible"]),
        "cp_objective": cp.objective,
        "cp_makespan": cp.makespan,
        "cp_total_fuel": cp.total_fuel,
        "cp_time_s": cp.wall_time_s,
        "gr_status": gr.status,
        "gr_feasible": gr.feasible,
        "gr_valid": bool(gr_valid["feasible"]),
        "gr_objective": gr.objective,
        "gr_makespan": gr.makespan,
        "gr_total_fuel": gr.total_fuel,
        "gr_time_s": gr.wall_time_s,
    }


def run_benchmark(config: BenchmarkConfig) -> pd.DataFrame:
    rows = []
    for n_modules in config.module_sizes:
        for seed in config.seeds:
            rows.append(
                run_single(
                    n_modules=n_modules,
                    seed=seed,
                    horizon=config.horizon,
                    cp_time_limit_s=config.cp_time_limit_s,
                    cp_workers=config.cp_workers,
                )
            )
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    def _nanmean(x: Iterable[float]) -> float:
        arr = np.asarray(list(x), dtype=float)
        if arr.size == 0:
            return np.nan
        valid = arr[~np.isnan(arr)]
        if valid.size == 0:
            return np.nan
        return float(valid.mean())

    summary = (
        df.groupby("n_modules", as_index=False)
        .agg(
            instances=("instance_name", "count"),
            cp_feasible_rate=("cp_feasible", "mean"),
            cp_valid_rate=("cp_valid", "mean"),
            cp_mean_makespan=("cp_makespan", _nanmean),
            cp_mean_total_fuel=("cp_total_fuel", _nanmean),
            cp_mean_time_s=("cp_time_s", _nanmean),
            gr_feasible_rate=("gr_feasible", "mean"),
            gr_valid_rate=("gr_valid", "mean"),
            gr_mean_makespan=("gr_makespan", _nanmean),
            gr_mean_total_fuel=("gr_total_fuel", _nanmean),
            gr_mean_time_s=("gr_time_s", _nanmean),
        )
        .sort_values("n_modules")
        .reset_index(drop=True)
    )

    paired = df[
        (df["cp_valid"])
        & (df["gr_valid"])
        & df["cp_makespan"].notna()
        & df["gr_makespan"].notna()
        & df["cp_total_fuel"].notna()
        & df["gr_total_fuel"].notna()
    ].copy()
    if not paired.empty:
        paired["makespan_gain_pct"] = 100.0 * (
            (paired["gr_makespan"] - paired["cp_makespan"]) / paired["gr_makespan"]
        )
        paired["fuel_gain_pct"] = 100.0 * (
            (paired["gr_total_fuel"] - paired["cp_total_fuel"]) / paired["gr_total_fuel"]
        )
        paired_summary = (
            paired.groupby("n_modules", as_index=False)
            .agg(
                paired_instances=("instance_name", "count"),
                cp_paired_mean_makespan=("cp_makespan", _nanmean),
                gr_paired_mean_makespan=("gr_makespan", _nanmean),
                cp_paired_mean_total_fuel=("cp_total_fuel", _nanmean),
                gr_paired_mean_total_fuel=("gr_total_fuel", _nanmean),
                mean_makespan_gain_pct=("makespan_gain_pct", _nanmean),
                mean_fuel_gain_pct=("fuel_gain_pct", _nanmean),
            )
        )
        summary = summary.merge(paired_summary, on="n_modules", how="left")
    else:
        summary["paired_instances"] = 0
        summary["cp_paired_mean_makespan"] = np.nan
        summary["gr_paired_mean_makespan"] = np.nan
        summary["cp_paired_mean_total_fuel"] = np.nan
        summary["gr_paired_mean_total_fuel"] = np.nan
        summary["mean_makespan_gain_pct"] = np.nan
        summary["mean_fuel_gain_pct"] = np.nan

    return summary


def export_results(df: pd.DataFrame, summary: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "benchmark_raw.csv", index=False)
    summary.to_csv(out_dir / "benchmark_summary.csv", index=False)
