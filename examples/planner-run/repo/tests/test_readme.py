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
