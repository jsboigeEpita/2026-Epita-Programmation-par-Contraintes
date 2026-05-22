"""
visualization.py
================
Tracés matplotlib pour le projet A3 :

- ``plot_gantt`` : Gantt par salle, couleur = chirurgien, hachures = urgence.
- ``plot_surgeon_utilization`` : barres horizontales d'occupation par chirurgien.
- ``plot_solver_comparison`` : comparatif makespan/attente/temps entre solveurs.
- ``format_schedule`` : impression texte d'un planning (utilisée par main.py).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from .models import Instance, Priority, ScheduleResult


def _minutes_to_hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _surgeon_palette(n: int) -> list:
    cmap = plt.get_cmap("tab10" if n <= 10 else "tab20")
    return [cmap(i % cmap.N) for i in range(n)]


def plot_gantt(
    result: ScheduleResult,
    instance: Instance,
    title: Optional[str] = None,
    figsize=(11, 4.5),
    ax=None,
):
    """Gantt par salle : un sous-axe horizontal par salle d'opération."""
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    palette = _surgeon_palette(len(instance.surgeons))
    rooms = instance.rooms
    y_for_room = {r.rid: i for i, r in enumerate(rooms)}

    for a in result.assignments:
        s = instance.surgeries[a.sid]
        room = next(r for r in rooms if r.rid == a.room)
        y = y_for_room[a.room]
        # corps de l'intervention
        ax.barh(
            y, a.end - a.start, left=a.start, height=0.65,
            color=palette[a.surgeon], edgecolor="black", linewidth=0.6,
            hatch="//" if s.priority == Priority.URGENT else None,
        )
        # nettoyage
        ax.barh(
            y, room.clean_time, left=a.end, height=0.65,
            color="lightgrey", edgecolor="grey", linewidth=0.4,
        )
        label = f"{s.name}"
        if (a.end - a.start) > 25:
            ax.text(
                a.start + (a.end - a.start) / 2, y, label,
                ha="center", va="center", fontsize=8, color="white",
                fontweight="bold",
            )

    ax.set_yticks(list(y_for_room.values()))
    ax.set_yticklabels([r.name for r in rooms])
    ax.set_xlabel("Temps (minutes)")
    ax.set_xlim(0, max(result.makespan + 30, instance.horizon // 4))
    ax.grid(axis="x", linestyle=":", alpha=0.5)

    # légende chirurgiens
    handles = [
        mpatches.Patch(color=palette[sg.surg_id], label=sg.name)
        for sg in instance.surgeons
    ]
    handles.append(mpatches.Patch(facecolor="white", edgecolor="black", hatch="//",
                                  label="Urgence"))
    handles.append(mpatches.Patch(color="lightgrey", label="Nettoyage"))
    ax.legend(handles=handles, loc="upper right", fontsize=8, ncol=2)

    if title is None:
        title = (f"Gantt — {result.solver} | makespan={result.makespan} min "
                 f"| obj={result.objective:.0f} | {result.solve_ms:.0f} ms")
    ax.set_title(title)
    fig.tight_layout()
    return ax


def plot_surgeon_utilization(
    result: ScheduleResult,
    instance: Instance,
    figsize=(8, 3.2),
    ax=None,
):
    """Barres horizontales : temps de travail effectif par chirurgien."""
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    work: Dict[int, int] = {sg.surg_id: 0 for sg in instance.surgeons}
    for a in result.assignments:
        work[a.surgeon] += a.end - a.start

    palette = _surgeon_palette(len(instance.surgeons))
    names = [sg.name for sg in instance.surgeons]
    values = [work[sg.surg_id] for sg in instance.surgeons]
    colors = [palette[sg.surg_id] for sg in instance.surgeons]

    ax.barh(names, values, color=colors, edgecolor="black")
    for i, v in enumerate(values):
        ax.text(v + 2, i, f"{v} min", va="center", fontsize=9)
    ax.set_xlabel("Temps opératoire cumulé (min)")
    ax.set_title(f"Utilisation chirurgiens — {result.solver}")
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    fig.tight_layout()
    return ax


def plot_solver_comparison(
    results: List[ScheduleResult],
    figsize=(10, 3.4),
):
    """Trois sous-graphes côte à côte : makespan, attente, temps solveur."""
    fig, axes = plt.subplots(1, 3, figsize=figsize)
    names = [r.solver for r in results]
    palette = plt.get_cmap("Set2")(range(len(results)))

    axes[0].bar(names, [r.makespan for r in results], color=palette, edgecolor="black")
    axes[0].set_title("Makespan (min)")
    axes[0].grid(axis="y", linestyle=":", alpha=0.5)

    axes[1].bar(names, [r.total_wait for r in results], color=palette, edgecolor="black")
    axes[1].set_title("Attente pondérée")
    axes[1].grid(axis="y", linestyle=":", alpha=0.5)

    axes[2].bar(names, [r.solve_ms for r in results], color=palette, edgecolor="black")
    axes[2].set_title("Temps de résolution (ms)")
    axes[2].set_yscale("log")
    axes[2].grid(axis="y", linestyle=":", alpha=0.5, which="both")

    fig.tight_layout()
    return fig


def format_schedule(result: ScheduleResult, instance: Instance) -> str:
    """Impression texte d'un planning, groupé par salle."""
    if not result.assignments:
        return f"  (aucun planning : status={result.status})"
    by_room: Dict[int, list] = {r.rid: [] for r in instance.rooms}
    for a in result.assignments:
        by_room[a.room].append(a)
    surgeons_by_id = {sg.surg_id: sg for sg in instance.surgeons}

    lines = []
    for room in instance.rooms:
        items = sorted(by_room[room.rid], key=lambda a: a.start)
        if not items:
            lines.append(f"{room.name} : vide")
            continue
        lines.append(f"{room.name} ({', '.join(room.specialties)}) :")
        for a in items:
            s = instance.surgeries[a.sid]
            sg = surgeons_by_id[a.surgeon]
            tag = "URG" if s.priority == Priority.URGENT else "   "
            pref = ""
            if s.preferred_surgeon is not None and s.preferred_surgeon != a.surgeon:
                pref = "  (préféré: Dr-" + str(s.preferred_surgeon + 1) + ")"
            lines.append(
                f"  [{tag}] {_minutes_to_hhmm(a.start)}–{_minutes_to_hhmm(a.end)}  "
                f"{s.name:14s}  par {sg.name}{pref}"
            )
    return "\n".join(lines)


__all__ = [
    "plot_gantt",
    "plot_surgeon_utilization",
    "plot_solver_comparison",
    "format_schedule",
]
