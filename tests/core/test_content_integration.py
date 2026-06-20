"""Integration test: resolver loads the real agent/ + shared/ content."""

from pathlib import Path

import pytest
from core.resolver import resolve

REPO_ROOT = Path(__file__).parent.parent.parent
SHARED = REPO_ROOT / "shared"
AGENT = REPO_ROOT / "agent"


@pytest.fixture(scope="module")
def cfg():
    return resolve(SHARED, AGENT)


def test_agent_id(cfg):
    assert cfg.agent_id == "sonaria-bogota"


def test_model_set(cfg):
    assert cfg.model  # non-empty


def test_handles_include_text(cfg):
    assert "text" in cfg.handles


def test_system_blocks_non_empty(cfg):
    assert len(cfg.system_blocks) > 0


def test_system_prompt_contains_sonaria(cfg):
    full_text = " ".join(b["text"] for b in cfg.system_blocks)
    assert "SonarIA" in full_text or "Bogotá" in full_text


def test_whatsapp_formatter_skill_included(cfg):
    full_text = " ".join(b["text"] for b in cfg.system_blocks)
    assert "whatsapp-formatter" in full_text or "WhatsApp" in full_text


def test_recommend_events_tool_present(cfg):
    names = {t.name for t in cfg.tool_defs}
    assert "recommend_events" in names


def test_recommend_music_tool_present(cfg):
    names = {t.name for t in cfg.tool_defs}
    assert "recommend_music" in names


def test_user_lookup_tool_present(cfg):
    names = {t.name for t in cfg.tool_defs}
    assert "user_lookup" in names


def test_tool_handles_are_callable(cfg):
    for tool in cfg.tool_defs:
        assert callable(tool.handle), f"handle not callable for {tool.name}"


def test_stub_tools_return_ok(cfg):
    from unittest.mock import MagicMock, patch

    tool_map = {t.name: t for t in cfg.tool_defs}

    # recommend_events queries DynamoDB — mock the table
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    with patch("agent.tools.recommend_events.get_table", return_value=mock_table):
        result = tool_map["recommend_events"].handle({}, ctx={})
    assert result["ok"] is True

    # recommend_music requires artist/genre + API key — verify it returns a structured response
    result_music = tool_map["recommend_music"].handle({}, ctx={})
    assert "ok" in result_music
