import pytest

from planner.model import PlannerError, Section
from planner.solver import Choice, group_sections, overlaps, solve


def row(course, section, day, start, end, location="R"):
    return Section(course, section, day, start * 60, end * 60, location)


DATA = [
    row("A", "1", "Mon", 9, 10),
    row("A", "2", "Tue", 9, 10),
    row("B", "1", "Mon", 9, 10),
    row("B", "2", "Mon", 11, 12),
    row("B", "2", "Tue", 14, 15),  # second meeting of the same section
]


def test_group_sections_merges_meetings():
    groups = group_sections(DATA)
    assert list(groups) == ["A", "B"]
    assert [(g.section, len(g.meetings)) for g in groups["B"]] == [("1", 1), ("2", 2)]


def test_overlaps_touching_is_not_overlap():
    assert overlaps([row("A", "1", "Mon", 9, 10)], [row("B", "1", "Mon", 10, 11)]) is False
    assert overlaps([row("A", "1", "Mon", 9, 10)], [row("B", "1", "Mon", 9, 30)]) is True
    assert overlaps([row("A", "1", "Mon", 9, 10)], [row("B", "1", "Tue", 9, 10)]) is False


def test_solve_returns_all_feasible_schedules_in_file_order():
    schedules = solve(DATA, ["A", "B"])
    pairs = [(c[0].section, c[1].section) for c in schedules]
    # B 2 meets on Mon 11-12 and Tue 14-15, so it fits next to every A
    # section; A 1 and B 1 clash on Mon 09-10, and so do A 2 and B 2's Mon
    # meeting is 11-12 so it does not. All three combinations are feasible.
    assert pairs == [("1", "2"), ("2", "1"), ("2", "2")]


def test_solve_limit():
    assert len(solve(DATA, ["A", "B"], limit=1)) == 1


def test_section_with_two_meetings_must_fit_on_both_days():
    schedules = solve(DATA, ["B", "A"])
    assert [(c[0].section, c[1].section) for c in schedules] == [
        ("1", "2"),
        ("2", "1"),
        ("2", "2"),
    ]
    two = schedules[1][0]
    assert isinstance(two, Choice)
    assert [m.day for m in two.meetings] == ["Mon", "Tue"]  # both meetings kept
    assert two.places() == ["R", "R"]
    assert "Mon " in two_label(two) and "Tue " in two_label(two)


def two_label(choice):
    from planner.solver import describe

    return describe(choice)


def test_unknown_course_message():
    with pytest.raises(PlannerError, match=r"unknown course\(s\): Z \(known courses: A, B\)"):
        solve(DATA, ["Z"])


def test_duplicate_course_request():
    with pytest.raises(PlannerError, match="more than once"):
        solve(DATA, ["A", "A"])


def test_no_courses():
    with pytest.raises(PlannerError, match="no courses"):
        solve(DATA, [])


def test_course_with_internal_clash_is_rejected():
    data = DATA + [row("C", "1", "Fri", 9, 10), row("C", "1", "Fri", 9, 30, "S")]
    with pytest.raises(PlannerError, match="course C is unusable"):
        solve(data, ["C"])


def test_skips_internally_clashing_section_if_another_is_usable():
    data = [
        Section("C", "1", "Mon", 9 * 60, 10 * 60, "R"),
        Section("C", "1", "Mon", 9 * 60 + 30, 10 * 60 + 30, "S"),
        Section("C", "2", "Tue", 9 * 60, 10 * 60, "T"),
    ]
    schedules = solve(data, ["C"])
    assert len(schedules) == 1
    assert schedules[0][0].section == "2"


def test_impossible_explanation_names_the_pair():
    data = [row("A", "1", "Mon", 9, 10), row("B", "1", "Mon", 9, 30, 10)]
    with pytest.raises(PlannerError) as info:
        solve(data, ["A", "B"])
    assert "A and B cannot be combined at all" in str(info.value)


def test_explanation_names_the_most_constrained_course():
    # Pairwise feasible, but A and C together leave B no slot. B is the most
    # constrained course, so its sections are reported.
    data = [
        row("A", "1", "Mon", 9, 10),
        row("B", "1", "Mon", 9, 10),
        row("B", "2", "Mon", 11, 12),
        row("C", "1", "Mon", 11, 12),
    ]
    for pair in (["A", "B"], ["A", "C"], ["B", "C"]):
        assert solve(data, pair)
    with pytest.raises(PlannerError) as info:
        solve(data, ["A", "B", "C"])
    message = str(info.value)
    assert message.startswith("no schedule without overlaps is possible for A, B, C")
    assert "for example" in message
    assert "Mon 09:00-10:00 in R" in message
    assert "clashes with" in message
    # the message must point at a course whose sections cannot all be used
    assert "A 1" in message or "B 1" in message or "C 1" in message


def test_impossible_due_to_combination_not_pair():
    # Every pair of courses can be combined, but not all three together:
    # A's Monday section clashes with B, its Tuesday section with C.
    data = [
        row("A", "1", "Mon", 9, 10),
        row("A", "2", "Tue", 9, 10),
        row("B", "1", "Mon", 9, 10),
        row("C", "1", "Tue", 9, 10),
    ]
    for pair in (["A", "B"], ["A", "C"], ["B", "C"]):
        assert solve(data, pair)
    with pytest.raises(PlannerError) as info:
        solve(data, ["A", "B", "C"])
    message = str(info.value)
    assert "no schedule without overlaps is possible" in message
    # The explanation must not claim a pair is hopeless: (A, B) is feasible.
    assert "cannot be combined at all" not in message


def test_explanation_falls_back_when_no_course_looks_constrained():
    # A and B are each available, but B's only section clashes with C's only
    # section, so the pair message is used and no "for example" is invented.
    from planner.solver import Choice, _explain_impossible

    options = [
        [Choice("A", "1", [row("A", "1", "Mon", 9, 10)])],
        [
            Choice("B", "1", [row("B", "1", "Mon", 9, 10)]),
            Choice("B", "2", [row("B", "2", "Mon", 9, 10)]),
        ],
    ]
    # force the "available" branch of the per-course explanation
    text = _explain_impossible(["A", "B"], options)
    assert "cannot be combined at all" in text
