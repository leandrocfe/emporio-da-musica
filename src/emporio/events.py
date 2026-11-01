"""`EventSink` port: what happened inside the Assistant loop (ADR-0001).

The default sink discards everything; the masked JSONL audit log
(`emporio.audit_log`) is the production implementation. Event types:
`customer_message`, `llm_call`, `tool_call`, `final_response` and `error`.
Payloads may carry personal data: masking is the sink's job, not the emitter's.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

EventType = Literal["customer_message", "llm_call", "tool_call", "final_response", "error"]


@dataclass(frozen=True, slots=True)
class Event:
    type: EventType
    session_id: str
    data: Mapping[str, object] = field(default_factory=dict)


class EventSink(Protocol):
    def emit(self, event: Event) -> None: ...


class NullEventSink:
    """No-op sink: the Assistant works without anyone listening."""

    def emit(self, event: Event) -> None:
        pass
