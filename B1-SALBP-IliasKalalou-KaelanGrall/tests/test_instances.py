import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instances import Instance
from instances.library import classic_metadata, list_classics, load_classic
from instances.multimodel import to_aggregated_instance, two_model_toy
from instances.toy import toy_instance
from instances.validators import (
    InstanceValidationError,
    validate_instance,
    validate_precedences,
)


def test_toy_instance_well_formed():
    inst = toy_instance()
    assert len(inst.tasks) == 11
    assert all(t in inst.durations for t in inst.tasks)
    assert inst.cycle_time == 12
    assert all(0 <= a < 11 and 0 <= b < 11 for a, b in inst.precedences)


@pytest.mark.parametrize("name", list_classics())
def test_classic_instance_well_formed(name):
    inst = load_classic(name)
    meta = classic_metadata(name)
    assert len(inst.tasks) == meta["n_tasks"]
    assert len(inst.precedences) == meta["n_precedences"]
    assert all(t in inst.durations for t in inst.tasks)
    assert all(inst.durations[t] > 0 for t in inst.tasks)
    assert inst.cycle_time >= max(inst.durations.values())


def test_precedence_validator_strips_invalid():
    pairs = [(0, 1), (1, 0), (0, 5), (1, 1), (2, 3), (2, 3)]
    with pytest.raises(InstanceValidationError):
        validate_precedences(4, pairs)


def test_precedence_validator_detects_cycle():
    pairs = [(0, 1), (1, 2), (2, 0)]
    with pytest.raises(InstanceValidationError, match="Cycle"):
        validate_precedences(3, pairs)


def test_precedence_validator_accepts_valid():
    pairs = [(0, 1), (1, 2), (2, 3)]
    cleaned, warnings = validate_precedences(4, pairs)
    assert cleaned == pairs
    assert warnings == []


def test_validate_instance_rejects_oversized_task():
    inst = Instance(
        name="bad",
        tasks=[0, 1],
        durations={0: 100, 1: 1},
        precedences=[],
        cycle_time=10,
    )
    with pytest.raises(InstanceValidationError):
        validate_instance(inst)


def test_multimodel_two_models_consistent():
    mm = two_model_toy()
    assert len(mm.models) == 2
    for model in mm.models:
        assert set(mm.durations[model].keys()) == set(mm.tasks)
    agg = to_aggregated_instance(mm, mode="max")
    for t in mm.tasks:
        assert agg.durations[t] == max(mm.durations[m][t] for m in mm.models)
