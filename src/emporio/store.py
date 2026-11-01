"""The Store (`StoreService`): deterministic domain layer over SQLite.

Money is returned in integer cents; conversion to reais happens only at the
tool output boundary (ADR-0002).
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from emporio.db import connect
from emporio.text import normalize, tokenize

DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 10


@dataclass(frozen=True, slots=True)
class ProductSummary:
    id: int
    name: str
    category: str
    list_price: int  # cents


@dataclass(frozen=True, slots=True)
class SearchResult:
    total: int  # all matches, before applying `limit`
    products: list[ProductSummary]


class StoreService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def search_products(
        self,
        query: str | None = None,
        category: str | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> SearchResult:
        """Token (AND) search over non-discontinued Products, ranked by relevance.

        Relevance per token: name hit x2 + category hit + description hit.
        `limit` is clamped to 1..10 without error.
        """
        tokens = tokenize(query or "")
        limit = max(1, min(limit, MAX_SEARCH_LIMIT))

        sql = [
            "SELECT p.id, p.name, p.description, p.list_price, c.name AS category",
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

        ranked = sorted(
            rows, key=lambda row: (-_relevance(row, tokens), row["list_price"], row["id"])
        )
        return SearchResult(
            total=len(ranked),
            products=[_summary(row) for row in ranked[:limit]],
        )


def _relevance(row: sqlite3.Row, tokens: list[str]) -> int:
    name, category, description = (
        tokenize(row[field]) for field in ("name", "category", "description")
    )
    return sum(
        2 * _hits(name, token) + _hits(category, token) + _hits(description, token)
        for token in tokens
    )


def _hits(words: list[str], token: str) -> int:
    """1 if `token` is one of the words (same rule as the SQL match)."""
    return int(token in words)


def _summary(row: sqlite3.Row) -> ProductSummary:
    return ProductSummary(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        list_price=row["list_price"],
    )
