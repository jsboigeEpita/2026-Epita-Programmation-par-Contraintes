import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instances.otto import AlbParseError
from instances.scholl import (
    available_cycles,
    default_cycle,
    known_optimum,
    list_scholl,
    load_scholl,
    parse_in2,
    scholl_metadata,
)


def test_list_scholl_returns_25_instances():
    names = list_scholl()
    assert len(names) >= 20
    assert "MERTENS" in names
    assert "JACKSON" in names
    assert "TONGE70" in names


def test_load_classic_instance_well_formed():
    inst = load_scholl("MERTENS")
    assert len(inst.tasks) == 7
    assert all(t in inst.durations for t in inst.tasks)
    assert all(inst.durations[t] > 0 for t in inst.tasks)
    assert inst.cycle_time > 0


def test_known_optimum_returns_expected_values():
    assert known_optimum("MERTENS", 6) == 6
    assert known_optimum("MERTENS", 18) == 2
    assert known_optimum("JACKSON", 13) == 5
    assert known_optimum("MITCHELL", 26) == 5


def test_known_optimum_unknown_cycle_returns_none():
    assert known_optimum("MERTENS", 9999) is None


def test_available_cycles_non_empty():
    cycles = available_cycles("BOWMAN8")
    assert cycles == [20, 75]


def test_load_scholl_unknown_raises():
    with pytest.raises(FileNotFoundError):
        load_scholl("NOT_AN_INSTANCE")


def test_scholl_metadata_contains_expected_keys():
    meta = scholl_metadata("JACKSON")
    assert meta["n_tasks"] == 11
    assert "n_precedences" in meta
    assert "available_cycles" in meta
    assert "default_cycle" in meta


def test_parse_in2_invalid_file_raises(tmp_path):
    f = tmp_path / "bad.IN2"
    f.write_text("abc\n")
    with pytest.raises(AlbParseError):
        parse_in2(f)


def test_parse_in2_handles_terminator():
    inst = load_scholl("MERTENS")
    assert len(inst.precedences) > 0
    for a, b in inst.precedences:
        assert 0 <= a < len(inst.tasks)
        assert 0 <= b < len(inst.tasks)
