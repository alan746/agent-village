from planner.model import Section
from planner.travel import Building, travel_warnings


def test_travel_skips_overlapping_intervening_meetings():
    buildings = {
        "Hall A": Building("Hall A", 43.6610, -79.3960),
        "Science Center": Building("Science Center", 43.6625, -79.3980),
    }
    # The middle meeting overlaps the first. Although it is adjacent in
    # start-time order, it is not a candidate for the first meeting's walk;
    # the first meeting's next non-overlapping meeting is C at noon.
    schedule = [
        Section("A", "A1", "Mon", 9 * 60, 12 * 60, "Hall A"),
        Section("B", "B1", "Mon", 10 * 60, 11 * 60, "Hall A"),
        Section("C", "C1", "Mon", 12 * 60, 13 * 60, "Science Center"),
    ]
    warnings = travel_warnings(schedule, buildings)
    assert len(warnings) == 1
    assert "A A1" in warnings[0] and "C C1" in warnings[0]
    assert "only 0 min available" in warnings[0]


def test_duplicate_meetings_do_not_duplicate_walking_warnings():
    buildings = {
        "Hall A": Building("Hall A", 43.6610, -79.3960),
        "Science Center": Building("Science Center", 43.6625, -79.3980),
    }
    pair = [
        Section("A", "1", "Mon", 9 * 60, 10 * 60, "Hall A"),
        Section("B", "1", "Mon", 10 * 60, 11 * 60, "Science Center"),
    ]
    warnings = travel_warnings(pair + pair, buildings)
    assert len(warnings) == 1
    assert "A 1" in warnings[0] and "B 1" in warnings[0]
