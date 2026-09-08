import pytest

from app.football.tools import FootballTools


@pytest.mark.parametrize(
    "name,args,expected",
    [
        ("count_team_matches", {"team": "Alpha", "venue": "home", "result": "win"}, 1),
        ("count_team_matches", {"team": "Alpha", "venue": "away", "result": "win"}, 0),
        ("get_average_goals", {"team": "Beta", "venue": "home"}, 3.0),
        ("get_team_record", {"team": "Alpha"}, {"played": 4, "wins": 1, "draws": 1, "losses": 2}),
    ],
)
def test_tool_values_and_evidence(repository, name, args, expected):
    tools = FootballTools(repository)
    result = tools.execute(name, args)
    assert result.value == expected
    assert result == tools.execute(name, args)
    all_ids = {row["match_id"] for row in repository.get_matches(args["team"])}
    assert set(result.evidence) <= all_ids
    assert result.query_metadata["tool"] == name
    if expected == 0:
        assert result.evidence == []
    else:
        assert result.evidence


def test_head_to_head_shape(repository):
    result = FootballTools(repository).execute(
        "get_head_to_head",
        {
            "team_a": "Alpha",
            "team_b": "Beta",
        },
    )
    assert len(result.value) == 2
    assert [row["match_id"] for row in result.value] == result.evidence


@pytest.mark.parametrize(
    "name,args",
    [
        ("sql", {"query": "SELECT *"}),
        ("count_team_matches", {"team": "Alpha", "arbitrary": True}),
        ("get_head_to_head", {"team_a": "Alpha", "team_b": "Alpha"}),
        ("get_team_record", {"team": "Alpha", "venue": "neutral"}),
    ],
)
def test_invalid_tool_calls_rejected(repository, name, args):
    with pytest.raises(ValueError):
        FootballTools(repository).execute(name, args)
