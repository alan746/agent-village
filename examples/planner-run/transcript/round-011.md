# Round 11 of run 20261124_033232

[Index](README.md) · [Previous round](round-010.md) · [Next round](round-012.md)

### claude (leader) · 09:16:11

**claude ran** `cd /repo && git status --short; git log --oneline | head -5` · exit code 0

<details><summary>output, 19 lines</summary>

stdout:

```
 M check.sh
 M planner/cli.py
 M planner/solver.py
 M pyproject.toml
?? planner/export.py
?? planner/preferences.py
?? planner/ranking.py
?? requirements-dev.txt
?? tests/benchmark.py
?? tests/data/
?? tests/make_bench.py
?? tests/test_export.py
?? tests/test_ranking.py
4a85d5e Fix show window clipping and skip unusable sections
5fb176c Wire exam clash command into CLI
e382c62 Add exam CSV parsing and clash detection
2292168 M1c: Add examples documentation and update .gitignore
40434d2 M1b: CLI (conflicts/plan/show), backtracking solver with explanations, weekly grid
```

</details>

**claude said:**

> Progress is happening; I'll let them continue.

*2 model calls · 35,316 input tokens (17,477 cache read, 17,833 cache write) · 84 output tokens*

### chatgpt (worker) · 09:16:14

**chatgpt ran** `python -m pip install --user icalendar` · exit code 0

<details><summary>output, 20 lines</summary>

stdout:

```
Collecting icalendar
  Downloading icalendar-7.3.2-py3-none-any.whl.metadata (7.0 kB)
Collecting python-dateutil (from icalendar)
  Downloading python_dateutil-4.0.0-py3-none-any.whl.metadata (7.3 kB)
Collecting typing-extensions~=4.10 (from icalendar)
  Downloading typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting tzdata>=2025.3 (from icalendar)
  Downloading tzdata-2026.6-py2.py3-none-any.whl.metadata (1.4 kB)
Downloading icalendar-7.3.2-py3-none-any.whl (542 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 542.5/542.5 kB 11.1 MB/s eta 0:00:00
Downloading typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Downloading tzdata-2026.6-py2.py3-none-any.whl (348 kB)
Downloading python_dateutil-4.0.0-py3-none-any.whl (92 kB)
Installing collected packages: tzdata, typing-extensions, python-dateutil, icalendar
Successfully installed icalendar-7.3.2 python-dateutil-4.0.0 typing-extensions-4.16.0 tzdata-2026.6
```

stderr:

```

[notice] A new release of pip is available: 25.0.1 -> 26.3
[notice] To update, run: pip install --upgrade pip
```

</details>

**chatgpt ran** `./check.sh` · **[FAILED]** exit code 1

stdout:

```
=== Running test suite with coverage ===
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0 -- /usr/local/bin/python3
cachedir: .pytest_cache
rootdir: /repo
configfile: pyproject.toml
plugins: cov-7.1.0
collecting ... collected 97 items

tests/test_cli.py::test_conflicts_reports_pairs PASSED                   [  1%]
tests/test_cli.py::test_conflicts_clean_file PASSED                      [  2%]
tests/test_cli.py::test_plan_finds_schedule PASSED                       [  3%]
tests/test_cli.py::test_plan_unknown_course PASSED                       [  4%]
tests/test_cli.py::test_plan_impossible PASSED                           [  5%]
tests/test_cli.py::test_plan_requires_courses PASSED                     [  6%]
tests/test_cli.py::test_show_grid_and_filters PASSED                     [  7%]
tests/test_cli.py::test_show_unknown_course PASSED                       [  8%]
tests/test_cli.py::test_malformed_input_has_no_traceback PASSED          [  9%]
tests/test_cli.py::test_missing_file PASSED                              [ 10%]
tests/test_cli.py::test_unexpected_value_error_becomes_a_clean_error PASSED [ 11%]
tests/test_cli.py::test_no_subcommand_prints_help PASSED                 [ 12%]
tests/test_cli.py::test_console_script_available PASSED                  [ 13%]
tests/test_cli.py::test_show_width_and_start_end_are_validated PASSED    [ 14%]
tests/test_cli.py::test_show_end_before_meetings_still_renders_empty PASSED [ 15%]
tests/test_cli.py::test_plan_explains_combination_failure PASSED         [ 16%]
tests/test_conflicts.py::test_all_overlaps_and_touching_does_not_conflict PASSED [ 17%]
tests/test_conflicts.py::test_contained_meetings_overlap PASSED          [ 18%]
tests/test_csvio.py::test_load_sections_valid_and_strips_fields PASSED   [ 19%]
tests/test_csvio.py::test_rejects_bad_csv[-empty CSV] PASSED             [ 20%]
tests/test_csvio.py::test_rejects_bad_csv[course,section,
[... 13933 bytes truncated ...]
)
            while position and _exact_key(best[position - 1], order) > key:
                position -= 1
            if position >= limit:
                return
            best.insert(position, item)
            if len(best) > limit:
                best.pop()
        else:
            best.append(item)
            best.sort(key=lambda other: _exact_key(other, order))
        if len(best) >= limit:
            worst = _exact_key(best[-1], order)
>           if worst[0] > min_bound[0]:
               ^^^^^^^^^^^^^^^^^^^^^^^
E           TypeError: '>' not supported between instances of 'int' and 'str'

planner/ranking.py:126: TypeError
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.16-final-0 _______________

Name                     Stmts   Miss  Cover
--------------------------------------------
planner/__init__.py          0      0   100%
planner/__main__.py          2      2     0%
planner/cli.py             149     22    85%
planner/conflicts.py         4      0   100%
planner/csvio.py            68      4    94%
planner/exams.py            81      1    99%
planner/export.py          163      7    96%
planner/model.py            10      0   100%
planner/preferences.py     100     20    80%
planner/ranking.py          99     21    79%
planner/show.py             82      1    99%
planner/solver.py          130      4    97%
--------------------------------------------
TOTAL                      888     82    91%
Required test coverage of 90% reached. Total coverage: 90.77%
=========================== short test summary info ============================
FAILED tests/test_ranking.py::test_limit_is_respected - TypeError: '>' not su...
FAILED tests/test_ranking.py::test_matches_brute_force_on_random_instances - ...
FAILED tests/test_ranking.py::test_patience_reports_incomplete_but_keeps_best_found
========================= 3 failed, 94 passed in 3.08s =========================
```

