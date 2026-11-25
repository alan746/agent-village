"""Tests for the M2 preference ranking search."""

import itertools
import random

import pytest

from planner.model import PlannerError, Section
from planner.preferences import lesson_key, measure, schedule_order_key
from planner.ranking import search
from planner.solver import solve

ORDER = ("days", "early", "gaps", "span")


def section(course, sec, day, start, end, location="Room"):
    return Section(course, sec, day, start * 60, end * 60, location)


def exact_key(choices, order=ORDER, not_before=9 * 60):
    meetings = [row for choice in choices for row in choice.meetings]
    return (
        measure(meetings, not_before=not_before).as_tuple(order),
        [(choice.course, choice.section) for choice in choices],
        lesson_key(meetings),
    )


def brute_force(rows, courses, order=ORDER, not_before=9 * 60):
    # ``solve`` yields tuples of choices, which the search must reproduce.
    keys = (
        exact_key(list(schedule), order, not_before)
        for schedule in solve(rows, courses)
    )
    return sorted(keys)


def random_instance(rng, courses_max=4):
    rows, courses = [], []
    for index in range(rng.randint(2, courses_max)):
        name = f"C{index}"
        courses.append(name)
        for sec in range(rng.randint(1, 3)):
            for day in rng.sample(["Mon", "Tue", "Wed"], rng.randint(1, 2)):
                start = rng.randrange(8, 14)
                rows.append(section(name, f"S{sec}", day, start, start + 1))
    return rows, courses


def test_returns_best_schedule_first():
    rows = [
        section("A", "S0", "Mon", 8, 9),
        section("A", "S1", "Mon", 10, 11),
        section("B", "S0", "Mon", 11, 12),
        section("B", "S1", "Tue", 9, 10),
    ]
    result = search(rows, ["A", "B"], not_before=9 * 60)
    assert result.complete is True
    assert result.total == 4
    best = result.best[0]
    # Two days for A=S0,B=S1 vs one day for A=S1,B=S0: fewest days wins.
    assert [c.section for c in best.choices] == ["S1", "S0"]
    assert best.metrics.days == 1
    assert [item.rank for item in result.best] == [1, 2, 3, 4]


def test_limit_is_respected():
    rows = [
        section("A", "S0", "Mon", 9, 10),
        section("A", "S1", "Tue", 9, 10),
        section("B", "S0", "Wed", 9, 10),
        section("B", "S1", "Thu", 9, 10),
    ]
    result = search(rows, ["A", "B"], limit=2)
    assert len(result.best) == 2
    assert result.total == 4


def test_matches_brute_force_on_random_instances():
    rng = random.Random(2024)
    checked = 0
    for _ in range(150):
        rows, courses = random_instance(rng)
        try:
            expected = brute_force(rows, courses)[:5]
        except PlannerError:
            with pytest.raises(PlannerError):
                search(rows, courses, limit=5)
            continue
        result = search(rows, courses, limit=5)
        assert [exact_key(item.choices) for item in result.best] == expected
        # limit=5 caps the stored list, so the total can be larger. Pruning can
        # skip subtrees, so ``total`` is only a lower bound in that case.
        assert result.total >= len(expected)
        if result.complete:
            assert result.total == len(list(solve(rows, courses)))
        checked += 1
    assert checked > 30


def test_matches_brute_force_with_other_orders():
    rows = [
        section("A", "S0", "Mon", 8, 9),
        section("A", "S1", "Mon", 9, 10),
        section("B", "S0", "Mon", 9, 10),
        section("B", "S1", "Tue", 13, 14),
        section("C", "S0", "Wed", 10, 11),
        section("C", "S1", "Mon", 11, 12),
    ]
    for order in itertools.permutations(ORDER):
        expected = [
            key[:2]
            for key in brute_force(rows, ["A", "B", "C"], order=order)
        ]
        result = search(rows, ["A", "B", "C"], order=list(order))
        assert [exact_key(item.choices, order)[:2] for item in result.best] == expected, order


