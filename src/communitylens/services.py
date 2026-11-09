"""Cas d'usage et composition des dépendances."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from communitylens.config import Settings
from communitylens.domain.models import Analysis
from communitylens.domain.tickers import company_name
from communitylens.llm.clients import LLMClient, build_llm_client
from communitylens.llm.explainer import build_fact_pack, explain, freeze_analysis
from communitylens.observability import emit_generation_metrics
from communitylens.rag.embeddings import build_embedder
from communitylens.rag.retriever import Retriever
from communitylens.rag.vector_store import LocalVectorStore, S3VectorStore, VectorStore
from communitylens.storage.objects import LocalObjectStore, ObjectStore, S3ObjectStore
from communitylens.storage.repository import DynamoRepository, LocalRepository, Repository


class UnknownTicker(LookupError):
    """Aucune prévision pour ce titre."""


@dataclass
class Services:
    """Dépendances d'exécution, injectées dans l'API et le job."""

    settings: Settings
    store: ObjectStore
    repository: Repository
    vectors: VectorStore
    retriever: Retriever
    llm: LLMClient
    embedder: object


class AnalysisService:
    """Produit une analyse par titre et par date, puis la réutilise."""

    def __init__(self, services: Services) -> None:
        self._services = services

    def _cost(self, generation) -> float:
        settings = self._services.settings
        return round(
            generation.input_tokens * settings.input_price_per_million / 1_000_000
            + generation.output_tokens * settings.output_price_per_million / 1_000_000,
            6,
        )

    def analyze(self, ticker: str) -> Analysis:
        """Renvoie l'analyse du jour, depuis le cache ou en la générant."""
        repository = self._services.repository
        forecast = repository.latest_forecast(ticker)
        if forecast is None:
            raise UnknownTicker(ticker)
        cached = repository.cached_analysis(ticker, forecast.as_of)
        if cached is not None:
            return cached
        company = company_name(ticker)
        passages = self._services.retriever.retrieve(ticker, company, forecast.as_of)
        pack = build_fact_pack(forecast, company, passages)
        explanation, generation = explain(self._services.llm, pack)
        generation.cost_usd = self._cost(generation)
        emit_generation_metrics(ticker, generation, generation.cost_usd)
        analysis = freeze_analysis(
            uuid.uuid4().hex,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            forecast,
            pack,
            explanation,
            generation,
        )
        repository.put_analysis(analysis)
        return analysis


def build_services(settings: Settings) -> Services:
    """Assemble les adaptateurs selon l'environnement."""
    session = None
    if (
        settings.backend == "aws"
        or "bedrock" in settings.llm_backend
        or (settings.embedding_backend == "titan")
    ):
        import boto3  # pylint: disable=import-outside-toplevel

        session = boto3.session.Session(region_name=settings.region)
    if settings.backend == "aws":
        store = S3ObjectStore(session.client("s3"), settings.bucket)
        repository: Repository = DynamoRepository(
            session.resource("dynamodb").Table(settings.table)
        )
        vectors: VectorStore = S3VectorStore(
            session.client("s3vectors"), settings.vector_bucket, settings.vector_index
        )
    elif settings.backend == "local":
        store = LocalObjectStore(settings.data_dir)
        repository = LocalRepository(store)
        vectors = LocalVectorStore(store)
    else:
        raise ValueError(f"Backend inconnu : {settings.backend}")
    embedder = build_embedder(settings, session)
    return Services(
        settings=settings,
        store=store,
        repository=repository,
        vectors=vectors,
        retriever=Retriever(embedder, vectors),
        llm=build_llm_client(settings, session),
        embedder=embedder,
    )
