from datetime import datetime, timezone

import pandas as pd
import pytest

from communitylens.ingestion import prices as price_module
from communitylens.ingestion.community import HackerNewsSource, LocalFileSource, RedditSource
from communitylens.ingestion.edgar import EdgarSource
from communitylens.ingestion.prices import (
    PriceDataError,
    download_prices,
    load_prices,
    save_prices,
    validate_prices,
)
from communitylens.storage.objects import LocalObjectStore


class FakeResponse:
    def __init__(self, payload=None, text=""):
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        for pattern, response in self.routes.items():
            if pattern in url:
                return response
        raise AssertionError(url)

    def post(self, url, **kwargs):
        return self.get(url, **kwargs)


def _row(**changes):
    row = {
        "date": "2020-01-02",
        "ticker": "A",
        "open": 1,
        "high": 2,
        "low": 1,
        "close": 1.5,
        "volume": 10,
    }
    return {**row, **changes}


def test_impossible_rows_and_duplicates_are_removed():
    frame = pd.DataFrame(
        [_row(), _row(), _row(date="2020-01-03", close=-1), _row(date="2020-01-06", high=0.5)]
    )
    assert len(validate_prices(frame)) == 1


def test_missing_columns_and_empty_data_are_refused():
    with pytest.raises(PriceDataError):
        validate_prices(pd.DataFrame([{"date": "2020-01-02"}]))
    with pytest.raises(PriceDataError):
        validate_prices(pd.DataFrame([_row(close=-1)]))


def _yahoo_frame():
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date")
    columns = pd.MultiIndex.from_tuples(
        [(name, "AAA") for name in ("Open", "High", "Low", "Close", "Volume")]
    )
    return pd.DataFrame([[1, 2, 1, 1.5, 9], [1, 2, 1, 1.6, 9]], index=index, columns=columns)


def test_download_drops_todays_incomplete_bar_and_reports_failures(monkeypatch):
    import yfinance

    def fake_download(ticker, **_):
        if ticker == "BAD":
            raise RuntimeError("rate limited")
        if ticker == "EMPTY":
            return pd.DataFrame()
        return _yahoo_frame()

    monkeypatch.setattr(yfinance, "download", fake_download)
    now = datetime(2024, 1, 3, 15, tzinfo=timezone.utc)
    frame, failures = download_prices(["AAA", "BAD", "EMPTY"], now=now)
    assert failures == ["BAD", "EMPTY"]
    assert frame["date"].dt.date.astype(str).tolist() == ["2024-01-02"]


def test_download_fails_when_nothing_is_available(monkeypatch):
    import yfinance

    monkeypatch.setattr(yfinance, "download", lambda *_, **__: pd.DataFrame())
    with pytest.raises(PriceDataError):
        download_prices(["AAA"])


def test_prices_round_trip(tmp_path, prices):
    store = LocalObjectStore(str(tmp_path))
    assert load_prices(store) is None
    save_prices(store, prices)
    assert len(load_prices(store)) == len(prices)


def test_hacker_news_keeps_no_author():
    payload = {
        "hits": [
            {
                "objectID": "42",
                "created_at_i": 1517900000,
                "title": "Apple stock falls",
                "author": "secret_user",
                "story_text": None,
                "comment_text": "<p>Big move</p>",
            }
        ]
    }
    session = FakeSession({"hn.algolia.com": FakeResponse(payload)})
    since = datetime(2018, 1, 1, tzinfo=timezone.utc)
    chunks = HackerNewsSource(session=session).fetch("AAPL", "Apple", since)
    assert chunks[0].text == "Apple stock falls Big move"
    assert "secret_user" not in chunks[0].model_dump_json()
    assert chunks[0].url.endswith("id=42")
    params = session.calls[0][1]["params"]
    assert params["query"] == "Apple stock"
    assert str(int(since.timestamp())) in params["numericFilters"]


def test_reddit_filters_old_posts():
    posts = {
        "data": {
            "children": [
                {
                    "data": {
                        "created_utc": 1517900000,
                        "permalink": "/r/x/1",
                        "title": "Apple",
                        "selftext": "up",
                    }
                },
                {
                    "data": {
                        "created_utc": 1000,
                        "permalink": "/r/x/2",
                        "title": "Ancien",
                        "selftext": "",
                    }
                },
            ]
        }
    }
    session = FakeSession(
        {
            "access_token": FakeResponse({"access_token": "t"}),
            "oauth.reddit.com": FakeResponse(posts),
        }
    )
    source = RedditSource("id", "secret", subreddits=("stocks",), session=session)
    chunks = source.fetch("AAPL", "Apple", datetime(2018, 1, 1, tzinfo=timezone.utc))
    assert len(chunks) == 1 and chunks[0].url == "https://www.reddit.com/r/x/1"


def test_local_file_source(tmp_path):
    path = tmp_path / "posts.jsonl"
    path.write_text(
        '{"ticker":"AAPL","published_at":"2018-02-06","text":"Récent"}\n'
        '{"ticker":"AAPL","published_at":"2017-02-06","text":"Ancien"}\n',
        encoding="utf-8",
    )
    chunks = LocalFileSource(str(path)).fetch(
        "AAPL", "Apple", datetime(2018, 1, 1, tzinfo=timezone.utc)
    )
    assert [chunk.text for chunk in chunks] == ["Récent"]


def _edgar_routes():
    return {
        "company_tickers": FakeResponse({"0": {"ticker": "AAPL", "cik_str": 320193}}),
        "submissions": FakeResponse(
            {
                "filings": {
                    "recent": {
                        "form": ["4", "10-Q", "8-K", "10-K"],
                        "filingDate": ["2018-02-05", "2018-02-02", "2018-02-01", "2017-11-03"],
                        "accessionNumber": ["a-1", "0000-18-1", "0000-18-2", "0000-17-3"],
                        "primaryDocument": ["x.xml", "q.htm", "k.htm", "y.htm"],
                    }
                }
            }
        ),
        "Archives": FakeResponse(text="<html>Risk factors for the quarter</html>"),
    }


def test_edgar_keeps_recent_reports_only(monkeypatch):
    monkeypatch.setattr("communitylens.ingestion.edgar.time.sleep", lambda _: None)
    session = FakeSession(_edgar_routes())
    chunks = EdgarSource("Equipe contact@example.org", session=session).fetch("AAPL", "2018-01-15")
    assert {chunk.source for chunk in chunks} == {"SEC 10-Q", "SEC 8-K"}
    assert chunks[0].doc_type == "official" and "Risk factors" in chunks[0].text
    assert session.calls[0][1]["headers"]["User-Agent"].startswith("Equipe")


def test_edgar_requires_a_user_agent_and_handles_unknown_ticker(monkeypatch):
    monkeypatch.setattr("communitylens.ingestion.edgar.time.sleep", lambda _: None)
    with pytest.raises(ValueError):
        EdgarSource("")
    source = EdgarSource("Equipe a@b.c", session=FakeSession(_edgar_routes()))
    assert source.fetch("ZZZ", "2018-01-01") == []
