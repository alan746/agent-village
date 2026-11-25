import pytest

from planner.csvio import load_sections
from planner.model import PlannerError, Section


def test_load_sections_valid_and_strips_fields(tmp_path):
    path = tmp_path / "sections.csv"
    path.write_text(
        "course, section, day, start, end, location\n"
        " CS101 , 01 , Mon , 09:05 , 10:00 , Room A \n",
        encoding="utf-8",
    )
    assert load_sections(path) == [Section("CS101", "01", "Mon", 545, 600, "Room A")]


@pytest.mark.parametrize("contents, message", [
    ("", "empty CSV"),
    ("course,section,day,start,end\n", "missing required column"),
    ("course,section,day,start,end,location\nCS,1,Xyz,09:00,10:00,R\n", "line 2: invalid day"),
    ("course,section,day,start,end,location\nCS,1,Mon,9:00,10:00,R\n", "line 2: invalid start time"),
    ("course,section,day,start,end,location\nCS,1,Mon,10:00,10:00,R\n", "line 2: end time"),
    ("course,section,day,start,end,location\nCS,1,Mon,11:00,10:00,R\n", "line 2: end time"),
    ("course,section,day,start,end,location\nCS,1,Mon,09:00,10:00\n", "line 2: too few"),
    ("course,section,day,start,end,location\nCS,1,Mon,09:00,10:00,R,extra\n", "line 2: too many"),
    ("course,section,day,start,end,location\n,,,,,\n", "course must not be empty"),
    ("course,course,day,start,end,location\n", "duplicate"),
])
def test_rejects_bad_csv(tmp_path, contents, message):
    path = tmp_path / "bad.csv"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(PlannerError, match=message):
        load_sections(path)


def test_missing_file_is_clear_error(tmp_path):
    with pytest.raises(PlannerError, match="cannot read sections file"):
        load_sections(tmp_path / "absent.csv")


def test_only_header_is_rejected(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("course,section,day,start,end,location\n", encoding="utf-8")
    with pytest.raises(PlannerError, match="no data rows"):
        load_sections(path)


def test_end_of_day_24_00_is_a_valid_end_time(tmp_path):
    # 24:00 is the natural way to write "midnight, end of the day"; it is a
    # valid *end* and must not be rejected outright.
    path = tmp_path / "late.csv"
    path.write_text(
        "course,section,day,start,end,location\nZ,A,Mon,22:00,24:00,R\n",
        encoding="utf-8",
    )
    [section] = load_sections(path)
    assert (section.start, section.end) == (22 * 60, 24 * 60)


@pytest.mark.parametrize("start, message", [
    ("24:00", "cannot begin at the end of the day"),
    ("24:30", "invalid start time"),
])
def test_start_time_of_24_hours_is_rejected(tmp_path, start, message):
    path = tmp_path / "late.csv"
    path.write_text(
        f"course,section,day,start,end,location\nZ,A,Mon,{start},24:00,R\n",
        encoding="utf-8",
    )
    with pytest.raises(PlannerError, match=message):
        load_sections(path)
