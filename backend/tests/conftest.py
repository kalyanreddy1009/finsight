import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.database.migrate import apply_migrations
from app.database.seed import seed_system_accounts
from app.database.session import connect


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "test.db")
    apply_migrations(connection)
    seed_system_accounts(connection)
    yield connection
    connection.close()