def test_patience_reports_incomplete_but_keeps_best_found():
    # 8 courses with 3 sections each on distinct slots would be 3**8 = 6561
    # schedules; a patience of 200 cuts the count short.
    rows = []
    for course in range(8):
        for sec in range(3):
            rows.append(section(f"C{course}", f"S{sec}", "Mon", 8 + course, 9 + course))
    result = search(rows, [f"C{course}" for course in range(8)], limit=3, patience=200)
    assert result.complete is False
    assert result.explored <= 200
    assert len(result.best) == 3
    # The patience cap must not corrupt the top list.
    everything = search(rows, [f"C{course}" for course in range(8)], limit=3, patience=10**6)
    assert [exact_key(i.choices)[:2] for i in result.best] == [
        exact_key(i.choices)[:2] for i in everything.best
    ]


def test_single_feasible_schedule():
    rows = [section("A", "S0", "Mon", 9, 10), section("B", "S0", "Tue", 9, 10)]
    result = search(rows, ["A", "B"])
    assert result.total == 1
    assert len(result.best) == 1


def test_impossible_raises_clear_error():
    rows = [section("A", "S0", "Mon", 9, 10), section("B", "S0", "Mon", 9, 10)]
    with pytest.raises(PlannerError, match="no schedule without overlaps"):
        search(rows, ["A", "B"])


def test_duplicate_and_unknown_courses():
    rows = [section("A", "S0", "Mon", 9, 10)]
    with pytest.raises(PlannerError, match="more than once"):
        search(rows, ["A", "A"])
    with pytest.raises(PlannerError, match="unknown course"):
        search(rows, ["A", "B"])


def test_bad_limit():
    rows = [section("A", "S0", "Mon", 9, 10)]
    with pytest.raises(PlannerError, match="max_results"):
        search(rows, ["A"], limit=0)


def test_prune_only_on_lexicographic_bound():
    # Regression: a partial branch with more days but fewer gaps must not be
    # pruned when the worst stored schedule has fewer days and more gaps.
    rows = [
        section("C0", "S0", "Mon", 10, 11),
        section("C0", "S1", "Tue", 13, 14),
        section("C0", "S1", "Wed", 11, 12),
        section("C1", "S0", "Wed", 9, 10),
        section("C1", "S0", "Tue", 10, 11),
        section("C1", "S1", "Thu", 14, 15),
        section("C2", "S0", "Mon", 14, 15),
        section("C2", "S1", "Mon", 10, 11),
        section("C2", "S1", "Thu", 8, 9),
        section("C3", "S0", "Thu", 11, 12),
    ]
    result = search(rows, ["C0", "C1", "C2", "C3"], limit=5)
    expected = brute_force(rows, ["C0", "C1", "C2", "C3"])[:5]
    assert [exact_key(item.choices) for item in result.best] == expected
    assert result.complete is True


def test_gaps_do_not_prune_filled_gaps():
    # Regression for the unsound gap bound found in review: the optimal
    # schedule puts a class *into* a gap (11:30-13:00, 13:00-14:30, 14:30-15:30
    # = zero gaps) — a partial branch already shows a larger gap total, so
    # pruning on ``gaps`` would discard it.
    def hm(h, m):
        return h * 60 + m

    rows = [
        Section("C0", "S0", "Mon", hm(11, 30), hm(13, 0), "R"),
        Section("C0", "S0", "Mon", hm(13, 0), hm(14, 30), "R"),
        Section("C1", "S0", "Mon", hm(14, 30), hm(15, 30), "R"),
        Section("C1", "S1", "Tue", hm(14, 30), hm(15, 30), "R"),
        Section("C2", "S1", "Wed", hm(14, 30), hm(15, 30), "R"),
        Section("C2", "S2", "Mon", hm(11, 30), hm(13, 0), "R"),
    ]
    order = ("gaps", "days", "early", "span")
    result = search(rows, ["C0", "C1", "C2"], limit=1, order=list(order))
    # Either class fits into the gap; with gaps first both have 0 gaps there.
    assert result.best[0].metrics.gaps == 0
    assert [exact_key(item.choices, order) for item in result.best] == brute_force(
        rows, ["C0", "C1", "C2"], order
    )[:1]


