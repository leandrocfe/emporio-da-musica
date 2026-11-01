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


def to_brl(cents: int) -> str:
    """Integer cents (59990) to an exact decimal BRL string ("599.90") for tool output."""
    if cents < 0:
        raise ValueError(f"negative amount: {cents}")
    return f"{cents // 100}.{cents % 100:02d}"


def discounted(cents: int, percent: int) -> int:
    """`cents` minus `percent`%, in integer cents.

    Integer-only equivalent of Decimal arithmetic with ROUND_HALF_UP (ADR-0002):
    (599.90 minus 5%) is 569.905, which becomes 569.91.
    """
    if cents < 0 or not 0 <= percent <= 100:
        raise ValueError(f"invalid discount: {percent}% of {cents}")
    # cents * (100 - percent) / 100, rounded half up: add half the divisor before flooring.
    return (cents * (100 - percent) + 50) // 100
