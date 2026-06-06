import json

import boto3
import httpx
import pytest
from moto import mock_aws

import services.media.handler as media_handler

BUCKET = "sonaria-test-media"
QUEUE_NAME = "sonaria-agent.fifo"
AUDIO_RECORD = {
    "messageId": "rec-001",
    "body": json.dumps(
        {
            "wa_id": "573009876543",
            "wamid": "wamid.AUDIO001",
            "phone_number_id": "PID",
            "message_type": "audio",
            "media_id": "MEDIA_ID_123",
        }
    ),
}
IMAGE_RECORD = {
    "messageId": "rec-002",
    "body": json.dumps(
        {
            "wa_id": "573009876543",
            "wamid": "wamid.IMG001",
            "phone_number_id": "PID",
            "message_type": "image",
            "media_id": "MEDIA_IMG_456",
        }
    ),
}


@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("META_ACCESS_TOKEN", "fake_token")
    monkeypatch.setenv("OPENAI_API_KEY", "fake_openai_key")
    monkeypatch.setenv("MEDIA_BUCKET", BUCKET)


@pytest.fixture
def aws_resources(monkeypatch):
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)

        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "false"},
        )
        queue_url = resp["QueueUrl"]
        monkeypatch.setenv("SQS_QUEUE_URL", queue_url)

        media_handler._s3 = s3
        media_handler._sqs = sqs

        yield {"s3": s3, "sqs": sqs, "queue_url": queue_url}


def _make_response(url: str, status: int = 200, **kwargs) -> httpx.Response:
    """Create an httpx.Response with a bound request (required for raise_for_status)."""
    request = httpx.Request("GET", url)
    return httpx.Response(status, request=request, **kwargs)


def _mock_http(monkeypatch, audio_bytes: bytes = b"fake_audio"):
    """Patch httpx.get to return fake Meta API responses."""

    def fake_get(url, *, headers=None, timeout=None):
        if "graph.facebook.com" in url and "/MEDIA" in url:
            return _make_response(url, json={"url": "https://cdn.example.com/media/file"})
        return _make_response(url, content=audio_bytes)

    monkeypatch.setattr(httpx, "get", fake_get)


def test_audio_transcribed_and_enqueued(aws_resources, monkeypatch):
    _mock_http(monkeypatch, audio_bytes=b"fake_ogg_data")
    monkeypatch.setattr(media_handler, "_transcribe_audio", lambda b: "Hola qué eventos hay")

    media_handler.handler({"Records": [AUDIO_RECORD]}, None)

    # Check S3 upload
    keys = [o["Key"] for o in aws_resources["s3"].list_objects(Bucket=BUCKET).get("Contents", [])]
    assert any("audio" in k for k in keys)

    # Check SQS message
    msgs = (
        aws_resources["sqs"]
        .receive_message(QueueUrl=aws_resources["queue_url"], MaxNumberOfMessages=1)
        .get("Messages", [])
    )
    assert len(msgs) == 1
    body = json.loads(msgs[0]["Body"])
    assert body["text"] == "Hola qué eventos hay"
    assert body["message_type"] == "text"
    assert body["wa_id"] == "573009876543"


def test_image_enqueued_as_placeholder(aws_resources, monkeypatch):
    _mock_http(monkeypatch, audio_bytes=b"fake_jpg_data")

    media_handler.handler({"Records": [IMAGE_RECORD]}, None)

    msgs = (
        aws_resources["sqs"]
        .receive_message(QueueUrl=aws_resources["queue_url"], MaxNumberOfMessages=1)
        .get("Messages", [])
    )
    assert len(msgs) == 1
    body = json.loads(msgs[0]["Body"])
    assert "[image" in body["text"]


def test_download_error_does_not_propagate(aws_resources, monkeypatch):
    def fail_get(url, **kw):
        raise httpx.ConnectError("timeout")

    monkeypatch.setattr(httpx, "get", fail_get)

    result = media_handler.handler({"Records": [AUDIO_RECORD]}, None)
    assert result["statusCode"] == 200
