"""Generate a large but satisfiable timetable for the M2 benchmark.

Forty courses with five sections each, every section a one-hour class on one
day. To make the instance realistically hard yet definitely solvable, a hidden
"master plan" is drawn first: each course gets its own day and hour, so the
sections that follow the master plan never clash with each other. The other
four sections are random noise, which creates plenty of partial clashes.

The master-plan slot is given a random section number within each course and
the other sections are noise, so the instance is solvable but neither "first
section" nor "last section" happens to be the answer.

Usage: ``python tests/make_bench.py`` writes ``tests/data/bench_40x5.csv``.
"""

import csv
import random
from pathlib import Path

COURSES = 40
SECTIONS_PER_COURSE = 5
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
# Hourly starts 08:00-19:00; the master plan uses distinct (day, hour)
# cells, so its classes never overlap.
HOURS = range(8, 19)
LOCATIONS = ("Hall A", "Science Center", "Engineering Hall", "Math Hall", "Library")
DEFAULT_PATH = Path(__file__).with_name("data") / "bench_40x5.csv"


def generate(seed: int = 20240) -> list[tuple[str, str, str, str, str, str]]:
    """Return ``(course, section, day, start, end, location)`` rows."""
    rng = random.Random(seed)
    rng_shuffle = random.Random(seed + 7919)
    plan: list[tuple[str, int]] = []
    # Distinct (day, hour) pairs keep the master plan clash-free.
    cells = [(day, hour) for day in DAYS for hour in HOURS]
    rng.shuffle(cells)
    if COURSES > len(cells):
        raise ValueError("not enough distinct slots for a clash-free master plan")
    plan = cells[:COURSES]

    rows = []
    for index, (day, hour) in enumerate(plan):
        course = f"C{index:02d}"
        # A clash-free plan for this course is added under a random section
        # number; the other sections are drawn from a fresh shuffle of every
        # slot, so taking "the first section" or "the last section" does not
        # work and the solver has to actually search.
        others = list(cells)
        rng_shuffle.shuffle(others)
        plan_section = rng.randrange(SECTIONS_PER_COURSE)
        slots = [*others[: SECTIONS_PER_COURSE - 1]]
        slots.insert(plan_section, (day, hour))
        for section, (slot_day, slot_hour) in enumerate(slots):
            rows.append(
                (
                    course,
                    f"S{section}",
                    slot_day,
                    f"{slot_hour:02d}:00",
                    f"{slot_hour + 1:02d}:00",
                    rng.choice(LOCATIONS),
                )
            )
    return rows


def write(path: Path = DEFAULT_PATH, seed: int = 20240) -> Path:
    rows = generate(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("course", "section", "day", "start", "end", "location"))
        writer.writerows(rows)
    return path


if __name__ == "__main__":
    print(write())
