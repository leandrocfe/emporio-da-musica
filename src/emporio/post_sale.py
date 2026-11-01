"""Post-sale windows computed in code from the Reference date (ADR-0005).

Pure date arithmetic, no database. Everything is a calendar date in the store
timezone (the caller converts `ctx.now`); datetimes are never compared.

- arrependimento (`withdrawal`): 7 calendar days from the Entrega prevista;
- troca por defeito (`defect_exchange`): 30 calendar days from the Order date;
- garantia legal (`legal_warranty`): 90 calendar days from the Entrega prevista.

`until` is the last day still inside the window ("até 17/03" means 17/03 is
within), so `within` is `today <= until`. `borderline` is true when `today` is
at most 2 days before or after `until`, only for the windows counted from the
Entrega prevista, an approximation of the real delivery date. The Order date is
exact, so the defect exchange never has a margin.

Every window exists only for `delivered` Orders; any other status gets `None`
for all three. The defect exchange counts from the Order date, but before the
Product arrives it would show up "expired" for something never received. A
delivered Order without an Entrega prevista still gets the defect exchange. A
`shipped` Order whose Entrega prevista is before `today` is `overdue`.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from emporio.orders import OrderStatus

WITHDRAWAL_DAYS = 7
DEFECT_EXCHANGE_DAYS = 30
LEGAL_WARRANTY_DAYS = 90
BORDERLINE_DAYS = 2


@dataclass(frozen=True, slots=True)
class Window:
    until: date  # last day inside the window (inclusive)
    within: bool
    borderline: bool


@dataclass(frozen=True, slots=True)
class PostSaleWindows:
    withdrawal: Window | None
    defect_exchange: Window | None
    legal_warranty: Window | None
    overdue: bool


def post_sale_windows(
    status: OrderStatus, order_date: date, estimated_delivery: date | None, today: date
) -> PostSaleWindows:
    withdrawal = defect_exchange = legal_warranty = None
    if status == "delivered":
        defect_exchange = _window(order_date, DEFECT_EXCHANGE_DAYS, today, with_margin=False)
        if estimated_delivery is not None:
            withdrawal = _window(estimated_delivery, WITHDRAWAL_DAYS, today, with_margin=True)
            legal_warranty = _window(
                estimated_delivery, LEGAL_WARRANTY_DAYS, today, with_margin=True
            )
    overdue = status == "shipped" and estimated_delivery is not None and estimated_delivery < today
    return PostSaleWindows(withdrawal, defect_exchange, legal_warranty, overdue)


def _window(start: date, days: int, today: date, *, with_margin: bool) -> Window:
    until = start + timedelta(days=days)
    borderline = with_margin and abs((today - until).days) <= BORDERLINE_DAYS
    return Window(until=until, within=today <= until, borderline=borderline)
