import pytest

from planner.cli import main
from planner.model import PlannerError, Section
from planner.travel import Building, haversine_km, load_buildings, travel_warnings


def test_load_buildings_accepts_short_and_descriptive_coordinate_headers(tmp_path):
    path = tmp_path / "buildings.csv"
    path.write_text("building,lat,lon\nNorth,45.0,-75.0\n", encoding="utf-8")
    loaded = load_buildings(path)
    assert loaded == {"North": Building("North", 45.0, -75.0)}

    path.write_text("building,latitude,longitude\nSouth,0,1\n", encoding="utf-8")
    assert load_buildings(path)["South"] == Building("South", 0, 1)


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("", "empty"),
        ("building,lat\nA,1\n", "missing required"),
        ("building,lat,lon\nA,nope,1\n", "invalid coordinates"),
        ("building,lat,lon\nA,91,1\n", "latitude.*between"),
        ("building,lat,lon\nA,1,181\n", "longitude.*between"),
        ("building,lat,lon\nA,1,2\nA,3,4\n", "duplicate building"),
        ("building,lat,lon\n", "no data rows"),
        ("building,lat,lon\nA,1\n", "too few CSV fields"),
        ("building,lat,lon\nA,1,2,3\n", "too many CSV fields"),
    ],
)
def test_load_buildings_rejects_bad_inputs(tmp_path, contents, message):
    path = tmp_path / "bad.csv"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(PlannerError, match=message):
        load_buildings(path)


def test_load_buildings_rejects_missing_and_binary_files(tmp_path):
    with pytest.raises(PlannerError, match="cannot read buildings file"):
        load_buildings(tmp_path / "missing.csv")
    path = tmp_path / "binary.csv"
    path.write_bytes(b"building,lat,lon\n\xff")
    with pytest.raises(PlannerError, match="invalid text encoding|cannot read buildings file"):
        load_buildings(path)


def test_haversine_distance_and_invalid_coordinates_are_clamped():
    same = Building("same", 43.0, -79.0)
    assert haversine_km(same, same) == pytest.approx(0)
    one_degree = haversine_km(Building("a", 0, 0), Building("b", 0, 1))
    assert one_degree == pytest.approx(111.195, rel=1e-3)


def test_travel_warns_when_walk_too_long_and_for_unknown_locations():
    buildings = {
        "West": Building("West", 0, 0),
        "East": Building("East", 0, 0.01),
    }
    schedule = [
        Section("BIO", "A", "Mon", 9 * 60, 10 * 60, "West"),
        Section("CHEM", "B", "Mon", 10 * 60 + 5, 11 * 60, "East"),
        Section("MATH", "A", "Tue", 9 * 60, 10 * 60, "Unlisted Hall"),
    ]
    warnings = travel_warnings(schedule, buildings)
    assert len(warnings) == 2
    walking = next(warning for warning in warnings if "needs about" in warning)
    unknown = next(warning for warning in warnings if "unknown building" in warning)
    assert "Mon" in walking and "BIO A" in walking and "CHEM B" in walking
    assert "1.1 km" in walking and "13.3 min" in walking and "min available" in walking
    assert "Unlisted Hall" in unknown and "MATH A" in unknown


def test_travel_sufficient_gap_same_building_and_speed_override():
    buildings = {
        "A": Building("A", 0, 0),
        "B": Building("B", 0, 0.01),
    }
    schedule = [
        Section("C1", "1", "Mon", 9 * 60, 10 * 60, "A"),
        Section("C2", "1", "Mon", 10 * 60 + 20, 11 * 60, "B"),
        Section("C3", "1", "Mon", 11 * 60, 12 * 60, "B"),
    ]
    assert travel_warnings(schedule, buildings) == []
    assert len(travel_warnings(schedule[:2], buildings, walk_speed=2.5)) == 1


def test_unknown_location_warning_is_deduplicated_across_meeting_days():
    schedule = [
        Section("A", "1", "Mon", 9 * 60, 10 * 60, "Unlisted"),
        Section("A", "1", "Wed", 9 * 60, 10 * 60, "Unlisted"),
        Section("B", "1", "Tue", 9 * 60, 10 * 60, "Unlisted"),
    ]
    warnings = travel_warnings(schedule, {})
    assert len(warnings) == 2
    assert sum("A 1" in warning for warning in warnings) == 1
    assert sum("B 1" in warning for warning in warnings) == 1


def test_exact_walking_gap_same_building_and_day_boundaries():
    import math

    from planner.travel import EARTH_RADIUS_KM

    # 0.5 km at 5 km/h takes exactly six minutes.
    lon = math.degrees(0.5 / EARTH_RADIUS_KM)
    buildings = {"A": Building("A", 0, 0), "B": Building("B", 0, lon)}
    exact_gap = [
        Section("A", "1", "Mon", 9 * 60, 10 * 60, "A"),
        Section("B", "1", "Mon", 10 * 60 + 6, 11 * 60, "B"),
    ]
    assert travel_warnings(exact_gap, buildings) == []

    # One minute less than the exact requirement does warn.
    short_gap = [
        exact_gap[0],
        Section("B", "1", "Mon", 10 * 60 + 5, 11 * 60, "B"),
    ]
    warnings = travel_warnings(short_gap, buildings)
    assert len(warnings) == 1
    assert "0.5 km" in warnings[0] and "only 5 min available" in warnings[0]

    # Zero travel time for the same building needs no positive gap.
    same_building = [
        Section("A", "1", "Mon", 9 * 60, 10 * 60, "A"),
        Section("B", "1", "Mon", 10 * 60, 11 * 60, "A"),
    ]
    assert travel_warnings(same_building, buildings) == []

    # CSV intervals cannot span midnight. An early class after a late one is
    # not a valid back-to-back pair across the day boundary.
    across_boundary = [
        Section("Late", "1", "Mon", 23 * 60, 23 * 60 + 30, "A"),
        Section("Early", "1", "Mon", 0, 30, "B"),
    ]
    assert travel_warnings(across_boundary, buildings) == []


@pytest.mark.parametrize("speed", [0, -1, float("inf"), float("nan"), "fast"])
def test_travel_rejects_invalid_walk_speed(speed):
    with pytest.raises(PlannerError, match="walk speed must be a positive finite"):
        travel_warnings([], {}, speed)


def test_travel_cli_command_and_plan_flag(tmp_path, capsys):
    sections = tmp_path / "sections.csv"
    sections.write_text(
        "course,section,day,start,end,location\n"
        "A,1,Mon,09:00,10:00,West\n"
        "B,1,Mon,10:05,11:00,East\n",
        encoding="utf-8",
    )
    buildings = tmp_path / "buildings.csv"
    buildings.write_text("building,lat,lon\nWest,0,0\nEast,0,0.01\n", encoding="utf-8")

    assert main(["travel", str(sections), str(buildings), "A", "B"]) == 0
    output = capsys.readouterr().out
    assert "warning:" in output and "needs about" in output

    assert main(["plan", str(sections), "A", "B", "--buildings", str(buildings)]) == 0
    output = capsys.readouterr().out
    assert "warning:" in output

    assert main(["plan", str(sections), "A", "B", "--buildings", str(buildings), "--walk-speed", "0"]) == 1
    error = capsys.readouterr().err
    assert "error: walk speed" in error
    assert "Traceback" not in error
