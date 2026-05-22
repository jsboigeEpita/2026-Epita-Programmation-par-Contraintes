from . import Instance


_LIBRARY: dict[str, dict] = {
    "Mertens-7": {
        "durations": [1, 5, 4, 3, 5, 6, 5],
        "precedences": [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (5, 6)],
        "default_cycle": 6,
        "known_optimum": 6,
    },
    "Bowman-8": {
        "durations": [17, 27, 36, 7, 30, 19, 27, 39],
        "precedences": [(0, 3), (1, 3), (3, 4), (4, 6), (4, 7), (2, 5), (5, 7), (6, 7)],
        "default_cycle": 75,
        "known_optimum": 3,
    },
    "Jaeschke-9": {
        "durations": [1, 3, 4, 4, 5, 4, 8, 1, 6],
        "precedences": [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (3, 5), (4, 6), (5, 6), (6, 7), (6, 8), (7, 8)],
        "default_cycle": 8,
        "known_optimum": 5,
    },
    "Jackson-11": {
        "durations": [6, 2, 5, 7, 1, 2, 3, 6, 5, 5, 4],
        "precedences": [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (4, 5), (5, 7), (6, 7), (7, 8), (7, 9), (8, 10), (9, 10)],
        "default_cycle": 10,
        "known_optimum": 6,
    },
    "Mansoor-11": {
        "durations": [2, 3, 4, 6, 6, 4, 4, 1, 7, 6, 4],
        "precedences": [(0, 1), (1, 2), (0, 3), (2, 4), (3, 5), (4, 6), (5, 7), (5, 8), (6, 9), (7, 9), (8, 9), (9, 10)],
        "default_cycle": 15,
        "known_optimum": 4,
    },
    "Mitchell-21": {
        "durations": [1, 5, 4, 5, 5, 6, 4, 4, 1, 1, 1, 2, 5, 1, 4, 4, 6, 7, 5, 6, 6],
        "precedences": [
            (0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (3, 6), (4, 6), (4, 8),
            (5, 9), (6, 9), (6, 10), (7, 10), (8, 10), (9, 11), (10, 11),
            (9, 12), (11, 13), (13, 14), (14, 15), (15, 16), (15, 17),
            (16, 18), (17, 19), (18, 19), (19, 20),
        ],
        "default_cycle": 14,
        "known_optimum": 8,
    },
    "Heskiaoff-28": {
        "durations": [
            108, 38, 36, 51, 23, 41, 49, 17, 36, 53, 24, 24, 25, 88,
            74, 53, 14, 54, 28, 32, 60, 53, 28, 32, 60, 33, 23, 28,
        ],
        "precedences": [
            (0, 1), (0, 5), (1, 2), (2, 3), (3, 4), (4, 6), (5, 6), (6, 7),
            (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13), (13, 14),
            (14, 15), (15, 16), (16, 17), (17, 18), (18, 19), (19, 20),
            (20, 21), (21, 22), (22, 23), (23, 24), (24, 25), (25, 26), (26, 27),
        ],
        "default_cycle": 256,
        "known_optimum": 5,
    },
}


def list_classics() -> list[str]:
    return list(_LIBRARY.keys())


def load_classic(name: str, cycle_time: int | None = None) -> Instance:
    data = _LIBRARY[name]
    tasks = list(range(len(data["durations"])))
    return Instance(
        name=name,
        tasks=tasks,
        durations={i: d for i, d in enumerate(data["durations"])},
        precedences=list(data["precedences"]),
        cycle_time=cycle_time or data["default_cycle"],
    )


def classic_metadata(name: str) -> dict:
    data = _LIBRARY[name]
    return {
        "n_tasks": len(data["durations"]),
        "n_precedences": len(data["precedences"]),
        "default_cycle": data["default_cycle"],
        "known_optimum": data["known_optimum"],
    }
