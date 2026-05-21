import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from solvers.biobjective import ParetoFront


def draw_pareto_front(front: ParetoFront, cycle_imposed: int | None = None,
                      figsize: tuple[int, int] = (12, 6)) -> Figure:
    fig, ax = plt.subplots(figsize=figsize)

    if not front.points:
        ax.text(0.5, 0.5, "Aucun point Pareto trouvé",
                ha="center", va="center", fontsize=14)
        return fig

    xs = [p.n_stations for p in front.points]
    ys = [p.cycle_time for p in front.points]

    ax.plot(xs, ys, "o-", linewidth=2, markersize=10,
            color="#1E3A8A", markerfacecolor="#1E3A8A",
            markeredgecolor="white", markeredgewidth=2,
            label="Front de Pareto")

    for p in front.points:
        annotation = f"  m={p.n_stations}, C={p.cycle_time}"
        ax.annotate(annotation, (p.n_stations, p.cycle_time),
                    xytext=(8, -4), textcoords="offset points",
                    fontsize=10, color="#0F172A")

    if cycle_imposed is not None:
        ax.axhline(y=cycle_imposed, color="red", linestyle="--",
                   linewidth=1.5,
                   label=f"Cycle de référence = {cycle_imposed}")

    ax.set_xlabel("Nombre de stations  m", fontsize=12)
    ax.set_ylabel("Cycle time minimal  C", fontsize=12)
    ax.set_title(
        f"Front de Pareto — instance {front.instance_name}",
        fontsize=13, fontweight="bold",
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=10)
    ax.set_xticks(xs)
    fig.tight_layout()
    return fig
