from . import Instance


def toy_instance() -> Instance:
    return Instance(
        name="toy-11",
        tasks=list(range(11)),
        durations={0: 6, 1: 5, 2: 4, 3: 5, 4: 3, 5: 6, 6: 4, 7: 7, 8: 5, 9: 6, 10: 7},
        precedences=[
            (0, 1), (0, 2), (1, 3), (2, 3), (2, 4),
            (3, 5), (4, 5), (4, 6), (5, 7), (6, 7),
            (7, 8), (7, 9), (8, 10), (9, 10),
        ],
        cycle_time=12,
    )
