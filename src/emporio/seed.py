"""Rebuild the catalog tables from the CSVs in one transaction (ADR-0002).

The CSVs are the source of truth: the six catalog tables are dropped and
recreated on every run. `complaints` is durable state and is only created
if missing. Run at service startup via `python -m emporio.seed`; nothing
here runs at import time.
"""

import csv
import json
import re
import sqlite3
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from emporio.db import connect, data_dir_from_env, db_path_from_env, transaction
from emporio.money import to_cents
from emporio.text import tokenize

# Children first, so DROP TABLE never violates a foreign key.
CATALOG_TABLES = (
    "order_items",
    "orders",
    "customers",
    "promotions",
    "products",
    "categories",
)

# Both schemas are split on ";" by _execute_script(): never put ";" inside
# comments, string literals or DEFAULT values here.
CATALOG_SCHEMA = """
CREATE TABLE categories (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE products (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    category_id    INTEGER NOT NULL REFERENCES categories (id),
    description    TEXT NOT NULL,
    list_price     INTEGER NOT NULL CHECK (list_price >= 0),          -- cents
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status         TEXT NOT NULL
                   CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    specs          TEXT NOT NULL CHECK (json_valid(specs)),
    created_at     TEXT NOT NULL,                                     -- ISO 8601 date
    search_text    TEXT NOT NULL      -- normalized name + description + category name
);
CREATE INDEX products_category_id ON products (category_id);

CREATE TABLE promotions (
    id               INTEGER PRIMARY KEY,
    product_id       INTEGER NOT NULL REFERENCES products (id),
    discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 100),
    description      TEXT NOT NULL,
    is_active        INTEGER NOT NULL CHECK (is_active IN (0, 1))
);
CREATE INDEX promotions_product_id ON promotions (product_id);

CREATE TABLE customers (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL,
    phone TEXT NOT NULL,          -- digits only
    email TEXT NOT NULL,          -- lowercase, no whitespace (not unique in the data)
    city  TEXT NOT NULL
);

CREATE TABLE orders (
    id                 INTEGER PRIMARY KEY,
    customer_id        INTEGER NOT NULL REFERENCES customers (id),
    order_date         TEXT NOT NULL,                                 -- ISO 8601 date
    status             TEXT NOT NULL CHECK (status IN
                       ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total              INTEGER NOT NULL CHECK (total >= 0),           -- cents, as recorded
    payment_method     TEXT NOT NULL,
    tracking_code      TEXT,
    estimated_delivery TEXT,                                          -- ISO 8601 date
    notes              TEXT
);
CREATE INDEX orders_customer_id ON orders (customer_id);

CREATE TABLE order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders (id),
    product_id INTEGER NOT NULL REFERENCES products (id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0)
);
CREATE INDEX order_items_order_id ON order_items (order_id);
"""

