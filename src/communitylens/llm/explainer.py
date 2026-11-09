"""Orchestre le LLM : génération, validation, vérification, nouvel essai, repli."""

from __future__ import annotations

import time
from importlib import resources

from pydantic import ValidationError

from communitylens.domain.models import (
    Analysis,
    Explanation,
    Fact,
    FactPack,
    Forecast,
    Generation,
    Passage,
)
from communitylens.llm.clients import LLMClient, LLMError, french_number
from communitylens.llm.verifier import verify

PROMPT_VERSION = "v1"


def load_system_prompt(version: str = PROMPT_VERSION) -> str:
    """Charge un prompt versionné depuis le paquet."""
    path = resources.files("communitylens.llm") / "prompts" / f"system_{version}.txt"
    return path.read_text(encoding="utf-8")


def build_fact_pack(forecast: Forecast, company: str, passages: list[Passage]) -> FactPack:
    """Rassemble les faits calculés ; le LLM ne reçoit aucun autre chiffre."""
    labels = [
        ("Volatilité annualisée prévue (%)", forecast.volatility_pct),
        ("Borne basse de l'intervalle (%)", forecast.low_pct),
        ("Borne haute de l'intervalle (%)", forecast.high_pct),
        ("Niveau de l'intervalle (%)", float(forecast.level_pct)),
        ("Horizon (jours)", float(forecast.horizon_days)),
        ("Volatilité annualisée sur 20 jours (%)", forecast.recent_volatility_pct),
        ("Volatilité annualisée sur 60 jours (%)", forecast.usual_volatility_pct),
        ("Couverture observée sur 60 jours (%)", forecast.coverage_60d_pct),
        ("Dernier cours ($)", forecast.last_close),
        ("Variation sur 5 jours (%)", forecast.change_5d_pct),
    ]
    labels += [(f"Effet : {item.label} (%)", item.effect_pct) for item in forecast.attributions]
    facts = [
        Fact(id=f"F{index}", label=label, value=value)
        for index, (label, value) in enumerate(labels, start=1)
    ]
    return FactPack(
        ticker=forecast.ticker,
        company=company,
        as_of=forecast.as_of,
        facts=facts,
        passages=passages,
    )


def fallback_explanation(pack: FactPack) -> Explanation:
    """Texte produit par le code : le service reste honnête si le LLM échoue."""
    values = {fact.id: fact for fact in pack.facts}
    return Explanation(
        summary=(
            f"Pour {pack.company}, la volatilité annualisée prévue est de "
            f"{french_number(values['F1'].value)} % [F1], dans un intervalle allant de "
            f"{french_number(values['F2'].value)} % [F2] à "
            f"{french_number(values['F3'].value)} % [F3]."
        ),
        claims=[],
        limits=(
            "Texte généré sans LLM : les discussions de la communauté n'ont pas été analysées. "
            "Il s'agit d'une estimation statistique, pas d'un conseil."
        ),
    )


def explain(
    client: LLMClient, pack: FactPack, system: str | None = None, retries: int = 1
) -> tuple[Explanation, Generation]:
    """Renvoie toujours un texte publiable, et la trace de ce qui s'est passé."""
    system_prompt = system or load_system_prompt()
    schema = Explanation.model_json_schema()
    base = pack.model_dump_json()
    user = base
    trace = Generation(
        generator=client.name,
        model_id=client.model_id,
        prompt_version=PROMPT_VERSION,
        attempts=0,
        fallback_used=False,
    )
    started = time.perf_counter()
    for _ in range(retries + 1):
        trace.attempts += 1
        try:
            result = client.complete(system_prompt, user, schema)
        except LLMError as error:
            trace.rejected_reasons.append(f"erreur d'appel : {error}")
            continue
        trace.input_tokens += result.input_tokens
        trace.output_tokens += result.output_tokens
        try:
            candidate = Explanation.model_validate_json(result.text)
        except ValidationError as error:
            trace.rejected_reasons.append("schéma invalide")
            user = f"{base}\nSortie précédente invalide : {error.error_count()} erreurs"
            continue
        problems = verify(candidate, pack)
        if not problems:
            trace.latency_ms = int((time.perf_counter() - started) * 1000)
            return candidate, trace
        trace.rejected_reasons.extend(problems)
        user = f"{base}\nCorrige ces violations : {problems}"
    trace.fallback_used = True
    trace.generator = "repli-sans-llm"
    trace.latency_ms = int((time.perf_counter() - started) * 1000)
    return fallback_explanation(pack), trace


def freeze_analysis(
    analysis_id: str,
    created_at: str,
    forecast: Forecast,
    pack: FactPack,
    explanation: Explanation,
    generation: Generation,
) -> Analysis:
    """Assemble l'analyse à stocker et à partager."""
    return Analysis(
        id=analysis_id,
        ticker=forecast.ticker,
        company=pack.company,
        created_at=created_at,
        forecast=forecast,
        facts=pack.facts,
        explanation=explanation,
        passages=pack.passages,
        generation=generation,
    )
