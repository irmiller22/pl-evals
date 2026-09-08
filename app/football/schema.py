"""Validation for normalized match data and constrained football tool inputs."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.football.normalizer import slug

Venue = Literal["home", "away", "all"]
Result = Literal["win", "draw", "loss", "all"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Match(StrictModel):
    match_id: str
    date: date
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    half_time_home_goals: int = Field(ge=0)
    half_time_away_goals: int = Field(ge=0)
    result: Literal["H", "D", "A"]

    @model_validator(mode="after")
    def consistent(self) -> "Match":
        if self.home_team == self.away_team:
            raise ValueError("A team cannot play itself")
        expected = (
            "H"
            if self.home_goals > self.away_goals
            else "A"
            if self.home_goals < self.away_goals
            else "D"
        )
        if self.result != expected:
            raise ValueError("Result disagrees with full-time score")
        if (
            self.half_time_home_goals > self.home_goals
            or self.half_time_away_goals > self.away_goals
        ):
            raise ValueError("Half-time goals exceed full-time goals")
        expected_id = f"{self.date.isoformat()}_{slug(self.home_team)}_{slug(self.away_team)}"
        if self.match_id != expected_id:
            raise ValueError("Match ID disagrees with date and teams")
        return self


class TeamArgs(StrictModel):
    team: str = Field(min_length=1)
    venue: Venue = "all"


class CountArgs(TeamArgs):
    result: Result = "all"
    opponent: str | None = None
    half_time_result: Result = "all"


class HeadToHeadArgs(StrictModel):
    team_a: str = Field(min_length=1)
    team_b: str = Field(min_length=1)


class ToolResult(StrictModel):
    value: int | float | dict | list | None
    evidence: list[str]
    query_metadata: dict
