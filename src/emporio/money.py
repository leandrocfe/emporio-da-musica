"""Money is integer cents everywhere in the domain (ADR-0002)."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def to_cents(brl: str) -> int:
    """Convert a decimal BRL string ("599.9") to integer cents (59990), ROUND_HALF_UP."""
    try:
        amount = Decimal(brl.strip())
    except InvalidOperation as exc:
        raise ValueError(f"invalid BRL amount: {brl!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"invalid BRL amount: {brl!r}")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
