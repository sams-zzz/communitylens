"""Journaux JSON, avec le format de métriques intégrées de CloudWatch (EMF)."""

from __future__ import annotations

import json
import logging
import sys
import time

_NAMESPACE = "CommunityLens"
_METRICS = {
    "LatencyMs": "Milliseconds",
    "InputTokens": "Count",
    "OutputTokens": "Count",
    "CostUsd": "None",
    "Fallback": "Count",
    "Attempts": "Count",
}


def configure_logging() -> None:
    """Écrit les messages bruts sur la sortie standard, que Lambda envoie à CloudWatch."""
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s", force=True)


def log_event(event: str, **fields) -> dict:
    """Journalise un événement structuré."""
    record = {"event": event, **fields}
    logging.getLogger("communitylens").info(json.dumps(record, ensure_ascii=False, default=str))
    return record


def emit_generation_metrics(ticker: str, generation, cost_usd: float) -> dict:
    """Publie les mesures d'une génération ; CloudWatch les extrait des journaux."""
    values = {
        "LatencyMs": generation.latency_ms,
        "InputTokens": generation.input_tokens,
        "OutputTokens": generation.output_tokens,
        "CostUsd": cost_usd,
        "Fallback": int(generation.fallback_used),
        "Attempts": generation.attempts,
    }
    payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": _NAMESPACE,
                    "Dimensions": [["Generator"]],
                    "Metrics": [{"Name": name, "Unit": unit} for name, unit in _METRICS.items()],
                }
            ],
        },
        "Generator": generation.generator,
        "ticker": ticker,
        "prompt_version": generation.prompt_version,
        "model_id": generation.model_id,
        **values,
    }
    logging.getLogger("communitylens").info(json.dumps(payload, ensure_ascii=False))
    return payload
