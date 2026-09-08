"""Normalize the pinned OpenFootball snapshot without network access by default."""

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Annotated

import httpx
import typer

from app.football.normalizer import canonical_name, slug
from app.football.schema import Match

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
REVISION = "0690446f794fde748ea4b994244def699c6a65b2"
SOURCE_URL = (
    f"https://raw.githubusercontent.com/openfootball/england/{REVISION}/2024-25/1-premierleague.txt"
)
SOURCE = DATA / "source" / "2024-25-premierleague.txt"
MONTHS = {
    name: i for i, name in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)
}
DATE_LINE = re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\w{3}) (\d{1,2})(?: (\d{4}))?")
MATCH_LINE = re.compile(
    r"(?:\d{1,2}:\d{2}\s+)?(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)"
    r"(?:\s+\((\d+)-(\d+)\))?"
)
app = typer.Typer(help="Normalize the pinned 2024/25 OpenFootball season.")


def parse_source(text: str) -> list[Match]:
    rows: list[Match] = []
    current_date: date | None = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("=", "#", "▪")):
            continue
        if match := DATE_LINE.fullmatch(line):
            month_name, day, explicit_year = match.groups()
            month = MONTHS[month_name]
            year = int(explicit_year) if explicit_year else (2024 if month >= 8 else 2025)
            current_date = date(year, month, int(day))
            continue
        match = MATCH_LINE.fullmatch(line)
        if match is None or current_date is None:
            raise ValueError(f"Unrecognized source line {line_number}: {line}")
        home, away, hg, ag, hhg, hag = match.groups()
        home, away = canonical_name(home), canonical_name(away)
        # A completed 0-0 necessarily had a 0-0 half-time score.
        if hhg is None:
            if (hg, ag) != ("0", "0"):
                raise ValueError(f"Missing half-time score on line {line_number}")
            hhg, hag = "0", "0"
        rows.append(
            Match(
                match_id=f"{current_date.isoformat()}_{slug(home)}_{slug(away)}",
                date=current_date,
                home_team=home,
                away_team=away,
                home_goals=int(hg),
                away_goals=int(ag),
                half_time_home_goals=int(hhg),
                half_time_away_goals=int(hag),
                result="H" if int(hg) > int(ag) else "A" if int(hg) < int(ag) else "D",
            )
        )
    if not rows:
        raise ValueError("Source contains no matches")
    if len({row.match_id for row in rows}) != len(rows):
        raise ValueError("Duplicate match IDs")
    return sorted(rows, key=lambda row: (row.date, row.match_id))


def validate_season(rows: list[Match]) -> None:
    teams = {row.home_team for row in rows} | {row.away_team for row in rows}
    pairs = Counter((row.home_team, row.away_team) for row in rows)
    if len(rows) != 380 or len(teams) != 20:
        raise ValueError("Expected 380 matches and 20 teams in a complete season")
    if any(pairs[(home, away)] != 1 for home in teams for away in teams if home != away):
        raise ValueError("Each team must host every other team exactly once")
    if any(not date(2024, 8, 1) <= row.date <= date(2025, 5, 31) for row in rows):
        raise ValueError("Match date is outside the selected 2024/25 season")


def ingest(source: Path, output: Path, *, verify_pin: bool = True) -> dict:
    raw = source.read_bytes()
    manifest = json.loads((DATA / "source" / "manifest.json").read_text())
    source_hash = hashlib.sha256(raw).hexdigest()
    if verify_pin and source_hash != manifest["sha256"]:
        raise ValueError("Source checksum does not match the pinned snapshot")
    rows = parse_source(raw.decode("utf-8"))
    validate_season(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Validate before writing, then replace atomically to preserve a prior valid dataset.
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(Match.model_fields), lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(row.model_dump(mode="json") for row in rows)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "matches": len(rows),
        "season": "2024/25",
        "source_sha256": source_hash,
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


@app.command()
def main(
    output: Annotated[Path, typer.Option(help="Normalized CSV destination")] = DATA / "matches.csv",
    download: Annotated[bool, typer.Option(help="Re-download the pinned snapshot")] = False,
) -> None:
    if download:
        response = httpx.get(SOURCE_URL, timeout=30, follow_redirects=True)
        response.raise_for_status()
        manifest = json.loads((DATA / "source" / "manifest.json").read_text())
        if hashlib.sha256(response.content).hexdigest() != manifest["sha256"]:
            raise ValueError("Downloaded source checksum mismatch")
        SOURCE.write_bytes(response.content)
    typer.echo(json.dumps(ingest(SOURCE, output), indent=2))


if __name__ == "__main__":
    app()
