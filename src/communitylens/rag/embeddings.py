"""Embeddings : Titan sur AWS, hachage déterministe pour les tests et la démo locale."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """Port de vectorisation."""

    def embed(self, texts: list[str]) -> np.ndarray:
        """Renvoie une matrice de vecteurs normalisés."""


class TitanEmbedder:
    """Titan Text Embeddings V2, appelé texte par texte."""

    MODEL_ID = "amazon.titan-embed-text-v2:0"

    def __init__(self, runtime, dimensions: int = 512) -> None:
        self._runtime = runtime
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        """Appelle le modèle pour chaque texte."""
        rows = []
        for text in texts:
            response = self._runtime.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(
                    {"inputText": text, "dimensions": self._dimensions, "normalize": True}
                ),
                contentType="application/json",
                accept="application/json",
            )
            rows.append(json.loads(response["body"].read())["embedding"])
        return np.asarray(rows, dtype=np.float32)


class HashingEmbedder:
    """Sac de mots haché : sans réseau ni coût, mais sans notion de sens."""

    def __init__(self, dimensions: int = 512) -> None:
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self._dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                digest = hashlib.blake2b(word.encode(), digest_size=4).digest()
                matrix[row, int.from_bytes(digest, "big") % self._dimensions] += 1.0
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.where(norms == 0, 1, norms)


def build_embedder(settings, session=None) -> Embedder:
    """Choisit l'embedder selon la configuration."""
    if settings.embedding_backend == "titan":
        runtime = session.client("bedrock-runtime", region_name=settings.region)
        return TitanEmbedder(runtime, settings.embedding_dimensions)
    if settings.embedding_backend == "hashing":
        return HashingEmbedder(settings.embedding_dimensions)
    raise ValueError(f"Backend d'embeddings inconnu : {settings.embedding_backend}")
