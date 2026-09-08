from app.football.repository import FootballRepository
from scripts.generate_eval_cases import generate


def test_generated_suites_have_expected_sizes_and_status(repository):
    datasets = generate(FootballRepository())
    assert len(datasets["smoke"]) == 10
    assert len(datasets["golden"]) == 60
    assert len(datasets["unsupported"]) == 10
    assert len(datasets["adversarial"]) == 10
    assert all(case["expected"]["status"] == "answered" for case in datasets["golden"])
    assert all(case["expected"]["status"] == "unsupported" for case in datasets["unsupported"])
    assert all(case["expected"]["status"] == "answered" for case in datasets["adversarial"])


def test_generation_is_deterministic(repository):
    real = FootballRepository()
    assert generate(real) == generate(real)
