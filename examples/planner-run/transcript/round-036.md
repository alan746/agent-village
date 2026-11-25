# Round 36 of run 20261124_033232

[Index](README.md) · [Previous round](round-035.md) · [Next round](round-037.md)

### claude (leader) · 10:28:13

**claude posted to chat:**

> Leader: task 21 closed (8af5781). deepseek: note chatgpt/gemini showed your ICS 'bug' wasn't reproducible on the parent commit — please don't report bugs without a failing-before repro on HEAD; and the commit message/changelog must not claim an ICS fix. Please proceed with task 22.

**task board:** Task 21 is marked done.

**claude said:**

> I closed task 21. Gemini's commit `8af5781` makes `--top`, `--prefer` and `--not-before` each trigger ranking on their own for a single course. It adds regression tests, including that explicitly passing the default values still counts as asking for ranking. This follows chatgpt's finding that `b7d2359` only handled `--prefer`. I haven't re-run those commands myself.
>
> Deepseek's ICS "bug" turned out not to be real. chatgpt and gemini both found that `export.py` already computed the start date correctly before `6641a26`, and the new export tests also pass on the parent commit. I told deepseek not to report bugs without a failing-before repro on HEAD, and that the commit message and CHANGELOG must not claim an ICS fix.
>
> Task 22 (the misleading ranking score) is still with deepseek. Gemini will review it, update the CHANGELOG and tag `v1.0.2` once `./check.sh` is green.

*2 model calls · 111,091 input tokens (109,290 cache read, 1,795 cache write) · 516 output tokens*

### chatgpt (worker) · 10:28:18

*checked: read_task*

**[COMPACTED]** memory compacted: summarized messages 677-690

**chatgpt ran** `cd /repo && git log --oneline --decorate -7 && git status --short && git show --stat --oneline HEAD` · exit code 0

<details><summary>output, 13 lines</summary>

stdout:

```
8af5781 (HEAD -> main) Route single-course plan through ranking search on any ranking flag (--top, --not-before, --prefer)
6641a26 ICS: anchor DTSTART on the meeting's real weekday (was off for non-Monday term starts)
b7d2359 Rank a single course when --prefer is given instead of using the shortcut
49dd5f4 (tag: v1.0.1) Update CHANGELOG for v1.0.0 and v1.0.1 releases
f06c037 Ranking: honest best-found reporting when the search is not exhaustive
522986a Show required walking times precisely
edf0ae4 Show travel distances to one decimal place
 M planner/preferences.py
8af5781 Route single-course plan through ranking search on any ranking flag (--top, --not-before, --prefer)
 planner/cli.py    | 18 +++++++++++-------
 tests/test_cli.py | 39 +++++++++++++++++++++++++++++++++++++++
 2 files changed, 50 insertions(+), 7 deletions(-)
```

</details>

**chatgpt ran** `cd /repo && git show 8af5781 -- && sed -n '110,180p' planner/cli.py && sed -n '220,250p' planner/cli.py` · exit code 0

<details><summary>output, 88 lines</summary>

stdout:

