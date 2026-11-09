"""Évaluation et benchmark des LLM sur un jeu de référence annoté."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from communitylens.config import Settings
from communitylens.domain.models import Fact, FactPack, Passage
from communitylens.llm.clients import BedrockClient, DemoClient, LLMClient, OllamaClient
from communitylens.llm.explainer import explain

_LABELS = {
    "F1": "Volatilité annualisée prévue (%)",
    "F2": "Borne basse de l'intervalle (%)",
    "F3": "Borne haute de l'intervalle (%)",
    "F4": "Niveau de l'intervalle (%)",
    "F5": "Horizon (jours)",
    "F6": "Volatilité annualisée sur 20 jours (%)",
    "F7": "Volatilité annualisée sur 60 jours (%)",
}
STATUSES = ("soutenue", "contredite", "non_verifiable")


def pack_for_case(case: dict) -> FactPack:
    """Construit le contexte d'un cas annoté."""
    defaults = {"F2": 10.0, "F3": 50.0, "F4": 80.0, "F5": 5.0, "F6": 22.0}
    values = {**defaults, **case["facts"]}
    return FactPack(
        ticker="AAPL",
        company="Apple",
        as_of="2018-02-07",
        facts=[Fact(id=key, label=_LABELS[key], value=values[key]) for key in sorted(values)],
        passages=[
            Passage(
                id="P1",
                source="jeu de référence",
                doc_type="community",
                published_at="2018-02-06",
                text=case["passage"],
            )
        ],
    )


def macro_f1(pairs: list[tuple[str, str | None]]) -> float:
    """F1 macro sur les trois statuts ; une affirmation manquante compte comme une erreur."""
    scores = []
    for status in STATUSES:
        tp = sum(1 for expected, got in pairs if expected == status and got == status)
        fp = sum(1 for expected, got in pairs if expected != status and got == status)
        fn = sum(1 for expected, got in pairs if expected == status and got != status)
        scores.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0)
    return sum(scores) / len(scores)


def evaluate_client(client: LLMClient, cases: list[dict], prices: tuple[float, float]) -> dict:
    """Mesure qualité, fiabilité, latence et coût d'un modèle."""
    pairs, latencies, costs = [], [], []
    fallbacks = first_try = 0
    for case in cases:
        started = time.perf_counter()
        explanation, generation = explain(client, pack_for_case(case))
        latencies.append((time.perf_counter() - started) * 1000)
        got = explanation.claims[0].status if explanation.claims else None
        pairs.append((case["expected"], got))
        fallbacks += generation.fallback_used
        first_try += generation.attempts == 1 and not generation.fallback_used
        costs.append(
            (generation.input_tokens * prices[0] + generation.output_tokens * prices[1]) / 1e6
        )
    count = len(cases)
    return {
        "model": client.model_id,
        "cases": count,
        "macro_f1": round(macro_f1(pairs), 3),
        "accuracy": round(sum(e == g for e, g in pairs) / count, 3),
        "accepted_first_try": round(first_try / count, 3),
        "fallback_rate": round(fallbacks / count, 3),
        "latency_median_ms": round(statistics.median(latencies)),
        "latency_max_ms": round(max(latencies)),
        "cost_per_analysis_usd": round(sum(costs) / count, 6),
    }


def _client(spec: str, settings: Settings) -> LLMClient:
    backend, _, model = spec.partition(":")
    if backend == "demo":
        return DemoClient()
    if backend == "ollama":
        return OllamaClient(settings.ollama_url, model)
    if backend == "bedrock":
        import boto3  # pylint: disable=import-outside-toplevel

        runtime = boto3.client("bedrock-runtime", region_name=settings.region)
        return BedrockClient(runtime, model)
    raise ValueError(f"Modèle inconnu : {spec}")


def main() -> None:
    """Exemple : --models bedrock:eu.amazon.nova-micro-v1:0 ollama:mistral"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evaluation_data/golden_sample.jsonl")
    parser.add_argument("--models", nargs="+", default=["demo"])
    parser.add_argument("--output", default="results/llm_benchmark.json")
    args = parser.parse_args()
    settings = Settings.from_env()
    lines = Path(args.cases).read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    prices = (settings.input_price_per_million, settings.output_price_per_million)
    report = [evaluate_client(_client(spec, settings), cases, prices) for spec in args.models]
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
