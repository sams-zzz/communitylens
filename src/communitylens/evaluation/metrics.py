"""Métriques de prévision de volatilité et de calibration."""

from __future__ import annotations

import math

import numpy as np


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Erreur absolue moyenne, en log-volatilité."""
    return float(np.mean(np.abs(y_true - y_pred)))


def qlike(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Perte QLIKE sur les variances, robuste au bruit de la volatilité réalisée."""
    ratio = np.exp(2 * (y_true - y_pred))
    return float(np.mean(ratio - np.log(ratio) - 1))


def r2_oos(y_true: np.ndarray, y_pred: np.ndarray, y_reference: np.ndarray) -> float:
    """R² hors échantillon par rapport à une prévision de référence."""
    return float(1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_reference) ** 2))


def diebold_mariano(loss_a: np.ndarray, loss_b: np.ndarray, lag: int) -> dict:
    """Test bilatéral avec variance de Newey-West ; une statistique négative favorise A."""
    diff = loss_a - loss_b
    size = diff.size
    centered = diff - diff.mean()
    variance = float(centered @ centered) / size
    for shift in range(1, lag + 1):
        weight = 1 - shift / (lag + 1)
        variance += 2 * weight * float(centered[shift:] @ centered[:-shift]) / size
    statistic = float(diff.mean() / math.sqrt(variance / size))
    p_value = math.erfc(abs(statistic) / math.sqrt(2))
    return {"statistic": statistic, "p_value": p_value}


def brier(y_true: np.ndarray, probability: np.ndarray) -> float:
    """Score de Brier."""
    return float(np.mean((probability - y_true) ** 2))
