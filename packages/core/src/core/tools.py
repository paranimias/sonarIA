import importlib
import json
from pathlib import Path

import yaml

from .types import ToolCall, ToolDef


def load_tools(shared_dir: Path, agent_dir: Path, agent_cfg: dict) -> list[ToolDef]:
    """Load and merge tool definitions from shared/ and agent/ directories.

    agent tools override shared tools with the same name.
    tools_disabled are excluded from the result.
    """
    disabled = set(agent_cfg.get("tools_disabled", []))

    shared_tools = _load_from_dir(shared_dir / "tools")
    agent_tools = _load_from_dir(agent_dir / "tools")

    merged: dict[str, ToolDef] = {**shared_tools, **agent_tools}  # agent wins

    return [t for name, t in merged.items() if name not in disabled]


def _load_from_dir(tools_dir: Path) -> dict[str, ToolDef]:
    result: dict[str, ToolDef] = {}
    if not tools_dir.exists():
        return result

    for yaml_path in sorted(tools_dir.glob("*.yaml")):
        with open(yaml_path) as f:
            schema = yaml.safe_load(f) or {}

        name = schema.get("name", yaml_path.stem)
        handler_module = schema.get("handler_module")

        if not handler_module:
            continue

        handle = _import_handle(handler_module)
        if handle is None:
            continue

        result[name] = ToolDef(
            name=name,
            description=schema.get("description", ""),
            input_schema=schema.get("input_schema", {"type": "object", "properties": {}}),
            handle=handle,
        )

    return result


def _import_handle(module_path: str):
    """Dynamically import `handle` from a dotted module path."""
    try:
        module = importlib.import_module(module_path)
        return getattr(module, "handle", None)
    except (ImportError, AttributeError):
        return None


def dispatch(tool_call: ToolCall, tool_defs: list[ToolDef], ctx: dict) -> str:
    """Call the matching tool handler and return a JSON string result.

    Never raises — errors are returned as {"ok": false, "error": "..."}.
    """
    tool_map = {t.name: t for t in tool_defs}
    tool = tool_map.get(tool_call.name)

    if tool is None:
        return json.dumps({"ok": False, "error": f"Unknown tool: {tool_call.name}"})

    try:
        result = tool.handle(tool_call.input, ctx=ctx)
        return json.dumps(result)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(exc)})
