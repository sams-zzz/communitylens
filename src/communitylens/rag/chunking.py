"""Nettoyage et découpage des textes avant indexation."""

from __future__ import annotations

import hashlib
import html
import re

from communitylens.domain.models import Chunk

COMMUNITY_MAX_WORDS, COMMUNITY_OVERLAP = 220, 30
OFFICIAL_MAX_WORDS, OFFICIAL_OVERLAP = 380, 40
_TAGS = re.compile(r"<[^>]+>")
_HANDLES = re.compile(r"(?<!\w)(?:@[\w-]+|/?u/[\w-]+)")
_CONTROL = re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f" + "\\u200b-\\u200f\\u2060-\\u206f]")
_INJECTION = re.compile(
    r"ignore\s+(?:all\s+|tes\s+|les\s+|your\s+|previous\s+|pr[ée]c[ée]dentes\s+)*"
    r"(?:instructions?|consignes?|rules?|r[èe]gles?)|system prompt|prompt syst[èe]me|"
    r"you are now|tu es maintenant|<\s*/?\s*system|oublie (?:tes|les) (?:consignes|instructions)",
    re.IGNORECASE,
)


def clean_text(raw: str) -> str:
    """Retire balises, pseudonymes, caractères invisibles et espaces superflus."""
    text = _CONTROL.sub("", html.unescape(_TAGS.sub(" ", raw)))
    text = _HANDLES.sub("un membre", text)
    return re.sub(r"\s+", " ", text).strip()


def looks_like_injection(text: str) -> bool:
    """Repère les tentatives évidentes ; ce filtre ne suffit pas à lui seul."""
    return bool(_INJECTION.search(text))


def split_words(text: str, max_words: int, overlap: int) -> list[str]:
    """Découpe en fenêtres de mots qui se recouvrent."""
    if max_words <= overlap:
        raise ValueError("Le recouvrement doit être inférieur à la taille de fenêtre")
    words = text.split()
    if len(words) <= max_words:
        return [text] if text else []
    step = max_words - overlap
    return [
        " ".join(words[start : start + max_words]) for start in range(0, len(words) - overlap, step)
    ]


def make_chunks(
    ticker: str, source: str, doc_type: str, published_at: str, url: str, raw_text: str
) -> list[Chunk]:
    """Produit des passages à identifiant stable, ce qui rend l'indexation idempotente."""
    text = clean_text(raw_text)
    official = doc_type == "official"
    max_words = OFFICIAL_MAX_WORDS if official else COMMUNITY_MAX_WORDS
    overlap = OFFICIAL_OVERLAP if official else COMMUNITY_OVERLAP
    chunks = []
    for part in split_words(text, max_words, overlap):
        key = hashlib.sha256(f"{ticker}|{part}".encode()).hexdigest()[:24]
        chunks.append(
            Chunk(
                id=key,
                ticker=ticker,
                source=source,
                doc_type=doc_type,
                published_at=published_at,
                url=url,
                text=part,
                suspected_injection=looks_like_injection(part),
            )
        )
    return chunks


def deduplicate(chunks: list[Chunk]) -> list[Chunk]:
    """Garde une seule occurrence d'un même passage."""
    return list({chunk.id: chunk for chunk in chunks}.values())
