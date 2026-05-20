import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instances.library import classic_metadata, load_classic
from instances.toy import toy_instance
from solvers import cpsat, plne, rpw


def _is_valid_assignment(inst, solution) -> bool:
    if solution is None:
        return False
    if set(solution.assignment.keys()) != set(inst.tasks):
        return False
    for i, j in inst.precedences:
        if solution.assignment[i] > solution.assignment[j]:
            return False
    loads: dict[int, int] = {}
    for t, s in solution.assignment.items():
        loads[s] = loads.get(s, 0) + inst.durations[t]
    return all(load <= inst.cycle_time for load in loads.values())


def test_rpw_on_toy():
    inst = toy_instance()
    sol = rpw.solve_salbp1(inst)
    assert _is_valid_assignment(inst, sol)
    assert sol.n_stations <= len(inst.tasks)


@pytest.mark.parametrize(
    "name",
    ["Mertens-7", "Bowman-8", "Jaeschke-9", "Jackson-11", "Mansoor-11"],
)
def test_rpw_produces_feasible(name):
    inst = load_classic(name)
    sol = rpw.solve_salbp1(inst)
    assert _is_valid_assignment(inst, sol)


@pytest.mark.parametrize("name", ["Mertens-7", "Bowman-8", "Jackson-11", "Mansoor-11"])
def test_cpsat_finds_optimum(name):
    inst = load_classic(name)
    meta = classic_metadata(name)
    sol = cpsat.solve_salbp1(inst, time_limit=20)
    assert sol is not None
    assert _is_valid_assignment(inst, sol)
    assert sol.optimal is True
    assert sol.n_stations == meta["known_optimum"]


@pytest.mark.parametrize("name", ["Mertens-7", "Jackson-11", "Mansoor-11"])
def test_plne_finds_optimum(name):
    inst = load_classic(name)
    meta = classic_metadata(name)
    sol = plne.solve_salbp1(inst, time_limit=20)
    assert sol is not None
    assert _is_valid_assignment(inst, sol)
    assert sol.n_stations == meta["known_optimum"]


def test_cpsat_salbp2_consistency():
    inst = load_classic("Jackson-11")
    s1 = cpsat.solve_salbp1(inst, time_limit=20)
    assert s1 is not None
    s2 = cpsat.solve_salbp2(inst, n_stations=s1.n_stations, time_limit=20)
    assert s2 is not None
    assert s2.optimal is True
    assert s2.cycle_time <= inst.cycle_time
