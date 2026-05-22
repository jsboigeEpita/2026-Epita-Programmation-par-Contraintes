from pathlib import Path

from . import Instance


class AlbParseError(ValueError):
    pass


def parse_alb(path: str | Path, cycle_time: int | None = None) -> Instance:
    path = Path(path)
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        raise AlbParseError(f"Impossible de lire le fichier : {e}") from e

    lines = [line.strip() for line in content.splitlines()]

    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        if not line:
            continue
        if line.startswith("<") and line.endswith(">"):
            current = line.strip("<>").strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    if "number of tasks" not in sections or not sections["number of tasks"]:
        raise AlbParseError("Section <number of tasks> manquante ou vide.")
    if "task times" not in sections or not sections["task times"]:
        raise AlbParseError("Section <task times> manquante ou vide.")

    try:
        n_tasks = int(sections["number of tasks"][0])
    except ValueError as e:
        raise AlbParseError(f"Nombre de taches invalide : {sections['number of tasks'][0]!r}") from e

    if n_tasks <= 0:
        raise AlbParseError(f"Nombre de taches doit etre positif (recu {n_tasks}).")

    tasks = list(range(n_tasks))
    durations: dict[int, int] = {}
    for raw in sections["task times"]:
        parts = raw.split()
        if len(parts) < 2:
            raise AlbParseError(f"Ligne task times invalide : {raw!r}")
        try:
            task_id = int(parts[0]) - 1
            duration = int(parts[1])
        except ValueError as e:
            raise AlbParseError(f"Ligne task times non numerique : {raw!r}") from e
        if not 0 <= task_id < n_tasks:
            raise AlbParseError(f"Identifiant de tache hors plage : {task_id + 1}")
        if duration < 0:
            raise AlbParseError(f"Duree negative pour la tache {task_id + 1} : {duration}")
        durations[task_id] = duration

    if len(durations) != n_tasks:
        missing = sorted(set(tasks) - set(durations))
        raise AlbParseError(f"Durees manquantes pour les taches : {missing}")

    precedences: list[tuple[int, int]] = []
    for raw in sections.get("precedence relations", []):
        if "," not in raw:
            continue
        try:
            a_str, b_str = raw.split(",", 1)
            a = int(a_str) - 1
            b = int(b_str) - 1
        except ValueError as e:
            raise AlbParseError(f"Ligne precedence invalide : {raw!r}") from e
        if not (0 <= a < n_tasks and 0 <= b < n_tasks):
            raise AlbParseError(f"Precedence hors plage : ({a + 1}, {b + 1})")
        if a == b:
            raise AlbParseError(f"Precedence auto-referente : ({a + 1}, {b + 1})")
        precedences.append((a, b))

    if cycle_time is None:
        if "cycle time" in sections and sections["cycle time"]:
            try:
                cycle_time = int(sections["cycle time"][0])
            except ValueError as e:
                raise AlbParseError(f"Cycle time invalide : {sections['cycle time'][0]!r}") from e
        else:
            cycle_time = max(durations.values()) if durations else 1

    if cycle_time <= 0:
        raise AlbParseError(f"Cycle time doit etre positif (recu {cycle_time}).")

    return Instance(
        name=path.stem,
        tasks=tasks,
        durations=durations,
        precedences=precedences,
        cycle_time=cycle_time,
    )
