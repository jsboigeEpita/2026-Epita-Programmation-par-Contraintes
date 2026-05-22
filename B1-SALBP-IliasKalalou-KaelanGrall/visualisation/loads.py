import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from instances import Instance, Solution


def draw_station_loads(solution: Solution, instance: Instance, figsize: tuple[int, int] = (14, 7)) -> Figure:
    stations = sorted(solution.stations.keys())
    loads = [solution.station_load(s, instance.durations) for s in stations]
    mean_load = float(np.mean(loads)) if loads else 0.0

    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.bar(
        [f"S{s}" for s in stations],
        loads,
        color="#4ECDC4",
        edgecolor="black",
        linewidth=1.2,
    )
    ax.axhline(
        y=solution.cycle_time,
        color="red",
        linestyle="--",
        linewidth=1.5,
        label=f"Cycle time = {solution.cycle_time}",
    )
    ax.axhline(
        y=mean_load,
        color="gray",
        linestyle=":",
        linewidth=1.5,
        label=f"Charge moyenne = {mean_load:.1f}",
    )

    for bar, load in zip(bars, loads):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.25,
            str(load),
            ha="center",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_ylabel("Charge cumulée", fontsize=12)
    ax.set_xlabel("Station", fontsize=12)
    ax.set_title("Charge par station", fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0.0, fontsize=10)
    fig.subplots_adjust(right=0.80)
    return fig
