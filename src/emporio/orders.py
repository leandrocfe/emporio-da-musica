"""Orders (`Order`): records, the repository port and the Order verification (ADR-0003).

Actor: the anonymous Session. Allowed: an Order number plus a contact that,
normalized, equals the e-mail or the phone of the Customer who owns that Order.
Denied: nonexistent Order, other contact, unusable contact, invalid `order_id`.
Every denied case gives the same outcome (`DENIED`) and adds one to the
Session's `failed_verifications`, which never goes back to zero. Once it reaches
`MAX_FAILED_VERIFICATIONS`, every further attempt is `LOCKED` before anything
else is looked at, the database included. Check, lookup and increment run under
the Session's lock, so concurrent turns cannot win extra attempts.

The decision lives here, in code; the prompt only tells Lia how to talk about it.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Literal, Protocol

from emporio.contact import Contact, contact_matches, normalize_contact
from emporio.session import Session

OrderStatus = Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]

MAX_FAILED_VERIFICATIONS = 3
MAX_ORDER_ID = 2**63 - 1  # largest SQLite INTEGER; bigger ints overflow the driver


@dataclass(frozen=True, slots=True)
class OrderOwner:
    """The Customer who owns the Order: used to verify, never shown whole."""

    name: str
    email: str
    phone: str


@dataclass(frozen=True, slots=True)
class OrderItem:
    """Item do pedido: a Product and the quantity bought (no price is recorded per item)."""

    product_id: int
    product_name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class OrderRecord:
    id: int
    owner: OrderOwner
    order_date: date
    status: OrderStatus
    total: int  # cents, Valor do pedido as recorded (never recalculated)
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None  # observations; the cancellation reason of cancelled Orders
    items: tuple[OrderItem, ...]


class OrderRepository(Protocol):
    def find_order(self, order_id: int) -> OrderRecord | None: ...


@dataclass(frozen=True, slots=True)
class Verified:
    order: OrderRecord


class Refusal(Enum):
    DENIED = "denied"  # one outcome for every denied case: nothing tells them apart
    LOCKED = "locked"  # too many failures in this Session


DENIED = Refusal.DENIED
LOCKED = Refusal.LOCKED

VerificationOutcome = Verified | Refusal


def verify_order(
    orders: OrderRepository, session: Session, order_id: object, contact: object
) -> VerificationOutcome:
    """Order verification of `order_id` + `contact` as sent by the model (unvalidated).

    Atomic per Session: concurrent turns of the same Session wait for each other,
    so the limit can never be exceeded; other Sessions are not blocked.
    """
    with session.verification_lock:
        return _verify(orders, session, order_id, contact)


def _verify(
    orders: OrderRepository, session: Session, order_id: object, contact: object
) -> VerificationOutcome:
    if session.failed_verifications >= MAX_FAILED_VERIFICATIONS:
        return LOCKED
    valid_id = _order_id(order_id)
    normalized = _contact(contact)
    order = None
    if valid_id is not None and normalized is not None:
        order = orders.find_order(valid_id)
    if (
        order is None
        or normalized is None
        or not contact_matches(normalized, email=order.owner.email, phone=order.owner.phone)
    ):
        session.failed_verifications += 1
        return DENIED
    return Verified(order)


def _order_id(value: object) -> int | None:
    # bool is a subclass of int in Python: `true` is not Order 1.
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= MAX_ORDER_ID:
        return value
    return None


def _contact(value: object) -> Contact | None:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)  # a phone the model sent as a JSON number
    return normalize_contact(value) if isinstance(value, str) else None
