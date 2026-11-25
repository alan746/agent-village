"""Tests for iCalendar (.ics) and HTML exports."""

import re
from datetime import date
from pathlib import Path

import pytest
from icalendar import Calendar

from planner.export import (
    _fold_ics_line,
    _parse_term_start,
    add_export_arguments,
    export_schedule,
    to_html,
    to_ics,
)
from planner.model import PlannerError, Section
from planner.solver import Choice


@pytest.fixture
def sample_schedule():
    return [
        Choice(
            course="CS101",
            section="A",
            meetings=[
                Section("CS101", "A", "Mon", 9 * 60, 10 * 60, "Hall A"),
                Section("CS101", "A", "Wed", 9 * 60, 10 * 60, "Hall A"),
                Section("CS101", "A", "Fri", 9 * 60, 10 * 60, "Hall A"),
            ],
        ),
        Choice(
            course="MATH101",
            section="B",
            meetings=[
                Section("MATH101", "B", "Tue", 10 * 60 + 30, 12 * 60, "Math 202"),
                Section("MATH101", "B", "Thu", 10 * 60 + 30, 12 * 60, "Math 202"),
            ],
        ),
    ]


def test_ics_dtstart_weekday_matches_byday_for_every_day_and_term_start():
    # Regex-based ICS readers trust RRULE alone, but iCalendar clients (and
    # ``icalendar``) place the first occurrence on DTSTART. A DTSTART on a
    # different weekday than BYDAY silently moves every meeting, so the anchor
    # date must already be the meeting's weekday.
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    codes = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    for start in (date(2026, 1, 5), date(2025, 9, 1), date(2026, 2, 28)):
        meetings = [Section("Z", "A", day, 9 * 60, 10 * 60, "R") for day in days]
        ics = to_ics(meetings, term_start=start, weeks=3)
        events = [c for c in Calendar.from_ical(ics).walk() if c.name == "VEVENT"]
        assert len(events) == 7
        for event in events:
            byday = str(event["RRULE"]["BYDAY"][0])
            dtstart = event["DTSTART"].dt
            assert dtstart.date().weekday() == codes.index(byday), (start, byday, dtstart)
            # And the event really starts on that weekday, not a week later.
            assert (dtstart.date() - start).days < 7


def test_ics_dtstart_weekday_matches_byday_for_a_late_term_start_week():
    # The anchor must be a date that really is the meeting's weekday, without
    # jumping into the next week: a Thursday term start with a Monday class
    # puts DTSTART on the following Monday and the weekly streak from there.
    ics = to_ics([Section("Z", "A", "Mon", 9 * 60, 10 * 60, "R")], term_start=date(2026, 1, 8))
    event = [c for c in Calendar.from_ical(ics).walk() if c.name == "VEVENT"][0]
    assert event["DTSTART"].dt.date() == date(2026, 1, 12)
    assert event["DTSTART"].dt.weekday() == 0
    assert str(event["RRULE"]["BYDAY"][0]) == "MO"


