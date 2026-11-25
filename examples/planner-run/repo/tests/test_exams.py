from datetime import date

import pytest

from planner.cli import main
from planner.exams import Exam, find_exam_clashes, load_exams
from planner.model import PlannerError


def test_load_exams_valid_and_strips_fields(tmp_path):
    path = tmp_path / "exams.csv"
    path.write_text(
        "course, date, start, end\n CS101 , 2025-12-10 , 09:05 , 10:00 \n",
        encoding="utf-8",
    )
    assert load_exams(path) == [Exam("CS101", date(2025, 12, 10), 545, 600)]


@pytest.mark.parametrize("contents, message", [
    ("", "empty CSV"),
    ("course,date,start\n", "missing required column"),
    ("course,course,date,start,end\n", "duplicate"),
    ("course,date,start,end\n,2025-12-10,09:00,10:00\n", "course must not be empty"),
    ("course,date,start,end\nCS,2025-2-10,09:00,10:00\n", "invalid date"),
    ("course,date,start,end\nCS,2025-02-30,09:00,10:00\n", "invalid date"),
    ("course,date,start,end\nCS,2025-12-10,9:00,10:00\n", "invalid start time"),
    ("course,date,start,end\nCS,2025-12-10,09:00,24:00\n", "invalid end time"),
    ("course,date,start,end\nCS,2025-12-10,10:00,10:00\n", "end time must be later"),
    ("course,date,start,end\nCS,2025-12-10,09:00\n", "too few"),
    ("course,date,start,end\nCS,2025-12-10,09:00,10:00,extra\n", "too many"),
    ("course,date,start,end\nCS,\"bad,09:00,10:00\n", "invalid CSV"),
])
def test_rejects_malformed_exam_csv(tmp_path, contents, message):
    path = tmp_path / "bad.csv"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(PlannerError, match=message):
        load_exams(path)


def test_rejects_binary_and_missing_files(tmp_path):
    binary = tmp_path / "binary.csv"
    binary.write_bytes(b"course,date,start,end\n\xff\xfe\n")
    with pytest.raises(PlannerError, match="invalid text encoding"):
        load_exams(binary)
    with pytest.raises(PlannerError, match="cannot read exams file"):
        load_exams(tmp_path / "missing.csv")


def test_header_without_data_is_rejected(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("course,date,start,end\n", encoding="utf-8")
    with pytest.raises(PlannerError, match="no data rows"):
        load_exams(path)


def test_find_exam_clashes_only_selected_courses_and_half_open():
    day = date(2025, 12, 10)
    exams = [
        Exam("A", day, 9 * 60, 10 * 60),
        Exam("B", day, 10 * 60, 11 * 60),  # touching is not a clash
        Exam("C", day, 9 * 60 + 30, 10 * 60 + 30),
        Exam("A", day, 11 * 60, 11 * 60 + 30),  # same course, no other overlap
        Exam("D", date(2025, 12, 11), 9 * 60, 10 * 60),
    ]
    assert find_exam_clashes(exams, ["A", "B", "C", "D"]) == [
        (exams[0], exams[2]),
        (exams[1], exams[2]),
    ]
    assert find_exam_clashes(exams, ["A", "B"]) == []
    assert find_exam_clashes(exams, []) == []
    with pytest.raises(PlannerError, match="unknown course.*X"):
        find_exam_clashes(exams, ["X"])


def test_find_exam_clashes_reports_overlapping_exams_within_same_course():
    day = date(2025, 12, 10)
    first = Exam("A", day, 9 * 60, 10 * 60)
    second = Exam("A", day, 9 * 60 + 30, 10 * 60 + 30)
    touching = Exam("A", day, 10 * 60 + 30, 11 * 60)
    assert find_exam_clashes([first, second, touching], ["A"]) == [(first, second)]


def test_find_exam_clashes_preserves_input_order_and_deduplicates_courses():
    day = date(2025, 12, 10)
    a = Exam("A", day, 9 * 60, 10 * 60)
    b = Exam("B", day, 9 * 60, 10 * 60)
    assert find_exam_clashes([a, b], ["A", "A", "B"]) == [(a, b)]


def test_cli_exams_lists_clashes_and_success_when_clear(tmp_path, capsys):
    path = tmp_path / "exams.csv"
    path.write_text(
        "course,date,start,end\n"
        "A,2025-12-10,09:00,10:00\n"
        "B,2025-12-10,09:30,10:30\n"
        "C,2025-12-11,09:00,10:00\n",
        encoding="utf-8",
    )
    assert main(["exams", str(path), "A", "B"]) == 1
    captured = capsys.readouterr()
    assert "exam clash: A (2025-12-10 09:00-10:00) overlaps B" in captured.out
    assert captured.out.endswith("1 exam clash(es)\n")
    assert captured.err == ""

    assert main(["exams", str(path), "A", "C"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "no exam clashes among 2 course(s)\n"


def test_cli_exams_rejects_unknown_course_and_bad_file(tmp_path, capsys):
    path = tmp_path / "exams.csv"
    path.write_text("course,date,start,end\nA,2025-12-10,09:00,10:00\n", encoding="utf-8")
    assert main(["exams", str(path), "MISSING"]) == 1
    assert "error: unknown course(s) in exams file: MISSING" in capsys.readouterr().err

    path.write_text("course,date,start,end\nA,2025-99-10,09:00,10:00\n", encoding="utf-8")
    assert main(["exams", str(path), "A"]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error: line 2: invalid date")
    assert "Traceback" not in captured.err
