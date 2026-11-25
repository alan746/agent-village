"""Export schedules to iCalendar (.ics) and HTML weekly views."""

import hashlib
import html
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Sequence

from planner.model import PlannerError, Section
from planner.solver import Choice

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_INDEX = {day: i for i, day in enumerate(DAYS)}
ICS_DAY_CODE = {
    "Mon": "MO",
    "Tue": "TU",
    "Wed": "WE",
    "Thu": "TH",
    "Fri": "FR",
    "Sat": "SA",
    "Sun": "SU",
}


def _normalize_meetings(schedule: Sequence[Choice | Section]) -> list[Section]:
    """Extract a flat list of Section meetings from a schedule of Choice or Section items."""
    meetings: list[Section] = []
    for item in schedule:
        if isinstance(item, Choice):
            meetings.extend(item.meetings)
        elif isinstance(item, Section):
            meetings.append(item)
        elif hasattr(item, "meetings"):
            meetings.extend(item.meetings)  # type: ignore[union-attr]
        else:
            meetings.append(item)  # type: ignore[arg-type]
    return meetings


def _parse_term_start(term_start: date | str | None) -> date:
    """Parse or default the term start date. Defaults to next Monday (or today if Monday)."""
    if term_start is None:
        today = date.today()
        days_ahead = (0 - today.weekday()) % 7
        return today + timedelta(days=days_ahead)
    if isinstance(term_start, str):
        try:
            return date.fromisoformat(term_start)
        except ValueError:
            raise PlannerError(
                f"invalid term start date {term_start!r}; expected YYYY-MM-DD"
            ) from None
    if isinstance(term_start, date):
        return term_start
    raise PlannerError(f"invalid term start date type: {type(term_start).__name__}")


def _escape_ics_text(text: str) -> str:
    """Escape text for RFC 5545 iCalendar values and strip prohibited control characters."""
    # Strip prohibited control characters per RFC 5545 section 3.3.11 (TEXT excludes controls except TAB/CR/LF)
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
    text = text.replace("\\", "\\\\")
    text = text.replace(";", r"\;")
    text = text.replace(",", r"\,")
    text = text.replace("\r\n", r"\n").replace("\r", r"\n").replace("\n", r"\n")
    return text


