"""Sources communautaires : aucun pseudonyme n'est conservé."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import requests

from communitylens.domain.models import Chunk
from communitylens.rag.chunking import make_chunks

_TIMEOUT = 15
_UA = "CommunityLens/0.1 (projet etudiant)"


class CommunitySource(Protocol):
    """Port d'une source de discussions."""

    name: str

    def fetch(self, ticker: str, company: str, since: datetime) -> list[Chunk]:
        """Renvoie les passages publiés depuis une date."""


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


class HackerNewsSource:
    """API publique Algolia de Hacker News, sans clé."""

    name = "Hacker News"
    URL = "https://hn.algolia.com/api/v1/search_by_date"

    def __init__(self, session=None, per_page: int = 50) -> None:
        self._session = session or requests.Session()
        self._per_page = per_page

    def fetch(self, ticker: str, company: str, since: datetime) -> list[Chunk]:
        """Renvoie les passages publiés depuis une date."""
        response = self._session.get(
            self.URL,
            params={
                "query": f"{company} stock",
                "tags": "(story,comment)",
                "numericFilters": f"created_at_i>{int(since.timestamp())}",
                "hitsPerPage": self._per_page,
            },
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        chunks: list[Chunk] = []
        for hit in response.json().get("hits", []):
            body = " ".join(
                part
                for part in (
                    hit.get("title"),
                    hit.get("story_text"),
                    hit.get("comment_text"),
                )
                if part
            )
            url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
            chunks += make_chunks(
                ticker, self.name, "community", _iso(hit["created_at_i"]), url, body
            )
        return chunks


class RedditSource:
    """API Reddit par OAuth. À n'activer qu'après accord explicite de Reddit."""

    name = "Reddit"
    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"  # nosec B105
    SEARCH_URL = "https://oauth.reddit.com/r/{subreddit}/search"

    def __init__(
        self, client_id: str, client_secret: str, subreddits=("stocks", "investing"), session=None
    ) -> None:
        self._auth = (client_id, client_secret)
        self._subreddits = subreddits
        self._session = session or requests.Session()

    def _token(self) -> str:
        response = self._session.post(
            self.TOKEN_URL,
            auth=self._auth,
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def fetch(self, ticker: str, company: str, since: datetime) -> list[Chunk]:
        """Renvoie les passages publiés depuis une date."""
        headers = {"Authorization": f"bearer {self._token()}", "User-Agent": _UA}
        chunks: list[Chunk] = []
        for subreddit in self._subreddits:
            response = self._session.get(
                self.SEARCH_URL.format(subreddit=subreddit),
                params={
                    "q": f"{ticker} OR {company}",
                    "restrict_sr": 1,
                    "sort": "new",
                    "limit": 50,
                },
                headers=headers,
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            for child in response.json()["data"]["children"]:
                post = child["data"]
                if post["created_utc"] < since.timestamp():
                    continue
                url = f"https://www.reddit.com{post['permalink']}"
                body = f"{post.get('title', '')} {post.get('selftext', '')}"
                chunks += make_chunks(
                    ticker, self.name, "community", _iso(post["created_utc"]), url, body
                )
        return chunks


class LocalFileSource:
    """Lit un fichier JSONL, utilisé pour la démo locale avec des messages fictifs."""

    name = "Exemple fictif"

    def __init__(self, path: str) -> None:
        self._records = [
            json.loads(line)
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def fetch(self, ticker: str, company: str, since: datetime) -> list[Chunk]:
        """Renvoie les passages publiés depuis une date."""
        del company
        chunks: list[Chunk] = []
        for record in self._records:
            published = datetime.fromisoformat(record["published_at"]).replace(tzinfo=timezone.utc)
            if record["ticker"] == ticker and published >= since:
                chunks += make_chunks(
                    ticker, self.name, "community", record["published_at"], "", record["text"]
                )
        return chunks
