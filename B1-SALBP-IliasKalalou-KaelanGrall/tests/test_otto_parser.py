import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instances.otto import AlbParseError, parse_alb


VALID_ALB = """<number of tasks>
3

<task times>
1 2
2 3
3 4

<cycle time>
6

<precedence relations>
1,2
2,3

<end>
"""


def _write(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "test.alb"
    f.write_text(content, encoding="utf-8")
    return f


def test_parse_valid(tmp_path):
    f = _write(tmp_path, VALID_ALB)
    inst = parse_alb(f)
    assert len(inst.tasks) == 3
    assert inst.durations == {0: 2, 1: 3, 2: 4}
    assert inst.precedences == [(0, 1), (1, 2)]
    assert inst.cycle_time == 6


def test_parse_missing_n_tasks(tmp_path):
    f = _write(tmp_path, "<task times>\n1 2\n")
    with pytest.raises(AlbParseError, match="number of tasks"):
        parse_alb(f)


def test_parse_missing_durations(tmp_path):
    f = _write(tmp_path, "<number of tasks>\n3\n<task times>\n1 2\n")
    with pytest.raises(AlbParseError):
        parse_alb(f)


def test_parse_non_numeric_duration(tmp_path):
    f = _write(tmp_path, "<number of tasks>\n1\n<task times>\n1 abc\n")
    with pytest.raises(AlbParseError):
        parse_alb(f)


def test_parse_negative_duration(tmp_path):
    f = _write(tmp_path, "<number of tasks>\n1\n<task times>\n1 -5\n")
    with pytest.raises(AlbParseError):
        parse_alb(f)


def test_parse_out_of_range_precedence(tmp_path):
    f = _write(
        tmp_path,
        "<number of tasks>\n2\n<task times>\n1 1\n2 1\n<precedence relations>\n1,5\n",
    )
    with pytest.raises(AlbParseError):
        parse_alb(f)


def test_parse_self_precedence(tmp_path):
    f = _write(
        tmp_path,
        "<number of tasks>\n2\n<task times>\n1 1\n2 1\n<precedence relations>\n1,1\n",
    )
    with pytest.raises(AlbParseError):
        parse_alb(f)


def test_parse_with_cycle_override(tmp_path):
    f = _write(tmp_path, VALID_ALB)
    inst = parse_alb(f, cycle_time=10)
    assert inst.cycle_time == 10