def test_to_ics_parses_back_with_icalendar(sample_schedule):
    term_start = "2025-09-01"  # A Monday
    ics_text = to_ics(sample_schedule, term_start=term_start, weeks=12)

    assert ics_text.endswith("\r\n")
    # All lines should end with CRLF
    for line in ics_text.splitlines():
        assert len(line.encode("utf-8")) <= 75

    cal = Calendar.from_ical(ics_text)
    assert cal.get("prodid") is not None
    assert cal.get("version") == "2.0"

    events = [comp for comp in cal.walk() if comp.name == "VEVENT"]
    # CS101 has 3 meetings, MATH101 has 2 meetings = 5 events
    assert len(events) == 5

    # Check first event (Mon CS101 A)
    mon_events = [e for e in events if "CS101" in str(e.get("summary")) and "MO" in e.get("rrule")["BYDAY"]]
    assert len(mon_events) == 1
    ev = mon_events[0]
    assert ev.get("summary") == "CS101 A"
    assert ev.get("location") == "Hall A"
    assert ev.get("dtstart").dt.strftime("%Y-%m-%d %H:%M") == "2025-09-01 09:00"
    assert ev.get("dtend").dt.strftime("%Y-%m-%d %H:%M") == "2025-09-01 10:00"
    assert ev.get("rrule")["COUNT"] == [12]
    assert ev.get("rrule")["FREQ"] == ["WEEKLY"]

    # Check Tue event (MATH101 B)
    tue_events = [e for e in events if "MATH101" in str(e.get("summary")) and "TU" in e.get("rrule")["BYDAY"]]
    assert len(tue_events) == 1
    ev_tue = tue_events[0]
    assert ev_tue.get("dtstart").dt.strftime("%Y-%m-%d %H:%M") == "2025-09-02 10:30"
    assert ev_tue.get("dtend").dt.strftime("%Y-%m-%d %H:%M") == "2025-09-02 12:00"


def test_to_ics_escaping_and_folding():
    special_section = [
        Section(
            course="ENG, 101; Spec",
            section="A\\1",
            day="Mon",
            start=14 * 60,
            end=15 * 60 + 30,
            location="Room 101, Bldg A; 2nd Floor, Very Long Corridor Name That Causes Line Folding In The Output \U0001f3eb",
        )
    ]
    ics_text = to_ics(special_section, term_start=date(2025, 9, 1), weeks=10)
    for raw_line in ics_text.split("\r\n"):
        assert len(raw_line.encode("utf-8")) <= 75

    cal = Calendar.from_ical(ics_text)
    events = [comp for comp in cal.walk() if comp.name == "VEVENT"]
    assert len(events) == 1
    ev = events[0]
    assert ev.get("summary") == "ENG, 101; Spec A\\1"
    assert "Very Long Corridor Name" in str(ev.get("location"))


def test_to_ics_strips_prohibited_control_characters():
    # Section with NUL byte and non-printable control characters
    section_with_ctrl = [
        Section(
            course="CS\x00101\x07",
            section="A\x1b",
            day="Mon",
            start=9 * 60,
            end=10 * 60,
            location="Lab\x08 1",
        )
    ]
    ics_text = to_ics(section_with_ctrl, term_start=date(2025, 9, 1))
    assert "\x00" not in ics_text
    assert "\x07" not in ics_text
    assert "\x1b" not in ics_text
    assert "\x08" not in ics_text
    cal = Calendar.from_ical(ics_text)
    events = [comp for comp in cal.walk() if comp.name == "VEVENT"]
    assert len(events) == 1
    assert str(events[0].get("summary")) == "CS101 A"
    assert str(events[0].get("location")) == "Lab 1"


def test_to_ics_uid_uniqueness_with_punctuation_variations():
    sections = [
        Section("CS 101", "A", "Mon", 9 * 60, 10 * 60, "Hall A"),
        Section("CS101", "A", "Mon", 9 * 60, 10 * 60, "Hall A"),
    ]
    ics_text = to_ics(sections, term_start=date(2025, 9, 1))
    cal = Calendar.from_ical(ics_text)
    events = [comp for comp in cal.walk() if comp.name == "VEVENT"]
    assert len(events) == 2
    uids = [str(ev.get("uid")) for ev in events]
    assert len(set(uids)) == 2
    assert uids[0] != uids[1]


def test_to_ics_invalid_inputs():
    sections = [Section("C", "1", "Mon", 9 * 60, 10 * 60, "R")]
    with pytest.raises(PlannerError, match="weeks must be at least 1"):
        to_ics(sections, weeks=0)
    with pytest.raises(PlannerError, match="invalid term start date"):
        to_ics(sections, term_start="not-a-date")
    with pytest.raises(PlannerError, match="invalid term start date type"):
        to_ics(sections, term_start=12345)


