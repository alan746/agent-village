"""Command line interface: ``planner conflicts|plan|show FILE ...``."""

import argparse
import csv
import sys
from pathlib import Path
from typing import Sequence

from planner import export, preferences, ranking
from planner import show as show_module
from planner.preferences import RankedSchedule
from planner.conflicts import find_conflicts
from planner.csvio import load_sections
from planner.exams import Exam, find_exam_clashes, load_exams
from planner.travel import load_buildings, travel_warnings
from planner.model import PlannerError, Section
from planner.show import render
from planner.solver import Choice, describe, solve

PROGRAM = "planner"


def _hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _meeting(row: Section) -> str:
    return f"{row.day} {_hm(row.start)}-{_hm(row.end)} @ {row.location}"


def _load(path: str) -> list[Section]:
    return load_sections(Path(path))


def cmd_conflicts(args: argparse.Namespace) -> int:
    sections = _load(args.file)
    conflicts = find_conflicts(sections)
    if not conflicts:
        print(f"no conflicts among {len(sections)} meetings")
        return 0
    for first, second in conflicts:
        print(
            f"conflict: {first.course} {first.section} ({_meeting(first)})"
            f" overlaps {second.course} {second.section} ({_meeting(second)})"
        )
    print(f"{len(conflicts)} conflicting pair(s)")
    return 1


def _exam_label(exam: Exam) -> str:
    return f"{exam.course} ({exam.date.isoformat()} {_hm(exam.start)}-{_hm(exam.end)})"


def cmd_exams(args: argparse.Namespace) -> int:
    exams = load_exams(Path(args.file))
    clashes = find_exam_clashes(exams, args.courses)
    if not clashes:
        print(f"no exam clashes among {len(set(args.courses))} course(s)")
        return 0
    for first, second in clashes:
        print(f"exam clash: {_exam_label(first)} overlaps {_exam_label(second)}")
    print(f"{len(clashes)} exam clash(es)")
    return 1


def _print_travel_warnings(args: argparse.Namespace, choices: list[Choice]) -> None:
    if args.buildings is None:
        return
    buildings = load_buildings(Path(args.buildings))
    warnings = travel_warnings(choices, buildings, walk_speed=args.walk_speed)
    if warnings:
        for warning in warnings:
            print(warning)
    else:
        print("no travel warnings")


def cmd_travel(args: argparse.Namespace) -> int:
    sections = _load(args.file)
    buildings = load_buildings(Path(args.buildings))
    choices = solve(sections, args.courses, limit=1)[0]
    _print_schedule(choices)
    warnings = travel_warnings(choices, buildings, walk_speed=args.walk_speed)
    if warnings:
        for warning in warnings:
            print(warning)
    else:
        print("no travel warnings")
    return 0


def _print_schedule(choices: list[Choice], indent: str = "  ") -> None:
    for choice in choices:
        print(f"{indent}{choice.course} {choice.section}")
        for row in choice.meetings:
            print(f"{indent}    {_meeting(row)}")


def _minutes(clock: str) -> int:
    """Parse ``HH:MM`` (or ``H``) into minutes after midnight."""
    text = clock.strip()
    if ":" in text:
        hour_text, minute_text = text.split(":", 1)
    else:
        hour_text, minute_text = text, "0"
    try:
        hour, minute = int(hour_text), int(minute_text)
    except ValueError:
        raise PlannerError(f"invalid time {clock!r}; expected HH:MM") from None
    if not 0 <= hour <= 24 or not 0 <= minute < 60 or (hour, minute) > (24, 0):
        raise PlannerError(f"invalid time {clock!r}; expected HH:MM between 00:00 and 24:00")
    return hour * 60 + minute


#: How each preference metric is worded in the ranked listing.
_METRIC_LABELS = {
    "days": "day(s) on campus",
    "early": "early class(es)",
    "gaps": "min of gaps",
    "span": "min on campus",
}


def _describe_ranked(item: RankedSchedule, order: Sequence[str]) -> str:
    """Metrics in *priority* order, so the listing reads like the preference.

    No single "score" is printed: a scalar cannot express a lexicographic
    preference list, and showing one invited comparisons it did not support.
    """
    values = item.metrics.as_dict()
    names = list(order) or ["days", "early", "gaps", "span"]
    return ", ".join(f"{values[name]} {_METRIC_LABELS[name]}" for name in names)


def _print_ranked(item: RankedSchedule, order: Sequence[str]) -> None:
    print(f"#{item.rank} {_describe_ranked(item, order)}")
    _print_schedule(item.choices, indent="    ")
    print(render(
        [row for choice in item.choices for row in choice.meetings],
        start=item.window[0],
        end=item.window[1],
    ), end="")