```
commit 8af5781f95a0aede070ca7063bc36e8b10e706a6
Author: gemini <gemini@village.local>
Date:   Tue Nov 24 10:27:52 2026 +0000

    Route single-course plan through ranking search on any ranking flag (--top, --not-before, --prefer)

diff --git a/planner/cli.py b/planner/cli.py
index 6c5c063..06d1740 100644
--- a/planner/cli.py
+++ b/planner/cli.py
@@ -127,10 +127,14 @@ def cmd_plan(args: argparse.Namespace) -> int:
     courses = list(dict.fromkeys(args.courses))
     not_before = _minutes(args.not_before) if args.not_before is not None else 9 * 60
     order = preferences.normalise_order(args.prefer)
-    if len(courses) == 1 and not args.prefer:
-        # A single course without preferences: show its first usable section.
-        # Any ranking flag (--prefer) must instead go through ``search`` below,
-        # which ranks every feasible section of the course.
+    # ``--top``/``--not-before`` default to None so an explicit use can be
+    # told apart from "not given": the single-course shortcut may only hide
+    # ranking when no ranking flag was actually asked for.
+    explicit = args.prefer or args.top is not None or args.not_before is not None
+    if len(courses) == 1 and not explicit:
+        # A single course without ranking flags: show its first usable
+        # section. Otherwise fall through to ``search``, which ranks every
+        # feasible section of the course.
         schedules = solve(sections, courses, limit=1)
         choices = schedules[0]
         print("schedule:")
@@ -144,7 +148,7 @@ def cmd_plan(args: argparse.Namespace) -> int:
         courses,
         order=order,
         not_before=not_before,
-        limit=args.top,
+        limit=args.top if args.top is not None else 10,
     )
     if not result.best:
         raise PlannerError("no schedule without overlaps is possible")
@@ -230,7 +234,7 @@ def build_parser() -> argparse.ArgumentParser:
     plan.add_argument("file", help="sections CSV")
     plan.add_argument("courses", n
[... 5327 bytes truncated ...]
se a step
        # budget ran out: report the count as the lower bound it is without
        # claiming the search was cut short.
        print(
            f"at least {result.total} feasible schedule(s) exist; showing the"
            f" best {how_many} found (not all were enumerated):"
        )
    for item in result.best:
        _print_ranked(item, result.total, result.complete)
    _print_travel_warnings(args, result.best[0].choices)
    export.handle_plan_exports(args, result.best[0].choices)
    return 0


        description="Plan a university term from a CSV of course sections.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    conflicts = sub.add_parser("conflicts", help="list pairs of sections that overlap")
    conflicts.add_argument("file", help="sections CSV")
    conflicts.set_defaults(func=cmd_conflicts)

    exams = sub.add_parser("exams", help="list exam clashes for selected courses")
    exams.add_argument("file", help="exams CSV")
    exams.add_argument("courses", nargs="+", metavar="COURSE", help="course codes")
    exams.set_defaults(func=cmd_exams)

    plan = sub.add_parser("plan", help="pick one non-overlapping section per course")
    plan.add_argument("file", help="sections CSV")
    plan.add_argument("courses", nargs="+", metavar="COURSE", help="course codes")
    plan.add_argument(
        "--top", type=_positive_int, default=None, metavar="N",
        help="how many ranked schedules to print (default 10)",
    )
    plan.add_argument(
        "--prefer", action="append", metavar="METRIC",
        help="preference in priority order, repeatable; one of"
             " days (fewest days on campus), early (no classes before"
             " --not-before), gaps (smallest total gap), span (shortest days)",
    )
    plan.add_argument(
        "--not-before", default=None, metavar="HH:MM",
        help="classes starting earlier than this count as early (default 09:00)",
    )
    export.add_export_arguments(plan)
```

</details>

**chatgpt ran** · exit code 0

```bash
cd /repo && pytest -q tests/test_cli.py && python -m planner plan examples/sections.csv CS101 --top 3 | head -5 && python -m planner plan examples/sections.csv CS101 --not-before 12:00 | head -5
```

<details><summary>output, 13 lines</summary>

stdout:

```
.................................                                        [100%]
33 passed in 1.64s
2 feasible schedule(s) found; best 2:
#1 (score 2048994723062) 2 day(s) on campus, 0 early class(es), 0 min of gaps, 180 min on campus
    CS101 B
        Tue 10:00-11:30 @ Science Center
        Thu 10:00-11:30 @ Science Center
2 feasible schedule(s) found; best 2:
#1 (score 2049197976184) 2 day(s) on campus, 2 early class(es), 0 min of gaps, 180 min on campus
    CS101 B
        Tue 10:00-11:30 @ Science Center
        Thu 10:00-11:30 @ Science Center
```

</details>

**chatgpt ran** `cd /repo && git diff -- planner/preferences.py && git status --short` · exit code 0

<details><summary>output, 61 lines</summary>

stdout:

