"""
railway_visualizer.py
---------------------
Visualisation graphique d'un réseau ferroviaire (RailwayNetwork).

Fonctionnalités
---------------
- Nœuds = stations (avec le nombre de quais affiché)
- Arcs colorés par ligne (avec légende)
- Arcs parallèles si plusieurs lignes partagent un tronçon
- Arc noir pointillé = voie unique (sens unique), continu = double voie
- Layout automatique via NetworkX spring layout
"""

import math
import itertools
import collections
from typing import Optional

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
import networkx as nx

# Palette de couleurs distinctes pour les lignes
LINE_COLORS = [
    "#E63946",  # rouge vif
    "#2196F3",  # bleu
    "#4CAF50",  # vert
    "#FF9800",  # orange
    "#9C27B0",  # violet
    "#00BCD4",  # cyan
    "#FF5722",  # orange foncé
    "#795548",  # marron
    "#607D8B",  # gris bleu
    "#E91E63",  # rose
    "#CDDC39",  # lime
    "#009688",  # teal
]


def _curved_arrow(
    ax,
    p1: np.ndarray,
    p2: np.ndarray,
    offset: float,
    color: str,
    lw: float = 2.5,
    alpha: float = 0.85,
    zorder: int = 3,
) -> None:
    """
    Dessine un arc courbé entre p1 et p2 avec un décalage latéral `offset`.
    L'arc est une courbe de Bézier quadratique.
    """
    mid = (p1 + p2) / 2.0
    direction = p2 - p1
    length = np.linalg.norm(direction)
    if length < 1e-9:
        return
    perp = np.array([-direction[1], direction[0]]) / length
    ctrl = mid + perp * offset

    # Paramétrique Bézier quadratique : 50 points
    t = np.linspace(0, 1, 60)
    curve = (
        np.outer((1 - t) ** 2, p1)
        + np.outer(2 * (1 - t) * t, ctrl)
        + np.outer(t ** 2, p2)
    )
    ax.plot(
        curve[:, 0],
        curve[:, 1],
        color=color,
        lw=lw,
        alpha=alpha,
        zorder=zorder,
        solid_capstyle="round",
    )
    # Petite flèche à l'arrivée
    dx = curve[-1, 0] - curve[-2, 0]
    dy = curve[-1, 1] - curve[-2, 1]
    ax.annotate(
        "",
        xy=curve[-1],
        xytext=curve[-3],
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw * 0.8,
            mutation_scale=10,
        ),
        zorder=zorder,
    )


def _draw_segment_base(
    ax,
    p1: np.ndarray,
    p2: np.ndarray,
    single_track: bool,
    zorder: int = 2,
) -> None:
    """
    Dessine l'arc de fond représentant le tronçon physique.
    Pointillé = voie unique, continu = double voie.
    """
    # Halo blanc très léger pour garantir la visibilité sur fond sombre
    ax.plot(
        [p1[0], p2[0]], [p1[1], p2[1]],
        color="white", lw=9, linestyle="solid",
        alpha=0.06, zorder=zorder, solid_capstyle="round",
    )
    # Trait principal gris clair bleuté, bien visible sur fond noir
    style = (0, (6, 4)) if single_track else "solid"
    ax.plot(
        [p1[0], p2[0]], [p1[1], p2[1]],
        color="#c8d0e0", lw=6, linestyle=style,
        alpha=0.55, zorder=zorder + 1,
        solid_capstyle="round", dash_capstyle="round",
    )


