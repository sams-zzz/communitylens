"""Explique l'écart entre erreur en log et QLIKE : le niveau moyen de chaque prévision."""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from communitylens.evaluation.forecast_eval import walk_forward_volatility
from communitylens.evaluation.metrics import diebold_mariano
from communitylens.forecasting.features import HORIZON, build_panel


def _losses(target: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    ratio = np.exp(2 * (target - prediction))
    return ratio - np.log(ratio) - 1


def main() -> None:
    """Affiche biais, QLIKE, test de Diebold-Mariano et effet d'un décalage de niveau."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prices", help="Fichier Parquet au format long")
    parser.add_argument("--output", default="results/qlike_diagnostic.json")
    args = parser.parse_args()
    out = walk_forward_volatility(build_panel(pd.read_parquet(args.prices)))
    target = out["target"].to_numpy()
    report: dict = {"models": {}}
    daily = {}
    for name in ("ridge", "har", "persistence"):
        prediction = out[name].to_numpy()
        losses = _losses(target, prediction)
        daily[name] = pd.Series(losses).groupby(out["date"].to_numpy()).mean().to_numpy()
        report["models"][name] = {
            "mean_error_log": float((target - prediction).mean()),
            "qlike": float(losses.mean()),
            "qlike_median": float(np.median(losses)),
            "share_underestimated": float((target > prediction).mean()),
        }
    report["qlike_ridge_vs_persistence"] = diebold_mariano(
        daily["ridge"], daily["persistence"], HORIZON - 1
    )
    ridge = out["ridge"].to_numpy()
    report["ridge_with_level_shift"] = {
        str(shift): {
            "qlike": float(_losses(target, ridge + shift).mean()),
            "mae": float(np.abs(target - ridge - shift).mean()),
        }
        for shift in (0.1, 0.2, 0.3)
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
