"""The Store (`StoreService`): deterministic domain layer over SQLite.

Money is returned in integer cents; conversion to reais happens only at the
tool output boundary (ADR-0002).
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from emporio.db import connect
from emporio.money import discounted
from emporio.text import normalize, tokenize

DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 10
PIX_DISCOUNT_PERCENT = 5
LAST_UNITS_MAX_STOCK = 3

Availability = Literal["available", "last_units", "out_of_stock", "discontinued", "coming_soon"]


@dataclass(frozen=True, slots=True)
class ProductSummary:
    id: int
    name: str
    category: str
    list_price: int  # cents
    availability: Availability
    # With a Promoção vigente: promo_price + discount_percent and no pix_price.
    # Without one: pix_price only. Em breve Products carry neither (list price only).
    promo_price: int | None = None  # cents
    discount_percent: int | None = None
    pix_price: int | None = None  # cents

    @property
    def effective_price(self) -> int:
        """What the Customer pays before PIX: promo price when there is one."""
        return self.promo_price if self.promo_price is not None else self.list_price


@dataclass(frozen=True, slots=True)
class SearchResult:
    total: int  # all matches, before applying `limit`
    products: list[ProductSummary]


class StoreService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def category_names(self) -> list[str]:
        """Category names in catalog order (they feed the tool schema `enum`)."""
        with connect(self._db_path) as conn:
            rows = conn.execute("SELECT name FROM categories ORDER BY id").fetchall()
        return [row["name"] for row in rows]

    def search_products(
        self,
        query: str | None = None,
        category: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> SearchResult:
        """Token (AND) search over non-discontinued Products.

        `min_price`/`max_price` (cents, inclusive) filter by effective price
        (promo price when there is a Promoção vigente). Em breve Products only
        appear when neither bound is given.

        Order: relevance band first, then effective price ascending, then id.
        Band 0: every query token appears in the name or category; band 1: at
        least one token appears only in the description. Counting repeated
        hits would let a wordy description outrank a cheaper Product that
        matches just as fully. `limit` is clamped to 1..10 without error.
        """
        tokens = tokenize(query or "")
        limit = max(1, min(limit, MAX_SEARCH_LIMIT))

        sql = [
            "SELECT p.id, p.name, p.description, p.list_price, p.status, p.stock_quantity,",
            "  c.name AS category,",
            "  (SELECT MAX(pr.discount_percent) FROM promotions pr",
            "   WHERE pr.product_id = p.id AND pr.is_active = 1) AS discount_percent",
            "FROM products p JOIN categories c ON c.id = p.category_id",
            "WHERE p.status != 'discontinued'",
        ]
        params: list[str] = []
        for token in tokens:
            # Whole-word match; tokens are [a-z0-9]+ so they hold no LIKE wildcards.
            sql.append("AND (' ' || p.search_text || ' ') LIKE '% ' || ? || ' %'")
            params.append(token)
        with connect(self._db_path) as conn:
            rows = conn.execute("\n".join(sql), params).fetchall()

        if category is not None:
            wanted = normalize(category)
            rows = [row for row in rows if normalize(row["category"]) == wanted]

        products = [_summary(row) for row in rows]
        if min_price is not None or max_price is not None:
            products = [
                p
                for p in products
                if p.availability != "coming_soon"
                and (min_price is None or p.effective_price >= min_price)
                and (max_price is None or p.effective_price <= max_price)
            ]
        bands = {row["id"]: _band(row, tokens) for row in rows}
        products.sort(key=lambda p: (bands[p.id], p.effective_price, p.id))
        return SearchResult(total=len(products), products=products[:limit])


def _band(row: sqlite3.Row, tokens: list[str]) -> int:
    """0 when every token is in the name or category, 1 when some are description-only."""
    words = set(tokenize(row["name"])) | set(tokenize(row["category"]))
    return 0 if all(token in words for token in tokens) else 1


def _availability(status: str, stock_quantity: int) -> Availability:
    if status == "discontinued":
        return "discontinued"
    if status == "coming_soon":
        return "coming_soon"
    if stock_quantity == 0:
        return "out_of_stock"
    if stock_quantity <= LAST_UNITS_MAX_STOCK:
        return "last_units"
    return "available"


def _summary(row: sqlite3.Row) -> ProductSummary:
    list_price: int = row["list_price"]
    availability = _availability(row["status"], row["stock_quantity"])
    percent: int | None = None if availability == "coming_soon" else row["discount_percent"]
    has_prices = availability != "coming_soon"
    return ProductSummary(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        list_price=list_price,
        availability=availability,
        promo_price=discounted(list_price, percent) if percent is not None else None,
        discount_percent=percent,
        pix_price=(
            discounted(list_price, PIX_DISCOUNT_PERCENT) if has_prices and percent is None else None
        ),
    )
