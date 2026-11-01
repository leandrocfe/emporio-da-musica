"""The Assistant (`Assistant`): explicit tool-calling loop (ADR-0001).

Each `reply` is one turn: the Customer message is sent with the history and
the tool definitions; every tool call of a model round is executed and
answered (by `tool_call_id`) before the next round; the loop ends on a final
answer or when `max_rounds` model rounds are used up. Tool calls requested in
that last round are answered with a `round_limit` error and never executed:
the model would not read their results, and a tool may write (ticket 07).

The turn is atomic for the Session: messages are built on a working copy and
appended to `session.history` only when the turn completes, so an exception
(e.g. the provider is down) never leaves a dangling user message or a tool
call without its result in the history.
"""

import json
import time
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from emporio.events import Event, EventSink, NullEventSink
from emporio.llm import LLMClient, LLMResponse, Message
from emporio.prompt import build_system_prompt
from emporio.session import Session
from emporio.tools import ToolContext, ToolRegistry, ToolResult

STORE_TIMEZONE = ZoneInfo("America/Campo_Grande")
DEFAULT_MAX_ROUNDS = 5

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


def store_clock() -> datetime:
    """Real clock in the store's timezone (`AGENT_NOW` override is ticket 05)."""
    return datetime.now(STORE_TIMEZONE)


class Assistant:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        events: EventSink | None = None,
        clock: Callable[[], datetime] = store_clock,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        self._llm = llm
        self._tools = tools
        self._events = events or NullEventSink()
        self._clock = clock
        self._max_rounds = max_rounds

    def reply(self, session: Session, message: str) -> str:
        """Run one Customer turn and return Lia's answer."""
        self._emit("customer_message", session, content=message)
        ctx = ToolContext(session=session, now=self._clock(), events=self._events)
        turn: list[Message] = [{"role": "user", "content": message}]
        system: Message = {"role": "system", "content": build_system_prompt()}
        definitions = self._tools.definitions()

        answer: str | None = None
        for round_number in range(1, self._max_rounds + 1):
            started = time.perf_counter()
            response = self._llm.complete([system, *session.history, *turn], definitions)
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
        session.history.extend(turn)
        self._emit("final_response", session, content=answer)
        return answer

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
