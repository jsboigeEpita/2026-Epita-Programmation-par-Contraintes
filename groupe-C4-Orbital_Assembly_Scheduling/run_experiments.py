from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from src.experiments import BenchmarkConfig, export_results, run_benchmark, summarize
from src.baseline_greedy import solve_greedy
from src.instance_generator import generate_instance
from src.plotting import plot_benchmark_summary, plot_schedule, save_figure
from src.solver_cp_sat import solve_cpsat


def export_single_instance_comparison(project_dir: Path, fig_dir: Path) -> None:
    instance = generate_instance(n_modules=6, horizon=420, seed=22)
    cp_result = solve_cpsat(instance, time_limit_s=10.0, workers=8, seed=22)
    greedy_result = solve_greedy(instance)

    if cp_result.schedule is None or greedy_result.schedule is None:
        return

    fig, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    plot_schedule(cp_result.schedule, title="CP-SAT schedule", ax=axes[0])
    plot_schedule(greedy_result.schedule, title="Greedy schedule", ax=axes[1])
    plt.tight_layout()

    save_figure(fig, fig_dir / "single_instance_schedule_comparison.png")
    save_figure(fig, project_dir / "single_instance_schedule_comparison.png")
    plt.close(fig)


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    out_dir = project_dir / "results"
    fig_dir = out_dir / "figures"

    config = BenchmarkConfig(
        module_sizes=[4, 6, 8, 10, 12],
        seeds=[11, 22, 33, 44, 55],
        horizon=420,
        cp_time_limit_s=20.0,
        cp_workers=8,
    )

    raw = run_benchmark(config)
    summary = summarize(raw)
    export_results(raw, summary, out_dir)

    fig, _ = plot_benchmark_summary(summary)
    save_figure(fig, fig_dir / "benchmark_overview.png")
    save_figure(fig, project_dir / "benchmark_overview.png")
    plt.close(fig)

    export_single_instance_comparison(project_dir, fig_dir)

    print("Benchmark complete.")
    print(f"Raw results: {out_dir / 'benchmark_raw.csv'}")
    print(f"Summary    : {out_dir / 'benchmark_summary.csv'}")
    print(f"Figure     : {fig_dir / 'benchmark_overview.png'}")
    print(f"Root figure: {project_dir / 'benchmark_overview.png'}")
    print(f"Comparison : {project_dir / 'single_instance_schedule_comparison.png'}")


if __name__ == "__main__":
    main()