@pytest.mark.parametrize("order", [
    ("gaps", "early", "days", "span"),
    ("days", "gaps", "span", "early"),
    ("early", "gaps", "days", "span"),
    ("span", "gaps", "days", "early"),
])
def test_matches_brute_force_with_gaps_orders(order):
    rng = random.Random(2024)
    for _ in range(25):
        rows, courses = random_instance(rng)
        try:
            expected = brute_force(rows, courses, order)
        except PlannerError:
            continue
        result = search(rows, courses, limit=5, order=list(order))
        # Half-hour granularity makes gaps easy to fill; brute force decides.
        got = [exact_key(item.choices, order) for item in result.best]
        assert got == sorted(got)
        assert all(key in expected for key in got)
        if result.complete:
            assert got == expected[:5]
        else:
            # Only a lower bound: the leading metric has no sound bound, so
            # the listed schedules are the best *found*, not promised top-N.
            assert result.total <= len(expected)


@pytest.mark.parametrize("order", [ORDER, ("early", "gaps", "days", "span")])
def test_monotonic_prefix(order):
    # Pruning may only compare the leading metrics that cannot shrink when
    # meetings are added; ``span`` ends the prefix (filling a day leaves it
    # unchanged, so it is not a lower bound).
    from planner.ranking import _monotonic_prefix

    expected = {
        ORDER: (1, 2),
        ("early", "gaps", "days", "span"): (1,),
    }[order]
    assert _monotonic_prefix((1, 2, 3, 4), order) == expected
    assert _monotonic_prefix((1, 2, 3, 4), ("span", "days", "early")) == ()
    assert _monotonic_prefix((1, 2, 3, 4), ("span", "early")) == ()
    assert _monotonic_prefix((1, 2, 3, 4), ("gaps", "days", "early", "span")) == ()


def test_patience_never_returns_worse_results():
    # A search cut short by ``patience`` may report fewer results, never worse
    # ones than the full search.
    order = ("early", "gaps", "days", "span")
    rng = random.Random(7)
    rows, courses = random_instance(rng)
    full = search(rows, courses, limit=5, order=list(order), patience=100000)
    tight = search(rows, courses, limit=5, order=list(order), patience=8)
    full_keys = [exact_key(item.choices, order) for item in full.best]
    tight_keys = [exact_key(item.choices, order) for item in tight.best]
    assert tight_keys == full_keys[: len(tight_keys)]
    assert tight.explored <= tight.total + 8


def test_patience_never_reports_impossible():
    # The node budget must not make a feasible timetable look impossible:
    # with any patience the first schedule is still found.
    rows = [Section("C", "1", "Mon", 540, 600, "R")]
    for patience in (0, 1, 2):
        result = search(rows, ["C"], patience=patience)
        assert [choice.section for choice in result.best[0].choices] == ["1"]
    # And an impossible timetable is still reported as impossible.
    clash = [
        Section("A", "1", "Mon", 540, 600, "R"),
        Section("B", "1", "Mon", 570, 630, "R"),
    ]
    with pytest.raises(PlannerError, match="cannot be combined"):
        search(clash, ["A", "B"], patience=0)


