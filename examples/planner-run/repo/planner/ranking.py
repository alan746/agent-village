"""Search for the best schedules without enumerating every feasible one."""

from dataclasses import dataclass

from planner.model import PlannerError, Section
from planner.preferences import (
    RankedSchedule,
    measure,
    normalise_order,
    schedule_order_key,
)
from planner.solver import (
    Choice,
    _explain_impossible,
    _no_overlap,
    group_sections,
    usable_choices,
)

# How many search nodes to visit after the top ``limit`` schedules are known
# before reporting the counts as approximate. Small enough to answer in well
# under a second, large enough that small timetables are counted exactly.
DEFAULT_PATIENCE = 20_000


@dataclass
class SearchResult:
    """Best schedules found (best first) plus what the search did.

    ``total`` is the number of feasible schedules seen; ``complete`` says
    whether the search was exhaustive, so ``best`` is the exact top ``limit``
    and ``total`` the exact number of feasible schedules. It is False when the
    search hit its budget after the top ``limit`` were already found, or when
    pruning was heuristic (see ``search``); ``best`` is then only the best
    found among the branches actually visited. ``stopped`` is true only when
    the node budget ran out (as opposed to a provably safe prune), so callers
    can say "search stopped" only when it really did.
    """

    best: list[RankedSchedule]
    total: int
    complete: bool
    explored: int
    stopped: bool = False


def _exact_key(item: RankedSchedule, order: tuple[str, ...]) -> tuple:
    return schedule_order_key(item.choices, order, item.not_before)


