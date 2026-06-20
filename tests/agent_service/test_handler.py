import json

from data.conversations import get_turns
from moto import mock_aws

import services.agent.handler as agent_handler
from tests.agent_service.conftest import FakeRuntime, end_turn

SQS_RECORD = {
    "messageId": "msg-001",
    "body": json.dumps(
        {
            "wa_id": "573009876543",
            "wamid": "wamid.TEST001",
            "phone_number_id": "PID",
            "message_type": "text",
            "text": "Hola SonarIA",
            "media_id": None,
        }
    ),
}


@mock_aws
def test_full_turn_persists_and_sends(table, monkeypatch):
    fake_rt = FakeRuntime([end_turn("Hola! Aquí los eventos de esta semana.")])
    sent: list[dict] = []

    class FakeWAClient:
        def __init__(self, *a, **kw):
            pass

        def send_text(self, *, to, text):
            sent.append({"to": to, "text": text})

        def mark_as_read(self, *, wamid):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(agent_handler, "_build_runtime", lambda: fake_rt)
    monkeypatch.setattr(agent_handler, "_build_wa_client", lambda pid: FakeWAClient())

    agent_handler.handler({"Records": [SQS_RECORD]}, None)

    # Sent the reply
    assert len(sent) == 1
    assert sent[0]["to"] == "573009876543"
    assert "eventos" in sent[0]["text"]

    # Persisted both turns
    turns = get_turns(table, wa_id="573009876543", n=10)
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"
    assert turns[1]["content"] == "Hola! Aquí los eventos de esta semana."


@mock_aws
def test_turn_error_does_not_propagate(table, monkeypatch):
    def boom():
        raise RuntimeError("LLM down")

    monkeypatch.setattr(agent_handler, "_build_runtime", boom)

    # Should not raise — errors are caught per-record
    result = agent_handler.handler({"Records": [SQS_RECORD]}, None)
    assert result["statusCode"] == 200


@mock_aws
def test_history_included_in_runtime_call(table, monkeypatch):
    from data.conversations import append_turn

    # Seed an existing conversation turn
    append_turn(table, wa_id="573009876543", index=0, role="user", content="Mensaje previo")

    captured_messages: list = []

    class CapturingRuntime:
        def complete(self, **kwargs):
            captured_messages.extend(kwargs["messages"])
            return end_turn("ok")

    class FakeWA:
        def __init__(self, *a, **kw):
            pass

        def send_text(self, **kw):
            pass

        def mark_as_read(self, *, wamid):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(agent_handler, "_build_runtime", lambda: CapturingRuntime())
    monkeypatch.setattr(agent_handler, "_build_wa_client", lambda pid: FakeWA())

    agent_handler.handler({"Records": [SQS_RECORD]}, None)

    # First message in history should be the seeded turn
    assert captured_messages[0]["content"] == "Mensaje previo"
    # Second is the current user message
    assert captured_messages[1]["content"] == "Hola SonarIA"


@mock_aws
def test_empty_records_returns_200(table):
    result = agent_handler.handler({"Records": []}, None)
    assert result["statusCode"] == 200
