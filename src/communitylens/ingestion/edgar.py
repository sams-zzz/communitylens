"""Rapports officiels SEC EDGAR : limite de 10 requêtes par seconde et User-Agent déclaré."""

from __future__ import annotations

import time

import requests

from communitylens.domain.models import Chunk
from communitylens.rag.chunking import clean_text, make_chunks

_TIMEOUT = 20
_DELAY_SECONDS = 0.12
FORMS = {"10-K", "10-Q", "8-K"}
MAX_CHARS = 60_000


class EdgarSource:
    """Récupère les derniers rapports d'une société cotée aux États-Unis."""

    name = "SEC EDGAR"
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
    DOCUMENT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

    def __init__(self, user_agent: str, session=None, max_documents: int = 3) -> None:
        if not user_agent:
            raise ValueError("La SEC exige un User-Agent avec une adresse de contact")
        self._headers = {"User-Agent": user_agent}
        self._session = session or requests.Session()
        self._max_documents = max_documents
        self._ciks: dict[str, int] = {}

    def _get(self, url: str):
        time.sleep(_DELAY_SECONDS)
        response = self._session.get(url, headers=self._headers, timeout=_TIMEOUT)
        response.raise_for_status()
        return response

    def _cik(self, ticker: str) -> int | None:
        if not self._ciks:
            rows = self._get(self.TICKERS_URL).json().values()
            self._ciks = {row["ticker"]: int(row["cik_str"]) for row in rows}
        return self._ciks.get(ticker)

    def fetch(self, ticker: str, since_date: str) -> list[Chunk]:
        """Renvoie les passages des rapports déposés depuis une date ISO."""
        cik = self._cik(ticker)
        if cik is None:
            return []
        recent = self._get(self.SUBMISSIONS_URL.format(cik=cik)).json()["filings"]["recent"]
        chunks: list[Chunk] = []
        count = 0
        rows = zip(
            recent["form"],
            recent["filingDate"],
            recent["accessionNumber"],
            recent["primaryDocument"],
        )
        for form, filed, accession, document in rows:
            if form not in FORMS or filed < since_date or count >= self._max_documents:
                continue
            url = self.DOCUMENT_URL.format(
                cik=cik, accession=accession.replace("-", ""), document=document
            )
            text = clean_text(self._get(url).text)[:MAX_CHARS]
            chunks += make_chunks(ticker, f"SEC {form}", "official", filed, url, text)
            count += 1
        return chunks
