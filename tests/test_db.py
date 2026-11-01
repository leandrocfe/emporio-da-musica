from pathlib import Path

import pytest

from emporio.db import connect, transaction


class BoomError(Exception):
    pass


def test_original_error_survives_a_transaction_sqlite_already_aborted(tmp_path: Path) -> None:
    with connect(tmp_path / "t.db") as conn, pytest.raises(BoomError), transaction(conn):
        # Simulates SQLite auto-aborting (e.g. SQLITE_FULL) before the error surfaces.
        conn.execute("ROLLBACK")
        raise BoomError
