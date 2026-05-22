from pathlib import Path

from . import Instance
from .otto import AlbParseError


DATA_DIR = Path(__file__).resolve().parent / "otto_data"


_KNOWN_CYCLES_AND_OPTIMA: dict[str, list[tuple[int, int]]] = {
    "MERTENS": [(6, 6), (7, 5), (8, 5), (10, 3), (15, 2), (18, 2)],
    "BOWMAN8": [(20, 5), (75, 3)],
    "JAESCHKE": [(6, 8), (7, 7), (8, 6), (10, 4), (18, 3)],
    "JACKSON": [(7, 8), (9, 6), (10, 5), (13, 5), (14, 4), (21, 3)],
    "MANSOOR": [(48, 4), (62, 3), (94, 2)],
    "MITCHELL": [(14, 8), (15, 8), (21, 5), (26, 5), (35, 3), (39, 3)],
    "ROSZIEG": [(14, 10), (18, 8), (21, 6), (32, 4)],
    "BUXEY": [(27, 13), (30, 11), (33, 10), (36, 9), (41, 8), (47, 7), (54, 7)],
    "SAWYER30": [(25, 14), (30, 12), (33, 11), (36, 10), (41, 8), (54, 7)],
    "LUTZ1": [(1414, 11), (1572, 10), (1768, 9), (2020, 8)],
    "GUNTHER": [(41, 14), (44, 12), (49, 11), (54, 9), (61, 8), (69, 8)],
    "KILBRID": [(57, 10), (62, 10), (69, 9), (79, 8), (92, 6)],
    "HAHN": [(2004, 8), (2338, 7), (2806, 6), (3507, 5)],
    "WARNECKE": [(54, 31), (58, 29), (62, 27), (68, 25), (74, 23), (80, 22), (92, 19), (104, 17), (111, 17)],
    "TONGE70": [(160, 23), (168, 23), (176, 22), (185, 21), (196, 20), (207, 19), (220, 17), (234, 17), (251, 16), (270, 15), (293, 14), (320, 13), (364, 11), (410, 11), (468, 10), (527, 9)],
    "WEE-MAG": [(46, 24), (47, 24), (49, 24), (50, 23), (52, 22), (54, 22), (56, 21)],
    "ARC83": [(5048, 16), (5853, 14), (6842, 12), (7571, 11), (8412, 10), (8898, 9), (10816, 8)],
    "ARC111": [(5755, 27), (5785, 27), (6309, 25), (6840, 23), (7515, 21), (8847, 18), (10027, 16)],
    "LUTZ2": [(11, 49), (12, 44), (13, 41), (14, 38), (15, 35), (16, 33), (17, 31), (18, 30), (19, 28), (20, 27), (21, 26), (22, 25), (23, 24), (24, 23), (25, 22)],
    "LUTZ3": [(75, 23), (79, 22), (83, 21), (87, 20), (92, 19), (97, 18), (103, 17), (110, 16), (118, 15)],
    "MUKHERJE": [(176, 25), (183, 24), (192, 23), (201, 22), (211, 21), (222, 20), (234, 19), (248, 18), (263, 17), (281, 16), (301, 15), (324, 14), (351, 13)],
    "BARTHOLD": [(403, 14), (434, 13), (470, 12), (513, 11), (564, 10), (626, 9), (705, 8), (805, 7)],
    "BARTHOL2": [(84, 51), (85, 50), (87, 49), (89, 48), (91, 47), (93, 46), (95, 45), (97, 44), (99, 43), (101, 42), (104, 41), (106, 40), (109, 39), (112, 38), (115, 37), (118, 36), (121, 35), (125, 34), (129, 33), (133, 32), (137, 31), (142, 30), (146, 29)],
    "HESKIA": [(138, 8), (205, 5), (216, 5), (256, 5), (324, 4), (342, 4), (393, 4)],
    "SCHOLL": [(1394, 50), (1422, 50), (1452, 50)],
}


def parse_in2(path: str | Path) -> Instance:
    path = Path(path)
    try:
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        ]
    except OSError as e:
        raise AlbParseError(f"Lecture impossible : {e}") from e

    if not lines:
        raise AlbParseError("Fichier vide.")

    try:
        n_tasks = int(lines[0])
    except ValueError as e:
        raise AlbParseError(f"Nombre de taches invalide : {lines[0]!r}") from e

    if n_tasks <= 0 or len(lines) < n_tasks + 1:
        raise AlbParseError("Fichier .IN2 malforme (durees manquantes).")

    durations: dict[int, int] = {}
    for i in range(n_tasks):
        try:
            durations[i] = int(lines[1 + i])
        except ValueError as e:
            raise AlbParseError(f"Duree invalide ligne {2 + i} : {lines[1 + i]!r}") from e

    precedences: list[tuple[int, int]] = []
    for raw in lines[n_tasks + 1:]:
        if "," not in raw:
            continue
        a_str, b_str = raw.split(",", 1)
        try:
            a, b = int(a_str), int(b_str)
        except ValueError:
            continue
        if a == -1 and b == -1:
            break
        if not (1 <= a <= n_tasks and 1 <= b <= n_tasks):
            continue
        precedences.append((a - 1, b - 1))

    return Instance(
        name=path.stem,
        tasks=list(range(n_tasks)),
        durations=durations,
        precedences=precedences,
        cycle_time=max(durations.values()),
    )


def list_scholl() -> list[str]:
    return sorted(p.stem for p in DATA_DIR.glob("*.IN2"))


def load_scholl(name: str, cycle_time: int | None = None) -> Instance:
    path = DATA_DIR / f"{name}.IN2"
    if not path.exists():
        raise FileNotFoundError(f"Instance Scholl/Otto inconnue : {name}")
    instance = parse_in2(path)
    cycle = cycle_time or default_cycle(name)
    return Instance(
        name=instance.name,
        tasks=instance.tasks,
        durations=instance.durations,
        precedences=instance.precedences,
        cycle_time=cycle,
    )


def default_cycle(name: str) -> int:
    table = _KNOWN_CYCLES_AND_OPTIMA.get(name.upper())
    if table:
        return table[len(table) // 2][0]
    path = DATA_DIR / f"{name}.IN2"
    if path.exists():
        return max(parse_in2(path).durations.values())
    return 1


def available_cycles(name: str) -> list[int]:
    return [c for c, _ in _KNOWN_CYCLES_AND_OPTIMA.get(name.upper(), [])]


def known_optimum(name: str, cycle_time: int) -> int | None:
    for c, opt in _KNOWN_CYCLES_AND_OPTIMA.get(name.upper(), []):
        if c == cycle_time:
            return opt
    return None


def scholl_metadata(name: str) -> dict:
    path = DATA_DIR / f"{name}.IN2"
    if not path.exists():
        raise FileNotFoundError(f"Instance Scholl/Otto inconnue : {name}")
    instance = parse_in2(path)
    return {
        "n_tasks": len(instance.tasks),
        "n_precedences": len(instance.precedences),
        "available_cycles": available_cycles(name),
        "default_cycle": default_cycle(name),
    }