```
diff --git a/planner/preferences.py b/planner/preferences.py
index 30262b7..13f9a15 100644
--- a/planner/preferences.py
+++ b/planner/preferences.py
@@ -47,7 +47,12 @@ class Metrics:
 
 @dataclass
 class RankedSchedule:
-    """A feasible schedule together with its measured and weighted scores."""
+    """A feasible schedule together with its measured metrics and display score.
+
+    ``score`` is a mixed-radix encoding of ``metrics`` (see :func:`weighted`):
+    lower is better and it orders schedules exactly like the lexicographic
+    preference key while the digits fit ``_METRIC_BOUND``.
+    """
 
     choices: list[Choice]
     metrics: Metrics
@@ -150,17 +155,31 @@ def measure(meetings: list[Section], *, not_before: int = 9 * 60) -> Metrics:
     return Metrics(days=len(per_day), early=early, gaps=gaps, span=span)
 
 
-def weighted(metrics: Metrics, order: tuple[str, ...]) -> int:
-    """Combine metrics into one number, weighting earlier preferences more.
+#: Upper bound used by :func:`weighted` as the unit of one "small step" in a
+#: metric: a full week in minutes. Every bounded metric (``gaps``, ``span``)
+#: is at most a few days; ``positional`` clamps them to this unit anyway.
+_METRIC_BOUND = 7 * 24 * 60
 
-    The first preference counts ``len(order)`` times, the next one less, so a
-    single-unit improvement of a higher preference always beats any change in
-    the preferences below it (each lower metric is bounded by the number of
-    meetings times a day's minutes, far below the weight ratio).
+
+def weighted(metrics: Metrics, order: tuple[str, ...]) -> int:
+    """Mix the metrics into one integer that respects the preference order.
+
+    The result is a mixed-radix number: the first preference is the most
+    significant digit, each following one less significant. Every digit is
+    clamped to ``[0, _METRIC_BOUND]``, so one unit of a higher preference
+    outweighs *any* change in all preferences below it -- which is what the
+    lexicographic ordering does, and what a plain weighted sum (4*span vs
+    1*days) does not.
+
+    Non-monotonic metrics (``gaps``, ``span``) are clamped and so can collide,
+    which is fine: the score is for display and rough comparisons, the ranking
+    itself uses the lexicographic key.
     """
-    weights = list(range(len(order), 0, -1))
-    values = metrics.as_dict()
-    return sum(weights[i] * values[name] for i, name in enumerate(order))
+    value = 0
+    for name in order:
+        raw = metrics.as_dict()[name]
+        value = value * (_METRIC_BOUND + 1) + min(max(raw, 0), _METRIC_BOUND)
+    return value
 
 
 def sort_key(schedule: RankedSchedule, order: tuple[str, ...]) -> tuple:
 M planner/preferences.py
```

</details>

**chatgpt posted to chat:**

> Reviewed 8af5781: the explicit-ranking detection with None argparse defaults and effective defaults in cmd_plan looks sound; regression coverage includes explicit default-valued options. `pytest -q tests/test_cli.py` passes (33), and the reported single-course repros now go through ranked output for `--top 3` and `--not-before 12:00`. I don't see a further task-21 blocker.

**chatgpt posted to chat:**

> One review note for the in-progress Task 22 diff: `weighted()` is still being retained, so the CLI continues to print `score` (now mixed-radix numbers around 2e12 in the sample). Although this might preserve order, task 22 specifically asks to remove the misleading score and print priority-ordered named metrics; please ensure `_print_ranked`/tests/README reflect that rather than just repairing the numerical ordering.

**chatgpt said:**

> I reviewed `8af5781` and found no further blocker in the single-course ranking fix. Its CLI tests pass, and `--top 3` and `--not-before 12:00` now trigger ranked output.
>
> I also noted in chat that the in-progress Task 22 change should remove the displayed score and print named metrics in preference order, as requested, rather than merely replacing it with a large mixed-radix score.

*9 model calls · 159,035 input tokens (132,732 cache read, 26,276 cache write) · 1,779 output tokens*

### deepseek (worker) · 10:28:58

**deepseek ran** `cd /repo && git status --short; sed -n 105,122p planner/cli.py; grep -n "score" README.md CHANGELOG.md tests/*.py | head` · exit code 0

<details><summary>output, 21 lines</summary>

stdout:

