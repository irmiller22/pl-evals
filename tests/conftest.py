import csv
from pathlib import Path

import pytest

from app.football.repository import FootballRepository
from app.football.schema import Match
from scripts.ingest_dataset import parse_source

# Synthetic matches, deliberately independent of the real-season answers.
FIXTURE = """= Fixture
Sat Aug 17 2024
Alpha FC v Beta FC 2-0 (1-0)
Sun Aug 18
Gamma FC v Alpha FC 1-1 (0-1)
Mon Aug 19
Beta FC v Alpha FC 3-1 (2-0)
Tue Aug 20
Alpha FC v Gamma FC 0-1 (0-0)
"""


@pytest.fixture
def repository(tmp_path: Path) -> FootballRepository:
    path = tmp_path / "matches.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(Match.model_fields))
        writer.writeheader()
        writer.writerows(row.model_dump(mode="json") for row in parse_source(FIXTURE))
    return FootballRepository(path)
