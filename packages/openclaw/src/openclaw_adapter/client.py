import json
import os

from core.types import Completion, ToolCall
from openai import OpenAI

_STOP_REASON_MAP = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "end_turn",
}


class OpenAIRuntime:
    """AgentRuntime backed by OpenAI. Translates Anthropic-style tool_use/tool_result
    protocol to OpenAI function-calling and back."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])

    def complete(
        self,
        *,
        model: str,
        system: list[dict],
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> Completion:
        oai_messages = _build_messages(system, messages)
        kwargs: dict = {"model": model, "messages": oai_messages, "max_tokens": max_tokens}
        if tools:
            kwargs["tools"] = [_to_oai_tool(t) for t in tools]

        response = self._client.chat.completions.create(**kwargs)
        return _parse_response(response)


# --- format translation ---

def _build_messages(system: list[dict], messages: list[dict]) -> list[dict]:
    result: list[dict] = []

    system_text = "\n\n".join(
        b.get("text", "") for b in system if b.get("type") == "text"
    )
    if system_text:
        result.append({"role": "system", "content": system_text})

    for msg in messages:
        if msg["role"] == "assistant":
            result.extend(_from_assistant(msg["content"]))
        else:
            result.extend(_from_user(msg["content"]))

    return result


def _from_user(content) -> list[dict]:
    if isinstance(content, str):
        return [{"role": "user", "content": content}]

    texts = [b for b in content if b.get("type") == "text"]
    tool_results = [b for b in content if b.get("type") == "tool_result"]
    out: list[dict] = []

    if texts:
        out.append({"role": "user", "content": " ".join(b.get("text", "") for b in texts)})

    for tr in tool_results:
        raw = tr.get("content", "")
        if isinstance(raw, list):
            raw = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in raw)
        out.append({"role": "tool", "tool_call_id": tr["tool_use_id"], "content": str(raw)})

    return out


def _from_assistant(content) -> list[dict]:
    if isinstance(content, str):
        return [{"role": "assistant", "content": content}]

    texts = [b for b in content if b.get("type") == "text"]
    uses = [b for b in content if b.get("type") == "tool_use"]

    msg: dict = {
        "role": "assistant",
        "content": " ".join(b.get("text", "") for b in texts) or None,
    }
    if uses:
        msg["tool_calls"] = [
            {
                "id": u["id"],
                "type": "function",
                "function": {"name": u["name"], "arguments": json.dumps(u.get("input", {}))},
            }
            for u in uses
        ]

    return [msg]


def _to_oai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


def _parse_response(response) -> Completion:
    choice = response.choices[0]
    msg = choice.message

    return Completion(
        text_blocks=[msg.content] if msg.content else [],
        tool_calls=[
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                input=json.loads(tc.function.arguments),
            )
            for tc in (msg.tool_calls or [])
        ],
        stop_reason=_STOP_REASON_MAP.get(choice.finish_reason, "end_turn"),
        usage={
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        },
    )
