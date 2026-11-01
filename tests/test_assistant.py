"""Seam 2 — `Assistant.reply` with a scripted language model (ADR-0001)."""

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio.assistant import LLM_FAILURE_FALLBACK, ROUND_LIMIT_FALLBACK, Assistant
from emporio.llm import LLMResponse, Message
from emporio.session import Session
from emporio.tools import ToolContext, ToolRegistry, ToolResult

from .fakes import RecordingSink, ScriptedLLM, asks, says, tool_call

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande"))

ECHO_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


@dataclass
class EchoTool:
    """A test tool that records what its handler received."""

    received: list[tuple[Mapping[str, object], ToolContext]] = field(default_factory=list)

    def __call__(self, args: Mapping[str, object], ctx: ToolContext) -> ToolResult:
        self.received.append((args, ctx))
        return {"echo": args["text"]}


def make_assistant(llm: ScriptedLLM, echo: EchoTool | None = None) -> Assistant:
    registry = ToolRegistry()
    registry.register("echo", "Repete o texto.", ECHO_SCHEMA, echo or EchoTool())
    return Assistant(llm, registry, clock=lambda: NOW)


def test_reply_returns_the_model_final_answer() -> None:
    llm = ScriptedLLM([says("Oi! Sou a Lia.")])

    assert make_assistant(llm).reply(Session(id="s1"), "oi") == "Oi! Sou a Lia."


def test_requested_tool_runs_with_model_arguments_and_its_result_goes_back() -> None:
    echo = EchoTool()
    llm = ScriptedLLM([asks(tool_call("call_1", "echo", {"text": "violão"})), says("Pronto")])

    answer = make_assistant(llm, echo).reply(Session(id="s1"), "repete violão")

    assert answer == "Pronto"
    assert [args for args, _ in echo.received] == [{"text": "violão"}]
    assert llm.tool_results(1) == {"call_1": {"echo": "violão"}}


def test_handler_context_carries_the_session_and_reference_date() -> None:
    echo = EchoTool()
    session = Session(id="s1")
    llm = ScriptedLLM([asks(tool_call("call_1", "echo", {"text": "x"})), says("ok")])

    make_assistant(llm, echo).reply(session, "oi")

    (_, ctx) = echo.received[0]
    assert ctx.session is session
    assert ctx.now == NOW


def test_model_receives_the_registered_tool_definitions() -> None:
    llm = ScriptedLLM([says("ok")])

    make_assistant(llm).reply(Session(id="s1"), "oi")

    (definition,) = llm.calls[0].tools
    assert definition == {
        "type": "function",
        "function": {"name": "echo", "description": "Repete o texto.", "parameters": ECHO_SCHEMA},
    }


def test_every_tool_call_of_a_round_is_answered_by_id_before_the_next_model_call() -> None:
    echo = EchoTool()
    llm = ScriptedLLM(
        [
            asks(
                tool_call("call_a", "echo", {"text": "violão"}),
                tool_call("call_b", "echo", {"text": "guitarra"}),
            ),
            says("Achei os dois"),
        ]
    )

    make_assistant(llm, echo).reply(Session(id="s1"), "violão e guitarra")

    second_request = llm.calls[1].messages
    assert [m["role"] for m in second_request[-3:]] == ["assistant", "tool", "tool"]
    assert llm.tool_results(1) == {
        "call_a": {"echo": "violão"},
        "call_b": {"echo": "guitarra"},
    }


def test_history_is_kept_between_messages_of_the_same_session() -> None:
    session = Session(id="s1")
    llm = ScriptedLLM(
        [
            asks(tool_call("call_1", "echo", {"text": "C40"})),
            says("O C40 custa R$ 599,90."),
            says("Ele tem cordas de nylon."),
        ]
    )
    assistant = make_assistant(llm)

    assistant.reply(session, "quanto custa o C40?")
    assistant.reply(session, "e as cordas?")

    contents = [
        m.get("content") for m in llm.calls[2].messages if m["role"] in {"user", "assistant"}
    ]
    assert contents == [
        "quanto custa o C40?",
        None,  # the assistant message that carried the tool call
        "O C40 custa R$ 599,90.",
        "e as cordas?",
    ]


