"""Fuzz and property tests: every CLI command survives random/malformed input.

The contract under test (see README):

* no command ever raises out of ``planner.cli.main`` and never prints a
  traceback; the exit code is always one of ``{0, 1, 2}``;
* argparse usage errors exit 2 (the argparse convention), everything else
  that fails exits 1 after printing a single ``error: ...`` line;
* ``plan`` only ever prints schedules without overlapping meetings, and for
  small inputs its top result equals brute force;
* exports written by ``plan`` parse back with ``icalendar`` / contain the
  expected escape-free HTML.
"""

import contextlib
import csv
import io
import string
from io import StringIO

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from planner import cli
from planner.csvio import load_sections
from planner.model import Section
from planner.preferences import schedule_order_key
from planner.ranking import search
from planner.solver import solve

ALLOWED_EXIT_CODES = {0, 1, 2}

SECTION_HEADER = "course,section,day,start,end,location\n"
EXAM_HEADER = "course,date,start,end\n"
BUILDING_HEADER = "building,lat,lon\n"

#: Courses used by the plan/show/conflicts commands in the fuzz cases.
COURSE_NAMES = ["A", "B", "C", "D"]
DEFAULT_ORDER = ("days", "early", "gaps", "span")
PATIENCE = 20000  # planner.ranking.DEFAULT_PATIENCE
NO_FIXTURE = [HealthCheck.function_scoped_fixture]


@pytest.fixture()
def write_csv(tmp_path):
    counter = {"n": 0}

    def write(text, name=None):
        counter["n"] += 1
        path = tmp_path / (name or f"in{counter['n']}.csv")
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
        return str(path)

    return write


