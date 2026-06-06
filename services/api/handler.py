import json
import os
import uuid

import boto3
from common.logging import get_logger
from data.conversations import append_turn, get_turns
from data.table import get_table

logger = get_logger()

_sqs = boto3.client("sqs")


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")

    claims = _extract_claims(event)
    if claims is None:
        return _response(401, {"error": "Unauthorized"})

    if method == "POST" and path == "/messages":
        return _post_message(event, claims)

    if method == "GET" and path.startswith("/conversations/"):
        wa_id = path.removeprefix("/conversations/").strip("/")
        return _get_conversation(wa_id, event)

    return _response(404, {"error": "Not found"})


def _extract_claims(event: dict) -> dict | None:
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return None


def _post_message(event: dict, claims: dict) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON"})

    text = body.get("text", "").strip()
    if not text:
        return _response(400, {"error": "text is required"})

    user_id: str = claims.get("sub", "anonymous")
    wa_id: str = body.get("wa_id") or user_id
    wamid: str = f"web-{uuid.uuid4()}"
    phone_number_id: str = _cfg("PHONE_NUMBER_ID", "webchat")

    table = get_table(_cfg("SONARIA_TABLE_NAME", "sonaria"))

    # Persist user turn
    turns = get_turns(table, wa_id=wa_id, n=1)
    next_index = len(turns)
    append_turn(table, wa_id=wa_id, index=next_index, role="user", content=text)

    # Enqueue for the agent
    _sqs.send_message(
        QueueUrl=_cfg("SQS_QUEUE_URL"),
        MessageBody=json.dumps(
            {
                "wa_id": wa_id,
                "wamid": wamid,
                "phone_number_id": phone_number_id,
                "message_type": "text",
                "text": text,
                "media_id": None,
            }
        ),
        MessageGroupId=wa_id,
        MessageDeduplicationId=wamid,
    )

    return _response(202, {"wamid": wamid, "status": "queued"})


def _get_conversation(wa_id: str, event: dict) -> dict:
    params = event.get("queryStringParameters") or {}
    n = int(params.get("n", 20))
    n = min(max(n, 1), 100)  # clamp 1-100

    table = get_table(_cfg("SONARIA_TABLE_NAME", "sonaria"))
    turns = get_turns(table, wa_id=wa_id, n=n)

    return _response(
        200,
        {
            "wa_id": wa_id,
            "turns": [
                {"role": t["role"], "content": t["content"], "meta": t.get("meta", {})}
                for t in turns
            ],
        },
    )


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
