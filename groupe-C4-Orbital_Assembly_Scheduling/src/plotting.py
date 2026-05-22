from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _select_metric(summary: pd.DataFrame, preferred: str, fallback: str) -> tuple[str, str]:
    if preferred in summary.columns and summary[preferred].notna().any():
        return preferred, "paired feasible instances"
    return fallback, "all feasible instances"


def plot_schedule(schedule: pd.DataFrame, title: str = "Schedule", ax=None):
    if schedule is None or schedule.empty:
        raise ValueError("schedule is empty")

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 4))

    lanes = sorted(schedule["lane"].unique().tolist())
    lane_to_y = {lane: i for i, lane in enumerate(lanes)}
    colors = plt.cm.tab20(np.linspace(0, 1, max(3, len(lanes))))

    for _, row in schedule.iterrows():
        y = lane_to_y[int(row["lane"])]
        start = int(row["start"])
        duration = int(row["duration"])
        mode = str(row["mode"])
        alpha = 0.95 if mode == "fast" else 0.65
        ax.broken_barh([(start, duration)], (y - 0.35, 0.7), facecolors=colors[y], alpha=alpha)
        ax.text(start + 0.2, y, str(row["name"]), fontsize=7, va="center")

    ax.set_yticks(list(range(len(lanes))))
    ax.set_yticklabels([f"lane {lane}" for lane in lanes])
    ax.set_xlabel("Time (10-min slots)")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    return ax


def plot_benchmark_summary(summary: pd.DataFrame):
    if summary.empty:
        raise ValueError("summary is empty")

    fig, axes = plt.subplots(1, 3, figsize=(16, 4))

    cp_mk_col, mk_scope = _select_metric(summary, "cp_paired_mean_makespan", "cp_mean_makespan")
    gr_mk_col, _ = _select_metric(summary, "gr_paired_mean_makespan", "gr_mean_makespan")
    axes[0].plot(summary["n_modules"], summary[cp_mk_col], marker="o", label="CP-SAT")
    axes[0].plot(summary["n_modules"], summary[gr_mk_col], marker="o", label="Greedy")
    axes[0].set_title(f"Mean Makespan ({mk_scope})")
    axes[0].set_xlabel("Modules")
    axes[0].set_ylabel("Slots (10 min)")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    cp_fuel_col, fuel_scope = _select_metric(summary, "cp_paired_mean_total_fuel", "cp_mean_total_fuel")
    gr_fuel_col, _ = _select_metric(summary, "gr_paired_mean_total_fuel", "gr_mean_total_fuel")
    axes[1].plot(summary["n_modules"], summary[cp_fuel_col], marker="o", label="CP-SAT")
    axes[1].plot(summary["n_modules"], summary[gr_fuel_col], marker="o", label="Greedy")
    axes[1].set_title(f"Mean Fuel Consumption ({fuel_scope})")
    axes[1].set_xlabel("Modules")
    axes[1].set_ylabel("Delta-V units (10 m/s)")
    axes[1].grid(alpha=0.25)
    axes[1].legend()

    width = 0.35
    x = np.arange(len(summary))
    axes[2].bar(x - width / 2, summary["cp_feasible_rate"], width=width, label="CP-SAT")
    axes[2].bar(x + width / 2, summary["gr_feasible_rate"], width=width, label="Greedy")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(summary["n_modules"].tolist())
    axes[2].set_ylim(0.0, 1.05)
    axes[2].set_title("Feasibility Rate")
    axes[2].set_xlabel("Modules")
    axes[2].set_ylabel("Rate")
    axes[2].grid(axis="y", alpha=0.25)
    axes[2].legend()

    plt.tight_layout()
    return fig, axes


def save_figure(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
