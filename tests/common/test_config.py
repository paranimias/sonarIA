import pytest
from pathlib import Path

from common.config import load_yaml, load_agent_config, load_stages_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_yaml_basic(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("key: value\nnumber: 42\n")
    result = load_yaml(f)
    assert result == {"key": "value", "number": 42}


def test_load_yaml_empty(tmp_path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    assert load_yaml(f) == {}


def test_load_agent_config(tmp_path):
    (tmp_path / "agent.yaml").write_text("agent_id: sonaria-bogota\nversion: 0.1.0\n")
    cfg = load_agent_config(tmp_path)
    assert cfg["agent_id"] == "sonaria-bogota"
    assert cfg["version"] == "0.1.0"


def test_load_stages_config(tmp_path):
    (tmp_path / "stages.yaml").write_text(
        "staging:\n  dynamo:\n    billing_mode: PAY_PER_REQUEST\n"
    )
    cfg = load_stages_config(tmp_path)
    assert cfg["staging"]["dynamo"]["billing_mode"] == "PAY_PER_REQUEST"


def test_load_yaml_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_yaml("/nonexistent/path.yaml")