def cmd_plan(args: argparse.Namespace) -> int:
    sections = _load(args.file)
    courses = list(dict.fromkeys(args.courses))
    not_before = _minutes(args.not_before) if args.not_before is not None else 9 * 60
    order = preferences.normalise_order(args.prefer)
    # ``--top``/``--not-before`` default to None so an explicit use can be
    # told apart from "not given": the single-course shortcut may only hide
    # ranking when no ranking flag was actually asked for.
    explicit = args.prefer or args.top is not None or args.not_before is not None
    if len(courses) == 1 and not explicit:
        # A single course without ranking flags: show its first usable
        # section. Otherwise fall through to ``search``, which ranks every
        # feasible section of the course.
        schedules = solve(sections, courses, limit=1)
        choices = schedules[0]
        print("schedule:")
        _print_schedule(choices)
        print(render([row for choice in choices for row in choice.meetings]), end="")
        _print_travel_warnings(args, choices)
        export.handle_plan_exports(args, choices)
        return 0
    result = ranking.search(
        sections,
        courses,
        order=order,
        not_before=not_before,
        limit=args.top if args.top is not None else 10,
    )
    if not result.best:
        raise PlannerError("no schedule without overlaps is possible")
    how_many = len(result.best)
    if result.complete:
        print(f"{result.total} feasible schedule(s) found; best {how_many}:")
    elif result.stopped:
        # "best found", not "best": a search that ran out of budget cannot
        # promise the true top list (see ranking.search), so the wording must
        # not either.
        print(
            f"search stopped after {result.explored} steps; showing the best"
            f" {how_many} found of at least {result.total} feasible schedule(s):"
        )
    else:
        # Not exhaustive because branches were pruned, not because a step
        # budget ran out: report the count as the lower bound it is without
        # claiming the search was cut short.
        print(
            f"at least {result.total} feasible schedule(s) exist; showing the"
            f" best {how_many} found (not all were enumerated):"
        )
    for item in result.best:
        _print_ranked(item, order)
    _print_travel_warnings(args, result.best[0].choices)
    export.handle_plan_exports(args, result.best[0].choices)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    sections = _load(args.file)
    if args.courses:
        grouped = {}
        for row in sections:
            grouped.setdefault(row.course, []).append(row)
        unknown = [name for name in args.courses if name not in grouped]
        if unknown:
            known = ", ".join(grouped) or "(none)"
            raise PlannerError(
                f"unknown course(s): {', '.join(unknown)} (known courses: {known})"
            )
        wanted = set(args.courses)
        sections = [row for row in sections if row.course in wanted]
    print(
        render(
            sections,
            start=args.start * 60 if args.start is not None else None,
            end=args.end * 60 if args.end is not None else None,
            width=args.width,
        ),
        end="",
    )
    return 0


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Plan a university term from a CSV of course sections.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    conflicts = sub.add_parser("conflicts", help="list pairs of sections that overlap")
    conflicts.add_argument("file", help="sections CSV")
    conflicts.set_defaults(func=cmd_conflicts)

    exams = sub.add_parser("exams", help="list exam clashes for selected courses")
    exams.add_argument("file", help="exams CSV")
    exams.add_argument("courses", nargs="+", metavar="COURSE", help="course codes")
    exams.set_defaults(func=cmd_exams)

    plan = sub.add_parser("plan", help="pick one non-overlapping section per course")
    plan.add_argument("file", help="sections CSV")
    plan.add_argument("courses", nargs="+", metavar="COURSE", help="course codes")
    plan.add_argument(
        "--top", type=_positive_int, default=None, metavar="N",
        help="how many ranked schedules to print (default 10)",
    )
    plan.add_argument(
        "--prefer", action="append", metavar="METRIC",
        help="preference in priority order, repeatable; one of"
             " days (fewest days on campus), early (no classes before"
             " --not-before), gaps (smallest total gap), span (shortest days)",
    )
    plan.add_argument(
        "--not-before", default=None, metavar="HH:MM",
        help="classes starting earlier than this count as early (default 09:00)",
    )
    export.add_export_arguments(plan)
    plan.add_argument("--buildings", metavar="FILE", help="building-coordinate CSV for walking warnings")
    plan.add_argument("--walk-speed", type=float, default=5.0, metavar="KM/H", help="walking speed used for travel warnings (default 5 km/h)")
    plan.set_defaults(func=cmd_plan)

    travel = sub.add_parser("travel", help="check walking time between selected courses")
    travel.add_argument("file", help="sections CSV")
    travel.add_argument("buildings", help="buildings CSV (building,lat,lon)")
    travel.add_argument("courses", nargs="+", metavar="COURSE", help="course codes")
    travel.add_argument("--walk-speed", type=float, default=5.0, metavar="KM/H", help="walking speed (default 5 km/h)")
    travel.set_defaults(func=cmd_travel)

    show = sub.add_parser("show", help="print a weekly text grid")
    show.add_argument("file", help="sections CSV")
    show.add_argument("courses", nargs="*", metavar="COURSE", help="limit to these courses")
    show.add_argument("--start", type=int, metavar="HOUR", help="first hour to show")
    show.add_argument("--end", type=int, metavar="HOUR", help="hour to stop showing")
    show.add_argument("--width", type=int, default=show_module.DEFAULT_WIDTH, help="cell width")
    show.set_defaults(func=cmd_show)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2
    try:
        return int(args.func(args))
    except PlannerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, OSError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised via __main__
    raise SystemExit(main())
