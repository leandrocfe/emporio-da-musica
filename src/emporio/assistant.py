"""The Assistant (`Assistant`): explicit tool-calling loop (ADR-0001).

Each `reply` is one turn: the Customer message is sent with the history and
the tool definitions; every tool call of a model round is executed and
answered (by `tool_call_id`) before the next round; the loop ends on a final
answer or when `max_rounds` model rounds are used up. Tool calls requested in
that last round are answered with a `round_limit` error and never executed:
the model would not read their results, and a tool may write (ticket 07).

Messages are built on a working copy and committed when the turn completes.
Provider failure closes the turn with a friendly answer, retaining any tool
results already produced without executing those tools again.
"""

import json
import time
from collections.abc import Callable, Sequence
from datetime import datetime

from litellm.exceptions import Timeout as LiteLLMTimeout

from emporio.clock import real_clock
from emporio.events import Event, EventSink, NullEventSink
from emporio.llm import LLMClient, LLMResponse, Message
from emporio.prompt import PROMPT_VERSION, build_system_prompt, static_prompt_hash
from emporio.session import Session
from emporio.tools import ToolContext, ToolRegistry, ToolResult

DEFAULT_MAX_ROUNDS = 5
DEFAULT_HISTORY_TURNS = 20
MAX_RETRIES = 2

ROUND_LIMIT_FALLBACK = (
    "Desculpe, não consegui concluir sua consulta agora. Pode reformular a pergunta? "
    "Se preferir, fale com a loja pelo telefone (67) 3341-4444."
)
# Synthetic answer for tool calls of the last allowed round (never executed).
ROUND_LIMIT_RESULT: ToolResult = {
    "error": {
        "code": "round_limit",
        "message": "Limite de consultas desta mensagem atingido; a ferramenta não foi executada.",
    }
}
EMPTY_ANSWER_FALLBACK = "Desculpe, não entendi. Pode repetir de outro jeito?"
LLM_FAILURE_FALLBACK = (
    "Desculpe, não consegui responder agora. Tente novamente ou fale com a loja "
    "pelo telefone (67) 3341-4444."
)


class Assistant:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        events: EventSink | None = None,
        clock: Callable[[], datetime] = real_clock,
        categories: Sequence[str] = (),
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        history_turns: int = DEFAULT_HISTORY_TURNS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        if history_turns < 1:
            raise ValueError("history_turns must be at least 1")
        self._llm = llm
        self._tools = tools
        self._events = events or NullEventSink()
        self._clock = clock
        self._categories = tuple(categories)
        self._max_rounds = max_rounds
        self._history_turns = history_turns
        self._sleep = sleep
        self._prompt_hash = static_prompt_hash(self._categories)

    def reply(self, session: Session, message: str) -> str:
        """Run one Customer turn and return Lia's answer."""
        self._emit("customer_message", session, content=message)
        try:
            return self._run_turn(session, message)
        except Exception as exc:
            # Audit only; the caller still decides what the Customer sees.
            self._emit("error", session, error_type=type(exc).__name__, message=str(exc))
            raise

    def _run_turn(self, session: Session, message: str) -> str:
        now = self._clock()
        ctx = ToolContext(session=session, now=now, events=self._events)
        turn: list[Message] = [{"role": "user", "content": message}]
        with session.history_lock:
            history = _last_turns(session.history, self._history_turns - 1)
        system = build_system_prompt(self._categories, now)
        definitions = self._tools.definitions()

        answer: str | None = None
        for round_number in range(1, self._max_rounds + 1):
            started = time.perf_counter()
            try:
                response = self._complete_with_retry([system, *history, *turn], definitions)
            except Exception as exc:
                self._emit("error", session, error_type=type(exc).__name__, message=str(exc))
                answer = LLM_FAILURE_FALLBACK
                break
            self._emit_llm_call(session, response, round_number, _elapsed_ms(started))
            if not response.tool_calls:
                answer = response.content or EMPTY_ANSWER_FALLBACK
                break
            turn.append(_assistant_tool_message(response))
            if round_number == self._max_rounds:
                # The model will not be called again, so nobody would read these
                # results: answer each call (the history must stay well formed) but
                # never run tools with side effects whose outcome is then discarded.
                turn.extend(self._skip_tools(response, ctx))
            else:
                turn.extend(self._run_tools(response, ctx))

        if answer is None:
            answer = ROUND_LIMIT_FALLBACK
        turn.append({"role": "assistant", "content": answer})
        with session.history_lock:
            session.history[:] = _last_turns([*session.history, *turn], self._history_turns)
        self._emit("final_response", session, content=answer)
        return answer

    def _complete_with_retry(
        self, messages: Sequence[Message], definitions: Sequence[dict[str, object]]
    ) -> LLMResponse:
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self._llm.complete(messages, definitions)
            except Exception as exc:
                if attempt == MAX_RETRIES or not _is_retryable(exc):
                    raise
                self._sleep(float(2**attempt))
        raise AssertionError("unreachable")

    def _run_tools(self, response: LLMResponse, ctx: ToolContext) -> list[Message]:
        """Execute every tool call of the round, in order; one `tool` message each."""
        results: list[Message] = []
        for call in response.tool_calls:
            started = time.perf_counter()
            outcome = self._tools.execute(call.name, call.arguments, ctx)
            self._emit(
                "tool_call",
                ctx.session,
                name=call.name,
                arguments=call.arguments,
                ok=outcome.ok,
                duration_ms=_elapsed_ms(started),
                result=outcome.result,
            )
            results.append(_tool_message(call.id, outcome.result))
        return results

    def _skip_tools(self, response: LLMResponse, ctx: ToolContext) -> list[Message]:
        results: list[Message] = []
        for call in response.tool_calls:
            outcome = ROUND_LIMIT_RESULT
            self._emit(
                "tool_call",
                ctx.session,
                name=call.name,
                arguments=call.arguments,
                ok=False,
                duration_ms=0,
                result=outcome,
            )
            results.append(_tool_message(call.id, outcome))
        return results

    def _emit_llm_call(
        self, session: Session, response: LLMResponse, round_number: int, latency_ms: int
    ) -> None:
        usage = response.usage
        self._emit(
            "llm_call",
            session,
            round=round_number,
            model=response.model,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            cache_read_tokens=usage.cache_read_tokens if usage else None,
            cache_creation_tokens=usage.cache_creation_tokens if usage else None,
            prompt_hash=self._prompt_hash,
            prompt_version=PROMPT_VERSION,
            tool_calls=[call.name for call in response.tool_calls],
        )

    def _emit(self, event_type: str, session: Session, **data: object) -> None:
        self._events.emit(Event(type=event_type, session_id=session.id, data=data))


def _assistant_tool_message(response: LLMResponse) -> Message:
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in response.tool_calls
        ],
    }


def _tool_message(call_id: str, result: ToolResult) -> Message:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(result, ensure_ascii=False),
    }


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or 500 <= status <= 599 or (
            status == 408 and isinstance(exc, (TimeoutError, LiteLLMTimeout))
        )
    return isinstance(exc, (TimeoutError, LiteLLMTimeout))


def _last_turns(history: Sequence[Message], limit: int) -> list[Message]:
    if limit == 0:
        return []
    starts = [index for index, message in enumerate(history) if message["role"] == "user"]
    if not starts:
        return []
    return list(history[starts[max(0, len(starts) - limit)] :])
