"""Télécharge 10 ans de prix ajustés depuis Yahoo Finance ; à lancer depuis un poste de l'équipe."""

from __future__ import annotations

from pathlib import Path

from communitylens.domain.tickers import COMPANIES
from communitylens.ingestion.prices import download_prices

# Ces deux symboles n'existent plus chez Yahoo sous cette forme.
EXCLUDED = {"DWDP", "UTX"}


def main() -> None:
    """Écrit data/yahoo.parquet."""
    tickers = [ticker for ticker in COMPANIES if ticker not in EXCLUDED]
    prices, failures = download_prices(tickers, period="10y")
    Path("data").mkdir(exist_ok=True)
    prices.to_parquet("data/yahoo.parquet", index=False)
    print(f"{len(prices)} lignes, échecs : {failures}")


if __name__ == "__main__":
    main()
