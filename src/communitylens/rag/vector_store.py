"""Index vectoriel : S3 Vectors sur AWS, version en mémoire en local."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import numpy as np

from communitylens.domain.models import Chunk
from communitylens.storage.objects import ObjectStore

_BATCH = 100


def to_timestamp(date_text: str) -> float:
    """Convertit une date ISO en horodatage, pour les filtres."""
    parsed = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()


class VectorStore(Protocol):
    """Port de l'index."""

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        """Ajoute ou remplace des passages."""

    def query(
        self, vector: np.ndarray, ticker: str, since: str, top_k: int
    ) -> list[tuple[Chunk, np.ndarray]]:
        """Renvoie les plus proches voisins du bon titre et de la bonne période."""


class LocalVectorStore:
    """Recherche exacte en mémoire, persistée dans le stockage objet."""

    KEY = "index/chunks.json"

    def __init__(self, store: ObjectStore) -> None:
        self._store = store
        self._records: dict[str, dict] = store.get_json(self.KEY) or {}

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        for chunk, vector in zip(chunks, vectors):
            self._records[chunk.id] = {"chunk": chunk.model_dump(), "vector": vector.tolist()}
        self._store.put_json(self.KEY, self._records)

    def query(
        self, vector: np.ndarray, ticker: str, since: str, top_k: int
    ) -> list[tuple[Chunk, np.ndarray]]:
        """Filtre puis classe tous les passages en mémoire."""
        minimum = to_timestamp(since)
        hits = []
        for record in self._records.values():
            chunk = Chunk.model_validate(record["chunk"])
            if chunk.ticker == ticker and to_timestamp(chunk.published_at) >= minimum:
                candidate = np.asarray(record["vector"], dtype=np.float32)
                hits.append((float(candidate @ vector), chunk, candidate))
        hits.sort(key=lambda item: -item[0])
        return [(chunk, candidate) for _, chunk, candidate in hits[:top_k]]


class S3VectorStore:
    """Adaptateur S3 Vectors ; le texte est stocké en métadonnée non filtrable."""

    def __init__(self, client, bucket: str, index: str) -> None:
        self._client = client
        self._target = {"vectorBucketName": bucket, "indexName": index}

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        """Écrit les vecteurs par lots."""
        records = [
            {
                "key": chunk.id,
                "data": {"float32": [float(value) for value in vector]},
                "metadata": {
                    "ticker": chunk.ticker,
                    "published_ts": to_timestamp(chunk.published_at),
                    "doc_type": chunk.doc_type,
                    "suspected_injection": chunk.suspected_injection,
                    "payload": chunk.model_dump_json(),
                },
            }
            for chunk, vector in zip(chunks, vectors)
        ]
        for start in range(0, len(records), _BATCH):
            self._client.put_vectors(**self._target, vectors=records[start : start + _BATCH])

    def query(
        self, vector: np.ndarray, ticker: str, since: str, top_k: int
    ) -> list[tuple[Chunk, np.ndarray]]:
        """Interroge l'index, puis relit les vecteurs pour la diversification."""
        response = self._client.query_vectors(
            **self._target,
            queryVector={"float32": [float(value) for value in vector]},
            topK=top_k,
            filter={"ticker": ticker, "published_ts": {"$gte": to_timestamp(since)}},
            returnMetadata=True,
        )
        hits = response.get("vectors", [])
        if not hits:
            return []
        stored = self._client.get_vectors(
            **self._target, keys=[hit["key"] for hit in hits], returnData=True
        )
        data = {item["key"]: item["data"]["float32"] for item in stored.get("vectors", [])}
        return [
            (
                Chunk.model_validate_json(hit["metadata"]["payload"]),
                np.asarray(data[hit["key"]], dtype=np.float32),
            )
            for hit in hits
            if hit["key"] in data
        ]
