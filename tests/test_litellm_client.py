"""LiteLLM adapter: the litellm `completion` function is the mocked boundary (no network)."""

import functools
from dataclasses import dataclass, field

import litellm
import pytest
from litellm import ModelResponse
from litellm.types.utils import (
    ChatCompletionCustomToolCallPayload,
    ChatCompletionMessageCustomToolCall,
)

from emporio.litellm_client import DEFAULT_MODEL, DEFAULT_TIMEOUT_SECONDS, LiteLLMClient
from emporio.llm import LLMResponse, TokenUsage, ToolCall, system_message

TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Busca",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


@dataclass
class FakeCompletion:
    response: ModelResponse
    kwargs: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, **kwargs: object) -> ModelResponse:
        self.kwargs.append(kwargs)
        return self.response


def model_response(message: dict[str, object]) -> ModelResponse:
    return ModelResponse(
        model="claude-sonnet-5-5",
        choices=[{"index": 0, "finish_reason": "stop", "message": message}],
        usage={"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
    )


def test_tool_calls_and_usage_are_converted() -> None:
    fake = FakeCompletion(
        model_response(
            {
                "role": "assistant",
                "content": "Vou procurar.",
                "tool_calls": [
                    {
                        "id": "toolu_1",
                        "type": "function",
                        "function": {"name": "search_products", "arguments": '{"query": "yamaha"}'},
                    },
                    {
                        "id": "toolu_2",
                        "type": "function",
                        "function": {"name": "search_products", "arguments": '{"query": "c40"}'},
                    },
                ],
            }
        )
    )
    client = LiteLLMClient(model="anthropic/claude-sonnet-5-5", completion=fake)

    response = client.complete([{"role": "user", "content": "tem yamaha?"}], TOOLS)

    assert response == LLMResponse(
        content="Vou procurar.",
        tool_calls=[
            ToolCall(id="toolu_1", name="search_products", arguments='{"query": "yamaha"}'),
            ToolCall(id="toolu_2", name="search_products", arguments='{"query": "c40"}'),
        ],
        usage=TokenUsage(prompt_tokens=120, completion_tokens=30),
        model="claude-sonnet-5-5",
    )


def test_final_answer_has_no_tool_calls() -> None:
    fake = FakeCompletion(model_response({"role": "assistant", "content": "Oi!"}))

    response = LiteLLMClient(model="anthropic/claude-sonnet-5-5", completion=fake).complete(
        [{"role": "user", "content": "oi"}], TOOLS
    )

    assert response.content == "Oi!"
    assert response.tool_calls == []


def test_request_uses_openai_format_explicit_timeout_and_no_hidden_retries() -> None:
    fake = FakeCompletion(model_response({"role": "assistant", "content": "Oi!"}))
    messages: list[dict[str, object]] = [{"role": "user", "content": "oi"}]

    LiteLLMClient(model="gemini/gemini-3-pro", timeout=12.5, completion=fake).complete(
        messages, TOOLS
    )

    (sent,) = fake.kwargs
    assert sent["model"] == "gemini/gemini-3-pro"
    assert sent["messages"] == messages
    assert sent["tools"] == TOOLS
    assert sent["timeout"] == 12.5
    # Retries belong to the Assistant (ADR-0004), not to the provider SDK.
    assert sent["num_retries"] == 0
    assert sent["_skip_mcp_handler"] is True


def test_no_tools_are_sent_when_none_are_registered() -> None:
    fake = FakeCompletion(model_response({"role": "assistant", "content": "Oi!"}))

    LiteLLMClient(model="anthropic/claude-sonnet-5-5", completion=fake).complete(
        [{"role": "user", "content": "oi"}], []
    )

    assert fake.kwargs[0]["tools"] is None


def test_model_and_timeout_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-6")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")

    client = LiteLLMClient.from_env()

    assert (client.model, client.timeout) == ("openai/gpt-6", 45.0)


def test_defaults_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)

    client = LiteLLMClient.from_env()

    assert (client.model, client.timeout) == (DEFAULT_MODEL, DEFAULT_TIMEOUT_SECONDS)
    assert DEFAULT_MODEL == "anthropic/claude-sonnet-5-5"
    assert DEFAULT_TIMEOUT_SECONDS == 30.0


