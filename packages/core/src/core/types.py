from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class Completion:
    text_blocks: list[str]
    tool_calls: list[ToolCall]
    stop_reason: str    # "end_turn" | "tool_use" | "max_tokens"
    usage: dict         # input_tokens, output_tokens


@runtime_checkable
class AgentRuntime(Protocol):
    def complete(
        self,
        *,
        model: str,
        system: list[dict],     # bloques {type, text, cache_control?}
        messages: list[dict],   # historial user/assistant/tool_result
        tools: list[dict],      # schemas tipo {name, description, input_schema}
        max_tokens: int,
    ) -> Completion: ...
