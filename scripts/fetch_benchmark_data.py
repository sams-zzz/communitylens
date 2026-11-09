"""Télécharge le jeu public de référence et garde les 30 titres du Dow Jones de février 2018."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

URL = "https://raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv"
DOW_30 = (
    "AAPL AXP BA CAT CSCO CVX DIS DWDP GE GS HD IBM INTC JNJ JPM KO MCD MMM MRK MSFT "
    "NKE PFE PG TRV UNH UTX V VZ WMT XOM"
).split()


def main() -> None:
    """Écrit un fichier Parquet au format long."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=URL)
    parser.add_argument("--output", default="data/benchmark_dow30.parquet")
    args = parser.parse_args()
    frame = pd.read_csv(args.source)
    frame = frame.rename(columns={"Name": "ticker", "Date": "date"})
    frame.columns = [column.lower() for column in frame.columns]
    frame["date"] = pd.to_datetime(frame["date"])
    selected = frame[frame["ticker"].isin(DOW_30)].dropna()
    missing = sorted(set(DOW_30) - set(selected["ticker"]))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    selected.to_parquet(args.output, index=False)
    print(f"{selected['ticker'].nunique()} titres, {len(selected)} lignes, manquants : {missing}")


if __name__ == "__main__":
    main()