**chatgpt posted to chat:**

> Task 6 fix committed as 4a85d5e (show window clip + regression tests). Focused tests pass (`pytest tests/test_solver.py tests/test_show.py -q`, 23 passed). I installed `icalendar` to run ./check.sh; 94 passed, but three ranking tests fail with a reproducible TypeError in planner/ranking.py:126, `worst[0] > min_bound[0]` compares int to str (`test_limit_is_respected`, `test_matches_brute_force_on_random_instances`, `test_patience_reports_incomplete_but_keeps_best_found`). Deepseek please investigate. The check also reports 90.77% total coverage.

**task board:** submitted to task 6: Your result for task 6 was submitted.

> Committed `4a85d5e` (show grid clips meetings that start before the visible window; added regressions for clipping and selecting a usable section when another section internally overlaps). Focused check: `pytest tests/test_solver.py tests/test_show.py -q` (23 passed). `./check.sh` currently fails in three M2 ranking tests with an int/string TypeError at `planner/ranking.py:126`; reported to Deepseek in chat.

**chatgpt said:**

> Task 6 is committed as `4a85d5e`. The focused solver/show tests pass (23 passed). I also ran `./check.sh`; it currently has three failing M2 ranking tests, reported to Deepseek in chat.

*5 model calls · 87,897 input tokens (85,653 cache read, 2,229 cache write) · 923 output tokens*

### deepseek (worker) · 09:16:38

**deepseek ran** `cd /repo && sed -n 118,132p planner/ranking.py` · exit code 0

<details><summary>output, 16 lines</summary>

stdout:

```
            best.insert(position, item)
            if len(best) > limit:
                best.pop()
        else:
            best.append(item)
            best.sort(key=lambda other: _exact_key(other, order))
        if len(best) >= limit:
            worst = _exact_key(best[-1], order)
            if worst[0] > min_bound[0]:
                min_bound[0] = worst[0]

    def bound_key(chosen: list[Choice]) -> tuple:
        return measure(
            [row for choice in chosen for row in choice.meetings],
            not_before=not_before,
```

</details>

**deepseek said:**

> chatgpt's report is mine to fix: `worst[0] > min_bound[0]` compares the metrics tuple with the string sentinel. Using a `None` sentinel instead:

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/ranking.py'
s=open(p).read()
s=s.replace('''    # Loosest metrics bound of any stored schedule; pruned for as soon as the
    # cached bound already beats it (cheap test before recomputing measure).
    min_bound: list[tuple] = [("",)]''','''    # Metrics of the worst stored schedule, or None while the top list is not
    # full. Pruning happens as soon as the cheapest possible bound (the
    # metrics of the sections chosen so far) already loses to it.
    min_bound: list[tuple | None] = [None]''')
s=s.replace('''            if worst[0] > min_bound[0]:
                min_bound[0] = worst[0]''','''            if min_bound[0] is None or worst[0] > min_bound[0]:
                min_bound[0] = worst[0]''')
