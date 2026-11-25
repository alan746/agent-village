"""M2 benchmark: rank 40 courses x 5 sections in well under two seconds.

Builds the timetable from ``tests/make_bench.py`` (deterministic), runs the
real CLI ``planner plan ... --top 10`` on it two ways, and fails with a
non-zero exit code if any run takes 2 seconds or more.

Usage: ``python tests/benchmark.py [--json]``
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import make_bench  # noqa: E402  (needs the path tweak above)

BUDGET_SECONDS = 2.0
LIMIT = 10

CASES = {
    "default order": ["--top", str(LIMIT)],
    "days, gaps, span": [
        "--top", str(LIMIT), "--prefer", "days", "--prefer", "gaps", "--prefer", "span",
        "--not-before", "09:00",
    ],
}


def run_cli(data: Path, courses: list[str], options: list[str]) -> float:
    command = [sys.executable, "-m", "planner", "plan", str(data), *courses, *options]
    started = time.perf_counter()
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise SystemExit(
            "benchmark command failed:\n"
            + " ".join(command)
            + "\n"
            + completed.stderr
        )
    if not completed.stdout.strip():
        raise SystemExit("benchmark command printed nothing")
    return elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args()

    data = make_bench.write()
    courses = sorted({row[0] for row in make_bench.generate()})
    print(f"benchmark data: {data} ({len(courses)} courses x {make_bench.SECTIONS_PER_COURSE} sections)")

    results = {}
    failures = []
    for label, options in CASES.items():
        elapsed = run_cli(data, courses, options)
        results[label] = round(elapsed, 3)
        status = "ok" if elapsed < BUDGET_SECONDS else "TOO SLOW"
        print(f"  {label:<18} {elapsed:6.3f}s  (budget {BUDGET_SECONDS:.0f}s)  {status}")
        if elapsed >= BUDGET_SECONDS:
            failures.append(label)

    if args.json:
        print(json.dumps(results))
    if failures:
        print("benchmark FAILED for: " + ", ".join(failures))
        return 1
    print("benchmark passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
