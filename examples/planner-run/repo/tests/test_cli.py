import subprocess
import sys

import pytest

from planner.cli import main

GOOD = """course,section,day,start,end,location
CS101,01,Mon,09:00,10:00,Room A
CS101,02,Tue,09:00,10:00,Room A
MA200,01,Mon,09:30,10:30,Room B
MA200,02,Wed,14:00,15:00,Room B
"""

BAD = "course,section,day,start,end,location\nCS101,01,Funday,09:00,10:00,Room A\n"


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "sections.csv"
    path.write_text(GOOD, encoding="utf-8")
    return str(path)


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_conflicts_reports_pairs(capsys, csv_file):
    code, out, err = run(capsys, "conflicts", csv_file)
    assert code == 1
    assert "CS101 01" in out and "MA200 01" in out
    assert "1 conflicting pair(s)" in out
    assert err == ""


def test_conflicts_clean_file(capsys, tmp_path):
    path = tmp_path / "clean.csv"
    path.write_text("course,section,day,start,end,location\nA,1,Mon,09:00,10:00,R\n", encoding="utf-8")
    code, out, _ = run(capsys, "conflicts", str(path))
    assert code == 0
    assert "no conflicts among 1 meetings" in out


def test_plan_finds_schedule(capsys, csv_file):
    code, out, _ = run(capsys, "plan", csv_file, "CS101", "MA200")
    assert code == 0
    # first feasible combination in file order: CS101 01 (Mon) + MA200 02 (Wed)
    assert "CS101 01" in out and "MA200 02" in out
    assert "Mon" in out  # the weekly grid is printed too


def test_plan_unknown_course(capsys, csv_file):
    code, out, err = run(capsys, "plan", csv_file, "CS101", "NOPE")
    assert code == 1
    assert out == ""
    assert err.startswith("error:")
    assert "unknown course(s): NOPE" in err


def test_plan_impossible(capsys, tmp_path):
    path = tmp_path / "clash.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "A,1,Mon,09:00,10:00,R\n"
        "B,1,Mon,09:30,10:30,R\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, "plan", str(path), "A", "B")
    assert code == 1
    assert "no schedule without overlaps is possible" in err


def test_plan_requires_courses(capsys, csv_file):
    with pytest.raises(SystemExit):
        main(["plan", csv_file])
    assert "usage" in capsys.readouterr().err


def test_show_grid_and_filters(capsys, csv_file):
    code, out, _ = run(capsys, "show", csv_file)
    assert code == 0
    assert "Mon" in out and "Wed" in out
    code, out, _ = run(capsys, "show", csv_file, "MA200", "--start", "13", "--end", "16")
    assert code == 0
    assert "MA200 02" in out
    assert "CS101" not in out


def test_show_unknown_course(capsys, csv_file):
    code, _, err = run(capsys, "show", csv_file, "ZZZ")
    assert code == 1
    assert "unknown course(s): ZZZ" in err


