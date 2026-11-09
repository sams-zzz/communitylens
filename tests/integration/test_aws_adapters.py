"""Adaptateurs S3 et DynamoDB, testés sur le simulateur moto."""

import boto3
import pytest
from moto import mock_aws

from communitylens.domain.models import Analysis, Explanation, Generation
from communitylens.storage.objects import LocalObjectStore, S3ObjectStore
from communitylens.storage.repository import DynamoRepository, LocalRepository

REGION = "eu-west-3"


@pytest.fixture(name="dynamo")
def dynamo_fixture(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name=REGION)
        table = resource.create_table(
            TableName="t",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoRepository(table)


@pytest.fixture(name="local_repo")
def local_repo_fixture(tmp_path):
    return LocalRepository(LocalObjectStore(str(tmp_path)))


def _analysis(forecast, key="a" * 32) -> Analysis:
    return Analysis(
        id=key,
        ticker=forecast.ticker,
        company="Apple",
        created_at="2018-02-08T00:00:00+00:00",
        forecast=forecast,
        facts=[],
        explanation=Explanation(summary="s", claims=[], limits="l"),
        passages=[],
        generation=Generation(
            generator="demo", prompt_version="v1", attempts=1, fallback_used=False
        ),
    )


@pytest.mark.parametrize("name", ["dynamo", "local_repo"])
def test_repository_contract(name, request, forecast):
    """Les deux implémentations doivent se comporter à l'identique."""
    repo = request.getfixturevalue(name)
    assert repo.latest_forecast("AAPL") is None and repo.tickers() == []
    repo.put_forecast(forecast)
    assert repo.latest_forecast("AAPL") == forecast
    assert repo.tickers() == ["AAPL"]

    analysis = _analysis(forecast)
    assert repo.cached_analysis("AAPL", forecast.as_of) is None
    repo.put_analysis(analysis)
    assert repo.get_analysis(analysis.id) == analysis
    assert repo.cached_analysis("AAPL", forecast.as_of) == analysis
    assert repo.get_analysis("b" * 32) is None

    assert repo.add_vote(analysis.id, "token-1", True) is True
    assert repo.add_vote(analysis.id, "token-1", False) is False
    assert repo.add_vote(analysis.id, "token-2", False) is True
    assert repo.vote_counts(analysis.id) == {"useful": 1, "not_useful": 1}


def test_s3_store(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(
            Bucket="bucket-test", CreateBucketConfiguration={"LocationConstraint": REGION}
        )
        store = S3ObjectStore(client, "bucket-test")
        assert store.get_bytes("absent") is None
        store.put_json("x/y.json", {"é": 1})
        assert store.get_json("x/y.json") == {"é": 1}


def test_local_store_refuses_path_traversal(tmp_path):
    store = LocalObjectStore(str(tmp_path))
    with pytest.raises(ValueError):
        store.put_bytes("../sortie.txt", b"x")
