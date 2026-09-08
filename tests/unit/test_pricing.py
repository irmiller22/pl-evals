from evals.pricing import Price, estimate_cost, price_for


def test_cost_and_exact_or_prefix_resolution():
    prices = {"claude-sonnet-": Price(3, 15), "claude-sonnet-5": Price(2, 10)}
    assert price_for("claude-sonnet-5", prices) == Price(2, 10)
    assert price_for("claude-sonnet-5-20260101", prices) == Price(2, 10)
    assert price_for("unknown", prices) is None
    assert estimate_cost(1000, 500, Price(2, 10)) == 0.007
    assert estimate_cost(None, 500, Price(2, 10)) is None
