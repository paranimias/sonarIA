from pathlib import Path

import pytest
from core.resolver import resolve

SHARED = Path(__file__).parent / "fixtures" / "shared"
AGENT = Path(__file__).parent / "fixtures" / "agent"


@pytest.fixture
def cfg():
    return resolve(SHARED, AGENT)


def test_resolver_produces_effective_config(cfg):
    assert cfg.agent_id == "test-agent"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.max_tokens == 512
    assert cfg.conversation["window_size"] == 10


def test_resolver_handles_list(cfg):
    assert "text" in cfg.handles
    assert "audio" in cfg.handles


def test_system_blocks_contain_shared_prompt(cfg):
    texts = " ".join(b["text"] for b in cfg.system_blocks)
    assert "Eres un asistente de música" in texts


def test_system_blocks_contain_agent_prompt(cfg):
    texts = " ".join(b["text"] for b in cfg.system_blocks)
    assert "Bogotá" in texts


def test_system_blocks_contain_required_skill(cfg):
    texts = " ".join(b["text"] for b in cfg.system_blocks)
    assert "whatsapp-formatter" in texts


def test_last_system_block_has_cache_control(cfg):
    assert cfg.system_blocks[-1].get("cache_control") == {"type": "ephemeral"}


def test_tool_from_shared_present(cfg):
    names = [t.name for t in cfg.tool_defs]
    assert "user_lookup" in names


def test_tool_from_agent_present(cfg):
    names = [t.name for t in cfg.tool_defs]
    assert "recommend_events" in names


def test_tools_disabled_excludes_tool():
    import shutil
    import tempfile
    from pathlib import Path

    from core.resolver import resolve as _resolve

    with tempfile.TemporaryDirectory() as tmp:
        # Copy fixtures but add tools_disabled in agent.yaml
        import yaml

        agent_dir = Path(tmp) / "agent"
        agent_dir.mkdir()
        (agent_dir / "tools").mkdir()
        # Copy tool yaml
        shutil.copy(AGENT / "tools" / "recommend_events.yaml", agent_dir / "tools")
        shutil.copy(AGENT / "tools" / "recommend_events.py", agent_dir / "tools")
        (agent_dir / "tools" / "__init__.py").touch()
        # Write agent.yaml with tools_disabled
        with open(agent_dir / "agent.yaml", "w") as f:
            yaml.dump(
                {
                    "agent_id": "test",
                    "model": "gpt-4o-mini",
                    "tools_disabled": ["recommend_events"],
                },
                f,
            )

        cfg = _resolve(SHARED, agent_dir)
        names = [t.name for t in cfg.tool_defs]
        assert "recommend_events" not in names


def test_agent_tool_overrides_shared_tool(tmp_path):
    # Create a shared tool and an agent tool with the same name
    (tmp_path / "shared" / "tools").mkdir(parents=True)
    (tmp_path / "agent" / "tools").mkdir(parents=True)
    (tmp_path / "shared" / "tools" / "__init__.py").touch()
    (tmp_path / "agent" / "tools" / "__init__.py").touch()

    import yaml

    shared_handler = "tests.core.fixtures.shared.tools.user_lookup"
    agent_handler = "tests.core.fixtures.agent.tools.recommend_events"
    shared_yaml = {
        "name": "my_tool",
        "description": "shared version",
        "handler_module": shared_handler,
    }
    agent_yaml_tool = {
        "name": "my_tool",
        "description": "agent version",
        "handler_module": agent_handler,
    }

    with open(tmp_path / "shared" / "tools" / "my_tool.yaml", "w") as f:
        yaml.dump(shared_yaml, f)
    with open(tmp_path / "agent" / "tools" / "my_tool.yaml", "w") as f:
        yaml.dump(agent_yaml_tool, f)
    with open(tmp_path / "agent" / "agent.yaml", "w") as f:
        yaml.dump({"agent_id": "t", "model": "m"}, f)

    cfg = resolve(tmp_path / "shared", tmp_path / "agent")
    my_tool = next(t for t in cfg.tool_defs if t.name == "my_tool")
    assert my_tool.description == "agent version"
