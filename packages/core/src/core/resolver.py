from pathlib import Path

import yaml

from .tools import load_tools
from .types import EffectiveConfig

_DEFAULTS = {
    "conversation": {"window_size": 20, "ttl_hours": 72},
    "max_tokens": 1024,
    "handles": ["text"],
    "default_tools": [],
    "tools_disabled": [],
    "required_skills_from_shared": [],
}


def resolve(shared_dir: str | Path, agent_dir: str | Path) -> EffectiveConfig:
    """Merge shared/ + agent/ into an immutable EffectiveConfig."""
    shared_dir = Path(shared_dir)
    agent_dir = Path(agent_dir)

    agent_cfg = _load_yaml(agent_dir / "agent.yaml")

    system_blocks = _merge_prompts(shared_dir, agent_dir, agent_cfg)
    tool_defs = load_tools(shared_dir, agent_dir, agent_cfg)

    conv = agent_cfg.get("conversation", _DEFAULTS["conversation"])
    handles = agent_cfg.get("handles", _DEFAULTS["handles"])

    return EffectiveConfig(
        agent_id=agent_cfg["agent_id"],
        model=agent_cfg["model"],
        system_blocks=system_blocks,
        tool_defs=tool_defs,
        conversation=conv,
        max_tokens=agent_cfg.get("max_tokens", _DEFAULTS["max_tokens"]),
        handles=handles,
    )


# --- internals ---


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text().strip()


def _load_skills(skills_dir: Path) -> dict[str, str]:
    """Return {skill_id: content} from a skills/ directory."""
    result: dict[str, str] = {}
    if not skills_dir.exists():
        return result
    for md in sorted(skills_dir.glob("*.md")):
        result[md.stem] = md.read_text().strip()
    return result


def _merge_prompts(shared_dir: Path, agent_dir: Path, agent_cfg: dict) -> list[dict]:
    """Build system prompt blocks: shared prompt + shared skills + agent prompt + agent skills."""
    blocks: list[dict] = []

    shared_prompt = _read_text(shared_dir / "prompt.md")
    if shared_prompt:
        blocks.append({"type": "text", "text": f"# Global\n\n{shared_prompt}"})

    required_skills = set(agent_cfg.get("required_skills_from_shared", []))
    shared_skills = _load_skills(shared_dir / "skills")
    for skill_id, content in shared_skills.items():
        if not required_skills or skill_id in required_skills:
            blocks.append({"type": "text", "text": f"## Skill: {skill_id}\n\n{content}"})

    agent_prompt = _read_text(agent_dir / "prompt.md")
    if agent_prompt:
        blocks.append({"type": "text", "text": f"# Agent\n\n{agent_prompt}"})

    agent_skills = _load_skills(agent_dir / "skills")
    for skill_id, content in agent_skills.items():
        blocks.append({"type": "text", "text": f"## Skill: {skill_id}\n\n{content}"})

    # Mark the last block as cacheable if there are any blocks
    if blocks:
        blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}

    return blocks
