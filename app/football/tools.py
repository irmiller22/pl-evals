"""Constrained model tools with validated arguments and reproducible evidence."""

from pydantic import BaseModel

from app.football.repository import FootballRepository
from app.football.schema import CountArgs, HeadToHeadArgs, TeamArgs, ToolResult

TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "count_team_matches": CountArgs,
    "get_team_record": TeamArgs,
    "get_head_to_head": HeadToHeadArgs,
    "get_average_goals": TeamArgs,
}
DESCRIPTIONS = {
    "count_team_matches": "Count matches by team, venue, opponent, and full/half-time outcome.",
    "get_team_record": "Return played, wins, draws, and losses from a team's perspective.",
    "get_head_to_head": "Return both fixtures between two teams with scores and dates.",
    "get_average_goals": "Mean goals scored by the team per match, not conceded or match total.",
}


class FootballTools:
    def __init__(self, repository: FootballRepository):
        self.repository = repository

    def definitions(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": DESCRIPTIONS[name],
                "parameters": schema.model_json_schema(),
            }
            for name, schema in TOOL_SCHEMAS.items()
        ]

    def validate(self, name: str, arguments: dict) -> dict:
        if name not in TOOL_SCHEMAS:
            raise ValueError(f"Unknown tool: {name}")
        args = TOOL_SCHEMAS[name].model_validate(arguments).model_dump()
        for key in ("team", "opponent", "team_a", "team_b"):
            if args.get(key) is not None:
                args[key] = self.repository.normalize(args[key])
        if args.get("opponent") == args.get("team") and args.get("opponent") is not None:
            raise ValueError("Opponent must differ from team")
        if "team_a" in args and args["team_a"] == args["team_b"]:
            raise ValueError("Head-to-head requires two different teams")
        return args

    def execute(self, name: str, arguments: dict) -> ToolResult:
        args = self.validate(name, arguments)
        value: int | float | dict | list | None
        if name == "count_team_matches":
            matches = self.repository.get_matches(**args)
            value = len(matches)
        elif name == "get_team_record":
            matches = self.repository.get_matches(**args)
            value = self.repository.team_record(**args)
        elif name == "get_head_to_head":
            matches = self.repository.head_to_head(**args)
            value = [
                {
                    key: row[key]
                    for key in (
                        "match_id",
                        "date",
                        "home_team",
                        "away_team",
                        "home_goals",
                        "away_goals",
                    )
                }
                for row in matches
            ]
        else:
            matches = self.repository.get_matches(**args)
            value = self.repository.average_goals(**args)
        return ToolResult(
            value=value,
            evidence=[row["match_id"] for row in matches],
            query_metadata={"tool": name, **args},
        )
