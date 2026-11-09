import pytest

from communitylens.forecasting.pipeline import run_forecast
from tests.conftest import make_prices


def test_forecast_is_published_with_consistent_interval(prices):
    run = run_forecast(prices, git_sha="abc")
    assert {item.ticker for item in run.forecasts} == {"AAA", "BBB"}
    for item in run.forecasts:
        assert item.low_pct < item.volatility_pct < item.high_pct
        assert 0 <= item.coverage_60d_pct <= 100
        assert len(item.attributions) == 3
    assert run.manifest["git_sha"] == "abc"
    assert run.manifest["model"]["features"]


def test_version_changes_when_data_changes(prices):
    other = prices.copy()
    other.loc[other.index[-1], "close"] *= 1.01
    assert run_forecast(prices).manifest["version"] != run_forecast(other).manifest["version"]


def test_history_shows_no_realized_value_on_recent_days(prices):
    history = run_forecast(prices).history["AAA"]
    assert history[-1]["realized"] is None
    assert history[0]["realized"] is not None
    assert all(row["low"] <= row["predicted"] <= row["high"] for row in history)


def test_short_history_ticker_is_skipped():
    long = make_prices(("AAA", "BBB"), days=700)
    short = make_prices(("NEW",), days=700, seed=9).tail(90)
    import pandas as pd

    run = run_forecast(pd.concat([long, short], ignore_index=True))
    assert "NEW" in run.skipped
    assert {item.ticker for item in run.forecasts} == {"AAA", "BBB"}


def test_too_little_data_is_refused():
    with pytest.raises(ValueError):
        run_forecast(make_prices(("AAA",), days=150))
