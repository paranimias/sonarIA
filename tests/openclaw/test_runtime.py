from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from openclaw_adapter.client import LangChainRuntime, _parse_ai_message, _to_lc_messages

# --- _to_lc_messages ---


def test_system_becomes_system_message():
    msgs = _to_lc_messages([{"type": "text", "text": "Eres un asistente"}], [])
    assert len(msgs) == 1
    assert msgs[0].__class__.__name__ == "SystemMessage"
    assert msgs[0].content == "Eres un asistente"


def test_plain_user_string():
    msgs = _to_lc_messages([], [{"role": "user", "content": "Hola"}])
    assert len(msgs) == 1
    assert msgs[0].__class__.__name__ == "HumanMessage"
    assert msgs[0].content == "Hola"


def test_tool_result_becomes_tool_message():
    content = [{"type": "tool_result", "tool_use_id": "tc1", "content": '{"ok": true}'}]
    msgs = _to_lc_messages([], [{"role": "user", "content": content}])
    assert len(msgs) == 1
    assert msgs[0].__class__.__name__ == "ToolMessage"
    assert msgs[0].tool_call_id == "tc1"


def test_assistant_with_tool_use_becomes_ai_message_with_tool_calls():
    content = [
        {"type": "text", "text": "Buscando..."},
        {"type": "tool_use", "id": "tc1", "name": "recommend_events", "input": {"genre": "jazz"}},
    ]
    msgs = _to_lc_messages([], [{"role": "assistant", "content": content}])
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.__class__.__name__ == "AIMessage"
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0]["name"] == "recommend_events"
    assert msg.tool_calls[0]["args"] == {"genre": "jazz"}


# --- _parse_ai_message ---


def test_parse_text_response():
    ai_msg = AIMessage(
        content="Aquí van los eventos",
        response_metadata={"finish_reason": "stop"},
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    result = _parse_ai_message(ai_msg)
    assert result.text_blocks == ["Aquí van los eventos"]
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"
    assert result.usage == {"input_tokens": 10, "output_tokens": 5}


def test_parse_tool_call_response():
    ai_msg = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "tc1",
                "name": "recommend_events",
                "args": {"genre": "salsa"},
                "type": "tool_call",
            }
        ],
        response_metadata={"finish_reason": "tool_calls"},
        usage_metadata={"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
    )
    result = _parse_ai_message(ai_msg)
    assert result.stop_reason == "tool_use"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "recommend_events"
    assert result.tool_calls[0].input == {"genre": "salsa"}
    assert result.tool_calls[0].id == "tc1"


# --- LangChainRuntime.complete (mocked ChatOpenAI) ---


def test_complete_returns_completion(monkeypatch):
    fake_response = AIMessage(
        content="Respuesta del LLM",
        response_metadata={"finish_reason": "stop"},
        usage_metadata={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
    )

    with patch("openclaw_adapter.client.ChatOpenAI") as MockLLM:
        instance = MagicMock()
        instance.invoke.return_value = fake_response
        instance.bind_tools.return_value = instance
        MockLLM.return_value = instance

        runtime = LangChainRuntime(api_key="test-key")
        result = runtime.complete(
            model="gpt-4o-mini",
            system=[{"type": "text", "text": "Sistema"}],
            messages=[{"role": "user", "content": "Hola"}],
            tools=[],
            max_tokens=512,
        )

    assert result.text_blocks == ["Respuesta del LLM"]
    assert result.stop_reason == "end_turn"
    assert result.usage["input_tokens"] == 5
