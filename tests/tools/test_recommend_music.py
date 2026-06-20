from unittest.mock import MagicMock, patch

import pytest

from agent.tools.recommend_music import (
    _artist_top_tracks,
    _similar_artists,
    _tag_top_artists,
    _tag_top_tracks,
    handle,
)


@pytest.fixture
def mock_client():
    return MagicMock()


def _resp(data: dict) -> MagicMock:
    r = MagicMock()
    r.json.return_value = data
    r.raise_for_status = MagicMock()
    return r


# ── handle ────────────────────────────────────────────────────────────────────


def test_handle_missing_api_key(monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    result = handle({"artist": "Shakira"}, ctx={})
    assert result["ok"] is False
    assert "LASTFM_API_KEY" in result["error"]


def test_handle_no_inputs(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "testkey")
    result = handle({}, ctx={})
    assert result["ok"] is False


def test_handle_artist_calls_lastfm(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "testkey")
    similar_resp = {
        "similarartists": {
            "artist": [{"name": "Carlos Vives", "match": "0.9", "url": "http://last.fm/cv"}]
        }
    }
    top_resp = {
        "toptracks": {
            "track": [
                {"name": "La Bicicleta", "artist": {"name": "Shakira"}, "url": "http://last.fm/t"}
            ]
        }
    }

    with patch("agent.tools.recommend_music.httpx.Client") as mock_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = [_resp(similar_resp), _resp(top_resp)]
        mock_cls.return_value = mock_client

        result = handle({"artist": "Shakira"}, ctx={})

    assert result["ok"] is True
    assert result["similar_artists"][0]["name"] == "Carlos Vives"
    assert result["similar_artists"][0]["match_pct"] == 90
    assert result["top_tracks"][0]["title"] == "La Bicicleta"


def test_handle_genre_calls_lastfm(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "testkey")
    artists_resp = {"topartists": {"artist": [{"name": "Systema Solar", "url": ""}]}}
    tracks_resp = {"tracks": {"track": [{"name": "Track1", "artist": {"name": "A"}, "url": ""}]}}

    with patch("agent.tools.recommend_music.httpx.Client") as mock_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = [_resp(artists_resp), _resp(tracks_resp)]
        mock_cls.return_value = mock_client

        result = handle({"genre": "cumbia"}, ctx={})

    assert result["ok"] is True
    assert result["top_artists"][0]["name"] == "Systema Solar"
    assert result["top_tracks_by_genre"][0]["title"] == "Track1"


# ── helpers ───────────────────────────────────────────────────────────────────


def test_similar_artists_returns_empty_on_error(mock_client):
    mock_client.get.side_effect = Exception("timeout")
    result = _similar_artists(mock_client, "key", "Artist")
    assert result == []


def test_artist_top_tracks_returns_empty_on_error(mock_client):
    mock_client.get.side_effect = Exception("timeout")
    result = _artist_top_tracks(mock_client, "key", "Artist")
    assert result == []


def test_tag_top_artists_returns_empty_on_error(mock_client):
    mock_client.get.side_effect = Exception("timeout")
    result = _tag_top_artists(mock_client, "key", "jazz")
    assert result == []


def test_tag_top_tracks_returns_empty_on_error(mock_client):
    mock_client.get.side_effect = Exception("timeout")
    result = _tag_top_tracks(mock_client, "key", "jazz")
    assert result == []
