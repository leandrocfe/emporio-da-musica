"""Seams: `ComplaintService` over SQLite and `register_complaint` as the model sees it."""

import re
import sqlite3
import threading
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import pytest

from emporio.app import build_assistant
from emporio.assistant import Assistant
from emporio.clock import STORE_TIMEZONE
from emporio.complaint_tools import (
    MAX_CONTACT_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_ORDER_REFERENCE_LENGTH,
    register_complaint_tools,
)
from emporio.complaints import ComplaintService
from emporio.seed import seed
from emporio.session import Session
from emporio.tools import ToolRegistry

from .conftest import DATA_DIR
from .fakes import ScriptedLLM, asks, says, tool_call

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=STORE_TIMEZONE)
PROTOCOL = re.compile(r"EMP-20260323-[2-9A-HJKMNP-TW-Z]{6}")


def register(
    service: ComplaintService,
    session_id: str = "s1",
    description: str = "Chegou riscado",
    order_id: str | None = "7",
    name: str = "Ana Souza",
    contact: str = "ana@example.com",
    now: datetime = NOW,
) -> str:
    return service.register(
        session_id=session_id,
        name=name,
        contact=contact,
        description=description,
        order_id=order_id,
        now=now,
    )


def call_tool(
    db_path: Path, arguments: Mapping[str, object] | str, session: Session | None = None
) -> dict[str, object]:
    registry = ToolRegistry()
    register_complaint_tools(registry, ComplaintService(db_path))
    llm = ScriptedLLM([asks(tool_call("c1", "register_complaint", arguments)), says("ok")])
    Assistant(llm, registry, clock=lambda: NOW).reply(session or Session(id="s1"), "reclamar")
    result = llm.tool_results(1)["c1"]
    assert isinstance(result, dict)
    return result


