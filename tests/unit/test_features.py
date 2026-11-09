import numpy as np
import pandas as pd
import pytest

from communitylens.forecasting.features import FEATURES, HORIZON, build_panel


def _one(prices):
    return prices[prices["ticker"] == "AAA"].reset_index(drop=True)


def test_features_do_not_depend_on_the_future(prices):
    """Modifier les prix futurs ne doit changer aucune feature passée."""
    base = _one(prices)
    cut = 500
    altered = base.copy()
    altered.loc[cut:, ["open", "high", "low", "close"]] *= 3.0
    altered.loc[cut:, "volume"] *= 7.0
    date = base.loc[cut - 1, "date"]
    left = build_panel(base).set_index("date").loc[date, FEATURES].astype(float)
    right = build_panel(altered).set_index("date").loc[date, FEATURES].astype(float)
    pd.testing.assert_series_equal(left, right)


def test_target_uses_only_the_next_horizon_days(prices):
    base = _one(prices)
    panel = build_panel(base).set_index("date")
    returns = np.log(base["close"]).diff()
    position = 300
    expected = np.log(returns.iloc[position + 1 : position + 1 + HORIZON].std())
    assert panel.loc[base.loc[position, "date"], "target"] == pytest.approx(expected)


def test_last_rows_have_no_label(prices):
    panel = build_panel(_one(prices))
    assert panel["target"].tail(HORIZON).isna().all()
    assert np.isnan(panel["next_up"].iloc[-1])
    assert panel["target"].iloc[:-HORIZON].notna().all()


def test_features_are_scale_invariant(prices):
    """Même dynamique, autre niveau de prix : mêmes features (défaut du modèle initial)."""
    base = _one(prices)
    scaled = base.copy()
    scaled[["open", "high", "low", "close"]] *= 25
    left = build_panel(base)[FEATURES].to_numpy()
    right = build_panel(scaled)[FEATURES].to_numpy()
    assert np.allclose(left, right, atol=1e-9)


def test_zero_volume_gives_no_infinite_value(prices):
    base = _one(prices)
    base.loc[600, "volume"] = 0.0
    panel = build_panel(base)
    assert np.isfinite(panel[FEATURES].to_numpy()).all()


def test_missing_column_is_refused(prices):
    with pytest.raises(ValueError, match="volume"):
        build_panel(prices.drop(columns="volume"))
