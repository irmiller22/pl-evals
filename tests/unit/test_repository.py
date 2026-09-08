import pytest

from app.football.repository import FootballRepository


def test_filters_and_perspective(repository):
    assert repository.count_matches("Alpha") == 4
    assert repository.count_matches("Alpha", venue="home") == 2
    assert repository.count_matches("Alpha", venue="away", result="loss") == 1
    assert repository.count_matches("Alpha", result="win") == 1
    assert repository.count_matches("Alpha", opponent="Beta") == 2
    assert repository.count_matches("Beta", result="win", opponent="Alpha") == 1
    assert repository.count_matches("Alpha", half_time_result="win", result="draw") == 1
    assert repository.count_matches("Alpha", venue="away", result="win") == 0


def test_record_and_average(repository):
    assert repository.team_record("Alpha") == {"played": 4, "wins": 1, "draws": 1, "losses": 2}
    assert repository.team_record("Alpha", "away") == {
        "played": 2,
        "wins": 0,
        "draws": 1,
        "losses": 1,
    }
    assert repository.average_goals("Alpha") == 1.0
    assert repository.average_goals("Beta", "home") == 3.0


def test_head_to_head(repository):
    rows = repository.head_to_head("Alpha", "Beta")
    assert [(row["home_goals"], row["away_goals"]) for row in rows] == [(2, 0), (3, 1)]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"team": "Unknown"},
        {"team": "United"},
        {"team": "Alpha", "venue": "neutral"},
        {"team": "Alpha", "result": "H"},
        {"team": "Alpha", "opponent": "Alpha"},
        {"team": "Alpha' OR 1=1 --"},
    ],
)
def test_invalid_queries_rejected(repository, kwargs):
    with pytest.raises(ValueError):
        repository.get_matches(**kwargs)


def test_real_season_aliases_and_fixture():
    repository = FootballRepository()
    assert repository.normalize("  Man Utd  ") == "Manchester United"
    assert repository.normalize("Manchester United FC") == "Manchester United"
    assert repository.normalize("Wolves") == "Wolverhampton Wanderers"
    assert repository.count_matches("Manchester United") == 38
    (opening,) = repository.get_matches("Manchester United", "home", opponent="Fulham")
    assert (opening["date"], opening["home_goals"], opening["away_goals"]) == (
        "2024-08-16",
        1,
        0,
    )
