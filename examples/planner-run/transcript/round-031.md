# Round 31 of run 20261124_033232

[Index](README.md) · [Previous round](round-030.md) · [Next round](round-032.md)

### claude (leader) · 10:14:01

**claude said:**

> Version 1.0.0 is tagged, so all five milestones have now passed their gates. I'll let tasks 19 and 20 proceed.

**task board:** Task 16 is marked done.

**claude said:**

> `v1.0.0` is tagged at `ab914e0`, so all five milestones have passed their gates. chatgpt tagged it after a clean-clone run of `./check.sh`: 164 tests, 94.55% coverage, and the benchmark at about 1.2–1.3 s. The README examples ran by hand and `pip install .` gave a working `planner` command. As a mutation check, chatgpt bypassed the `--not-before` parsing in the clone and the tests failed, so they do catch it. I marked task 16 (the M5 gate review) done.
>
> The maintenance phase is under way. Two patches are in progress for `v1.0.1`:
> - **Task 19:** chatgpt is fixing the travel warning wording and adding the exact-boundary test.
> - **Task 20:** deepseek is fixing the ranking claim that the best results are always the true best when the search is incomplete.
>
> Gemini will review both and tag `v1.0.1`.

*2 model calls · 94,825 input tokens (93,880 cache read, 939 cache write) · 408 output tokens*

### chatgpt (worker) · 10:14:05

**chatgpt ran** · exit code 0

```bash
cd /repo && python - <<'PY'
import math
from planner.travel import *
from planner.model import Section
lon=math.degrees(.5/EARTH_RADIUS_KM)
a,b=Building('A',0,0),Building('B',0,lon)
d=haversine_km(a,b)
print(repr(lon), repr(d),repr(d/5*60))
print(travel_warnings([Section('A','1','Mon',540,600,'A'),Section('B','1','Mon',606,660,'B')],{'A':a,'B':b}))
PY
```

stdout:

```
0.00449660181862269 0.5 6.0
[]
```

**chatgpt ran** `cd /repo && grep -R '2 km\|1\.11\|\.2f.*km\|needs about' -n tests README.md planner | head -` · exit code 0

stdout:

```
tests/test_travel.py:67:    walking = next(warning for warning in warnings if "needs about" in warning)
tests/test_travel.py:149:    assert "warning:" in output and "needs about" in output
README.md:80:warning: Fri CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
README.md:81:warning: Mon CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
README.md:82:warning: Wed CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
planner/travel.py:169:                    f"{second.course} {second.section} at {second.location!r}: {distance:.2f} km "
planner/travel.py:170:                    f"needs about {needed:.0f} min to walk at {speed:g} km/h, but only {gap} min available"
```

**chatgpt ran** `cd /repo && sed -n '55,90p' README.md; sed -n '1,220p' tests/test_readme.py` · exit code 0

<details><summary>output, 97 lines</summary>

stdout:

````

### 3. Exam Clashes

Detect overlapping exam schedules for a set of courses:

```console
$ planner exams examples/exams.csv CS101 MATH101
exam clash: CS101 (2025-12-10 09:00-12:00) overlaps MATH101 (2025-12-10 09:00-12:00)
1 exam clash(es)
```

### 4. Walking Distance & Travel Times

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
warning: Fri CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
warning: Mon CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
warning: Wed CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
```

### 5. Exporting Schedules

Export chosen schedules to iCalendar (`.ics`) and standalone HTML weekly views:

```sh
planner plan examples/sections.csv CS101 --ics schedule.ics --html schedule.html --weeks 14
"""Verify that all shell examples in README.md run and match the documented output."""

import re
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"

CODE_BLOCK_RE = re.compile(r"```(?:console|sh|bash)?\n(.*?)```", re.DOTALL)


def extract_readme_commands():
    if not README_PATH.exists():
        return []
    content = README_PATH.read_text(encoding="utf-8")
    blocks = CODE_BLOCK_RE.findall(content)
    test_cases = []
    for block in blocks:
        lines = block.splitlines()
        cmd = None
        output_lines = []
        for line in lines:
            if line.startswith("$ planner "):
                if cmd is not None:
                    test_cases.append((cmd, "\n".join(output_lines).strip()))
                    output_lines = []
                cmd = line[len("$ ") :].strip()
            elif cmd is not None:
                output_lines.append(line)
        if cmd is not None:
            test_cases.append((cmd, "\n".join(output_lines).strip()))
    return test_cases


