import json
from pathlib import Path

import pytest
from whatsapp.parse import parse_webhook

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def text_payload():
    return json.loads((FIXTURES / "text_message.json").read_text())


@pytest.fixture
def audio_payload():
    return json.loads((FIXTURES / "audio_message.json").read_text())


def test_parse_text_message(text_payload):
    messages = parse_webhook(text_payload)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.wa_id == "573009876543"
    assert msg.wamid == "wamid.ABC123"
    assert msg.phone_number_id == "PHONE_NUMBER_ID"
    assert msg.message_type == "text"
    assert msg.text == "Hola, qué eventos hay este finde?"
    assert msg.media_id is None


def test_parse_audio_message(audio_payload):
    messages = parse_webhook(audio_payload)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.wa_id == "573009876543"
    assert msg.wamid == "wamid.AUDIO456"
    assert msg.message_type == "audio"
    assert msg.text is None
    assert msg.media_id == "MEDIA_ID_AUDIO"


def test_parse_empty_payload():
    assert parse_webhook({}) == []


def test_parse_status_update_ignored():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PID"},
                            "statuses": [{"id": "wamid.XYZ", "status": "delivered"}],
                        }
                    }
                ]
            }
        ]
    }
    assert parse_webhook(payload) == []
