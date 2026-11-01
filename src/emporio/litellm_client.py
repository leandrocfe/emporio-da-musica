"""Production `LLMClient` on LiteLLM (ADR-0001, ADR-0004).

The provider is chosen only by `LLM_MODEL` ("provider/model"); LiteLLM reads
the API key of that provider from its usual variable (ANTHROPIC_API_KEY,
GEMINI_API_KEY, OPENAI_API_KEY...), so only the key in use is required.

Every call has an explicit timeout. LiteLLM's own retries are disabled: the
retry policy (only timeout/429/5xx, with backoff) lives in the Assistant
(ticket 09), where it is testable.
"""

import os
from collections.abc import Callable, Sequence

import litellm
from litellm import ModelResponse
from litellm.types.utils import ChatCompletionMessageToolCall

from emporio.llm import LLMResponse, Message, TokenUsage, ToolCall

DEFAULT_MODEL = "anthropic/claude-sonnet-5-5"
DEFAULT_TIMEOUT_SECONDS = 30.0

Completion = Callable[..., object]


class LiteLLMClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        completion: Completion = litellm.completion,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self._completion = completion

    @classmethod
    def from_env(cls) -> "LiteLLMClient":
        """`LLM_MODEL` and `LLM_TIMEOUT_SECONDS`, with the defaults above."""
        model = os.environ.get("LLM_MODEL") or DEFAULT_MODEL
        timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS)
        return cls(model=model, timeout=timeout)

    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, object]]
    ) -> LLMResponse:
        response = self._completion(
            model=self.model,
            messages=list(messages),
            tools=list(tools) or None,
            timeout=self.timeout,
            num_retries=0,
            # Our tools are plain functions, never LiteLLM-proxy MCP servers. Skipping
            # the MCP gateway check also avoids its import of `mcp>=2` APIs, which the
            # locked mcp 1.x lacks (Chainlit 2.12 pins mcp<2): without this flag every
            # call with tools fails with ImportError. Private litellm kwarg, so litellm
            # is pinned to <1.107 in pyproject.toml and the real-litellm offline tests in
            # tests/test_litellm_client.py guard it; drop both once litellm and Chainlit
            # agree on an mcp major version.
            _skip_mcp_handler=True,
        )
        if not isinstance(response, ModelResponse):
            raise TypeError(f"unexpected LiteLLM response: {type(response).__name__}")
        return _to_llm_response(response)


def _to_llm_response(response: ModelResponse) -> LLMResponse:
    message = response.choices[0].message
    tool_calls = [_to_tool_call(call) for call in message.tool_calls or []]
    usage = getattr(response, "usage", None)
    return LLMResponse(
        content=message.content,
        tool_calls=tool_calls,
        usage=(
            TokenUsage(prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens)
            if usage is not None
            else None
        ),
        model=response.model,
    )


def _to_tool_call(call: object) -> ToolCall:
    # Only function calls can be answered by the ToolRegistry; dropping any other
    # kind would leave a tool call without its result in the history.
    if not isinstance(call, ChatCompletionMessageToolCall):
        raise TypeError(f"unexpected LiteLLM tool call: {type(call).__name__}")
    return ToolCall(id=call.id, name=call.function.name or "", arguments=call.function.arguments)
