import json

import services.webhook.handler as wh
from tests.webhook.conftest import make_post_event

META_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WABA",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "PID"},
                        "messages": [
                            {
                                "from": "573009876543",
                                "id": "wamid.TEST001",
                                "timestamp": "1700000000",
                                "type": "text",
                                "text": {"body": "Hola SonarIA"},
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


# --- GET handshake ---


def test_verify_valid_token():
    event = {
        "requestContext": {"http": {"method": "GET"}},
        "queryStringParameters": {
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_abc",
        },
    }
    resp = wh.handler(event, None)
    assert resp["statusCode"] == 200
    assert resp["body"] == "challenge_abc"


def test_verify_invalid_token():
    event = {
        "requestContext": {"http": {"method": "GET"}},
        "queryStringParameters": {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "xyz",
        },
    }
    resp = wh.handler(event, None)
    assert resp["statusCode"] == 403


# --- POST webhook ---


def test_valid_post_enqueues_message(aws_mock):
    event = make_post_event(META_PAYLOAD)
    resp = wh.handler(event, None)

    assert resp["statusCode"] == 200

    msgs = (
        aws_mock["sqs"]
        .receive_message(QueueUrl=aws_mock["queue_url"], MaxNumberOfMessages=1)
        .get("Messages", [])
    )
    assert len(msgs) == 1
    body = json.loads(msgs[0]["Body"])
    assert body["wa_id"] == "573009876543"
    assert body["wamid"] == "wamid.TEST001"
    assert body["text"] == "Hola SonarIA"


def test_invalid_signature_returns_200_but_does_not_enqueue(aws_mock):
    event = make_post_event(META_PAYLOAD, secret="wrong_secret")
    resp = wh.handler(event, None)

    assert resp["statusCode"] == 200  # Meta siempre recibe 200

    msgs = (
        aws_mock["sqs"]
        .receive_message(QueueUrl=aws_mock["queue_url"], MaxNumberOfMessages=1)
        .get("Messages", [])
    )
    assert len(msgs) == 0


def test_duplicate_wamid_not_enqueued_twice(aws_mock):
    event = make_post_event(META_PAYLOAD)

    wh.handler(event, None)  # first — enqueues
    wh.handler(event, None)  # duplicate — skipped

    msgs = (
        aws_mock["sqs"]
        .receive_message(
            QueueUrl=aws_mock["queue_url"],
            MaxNumberOfMessages=10,
        )
        .get("Messages", [])
    )
    assert len(msgs) == 1


def test_media_message_not_enqueued(aws_mock):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "PID"},
                            "messages": [
                                {
                                    "from": "573009876543",
                                    "id": "wamid.AUDIO001",
                                    "timestamp": "1700000000",
                                    "type": "audio",
                                    "audio": {"id": "media_abc"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ]
            }
        ],
    }
    event = make_post_event(payload)
    resp = wh.handler(event, None)

    assert resp["statusCode"] == 200
    msgs = (
        aws_mock["sqs"]
        .receive_message(QueueUrl=aws_mock["queue_url"], MaxNumberOfMessages=1)
        .get("Messages", [])
    )
    assert len(msgs) == 0


def test_status_update_not_enqueued(aws_mock):
    payload = {
        "object": "whatsapp_business_account",
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
        ],
    }
    event = make_post_event(payload)
    resp = wh.handler(event, None)

    assert resp["statusCode"] == 200
    msgs = (
        aws_mock["sqs"]
        .receive_message(QueueUrl=aws_mock["queue_url"], MaxNumberOfMessages=1)
        .get("Messages", [])
    )
    assert len(msgs) == 0
