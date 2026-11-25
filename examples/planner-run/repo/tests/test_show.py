import pytest

from planner.model import Section
from planner.show import active_days, render


def row(course, section, day, start, end, location="R"):
    return Section(course, section, day, start * 60, end * 60, location)


def test_empty_grid():
    assert render([]) == "(no meetings)\n"


def test_header_lists_only_days_with_meetings():
    rows = [row("A", "1", "Wed", 9, 10), row("B", "1", "Mon", 9, 10)]
    out = render(rows)
    header = out.splitlines()[0]
    assert header.split() == ["Mon", "Wed"]
    assert "A 1" in out and "09:00-10:00" in out


def test_active_days_order():
    rows = [row("A", "1", "Fri", 9, 10), row("B", "1", "Mon", 9, 10)]
    assert active_days(rows) == ["Mon", "Fri"]


def test_days_argument_forces_columns():
    out = render([row("A", "1", "Mon", 9, 10)], days=["Mon", "Tue"])
    assert out.splitlines()[0].split() == ["Mon", "Tue"]


def test_hour_window_hides_meetings():
    rows = [row("A", "1", "Mon", 9, 10, "R1"), row("B", "1", "Mon", 15, 16, "R2")]
    out = render(rows, start=14 * 60, end=17 * 60)
    assert "B 1" in out and "A 1" not in out
    assert out.splitlines()[-3].startswith("17:00") is False
    lines = out.splitlines()
    assert any(line.startswith("14:00") for line in lines)
    assert any(line.startswith("16:00") for line in lines)


def test_meeting_overlapping_window_start_is_shown_clipped():
    meeting = Section("A", "1", "Mon", 9 * 60 + 30, 10 * 60 + 30, "R")
    out = render([meeting], start=10 * 60, end=11 * 60)
    assert "10:00-10:30" in out
    assert "A 1" in out
    assert any(line.startswith("10:00|") for line in out.splitlines())
    assert not any(line.startswith("09:00|") for line in out.splitlines())


def test_two_meetings_in_same_hour_share_a_cell():
    rows = [row("A", "1", "Mon", 9, 10, "X"), row("A", "1", "Mon", 9, 10, "Y")]
    out = render(rows)
    assert "X" in out and "Y" in out


def test_grid_width_is_bounded():
    out = render([row("LONGC", "99", "Mon", 9, 10, "VeryLongRoomName")], width=12)
    for line in out.splitlines():
        assert len(line) <= 7 + 13


def test_invalid_arguments():
    with pytest.raises(ValueError, match="at least 12"):
        render([row("A", "1", "Mon", 9, 10)], width=5)
    with pytest.raises(ValueError, match="unknown day"):
        render([row("A", "1", "Mon", 9, 10)], days=["Funday"])
    with pytest.raises(ValueError, match="start must be before"):
        render([row("A", "1", "Mon", 9, 10)], start=600, end=600)