def search(
    sections: list[Section],
    courses: list[str],
    *,
    order: list[str] | tuple[str, ...] | None = None,
    not_before: int = 9 * 60,
    limit: int = 10,
    patience: int = DEFAULT_PATIENCE,
) -> SearchResult:
    """Find up to ``limit`` feasible schedules, best first, according to ``order``.

    The result is *exact* when ``SearchResult.complete`` is true: ``best``
    holds the true top ``limit`` and ``total`` is the exact number of feasible
    schedules. When the search is incomplete -- it hit ``patience``, or the
    first preference metric has no sound bound so pruning is heuristic --
    ``best`` is only the best *found* and must not be presented as the true
    top. The CLI words those two cases differently for this reason.

    Depth-first search in the requested course order, but each course's
    sections are tried best-first (the one that starts latest when avoiding
    early classes, otherwise the one starting soonest), so a good schedule is
    found almost immediately and the stored top list is tight quickly.

    The prune is provably safe: when the top list is full, a branch is
    dropped if the metrics of the sections chosen so far already lose
    lexicographically to those of the worst stored schedule, compared over the
    *monotonic prefix* of the preference order and stopping at the first
    non-monotonic metric. Adding meetings never increases the number of days
    on campus or the number of early classes, so those metrics of a partial
    branch are lower bounds. ``gaps`` is not monotonic (a meeting slotted
    between two existing classes fills the gap) and neither is ``span`` (a
    meeting inside an existing day leaves the first-to-last distance
    unchanged), so they and everything after them are never used to prune.
    Equal metrics are always explored because the section-number tie-break
    cannot be bounded.

    When pruning cannot decide -- the order starts with a non-monotonic metric,
    so the comparable prefix is empty -- the search falls back to plain
    branch-and-bound on the section-number tie-break, which is a heuristic:
    a branch that is worse on the tie-break alone can still finish with better
    metrics. Such a search is never reported as complete, so the counts and
    the "best" it returns are honest lower bounds.

    ``patience`` caps the nodes visited once a feasible schedule is known, so a
    timetable with thousands of options still answers quickly; ``complete``
    then reports that the counts are approximate. The budget never makes the
    search claim a timetable is impossible: the first feasible schedule is
    always searched for.
    """
    order = normalise_order(order)
    if limit < 1:
        raise PlannerError("max_results must be at least 1")
    if not courses:
        raise PlannerError("no courses requested")
    grouped = group_sections(sections)
    duplicate = {name for name in courses if courses.count(name) > 1}
    if duplicate:
        raise PlannerError("course requested more than once: " + ", ".join(sorted(duplicate)))
    unknown = [name for name in courses if name not in grouped]
    if unknown:
        known = ", ".join(grouped) or "(none)"
        raise PlannerError(
            f"unknown course(s): {', '.join(unknown)} (known courses: {known})"
        )

    options = [usable_choices(name, grouped[name]) for name in courses]
    for choices in options:
        choices.sort(key=lambda choice: _option_rank(choice, order, not_before))

    stats = {
        "found": 0,
        "explored": 0,
        "capped": False,
        "pruned": False,
        "heuristic": False,
    }
    best: list[RankedSchedule] = []
    worst: tuple | None = None
    worst_bound: tuple = ()
    # A section-number bound is not sound for counting, so with an empty
    # monotonic prefix the search stops enumerating once the top list is full
    # and says so through ``complete``.
    counting = bool(_monotonic_prefix((0,) * len(order), order))

    def offer(chosen: list[Choice]) -> None:
        nonlocal worst, worst_bound
        meetings = [row for choice in chosen for row in choice.meetings]
        metrics = measure(meetings, not_before=not_before)
        item = RankedSchedule(list(chosen), metrics, not_before=not_before)
        key = _exact_key(item, order)
        if worst is not None and key >= worst:
            return
        if worst is not None:
            # The top list is full and sorted: walk from the end only as far
            # as needed and drop the item as soon as it cannot make the top.
            position = len(best)
            while position and _exact_key(best[position - 1], order) > key:
                position -= 1
            if position >= limit:
                return
            best.insert(position, item)
            if len(best) > limit:
                best.pop()
        else:
            best.append(item)
            best.sort(key=lambda other: _exact_key(other, order))
        if len(best) >= limit:
            worst = _exact_key(best[-1], order)
            worst_bound = bound_key(best[-1].choices)
            if not counting:
                # No sound bound covers the leading metric, so the search stops
                # enumerating now: the count and the stored list are a lower
                # bound, not the true top. This is a heuristic cut, not the
                # ``patience`` budget, so ``stopped`` stays false.
                stats["heuristic"] = True

    def bound_key(chosen: list[Choice]) -> tuple:
        # ``measure`` is normalised over all four metrics; read them in the
        # user's order so the monotonic prefix matches ``order``.
        return _monotonic_prefix(
            measure(
                [row for choice in chosen for row in choice.meetings],
                not_before=not_before,
            ).as_tuple(normalise_order(order)),
            normalise_order(order),
        )

    def visit(position: int, chosen: list[Choice]) -> None:
        # The node budget only applies once a schedule is known to exist: a
        # search that gives up before then would wrongly report the timetable
        # as impossible. Finding the first schedule is bounded by the number
        # of sections, so this always terminates.
        if stats["found"] and stats["explored"] >= patience:
            stats["capped"] = True
            return
        stats["explored"] += 1
        if stats["capped"] or stats["heuristic"]:
            return
        if worst is not None:
            # Prune only when the bound loses lexicographically to the bound
            # of the worst stored schedule, over comparable metrics only (see
            # ``_monotonic_prefix``). Using the stored key's full tuple would be
            # unsound: its tail is the stored schedule's own section numbers
            # and meetings, which a partial branch cannot be compared to.
            if bound_key(chosen) > worst_bound:
                # This subtree cannot improve the top list, but it may hold
                # zero or many feasible schedules. Do not guess its count: the
                # result is still an exact top list but its reported count is
                # only a lower bound.
                stats["pruned"] = True
                return
        if position == len(options):
            stats["found"] += 1
            offer(chosen)
            return
        for candidate in options[position]:
            if all(_no_overlap(candidate, other) for other in chosen):
                chosen.append(candidate)
                try:
                    visit(position + 1, chosen)
                finally:
                    chosen.pop()

    visit(0, [])
    if stats["found"] == 0:
        raise PlannerError(_explain_impossible(courses, options))
    # The search ran out of budget (as opposed to pruning a subtree it could
    # bound): it did stop early. Callers phrase their report from this rather
    # than claiming a stop whenever the result is not exhaustive.
    stopped = stats["capped"]
    seen: list[tuple] = []
    for item in best:
        key = item.metrics.as_tuple(order)
        if key not in seen:
            seen.append(key)
        item.rank = seen.index(key) + 1
    return SearchResult(
        best=best,
        total=stats["found"],
        complete=not (
            stats["capped"] or stats["pruned"] or stats["heuristic"]
        ),
        stopped=stopped,
        explored=stats["explored"],
    )


#: Metrics that never increase when meetings are added to a partial schedule:
#: a new day can only be added and a new early class only counted. ``gaps`` is
#: absent (a meeting slotted between two existing classes fills the gap) and so
#: is ``span`` (a meeting inside an existing day leaves it unchanged).
MONOTONIC_METRICS = frozenset({"days", "early"})


def _monotonic_prefix(values: tuple, order: tuple[str, ...]) -> tuple:
    """The leading metrics that can safely bound an unfinished schedule.

    Only the run of monotonic metrics at the head of ``order`` is compared;
    the first non-monotonic metric (``gaps`` or ``span``) ends it. Zeros would
    be padded for later positions, so a shorter tuple is what makes the
    comparison say "cannot tell" rather than "better".
    """
    prefix = []
    for name, value in zip(order, values):
        if name not in MONOTONIC_METRICS:
            break
        prefix.append(value)
    return tuple(prefix)


def _option_rank(choice: Choice, order: tuple[str, ...], not_before: int) -> tuple:
    """Sort key for one course's sections: the most promising first."""
    metrics = measure(choice.meetings, not_before=not_before)
    first = choice.meetings[0] if choice.meetings else None
    clock = (first.start, first.end) if first else (0, 0)
    if order[0] == "early" or "early" in order:
        return (metrics.early, clock, choice.section)
    return (clock, choice.section)
