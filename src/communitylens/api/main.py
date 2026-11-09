"""API HTTP : FastAPI sur EC2 ou sur Lambda via le Web Adapter, sans changer le code."""

from __future__ import annotations


import os

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from communitylens import __version__
from communitylens.config import Settings
from communitylens.domain.models import Analysis
from communitylens.domain.tickers import company_name
from communitylens.observability import configure_logging
from communitylens.services import AnalysisService, Services, UnknownTicker, build_services

_TICKER = r"^[A-Z][A-Z0-9.\-]{0,9}$"
_ANALYSIS_ID = r"^[0-9a-f]{32}$"


class VoteRequest(BaseModel):
    """Vote anonyme : le jeton est généré dans le navigateur."""

    token: str = Field(pattern=r"^[A-Za-z0-9\-]{8,64}$")
    useful: bool


def create_app(services: Services) -> FastAPI:
    """Construit l'application à partir de ses dépendances."""
    app = FastAPI(title="CommunityLens", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[services.settings.cors_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    analyses = AnalysisService(services)

    @app.get("/health")
    def health() -> dict:
        """Indique que le service répond."""
        return {"status": "ok", "version": __version__}

    @app.get("/v1/tickers")
    def tickers() -> list[dict]:
        """Liste les titres couverts."""
        return [
            {"ticker": ticker, "company": company_name(ticker)}
            for ticker in services.repository.tickers()
        ]

    @app.get("/v1/tickers/{ticker}/analysis")
    def analysis(ticker: str = Path(pattern=_TICKER)) -> Analysis:
        """Renvoie l'analyse du jour pour un titre."""
        try:
            return analyses.analyze(ticker)
        except UnknownTicker as error:
            raise HTTPException(404, f"Le titre {ticker} n'est pas suivi.") from error

    @app.get("/v1/tickers/{ticker}/history")
    def history(ticker: str = Path(pattern=_TICKER)) -> list[dict]:
        """Renvoie prévisions, intervalles et volatilité réalisée des derniers mois."""
        payload = services.store.get_json(f"serving/history/{ticker}.json")
        if payload is None:
            raise HTTPException(404, f"Aucun historique pour {ticker}.")
        return payload

    @app.get("/v1/analyses/{analysis_id}")
    def shared_analysis(analysis_id: str = Path(pattern=_ANALYSIS_ID)) -> Analysis:
        """Relit une analyse figée, pour le lien de partage."""
        found = services.repository.get_analysis(analysis_id)
        if found is None:
            raise HTTPException(404, "Cette analyse n'existe pas.")
        return found

    @app.get("/v1/analyses/{analysis_id}/votes")
    def votes(analysis_id: str = Path(pattern=_ANALYSIS_ID)) -> dict:
        """Renvoie les totaux de votes."""
        return services.repository.vote_counts(analysis_id)

    @app.post("/v1/analyses/{analysis_id}/votes", status_code=201)
    def vote(request: VoteRequest, analysis_id: str = Path(pattern=_ANALYSIS_ID)) -> dict:
        """Enregistre un vote par jeton et par analyse."""
        if services.repository.get_analysis(analysis_id) is None:
            raise HTTPException(404, "Cette analyse n'existe pas.")
        if not services.repository.add_vote(analysis_id, request.token, request.useful):
            raise HTTPException(409, "Ce navigateur a déjà voté pour cette analyse.")
        return services.repository.vote_counts(analysis_id)

    @app.get("/v1/metrics")
    def metrics() -> dict:
        """Publie les résultats d'évaluation du modèle."""
        payload = services.store.get_json("serving/metrics.json")
        if payload is None:
            raise HTTPException(404, "Aucune évaluation publiée.")
        return payload

    static_dir = os.environ.get("CL_STATIC_DIR")
    if static_dir:
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


def build_app() -> FastAPI:
    """Fabrique utilisée par uvicorn : `uvicorn --factory communitylens.api.main:build_app`."""
    configure_logging()
    return create_app(build_services(Settings.from_env()))
