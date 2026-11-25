# Planner

A university term planning toolkit for course schedules, section selection, exam clash checking, and campus travel validation.

## Features

- **Timetable Core**: Read course section schedules from CSV, detect section overlaps, find non-conflicting course combinations, and render weekly ASCII calendars.
- **Preference-Based Ranking**: Rank feasible schedules by fewest days on campus, no early classes before a target time, and minimal gaps between classes.
- **Exports**: Export schedules to RFC 5545 iCalendar (`.ics`) format for import into Google Calendar / Apple Calendar, and self-contained HTML weekly schedule views.
- **Exams and Travel**: Detect final exam clashes across courses, and compute walking travel times between back-to-back classes based on campus building coordinates.

## Installation

```sh
pip install .
```

For development and test dependencies:

```sh
pip install -r requirements-dev.txt
```

## Usage

### 1. Visualizing Schedules

Render a weekly schedule grid in the terminal:

```console
$ planner show examples/sections.csv CS101
             Mon                Tue                Wed                Thu                Fri
09:00|09:00-10:00                           09:00-10:00                           09:00-10:00
     |CS101 A Hall A                        CS101 A Hall A                        CS101 A Hall A
10:00|                   10:00-11:30                           10:00-11:30
     |                   CS101 B Science C                     CS101 B Science C
11:00|
```

### 2. Planning Courses

Pick non-overlapping course sections:

```console
$ planner plan examples/sections.csv CS101
schedule:
  CS101 A
      Mon 09:00-10:00 @ Hall A
      Wed 09:00-10:00 @ Hall A
      Fri 09:00-10:00 @ Hall A
             Mon                Wed                Fri
09:00|09:00-10:00        09:00-10:00        09:00-10:00
     |CS101 A Hall A     CS101 A Hall A     CS101 A Hall A
```

### 3. Ranking Schedules by Preferences

`--prefer` ranks every feasible schedule. Give it more than once for a
priority list; `--top N` limits how many are printed. Each line lists the
metrics in the order you asked for them (no opaque score), so the order the
schedules appear in is the order you asked to optimise:

```console
$ planner plan examples/sections.csv CS101 MATH101 --prefer days --top 2
3 feasible schedule(s) found; best 2:
#1 3 day(s) on campus, 0 early class(es), 0 min of gaps, 360 min on campus
    CS101 A
        Mon 09:00-10:00 @ Hall A
        Wed 09:00-10:00 @ Hall A
        Fri 09:00-10:00 @ Hall A
    MATH101 A
        Mon 10:00-11:00 @ Math Hall
        Wed 10:00-11:00 @ Math Hall
        Fri 10:00-11:00 @ Math Hall
             Mon                Wed                Fri
08:00|
09:00|09:00-10:00        09:00-10:00        09:00-10:00
     |CS101 A Hall A     CS101 A Hall A     CS101 A Hall A
10:00|10:00-11:00        10:00-11:00        10:00-11:00
     |MATH101 A Math Ha  MATH101 A Math Ha  MATH101 A Math Ha
11:00|
12:00|
13:00|
14:00|
15:00|
16:00|
17:00|
18:00|
19:00|
#2 5 day(s) on campus, 0 early class(es), 0 min of gaps, 360 min on campus
    CS101 A
        Mon 09:00-10:00 @ Hall A
        Wed 09:00-10:00 @ Hall A
        Fri 09:00-10:00 @ Hall A
    MATH101 B
        Tue 09:00-10:30 @ Math Hall
        Thu 09:00-10:30 @ Math Hall
             Mon                Tue                Wed                Thu                Fri
08:00|
09:00|09:00-10:00        09:00-10:30        09:00-10:00        09:00-10:30        09:00-10:00
     |CS101 A Hall A     MATH101 B Math Ha  CS101 A Hall A     MATH101 B Math Ha  CS101 A Hall A
10:00|
11:00|
12:00|
13:00|
14:00|
15:00|
16:00|
17:00|
18:00|
19:00|
```

### 4. Exam Clashes

Detect overlapping exam schedules for a set of courses:

```console
$ planner exams examples/exams.csv CS101 MATH101
exam clash: CS101 (2025-12-10 09:00-12:00) overlaps MATH101 (2025-12-10 09:00-12:00)
1 exam clash(es)
```

### 5. Walking Distance & Travel Times

Check if back-to-back classes are located too far apart to walk in the available gap:

```console
$ planner travel examples/sections.csv examples/buildings.csv CS101 MATH101
  CS101 A
      Mon 09:00-10:00 @ Hall A
      Wed 09:00-10:00 @ Hall A
      Fri 09:00-10:00 @ Hall A
  MATH101 A
      Mon 10:00-11:00 @ Math Hall
      Wed 10:00-11:00 @ Math Hall
      Fri 10:00-11:00 @ Math Hall
warning: Fri CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1.4 min to walk at 5 km/h, but only 0 min available
warning: Mon CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1.4 min to walk at 5 km/h, but only 0 min available
warning: Wed CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1.4 min to walk at 5 km/h, but only 0 min available
```

### 6. Exporting Schedules

Export chosen schedules to iCalendar (`.ics`) and standalone HTML weekly views:

```sh
planner plan examples/sections.csv CS101 --ics schedule.ics --html schedule.html --weeks 14
```

> **Note on Timezones**: Exported iCalendar files use floating local times (no `TZID`), adhering to RFC 5545 guidelines for university schedules so meetings automatically display in the calendar client's local campus time zone.

### 7. Input Validation

Malformed input is rejected cleanly with clear error messages and non-zero exit codes:

```console
$ planner conflicts examples/bad_sections.csv
error: line 2: invalid day 'Funday'; expected Mon, Tue, Wed, Thu, Fri, Sat, or Sun
```

## Running Checks

Run the entire test suite and benchmarks:

```sh
./check.sh
```
