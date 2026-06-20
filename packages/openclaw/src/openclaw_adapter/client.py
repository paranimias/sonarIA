import os

from core.types import Completion, ToolCall
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

_STOP_REASON_MAP = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "end_turn",
}


class LangChainRuntime:
    """AgentRuntime backed by LangChain + ChatOpenAI."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ["OPENAI_API_KEY"]

    def complete(
        self,
        *,
        model: str,
        system: list[dict],
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> Completion:
        llm = ChatOpenAI(model=model, max_tokens=max_tokens, api_key=self._api_key)
        if tools:
            llm = llm.bind_tools([_to_openai_tool(t) for t in tools])
        lc_messages = _to_lc_messages(system, messages)
        response: AIMessage = llm.invoke(lc_messages)
        return _parse_ai_message(response)


def _to_lc_messages(system: list[dict], messages: list[dict]) -> list[BaseMessage]:
    result: list[BaseMessage] = []

    system_text = "\n\n".join(b["text"] for b in system if b.get("type") == "text")
    if system_text:
        result.append(SystemMessage(content=system_text))

    for msg in messages:
        if msg["role"] == "assistant":
            result.extend(_assistant_to_lc(msg["content"]))
        else:
            result.extend(_user_to_lc(msg["content"]))

    return result


def _user_to_lc(content) -> list[BaseMessage]:
    if isinstance(content, str):
        return [HumanMessage(content=content)]

    texts = [b for b in content if b.get("type") == "text"]
    tool_results = [b for b in content if b.get("type") == "tool_result"]
    out: list[BaseMessage] = []

    if texts:
        out.append(HumanMessage(content=" ".join(b.get("text", "") for b in texts)))

    for tr in tool_results:
        raw = tr.get("content", "")
        if isinstance(raw, list):
            raw = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in raw)
        out.append(ToolMessage(content=str(raw), tool_call_id=tr["tool_use_id"]))

    return out


def _assistant_to_lc(content) -> list[BaseMessage]:
    if isinstance(content, str):
        return [AIMessage(content=content)]

    texts = [b for b in content if b.get("type") == "text"]
    uses = [b for b in content if b.get("type") == "tool_use"]

    tool_calls = [
        {"id": u["id"], "name": u["name"], "args": u.get("input", {}), "type": "tool_call"}
        for u in uses
    ]
    return [AIMessage(content=" ".join(b.get("text", "") for b in texts), tool_calls=tool_calls)]


def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


def _parse_ai_message(response: AIMessage) -> Completion:
    content = response.content
    if isinstance(content, str):
        text_blocks = [content] if content else []
    else:
        text_blocks = [b["text"] for b in content if b.get("type") == "text" and b.get("text")]

    tool_calls = [
        ToolCall(id=tc["id"], name=tc["name"], input=tc["args"])
        for tc in (response.tool_calls or [])
    ]

    finish_reason = response.response_metadata.get("finish_reason", "stop")
    stop_reason = _STOP_REASON_MAP.get(finish_reason, "end_turn")

    usage: dict = {}
    if response.usage_metadata:
        usage = {
            "input_tokens": response.usage_metadata.get("input_tokens", 0),
            "output_tokens": response.usage_metadata.get("output_tokens", 0),
        }

    return Completion(
        text_blocks=text_blocks, tool_calls=tool_calls, stop_reason=stop_reason, usage=usage
    )
