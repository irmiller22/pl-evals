import pytest
from pydantic import ValidationError

from app.agent.types import FinalAnswer


@pytest.mark.parametrize(
    "structured",
    [
        {"status": "answered", "kind": "count", "value": 0},
        {"status": "answered", "kind": "average", "value": 1.25},
        {
            "status": "answered",
            "kind": "record",
            "value": {"played": 3, "wins": 1, "draws": 1, "losses": 1},
        },
        {
            "status": "answered",
            "kind": "comparison",
            "value": {
                "metric": "wins",
                "items": [{"label": "A", "value": 2}, {"label": "B", "value": 2}],
                "winner_labels": ["A", "B"],
            },
        },
        {"status": "answered", "kind": "head_to_head", "value": []},
        {"status": "answered", "kind": "exact", "value": True},
        {"status": "unsupported", "reason": "Player data unavailable"},
    ],
)
def test_answer_variants_round_trip(structured):
    answer = FinalAnswer(answer="Answer", structured_answer=structured)
    assert FinalAnswer.model_validate_json(answer.model_dump_json()) == answer


@pytest.mark.parametrize(
    "structured",
    [
        {"status": "answered", "kind": "count", "value": True},
        {"status": "answered", "kind": "count", "value": -1},
        {"status": "answered", "kind": "count", "value": "3"},
        {"status": "answered", "kind": "average", "value": True},
        {"status": "answered", "kind": "average", "value": float("nan")},
        {"status": "answered", "kind": "average", "value": float("inf")},
        {
            "status": "answered",
            "kind": "record",
            "value": {"played": 4, "wins": 1, "draws": 1, "losses": 1},
        },
        {
            "status": "answered",
            "kind": "comparison",
            "value": {
                "metric": "wins",
                "items": [{"label": "A", "value": 2}, {"label": "B", "value": 2}],
                "winner_labels": ["A"],
            },
        },
        {
            "status": "answered",
            "kind": "comparison",
            "value": {
                "metric": "wins",
                "items": [{"label": "A", "value": 2}, {"label": "A", "value": 2}],
                "winner_labels": ["A"],
            },
        },
        {"status": "unsupported", "reason": " "},
        {"status": "unsupported", "reason": "Missing", "value": 3},
        {"status": "answered", "kind": "count", "value": 3, "reason": "Missing"},
    ],
)
def test_invalid_answers_rejected(structured):
    with pytest.raises(ValidationError):
        FinalAnswer(answer="Answer", structured_answer=structured)
