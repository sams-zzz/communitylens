"""Jeux de données synthétiques, à graine fixe."""

import numpy as np
import pandas as pd
import pytest

from communitylens.domain.models import Attribution, Fact, FactPack, Forecast, Passage


def make_prices(tickers=("AAA", "BBB"), days=700, seed=0) -> pd.DataFrame:
    """Prix avec volatilité persistante, pour que le modèle ait un signal à trouver."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2019-01-01", periods=days)
    frames = []
    for ticker in tickers:
        log_vol = np.empty(days)
        log_vol[0] = np.log(0.015)
        for index in range(1, days):
            log_vol[index] = 0.97 * log_vol[index - 1] + 0.03 * np.log(0.015) + rng.normal(0, 0.08)
        returns = rng.normal(0, 1, days) * np.exp(log_vol)
        close = 100 * np.exp(np.cumsum(returns))
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "open": close,
                    "high": close * (1 + np.abs(rng.normal(0, 0.006, days))),
                    "low": close * (1 - np.abs(rng.normal(0, 0.006, days))),
                    "close": close,
                    "volume": rng.integers(1_000_000, 5_000_000, days).astype(float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


@pytest.fixture(name="prices")
def prices_fixture() -> pd.DataFrame:
    """Deux titres sur 700 jours."""
    return make_prices()


@pytest.fixture(name="forecast")
def forecast_fixture() -> Forecast:
    """Une prévision type."""
    return Forecast(
        ticker="AAPL",
        as_of="2018-02-07",
        volatility_pct=23.6,
        low_pct=15.3,
        high_pct=36.3,
        recent_volatility_pct=28.1,
        usual_volatility_pct=20.2,
        coverage_60d_pct=86.7,
        last_close=159.54,
        change_5d_pct=-4.7,
        attributions=[Attribution(feature="log_range", label="Amplitude", effect_pct=18.2)],
        model_version="test",
    )


@pytest.fixture(name="pack")
def pack_fixture() -> FactPack:
    """Un contexte minimal pour le vérificateur."""
    return FactPack(
        ticker="AAPL",
        company="Apple",
        as_of="2018-02-07",
        facts=[
            Fact(id="F1", label="Volatilité", value=23.6),
            Fact(id="F2", label="Basse", value=15.3),
            Fact(id="F3", label="Haute", value=36.3),
        ],
        passages=[
            Passage(
                id="P1",
                source="forum",
                doc_type="community",
                published_at="2018-02-06",
                text="Rachat de 100 milliards annoncé bientôt.",
            )
        ],
    )
