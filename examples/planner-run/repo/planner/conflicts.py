"""Detection of overlapping section meeting rows."""

from itertools import combinations

from planner.model import Section


def find_conflicts(sections: list[Section]) -> list[tuple[Section, Section]]:
    """Return every pair whose meetings overlap on the same day.

    Intervals are half-open: a meeting ending exactly when another begins is
    not a conflict. The returned pair order follows input order.
    """
    return [
        (first, second)
        for first, second in combinations(sections, 2)
        if first.day == second.day
        and first.start < second.end
        and second.start < first.end
    ]
