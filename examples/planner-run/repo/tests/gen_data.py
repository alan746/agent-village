"""Synthetic data generator for benchmark and fuzz testing."""

import argparse
import csv
import io
import random
from pathlib import Path
from typing import Sequence

DEFAULT_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
DEFAULT_LOCATIONS = (
    "Hall A",
    "Science Center",
    "Engineering Hall",
    "Math Hall",
    "Arts Building",
    "Library",
)

# Standard class time blocks in 24-hour HH:MM (start, end)
DEFAULT_TIME_SLOTS = (
    ("08:30", "09:30"),
    ("09:00", "10:00"),
    ("09:30", "10:30"),
    ("10:00", "11:00"),
    ("10:00", "11:30"),
    ("11:00", "12:00"),
    ("11:30", "13:00"),
    ("12:00", "13:00"),
    ("13:00", "14:00"),
    ("13:00", "14:30"),
    ("14:00", "15:00"),
    ("14:30", "16:00"),
    ("15:00", "16:00"),
    ("15:30", "17:00"),
    ("16:00", "17:00"),
    ("16:00", "17:30"),
    ("17:00", "18:00"),
)


def generate_sections(
    num_courses: int,
    sections_per_course: int,
    *,
    seed: int | None = None,
    days: Sequence[str] = DEFAULT_DAYS,
    locations: Sequence[str] = DEFAULT_LOCATIONS,
    time_slots: Sequence[tuple[str, str]] = DEFAULT_TIME_SLOTS,
    meetings_per_section: int = 1,
) -> list[dict[str, str]]:
    """Generate section records as dictionaries matching the standard CSV schema."""
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []

    for c_idx in range(1, num_courses + 1):
        course = f"COURSE{c_idx:03d}"
        for s_idx in range(1, sections_per_course + 1):
            section = f"S{s_idx:02d}"
            # Choose distinct days for meetings of the same section if possible
            chosen_days = rng.sample(list(days), k=min(meetings_per_section, len(days)))
            start, end = rng.choice(time_slots)
            loc = rng.choice(locations)
            for d in chosen_days:
                rows.append({
                    "course": course,
                    "section": section,
                    "day": d,
                    "start": start,
                    "end": end,
                    "location": loc,
                })

    return rows


def generate_csv(
    num_courses: int,
    sections_per_course: int,
    *,
    seed: int | None = None,
    **kwargs,
) -> str:
    """Generate CSV text containing the requested course sections."""
    rows = generate_sections(num_courses, sections_per_course, seed=seed, **kwargs)
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["course", "section", "day", "start", "end", "location"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def write_sections_csv(
    path: str | Path,
    num_courses: int,
    sections_per_course: int,
    *,
    seed: int | None = None,
    **kwargs,
) -> None:
    """Write generated sections directly to a file."""
    content = generate_csv(num_courses, sections_per_course, seed=seed, **kwargs)
    Path(path).write_text(content, encoding="utf-8")


MUTATION_TYPES = (
    "missing_column",
    "duplicate_column",
    "bad_day",
    "bad_time_format",
    "end_before_start",
    "empty_file",
    "extra_field",
    "missing_value",
    "non_utf8",
)


def corrupt_csv(
    csv_text: str,
    mutation_type: str | None = None,
    *,
    seed: int | None = None,
) -> str | bytes:
    """Introduce an intentional formatting error into CSV text for fuzzing."""
    rng = random.Random(seed)
    chosen_type = mutation_type or rng.choice(MUTATION_TYPES)

    if chosen_type == "empty_file":
        return ""

    if chosen_type == "missing_column":
        # Remove a required column header and its values
        lines = csv_text.splitlines()
        header = lines[0].split(",")
        col_to_drop = rng.randint(0, len(header) - 1)
        new_lines = []
        for line in lines:
            parts = line.split(",")
            if len(parts) > col_to_drop:
                parts.pop(col_to_drop)
            new_lines.append(",".join(parts))
        return "\n".join(new_lines) + "\n"

    if chosen_type == "duplicate_column":
        lines = csv_text.splitlines()
        if lines:
            lines[0] = lines[0] + ",course"
            for i in range(1, len(lines)):
                lines[i] = lines[i] + ",EXTRA"
        return "\n".join(lines) + "\n"

    if chosen_type == "bad_day":
        lines = csv_text.splitlines()
        if len(lines) > 1:
            idx = rng.randint(1, len(lines) - 1)
            parts = lines[idx].split(",")
            if len(parts) >= 3:
                parts[2] = rng.choice(["Monday", "SunDay", "Funday", "Xyz", "12"])
                lines[idx] = ",".join(parts)
        return "\n".join(lines) + "\n"

    if chosen_type == "bad_time_format":
        lines = csv_text.splitlines()
        if len(lines) > 1:
            idx = rng.randint(1, len(lines) - 1)
            parts = lines[idx].split(",")
            if len(parts) >= 5:
                bad_val = rng.choice(["25:00", "09:60", "9:00", "noon", "9am", "-01:00"])
                target_col = rng.choice([3, 4])
                parts[target_col] = bad_val
                lines[idx] = ",".join(parts)
        return "\n".join(lines) + "\n"

    if chosen_type == "end_before_start":
        lines = csv_text.splitlines()
        if len(lines) > 1:
            idx = rng.randint(1, len(lines) - 1)
            parts = lines[idx].split(",")
            if len(parts) >= 5:
                # Set end time earlier than or equal to start time
                parts[3] = "14:00"
                parts[4] = "13:00"
                lines[idx] = ",".join(parts)
        return "\n".join(lines) + "\n"

    if chosen_type == "extra_field":
        lines = csv_text.splitlines()
        if len(lines) > 1:
            idx = rng.randint(1, len(lines) - 1)
            lines[idx] = lines[idx] + ",extra_value"
        return "\n".join(lines) + "\n"

    if chosen_type == "missing_value":
        lines = csv_text.splitlines()
        if len(lines) > 1:
            idx = rng.randint(1, len(lines) - 1)
            parts = lines[idx].split(",")
            if parts:
                col = rng.randint(0, len(parts) - 1)
                parts[col] = ""
                lines[idx] = ",".join(parts)
        return "\n".join(lines) + "\n"

    if chosen_type == "non_utf8":
        # Returns invalid bytes that cannot be decoded as utf-8
        return (csv_text.encode("utf-8") + b"\xff\xfe\xfa")

    return csv_text


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic sections CSV.")
    parser.add_argument(
        "-c", "--courses", type=int, default=40, help="Number of courses (default: 40)"
    )
    parser.add_argument(
        "-s",
        "--sections",
        type=int,
        default=5,
        help="Sections per course (default: 5)",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="Output file path (default: stdout)"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument(
        "--corrupt",
        choices=MUTATION_TYPES,
        default=None,
        help="Introduce an intentional corruption for fuzz testing",
    )
    parsed = parser.parse_args(args)

    content = generate_csv(parsed.courses, parsed.sections, seed=parsed.seed)
    if parsed.corrupt:
        corrupted = corrupt_csv(content, mutation_type=parsed.corrupt, seed=parsed.seed)
        if isinstance(corrupted, bytes):
            if parsed.output:
                Path(parsed.output).write_bytes(corrupted)
            else:
                import sys
                sys.stdout.buffer.write(corrupted)
            return 0
        content = corrupted

    if parsed.output:
        Path(parsed.output).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
