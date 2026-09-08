from pathlib import Path

import pytest

from scripts.ingest_dataset import DATA, SOURCE, ingest, parse_source, validate_season


def test_snapshot_is_complete_and_reproducible(tmp_path: Path):
    output = tmp_path / "matches.csv"
    first = ingest(SOURCE, output)
    assert first["matches"] == 380
    assert output.read_bytes() == (DATA / "matches.csv").read_bytes()
    assert ingest(SOURCE, output) == first
    rows = parse_source(SOURCE.read_text())
    validate_season(rows)
    assert len({row.match_id for row in rows}) == 380
    assert min(row.date.isoformat() for row in rows) == "2024-08-16"
    assert max(row.date.isoformat() for row in rows) == "2025-05-25"


def test_pin_failure_preserves_existing_output(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("changed")
    output = tmp_path / "matches.csv"
    output.write_text("previous")
    with pytest.raises(ValueError, match="checksum"):
        ingest(source, output)
    assert output.read_text() == "previous"


@pytest.mark.parametrize(
    "line",
    [
        "Alpha FC v Beta FC 1-0",  # Missing half time is not assumed for nonzero scores.
        "Alpha FC v Beta FC 1-0 (2-0)",
        "Alpha FC v Alpha FC 0-0",
        "Alpha FC v Beta FC postponed",
    ],
)
def test_invalid_match_rejected(line):
    with pytest.raises(ValueError):
        parse_source("Sat Aug 17 2024\n" + line)


def test_zero_zero_half_time_is_derived():
    (row,) = parse_source("Sat Aug 17 2024\nAlpha FC v Beta FC 0-0")
    assert row.half_time_home_goals == row.half_time_away_goals == 0


def test_duplicate_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        parse_source("Sat Aug 17 2024\nAlpha FC v Beta FC 0-0\nAlpha FC v Beta FC 0-0")


def test_incomplete_season_rejected():
    with pytest.raises(ValueError, match="380"):
        validate_season(parse_source("Sat Aug 17 2024\nAlpha FC v Beta FC 0-0"))