def _fold_ics_line(line: str, limit: int = 75) -> str:
    """Fold a line according to RFC 5545 section 3.1 (max 75 octets)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return line
    parts: list[str] = []
    cut = limit
    while cut > 0:
        try:
            parts.append(encoded[:cut].decode("utf-8"))
            encoded = encoded[cut:]
            break
        except UnicodeDecodeError:
            cut -= 1
    while len(encoded) > 0:
        chunk_limit = limit - 1
        cut = min(chunk_limit, len(encoded))
        while cut > 0:
            try:
                parts.append(" " + encoded[:cut].decode("utf-8"))
                encoded = encoded[cut:]
                break
            except UnicodeDecodeError:
                cut -= 1
    return "\r\n".join(parts)


def to_ics(
    schedule: Sequence[Choice | Section],
    term_start: date | str | None = None,
    weeks: int = 14,
) -> str:
    """Export a schedule to RFC 5545 iCalendar text (.ics).

    Each section meeting becomes a recurring VEVENT with weekly RRULE.
    Times are represented as floating local times (no TZID), which standard calendar
    applications interpret in the viewer's active time zone.
    Lines are CRLF-terminated and folded at 75 octets.
    """
    if weeks < 1:
        raise PlannerError("weeks must be at least 1")
    start_date = _parse_term_start(term_start)
    meetings = _normalize_meetings(schedule)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Village Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for idx, meeting in enumerate(meetings):
        day_idx = DAY_INDEX.get(meeting.day)
        if day_idx is None:
            continue
        start_time = time(meeting.start // 60, meeting.start % 60)
        end_time = time(meeting.end // 60, meeting.end % 60)

        # Anchor the first occurrence on a date that really is ``meeting.day``,
        # in the week starting ``term_start``: clients (and ``icalendar``) put
        # the first occurrence on DTSTART, so a DTSTART on another weekday
        # would move the meeting even though RRULE lists the right BYDAY.
        days_offset = (day_idx - start_date.weekday()) % 7
        event_date = start_date + timedelta(days=days_offset)

        dtstart = f"{event_date.strftime('%Y%m%d')}T{start_time.strftime('%H%M%S')}"
        dtend = f"{event_date.strftime('%Y%m%d')}T{end_time.strftime('%H%M%S')}"

        clean_course = re.sub(r"[^A-Za-z0-9_-]", "", meeting.course)
        clean_section = re.sub(r"[^A-Za-z0-9_-]", "", meeting.section)
        # Use sha256 fingerprint to prevent collisions between courses with differing punctuation
        fingerprint = hashlib.sha256(
            f"{meeting.course}\x00{meeting.section}\x00{meeting.location}\x00{idx}".encode("utf-8")
        ).hexdigest()[:8]
        uid = f"{clean_course}-{clean_section}-{meeting.day}-{meeting.start}-{meeting.end}-{event_date.isoformat()}-{fingerprint}@planner"

        summary = _escape_ics_text(f"{meeting.course} {meeting.section}")
        location = _escape_ics_text(meeting.location) if meeting.location else ""
        description = _escape_ics_text(
            f"Course: {meeting.course}\nSection: {meeting.section}\nLocation: {meeting.location}"
        )
        byday = ICS_DAY_CODE.get(meeting.day, "MO")
        rrule = f"FREQ=WEEKLY;COUNT={weeks};BYDAY={byday}"

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"RRULE:{rrule}",
            f"SUMMARY:{summary}",
        ]
        if location:
            event_lines.append(f"LOCATION:{location}")
        event_lines.append(f"DESCRIPTION:{description}")
        event_lines.append("END:VEVENT")

        lines.extend(event_lines)

    lines.append("END:VCALENDAR")

    folded_lines = [_fold_ics_line(line) for line in lines]
    return "\r\n".join(folded_lines) + "\r\n"


def _hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def to_html(
    schedule: Sequence[Choice | Section],
    title: str = "Weekly Class Schedule",
) -> str:
    """Export schedule to a self-contained HTML weekly view.

    Includes inline CSS, no external resources, and HTML-escapes all fields.
    Classes spanning multiple hours visibly occupy every covered hourly row.
    """
    meetings = _normalize_meetings(schedule)
    active = [day for day in DAYS if any(m.day == day for m in meetings)]
    if not active:
        active = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    min_min = min((m.start for m in meetings), default=8 * 60)
    max_min = max((m.end for m in meetings), default=18 * 60)
    start_hour = max(0, (min_min // 60))
    end_hour = min(24, -(-max_min // 60))
    if end_hour <= start_hour:
        end_hour = start_hour + 1

    courses_list: list[dict[str, str]] = []
    for m in sorted(meetings, key=lambda x: (x.course, x.section, DAY_INDEX.get(x.day, 0), x.start)):
        courses_list.append({
            "course": m.course,
            "section": m.section,
            "day": m.day,
            "time": f"{_hm(m.start)} - {_hm(m.end)}",
            "location": m.location,
        })

    # Map (day, hour) -> list of (meeting, is_continuation)
    grid_cells: dict[tuple[str, int], list[tuple[Section, bool]]] = defaultdict(list)
    for m in meetings:
        first_hour = m.start // 60
        # Meeting covers hours from first_hour up to (m.end - 1) // 60 inclusive
        last_hour = (m.end - 1) // 60 if m.end > m.start else first_hour
        for h in range(first_hour, last_hour + 1):
            is_cont = (h > first_hour)
            grid_cells[(m.day, h)].append((m, is_cont))

    hours_rows = []
    for h in range(start_hour, end_hour):
        time_label = f"{h:02d}:00"
        day_cols = []
        for day in active:
            cell_items = grid_cells.get((day, h), [])
            if cell_items:
                items_html = []
                for cm, is_cont in cell_items:
                    if is_cont:
                        items_html.append(
                            f"""<div class="meeting-card continuation">
                                <div class="card-course">{html.escape(cm.course)} {html.escape(cm.section)} <span class="cont-badge">(cont.)</span></div>
                                <div class="card-time">{_hm(cm.start)} - {_hm(cm.end)}</div>
                            </div>"""
                        )
                    else:
                        items_html.append(
                            f"""<div class="meeting-card">
                                <div class="card-course">{html.escape(cm.course)} {html.escape(cm.section)}</div>
                                <div class="card-time">{_hm(cm.start)} - {_hm(cm.end)}</div>
                                <div class="card-loc">{html.escape(cm.location)}</div>
                            </div>"""
                        )
                day_cols.append(f'<td class="cell filled">{"".join(items_html)}</td>')
            else:
                day_cols.append('<td class="cell empty"></td>')
        hours_rows.append(
            f'<tr><th class="time-col">{time_label}</th>{"".join(day_cols)}</tr>'
        )

    table_rows = "".join(hours_rows)
    day_headers = "".join(f"<th>{html.escape(day)}</th>" for day in active)

    summary_rows = "".join(
        f"""<tr>
            <td><strong>{html.escape(item['course'])}</strong></td>
            <td>{html.escape(item['section'])}</td>
            <td>{html.escape(item['day'])}</td>
            <td>{html.escape(item['time'])}</td>
            <td>{html.escape(item['location'])}</td>
        </tr>"""
        for item in courses_list
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
  :root {{
    --bg: #f8fafc;
    --surface: #ffffff;
    --text: #0f172a;
    --muted: #64748b;
    --border: #e2e8f0;
    --primary: #2563eb;
    --card-bg: #eff6ff;
    --card-border: #bfdbfe;
    --card-text: #1e40af;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.5;
  }}
  .container {{
    max-width: 1200px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.75rem;
    font-weight: 700;
    margin-bottom: 8px;
    color: var(--text);
  }}
  .subtitle {{
    color: var(--muted);
    margin-bottom: 24px;
    font-size: 0.95rem;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  .card-title {{
    padding: 14px 18px;
    font-size: 1.1rem;
    font-weight: 600;
    border-bottom: 1px solid var(--border);
    background: #f1f5f9;
  }}
  .timetable-wrapper {{
    overflow-x: auto;
  }}
  table.grid {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  table.grid th, table.grid td {{
    border: 1px solid var(--border);
    padding: 6px;
    vertical-align: top;
  }}
  table.grid th {{
    background: #f8fafc;
    font-weight: 600;
    font-size: 0.85rem;
    text-align: center;
    padding: 10px 6px;
  }}
  table.grid th.time-col {{
    width: 70px;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    font-size: 0.8rem;
    text-align: right;
    padding-right: 8px;
  }}
  td.cell {{
    min-height: 52px;
    height: 52px;
  }}
  td.cell.empty {{
    background: var(--surface);
  }}
  .meeting-card {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-left: 3px solid var(--primary);
    border-radius: 4px;
    padding: 4px 6px;
    margin-bottom: 4px;
    font-size: 0.78rem;
    color: var(--card-text);
  }}
  .meeting-card.continuation {{
    border-left: 3px dashed var(--primary);
    opacity: 0.85;
    background: #f1f5f9;
  }}
  .cont-badge {{
    font-size: 0.72rem;
    color: var(--muted);
    font-weight: normal;
  }}
  .meeting-card .card-course {{
    font-weight: 700;
    font-size: 0.82rem;
  }}
  .meeting-card .card-time {{
    font-variant-numeric: tabular-nums;
    color: var(--muted);
  }}
  .meeting-card .card-loc {{
    font-style: italic;
    color: var(--text);
  }}
  table.summary {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }}
  table.summary th, table.summary td {{
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    text-align: left;
  }}
  table.summary th {{
    background: #f8fafc;
    font-weight: 600;
    color: var(--muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  table.summary tr:last-child td {{
    border-bottom: none;
  }}
  table.summary tr:hover td {{
    background: #f8fafc;
  }}
</style>
</head>
<body>
<div class="container">
  <h1>{html.escape(title)}</h1>
  <div class="subtitle">Generated by Planner</div>

  <div class="card">
    <div class="card-title">Weekly Grid</div>
    <div class="timetable-wrapper">
      <table class="grid">
        <thead>
          <tr>
            <th class="time-col">Time</th>
            {day_headers}
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Course Details</div>
    <table class="summary">
      <thead>
        <tr>
          <th>Course</th>
          <th>Section</th>
          <th>Day</th>
          <th>Time</th>
          <th>Location</th>
        </tr>
      </thead>
      <tbody>
        {summary_rows}
      </tbody>
    </table>
  </div>
</div>
</body>
</html>
"""
    return doc


