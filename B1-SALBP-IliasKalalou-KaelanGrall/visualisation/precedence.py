import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.figure import Figure

from instances import Instance


def draw_precedence_graph(instance: Instance, figsize: tuple[int, int] = (14, 9)) -> Figure:
    graph = nx.DiGraph()
    for task in instance.tasks:
        graph.add_node(task, duration=instance.durations[task])
    graph.add_edges_from(instance.precedences)

    fig, ax = plt.subplots(figsize=figsize)
    pos = nx.spring_layout(graph, seed=42, k=1.8)
    labels = {t: f"{t}\n({instance.durations[t]})" for t in instance.tasks}

    nx.draw(
        graph,
        pos,
        ax=ax,
        with_labels=True,
        labels=labels,
        node_color="#4ECDC4",
        node_size=1300,
        font_size=10,
        font_weight="bold",
        edge_color="gray",
        arrows=True,
        arrowsize=18,
        edgecolors="black",
        width=1.4,
    )
    ax.set_title(
        f"Graphe de précédence — {instance.name} ({len(instance.tasks)} tâches, {len(instance.precedences)} précédences)",
        fontsize=13,
        fontweight="bold",
    )

    legend_handles = [
        mpatches.Patch(facecolor="#4ECDC4", edgecolor="black", label="Tâche (id / durée)"),
        plt.Line2D([0], [0], color="gray", lw=1.5, label="Précédence (A → B)"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        fontsize=10,
    )
    fig.subplots_adjust(right=0.80)
    return fig
