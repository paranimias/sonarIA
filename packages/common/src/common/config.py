from pathlib import Path

import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_agent_config(agent_dir: str | Path) -> dict:
    return load_yaml(Path(agent_dir) / "agent.yaml")


def load_stages_config(config_dir: str | Path) -> dict:
    return load_yaml(Path(config_dir) / "stages.yaml")