def test_another_session_does_not_see_the_history() -> None:
    llm = ScriptedLLM([says("Oi, Ana!"), says("Oi!")])
    assistant = make_assistant(llm)

    assistant.reply(Session(id="ana"), "sou a Ana")
    assistant.reply(Session(id="bia"), "oi")

    user_messages = [m["content"] for m in llm.calls[1].messages if m["role"] == "user"]
    assert user_messages == ["oi"]


def test_system_prompt_presents_lia_before_the_conversation() -> None:
    llm = ScriptedLLM([says("ok")])

    make_assistant(llm).reply(Session(id="s1"), "oi")

    first = llm.calls[0].messages[0]
    assert first["role"] == "system"
    assert "Lia" in str(first["content"])


def test_unknown_tool_becomes_a_structured_error_for_the_model() -> None:
    llm = ScriptedLLM([asks(tool_call("call_1", "delete_orders", {})), says("Não consigo.")])

    answer = make_assistant(llm).reply(Session(id="s1"), "apaga tudo")

    assert answer == "Não consigo."
    error = llm.tool_results(1)["call_1"]
    assert isinstance(error, dict)
    assert error["error"]["code"] == "unknown_tool"


def test_malformed_json_arguments_become_a_structured_error() -> None:
    echo = EchoTool()
    llm = ScriptedLLM([asks(tool_call("call_1", "echo", '{"text": ')), says("ops")])

    make_assistant(llm, echo).reply(Session(id="s1"), "oi")

    assert echo.received == []
    assert llm.tool_results(1)["call_1"] == {
        "error": {
            "code": "invalid_arguments",
            "message": "Argumentos não são JSON válido: Expecting value.",
        }
    }


def test_session_sent_by_the_model_is_rejected_not_used() -> None:
    echo = EchoTool()
    llm = ScriptedLLM(
        [asks(tool_call("call_1", "echo", {"text": "x", "session_id": "outra"})), says("ok")]
    )

    make_assistant(llm, echo).reply(Session(id="s1"), "oi")

    assert echo.received == []
    error = llm.tool_results(1)["call_1"]
    assert isinstance(error, dict)
    assert error["error"]["code"] == "invalid_arguments"
    assert "session_id" in error["error"]["message"]


def test_missing_required_argument_becomes_a_structured_error() -> None:
    llm = ScriptedLLM([asks(tool_call("call_1", "echo", {})), says("ok")])

    make_assistant(llm).reply(Session(id="s1"), "oi")

    error = llm.tool_results(1)["call_1"]
    assert isinstance(error, dict)
    assert error["error"]["code"] == "invalid_arguments"
    assert "text" in error["error"]["message"]


def test_round_limit_ends_the_turn_with_a_friendly_fallback() -> None:
    looping = [asks(tool_call(f"call_{n}", "echo", {"text": "de novo"})) for n in range(3)]
    llm = ScriptedLLM(looping)
    assistant = Assistant(llm, _echo_registry(), clock=lambda: NOW, max_rounds=3)

    answer = assistant.reply(Session(id="s1"), "oi")

    assert answer == ROUND_LIMIT_FALLBACK
    assert len(llm.calls) == 3


def test_after_the_round_limit_the_history_stays_well_formed() -> None:
    session = Session(id="s1")
    script = [asks(tool_call("call_1", "echo", {"text": "x"})), says("Agora sim.")]
    assistant = Assistant(ScriptedLLM(script), _echo_registry(), clock=lambda: NOW, max_rounds=1)

    assistant.reply(session, "oi")

    roles = [m["role"] for m in session.history]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert session.history[-1]["content"] == ROUND_LIMIT_FALLBACK


class ProviderDownError(Exception):
    pass


