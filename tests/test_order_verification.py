"""Seam — `verify_order`: who may see an Order, and the per-Session counter (ADR-0003)."""

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date

import pytest

from emporio.orders import (
    DENIED,
    LOCKED,
    MAX_FAILED_VERIFICATIONS,
    OrderItem,
    OrderOwner,
    OrderRecord,
    Verified,
    verify_order,
)
from emporio.session import Session

ORDER_7 = OrderRecord(
    id=7,
    owner=OrderOwner(
        name="Letícia Gonçalves Rocha", email="leticia.rocha@jmail.com", phone="67997890123"
    ),
    order_date=date(2026, 2, 3),
    status="delivered",
    total=15990,
    payment_method="credit_3x",
    tracking_code="BRKR1122334BR",
    estimated_delivery=date(2026, 2, 17),
    notes=None,
    items=(OrderItem(product_id=119, product_name="Ukulele", quantity=1),),
)


@dataclass
class SpyOrders:
    """In-memory OrderRepository that records every lookup."""

    orders: dict[int, OrderRecord] = field(default_factory=lambda: {7: ORDER_7})
    lookups: list[int] = field(default_factory=list)

    def find_order(self, order_id: int) -> OrderRecord | None:
        self.lookups.append(order_id)
        return self.orders.get(order_id)


def test_owner_email_verifies_and_does_not_count_a_failure() -> None:
    session = Session(id="s1")

    outcome = verify_order(SpyOrders(), session, 7, "Leticia.Rocha@jmail.com")

    assert outcome == Verified(ORDER_7)
    assert session.failed_verifications == 0


@pytest.mark.parametrize("contact", ["+55 (67) 99789-0123", "67997890123", "997890123"])
def test_owner_phone_verifies_with_or_without_ddd_and_country_code(contact: str) -> None:
    assert verify_order(SpyOrders(), Session(id="s1"), 7, contact) == Verified(ORDER_7)


@pytest.mark.parametrize(
    ("order_id", "contact"),
    [
        (999, "leticia.rocha@jmail.com"),  # nonexistent Order
        (7, "outra.pessoa@jmail.com"),  # wrong contact
        (7, "67911112222"),  # wrong phone
        (7, "123"),  # unusable contact
        (7, ""),
        ("7", "leticia.rocha@jmail.com"),  # invalid order_id
        (True, "leticia.rocha@jmail.com"),
        (0, "leticia.rocha@jmail.com"),
        (-7, "leticia.rocha@jmail.com"),
        (7.0, "leticia.rocha@jmail.com"),
        (None, "leticia.rocha@jmail.com"),
        (2**63, "leticia.rocha@jmail.com"),  # beyond SQLite INTEGER
        (7, None),  # contact that is not text
        (7, ["67997890123"]),
    ],
)
def test_every_denied_case_is_the_same_outcome_and_counts(
    order_id: object, contact: object
) -> None:
    session = Session(id="s1")

    assert verify_order(SpyOrders(), session, order_id, contact) is DENIED
    assert session.failed_verifications == 1


def test_phone_sent_as_a_json_number_is_accepted() -> None:
    assert verify_order(SpyOrders(), Session(id="s1"), 7, 67997890123) == Verified(ORDER_7)


def test_after_three_failures_the_fourth_attempt_is_locked_without_lookup() -> None:
    orders = SpyOrders()
    session = Session(id="s1")
    for _ in range(MAX_FAILED_VERIFICATIONS):
        assert verify_order(orders, session, 7, "errado@jmail.com") is DENIED
    lookups_before = len(orders.lookups)

    # Locked even with the right contact, and identical for an existing or missing Order.
    assert verify_order(orders, session, 7, "leticia.rocha@jmail.com") is LOCKED
    assert verify_order(orders, session, 999, "leticia.rocha@jmail.com") is LOCKED
    assert verify_order(orders, session, "lixo", None) is LOCKED
    assert len(orders.lookups) == lookups_before


def test_counter_is_per_session_not_per_order() -> None:
    orders = SpyOrders()
    session = Session(id="s1")
    verify_order(orders, session, 7, "errado@jmail.com")
    verify_order(orders, session, 999, "errado@jmail.com")
    verify_order(orders, session, 3, "errado@jmail.com")

    assert verify_order(orders, session, 7, "leticia.rocha@jmail.com") is LOCKED
    assert verify_order(orders, Session(id="s2"), 7, "leticia.rocha@jmail.com") == Verified(ORDER_7)


def test_success_does_not_reset_the_counter() -> None:
    orders = SpyOrders()
    session = Session(id="s1")
    verify_order(orders, session, 7, "errado@jmail.com")
    verify_order(orders, session, 7, "errado@jmail.com")
    assert verify_order(orders, session, 7, "leticia.rocha@jmail.com") == Verified(ORDER_7)
    assert session.failed_verifications == 2

    assert verify_order(orders, session, 7, "errado@jmail.com") is DENIED
    assert verify_order(orders, session, 7, "leticia.rocha@jmail.com") is LOCKED


def test_invalid_input_is_denied_without_lookup() -> None:
    orders = SpyOrders()

    verify_order(orders, Session(id="s1"), "7", "leticia.rocha@jmail.com")
    verify_order(orders, Session(id="s2"), 7, "123")

    assert orders.lookups == []


@dataclass
class SlowSpyOrders(SpyOrders):
    """Spy whose lookup takes a while, so concurrent turns overlap inside it."""

    def find_order(self, order_id: int) -> OrderRecord | None:
        time.sleep(0.02)
        return super().find_order(order_id)


def test_concurrent_turns_of_one_session_never_exceed_the_limit() -> None:
    # Chainlit runs each reply in a worker thread: two messages of the same tab
    # can verify at the same time. Check, lookup and increment must be atomic.
    orders = SlowSpyOrders()
    session = Session(id="s1")
    attempts = 12
    start = threading.Barrier(attempts, timeout=5)

    def attempt(_: int) -> object:
        start.wait()
        return verify_order(orders, session, 7, "errado@jmail.com")

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        outcomes = list(pool.map(attempt, range(attempts)))

    assert len(orders.lookups) == MAX_FAILED_VERIFICATIONS
    assert session.failed_verifications == MAX_FAILED_VERIFICATIONS
    assert outcomes.count(DENIED) == MAX_FAILED_VERIFICATIONS
    assert outcomes.count(LOCKED) == attempts - MAX_FAILED_VERIFICATIONS


def test_session_lock_does_not_affect_equality_repr_or_copies() -> None:
    session = Session(id="s1", failed_verifications=2)

    assert session == Session(id="s1", failed_verifications=2)
    assert "lock" not in repr(session).lower()
    clone = copy.deepcopy(session)
    assert clone == session
    # A copy is another Session: it must not share the original's lock.
    with session.verification_lock:
        assert clone.verification_lock.acquire(blocking=False)
        clone.verification_lock.release()
