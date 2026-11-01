"""The Store (`StoreService`): deterministic domain layer over SQLite.

Money is returned in integer cents; conversion to reais happens only at the
tool output boundary (ADR-0002).
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from emporio.db import connect
from emporio.money import discounted
from emporio.text import normalize, tokenize

DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 10
MAX_AMBIGUOUS_MATCHES = 10
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


@dataclass(frozen=True, slots=True)
class ExpiredPromotion:
    """A Promoção no longer in force (`is_active = 0`); the Assistant must never offer it."""

    discount_percent: int
    description: str


@dataclass(frozen=True, slots=True)
class ProductDetail:
    id: int
    name: str
    category: str
    description: str
    specs: dict[str, str]  # keys as in the CSV (English); the model translates
    availability: Availability
    # Same pricing rules as ProductSummary. Discontinued Products carry no sale
    # prices at all (not even list_price); Em breve carries list_price only.
    list_price: int | None = None  # cents
    promo_price: int | None = None  # cents
    discount_percent: int | None = None
    pix_price: int | None = None  # cents
    expired_promotions: tuple[ExpiredPromotion, ...] = ()


@dataclass(frozen=True, slots=True)
class AmbiguousProduct:
    """A `name` that matched more than one Product: candidates only, no details."""

    total: int  # all candidates; `matches` is capped at MAX_AMBIGUOUS_MATCHES
    matches: list[tuple[int, str]]  # (id, name)


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

    def get_product(
        self, product_id: int | None = None, name: str | None = None
    ) -> ProductDetail | AmbiguousProduct | None:
        """One Product with full detail, looked up by `product_id` or by `name`.

        `product_id` wins when both are given. `name` matches when every token of
        the query is in the Product name (same normalization as the search); a
        single exact name match beats longer names that merely contain it. Several
        candidates give `AmbiguousProduct`; none gives `None`. Discontinued
        Products are included (without sale prices).
        """
        with connect(self._db_path) as conn:
            if product_id is not None:
                found = _detail_row(conn, product_id)
            else:
                tokens = tokenize(name or "")
                if not tokens:
                    return None
                rows = conn.execute("SELECT id, name FROM products ORDER BY id").fetchall()
                names = {row["id"]: (row["name"], tokenize(row["name"])) for row in rows}
                matches = [
                    (pid, pname)
                    for pid, (pname, words) in names.items()
                    if set(tokens) <= set(words)
                ]
                exact = [(pid, pname) for pid, pname in matches if names[pid][1] == tokens]
                if len(exact) == 1:
                    matches = exact
                if len(matches) > 1:
                    return AmbiguousProduct(
                        total=len(matches), matches=matches[:MAX_AMBIGUOUS_MATCHES]
                    )
                found = _detail_row(conn, matches[0][0]) if matches else None
            if found is None:
                return None
            promo_rows = conn.execute(
                "SELECT discount_percent, description FROM promotions "
                "WHERE product_id = ? AND is_active = 0 ORDER BY id",
                (found["id"],),
            ).fetchall()
        return _detail(
            found, [ExpiredPromotion(r["discount_percent"], r["description"]) for r in promo_rows]
        )


def _detail_row(conn: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT p.id, p.name, p.description, p.list_price, p.status, p.stock_quantity, p.specs,"
        "  c.name AS category,"
        "  (SELECT MAX(pr.discount_percent) FROM promotions pr"
        "   WHERE pr.product_id = p.id AND pr.is_active = 1) AS discount_percent "
        "FROM products p JOIN categories c ON c.id = p.category_id WHERE p.id = ?",
        (product_id,),
    ).fetchone()
    return row


def _detail(row: sqlite3.Row, expired: list[ExpiredPromotion]) -> ProductDetail:
    summary = _summary(row)  # the one place pricing rules live
    raw_specs: object = json.loads(row["specs"])
    if not isinstance(raw_specs, dict):
        raise ValueError(f"specs of product {row['id']} is not a JSON object")
    specs = {str(key): str(value) for key, value in raw_specs.items()}
    discontinued = summary.availability == "discontinued"
    return ProductDetail(
        id=summary.id,
        name=summary.name,
        category=summary.category,
        description=row["description"],
        specs=specs,
        availability=summary.availability,
        list_price=None if discontinued else summary.list_price,
        promo_price=None if discontinued else summary.promo_price,
        discount_percent=None if discontinued else summary.discount_percent,
        pix_price=None if discontinued else summary.pix_price,
        expired_promotions=tuple(expired),
    )


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
