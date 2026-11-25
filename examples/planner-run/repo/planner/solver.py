"""Choose one section per requested course without timetable overlaps."""

from dataclasses import dataclass, field
from itertools import product
from operator import attrgetter

from planner.model import PlannerError, Section


@dataclass
class CourseSections:
    """All meeting rows of one section of one course."""

    course: str
    section: str
    meetings: list[Section]


@dataclass
class Choice:
    """A section picked for a course; ``meetings`` is usually one row."""

    course: str
    section: str
    meetings: list[Section] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.course} {self.section}".strip()

    def places(self) -> list[str]:
        return [m.location for m in self.meetings]


def usable_choices(course: str, groups: list[CourseSections]) -> list[Choice]:
    """Sections of one course that can appear in a schedule.

    A section whose own meetings overlap is dropped (it can never fit), but
    the other sections of the course stay available. Only when every section
    is broken is the course itself unusable.
    """
    usable: list[Choice] = []
    broken: list[Choice] = []
    for group in groups:
        choice = Choice(group.course, group.section, list(group.meetings))
        if _self_clash(choice.meetings):
            broken.append(choice)
        else:
            usable.append(choice)
    if not usable:
        example = broken[0]
        raise PlannerError(
            f"course {course} is unusable: every section has overlapping"
            f" meetings, e.g. section {example.section} ({describe(example)})"
        )
    return usable


def group_sections(sections: list[Section]) -> dict[str, list[CourseSections]]:
    """Group meeting rows into ``course -> [section, ...]``, keeping file order."""
    courses: dict[str, list[CourseSections]] = {}
    index: dict[tuple[str, str], CourseSections] = {}
    for row in sections:
        key = (row.course, row.section)
        group = index.get(key)
        if group is None:
            group = CourseSections(row.course, row.section, [])
            index[key] = group
            courses.setdefault(row.course, []).append(group)
        group.meetings.append(row)
    return courses


def _rows(choice: Choice) -> list[Section]:
    return choice.meetings if isinstance(choice, Choice) else list(choice)


def overlaps(a: list[Section], b: list[Section]) -> bool:
    """True when any meeting in ``a`` overlaps any meeting in ``b``."""
    return any(
        x.day == y.day and x.start < y.end and y.start < x.end
        for x in a
        for y in b
    )


def describe(choice: Choice) -> str:
    return ", ".join(
        f"{m.day} {m.start // 60:02d}:{m.start % 60:02d}-{m.end // 60:02d}:{m.end % 60:02d}"
        f" in {m.location}"
        for m in choice.meetings
    )


def _self_clash(meetings: list[Section]) -> bool:
    from itertools import combinations

    return any(
        a.day == b.day and a.start < b.end and b.start < a.end
        for a, b in combinations(meetings, 2)
    )


def _no_overlap(first: Choice, second: Choice) -> bool:
    return not overlaps(_rows(first), _rows(second))


def solve(
    sections: list[Section], courses: list[str], *, limit: int | None = None
) -> list[list[Choice]]:
    """Return feasible schedules, each a list of :class:`Choice`.

    Schedules are produced in input order of the requested courses, then file
    order of the sections, and stop after ``limit`` results (None = all).
    Raises :class:`PlannerError` when a course is unknown, has itself two
    clashing sections, or the requested courses cannot all be combined.
    """
    if not courses:
        raise PlannerError("no courses requested")
    grouped = group_sections(sections)
    duplicate = {name for name in courses if courses.count(name) > 1}
    if duplicate:
        raise PlannerError(
            "course requested more than once: " + ", ".join(sorted(duplicate))
        )
    unknown = [name for name in courses if name not in grouped]
    if unknown:
        known = ", ".join(grouped) or "(none)"
        raise PlannerError(
            f"unknown course(s): {', '.join(unknown)} (known courses: {known})"
        )
    options = [usable_choices(name, grouped[name]) for name in courses]

    results: list[list[Choice]] = []
    order = _search_order(options)

    def extend(position: int, chosen: list[Choice]) -> None:
        if limit is not None and len(results) >= limit:
            return
        if position == len(order):
            results.append(list(chosen))
            return
        for candidate in order[position]:
            if all(_no_overlap(candidate, other) for other in chosen):
                chosen.append(candidate)
                extend(position + 1, chosen)
                chosen.pop()

    extend(0, [])
    if not results:
        raise PlannerError(_explain_impossible(courses, options))
    if order is options:
        return results
    output = []
    for schedule in results:
        by_course = {choice.course: choice for choice in schedule}
        output.append([by_course[name] for name in courses])
    return output


def _search_order(options: list[list[Choice]]) -> list[list[Choice]]:
    """Visit the most constrained courses first.

    Courses with fewer sections are searched first, because backtracking is
    cheapest when the few options are decided early. This only changes the
    traversal: results are re-ordered back to the requested course order, and
    because the search is exhaustive (unless ``limit`` cuts it short) the set
    of schedules found is the same.
    """
    indexed = sorted(
        enumerate(options),
        key=lambda item: (len(item[1]), item[0]),
    )
    return [choices for _, choices in indexed]


def _blockers(
    options: list[list[Choice]], course_index: int
) -> dict[int, set[int]]:
    """Map option index -> indexes of options in other courses it clashes with."""
    blocked: dict[int, set[int]] = {i: set() for i in range(len(options[course_index]))}
    for other_index, other_options in enumerate(options):
        if other_index == course_index:
            continue
        for i, choice in enumerate(options[course_index]):
            for j, other in enumerate(other_options):
                if not _no_overlap(choice, other):
                    blocked[i].add((other_index, j))
    return blocked


def _course_level_explanation(options: list[list[Choice]]) -> str:
    """Name the most constrained course and what its sections clash with."""
    best: tuple[int, str] | None = None
    for index, choices in enumerate(options):
        blocked = _blockers(options, index)
        if not blocked:
            continue
        viable = [i for i, blocked_on in blocked.items() if not blocked_on]
        score = len(viable)
        if best is not None and score >= best[0]:
            continue
        parts = []
        for i, choice in enumerate(choices):
            clashes = ", ".join(
                options[other_index][other_j].label
                for other_index, other_j in sorted(blocked[i])
            )
            if clashes:
                line = f"{choice.label} ({describe(choice)}) clashes with {clashes}"
            else:
                line = f"{choice.label} ({describe(choice)}) is available"
            parts.append(line)
        best = (score, "; ".join(parts))
    return best[1] if best else ""


def _explain_impossible(courses: list[str], options: list[list[Choice]]) -> str:
    """Explain why no combination of sections avoids every overlap."""
    hopeless = [
        (name_a, name_b)
        for i, name_a in enumerate(courses)
        for j, name_b in enumerate(courses)
        if i < j
        and not any(_no_overlap(a, b) for a in options[i] for b in options[j])
    ]
    if hopeless:
        details = "; ".join(
            f"{a} and {b} cannot be combined at all" for a, b in hopeless
        )
        return f"no schedule without overlaps is possible: {details}"
    detail = _course_level_explanation(options)
    if detail:
        return (
            "no schedule without overlaps is possible for "
            + ", ".join(courses)
            + "; for example "
            + detail
        )
    return (
        "no schedule without overlaps is possible for "
        + ", ".join(courses)
        + ": each pair can be combined, but no combination covers all"
        " requested courses at once"
    )
