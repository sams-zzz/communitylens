"""Entraîne le modèle et produit prévisions, intervalles et historique d'affichage."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from communitylens.domain.models import Attribution, Forecast
from communitylens.forecasting.conformal import adaptive_intervals
from communitylens.forecasting.features import FEATURE_LABELS, FEATURES, HORIZON, build_panel
from communitylens.forecasting.model import VolatilityModel

ANNUALIZE = math.sqrt(252) * 100
CALIBRATION_DAYS = 250
RETRAIN_DAYS = 21
MIN_TRAIN_ROWS = 500
WINDOW = 60
COVERAGE_DAYS = 60
LEVEL = 0.8


def to_annual_pct(log_volatility: np.ndarray | float) -> np.ndarray | float:
    """Convertit une log-volatilité quotidienne en pourcentage annualisé."""
    return np.exp(log_volatility) * ANNUALIZE


@dataclass
class ForecastRun:
    """Résultat complet d'une exécution."""

    model: VolatilityModel
    manifest: dict
    forecasts: list[Forecast]
    history: dict[str, list[dict]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)


def _calibration_predictions(panel: pd.DataFrame) -> pd.DataFrame:
    """Prévoit les derniers jours hors échantillon, en réentraînant chaque mois."""
    dates = np.sort(panel["date"].unique())
    labelled = panel.dropna(subset=["target"])
    parts = []
    start = max(dates.size - CALIBRATION_DAYS, HORIZON + 1)
    for begin in range(start, dates.size, RETRAIN_DAYS):
        cutoff = dates[begin - HORIZON - 1]
        train = labelled[labelled["date"] <= cutoff]
        if len(train) < MIN_TRAIN_ROWS:
            continue
        model = VolatilityModel.fit(train[FEATURES].to_numpy(), train["target"].to_numpy())
        stop = dates[min(begin + RETRAIN_DAYS, dates.size) - 1]
        test = panel[panel["date"].between(dates[begin], stop)].copy()
        test["prediction"] = model.predict(test[FEATURES].to_numpy())
        parts.append(test)
    if not parts:
        raise ValueError("Historique insuffisant pour calibrer les intervalles")
    return pd.concat(parts, ignore_index=True)


def _ticker_forecast(
    group: pd.DataFrame, model: VolatilityModel, last_row: pd.Series, version: str
) -> tuple[Forecast | None, list[dict]]:
    errors = (group["target"] - group["prediction"]).to_numpy()
    half = adaptive_intervals(errors, round(1 - LEVEL, 2), WINDOW, HORIZON)
    valid = np.isfinite(half) & ~np.isnan(errors)
    if not np.isfinite(half[-1]) or valid.sum() < 20:
        return None, []
    recent = valid.nonzero()[0][-COVERAGE_DAYS:]
    coverage = float(np.mean(np.abs(errors[recent]) <= half[recent]))

    features = last_row[FEATURES].to_numpy(dtype=float)
    prediction = float(model.predict(features))
    effects = model.contributions(features)
    order = np.argsort(-np.abs(effects))[:3]
    attributions = [
        Attribution(
            feature=FEATURES[i],
            label=FEATURE_LABELS[FEATURES[i]],
            effect_pct=round(float(np.exp(effects[i]) - 1) * 100, 1),
        )
        for i in order
    ]
    forecast = Forecast(
        ticker=str(last_row["ticker"]),
        as_of=str(pd.Timestamp(last_row["date"]).date()),
        volatility_pct=round(float(to_annual_pct(prediction)), 1),
        low_pct=round(float(to_annual_pct(prediction - half[-1])), 1),
        high_pct=round(float(to_annual_pct(prediction + half[-1])), 1),
        level_pct=int(LEVEL * 100),
        horizon_days=HORIZON,
        recent_volatility_pct=round(float(to_annual_pct(last_row["log_vol_20"])), 1),
        usual_volatility_pct=round(float(to_annual_pct(last_row["log_vol_60"])), 1),
        coverage_60d_pct=round(coverage * 100, 1),
        last_close=round(float(last_row["close"]), 2),
        change_5d_pct=round(float(last_row["return_5"]) * 100, 1),
        attributions=attributions,
        model_version=version,
    )
    history = []
    for position in np.isfinite(half).nonzero()[0][-120:]:
        row = group.iloc[position]
        realized = row["target"]
        history.append(
            {
                "date": str(pd.Timestamp(row["date"]).date()),
                "close": round(float(row["close"]), 2),
                "predicted": round(float(to_annual_pct(row["prediction"])), 1),
                "low": round(float(to_annual_pct(row["prediction"] - half[position])), 1),
                "high": round(float(to_annual_pct(row["prediction"] + half[position])), 1),
                "realized": None if pd.isna(realized) else round(float(to_annual_pct(realized)), 1),
            }
        )
    return forecast, history


def run_forecast(prices: pd.DataFrame, git_sha: str = "unknown") -> ForecastRun:
    """Exécute le pipeline : calibration, entraînement final, prévisions par titre."""
    panel = build_panel(prices)
    labelled = panel.dropna(subset=["target"])
    model = VolatilityModel.fit(labelled[FEATURES].to_numpy(), labelled["target"].to_numpy())
    canonical = prices.sort_values(["ticker", "date"])[["ticker", "date", "close"]]
    digest = hashlib.sha256(canonical.to_csv(index=False).encode()).hexdigest()
    version = f"{pd.Timestamp(panel['date'].max()).date()}-{digest[:8]}"
    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_sha256": digest,
        "git_sha": git_sha,
        "trained_until": str(pd.Timestamp(labelled["date"].max()).date()),
        "rows": int(len(labelled)),
        "features": FEATURES,
        "model": json.loads(json.dumps(model.to_dict())),
    }
    calibration = _calibration_predictions(panel)
    run = ForecastRun(model=model, manifest=manifest, forecasts=[])
    last_date = panel["date"].max()
    for ticker, group in calibration.sort_values("date").groupby("ticker"):
        row = panel[(panel["ticker"] == ticker) & (panel["date"] == last_date)]
        forecast, history = (None, [])
        if not row.empty:
            forecast, history = _ticker_forecast(group, model, row.iloc[0], version)
        if forecast is None:
            run.skipped.append(str(ticker))
            continue
        run.forecasts.append(forecast)
        run.history[str(ticker)] = history
    return run
