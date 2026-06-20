from unittest.mock import MagicMock, patch

import pytest


def _make_table(items: list[dict]) -> MagicMock:
    table = MagicMock()
    table.query.return_value = {"Items": items}
    return table


SAMPLE_EVENTS = [
    {
        "title": "Rock al Parque",
        "date": "2026-07-15",
        "venue": "Simón Bolívar",
        "source": "tuboleta",
        "url": "http://t.co/1",
    },
    {
        "title": "Fonseca Live",
        "date": "2026-08-01",
        "venue": "Movistar Arena",
        "source": "ticketmaster",
        "url": "http://t.co/2",
    },
    {
        "title": "Jazz en el Parque",
        "date": "2026-07-20",
        "venue": "Parque El Country",
        "source": "bogota_gov",
        "url": "http://t.co/3",
    },
]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SONARIA_TABLE_NAME", "sonaria-test")


def test_handle_returns_all_events():
    from agent.tools.recommend_events import handle

    with patch("agent.tools.recommend_events.get_table", return_value=_make_table(SAMPLE_EVENTS)):
        result = handle({}, ctx={})

    assert result["ok"] is True
    assert len(result["events"]) == 3


def test_handle_filters_by_artist():
    from agent.tools.recommend_events import handle

    with patch("agent.tools.recommend_events.get_table", return_value=_make_table(SAMPLE_EVENTS)):
        result = handle({"artist": "fonseca"}, ctx={})

    assert len(result["events"]) == 1
    assert result["events"][0]["title"] == "Fonseca Live"


def test_handle_filters_by_genre():
    from agent.tools.recommend_events import handle

    with patch("agent.tools.recommend_events.get_table", return_value=_make_table(SAMPLE_EVENTS)):
        result = handle({"genre": "jazz"}, ctx={})

    assert len(result["events"]) == 1
    assert "Jazz" in result["events"][0]["title"]


def test_handle_empty_db_returns_note():
    from agent.tools.recommend_events import handle

    with patch("agent.tools.recommend_events.get_table", return_value=_make_table([])):
        result = handle({}, ctx={})

    assert result["ok"] is True
    assert result["total_found"] == 0
    assert result["note"] is not None


def test_handle_limits_to_12():
    from agent.tools.recommend_events import handle

    many = [
        {"title": f"Evento {i}", "source": "tuboleta", "url": f"http://x.co/{i}"} for i in range(20)
    ]
    with patch("agent.tools.recommend_events.get_table", return_value=_make_table(many)):
        result = handle({}, ctx={})

    assert len(result["events"]) <= 12