def test_real_litellm_accepts_our_tool_definitions_offline() -> None:
    # Real litellm.completion; `mock_response` short-circuits the provider call.
    # Guards the dependency set: with tools, litellm 1.106.6 imports its proxy
    # MCP gateway, which needs mcp>=2 while Chainlit 2.12 pins mcp<2.
    offline = functools.partial(litellm.completion, mock_response="Oi! Sou a Lia.")
    client = LiteLLMClient(model="anthropic/claude-sonnet-5-5", completion=offline)

    response = client.complete([{"role": "user", "content": "oi"}], TOOLS)

    assert response.content == "Oi! Sou a Lia."


def test_real_litellm_tool_call_response_is_converted_offline() -> None:
    offline = functools.partial(
        litellm.completion,
        mock_response="",
        mock_tool_calls=[
            {
                "id": "toolu_9",
                "type": "function",
                "function": {"name": "search_products", "arguments": '{"query": "yamaha"}'},
            }
        ],
    )
    client = LiteLLMClient(model="anthropic/claude-sonnet-5-5", completion=offline)

    response = client.complete([{"role": "user", "content": "tem yamaha?"}], TOOLS)

    assert response.tool_calls == [
        ToolCall(id="toolu_9", name="search_products", arguments='{"query": "yamaha"}')
    ]


def test_unexpected_tool_call_type_fails_loudly() -> None:
    # A custom (non-function) tool call cannot be answered by our registry; dropping
    # it silently would leave a tool_use without its tool_result in the history.
    response = model_response({"role": "assistant", "content": None})
    response.choices[0].message.tool_calls = [
        ChatCompletionMessageCustomToolCall(
            id="ctc_1", custom=ChatCompletionCustomToolCallPayload(name="grep", input="x")
        )
    ]
    client = LiteLLMClient(model="anthropic/claude-sonnet-5-5", completion=FakeCompletion(response))

    with pytest.raises(TypeError, match="ChatCompletionMessageCustomToolCall"):
        client.complete([{"role": "user", "content": "oi"}], TOOLS)


def test_system_gets_a_cache_breakpoint_after_the_static_block_when_supported() -> None:
    fake = FakeCompletion(model_response({"role": "assistant", "content": "Oi!"}))
    client = LiteLLMClient(model="m", completion=fake, supports_caching=lambda _model: True)

    client.complete([system_message("PREFIXO", "DINAMICO"), {"role": "user", "content": "oi"}], [])

    (sent,) = fake.kwargs
    messages = sent["messages"]
    assert isinstance(messages, list)
    assert messages[0]["content"] == [
        {"type": "text", "text": "PREFIXO", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "DINAMICO"},
    ]
    assert messages[1] == {"role": "user", "content": "oi"}


def test_system_is_plain_text_without_cache_control_when_unsupported() -> None:
    fake = FakeCompletion(model_response({"role": "assistant", "content": "Oi!"}))
    client = LiteLLMClient(model="m", completion=fake, supports_caching=lambda _model: False)

    client.complete([system_message("PREFIXO", "DINAMICO")], [])

    (sent,) = fake.kwargs
    assert sent["messages"] == [{"role": "system", "content": "PREFIXO\n\nDINAMICO"}]


def test_caching_support_is_asked_for_the_configured_model() -> None:
    asked: list[str] = []

    def supports(model: str) -> bool:
        asked.append(model)
        return False

    fake = FakeCompletion(model_response({"role": "assistant", "content": "Oi!"}))
    LiteLLMClient(model="gemini/x", completion=fake, supports_caching=supports).complete(
        [system_message("a", "b")], []
    )

    assert asked == ["gemini/x"]


def test_real_litellm_knows_prompt_caching_support_offline() -> None:
    assert LiteLLMClient(model="anthropic/claude-sonnet-5-5")._supports_caching(
        "anthropic/claude-sonnet-5-5"
    )
    assert LiteLLMClient(model="bogus/model")._supports_caching("bogus/model") is False
