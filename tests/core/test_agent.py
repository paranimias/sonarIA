from pathlib import Path

import pytest

from core.agent import run_turn, MAX_ITERATIONS
from core.resolver import resolve
from core.types import Completion, ToolCall

SHARED = Path(__file__).parent / "fixtures" / "shared"
AGENT = Path(__file__).parent / "fixtures" / "agent"


class FakeRuntime:
    """Returns a predefined sequence of Completions."""

    def __init__(self, responses: list[Completion]):
        self._responses = list(responses)
        self._index = 0

    def complete(self, **kwargs) -> Completion:
        if self._index >= len(self._responses):
            return Completion(text_blocks=["done"], tool_calls=[], stop_reason="end_turn", usage={})
        c = self._responses[self._index]
        self._index += 1
        return c


def _end_turn(text: str) -> Completion:
    return Completion(text_blocks=[text], tool_calls=[], stop_reason="end_turn", usage={"input_tokens": 10, "output_tokens": 5})


def _tool_use(tool_name: str, tool_id: str = "tc1", tool_input: dict | None = None) -> Completion:
    return Completion(
        text_blocks=[],
        tool_calls=[ToolCall(id=tool_id, name=tool_name, input=tool_input or {})],
        stop_reason="tool_use",
        usage={"input_tokens": 20, "output_tokens": 10},
    )


@pytest.fixture
def config():
    return resolve(SHARED, AGENT)


def test_simple_text_turn(config):
    runtime = FakeRuntime([_end_turn("Hola desde SonarIA")])
    result = run_turn(runtime=runtime, config=config, messages=[], ctx={})
    assert result.text == "Hola desde SonarIA"
    assert result.iterations == 1
    assert result.tools_used == []


def test_turn_with_tool_call(config):
    runtime = FakeRuntime([
        _tool_use("recommend_events", tool_id="tc1", tool_input={"genre": "jazz"}),
        _end_turn("Te recomiendo este evento de jazz"),
    ])
    result = run_turn(runtime=runtime, config=config, messages=[], ctx={})
    assert result.text == "Te recomiendo este evento de jazz"
    assert result.iterations == 2
    assert "recommend_events" in result.tools_used


def test_turn_accumulates_usage(config):
    runtime = FakeRuntime([
        _tool_use("recommend_events"),
        _end_turn("Listo"),
    ])
    result = run_turn(runtime=runtime, config=config, messages=[], ctx={})
    assert result.usage["input_tokens"] == 30  # 20 + 10
    assert result.usage["output_tokens"] == 15  # 10 + 5


def test_turn_respects_max_iterations(config):
    # FakeRuntime keeps returning tool_use indefinitely via the fallback
    tool_responses = [_tool_use("recommend_events")] * (MAX_ITERATIONS + 5)
    runtime = FakeRuntime(tool_responses)
    result = run_turn(runtime=runtime, config=config, messages=[], ctx={})
    assert result.iterations == MAX_ITERATIONS


def test_turn_with_unknown_tool_does_not_crash(config):
    runtime = FakeRuntime([
        _tool_use("unknown_tool"),
        _end_turn("Respondí igual"),
    ])
    result = run_turn(runtime=runtime, config=config, messages=[], ctx={})
    assert result.text == "Respondí igual"
    assert "unknown_tool" in result.tools_used


def test_history_is_passed_to_runtime(config):
    captured = []

    class CapturingRuntime:
        def complete(self, **kwargs):
            captured.append(kwargs["messages"])
            return _end_turn("ok")

    history = [{"role": "user", "content": "mensaje previo"}]
    run_turn(runtime=CapturingRuntime(), config=config, messages=history, ctx={})
    assert captured[0][0]["content"] == "mensaje previo"