```
 M planner/preferences.py
        hour_text, minute_text = text, "0"
    try:
        hour, minute = int(hour_text), int(minute_text)
    except ValueError:
        raise PlannerError(f"invalid time {clock!r}; expected HH:MM") from None
    if not 0 <= hour <= 24 or not 0 <= minute < 60 or (hour, minute) > (24, 0):
        raise PlannerError(f"invalid time {clock!r}; expected HH:MM between 00:00 and 24:00")
    return hour * 60 + minute


def _print_ranked(item: RankedSchedule, total: int | None, complete: bool) -> None:
    print(f"#{item.rank} (score {item.score}) {item.describe()}")
    _print_schedule(item.choices, indent="    ")
    print(render(
        [row for choice in item.choices for row in choice.meetings],
        start=item.window[0],
        end=item.window[1],
    ), end="")
tests/test_ranking.py:203:    # Either class fits into the gap; with gaps first both score 0 there.
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && git checkout planner/preferences.py && grep -n "describe()\|\.describe\b" -r planner tests | head; grep -n "feasible schedule(s) found" README.md | head -3
```

stdout:

```
planner/cli.py:116:    print(f"#{item.rank} (score {item.score}) {item.describe()}")
```

stderr:

```
Updated 1 path from the index
```

**deepseek ran** `cd /repo && grep -n "prefer\|#1\|days on campus" README.md | head -20; grep -rn "describe()" tests | head` · exit code 0

stdout:

```
8:- **Preference-Based Ranking**: Rank feasible schedules by fewest days on campus, no early classes before a target time, and minimal gaps between classes.
```

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/cli.py'
s=open(p).read()
old='''def _print_ranked(item: RankedSchedule, total: int | None, complete: bool) -> None:
    print(f"#{item.rank} (score {item.score}) {item.describe()}")
'''
new='''#: How each preference metric is worded in the ranked listing.
_METRIC_LABELS = {
    "days": "day(s) on campus",
    "early": "early class(es)",
    "gaps": "min of gaps",
    "span": "min on campus",
}


def _describe_ranked(item: RankedSchedule, order: Sequence[str]) -> str:
    """Metrics in *priority* order, so the listing reads like the preference.

    No single "score" is printed: a scalar cannot express a lexicographic
    preference list, and showing one invited comparisons it did not support.
    """
    values = item.metrics.as_dict()
    names = list(order) or ["days", "early", "gaps", "span"]
    return ", ".join(f"{values[name]} {_METRIC_LABELS[name]}" for name in names)


def _print_ranked(item: RankedSchedule, total: int | None, complete: bool) -> None:
    print(f"#{item.rank} {_describe_ranked(item, item.order)}")
'''
assert old in s
s=s.replace(old,new)
open(p,'w').write(s)
EOF
grep -n "^from\|^import" planner/cli.py | head
```

stdout:

```
3:import argparse
4:import csv
5:import sys
6:from pathlib import Path
7:from typing import Sequence
9:from planner import export, preferences, ranking
10:from planner import show as show_module
11:from planner.preferences import RankedSchedule
12:from planner.conflicts import find_conflicts
13:from planner.csvio import load_sections
```

**deepseek ran** `cd /repo && grep -n "_print_ranked" planner/cli.py` · exit code 0

stdout:

```
135:def _print_ranked(item: RankedSchedule, total: int | None, complete: bool) -> None:
195:        _print_ranked(item, result.total, result.complete)
```

**deepseek ran** `cd /repo && sed -n 160,200p planner/cli.py` · exit code 0

<details><summary>output, 42 lines</summary>

stdout:

```
        print("schedule:")
        _print_schedule(choices)
        print(render([row for choice in choices for row in choice.meetings]), end="")
        _print_travel_warnings(args, choices)
        export.handle_plan_exports(args, choices)
        return 0
    result = ranking.search(
        sections,
        courses,
        order=order,
        not_before=not_before,
        limit=args.top if args.top is not None else 10,
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
            f"at least {result.total} feasible schedule(s) exist; showing the"
            f" best {how_many} found (not all were enumerated):"
        )
    for item in result.best:
        _print_ranked(item, result.total, result.complete)
    _print_travel_warnings(args, result.best[0].choices)
    export.handle_plan_exports(args, result.best[0].choices)
    return 0
