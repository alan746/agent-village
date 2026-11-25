"""Render meetings as a weekly text grid."""

from collections import defaultdict

from planner.model import Section

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DEFAULT_START = 8 * 60
DEFAULT_END = 21 * 60
LABEL = 5  # width of "HH:MM"
DEFAULT_WIDTH = 18


def _hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _block(row: Section) -> int:
    """Grid row index (relative hours from the first hour of the grid)."""
    return row.start // 60


def active_days(rows: list[Section]) -> list[str]:
    """Days (Mon..Sun order) on which at least one meeting happens."""
    present = {row.day for row in rows}
    return [day for day in DAYS if day in present]


def _label(row: Section) -> str:
    text = f"{row.course} {row.section}".strip()
    if row.location:
        text += f" {row.location}"
    return text


def _visible(rows: list[Section], start: int, end: int) -> list[Section]:
    return [row for row in rows if row.end > start and row.start < end]


def _layout(slots: list[Section], width: int, *, clip_start: int) -> list[str]:
    """Split one hour cell into lines shared by every meeting starting there."""
    pieces = []
    for row in slots:
        first = _hm(max(row.start, clip_start))
        last = _hm(row.end)
        pieces.append([first + "-" + last, _label(row)])
    if not pieces:
        return []
    lines = []
    for index in range(max(len(p) for p in pieces)):
        line = " ".join(p[index] if index < len(p) else "" for p in pieces)
        lines.append(line[: width - 1])
    return lines


def render(
    rows: list[Section],
    *,
    start: int | None = None,
    end: int | None = None,
    width: int = DEFAULT_WIDTH,
    days: list[str] | None = None,
) -> str:
    """Return an ASCII weekly grid.

    ``start``/``end`` confine the grid to hours (minutes after midnight); by
    default the grid spans the meetings. ``days`` forces the columns, otherwise
    only days with a meeting are shown. Each cell lists every meeting that
    starts in that hour.
    """
    if width < 12:
        raise ValueError("cell width must be at least 12 characters")
    chosen = list(days) if days is not None else active_days(rows)
    bad = [day for day in chosen if day not in DAYS]
    if bad:
        raise ValueError("unknown day(s): " + ", ".join(bad))
    if not chosen:
        return "(no meetings)\n"
    low = start if start is not None else min((r.start for r in rows), default=DEFAULT_START)
    high = end if end is not None else max((r.end for r in rows), default=DEFAULT_END)
    low -= low % 60
    high = min(24 * 60, -(-high // 60) * 60)
    if low >= high:
        raise ValueError("grid start must be before grid end")
    visible = _visible(rows, low, high)
    if not visible:
        return "(no meetings)\n"

    first_col = LABEL + 1
    total = first_col + len(chosen) * (width + 1)

    def line_of(lead: str, cells: dict[int, str]) -> str:
        out = [" "] * total
        for i, char in enumerate(lead):
            out[i] = char
        for index, text in cells.items():
            base = first_col + index * (width + 1)
            for i, char in enumerate(text[:width]):
                out[base + i] = char
        return "".join(out).rstrip()

    header = {
        index: day.center(width) for index, day in enumerate(chosen)
    }
    lines = [line_of("", header)]
    by_day: dict[str, list[Section]] = defaultdict(list)
    for row in visible:
        if row.day in chosen:
            by_day[row.day].append(row)
    for day in by_day:
        by_day[day].sort(key=lambda r: (r.start, r.end, r.course, r.section))

    for slot_start in range(low, high, 60):
        cells = {
            index: _layout(
                [
                    r for r in by_day.get(day, [])
                    if max((r.start // 60) * 60, low) == slot_start
                ],
                width,
                clip_start=low,
            )
            for index, day in enumerate(chosen)
        }
        depth = max((len(c) for c in cells.values()), default=0)
        if depth == 0:
            lines.append(line_of(f"{_hm(slot_start)}|", {}))
            continue
        for depth_index in range(depth):
            label = f"{_hm(slot_start)}|" if depth_index == 0 else "     |"
            row_cells = {
                index: (c[depth_index] if depth_index < len(c) else " ")
                for index, c in cells.items()
            }
            lines.append(line_of(label, row_cells))
    return "\n".join(lines) + "\n"