def rows(db_path: Path, sql: str = "SELECT * FROM complaints") -> list[tuple[object, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def dump(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return list(conn.iterdump())
    finally:
        conn.close()


def test_complaint_is_saved_and_found_by_protocol_with_every_field(db_path: Path) -> None:
    service = ComplaintService(db_path)

    protocol = register(service)

    assert PROTOCOL.fullmatch(protocol)
    found = service.find_by_protocol(protocol)
    assert found is not None
    assert (found.session_id, found.name, found.contact) == ("s1", "Ana Souza", "ana@example.com")
    assert (found.description, found.order_id) == ("Chegou riscado", "7")
    assert found.created_at == "2026-03-23T10:00:00-04:00"
    assert service.find_by_protocol("EMP-20260323-AAAAAA") is None


def test_protocol_is_unique_across_many_records(db_path: Path) -> None:
    service = ComplaintService(db_path)

    protocols = {register(service, f"s{n}") for n in range(50)}

    assert len(protocols) == 50
    assert all(PROTOCOL.fullmatch(protocol) for protocol in protocols)
    assert rows(db_path, "SELECT count(*) FROM complaints") == [(50,)]


def test_protocol_collision_draws_another_suffix(db_path: Path) -> None:
    suffixes = iter(["AAAAAA", "AAAAAA", "BBBBBB"])
    service = ComplaintService(db_path, suffix=lambda: next(suffixes))

    first = register(service, "s1")
    second = register(service, "s2")

    assert (first, second) == ("EMP-20260323-AAAAAA", "EMP-20260323-BBBBBB")


def test_same_session_and_description_return_the_same_protocol_once(db_path: Path) -> None:
    service = ComplaintService(db_path)

    first = register(service)
    again = register(service, description="Chegou riscado")

    assert first == again
    assert rows(db_path, "SELECT count(*) FROM complaints") == [(1,)]


def test_correcting_contact_updates_the_row_and_keeps_the_protocol(db_path: Path) -> None:
    service = ComplaintService(db_path)
    first = register(service, order_id="7")

    again = register(
        service, name="Ana S.", contact="67999990000", order_id="8", now=NOW.replace(hour=11)
    )

    assert again == first
    assert rows(
        db_path, "SELECT protocol, name, contact, order_id, created_at FROM complaints"
    ) == [(first, "Ana S.", "67999990000", "8", "2026-03-23T10:00:00-04:00")]


def test_omitted_order_id_keeps_the_previous_one(db_path: Path) -> None:
    service = ComplaintService(db_path)
    register(service, order_id="7")

    register(service, contact="67999990000", order_id=None)

    assert rows(db_path, "SELECT contact, order_id FROM complaints") == [("67999990000", "7")]


def test_protocol_collision_never_updates_another_complaint(db_path: Path) -> None:
    suffixes = iter(["AAAAAA", "AAAAAA", "BBBBBB"])
    service = ComplaintService(db_path, suffix=lambda: next(suffixes))
    first = register(service, "s1", name="Ana")

    second = register(service, "s2", name="Bia")

    assert second != first
    assert rows(db_path, "SELECT protocol, name FROM complaints ORDER BY id") == [
        (first, "Ana"),
        (second, "Bia"),
    ]


def test_protocol_date_is_the_store_day_not_the_utc_day(db_path: Path) -> None:
    late = datetime(2026, 3, 23, 23, 30, tzinfo=STORE_TIMEZONE)  # already 03-24 in UTC

    protocol = register(ComplaintService(db_path), now=late)

    assert re.fullmatch(r"EMP-20260323-[2-9A-HJKMNP-TW-Z]{6}", protocol)


def test_other_session_same_description_gets_another_protocol(db_path: Path) -> None:
    service = ComplaintService(db_path)

    assert register(service, "s1") != register(service, "s2")
    assert rows(db_path, "SELECT count(*) FROM complaints") == [(2,)]


def test_same_session_other_description_is_a_new_complaint(db_path: Path) -> None:
    service = ComplaintService(db_path)

    assert register(service) != register(service, description="Também faltou o cabo")


def test_concurrent_calls_of_one_session_leave_one_row(db_path: Path) -> None:
    service = ComplaintService(db_path)
    barrier = threading.Barrier(8, timeout=5)
    protocols: list[str] = []

    def work() -> None:
        barrier.wait()
        protocols.append(register(service))

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(protocols) == 8
    assert len(set(protocols)) == 1
    assert rows(db_path, "SELECT count(*) FROM complaints") == [(1,)]


def test_complaints_survive_a_new_seed_through_the_service(db_path: Path) -> None:
    service = ComplaintService(db_path)
    protocol = register(service)

    seed(db_path, DATA_DIR)

    found = service.find_by_protocol(protocol)
    assert found is not None
    assert found.description == "Chegou riscado"


def test_tool_saves_and_returns_only_protocol_and_deadline(db_path: Path) -> None:
    result = call_tool(
        db_path,
        {
            "name": "  Ana   Souza ",
            "contact": "ana@example.com",
            "description": "Chegou\n riscado",
            "order_id": 7,
        },
    )

    assert set(result) == {"protocol", "response_deadline"}
    assert result["response_deadline"] == "até 24 horas úteis"
    protocol = result["protocol"]
    assert isinstance(protocol, str)
    found = ComplaintService(db_path).find_by_protocol(protocol)
    assert found is not None
    assert (found.name, found.description, found.order_id) == ("Ana Souza", "Chegou riscado", "7")
    assert found.session_id == "s1"


def test_tool_is_idempotent_per_session_ignoring_whitespace_differences(db_path: Path) -> None:
    session = Session(id="tab-1")
    args = {"name": "Ana", "contact": "ana@example.com", "description": "Chegou riscado"}

    first = call_tool(db_path, args, session)
    again = call_tool(db_path, {**args, "description": " Chegou   riscado "}, session)

    assert first == again
    assert rows(db_path, "SELECT count(*) FROM complaints") == [(1,)]


def test_order_id_is_a_free_reference_without_lookup_or_echo(db_path: Path) -> None:
    result = call_tool(
        db_path,
        {"name": "Ana", "contact": "ana", "description": "Cadê o pedido?", "order_id": 999},
    )

    assert set(result) == {"protocol", "response_deadline"}
    assert rows(db_path, "SELECT order_id FROM complaints") == [("999",)]


@pytest.mark.parametrize("blank", ["", "  "])
def test_blank_order_id_is_stored_as_null(db_path: Path, blank: str) -> None:
    call_tool(
        db_path, {"name": "Ana", "contact": "ana", "description": "Problema", "order_id": blank}
    )

    assert rows(db_path, "SELECT order_id FROM complaints") == [(None,)]


def test_order_id_is_optional(db_path: Path) -> None:
    call_tool(db_path, {"name": "Ana", "contact": "ana", "description": "Atendimento ruim"})

    assert rows(db_path, "SELECT order_id FROM complaints") == [(None,)]


@pytest.mark.parametrize(
    "arguments",
    [
        {"contact": "c", "description": "d"},  # missing name
        {"name": "   ", "contact": "c", "description": "d"},
        {"name": "n", "contact": "", "description": "d"},
        {"name": "n", "contact": "c", "description": " \n "},
        {"name": "n", "contact": "c" * (MAX_CONTACT_LENGTH + 1), "description": "d"},
        {"name": 5, "contact": "c", "description": "d"},
        {"name": "n", "contact": "c", "description": None},
        {"name": "x" * (MAX_NAME_LENGTH + 1), "contact": "c", "description": "d"},
        {"name": "n", "contact": "c", "description": "d" * (MAX_DESCRIPTION_LENGTH + 1)},
        {"name": "n", "contact": "c", "description": "d", "order_id": True},
        {"name": "n", "contact": "c", "description": "d", "order_id": ["7"]},
        {
            "name": "n",
            "contact": "c",
            "description": "d",
            "order_id": "7" * (MAX_ORDER_REFERENCE_LENGTH + 1),
        },
        {"name": "n", "contact": "c", "description": "d", "extra": 1},
        "not json",
    ],
)
def test_invalid_arguments_are_a_tool_error_and_write_nothing(
    db_path: Path, arguments: Mapping[str, object] | str
) -> None:
    result = call_tool(db_path, arguments)

    error = result["error"]
    assert isinstance(error, dict)
    assert error["code"] == "invalid_arguments"
    assert rows(db_path, "SELECT count(*) FROM complaints") == [(0,)]


def test_description_at_the_limit_is_accepted(db_path: Path) -> None:
    result = call_tool(
        db_path,
        {"name": "n", "contact": "c", "description": "d" * MAX_DESCRIPTION_LENGTH},
    )

    assert "protocol" in result


def test_the_assistant_offers_register_complaint(db_path: Path) -> None:
    llm = ScriptedLLM([says("oi")])
    build_assistant(llm, db_path, clock=lambda: NOW).reply(Session(id="s"), "oi")

    functions = [tool["function"] for tool in llm.calls[0].tools]
    assert any(isinstance(f, dict) and f.get("name") == "register_complaint" for f in functions)


def test_read_only_tools_do_not_write_to_the_database(db_path: Path) -> None:
    before = dump(db_path)
    llm = ScriptedLLM(
        [
            asks(
                tool_call("a", "search_products", {"query": "violao"}),
                tool_call("b", "get_product", {"product_id": 1}),
                tool_call("c", "get_order", {"order_id": 7, "email_or_phone": "x@y.z"}),
            ),
            says("ok"),
        ]
    )
    build_assistant(llm, db_path, clock=lambda: NOW).reply(Session(id="s"), "oi")

    assert len(llm.tool_results(1)) == 3
    assert dump(db_path) == before
