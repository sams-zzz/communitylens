"""Contrôle par le code : aucun texte du LLM n'est publié sans passer ici."""

from __future__ import annotations

import re

from communitylens.domain.models import Explanation, FactPack

NUMBER = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)?(?![\w])")
CITATION = re.compile(r"\[(F\d+|P\d+)\]")
ADVICE = re.compile(
    r"\b(achetez|vendez|acheter|vendre|conservez|je recommande|nous recommandons|"
    r"recommandation d'achat|objectif de cours|buy now|sell now)\b",
    re.IGNORECASE,
)


def _number_matches(raw: str, allowed: set[float]) -> bool:
    """Accepte un arrondi cohérent avec le nombre de décimales écrites."""
    normalized = raw.replace(",", ".")
    decimals = len(normalized.split(".")[1]) if "." in normalized else 0
    value = float(normalized)
    return any(abs(abs(value) - abs(item)) <= 0.5 * 10**-decimals + 1e-9 for item in allowed)


def _numbers_in(text: str) -> list[str]:
    return NUMBER.findall(CITATION.sub("", text))


def _check_text(text: str, allowed_ids: set[str], allowed_numbers: set[float]) -> list[str]:
    problems = [
        f"source inconnue : {cited}" for cited in CITATION.findall(text) if cited not in allowed_ids
    ]
    problems += [
        f"chiffre hors contexte : {raw}"
        for raw in _numbers_in(text)
        if not _number_matches(raw, allowed_numbers)
    ]
    if ADVICE.search(text):
        problems.append("formulation de conseil en investissement")
    return problems


def verify(explanation: Explanation, pack: FactPack) -> list[str]:
    """Renvoie les violations ; une liste vide signifie un texte publiable."""
    fact_ids = {fact.id for fact in pack.facts}
    passages = {passage.id: passage for passage in pack.passages}
    allowed_ids = fact_ids | set(passages)
    fact_numbers = {fact.value for fact in pack.facts}
    problems: list[str] = []

    for text in (explanation.summary, explanation.limits):
        problems += _check_text(text.replace(pack.as_of, ""), allowed_ids, fact_numbers)

    for claim in explanation.claims:
        unknown = [item for item in claim.evidence if item not in allowed_ids]
        problems += [f"preuve inconnue : {item}" for item in unknown]
        cited_passages = [passages[item] for item in claim.evidence if item in passages]
        if not cited_passages:
            problems.append("affirmation sans passage source")
        if claim.status != "non_verifiable" and not set(claim.evidence) & fact_ids:
            problems.append("affirmation tranchée sans fait")
        quoted = {
            float(raw.replace(",", "."))
            for passage in cited_passages
            for raw in _numbers_in(passage.text)
        }
        problems += _check_text(claim.text, allowed_ids, fact_numbers | quoted)
    return problems