def test_parse_term_start_default():
    d = _parse_term_start(None)
    assert isinstance(d, date)
    assert d.weekday() == 0  # Monday


def test_to_html_content_and_safety(sample_schedule):
    html_text = to_html(sample_schedule, title="Fall 2025 Timetable")
    assert "<!DOCTYPE html>" in html_text
    assert "<title>Fall 2025 Timetable</title>" in html_text
    assert "CS101" in html_text
    assert "MATH101" in html_text
    assert "Hall A" in html_text
    assert "Math 202" in html_text
    # Check self-contained: no external links
    assert "<link" not in html_text
    assert "<script" not in html_text
    assert "@import" not in html_text


def test_to_html_multi_hour_continuation():
    schedule = [
        Section("PHYS301", "Lab", "Wed", 9 * 60, 12 * 60, "Physics Lab"),
    ]
    html_text = to_html(schedule)
    # Row 09:00 should have primary card
    assert "PHYS301 Lab" in html_text
    # Continuation badge should be present for subsequent hours (10:00 and 11:00)
    assert "continuation" in html_text
    assert "(cont.)" in html_text
    # Count occurrences of PHYS301 in the table
    # Should appear 3 times in grid (hour 9, 10, 11) plus once in summary = 4 times
    assert html_text.count("PHYS301") == 4


def test_to_html_escaping():
    dangerous = [
        Section(
            course="<script>alert(1)</script>",
            section="A & B",
            day="Wed",
            start=11 * 60,
            end=12 * 60,
            location='Hall "Dangerous" <Room>',
        )
    ]
    html_text = to_html(dangerous)
    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
    assert "A &amp; B" in html_text
    assert "Hall &quot;Dangerous&quot; &lt;Room&gt;" in html_text


def test_to_html_empty_schedule():
    html_text = to_html([])
    assert "<!DOCTYPE html>" in html_text
    assert "Mon" in html_text
    assert "Fri" in html_text


def test_to_ics_skips_unknown_day():
    # Construct meeting with invalid day
    invalid_day_section = [Section("X", "1", "Holiday", 9 * 60, 10 * 60, "Room")]
    ics = to_ics(invalid_day_section, term_start=date(2025, 9, 1))
    cal = Calendar.from_ical(ics)
    assert len([e for e in cal.walk() if e.name == "VEVENT"]) == 0


def test_export_schedule_to_disk(tmp_path, sample_schedule):
    ics_file = tmp_path / "term.ics"
    html_file = tmp_path / "term.html"

    export_schedule(sample_schedule, ics_path=ics_file, html_path=html_file, term_start="2025-09-01", weeks=10)

    assert ics_file.exists()
    assert html_file.exists()
    assert "BEGIN:VCALENDAR" in ics_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_file.read_text(encoding="utf-8")


def test_export_schedule_write_error(sample_schedule):
    with pytest.raises(PlannerError, match="cannot write iCalendar export"):
        export_schedule(sample_schedule, ics_path="/dev/null/impossible.ics")
    with pytest.raises(PlannerError, match="cannot write HTML export"):
        export_schedule(sample_schedule, html_path="/dev/null/impossible.html")


def test_add_export_arguments():
    import argparse
    parser = argparse.ArgumentParser()
    add_export_arguments(parser)
    args = parser.parse_args(["--ics", "out.ics", "--html", "out.html", "--weeks", "16", "--term-start", "2025-10-01"])
    assert args.ics == "out.ics"
    assert args.html == "out.html"
    assert args.weeks == 16
    assert args.term_start == "2025-10-01"


def test_fold_line_multibyte_split():
    # 74 ASCII 'a's followed by a 4-byte emoji
    line = "a" * 74 + "\U0001f3eb" + "end"
    folded = _fold_ics_line(line, limit=75)
    for part in folded.split("\r\n"):
        assert len(part.encode("utf-8")) <= 75
    # Unfolding reproduces line
    unfolded = folded.replace("\r\n ", "")
    assert unfolded == line
