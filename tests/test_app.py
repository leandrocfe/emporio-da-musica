"""Composition root: the production Assistant answers from the real catalog."""

import json
from datetime import datetime
from pathlib import Path

from emporio.app import build_assistant, build_event_sink_from_env
from emporio.audit_log import JsonlEventSink
from emporio.clock import STORE_TIMEZONE, clock_from_env
from emporio.events import Event
from emporio.session import Session

from .fakes import ScriptedLLM, asks, says, tool_call


def test_assembled_assistant_searches_the_seeded_catalog(db_path: Path) -> None:
    llm = ScriptedLLM(
        [asks(tool_call("call_1", "search_products", {"query": "violao yamaha"})), says("Temos!")]
    )

    answer = build_assistant(llm=llm, db_path=db_path).reply(Session(id="s1"), "tem violão Yamaha?")

    assert answer == "Temos!"
    result = llm.tool_results(1)["call_1"]
    assert isinstance(result, dict)
    assert result["total"] == 7


def test_audit_log_ts_is_the_real_clock_even_with_agent_now_fixed(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    environ = {"AGENT_NOW": "2026-03-23T10:00:00-04:00", "LOG_PATH": str(log)}
    before = datetime.now(STORE_TIMEZONE)

    build_event_sink_from_env(environ).emit(Event("customer_message", "s1", {"content": "oi"}))

    after = datetime.now(STORE_TIMEZONE)
    ts = datetime.fromisoformat(json.loads(log.read_text("utf-8"))["ts"])
    assert before <= ts <= after
    assert ts.utcoffset() == before.utcoffset()
    assert ts != clock_from_env(environ)()  # AGENT_NOW still pins the Reference date


def test_event_sink_uses_an_injected_clock_instead_of_agent_now(
    tmp_path: Path, db_path: Path
) -> None:
    log = tmp_path / "audit.jsonl"
    injected = datetime(2030, 1, 2, 3, 4, 5, tzinfo=STORE_TIMEZONE)
    agent_now = datetime(2026, 3, 23, 10, tzinfo=STORE_TIMEZONE)
    llm = ScriptedLLM([says("Oi!")])
    assistant = build_assistant(
        llm=llm,
        db_path=db_path,
        events=JsonlEventSink(log, clock=lambda: injected),
        clock=lambda: agent_now,
    )

    assistant.reply(Session(id="s1"), "oi")

    stamps = {json.loads(line)["ts"] for line in log.read_text("utf-8").splitlines()}
    assert stamps == {injected.isoformat()}
