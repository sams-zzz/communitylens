"""Évaluation walk-forward multi-titres : volatilité, intervalles et contre-preuve de direction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

from communitylens.evaluation.metrics import brier, diebold_mariano, mae, qlike, r2_oos
from communitylens.forecasting.conformal import adaptive_intervals, rolling_intervals
from communitylens.forecasting.features import FEATURES, HORIZON, build_panel
from communitylens.forecasting.model import VolatilityModel, fit_har, predict_har

HAR_COLUMNS = ["log_vol_5", "log_vol_20", "log_vol_60"]
MIN_TRAIN_DAYS = 504
STEP_DAYS = 21


def _xgb_regressor() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42
    )


def _xgb_classifier() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05, random_state=42, eval_metric="logloss"
    )


def _folds(dates: np.ndarray, embargo: int):
    for start in range(MIN_TRAIN_DAYS, dates.size, STEP_DAYS):
        yield dates[start - embargo - 1], dates[start], dates[
            min(start + STEP_DAYS, dates.size) - 1
        ]


def walk_forward_volatility(panel: pd.DataFrame) -> pd.DataFrame:
    """Prévoit hors échantillon ; l'embargo retire les cibles qui chevauchent le test."""
    labelled = panel.dropna(subset=["target"])
    dates = np.sort(labelled["date"].unique())
    parts = []
    for train_end, test_start, test_end in _folds(dates, HORIZON):
        train = labelled[labelled["date"] <= train_end]
        test = labelled[labelled["date"].between(test_start, test_end)].copy()
        x_train, y_train = train[FEATURES].to_numpy(), train["target"].to_numpy()
        x_test = test[FEATURES].to_numpy()
        test["ridge"] = VolatilityModel.fit(x_train, y_train).predict(x_test)
        beta = fit_har(train[HAR_COLUMNS].to_numpy(), y_train)
        test["har"] = predict_har(beta, test[HAR_COLUMNS].to_numpy())
        test["xgboost"] = _xgb_regressor().fit(x_train, y_train).predict(x_test)
        means = train.groupby("ticker")["target"].mean()
        test["historical_mean"] = test["ticker"].map(means).fillna(y_train.mean())
        test["persistence"] = test["log_vol_20"]
        parts.append(test)
    return pd.concat(parts, ignore_index=True)


def score_volatility(out: pd.DataFrame) -> dict:
    """Compare tous les modèles et teste Ridge contre chaque autre."""
    y_true = out["target"].to_numpy()
    reference = out["historical_mean"].to_numpy()
    names = ["ridge", "xgboost", "har", "persistence", "historical_mean"]
    scores: dict = {"models": {}, "versus_ridge": {}, "tickers_won": {}}
    for name in names:
        pred = out[name].to_numpy()
        scores["models"][name] = {
            "mae": mae(y_true, pred),
            "qlike": qlike(y_true, pred),
            "r2_vs_historical_mean": r2_oos(y_true, pred, reference),
            "correlation": float(np.corrcoef(y_true, pred)[0, 1]),
        }
    ridge_loss = (out["target"] - out["ridge"]) ** 2
    daily_ridge = ridge_loss.groupby(out["date"]).mean().to_numpy()
    for name in names[1:]:
        loss = (out["target"] - out[name]) ** 2
        daily = loss.groupby(out["date"]).mean().to_numpy()
        scores["versus_ridge"][name] = diebold_mariano(daily_ridge, daily, HORIZON - 1)
        by_ticker = pd.DataFrame({"ridge": ridge_loss, "other": loss, "ticker": out["ticker"]})
        means = by_ticker.groupby("ticker")[["ridge", "other"]].mean()
        scores["tickers_won"][name] = int((means["ridge"] < means["other"]).sum())
    return scores