def test_malformed_input_has_no_traceback(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(BAD, encoding="utf-8")
    for command in (["conflicts", str(path)], ["plan", str(path), "CS101"], ["show", str(path)]):
        result = subprocess.run(
            [sys.executable, "-m", "planner", *command],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert result.stderr.startswith("error:")
        assert "Traceback" not in result.stderr


def test_missing_file(tmp_path, capsys):
    code, _, err = run(capsys, "conflicts", str(tmp_path / "missing.csv"))
    assert code == 1
    assert "cannot read sections file" in err


def test_unexpected_value_error_becomes_a_clean_error(capsys, csv_file, monkeypatch):
    import planner.cli as cli
    import planner.show as show_module

    def boom(*args, **kwargs):
        raise ValueError("something odd")

    monkeypatch.setattr(show_module, "render", boom)
    monkeypatch.setattr(cli, "render", boom)
    code, out, err = run(capsys, "show", csv_file)
    assert code == 1
    assert out == ""
    assert err == "error: something odd\n"


def test_no_subcommand_prints_help():
    result = subprocess.run([sys.executable, "-m", "planner"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "usage: planner" in result.stderr


def test_console_script_available():
    result = subprocess.run([sys.executable, "-m", "planner", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "conflicts" in result.stdout


def test_show_width_and_start_end_are_validated(capsys, csv_file):
    code, _, err = run(capsys, "show", csv_file, "--width", "3")
    assert code == 1
    assert "at least 12" in err
    code, _, err = run(capsys, "show", csv_file, "--start", "12", "--end", "12")
    assert code == 1
    assert "start must be before" in err


def test_show_end_before_meetings_still_renders_empty(capsys, csv_file):
    code, out, _ = run(capsys, "show", csv_file, "--start", "6", "--end", "8")
    # every meeting falls outside the window, so the grid says so
    assert code == 0
    assert out.strip() == "(no meetings)"


def test_plan_explains_combination_failure(capsys, tmp_path):
    path = tmp_path / "combo.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "A,1,Mon,09:00,10:00,R\n"
        "B,1,Mon,09:00,10:00,R\n"
        "B,2,Mon,11:00,12:00,R\n"
        "C,1,Mon,11:00,12:00,R\n",
        encoding="utf-8",
    )
    code, _, err = run(capsys, "plan", str(path), "A", "B", "C")
    assert code == 1
    assert "no schedule without overlaps is possible for A, B, C" in err


def test_plan_export_ics_and_html(capsys, csv_file, tmp_path):
    ics_out = tmp_path / "out.ics"
    html_out = tmp_path / "out.html"
    code, out, err = run(capsys, "plan", csv_file, "CS101", "--ics", str(ics_out), "--html", str(html_out))
    assert code == 0
    assert ics_out.exists()
    assert html_out.exists()
    ics_content = ics_out.read_text(encoding="utf-8")
    assert "BEGIN:VCALENDAR" in ics_content
    assert "CS101" in ics_content
    html_content = html_out.read_text(encoding="utf-8")
    assert "<html" in html_content
    assert "CS101" in html_content


@pytest.mark.parametrize(
    "bad_time",
    ["24:01", "25:00", "-1", ":30", "24:60", "abc", "-1:00", "10:-5"],
)
def test_plan_not_before_validation_rejects_invalid_times(capsys, csv_file, bad_time):
    code, out, err = run(capsys, "plan", csv_file, "CS101", f"--not-before={bad_time}")
    assert code == 1
    assert "error: invalid time" in err
    assert "Traceback" not in err


def test_plan_not_before_valid_24_00(capsys, csv_file):
    code, out, err = run(capsys, "plan", csv_file, "CS101", "--not-before", "24:00")
    assert code == 0
    assert err == ""


def test_plan_prefer_hint_on_unknown_preference(capsys, csv_file):
    code, out, err = run(capsys, "plan", csv_file, "CS101", "--prefer", "days,gaps")
    assert code == 1
    assert "error: unknown preference 'days,gaps'; choose from days, early, gaps, span; repeat --prefer for several" in err
    assert "Traceback" not in err


def test_plan_incomplete_wording_matches_reason(capsys, tmp_path, monkeypatch):
    # Pruned-but-not-stopped and budget-stopped searches are different facts
    # and the CLI must not describe one as the other.
    import planner.cli as cli
    import planner.ranking as ranking

    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "A,A1,Mon,09:00,10:00,R\n"
        "A,A2,Tue,09:00,10:00,R\n"
        "B,B1,Mon,10:00,11:00,R\n"
        "B,B2,Wed,10:00,11:00,R\n",
        encoding="utf-8",
    )

    real_search = ranking.search

    def fake(stop):
        def wrapper(*args, **kwargs):
            result = real_search(*args, **kwargs)
            result.stopped = stop
            result.complete = False
            return result

        return wrapper

    for stop, mine, theirs in (
        (True, "search stopped", "not all were enumerated"),
        (False, "not all were enumerated", "search stopped"),
    ):
        monkeypatch.setattr(cli.ranking, "search", fake(stop))
        code, out, err = run(capsys, "plan", str(path), "A", "B", "--prefer", "days")
        assert code == 0, err
        assert mine in out
        assert theirs not in out
        assert "at least" in out


def test_single_course_with_preferences_is_ranked(capsys, tmp_path):
    # The one-course shortcut must not swallow ranking flags: with --prefer
    # every feasible section is ranked, so the fewest-days section wins.
    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "C,A,Mon,09:00,10:00,R\n"
        "C,A,Wed,09:00,10:00,R\n"
        "C,B,Tue,10:00,11:00,R\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, "plan", str(path), "C", "--prefer", "days")
    assert code == 0, err
    assert "#1" in out and "#2" in out
    first = out.split("#1", 1)[1].split("#2", 1)[0]
    assert "C B" in first
    assert "C A" not in first
    # Without --prefer the shortcut still prints the plain "schedule:" view.
    code, out, err = run(capsys, "plan", str(path), "C")
    assert code == 0 and out.startswith("schedule:")


def test_single_course_preferences_respect_not_before(capsys, tmp_path):
    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "C,A,Mon,08:00,09:00,R\n"
        "C,B,Wed,08:00,09:00,R\n",
        encoding="utf-8",
    )
    code, out, err = run(
        capsys, "plan", str(path), "C", "--prefer", "early", "--not-before", "07:00"
    )
    assert code == 0, err
    assert "0 early class(es)" in out


@pytest.mark.parametrize("extra", [("--top", "3"), ("--not-before", "12:00")])
def test_single_course_ranking_flags_alone_are_not_swallowed(capsys, tmp_path, extra):
    # --top and --not-before are ranking flags too: giving either for one
    # course must rank its sections instead of printing the first one.
    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "C,A,Mon,09:00,10:00,R\n"
        "C,B,Tue,13:00,14:00,R\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, "plan", str(path), "C", *extra)
    assert code == 0, err
    assert out.startswith("2 feasible schedule(s) found")
    assert "#1" in out
    # Both sections tie on every metric, so they share rank #1 and only one
    # ranked entry is printed; the ranked header proves the flag was used.
    assert not out.startswith("schedule:")
    if extra[0] == "--not-before":
        # 09:00 is before the threshold and 13:00 is not: the ranked view
        # proves the value was parsed and used.
        assert "1 early class(es)" in out


def test_explicit_default_ranking_values_are_honoured(capsys, tmp_path):
    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "C,A,Mon,09:00,10:00,R\n"
        "C,B,Tue,13:00,14:00,R\n",
        encoding="utf-8",
    )
    # Exactly the documented defaults, given explicitly, still mean "rank":
    # --top must accept 10 and --not-before must accept the 09:00 default.
    code, out, err = run(capsys, "plan", str(path), "C", "--top", "10", "--not-before", "09:00")
    assert code == 0, err
    assert "#1" in out and out.count("early class(es)") >= 2


def test_ranked_listing_has_no_score_and_follows_priority_order(capsys, tmp_path):
    # A single scalar "score" cannot express a preference list and used to
    # contradict the printed order (a 600-minute gap outweighed "days"), so it
    # is not shown; the metrics are listed in the requested priority order.
    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "A,1,Mon,08:00,09:00,R\n"
        "A,2,Tue,08:00,09:00,R\n"
        "B,1,Mon,18:00,19:00,R\n"
        "B,2,Wed,08:00,09:00,R\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, "plan", str(path), "A", "B", "--prefer", "days", "--top", "4")
    assert code == 0, err
    assert "score" not in out
    lines = [line for line in out.splitlines() if line.startswith("#")]
    assert lines, out
    # Most significant (fewest campus days) is listed first on every line.
    for line in lines:
        assert line.index("day(s) on campus") < line.index("min on campus") or "min on campus" not in line
    assert lines[0].startswith("#1 1 day(s) on campus")
    # The gaps-first order rewords the same numbers in that order.
    code, out, err = run(capsys, "plan", str(path), "A", "B", "--prefer", "gaps")
    assert code == 0, err
    first = [line for line in out.splitlines() if line.startswith("#")][0]
    assert "min of gaps" in first
    assert first.index("min of gaps") < first.index("day(s) on campus")


def test_ranked_listing_covers_every_metric_label(capsys, tmp_path):
    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\n"
        "A,1,Mon,08:00,09:00,R\n"
        "A,2,Tue,08:00,09:00,R\n",
        encoding="utf-8",
    )
    for order in ("days", "early", "gaps", "span"):
        code, out, err = run(capsys, "plan", str(path), "A", "--prefer", order)
        assert code == 0, err
        first = [line for line in out.splitlines() if line.startswith("#")][0]
        labels = {
            "days": "day(s) on campus",
            "early": "early class(es)",
            "gaps": "min of gaps",
            "span": "min on campus",
        }
        # The chosen preference appears first, and all four metrics appear.
        assert first.index(labels[order]) < min(
            first.index(label) for name, label in labels.items() if name != order
        )
        for label in labels.values():
            assert label in first


def test_end_of_day_class_shows_and_does_not_crash(capsys, tmp_path):
    path = tmp_path / "late.csv"
    path.write_text(
        "course,section,day,start,end,location\nZ,A,Mon,23:00,24:00,R\n",
        encoding="utf-8",
    )
    code, out, err = run(capsys, "show", str(path))
    assert code == 0, err
    assert "23:00-24:00" in out
