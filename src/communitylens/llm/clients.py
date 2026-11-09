"""Adaptateurs LLM derrière un même port."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

import requests
from botocore.exceptions import BotoCoreError, ClientError

from communitylens.domain.models import Claim, Explanation, FactPack


class LLMError(RuntimeError):
    """Échec technique d'appel au modèle."""


@dataclass
class LLMResult:
    """Réponse brute et consommation."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(Protocol):
    """Port commun : Bedrock, Ollama, mode démo ou faux client de test."""

    name: str
    model_id: str

    def complete(self, system: str, user: str, schema: dict) -> LLMResult:
        """Renvoie le texte JSON produit par le modèle."""


class BedrockClient:
    """Adaptateur Bedrock fondé sur l'API Converse et la sortie structurée."""

    name = "bedrock"

    def __init__(
        self, runtime, model_id: str, guardrail_id: str = "", guardrail_version: str = "1"
    ) -> None:
        self._runtime = runtime
        self.model_id = model_id
        self._guardrail_id = guardrail_id
        self._guardrail_version = guardrail_version

    def complete(self, system: str, user: str, schema: dict) -> LLMResult:
        """Appelle Converse en imposant le schéma de sortie."""
        options = {}
        if self._guardrail_id:
            options["guardrailConfig"] = {
                "guardrailIdentifier": self._guardrail_id,
                "guardrailVersion": self._guardrail_version,
            }
        try:
            response = self._runtime.converse(
                **options,
                modelId=self.model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": 900, "temperature": 0.0},
                outputConfig={
                    "textFormat": {
                        "type": "json_schema",
                        "structure": {
                            "jsonSchema": {
                                "schema": json.dumps(schema),
                                "name": "explanation",
                                "description": "Explication vérifiable",
                            }
                        },
                    }
                },
            )
        except (BotoCoreError, ClientError) as error:
            raise LLMError(type(error).__name__) from error
        usage = response.get("usage", {})
        return LLMResult(
            response["output"]["message"]["content"][0]["text"],
            usage.get("inputTokens", 0),
            usage.get("outputTokens", 0),
        )


class OllamaClient:
    """Adaptateur local, utilisé en développement et comme baseline du benchmark."""

    name = "ollama"

    def __init__(self, url: str, model_id: str, timeout: int = 120) -> None:
        self._url = url.rstrip("/")
        self.model_id = model_id
        self._timeout = timeout

    def complete(self, system: str, user: str, schema: dict) -> LLMResult:
        """Appelle l'API de chat d'Ollama avec un format imposé."""
        try:
            response = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self.model_id,
                    "stream": False,
                    "format": schema,
                    "options": {"temperature": 0},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise LLMError(type(error).__name__) from error
        payload = response.json()
        return LLMResult(
            payload["message"]["content"],
            payload.get("prompt_eval_count", 0),
            payload.get("eval_count", 0),
        )


class DemoClient:
    """Mode sans LLM, à règles simples. L'interface l'indique toujours clairement."""

    name = "demo"
    model_id = "regles-sans-llm"

    def complete(self, system: str, user: str, schema: dict) -> LLMResult:
        """Produit une réponse par règles, à partir du seul contexte."""
        del system, schema
        pack = FactPack.model_validate_json(user.split("\nCorrige")[0].split("\nSortie")[0])
        values = {fact.id: fact.value for fact in pack.facts}
        claims = [_demo_claim(passage, values) for passage in pack.passages[:4]]
        summary = (
            f"La volatilité annualisée prévue à {values['F5']:.0f} [F5] jours est de "
            f"{french_number(values['F1'])} % [F1], avec un intervalle à {values['F4']:.0f} % [F4] "
            f"allant de {french_number(values['F2'])} % [F2] "
            f"à {french_number(values['F3'])} % [F3]. "
            f"Sa référence récente est de {french_number(values['F7'])} % [F7]."
        )
        result = Explanation(
            summary=summary,
            claims=claims,
            limits="Il s'agit d'une estimation statistique, pas d'un conseil.",
        )
        return LLMResult(result.model_dump_json())


def french_number(value: float) -> str:
    """Écrit un nombre avec une virgule décimale."""
    return f"{value:g}".replace(".", ",")


def _demo_claim(passage, values: dict[str, float]) -> Claim:
    first = re.split(r"(?<=[.!?])\s", passage.text.strip())[0][:180]
    text = f"Un message indique : « {first} » [{passage.id}]"
    lowered = passage.text.lower()
    evidence = ["F1", "F7", passage.id]
    if re.search(r"calme|tranquille|stable", lowered):
        status = "contredite" if values["F1"] >= values["F7"] else "soutenue"
        return Claim(text=text, status=status, evidence=evidence)
    if re.search(r"volatil|agit|nerveu|turbulen", lowered):
        status = "soutenue" if values["F1"] >= values["F7"] else "contredite"
        return Claim(text=text, status=status, evidence=evidence)
    return Claim(text=text, status="non_verifiable", evidence=[passage.id])


def build_llm_client(settings, session=None) -> LLMClient:
    """Choisit l'adaptateur selon la configuration."""
    if settings.llm_backend == "bedrock":
        runtime = session.client("bedrock-runtime", region_name=settings.region)
        return BedrockClient(
            runtime,
            settings.bedrock_model_id,
            settings.guardrail_id,
            settings.guardrail_version,
        )
    if settings.llm_backend == "ollama":
        return OllamaClient(settings.ollama_url, settings.ollama_model)
    if settings.llm_backend == "demo":
        return DemoClient()
    raise ValueError(f"Backend LLM inconnu : {settings.llm_backend}")
