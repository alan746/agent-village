"""Read section data from CSV files."""

import csv
import re
from pathlib import Path
from typing import TextIO

from planner.model import PlannerError, Section

COLUMNS = ("course", "section", "day", "start", "end", "location")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
#: ``24:00`` is accepted as an *end* time (end of day) but never as a start.
_TIME_RE = re.compile(r"^([01][0-9]|2[0-3]|24):([0-5][0-9])$")


def _parse_time(value: str, *, column: str, line: int) -> int:
    match = _TIME_RE.fullmatch(value.strip())
    if match is None:
        raise PlannerError(
            f"line {line}: invalid {column} time {value!r}; expected 24-hour HH:MM"
        )
    hour, minute = map(int, match.groups())
    if hour == 24 and minute:
        raise PlannerError(
            f"line {line}: invalid {column} time {value!r}; expected 24-hour HH:MM"
        )
    return hour * 60 + minute


def _reader(source: TextIO):
    try:
        reader = csv.DictReader(source, skipinitialspace=True, strict=True)
        headers = reader.fieldnames
        if headers is None:
            raise PlannerError("line 1: empty CSV file (missing header)")
        # Strip surrounding whitespace in headers, but do not silently accept
        # duplicate names (DictReader would otherwise discard a column).
        clean_headers = [h.strip() if h is not None else "" for h in headers]
        if len(clean_headers) != len(set(clean_headers)):
            raise PlannerError("line 1: duplicate CSV column name")
        missing = [name for name in COLUMNS if name not in clean_headers]
        if missing:
            raise PlannerError("line 1: missing required column(s): " + ", ".join(missing))
        reader.fieldnames = clean_headers
        return reader
    except csv.Error as exc:
        raise PlannerError(f"line 1: invalid CSV: {exc}") from exc
    except UnicodeError as exc:
        raise PlannerError(f"line 1: invalid text encoding: {exc}") from exc


def load_sections(path: str | Path) -> list[Section]:
    """Load, validate, and return meeting rows in file order.

    Extra CSV columns are ignored, allowing datasets to carry annotations.
    Blank physical rows are ignored by :mod:`csv`'s DictReader.
    """
    try:
        source = open(path, "r", newline="", encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise PlannerError(f"line 1: cannot read sections file {str(path)!r}: {exc}") from exc

    sections: list[Section] = []
    with source:
        reader = _reader(source)
        try:
            for row in reader:
                line = reader.line_num
                # An entirely blank line is returned as {None: []}.
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
                day = data["day"]
                if day not in DAYS:
                    raise PlannerError(
                        f"line {line}: invalid day {day!r}; expected Mon, Tue, Wed, Thu, Fri, Sat, or Sun"
                    )
                start = _parse_time(data["start"], column="start", line=line)
                if start == 24 * 60:
                    raise PlannerError(
                        f"line {line}: invalid start time '24:00'; a class cannot begin at the end of the day"
                    )
                end = _parse_time(data["end"], column="end", line=line)
                if end <= start:
                    raise PlannerError(f"line {line}: end time must be later than start time")
                sections.append(Section(data["course"], data["section"], day, start, end, data["location"]))
        except csv.Error as exc:
            raise PlannerError(f"line {reader.line_num}: invalid CSV: {exc}") from exc
        except UnicodeError as exc:
            raise PlannerError(f"line {reader.line_num}: invalid text encoding: {exc}") from exc
    if not sections:
        raise PlannerError("line 1: sections CSV contains no data rows")
    return sections
