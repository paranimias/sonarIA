from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable


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


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    handle: Callable[..., dict]

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class EffectiveConfig:
    agent_id: str
    model: str
    system_blocks: list[dict]   # bloques listos para runtime.complete (con cache_control)
    tool_defs: list[ToolDef]
    conversation: dict          # {window_size, ttl_hours}
    max_tokens: int
    handles: list[str]          # tipos de mensaje aceptados: ["text", "audio", "image"]
