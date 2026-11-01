from pathlib import Path

import pytest

from emporio.seed import seed
from emporio.store import StoreService

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary SQLite file seeded from the real CSVs."""
    path = tmp_path / "emporio.db"
    seed(path, DATA_DIR)
    return path


@pytest.fixture
def store(db_path: Path) -> StoreService:
    return StoreService(db_path)