@dataclass
class FailingLLM:
    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, object]]
    ) -> LLMResponse:
        raise ProviderDownError


def test_failed_turn_returns_fallback_and_keeps_a_complete_history() -> None:
    session = Session(id="s1")
    assistant = Assistant(FailingLLM(), _echo_registry(), clock=lambda: NOW)

    assert assistant.reply(session, "oi") == LLM_FAILURE_FALLBACK

    assert [m["role"] for m in session.history] == ["user", "assistant"]


class StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@dataclass
class RetryLLM:
    script: list[LLMResponse | Exception]
    calls: int = 0

    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, object]]
    ) -> LLMResponse:
        self.calls += 1
        result = self.script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.parametrize("error", [TimeoutError(), StatusError(429), StatusError(500)])
def test_retry_exhaustion_emits_error_and_returns_fallback(error: Exception) -> None:
    llm = RetryLLM([error, error, error])
    delays: list[float] = []
    sink = RecordingSink()
    assistant = Assistant(llm, _echo_registry(), events=sink, sleep=delays.append)

    assert assistant.reply(Session(id="s1"), "oi") == LLM_FAILURE_FALLBACK
    assert llm.calls == 3
    assert delays == [1.0, 2.0]
    assert [event.type for event in sink.events] == ["customer_message", "error", "final_response"]


@pytest.mark.parametrize("status", [400, 401, 403, 499])
def test_non_retryable_status_is_attempted_only_once(status: int) -> None:
    llm = RetryLLM([StatusError(status)])
    delays: list[float] = []
    assistant = Assistant(llm, _echo_registry(), sleep=delays.append)

    assert assistant.reply(Session(id="s1"), "oi") == LLM_FAILURE_FALLBACK
    assert llm.calls == 1
    assert delays == []


def test_retry_does_not_repeat_a_tool_that_already_ran() -> None:
    echo = EchoTool()
    registry = ToolRegistry()
    registry.register("echo", "Repete o texto.", ECHO_SCHEMA, echo)
    llm = RetryLLM([asks(tool_call("c1", "echo", {"text": "x"})), TimeoutError(), says("ok")])
    assistant = Assistant(llm, registry, sleep=lambda _: None)

    assert assistant.reply(Session(id="s1"), "oi") == "ok"
    assert len(echo.received) == 1
    assert llm.calls == 3


def test_history_truncation_keeps_complete_tool_turns() -> None:
    llm = ScriptedLLM(
        [
            asks(tool_call("c1", "echo", {"text": "x"})),
            says("primeira"),
            asks(tool_call("c2", "echo", {"text": "y"})),
            says("segunda"),
            says("terceira"),
        ]
    )
    session = Session(id="s1")
    assistant = Assistant(llm, _echo_registry(), history_turns=2)

    assistant.reply(session, "um")
    assistant.reply(session, "dois")
    assistant.reply(session, "três")

    sent = llm.calls[4].messages[1:]
    assert [message["role"] for message in sent] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert sent[0]["content"] == "dois"
    assert sent[2]["tool_call_id"] == "c2"
    assert session.history == [
        *sent[:-1],
        {"role": "user", "content": "três"},
        {"role": "assistant", "content": "terceira"},
    ]


