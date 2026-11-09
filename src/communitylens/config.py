"""Configuration lue uniquement depuis l'environnement."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Paramètres d'exécution ; les valeurs par défaut lancent le mode local."""

    backend: str = "local"
    data_dir: str = "data/runtime"
    bucket: str = ""
    table: str = ""
    vector_bucket: str = ""
    vector_index: str = "passages"
    region: str = "eu-west-3"
    llm_backend: str = "demo"
    bedrock_model_id: str = "eu.amazon.nova-micro-v1:0"
    guardrail_id: str = ""
    guardrail_version: str = "1"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    embedding_backend: str = "hashing"
    embedding_dimensions: int = 512
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cors_origin: str = "*"
    sec_user_agent: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        """Construit les paramètres à partir des variables CL_*."""
        env = os.environ.get
        return cls(
            backend=env("CL_BACKEND", cls.backend),
            data_dir=env("CL_DATA_DIR", cls.data_dir),
            bucket=env("CL_BUCKET", cls.bucket),
            table=env("CL_TABLE", cls.table),
            vector_bucket=env("CL_VECTOR_BUCKET", cls.vector_bucket),
            vector_index=env("CL_VECTOR_INDEX", cls.vector_index),
            region=env("AWS_REGION", cls.region),
            llm_backend=env("CL_LLM_BACKEND", cls.llm_backend),
            bedrock_model_id=env("CL_BEDROCK_MODEL_ID", cls.bedrock_model_id),
            guardrail_id=env("CL_GUARDRAIL_ID", cls.guardrail_id),
            guardrail_version=env("CL_GUARDRAIL_VERSION", cls.guardrail_version),
            ollama_url=env("CL_OLLAMA_URL", cls.ollama_url),
            ollama_model=env("CL_OLLAMA_MODEL", cls.ollama_model),
            embedding_backend=env("CL_EMBEDDING_BACKEND", cls.embedding_backend),
            embedding_dimensions=int(env("CL_EMBEDDING_DIMENSIONS", cls.embedding_dimensions)),
            input_price_per_million=float(env("CL_INPUT_PRICE", cls.input_price_per_million)),
            output_price_per_million=float(env("CL_OUTPUT_PRICE", cls.output_price_per_million)),
            cors_origin=env("CL_CORS_ORIGIN", cls.cors_origin),
            sec_user_agent=env("CL_SEC_USER_AGENT", cls.sec_user_agent),
        )