def export_schedule(
    schedule: Sequence[Choice | Section],
    *,
    ics_path: str | Path | None = None,
    html_path: str | Path | None = None,
    term_start: date | str | None = None,
    weeks: int = 14,
) -> None:
    """Export schedule to file paths for iCalendar (.ics) and/or HTML."""
    if ics_path:
        ics_text = to_ics(schedule, term_start=term_start, weeks=weeks)
        p = Path(ics_path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ics_text, encoding="utf-8")
        except OSError as exc:
            raise PlannerError(f"cannot write iCalendar export '{ics_path}': {exc}") from exc

    if html_path:
        html_text = to_html(schedule)
        p = Path(html_path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(html_text, encoding="utf-8")
        except OSError as exc:
            raise PlannerError(f"cannot write HTML export '{html_path}': {exc}") from exc


def add_export_arguments(parser) -> None:
    """Add export command line flags (--ics, --html, --term-start, --weeks)."""
    parser.add_argument("--ics", metavar="FILE", help="export schedule to iCalendar (.ics) file")
    parser.add_argument("--html", metavar="FILE", help="export schedule to HTML weekly view file")
    parser.add_argument(
        "--term-start",
        metavar="YYYY-MM-DD",
        help="term start date for iCalendar export (default: next Monday)",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=14,
        metavar="N",
        help="number of weeks for recurring iCalendar events (default 14)",
    )


def handle_plan_exports(args, choices: Sequence[Choice | Section]) -> None:
    """Export schedule if --ics or --html arguments were provided."""
    ics_path = getattr(args, "ics", None)
    html_path = getattr(args, "html", None)
    if ics_path or html_path:
        export_schedule(
            choices,
            ics_path=ics_path,
            html_path=html_path,
            term_start=getattr(args, "term_start", None),
            weeks=getattr(args, "weeks", 14),
        )