def score_intervals(out: pd.DataFrame, window: int = 60) -> dict:
    """Mesure la couverture réelle, globale et par titre, des deux méthodes."""
    results: dict = {}
    methods = {"rolling": rolling_intervals, "adaptive": adaptive_intervals}
    for target_coverage in (0.8, 0.9):
        alpha = round(1 - target_coverage, 2)
        for method_name, method in methods.items():
            covered, widths, per_ticker = [], [], {}
            for ticker, group in out.sort_values("date").groupby("ticker"):
                errors = (group["target"] - group["ridge"]).to_numpy()
                half = method(errors, alpha, window, HORIZON)
                mask = ~np.isnan(half) & np.isfinite(half)
                if not mask.any():
                    continue
                hit = np.abs(errors[mask]) <= half[mask]
                covered.append(hit)
                widths.append(half[mask])
                per_ticker[ticker] = float(hit.mean())
            hits, all_widths = np.concatenate(covered), np.concatenate(widths)
            values = np.array(list(per_ticker.values()))
            results[f"{method_name}_{int(target_coverage * 100)}"] = {
                "target": target_coverage,
                "coverage": float(hits.mean()),
                "points": int(hits.size),
                "mean_half_width_log": float(all_widths.mean()),
                "ticker_coverage_min": float(values.min()),
                "ticker_coverage_max": float(values.max()),
                "tickers_measured": int(values.size),
            }
    return results


def _confidence_label(probability: np.ndarray) -> np.ndarray:
    return np.select(
        [(probability > 0.65) | (probability < 0.35), (probability > 0.55) | (probability < 0.45)],
        ["elevee", "moyenne"],
        "faible",
    )


def evaluate_direction(panel: pd.DataFrame) -> dict:
    """Contre-preuve : le classifieur initial, évalué sur les mêmes titres et la même période."""
    labelled = panel.dropna(subset=["next_up"])
    dates = np.sort(labelled["date"].unique())
    parts = []
    for train_end, test_start, test_end in _folds(dates, 1):
        train = labelled[labelled["date"] <= train_end]
        test = labelled[labelled["date"].between(test_start, test_end)].copy()
        x_train, y_train = train[FEATURES].to_numpy(), train["next_up"].to_numpy()
        logistic = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=500))
        test["logistic"] = logistic.fit(x_train, y_train).predict_proba(test[FEATURES].to_numpy())[
            :, 1
        ]
        test["xgboost"] = (
            _xgb_classifier().fit(x_train, y_train).predict_proba(test[FEATURES].to_numpy())[:, 1]
        )
        test["constant"] = y_train.mean()
        parts.append(test)
    out = pd.concat(parts, ignore_index=True)
    y_true = out["next_up"].to_numpy()
    results: dict = {
        "points": int(y_true.size),
        "always_up_accuracy": float(y_true.mean()),
        "constant_brier": brier(y_true, out["constant"].to_numpy()),
    }
    for name in ("logistic", "xgboost"):
        probability = out[name].to_numpy()
        hits = (probability > 0.5) == (y_true == 1)
        labels = _confidence_label(probability)
        results[name] = {
            "accuracy": float(hits.mean()),
            "auc": float(roc_auc_score(y_true, probability)),
            "brier": brier(y_true, probability),
            "share_high_confidence": float((labels == "elevee").mean()),
            "accuracy_high_confidence": (
                float(hits[labels == "elevee"].mean()) if (labels == "elevee").any() else None
            ),
        }
    return results


def run(prices: pd.DataFrame) -> dict:
    """Lance l'évaluation complète."""
    panel = build_panel(prices)
    out = walk_forward_volatility(panel)
    return {
        "dataset": {
            "tickers": int(prices["ticker"].nunique()),
            "start": str(pd.Timestamp(prices["date"].min()).date()),
            "end": str(pd.Timestamp(prices["date"].max()).date()),
            "out_of_sample_points": int(len(out)),
            "out_of_sample_start": str(pd.Timestamp(out["date"].min()).date()),
            "horizon_days": HORIZON,
        },
        "volatility": score_volatility(out),
        "intervals": score_intervals(out),
        "direction": evaluate_direction(panel),
    }


def main() -> None:
    """Point d'entrée en ligne de commande."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prices", help="Fichier Parquet ou CSV au format long")
    parser.add_argument("--output", default="results/forecast_eval.json")
    args = parser.parse_args()
    path = Path(args.prices)
    prices = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    prices["date"] = pd.to_datetime(prices["date"])
    results = run(prices)
    Path(args.output).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