def plot_railway_network(
    net,  # RailwayNetwork
    title: str = "Réseau Ferroviaire",
    figsize: tuple = (14, 10),
    seed: Optional[int] = 42,
    show: bool = True,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Affiche une carte visuelle du réseau ferroviaire.

    Parameters
    ----------
    net : RailwayNetwork
        L'instance à visualiser.
    title : str
        Titre du graphique.
    figsize : tuple
        Taille de la figure (largeur, hauteur) en pouces.
    seed : int, optional
        Graine pour la disposition des nœuds (reproductibilité).
    show : bool
        Si True, appelle plt.show() à la fin.
    save_path : str, optional
        Si fourni, sauvegarde la figure à ce chemin.

    Returns
    -------
    matplotlib.figure.Figure
    """
    # ------------------------------------------------------------------ #
    # 1. Construction du graphe NetworkX (non dirigé pour le layout)      #
    # ------------------------------------------------------------------ #
    G = nx.Graph()
    G.add_nodes_from(net.stations.keys())
    for edge in net.segments:
        a, b = list(edge)
        G.add_edge(a, b)

    # Layout : spring layout pondéré par temps de trajet (t_min)
    weight_map = {}
    for edge, (t_min, t_max, single) in net.segments.items():
        a, b = list(edge)
        weight_map[(a, b)] = t_min
        weight_map[(b, a)] = t_min

    # Utiliser kamada_kawai si possible (plus lisible), sinon spring
    try:
        pos = nx.kamada_kawai_layout(G)
    except Exception:
        pos = nx.spring_layout(G, seed=seed, k=2.5 / math.sqrt(len(G.nodes)))

    pos_arr = {s: np.array(v) for s, v in pos.items()}

    # ------------------------------------------------------------------ #
    # 2. Associer une couleur à chaque ligne                              #
    # ------------------------------------------------------------------ #
    line_names = list(net.lines.keys())
    line_colors = {
        line: LINE_COLORS[i % len(LINE_COLORS)]
        for i, line in enumerate(line_names)
    }

    # ------------------------------------------------------------------ #
    # 3. Calcul des offsets pour les arcs parallèles                      #
    #    Pour chaque tronçon (a,b), trouver toutes les lignes qui         #
    #    l'empruntent, puis distribuer les offsets symétriquement.        #
    # ------------------------------------------------------------------ #
    # segment -> liste ordonnée des lignes qui le parcourent
    seg_lines: dict = collections.defaultdict(list)
    for line, route in net.lines.items():
        for i in range(len(route) - 1):
            key = frozenset({route[i], route[i + 1]})
            seg_lines[key].append(line)

    OFFSET_BASE = 0.038  # décalage entre deux arcs parallèles
    # Les arcs colorés sont TOUJOURS décalés du centre, même s'il n'y a
    # qu'une seule ligne sur le tronçon, afin que le trait de fond
    # (voie unique / double voie) reste visible en dessous.

    # ------------------------------------------------------------------ #
    # 4. Figure & style                                                   #
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=figsize, facecolor="#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_aspect("equal")
    ax.axis("off")

    # Titre
    ax.set_title(
        title,
        color="white",
        fontsize=18,
        fontweight="bold",
        fontfamily="monospace",
        pad=18,
    )

    # ------------------------------------------------------------------ #
    # 5. Dessiner les tronçons physiques (fond noir)                      #
    # ------------------------------------------------------------------ #
    for edge, (t_min, t_max, single) in net.segments.items():
        a, b = list(edge)
        if a not in pos_arr or b not in pos_arr:
            continue
        _draw_segment_base(ax, pos_arr[a], pos_arr[b], single_track=single)

    # ------------------------------------------------------------------ #
    # 6. Dessiner les arcs colorés par ligne (parallèles si besoin)       #
    # ------------------------------------------------------------------ #
    for edge, lines_on_seg in seg_lines.items():
        a, b = list(edge)
        if a not in pos_arr or b not in pos_arr:
            continue
        n = len(lines_on_seg)
        # Toujours centrer les offsets autour d'une valeur non nulle
        # pour que le fond (voie unique/double) reste visible.
        # Avec n=1 : offset = +OFFSET_BASE/2 (légèrement sur le côté)
        # Avec n≥2 : distribution symétrique espacée de OFFSET_BASE
        if n == 1:
            offsets = [OFFSET_BASE * 0.55]
        else:
            step = OFFSET_BASE
            offsets = [step * (i - (n - 1) / 2) for i in range(n)]

        for line, offset in zip(lines_on_seg, offsets):
            color = line_colors[line]
            # Trouver la direction de la ligne sur ce tronçon
            route = net.lines[line]
            idx_a = list(route).index(a) if a in route else -1
            idx_b = list(route).index(b) if b in route else -1

            if idx_a >= 0 and idx_b >= 0 and idx_a < idx_b:
                p_start, p_end = pos_arr[a], pos_arr[b]
            else:
                p_start, p_end = pos_arr[b], pos_arr[a]

            _curved_arrow(
                ax, p_start, p_end,
                offset=offset,
                color=color,
                lw=2.5,
                alpha=0.90,
                zorder=4,
            )

    # ------------------------------------------------------------------ #
    # 7. Dessiner les nœuds (stations)                                    #
    # ------------------------------------------------------------------ #
    xs = [pos_arr[s][0] for s in net.stations]
    ys = [pos_arr[s][1] for s in net.stations]

    # Halo lumineux
    ax.scatter(xs, ys, s=420, color="#ffffff", alpha=0.12, zorder=5)
    # Cercle principal
    ax.scatter(xs, ys, s=200, color="#f0f4f8", edgecolors="#a0b4c8", lw=1.5, zorder=6)

    # Labels stations
    for station, n_platforms in net.stations.items():
        x, y = pos_arr[station]
        ax.text(
            x, y + 0.065,
            station,
            ha="center", va="bottom",
            color="white",
            fontsize=9,
            fontweight="bold",
            fontfamily="monospace",
            zorder=7,
        )
        ax.text(
            x, y - 0.065,
            f"[{n_platforms} quais]",
            ha="center", va="top",
            color="#7ec8e3",
            fontsize=7,
            fontfamily="monospace",
            zorder=7,
        )

    # ------------------------------------------------------------------ #
    # 8. Légende                                                          #
    # ------------------------------------------------------------------ #
    legend_elements = [
        Line2D([0], [0], color=line_colors[line], lw=2.5, label=line)
        for line in line_names
    ]

    leg = ax.legend(
        handles=legend_elements,
        loc="lower right",
        framealpha=0.22,
        facecolor="#1a2035",
        edgecolor="#3a4a6a",
        labelcolor="white",
        fontsize=9,
    )

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"Figure sauvegardée : {save_path}")

    if show:
        plt.show()

    return fig


# --------------------------------------------------------------------------- #
# Demo rapide                                                                  #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/mnt/user-data/uploads")

    from railway_network import RailwayNetwork
    from railway_generator import generate_railway_network

    net = generate_railway_network(n_stations=8, n_lines=4, T=60, seed=42)
    plot_railway_network(net, title="Réseau Ferroviaire (seed=42)", show=False,
                         save_path="/mnt/user-data/outputs/railway_map.png")