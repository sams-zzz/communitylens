"""Retrieval : filtre par titre et date, puis diversification MMR."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from communitylens.domain.models import Chunk, Passage
from communitylens.rag.embeddings import Embedder
from communitylens.rag.vector_store import VectorStore

CANDIDATES = 20
COMMUNITY_LIMIT = 4
OFFICIAL_LIMIT = 2
LOOKBACK_DAYS = 30
MMR_LAMBDA = 0.7


def mmr(
    query: np.ndarray, vectors: np.ndarray, limit: int, weight: float = MMR_LAMBDA
) -> list[int]:
    """Sélectionne des passages pertinents et différents entre eux."""
    if len(vectors) == 0:
        return []
    relevance = vectors @ query
    selected: list[int] = []
    remaining = list(range(len(vectors)))
    while remaining and len(selected) < limit:
        if selected:
            redundancy = (vectors[remaining] @ vectors[selected].T).max(axis=1)
        else:
            redundancy = np.zeros(len(remaining))
        scores = weight * relevance[remaining] - (1 - weight) * redundancy
        selected.append(remaining.pop(int(np.argmax(scores))))
    return selected


class Retriever:
    """Construit lui-même sa requête : l'utilisateur ne peut pas y injecter de texte."""

    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store

    def _select(
        self, query: np.ndarray, hits: list[tuple[Chunk, np.ndarray]], doc_type: str, limit: int
    ) -> list[Chunk]:
        pool = [
            (chunk, vector)
            for chunk, vector in hits
            if chunk.doc_type == doc_type and not chunk.suspected_injection
        ]
        if not pool:
            return []
        vectors = np.vstack([vector for _, vector in pool])
        return [pool[index][0] for index in mmr(query, vectors, limit)]

    def retrieve(self, ticker: str, company: str, as_of: str) -> list[Passage]:
        """Renvoie les passages étiquetés P1, P2, etc."""
        text = f"{company} {ticker} stock volatility risk earnings rumor outlook"
        query = self._embedder.embed([text])[0]
        since = (datetime.fromisoformat(as_of) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
        hits = self._store.query(query, ticker, since, CANDIDATES)
        chunks = self._select(query, hits, "community", COMMUNITY_LIMIT)
        chunks += self._select(query, hits, "official", OFFICIAL_LIMIT)
        return [
            Passage(
                id=f"P{index}",
                source=chunk.source,
                doc_type=chunk.doc_type,
                published_at=chunk.published_at,
                url=chunk.url,
                text=chunk.text,
            )
            for index, chunk in enumerate(chunks, start=1)
        ]
