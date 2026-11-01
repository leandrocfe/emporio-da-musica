"""Reference date (`now`): the moment the Assistant treats as "now".

Real clock in the store's timezone by default; `AGENT_NOW` (ISO 8601) pins it
for reproducible demos. The same callable feeds the prompt and `ToolContext.now`,
so both always agree.
"""

from collections.abc import Callable, Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

STORE_TIMEZONE = ZoneInfo("America/Campo_Grande")

Clock = Callable[[], datetime]


def real_clock() -> datetime:
    return datetime.now(STORE_TIMEZONE)


def parse_agent_now(value: str) -> datetime:
    """ISO 8601 to store time; no offset means store time, an offset is converted."""
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(
            f"AGENT_NOW inválido: {value!r}. Use ISO 8601, ex.: 2026-03-23T10:00:00-04:00."
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=STORE_TIMEZONE)
    return parsed.astimezone(STORE_TIMEZONE)


def clock_from_env(environ: Mapping[str, str]) -> Clock:
    """`AGENT_NOW` pins the clock (validated now, at startup); otherwise the real one."""
    raw = environ.get("AGENT_NOW", "").strip()
    if not raw:
        return real_clock
    fixed = parse_agent_now(raw)
    return lambda: fixed
