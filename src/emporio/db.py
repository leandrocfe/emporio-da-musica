"""SQLite access: one connection per operation (ADR-0002)."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_FILENAME = "emporio.db"


def data_dir_from_env() -> Path:
    """CSV directory: `DATA_DIR` or the repository's `data/`."""
    return Path(os.environ.get("DATA_DIR") or DEFAULT_DATA_DIR)


def db_path_from_env() -> Path:
    """SQLite file: `DB_PATH` or `data/emporio.db`."""
    return Path(os.environ.get("DB_PATH") or DEFAULT_DATA_DIR / DEFAULT_DB_FILENAME)


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open an autocommit connection with FK enforcement; always closes it.

    Writes that must be atomic wrap themselves in `transaction()`.
    """
    conn = sqlite3.connect(db_path, autocommit=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Explicit BEGIN IMMEDIATE / COMMIT, ROLLBACK on any error (DDL included)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        # SQLite may have aborted already (SQLITE_FULL, IOERR); don't mask the original error.
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
