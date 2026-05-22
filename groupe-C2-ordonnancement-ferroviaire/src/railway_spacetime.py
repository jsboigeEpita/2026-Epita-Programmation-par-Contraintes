"""
railway_spacetime.py
--------------------
Diagramme espace-temps (space-time diagram) pour visualiser la solution
d'un problème de timetabling ferroviaire PESP.

Toutes les lignes sur un seul graphique :
  - Axe X : temps (0 → T, périodique)
  - Axe Y : stations ordonnées globalement (tri topologique sur les routes)
  - Chaque ligne a sa couleur ; elle ne connecte que ses propres stations
  - Segments fantômes (wrap-around ±T) pour visualiser la périodicité
"""

from typing import Dict, Tuple, Optional, List
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

EventKey = Tuple[str, str, str]   # (line, station, "arr"|"dep")

LINE_COLORS = [
    "#E63946", "#2196F3", "#4CAF50", "#FF9800",
    "#9C27B0", "#00BCD4", "#FF5722", "#E91E63",
]


def _global_station_order(network) -> List[str]:
    """
    Ordre global des stations cohérent avec toutes les lignes,
    via tri topologique (Kahn) sur le graphe de précédence des routes.
    Si des cycles existent, les stations restantes sont insérées alphabétiquement.
    """
    from collections import defaultdict, deque

    stations = list(network.stations.keys())
    in_degree = {s: 0 for s in stations}
    adj = defaultdict(set)

    for route in network.lines.values():
        for i in range(len(route) - 1):
            a, b = route[i], route[i + 1]
            if b not in adj[a]:
                adj[a].add(b)
                in_degree[b] += 1

    queue = deque(sorted(s for s in stations if in_degree[s] == 0))
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in sorted(adj[node]):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    seen = set(order)
    for s in sorted(stations):
        if s not in seen:
            order.append(s)
    return order


def _draw_periodic_segment(ax, x0, x1, y0, y1, T, color, lw, alpha, zorder):
    """
    Dessine (x0,y0)→(x1,y1) avec gestion du wrap-around mod T.
    Copies fantômes en tiretés pour montrer la périodicité.
    """
    ghost = alpha * 0.18
    if x1 >= x0:
        ax.plot([x0, x1], [y0, y1], color=color, lw=lw, alpha=alpha,
                zorder=zorder, solid_capstyle="round")
        ax.plot([x0 + T, x1 + T], [y0, y1], color=color, lw=lw,
                alpha=ghost, linestyle="--", zorder=zorder - 1,
                solid_capstyle="round")
    else:
        # Wrap-around : découpage au bord T
        frac = (T - x0) / (T - x0 + x1)
        y_mid = y0 + frac * (y1 - y0)
        ax.plot([x0, T],  [y0, y_mid], color=color, lw=lw, alpha=alpha,
                zorder=zorder, solid_capstyle="round")
        ax.plot([0,  x1], [y_mid, y1], color=color, lw=lw, alpha=alpha,
                zorder=zorder, solid_capstyle="round")
        ax.plot([x0 - T, x1], [y0, y1], color=color, lw=lw,
                alpha=ghost, linestyle="--", zorder=zorder - 1)
        ax.plot([x0, x1 + T], [y0, y1], color=color, lw=lw,
                alpha=ghost, linestyle="--", zorder=zorder - 1)


