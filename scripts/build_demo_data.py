"""Prépare la démo locale : prix réels jusqu'au 7 février 2018 et messages explicitement fictifs."""

from __future__ import annotations

import json
from pathlib import Path

from communitylens.config import Settings
from communitylens.jobs.daily import run_job
from communitylens.observability import configure_logging
from communitylens.services import build_services
from communitylens.domain.tickers import COMPANIES


def main() -> None:
    """Exécute le job et publie les métriques mesurées."""
    configure_logging()
    settings = Settings.from_env()
    services = build_services(settings)
    print(
        run_job(
            services,
            sorted(COMPANIES),
            prices_file="data/benchmark_dow30.parquet",
            posts_file="evaluation_data/demo_posts.jsonl",
        )
    )
    metrics = json.loads(Path("results/forecast_eval.json").read_text(encoding="utf-8"))
    services.store.put_json("serving/metrics.json", metrics)


if __name__ == "__main__":
    main()
