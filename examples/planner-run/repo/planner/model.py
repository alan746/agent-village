"""Core data types and user-facing errors for planner."""

from dataclasses import dataclass


class PlannerError(Exception):
    """An invalid planner input or an impossible planning request."""


@dataclass(frozen=True)
class Section:
    """One meeting of a course section; times are minutes after midnight."""

    course: str
    section: str
    day: str
    start: int
    end: int
    location: str