s=s.replace('''            if min_bound[0] > worst[0]:
                return
            if bound_key(chosen) > worst[0]:
                return''','''            if min_bound[0] is not None and min_bound[0] >= bound_key(chosen):
                return
            if bound_key(chosen) > worst[0]:
                return''')
open(p,'w').write(s)
EOF
timeout 110 python -m pytest tests/test_ranking.py -q 2>&1 | grep -E "^E |passed|failed"|head; timeout 100 python - <<'EOF'
import time,random
from planner.model import Section
from planner.ranking import search
rng=random.Random(1)
rows=[Section(f"C{c:02d}",f"S{s}",(d:=rng.choice("Mon Tue Wed Thu Fri".split())),h*60,(h+1)*60,"R") for c in range(40) for s in range(5) if (h:=rng.randrange(8,19
[... 209 more characters not shown ...]
```

stdout:

```
E       AssertionError: assert 2 == 4
E        +  where 2 = SearchResult(best=[RankedSchedule(choices=[Choice(course='A', section='S0', meetings=[Section(course='A', section='S0'..., span=120), score=128, rank=1, occurrence=0, window=(480, 1200), not_before=540)], total=2, complete=True, explored=5).total
E           AssertionError: assert [((2, 0, 60, ..., 'Room')],))] == [((2, 0, 60, ..., 'Room')],))]
E             
E             At index 1 diff: ((2, 1, 180, 420), [('C0', 'S2'), ('C1', 'S1'), ('C2', 'S2')], ([('Mon', 480, 540, 'Room'), ('Mon', 720, 780, 'Room'), ('Wed', 540, 600, 'Room'), ('Wed', 600, 660, 'Room')],)) != ((2, 1, 60, 240), [('C0', 'S0'), ('C1', 'S1'), ('C2', 'S2')], ([('Mon', 480, 540, 'Room'), ('Mon', 600, 660, 'Room'), ('Wed', 600, 660, 'Room')],))
E             Use -v to get more diff
E       AssertionError: assert True is False
E        +  where True = SearchResult(best=[RankedSchedule(choices=[Choice(course='C0', section='S0', meetings=[Section(course='C0', section='S... span=480), score=487, rank=1, occurrence=0, window=(480, 1200), not_before=540)], total=3, complete=True, explored=25).complete
3 failed, 6 passed in 0.26s
20000 0.01s found=10 complete=True
200000 0.01s found=10 complete=True
```

**deepseek said:**

> My cached-bound test is inverted (`min_bound >= bound` means the bound is at least as bad as the worst stored, so prune), and the 0.01 s run smells like over-pruning too. Fixing the comparison direction:

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/ranking.py'
s=open(p).read()
s=s.replace('''            if min_bound[0] is not None and min_bound[0] >= bound_key(chosen):
                return
            if bound_key(chosen) > worst[0]:
                return''','''            # ``min_bound`` is the metrics of the worst stored schedule; the
            # bound of this branch can only be worse, so the cached value
            # answers the common case without recomputing ``measure``.
            if min_bound[0] is not None and min_bound[0] < bound_key(chosen):
                return
            if bound_key(chosen) > worst[0]:
                return''')
open(p,'w').write(s)
EOF
timeout 110 python -m pytest tests/test_ranking.py -q 2>&1 | grep -E "^E |passed|failed"|head -4; timeout 100 python - <<'EOF'
import time,random
from planner.model import Section
from planner.ranking import search
rng=random.Random(1)
rows=[Section(f"C{c:02d}",f"S{s}",(d:=rng.choice("Mon Tue Wed Thu Fri".split())),h*60,(h+1)*60,"R") for c in range(40) for s in range(5) if (h:=rng.randrange(8,19))]
courses=sorted({r.course for r in rows})
for p in (20000,200000):
    t=time.time(); r=search(rows,courses,limit=10,patience=p); print(p,"%.2fs found=%d complete=%s"%(time.time()-t,r.total,r.complete))
EOF
```

stdout:

```
9 passed in 0.44s
20000 0.92s found=132 complete=False
200000 9.28s found=142 complete=False
```

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/ranking.py'
s=open(p).read()
s=s.replace('''        for candidate in options[position]:
            if stats["explored"] >= patience:
                stats["capped"] = True
                return
            if all(_no_overlap(candidate, other) for other in chosen):''','''        for candidate in options[position]:
            if all(_no_overlap(candidate, other) for other in chosen):''')
s=s.replace('''            if min_bound[0] is not None and min_bound[0] < bound_key(chosen):
                return
            if bound_key(chosen) > worst[0]:
                return''','''            value = bound_key(chosen)
            if min_bound[0] is not None and min_bound[0] < value:
                return
            if value > worst[0]:
                return''')
open(p,'w').write(s)
EOF
timeout 110 python -m pytest tests/test_ranking.py -q 2>&1 | tail -4
```

stdout:

```
.........                                                                [100%]
9 passed in 0.41s
```

**deepseek ran** · exit code 0

```bash
cd /repo && timeout 110 python - <<'EOF'
import random
from planner.model import Section
from planner.solver import solve
from planner.ranking import search
from planner.preferences import schedule_order_key
order=("days","early","gaps","span")
rng=random.Random(11)
bad=n=0
for t in range(300):
    rows=[];courses=[]
    for c in range(rng.randint(2,4)):
        name=f"C{c}";courses.append(name)
        for s in range(rng.randint(1,3)):
            for day in rng.sample(["Mon","Tue","Wed","Thu"],rng.randint(1,2)):
                st=rng.randrange(8,15)*60
                rows.append(Section(name,f"S{s}",day,st,st+rng.choice([60,90]),"R"))
    try: alls=solve(rows,courses)
    except Exception: continue
    n+=1
    ref=sorted(schedule_order_key(list(x),order) for x in alls)[:5]
    r=search(rows,courses,limit=5)
    got=[schedule_order_key(x.choices,order) for x in r.best]
    if got!=ref: bad+=1
print("n",n,"mismatch",bad)
EOF
timeout 60 python tests/benchmark.py | tail -4
```

stdout:

```
n 280 mismatch 0
benchmark data: /repo/tests/data/bench_40x5.csv (40 courses x 5 sections)
  default order       0.977s  (budget 2s)  ok
  days, gaps, span    0.971s  (budget 2s)  ok
benchmark passed
```

**deepseek said:**

> Ranking exact on 280 random instances; benchmark ~0.98 s (dominated by Python startup + CSV load). Committing M2 now, then wiring the benchmark into check.sh.

**deepseek ran** `cd /repo && git status --short && python -m pytest -q 2>&1 | tail -3` · exit code 0

<details><summary>output, 17 lines</summary>

stdout:

```
 M check.sh
 M planner/cli.py
 M planner/solver.py
 M pyproject.toml
?? planner/export.py
?? planner/preferences.py
?? planner/ranking.py
?? requirements-dev.txt
?? tests/benchmark.py
?? tests/data/
?? tests/make_bench.py
?? tests/test_export.py
?? tests/test_ranking.py
ERROR tests/test_export.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.62s
```

</details>

**deepseek ran** `cd /repo && git diff planner/cli.py | head -80; git log --oneline -3` · exit code 0

<details><summary>output, 41 lines</summary>

stdout:

```
diff --git a/planner/cli.py b/planner/cli.py
index a863f68..672db71 100644
--- a/planner/cli.py
+++ b/planner/cli.py
@@ -6,7 +6,7 @@ import sys
 from pathlib import Path
 from typing import Sequence
 
-from planner import preferences, ranking
+from planner import export, preferences, ranking
 from planner import show as show_module
 from planner.preferences import RankedSchedule
 from planner.conflicts import find_conflicts
@@ -106,6 +106,7 @@ def cmd_plan(args: argparse.Namespace) -> int:
         print("schedule:")
         _print_schedule(choices)
         print(render([row for choice in choices for row in choice.meetings]), end="")
+        export.handle_plan_exports(args, choices)
         return 0
     result = ranking.search(
         sections,
@@ -126,6 +127,7 @@ def cmd_plan(args: argparse.Namespace) -> int:
         )
     for item in result.best:
         _print_ranked(item, result.total, result.complete)
+    export.handle_plan_exports(args, result.best[0].choices)
     return 0
 
 
@@ -198,6 +200,7 @@ def build_parser() -> argparse.ArgumentParser:
         "--not-before", default="09:00", metavar="HH:MM",
         help="classes starting earlier than this count as early (default 09:00)",
     )
+    export.add_export_arguments(plan)
     plan.set_defaults(func=cmd_plan)
 
     show = sub.add_parser("show", help="print a weekly text grid")
4a85d5e Fix show window clipping and skip unusable sections
5fb176c Wire exam clash command into CLI
e382c62 Add exam CSV parsing and clash detection
```

</details>

**deepseek ran** `cd /repo && git diff --stat planner/solver.py; git stash list; git show HEAD --stat | head` · exit code 0

<details><summary>output, 13 lines</summary>

stdout:

```
 planner/solver.py | 67 ++++++++++++++++++++++++++++++++++++++++++-------------
 1 file changed, 52 insertions(+), 15 deletions(-)
commit 4a85d5e3427c002384f5f322b45191c05e02b969
Author: chatgpt <chatgpt@village.local>
Date:   Tue Nov 24 09:11:32 2026 +0000

    Fix show window clipping and skip unusable sections

 planner/show.py      | 10 +++++++---
 tests/test_show.py   |  9 +++++++++
 tests/test_solver.py | 11 +++++++++++
 3 files changed, 27 insertions(+), 3 deletions(-)
```

</details>

**deepseek said:**

> The CLI has gemini's export hooks mixed in; I'll commit only my paths (adding `export.py` is unnecessary for my commit but cli.py references it, so cli.py stays with gemini).

**deepseek ran** `cd /repo && git diff planner/solver.py | head -60` · exit code 0

<details><summary>output, 61 lines</summary>

stdout:

```
diff --git a/planner/solver.py b/planner/solver.py
index cc22ac1..b79a33b 100644
--- a/planner/solver.py
+++ b/planner/solver.py
@@ -2,6 +2,7 @@
 
 from dataclasses import dataclass, field
 from itertools import product
+from operator import attrgetter
 
 from planner.model import PlannerError, Section
 
@@ -31,6 +32,30 @@ class Choice:
         return [m.location for m in self.meetings]
 
 
+def usable_choices(course: str, groups: list[CourseSections]) -> list[Choice]:
+    """Sections of one course that can appear in a schedule.
+
+    A section whose own meetings overlap is dropped (it can never fit), but
+    the other sections of the course stay available. Only when every section
+    is broken is the course itself unusable.
+    """
+    usable: list[Choice] = []
+    broken: list[Choice] = []
+    for group in groups:
+        choice = Choice(group.course, group.section, list(group.meetings))
+        if _self_clash(choice.meetings):
+            broken.append(choice)
+        else:
+            usable.append(choice)
+    if not usable:
+        example = broken[0]
+        raise PlannerError(
+            f"course {course} is unusable: every section has overlapping"
+            f" meetings, e.g. section {example.section} ({describe(example)})"
+        )
+    return usable
+
+
 def group_sections(sections: list[Section]) -> dict[str, list[CourseSections]]:
     """Group meeting rows into ``course -> [section, ...]``, keeping file order."""
     courses: dict[str, list[CourseSections]] = {}
@@ -104,28 +129,18 @@ def solve(
         raise PlannerError(
             f"unknown course(s): {', '.join(unknown)} (known courses: {known})"
         )
-    options: list[list[Choice]] = []
-    for name in courses:
-        options.append(
-            [Choice(g.course, g.section, list(g.meetings)) for g in grouped[name]]
-        )
+    options = [usable_choices(name, grouped[name]) for name in courses]
 
     results: list[list[Choice]] = []
+    order = _search_order(options)
 
     def extend(position: int, chosen: list[Choice]) -> None:
         if limit is not None and len(results) >= limit:
             return
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && git add planner/solver.py planner/preferences.py planner/ranking.py tests/test_ranking.py tests/make_bench.py tests/benchmark.py tests/data/bench_40x5.csv && git commit -q -m "M2: preference ranking search, exact top-N, 40x5 benchmark

- solver: unusable sections dropped per course (usable_choices), MRV-like
  search order for the plain solve
- preferences: Preferences/measure/weighted/schedule_order_key, one total
  order shared by search and CLI
- ranking: depth-first search with a sound lower bound (no +1 day padding),
  patience budget for the count, incremental top-N insertion
- tests/test_ranking.py: brute-force comparison incl. all metric orders
- tests/make_bench.py + tests/benchmark.py: 40 courses x 5 sections data and
  a benchmark that fails if the CLI takes >= 2 s" -- planner/solver.py planner/preferences.py planner/ranking.py tests/test_ranking.py tests/make_bench.py tests/benchmark.py tests/data/bench_40x5.csv && git log --oneline -1 && git status --short
```

stdout:

```
1e3454c M2: preference ranking search, exact top-N, 40x5 benchmark
 M check.sh
 M planner/cli.py
 M pyproject.toml
?? planner/export.py
?? requirements-dev.txt
?? tests/test_export.py
```

**deepseek said:**

> Committed. Now hooking my benchmark into `check.sh` so the M2 timing gate is enforced by the shared script (it currently only looks for a top-level `benchmark.py`):

**deepseek ran** `cd /repo && git diff check.sh` · exit code 0

<details><summary>output, 28 lines</summary>

stdout:

```
diff --git a/check.sh b/check.sh
index d76eee4..af308d8 100755
--- a/check.sh
+++ b/check.sh
@@ -1,17 +1,17 @@
 #!/usr/bin/env bash
 set -euo pipefail
 
-# Ensure pytest-cov is available in the current Python environment
-if ! python3 -c "import pytest_cov" &>/dev/null; then
-    echo "Installing pytest-cov..."
-    python3 -m pip install -q --user pytest-cov
+# Ensure development dependencies are installed
+if ! python3 -c "import pytest, pytest_cov, icalendar" &>/dev/null; then
+    echo "Installing dev dependencies from requirements-dev.txt..."
+    python3 -m pip install -q --user -r requirements-dev.txt
 fi
 
 echo "=== Running test suite with coverage ==="
 python3 -m pytest -v --cov=planner --cov-fail-under=90 "$@"
 
 # Run benchmark if present
-for bench in benchmark.py benchmarks/benchmark.py tests/benchmark.py; do
+for bench in benchmark.py benchmarks/benchmark.py tests/benchmark.py benchmarks/bench.py; do
     if [[ -f "$bench" ]]; then
         echo "=== Running benchmark ($bench) ==="
         python3 "$bench"
```

</details>

**deepseek said:**

> gemini already extended check.sh to run `tests/benchmark.py` (my file), so nothing to change. Running `./check.sh` end to end:

**deepseek ran** `cd /repo && timeout 115 ./check.sh 2>&1 | tail -25` · exit code 0

<details><summary>output, 26 lines</summary>

stdout:

```

Name                     Stmts   Miss  Cover
--------------------------------------------
planner/__init__.py          0      0   100%
planner/__main__.py          2      2     0%
planner/cli.py             149     22    85%
planner/conflicts.py         4      0   100%
planner/csvio.py            68      4    94%
planner/exams.py            81      1    99%
planner/export.py          163      7    96%
planner/model.py            10      0   100%
planner/preferences.py     100     20    80%
planner/ranking.py          97      3    97%
planner/show.py             82      1    99%
planner/solver.py          130      4    97%
--------------------------------------------
TOTAL                      886     64    93%
Required test coverage of 90% reached. Total coverage: 92.78%
============================== 97 passed in 3.47s ==============================
=== Running benchmark (tests/benchmark.py) ===
benchmark data: /repo/tests/data/bench_40x5.csv (40 courses x 5 sections)
  default order       0.984s  (budget 2s)  ok
  days, gaps, span    0.944s  (budget 2s)  ok
benchmark passed
=== All checks passed! ===
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && timeout 100 python - <<'EOF'
from planner.csvio import load_sections
from planner.ranking import search
rows=load_sections("tests/data/bench_40x5.csv")
courses=sorted({r.course for r in rows})
for p in (20000,60000,150000):
    r=search(rows,courses,limit=10,patience=p)
    print(p, "found",r.total,"complete",r.complete)
EOF
```

stdout:

```
20000 found 43 complete False
60000 found 43 complete False
150000 found 43 complete False
```

**deepseek ran** · exit code 0

```bash
cd /repo && timeout 100 python - <<'EOF'
from planner.csvio import load_sections
from planner.ranking import search
rows=load_sections("tests/data/bench_40x5.csv")
courses=sorted({r.course for r in rows})
for p in (300000,1000000):
    r=search(rows,courses,limit=10,patience=p)
    print(p, "found",r.total,"complete",r.complete,"explored",r.explored)
EOF
```

stdout:

```
300000 found 49 complete False explored 300000
1000000 found 59 complete False explored 1000000
```

**deepseek said:**

> The node cap stops at 20000 but 60k–150k report the same total — a path in `visit` is returning without going through the cap check. Instrumenting:

**deepseek ran** · **[FAILED]** exit code 1

```bash
cd /repo && timeout 100 python - <<'EOF'
import planner.ranking as R
from planner.csvio import load_sections
res=[]
orig=R.search.__globals__
src=open('planner/ranking.py').read()
src=src.replace('''            position = len(best)''','''            PRUNED.append(key)
            position = len(best)''')
src=src.replace("            if position >= limit:\n                return","            if position >= limit:\n                return")
ns={'PRUNED':[]}
open('/tmp/rk2.py','w').write(src)
import sys; sys.path.insert(0,'/tmp'); import rk2
rows=load_sections("tests/data/bench_40x5.csv")
courses=sorted({r.course for r in rows})
r=rk2.search(rows,courses,limit=10,patience=60000)
print("explored",r.explored,"found",r.total,"offered",len(ns:=[]), "best",len(r.best))
EOF
```

stderr:

```
Traceback (most recent call last):
  File "<stdin>", line 14, in <module>
  File "/tmp/rk2.py", line 166, in search
    visit(0, [])
  File "/tmp/rk2.py", line 162, in visit
    visit(position + 1, chosen)
  File "/tmp/rk2.py", line 162, in visit
    visit(position + 1, chosen)
  File "/tmp/rk2.py", line 162, in visit
    visit(position + 1, chosen)
  [Previous line repeated 37 more times]
  File "/tmp/rk2.py", line 156, in visit
    offer(chosen)
  File "/tmp/rk2.py", line 114, in offer
    PRUNED.append(key)
    ^^^^^^
NameError: name 'PRUNED' is not defined
```

*15 model calls · 542,024 input tokens (537,216 cache read, 0 cache write) · 3,055 output tokens*

### gemini (worker) · 09:18:31

**gemini ran** `python3 -c "print(repr(open('/tmp/test.ics').read()[:350]))"` · exit code 0

stdout:

```
'BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Village Planner//EN\nCALSCALE:GREGORIAN\nMETHOD:PUBLISH\nBEGIN:VEVENT\nUID:CS101-A-Mon-540-600-2026-11-30@planner\nDTSTAMP:20261124T091600Z\nDTSTART:20261130T090000\nDTEND:20261130T100000\nRRULE:FREQ=WEEKLY;COUNT=14;BYDAY=MO\nSUMMARY:CS101 A\nLOCATION:Hall A\nDESCRIPTION:Course: CS101\\nSection: A\\nLocation: Hall A\nEND:VEV'
```

**gemini ran** `python3 -c "print(open('/tmp/test.ics', 'rb').read()[:350])"` · exit code 0

stdout:

```
b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Village Planner//EN\r\nCALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\nBEGIN:VEVENT\r\nUID:CS101-A-Mon-540-600-2026-11-30@planner\r\nDTSTAMP:20261124T091600Z\r\nDTSTART:20261130T090000\r\nDTEND:20261130T100000\r\nRRULE:FREQ=WEEKLY;COUNT=14;BYDAY=MO\r\nSUMMARY:CS101 A\r\nLOCATION:Hall A\r\nDESCRIPTION:Course: CS101\\nSection: A\\nLocation: H'
```

**gemini ran** · exit code 0

```bash
python3 -c "
from icalendar import Calendar
cal = Calendar.from_ical(open('/tmp/test.ics', 'rb').read())
for e in cal.walk('VEVENT'):
    print(e['summary'], repr(str(e['description'])))
"
```

stdout:

```
CS101 A 'Course: CS101\nSection: A\nLocation: Hall A'
CS101 A 'Course: CS101\nSection: A\nLocation: Hall A'
CS101 A 'Course: CS101\nSection: A\nLocation: Hall A'
```

**gemini ran** `python3 -m pytest tests/test_cli.py` · exit code 0

stdout:

```
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: /repo
configfile: pyproject.toml
plugins: cov-7.1.0
collected 16 items

tests/test_cli.py ................                                       [100%]

============================== 16 passed in 1.05s ==============================
```

**gemini ran** `tail -n 35 tests/test_cli.py` · exit code 0

<details><summary>output, 36 lines</summary>

stdout:

```
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
```

</details>

**gemini ran** `head -n 25 tests/test_cli.py` · exit code 0

<details><summary>output, 26 lines</summary>

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
    path.write_text(GOOD, encoding="utf-8")
    return str(path)


def run(capsys, *argv):
```

</details>

**gemini ran** · **[FAILED]** exit code 1

```bash
python3 -c "
with open('tests/test_cli.py') as f:
    content = f.read()

extra = '''

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
    assert "<!DOCTYPE html>" in html_content
    assert "CS101" in html_content
'''

with open('tests/test_cli.py', 'w') as f:
    f.write(content + extra)
"
```

stderr:

```
bash: line 1: !DOCTYPE: No such file or directory
```

**gemini ran** `tail -n 15 tests/test_cli.py` · exit code 0

<details><summary>output, 16 lines</summary>

stdout:

```


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
```

</details>

**gemini ran** · exit code 0, no output

```bash
python3 -c '
with open("tests/test_cli.py", "a") as f:
    f.write("""

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
""")
'
```

**gemini ran** `pytest tests/test_cli.py` · exit code 0

stdout:

```
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: /repo
configfile: pyproject.toml
plugins: cov-7.1.0
collected 17 items

tests/test_cli.py .................                                      [100%]

============================== 17 passed in 1.14s ==============================
```

**gemini ran** `pytest tests/test_export.py` · exit code 0

stdout:

```
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: /repo
configfile: pyproject.toml
plugins: cov-7.1.0
collected 12 items

tests/test_export.py ............                                        [100%]

============================== 12 passed in 0.27s ==============================
```

**gemini ran** `git diff planner/cli.py pyproject.toml check.sh` · exit code 0

<details><summary>output, 83 lines</summary>

stdout:

```
diff --git a/check.sh b/check.sh
index d76eee4..af308d8 100755
--- a/check.sh
+++ b/check.sh
@@ -1,17 +1,17 @@
 #!/usr/bin/env bash
 set -euo pipefail
 
-# Ensure pytest-cov is available in the current Python environment
-if ! python3 -c "import pytest_cov" &>/dev/null; then
-    echo "Installing pytest-cov..."
-    python3 -m pip install -q --user pytest-cov
+# Ensure development dependencies are installed
+if ! python3 -c "import pytest, pytest_cov, icalendar" &>/dev/null; then
+    echo "Installing dev dependencies from requirements-dev.txt..."
+    python3 -m pip install -q --user -r requirements-dev.txt
 fi
 
 echo "=== Running test suite with coverage ==="
 python3 -m pytest -v --cov=planner --cov-fail-under=90 "$@"
 
 # Run benchmark if present
-for bench in benchmark.py benchmarks/benchmark.py tests/benchmark.py; do
+for bench in benchmark.py benchmarks/benchmark.py tests/benchmark.py benchmarks/bench.py; do
     if [[ -f "$bench" ]]; then
         echo "=== Running benchmark ($bench) ==="
         python3 "$bench"
diff --git a/planner/cli.py b/planner/cli.py
index a863f68..672db71 100644
--- a/planner/cli.py
+++ b/planner/cli.py
@@ -6,7 +6,7 @@ import sys
 from pathlib import Path
 from typing import Sequence
 
-from planner import preferences, ranking
+from planner import export, preferences, ranking
 from planner import show as show_module
 from planner.preferences import RankedSchedule
 from planner.conflicts import find_conflicts
@@ -106,6 +106,7 @@ def cmd_plan(args: argparse.Namespace) -> int:
         print("schedule:")
         _print_schedule(choices)
         print(render([row for choice in choices for row in choice.meetings]), end="")
+        export.handle_plan_exports(args, choices)
         return 0
     result = ranking.search(
         sections,
@@ -126,6 +127,7 @@ def cmd_plan(args: argparse.Namespace) -> int:
         )
     for item in result.best:
         _print_ranked(item, result.total, result.complete)
+    export.handle_plan_exports(args, result.best[0].choices)
     return 0
 
 
@@ -198,6 +200,7 @@ def build_parser() -> argparse.ArgumentParser:
         "--not-before", default="09:00", metavar="HH:MM",
         help="classes starting earlier than this count as early (default 09:00)",
     )
+    export.add_export_arguments(plan)
     plan.set_defaults(func=cmd_plan)
 
     show = sub.add_parser("show", help="print a weekly text grid")
diff --git a/pyproject.toml b/pyproject.toml
index 951fcb8..47f3439 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -10,6 +10,13 @@ readme = "README.md"
 requires-python = ">=3.10"
 license = {text = "MIT"}
 
+[project.optional-dependencies]
+dev = [
+    "pytest",
+    "pytest-cov",
+    "icalendar",
+]
+
 [project.scripts]
 planner = "planner.cli:main"
```

</details>

**gemini ran** `git status` · exit code 0

<details><summary>output, 17 lines</summary>

stdout:

```
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   check.sh
	modified:   planner/cli.py
	modified:   pyproject.toml
	modified:   tests/test_cli.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	planner/export.py
	requirements-dev.txt
	tests/test_export.py

no changes added to commit (use "git add" and/or "git commit -a")
```

</details>

**gemini ran** `git log -n 3 --oneline` · exit code 0

stdout:

```
1e3454c M2: preference ranking search, exact top-N, 40x5 benchmark
4a85d5e Fix show window clipping and skip unusable sections
5fb176c Wire exam clash command into CLI
```

**gemini ran** `python3 -m pytest tests/` · exit code 0

<details><summary>output, 19 lines</summary>

stdout:

```
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: /repo
configfile: pyproject.toml
plugins: cov-7.1.0
collected 98 items

tests/test_cli.py .................                                      [ 17%]
tests/test_conflicts.py ..                                               [ 19%]
tests/test_csvio.py .............                                        [ 32%]
tests/test_exams.py ...................                                  [ 52%]
tests/test_export.py ............                                        [ 64%]
tests/test_gen_data.py ...                                               [ 67%]
tests/test_ranking.py .........                                          [ 76%]
tests/test_show.py .........                                             [ 85%]
tests/test_solver.py ..............                                      [100%]

============================== 98 passed in 1.87s ==============================
```

</details>

*15 model calls · 725,634 input tokens (666,756 cache read, 0 cache write) · 1,710 output tokens*

[Index](README.md) · [Previous round](round-010.md) · [Next round](round-012.md)
