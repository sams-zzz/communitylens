"""Contrats de données partagés, sans dépendance à AWS."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Attribution(BaseModel):
    """Effet d'une feature sur la prévision, en pourcentage."""

    feature: str
    label: str
    effect_pct: float


class Forecast(BaseModel):
    """Prévision de volatilité à 5 jours, annualisée, avec son intervalle."""

    ticker: str
    as_of: str
    volatility_pct: float
    low_pct: float
    high_pct: float
    level_pct: int = 80
    horizon_days: int = 5
    recent_volatility_pct: float
    usual_volatility_pct: float
    coverage_60d_pct: float
    last_close: float
    change_5d_pct: float
    attributions: list[Attribution]
    model_version: str


class Chunk(BaseModel):
    """Passage indexé, sans pseudonyme d'auteur."""

    id: str
    ticker: str
    source: str
    doc_type: Literal["community", "official"]
    published_at: str
    url: str = ""
    text: str
    suspected_injection: bool = False


class Fact(BaseModel):
    """Fait calculé par le code : seule source de chiffres autorisée."""

    id: str
    label: str
    value: float


class Passage(BaseModel):
    """Passage transmis au LLM, traité comme une donnée non fiable."""

    id: str
    source: str
    doc_type: str
    published_at: str
    url: str = ""
    text: str


class FactPack(BaseModel):
    """Contexte complet transmis au LLM."""

    ticker: str
    company: str
    as_of: str
    facts: list[Fact]
    passages: list[Passage]


class Claim(BaseModel):
    """Affirmation de la communauté confrontée aux données."""

    model_config = ConfigDict(extra="forbid")
    text: str
    status: Literal["soutenue", "contredite", "non_verifiable"]
    evidence: list[str]


class Explanation(BaseModel):
    """Contrat de sortie du LLM."""

    model_config = ConfigDict(extra="forbid")
    summary: str
    claims: list[Claim]
    limits: str


class Generation(BaseModel):
    """Trace de la génération, pour l'observabilité et le rejeu."""

    generator: str
    model_id: str = ""
    prompt_version: str
    attempts: int
    fallback_used: bool
    rejected_reasons: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class Analysis(BaseModel):
    """Analyse figée, partageable par lien."""

    id: str
    ticker: str
    company: str
    created_at: str
    forecast: Forecast
    facts: list[Fact]
    explanation: Explanation
    passages: list[Passage]
    generation: Generation
