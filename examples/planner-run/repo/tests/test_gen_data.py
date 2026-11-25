"""Tests for the synthetic data generator."""

import pytest
from pathlib import Path

from planner.csvio import load_sections
from planner.model import PlannerError
from tests.gen_data import (
    MUTATION_TYPES,
    corrupt_csv,
    generate_csv,
    generate_sections,
    write_sections_csv,
)


def test_generate_sections():
    rows = generate_sections(num_courses=5, sections_per_course=3, seed=42)
    assert len(rows) == 15
    for r in rows:
        assert "course" in r
        assert "section" in r
        assert "day" in r
        assert "start" in r
        assert "end" in r
        assert "location" in r


def test_generate_and_load_sections(tmp_path: Path):
    out_file = tmp_path / "test_sections.csv"
    write_sections_csv(out_file, num_courses=10, sections_per_course=2, seed=123)
    sections = load_sections(out_file)
    assert len(sections) == 20
    courses = {s.course for s in sections}
    assert len(courses) == 10


def test_corrupt_csv_mutations(tmp_path: Path):
    base_csv = generate_csv(num_courses=4, sections_per_course=2, seed=99)
    for mutation in MUTATION_TYPES:
        corrupted = corrupt_csv(base_csv, mutation_type=mutation, seed=99)
        test_file = tmp_path / f"corrupt_{mutation}.csv"
        if isinstance(corrupted, bytes):
            test_file.write_bytes(corrupted)
        else:
            test_file.write_text(corrupted, encoding="utf-8")

        # Loading corrupted CSV must raise PlannerError
        with pytest.raises(PlannerError):
            load_sections(test_file)
