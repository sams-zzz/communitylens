"""Features stationnaires et cible de volatilité, sans aucune fuite du futur."""

from __future__ import annotations

import numpy as np
import pandas as pd

HORIZON = 5
FEATURES = [
    "log_vol_5",
    "log_vol_20",
    "log_vol_60",
    "log_abs_return",
    "log_range",
    "volume_change",
    "dist_ma20",
    "return_5",
]
FEATURE_LABELS = {
    "log_vol_5": "Volatilité récente (5 jours)",
    "log_vol_20": "Volatilité sur 20 jours",
    "log_vol_60": "Volatilité sur 60 jours",
    "log_abs_return": "Ampleur du dernier mouvement",
    "log_range": "Amplitude de la dernière séance",
    "volume_change": "Variation du volume",
    "dist_ma20": "Écart à la moyenne sur 20 jours",
    "return_5": "Rendement sur 5 jours",
}
REQUIRED_COLUMNS = {"date", "ticker", "open", "high", "low", "close", "volume"}
_EPSILON = 1e-4


def _one_ticker_features(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    close = frame["close"]
    returns = np.log(close).diff()
    volume = frame["volume"].where(frame["volume"] > 0)
    out = frame[["date", "ticker", "close"]].copy()
    for window in (5, 20, 60):
        out[f"log_vol_{window}"] = np.log(returns.rolling(window).std())
    out["log_abs_return"] = np.log(returns.abs() + _EPSILON)
    out["log_range"] = np.log(np.log(frame["high"] / frame["low"]) + _EPSILON)
    out["volume_change"] = np.log(volume).diff().clip(-2, 2)
    out["dist_ma20"] = close / close.rolling(20).mean() - 1
    out["return_5"] = close.pct_change(5)
    out["target"] = np.log(returns.shift(-horizon).rolling(horizon).std())
    out["next_up"] = (close.shift(-1) > close).astype("float").where(close.shift(-1).notna())
    return out.replace([np.inf, -np.inf], np.nan)


def build_panel(prices: pd.DataFrame, horizon: int = HORIZON) -> pd.DataFrame:
    """Construit le panel de features. La cible reste vide sur les derniers jours."""
    missing = REQUIRED_COLUMNS - set(prices.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes : {sorted(missing)}")
    ordered = prices.sort_values(["ticker", "date"])
    frames = [
        _one_ticker_features(group, horizon) for _, group in ordered.groupby("ticker", sort=True)
    ]
    panel = pd.concat(frames, ignore_index=True)
    return panel.dropna(subset=FEATURES).reset_index(drop=True)
