import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instances.library import load_classic
from instances.toy import toy_instance
from solvers.biobjective import (
    ParetoFront,
    ParetoPoint,
    compute_pareto_front,
    weighted_sum,
)


def test_pareto_front_dataclass_defaults():
    front = ParetoFront(instance_name="test")
    assert front.points == []
    assert front.total_time_ms == 0.0


def test_pareto_point_immutable():
    p = ParetoPoint(
        n_stations=3,
        cycle_time=10,
        assignment={0: 0},
        optimal=True,
        time_ms=5.0,
    )
    with pytest.raises(Exception):
        p.n_stations = 4


def test_pareto_front_extends_with_added_stations():
    inst = toy_instance()
    front = compute_pareto_front(inst, extra_stations=2, time_limit_per_point=10)
    assert len(front.points) >= 1
    n_stations_seq = [p.n_stations for p in front.points]
    assert n_stations_seq == sorted(n_stations_seq)
    cycle_seq = [p.cycle_time for p in front.points]
    assert cycle_seq == sorted(cycle_seq, reverse=True)


def test_pareto_front_minimal_point_matches_salbp1():
    inst = load_classic("Jackson-11")
    front = compute_pareto_front(inst, extra_stations=2, time_limit_per_point=15)
    assert len(front.points) >= 1
    assert front.points[0].n_stations == 6


def test_weighted_sum_returns_valid_solution():
    inst = toy_instance()
    res = weighted_sum(inst, alpha=1.0, beta=0.1, time_limit=15)
    assert res is not None
    m, max_load, assignment, optimal, t = res
    assert m >= 1
    assert max_load <= inst.cycle_time
    assert set(assignment.keys()) == set(inst.tasks)
    loads: dict[int, int] = {}
    for task, station in assignment.items():
        loads[station] = loads.get(station, 0) + inst.durations[task]
    assert max(loads.values()) == max_load


def test_weighted_sum_alpha_dominant_minimizes_stations():
    inst = toy_instance()
    res_high_alpha = weighted_sum(inst, alpha=5.0, beta=0.01, time_limit=15)
    res_high_beta = weighted_sum(inst, alpha=0.01, beta=2.0, time_limit=15)
    assert res_high_alpha is not None
    assert res_high_beta is not None
    m_high_alpha = res_high_alpha[0]
    m_high_beta = res_high_beta[0]
    assert m_high_alpha <= m_high_beta
