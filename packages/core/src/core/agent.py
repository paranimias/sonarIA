from dataclasses import dataclass, field
from pathlib import Path

from .tools import dispatch
from .types import AgentRuntime, Completion, EffectiveConfig, ToolCall

MAX_ITERATIONS = 15


@dataclass
class TurnResult:
    text: str
    tools_used: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    iterations: int = 0


def run_turn(
    *,
    runtime: AgentRuntime,
    config: EffectiveConfig,
    messages: list[dict],
    ctx: dict,
) -> TurnResult:
    """Execute one agent turn: loop until end_turn or max iterations."""
    tool_schemas = [t.to_schema() for t in config.tool_defs]
    current_messages = list(messages)
    tools_used: list[str] = []
    total_usage: dict = {"input_tokens": 0, "output_tokens": 0}
    iterations = 0

    for _ in range(MAX_ITERATIONS):
        iterations += 1
        completion: Completion = runtime.complete(
            model=config.model,
            system=config.system_blocks,
            messages=current_messages,
            tools=tool_schemas,
            max_tokens=config.max_tokens,
        )

        _accumulate_usage(total_usage, completion.usage)

        if completion.stop_reason != "tool_use" or not completion.tool_calls:
            return TurnResult(
                text="\n".join(completion.text_blocks),
                tools_used=tools_used,
                usage=total_usage,
                iterations=iterations,
            )

        # Append assistant message with tool_use blocks
        assistant_content = [
            {"type": "text", "text": t} for t in completion.text_blocks if t
        ] + [
            {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}
            for tc in completion.tool_calls
        ]
        current_messages.append({"role": "assistant", "content": assistant_content})

        # Dispatch each tool call and collect results
        tool_results = []
        for tc in completion.tool_calls:
            tools_used.append(tc.name)
            result_json = dispatch(tc, config.tool_defs, ctx)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result_json,
            })

        current_messages.append({"role": "user", "content": tool_results})

    # Reached max iterations — return whatever text we have
    return TurnResult(
        text="",
        tools_used=tools_used,
        usage=total_usage,
        iterations=iterations,
    )


def _accumulate_usage(total: dict, usage: dict) -> None:
    for key in ("input_tokens", "output_tokens"):
        total[key] = total.get(key, 0) + usage.get(key, 0)
