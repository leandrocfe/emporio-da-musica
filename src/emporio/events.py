"""`EventSink` port: what happened inside the Assistant loop (ADR-0001).

The default sink discards everything; the JSONL audit log (ticket 08) is
another implementation. Event types: `customer_message`, `llm_call`,
`tool_call`, `final_response` (and `error`, emitted from ticket 09 on).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Event:
    type: str
    session_id: str
    data: Mapping[str, object] = field(default_factory=dict)


class EventSink(Protocol):
    def emit(self, event: Event) -> None: ...


class NullEventSink:
    """No-op sink: the Assistant works without anyone listening."""

    def emit(self, event: Event) -> None:
        pass
