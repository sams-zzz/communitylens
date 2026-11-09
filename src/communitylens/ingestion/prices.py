"""Collecte Yahoo Finance : la bougie du jour est exclue, car elle peut être incomplète."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd

from communitylens.storage.objects import ObjectStore

PRICES_KEY = "curated/prices.parquet"


class PriceDataError(ValueError):
    """Données de prix inutilisables."""


def validate_prices(frame: pd.DataFrame) -> pd.DataFrame:
    """Rejette les lignes impossibles et les doublons."""
    required = {"date", "ticker", "open", "high", "low", "close", "volume"}
    if missing := required - set(frame.columns):
        raise PriceDataError(f"Colonnes manquantes : {sorted(missing)}")
    clean = frame.dropna(subset=["date", "ticker", "open", "high", "low", "close"]).copy()
    clean["date"] = pd.to_datetime(clean["date"]).dt.tz_localize(None)
    valid = (clean[["open", "high", "low", "close"]] > 0).all(axis=1) & (
        clean["high"] >= clean["low"]
    )
    clean = clean[valid].drop_duplicates(["ticker", "date"], keep="last")
    if clean.empty:
        raise PriceDataError("Aucune ligne valide")
    return clean.sort_values(["ticker", "date"]).reset_index(drop=True)


def download_prices(tickers: list[str], period: str = "6y", now: datetime | None = None):
    """Télécharge les prix ; un titre en échec est signalé sans bloquer les autres."""
    import yfinance as yf  # pylint: disable=import-outside-toplevel

    today = (now or datetime.now(timezone.utc)).date()
    frames, failures = [], []
    for ticker in tickers:
        try:
            raw = yf.download(
                ticker, period=period, auto_adjust=True, progress=False, threads=False
            )
        except Exception:  # pylint: disable=broad-exception-caught
            failures.append(ticker)
            continue
        if raw is None or raw.empty:
            failures.append(ticker)
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        frame = raw.rename(columns=str.lower).reset_index().rename(columns={"Date": "date"})
        frame["ticker"] = ticker
        frames.append(frame[pd.to_datetime(frame["date"]).dt.date < today])
    if not frames:
        raise PriceDataError("Aucun titre téléchargé")
    return validate_prices(pd.concat(frames, ignore_index=True)), failures


def save_prices(store: ObjectStore, prices: pd.DataFrame) -> None:
    """Écrit le dernier état, qui sert aussi de repli si Yahoo est indisponible."""
    buffer = io.BytesIO()
    prices.to_parquet(buffer, index=False)
    store.put_bytes(PRICES_KEY, buffer.getvalue())


def load_prices(store: ObjectStore) -> pd.DataFrame | None:
    """Relit le dernier état."""
    data = store.get_bytes(PRICES_KEY)
    return None if data is None else pd.read_parquet(io.BytesIO(data))
