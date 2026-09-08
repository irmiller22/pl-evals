"""Read-only, parameterized DuckDB queries over a validated match snapshot."""

import csv
from pathlib import Path

import duckdb

from app.football.normalizer import normalize_team
from app.football.schema import CountArgs, Match, Result, Venue

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data" / "matches.csv"


class FootballRepository:
    def __init__(self, path: Path = DEFAULT_DATA):
        self.path = path
        with path.open(encoding="utf-8", newline="") as handle:
            rows = [Match.model_validate(row) for row in csv.DictReader(handle)]
        if not rows or len({row.match_id for row in rows}) != len(rows):
            raise ValueError("Dataset must be nonempty with unique match IDs")
        self.teams = {row.home_team for row in rows} | {row.away_team for row in rows}

    def normalize(self, team: str) -> str:
        return normalize_team(team, self.teams)

    def _query(self, where: str, parameters: list) -> list[dict]:
        # Each query owns its connection, allowing concurrent in-process requests.
        with duckdb.connect(":memory:") as connection:
            cursor = connection.execute(
                f"SELECT * FROM read_csv(?, header=true) WHERE {where} ORDER BY date, match_id",
                [str(self.path), *parameters],
            )
            columns = [column[0] for column in cursor.description]
            return [
                Match.model_validate(dict(zip(columns, row, strict=True))).model_dump(mode="json")
                for row in cursor.fetchall()
            ]

    def get_matches(
        self,
        team: str,
        venue: Venue = "all",
        result: Result = "all",
        opponent: str | None = None,
        half_time_result: Result = "all",
    ) -> list[dict]:
        args = CountArgs(
            team=team,
            venue=venue,
            result=result,
            opponent=opponent,
            half_time_result=half_time_result,
        )
        team = self.normalize(args.team)
        clauses = ["(home_team = ? OR away_team = ?)"]
        parameters: list = [team, team]
        if venue != "all":
            clauses.append(f"{venue}_team = ?")
            parameters.append(team)
        if opponent is not None:
            opponent = self.normalize(opponent)
            if opponent == team:
                raise ValueError("Opponent must differ from team")
            clauses.append("(home_team = ? OR away_team = ?)")
            parameters.extend([opponent, opponent])
        for outcome, prefix in ((result, ""), (half_time_result, "half_time_")):
            if outcome != "all":
                operator = {"win": ">", "draw": "=", "loss": "<"}[outcome]
                clauses.append(
                    f"((home_team = ? AND {prefix}home_goals {operator} {prefix}away_goals)"
                    f" OR (away_team = ? AND {prefix}away_goals {operator} {prefix}home_goals))"
                )
                parameters.extend([team, team])
        return self._query(" AND ".join(clauses), parameters)

    def count_matches(
        self,
        team: str,
        venue: Venue = "all",
        result: Result = "all",
        opponent: str | None = None,
        half_time_result: Result = "all",
    ) -> int:
        return len(self.get_matches(team, venue, result, opponent, half_time_result))

    def team_record(self, team: str, venue: Venue = "all") -> dict[str, int]:
        team = self.normalize(team)
        matches = self.get_matches(team, venue)
        wins = draws = losses = 0
        for row in matches:
            own, other = (
                (row["home_goals"], row["away_goals"])
                if row["home_team"] == team
                else (row["away_goals"], row["home_goals"])
            )
            wins += own > other
            draws += own == other
            losses += own < other
        return {"played": len(matches), "wins": wins, "draws": draws, "losses": losses}

    def head_to_head(self, team_a: str, team_b: str) -> list[dict]:
        return self.get_matches(team_a, opponent=team_b)

    def average_goals(self, team: str, venue: Venue = "all") -> float | None:
        """Goals scored by the requested team per match; None for an empty selection."""
        team = self.normalize(team)
        matches = self.get_matches(team, venue)
        if not matches:
            return None
        return sum(
            row["home_goals"] if row["home_team"] == team else row["away_goals"] for row in matches
        ) / len(matches)
