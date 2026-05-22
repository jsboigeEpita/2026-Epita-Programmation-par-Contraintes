import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from instances import Instance, Solution


def draw_gantt(solution: Solution, instance: Instance, figsize: tuple[int, int] | None = None) -> Figure:
    stations = solution.stations
    n = len(stations)
    fig, ax = plt.subplots(figsize=figsize or (16, max(5, n * 0.9)))

    palette = plt.cm.Set3(np.linspace(0, 1, max(n, 1)))

    for idx, (station, task_list) in enumerate(sorted(stations.items())):
        x = 0
        for task in task_list:
            duration = instance.durations[task]
            ax.barh(
                station,
                duration,
                left=x,
                color=palette[idx % len(palette)],
                edgecolor="black",
                linewidth=1,
            )
            ax.text(
                x + duration / 2,
                station,
                f"T{task}\n({duration})",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
            x += duration

    ax.axvline(
        x=solution.cycle_time,
        color="red",
        linestyle="--",
        linewidth=1.5,
        label=f"Cycle time = {solution.cycle_time}",
    )
    ax.set_yticks(sorted(stations.keys()))
    ax.set_yticklabels([f"Station {s}" for s in sorted(stations.keys())], fontsize=11)
    ax.set_xlabel("Temps", fontsize=12)
    ax.set_title(
        f"{solution.variant} — {solution.solver} : {solution.n_stations} stations, cycle {solution.cycle_time}",
        fontsize=13,
        fontweight="bold",
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0.0, fontsize=10)
    ax.invert_yaxis()
    fig.subplots_adjust(right=0.82)
    return fig
