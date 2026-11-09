"""Modèle Ridge de volatilité, sérialisé en JSON pour éviter pickle."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from communitylens.forecasting.features import FEATURES


@dataclass
class VolatilityModel:
    """Régression linéaire régularisée ; chaque contribution est exacte."""

    intercept: float
    coefficients: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    features: tuple[str, ...] = tuple(FEATURES)

    @classmethod
    def fit(cls, x: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> "VolatilityModel":
        """Entraîne le modèle sur des features standardisées."""
        scaler = StandardScaler().fit(x)
        ridge = Ridge(alpha=alpha).fit(scaler.transform(x), y)
        return cls(float(ridge.intercept_), ridge.coef_, scaler.mean_, scaler.scale_)

    def contributions(self, x: np.ndarray) -> np.ndarray:
        """Renvoie la contribution de chaque feature, en log-volatilité."""
        return self.coefficients * (x - self.means) / self.scales

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Prévoit la log-volatilité."""
        return self.intercept + self.contributions(x).sum(axis=-1)

    def to_dict(self) -> dict:
        """Sérialise le modèle."""
        return {
            "intercept": self.intercept,
            "coefficients": self.coefficients.tolist(),
            "means": self.means.tolist(),
            "scales": self.scales.tolist(),
            "features": list(self.features),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "VolatilityModel":
        """Recharge un modèle sérialisé et contrôle l'ordre des features."""
        if list(payload["features"]) != FEATURES:
            raise ValueError("Features incompatibles avec cette version du code")
        return cls(
            float(payload["intercept"]),
            np.asarray(payload["coefficients"]),
            np.asarray(payload["means"]),
            np.asarray(payload["scales"]),
        )


def fit_har(x_har: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ajuste la baseline HAR par moindres carrés."""
    design = np.column_stack([np.ones(len(x_har)), x_har])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    return beta


def predict_har(beta: np.ndarray, x_har: np.ndarray) -> np.ndarray:
    """Prévoit avec la baseline HAR."""
    return beta[0] + x_har @ beta[1:]
