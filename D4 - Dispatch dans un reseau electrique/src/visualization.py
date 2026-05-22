"""Plots for the Economic Dispatch / Unit Commitment outputs.

All functions accept a solution object from `dispatch_solver` /
`unit_commitment` / `stochastic` and return the matplotlib `Figure`
(so the caller can decide what to do with it — save, display, …).
"""

from __future__ import annotations

from typing import Optional, Iterable, Dict, List

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from .instance import PowerNetwork


# Consistent palette across plots
_THERMAL_CMAP = plt.cm.tab10
_RENEW_COLORS = {"wind": "#7fbf7b", "solar": "#fdae61"}


def _gen_color(net: PowerNetwork, gid: str, idx: int):
    g = next(g for g in net.generators if g.id == gid)
    if g.kind in _RENEW_COLORS:
        return _RENEW_COLORS[g.kind]
    return _THERMAL_CMAP(idx % 10)


# --------------------------------------------------------------------------- #
# Single-period
# --------------------------------------------------------------------------- #

def plot_single_period(sol, ax=None, title: Optional[str] = None):
    """Bar chart: power output of each generator + dashed line for p_max."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 4))
    else:
        fig = ax.figure
    gens = sol.network.generators
    xs = np.arange(len(gens))
    powers = [sol.power[g.id] for g in gens]
    caps   = [g.p_max for g in gens]
    colors = [_gen_color(sol.network, g.id, i) for i, g in enumerate(gens)]
    ax.bar(xs, powers, color=colors, edgecolor="black", linewidth=0.6, alpha=0.85)
    for i, c in enumerate(caps):
        ax.hlines(c, i - 0.4, i + 0.4, colors="red", linestyles=":", linewidth=1.2)
    ax.set_xticks(xs)
    ax.set_xticklabels([g.id for g in gens], rotation=30, ha="right")
    ax.set_ylabel("Power (MW)")
    ax.set_title(title or f"Dispatch — {sol.network.name}  "
                          f"(cost = ${sol.total_cost:,.0f}/h)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# Multi-period
# --------------------------------------------------------------------------- #

def plot_dispatch_stack(sol, title: Optional[str] = None,
                        ax=None, show_load: bool = True):
    """Stacked area chart of generation per hour, with the demand curve."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 5))
    else:
        fig = ax.figure
    H = sol.horizon
    xs = np.arange(H)
    net = sol.network
    # Order: thermal cheapest first, then renewables on top
    thermal = sorted(net.thermal_generators(),
                     key=lambda g: g.cost_b + g.cost_c * (g.p_max / 2.0))
    renew = net.renewable_generators()
    order = thermal + renew

    bottom = np.zeros(H)
    legend_handles = []
    for i, g in enumerate(order):
        ys = np.array(sol.power[g.id])
        color = _gen_color(net, g.id, i)
        ax.fill_between(xs, bottom, bottom + ys, color=color, alpha=0.85,
                        step="post", linewidth=0)
        legend_handles.append(mpatches.Patch(color=color, label=g.id))
        bottom = bottom + ys

    if show_load:
        load_tot = [sum(row) for row in sol.loads]
        ax.step(xs, load_tot, where="post", color="black", linewidth=2,
                label="Demand", linestyle="--")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Power (MW)")
    ax.set_xticks(xs[::max(1, H // 12)])
    ax.set_xlim(0, H - 1)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title(title or f"Hourly dispatch — {net.name}")
    ax.legend(handles=legend_handles + [plt.Line2D([], [], color="black",
                                                   linestyle="--", label="Demand")],
              loc="upper left", fontsize=8, ncol=2)
    fig.tight_layout()
    return fig


def plot_schedule(sol, ax=None, title: Optional[str] = None):
    """ON/OFF schedule heatmap, with start-ups annotated."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 0.6 + 0.4 * len(sol.network.generators)))
    else:
        fig = ax.figure
    gens = sol.network.generators
    H = sol.horizon
    grid = np.array([[sol.on[g.id][t] for t in range(H)] for g in gens])
    ax.imshow(grid, aspect="auto", cmap="Greens", vmin=0, vmax=1,
              interpolation="nearest")
    ax.set_yticks(range(len(gens)))
    ax.set_yticklabels([g.id for g in gens])
    ax.set_xticks(range(0, H, max(1, H // 12)))
    ax.set_xlabel("Hour")
    ax.set_title(title or f"Commitment schedule — {sol.network.name}")
    for i, g in enumerate(gens):
        for t in range(H):
            if sol.startups.get(g.id, [0] * H)[t]:
                ax.text(t, i, "↑", ha="center", va="center", fontsize=10,
                        color="navy", fontweight="bold")
            elif sol.shutdowns.get(g.id, [0] * H)[t]:
                ax.text(t, i, "↓", ha="center", va="center", fontsize=10,
                        color="crimson", fontweight="bold")
    fig.tight_layout()
    return fig


def plot_line_loadings(sol, ax=None, top_k: int = 6,
                       title: Optional[str] = None):
    """Time series of |flow| / capacity for the most-loaded lines."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
    else:
        fig = ax.figure
    H = sol.horizon
    xs = np.arange(H)
    util = []
    for i, ln in enumerate(sol.network.lines):
        f = np.array(sol.flows[i])
        u = np.abs(f) / ln.capacity
        util.append((u.max(), i, ln, u))
    util.sort(reverse=True)
    util = util[:top_k]
    cmap = plt.cm.viridis(np.linspace(0, 1, len(util)))
    for c, (_, i, ln, u) in zip(cmap, util):
        ax.plot(xs, 100 * u, label=f"L{i} B{ln.from_bus}→B{ln.to_bus}",
                color=c, linewidth=1.6)
    ax.axhline(100, color="red", linestyle=":", linewidth=1, label="Capacity")
    ax.set_ylabel("Line utilisation  (% of capacity)")
    ax.set_xlabel("Hour")
    ax.set_ylim(0, 110)
    ax.set_xticks(xs[::max(1, H // 12)])
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(title or "Transmission line loadings")
    fig.tight_layout()
    return fig


def plot_cost_breakdown(sol, ax=None):
    """Bar chart: fuel vs start-up vs shut-down cost."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(5, 4))
    else:
        fig = ax.figure
    cats = ["Fuel", "Start-up", "Shut-down"]
    vals = [sol.fuel_cost, sol.startup_cost, sol.shutdown_cost]
    colors = ["#5b9bd5", "#70ad47", "#ed7d31"]
    bars = ax.bar(cats, vals, color=colors, edgecolor="black")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"${v:,.0f}",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Cost ($)")
    ax.set_title(f"Cost breakdown — total ${sol.total_cost:,.0f}")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# Scenarios / stochastic
# --------------------------------------------------------------------------- #

def plot_scenarios(scenarios: List[Dict[str, List[float]]],
                   asset_id: str, capacity_mw: float = 1.0,
                   mean_profile: Optional[List[float]] = None,
                   ax=None, title: Optional[str] = None):
    """Spaghetti plot of scenario realisations for a given renewable asset."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 4))
    else:
        fig = ax.figure
    H = len(scenarios[0][asset_id])
    xs = np.arange(H)
    for s, scen in enumerate(scenarios):
        ax.plot(xs, np.array(scen[asset_id]) * capacity_mw,
                color="grey", alpha=0.45, linewidth=1)
    if mean_profile is not None:
        ax.plot(xs, np.array(mean_profile) * capacity_mw,
                color="black", linewidth=2.2, label="Mean")
        ax.legend()
    ax.set_xlabel("Hour")
    ax.set_ylabel(f"{asset_id} availability (MW)")
    ax.set_title(title or f"{len(scenarios)} scenarios — {asset_id}")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def plot_network(net: PowerNetwork, flows: Optional[List[float]] = None,
                 ax=None, layout: Optional[Dict[int, tuple]] = None,
                 title: Optional[str] = None):
    """Schematic of the network. If `flows` is given, line width and color
    encode flow magnitude/direction."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 6))
    else:
        fig = ax.figure
    rng = np.random.default_rng(7)
    if layout is None:
        # circular layout
        n = len(net.buses)
        layout = {i: (np.cos(2 * np.pi * i / n), np.sin(2 * np.pi * i / n))
                  for i in range(n)}
    # Lines
    for i, ln in enumerate(net.lines):
        x1, y1 = layout[ln.from_bus]
        x2, y2 = layout[ln.to_bus]
        if flows is not None:
            f = flows[i]
            util = abs(f) / ln.capacity
            color = plt.cm.RdYlGn_r(util)
            lw = 1 + 4 * util
        else:
            color, lw = "lightgrey", 1.5
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, zorder=1)
        # arrow at midpoint if there's a flow
        if flows is not None and abs(flows[i]) > 1e-3:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            dx, dy = (x2 - x1) * 0.08, (y2 - y1) * 0.08
            if flows[i] < 0:
                dx, dy = -dx, -dy
            ax.annotate("", xy=(mx + dx, my + dy), xytext=(mx - dx, my - dy),
                        arrowprops=dict(arrowstyle="->", color=color, lw=lw))
    # Buses
    for b in net.buses:
        x, y = layout[b.id]
        has_gen = bool(net.gen_at_bus(b.id))
        color = "#ffd166" if has_gen else "#bdd9ef"
        ax.scatter([x], [y], s=900, c=color, edgecolors="black", zorder=3)
        ax.text(x, y, str(b.id), ha="center", va="center",
                fontsize=10, zorder=4, fontweight="bold")
        if b.load > 0:
            ax.text(x, y - 0.15, f"{b.load:.0f} MW", ha="center", va="top",
                    fontsize=8, color="darkred")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title or net.name)
    fig.tight_layout()
    return fig