def test_stopped_only_when_the_budget_ran_out():
    # ``stopped`` drives the CLI's "search stopped after N steps" wording, so
    # it must be false for a search that finished its tree or merely pruned a
    # bounded subtree, and true only when ``patience`` cut it short.
    rows = []
    for course in range(8):
        for sec in range(3):
            rows.append(section(f"C{course}", f"S{sec}", "Mon", 8 + course, 9 + course))
    courses = [f"C{course}" for course in range(8)]
    exhaustive = search(rows, courses, limit=3, patience=10**6)
    assert exhaustive.complete is True
    assert exhaustive.stopped is False
    tight = search(rows, courses, limit=3, patience=50)
    assert tight.complete is False
    assert tight.stopped is True
    # A tiny search under a heuristic-only order (no sound prefix) is
    # incomplete without the budget being the reason: saying "stopped after N
    # steps" would be a lie, because the stop came from the heuristic.
    small = [Section("A", "1", "Mon", 540, 600, "R"), Section("B", "1", "Tue", 540, 600, "R")]
    heuristic = search(small, ["A", "B"], limit=1, order=["span"], patience=10**6)
    assert heuristic.complete is False
    assert heuristic.stopped is False
    assert heuristic.total == 1


def test_incomplete_top_list_is_a_lower_bound_not_a_promise():
    # Ties broken only by section number are invisible to the metric bound:
    # with ``span`` first there is no sound prefix, so the search may stop
    # enumerating early. It must then report best-found honestly instead of
    # presenting the list as the true top.
    good = [
        Section("A", "A1", "Mon", 540, 600, "R"),
        Section("A", "A2", "Tue", 540, 600, "R"),
        Section("B", "B1", "Mon", 600, 660, "R"),
        Section("B", "B2", "Wed", 600, 660, "R"),
        Section("C", "C1", "Tue", 600, 660, "R"),
        Section("C", "C2", "Thu", 600, 660, "R"),
    ]
    result = search(good, ["A", "B", "C"], limit=1, order=["span"], patience=4)
    assert result.complete is False
    assert result.stopped is True
    # Whatever it found is a real schedule of the requested courses.
    assert [choice.course for choice in result.best[0].choices] == ["A", "B", "C"]
    # An exhaustive search over the same data is the reference, and the
    # incomplete one never claims equality with it without ``complete``.
    reference = search(good, ["A", "B", "C"], limit=5, order=["span"], patience=10**6)
    if not result.complete:
        assert result.total <= reference.total


def test_bound_uses_the_requested_metric_order():
    # The prune bound must read metrics in the user's order; ranking gaps
    # first used to compare ``days`` against the wrong metric and drop a
    # schedule it should have kept (caught by the fuzz suite).
    rows = [
        Section("C0", "S0", "Mon", 600, 660, "R"),
        Section("C0", "S0", "Tue", 480, 540, "R"),
        Section("C0", "S1", "Mon", 600, 660, "R"),
        Section("C0", "S1", "Tue", 480, 540, "R"),
        Section("C1", "S0", "Mon", 480, 540, "R"),
        Section("C1", "S1", "Mon", 540, 600, "R"),
        Section("C1", "S2", "Mon", 540, 600, "R"),
        Section("C2", "S0", "Mon", 660, 720, "R"),
        Section("C2", "S0", "Tue", 540, 600, "R"),
        Section("C2", "S1", "Wed", 480, 540, "R"),
        Section("C3", "S0", "Mon", 480, 540, "R"),
        Section("C3", "S1", "Mon", 480, 540, "R"),
        Section("C3", "S2", "Mon", 480, 540, "R"),
    ]
    courses = ["C0", "C1", "C2", "C3"]
    everything = list(solve(rows, courses))
    for order in (["days", "early", "gaps", "span"], ["gaps"], ["early"], ["span", "gaps"], ["span"]):
        result = search(rows, courses, limit=10, order=order)
        expected = sorted(schedule_order_key(list(s), order) for s in everything)
        got = [schedule_order_key(item.choices, order) for item in result.best]
        assert got == sorted(got)
        assert all(key in expected for key in got)
        if result.complete:
            assert got == expected[: len(got)]
            assert result.total == len(everything)
        else:
            assert result.total <= len(everything)
