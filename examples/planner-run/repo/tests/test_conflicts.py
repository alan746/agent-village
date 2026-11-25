from planner.conflicts import find_conflicts
from planner.model import Section


def sec(course, day, start, end):
    return Section(course, "1", day, start, end, "R")


def test_all_overlaps_and_touching_does_not_conflict():
    rows = [
        sec("A", "Mon", 540, 600),
        sec("B", "Mon", 600, 650),
        sec("C", "Mon", 590, 610),
        sec("D", "Tue", 590, 610),
    ]
    assert find_conflicts(rows) == [(rows[0], rows[2]), (rows[1], rows[2])]


def test_contained_meetings_overlap():
    outer, inner = sec("A", "Fri", 500, 700), sec("B", "Fri", 550, 560)
    assert find_conflicts([outer, inner]) == [(outer, inner)]