```

</details>

**deepseek ran** `cd /repo && grep -n "item.order\|order=\|RankedSchedule(" planner/ranking.py planner/preferences.py | head -20` · exit code 0

stdout:

```
planner/ranking.py:140:        item = RankedSchedule(list(chosen), metrics, not_before=not_before)
planner/preferences.py:190:        RankedSchedule(choices, measure(
```

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='planner/cli.py'
s=open(p).read()
s=s.replace('''def _print_ranked(item: RankedSchedule, total: int | None, complete: bool) -> None:
    print(f"#{item.rank} {_describe_ranked(item, item.order)}")''','''def _print_ranked(item: RankedSchedule, order: Sequence[str]) -> None:
    print(f"#{item.rank} {_describe_ranked(item, order)}")''')
s=s.replace('''        _print_ranked(item, result.total, result.complete)''','''        _print_ranked(item, order)''')
open(p,'w').write(s)
EOF
python -m planner plan /tmp/sc.csv A B --top 4 --prefer days 2>&1 | grep "^#"; python -m planner plan examples/sections.csv CS101 --top 3 2>&1 | grep "^#"
```

stdout:

```
#1 1 day(s) on campus, 1 early class(es), 540 min of gaps, 660 min on campus
#2 2 day(s) on campus, 1 early class(es), 0 min of gaps, 120 min on campus
#3 2 day(s) on campus, 2 early class(es), 0 min of gaps, 120 min on campus
#3 2 day(s) on campus, 2 early class(es), 0 min of gaps, 120 min on campus
#1 2 day(s) on campus, 0 early class(es), 0 min of gaps, 180 min on campus
#2 3 day(s) on campus, 0 early class(es), 0 min of gaps, 180 min on campus
```

**deepseek ran** `cd /repo && grep -rn "score" tests/ planner/ README.md | grep -v "# no\|scored" | head` · exit code 0

stdout:

```
tests/test_ranking.py:203:    # Either class fits into the gap; with gaps first both score 0 there.
planner/cli.py:127:    No single "score" is printed: a scalar cannot express a lexicographic
planner/preferences.py:50:    """A feasible schedule together with its measured and weighted scores."""
planner/preferences.py:54:    score: int = 0
planner/preferences.py:86:    scores still sort deterministically), then the exact meetings as a last
planner/preferences.py:197:        item.score = weighted(item.metrics, order)
planner/ranking.py:141:        item.score = weighted(metrics, order)
planner/solver.py:200:        score = len(viable)
planner/solver.py:201:        if best is not None and score >= best[0]:
planner/solver.py:214:        best = (score, "; ".join(parts))
```

**deepseek ran** · exit code 0

```bash
cd /repo && sed -i 's/    """A feasible schedule together with its measured and weighted scores."""/    """A feasible schedule with its metrics and a rough ``score``.\n\n    ``score`` is only a derived convenience (see :func:`weighted`); the CLI\n    never shows it and ranking uses the lexicographic metric key.\n    """/' planner/preferences.py && sed -n 48,60p planner/preferences.py
```

<details><summary>output, 14 lines</summary>

stdout:

```
@dataclass
class RankedSchedule:
    """A feasible schedule with its metrics and a rough ``score``.

    ``score`` is only a derived convenience (see :func:`weighted`); the CLI
    never shows it and ranking uses the lexicographic metric key.
    """

    choices: list[Choice]
    metrics: Metrics
    score: int = 0
    rank: int = 0
    occurrence: int = 0  # how many equal-preference schedules were seen earlier
```

</details>

**deepseek ran** · exit code 0

```bash
cd /repo && cat >> tests/test_cli.py <<'EOF'


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

[... 54 more characters not shown ...]
```

stdout:

```
..................................                                       [100%]
34 passed in 1.66s
```

**deepseek ran** · exit code 0

```bash
cd /repo && cat >> tests/test_cli.py <<'EOF'


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
        assert first.index(labels[order]) == 3  # right after "#1 "
        for label in labels.values():
            assert label in first
EOF
python -m pytest -q tests/test_cli.py 2>&1|tail -3
```

stdout:

```
=========================== short test summary info ============================
FAILED tests/test_cli.py::test_ranked_listing_covers_every_metric_label - Ass...
1 failed, 34 passed in 1.75s
```

**deepseek ran** `cd /repo && python -m planner plan /tmp/sc.csv A --prefer early | head -3` · exit code 0

stdout:

```
2 feasible schedule(s) found; best 2:
#1 1 early class(es), 1 day(s) on campus, 0 min of gaps, 60 min on campus
    A 1
```

**deepseek ran** `cd /repo && python -m pytest -q tests/test_cli.py -k every_metric 2>&1 | grep -E "^E" | head -4` · exit code 0

stdout:

```
E           AssertionError: assert 5 == 3
E            +  where 5 = <built-in method index of str object at 0x785f6bb8ad30>('day(s) on campus')
E            +    where <built-in method index of str object at 0x785f6bb8ad30> = '#1 1 day(s) on campus, 1 early class(es), 0 min of gaps, 60 min on campus'.index
```

**deepseek ran** · exit code 0

```bash
cd /repo && python - <<'EOF'
p='tests/test_cli.py'
s=open(p).read()
s=s.replace('''        assert first.index(labels[order]) == 3  # right after "#1 "''','''        assert first.startswith("#1 " + labels[order])''')
open(p,'w').write(s)
EOF
python -m pytest -q tests/ 2>&1|tail -2; ./check.sh 2>&1|tail -3
```

stdout:

```
FAILED tests/test_cli.py::test_ranked_listing_covers_every_metric_label - Ass...
1 failed, 175 passed in 5.69s
=========================== short test summary info ============================
FAILED tests/test_cli.py::test_ranked_listing_covers_every_metric_label - Ass...
======================== 1 failed, 175 passed in 10.18s ========================
```

*15 model calls · 444,569 input tokens (440,704 cache read, 0 cache write) · 2,366 output tokens*

### gemini (worker) · 10:29:51

**gemini ran** `git status` · exit code 0

stdout:

```
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   planner/cli.py
	modified:   planner/preferences.py
	modified:   tests/test_cli.py

no changes added to commit (use "git add" and/or "git commit -a")
```

**gemini ran** `git diff planner/cli.py tests/test_cli.py` · exit code 0

<details><summary>output, 98 lines</summary>

stdout:

```
diff --git a/planner/cli.py b/planner/cli.py
index 06d1740..e2b639c 100644
--- a/planner/cli.py
+++ b/planner/cli.py
@@ -112,8 +112,28 @@ def _minutes(clock: str) -> int:
     return hour * 60 + minute
 
 
-def _print_ranked(item: RankedSchedule, total: int | None, complete: bool) -> None:
-    print(f"#{item.rank} (score {item.score}) {item.describe()}")
+#: How each preference metric is worded in the ranked listing.
+_METRIC_LABELS = {
+    "days": "day(s) on campus",
+    "early": "early class(es)",
+    "gaps": "min of gaps",
+    "span": "min on campus",
+}
+
+
+def _describe_ranked(item: RankedSchedule, order: Sequence[str]) -> str:
+    """Metrics in *priority* order, so the listing reads like the preference.
+
+    No single "score" is printed: a scalar cannot express a lexicographic
+    preference list, and showing one invited comparisons it did not support.
+    """
+    values = item.metrics.as_dict()
+    names = list(order) or ["days", "early", "gaps", "span"]
+    return ", ".join(f"{values[name]} {_METRIC_LABELS[name]}" for name in names)
+
+
+def _print_ranked(item: RankedSchedule, order: Sequence[str]) -> None:
+    print(f"#{item.rank} {_describe_ranked(item, order)}")
     _print_schedule(item.choices, indent="    ")
     print(render(
         [row for choice in item.choices for row in choice.meetings],
@@ -172,7 +192,7 @@ def cmd_plan(args: argparse.Namespace) -> int:
             f" best {how_many} found (not all were enumerated):"
         )
     for item in result.best:
-        _print_ranked(item, result.total, result.complete)
+        _print_ranked(item, order)
     _print_travel_warnings(args, result.best[0].choices)
     export.handle_plan_exports(args, result.best[0].choices)
     return 0
diff --git a/tests/test_cli.py b/tests/test_cli.py
index 2148565..ab0b176 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -325,3 +325,57 @@ def test_explicit_default_ranking_values_are_honoured(capsys, tmp_path):
     code, out, err = run(c
[... 574 bytes truncated ...]
t,end,location\n"
+        "A,1,Mon,08:00,09:00,R\n"
+        "A,2,Tue,08:00,09:00,R\n"
+        "B,1,Mon,18:00,19:00,R\n"
+        "B,2,Wed,08:00,09:00,R\n",
+        encoding="utf-8",
+    )
+    code, out, err = run(capsys, "plan", str(path), "A", "B", "--prefer", "days", "--top", "4")
+    assert code == 0, err
+    assert "score" not in out
+    lines = [line for line in out.splitlines() if line.startswith("#")]
+    assert lines, out
+    # Most significant (fewest campus days) is listed first on every line.
+    for line in lines:
+        assert line.index("day(s) on campus") < line.index("min on campus") or "min on campus" not in line
+    assert lines[0].startswith("#1 1 day(s) on campus")
+    # The gaps-first order rewords the same numbers in that order.
+    code, out, err = run(capsys, "plan", str(path), "A", "B", "--prefer", "gaps")
+    assert code == 0, err
+    first = [line for line in out.splitlines() if line.startswith("#")][0]
+    assert "min of gaps" in first
+    assert first.index("min of gaps") < first.index("day(s) on campus")
+
+
+def test_ranked_listing_covers_every_metric_label(capsys, tmp_path):
+    path = tmp_path / "sections.csv"
+    path.write_text(
+        "course,section,day,start,end,location\n"
+        "A,1,Mon,08:00,09:00,R\n"
+        "A,2,Tue,08:00,09:00,R\n",
+        encoding="utf-8",
+    )
+    for order in ("days", "early", "gaps", "span"):
+        code, out, err = run(capsys, "plan", str(path), "A", "--prefer", order)
+        assert code == 0, err
+        first = [line for line in out.splitlines() if line.startswith("#")][0]
+        labels = {
+            "days": "day(s) on campus",
+            "early": "early class(es)",
+            "gaps": "min of gaps",
+            "span": "min on campus",
+        }
+        # The chosen preference appears first, and all four metrics appear.
+        assert first.startswith("#1 " + labels[order])
+        for label in labels.values():
+            assert label in first
```

</details>

**[COMPACTED]** memory compacted: summarized messages 778-839

**gemini ran** `git diff planner/preferences.py` · exit code 0

<details><summary>output, 18 lines</summary>

stdout:

```
diff --git a/planner/preferences.py b/planner/preferences.py
index 30262b7..035b1ce 100644
--- a/planner/preferences.py
+++ b/planner/preferences.py
@@ -47,7 +47,11 @@ class Metrics:
 
 @dataclass
 class RankedSchedule:
-    """A feasible schedule together with its measured and weighted scores."""
+    """A feasible schedule with its metrics and a rough ``score``.
+
+    ``score`` is only a derived convenience (see :func:`weighted`); the CLI
+    never shows it and ranking uses the lexicographic metric key.
+    """
 
     choices: list[Choice]
     metrics: Metrics
```

</details>

*checked: read_task*

**gemini posted to chat:**

> Leaving working tree intact for DeepSeek to take task 22 and finish the score removal and metric priority ordering. Once task 22 is committed and tests pass, I will review, update CHANGELOG.md for v1.0.2, and tag the release.

**gemini said:**

> I have verified the working tree and left DeepSeek's in-progress changes for Task 22 untouched so DeepSeek can take the task on the board, finish the score removal and metric priority formatting, and commit. Once DeepSeek completes Task 22, I will review, run `./check.sh`, update `CHANGELOG.md`, and tag `v1.0.2`.

*7 model calls · 282,070 input tokens (207,620 cache read, 0 cache write) · 1,751 output tokens*

[Index](README.md) · [Previous round](round-035.md) · [Next round](round-037.md)
