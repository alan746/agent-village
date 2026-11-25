"""Read exam CSV data and detect clashes among selected courses."""

import csv
import re
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from pathlib import Path

from planner.model import PlannerError

COLUMNS = ("course", "date", "start", "end")
_TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Exam:
    """One exam interval; times are minutes after midnight."""

    course: str
    date: date
    start: int
    end: int


def _parse_time(value: str, column: str, line: int) -> int:
    match = _TIME_RE.fullmatch(value.strip())
    if match is None:
        raise PlannerError(
            f"line {line}: invalid {column} time {value!r}; expected 24-hour HH:MM"
        )
    hour, minute = map(int, match.groups())
    return hour * 60 + minute


def load_exams(path: str | Path) -> list[Exam]:
    """Load exam CSV with columns course,date,start,end.

    Date values must be valid ISO dates (YYYY-MM-DD); time intervals are
    same-day, half-open intervals with end later than start.
    """
    try:
        source = open(path, "r", newline="", encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise PlannerError(f"line 1: cannot read exams file {str(path)!r}: {exc}") from exc

    exams: list[Exam] = []
    with source:
        try:
            reader = csv.DictReader(source, skipinitialspace=True, strict=True)
            headers = reader.fieldnames
            if headers is None:
                raise PlannerError("line 1: empty CSV file (missing header)")
            clean_headers = [header.strip() if header is not None else "" for header in headers]
            if len(clean_headers) != len(set(clean_headers)):
                raise PlannerError("line 1: duplicate CSV column name")
            missing = [column for column in COLUMNS if column not in clean_headers]
            if missing:
                raise PlannerError("line 1: missing required column(s): " + ", ".join(missing))
            reader.fieldnames = clean_headers
            for row in reader:
                line = reader.line_num
                if None in row and not any(value for key, value in row.items() if key is not None):
                    continue
                if None in row:
                    raise PlannerError(f"line {line}: too many CSV fields")
                if any(value is None for value in row.values()):
                    raise PlannerError(f"line {line}: too few CSV fields")
                data = {key: (value or "").strip() for key, value in row.items()}
                for name in COLUMNS:
                    if not data.get(name):
                        raise PlannerError(f"line {line}: {name} must not be empty")
                raw_date = data["date"]
                if not _DATE_RE.fullmatch(raw_date):
                    raise PlannerError(
                        f"line {line}: invalid date {raw_date!r}; expected YYYY-MM-DD"
                    )
                try:
                    exam_date = date.fromisoformat(raw_date)
                except ValueError as exc:
                    raise PlannerError(f"line {line}: invalid date {raw_date!r}") from exc
                start = _parse_time(data["start"], "start", line)
                end = _parse_time(data["end"], "end", line)
                if end <= start:
                    raise PlannerError(f"line {line}: end time must be later than start time")
                exams.append(Exam(data["course"], exam_date, start, end))
        except csv.Error as exc:
            raise PlannerError(f"line {reader.line_num}: invalid CSV: {exc}") from exc
        except UnicodeError as exc:
            raise PlannerError(f"line {reader.line_num}: invalid text encoding: {exc}") from exc
    if not exams:
        raise PlannerError("line 1: exams CSV contains no data rows")
    return exams


def find_exam_clashes(
    exams: list[Exam], courses: list[str] | tuple[str, ...]
) -> list[tuple[Exam, Exam]]:
    """Return overlapping exam pairs for the requested courses, in input order.

    This includes clashes between two exams belonging to the same course.
    Intervals are half-open, so one exam ending exactly when another starts
    does not clash. Each requested course must occur in the exam data.
    """
    selected = list(dict.fromkeys(courses))
    available = {exam.course for exam in exams}
    unknown = [course for course in selected if course not in available]
    if unknown:
        raise PlannerError("unknown course(s) in exams file: " + ", ".join(unknown))
    selected_set = set(selected)
    chosen = [exam for exam in exams if exam.course in selected_set]
    return [
        (first, second)
        for first, second in combinations(chosen, 2)
        if first.date == second.date
        and first.start < second.end
        and second.start < first.end
    ]
