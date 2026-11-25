"""Building lookup and walking-time warnings for consecutive classes."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from planner.model import PlannerError, Section
from planner.solver import Choice

EARTH_RADIUS_KM = 6371.0088
DEFAULT_WALK_SPEED_KMH = 5.0


@dataclass(frozen=True)
class Building:
    """A named building and its geographic coordinates in decimal degrees."""

    name: str
    latitude: float
    longitude: float


def load_buildings(path: str | Path) -> dict[str, Building]:
    """Load named buildings from CSV columns ``building,lat,lon``.

    For compatibility with descriptive headings, ``latitude`` and ``longitude``
    are accepted in place of ``lat`` and ``lon``. Building names are matched
    exactly to ``Section.location``.
    """
    source_path = Path(path)
    try:
        source = source_path.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as exc:
        raise PlannerError(f"line 1: cannot read buildings file {str(source_path)!r}: {exc}") from exc

    buildings: dict[str, Building] = {}
    with source:
        reader = csv.DictReader(source, strict=True)
        try:
            header = reader.fieldnames
            if not header:
                raise PlannerError("line 1: buildings CSV is empty")
            normalized = [name.strip().lower() if name else "" for name in header]
            if len(normalized) != len(set(normalized)):
                raise PlannerError("line 1: buildings CSV has duplicate column names")
            columns = dict(zip(normalized, header))
            lat_col = columns.get("lat") or columns.get("latitude")
            lon_col = columns.get("lon") or columns.get("longitude")
            missing = [name for name, actual in (("building", columns.get("building")), ("lat/latitude", lat_col), ("lon/longitude", lon_col)) if actual is None]
            if missing:
                raise PlannerError(f"line 1: buildings CSV missing required column(s): {', '.join(missing)}")

            for row in reader:
                line = reader.line_num
                if None in row:
                    raise PlannerError(f"line {line}: too many CSV fields")
                if any(value is None for value in row.values()):
                    raise PlannerError(f"line {line}: too few CSV fields")
                name = (row.get(columns["building"]) or "").strip()
                lat_text = (row.get(lat_col) or "").strip()
                lon_text = (row.get(lon_col) or "").strip()
                if not name:
                    raise PlannerError(f"line {line}: building must not be empty")
                if not lat_text:
                    raise PlannerError(f"line {line}: latitude must not be empty")
                if not lon_text:
                    raise PlannerError(f"line {line}: longitude must not be empty")
                try:
                    latitude = float(lat_text)
                    longitude = float(lon_text)
                except ValueError:
                    raise PlannerError(f"line {line}: invalid coordinates for building {name!r}") from None
                if not math.isfinite(latitude) or not -90 <= latitude <= 90:
                    raise PlannerError(f"line {line}: latitude for building {name!r} must be between -90 and 90")
                if not math.isfinite(longitude) or not -180 <= longitude <= 180:
                    raise PlannerError(f"line {line}: longitude for building {name!r} must be between -180 and 180")
                if name in buildings:
                    raise PlannerError(f"line {line}: duplicate building {name!r}")
                buildings[name] = Building(name, latitude, longitude)
        except csv.Error as exc:
            raise PlannerError(f"line {reader.line_num}: invalid CSV: {exc}") from exc
        except UnicodeError as exc:
            raise PlannerError(f"line {reader.line_num}: invalid text encoding: {exc}") from exc
    if not buildings:
        raise PlannerError("line 1: buildings CSV contains no data rows")
    return buildings


def haversine_km(first: Building, second: Building) -> float:
    """Return great-circle distance between two buildings in kilometres."""
    lat1, lat2 = math.radians(first.latitude), math.radians(second.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(second.longitude - first.longitude)
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(value)))


def _meetings(schedule: Iterable[Choice | Section]) -> list[Section]:
    result: list[Section] = []
    for item in schedule:
        if isinstance(item, Section):
            result.append(item)
        elif isinstance(item, Choice):
            result.extend(item.meetings)
        elif hasattr(item, "meetings"):
            result.extend(item.meetings)  # supports RankedSchedule without an import cycle
        else:
            raise PlannerError(f"unsupported schedule item: {type(item).__name__}")
    return result


def travel_warnings(
    schedule: Iterable[Choice | Section],
    buildings: Mapping[str, Building],
    walk_speed: float = DEFAULT_WALK_SPEED_KMH,
) -> list[str]:
    """Return warnings for unknown locations or tight walks between classes.

    Consecutive non-overlapping classes on a day are checked. Walking time is
    straight-line distance / ``walk_speed``; callers can choose a conservative
    speed to account for campus paths and accessibility constraints.
    """
    try:
        speed = float(walk_speed)
    except (TypeError, ValueError):
        raise PlannerError("walk speed must be a positive finite number of km/h") from None
    if not math.isfinite(speed) or speed <= 0:
        raise PlannerError("walk speed must be a positive finite number of km/h")

    meetings = _meetings(schedule)
    warnings: list[str] = []
    unknown_seen: set[tuple[str, str, str]] = set()
    for meeting in meetings:
        if meeting.location not in buildings:
            key = (meeting.course, meeting.section, meeting.location)
            if key not in unknown_seen:
                unknown_seen.add(key)
                warnings.append(
                    f"warning: unknown building/location {meeting.location!r} for {meeting.course} {meeting.section}"
                )

    by_day: dict[str, list[Section]] = {}
    for meeting in meetings:
        by_day.setdefault(meeting.day, []).append(meeting)
    walking_seen: set[str] = set()
    for day in sorted(by_day):
        ordered = sorted(by_day[day], key=lambda meeting: (meeting.start, meeting.end, meeting.course, meeting.section))
        for index, first in enumerate(ordered):
            # Intervening meetings may overlap ``first``. Find the next meeting
            # that starts after it ends instead of considering only the adjacent
            # list item (which may be one of those overlapping meetings).
            second = next((meeting for meeting in ordered[index + 1:] if meeting.start >= first.end), None)
            if second is None:
                continue
            gap = second.start - first.end
            first_building = buildings.get(first.location)
            second_building = buildings.get(second.location)
            if first_building is None or second_building is None:
                continue
            distance = haversine_km(first_building, second_building)
            needed = distance / speed * 60
            if gap < needed:
                warning = (
                    f"warning: {day} {first.course} {first.section} at {first.location!r} to "
                    f"{second.course} {second.section} at {second.location!r}: {distance:.1f} km "
                    f"needs about {needed:.1f} min to walk at {speed:g} km/h, but only {gap} min available"
                )
                if warning not in walking_seen:
                    walking_seen.add(warning)
                    warnings.append(warning)
    return warnings
