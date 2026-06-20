import json
import os
from pathlib import Path

from common.logging import bind_context, get_logger, log_turn_usage
from core.agent import run_turn
from core.resolver import resolve
from data.conversations import append_turn, get_turns
from data.table import get_table
from openclaw_adapter.client import LangChainRuntime
from whatsapp.client import WhatsAppClient

logger = get_logger()

_REPO_ROOT = Path(__file__).parent.parent.parent


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _build_runtime() -> LangChainRuntime:
    return LangChainRuntime(api_key=_cfg("OPENAI_API_KEY"))


def _build_wa_client(phone_number_id: str) -> WhatsAppClient:
    return WhatsAppClient(
        access_token=_cfg("META_ACCESS_TOKEN"),
        phone_number_id=phone_number_id,
    )


def handler(event: dict, context) -> dict:
    records = event.get("Records", [])
    for record in records:
        try:
            _process_record(record)
        except Exception as exc:  # noqa: BLE001
            logger.error("agent_turn_error", error=str(exc), record=record.get("messageId"))
    return {"statusCode": 200}


def _process_record(record: dict) -> None:
    msg = json.loads(record["body"])
    wa_id: str = msg["wa_id"]
    wamid: str = msg["wamid"]
    phone_number_id: str = msg["phone_number_id"]
    text: str | None = msg.get("text")

    bind_context(logger, phone_number=wa_id, wamid=wamid, agent_id="sonaria-bogota")

    # Signal immediately that the message was received
    with _build_wa_client(phone_number_id) as wa:
        wa.mark_as_read(wamid=wamid)

    table = get_table(_cfg("SONARIA_TABLE_NAME", "sonaria"))
    config = resolve(
        shared_dir=_cfg("SHARED_DIR", str(_REPO_ROOT / "shared")),
        agent_dir=_cfg("AGENT_DIR", str(_REPO_ROOT / "agent")),
    )

    # Load conversation history
    turns = get_turns(table, wa_id=wa_id, n=config.conversation.get("window_size", 20))
    messages = _turns_to_messages(turns)

    # Persist user turn before calling the LLM
    user_index = len(turns)
    append_turn(table, wa_id=wa_id, index=user_index, role="user", content=text or "")

    messages.append({"role": "user", "content": text or ""})

    runtime = _build_runtime()
    ctx = {
        "wa_id": wa_id,
        "wamid": wamid,
        "phone_number_id": phone_number_id,
        "logger": logger,
    }

    result = run_turn(runtime=runtime, config=config, messages=messages, ctx=ctx)

    # Persist assistant turn
    append_turn(
        table,
        wa_id=wa_id,
        index=user_index + 1,
        role="assistant",
        content=result.text,
        meta={
            "tools_used": result.tools_used,
            "usage": result.usage,
            "iterations": result.iterations,
        },
    )

    # Send reply
    with _build_wa_client(phone_number_id) as wa:
        wa.send_text(to=wa_id, text=result.text)

    log_turn_usage(
        logger,
        input_tokens=result.usage.get("input_tokens", 0),
        output_tokens=result.usage.get("output_tokens", 0),
        iterations=result.iterations,
        tools_used=result.tools_used,
        identified=False,
    )


def _turns_to_messages(turns: list[dict]) -> list[dict]:
    return [{"role": t["role"], "content": t["content"]} for t in turns]
