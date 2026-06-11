import json
import os

import boto3
from data.idempotency import check_and_set
from data.table import get_table
from whatsapp.parse import parse_webhook
from whatsapp.signature import verify_signature


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


_sqs = boto3.client("sqs")


def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    if method == "GET":
        return _handle_verify(event)
    return _handle_webhook(event)


def _handle_verify(event: dict) -> dict:
    params = event.get("queryStringParameters") or {}
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")

    if mode == "subscribe" and token == _cfg("META_VERIFY_TOKEN"):
        return {"statusCode": 200, "body": challenge}
    return {"statusCode": 403, "body": "Forbidden"}


def _handle_webhook(event: dict) -> dict:
    body_raw = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64

        body_raw = base64.b64decode(body_raw).decode()

    body_bytes = body_raw.encode() if isinstance(body_raw, str) else body_raw
    signature = (event.get("headers") or {}).get("x-hub-signature-256", "")

    if not verify_signature(body_bytes, signature, _cfg("META_APP_SECRET")):
        # Always return 200 to Meta — don't reveal signature failure
        return {"statusCode": 200, "body": "OK"}

    try:
        payload = json.loads(body_raw)
    except json.JSONDecodeError:
        return {"statusCode": 200, "body": "OK"}

    messages = parse_webhook(payload)
    table = get_table(_cfg("SONARIA_TABLE_NAME", "sonaria"))

    for msg in messages:
        if msg.message_type != "text":
            continue  # MVP: text-only

        if not check_and_set(table, wamid=msg.wamid):
            continue  # duplicate

        _enqueue(msg)

    return {"statusCode": 200, "body": "OK"}


def _enqueue(msg) -> None:
    body = json.dumps(
        {
            "wa_id": msg.wa_id,
            "wamid": msg.wamid,
            "phone_number_id": msg.phone_number_id,
            "message_type": msg.message_type,
            "text": msg.text,
            "media_id": msg.media_id,
        }
    )
    _sqs.send_message(
        QueueUrl=_cfg("SQS_QUEUE_URL"),
        MessageBody=body,
        MessageGroupId=msg.wa_id,
        MessageDeduplicationId=msg.wamid,
    )