def plot_spacetime(
    network,
    solution: Dict[EventKey, int],
    title: str = "Diagramme Espace-Temps",
    figsize: Optional[Tuple[float, float]] = None,
    show: bool = True,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Trace le diagramme espace-temps, toutes lignes superposées.

    Parameters
    ----------
    network : RailwayNetwork
    solution : dict  {(line, station, "arr"|"dep"): int}
    title, figsize, show, save_path : voir noms
    """
    T = network.T
    line_names = list(network.lines.keys())
    line_colors = {line: LINE_COLORS[i % len(LINE_COLORS)]
                   for i, line in enumerate(line_names)}

    # Ordre global Y
    station_order = _global_station_order(network)
    n_st = len(station_order)
    y_pos = {s: i for i, s in enumerate(station_order)}

    if figsize is None:
        figsize = (13, max(5, 1.2 * n_st + 2))

    fig, ax = plt.subplots(figsize=figsize, facecolor="#0f1117")
    ax.set_facecolor("#141820")
    fig.suptitle(title, color="white", fontsize=15, fontweight="bold",
                 fontfamily="monospace", y=0.98)

    # Axes
    ax.set_xlim(-1, T + 1)
    ax.set_ylim(-0.7, n_st - 0.3)
    ax.set_yticks(range(n_st))
    ax.set_yticklabels(station_order, color="white", fontsize=9,
                       fontfamily="monospace")
    ax.set_xlabel("Temps (min)", color="#aab4c8", fontsize=9,
                  fontfamily="monospace")
    ax.tick_params(axis="x", colors="#aab4c8", labelsize=8)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(max(5, T // 12)))
    for spine in ax.spines.values():
        spine.set_edgecolor("#2a3040")

    # Grille
    ax.grid(axis="x", color="#232d3f", lw=0.5, zorder=0)
    for i in range(n_st):
        ax.axhline(i, color="#1e2838", lw=0.8, zorder=1)

    # Frontières de période
    for xv, label in [(0, "0"), (T, "T")]:
        ax.axvline(xv, color="#4a5870", lw=1.2, linestyle="--", zorder=2)
        ax.text(xv, n_st - 0.42, label, color="#4a5870", fontsize=7.5,
                ha="center", fontfamily="monospace", zorder=3)

    # Tracé de chaque ligne
    lw = 2.0
    for line in line_names:
        color = line_colors[line]
        route = list(network.lines[line])

        # Trajets diagonaux
        for i in range(len(route) - 1):
            s_from, s_to = route[i], route[i + 1]
            x0 = solution[(line, s_from, "dep")]
            x1 = solution[(line, s_to,   "arr")]
            _draw_periodic_segment(ax, x0, x1, y_pos[s_from], y_pos[s_to],
                                   T, color, lw, 0.85, 4)

        # Événements par station
        for station in route:
            arr = solution[(line, station, "arr")]
            dep = solution[(line, station, "dep")]
            y   = y_pos[station]

            # Dwell
            if dep != arr:
                _draw_periodic_segment(ax, arr, dep, y, y, T,
                                       color, lw * 1.8, 0.95, 5)

            # Points
            ax.scatter([arr], [y], color=color, s=30, zorder=7,
                       edgecolors="white", linewidths=0.7)
            ax.scatter([dep], [y], color=color, s=18, zorder=7,
                       marker="D", edgecolors="white", linewidths=0.5)

            # Annotations
            ax.text(arr, y + 0.15, str(arr), color=color, fontsize=6,
                    ha="center", va="bottom", fontfamily="monospace", zorder=8)
            if dep != arr:
                ax.text(dep, y - 0.15, str(dep), color=color, fontsize=6,
                        ha="center", va="top", fontfamily="monospace", zorder=8)

    # Légende
    elems = [
        Line2D([0], [0], color=line_colors[line], lw=2, label=line)
        for line in line_names
    ]
    leg = ax.legend(handles=elems, loc="lower right", fontsize=9,
                    framealpha=0.25, facecolor="#1a2035", edgecolor="#3a4a6a",
                    labelcolor="white")

    plt.tight_layout(pad=1.2)

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        print(f"Sauvegardé : {save_path}")
    if show:
        plt.show()
    return fig


# --------------------------------------------------------------------------- #
# Demo                                                                         #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/mnt/user-data/uploads")

    from railway_generator import generate_railway_network
    from railway_solver import solve

    net = generate_railway_network(6, 3, 60, seed=1)
    solution = solve(net, time_limit_seconds=15.0)

    if solution:
        plot_spacetime(net, solution,
                       title="Diagramme Espace-Temps — seed=1",
                       show=False,
                       save_path="/mnt/user-data/outputs/spacetime.png")
    else:
        print("Pas de solution trouvée.")