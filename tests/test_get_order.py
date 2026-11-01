"""`get_order` as the model sees it: Order verification, output and post-sale windows.

Seam: `Assistant.reply` with a scripted model over the seeded database (ADR-0001),
plus a spy repository where the test must prove the database is not queried.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from emporio.app import build_assistant
from emporio.assistant import Assistant
from emporio.clock import STORE_TIMEZONE
from emporio.order_tools import register_order_tools
from emporio.orders import OrderRecord, OrderRepository
from emporio.session import Session
from emporio.store import StoreService
from emporio.tools import ToolRegistry

from .fakes import ScriptedLLM, asks, says, tool_call

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=STORE_TIMEZONE)
ORDER_7_EMAIL = "leticia.rocha@jmail.com"  # Customer 14, Letícia Gonçalves Rocha
ORDER_7_PHONE = "67997890123"


def call_get_order(
    orders: OrderRepository,
    arguments: Mapping[str, object] | str,
    session: Session | None = None,
    now: datetime = NOW,
) -> dict[str, object]:
    registry = ToolRegistry()
    register_order_tools(registry, orders)
    llm = ScriptedLLM([asks(tool_call("call_1", "get_order", arguments)), says("ok")])
    Assistant(llm, registry, clock=lambda: now).reply(session or Session(id="s1"), "meu pedido")
    result = llm.tool_results(1)["call_1"]
    assert isinstance(result, dict)
    return result


def verified_order(result: dict[str, object]) -> dict[str, object]:
    assert result["verified"] is True
    order = result["order"]
    assert isinstance(order, dict)
    return order


def windows(result: dict[str, object]) -> dict[str, object]:
    assert result["verified"] is True
    found = result["post_sale_windows"]
    assert isinstance(found, dict)
    return found


@dataclass
class SpyOrders:
    """Wraps the real Store and records every lookup."""

    store: StoreService
    lookups: list[int] = field(default_factory=list)

    def find_order(self, order_id: int) -> OrderRecord | None:
        self.lookups.append(order_id)
        return self.store.find_order(order_id)


def test_order_7_verified_by_email(store: StoreService) -> None:
    result = call_get_order(store, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL})

    assert verified_order(result) == {
        "id": 7,
        "customer_first_name": "Letícia",
        "status": "delivered",
        "order_date": "2026-02-03",
        "items": [{"product_id": 119, "name": "Shelby SU-21S Soprano Sunburst", "quantity": 1}],
        "total": "159.90",
        "payment_method": "credit_3x",
        "tracking_code": "BRKR1122334BR",
        "estimated_delivery": "2026-02-17",
        "notes": None,
    }


@pytest.mark.parametrize("contact", ["+55 (67) 99789-0123", "67997890123", "997890123"])
def test_order_7_verified_by_phone_in_any_accepted_format(
    store: StoreService, contact: str
) -> None:
    result = call_get_order(store, {"order_id": 7, "email_or_phone": contact})

    assert verified_order(result)["id"] == 7


def test_nonexistent_wrong_contact_and_invalid_id_are_identical(store: StoreService) -> None:
    denied = [
        call_get_order(store, arguments)
        for arguments in (
            {"order_id": 999, "email_or_phone": ORDER_7_EMAIL},  # nonexistent
            {"order_id": 7, "email_or_phone": "anacarol.ferreira@coldmail.com"},  # other Customer
            {"order_id": 7, "email_or_phone": "67911112222"},  # wrong phone
            {"order_id": "7", "email_or_phone": ORDER_7_EMAIL},  # invalid order_id
            {"order_id": -7, "email_or_phone": ORDER_7_EMAIL},
            {"order_id": True, "email_or_phone": ORDER_7_EMAIL},
            {"order_id": "abc; DROP TABLE orders", "email_or_phone": ORDER_7_EMAIL},
            {"order_id": 2**70, "email_or_phone": ORDER_7_EMAIL},
            {"order_id": None, "email_or_phone": ORDER_7_EMAIL},
        )
    ]

    assert denied[0]["verified"] is False
    assert "locked" in denied[0]
    assert denied[0]["locked"] is False
    assert all(result == denied[0] for result in denied)
    echoed = json.dumps(denied[0], ensure_ascii=False)
    assert not any(ch.isdigit() for ch in echoed)  # no Order number echoed back
    assert "@" not in echoed


def test_invalid_order_id_counts_as_a_failure(store: StoreService) -> None:
    session = Session(id="s1")

    call_get_order(store, {"order_id": "sete", "email_or_phone": ORDER_7_EMAIL}, session)

    assert session.failed_verifications == 1


def test_lock_after_three_failures_is_identical_for_existing_and_nonexistent(
    store: StoreService,
) -> None:
    session = Session(id="s1")
    for order_id in (7, 999, 3):
        result = call_get_order(store, {"order_id": order_id, "email_or_phone": "x@y.com"}, session)
        assert result["verified"] is False
        assert result["locked"] is False

    existing = call_get_order(store, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL}, session)
    nonexistent = call_get_order(store, {"order_id": 999, "email_or_phone": ORDER_7_EMAIL}, session)
    invalid = call_get_order(store, {"order_id": "x", "email_or_phone": ORDER_7_EMAIL}, session)

    assert existing == nonexistent == invalid
    assert existing["verified"] is False
    assert existing["locked"] is True
    message = existing["message"]
    assert isinstance(message, str)
    assert "(67) 3341-4444" in message
    assert "contato@emporiodamusica.com.br" in message


def test_fourth_attempt_does_not_query_the_database(store: StoreService) -> None:
    spy = SpyOrders(store)
    session = Session(id="s1")
    for _ in range(3):
        call_get_order(spy, {"order_id": 7, "email_or_phone": "x@y.com"}, session)
    assert spy.lookups == [7, 7, 7]

    call_get_order(spy, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL}, session)
    call_get_order(spy, {"order_id": 999, "email_or_phone": ORDER_7_EMAIL}, session)

    assert spy.lookups == [7, 7, 7]


def test_locked_session_works_even_without_a_database(tmp_path: Path) -> None:
    missing = StoreService(tmp_path / "does-not-exist" / "emporio.db")
    session = Session(id="s1", failed_verifications=3)

    result = call_get_order(missing, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL}, session)

    assert result["locked"] is True


def test_success_does_not_reset_the_counter(store: StoreService) -> None:
    session = Session(id="s1")
    call_get_order(store, {"order_id": 7, "email_or_phone": "x@y.com"}, session)
    call_get_order(store, {"order_id": 7, "email_or_phone": "x@y.com"}, session)

    ok = call_get_order(store, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL}, session)
    assert ok["verified"] is True
    assert session.failed_verifications == 2

    call_get_order(store, {"order_id": 7, "email_or_phone": "x@y.com"}, session)
    locked = call_get_order(store, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL}, session)
    assert locked["locked"] is True


def test_parallel_calls_in_one_round_share_the_counter(store: StoreService) -> None:
    registry = ToolRegistry()
    register_order_tools(registry, store)
    calls = [
        tool_call(f"call_{n}", "get_order", {"order_id": n, "email_or_phone": "x@y.com"})
        for n in range(1, 6)
    ]
    llm = ScriptedLLM([asks(*calls), says("ok")])
    session = Session(id="s1")

    Assistant(llm, registry, clock=lambda: NOW).reply(session, "pedidos")

    locked = []
    for result in llm.tool_results(1).values():
        assert isinstance(result, dict)
        locked.append(result["locked"])
    assert locked == [False, False, False, True, True]
    assert session.failed_verifications == 3


@pytest.mark.parametrize(
    ("order_id", "email", "total"),
    [
        (3, "isabela.moreira@jmail.com", "3450.00"),  # 2 x a Product now listed at 1749.00
        (20, "thiago.barbosa@jmail.com", "1400.00"),  # items now add up to 1488.00
    ],
)
def test_order_total_is_the_recorded_value(
    store: StoreService, order_id: int, email: str, total: str
) -> None:
    result = call_get_order(store, {"order_id": order_id, "email_or_phone": email})

    assert verified_order(result)["total"] == total


def test_cancelled_order_shows_the_reason_and_has_no_windows(store: StoreService) -> None:
    result = call_get_order(store, {"order_id": 20, "email_or_phone": "thiago.barbosa@jmail.com"})

    order = verified_order(result)
    assert order["status"] == "cancelled"
    assert order["notes"] == "Endereço de entrega inválido informado pelo cliente"
    assert order["customer_first_name"] == "Thiago"
    assert windows(result) == {
        "reference_date": "2026-03-23",
        "withdrawal": None,
        "defect_exchange": None,
        "legal_warranty": None,
    }
    assert result["overdue"] is False


def test_order_7_on_march_23_windows(store: StoreService) -> None:
    result = call_get_order(store, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL})

    assert windows(result) == {
        "reference_date": "2026-03-23",
        "withdrawal": {"until": "2026-02-24", "within": False, "borderline": False},
        "defect_exchange": {"until": "2026-03-05", "within": False, "borderline": False},
        "legal_warranty": {"until": "2026-05-18", "within": True, "borderline": False},
    }
    assert result["overdue"] is False


def test_order_8_is_overdue(store: StoreService) -> None:
    result = call_get_order(
        store, {"order_id": 8, "email_or_phone": "anacarol.ferreira@coldmail.com"}
    )

    assert verified_order(result)["status"] == "shipped"
    assert result["overdue"] is True
    assert windows(result)["defect_exchange"] is None


def test_confirmed_order_has_no_windows(store: StoreService) -> None:
    # Order 9: confirmed, bought 2026-02-20; Customer 6 has not received it yet.
    result = call_get_order(
        store, {"order_id": 9, "email_or_phone": "juliana.almeida@hayoo.com.br"}
    )

    assert verified_order(result)["status"] == "confirmed"
    assert windows(result) == {
        "reference_date": "2026-03-23",
        "withdrawal": None,
        "defect_exchange": None,
        "legal_warranty": None,
    }
    assert result["overdue"] is False


def test_reference_date_is_the_store_calendar_day(store: StoreService) -> None:
    # 2026-02-25 00:30 UTC is still 2026-02-24 in Campo Grande: last day of the withdrawal.
    utc_now = datetime.fromisoformat("2026-02-25T00:30:00+00:00")

    result = call_get_order(store, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL}, now=utc_now)

    found = windows(result)
    assert found["reference_date"] == "2026-02-24"
    assert found["withdrawal"] == {"until": "2026-02-24", "within": True, "borderline": True}


def test_output_has_no_other_customer_data(store: StoreService) -> None:
    result = call_get_order(store, {"order_id": 7, "email_or_phone": "997890123"})

    text = json.dumps(result, ensure_ascii=False)
    for secret in ("leticia.rocha", "99789", "Gonçalves", "Rocha", "Campo Grande", "customer_id"):
        assert secret not in text, secret
    assert set(result) == {"verified", "order", "post_sale_windows", "overdue"}


def test_verified_contact_does_not_open_another_customers_order(store: StoreService) -> None:
    session = Session(id="s1")
    assert call_get_order(store, {"order_id": 7, "email_or_phone": ORDER_7_EMAIL}, session)[
        "verified"
    ]

    other = call_get_order(store, {"order_id": 8, "email_or_phone": ORDER_7_EMAIL}, session)

    assert other["verified"] is False
    assert session.failed_verifications == 1


def test_missing_contact_is_a_tool_error_that_does_not_count(store: StoreService) -> None:
    session = Session(id="s1")

    result = call_get_order(store, {"order_id": 7}, session)

    assert result["error"] == {
        "code": "invalid_arguments",
        "message": "Argumentos obrigatórios ausentes: email_or_phone.",
    }
    assert session.failed_verifications == 0


def test_assembled_assistant_registers_get_order(db_path: Path) -> None:
    llm = ScriptedLLM(
        [
            asks(
                tool_call("call_1", "get_order", {"order_id": 7, "email_or_phone": ORDER_7_EMAIL})
            ),
            says("ok"),
        ]
    )

    build_assistant(llm=llm, db_path=db_path, clock=lambda: NOW).reply(Session(id="s1"), "pedido 7")

    functions = [tool["function"] for tool in llm.calls[0].tools]
    assert any(isinstance(f, dict) and f.get("name") == "get_order" for f in functions)
    result = llm.tool_results(1)["call_1"]
    assert isinstance(result, dict)
    assert result["verified"] is True
