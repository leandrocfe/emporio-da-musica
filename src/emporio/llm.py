"""`LLMClient` port: the language model the Assistant talks to (ADR-0001).

Messages and tool definitions follow the OpenAI chat format, which LiteLLM
translates to every provider. Tests inject a scripted fake; production uses
`emporio.litellm_client.LiteLLMClient`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

# One OpenAI-format chat message ({"role": ..., "content": ..., ...}).
Message = dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text, exactly as the model sent it (may be invalid)


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage | None = None
    model: str | None = None


class LLMClient(Protocol):
    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, object]]
    ) -> LLMResponse:
        """One model turn: either a final answer or a batch of tool calls."""
        ...
