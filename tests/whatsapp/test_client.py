import json

import httpx
import pytest
from whatsapp.client import WhatsAppClient

PHONE_NUMBER_ID = "TEST_PID"
ACCESS_TOKEN = "TEST_TOKEN"
RECIPIENT = "573009876543"


def _make_transport(status_code: int = 200, body: dict | None = None):
    response_body = json.dumps(body or {"messages": [{"id": "wamid.SENT"}]}).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=response_body)

    return httpx.MockTransport(handler)


@pytest.fixture
def client(monkeypatch):
    transport = _make_transport()
    c = WhatsAppClient(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    c._http = httpx.Client(
        base_url="https://graph.facebook.com/v19.0",
        transport=transport,
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    )
    return c


def test_send_text_posts_correct_payload(client):
    result = client.send_text(to=RECIPIENT, text="Hola desde SonarIA")
    assert result == {"messages": [{"id": "wamid.SENT"}]}


def test_send_text_uses_correct_url():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b'{"messages":[{"id":"wamid.X"}]}')

    c = WhatsAppClient(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    c._http = httpx.Client(
        base_url="https://graph.facebook.com/v19.0",
        transport=httpx.MockTransport(handler),
    )
    c.send_text(to=RECIPIENT, text="test")

    assert len(captured) == 1
    assert f"/{PHONE_NUMBER_ID}/messages" in captured[0].url.path


def test_send_text_raises_on_error():
    c = WhatsAppClient(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    c._http = httpx.Client(
        base_url="https://graph.facebook.com/v19.0",
        transport=_make_transport(status_code=401, body={"error": "unauthorized"}),
    )
    with pytest.raises(httpx.HTTPStatusError):
        c.send_text(to=RECIPIENT, text="fail")


def test_mark_as_read_sends_correct_payload():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b'{"success": true}')

    import json as _json

    c = WhatsAppClient(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    c._http = httpx.Client(
        base_url="https://graph.facebook.com/v19.0",
        transport=httpx.MockTransport(handler),
    )
    c.mark_as_read(wamid="wamid.test123")

    assert len(captured) == 1
    body = _json.loads(captured[0].content)
    assert body["status"] == "read"
    assert body["message_id"] == "wamid.test123"
    assert body["messaging_product"] == "whatsapp"


def test_mark_as_read_fails_silently_on_error():
    c = WhatsAppClient(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    c._http = httpx.Client(
        base_url="https://graph.facebook.com/v19.0",
        transport=_make_transport(status_code=500, body={"error": "server error"}),
    )
    # Should not raise
    c.mark_as_read(wamid="wamid.test456")


def test_send_media_posts_correct_type():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b'{"messages":[{"id":"wamid.Y"}]}')

    c = WhatsAppClient(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    c._http = httpx.Client(
        base_url="https://graph.facebook.com/v19.0",
        transport=httpx.MockTransport(handler),
    )
    c.send_media(to=RECIPIENT, media_type="image", media_id="MEDIA_123", caption="Cover")

    body = json.loads(captured[0].content)
    assert body["type"] == "image"
    assert body["image"]["id"] == "MEDIA_123"
    assert body["image"]["caption"] == "Cover"