@pytest.mark.parametrize("cmd,expected_output", extract_readme_commands())
def test_readme_example(cmd, expected_output, tmp_path):
    # Parse command arguments
    parts = cmd.split()
    assert parts[0] == "planner"
    args = parts[1:]

    # Replace any /tmp/ paths or arbitrary output paths if needed, or allow /tmp/
    run_cmd = [sys.executable, "-m", "planner", *args]
    proc = subprocess.run(
        run_cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    actual_output = (proc.stdout + proc.stderr).strip()

    # Compare trimmed expected and actual output
    # Normalize whitespace on each line for robust comparison
    actual_lines = [line.rstrip() for line in actual_output.splitlines()]
    expected_lines = [line.rstrip() for line in expected_output.splitlines()]

    assert "\n".join(actual_lines) == "\n".join(expected_lines)
````

</details>

**chatgpt ran** · exit code 0

```bash
cd /repo && python - <<'PY'
p='planner/travel.py'
s=open(p).read()
old='f"{second.course} {second.section} at {second.location!r}: {distance:.2f} km "'
new='f"{second.course} {second.section} at {second.location!r}: {distance:.1f} km "'
assert old in s
open(p,'w').write(s.replace(old,new))
p='tests/test_travel.py'
s=open(p).read()
s=s.replace('assert "km" in walking and "min available" in walking', 'assert "1.1 km" in walking and "min available" in walking')
needle='''    assert travel_warnings(exact_gap, buildings) == []

    # Zero travel time for the same building needs no positive gap.'''
replacement='''    assert travel_warnings(exact_gap, buildings) == []

    # One minute less than the exact requirement does warn.
    short_gap = [
        exact_gap[0],
        Section("B", "1", "Mon", 10 * 60 + 5, 11 * 60, "B"),
    ]
    warnings = travel_warnings(short_gap, buildings)
    assert len(warnings) == 1
    assert "0.5 km" in warnings[0] and "only 5 min available" in warnings[0]

    # Zero travel time for the same building needs no positive gap.'''
assert needle in s
open(p,'w').write(s.replace(needle,replacement))
p='README.md'
s=open(p).read()
assert s.count('0.12 km') == 3
open(p,'w').write(s.replace('0.12 km','0.1 km'))
p='CHANGELOG.md'
s=open(p).read()
needle='## [Unreleased]\n'
replacement='## [Unreleased]\n\n### Fixed\n- Displayed travel-warning distances to one decimal place; added a strict walking-time boundary regression test.\n'
assert needle in s
open(p,'w').
[... 103 more characters not shown ...]
```

stdout:

```
...........................                                              [100%]
27 passed in 1.73s
```

**chatgpt ran** `cd /repo && git diff --check && git diff -- planner/travel.py tests/test_travel.py README.md CHANGELOG.md && ./check.sh` · exit code 0

<details><summary>output, 80 lines</summary>

stdout:

````
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 3adff9a..f222e4f 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -7,6 +7,9 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 ## [Unreleased]
 
+### Fixed
+- Displayed travel-warning distances to one decimal place; added a strict walking-time boundary regression test.
+
 ## [0.4.0] - 2026-11-24
 
 ### Added
diff --git a/README.md b/README.md
index c01d027..9dde1bd 100644
--- a/README.md
+++ b/README.md
@@ -77,9 +77,9 @@ $ planner travel examples/sections.csv examples/buildings.csv CS101 MATH101
       Mon 10:00-11:00 @ Math Hall
       Wed 10:00-11:00 @ Math Hall
       Fri 10:00-11:00 @ Math Hall
-warning: Fri CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
-warning: Mon CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
-warning: Wed CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
+warning: Fri CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1 min to walk at 5 km/h, but only 0 min available
+warning: Mon CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1 min to walk at 5 km/h, but only 0 min available
+warning: Wed CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1 min to walk at 5 km/h, but only 0 min available
 ```
 
 ### 5. Exporting Schedules
diff --git a/planner/travel.py b/planner/travel.py
index e4d81ff..991530f 100644
--- a/planner/travel.py
+++ b/planner/travel.py
@@ -166,7 +166,7 @@ def travel_warnings(
             if gap < needed:
                 warning = (
                     f"warning: {day} {first.course} {first.section} at {first.location!r} to "
-                    f"{second.course} {second.section} at {second.location!r}: {distance:.2f} km "
+                    f"{second.course} {second.section} a
[... 16479 bytes truncated ...]
est_travel_rejects_invalid_walk_speed[0] PASSED   [ 95%]
tests/test_travel.py::test_travel_rejects_invalid_walk_speed[-1] PASSED  [ 96%]
tests/test_travel.py::test_travel_rejects_invalid_walk_speed[inf] PASSED [ 96%]
tests/test_travel.py::test_travel_rejects_invalid_walk_speed[nan] PASSED [ 97%]
tests/test_travel.py::test_travel_rejects_invalid_walk_speed[fast] PASSED [ 98%]
tests/test_travel.py::test_travel_cli_command_and_plan_flag PASSED       [ 98%]
tests/test_travel_edge_regression.py::test_travel_skips_overlapping_intervening_meetings PASSED [ 99%]
tests/test_travel_edge_regression.py::test_duplicate_meetings_do_not_duplicate_walking_warnings PASSED [100%]

================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.16-final-0 _______________

Name                     Stmts   Miss  Cover
--------------------------------------------
planner/__init__.py          0      0   100%
planner/__main__.py          2      2     0%
planner/cli.py             181      8    96%
planner/conflicts.py         4      0   100%
planner/csvio.py            68      4    94%
planner/exams.py            81      1    99%
planner/export.py          172      6    97%
planner/model.py            10      0   100%
planner/preferences.py     100     19    81%
planner/ranking.py         107      4    96%
planner/show.py             82      1    99%
planner/solver.py          130      4    97%
planner/travel.py          127      9    93%
--------------------------------------------
TOTAL                     1064     58    95%
Required test coverage of 90% reached. Total coverage: 94.55%
============================= 164 passed in 8.89s ==============================
=== Running benchmark (tests/benchmark.py) ===
benchmark data: /repo/tests/data/bench_40x5.csv (40 courses x 5 sections)
  default order       1.286s  (budget 2s)  ok
  days, gaps, span    1.385s  (budget 2s)  ok
benchmark passed
=== All checks passed! ===
````

</details>

**chatgpt ran** · exit code 0

```bash
cd /repo && git status --short && git diff --stat && git add planner/travel.py tests/test_travel.py README.md CHANGELOG.md && git commit -m 'Show travel distances to one decimal place' && git status --short
```

<details><summary>output, 21 lines</summary>

stdout:

```
 M CHANGELOG.md
 M README.md
 M planner/cli.py
 M planner/ranking.py
 M planner/travel.py
 M tests/test_fuzz.py
 M tests/test_travel.py
 CHANGELOG.md         |  3 +++
 README.md            |  6 +++---
 planner/cli.py       |  4 +++-
 planner/ranking.py   | 30 +++++++++++++++++++++---------
 planner/travel.py    |  2 +-
 tests/test_fuzz.py   | 10 ++++++++--
 tests/test_travel.py | 11 ++++++++++-
 7 files changed, 49 insertions(+), 17 deletions(-)
[main edf0ae4] Show travel distances to one decimal place
 4 files changed, 17 insertions(+), 5 deletions(-)
 M planner/cli.py
 M planner/ranking.py
 M tests/test_fuzz.py
```

</details>

**chatgpt posted to chat:**

> Task 19 implementation committed as edf0ae4 (`Show travel distances to one decimal place`). It changes `planner/travel.py` formatting to one decimal, updates README expected output, strengthens the exact 6-minute/0.5-km boundary test to assert no warning at equality and warning at 5 minutes, and notes the fix in Unreleased. `./check.sh` passes (164, 94.55%; benchmark 1.286s/1.385s), and `git diff --check` is clean. Gemini: please independently review edf0ae4 and the README example; DeepSeek's ranking files are still uncommitted and left untouched.

**task board:** submitted to task 19: Your result for task 19 was submitted.

> Committed task 19 as edf0ae4 (`Show travel distances to one decimal place`). Changed `planner/travel.py`, `tests/test_travel.py`, `README.md`, and `CHANGELOG.md`; precise warning display is one decimal, exact 6-minute/0.5-km boundary is tested (no warning at equality; warning with five minutes), and documented README output updated. `./check.sh` passes: 164 tests, 94.55% coverage, benchmark 1.286s/1.385s; `git diff --check` clean. Await independent review before release. Run `./check.sh`.

**chatgpt ran** `cd /repo && git diff -- planner/cli.py planner/ranking.py tests/test_fuzz.py` · exit code 0

<details><summary>output, 82 lines</summary>

stdout:

```
diff --git a/planner/cli.py b/planner/cli.py
index a40aa48..cf69874 100644
--- a/planner/cli.py
+++ b/planner/cli.py
@@ -150,9 +150,11 @@ def cmd_plan(args: argparse.Namespace) -> int:
     if result.complete:
         print(f"{result.total} feasible schedule(s) found; best {how_many}:")
     else:
+        # "best found", not "best": an incomplete search cannot promise the
+        # true top list (see ranking.search), so the wording must not either.
         print(
             f"search stopped after {result.explored} steps; showing the best"
-            f" {how_many} of at least {result.total} feasible schedule(s):"
+            f" {how_many} found of at least {result.total} feasible schedule(s):"
         )
     for item in result.best:
         _print_ranked(item, result.total, result.complete)
diff --git a/planner/ranking.py b/planner/ranking.py
index a755328..62a58bc 100644
--- a/planner/ranking.py
+++ b/planner/ranking.py
@@ -29,8 +29,11 @@ class SearchResult:
     """Best schedules found (best first) plus what the search did.
 
     ``total`` is the number of feasible schedules seen; ``complete`` says
-    whether that count is exact (False when the search hit its budget after
-    the top ``limit`` were already found).
+    whether the search was exhaustive, so ``best`` is the exact top ``limit``
+    and ``total`` the exact number of feasible schedules. It is False when the
+    search hit its budget after the top ``limit`` were already found, or when
+    pruning was heuristic (see ``search``); ``best`` is then only the best
+    found among the branches actually visited.
     """
 
     best: list[RankedSchedule]
@@ -52,14 +55,21 @@ def search(
     limit: int = 10,
     patience: int = DEFAULT_PATIENCE,
 ) -> SearchResult:
-    """Find up to ``limit`` best feasible schedules according to ``order``.
+    """Find up to ``limit`` feasible schedules, best first, according to ``order``.
+
+    The result is *exact* when ``SearchResult.complete`` is true: `
[... 1871 bytes truncated ...]
ne. That heuristic can cost
-    completeness, so in that case it is only trusted for the *best* schedule:
-    the reported ``total`` counts the schedules actually enumerated.
+    branch-and-bound on the section-number tie-break, which is a heuristic:
+    a branch that is worse on the tie-break alone can still finish with better
+    metrics. Such a search is never reported as complete, so the counts and
+    the "best" it returns are honest lower bounds.
 
     ``patience`` caps the nodes visited once a feasible schedule is known, so a
     timetable with thousands of options still answers quickly; ``complete``
diff --git a/tests/test_fuzz.py b/tests/test_fuzz.py
index b54cd08..7fa54e5 100644
--- a/tests/test_fuzz.py
+++ b/tests/test_fuzz.py
@@ -329,14 +329,20 @@ def test_plan_output_never_overlaps_and_matches_brute_force(write_csv, data):
     )
     result = search(parsed, courses, limit=10)
     got = [schedule_order_key(item.choices, DEFAULT_ORDER) for item in result.best]
-    # The best results are always the true best, complete or not.
-    assert got == everything[: len(got)]
     for item in result.best:
         _assert_no_overlaps(item.choices)
     if not result.complete:
+        # An incomplete search only promises the best *found*: the default
+        # order's prune is sound down to the tie-break, so the top list is
+        # checked against a subset of the brute-force order instead.
+        assert got == sorted(got), got
+        assert all(key in everything for key in got), got
         assert result.total <= len(everything)  # a lower bound, stated as such
         assert "at least" in out
+        assert "found of at least" in out
         return
+    # Exhaustive: the stored top list is the true top list.
+    assert got == everything[: len(got)]
     # An exhaustive search counts every schedule once. ``explored`` counts
     # closed branches, so this is where an over-pruned branch would show.
     assert result.total == len(everything)
```

</details>

**read** `planner/ranking.py`

**chatgpt posted to chat:**

> Reviewing task20's currently visible ranking diff, I see one concrete CLI/result inconsistency to consider before committing: when `order` starts `gaps` or `span`, `counting=False`, and `offer()` sets `stats['capped']=True` as soon as `limit` is filled; `visit()` only stops on `stats['capped']` if `counting` is true. Thus a small exhaustive search (e.g. one feasible schedule with `order=['span']`, limit=1, ample patience) finishes its whole tree but returns `complete=False`, causing CLI to say “search stopped after … steps” even though it did not stop and report “at least N” despite exact count. Consider track heuristic/inexact-top separately from actual budget stop and only claim it stopped when a stop occurred (or frame wording as “top ranking not guaranteed; N feasible schedules visited”).

**[COMPACTED]** memory compacted: summarized messages 578-608

*checked: read_task*

**chatgpt said:**

> Task 19 is committed as `edf0ae4`; `./check.sh` passes. I submitted the result and notified Gemini that the commit is ready for independent review. I also reported a potential CLI wording inconsistency in DeepSeek’s in-progress ranking changes.

*14 model calls · 251,692 input tokens (215,614 cache read, 36,036 cache write) · 4,046 output tokens*

### deepseek (worker) · 10:15:17

**deepseek ran** `cd /repo && sed -n '/^    order = normalise_order(order)/,$p' planner/ranking.py | head -110` · exit code 0

<details><summary>output, 92 lines</summary>

stdout:

```
    order = normalise_order(order)
    if limit < 1:
        raise PlannerError("max_results must be at least 1")
    if not courses:
        raise PlannerError("no courses requested")
    grouped = group_sections(sections)
    duplicate = {name for name in courses if courses.count(name) > 1}
    if duplicate:
        raise PlannerError("course requested more than once: " + ", ".join(sorted(duplicate)))
    unknown = [name for name in courses if name not in grouped]
    if unknown:
        known = ", ".join(grouped) or "(none)"
        raise PlannerError(
            f"unknown course(s): {', '.join(unknown)} (known courses: {known})"
        )

    options = [usable_choices(name, grouped[name]) for name in courses]
    for choices in options:
        choices.sort(key=lambda choice: _option_rank(choice, order, not_before))

    stats = {"found": 0, "explored": 0, "capped": False, "pruned": False}
    best: list[RankedSchedule] = []
    worst: tuple | None = None
    worst_bound: tuple = ()
    # A section-number bound is not sound for counting, so with an empty
    # monotonic prefix the search stops enumerating once the top list is full
    # and says so through ``complete``.
    counting = bool(_monotonic_prefix((0,) * len(order), order))

    def offer(chosen: list[Choice]) -> None:
        nonlocal worst, worst_bound
        meetings = [row for choice in chosen for row in choice.meetings]
        metrics = measure(meetings, not_before=not_before)
        item = RankedSchedule(list(chosen), metrics, not_before=not_before)
        item.score = weighted(metrics, order)
        key = _exact_key(item, order)
        if worst is not None and key >= worst:
            return
        if worst is not None:
            # The top list is full and sorted: walk from the end only as far
            # as needed and drop the item as soon as it cannot make the top.
            position = len(best)
            while position and _exact_key(best[position - 1], order) > key:
       
[... 848 bytes truncated ...]
,
            ).as_tuple(normalise_order(order)),
            normalise_order(order),
        )

    def visit(position: int, chosen: list[Choice]) -> None:
        # The node budget only applies once a schedule is known to exist: a
        # search that gives up before then would wrongly report the timetable
        # as impossible. Finding the first schedule is bounded by the number
        # of sections, so this always terminates.
        if stats["found"] and stats["explored"] >= patience:
            stats["capped"] = True
            return
        stats["explored"] += 1
        if counting and stats["capped"]:
            return
        if worst is not None:
            # Prune only when the bound loses lexicographically to the bound
            # of the worst stored schedule, over comparable metrics only (see
            # ``_monotonic_prefix``). Using the stored key's full tuple would be
            # unsound: its tail is the stored schedule's own section numbers
            # and meetings, which a partial branch cannot be compared to.
            if bound_key(chosen) > worst_bound:
                # This subtree cannot improve the top list, but it may hold
                # zero or many feasible schedules. Do not guess its count: the
                # result is still an exact top list but its reported count is
                # only a lower bound.
                stats["pruned"] = True
                return
        if position == len(options):
            stats["found"] += 1
            offer(chosen)
            return
        for candidate in options[position]:
            if all(_no_overlap(candidate, other) for other in chosen):
                chosen.append(candidate)
                try:
                    visit(position + 1, chosen)
                finally:
                    chosen.pop()

    visit(0, [])
    if stats["found"] == 0:
        raise PlannerError(_explain_impossible(courses, options))
    seen: list[tuple] = []
    for item in best:
```

</details>

**deepseek ran** `cd /repo && sed -n '/^    visit(0, \[\])/,$p' planner/ranking.py` · exit code 0

<details><summary>output, 49 lines</summary>

stdout:

```
    visit(0, [])
    if stats["found"] == 0:
        raise PlannerError(_explain_impossible(courses, options))
    seen: list[tuple] = []
    for item in best:
        key = item.metrics.as_tuple(order)
        if key not in seen:
            seen.append(key)
        item.rank = seen.index(key) + 1
    return SearchResult(
        best=best,
        total=stats["found"],
        complete=not (stats["capped"] or stats["pruned"]),
        explored=stats["explored"],
    )


#: Metrics that never increase when meetings are added to a partial schedule:
#: a new day can only be added and a new early class only counted. ``gaps`` is
#: absent (a meeting slotted between two existing classes fills the gap) and so
#: is ``span`` (a meeting inside an existing day leaves it unchanged).
MONOTONIC_METRICS = frozenset({"days", "early"})


def _monotonic_prefix(values: tuple, order: tuple[str, ...]) -> tuple:
    """The leading metrics that can safely bound an unfinished schedule.

    Only the run of monotonic metrics at the head of ``order`` is compared;
    the first non-monotonic metric (``gaps`` or ``span``) ends it. Zeros would
    be padded for later positions, so a shorter tuple is what makes the
    comparison say "cannot tell" rather than "better".
    """
    prefix = []
    for name, value in zip(order, values):
        if name not in MONOTONIC_METRICS:
            break
        prefix.append(value)
    return tuple(prefix)


def _option_rank(choice: Choice, order: tuple[str, ...], not_before: int) -> tuple:
    """Sort key for one course's sections: the most promising first."""
    metrics = measure(choice.meetings, not_before=not_before)
    first = choice.meetings[0] if choice.meetings else None
    clock = (first.start, first.end) if first else (0, 0)
    if order[0] == "early" or "early" in order:
        return (metrics.early, clock, choice.section)
    return (clock, choice.section)
```

</details>

**deepseek ran** `cd /repo && grep -rn "\.complete" planner/ tests/ | grep -v "^planner/ranking.py" | head -20` · exit code 0

stdout:

```
planner/cli.py:150:    if result.complete:
planner/cli.py:160:        _print_ranked(item, result.total, result.complete)
tests/test_fuzz.py:334:    if not result.complete:
tests/test_fuzz.py:372:    assert got == expected[:5] or not result.complete
tests/test_ranking.py:58:    assert result.complete is True
tests/test_ranking.py:95:        if result.complete:
tests/test_ranking.py:127:    assert result.complete is False
tests/test_ranking.py:182:    assert result.complete is True
tests/test_ranking.py:302:        if result.complete:
```

**deepseek ran** · exit code 0

```bash
cd /repo && sed -n 290,310p tests/test_ranking.py; sed -n 355,380p tests/test_fuzz.py; sed -n 88,100p tests/test_ranking.py
```

<details><summary>output, 56 lines</summary>

stdout:

```
        Section("C2", "S1", "Wed", 480, 540, "R"),
        Section("C3", "S0", "Mon", 480, 540, "R"),
        Section("C3", "S1", "Mon", 480, 540, "R"),
        Section("C3", "S2", "Mon", 480, 540, "R"),
    ]
    courses = ["C0", "C1", "C2", "C3"]
    everything = list(solve(rows, courses))
    for order in (["days", "early", "gaps", "span"], ["gaps"], ["early"], ["span", "gaps"], ["span"]):
        result = search(rows, courses, limit=10, order=order)
        expected = sorted(schedule_order_key(list(s), order) for s in everything)
        got = [schedule_order_key(item.choices, order) for item in result.best]
        assert got == expected[: len(got)]
        if result.complete:
            assert result.total == len(everything)
        else:
            assert result.total <= len(everything)
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
    assert got == expected[: len(got)]
    assert got == expected[:5] or not result.complete


def test_csv_round_trip_is_lossless(write_csv):
    rows = [
        Section("CS101", "A01", "Mon", 480, 540, "Hall, East"),
        Section('Q"uote', "S1", "Sun", 0, 60, "x"),
        Section("ünïcode", "S2", "Sat", 1380, 1439, "Bldg 3"),
    ]
                search(rows, courses, limit=5)
            continue
        result = search(rows, courses, limit=5)
        assert [exact_key(item.choices) for item in result.best] == expected
        # limit=5 caps the stored list, so the total can be larger. Pruning can
        # skip subtrees, so ``total`` is only a lower bound in that case.
        assert result.total >= len(expected)
        if result.complete:
            assert result.total == len(list(solve(rows, courses)))
        checked += 1
    assert checked > 30
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/ranking.py'
s=open(p).read()
old='''    visit(0, [])
    if stats["found"] == 0:
        raise PlannerError(_explain_impossible(courses, options))'''
new='''    visit(0, [])
    if stats["found"] == 0:
        raise PlannerError(_explain_impossible(courses, options))
    # The search ran out of budget (as opposed to pruning a subtree it could
    # bound): it did stop early. Callers phrase their report from this rather
    # than claiming a stop whenever the result is not exhaustive.
    stopped = stats["capped"]'''
assert old in s
s=s.replace(old,new)
old2='''        complete=not (stats["capped"] or stats["pruned"]),
        explored=stats["explored"],'''
new2='''        complete=not (stats["capped"] or stats["pruned"]),
        stopped=stopped,
        explored=stats["explored"],'''
assert old2 in s
s=s.replace(old2,new2)
old3='''    best: list[RankedSchedule]
    total: int
    complete: bool
    explored: int
'''
new3='''    best: list[RankedSchedule]
    total: int
    complete: bool
    explored: int
    stopped: bool = False
'''
assert old3 in s
s=s.replace(old3,new3)
open(p,'w').write(s)
EOF
sed -n 28,45p planner/ranking.py
```

<details><summary>output, 19 lines</summary>

stdout:

```
class SearchResult:
    """Best schedules found (best first) plus what the search did.

    ``total`` is the number of feasible schedules seen; ``complete`` says
    whether the search was exhaustive, so ``best`` is the exact top ``limit``
    and ``total`` the exact number of feasible schedules. It is False when the
    search hit its budget after the top ``limit`` were already found, or when
    pruning was heuristic (see ``search``); ``best`` is then only the best
    found among the branches actually visited.
    """

    best: list[RankedSchedule]
    total: int
    complete: bool
    explored: int
    stopped: bool = False
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/ranking.py'
s=open(p).read()
s=s.replace('''    found among the branches actually visited.
    """''','''    found among the branches actually visited. ``stopped`` is true only when
    the node budget ran out (as opposed to a provably safe prune), so callers
    can say "search stopped" only when it really did.
    """''')
open(p,'w').write(s)

p='planner/cli.py'
s=open(p).read()
old='''    else:
        # "best found", not "best": an incomplete search cannot promise the
        # true top list (see ranking.search), so the wording must not either.
        print(
            f"search stopped after {result.explored} steps; showing the best"
            f" {how_many} found of at least {result.total} feasible schedule(s):"
        )'''
new='''    elif result.stopped:
        # "best found", not "best": a search that ran out of budget cannot
        # promise the true top list (see ranking.search), so the wording must
        # not either.
        print(
            f"search stopped after {result.explored} steps; showing the best"
            f" {how_many} found of at least {result.total} feasible schedule(s):"
        )
    else:
        # Not exhaustive because branches were pruned, not because a step
        # budget ran out: report the count as the lower bound it is without
        # claiming the search was cut short.
        print(
            f"{result.total} feasible schedule(s) visited; showing the best"
            f" {how_many} fo
[... 168 more characters not shown ...]
```

<details><summary>output, 32 lines</summary>

stdout:

```
        limit=args.top,
    )
    if not result.best:
        raise PlannerError("no schedule without overlaps is possible")
    how_many = len(result.best)
    if result.complete:
        print(f"{result.total} feasible schedule(s) found; best {how_many}:")
    elif result.stopped:
        # "best found", not "best": a search that ran out of budget cannot
        # promise the true top list (see ranking.search), so the wording must
        # not either.
        print(
            f"search stopped after {result.explored} steps; showing the best"
            f" {how_many} found of at least {result.total} feasible schedule(s):"
        )
    else:
        # Not exhaustive because branches were pruned, not because a step
        # budget ran out: report the count as the lower bound it is without
        # claiming the search was cut short.
        print(
            f"{result.total} feasible schedule(s) visited; showing the best"
            f" {how_many} found (at least {result.total} exist; not all were enumerated):"
        )
    for item in result.best:
        _print_ranked(item, result.total, result.complete)
    _print_travel_warnings(args, result.best[0].choices)
    export.handle_plan_exports(args, result.best[0].choices)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/cli.py'
s=open(p).read()
old='''        print(
            f"{result.total} feasible schedule(s) visited; showing the best"
            f" {how_many} found (at least {result.total} exist; not all were enumerated):"
        )'''
new='''        print(
            f"at least {result.total} feasible schedule(s) exist; showing the"
            f" best {how_many} found (not all were enumerated):"
        )'''
s=s.replace(old,new)
open(p,'w').write(s)
EOF
python -m planner plan /tmp/p.csv A B C --prefer span --top 2 2>&1 | head -2; python -m planner plan /tmp/p.csv A B C --prefer days --top 2 2>&1|head -2
```

stdout:

```
search stopped after 15 steps; showing the best 2 found of at least 8 feasible schedule(s):
#1 (score 726) 2 day(s) on campus, 0 early class(es), 0 min of gaps, 180 min on campus
at least 4 feasible schedule(s) exist; showing the best 2 found (not all were enumerated):
#1 (score 188) 2 day(s) on campus, 0 early class(es), 0 min of gaps, 180 min on campus
```

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='tests/test_fuzz.py'
s=open(p).read()
old='''        assert "at least" in out
        assert "found of at least" in out
'''
new='''        assert "at least" in out
        # The wording must match what happened: a budget stop is announced as
        # such, a prune-based incomplete count is not.
        expected = (
            "search stopped" if result.stopped else "not all were enumerated"
        )
        assert expected in out, out
        assert result.stopped is ("search stopped" in out)
'''
assert old in s
s=s.replace(old,new)
open(p,'w').write(s)
EOF
python -m pytest -q tests/test_fuzz.py 2>&1 | tail -2
```

stdout:

```
............                                                             [100%]
12 passed in 2.56s
```

**deepseek said:**

> Now the ranking tests for wording and stopped flag.

**deepseek ran** `cd /repo && sed -n 1,20p tests/test_cli.py; grep -n "def test_" tests/test_cli.py | head -40` · exit code 0

<details><summary>output, 41 lines</summary>

stdout:

```
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
31:def test_conflicts_reports_pairs(capsys, csv_file):
39:def test_conflicts_clean_file(capsys, tmp_path):
47:def test_plan_finds_schedule(capsys, csv_file):
55:def test_plan_unknown_course(capsys, csv_file):
63:def test_plan_impossible(capsys, tmp_path):
76:def test_plan_requires_courses(capsys, csv_file):
82:def test_show_grid_and_filters(capsys, csv_file):
92:def test_show_unknown_course(capsys, csv_file):
98:def test_malformed_input_has_no_traceback(tmp_path):
112:def test_missing_file(tmp_path, capsys):
118:def test_unexpected_value_error_becomes_a_clean_error(capsys, csv_file, monkeypatch):
133:def test_no_subcommand_prints_help():
139:def test_console_script_available():
145:def test_show_width_and_start_end_are_validated(capsys, csv_file):
154:def test_show_end_before_meetings_still_renders_empty(capsys, csv_file):
161:def test_plan_explains_combination_failure(capsys, tmp_path):
176:def test_plan_export_ics_and_html(capsys, csv_file, tmp_path):
195:def test_plan_not_before_validation_rejects_invalid_times(capsys, csv_file, bad_time):
202:def test_plan_not_before_valid_24_00(capsys, csv_file):
208:def test_plan_prefer_hint_on_unknown_preference(capsys, csv_file):
```

</details>

**deepseek ran** `cd /repo && sed -n 43,56p tests/test_cli.py; sed -n 19,30p tests/test_cli.py` · exit code 0

<details><summary>output, 27 lines</summary>

stdout:

```
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
def csv_file(tmp_path):
    path = tmp_path / "sections.csv"
    path.write_text(GOOD, encoding="utf-8")
    return str(path)


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='tests/test_cli.py'
s=open(p).read()
s+='''

def test_plan_incomplete_wording_matches_reason(capsys, tmp_path, monkeypatch):
    # Pruned-but-not-stopped and budget-stopped searches are different facts
    # and the CLI must not describe one as the other.
    import planner.cli as cli
    import planner.ranking as ranking

    path = tmp_path / "sections.csv"
    path.write_text(
        "course,section,day,start,end,location\\n"
        "A,A1,Mon,09:00,10:00,R\\n"
        "A,A2,Tue,09:00,10:00,R\\n"
        "B,B1,Mon,10:00,11:00,R\\n"
        "B,B2,Wed,10:00,11:00,R\\n",
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
'''
open(p,'w').write(s)
EOF
python -m pytest -q tests/test_cli.py 2>&1 | tail -2
```

stdout:

```
............................                                             [100%]
28 passed in 1.67s
```

**deepseek said:**

> Now ranking tests: stopped flag semantics, docs claim test.

**deepseek ran** `cd /repo && sed -n 246,278p tests/test_ranking.py` · exit code 0

<details><summary>output, 34 lines</summary>

stdout:

```
def test_patience_never_returns_worse_results():
    # A search cut short by ``patience`` may report fewer results, never worse
    # ones than the full search.
    order = ("early", "gaps", "days", "span")
    rng = random.Random(7)
    rows, courses = random_instance(rng)
    full = search(rows, courses, limit=5, order=list(order), patience=100000)
    tight = search(rows, courses, limit=5, order=list(order), patience=8)
    full_keys = [exact_key(item.choices, order) for item in full.best]
    tight_keys = [exact_key(item.choices, order) for item in tight.best]
    assert tight_keys == full_keys[: len(tight_keys)]
    assert tight.explored <= tight.total + 8


def test_patience_never_reports_impossible():
    # The node budget must not make a feasible timetable look impossible:
    # with any patience the first schedule is still found.
    rows = [Section("C", "1", "Mon", 540, 600, "R")]
    for patience in (0, 1, 2):
        result = search(rows, ["C"], patience=patience)
        assert [choice.section for choice in result.best[0].choices] == ["1"]
    # And an impossible timetable is still reported as impossible.
    clash = [
        Section("A", "1", "Mon", 540, 600, "R"),
        Section("B", "1", "Mon", 570, 630, "R"),
    ]
    with pytest.raises(PlannerError, match="cannot be combined"):
        search(clash, ["A", "B"], patience=0)


def test_bound_uses_the_requested_metric_order():
    # The prune bound must read metrics in the user's order; ranking gaps
    # first used to compare ``days`` against the wrong metric and drop a
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='tests/test_ranking.py'
s=open(p).read()
anchor='''def test_bound_uses_the_requested_metric_order():'''
new='''def test_stopped_only_when_the_budget_ran_out():
    # ``stopped`` drives the CLI's "search stopped after N steps" wording, so
    # it must be false for a search that finished its tree or merely pruned a
    # bounded subtree, and true only when ``patience`` cut it short.
    rows = []
    for course in range(8):
        for sec in range(3):
            rows.append(section(f"C{course}", f"S{sec}", "Mon", 8 + course, 9 + course))
    courses = [f"C{course}" for course in range(8)]
    exhaustive = search(rows, courses, limit=3, patience=10**6)
    assert exhaustive.complete is True
    assert exhaustive.stopped is False
    tight = search(rows, courses, limit=3, patience=50)
    assert tight.complete is False
    assert tight.stopped is True
    # A tiny exhaustive search under a heuristic-only order (no sound prefix)
    # is incomplete but did not stop: saying "stopped" would be a lie. One
    # feasible schedule, order starting with ``span``.
    small = [Section("A", "1", "Mon", 540, 600, "R"), Section("B", "1", "Tue", 540, 600, "R")]
    heuristic = search(small, ["A", "B"], limit=1, order=["span"], patience=10**6)
    assert heuristic.complete is False
    assert heuristic.stopped is False
    assert heuristic.total == 1


def test_incomplete_top_list_is_a_lower_bound_not_a_promise():
    # Ties broken only by section number are i
[... 1193 more characters not shown ...]
```

stdout:

```
planner/ranking.py:208: PlannerError
=========================== short test summary info ============================
FAILED tests/test_ranking.py::test_stopped_only_when_the_budget_ran_out - Ass...
FAILED tests/test_ranking.py::test_incomplete_top_list_is_a_lower_bound_not_a_promise
2 failed, 20 passed in 1.21s
```

**deepseek ran** · exit code 0

```bash
cd /repo && python -m pytest -q tests/test_ranking.py -k "stopped_only or lower_bound" 2>&1 | grep -E "^E |assert" | head -20
```

stdout:

```
        assert exhaustive.complete is True
        assert exhaustive.stopped is False
        assert tight.complete is False
        assert tight.stopped is True
        assert heuristic.complete is False
>       assert heuristic.stopped is False
E       AssertionError: assert True is False
E        +  where True = SearchResult(best=[RankedSchedule(choices=[Choice(course='A', section='1', meetings=[Section(course='A', section='1', ...ore=486, rank=1, occurrence=0, window=(480, 1200), not_before=540)], total=1, complete=False, explored=3, stopped=True).stopped
E           planner.model.PlannerError: no schedule without overlaps is possible for A, B, C; for example A A1 (Mon 09:00-10:00 in R) clashes with B B1
```

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='tests/test_ranking.py'
s=open(p).read()
s=s.replace('''    # A tiny exhaustive search under a heuristic-only order (no sound prefix)
    # is incomplete but did not stop: saying "stopped" would be a lie. One
    # feasible schedule, order starting with ``span``.
    small = [Section("A", "1", "Mon", 540, 600, "R"), Section("B", "1", "Tue", 540, 600, "R")]''','''    # A tiny search under a heuristic-only order (no sound prefix) is
    # incomplete without the budget being the reason: saying "stopped after N
    # steps" would be a lie, because the stop came from the heuristic.
    small = [Section("A", "1", "Mon", 540, 600, "R"), Section("B", "1", "Tue", 540, 600, "R")]''')
s=s.replace('''    good = [
        Section("A", "A1", "Mon", 540, 600, "R"),
        Section("B", "B1", "Mon", 540, 600, "R"),
        Section("B", "B2", "Mon", 600, 660, "R"),
        Section("C", "C1", "Mon", 600, 660, "R"),
    ]''','''    good = [
        Section("A", "A1", "Mon", 540, 600, "R"),
        Section("A", "A2", "Tue", 540, 600, "R"),
        Section("B", "B1", "Mon", 600, 660, "R"),
        Section("B", "B2", "Wed", 600, 660, "R"),
        Section("C", "C1", "Tue", 600, 660, "R"),
        Section("C", "C2", "Thu", 600, 660, "R"),
    ]''')
open(p,'w').write(s)
EOF
python -m pytest -q tests/test_ranking.py 2>&1 | grep -E "^E |passed|failed" | head -10
```

stdout:

```
E       AssertionError: assert True is False
E        +  where True = SearchResult(best=[RankedSchedule(choices=[Choice(course='A', section='1', meetings=[Section(course='A', section='1', ...ore=486, rank=1, occurrence=0, window=(480, 1200), not_before=540)], total=1, complete=False, explored=3, stopped=True).stopped
1 failed, 21 passed in 1.14s
```

*15 model calls · 529,761 input tokens (522,880 cache read, 0 cache write) · 3,635 output tokens*

### gemini (worker) · 10:16:03

**gemini ran** `git show edf0ae4` · exit code 0

<details><summary>output, 80 lines</summary>

stdout:

````
commit edf0ae44ee229a19e86efb54d0fc851dfca50f24
Author: chatgpt <chatgpt@village.local>
Date:   Tue Nov 24 10:14:42 2026 +0000

    Show travel distances to one decimal place

diff --git a/CHANGELOG.md b/CHANGELOG.md
index 3adff9a..f222e4f 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -7,6 +7,9 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 ## [Unreleased]
 
+### Fixed
+- Displayed travel-warning distances to one decimal place; added a strict walking-time boundary regression test.
+
 ## [0.4.0] - 2026-11-24
 
 ### Added
diff --git a/README.md b/README.md
index c01d027..9dde1bd 100644
--- a/README.md
+++ b/README.md
@@ -77,9 +77,9 @@ $ planner travel examples/sections.csv examples/buildings.csv CS101 MATH101
       Mon 10:00-11:00 @ Math Hall
       Wed 10:00-11:00 @ Math Hall
       Fri 10:00-11:00 @ Math Hall
-warning: Fri CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
-warning: Mon CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
-warning: Wed CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.12 km needs about 1 min to walk at 5 km/h, but only 0 min available
+warning: Fri CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1 min to walk at 5 km/h, but only 0 min available
+warning: Mon CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1 min to walk at 5 km/h, but only 0 min available
+warning: Wed CS101 A at 'Hall A' to MATH101 A at 'Math Hall': 0.1 km needs about 1 min to walk at 5 km/h, but only 0 min available
 ```
 
 ### 5. Exporting Schedules
diff --git a/planner/travel.py b/planner/travel.py
index e4d81ff..991530f 100644
--- a/planner/travel.py
+++ b/planner/travel.py
@@ -166,7 +166,7 @@ def travel_warnings(
             if gap < needed:
                 warning = (
                     f"warning: {day} {first.course} {first.section} at {first.location!r} to "
-                    f"{second.course} {second.section} at {second.location!r}: {distance:.2f} km "
+                    f"{second.course} {second.section} at {second.location!r}: {distance:.1f} km "
                     f"needs about {needed:.0f} min to walk at {speed:g} km/h, but only {gap} min available"
                 )
                 if warning not in walking_seen:
diff --git a/tests/test_travel.py b/tests/test_travel.py
index d879f04..21be179 100644
--- a/tests/test_travel.py
+++ b/tests/test_travel.py
@@ -67,7 +67,7 @@ def test_travel_warns_when_walk_too_long_and_for_unknown_locations():
     walking = next(warning for warning in warnings if "needs about" in warning)
     unknown = next(warning for warning in warnings if "unknown building" in warning)
     assert "Mon" in walking and "BIO A" in walking and "CHEM B" in walking
-    assert "km" in walking and "min available" in walking
+    assert "1.1 km" in walking and "min available" in walking
     assert "Unlisted Hall" in unknown and "MATH A" in unknown
 
 
@@ -111,6 +111,15 @@ def test_exact_walking_gap_same_building_and_day_boundaries():
     ]
     assert travel_warnings(exact_gap, buildings) == []
 
+    # One minute less than the exact requirement does warn.
+    short_gap = [
+        exact_gap[0],
+        Section("B", "1", "Mon", 10 * 60 + 5, 11 * 60, "B"),
+    ]
+    warnings = travel_warnings(short_gap, buildings)
+    assert len(warnings) == 1
+    assert "0.5 km" in warnings[0] and "only 5 min available" in warnings[0]
+
     # Zero travel time for the same building needs no positive gap.
     same_building = [
         Section("A", "1", "Mon", 9 * 60, 10 * 60, "A"),
````

</details>

**gemini ran** `git status` · exit code 0

stdout:

```
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   planner/cli.py
	modified:   planner/ranking.py
	modified:   tests/test_cli.py
	modified:   tests/test_fuzz.py
	modified:   tests/test_ranking.py

no changes added to commit (use "git add" and/or "git commit -a")
```

**gemini posted to chat:**

> @chatgpt Review finding on commit edf0ae4 (Task 19):
> Task 19 specifies: "travel warning message print needed minutes with one decimal; add boundary test (gap == needed exact semantic)".
> In `planner/travel.py`, `{distance:.2f} km` was changed to `{distance:.1f} km`, but `needed` was left as `{needed:.0f} min`:
> ```python
> f"{second.course} {second.section} at {second.location!r}: {distance:.1f} km "
> f"needs about {needed:.0f} min to walk at {speed:g} km/h, but only {gap} min available"
> ```
> DeepSeek's original report noted that rounding minutes to 0 decimals can cause cases like 30.4 min vs 30 min available to print "needs about 30 min ..., but only 30 min available".
> Should `{needed:.1f} min` (or both distance and needed) be formatted to one decimal place as requested? (If so, README and test expectations for `needed` minutes will also need updating to match, e.g. `1.4 min` for the README example).

*checked: check_balance*

**gemini said:**

> I reviewed commit `edf0ae4` for Task 19 and found that while `{distance:.2f} km` was changed to `{distance:.1f} km`, the needed minutes was left formatted as `{needed:.0f} min` rather than one decimal place (`{needed:.1f} min`) as requested in Task 19.
>
> I posted this review finding in the village chat so ChatGPT can update `planner/travel.py` and the corresponding tests/README. DeepSeek currently has in-progress modifications for Task 20. I will wait for both tasks to be finalized before completing the final review and tagging `v1.0.1`.

*5 model calls · 293,277 input tokens (273,821 cache read, 0 cache write) · 1,412 output tokens*

[Index](README.md) · [Previous round](round-030.md) · [Next round](round-032.md)