def run_cli(argv):
    """Run the CLI in-process and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(argv)
        except SystemExit as exc:  # argparse --help/usage errors
            code = exc.code if isinstance(exc.code, int) else 2
    return int(code), out.getvalue(), err.getvalue()


def assert_clean(argv):
    code, out, err = run_cli(argv)
    assert code in ALLOWED_EXIT_CODES, (argv, code, out, err)
    assert "Traceback" not in out + err, (argv, out[-500:], err[-2000:])
    if code == 1:
        assert err.startswith("error: "), (argv, err)
        assert err.count("error: ") == 1, (argv, err)
    return code, out, err


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------

junk_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=40)
junk_line = st.text(alphabet=string.printable + "éüß→", max_size=60)
#: Fields far longer than any real name, including NULs and other controls.
huge_field = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1000,
    max_size=5000,
).filter(lambda text: "," not in text and "\n" not in text)


@st.composite
def csv_document(draw, header=SECTION_HEADER):
    """Random text that often looks like (but rarely is) a valid CSV."""
    kind = draw(st.integers(min_value=0, max_value=5))
    if kind == 0:
        return draw(junk_text)
    lines = [header] if draw(st.booleans()) else []
    for _ in range(draw(st.integers(min_value=0, max_value=6))):
        choice = draw(st.integers(min_value=0, max_value=5))
        if choice == 0:
            lines.append(draw(junk_line))
        elif choice == 1:
            lines.append(",".join(draw(st.lists(junk_line, min_size=1, max_size=7))))
        elif choice == 2:
            # Plausible but possibly malformed section/meeting rows.
            lines.append(
                ",".join(
                    [
                        draw(st.sampled_from(COURSE_NAMES + ["ZZ", "", "A\x00B"])),
                        draw(st.sampled_from(["S1", "S2", "", "0"])),
                        draw(st.sampled_from(["Mon", "Sun", "Xyz", "", "monday"])),
                        draw(st.sampled_from(["09:00", "9:00", "24:00", "25:00", "9", "", "ab", "09:60"])),
                        draw(st.sampled_from(["10:00", "08:30", "10:00", "10:30", "", "x"])),
                        draw(st.sampled_from(["Room", "", "Hall, B", "A\x00B"])),
                    ]
                )
            )
        elif choice == 3:
            lines.append(", ".join(draw(st.lists(junk_line, max_size=5))))
        elif choice == 4:
            lines.append(lines[-1] if lines else draw(junk_line))
        elif choice == 5:
            lines.append(
                f"{draw(st.sampled_from(COURSE_NAMES))},S1,{draw(st.sampled_from(['Mon', 'Tue']))},"
                f"09:00,10:00,{draw(huge_field)}"
            )
        else:
            lines.append(draw(junk_line).replace(",", ";"))
    text = "\n".join(lines)
    if draw(st.booleans()):
        text += "\n"
    if draw(st.booleans()):
        return text.replace("\n", "\r\n")
    return text


binary_document = st.binary(max_size=200)


def fill(template, path, buildings, tmp_path):
    return [
        str(tmp_path / "out.ics") if arg == "OUT.ics"
        else str(tmp_path / "out.html") if arg == "OUT.html"
        else buildings if arg == "BLD"
        else path if arg == "FILE"
        else arg
        for arg in template
    ]


# --------------------------------------------------------------------------
# Every command, on random file contents
# --------------------------------------------------------------------------

SECTION_COMMANDS = [
    ["conflicts", "FILE"],
    ["show", "FILE"],
    ["show", "FILE", "A", "B"],
    ["show", "FILE", "--start", "9", "--end", "12"],
    ["show", "FILE", "A"],
    ["show", "FILE", "--width", "1"],
    ["plan", "FILE", "A"],
    ["plan", "FILE", "A", "B"],
    ["plan", "FILE", "A", "B", "--top", "3"],
    ["plan", "FILE", "A", "B", "--prefer", "gaps", "--prefer", "early", "--not-before", "08:30"],
    ["plan", "FILE", "A", "B", "C", "--top", "2", "--ics", "OUT.ics", "--html", "OUT.html"],
    ["plan", "FILE", "A", "B", "--term-start", "bad-date"],
    ["plan", "FILE", "A", "B", "--ics", "OUT.ics", "--html", "OUT.html"],
    ["plan", "FILE", "ZZ"],
    ["plan", "FILE", "A", "A"],
    ["plan", "FILE", "A", "B", "--buildings", "BLD"],
    ["plan", "FILE", "A", "B", "--no-travel"],
]


@settings(max_examples=40, deadline=None, suppress_health_check=NO_FIXTURE)
@given(document=csv_document())
def test_section_commands_survive_random_text(write_csv, tmp_path, document):
    path = write_csv(document)
    buildings = write_csv(BUILDING_HEADER + "Room,1.0,2.0\nHall,1.5,2.5\n", name="b.csv")
    for template in SECTION_COMMANDS:
        assert_clean(fill(template, path, buildings, tmp_path))


@settings(max_examples=20, deadline=None, suppress_health_check=NO_FIXTURE)
@given(document=binary_document)
def test_section_commands_survive_binary_files(write_csv, document):
    path = write_csv(document)
    for template in (["conflicts", "FILE"], ["show", "FILE"], ["plan", "FILE", "A"]):
        assert_clean([path if arg == "FILE" else arg for arg in template])


@settings(max_examples=20, deadline=None, suppress_health_check=NO_FIXTURE)
@given(document=csv_document(EXAM_HEADER))
def test_exams_command_survives_random_text(write_csv, document):
    path = write_csv(document)
    for argv in (["exams", path, "A"], ["exams", path, "A", "B"], ["exams", path, "A", "A"]):
        assert_clean(argv)


@settings(max_examples=20, deadline=None, suppress_health_check=NO_FIXTURE)
@given(document=csv_document(BUILDING_HEADER), document2=csv_document(SECTION_HEADER))
def test_buildings_survive_random_text(write_csv, document, document2):
    buildings = write_csv(document, name="b.csv")
    sections = write_csv(document2, name="s.csv")
    for argv in (
        ["travel", sections, buildings, "A"],
        ["travel", sections, buildings, "A", "B"],
        ["travel", sections, buildings, "A", "--walk-speed", "-3"],
        ["plan", sections, "A", "B", "--buildings", buildings],
        ["plan", sections, "A", "B", "--buildings", buildings, "--walk-speed", "0"],
    ):
        assert_clean(argv)


@settings(max_examples=20, deadline=None, suppress_health_check=NO_FIXTURE)
@given(start=st.floats(allow_nan=True, allow_infinity=True),
       speed=st.floats(allow_nan=True, allow_infinity=True))
def test_numeric_flags_reject_garbage(write_csv, start, speed):
    path = write_csv(SECTION_HEADER + "A,S1,Mon,09:00,10:00,Room\nB,S1,Tue,09:00,10:00,Hall\n")
    assert_clean(["show", path, "--start", repr(start)])
    assert_clean(["travel", path, str(path), "A", "--walk-speed", repr(speed)])


def test_unwritable_export_path_is_an_error(write_csv, tmp_path):
    path = write_csv(SECTION_HEADER + "A,S1,Mon,09:00,10:00,R\nB,S1,Tue,09:00,10:00,R\n")
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    bad = str(blocker / "out.ics")
    code, out, err = assert_clean(["plan", path, "A", "B", "--ics", bad])
    assert code == 1
    assert blocker.read_text() == "not a directory"


def test_valid_exports_parse_cleanly(write_csv, tmp_path):
    icalendar = pytest.importorskip("icalendar")
    path = write_csv(
        SECTION_HEADER
        + 'CS 101,A01,Mon,09:00,10:00,"Hall, East"\n'
        + 'CS 101,A01,Wed,09:00,10:00,"Hall, East"\n'
        + "MATH,B1,Tue,11:00,12:30,Bldg <1>\n"
    )
    ics, html = str(tmp_path / "o.ics"), str(tmp_path / "o.html")
    code, out, err = assert_clean(
        ["plan", path, "CS 101", "MATH", "--top", "1", "--ics", ics, "--html", html]
    )
    assert code == 0, err
    events = list(icalendar.Calendar.from_ical(open(ics, "rb").read()).walk("vevent"))
    assert len(events) == 3  # one event per meeting of the chosen schedule
    # The occurrence in the week starting 2026-11-30 (a Monday) is exported.
    hours = sorted(event["DTSTART"].dt.hour for event in events)
    assert hours == [9, 9, 11], hours
    assert events[0]["SUMMARY"].to_ical().decode() in {"CS 101 A01", "MATH B1"}
    page = open(html, encoding="utf-8").read()
    assert "<script" not in page and "http://" not in page and "https://" not in page
    assert "Hall, East" in page


def test_huge_and_nul_fields_never_crash(write_csv):
    huge = "x" * 20000
    path = write_csv(
        SECTION_HEADER
        + f"A,S1,Mon,09:00,10:00,{huge}\x00end\n"
        + "B,S1,Tue,09:00,10:00,\x01\x02\n"
    )
    for template in (["conflicts", "FILE"], ["show", "FILE"], ["plan", "FILE", "A", "B"]):
        assert_clean([path if arg == "FILE" else arg for arg in template])


# --------------------------------------------------------------------------
# Properties of good input
# --------------------------------------------------------------------------

@st.composite
def timetable(draw):
    """A small but valid timetable: 2-4 courses with 1-3 sections."""
    rows = []
    courses = []
    for index in range(draw(st.integers(min_value=2, max_value=4))):
        course = f"C{index}"
        courses.append(course)
        for sec in range(draw(st.integers(min_value=1, max_value=3))):
            days = draw(st.lists(
                st.sampled_from(["Mon", "Tue", "Wed", "Thu"]),
                min_size=1, max_size=2, unique=True,
            ))
            for day in days:
                start = draw(st.integers(min_value=8, max_value=16)) * 60
                rows.append(Section(course, f"S{sec}", day, start, start + 60, "Room"))
    return rows, courses


def _section_row(row):
    def hm(minutes):
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    return f"{row.course},{row.section},{row.day},{hm(row.start)},{hm(row.end)},{row.location}\n"


def _overlaps(a, b):
    return a.day == b.day and a.start < b.end and b.start < a.end


def _assert_no_overlaps(choices):
    meetings = [row for choice in choices for row in choice.meetings]
    for i, first in enumerate(meetings):
        for second in meetings[i + 1:]:
            assert not _overlaps(first, second), (first, second)


@settings(max_examples=60, deadline=None, suppress_health_check=NO_FIXTURE)
@given(data=timetable())
def test_plan_output_never_overlaps_and_matches_brute_force(write_csv, data):
    rows, courses = data
    path = write_csv(SECTION_HEADER + "".join(_section_row(r) for r in rows))
    parsed = load_sections(path)
    code, out, err = assert_clean(["plan", path, *courses, "--top", "10"])
    if code == 1:
        assert "no schedule" in err or "unusable" in err, err
        with pytest.raises(Exception):
            list(solve(parsed, courses))
        return
    everything = sorted(
        schedule_order_key(list(schedule), DEFAULT_ORDER) for schedule in solve(parsed, courses)
    )
    result = search(parsed, courses, limit=10)
    got = [schedule_order_key(item.choices, DEFAULT_ORDER) for item in result.best]
    for item in result.best:
        _assert_no_overlaps(item.choices)
    if not result.complete:
        # An incomplete search only promises the best *found*: the default
        # order's prune is sound down to the tie-break, so the top list is
        # checked against a subset of the brute-force order instead.
        assert got == sorted(got), got
        assert all(key in everything for key in got), got
        assert result.total <= len(everything)  # a lower bound, stated as such
        assert "at least" in out
        # The wording must match what happened: a budget stop is announced as
        # such, a prune-based incomplete count is not.
        expected = (
            "search stopped" if result.stopped else "not all were enumerated"
        )
        assert expected in out, out
        assert result.stopped is ("search stopped" in out)
        return
    # Exhaustive: the stored top list is the true top list.
    assert got == everything[: len(got)]
    # An exhaustive search counts every schedule once. ``explored`` counts
    # closed branches, so this is where an over-pruned branch would show.
    assert result.total == len(everything)
    assert f"{result.total} feasible schedule(s)" in out


@settings(max_examples=60, deadline=None, suppress_health_check=NO_FIXTURE)
@given(
    data=timetable(),
    preferences=st.lists(
        st.sampled_from(["days", "early", "gaps", "span"]), min_size=0, max_size=4
    ),
)
def test_ranking_matches_brute_force_for_any_preference_order(write_csv, data, preferences):
    rows, courses = data
    order = tuple(dict.fromkeys(preferences)) or DEFAULT_ORDER
    path = write_csv(SECTION_HEADER + "".join(_section_row(r) for r in rows))
    parsed = load_sections(path)
    try:
        everything = list(solve(parsed, courses))
    except Exception:
        return
    expected = sorted(schedule_order_key(list(s), order) for s in everything)
    result = search(parsed, courses, limit=5, order=list(order))
    got = [schedule_order_key(item.choices, order) for item in result.best]
    assert got == sorted(got)
    assert all(key in expected for key in got), got
    if result.complete:
        assert got == expected[:5]
    else:
        # Incomplete: these are the best *found*, so no equality claim.
        assert result.total <= len(expected)


def test_csv_round_trip_is_lossless(write_csv):
    rows = [
        Section("CS101", "A01", "Mon", 480, 540, "Hall, East"),
        Section('Q"uote', "S1", "Sun", 0, 60, "x"),
        Section("ünïcode", "S2", "Sat", 1380, 1439, "Bldg 3"),
    ]
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["course", "section", "day", "start", "end", "location"])
    for row in rows:
        writer.writerow([
            row.course, row.section, row.day,
            f"{row.start // 60:02d}:{row.start % 60:02d}",
            f"{row.end // 60:02d}:{row.end % 60:02d}",
            row.location,
        ])
    path = write_csv(buffer.getvalue())
    assert load_sections(path) == rows


def test_cli_is_deterministic(write_csv):
    lines = [SECTION_HEADER]
    for index, course in enumerate("ABCD"):
        for sec in range(3):
            for day in ("Mon", "Tue", "Wed"):
                start = 12 + sec
                lines.append(f"{course},S{sec},{day},{start:02d}:00,{start + 1:02d}:00,R\n")
        start = 16 + index
        lines.append(f"{course},SX,Mon,{start:02d}:00,{start + 1:02d}:00,R\n")
    path = write_csv("".join(lines))
    first = run_cli(["plan", path, "A", "B", "C", "D", "--top", "3"])
    second = run_cli(["plan", path, "A", "B", "C", "D", "--top", "3"])
    assert first == second
    assert first[0] == 0, first[2]
