"""Rank feasible schedules by user preferences."""

from dataclasses import dataclass, field

from planner.model import PlannerError, Section
from planner.solver import Choice

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_ORDER = {day: index for index, day in enumerate(DAYS)}

# Metrics are compared lexicographically in this order, so the first one is the
# most important preference.
METRICS = ("days", "early", "gaps", "span")


@dataclass(frozen=True)
class Preferences:
    """Ordered preferences used to rank schedules.

    ``days``        fewest days with any class on campus
    ``early``       fewest meetings starting before ``not_before``
    ``gaps``        smallest total waiting time between classes on a day
    ``span``        smallest total time from the first to the last class per day
    """

    order: tuple[str, ...] = METRICS
    not_before: int = 9 * 60
    max_results: int = 10


@dataclass(frozen=True)
class Metrics:
    """Measured values of a schedule; lower is better for every field."""

    days: int
    early: int
    gaps: int
    span: int

    def as_dict(self) -> dict[str, int]:
        return {"days": self.days, "early": self.early, "gaps": self.gaps, "span": self.span}

    def as_tuple(self, order: tuple[str, ...]) -> tuple[int, ...]:
        values = self.as_dict()
        return tuple(values[name] for name in order)


@dataclass
class RankedSchedule:
    """A feasible schedule together with its measured metrics.

    Ranking is lexicographic over :attr:`metrics` (see :func:`sort_key`); no
    single scalar is stored, because no weighted sum can express a preference
    list honestly (a 600-minute gap would outweigh "fewest days").
    """

    choices: list[Choice]
    metrics: Metrics
    rank: int = 0
    occurrence: int = 0  # how many equal-preference schedules were seen earlier
    window: tuple[int, int] = (8 * 60, 20 * 60)
    not_before: int = 9 * 60  # kept so the ordering key can be rebuilt

    def describe(self) -> str:
        metrics = self.metrics
        return (
            f"{metrics.days} day(s) on campus, {metrics.early} early class(es),"
            f" {metrics.gaps} min of gaps, {metrics.span} min on campus"
        )

    @property
    def meetings(self) -> list[Section]:
        return [row for choice in self.choices for row in choice.meetings]


@dataclass
class Ranking:
    """Result of :func:`rank_schedules`."""

    top: list[RankedSchedule]
    total: int
    truncated: bool = False
    seen: int = field(default=0)


def schedule_order_key(choices, order, not_before: int = 9 * 60) -> tuple:
    """Total order used to rank schedules.

    Metrics in ``order`` first, then the section numbers (so equal preference
    scores still sort deterministically), then the exact meetings as a last
    tie-break. Both the search and the CLI use this one key.
    """
    meetings = [row for choice in choices for row in choice.meetings]
    return (
        measure(meetings, not_before=not_before).as_tuple(normalise_order(order)),
        [(choice.course, choice.section) for choice in choices],
        lesson_key(meetings),
    )


def lesson_key(meetings: list[Section]) -> tuple:
    """Order schedules identically wherever they are compared.

    Preferences come first (in the user's order), then the chosen sections by
    course and section, then a fingerprint of the meetings themselves so that
    two different schedules never compare equal.
    """
    return (
        [(row.day, row.start, row.end, row.location) for row in sorted(
            meetings, key=lambda r: (r.day, r.start, r.end, r.location)
        )],
    )


def normalise_order(names: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Validate a preference order, filling in the remaining metrics."""
    if names is None:
        return METRICS
    cleaned: list[str] = []
    for name in names:
        key = name.strip().lower()
        if key not in METRICS:
            raise PlannerError(
                f"unknown preference {name!r}; choose from {', '.join(METRICS)}; repeat --prefer for several"
            )
        if key not in cleaned:
            cleaned.append(key)
    if not cleaned:
        raise PlannerError("at least one preference is required")
    return tuple(cleaned) + tuple(name for name in METRICS if name not in cleaned)


def measure(meetings: list[Section], *, not_before: int = 9 * 60) -> Metrics:
    """Compute the preference metrics of a set of meetings.

    A meeting counts as early when it starts before ``not_before`` (minutes
    after midnight). Gaps are the idle minutes between consecutive classes on
    the same day; ``span`` is the first-to-last distance per day.
    """
    per_day: dict[str, list[Section]] = {}
    for row in meetings:
        per_day.setdefault(row.day, []).append(row)
    gaps = 0
    span = 0
    for rows in per_day.values():
        rows = sorted(rows, key=lambda r: (r.start, r.end))
        cursor = rows[0].end
        for row in rows[1:]:
            if row.start > cursor:
                gaps += row.start - cursor
            cursor = max(cursor, row.end)
        span += rows[-1].end - rows[0].start
    early = sum(1 for row in meetings if row.start < not_before)
    return Metrics(days=len(per_day), early=early, gaps=gaps, span=span)


def sort_key(schedule: RankedSchedule, order: tuple[str, ...]) -> tuple:
    """Stable ordering: preferences in order, then a deterministic tie-break."""
    return (
        schedule.metrics.as_tuple(order),
        [(c.course, c.section) for c in schedule.choices],
    )


def rank(
    schedules: list[list[Choice]],
    *,
    preferences: Preferences | None = None,
    total: int | None = None,
) -> Ranking:
    """Rank and return the best schedules, best first.

    Ranks are 1-based and ties are kept (equal metrics share the rank shown
    by the earlier schedule's position), up to ``preferences.max_results``.
    """
    prefs = preferences or Preferences()
    order = normalise_order(prefs.order)
    if prefs.max_results < 1:
        raise PlannerError("max_results must be at least 1")
    ranked = [
        RankedSchedule(choices, measure(
            [row for choice in choices for row in choice.meetings],
            not_before=prefs.not_before,
        ))
        for choices in schedules
    ]
    ranked.sort(key=lambda item: sort_key(item, order))
    seen_order: list[tuple[int, ...]] = []
    for item in ranked:
        key = item.metrics.as_tuple(order)
        if key not in seen_order:
            seen_order.append(key)
        item.rank = seen_order.index(key) + 1
    top = ranked[: prefs.max_results]
    return Ranking(
        top=top,
        total=total if total is not None else len(schedules),
        truncated=len(schedules) < (total if total is not None else len(schedules)),
        seen=len(schedules),
    )
