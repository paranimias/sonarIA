from pathlib import Path

import pytest
from core.tools import dispatch, load_tools
from core.types import ToolCall

SHARED = Path(__file__).parent / "fixtures" / "shared"
AGENT = Path(__file__).parent / "fixtures" / "agent"


@pytest.fixture
def tool_defs():
    return load_tools(SHARED, AGENT, {})


def test_load_tools_returns_list(tool_defs):
    assert len(tool_defs) >= 2


def test_load_tools_has_correct_names(tool_defs):
    names = {t.name for t in tool_defs}
    assert "user_lookup" in names
    assert "recommend_events" in names


def test_tool_def_has_callable_handle(tool_defs):
    for t in tool_defs:
        assert callable(t.handle)


def test_dispatch_returns_json_string(tool_defs):
    import json

    tc = ToolCall(id="tc1", name="recommend_events", input={"genre": "rock"})
    result = dispatch(tc, tool_defs, ctx={})
    parsed = json.loads(result)
    assert parsed["ok"] is True


def test_dispatch_unknown_tool_returns_error(tool_defs):
    import json

    tc = ToolCall(id="tc2", name="nonexistent_tool", input={})
    result = dispatch(tc, tool_defs, ctx={})
    parsed = json.loads(result)
    assert parsed["ok"] is False
    assert "Unknown tool" in parsed["error"]


def test_dispatch_handler_exception_returns_error():
    import json

    from core.types import ToolDef

    def bad_handle(inp, *, ctx):
        raise ValueError("something went wrong")

    tool_defs = [ToolDef(name="bad_tool", description="", input_schema={}, handle=bad_handle)]
    tc = ToolCall(id="tc3", name="bad_tool", input={})
    result = dispatch(tc, tool_defs, ctx={})
    parsed = json.loads(result)
    assert parsed["ok"] is False
    assert "something went wrong" in parsed["error"]


def test_to_schema():
    from core.types import ToolDef

    td = ToolDef(
        name="my_tool",
        description="desc",
        input_schema={"type": "object"},
        handle=lambda i, ctx: {},
    )
    schema = td.to_schema()
    assert schema == {"name": "my_tool", "description": "desc", "input_schema": {"type": "object"}}
