import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instances.multimodel import (
    MultiModelInstance,
    to_aggregated_instance,
    two_model_toy,
)


def test_two_model_toy_consistent():
    mm = two_model_toy()
    assert len(mm.models) == 2
    assert "A" in mm.models and "B" in mm.models
    for model in mm.models:
        assert set(mm.durations[model].keys()) == set(mm.tasks)
        assert all(mm.durations[model][t] > 0 for t in mm.tasks)


def test_demand_is_normalized_or_normalizable():
    mm = two_model_toy()
    total = sum(mm.demand.values())
    assert abs(total - 1.0) < 1e-9


def test_max_durations_is_per_task_max():
    mm = two_model_toy()
    agg = mm.max_durations()
    for t in mm.tasks:
        expected = max(mm.durations[m][t] for m in mm.models)
        assert agg[t] == expected


def test_average_durations_weighted_by_demand():
    mm = two_model_toy()
    avg = mm.average_durations()
    for t in mm.tasks:
        expected = sum(mm.demand[m] * mm.durations[m][t] for m in mm.models)
        assert abs(avg[t] - round(expected)) <= 1


def test_union_precedences_is_set():
    mm = two_model_toy()
    union = mm.union_precedences()
    expected = set()
    for prec_list in mm.precedences.values():
        expected.update(prec_list)
    assert set(union) == expected


def test_to_aggregated_instance_max_mode():
    mm = two_model_toy()
    inst = to_aggregated_instance(mm, mode="max")
    assert len(inst.tasks) == len(mm.tasks)
    assert inst.cycle_time == mm.cycle_time
    for t in mm.tasks:
        assert inst.durations[t] == max(mm.durations[m][t] for m in mm.models)


def test_to_aggregated_instance_average_mode():
    mm = two_model_toy()
    inst = to_aggregated_instance(mm, mode="average")
    assert len(inst.tasks) == len(mm.tasks)
    for t in mm.tasks:
        assert inst.durations[t] > 0
