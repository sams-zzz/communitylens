import numpy as np
import pytest

from communitylens.evaluation import metrics
from communitylens.forecasting.conformal import (
    adaptive_intervals,
    conformal_quantile,
    rolling_intervals,
)
from communitylens.forecasting.features import FEATURES
from communitylens.forecasting.model import VolatilityModel, fit_har, predict_har


def _data(rows=400):
    rng = np.random.default_rng(1)
    x = rng.normal(size=(rows, len(FEATURES)))
    y = 2.0 * x[:, 0] - x[:, 1] + 0.1 * rng.normal(size=rows)
    return x, y


def test_contributions_sum_to_the_prediction():
    x, y = _data()
    model = VolatilityModel.fit(x, y)
    assert model.predict(x[0]) == pytest.approx(model.intercept + model.contributions(x[0]).sum())


def test_model_round_trip_through_json():
    x, y = _data()
    model = VolatilityModel.fit(x, y)
    restored = VolatilityModel.from_dict(model.to_dict())
    assert np.allclose(model.predict(x), restored.predict(x))


def test_incompatible_features_are_refused():
    x, y = _data()
    payload = VolatilityModel.fit(x, y).to_dict()
    payload["features"] = ["autre"]
    with pytest.raises(ValueError):
        VolatilityModel.from_dict(payload)


def test_har_recovers_a_linear_relation():
    x = np.random.default_rng(2).normal(size=(200, 3))
    y = 1.0 + x @ np.array([0.5, 0.2, 0.1])
    beta = fit_har(x, y)
    assert np.allclose(predict_har(beta, x), y)


def test_quantile_applies_finite_sample_correction():
    errors = np.arange(1.0, 10.0)
    assert conformal_quantile(errors, 0.2) == 8.0
    assert conformal_quantile(errors, 0.01) == np.inf
    assert conformal_quantile(np.array([]), 0.2) == np.inf
    assert conformal_quantile(errors, 1.0) == 0.0


def test_interval_never_uses_unobservable_errors():
    """Une erreur géante dans les 5 derniers jours ne doit pas modifier l'intervalle du jour."""
    errors = np.random.default_rng(3).normal(size=100)
    base = rolling_intervals(errors, 0.2, 60, 5)
    altered = errors.copy()
    altered[-5:] = 1000.0
    assert rolling_intervals(altered, 0.2, 60, 5)[-1] == base[-1]


@pytest.mark.parametrize("method", [rolling_intervals, adaptive_intervals])
def test_coverage_is_close_to_target_on_stationary_errors(method):
    errors = np.random.default_rng(4).normal(size=4000)
    half = method(errors, 0.2, 60, 5)
    mask = ~np.isnan(half)
    assert np.mean(np.abs(errors[mask]) <= half[mask]) == pytest.approx(0.8, abs=0.03)


def test_adaptive_widens_after_a_regime_change():
    rng = np.random.default_rng(5)
    errors = np.concatenate([rng.normal(0, 1, 300), rng.normal(0, 4, 300)])
    half = adaptive_intervals(errors, 0.2, 60, 5)
    assert np.nanmean(half[-100:]) > 2 * np.nanmean(half[100:300])


def test_qlike_is_zero_for_a_perfect_forecast():
    y = np.array([-4.0, -3.5])
    assert metrics.qlike(y, y) == pytest.approx(0.0)
    assert metrics.mae(y, y) == 0.0


def test_r2_against_reference():
    y = np.array([1.0, 2.0, 3.0])
    assert metrics.r2_oos(y, y, np.zeros(3)) == 1.0
    assert metrics.r2_oos(y, np.zeros(3), np.zeros(3)) == 0.0


def test_diebold_mariano_detects_a_better_forecast():
    rng = np.random.default_rng(6)
    worse = rng.normal(2, 0.5, 500)
    better = rng.normal(1, 0.5, 500)
    result = metrics.diebold_mariano(better, worse, 4)
    assert result["statistic"] < 0 and result["p_value"] < 0.01


def test_brier():
    assert metrics.brier(np.array([1.0, 0.0]), np.array([1.0, 0.0])) == 0.0
