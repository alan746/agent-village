# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-11-24

### Added
- README example and explanation for ranking schedules by preferences (`--prefer`, `--top`).
- Regression tests and documentation verifying iCalendar (`to_ics`) DTSTART weekday alignment across all weekdays and arbitrary term-start days.

### Fixed
- `planner plan ... --prefer/--top/--not-before` with one course no longer falls back to the plain "first section" view; any ranking flag ranks every feasible section. `--top` and `--not-before` default to `None` so an explicit flag is distinguishable from the documented defaults.
- Ranked listing no longer prints a misleading single `score` (a weighted sum whose tiny weights let a 600-minute gap override "fewest days"); metrics are now printed in the requested priority order.

### Removed
- `preferences.weighted()` and `RankedSchedule.score`: ranking is lexicographic over the metrics, so no scalar is stored or shown.

## [1.0.1] - 2026-11-24

### Changed
- `planner plan` no longer claims the true top-N when a preference order starting with `gaps` or `span` has no sound bound: such a search is reported as incomplete ("best N found", count as a lower bound), and "search stopped after N steps" is printed only when the step budget really ran out (`ranking.SearchResult.stopped`).

### Fixed
- `planner plan FILE COURSE --prefer ...` (one course) used to ignore the ranking flags and print only the first section; it now ranks every feasible section like the multi-course path.
- Displayed travel-warning distances and required walking times to one decimal place; added a strict walking-time boundary regression test.
- Ranking docs, tests and fuzz properties no longer assert that an incomplete search returns the true best schedules; only an exhaustive (`complete=True`) search promises the exact top-N and total.

## [1.0.0] - 2026-11-24

### Added
- M5: Property-based fuzz test suite (`tests/test_fuzz.py`) with Hypothesis testing all CLI commands and model invariants.
- Test coverage requirement (>= 90%) enforced with pytest-cov.
- All README shell and console examples automated and verified via `tests/test_readme.py`.
- Unified validation script `./check.sh` running tests, coverage check, and performance benchmark.

### Fixed
- Enforced upfront time validation for `--not-before` on single-course plan requests.
- Added syntax hint to repeat `--prefer` flag on invalid preference arguments.
- Corrected walking travel alerts across overlapping and intervening meetings.

## [0.4.0] - 2026-11-24

### Added
- M4: Exam clash detection (`planner exams FILE COURSE...`) detecting overlapping exam periods across courses.
- M4: Travel time and walking distance warnings between back-to-back classes (`planner travel FILE BUILDINGS COURSES` and `planner plan ... --buildings FILE --walk-speed KMH`).
- Haversine distance calculator and building coordinate catalog validation.

### Fixed
- Detected internal overlapping exam periods within the same course.
- Deduplicated unknown-building warnings per section.

## [0.3.0] - 2026-11-24

### Added
- M3: Export schedule to RFC 5545 iCalendar (`.ics`) with weekly recurrence rules (`RRULE`), line folding, and character escaping.
- M3: Export schedule to self-contained HTML weekly view (`.html`) with inline styles and zero external dependencies.
- CLI export flags `--ics`, `--html`, `--term-start`, and `--weeks` for `planner plan`.

### Fixed
- Stripped prohibited control characters (e.g. NUL) in RFC 5545 iCalendar TEXT fields.
- Guaranteed unique VEVENT UIDs across courses with punctuation differences (e.g., `CS 101` vs `CS101`).
- Rendered multi-hour classes across all covered hourly rows in the HTML grid with visual continuation badges.
- Documented floating local time semantics for iCalendar exports in README.

## [0.2.0] - 2026-11-24

### Added
- M2: Preference-based schedule ranking (`--prefer days|early|gaps|span`, `--top N`, `--not-before HH:MM`).
- Branch-and-bound search algorithm supporting timetables of 40 courses x 5 sections in under 2 seconds.
- Automated performance benchmark `tests/benchmark.py`.

## [0.1.0] - 2026-11-24

### Added
- M1: Core timetable model and CSV parser (`course,section,day,start,end,location`) with error diagnostics.
- Overlapping section conflict detection (`planner conflicts FILE`).
- Schedule solver generating non-overlapping section combinations (`planner plan FILE COURSE...`).
- Terminal weekly schedule grid visualization (`planner show FILE [COURSE...]`).
