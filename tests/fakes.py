"""Test doubles for the system boundaries (the language model, the event sink)."""

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from emporio.events import Event
from emporio.llm import LLMResponse, Message, ToolCall


def tool_call(call_id: str, name: str, arguments: Mapping[str, object] | str) -> ToolCall:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return ToolCall(id=call_id, name=name, arguments=raw)


def asks(*calls: ToolCall) -> LLMResponse:
    """A model turn that requests tools."""
    return LLMResponse(content=None, tool_calls=list(calls))


def says(text: str) -> LLMResponse:
    """A final model turn."""
    return LLMResponse(content=text, tool_calls=[])


@dataclass
class ModelCall:
    messages: list[Message]
    tools: list[dict[str, object]]


@dataclass
class ScriptedLLM:
    """Replays scripted responses and records a snapshot of every request."""

    script: list[LLMResponse]
    calls: list[ModelCall] = field(default_factory=list)

    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, object]]
    ) -> LLMResponse:
        self.calls.append(ModelCall(copy.deepcopy(list(messages)), copy.deepcopy(list(tools))))
        if not self.script:
            raise AssertionError("ScriptedLLM called more times than scripted")
        return self.script.pop(0)

    def tool_results(self, call_index: int) -> dict[str, object]:
        """`tool_call_id -> parsed content` of the tool messages sent in that call."""
        results: dict[str, object] = {}
        for message in self.calls[call_index].messages:
            if message["role"] == "tool":
                content = message["content"]
                assert isinstance(content, str)
                results[str(message["tool_call_id"])] = json.loads(content)
        return results


@dataclass
class RecordingSink:
    events: list[Event] = field(default_factory=list)

    def emit(self, event: Event) -> None:
        self.events.append(event)
