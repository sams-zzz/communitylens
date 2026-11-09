"""Traitement quotidien : prix, prévisions, index des textes et fichiers de service."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from communitylens.config import Settings
from communitylens.domain.tickers import COMPANIES, company_name
from communitylens.forecasting.pipeline import run_forecast
from communitylens.ingestion.community import (
    CommunitySource,
    HackerNewsSource,
    LocalFileSource,
    RedditSource,
)
from communitylens.ingestion.edgar import EdgarSource
from communitylens.ingestion.prices import PriceDataError, download_prices, load_prices, save_prices
from communitylens.observability import configure_logging, log_event
from communitylens.rag.chunking import deduplicate
from communitylens.services import Services, build_services

LOOKBACK_DAYS = 30


def collect_prices(services: Services, tickers: list[str], prices_file: str | None) -> pd.DataFrame:
    """Charge les prix ; en cas de panne de Yahoo, repart du dernier état connu."""
    if prices_file:
        prices = pd.read_parquet(prices_file)
        prices = prices[prices["ticker"].isin(tickers)]
        save_prices(services.store, prices)
        return prices
    try:
        prices, failures = download_prices(tickers)
    except PriceDataError as error:
        previous = load_prices(services.store)
        if previous is None:
            raise
        log_event("prices_fallback", reason=str(error))
        return previous
    if failures:
        log_event("prices_partial_failure", tickers=failures)
    save_prices(services.store, prices)
    return prices


def publish_forecasts(services: Services, prices: pd.DataFrame) -> str:
    """Publie modèle, manifeste, prévisions et historique ; renvoie la dernière date."""
    run = run_forecast(prices, git_sha=os.environ.get("GIT_SHA", "unknown"))
    version = run.manifest["version"]
    services.store.put_json(f"models/{version}/manifest.json", run.manifest)
    for forecast in run.forecasts:
        services.repository.put_forecast(forecast)
        services.store.put_json(
            f"serving/history/{forecast.ticker}.json", run.history[forecast.ticker]
        )
    log_event(
        "forecasts_published",
        version=version,
        count=len(run.forecasts),
        skipped=run.skipped,
    )
    return max(forecast.as_of for forecast in run.forecasts)


def index_texts(
    services: Services,
    tickers: list[str],
    as_of: str,
    sources: list[CommunitySource],
    edgar: EdgarSource | None,
) -> int:
    """Vectorise et indexe les nouveaux passages ; une source en panne n'arrête pas le job."""
    since = datetime.fromisoformat(as_of).replace(tzinfo=timezone.utc) - timedelta(
        days=LOOKBACK_DAYS
    )
    total = 0
    for ticker in tickers:
        chunks = []
        for source in sources:
            try:
                chunks += source.fetch(ticker, company_name(ticker), since)
            except Exception as error:  # pylint: disable=broad-exception-caught
                log_event(
                    "source_failure", source=source.name, ticker=ticker, error=type(error).__name__
                )
        if edgar is not None:
            try:
                chunks += edgar.fetch(ticker, since.date().isoformat())
            except Exception as error:  # pylint: disable=broad-exception-caught
                log_event(
                    "source_failure", source=edgar.name, ticker=ticker, error=type(error).__name__
                )
        unique = deduplicate(chunks)
        if unique:
            services.vectors.upsert(unique, services.embedder.embed([c.text for c in unique]))
            total += len(unique)
    return total


def build_sources(posts_file: str | None) -> list[CommunitySource]:
    """Choisit les sources : fichier local en démo, API publiques sinon."""
    if posts_file:
        return [LocalFileSource(posts_file)]
    sources: list[CommunitySource] = [HackerNewsSource()]
    client_id, secret = os.environ.get("CL_REDDIT_ID"), os.environ.get("CL_REDDIT_SECRET")
    if client_id and secret:
        sources.append(RedditSource(client_id, secret))
    return sources


def run_job(
    services: Services,
    tickers: list[str],
    prices_file: str | None = None,
    posts_file: str | None = None,
) -> dict:
    """Enchaîne toutes les étapes."""
    prices = collect_prices(services, tickers, prices_file)
    as_of = publish_forecasts(services, prices)
    edgar = None
    if services.settings.sec_user_agent:
        edgar = EdgarSource(services.settings.sec_user_agent)
    indexed = index_texts(services, tickers, as_of, build_sources(posts_file), edgar)
    summary = {"as_of": as_of, "indexed_passages": indexed, "tickers": len(tickers)}
    log_event("job_finished", **summary)
    return summary


def lambda_handler(_event, _context) -> dict:
    """Point d'entrée Lambda, déclenché par EventBridge."""
    configure_logging()
    settings = Settings.from_env()
    return run_job(build_services(settings), sorted(COMPANIES))


def main() -> None:
    """Point d'entrée en ligne de commande."""
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="*", default=sorted(COMPANIES))
    parser.add_argument("--prices-file", help="Parquet local, à la place de Yahoo Finance")
    parser.add_argument("--posts-file", help="JSONL local, à la place des API communautaires")
    args = parser.parse_args()
    services = build_services(Settings.from_env())
    print(run_job(services, args.tickers, args.prices_file, args.posts_file))


if __name__ == "__main__":
    main()
