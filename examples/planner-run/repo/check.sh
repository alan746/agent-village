#!/usr/bin/env bash
set -euo pipefail

# Ensure development dependencies are installed
if ! python3 -c "import pytest, pytest_cov, icalendar, hypothesis" &>/dev/null; then
    echo "Installing dev dependencies from requirements-dev.txt..."
    python3 -m pip install -q --user -r requirements-dev.txt
fi

echo "=== Running test suite with coverage ==="
python3 -m pytest -v --cov=planner --cov-fail-under=90 "$@"

# Run benchmark if present
for bench in benchmark.py benchmarks/benchmark.py tests/benchmark.py benchmarks/bench.py; do
    if [[ -f "$bench" ]]; then
        echo "=== Running benchmark ($bench) ==="
        python3 "$bench"
        break
    fi
done

echo "=== All checks passed! ==="
