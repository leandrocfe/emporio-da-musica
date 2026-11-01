"""The seed's public output is the database file itself, so these tests read it."""

import importlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

import emporio.seed
from emporio.seed import seed
from emporio.store import StoreService

from .conftest import DATA_DIR


def _dump(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return list(conn.iterdump())


def _query(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


@pytest.fixture
def data_copy(tmp_path: Path) -> Path:
    """Editable copy of the real CSVs."""
    target = tmp_path / "data"
    target.mkdir()
    for csv_file in DATA_DIR.glob("*.csv"):
        shutil.copy(csv_file, target)
    return target


def _rewrite(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    assert old in content
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def test_seed_loads_every_csv(tmp_path: Path) -> None:
    counts = seed(tmp_path / "emporio.db", DATA_DIR)

    assert counts == {
        "categories": 9,
        "products": 65,
        "promotions": 25,
        "customers": 50,
        "orders": 20,
        "order_items": 22,
    }


def test_seeding_twice_produces_the_same_state(db_path: Path) -> None:
    before = _dump(db_path)

    seed(db_path, DATA_DIR)

    assert _dump(db_path) == before


def test_complaints_survive_a_new_seed(db_path: Path) -> None:
    # Temporary raw insert until register_complaint exists (ticket 07).
    row = (
        "EM-0001",
        "session-1",
        "Ana",
        "ana@example.com",
        "Chegou riscado",
        "7",
        "2026-03-23T10:00:00-04:00",
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO complaints (protocol, session_id, name, contact, description,"
            " order_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    conn.close()

    seed(db_path, DATA_DIR)

    stored = _query(
        db_path,
        "SELECT protocol, session_id, name, contact, description, order_id, created_at"
        " FROM complaints",
    )
    assert stored == [row]


def test_failed_seed_keeps_the_previous_state(tmp_path: Path, data_copy: Path) -> None:
    db_path = tmp_path / "emporio.db"
    seed(db_path, data_copy)
    before = _dump(db_path)
    # Order item pointing to a Product that does not exist: fails at insert time,
    # after the catalog tables were already dropped inside the transaction.
    _rewrite(data_copy / "order_items.csv", "1,1,93", "1,1,999")

    with pytest.raises(sqlite3.IntegrityError):
        seed(db_path, data_copy)

    assert _dump(db_path) == before


def test_invalid_specs_json_is_rejected_before_touching_the_database(
    tmp_path: Path, data_copy: Path
) -> None:
    db_path = tmp_path / "emporio.db"
    _rewrite(data_copy / "products.csv", '{""top"":""Spruce""', '{""top"":Spruce')

    with pytest.raises(ValueError, match=r"products\.csv line 2"):
        seed(db_path, data_copy)

    assert not db_path.exists()


def test_seed_normalizes_contact_data(tmp_path: Path, data_copy: Path) -> None:
    db_path = tmp_path / "emporio.db"
    _rewrite(data_copy / "customers.csv", "lucas.mendes@jmail.com", " Lucas.Mendes@JMAIL.com ")

    seed(db_path, data_copy)

    assert _query(db_path, "SELECT phone, email FROM customers WHERE id = 1") == [
        ("67998123456", "lucas.mendes@jmail.com")
    ]


def test_seed_stores_typed_values(db_path: Path) -> None:
    (product,) = _query(db_path, "SELECT list_price, specs, created_at FROM products WHERE id = 81")
    order = _query(db_path, "SELECT total, order_date, estimated_delivery FROM orders WHERE id = 9")
    promotions = _query(db_path, "SELECT id, is_active FROM promotions WHERE id IN (1, 12)")

    assert product[0] == 59990
    assert json.loads(str(product[1]))["top"] == "Spruce"
    assert product[2] == "2021-03-15"
    assert order == [(34990, "2026-02-20", None)]
    assert sorted(promotions) == [(1, 0), (12, 1)]


def test_search_column_is_lowercase_and_unaccented(db_path: Path) -> None:
    (row,) = _query(db_path, "SELECT search_text FROM products WHERE id = 87")
    search_text = str(row[0])

    assert search_text == search_text.lower()
    assert "violao" in search_text.split()  # name "Violão" and category "Violões"
    assert "aco" in search_text.split()


def test_importing_the_seed_module_does_not_create_a_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "emporio.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    importlib.reload(emporio.seed)

    assert not db_path.exists()


def test_cli_entrypoint_seeds_the_database_at_db_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "nested" / "emporio.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    emporio.seed.main()

    assert StoreService(db_path).search_products("yamaha c40").total == 1
