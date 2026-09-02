"""THE LOOP — observe → reason → act → repeat.

Adapted from ShenSeanChen/waku-agent (MIT), waku/loop/agent.py.
That file's first docstring line ends: "This file is the whole trick."

No done flag. The loop ends when the model stops asking for tools.
The only thing stopping an infinite spin is range(1, max_iterations + 1).

Tool errors are *not* swallowed here. waku feeds them back as strings;
that is why a gate sits outside this file.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


class ToolError(Exception):
    """A tool failed. The loop stops; the gate decides what to do."""


class Ask(Protocol):
    def __call__(self, messages: list[dict[str, Any]]) -> "ModelTurn": ...


class Tools(Protocol):
    def execute(self, name: str, args: Mapping[str, Any]) -> str: ...


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ModelTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class LoopResult:
    reply: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    hit_limit: bool = False


def run_loop(
    ask: Ask,
    tools: Tools,
    messages: list[dict[str, Any]],
    max_iterations: int = 10,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> LoopResult:
    """Run one agent turn. `messages` is mutated in place."""
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    notify = on_event or (lambda _kind, _ev: None)
    result = LoopResult(reply="")

    for iteration in range(1, max_iterations + 1):
        result.iterations = iteration
        turn = ask(messages)
        notify(
            "llm",
            {
                "iteration": iteration,
                "tool_calls": [c.name for c in turn.tool_calls],
            },
        )
        messages.append(
            {
                "role": "assistant",
                "content": turn.text,
                "tool_calls": [
                    {"id": c.id, "name": c.name, "args": c.args}
                    for c in turn.tool_calls
                ],
            }
        )
        if not turn.tool_calls:
            result.reply = turn.text
            return result

        tool_results = []
        for call in turn.tool_calls:
            output = tools.execute(call.name, call.args)
            event = {"tool": call.name, "args": call.args, "output": output}
            result.tool_calls.append(event)
            notify("tool", event)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": call.id, "content": output}
            )
        messages.append({"role": "user", "content": tool_results})

    result.hit_limit = True
    result.reply = (
        "hit iteration limit before the model stopped asking for tools"
    )
    return result
