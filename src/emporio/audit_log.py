"""JSONL audit log: an `EventSink` that appends one masked JSON object per line (ticket 08).

Line shape: `{"ts", "session_id", "type", ...event data}`. `ts` is ISO 8601 with
offset, from the injected clock (the same one the Assistant uses, so `AGENT_NOW`
pins both). Everything goes through `emporio.masking` before it is serialized;
tool results longer than `max_result_chars` (after masking) are replaced by
`{"truncated": true, "chars": <full length>, "preview": <first chars>}`, so a
search with many Products does not bloat the log.

Text fields (Customer message, answer, error message) longer than
`max_text_chars` (10 000) are clipped after masking, with a `[truncated, N chars]`
marker; the model still receives the whole message, only the log is bounded.

Failure policy: the log is secondary to the Customer's reply. An `OSError`
(disk full, permission, missing mount), a `ValueError`/`TypeError` (encoding,
serialization) or a `RecursionError` (absurdly nested data) never propagates; it is printed once to
stderr per failure streak (not silent, not one line per event) and the sink tries
again on the next event. The file is opened per line in append mode under a lock:
Chainlit runs replies in worker threads, one `write` of a whole line keeps lines
whole, and re-opening survives log rotation or a bind mount that appears late.
"""

import json
import sys
import threading
from collections.abc import Mapping
from pathlib import Path

from emporio.clock import Clock, real_clock
from emporio.events import Event
from emporio.masking import mask_event_data

DEFAULT_LOG_PATH = Path("logs/audit.jsonl")
LOG_FILENAME = "audit.jsonl"
DEFAULT_MAX_RESULT_CHARS = 2000
DEFAULT_MAX_TEXT_CHARS = 10_000
# Anything that can go wrong turning an event into a line or appending it: the log
# must never take the Customer's reply down with it.
_LOG_ERRORS = (OSError, ValueError, TypeError, RecursionError)


def log_path_from_env(environ: Mapping[str, str]) -> Path:
    """`LOG_PATH`, else `LOG_DIR/audit.jsonl`, else `logs/audit.jsonl` (relative to cwd)."""
    log_path = environ.get("LOG_PATH", "").strip()
    if log_path:
        return Path(log_path)
    log_dir = environ.get("LOG_DIR", "").strip()
    if log_dir:
        return Path(log_dir) / LOG_FILENAME
    return DEFAULT_LOG_PATH


class JsonlEventSink:
    def __init__(
        self,
        path: Path,
        clock: Clock = real_clock,
        max_result_chars: int = DEFAULT_MAX_RESULT_CHARS,
        max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
    ) -> None:
        self._path = path
        self._clock = clock
        self._max_result_chars = max_result_chars
        self._max_text_chars = max_text_chars
        self._lock = threading.Lock()
        self._failing = False

    def emit(self, event: Event) -> None:
        try:
            line = self._serialize(event)
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                # backslashreplace: a lone surrogate in a message is written as \udXXX
                # instead of raising UnicodeEncodeError.
                with self._path.open("a", encoding="utf-8", errors="backslashreplace") as file:
                    file.write(line + "\n")
        except _LOG_ERRORS as exc:
            self._report_failure(exc)
        else:
            self._failing = False

    def _report_failure(self, exc: Exception) -> None:
        if self._failing:
            return
        self._failing = True
        # Only the error kind (and the OS reason): the message may echo logged data.
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else type(exc).__name__
        print(f"audit log: cannot write to {self._path}: {reason}", file=sys.stderr)

    def _serialize(self, event: Event) -> str:
        data = mask_event_data(event.type, event.data)
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = self._clip(value)
        if event.type == "tool_call" and "result" in data:
            data["result"] = self._summarize(data["result"])
        record: dict[str, object] = {
            "ts": self._clock().isoformat(),
            "session_id": event.session_id,
            "type": event.type,
        }
        record.update((key, value) for key, value in data.items() if key not in record)
        return json.dumps(record, ensure_ascii=False, default=str)

    def _clip(self, text: str) -> str:
        if len(text) <= self._max_text_chars:
            return text
        return f"{text[: self._max_text_chars]}...[truncated, {len(text)} chars]"

    def _summarize(self, result: object) -> object:
        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) <= self._max_result_chars:
            return result
        return {
            "truncated": True,
            "chars": len(text),
            "preview": text[: self._max_result_chars],
        }
