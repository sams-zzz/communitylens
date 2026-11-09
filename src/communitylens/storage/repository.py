"""Dépôt applicatif : prévisions, analyses et votes."""

from __future__ import annotations

from typing import Protocol

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from communitylens.domain.models import Analysis, Forecast
from communitylens.storage.objects import ObjectStore


class Repository(Protocol):
    """Port de persistance."""

    def put_forecast(self, forecast: Forecast) -> None:
        """Enregistre une prévision et met à jour la liste des titres."""

    def latest_forecast(self, ticker: str) -> Forecast | None:
        """Renvoie la dernière prévision d'un titre."""

    def tickers(self) -> list[str]:
        """Liste les titres couverts."""

    def put_analysis(self, analysis: Analysis) -> None:
        """Enregistre une analyse figée."""

    def get_analysis(self, analysis_id: str) -> Analysis | None:
        """Relit une analyse par son identifiant."""

    def cached_analysis(self, ticker: str, as_of: str) -> Analysis | None:
        """Renvoie l'analyse déjà produite pour ce titre et cette date."""

    def add_vote(self, analysis_id: str, token: str, useful: bool) -> bool:
        """Ajoute un vote ; False si ce jeton a déjà voté."""

    def vote_counts(self, analysis_id: str) -> dict[str, int]:
        """Renvoie les totaux de votes."""


class LocalRepository:
    """Dépôt fondé sur le stockage objet, pour le développement et la démo."""

    def __init__(self, store: ObjectStore) -> None:
        self._store = store

    def put_forecast(self, forecast: Forecast) -> None:
        self._store.put_json(f"repo/forecast/{forecast.ticker}.json", forecast.model_dump())
        known = set(self.tickers()) | {forecast.ticker}
        self._store.put_json("repo/tickers.json", sorted(known))

    def latest_forecast(self, ticker: str) -> Forecast | None:
        payload = self._store.get_json(f"repo/forecast/{ticker}.json")
        return None if payload is None else Forecast.model_validate(payload)

    def tickers(self) -> list[str]:
        return self._store.get_json("repo/tickers.json") or []

    def put_analysis(self, analysis: Analysis) -> None:
        self._store.put_json(f"repo/analysis/{analysis.id}.json", analysis.model_dump())
        key = f"repo/cache/{analysis.ticker}/{analysis.forecast.as_of}.json"
        self._store.put_json(key, {"id": analysis.id})

    def get_analysis(self, analysis_id: str) -> Analysis | None:
        payload = self._store.get_json(f"repo/analysis/{analysis_id}.json")
        return None if payload is None else Analysis.model_validate(payload)

    def cached_analysis(self, ticker: str, as_of: str) -> Analysis | None:
        pointer = self._store.get_json(f"repo/cache/{ticker}/{as_of}.json")
        return None if pointer is None else self.get_analysis(pointer["id"])

    def add_vote(self, analysis_id: str, token: str, useful: bool) -> bool:
        """Ajoute un vote si ce jeton n'a pas encore voté."""
        key = f"repo/votes/{analysis_id}.json"
        votes = self._store.get_json(key) or {}
        if token in votes:
            return False
        votes[token] = useful
        self._store.put_json(key, votes)
        return True

    def vote_counts(self, analysis_id: str) -> dict[str, int]:
        """Compte les votes enregistrés pour cette analyse."""
        votes = self._store.get_json(f"repo/votes/{analysis_id}.json") or {}
        useful = sum(1 for value in votes.values() if value)
        return {"useful": useful, "not_useful": len(votes) - useful}


class DynamoRepository:
    """Table unique : pk et sk ; chaque document est stocké en JSON."""

    def __init__(self, table) -> None:
        self._table = table

    def put_forecast(self, forecast: Forecast) -> None:
        """Écrit la dernière prévision et référence le titre."""
        self._table.put_item(
            Item={
                "pk": f"TICKER#{forecast.ticker}",
                "sk": "FORECAST#LATEST",
                "entity": "forecast",
                "doc": forecast.model_dump_json(),
            }
        )
        self._table.put_item(Item={"pk": "TICKERS", "sk": forecast.ticker})

    def latest_forecast(self, ticker: str) -> Forecast | None:
        item = self._table.get_item(Key={"pk": f"TICKER#{ticker}", "sk": "FORECAST#LATEST"}).get(
            "Item"
        )
        return None if item is None else Forecast.model_validate_json(item["doc"])

    def tickers(self) -> list[str]:
        response = self._table.query(KeyConditionExpression=Key("pk").eq("TICKERS"))
        return sorted(item["sk"] for item in response.get("Items", []))

    def put_analysis(self, analysis: Analysis) -> None:
        self._table.put_item(
            Item={"pk": f"ANALYSIS#{analysis.id}", "sk": "DOC", "doc": analysis.model_dump_json()}
        )
        self._table.put_item(
            Item={
                "pk": f"TICKER#{analysis.ticker}",
                "sk": f"CACHE#{analysis.forecast.as_of}",
                "analysis_id": analysis.id,
            }
        )

    def get_analysis(self, analysis_id: str) -> Analysis | None:
        item = self._table.get_item(Key={"pk": f"ANALYSIS#{analysis_id}", "sk": "DOC"}).get("Item")
        return None if item is None else Analysis.model_validate_json(item["doc"])

    def cached_analysis(self, ticker: str, as_of: str) -> Analysis | None:
        item = self._table.get_item(Key={"pk": f"TICKER#{ticker}", "sk": f"CACHE#{as_of}"}).get(
            "Item"
        )
        return None if item is None else self.get_analysis(item["analysis_id"])

    def add_vote(self, analysis_id: str, token: str, useful: bool) -> bool:
        """Écriture conditionnelle : un seul vote par jeton, même en concurrence."""
        try:
            self._table.put_item(
                Item={"pk": f"ANALYSIS#{analysis_id}", "sk": f"VOTE#{token}", "useful": useful},
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def vote_counts(self, analysis_id: str) -> dict[str, int]:
        response = self._table.query(
            KeyConditionExpression=Key("pk").eq(f"ANALYSIS#{analysis_id}")
            & Key("sk").begins_with("VOTE#")
        )
        items = response.get("Items", [])
        useful = sum(1 for item in items if item["useful"])
        return {"useful": useful, "not_useful": len(items) - useful}
