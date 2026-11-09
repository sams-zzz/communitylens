"""Stockage objet : S3 sur AWS, disque en local."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from botocore.exceptions import ClientError


class ObjectStore(Protocol):
    """Port de stockage."""

    def put_bytes(self, key: str, data: bytes) -> None:
        """Écrit un objet."""

    def get_bytes(self, key: str) -> bytes | None:
        """Lit un objet ; None s'il n'existe pas."""

    def put_json(self, key: str, value) -> None:
        """Écrit un objet JSON."""

    def get_json(self, key: str):
        """Lit un objet JSON ; None s'il n'existe pas."""


class _JsonMixin:
    def put_json(self, key: str, value) -> None:
        """Écrit un objet JSON."""
        self.put_bytes(key, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def get_json(self, key: str):
        """Lit un objet JSON ; None s'il n'existe pas."""
        data = self.get_bytes(key)
        return None if data is None else json.loads(data)


class LocalObjectStore(_JsonMixin):
    """Stockage sur disque, refuse toute clé qui sortirait du dossier."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"Clé invalide : {key}")
        return path

    def put_bytes(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None


class S3ObjectStore(_JsonMixin):
    """Adaptateur S3."""

    def __init__(self, client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put_bytes(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get_bytes(self, key: str) -> bytes | None:
        try:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as error:
            if error.response["Error"]["Code"] in {"NoSuchKey", "404"}:
                return None
            raise
