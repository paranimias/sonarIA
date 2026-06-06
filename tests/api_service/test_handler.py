import json

from data.conversations import append_turn, get_turns

import services.api.handler as api
from tests.api_service.conftest import USER_ID, apigw_event, apigw_event_no_auth

# --- POST /messages ---


def test_post_message_queues_and_returns_202(aws_resources):
    event = apigw_event("POST", "/messages", body={"text": "Hola SonarIA", "wa_id": "573001"})
    resp = api.handler(event, None)

    assert resp["statusCode"] == 202
    body = json.loads(resp["body"])
    assert "wamid" in body
    assert body["status"] == "queued"

    msgs = (
        aws_resources["sqs"]
        .receive_message(QueueUrl=aws_resources["queue_url"], MaxNumberOfMessages=1)
        .get("Messages", [])
    )
    assert len(msgs) == 1
    payload = json.loads(msgs[0]["Body"])
    assert payload["text"] == "Hola SonarIA"
    assert payload["wa_id"] == "573001"


def test_post_message_persists_user_turn(aws_resources):
    event = apigw_event("POST", "/messages", body={"text": "Eventos de jazz", "wa_id": USER_ID})
    api.handler(event, None)

    turns = get_turns(aws_resources["table"], wa_id=USER_ID, n=10)
    assert len(turns) == 1
    assert turns[0]["role"] == "user"
    assert turns[0]["content"] == "Eventos de jazz"


def test_post_message_missing_text_returns_400(aws_resources):
    event = apigw_event("POST", "/messages", body={"wa_id": "x"})
    resp = api.handler(event, None)
    assert resp["statusCode"] == 400


def test_post_message_no_auth_returns_401(aws_resources):
    event = apigw_event_no_auth("POST", "/messages", body={"text": "hola"})
    resp = api.handler(event, None)
    assert resp["statusCode"] == 401


# --- GET /conversations/:wa_id ---


def test_get_conversation_returns_turns(aws_resources):
    wa_id = "573009876543"
    append_turn(aws_resources["table"], wa_id=wa_id, index=0, role="user", content="Hola")
    append_turn(aws_resources["table"], wa_id=wa_id, index=1, role="assistant", content="Buenas")

    event = apigw_event("GET", f"/conversations/{wa_id}")
    resp = api.handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["wa_id"] == wa_id
    assert len(body["turns"]) == 2
    assert body["turns"][0]["role"] == "user"
    assert body["turns"][1]["role"] == "assistant"


def test_get_conversation_empty(aws_resources):
    event = apigw_event("GET", "/conversations/unknown_wa_id")
    resp = api.handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["turns"] == []


def test_get_conversation_no_auth_returns_401(aws_resources):
    event = apigw_event_no_auth("GET", "/conversations/573001")
    resp = api.handler(event, None)
    assert resp["statusCode"] == 401


def test_get_conversation_respects_n_param(aws_resources):
    wa_id = "573009876543"
    for i in range(5):
        append_turn(aws_resources["table"], wa_id=wa_id, index=i, role="user", content=f"msg{i}")

    event = apigw_event("GET", f"/conversations/{wa_id}", params={"n": "3"})
    resp = api.handler(event, None)
    body = json.loads(resp["body"])
    assert len(body["turns"]) == 3


def test_unknown_route_returns_404(aws_resources):
    event = apigw_event("GET", "/unknown/route")
    resp = api.handler(event, None)
    assert resp["statusCode"] == 404
