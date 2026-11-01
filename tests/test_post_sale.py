"""Seam — post-sale windows computed in code from the Reference date (ADR-0005)."""

from datetime import date, timedelta

import pytest

from emporio.orders import OrderStatus
from emporio.post_sale import Window, post_sale_windows

ORDER_7_DATE = date(2026, 2, 3)
ORDER_7_DELIVERY = date(2026, 2, 17)


def test_order_7_on_march_23_has_only_the_legal_warranty() -> None:
    windows = post_sale_windows("delivered", ORDER_7_DATE, ORDER_7_DELIVERY, date(2026, 3, 23))

    assert windows.withdrawal == Window(until=date(2026, 2, 24), within=False, borderline=False)
    assert windows.defect_exchange == Window(until=date(2026, 3, 5), within=False, borderline=False)
    assert windows.legal_warranty == Window(until=date(2026, 5, 18), within=True, borderline=False)
    assert windows.overdue is False


# ADR-0005 example: Entrega prevista 2026-03-10 -> arrependimento até 2026-03-17.
@pytest.mark.parametrize(
    ("today", "within", "borderline"),
    [
        (date(2026, 3, 14), True, False),  # limit - 3
        (date(2026, 3, 15), True, True),  # limit - 2
        (date(2026, 3, 17), True, True),  # limit: the last day is still within
        (date(2026, 3, 19), False, True),  # limit + 2
        (date(2026, 3, 20), False, False),  # limit + 3
    ],
)
def test_withdrawal_borderline_around_the_limit(
    today: date, within: bool, borderline: bool
) -> None:
    windows = post_sale_windows("delivered", date(2026, 3, 1), date(2026, 3, 10), today)

    assert windows.withdrawal == Window(date(2026, 3, 17), within, borderline)


@pytest.mark.parametrize(
    ("offset", "within", "borderline"),
    [(-3, True, False), (-2, True, True), (0, True, True), (2, False, True), (3, False, False)],
)
def test_legal_warranty_borderline_around_the_limit(
    offset: int, within: bool, borderline: bool
) -> None:
    delivery = date(2026, 1, 10)
    limit = date(2026, 4, 10)  # 90 days
    windows = post_sale_windows(
        "delivered", date(2026, 1, 1), delivery, limit + timedelta(days=offset)
    )

    assert windows.legal_warranty == Window(limit, within, borderline)


@pytest.mark.parametrize(("offset", "within"), [(-1, True), (0, True), (1, False), (2, False)])
def test_defect_exchange_never_has_a_margin(offset: int, within: bool) -> None:
    order_date = date(2026, 3, 1)
    limit = date(2026, 3, 31)  # 30 days
    windows = post_sale_windows(
        "delivered", order_date, date(2026, 3, 10), limit + timedelta(days=offset)
    )

    assert windows.defect_exchange == Window(limit, within, borderline=False)


def test_shipped_order_past_its_estimated_delivery_is_overdue() -> None:
    # Order 8: shipped, Entrega prevista 2026-02-28.
    windows = post_sale_windows("shipped", date(2026, 2, 15), date(2026, 2, 28), date(2026, 3, 23))

    assert windows.overdue is True
    assert windows.withdrawal is None
    assert windows.legal_warranty is None


@pytest.mark.parametrize("today", [date(2026, 2, 27), date(2026, 2, 28)])
def test_shipped_order_on_or_before_its_estimated_delivery_is_not_overdue(today: date) -> None:
    windows = post_sale_windows("shipped", date(2026, 2, 15), date(2026, 2, 28), today)

    assert windows.overdue is False


@pytest.mark.parametrize("status", ["pending", "confirmed", "shipped"])
def test_windows_only_for_delivered_orders(status: OrderStatus) -> None:
    # Order 9 shape: bought 2026-02-20, 31 days before the Reference date. Counting
    # the defect exchange before delivery would show it "expired" for a Product
    # the Customer never received.
    windows = post_sale_windows(status, date(2026, 2, 20), date(2026, 3, 10), date(2026, 3, 23))

    assert (windows.withdrawal, windows.defect_exchange, windows.legal_warranty) == (
        None,
        None,
        None,
    )


def test_cancelled_order_has_no_windows() -> None:
    windows = post_sale_windows("cancelled", date(2026, 3, 8), None, date(2026, 3, 23))

    assert (windows.withdrawal, windows.defect_exchange, windows.legal_warranty) == (
        None,
        None,
        None,
    )
    assert windows.overdue is False


def test_delivered_order_without_estimated_delivery_has_no_delivery_windows() -> None:
    windows = post_sale_windows("delivered", date(2026, 3, 1), None, date(2026, 3, 5))

    assert windows.withdrawal is None
    assert windows.legal_warranty is None
    assert windows.defect_exchange == Window(date(2026, 3, 31), within=True, borderline=False)
