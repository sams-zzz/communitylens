"""Intervalles conformes glissants, avec décalage pour respecter l'horizon de la cible."""

from __future__ import annotations

import math

import numpy as np


def conformal_quantile(past_abs_errors: np.ndarray, alpha: float) -> float:
    """Quantile conforme avec correction d'échantillon fini ; infini si trop peu de points."""
    errors = past_abs_errors[~np.isnan(past_abs_errors)]
    size = errors.size
    if size == 0:
        return math.inf
    rank = math.ceil((size + 1) * (1 - min(max(alpha, 0.0), 1.0)))
    if rank > size:
        return math.inf
    if rank <= 0:
        return 0.0
    return float(np.sort(errors)[rank - 1])


def rolling_intervals(errors: np.ndarray, alpha: float, window: int, lag: int) -> np.ndarray:
    """Calcule la demi-largeur à chaque date avec les erreurs déjà observables à cette date."""
    half_widths = np.full(errors.size, np.nan)
    for index in range(errors.size):
        end = index - lag + 1
        if end >= window:
            half_widths[index] = conformal_quantile(np.abs(errors[end - window : end]), alpha)
    return half_widths


def adaptive_intervals(
    errors: np.ndarray, alpha: float, window: int, lag: int, gamma: float = 0.01
) -> np.ndarray:
    """Variante ACI : le niveau s'ajuste selon les dépassements déjà observables."""
    half_widths = np.full(errors.size, np.nan)
    current_alpha = alpha
    for index in range(errors.size):
        end = index - lag + 1
        if end < window:
            continue
        if not np.isnan(half_widths[end - 1]):
            missed = abs(errors[end - 1]) > half_widths[end - 1]
            current_alpha += gamma * (alpha - float(missed))
        half_widths[index] = conformal_quantile(np.abs(errors[end - window : end]), current_alpha)
    return half_widths