# Durable: never dropped by the seed. No FK to catalog tables on purpose
# (they are recreated on every seed; order_id is a free-form reference).
COMPLAINTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS complaints (
    id          INTEGER PRIMARY KEY,
    protocol    TEXT NOT NULL UNIQUE,
    session_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    contact     TEXT NOT NULL,
    description TEXT NOT NULL,
    order_id    TEXT,
    created_at  TEXT NOT NULL,        -- ISO 8601 datetime with offset
    UNIQUE (session_id, description)
);
"""

Row = dict[str, str]
Record = tuple[str | int | None, ...]


def seed(db_path: Path, data_dir: Path) -> dict[str, int]:
    """Recreate the catalog from `data_dir` CSVs; return row counts per table.

    All CSVs are parsed before the database is touched, and all writes run in
    a single transaction: any error leaves the previous state intact.
    """
    records = _load_records(data_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn, transaction(conn):
        for table in CATALOG_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")  # fixed names, never input
        _execute_script(conn, CATALOG_SCHEMA)
        _execute_script(conn, COMPLAINTS_SCHEMA)
        for table in reversed(CATALOG_TABLES):
            rows = records[table]
            if rows:
                placeholders = ", ".join("?" * len(rows[0]))
                # Record tuples follow the column order of CATALOG_SCHEMA.
                sql = f"INSERT INTO {table} VALUES ({placeholders})"  # noqa: S608 - fixed names
                conn.executemany(sql, rows)
    return {table: len(records[table]) for table in reversed(CATALOG_TABLES)}


def _execute_script(conn: sqlite3.Connection, script: str) -> None:
    # executescript() would COMMIT the open transaction; run statements one by one.
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


def _load_records(data_dir: Path) -> dict[str, list[Record]]:
    categories = _read(data_dir, "categories")
    category_names = {row["category_id"]: row["name"].strip() for row in categories}

    def product(row: Row) -> Record:
        return _product(row, category_names)

    return {
        "categories": _parse("categories", categories, _category),
        "products": _parse("products", _read(data_dir, "products"), product),
        "promotions": _parse("promotions", _read(data_dir, "promotions"), _promotion),
        "customers": _parse("customers", _read(data_dir, "customers"), _customer),
        "orders": _parse("orders", _read(data_dir, "orders"), _order),
        "order_items": _parse("order_items", _read(data_dir, "order_items"), _order_item),
    }


def _read(data_dir: Path, name: str) -> list[Row]:
    with (data_dir / f"{name}.csv").open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _parse(name: str, rows: list[Row], parse: Callable[[Row], Record]) -> list[Record]:
    """Parse every row, naming the CSV and row on failure."""
    records = []
    for line, row in enumerate(rows, start=2):  # line 1 is the header
        try:
            records.append(parse(row))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{name}.csv line {line}: {exc!r}") from exc
    return records


def _category(r: Row) -> Record:
    return (int(r["category_id"]), r["name"].strip(), r["description"].strip())


def _product(r: Row, category_names: dict[str, str]) -> Record:
    name = r["name"].strip()
    description = r["description"].strip()
    category = category_names[r["category_id"]]
    return (
        int(r["product_id"]),
        name,
        int(r["category_id"]),
        description,
        to_cents(r["price_brl"]),
        int(r["stock_quantity"]),
        r["status"].strip(),
        _json_object(r["specs"]),
        _iso_date(r["created_at"]),
        " ".join(tokenize(f"{name} {description} {category}")),
    )


def _promotion(r: Row) -> Record:
    return (
        int(r["promotion_id"]),
        int(r["product_id"]),
        int(r["discount_percent"]),
        r["description"].strip(),
        _bool(r["is_active"]),
    )


def _customer(r: Row) -> Record:
    return (
        int(r["customer_id"]),
        r["name"].strip(),
        _digits(r["phone"]),
        _email(r["email"]),
        r["city"].strip(),
    )


def _order(r: Row) -> Record:
    return (
        int(r["order_id"]),
        int(r["customer_id"]),
        _iso_date(r["order_date"]),
        r["status"].strip(),
        to_cents(r["total_brl"]),
        r["payment_method"].strip(),
        _optional(r["tracking_code"]),
        _optional_date(r["estimated_delivery"]),
        _optional(r["notes"]),
    )


def _order_item(r: Row) -> Record:
    return (
        None,  # surrogate id
        int(r["order_id"]),
        int(r["product_id"]),
        int(r["quantity"]),
    )


def _optional(value: str) -> str | None:
    return value.strip() or None


def _iso_date(value: str) -> str:
    return date.fromisoformat(value.strip()).isoformat()


def _optional_date(value: str) -> str | None:
    return _iso_date(value) if value.strip() else None


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def _digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not digits:
        raise ValueError(f"phone without digits: {value!r}")
    return digits


def _email(value: str) -> str:
    return "".join(value.split()).lower()


def _json_object(value: str) -> str:
    parsed = json.loads(value)  # json.JSONDecodeError is a ValueError
    if not isinstance(parsed, dict):
        raise ValueError("specs must be a JSON object")
    return json.dumps(parsed, ensure_ascii=False)


def main() -> None:
    db_path = db_path_from_env()
    counts = seed(db_path, data_dir_from_env())
    summary = ", ".join(f"{table}={count}" for table, count in counts.items())
    print(f"seeded {db_path}: {summary}", file=sys.stderr)


if __name__ == "__main__":
    main()