def test_concurrent_replies_keep_both_complete_turns() -> None:
    barrier = threading.Barrier(2)

    class ConcurrentLLM:
        def complete(
            self, messages: Sequence[Message], tools: Sequence[dict[str, object]]
        ) -> LLMResponse:
            customer = next(str(m["content"]) for m in reversed(messages) if m["role"] == "user")
            if messages[-1]["role"] == "user":
                barrier.wait(timeout=5)
                return asks(tool_call(customer, "echo", {"text": customer}))
            return says(f"resposta {customer}")

    session = Session(id="s1")
    assistant = Assistant(ConcurrentLLM(), _echo_registry(), history_turns=2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = list(pool.map(lambda message: assistant.reply(session, message), ["um", "dois"]))

    assert answers == ["resposta um", "resposta dois"]
    assert len(session.history) == 8
    turns = [session.history[:4], session.history[4:]]
    assert {turn[0]["content"] for turn in turns} == {"um", "dois"}
    for turn in turns:
        assert [message["role"] for message in turn] == ["user", "assistant", "tool", "assistant"]
        assert turn[2]["tool_call_id"] == turn[0]["content"]
        assert turn[3]["content"] == f"resposta {turn[0]['content']}"


def test_loop_events_reach_the_sink_in_order() -> None:
    sink = RecordingSink()
    llm = ScriptedLLM([asks(tool_call("call_1", "echo", {"text": "x"})), says("ok")])
    assistant = Assistant(llm, _echo_registry(), events=sink, clock=lambda: NOW)

    assistant.reply(Session(id="s1"), "oi")

    assert [(e.type, e.session_id) for e in sink.events] == [
        ("customer_message", "s1"),
        ("llm_call", "s1"),
        ("tool_call", "s1"),
        ("llm_call", "s1"),
        ("final_response", "s1"),
    ]


def _echo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("echo", "Repete o texto.", ECHO_SCHEMA, EchoTool())
    return registry


def test_tool_calls_of_the_last_allowed_round_are_answered_but_not_executed() -> None:
    # Tools with side effects (register_complaint, ticket 07) must not run when
    # the model will never get to read their results.
    echo = EchoTool()
    registry = ToolRegistry()
    registry.register("echo", "Repete o texto.", ECHO_SCHEMA, echo)
    session = Session(id="s1")
    llm = ScriptedLLM(
        [
            asks(tool_call("call_1", "echo", {"text": "primeira"})),
            asks(
                tool_call("call_2", "echo", {"text": "segunda"}),
                tool_call("call_3", "echo", {"text": "terceira"}),
            ),
        ]
    )

    answer = Assistant(llm, registry, clock=lambda: NOW, max_rounds=2).reply(session, "oi")

    assert answer == ROUND_LIMIT_FALLBACK
    assert [args for args, _ in echo.received] == [{"text": "primeira"}]
    assert [m["role"] for m in session.history] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "tool",
        "assistant",
    ]
    unanswered = {
        str(m["tool_call_id"]): json.loads(str(m["content"])) for m in session.history[4:6]
    }
    assert set(unanswered) == {"call_2", "call_3"}
    assert all(r["error"]["code"] == "round_limit" for r in unanswered.values())


def fixed_clock(moment: datetime) -> Callable[[], datetime]:
    return lambda: moment


def system_blocks(llm: ScriptedLLM) -> list[dict[str, str]]:
    content = llm.calls[0].messages[0]["content"]
    assert isinstance(content, list)
    return content


def test_static_prefix_is_stable_across_reference_dates_and_dynamic_block_follows() -> None:
    sent: list[list[dict[str, str]]] = []
    for moment in (NOW, NOW.replace(day=22, hour=15)):  # Monday 10h, Sunday 15h
        llm = ScriptedLLM([says("ok")])
        registry = ToolRegistry()
        Assistant(llm, registry, clock=fixed_clock(moment), categories=["Violões"]).reply(
            Session(id="s1"), "oi"
        )
        sent.append(system_blocks(llm))

    (monday_static, monday_dynamic), (sunday_static, sunday_dynamic) = sent
    assert monday_static == sunday_static
    assert "Violões" in monday_static["text"]
    assert "ABERTA" in monday_dynamic["text"]
    assert "FECHADA" in sunday_dynamic["text"]
    assert "Situação da loja" not in monday_static["text"]


def test_prompt_and_tools_share_the_same_reference_date() -> None:
    echo = EchoTool()
    llm = ScriptedLLM([asks(tool_call("call_1", "echo", {"text": "x"})), says("ok")])

    make_assistant(llm, echo).reply(Session(id="s1"), "oi")

    assert f"{NOW:%Y-%m-%d %H:%M}" in system_blocks(llm)[1]["text"]
    assert echo.received[0][1].now == NOW
